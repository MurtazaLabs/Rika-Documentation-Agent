"use client";

import { Brain } from "lucide-react";

import {
  ConfidenceBadge,
  FileButton,
  humanizeKind,
} from "@/components/intelligence/shared";
import { Badge } from "@/components/ui/badge";
import type { ChatIntelligenceItem } from "@/lib/types";

/**
 * The derived report items an answer relied on.
 *
 * These are not retrieved passages: they come from the project's symbols,
 * imports and documentation, so they carry a confidence label and a source
 * location instead of a chunk citation.
 */
export function IntelligenceCitations({
  items,
  projectId,
}: {
  items: ChatIntelligenceItem[];
  projectId: string;
}) {
  if (items.length === 0) return null;

  return (
    <div className="mt-3 rounded-xl border border-line/70 bg-canvas/30 px-3 py-2.5">
      <div className="flex flex-wrap items-center gap-2">
        <Brain className="h-3 w-3 text-copper" />
        <p className="font-mono text-[9px] uppercase tracking-[0.16em] text-faint">
          Derived from the index
        </p>
        <Badge mono tone="violet">
          {items.length}
        </Badge>
        <span className="text-[10px] text-faint">
          computed from symbols, imports and docs
        </span>
      </div>

      <ul className="mt-2 space-y-1.5">
        {items.map((item) => (
          <li key={item.marker} className="flex flex-wrap items-start gap-2">
            <span className="mt-0.5 flex h-4 shrink-0 items-center rounded border border-line bg-surface-2/60 px-1 font-mono text-[9px] text-muted">
              {item.marker}
            </span>
            {item.confidence ? (
              <ConfidenceBadge confirmed={item.confidence === "confirmed"} />
            ) : null}
            <span className="min-w-0 flex-1 text-[10.5px] leading-relaxed text-muted">
              <span className="font-mono text-[9px] uppercase tracking-[0.1em] text-faint">
                {humanizeKind(item.kind)} ·{" "}
              </span>
              {item.message}
            </span>
            {item.file_path ? (
              <FileButton
                projectId={projectId}
                path={item.file_path}
                startLine={item.line}
                className="shrink-0"
              />
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
