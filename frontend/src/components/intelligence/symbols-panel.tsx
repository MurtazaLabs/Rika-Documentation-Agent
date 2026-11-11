"use client";

import { useMemo, useState } from "react";
import { Loader2, Search } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input, Select } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useIntelligenceSymbol,
  useIntelligenceSymbols,
} from "@/hooks/use-api";
import type { SymbolHit } from "@/lib/types";
import { cn, errorMessage, pluralize } from "@/lib/utils";

import { FileButton, PanelError } from "./shared";

const SYMBOL_TYPES = [
  { value: "", label: "All symbols" },
  { value: "function", label: "Functions" },
  { value: "class", label: "Classes" },
  { value: "method", label: "Methods" },
  { value: "route", label: "Routes" },
  { value: "constant", label: "Constants" },
];

function SymbolRow({
  hit,
  active,
  onSelect,
}: {
  hit: SymbolHit;
  active: boolean;
  onSelect: () => void;
}) {
  return (
    <li>
      <button
        type="button"
        onClick={onSelect}
        aria-current={active ? "true" : undefined}
        className={cn(
          "w-full rounded-lg px-3 py-2.5 text-left transition-colors",
          active ? "bg-copper/10" : "hover:bg-surface-2/50",
        )}
      >
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "min-w-0 flex-1 truncate font-mono text-[11.5px]",
              active ? "text-copper" : "text-parchment",
            )}
          >
            {hit.qualified_name}
          </span>
          <Badge mono tone="violet">
            {hit.symbol_type}
          </Badge>
        </div>
        <p className="mt-1 truncate text-[10px] text-faint">
          {hit.path}:{hit.start_line}–{hit.end_line}
        </p>
      </button>
    </li>
  );
}

