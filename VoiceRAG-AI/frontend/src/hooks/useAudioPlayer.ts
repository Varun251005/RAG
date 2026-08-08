"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { synthesizeVoiceSpeech } from "@/lib/api/voice";
import { fetchTTSVoices } from "@/lib/api/tts";
import { TTSVoice } from "@/types/tts";

export interface AudioPlayerState {
  activeMessageId: string | null;
  isPlaying: boolean;
  isPaused: boolean;
  isLoading: boolean;
  selectedVoice: string;
  speechRate: string; // e.g. "+0%", "+20%", "-10%"
  voices: TTSVoice[];
  error: string | null;
}

export interface AudioPlayerControls extends AudioPlayerState {
  play: (messageId: string, text: string) => Promise<void>;
  pause: () => void;
  resume: () => void;
  stop: () => void;
  setSelectedVoice: (voice: string) => void;
  setSpeechRate: (rate: string) => void;
}

export function useAudioPlayer(): AudioPlayerControls {
  const [activeMessageId, setActiveMessageId] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedVoice, setSelectedVoice] = useState("en-US-AvaNeural");
  const [speechRate, setSpeechRate] = useState("+0%");
  const [voices, setVoices] = useState<TTSVoice[]>([]);
  const [error, setError] = useState<string | null>(null);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const objectUrlRef = useRef<string | null>(null);

  // Fetch available voices on load
  useEffect(() => {
    fetchTTSVoices()
      .then((res) => {
        if (res.voices && res.voices.length > 0) {
          setVoices(res.voices);
        }
      })
      .catch((err) => console.error("Failed to load TTS voices list:", err));
  }, []);

  const revokeActiveObjectUrl = useCallback(() => {
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
  }, []);

  const stop = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.oncanplaythrough = null;
      audioRef.current.onended = null;
      audioRef.current.onerror = null;
      audioRef.current.src = "";
      audioRef.current = null;
    }
    revokeActiveObjectUrl();
    setActiveMessageId(null);
    setIsPlaying(false);
    setIsPaused(false);
    setIsLoading(false);
    setError(null);
  }, [revokeActiveObjectUrl]);

  const pause = useCallback(() => {
    if (audioRef.current && isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
      setIsPaused(true);
    }
  }, [isPlaying]);

  const resume = useCallback(() => {
    if (audioRef.current && isPaused) {
      audioRef.current
        .play()
        .then(() => {
          setIsPlaying(true);
          setIsPaused(false);
        })
        .catch((err) => {
          console.error("Resume audio playback failed:", err);
          stop();
        });
    }
  }, [isPaused, stop]);

  const play = useCallback(
    async (messageId: string, text: string) => {
      // If clicking play on currently active paused message, resume it
      if (activeMessageId === messageId && isPaused) {
        resume();
        return;
      }

      // 1. Stop any active audio and revoke Object URL
      stop();

      if (!text || !text.trim()) return;

      setActiveMessageId(messageId);
      setIsLoading(true);
      setError(null);

      try {
        // 2. Synthesize audio via POST /api/v1/voice/synthesize
        const audioBlob = await synthesizeVoiceSpeech({
          text: text.trim(),
          voice: selectedVoice,
        });

        if (!audioBlob || audioBlob.size === 0) {
          throw new Error("Received empty audio response from backend.");
        }

        // 3. Create browser Object URL
        const streamUrl = URL.createObjectURL(audioBlob);
        objectUrlRef.current = streamUrl;

        const audio = new Audio(streamUrl);
        audioRef.current = audio;

        audio.oncanplaythrough = () => {
          setIsLoading(false);
          setIsPlaying(true);
          audio
            .play()
            .then(() => {
              setIsPlaying(true);
            })
            .catch((err: unknown) => {
              console.warn("Browser autoplay restricted or playback failed:", err);
              setError("Browser prevented automatic audio playback. Click Listen to play.");
              setIsLoading(false);
              setIsPlaying(false);
            });
        };

        audio.onended = () => {
          stop();
        };

        audio.onerror = (e) => {
          console.error("Audio playback error event:", e);
          setError("Could not generate or play speech audio.");
          stop();
        };

        audio.load();
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Text-to-speech synthesis failed.";
        console.error("Failed to initiate TTS audio playback:", msg);
        setError("⚠️ Could not generate speech");
        stop();
      }
    },
    [activeMessageId, isPaused, resume, selectedVoice, stop]
  );

  useEffect(() => {
    return () => {
      stop();
    };
  }, [stop]);

  return {
    activeMessageId,
    isPlaying,
    isPaused,
    isLoading,
    selectedVoice,
    speechRate,
    voices,
    error,
    play,
    pause,
    resume,
    stop,
    setSelectedVoice,
    setSpeechRate,
  };
}
