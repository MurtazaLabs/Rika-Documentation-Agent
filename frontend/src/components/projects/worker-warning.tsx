"use client";

import { CircleAlert } from "lucide-react";

import { useReadiness } from "@/hooks/use-api";
import { cn } from "@/lib/utils";

/**
 * Visible only while readiness reports an unreachable Celery worker.
 *
 * Uploads are stored and queued by the API, so without this every job looks
 * healthy at `queued` while nothing parses or embeds the files.
 */
export function WorkerWarning({ className }: { className?: string }) {
  const readiness = useReadiness();
  const worker = readiness.data?.checks.find((check) => check.name === "worker");
  if (!worker || worker.status === "ok") return null;

  return (
    <div
      role="alert"
      className={cn(
        "flex items-start gap-2.5 rounded-xl border border-gold/30 bg-gold/5 p-3",
        className,
      )}
    >
      <CircleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0 text-gold" />
      <div className="min-w-0">
        <p className="text-[11px] font-medium text-parchment">
          Indexing worker is offline
        </p>
        <p className="mt-1 text-[10px] leading-relaxed text-muted">
          Uploads are stored but stay <span className="font-mono">queued</span>:
          parsing, chunking and embeddings only run while a Celery worker is
          running. Start one in{" "}
          <span className="font-mono">backend/</span> with{" "}
          <span className="font-mono">
            python -m celery -A app.workers.celery_app worker
          </span>
          .
        </p>
      </div>
    </div>
  );
}
