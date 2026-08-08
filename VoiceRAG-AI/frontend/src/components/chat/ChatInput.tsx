"use client";

import React, { useState, useRef, useEffect } from "react";
import { Send, Square, Trash2, FileText, Volume2, VolumeX, X } from "lucide-react";
import { useChatStore } from "@/store/useChatStore";
import { useDocumentStore } from "@/store/documentStore";
import { VoiceInputButton } from "./VoiceInputButton";
import { DocumentSelectorButton } from "./DocumentSelectorButton";

export function ChatInput() {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const {
    sendMessage,
    isStreaming,
    cancelStream,
    clearChat,
    activeDocumentId,
    setActiveDocumentId,
    autoSpeak,
    setAutoSpeak,
    messages,
  } = useChatStore();

  const { documents } = useDocumentStore();

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`;
    }
  }, [input]);

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!input.trim() || isStreaming) return;
    const q = input;
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
    await sendMessage(q);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleTranscribedText = async (text: string) => {
    if (!text || !text.trim()) return;

    if (autoSpeak) {
      setInput("");
      await sendMessage(text.trim());
    } else {
      setInput((prev) => (prev ? `${prev} ${text.trim()}` : text.trim()));
    }
  };

  const selectedDocument = documents.find((d) => d.document_id === activeDocumentId);

  return (

    <div className="bg-transparent p-3 md:p-4 space-y-2">
      {/* Top Toolbar: Voice Mode & Clear Chat */}
      <div className="flex items-center justify-between gap-2 text-xs px-1">
        <div className="flex items-center gap-2">
          {/* Voice Mode Toggle Button */}
          <button
            type="button"
            onClick={() => setAutoSpeak(!autoSpeak)}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-medium transition-all border ${
              autoSpeak
                ? "bg-zinc-900 text-white border-zinc-900 shadow-2xs"
                : "bg-white text-zinc-600 border-zinc-200 hover:bg-zinc-100 hover:text-zinc-900"
            }`}
          >
            {autoSpeak ? <Volume2 className="w-3 h-3" /> : <VolumeX className="w-3 h-3 text-zinc-400" />}
            <span>Voice Mode: {autoSpeak ? "ON" : "OFF"}</span>
          </button>
        </div>

        {/* Clear Chat Button */}
        {messages.length > 0 && (
          <button
            type="button"
            onClick={clearChat}
            disabled={isStreaming}
            className="flex items-center gap-1 px-2 py-1 text-[11px] text-zinc-400 hover:text-zinc-900 hover:bg-zinc-100 rounded-lg transition-colors shrink-0 font-medium"
            title="Clear all messages"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Clear Chat</span>
          </button>
        )}
      </div>

      {/* Main Floating Input Form */}
      <form
        onSubmit={handleSubmit}
        className="relative flex items-center gap-2 bg-white border border-zinc-200 rounded-full px-3 py-2 shadow-sm focus-within:ring-2 focus-within:ring-zinc-900/10 focus-within:border-zinc-400 transition-all"
      >
        {/* Document Selector (+) Button & Active PDF Badge */}
        <div className="flex items-center gap-1.5 shrink-0">
          <DocumentSelectorButton />

          {selectedDocument && (
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-zinc-900 text-white text-[11px] font-semibold max-w-[170px] truncate shadow-2xs animate-in fade-in zoom-in-95">
              <FileText className="w-3 h-3 shrink-0 text-zinc-300" />
              <span className="truncate">{selectedDocument.filename}</span>
              <button
                type="button"
                onClick={() => setActiveDocumentId(null)}
                className="hover:text-zinc-300 text-zinc-400 ml-0.5"
                title="Remove PDF filter"
              >
                <X className="w-3 h-3" />
              </button>
            </span>
          )}
        </div>

        {/* Text Input */}
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            selectedDocument
              ? `Ask a question about "${selectedDocument.filename}"...`
              : `Ask anything across all ${documents.length} uploaded PDF documents...`
          }
          rows={1}
          className="w-full resize-none bg-transparent border-0 px-2 py-1 text-xs md:text-sm text-zinc-900 focus:outline-none focus:ring-0 max-h-[140px] min-h-[24px] placeholder:text-zinc-400 leading-normal"
        />

        <div className="flex items-center gap-1.5 shrink-0 pr-1">
          {/* Voice Input STT Microphone Button */}
          <VoiceInputButton
            disabled={isStreaming}
            onTranscribed={handleTranscribedText}
          />

          {/* Send / Stop Streaming Button */}
          {isStreaming ? (
            <button
              type="button"
              onClick={cancelStream}
              className="flex items-center justify-center w-9 h-9 shrink-0 rounded-full bg-zinc-900 text-white hover:bg-zinc-800 transition-colors shadow-sm"
              title="Stop generation"
            >
              <Square className="w-3.5 h-3.5 fill-current" />
            </button>
          ) : (
            <button
              type="submit"
              disabled={!input.trim()}
              className="flex items-center justify-center w-9 h-9 shrink-0 rounded-full bg-zinc-900 text-white hover:bg-zinc-800 disabled:opacity-30 disabled:hover:bg-zinc-900 transition-all shadow-sm"
              title="Send question"
            >
              <Send className="w-4 h-4" />
            </button>
          )}
        </div>
      </form>
    </div>
  );
}

