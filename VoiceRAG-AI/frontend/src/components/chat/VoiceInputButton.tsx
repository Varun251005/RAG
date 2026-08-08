"use client";

import React from "react";
import { Mic, Square, X, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useVoiceRecorder } from "@/hooks/useVoiceRecorder";
import { transcribeVoiceAudio } from "@/lib/api/voice";
import { toast } from "sonner";

interface VoiceInputButtonProps {
  onTranscribed: (text: string) => void;
  disabled?: boolean;
}

export function VoiceInputButton({ onTranscribed, disabled }: VoiceInputButtonProps) {
  const {
    isRecording,
    isTranscribing,
    audioLevel,
    recordingTime,
    startRecording,
    stopRecording,
    cancelRecording,
    setTranscribing,
  } = useVoiceRecorder();

  const handleStart = async () => {
    if (disabled) return;
    try {
      await startRecording();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Microphone permission denied.";
      toast.error(msg);
    }
  };

  const handleStopAndTranscribe = async () => {
    const audioBlob = await stopRecording();
    if (!audioBlob || audioBlob.size < 100) {
      toast.error("Recording was empty or too short.");
      return;
    }

    try {
      setTranscribing(true);
      toast.info("Transcribing spoken audio...");
      const res = await transcribeVoiceAudio(audioBlob);

      if (res.text && res.text.trim()) {
        onTranscribed(res.text.trim());
        toast.success("Voice transcribed! Review text in input before sending.");
      } else {
        toast.warning("No speech recognized in recording.");
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Speech-to-text transcription failed.";
      toast.error(msg);
    } finally {
      setTranscribing(false);
    }
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  if (isTranscribing) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-primary/10 border border-primary/20 text-xs text-primary font-medium animate-pulse">
        <Loader2 className="w-4 h-4 animate-spin shrink-0" />
        <span>Transcribing...</span>
      </div>
    );
  }

  if (isRecording) {
    return (
      <div className="flex items-center gap-2 px-2 py-1 rounded-xl bg-destructive/10 border border-destructive/30 text-destructive text-xs font-medium animate-in fade-in">
        {/* Animated pulse indicator */}
        <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-destructive/20 text-destructive">
          <span className="w-2 h-2 rounded-full bg-destructive animate-ping" />
          <span className="font-mono text-xs font-semibold">{formatTime(recordingTime)}</span>
        </div>

        {/* Audio Level Visualizer */}
        <div className="flex items-center gap-0.5 h-5 px-1">
          {[0.4, 0.7, 1.0, 0.6, 0.8].map((scale, i) => {
            const h = Math.max(4, Math.round((audioLevel / 100) * 18 * scale));
            return (
              <div
                key={i}
                className="w-1 bg-destructive/80 rounded-full transition-all duration-75"
                style={{ height: `${h}px` }}
              />
            );
          })}
        </div>

        {/* Stop and Transcribe Button */}
        <Button
          type="button"
          size="sm"
          onClick={handleStopAndTranscribe}
          className="h-7 px-2.5 text-xs bg-destructive text-destructive-foreground hover:bg-destructive/90 gap-1 rounded-md"
          title="Done — Transcribe recording"
        >
          <Square className="w-3 h-3 fill-current" />
          <span>Stop</span>
        </Button>

        {/* Cancel Button */}
        <Button
          type="button"
          size="icon"
          variant="ghost"
          onClick={cancelRecording}
          className="h-7 w-7 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-md"
          title="Cancel recording"
        >
          <X className="w-3.5 h-3.5" />
        </Button>
      </div>
    );
  }

  return (
    <Button
      type="button"
      size="icon"
      variant="ghost"
      onClick={handleStart}
      disabled={disabled}
      className="h-9 w-9 rounded-lg text-muted-foreground hover:text-primary hover:bg-primary/10 transition-colors shrink-0"
      title="Voice Input (Speech-to-Text)"
    >
      <Mic className="w-4 h-4" />
    </Button>
  );
}
