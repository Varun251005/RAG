"use client";

import React from "react";

export function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 py-1.5 px-3 rounded-xl bg-muted/60 text-muted-foreground w-fit animate-pulse border border-border/50">
      <span className="text-xs font-medium mr-1 text-foreground/70">Thinking</span>
      <div className="w-1.5 h-1.5 rounded-full bg-primary/70 animate-bounce [animation-delay:-0.32s]" />
      <div className="w-1.5 h-1.5 rounded-full bg-primary/70 animate-bounce [animation-delay:-0.16s]" />
      <div className="w-1.5 h-1.5 rounded-full bg-primary/70 animate-bounce" />
    </div>
  );
}

export function StreamingCursor() {
  return (
    <span className="inline-block w-2 h-4 ml-0.5 bg-primary/80 animate-pulse align-middle" />
  );
}
