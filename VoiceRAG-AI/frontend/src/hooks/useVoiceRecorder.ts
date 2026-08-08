"use client";

import { useState, useRef, useCallback, useEffect } from "react";

export interface VoiceRecorderState {
  isRecording: boolean;
  isTranscribing: boolean;
  audioLevel: number; // 0 to 100
  recordingTime: number; // seconds
  error: string | null;
}

export interface VoiceRecorderControls extends VoiceRecorderState {
  startRecording: () => Promise<void>;
  stopRecording: () => Promise<Blob | null>;
  cancelRecording: () => void;
  setTranscribing: (val: boolean) => void;
}

export function useVoiceRecorder(): VoiceRecorderControls {
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  const [recordingTime, setRecordingTime] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const animFrameRef = useRef<number | null>(null);
  const timerIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const stopAudioTracks = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => {
        track.stop();
      });
      streamRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = null;
    }
    setAudioLevel(0);
  }, []);

  const cancelRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.onstop = null;
      mediaRecorderRef.current.stop();
    }
    stopAudioTracks();
    setIsRecording(false);
    setRecordingTime(0);
    audioChunksRef.current = [];
  }, [stopAudioTracks]);

  const stopRecording = useCallback((): Promise<Blob | null> => {
    return new Promise((resolve) => {
      const recorder = mediaRecorderRef.current;
      if (!recorder || recorder.state === "inactive") {
        stopAudioTracks();
        setIsRecording(false);
        resolve(null);
        return;
      }

      recorder.onstop = () => {
        const mimeType = recorder.mimeType || "audio/webm";
        const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
        stopAudioTracks();
        setIsRecording(false);
        audioChunksRef.current = [];
        resolve(audioBlob);
      };

      recorder.stop();
    });
  }, [stopAudioTracks]);

  const startRecording = useCallback(async () => {
    setError(null);
    audioChunksRef.current = [];

    if (
      typeof window === "undefined" ||
      !navigator?.mediaDevices?.getUserMedia ||
      typeof MediaRecorder === "undefined"
    ) {
      const msg = "Browser does not support MediaRecorder or microphone access.";
      setError(msg);
      throw new Error(msg);
    }

    try {
      // 1. Request microphone permission ONLY on button click
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      streamRef.current = stream;

      // 2. Select WebM/Opus if supported
      let mimeType = "audio/webm";
      if (MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) {
        mimeType = "audio/webm;codecs=opus";
      } else if (MediaRecorder.isTypeSupported("audio/webm")) {
        mimeType = "audio/webm";
      } else if (MediaRecorder.isTypeSupported("audio/mp4")) {
        mimeType = "audio/mp4";
      } else if (MediaRecorder.isTypeSupported("audio/ogg")) {
        mimeType = "audio/ogg";
      }

      const mediaRecorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.start(100);
      setIsRecording(true);
      setRecordingTime(0);

      // 3. Duration timer
      timerIntervalRef.current = setInterval(() => {
        setRecordingTime((prev) => prev + 1);
      }, 1000);

      // 4. Audio Visualizer Level
      try {
        const AudioCtx =
          window.AudioContext ||
          (window as unknown as { webkitAudioContext: typeof AudioContext })
            .webkitAudioContext;
        const audioCtx = new AudioCtx();
        audioContextRef.current = audioCtx;

        const sourceNode = audioCtx.createMediaStreamSource(stream);
        const analyserNode = audioCtx.createAnalyser();
        analyserNode.fftSize = 256;
        sourceNode.connect(analyserNode);

        const bufferLength = analyserNode.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);

        const analyze = () => {
          if (!streamRef.current) return;
          analyserNode.getByteFrequencyData(dataArray);

          let sum = 0;
          for (let i = 0; i < bufferLength; i++) {
            sum += dataArray[i];
          }
          const average = sum / bufferLength;
          const normalizedLevel = Math.min(100, Math.round((average / 128) * 100));

          setAudioLevel(normalizedLevel);
          animFrameRef.current = requestAnimationFrame(analyze);
        };

        analyze();
      } catch (audioCtxErr) {
        console.warn("AudioContext visualizer initialization skipped:", audioCtxErr);
      }
    } catch (err: unknown) {
      stopAudioTracks();
      setIsRecording(false);
      const msg =
        err instanceof Error
          ? err.message
          : "Microphone permission denied or device unavailable.";
      setError(msg);
      throw err;
    }
  }, [stopAudioTracks]);

  useEffect(() => {
    return () => {
      stopAudioTracks();
    };
  }, [stopAudioTracks]);

  return {
    isRecording,
    isTranscribing,
    audioLevel,
    recordingTime,
    error,
    startRecording,
    stopRecording,
    cancelRecording,
    setTranscribing: setIsTranscribing,
  };
}
