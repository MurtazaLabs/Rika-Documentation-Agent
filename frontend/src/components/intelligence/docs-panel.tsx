"use client";

import { useMemo } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ProgressBar } from "@/components/ui/progress";
import { EmptyState } from "@/components/ui/empty-state";
import { useIntelligenceDocs } from "@/hooks/use-api";
import { pluralize } from "@/lib/utils";

import {
  FileButton,
  FindingCard,
  PanelError,
  PanelLoading,
  StatCard,
  humanizeKind,
} from "./shared";

export function DocsPanel({ projectId }: { projectId: string }) {
  const query = useIntelligenceDocs(projectId);

  const grouped = useMemo(() => {
    const groups = new Map<string, { confirmed: number; total: number }>();
    for (const finding of query.data?.findings ?? []) {
      const current = groups.get(finding.kind) ?? { confirmed: 0, total: 0 };
      current.total += 1;
      if (finding.confirmed) current.confirmed += 1;
      groups.set(finding.kind, current);
    }
    return [...groups.entries()];
  }, [query.data]);

  if (query.isLoading) return <PanelLoading label="Comparing docs with the code…" />;
  if (query.isError || !query.data) {
    return (
      <PanelError
        title="Could not compare documentation"
        error={query.error}
        onRetry={() => void query.refetch()}
      />
    );
  }

  const data = query.data;
  const documented = data.routes.documented;
  const implemented = data.routes.implemented;
  const coverage =
    documented > 0 ? Math.min(100, (implemented / documented) * 100) : 0;

  return (
    <div className="space-y-5">
      <section className="grid gap-3 sm:grid-cols-3">
        <StatCard
          label="Documented routes"
          value={String(documented)}
          hint={
            data.readme
              ? "from the README route tables"
              : "no README is indexed"
          }
        />
        <StatCard
          label="Implemented routes"
          value={String(implemented)}
          hint="discovered from decorators"
        />
        <StatCard
          label="Doc findings"
          value={String(data.findings.length)}
          hint={`${data.findings.filter((item) => item.confirmed).length} confirmed`}
        />
      </section>

      <Card>
        <CardHeader>
          <div>
            <CardTitle>Documentation</CardTitle>
            <p className="mt-1 text-[11px] text-muted">
              The index of what the docs promise against what the code does.
            </p>
          </div>
          {data.readme ? (
            <FileButton projectId={projectId} path={data.readme} />
          ) : (
            <Badge tone="gold">no README</Badge>
          )}
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-muted">Route coverage</span>
            <span className="font-mono text-[10px] text-faint">
              {implemented} / {documented || "—"}
            </span>
          </div>
          <ProgressBar value={coverage} tone={coverage >= 80 ? "sage" : "gold"} className="mt-1.5" />
          <p className="mt-2.5 text-[10px] leading-relaxed text-faint">
            Paths are normalised before comparing: <code>/api/v1</code> prefixes
            are dropped and path parameters are compared by shape. A documented
            route with no handler stays <em>possible</em>, because the handler
            may live in a file that was never uploaded.
          </p>
        </CardContent>
      </Card>

      {grouped.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>By kind</CardTitle>
            <Badge mono>{pluralize(data.findings.length, "finding")}</Badge>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-1.5">
            {grouped.map(([kind, counts]) => (
              <Badge key={kind} mono>
                {humanizeKind(kind)}
                <span className="opacity-70">
                  {counts.total}
                  {counts.confirmed > 0 ? ` (${counts.confirmed}✓)` : ""}
                </span>
              </Badge>
            ))}
          </CardContent>
        </Card>
      ) : null}

      {data.findings.length === 0 ? (
        <EmptyState
          icon={<Badge tone="sage">ok</Badge>}
          title="Docs and code agree"
          description="No route, table, settings or link drift was found in the indexed files."
        />
      ) : (
        <div className="space-y-2">
          {data.findings.map((finding, index) => (
            <FindingCard
              key={`${finding.kind}:${finding.message}:${index}`}
              projectId={projectId}
              kind={finding.kind}
              message={finding.message}
              severity={finding.severity}
              confirmed={finding.confirmed}
              details={finding.details}
            />
          ))}
        </div>
      )}
    </div>
  );
}
