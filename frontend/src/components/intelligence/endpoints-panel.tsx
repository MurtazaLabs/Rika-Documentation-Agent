"use client";

import { useMemo, useState } from "react";
import { Search, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input, Select } from "@/components/ui/input";
import { useIntelligenceRoutes } from "@/hooks/use-api";
import { cn, pluralize } from "@/lib/utils";

import { FileButton, PanelError, PanelLoading } from "./shared";

const METHODS = ["all", "GET", "POST", "PUT", "PATCH", "DELETE"] as const;

type Method = (typeof METHODS)[number];

const METHOD_TONES: Record<string, "blue" | "sage" | "gold" | "rose" | "violet" | "neutral"> = {
  GET: "blue",
  POST: "sage",
  PUT: "gold",
  PATCH: "violet",
  DELETE: "rose",
};

export function EndpointsPanel({ projectId }: { projectId: string }) {
  const [method, setMethod] = useState<Method>("all");
  const [filter, setFilter] = useState("");
  const query = useIntelligenceRoutes(
    projectId,
    method === "all" ? undefined : method,
  );

  const flows = useMemo(() => {
    const items = query.data ?? [];
    const needle = filter.trim().toLowerCase();
    if (!needle) return items;
    return items.filter(
      (flow) =>
        flow.path.toLowerCase().includes(needle) ||
        flow.handler.toLowerCase().includes(needle),
    );
  }, [filter, query.data]);

  if (query.isLoading) return <PanelLoading label="Discovering endpoints…" />;
  if (query.isError) {
    return (
      <PanelError
        title="Could not discover endpoints"
        error={query.error}
        onRetry={() => void query.refetch()}
      />
    );
  }

  const total = query.data?.length ?? 0;

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="flex flex-col gap-2 p-4 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-faint" />
            <Input
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
              placeholder="Filter by path or handler"
              aria-label="Filter endpoints"
              className="h-10 pl-10"
            />
          </div>
          <Select
            value={method}
            onChange={(event) => setMethod(event.target.value as Method)}
            aria-label="HTTP method"
            className="h-10 w-full sm:w-36"
          >
            {METHODS.map((item) => (
              <option key={item} value={item}>
                {item === "all" ? "All methods" : item}
              </option>
            ))}
          </Select>
          {filter ? (
            <button
              type="button"
              onClick={() => setFilter("")}
              className="inline-flex items-center gap-1 self-start text-[10px] text-faint hover:text-parchment sm:self-auto"
            >
              <X className="h-3 w-3" /> Clear
            </button>
          ) : null}
        </CardContent>
      </Card>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[11px] text-muted">
          {query.isFetching
            ? "Refreshing…"
            : `${pluralize(flows.length, "endpoint")}${
                flows.length !== total ? ` of ${total}` : ""
              }`}
        </p>
        <p className="text-[10px] text-faint">
          Routes are read from decorators; the router prefix is folded in.
        </p>
      </div>

      {flows.length === 0 ? (
        <EmptyState
          icon={<Search className="h-4 w-4" />}
          title={total === 0 ? "No endpoints found" : "No matching endpoints"}
          description={
            total === 0
              ? "The parser recognises FastAPI and Flask route decorators. Upload the API files and reindex, then check again."
              : "Try a different path fragment or method."
          }
        />
      ) : (
        <Card>
          <CardContent className="p-2">
            <ul className="divide-y divide-line/50">
              {flows.map((flow) => (
                <li
                  key={`${flow.method}:${flow.path}:${flow.file_path}:${flow.line}`}
                  className="rounded-lg px-2 py-2.5 transition-colors hover:bg-surface-2/40"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge mono tone={METHOD_TONES[flow.method] ?? "neutral"}>
                      {flow.method}
                    </Badge>
                    <span className="min-w-0 flex-1 break-all font-mono text-[11.5px] text-parchment">
                      {flow.path}
                    </span>
                    {flow.framework ? <Badge mono>{flow.framework}</Badge> : null}
                  </div>
                  <div className="mt-1.5 flex flex-wrap items-center gap-2">
                    <span className="text-[10px] text-muted">
                      {flow.handler}
                    </span>
                    <span className={cn("text-[9px] text-faint")}>·</span>
                    <FileButton
                      projectId={projectId}
                      path={flow.file_path}
                      startLine={flow.line}
                    />
                  </div>
                  {flow.imports.length > 0 ? (
                    <p className="mt-1 truncate text-[9.5px] text-faint">
                      uses {flow.imports.slice(0, 5).join(", ")}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
