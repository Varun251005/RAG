"use client";

import React, { useState } from "react";
import { SourceCitation } from "@/types/chat";
import { FileText, ChevronDown, ChevronUp, ExternalLink } from "lucide-react";

interface SourceCitationsProps {
  sources: SourceCitation[];
  onSelectCitation?: (citation: SourceCitation) => void;
}

export function SourceCitations({ sources, onSelectCitation }: SourceCitationsProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!sources || sources.length === 0) return null;

  return (
    <div className="mt-3 pt-2.5 border-t border-zinc-100 text-xs">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        type="button"
        className="flex items-center justify-between w-full text-left py-1 text-zinc-500 hover:text-zinc-900 transition-colors group"
      >
        <div className="flex items-center gap-1.5 font-semibold text-zinc-800 text-xs">
          <span>Sources Used ({sources.length})</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-[11px] text-zinc-400 font-normal">
            {isExpanded ? "Hide sources" : "Show sources"}
          </span>
          {isExpanded ? (
            <ChevronUp className="w-3.5 h-3.5 text-zinc-400" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5 text-zinc-400" />
          )}
        </div>
      </button>

      {/* Pill summary when collapsed matching reference image */}
      {!isExpanded && (
        <div className="flex flex-wrap gap-1.5 mt-2">
          {sources.map((src, idx) => (
            <button
              key={`${src.chunk_id}-${idx}`}
              type="button"
              onClick={() => onSelectCitation && onSelectCitation(src)}
              className="px-2.5 py-1 rounded-lg border border-zinc-200 bg-white hover:bg-zinc-50 text-zinc-700 hover:text-zinc-900 text-[11px] font-medium flex items-center gap-1.5 transition-all shadow-2xs"
              title="Click to view PDF on this page"
            >
              <FileText className="w-3 h-3 text-zinc-400" />
              <span className="truncate max-w-[150px]">{src.original_filename}</span>
              <span className="text-zinc-500 font-semibold">p.{src.page_number}</span>
            </button>
          ))}
        </div>
      )}

      {/* Detailed view when expanded */}
      {isExpanded && (
        <div className="space-y-2 mt-2">
          {sources.map((src, idx) => {
            const scorePct = Math.round(src.score * 100);
            return (
              <div
                key={`${src.chunk_id}-${idx}`}
                onClick={() => onSelectCitation && onSelectCitation(src)}
                className="p-2.5 rounded-xl bg-zinc-50 hover:bg-zinc-100/80 border border-zinc-200 transition-all cursor-pointer space-y-1 text-zinc-800 group"
                title="Click to open PDF viewer on page"
              >
                <div className="flex items-center justify-between font-medium text-[11px]">
                  <div className="flex items-center gap-1.5 truncate">
                    <FileText className="w-3.5 h-3.5 text-zinc-700 shrink-0" />
                    <span className="font-semibold text-zinc-900 truncate group-hover:underline">
                      {src.original_filename}
                    </span>
                    <span className="text-zinc-500 font-normal">Page {src.page_number}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-200 text-zinc-800 font-mono font-semibold shrink-0">
                      {scorePct}% match
                    </span>
                    <ExternalLink className="w-3 h-3 text-zinc-400 group-hover:text-zinc-900 shrink-0" />
                  </div>
                </div>
                {src.snippet && (
                  <p className="text-[11px] leading-relaxed text-zinc-600 font-mono bg-white p-2 rounded-lg border border-zinc-200 line-clamp-3">
                    "{src.snippet}"
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

