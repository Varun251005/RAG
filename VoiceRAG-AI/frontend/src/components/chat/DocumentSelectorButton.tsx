"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { Plus, Check, Globe, FileText } from "lucide-react";
import { useChatStore } from "@/store/useChatStore";
import { useDocumentStore } from "@/store/documentStore";

export function DocumentSelectorButton() {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const { activeDocumentId, setActiveDocumentId } = useChatStore();
  const { documents } = useDocumentStore();

  // Close on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [open]);

  // Close on Escape key
  useEffect(() => {
    function handleKeyUp(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    if (open) {
      document.addEventListener("keyup", handleKeyUp);
      return () => document.removeEventListener("keyup", handleKeyUp);
    }
  }, [open]);

  const select = useCallback(
    (id: string | null) => {
      setActiveDocumentId(id);
      setOpen(false);
    },
    [setActiveDocumentId]
  );

  const activeDoc = documents.find((d) => d.document_id === activeDocumentId);

  return (
    <div ref={containerRef} className="relative shrink-0 self-center">
      {/* + button matching reference design */}
      <button
        type="button"
        aria-label="Select document filter"
        aria-expanded={open}
        aria-haspopup="listbox"
        onClick={() => setOpen((v) => !v)}
        title={activeDoc ? `Scoped to: ${activeDoc.filename}` : "Select document from library"}
        className={`
          flex items-center justify-center w-8 h-8 md:w-9 md:h-9 rounded-full border transition-all text-zinc-700
          focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-900/20
          ${
            open
              ? "bg-zinc-900 text-white border-zinc-900 shadow-sm"
              : activeDocumentId !== null
              ? "bg-zinc-900 text-white border-zinc-900 shadow-xs"
              : "bg-zinc-100 hover:bg-zinc-200 text-zinc-700 border-zinc-200"
          }
        `}
      >
        <Plus className={`w-4 h-4 transition-transform duration-200 ${open ? "rotate-45" : ""}`} />
      </button>

      {/* Popover Dropdown panel */}
      {open && (
        <div
          role="listbox"
          aria-label="Select document filter"
          className="
            absolute bottom-full left-0 mb-2 z-50
            min-w-[260px] max-w-[320px]
            bg-white text-zinc-900
            border border-zinc-200 rounded-2xl shadow-xl
            overflow-hidden
            animate-in fade-in-0 zoom-in-95 slide-in-from-bottom-2
            duration-150
          "
        >
          {/* Header */}
          <div className="px-3.5 py-2.5 border-b border-zinc-100 bg-zinc-50/70 flex items-center justify-between">
            <p className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider">
              Select PDF Scope
            </p>
            <span className="text-[10px] font-semibold text-zinc-500 bg-zinc-200/70 px-1.5 py-0.5 rounded">
              {documents.length} Files
            </span>
          </div>

          <ul className="py-1 max-h-[260px] overflow-y-auto" role="group">
            {/* All PDFs option */}
            <li>
              <button
                type="button"
                role="option"
                aria-selected={activeDocumentId === null}
                onClick={() => select(null)}
                className={`
                  w-full flex items-center gap-2.5 px-3.5 py-2.5 text-xs font-medium
                  hover:bg-zinc-100 text-zinc-800 transition-colors text-left
                  ${activeDocumentId === null ? "bg-zinc-50 font-bold" : ""}
                `}
              >
                <Globe className="w-4 h-4 shrink-0 text-zinc-900" />
                <span className="flex-1 text-zinc-900">All Documents ({documents.length})</span>
                {activeDocumentId === null && (
                  <Check className="w-4 h-4 text-zinc-900 shrink-0" />
                )}
              </button>
            </li>

            {/* Divider */}
            {documents.length > 0 && (
              <li aria-hidden="true">
                <div className="my-1 mx-3 h-px bg-zinc-100" />
              </li>
            )}

            {/* Individual documents from library */}
            {documents.length === 0 ? (
              <li className="px-3 py-4 text-center text-xs text-zinc-400">
                No documents uploaded yet in library
              </li>
            ) : (
              documents.map((doc) => {
                const isSelected = activeDocumentId === doc.document_id;
                return (
                  <li key={doc.document_id}>
                    <button
                      type="button"
                      role="option"
                      aria-selected={isSelected}
                      onClick={() => select(doc.document_id)}
                      title={doc.filename}
                      className={`
                        w-full flex items-center gap-2.5 px-3.5 py-2.5 text-xs
                        hover:bg-zinc-100 text-zinc-700 transition-colors text-left
                        ${isSelected ? "bg-zinc-50 font-bold text-zinc-900" : ""}
                      `}
                    >
                      <FileText className={`w-3.5 h-3.5 shrink-0 ${isSelected ? "text-zinc-900" : "text-zinc-400"}`} />
                      <span className="flex-1 truncate font-medium">{doc.filename}</span>
                      {isSelected && (
                        <Check className="w-3.5 h-3.5 text-zinc-900 shrink-0" />
                      )}
                    </button>
                  </li>
                );
              })
            )}
          </ul>
        </div>
      )}
    </div>
  );
}


