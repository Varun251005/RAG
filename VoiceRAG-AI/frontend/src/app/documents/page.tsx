"use client";

import { useEffect } from "react";
import Link from "next/link";
import { Toaster } from "@/components/ui/sonner";
import { UploadDropzone } from "@/components/document/UploadDropzone";
import { DocumentList } from "@/components/document/DocumentList";
import { useDocumentUpload } from "@/hooks/useDocumentUpload";
import { useDocumentStore } from "@/store/documentStore";
import { fetchDocuments } from "@/lib/api/documents";
import { FileText, ArrowLeft, MessageSquare } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function DocumentsPage() {
  const { entries, upload, clearCompleted } = useDocumentUpload();
  const setDocuments = useDocumentStore((s) => s.setDocuments);
  const setLoading = useDocumentStore((s) => s.setLoading);
  const setError = useDocumentStore((s) => s.setError);

  useEffect(() => {
    setLoading(true);
    fetchDocuments()
      .then((res) => {
        setDocuments(res.documents);
      })
      .catch((err) => {
        const msg =
          err.response?.data?.detail ||
          err.message ||
          "Failed to connect to backend service. Please check backend server.";
        setError(msg);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [setDocuments, setLoading, setError]);

  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-900 font-sans">
      {/* Navigation Header Bar matching reference image */}
      <header className="flex items-center justify-between px-6 py-3.5 border-b border-zinc-200 bg-white/90 backdrop-blur-md z-10 sticky top-0">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-zinc-100 text-zinc-900 border border-zinc-200 shadow-2xs">
            <FileText className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-base font-bold tracking-tight text-zinc-900 leading-none">Document Library</h1>
            <p className="text-[11px] text-zinc-500 mt-0.5">
              Upload and index PDF documents for local Qwen VoiceRAG AI queries
            </p>
          </div>
        </div>

        <Link href="/chat">
          <Button variant="outline" size="sm" className="h-8 text-xs gap-1.5 rounded-xl border-zinc-200 hover:bg-zinc-100 font-medium">
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Chat</span>
          </Button>
        </Link>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-8 space-y-8">
        <section aria-label="Upload PDFs" className="space-y-3">
          <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-400">
            Upload New Document
          </h2>
          <UploadDropzone
            entries={entries}
            onFilesSelected={upload}
            onClear={clearCompleted}
          />
        </section>

        <section aria-label="Uploaded documents" className="pt-2">
          <DocumentList />
        </section>

        <Toaster richColors position="bottom-right" />
      </main>
    </div>
  );
}

