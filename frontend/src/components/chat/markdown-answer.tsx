"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { Citation } from "@/lib/types";

/**
 * Inline `[S1]` markers become buttons.
 *
 * Only markers that resolved to a stored chunk are turned into links. The
 * backend already removes unknown markers, but a streaming response can show a
 * partial marker, so the UI never presents an unresolved one as a source.
 */
export function MarkdownAnswer({
  content,
  citations,
  onCitationClick,
}: {
  content: string;
  citations: Citation[];
  onCitationClick: (citation: Citation) => void;
}) {
  const byMarker = new Map(citations.map((citation) => [citation.marker, citation]));
  const prepared = content.replace(/\[(S\d+)\]/g, (match, marker: string) =>
    byMarker.has(marker) ? `[${marker}](#citation-${marker})` : match,
  );

  return (
    <div className="answer-prose">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => {
            if (href?.startsWith("#citation-")) {
              const marker = href.slice("#citation-".length);
              const citation = byMarker.get(marker);
              if (citation) {
                return (
                  <button
                    type="button"
                    onClick={() => onCitationClick(citation)}
                    className="mx-0.5 inline-flex translate-y-[-1px] items-center rounded border border-copper/30 bg-copper/10 px-1 py-0 align-baseline font-mono text-[9px] leading-4 text-copper transition-colors hover:border-copper/60 hover:bg-copper/20"
                    title={`${citation.file_path} · ${citation.marker}`}
                  >
                    {children}
                  </button>
                );
              }
            }
            return (
              <a href={href} target="_blank" rel="noreferrer">
                {children}
              </a>
            );
          },
        }}
      >
        {prepared}
      </ReactMarkdown>
    </div>
  );
}
