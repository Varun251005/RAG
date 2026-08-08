"use client";

import React from "react";
import Link from "next/link";
import { MessageSquare, FileText, Sparkles, ArrowRight, ShieldCheck, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function Home() {
  return (
    <div className="flex flex-col min-h-screen bg-background text-foreground">
      {/* Header */}
      <header className="px-6 py-4 border-b border-border flex items-center justify-between max-w-6xl mx-auto w-full">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-xl bg-primary text-primary-foreground font-bold">
            <Sparkles className="w-5 h-5" />
          </div>
          <span className="font-bold text-lg tracking-tight">VoiceRAG AI</span>
        </div>

        <nav className="flex items-center gap-3">
          <Link href="/documents">
            <Button variant="ghost" size="sm" className="text-xs gap-1.5">
              <FileText className="w-4 h-4" />
              <span>Library</span>
            </Button>
          </Link>
          <Link href="/chat">
            <Button size="sm" className="text-xs gap-1.5">
              <MessageSquare className="w-4 h-4" />
              <span>Launch Chat</span>
            </Button>
          </Link>
        </nav>
      </header>

      {/* Hero Section */}
      <main className="flex-1 flex flex-col items-center justify-center text-center px-4 py-20 max-w-4xl mx-auto space-y-8">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 text-xs font-semibold text-primary">
          <Zap className="w-3.5 h-3.5" />
          <span>Production-Grade Voice & Document AI</span>
        </div>

        <h1 className="text-4xl md:text-6xl font-extrabold tracking-tight leading-tight">
          Talk to your documents with <span className="text-primary">grounded AI</span>
        </h1>

        <p className="text-lg text-muted-foreground max-w-2xl leading-relaxed">
          Upload PDF documents, extract precise contextual answers with Gemini & ChromaDB vector search, and interact via voice or text in real time.
        </p>

        <div className="flex flex-col sm:flex-row items-center gap-4 pt-4">
          <Link href="/chat">
            <Button size="lg" className="h-12 px-6 text-sm font-semibold gap-2 rounded-xl shadow-lg">
              <MessageSquare className="w-5 h-5" />
              <span>Start Chatting</span>
              <ArrowRight className="w-4 h-4" />
            </Button>
          </Link>
          <Link href="/documents">
            <Button variant="outline" size="lg" className="h-12 px-6 text-sm font-semibold gap-2 rounded-xl">
              <FileText className="w-5 h-5" />
              <span>Manage Documents</span>
            </Button>
          </Link>
        </div>

        {/* Features grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-16 text-left w-full">
          <div className="p-5 rounded-2xl bg-card border border-border space-y-2">
            <div className="w-10 h-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center font-semibold">
              <Zap className="w-5 h-5" />
            </div>
            <h3 className="font-semibold text-base">Real-time Streaming</h3>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Token-by-token Server-Sent Events (SSE) stream responses instantaneously with source citations.
            </p>
          </div>

          <div className="p-5 rounded-2xl bg-card border border-border space-y-2">
            <div className="w-10 h-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center font-semibold">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <h3 className="font-semibold text-base">Strict Document Grounding</h3>
            <p className="text-xs text-muted-foreground leading-relaxed">
              ChromaDB vector search retrieves exact text chunks to prevent AI hallucination.
            </p>
          </div>

          <div className="p-5 rounded-2xl bg-card border border-border space-y-2">
            <div className="w-10 h-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center font-semibold">
              <FileText className="w-5 h-5" />
            </div>
            <h3 className="font-semibold text-base">Markdown & Code Blocks</h3>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Rich markdown formatting with syntax-highlighted code and one-click copy buttons.
            </p>
          </div>
        </div>
      </main>

      <footer className="py-6 border-t border-border text-center text-xs text-muted-foreground">
        VoiceRAG AI — Built with Next.js 15, FastAPI, LangChain & Gemini.
      </footer>
    </div>
  );
}
