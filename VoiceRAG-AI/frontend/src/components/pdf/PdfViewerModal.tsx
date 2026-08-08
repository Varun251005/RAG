"use client";

import React, { useState, useEffect } from "react";
import {
  X,
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  Maximize2,
  PanelLeft,
  FileText,
  Sparkles,
  Download,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface PdfViewerModalProps {
  isOpen: boolean;
  onClose: () => void;
  documentId: string;
  documentName: string;
  initialPage?: number;
  highlightSnippet?: string;
}

export function PdfViewerModal({
  isOpen,
  onClose,
  documentId,
  documentName,
  initialPage = 1,
  highlightSnippet,
}: PdfViewerModalProps) {
  const [currentPage, setCurrentPage] = useState(initialPage);
  const [numPages] = useState(20); // Default estimate for sidebar navigation
  const [zoom, setZoom] = useState(1.0);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  useEffect(() => {
    if (initialPage) {
      setCurrentPage(initialPage);
    }
  }, [initialPage, documentId]);

  if (!isOpen || !documentId) return null;

  const pdfFileUrl = `${API_BASE_URL}/api/v1/documents/${documentId}/file#page=${currentPage}&zoom=${Math.round(
    zoom * 100
  )}`;

  const handlePrevPage = () => {
    setCurrentPage((prev) => Math.max(1, prev - 1));
  };

  const handleNextPage = () => {
    setCurrentPage((prev) => prev + 1);
  };

  const handleZoomIn = () => {
    setZoom((prev) => Math.min(2.5, prev + 0.25));
  };

  const handleZoomOut = () => {
    setZoom((prev) => Math.max(0.5, prev - 0.25));
  };

  const handleFitWidth = () => {
    setZoom(1.0);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-md p-2 sm:p-4 animate-in fade-in">
      <div className="bg-card border border-border rounded-2xl w-full max-w-6xl h-[92vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header Toolbar */}
        <header className="flex items-center justify-between px-4 py-2.5 border-b border-border bg-slate-900 text-slate-100 shrink-0">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
              className="h-8 w-8 text-slate-300 hover:text-white hover:bg-slate-800"
              title="Toggle sidebar navigation"
            >
              <PanelLeft className="w-4 h-4" />
            </Button>

            <div className="flex items-center gap-2 max-w-[280px] sm:max-w-md truncate">
              <FileText className="w-4 h-4 text-primary shrink-0" />
              <span className="font-semibold text-xs truncate">{documentName}</span>
              <Badge variant="outline" className="text-[10px] bg-slate-800 text-slate-300 border-slate-700">
                PDF
              </Badge>
            </div>
          </div>

          {/* Page Jump Controls */}
          <div className="flex items-center gap-1 text-xs">
            <Button
              variant="ghost"
              size="icon"
              onClick={handlePrevPage}
              disabled={currentPage <= 1}
              className="h-7 w-7 text-slate-300 hover:text-white disabled:opacity-30"
              title="Previous Page"
            >
              <ChevronLeft className="w-4 h-4" />
            </Button>

            <div className="flex items-center gap-1 font-mono text-xs px-2 py-0.5 bg-slate-800 rounded-md border border-slate-700">
              <span>Page</span>
              <input
                type="number"
                min={1}
                value={currentPage}
                onChange={(e) => setCurrentPage(Math.max(1, parseInt(e.target.value) || 1))}
                className="w-8 bg-transparent text-center text-white focus:outline-none focus:ring-1 focus:ring-primary rounded"
              />
            </div>

            <Button
              variant="ghost"
              size="icon"
              onClick={handleNextPage}
              className="h-7 w-7 text-slate-300 hover:text-white"
              title="Next Page"
            >
              <ChevronRight className="w-4 h-4" />
            </Button>
          </div>

          {/* Zoom & Download Controls */}
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1 bg-slate-800 rounded-lg p-0.5 border border-slate-700">
              <Button
                variant="ghost"
                size="icon"
                onClick={handleZoomOut}
                className="h-7 w-7 text-slate-300 hover:text-white"
                title="Zoom Out"
              >
                <ZoomOut className="w-3.5 h-3.5" />
              </Button>

              <span className="text-[11px] font-mono w-10 text-center text-slate-300">
                {Math.round(zoom * 100)}%
              </span>

              <Button
                variant="ghost"
                size="icon"
                onClick={handleZoomIn}
                className="h-7 w-7 text-slate-300 hover:text-white"
                title="Zoom In"
              >
                <ZoomIn className="w-3.5 h-3.5" />
              </Button>

              <Button
                variant="ghost"
                size="icon"
                onClick={handleFitWidth}
                className="h-7 w-7 text-slate-300 hover:text-white"
                title="Reset Zoom / Fit Width"
              >
                <Maximize2 className="w-3.5 h-3.5" />
              </Button>
            </div>

            <a href={`${API_BASE_URL}/api/v1/documents/${documentId}/file`} download={documentName}>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-slate-300 hover:text-white hover:bg-slate-800"
                title="Download PDF"
              >
                <Download className="w-4 h-4" />
              </Button>
            </a>

            <Button
              variant="ghost"
              size="icon"
              onClick={onClose}
              className="h-8 w-8 text-slate-300 hover:text-white hover:bg-destructive/20 rounded-lg"
              title="Close PDF Viewer"
            >
              <X className="w-4 h-4" />
            </Button>
          </div>
        </header>

        {/* Main Body with Sidebar & Viewer */}
        <div className="flex-1 flex overflow-hidden relative bg-slate-950">
          {/* Sidebar Navigation Panel */}
          {isSidebarOpen && (
            <aside className="w-48 bg-slate-900 border-r border-slate-800 p-3 space-y-2 overflow-y-auto shrink-0 animate-in slide-in-from-left-4 duration-200">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 block px-1">
                Pages Navigation
              </span>
              <div className="space-y-1.5">
                {Array.from({ length: Math.min(15, numPages) }).map((_, idx) => {
                  const pageNum = idx + 1;
                  const isActive = currentPage === pageNum;
                  return (
                    <button
                      key={pageNum}
                      onClick={() => setCurrentPage(pageNum)}
                      type="button"
                      className={`w-full flex items-center justify-between p-2 rounded-lg text-xs font-medium transition-all ${
                        isActive
                          ? "bg-primary text-primary-foreground font-bold shadow-md"
                          : "bg-slate-800/60 text-slate-300 hover:bg-slate-800 hover:text-white"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <FileText className="w-3.5 h-3.5 shrink-0" />
                        <span>Page {pageNum}</span>
                      </div>
                      {pageNum === initialPage && highlightSnippet && (
                        <Sparkles className="w-3 h-3 text-amber-400 animate-pulse" />
                      )}
                    </button>
                  );
                })}
              </div>
            </aside>
          )}

          {/* Main PDF Canvas/Embed Container */}
          <main className="flex-1 flex flex-col relative overflow-hidden bg-slate-950">
            {/* Highlighted Source Citation Banner */}
            {highlightSnippet && (
              <div className="p-3 bg-amber-500/10 border-b border-amber-500/30 text-amber-200 text-xs flex items-start gap-2 shrink-0 animate-in fade-in">
                <Sparkles className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                <div className="space-y-0.5 overflow-hidden">
                  <span className="font-semibold text-amber-300">
                    Source Citation Highlight — Page {initialPage}:
                  </span>
                  <p className="font-mono text-[11px] text-amber-100/90 truncate">"{highlightSnippet}"</p>
                </div>
              </div>
            )}

            {/* PDF Render Engine iframe */}
            <div className="flex-1 w-full h-full relative">
              <iframe
                key={`${documentId}-${currentPage}-${zoom}`}
                src={pdfFileUrl}
                className="w-full h-full border-0"
                title={documentName}
              />
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
