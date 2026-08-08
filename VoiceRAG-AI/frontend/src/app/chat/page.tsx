"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useChatStore } from "@/store/useChatStore";
import { useDocumentStore } from "@/store/documentStore";
import { useAudioPlayer } from "@/hooks/useAudioPlayer";
import { fetchDocuments } from "@/lib/api/documents";
import { ChatMessageItem } from "@/components/chat/ChatMessageItem";
import { ChatInput } from "@/components/chat/ChatInput";
import { VoiceSettingsModal } from "@/components/chat/VoiceSettingsModal";
import { PdfViewerModal } from "@/components/pdf/PdfViewerModal";
import { AIFeaturesStudioModal } from "@/components/ai/AIFeaturesStudioModal";
import { Toaster } from "@/components/ui/sonner";
import { MessageSquare, FileText, Sparkles, ArrowRight, Volume2, Settings } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SourceCitation } from "@/types/chat";

const STARTER_PROMPTS = [
  "Summarize the main points of the document.",
  "What are the key requirements or policies outlined?",
  "List any dates, deadlines, or actionable steps mentioned.",
  "What is the overall conclusion of this report?",
];

export default function ChatPage() {
  const { messages, isStreaming, autoSpeak, sendMessage, regenerateLastMessage } = useChatStore();
  const { documents, setDocuments } = useDocumentStore();
  const audioPlayer = useAudioPlayer();

  const [isVoiceSettingsOpen, setIsVoiceSettingsOpen] = useState(false);
  const [isAiStudioOpen, setIsAiStudioOpen] = useState(false);
  const [selectedPdf, setSelectedPdf] = useState<{
    documentId: string;
    documentName: string;
    initialPage: number;
    highlightSnippet?: string;
  } | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const lastSpokenMsgIdRef = useRef<string | null>(null);

  // Fetch document list on load so filter selector works
  useEffect(() => {
    fetchDocuments()
      .then((res) => setDocuments(res.documents))
      .catch(() => console.error("Failed to load documents for chat scope selector"));
  }, [setDocuments]);

  // Auto scroll to bottom when streaming tokens arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isStreaming]);

  // Automatic TTS playback when Voice Mode (autoSpeak) is ON
  useEffect(() => {
    if (!autoSpeak) return;
    const lastMsg = messages[messages.length - 1];
    if (
      lastMsg &&
      lastMsg.role === "assistant" &&
      !lastMsg.isStreaming &&
      !lastMsg.isError &&
      lastMsg.content &&
      lastMsg.id !== lastSpokenMsgIdRef.current
    ) {
      lastSpokenMsgIdRef.current = lastMsg.id;
      audioPlayer.play(lastMsg.id, lastMsg.content);
    }
  }, [messages, autoSpeak, audioPlayer]);

  const handleSelectCitation = (citation: SourceCitation) => {
    const doc = documents.find(
      (d) => d.document_id === citation.document_id || d.filename === citation.original_filename
    );

    const docId = doc ? doc.document_id : citation.document_id;
    const docName = citation.original_filename || (doc ? doc.filename : "Document.pdf");

    if (docId) {
      setSelectedPdf({
        documentId: docId,
        documentName: docName,
        initialPage: citation.page_number || 1,
        highlightSnippet: citation.snippet,
      });
    }
  };

  return (
    <div className="flex flex-col h-screen max-h-screen bg-zinc-50 text-zinc-900 overflow-hidden font-sans">
      {/* Top Header Bar matching reference image */}
      <header className="flex items-center justify-between px-6 py-3.5 border-b border-zinc-200 bg-white/90 backdrop-blur-md z-10 shrink-0">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-zinc-100 text-zinc-900 border border-zinc-200 shadow-2xs">
            <MessageSquare className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-base font-bold tracking-tight text-zinc-900 leading-none">VoiceRAG AI</h1>
            <p className="text-[11px] text-zinc-500 mt-0.5">
              Grounded retrieval & answers powered by your uploaded documents
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* AI Studio Trigger Button */}
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsAiStudioOpen(true)}
            className="h-8 text-xs gap-1.5 rounded-xl text-zinc-900 border-zinc-200 hover:bg-zinc-100 font-semibold"
            title="Open AI Studio (Summary, Flashcards, Quiz, Notes, Key Topics, FAQ)"
          >
            <Sparkles className="w-3.5 h-3.5 text-zinc-800" />
            <span className="hidden sm:inline">AI Studio</span>
          </Button>

          {/* TTS Voice Settings Trigger Button */}
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsVoiceSettingsOpen(true)}
            className="h-8 text-xs gap-1.5 rounded-xl text-zinc-700 border-zinc-200 hover:bg-zinc-100 font-medium"
            title="Voice Output Settings"
          >
            <Volume2 className="w-3.5 h-3.5 text-zinc-700" />
            <span className="hidden sm:inline">Voice Settings</span>
            <Settings className="w-3 h-3 text-zinc-400" />
          </Button>

          <Link href="/documents">
            <Button variant="default" size="sm" className="h-8 text-xs gap-1.5 rounded-xl bg-zinc-900 text-white hover:bg-zinc-800 font-semibold">
              <FileText className="w-3.5 h-3.5" />
              <span>Library ({documents.length})</span>
            </Button>
          </Link>
        </div>
      </header>

      {/* Main Messages Container */}
      <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-4">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center min-h-[70vh] text-center max-w-lg mx-auto space-y-6 px-4">
            <div className="w-16 h-16 rounded-2xl bg-white border border-zinc-200 text-zinc-900 flex items-center justify-center shadow-xs">
              <Sparkles className="w-8 h-8" />
            </div>

            <div className="space-y-2">
              <h2 className="text-xl font-bold tracking-tight text-zinc-900">Ask your documents anything</h2>
              <p className="text-xs md:text-sm text-zinc-500 leading-relaxed">
                Upload PDFs to your library and start asking questions. VoiceRAG AI retrieves relevant passages and synthesizes accurate, cited answers with interactive PDF source viewing.
              </p>
            </div>

            {documents.length === 0 ? (
              <div className="p-5 rounded-2xl bg-white border border-zinc-200 space-y-3 text-left w-full shadow-2xs">
                <div className="flex items-center gap-2 text-xs font-semibold text-zinc-900">
                  <FileText className="w-4 h-4 text-zinc-700" />
                  <span>No documents uploaded yet</span>
                </div>
                <p className="text-xs text-zinc-500">
                  Upload a PDF in the document library to begin querying with AI context.
                </p>
                <Link href="/documents" className="inline-block">
                  <Button size="sm" className="h-8 text-xs gap-1.5 bg-zinc-900 text-white rounded-xl">
                    <span>Go to Library</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </Button>
                </Link>
              </div>
            ) : (
              <div className="w-full space-y-2.5 text-left">
                <span className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider px-1">
                  Suggested Questions
                </span>
                <div className="grid grid-cols-1 gap-2">
                  {STARTER_PROMPTS.map((prompt, idx) => (
                    <button
                      key={idx}
                      onClick={() => sendMessage(prompt)}
                      type="button"
                      className="p-3.5 rounded-2xl border border-zinc-200 bg-white hover:bg-zinc-100/60 text-xs font-medium text-zinc-800 text-left transition-all hover:border-zinc-400 flex items-center justify-between group shadow-2xs"
                    >
                      <span>{prompt}</span>
                      <ArrowRight className="w-3.5 h-3.5 text-zinc-400 group-hover:text-zinc-900 transition-colors shrink-0 ml-2" />
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="max-w-4xl mx-auto space-y-4 pb-2">
            {messages.map((msg, index) => (
              <ChatMessageItem
                key={msg.id}
                message={msg}
                isLastAssistant={
                  msg.role === "assistant" &&
                  index === messages.length - 1
                }
                onRegenerate={regenerateLastMessage}
                audioPlayer={audioPlayer}
                onSelectCitation={handleSelectCitation}
              />
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Bottom Input Area */}
      <div className="max-w-4xl mx-auto w-full shrink-0">
        <ChatInput />
      </div>

      {/* Voice Output Settings Modal */}
      <VoiceSettingsModal
        isOpen={isVoiceSettingsOpen}
        onClose={() => setIsVoiceSettingsOpen(false)}
        voices={audioPlayer.voices}
        selectedVoice={audioPlayer.selectedVoice}
        onSelectVoice={audioPlayer.setSelectedVoice}
        speechRate={audioPlayer.speechRate}
        onSelectRate={audioPlayer.setSpeechRate}
      />

      {/* AI Features Studio Modal */}
      <AIFeaturesStudioModal
        isOpen={isAiStudioOpen}
        onClose={() => setIsAiStudioOpen(false)}
        documentName="All Documents"
      />

      {/* PDF Viewer Modal */}
      {selectedPdf && (
        <PdfViewerModal
          isOpen={!!selectedPdf}
          onClose={() => setSelectedPdf(null)}
          documentId={selectedPdf.documentId}
          documentName={selectedPdf.documentName}
          initialPage={selectedPdf.initialPage}
          highlightSnippet={selectedPdf.highlightSnippet}
        />
      )}

      <Toaster richColors position="bottom-right" />
    </div>
  );
}

