"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useIntelligenceArchitecture } from "@/hooks/use-api";
import type { DatabaseTable } from "@/lib/types";
import { cn, pluralize, truncate } from "@/lib/utils";

import { FileButton, PanelError, PanelLoading } from "./shared";

function TableRow({ projectId, table }: { projectId: string; table: DatabaseTable }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <li className="rounded-xl border border-line/60 bg-canvas/30">
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        aria-expanded={expanded}
        className="flex w-full items-center gap-2 px-3 py-2.5 text-left"
      >
        <span className="min-w-0 flex-1 truncate font-mono text-[11.5px] text-parchment">
          {table.table}
        </span>
        <span className="shrink-0 text-[10px] text-faint">
          {pluralize(table.columns.length, "column")}
        </span>
        <ChevronDown
          className={cn(
            "h-3.5 w-3.5 shrink-0 text-faint transition-transform",
            expanded && "rotate-180",
          )}
        />
      </button>
      {expanded ? (
        <div className="space-y-2.5 border-t border-line/50 px-3 py-3">
          <div className="flex flex-wrap items-center gap-2">
            {table.model ? (
              <Badge mono tone="violet">
                {table.model}
              </Badge>
            ) : null}
            <FileButton
              projectId={projectId}
              path={table.file_path}
              startLine={table.line}
            />
          </div>
          <div className="flex flex-wrap gap-1">
            {table.columns.map((column) => (
              <span
                key={column}
                className="rounded border border-line/70 bg-surface-2/50 px-1.5 py-0.5 font-mono text-[9.5px] text-muted"
              >
                {column}
              </span>
            ))}
          </div>
          {table.references.length > 0 ? (
            <p className="text-[10px] leading-relaxed text-faint">
              References: {table.references.join(", ")}
            </p>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}

function FlowRow({
  projectId,
  method,
  path,
  handler,
  filePath,
  line,
  framework,
}: {
  projectId: string;
  method: string;
  path: string;
  handler: string;
  filePath: string;
  line: number;
  framework: string | null;
}) {
  return (
    <li className="flex flex-wrap items-center gap-2 rounded-lg px-2 py-2 transition-colors hover:bg-surface-2/40">
      <Badge mono tone={method === "GET" ? "blue" : method === "DELETE" ? "rose" : "sage"}>
        {method}
      </Badge>
      <span className="min-w-0 flex-1 truncate font-mono text-[11px] text-parchment">
        {path}
      </span>
      <span className="hidden text-[10px] text-faint md:inline">{handler}</span>
      {framework ? <Badge mono>{framework}</Badge> : null}
      <FileButton projectId={projectId} path={filePath} startLine={line} />
    </li>
  );
}

export function ArchitecturePanel({ projectId }: { projectId: string }) {
  const query = useIntelligenceArchitecture(projectId);

  if (query.isLoading) return <PanelLoading label="Tracing layers and imports…" />;
  if (query.isError || !query.data) {
    return (
      <PanelError
        title="Could not analyse the architecture"
        error={query.error}
        onRetry={() => void query.refetch()}
      />
    );
  }

  const data = query.data;

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Layers</CardTitle>
            <p className="mt-1 text-[11px] text-muted">
              Grouped from file paths, with how much each layer imports and is
              imported by.
            </p>
          </div>
          <Badge mono>{pluralize(data.layers.length, "layer")}</Badge>
        </CardHeader>
        <CardContent>
          {data.layers.length === 0 ? (
            <p className="py-3 text-center text-[11px] text-muted">
              Upload code files to see layers.
            </p>
          ) : (
            <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
              {data.layers.map((layer) => (
                <div
                  key={layer.name}
                  className="rounded-xl border border-line/60 bg-canvas/30 px-3 py-2.5"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[12px] font-medium text-parchment">
                      {layer.name}
                    </span>
                    <Badge mono>{layer.side}</Badge>
                  </div>
                  <p className="mt-1.5 font-mono text-[10px] text-faint">
                    {layer.files}f · {layer.symbols}s · out {layer.imports_out} ·
                    in {layer.imported_by}
                  </p>
                </div>
              ))}
            </div>
          )}

          {data.edges.length > 0 ? (
            <div className="mt-4">
              <p className="font-mono text-[9px] uppercase tracking-[0.14em] text-faint">
                Dependencies between layers
              </p>
              <ul className="mt-2 space-y-1">
                {data.edges.map((edge) => (
                  <li
                    key={`${edge.source}-${edge.target}`}
                    className="flex items-center gap-2 text-[11px]"
                  >
                    <span className="text-parchment">{edge.source}</span>
                    <span className="text-copper">→</span>
                    <span className="text-parchment">{edge.target}</span>
                    <span className="font-mono text-[10px] text-faint">
                      {pluralize(edge.count, "import")}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <div className="grid gap-5 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Database</CardTitle>
              <p className="mt-1 text-[11px] text-muted">
                ORM tables, their columns and foreign keys.
              </p>
            </div>
            <Badge mono>{pluralize(data.database.tables.length, "table")}</Badge>
          </CardHeader>
          <CardContent className="p-3">
            {data.database.tables.length === 0 ? (
              <p className="px-2 py-3 text-center text-[11px] text-muted">
                No ORM models were found in the indexed files.
              </p>
            ) : (
              <ul className="space-y-1.5">
                {data.database.tables.map((table) => (
                  <TableRow
                    key={table.table}
                    projectId={projectId}
                    table={table}
                  />
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div>
              <CardTitle>Request flows</CardTitle>
              <p className="mt-1 text-[11px] text-muted">
                Handlers, the routes they belong to and the modules they pull
                in.
              </p>
            </div>
            <Badge mono>{data.request_flows.length}</Badge>
          </CardHeader>
          <CardContent className="p-2">
            {data.request_flows.length === 0 ? (
              <p className="px-2 py-3 text-center text-[11px] leading-relaxed text-muted">
                No HTTP handlers were found. The parser recognises FastAPI and
                Flask decorators in indexed files.
              </p>
            ) : (
              <ul className="divide-y divide-line/40">
                {data.request_flows.slice(0, 14).map((flow) => (
                  <li key={`${flow.method}:${flow.path}`} className="py-0.5">
                    <FlowRow
                      projectId={projectId}
                      method={flow.method}
                      path={flow.path}
                      handler={flow.handler}
                      filePath={flow.file_path}
                      line={flow.line}
                      framework={flow.framework}
                    />
                    {flow.imports.length > 0 ? (
                      <p className="truncate px-2 pb-1.5 text-[9.5px] text-faint">
                        uses {flow.imports.slice(0, 4).join(", ")}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div>
            <CardTitle>Module responsibilities</CardTitle>
            <p className="mt-1 text-[11px] text-muted">
              What each layer says it does, taken from module docstrings.
            </p>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {data.responsibilities.length === 0 ? (
            <p className="py-3 text-center text-[11px] text-muted">
              Docstrings are needed to describe responsibilities.
            </p>
          ) : (
            data.responsibilities.map((group) => (
              <details
                key={group.layer}
                className="rounded-xl border border-line/60 bg-canvas/30 px-3 py-2.5"
              >
                <summary className="flex cursor-pointer items-center gap-2 text-[12px] text-parchment">
                  <span className="flex-1">{group.layer}</span>
                  <Badge mono>{group.side}</Badge>
                  <span className="font-mono text-[10px] text-faint">
                    {soleModules(group.modules.length)}
                  </span>
                </summary>
                <ul className="mt-2 space-y-2 border-t border-line/50 pt-2">
                  {group.modules.map((module) => (
                    <li key={module.path}>
                      <FileButton projectId={projectId} path={module.path} />
                      <p className="mt-0.5 text-[10.5px] leading-relaxed text-muted">
                        {module.doc
                          ? truncate(module.doc, 220)
                          : `${pluralize(module.symbols, "symbol")}, no docstring`}
                      </p>
                    </li>
                  ))}
                </ul>
              </details>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function soleModules(count: number) {
  return count === 1 ? "1 module" : `${count} modules`;
}
