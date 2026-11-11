"use client";

import { useMemo, useState } from "react";
import { ShieldCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { useIntelligenceFindings } from "@/hooks/use-api";
import type { FindingConfidence } from "@/lib/types";
import { cn, pluralize } from "@/lib/utils";

import {
  FindingCard,
  PanelError,
  PanelLoading,
  StatCard,
  humanizeKind,
} from "./shared";

type Filter = "all" | FindingConfidence;

const FILTERS: Array<{ value: Filter; label: string }> = [
  { value: "all", label: "All" },
  { value: "confirmed", label: "Confirmed" },
  { value: "possible", label: "Possible" },
];

export function FindingsPanel({ projectId }: { projectId: string }) {
  const query = useIntelligenceFindings(projectId);
  const [filter, setFilter] = useState<Filter>("all");
  const [kind, setKind] = useState<string | null>(null);

  const findings = useMemo(() => {
    const items = query.data?.findings ?? [];
    return items.filter(
      (finding) =>
        (filter === "all" || finding.confidence === filter) &&
        (kind === null || finding.kind === kind),
    );
  }, [filter, kind, query.data]);

  const kinds = useMemo(
    () => Object.entries(query.data?.summary.by_kind ?? {}),
    [query.data],
  );

  if (query.isLoading) return <PanelLoading label="Investigating the index…" />;
  if (query.isError || !query.data) {
    return (
      <PanelError
        title="Could not investigate the project"
        error={query.error}
        onRetry={() => void query.refetch()}
      />
    );
  }

  const summary = query.data.summary;

  return (
    <div className="space-y-5">
      <section className="grid gap-3 sm:grid-cols-3">
        <StatCard
          label="Confirmed"
          value={String(summary.confirmed)}
          hint="the index settles these"
        />
        <StatCard
          label="Possible"
          value={String(summary.possible)}
          hint="a human should look"
        />
        <StatCard
          label="Kinds"
          value={String(kinds.length)}
          hint="distinct finding categories"
        />
      </section>

      <p className="rounded-xl border border-line/70 bg-canvas/30 px-4 py-3 text-[11px] leading-relaxed text-muted">
        Every finding comes from the stored index and never from a model.
        <span className="text-parchment"> Confirmed</span> means the evidence is
        complete inside the project (an import that names a missing file, a bare{" "}
        <code>except:</code>); <span className="text-parchment">possible</span>{" "}
        means the index cannot decide, because runtime behaviour or unindexed
        files are involved.
      </p>

      <Card>
        <CardHeader>
          <CardTitle>Filter</CardTitle>
          <Badge mono>{pluralize(findings.length, "finding")}</Badge>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-1.5">
            {FILTERS.map((item) => (
              <button
                key={item.value}
                type="button"
                onClick={() => setFilter(item.value)}
                className={cn(
                  "rounded-lg border px-2.5 py-1.5 text-[11px] transition-colors",
                  filter === item.value
                    ? "border-copper/40 bg-copper/10 text-copper"
                    : "border-line text-muted hover:border-line-strong hover:text-parchment",
                )}
              >
                {item.label}
              </button>
            ))}
          </div>
          {kinds.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {kinds.map(([name, count]) => (
                <button
                  key={name}
                  type="button"
                  onClick={() => setKind((current) => (current === name ? null : name))}
                  className={cn(
                    "rounded-full border px-2.5 py-1 font-mono text-[9.5px] transition-colors",
                    kind === name
                      ? "border-copper/40 bg-copper/10 text-copper"
                      : "border-line bg-surface-2/50 text-muted hover:text-parchment",
                  )}
                >
                  {humanizeKind(name)} <span className="opacity-70">{count}</span>
                </button>
              ))}
            </div>
          ) : null}
        </CardContent>
      </Card>

      {findings.length === 0 ? (
        <EmptyState
          icon={<ShieldCheck className="h-4 w-4" />}
          title={
            summary.confirmed + summary.possible === 0
              ? "Nothing to report"
              : "No findings match this filter"
          }
          description={
            summary.confirmed + summary.possible === 0
              ? "No import, pattern or configuration problems were found in the indexed files."
              : "Clear the confidence or kind filter to see the rest."
          }
        />
      ) : (
        <div className="space-y-2">
          {findings.map((finding, index) => (
            <FindingCard
              key={`${finding.kind}:${finding.message}:${index}`}
              projectId={projectId}
              kind={finding.kind}
              message={finding.message}
              severity={finding.severity}
              confirmed={finding.confidence === "confirmed"}
              details={finding.details}
            />
          ))}
        </div>
      )}
    </div>
  );
}
