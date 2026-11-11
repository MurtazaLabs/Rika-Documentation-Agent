import { Activity, CircleAlert, CircleCheck, Loader2 } from "lucide-react";

import type { DependencyCheck, Readiness } from "@/lib/types";
import { cn } from "@/lib/utils";

type DotTone = "ok" | "error" | "warning" | "idle";

const DOT_TONES: Record<DotTone, string> = {
  ok: "bg-sage shadow-[0_0_0_3px_rgba(157,181,164,0.12)]",
  error: "bg-rose shadow-[0_0_0_3px_rgba(217,138,138,0.12)]",
  warning: "bg-gold shadow-[0_0_0_3px_rgba(217,178,111,0.12)]",
  idle: "bg-faint",
};

export function StatusDot({
  tone = "idle",
  pulse = false,
  className,
}: {
  tone?: DotTone;
  pulse?: boolean;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-block h-1.5 w-1.5 shrink-0 rounded-full",
        DOT_TONES[tone],
        pulse && "animate-[pulse-soft_2s_ease-in-out_infinite]",
        className,
      )}
    />
  );
}

export function ReadinessPill({
  readiness,
  loading = false,
}: {
  readiness?: Readiness;
  loading?: boolean;
}) {
  if (loading) {
    return (
      <span className="inline-flex items-center gap-2 rounded-full border border-line bg-surface-2/60 px-2.5 py-1 text-[10px] text-muted">
        <Loader2 className="h-3 w-3 animate-spin" />
        Checking
      </span>
    );
  }

  if (!readiness) {
    return (
      <span className="inline-flex items-center gap-2 rounded-full border border-line bg-surface-2/60 px-2.5 py-1 text-[10px] text-faint">
        <StatusDot tone="idle" />
        Offline
      </span>
    );
  }

  const tone: DotTone =
    readiness.status === "ready"
      ? "ok"
      : readiness.status === "degraded"
        ? "warning"
        : "error";
  const label =
    readiness.status === "ready"
      ? "Systems nominal"
      : readiness.status === "degraded"
        ? "Degraded"
        : "Unavailable";

  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-line bg-surface-2/60 px-2.5 py-1 text-[10px] text-muted">
      <StatusDot tone={tone} pulse={tone !== "ok"} />
      {label}
    </span>
  );
}

export function DependencyRow({ check }: { check: DependencyCheck }) {
  const labels: Record<string, string> = {
    postgres: "PostgreSQL",
    redis: "Redis queue",
    chat_model: "Chat model",
    embedding_model: "Embedding model",
  };
  const ok = check.status === "ok";

  return (
    <div className="flex items-start justify-between gap-3 py-2.5">
      <div className="flex min-w-0 items-start gap-2.5">
        {ok ? (
          <CircleCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-sage" />
        ) : (
          <CircleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0 text-rose" />
        )}
        <div className="min-w-0">
          <p className="text-xs text-parchment">{labels[check.name] ?? check.name}</p>
          {check.detail ? (
            <p className="mt-0.5 break-words text-[10px] leading-relaxed text-faint">
              {check.detail}
            </p>
          ) : null}
        </div>
      </div>
      <span
        className={cn(
          "shrink-0 font-mono text-[9px] uppercase tracking-[0.14em]",
          ok ? "text-sage" : "text-rose",
        )}
      >
        {ok ? "ok" : check.critical ? "down" : "offline"}
      </span>
    </div>
  );
}

export function SystemHealthIcon({ readiness }: { readiness?: Readiness }) {
  return (
    <Activity
      className={cn(
        "h-4 w-4",
        readiness?.status === "ready"
          ? "text-sage"
          : readiness
            ? "text-gold"
            : "text-faint",
      )}
    />
  );
}
