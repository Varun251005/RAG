"use client";

import React, { useState } from "react";
import { ChatMessage } from "@/types/chat";
import { MarkdownRenderer } from "./MarkdownRenderer";
import { SourceCitations } from "./SourceCitations";
import { TypingIndicator, StreamingCursor } from "./TypingIndicator";
import { Bot, User, Copy, Check, RotateCcw, AlertTriangle, Volume2, Pause, Square, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { AudioPlayerControls } from "@/hooks/useAudioPlayer";
import { SourceCitation } from "@/types/chat";

interface ChatMessageItemProps {
  message: ChatMessage;
  onRegenerate?: () => void;
  isLastAssistant?: boolean;
  audioPlayer?: AudioPlayerControls;
  onSelectCitation?: (citation: SourceCitation) => void;
}

export function ChatMessageItem({ message, onRegenerate, isLastAssistant, audioPlayer, onSelectCitation }: ChatMessageItemProps) {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === "user";

  const handleCopyMessage = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy message:", err);
    }
  };

  const isAudioActive = audioPlayer?.activeMessageId === message.id;
  const isAudioPlaying = isAudioActive && audioPlayer?.isPlaying;
  const isAudioPaused = isAudioActive && audioPlayer?.isPaused;
  const isAudioLoading = isAudioActive && audioPlayer?.isLoading;
  const audioError = isAudioActive ? audioPlayer?.error : null;

  const handleAudioClick = () => {
    if (!audioPlayer) return;
    if (isAudioPlaying) {
      audioPlayer.pause();
    } else if (isAudioPaused) {
      audioPlayer.resume();
    } else {
      audioPlayer.play(message.id, message.content);
    }
  };

  return (
    <div
      className={`flex gap-3.5 p-4 md:p-5 rounded-2xl transition-all ${
        isUser
          ? "bg-zinc-100/70 border border-zinc-200/80 ml-6 md:ml-20"
          : "bg-white border border-zinc-200 shadow-xs mr-4 md:mr-16"
      }`}
    >
      {/* Role Avatar */}
      <div
        className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-xs font-semibold shadow-xs ${
          isUser
            ? "bg-white text-zinc-900 border border-zinc-200"
            : "bg-zinc-900 text-white"
        }`}
      >
        {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
      </div>

      {/* Message Body */}
      <div className="flex-1 min-w-0 space-y-1.5">
        {/* Header line */}
        <div className="flex items-center justify-between text-xs text-zinc-500 mb-1">
          <span className="font-semibold text-zinc-900">
            {isUser ? "You" : "VoiceRAG Assistant"}
          </span>
          <span className="text-[11px] text-zinc-400 font-mono">{message.timestamp}</span>
        </div>

        {/* Content handling */}
        {message.isStreaming && !message.content ? (
          <TypingIndicator />
        ) : message.isError ? (
          <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs space-y-1">
            <div className="flex items-center gap-1.5 font-semibold">
              <AlertTriangle className="w-4 h-4" />
              <span>Generation Error</span>
            </div>
            <p>{message.errorDetail || message.content}</p>
          </div>
        ) : (
          <div className="relative text-zinc-800 text-xs md:text-sm leading-relaxed">
            <MarkdownRenderer content={message.content} />
            {message.isStreaming && <StreamingCursor />}
          </div>
        )}

        {/* Citations if available */}
        {!isUser && message.sources && message.sources.length > 0 && (
          <SourceCitations sources={message.sources} onSelectCitation={onSelectCitation} />
        )}

        {/* Footer Action Buttons */}
        {!isUser && !message.isStreaming && message.content && (
          <div className="flex flex-wrap items-center gap-2 pt-3 text-xs border-t border-zinc-100 mt-3">
            {/* Audio Speech Controls */}
            {audioPlayer && (
              <div className="flex items-center gap-1.5">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleAudioClick}
                  disabled={isAudioLoading}
                  className={`h-7 px-2.5 text-xs transition-colors rounded-lg border-zinc-200 font-medium ${
                    isAudioActive
                      ? "bg-zinc-900 text-white border-zinc-900"
                      : "bg-white text-zinc-700 hover:bg-zinc-50 hover:text-zinc-900"
                  }`}
                  title={
                    isAudioPlaying
                      ? "Pause playback"
                      : isAudioLoading
                      ? "Generating speech MP3..."
                      : "Listen to answer via Edge-TTS"
                  }
                >
                  {isAudioLoading ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin mr-1 text-zinc-400" />
                      <span>Generating...</span>
                    </>
                  ) : isAudioPlaying ? (
                    <>
                      <Volume2 className="w-3.5 h-3.5 mr-1 animate-pulse" />
                      <span>Playing...</span>
                    </>
                  ) : isAudioPaused ? (
                    <>
                      <Pause className="w-3.5 h-3.5 mr-1" />
                      <span>Resume</span>
                    </>
                  ) : (
                    <>
                      <Volume2 className="w-3.5 h-3.5 mr-1" />
                      <span>Listen</span>
                    </>
                  )}
                </Button>

                {/* Stop Button */}
                {isAudioActive && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={audioPlayer.stop}
                    className="h-7 px-2 text-xs text-zinc-500 hover:text-red-600 hover:bg-red-50 rounded-lg"
                    title="Stop playback"
                  >
                    <Square className="w-3 h-3 fill-current mr-1" />
                    <span>Stop</span>
                  </Button>
                )}

                {/* Audio Error indicator */}
                {audioError && (
                  <span className="text-[11px] text-red-600 font-medium flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" />
                    <span>{audioError}</span>
                  </span>
                )}
              </div>
            )}

            <Button
              variant="outline"
              size="sm"
              onClick={handleCopyMessage}
              className="h-7 px-2.5 text-xs text-zinc-700 border-zinc-200 hover:bg-zinc-50 rounded-lg font-medium"
              title="Copy message content"
            >
              {copied ? (
                <>
                  <Check className="w-3.5 h-3.5 text-emerald-600 mr-1" />
                  <span className="text-emerald-600 font-semibold">Copied</span>
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5 mr-1 text-zinc-500" />
                  <span>Copy</span>
                </>
              )}
            </Button>

            {isLastAssistant && onRegenerate && (
              <Button
                variant="outline"
                size="sm"
                onClick={onRegenerate}
                className="h-7 px-2.5 text-xs text-zinc-700 border-zinc-200 hover:bg-zinc-50 rounded-lg font-medium"
                title="Regenerate answer"
              >
                <RotateCcw className="w-3.5 h-3.5 mr-1 text-zinc-500" />
                <span>Regenerate</span>
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

