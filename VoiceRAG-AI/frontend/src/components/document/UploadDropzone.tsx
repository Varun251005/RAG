"use client";

import { useCallback, useRef, useState } from "react";
import { CloudUpload, FileText, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { UploadFileEntry } from "@/types/document";

interface UploadDropzoneProps {
  entries: UploadFileEntry[];
  onFilesSelected: (files: File[]) => void;
  onClear: () => void;
}

export function UploadDropzone({
  entries,
  onFilesSelected,
  onClear,
}: UploadDropzoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const isUploading = entries.some(
    (e) => e.status === "pending" || e.status === "uploading"
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      if (isUploading) return;
      const files = Array.from(e.dataTransfer.files).filter(
        (f) => f.name.toLowerCase().endsWith(".pdf") || f.type === "application/pdf"
      );
      if (files.length > 0) {
        onFilesSelected(files);
      }
    },
    [onFilesSelected, isUploading]
  );

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (isUploading) return;
    const files = Array.from(e.target.files ?? []);
    if (files.length > 0) onFilesSelected(files);
    e.target.value = "";
  };

  return (
    <div className="space-y-4">
      {/* Drop zone matching reference image */}
      <div
        role="button"
        tabIndex={0}
        aria-label="Upload PDF files"
        onClick={() => !isUploading && inputRef.current?.click()}
        onKeyDown={(e) =>
          !isUploading && e.key === "Enter" && inputRef.current?.click()
        }
        onDragOver={(e) => {
          e.preventDefault();
          if (!isUploading) setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        className={[
          "relative flex flex-col items-center justify-center gap-3",
          "rounded-2xl border-2 border-dashed px-8 py-12 transition-all duration-200 select-none bg-white",
          isUploading
            ? "opacity-60 cursor-not-allowed border-zinc-200 bg-zinc-50"
            : isDragging
            ? "border-zinc-900 bg-zinc-50 scale-[1.01] cursor-pointer"
            : "border-zinc-300 hover:border-zinc-900 hover:bg-zinc-50/60 cursor-pointer",
        ].join(" ")}
      >
        {isUploading ? (
          <Loader2 className="w-10 h-10 animate-spin text-zinc-900" />
        ) : (
          <div className="p-3 rounded-full bg-zinc-100 text-zinc-800 border border-zinc-200">
            <CloudUpload className="w-6 h-6" />
          </div>
        )}
        <div className="text-center">
          <p className="text-sm font-semibold text-zinc-900">
            {isUploading ? (
              <span>Ingesting PDF & generating 384-dim embeddings...</span>
            ) : (
              <span>
                Drop PDF here or <span className="underline font-bold text-zinc-900">browse files</span>
              </span>
            )}
          </p>
          <p className="mt-1 text-xs text-zinc-500">
            PDF format only • Max 25 MB file size limit
          </p>
        </div>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          disabled={isUploading}
          className="sr-only"
          onChange={handleChange}
        />
      </div>

      {/* Per-file progress list */}
      {entries.length > 0 && (
        <div className="space-y-2">
          {entries.map((entry) => (
            <FileRow key={entry.id} entry={entry} />
          ))}
          {!isUploading && (
            <div className="flex justify-end">
              <Button
                variant="ghost"
                size="sm"
                onClick={onClear}
                className="text-xs text-zinc-500 hover:text-zinc-900"
              >
                Clear completed
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}


function FileRow({ entry }: { entry: UploadFileEntry }) {
  const sizeMb = (entry.file.size / (1024 * 1024)).toFixed(2);

  return (
    <div className="rounded-xl border bg-card p-4 space-y-2 shadow-xs">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <FileText className="size-4 shrink-0 text-primary" />
          <div className="truncate text-sm font-medium">{entry.file.name}</div>
          <span className="text-xs text-muted-foreground shrink-0">({sizeMb} MB)</span>
        </div>

        {entry.status === "uploading" && (
          <Badge variant="outline" className="text-xs gap-1 border-primary/40 text-primary">
            <Loader2 className="size-3 animate-spin" /> Ingesting
          </Badge>
        )}
        {entry.status === "done" && (
          <Badge variant="default" className="text-xs gap-1 bg-emerald-600 hover:bg-emerald-600">
            <CheckCircle2 className="size-3" /> Completed
          </Badge>
        )}
        {entry.status === "error" && (
          <Badge variant="destructive" className="text-xs gap-1">
            <AlertCircle className="size-3" /> Failed
          </Badge>
        )}
        {entry.status === "pending" && (
          <Badge variant="secondary" className="text-xs">
            Pending
          </Badge>
        )}
      </div>

      {entry.status === "uploading" && (
        <div className="space-y-1 pt-1">
          <Progress value={entry.progress} className="h-1.5" />
          <p className="text-[11px] text-muted-foreground text-right">
            {entry.progress}% processed
          </p>
        </div>
      )}

      {entry.status === "error" && entry.error && (
        <p className="text-xs text-destructive pt-1">{entry.error}</p>
      )}

      {entry.status === "done" && entry.result && (
        <div className="text-xs text-muted-foreground pt-1 flex items-center gap-3">
          <span>Pages: <strong>{entry.result.total_pages}</strong></span>
          <span>Chunks: <strong>{entry.result.total_chunks}</strong></span>
          <span>ID: <code className="bg-muted px-1 py-0.5 rounded text-[11px]">{entry.result.document_id}</code></span>
        </div>
      )}
    </div>
  );
}
