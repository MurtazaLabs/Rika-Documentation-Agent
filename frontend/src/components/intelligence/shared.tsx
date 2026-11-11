"use client";

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  FileCode,
  Loader2,
  RefreshCw,
} from "lucide-react";

import { SourceViewer } from "@/components/source-viewer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useAllDocuments } from "@/hooks/use-api";
import { cn, errorMessage } from "@/lib/utils";

export function StatCard({
  label,
  value,
  hint,
  loading,
}: {
  label: string;
  value: string;
  hint?: string;
  loading?: boolean;
}) {
  return (
    <div className="rounded-2xl border border-line bg-surface/70 px-4 py-4">
      <p className="font-mono text-[9px] uppercase tracking-[0.18em] text-faint">
        {label}
      </p>
      {loading ? (
        <Skeleton className="mt-3 h-7 w-12" />
      ) : (
        <p className="mt-2 font-serif text-[1.75rem] leading-none tracking-[-0.03em] text-parchment">
          {value}
        </p>
      )}
      {hint ? <p className="mt-1.5 text-[10px] text-muted">{hint}</p> : null}
    </div>
  );
}

/**
 * A path that opens the indexed source at a line.
 *
 * Intelligence reports speak in project paths, while the viewer needs a
 * document id, so the path is resolved against the project's documents. Files
 * that were never uploaded stay plain text instead of pretending to open.
 */
export function FileButton({
  projectId,
  path,
  startLine,
  endLine,
  className,
}: {
  projectId: string;
  path: string;
  startLine?: number | null;
  endLine?: number | null;
  className?: string;
}) {
  const documents = useAllDocuments(projectId);
  const [open, setOpen] = useState(false);

  const documentId = useMemo(() => {
    const items = documents.data?.items ?? [];
    return (
      items.find((item) => item.original_path === path)?.id ??
      items.find(
        (item) =>
          item.original_path.endsWith(`/${path}`) ||
          path.endsWith(`/${item.original_path}`),
      )?.id
    );
  }, [documents.data, path]);

  if (!documentId) {
    return (
      <span
        className={cn("font-mono text-[11px] text-muted", className)}
        title="This path is not in the index"
      >
        {path}
      </span>
    );
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        title={`Open ${path}`}
        className={cn(
          "inline-flex max-w-full items-center gap-1.5 text-left font-mono text-[11px] text-muted underline-offset-2 transition-colors hover:text-copper hover:underline",
          className,
        )}
      >
        <FileCode className="h-3 w-3 shrink-0 text-faint" />
        <span className="truncate">{path}</span>
      </button>
      <SourceViewer
        open={open}
        onClose={() => setOpen(false)}
        documentId={documentId}
        projectId={projectId}
        highlight={
          startLine != null
            ? { startLine, endLine: endLine ?? startLine }
            : undefined
        }
      />
    </>
  );
}

export function ConfidenceBadge({ confirmed }: { confirmed: boolean }) {
  return (
    <Badge tone={confirmed ? "sage" : "gold"}>
      {confirmed ? (
        <CheckCircle2 className="h-3 w-3" />
      ) : (
        <AlertTriangle className="h-3 w-3" />
      )}
      {confirmed ? "confirmed" : "possible"}
    </Badge>
  );
}

export function SeverityBadge({ severity }: { severity: string }) {
  const tone =
    severity === "error"
      ? "rose"
      : severity === "warning"
        ? "gold"
        : severity === "info"
          ? "blue"
          : "neutral";
  return (
    <Badge tone={tone} mono>
      {severity}
    </Badge>
  );
}

export function humanizeKind(kind: string) {
  const text = kind.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function formatDetailValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (Array.isArray(value)) return value.map(formatDetailValue).join(" · ");
  if (typeof value === "object") {
    const record = value as Record<string, unknown>;
    if (typeof record.path === "string") {
      return record.line != null
        ? `${record.path}:${record.line}`
        : record.path;
    }
    return JSON.stringify(value);
  }
  return String(value);
}

export function DetailList({
  details,
}: {
  details: Record<string, unknown>;
}) {
  const entries = Object.entries(details).filter(
    ([key]) => key !== "file_path" && key !== "line",
  );
  if (entries.length === 0) return null;
  return (
    <dl className="mt-2 grid gap-x-4 gap-y-1 text-[10px] sm:grid-cols-2">
      {entries.map(([key, value]) => (
        <div key={key} className="flex min-w-0 gap-1.5">
          <dt className="shrink-0 font-mono text-faint">
            {key.replace(/_/g, " ")}
          </dt>
          <dd className="min-w-0 truncate text-muted" title={formatDetailValue(value)}>
            {formatDetailValue(value)}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function FindingCard({
  projectId,
  kind,
  message,
  severity,
  confirmed,
  details,
}: {
  projectId: string;
  kind: string;
  message: string;
  severity: string;
  confirmed: boolean;
  details: Record<string, unknown>;
}) {
  const filePath =
    typeof details.file_path === "string" ? details.file_path : null;
  const line = typeof details.line === "number" ? details.line : null;

  return (
    <div className="rounded-xl border border-line/70 bg-canvas/30 px-3.5 py-3">
      <div className="flex flex-wrap items-center gap-1.5">
        <ConfidenceBadge confirmed={confirmed} />
        <SeverityBadge severity={severity} />
        <span className="font-mono text-[9px] uppercase tracking-[0.12em] text-faint">
          {humanizeKind(kind)}
        </span>
      </div>
      <p className="mt-2 text-[12px] leading-relaxed text-parchment">
        {message}
      </p>
      {filePath ? (
        <div className="mt-2">
          <FileButton projectId={projectId} path={filePath} startLine={line} />
        </div>
      ) : null}
      <DetailList details={details} />
    </div>
  );
}

export function PanelLoading({ label = "Reading the index…" }: { label?: string }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-[11px] text-muted">
        <Loader2 className="h-3.5 w-3.5 animate-spin text-copper" />
        {label}
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[0, 1, 2, 3].map((index) => (
          <Skeleton key={index} className="h-24 w-full" />
        ))}
      </div>
      <Skeleton className="h-64 w-full" />
    </div>
  );
}

export function PanelError({
  title,
  error,
  onRetry,
}: {
  title: string;
  error: unknown;
  onRetry: () => void;
}) {
  return (
    <EmptyState
      icon={<AlertTriangle className="h-4 w-4" />}
      title={title}
      description={errorMessage(error)}
      action={
        <Button onClick={onRetry} icon={<RefreshCw className="h-3.5 w-3.5" />}>
          Try again
        </Button>
      }
    />
  );
}
