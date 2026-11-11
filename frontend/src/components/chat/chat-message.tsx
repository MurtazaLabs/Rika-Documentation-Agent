"use client";

import { useState } from "react";
import {
  AlertTriangle,
  Check,
  Copy,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";

import { CitationList } from "@/components/chat/citation-list";
import { IntelligenceCitations } from "@/components/chat/intelligence-citations";
import { MarkdownAnswer } from "@/components/chat/markdown-answer";
import { RikaMark } from "@/components/ui/brand";
import { useToast } from "@/components/ui/toast";
import type {
  ChatIntelligenceItem,
  Citation,
  MessageRole,
} from "@/lib/types";
import { cn, copyText, formatTime } from "@/lib/utils";

export interface ChatThreadMessage {
  id: string;
  role: MessageRole;
  content: string;
  citations: Citation[];
  intelligence?: ChatIntelligenceItem[];
  createdAt: string;
  streaming?: boolean;
  error?: string;
  warnings?: string[];
  grounded?: boolean;
  retrievedChunks?: number;
}

function TypingDots() {
  return (
    <span className="inline-flex items-center gap-1 py-1">
      {[0, 1, 2].map((index) => (
        <span
          key={index}
          className="h-1.5 w-1.5 animate-[pulse-soft_1.4s_ease-in-out_infinite] rounded-full bg-copper"
          style={{ animationDelay: `${index * 180}ms` }}
        />
      ))}
    </span>
  );
}

export function ChatMessageView({
  message,
  projectId,
  onOpenCitation,
}: {
  message: ChatThreadMessage;
  projectId: string;
  onOpenCitation: (citation: Citation) => void;
}) {
  const { toast } = useToast();
  const [copied, setCopied] = useState(false);

  if (message.role === "user") {
    return (
      <div className="flex flex-col items-end gap-1.5">
        <div className="max-w-[85%] rounded-2xl rounded-br-md border border-copper/20 bg-copper/10 px-4 py-2.5 text-[13px] leading-relaxed text-parchment">
          <p className="whitespace-pre-wrap break-words">{message.content}</p>
        </div>
        <p className="pr-1 text-[9px] text-faint">
          You · {formatTime(message.createdAt)}
        </p>
      </div>
    );
  }

  const copy = async () => {
    const done = await copyText(message.content);
    if (done) {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } else {
      toast({ title: "Could not copy the answer", tone: "error" });
    }
  };

  return (
    <div className="flex items-start gap-3">
      <RikaMark className="mt-0.5 h-7 w-7 shrink-0" />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-[11px] font-medium text-parchment">Rika</p>
          <span className="text-[9px] text-faint">
            {formatTime(message.createdAt)}
          </span>
          {message.streaming ? (
            <span className="font-mono text-[9px] uppercase tracking-[0.14em] text-copper">
              writing
            </span>
          ) : message.grounded === false ? (
            <span className="inline-flex items-center gap-1 font-mono text-[9px] uppercase tracking-[0.12em] text-gold">
              <ShieldAlert className="h-3 w-3" />
              no evidence
            </span>
          ) : message.grounded ? (
            <span className="inline-flex items-center gap-1 font-mono text-[9px] uppercase tracking-[0.12em] text-sage">
              <ShieldCheck className="h-3 w-3" />
              cited
            </span>
          ) : null}
          {message.retrievedChunks !== undefined && message.retrievedChunks > 0 ? (
            <span className="text-[9px] text-faint">
              {message.retrievedChunks} passages retrieved
            </span>
          ) : null}
        </div>

        <div className="mt-2">
          {message.error ? (
            <div className="flex items-start gap-2 rounded-xl border border-rose/30 bg-rose/10 px-3.5 py-3 text-[11px] leading-relaxed text-rose">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <div>
                <p className="font-medium">The answer could not be completed.</p>
                <p className="mt-0.5 text-rose/80">{message.error}</p>
              </div>
            </div>
          ) : message.content ? (
            <MarkdownAnswer
              content={message.content}
              citations={message.citations}
              onCitationClick={onOpenCitation}
            />
          ) : (
            <div className="flex items-center gap-2 text-xs text-muted">
              <TypingDots />
              <span>Retrieving evidence and writing…</span>
            </div>
          )}

          {message.streaming && message.content ? (
            <span className="caret" aria-hidden="true" />
          ) : null}

          {message.warnings && message.warnings.length > 0 ? (
            <ul className="mt-3 space-y-1">
              {message.warnings.map((warning) => (
                <li
                  key={warning}
                  className="flex items-start gap-1.5 rounded-lg border border-gold/20 bg-gold/5 px-2.5 py-1.5 text-[10px] leading-relaxed text-gold"
                >
                  <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
                  {warning}
                </li>
              ))}
            </ul>
          ) : null}

          <CitationList citations={message.citations} onOpen={onOpenCitation} />

          <IntelligenceCitations
            items={message.intelligence ?? []}
            projectId={projectId}
          />

          {!message.streaming && message.content ? (
            <div className="mt-2.5 flex items-center gap-1">
              <button
                type="button"
                onClick={copy}
                className={cn(
                  "inline-flex items-center gap-1 rounded px-1.5 py-1 text-[9px] transition-colors",
                  copied
                    ? "text-sage"
                    : "text-faint hover:bg-surface-2 hover:text-muted",
                )}
              >
                {copied ? (
                  <Check className="h-3 w-3" />
                ) : (
                  <Copy className="h-3 w-3" />
                )}
                {copied ? "Copied" : "Copy answer"}
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
