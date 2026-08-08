"use client";

import { useCallback, useState } from "react";
import { toast } from "sonner";
import { v4 as uuidv4 } from "uuid";

import { uploadPdfDocument } from "@/lib/api/documents";
import type { UploadFileEntry } from "@/types/document";
import { useDocumentStore } from "@/store/documentStore";

const MAX_SIZE_BYTES = 25 * 1024 * 1024;

export function useDocumentUpload() {
  const [entries, setEntries] = useState<UploadFileEntry[]>([]);
  const addDocument = useDocumentStore((s) => s.addDocument);

  const updateEntry = useCallback(
    (id: string, patch: Partial<UploadFileEntry>) =>
      setEntries((prev) =>
        prev.map((e) => (e.id === id ? { ...e, ...patch } : e))
      ),
    []
  );

  const validateFile = (file: File): string | null => {
    if (!file.name.toLowerCase().endsWith(".pdf") && file.type !== "application/pdf") {
      return `${file.name}: Only PDF files are accepted.`;
    }
    if (file.size > MAX_SIZE_BYTES) {
      return `${file.name}: Exceeds the 25 MB size limit.`;
    }
    return null;
  };

  const upload = useCallback(
    async (files: File[]) => {
      const newEntries: UploadFileEntry[] = [];
      const validFiles: { id: string; file: File }[] = [];

      for (const file of files) {
        const error = validateFile(file);
        const id = uuidv4();
        if (error) {
          newEntries.push({ id, file, progress: 0, status: "error", error });
          toast.error(error);
        } else {
          newEntries.push({ id, file, progress: 0, status: "pending" });
          validFiles.push({ id, file });
        }
      }

      setEntries((prev) => [...prev, ...newEntries]);

      if (validFiles.length === 0) return;

      for (const item of validFiles) {
        updateEntry(item.id, { status: "uploading", progress: 10 });
        try {
          const result = await uploadPdfDocument(item.file, (pct) => {
            updateEntry(item.id, { progress: Math.max(10, pct), status: "uploading" });
          });

          updateEntry(item.id, { status: "done", progress: 100, result });
          addDocument({
            document_id: result.document_id,
            filename: result.filename,
            total_chunks: result.total_chunks,
            total_pages: result.total_pages,
            status: result.status,
          });

          toast.success(
            `"${result.filename}" uploaded successfully (${result.total_pages} page(s), ${result.total_chunks} chunk(s)).`
          );
        } catch (err: any) {
          const detail =
            err.response?.data?.detail ||
            err.response?.data?.message ||
            err.message ||
            "Backend server unavailable. Please check connection.";

          updateEntry(item.id, { status: "error", error: detail });
          toast.error(`Upload failed for "${item.file.name}": ${detail}`);
        }
      }
    },
    [updateEntry, addDocument]
  );

  const clearCompleted = useCallback(
    () => setEntries((prev) => prev.filter((e) => e.status === "uploading")),
    []
  );

  return { entries, upload, clearCompleted };
}
