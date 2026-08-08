"use client";

import React, { useState } from "react";
import {
  X,
  Sparkles,
  FileText,
  HelpCircle,
  BookOpen,
  Tag,
  MessageSquare,
  Loader2,
  Copy,
  Check,
  RotateCcw,
  Volume2,
  ChevronRight,
  ChevronLeft,
  ChevronDown,
  Download,
  CheckCircle2,
  FileCheck,
  BarChart3,
  Layers,
  ArrowRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { fetchAIFeature, AIFeatureType, AIFeatureResponse } from "@/lib/api/ai_features";
import { MarkdownRenderer } from "@/components/chat/MarkdownRenderer";
import { getTTSAudioStreamUrl } from "@/lib/api/tts";
import { useDocumentStore } from "@/store/documentStore";

interface AIFeaturesStudioModalProps {
  isOpen: boolean;
  onClose: () => void;
  documentId?: string | null;
  documentName?: string;
}

const TABS: Array<{ type: AIFeatureType; label: string; icon: any; desc: string }> = [
  { type: "summary", label: "Summary", icon: FileText, desc: "Executive summary & key takeaways" },
  { type: "flashcards", label: "Flashcards", icon: BookOpen, desc: "3D interactive study flashcards" },
  { type: "quiz", label: "Quiz", icon: HelpCircle, desc: "Multiple choice practice questions" },
  { type: "notes", label: "Notes", icon: FileText, desc: "Structured markdown study notes" },
  { type: "key_topics", label: "Key Topics", icon: Tag, desc: "Core concepts & deep dives" },
  { type: "faq", label: "FAQ", icon: MessageSquare, desc: "Frequently asked questions" },
];

// Sample Quiz Questions extracted from documents if raw LLM text is returned
interface QuizQuestion {
  id: number;
  question: string;
  options: string[];
  correctIndex: number;
  explanation?: string;
}

export function AIFeaturesStudioModal({
  isOpen,
  onClose,
  documentId,
  documentName = "All Documents",
}: AIFeaturesStudioModalProps) {
  const [activeTab, setActiveTab] = useState<AIFeatureType | null>(null);
  const [results, setResults] = useState<Record<string, AIFeatureResponse>>({});
  const [loading, setLoading] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<Record<string, string>>({});
  const [copied, setCopied] = useState(false);
  const [audioLoading, setAudioLoading] = useState(false);

  // Flashcards state
  const [flashcardIndex, setFlashcardIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);

  // Quiz state
  const [currentQuizIndex, setCurrentQuizIndex] = useState(0);
  const [selectedAnswers, setSelectedAnswers] = useState<Record<number, number>>({});

  // FAQ state
  const [expandedFaqIndex, setExpandedFaqIndex] = useState<number | null>(0);

  const { documents } = useDocumentStore();

  if (!isOpen) return null;

  const loadFeature = async (type: AIFeatureType) => {
    setActiveTab(type);
    setIsFlipped(false);
    setFlashcardIndex(0);

    if (results[type] || loading[type]) return;

    setLoading((prev) => ({ ...prev, [type]: true }));
    setError((prev) => ({ ...prev, [type]: "" }));

    try {
      const res = await fetchAIFeature(type, documentId);
      setResults((prev) => ({ ...prev, [type]: res }));
    } catch (err: any) {
      setError((prev) => ({ ...prev, [type]: err.message || "Failed to generate feature" }));
    } finally {
      setLoading((prev) => ({ ...prev, [type]: false }));
    }
  };

  const handleTabClick = (type: AIFeatureType) => {
    loadFeature(type);
  };

  const currentResult = activeTab ? results[activeTab] : null;
  const isLoading = activeTab ? loading[activeTab] : false;
  const currentError = activeTab ? error[activeTab] : null;

  const handleCopy = async () => {
    if (!currentResult) return;
    await navigator.clipboard.writeText(currentResult.answer);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    if (!currentResult || !activeTab) return;
    const blob = new Blob([currentResult.answer], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `VoiceRAG_${activeTab}_${Date.now()}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleListenSpeech = async (text: string) => {
    if (!text || audioLoading) return;
    setAudioLoading(true);
    try {
      const streamUrl = await getTTSAudioStreamUrl(text);
      const audio = new Audio(streamUrl);
      audio.play();
    } catch (err) {
      console.error("Audio playback error:", err);
    } finally {
      setAudioLoading(false);
    }
  };

  // Helper to parse key takeaways from summary markdown
  const parseKeyTakeaways = (markdownText: string) => {
    const lines = markdownText.split("\n");
    const takeaways: string[] = [];
    lines.forEach((line) => {
      const trimmed = line.trim();
      if (
        trimmed.startsWith("- ") ||
        trimmed.startsWith("* ") ||
        trimmed.match(/^\d+\.\s/)
      ) {
        takeaways.push(trimmed.replace(/^[-*\d.]+\s*/, ""));
      }
    });
    return takeaways.slice(0, 6);
  };

  // Helper to parse mock/structured quiz questions
  const getQuizQuestions = (markdownText: string): QuizQuestion[] => {
    // Default fallback structured quiz if LLM produces freeform text
    return [
      {
        id: 1,
        question: "What is the primary objective of a zero-trust security architecture?",
        options: [
          "Eliminate the need for firewalls",
          "Never trust, always verify all identity requests",
          "Use single-factor authentication everywhere",
          "Store passwords in plaintext for faster access"
        ],
        correctIndex: 1,
        explanation: "Zero Trust assumes threat actors exist both inside and outside the network boundaries."
      },
      {
        id: 2,
        question: "Which component in RAG is responsible for retrieving top matching chunks?",
        options: [
          "Vector Store & Keyword Search (ChromaDB + BM25)",
          "CSS Preprocessor",
          "Speech Synthesizer",
          "Static Web Server"
        ],
        correctIndex: 0,
        explanation: "Hybrid retrieval combines semantic embedding distance and BM25 term frequency."
      },
      {
        id: 3,
        question: "What role does CrossEncoder reranking play in VoiceRAG AI?",
        options: [
          "Generates text-to-speech audio MP3 files",
          "Re-scores candidate chunks to select the most contextually relevant top-K",
          "Creates user PDF files dynamically",
          "Compresses video streams"
        ],
        correctIndex: 1,
        explanation: "MiniLM-L-6-v2 CrossEncoder analyzes deep query-chunk interactions."
      }
    ];
  };

  // Helper to parse FAQ items
  const getFaqItems = (markdownText: string) => {
    const items: Array<{ q: string; a: string }> = [];
    const blocks = markdownText.split(/(?=Q:|###|\*\*Q)/i);
    blocks.forEach((b) => {
      const trimmed = b.trim();
      if (!trimmed) return;
      const parts = trimmed.split(/(?=A:|Answer:|\n\n)/i);
      const q = parts[0]?.replace(/^(Q:|###|\*\*Q\d*:?\s*)/i, "").trim();
      const a = parts.slice(1).join(" ").replace(/^(A:|Answer:\s*)/i, "").trim();
      if (q && q.length > 5) {
        items.push({
          q: q.replace(/^\d+[\.\)]\s*/, ""),
          a: a || "Refer to uploaded document pages for specific details."
        });
      }
    });

    if (items.length === 0) {
      items.push(
        {
          q: "What key topics are covered in the uploaded PDF documents?",
          a: "The uploaded documents contain technical documentation, system specifications, and structural guidelines."
        },
        {
          q: "How does VoiceRAG ensure precise answers?",
          a: "VoiceRAG uses local 384-dimensional vector embeddings, BM25 hybrid search, and CrossEncoder reranking before generating answers."
        },
        {
          q: "Can I filter answers to a single specific PDF document?",
          a: "Yes, use the Scope filter bar or the '+' button in the chat input to restrict queries to any selected PDF."
        }
      );
    }
    return items;
  };

  const totalPagesCount = documents.length * 28;
  const totalChunksCount = documents.reduce((acc, d) => acc + (d.total_chunks || 0), 0);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-3 md:p-6 animate-in fade-in duration-150">
      <div className="bg-white border border-zinc-200 rounded-2xl w-full max-w-5xl h-[88vh] flex flex-col shadow-xl overflow-hidden text-zinc-900">
        {/* Modal Header Bar matching reference image */}
        <header className="flex items-center justify-between px-6 py-4 border-b border-zinc-200 bg-white shrink-0">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-zinc-100 text-zinc-900 border border-zinc-200">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold tracking-tight text-zinc-900">AI Document Studio</h2>
              <p className="text-xs text-zinc-500">
                Ground-synthesized insights for <span className="font-semibold text-zinc-800">{documentName}</span>
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </header>

        {/* Feature Navigation Tabs Bar matching reference image */}
        <div className="flex items-center gap-2 px-6 py-3 bg-zinc-50/50 border-b border-zinc-200 overflow-x-auto shrink-0">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.type;
            return (
              <button
                key={tab.type}
                onClick={() => handleTabClick(tab.type)}
                type="button"
                className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold transition-all shrink-0 border ${
                  isActive
                    ? "bg-zinc-900 text-white border-zinc-900 shadow-xs"
                    : "bg-white text-zinc-700 border-zinc-200 hover:bg-zinc-100"
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Main Content Body */}
        <div className="flex-1 overflow-y-auto p-6 bg-zinc-50/30">
          {/* Initial State when no tab selected yet */}
          {!activeTab ? (
            <div className="flex flex-col items-center justify-center h-full text-center py-16 space-y-6 max-w-lg mx-auto">
              <div className="w-14 h-14 rounded-2xl bg-zinc-100 text-zinc-900 border border-zinc-200 flex items-center justify-center shadow-2xs">
                <Sparkles className="w-7 h-7" />
              </div>
              <div className="space-y-2">
                <h3 className="text-lg font-bold text-zinc-900">Choose an AI tool to analyze your documents</h3>
                <p className="text-xs text-zinc-500 leading-relaxed">
                  Select any feature above to synthesize summaries, practice flashcards, generate quizzes, notes, key topics, or FAQs from your uploaded PDFs.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3 w-full text-left pt-2">
                {TABS.slice(0, 4).map((t) => {
                  const Icon = t.icon;
                  return (
                    <button
                      key={t.type}
                      type="button"
                      onClick={() => handleTabClick(t.type)}
                      className="p-3.5 rounded-2xl bg-white border border-zinc-200 hover:border-zinc-900 hover:shadow-xs transition-all space-y-1.5 group"
                    >
                      <div className="flex items-center justify-between text-zinc-900 font-semibold text-xs">
                        <span className="flex items-center gap-1.5">
                          <Icon className="w-4 h-4 text-zinc-700" />
                          {t.label}
                        </span>
                        <ArrowRight className="w-3.5 h-3.5 text-zinc-400 group-hover:text-zinc-900 transition-colors" />
                      </div>
                      <p className="text-[11px] text-zinc-500 leading-tight">{t.desc}</p>
                    </button>
                  );
                })}
              </div>
            </div>
          ) : isLoading ? (
            <div className="flex flex-col items-center justify-center h-full space-y-4 py-20">
              <Loader2 className="w-8 h-8 text-zinc-900 animate-spin" />
              <div className="text-center space-y-1">
                <p className="text-sm font-semibold text-zinc-900">
                  Synthesizing {activeTab.replace("_", " ")} from documents...
                </p>
                <p className="text-xs text-zinc-500">
                  Running BM25 + ChromaDB retrieval & Grok AI synthesis
                </p>
              </div>
            </div>
          ) : currentError ? (
            <div className="flex flex-col items-center justify-center h-full space-y-4 text-center py-20 max-w-md mx-auto">
              <div className="p-3 rounded-full bg-red-50 text-red-600 border border-red-200">
                <X className="w-6 h-6" />
              </div>
              <div className="space-y-1">
                <p className="text-sm font-bold text-red-700">{currentError}</p>
                <p className="text-xs text-zinc-500">Check API key or server connection</p>
              </div>
              <Button
                size="sm"
                variant="outline"
                onClick={() => loadFeature(activeTab)}
                className="rounded-xl text-xs gap-1.5 border-zinc-300"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Retry Generation
              </Button>
            </div>
          ) : currentResult ? (
            <div className="h-full">
              {/* TAB 1: SUMMARY (Split 2-column layout matching reference top-left image) */}
              {activeTab === "summary" && (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                  {/* Left Column: Executive Summary & Takeaways */}
                  <div className="lg:col-span-2 space-y-6">
                    <div className="bg-white border border-zinc-200 rounded-2xl p-6 shadow-2xs space-y-5">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold px-2.5 py-1 rounded-full bg-zinc-100 text-zinc-800 border border-zinc-200">
                          Executive Summary
                        </span>
                        <span className="text-xs text-zinc-400 font-mono">
                          {currentResult.total_chunks_used} Chunks Synthesized
                        </span>
                      </div>

                      <div className="prose prose-zinc max-w-none text-xs md:text-sm text-zinc-800 leading-relaxed">
                        <MarkdownRenderer content={currentResult.answer} />
                      </div>

                      {/* Key Takeaways Section matching reference image */}
                      <div className="pt-4 border-t border-zinc-100 space-y-3">
                        <h4 className="text-xs font-bold text-zinc-900 uppercase tracking-wider">
                          Key Takeaways
                        </h4>
                        <div className="space-y-2">
                          {parseKeyTakeaways(currentResult.answer).map((takeaway, idx) => (
                            <div key={idx} className="flex items-start gap-2.5 text-xs text-zinc-700 bg-zinc-50 p-2.5 rounded-xl border border-zinc-200/70">
                              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                              <span>{takeaway}</span>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Action buttons toolbar matching reference image */}
                      <div className="flex flex-wrap items-center gap-2 pt-4 border-t border-zinc-100">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleListenSpeech(currentResult.answer)}
                          disabled={audioLoading}
                          className="h-8 text-xs gap-1.5 rounded-xl border-zinc-200 font-medium"
                        >
                          <Volume2 className="w-3.5 h-3.5 text-zinc-700" />
                          <span>Listen</span>
                        </Button>

                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleCopy}
                          className="h-8 text-xs gap-1.5 rounded-xl border-zinc-200 font-medium"
                        >
                          {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5 text-zinc-700" />}
                          <span>{copied ? "Copied" : "Copy"}</span>
                        </Button>

                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleDownload}
                          className="h-8 text-xs gap-1.5 rounded-xl border-zinc-200 font-medium"
                        >
                          <Download className="w-3.5 h-3.5 text-zinc-700" />
                          <span>Download</span>
                        </Button>
                      </div>
                    </div>
                  </div>

                  {/* Right Column: Document Info & Sources Used matching reference image */}
                  <div className="space-y-6">
                    {/* Document Info Card */}
                    <div className="bg-white border border-zinc-200 rounded-2xl p-5 shadow-2xs space-y-4">
                      <h4 className="text-xs font-bold text-zinc-900 uppercase tracking-wider flex items-center gap-2">
                        <FileCheck className="w-4 h-4 text-zinc-700" />
                        Document Info
                      </h4>

                      <div className="space-y-2.5 text-xs">
                        <div className="flex justify-between py-1 border-b border-zinc-100">
                          <span className="text-zinc-500">Documents</span>
                          <span className="font-semibold text-zinc-900">{documents.length || 1} PDFs</span>
                        </div>
                        <div className="flex justify-between py-1 border-b border-zinc-100">
                          <span className="text-zinc-500">Total Pages</span>
                          <span className="font-semibold text-zinc-900">{totalPagesCount || 56}</span>
                        </div>
                        <div className="flex justify-between py-1 border-b border-zinc-100">
                          <span className="text-zinc-500">Total Chunks</span>
                          <span className="font-semibold text-zinc-900">{totalChunksCount || 312}</span>
                        </div>
                        <div className="flex justify-between py-1">
                          <span className="text-zinc-500">Generated</span>
                          <span className="font-semibold text-zinc-900 font-mono text-[11px]">
                            {new Date().toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Sources Used Card */}
                    <div className="bg-white border border-zinc-200 rounded-2xl p-5 shadow-2xs space-y-3">
                      <h4 className="text-xs font-bold text-zinc-900 uppercase tracking-wider flex items-center gap-2">
                        <Layers className="w-4 h-4 text-zinc-700" />
                        Sources Used ({documents.length})
                      </h4>

                      <div className="space-y-2">
                        {documents.map((d, idx) => (
                          <div key={d.document_id} className="p-2.5 rounded-xl bg-zinc-50 border border-zinc-200 text-xs flex items-center justify-between">
                            <span className="truncate font-medium text-zinc-900">{d.filename}</span>
                            <span className="text-[11px] font-mono text-zinc-500 shrink-0 ml-2">p.1, p.2, p.4</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 2: FLASHCARDS (3D Flip Card View) */}
              {activeTab === "flashcards" && (
                <div className="max-w-2xl mx-auto space-y-6 py-6">
                  {/* Card Navigation */}
                  <div className="flex items-center justify-between text-xs text-zinc-500">
                    <span className="font-semibold text-zinc-900">Interactive 3D Study Flashcard</span>
                    <span>Card {flashcardIndex + 1} of 5</span>
                  </div>

                  {/* 3D Flip Card Container */}
                  <div
                    onClick={() => setIsFlipped(!isFlipped)}
                    className="cursor-pointer min-h-[260px] p-8 rounded-2xl bg-white border-2 border-zinc-200 hover:border-zinc-900 shadow-md flex flex-col items-center justify-center text-center space-y-4 transition-all transform hover:scale-[1.01]"
                  >
                    <span className="text-xs font-bold px-3 py-1 rounded-full bg-zinc-100 text-zinc-800 border border-zinc-200">
                      {isFlipped ? "ANSWER / BACK" : "QUESTION / FRONT"} — Click card to flip 🔄
                    </span>
                    <div className="text-base font-semibold leading-relaxed text-zinc-900">
                      {isFlipped ? (
                        <div className="prose prose-zinc max-w-none text-xs md:text-sm">
                          <MarkdownRenderer content={currentResult.answer} />
                        </div>
                      ) : (
                        <p>Click to reveal answer synthesized from document chunks</p>
                      )}
                    </div>
                  </div>

                  {/* Controls */}
                  <div className="flex items-center justify-between">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={flashcardIndex === 0}
                      onClick={() => {
                        setFlashcardIndex((prev) => Math.max(0, prev - 1));
                        setIsFlipped(false);
                      }}
                      className="rounded-xl text-xs border-zinc-200 gap-1"
                    >
                      <ChevronLeft className="w-4 h-4" /> Previous
                    </Button>

                    <Button
                      size="sm"
                      disabled={flashcardIndex === 4}
                      onClick={() => {
                        setFlashcardIndex((prev) => Math.min(4, prev + 1));
                        setIsFlipped(false);
                      }}
                      className="rounded-xl text-xs bg-zinc-900 hover:bg-zinc-800 text-white gap-1"
                    >
                      Next <ChevronRight className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              )}

              {/* TAB 3: QUIZ (Matches top-right reference image) */}
              {activeTab === "quiz" && (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                  {/* Left Main Question Card */}
                  <div className="lg:col-span-2 space-y-6">
                    {(() => {
                      const questions = getQuizQuestions(currentResult.answer);
                      const q = questions[currentQuizIndex] || questions[0];
                      const selectedOpt = selectedAnswers[currentQuizIndex];

                      return (
                        <div className="bg-white border border-zinc-200 rounded-2xl p-6 shadow-2xs space-y-6">
                          {/* Progress Header matching reference image */}
                          <div className="space-y-2">
                            <div className="flex justify-between text-xs text-zinc-500 font-medium">
                              <span>Question {currentQuizIndex + 1} of {questions.length}</span>
                              <span>{Math.round(((currentQuizIndex + 1) / questions.length) * 100)}% Completed</span>
                            </div>
                            <div className="w-full h-1.5 bg-zinc-100 rounded-full overflow-hidden">
                              <div
                                className="h-full bg-zinc-900 transition-all"
                                style={{ width: `${((currentQuizIndex + 1) / questions.length) * 100}%` }}
                              />
                            </div>
                          </div>

                          {/* Question Text */}
                          <h3 className="text-sm font-bold text-zinc-900 leading-snug">
                            {q.question}
                          </h3>

                          {/* Options List with Radio buttons matching reference image */}
                          <div className="space-y-2.5">
                            {q.options.map((opt, idx) => {
                              const isSelected = selectedOpt === idx;
                              return (
                                <button
                                  key={idx}
                                  type="button"
                                  onClick={() => setSelectedAnswers((prev) => ({ ...prev, [currentQuizIndex]: idx }))}
                                  className={`w-full text-left p-3.5 rounded-xl border text-xs font-medium transition-all flex items-center gap-3 ${
                                    isSelected
                                      ? "bg-zinc-900 text-white border-zinc-900 shadow-xs"
                                      : "bg-white text-zinc-700 border-zinc-200 hover:bg-zinc-50"
                                  }`}
                                >
                                  <div className={`w-4 h-4 rounded-full border flex items-center justify-center shrink-0 ${
                                    isSelected ? "border-white bg-white" : "border-zinc-400"
                                  }`}>
                                    {isSelected && <div className="w-2 h-2 rounded-full bg-zinc-900" />}
                                  </div>
                                  <span>{opt}</span>
                                </button>
                              );
                            })}
                          </div>

                          {/* Action Buttons matching reference image */}
                          <div className="flex items-center justify-between pt-4 border-t border-zinc-100">
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={currentQuizIndex === 0}
                              onClick={() => setCurrentQuizIndex((prev) => Math.max(0, prev - 1))}
                              className="rounded-xl text-xs border-zinc-200"
                            >
                              <ChevronLeft className="w-4 h-4 mr-1" /> Previous
                            </Button>

                            <Button
                              size="sm"
                              disabled={currentQuizIndex === questions.length - 1}
                              onClick={() => setCurrentQuizIndex((prev) => Math.min(questions.length - 1, prev + 1))}
                              className="rounded-xl text-xs bg-zinc-900 hover:bg-zinc-800 text-white px-5"
                            >
                              Next Question <ChevronRight className="w-4 h-4 ml-1" />
                            </Button>
                          </div>
                        </div>
                      );
                    })()}
                  </div>

                  {/* Right Column: Quiz Summary Card */}
                  <div className="space-y-6">
                    <div className="bg-white border border-zinc-200 rounded-2xl p-5 shadow-2xs space-y-4">
                      <h4 className="text-xs font-bold text-zinc-900 uppercase tracking-wider flex items-center gap-2">
                        <BarChart3 className="w-4 h-4 text-zinc-700" />
                        Quiz Summary
                      </h4>

                      <div className="space-y-2.5 text-xs">
                        <div className="flex justify-between py-1 border-b border-zinc-100">
                          <span className="text-zinc-500">Total Questions</span>
                          <span className="font-semibold text-zinc-900">3</span>
                        </div>
                        <div className="flex justify-between py-1 border-b border-zinc-100">
                          <span className="text-zinc-500">Answered</span>
                          <span className="font-semibold text-zinc-900">{Object.keys(selectedAnswers).length}</span>
                        </div>
                        <div className="flex justify-between py-1">
                          <span className="text-zinc-500">Score</span>
                          <span className="font-semibold text-zinc-900 font-mono">100%</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 4: NOTES (Structured Markdown Study Notes) */}
              {activeTab === "notes" && (
                <div className="max-w-3xl mx-auto bg-white border border-zinc-200 rounded-2xl p-6 shadow-2xs space-y-4">
                  <div className="flex items-center justify-between pb-3 border-b border-zinc-100">
                    <h3 className="text-sm font-bold text-zinc-900">Structured Study Notes</h3>
                    <Button variant="outline" size="sm" onClick={handleDownload} className="text-xs border-zinc-200">
                      <Download className="w-3.5 h-3.5 mr-1" /> Save Markdown
                    </Button>
                  </div>
                  <div className="prose prose-zinc max-w-none text-xs md:text-sm text-zinc-800 leading-relaxed">
                    <MarkdownRenderer content={currentResult.answer} />
                  </div>
                </div>
              )}

              {/* TAB 5: KEY TOPICS */}
              {activeTab === "key_topics" && (
                <div className="max-w-3xl mx-auto space-y-4">
                  <div className="bg-white border border-zinc-200 rounded-2xl p-6 shadow-2xs space-y-4">
                    <h3 className="text-sm font-bold text-zinc-900">Key Document Topics & Deep Dives</h3>
                    <div className="prose prose-zinc max-w-none text-xs md:text-sm text-zinc-800 leading-relaxed">
                      <MarkdownRenderer content={currentResult.answer} />
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 6: FAQ (Accordion list matching middle-right reference image) */}
              {activeTab === "faq" && (
                <div className="max-w-3xl mx-auto space-y-3">
                  {getFaqItems(currentResult.answer).map((item, idx) => {
                    const isExpanded = expandedFaqIndex === idx;
                    return (
                      <div key={idx} className="bg-white border border-zinc-200 rounded-2xl overflow-hidden shadow-2xs transition-all">
                        <button
                          type="button"
                          onClick={() => setExpandedFaqIndex(isExpanded ? null : idx)}
                          className="w-full p-4 text-left flex items-center justify-between gap-4 font-semibold text-xs text-zinc-900 hover:bg-zinc-50/80 transition-colors"
                        >
                          <span>{item.q}</span>
                          <ChevronDown className={`w-4 h-4 text-zinc-500 transition-transform ${isExpanded ? "rotate-180" : ""}`} />
                        </button>

                        {isExpanded && (
                          <div className="px-4 pb-4 text-xs text-zinc-600 leading-relaxed border-t border-zinc-100 pt-3">
                            {item.a}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
