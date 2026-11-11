"use client";

import { useState } from "react";
import { ArrowUpRight, Quote } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Citation } from "@/lib/types";
import { cn, lineLabel, truncate } from "@/lib/utils";

export function CitationList({
  citations,
  onOpen,
}: {
  citations: Citation[];
  onOpen: (citation: Citation) => void;
}) {
  const [showAll, setShowAll] = useState(false);
  if (citations.length === 0) return null;

  const visible = showAll ? citations : citations.slice(0, 4);

  return (
    <div className="mt-4 border-t border-line/70 pt-3.5">
      <div className="flex items-center gap-2">
        <Quote className="h-3 w-3 text-copper" />
        <p className="font-mono text-[9px] uppercase tracking-[0.18em] text-faint">
          Sources
        </p>
        <Badge mono tone="copper">
          {citations.length}
        </Badge>
        <span className="text-[10px] text-faint">
          verified against stored chunks
        </span>
      </div>

      <div className="mt-2.5 grid gap-1.5 sm:grid-cols-2">
        {visible.map((citation) => (
          <button
            key={citation.marker}
            type="button"
            id={`citation-${citation.marker}`}
            onClick={() => onOpen(citation)}
            className={cn(
              "group flex items-start gap-2.5 rounded-xl border border-line/80 bg-canvas/40 px-3 py-2.5 text-left transition-colors",
              "hover:border-copper/30 hover:bg-surface-2/60",
            )}
          >
            <span className="mt-0.5 flex h-5 shrink-0 items-center rounded border border-copper/25 bg-copper/10 px-1 font-mono text-[9px] text-copper">
              {citation.marker}
            </span>
            <span className="min-w-0 flex-1">
              <span className="flex items-center gap-1.5">
                <span className="truncate text-[11px] font-medium text-parchment">
                  {citation.filename}
                </span>
                <span className="shrink-0 font-mono text-[9px] text-faint">
                  {lineLabel(
                    citation.start_line,
                    citation.end_line,
                    citation.page_number,
                  )}
                </span>
              </span>
              <span className="mt-0.5 block truncate font-mono text-[9px] text-faint">
                {citation.file_path}
              </span>
              <span className="mt-1 block text-[10px] leading-relaxed text-muted">
                {truncate(citation.snippet.replace(/\s+/g, " "), 180)}
              </span>
            </span>
            <ArrowUpRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-faint transition-colors group-hover:text-copper" />
          </button>
        ))}
      </div>

      {citations.length > 4 ? (
        <Button
          size="sm"
          variant="ghost"
          className="mt-1.5 h-7 px-2 text-[10px]"
          onClick={() => setShowAll((value) => !value)}
        >
          {showAll
            ? "Show fewer sources"
            : `Show all ${citations.length} sources`}
        </Button>
      ) : null}
    </div>
  );
}