function DetailView({
  projectId,
  symbolId,
  onSelectSymbol,
}: {
  projectId: string;
  symbolId: string;
  onSelectSymbol: (hit: SymbolHit) => void;
}) {
  const query = useIntelligenceSymbol(projectId, symbolId);

  if (query.isLoading) {
    return (
      <div className="space-y-2 p-4">
        {[0, 1, 2, 3].map((index) => (
          <Skeleton key={index} className="h-5 w-full" />
        ))}
      </div>
    );
  }
  if (query.isError || !query.data) {
    return (
      <p className="p-4 text-[11px] text-rose">
        {errorMessage(query.error, "This symbol could not be loaded.")}
      </p>
    );
  }

  const detail = query.data;
  const symbol = detail.symbol;

  return (
    <div className="space-y-4 p-4">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="min-w-0 break-all font-mono text-[13px] text-parchment">
            {symbol.qualified_name}
          </h3>
          <Badge mono tone="violet">
            {symbol.symbol_type}
          </Badge>
          {symbol.language ? <Badge mono>{symbol.language}</Badge> : null}
        </div>
        <div className="mt-1.5">
          <FileButton
            projectId={projectId}
            path={symbol.path}
            startLine={symbol.start_line}
            endLine={symbol.end_line}
          />
        </div>
        {detail.doc ? (
          <p className="mt-2.5 text-[11.5px] leading-relaxed text-muted">
            {detail.doc}
          </p>
        ) : (
          <p className="mt-2.5 text-[11px] text-faint">
            This symbol has no docstring, so the definition below is the whole
            explanation available.
          </p>
        )}
      </div>

      {detail.signature ? (
        <pre className="overflow-x-auto rounded-lg border border-line/70 bg-[#0d0c0b] px-3 py-2 font-mono text-[10.5px] leading-relaxed text-[#d8d0c4]">
          {detail.signature}
        </pre>
      ) : null}

      <div>
        <p className="font-mono text-[9px] uppercase tracking-[0.14em] text-faint">
          Definition · lines {symbol.start_line}–{symbol.end_line}
        </p>
        <pre className="mt-1.5 max-h-80 overflow-auto rounded-lg border border-line/70 bg-[#0d0c0b] px-3 py-2 font-mono text-[10.5px] leading-[1.7] text-[#d8d0c4]">
          {detail.definition || "No source lines were stored for this symbol."}
        </pre>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <p className="font-mono text-[9px] uppercase tracking-[0.14em] text-faint">
            Imports in this file
          </p>
          {detail.imports.length === 0 ? (
            <p className="mt-1 text-[10.5px] text-muted">None stored.</p>
          ) : (
            <ul className="mt-1 space-y-1">
              {detail.imports.slice(0, 10).map((item) => (
                <li
                  key={`${item.reference}:${item.resolved_path ?? ""}`}
                  className="flex flex-wrap items-center gap-1.5 text-[10.5px]"
                >
                  <span className="font-mono text-parchment">
                    {item.reference}
                  </span>
                  {item.resolved_path ? (
                    <Badge tone="sage" mono>
                      internal
                    </Badge>
                  ) : item.external ? (
                    <Badge mono>external</Badge>
                  ) : (
                    <Badge tone="gold" mono>
                      unresolved
                    </Badge>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div>
          <p className="font-mono text-[9px] uppercase tracking-[0.14em] text-faint">
            Imported by
          </p>
          {detail.imported_by.length === 0 ? (
            <p className="mt-1 text-[10.5px] text-muted">
              Nothing in the index imports this file.
            </p>
          ) : (
            <ul className="mt-1 space-y-1">
              {detail.imported_by.slice(0, 10).map((path) => (
                <li key={path}>
                  <FileButton projectId={projectId} path={path} />
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {detail.related_symbols.length > 0 ? (
        <div>
          <p className="font-mono text-[9px] uppercase tracking-[0.14em] text-faint">
            Related symbols in this file
          </p>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {detail.related_symbols.map((related) => (
              <button
                key={related.id}
                type="button"
                onClick={() => onSelectSymbol(related)}
                className="rounded-full border border-line bg-surface-2/50 px-2.5 py-1 font-mono text-[10px] text-muted transition-colors hover:border-copper/30 hover:text-parchment"
              >
                {related.name}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <div>
        <p className="font-mono text-[9px] uppercase tracking-[0.14em] text-faint">
          References · {pluralize(detail.references.length, "match", "matches")}
        </p>
        {detail.references.length === 0 ? (
          <p className="mt-1 text-[10.5px] text-muted">
            The name appears nowhere else in the indexed text.
          </p>
        ) : (
          <ul className="mt-1.5 space-y-1.5">
            {detail.references.map((reference) => (
              <li
                key={`${reference.path}:${reference.line}`}
                className="rounded-lg border border-line/60 bg-canvas/30 px-2.5 py-2"
              >
                <FileButton
                  projectId={projectId}
                  path={reference.path}
                  startLine={reference.line}
                />
                <p className="mt-1 overflow-hidden font-mono text-[10px] leading-relaxed text-muted [display:-webkit-box] [-webkit-box-orient:vertical] [-webkit-line-clamp:2]">
                  {reference.snippet}
                </p>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-2 text-[9.5px] leading-relaxed text-faint">
          References are textual matches in the indexed lines, not a resolved
          call graph.
        </p>
      </div>
    </div>
  );
}

export function SymbolsPanel({ projectId }: { projectId: string }) {
  const [input, setInput] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [symbolType, setSymbolType] = useState("");
  const [selected, setSelected] = useState<SymbolHit | null>(null);

  const query = useIntelligenceSymbols(projectId, {
    q: submitted || undefined,
    symbol_type: symbolType || undefined,
    limit: 50,
  });

  const items = useMemo(() => query.data ?? [], [query.data]);
  const activeId = selected?.id ?? items[0]?.id;

  const submit = () => setSubmitted(input.trim());

  return (
    <div className="space-y-4">
      <Card className="border-copper/15">
        <CardContent className="p-4">
          <div className="flex flex-col gap-2 sm:flex-row">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-faint" />
              <Input
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    submit();
                  }
                }}
                placeholder="e.g. hybrid_search, UploadService, router.get"
                aria-label="Search symbols"
                className="h-10 pl-10"
              />
            </div>
            <Select
              value={symbolType}
              onChange={(event) => {
                setSymbolType(event.target.value);
                setSelected(null);
              }}
              aria-label="Symbol type"
              className="h-10 w-full sm:w-40"
            >
              {SYMBOL_TYPES.map((type) => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </Select>
            <Button
              variant="primary"
              className="h-10"
              onClick={submit}
              loading={query.isFetching}
              icon={<Search className="h-3.5 w-3.5" />}
            >
              Search
            </Button>
          </div>
          <p className="mt-2 text-[10px] text-faint">
            Search is an exact substring match over symbol and qualified names.
            Pick a symbol to see its definition, imports, importers and
            references.
          </p>
        </CardContent>
      </Card>

      {query.isError ? (
        <PanelError
          title="Could not search symbols"
          error={query.error}
          onRetry={() => void query.refetch()}
        />
      ) : (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.4fr)]">
          <Card className="overflow-hidden">
            <CardHeader className="py-3">
              <CardTitle>Matches</CardTitle>
              <Badge mono>{items.length}</Badge>
            </CardHeader>
            <CardContent className="max-h-[70vh] overflow-y-auto p-2">
              {query.isLoading ? (
                <div className="space-y-2 p-2">
                  {[0, 1, 2, 3, 4].map((index) => (
                    <Skeleton key={index} className="h-12 w-full" />
                  ))}
                </div>
              ) : items.length === 0 ? (
                <p className="px-2 py-6 text-center text-[11px] leading-relaxed text-muted">
                  No symbols matched. Try a shorter fragment, or clear the type
                  filter.
                </p>
              ) : (
                <ul className="space-y-0.5">
                  {items.map((hit) => (
                    <SymbolRow
                      key={hit.id}
                      hit={hit}
                      active={hit.id === activeId}
                      onSelect={() => setSelected(hit)}
                    />
                  ))}
                </ul>
              )}
              {query.isFetching && !query.isLoading ? (
                <p className="flex items-center gap-1.5 px-3 py-2 text-[10px] text-faint">
                  <Loader2 className="h-3 w-3 animate-spin" /> searching…
                </p>
              ) : null}
            </CardContent>
          </Card>

          <Card className="overflow-hidden">
            <CardHeader className="py-3">
              <CardTitle>Explanation</CardTitle>
              {selected ? <Badge mono>{selected.path.split("/").pop()}</Badge> : null}
            </CardHeader>
            {activeId ? (
              <DetailView
                key={activeId}
                projectId={projectId}
                symbolId={activeId}
                onSelectSymbol={setSelected}
              />
            ) : (
              <CardContent>
                <EmptyState
                  compact
                  icon={<Search className="h-4 w-4" />}
                  title="Pick a symbol"
                  description="Select a match on the left to read its definition and where it is used."
                  className="border-0"
                />
              </CardContent>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
