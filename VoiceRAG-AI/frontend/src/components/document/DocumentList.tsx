"use client";

import { useCallback, useState } from "react";
import {
  FileText,
  Trash2,
  CheckCircle,
  Database,
  AlertTriangle,
  Loader2,
  RefreshCw,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { deleteDocument, fetchDocuments } from "@/lib/api/documents";
import { useDocumentStore } from "@/store/documentStore";
import type { DocumentInfoResponse } from "@/types/document";

export function DocumentList() {
  const {
    documents,
    selectedDocumentId,
    selectDocument,
    removeDocument,
    setDocuments,
    isLoading,
    error,
    setLoading,
    setError,
  } = useDocumentStore();

  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmDeleteDoc, setConfirmDeleteDoc] = useState<DocumentInfoResponse | null>(null);

  const handleRefresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchDocuments();
      setDocuments(res.documents);
    } catch (err: any) {
      const msg =
        err.response?.data?.detail ||
        err.message ||
        "Failed to connect to backend server.";
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  }, [setDocuments, setLoading, setError]);

  const confirmDelete = useCallback(
    async (doc: DocumentInfoResponse) => {
      setDeletingId(doc.document_id);
      try {
        await deleteDocument(doc.document_id);
        removeDocument(doc.document_id);
        toast.success(`"${doc.filename}" deleted from vector store.`);
      } catch (err: any) {
        const msg =
          err.response?.data?.detail ||
          err.message ||
          `Failed to delete document ${doc.document_id}`;
        toast.error(msg);
      } finally {
        setDeletingId(null);
        setConfirmDeleteDoc(null);
      }
    },
    [removeDocument]
  );

  if (isLoading && documents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-3 text-zinc-400">
        <Loader2 className="w-8 h-8 animate-spin text-zinc-900" />
        <p className="text-sm">Fetching document library...</p>
      </div>
    );
  }

  if (error && documents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-3 text-center border border-red-200 rounded-2xl bg-red-50/50 p-6">
        <AlertTriangle className="w-8 h-8 text-red-600" />
        <p className="text-sm font-semibold text-red-700">Backend Service Error</p>
        <p className="text-xs text-zinc-500 max-w-sm">{error}</p>
        <Button variant="outline" size="sm" onClick={handleRefresh} className="mt-2 gap-1.5 border-zinc-300">
          <RefreshCw className="w-3.5 h-3.5" /> Retry Connection
        </Button>
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-2 text-center text-zinc-400 border border-dashed rounded-2xl p-8 bg-white">
        <FileText className="w-10 h-10 opacity-30" />
        <p className="text-sm font-semibold text-zinc-700">No documents indexed yet.</p>
        <p className="text-xs max-w-xs text-zinc-500">Upload a PDF document above to start indexing for VoiceRAG AI queries.</p>
      </div>
    );
  }

  return (
    <>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <h2 className="text-base font-bold text-zinc-900">Indexed Library</h2>
          <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-zinc-100 border border-zinc-200 text-zinc-700">
            {documents.length}
          </span>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleRefresh}
          className="text-xs gap-1.5 text-zinc-700 border-zinc-200 hover:bg-zinc-100 rounded-xl"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </Button>
      </div>

      <div className="space-y-3">
        {documents.map((doc) => {
          const isSelected = selectedDocumentId === doc.document_id;
          const isDeleting = deletingId === doc.document_id;

          return (
            <div
              key={doc.document_id}
              className={`bg-white border rounded-2xl p-4 transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-2xs ${
                isSelected
                  ? "border-zinc-900 ring-1 ring-zinc-900/10"
                  : "border-zinc-200 hover:border-zinc-300"
              }`}
            >
              <div className="flex items-center gap-3.5 min-w-0">
                <div className="p-2.5 rounded-xl bg-zinc-100 text-zinc-900 shrink-0 border border-zinc-200">
                  <FileText className="w-5 h-5" />
                </div>

                <div className="min-w-0 space-y-0.5">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="truncate text-sm font-semibold text-zinc-900">{doc.filename}</p>
                    <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-zinc-100 border border-zinc-200 text-zinc-600 shrink-0 flex items-center gap-1">
                      <Database className="w-2.5 h-2.5" />
                      384-dim Chunks ({doc.total_chunks})
                    </span>
                  </div>
                  <p className="text-xs text-zinc-400 font-mono">
                    ID: <code className="text-[11px] text-zinc-500 bg-zinc-50 px-1 rounded">{doc.document_id}</code>
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
                {/* Ready Status Badge */}
                <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                  Ready
                </span>

                {/* Filter for chat selection toggle */}
                <Button
                  variant={isSelected ? "default" : "outline"}
                  size="sm"
                  onClick={() => selectDocument(doc.document_id)}
                  className={`text-xs h-8 px-3 gap-1.5 rounded-xl font-medium transition-all ${
                    isSelected
                      ? "bg-zinc-900 text-white border-zinc-900 shadow-sm"
                      : "bg-white text-zinc-700 border-zinc-200 hover:bg-zinc-100"
                  }`}
                >
                  <CheckCircle className="w-3.5 h-3.5" />
                  {isSelected ? "Selected" : "Filter Chat"}
                </Button>

                {/* Delete button */}
                <button
                  type="button"
                  disabled={isDeleting}
                  aria-label={`Delete ${doc.filename}`}
                  onClick={() => setConfirmDeleteDoc(doc)}
                  className="p-2 rounded-xl text-zinc-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                  title="Delete document & vectors"
                >
                  {isDeleting ? (
                    <Loader2 className="w-4 h-4 animate-spin text-zinc-900" />
                  ) : (
                    <Trash2 className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Delete Confirmation Modal */}
      {confirmDeleteDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4 animate-in fade-in">
          <div className="bg-white border border-zinc-200 rounded-2xl p-6 max-w-md w-full space-y-4 shadow-xl text-zinc-900">
            <div className="flex items-center gap-3 text-red-600">
              <AlertTriangle className="w-6 h-6 shrink-0" />
              <h3 className="text-base font-bold">Delete Document</h3>
            </div>
            <p className="text-xs text-zinc-600 leading-relaxed">
              Are you sure you want to delete <strong>"{confirmDeleteDoc.filename}"</strong>?
              This will permanently purge all vectors for document ID <code className="text-xs bg-zinc-100 px-1 py-0.5 rounded font-mono text-zinc-800">{confirmDeleteDoc.document_id}</code> from ChromaDB.
            </p>
            <div className="flex items-center justify-end gap-2 pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setConfirmDeleteDoc(null)}
                className="rounded-xl text-xs font-semibold border-zinc-200"
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => confirmDelete(confirmDeleteDoc)}
                className="rounded-xl text-xs font-semibold bg-red-600 hover:bg-red-700 text-white"
              >
                Confirm Delete
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

