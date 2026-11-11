"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Copy,
  FileWarning,
  Loader2,
  WrapText,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useDocumentPreview } from "@/hooks/use-api";
import type { UUID } from "@/lib/types";
import { copyText, lineLabel } from "@/lib/utils";

export interface SourceHighlight {
  startLine?: number | null;
  endLine?: number | null;
  pageNumber?: number | null;
}

interface SourceViewerProps {
  documentId?: UUID | null;
  projectId?: UUID;
  open: boolean;
  onClose: () => void;
  highlight?: SourceHighlight;
}

const INITIAL_LINES = 500;

export function SourceViewer({
  documentId,
  projectId,
  open,
  onClose,
  highlight,
}: SourceViewerProps) {
  const preview = useDocumentPreview(documentId ?? undefined, projectId, open);
  const { toast } = useToast();
  const [extraLines, setExtraLines] = useState(INITIAL_LINES);

  useEffect(() => {
    if (open) setExtraLines(INITIAL_LINES);
  }, [documentId, open, highlight?.startLine, highlight?.endLine]);

  const lines = useMemo(
    () => (preview.data ? preview.data.content.split("\n") : []),
    [preview.data],
  );

  const windowStart = useMemo(() => {
    if (highlight?.startLine == null) return 0;
    return Math.max(0, highlight.startLine - 41);
  }, [highlight?.startLine]);

  const windowEnd = useMemo(() => {
    if (highlight?.startLine == null) {
      return Math.min(lines.length, extraLines);
    }
    const focusEnd = highlight.endLine ?? highlight.startLine;
    return Math.min(lines.length, Math.max(focusEnd + 80, windowStart + 200));
  }, [extraLines, highlight?.endLine, highlight?.startLine, lines.length, windowStart]);

  const visible = lines.slice(windowStart, windowEnd);
  const hasMore = windowEnd < lines.length;
  const label =
    highlight?.startLine != null
      ? lineLabel(highlight.startLine, highlight.endLine ?? null, null)
      : highlight?.pageNumber != null
        ? `p. ${highlight.pageNumber}`
        : null;

  const copyPath = async () => {
    if (!preview.data) return;
    const copied = await copyText(preview.data.file_path);
    toast({
      title: copied ? "Path copied" : "Could not copy",
      description: copied ? preview.data.file_path : "Clipboard access is unavailable.",
      tone: copied ? "success" : "error",
    });
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={preview.data?.filename ?? "Source"}
      description={preview.data?.file_path}
      size="lg"
      footer={
        <div className="flex w-full items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2">
            {preview.data?.language ? (
              <Badge mono tone="copper">
                {preview.data.language}
              </Badge>
            ) : null}
            {preview.data ? (
              <Badge tone={preview.data.source === "file" ? "sage" : "gold"}>
                {preview.data.source === "file"
                  ? "original text"
                  : preview.data.source === "chunks"
                    ? "indexed chunks"
                    : "no preview"}
              </Badge>
            ) : null}
            {label ? <Badge mono>{label}</Badge> : null}
          </div>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="ghost"
              onClick={copyPath}
              icon={<Copy className="h-3.5 w-3.5" />}
              disabled={!preview.data}
            >
              Copy path
            </Button>
            <Button size="sm" onClick={onClose}>
              Close
            </Button>
          </div>
        </div>
      }
    >
      {preview.isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-4 w-1/3" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : preview.isError ? (
        <div className="flex items-center gap-2 rounded-xl border border-rose/30 bg-rose/10 px-4 py-3 text-xs text-rose">
          <FileWarning className="h-4 w-4 shrink-0" />
          {preview.error instanceof Error
            ? preview.error.message
            : "The preview could not be loaded."}
        </div>
      ) : preview.data ? (
        <div className="space-y-3">
          {preview.data.message ? (
            <p className="flex items-start gap-2 rounded-xl border border-gold/25 bg-gold/5 px-3.5 py-2.5 text-[11px] leading-relaxed text-gold">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              {preview.data.message}
            </p>
          ) : null}

          {preview.data.content ? (
            preview.data.source === "file" ? (
              <div className="overflow-hidden rounded-xl border border-line bg-[#0d0c0b]">
                <div className="flex items-center justify-between border-b border-line/70 px-3 py-2 text-[10px] text-faint">
                  <span className="inline-flex items-center gap-1.5">
                    <WrapText className="h-3 w-3" />
                    {preview.data.line_count
                      ? `${preview.data.line_count.toLocaleString()} lines`
                      : "lines"}
                    {windowStart > 0
                      ? ` · showing from line ${windowStart + 1}`
                      : ""}
                  </span>
                  {preview.data.truncated ? (
                    <span className="text-gold">preview truncated</span>
                  ) : null}
                </div>
                <div className="max-h-[52vh] overflow-auto">
                  <pre className="min-w-full py-2 font-mono text-[11.5px] leading-[1.7]">
                    {visible.map((line, index) => {
                      const lineNumber = windowStart + index + 1;
                      const active =
                        highlight?.startLine != null &&
                        lineNumber >= highlight.startLine &&
                        lineNumber <= (highlight.endLine ?? highlight.startLine);
                      return (
                        <div
                          key={lineNumber}
                          className={
                            active
                              ? "flex bg-copper/10 px-3 text-parchment"
                              : "flex px-3 text-[#d8d0c4]"
                          }
                        >
                          <span
                            className={
                              active
                                ? "mr-4 w-10 shrink-0 select-none text-right text-copper"
                                : "mr-4 w-10 shrink-0 select-none text-right text-faint/70"
                            }
                          >
                            {lineNumber}
                          </span>
                          <span className="whitespace-pre-wrap break-words">
                            {line || " "}
                          </span>
                        </div>
                      );
                    })}
                  </pre>
                </div>
                {hasMore ? (
                  <div className="border-t border-line/70 p-3 text-center">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setExtraLines((value) => value + 1000)}
                    >
                      Show more lines
                    </Button>
                  </div>
                ) : null}
              </div>
            ) : (
              <div className="max-h-[52vh] overflow-auto rounded-xl border border-line bg-[#0d0c0b] p-4">
                <pre className="whitespace-pre-wrap break-words font-mono text-[11.5px] leading-[1.75] text-[#d8d0c4]">
                  {preview.data.content}
                </pre>
              </div>
            )
          ) : (
            <div className="rounded-xl border border-dashed border-line px-4 py-10 text-center text-xs text-muted">
              There is no text to show for this document.
            </div>
          )}
        </div>
      ) : (
        <div className="flex items-center gap-2 text-xs text-muted">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Loading source…
        </div>
      )}
    </Dialog>
  );
}
