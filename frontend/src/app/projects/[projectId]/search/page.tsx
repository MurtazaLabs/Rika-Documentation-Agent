"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import {
  ArrowUpRight,
  Filter,
  Loader2,
  Search,
  Sparkles,
  X,
} from "lucide-react";

import { SourceViewer } from "@/components/source-viewer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input, Label, Select } from "@/components/ui/input";
import { useSearchProject } from "@/hooks/use-api";
import type { SearchFilters, SearchMode, SearchResult } from "@/lib/types";
import {
  cn,
  errorMessage,
  lineLabel,
  pluralize,
  truncate,
} from "@/lib/utils";

const EXAMPLES = [
  "Where is authentication handled?",
  "Which module owns upload validation?",
  "How are embeddings generated and stored?",
  "What does the retrieval pipeline fuse?",
];

interface FilterState {
  file_path: string;
  file_type: string;
  language: string;
  symbol_type: string;
}

const EMPTY_FILTERS: FilterState = {
  file_path: "",
  file_type: "",
  language: "",
  symbol_type: "",
};

function buildFilters(state: FilterState): SearchFilters {
  const filters: SearchFilters = {};
  for (const [key, value] of Object.entries(state) as Array<
    [keyof FilterState, string]
  >) {
    if (value.trim()) filters[key] = value.trim();
  }
  return filters;
}

function ResultCard({
  result,
  onOpen,
}: {
  result: SearchResult;
  onOpen: () => void;
}) {
  return (
    <Card className="overflow-hidden">
      <CardContent className="p-0">
        <div className="flex flex-wrap items-start gap-2 border-b border-line/70 px-4 py-3">
          <span className="mt-0.5 flex h-5 min-w-5 items-center justify-center rounded border border-copper/25 bg-copper/10 px-1 font-mono text-[9px] text-copper">
            {result.rank}
          </span>
          <div className="min-w-0 flex-1">
            <button
              type="button"
              onClick={onOpen}
              className="block max-w-full truncate text-left text-xs font-medium text-parchment hover:text-copper"
            >
              {result.file_path}
            </button>
            <div className="mt-1 flex flex-wrap items-center gap-1.5">
              <Badge mono>{lineLabel(result.start_line, result.end_line, result.page_number)}</Badge>
              {result.language ? <Badge mono tone="copper">{result.language}</Badge> : null}
              {result.symbol_name ? (
                <Badge mono tone="violet">
                  {result.symbol_type ? `${result.symbol_type} ` : ""}
                  {result.symbol_name}
                </Badge>
              ) : null}
              {result.matched_by.map((source) => (
                <Badge
                  key={source}
                  tone={source === "vector" ? "blue" : "sage"}
                >
                  {source}
                </Badge>
              ))}
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-3 text-right">
            <div>
              <p className="font-mono text-[9px] uppercase tracking-[0.12em] text-faint">
                score
              </p>
              <p className="text-[11px] text-muted">{result.score.toFixed(4)}</p>
            </div>
            <Button
              size="sm"
              variant="ghost"
              onClick={onOpen}
              icon={<ArrowUpRight className="h-3.5 w-3.5" />}
            >
              Open
            </Button>
          </div>
        </div>
        <pre className="max-h-52 overflow-y-auto whitespace-pre-wrap break-words px-4 py-3 font-mono text-[11px] leading-[1.7] text-[#d8d0c4]">
          {truncate(result.content, 1600)}
        </pre>
      </CardContent>
    </Card>
  );
}

export default function SearchPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
  const search = useSearchProject(projectId);
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<SearchMode>("hybrid");
  const [limit, setLimit] = useState(10);
  const [advanced, setAdvanced] = useState(false);
  const [filters, setFilters] = useState<FilterState>(EMPTY_FILTERS);
  const [elapsed, setElapsed] = useState<number | null>(null);
  const [viewing, setViewing] = useState<SearchResult | null>(null);

  const activeFilterCount = Object.values(filters).filter((value) =>
    value.trim(),
  ).length;

  const run = (nextQuery = query) => {
    const trimmed = nextQuery.trim();
    if (!trimmed) return;
    const started = performance.now();
    search.mutate(
      {
        query: trimmed,
        mode,
        limit,
        filters: buildFilters(filters),
      },
      {
        onSuccess: () => setElapsed(Math.round(performance.now() - started)),
      },
    );
  };

  const updateFilter = (key: keyof FilterState, value: string) => {
    setFilters((current) => ({ ...current, [key]: value }));
  };

  const results = search.data?.items ?? [];

  return (
    <div className="space-y-5">
      <div>
        <h2 className="font-serif text-2xl tracking-[-0.02em] text-parchment">
          Search
        </h2>
        <p className="mt-1 text-[12px] leading-relaxed text-muted">
          Query the hybrid index directly. Results are chunks, not generated
          answers, and every one can be opened at its source.
        </p>
      </div>

      <Card className="border-copper/15">
        <CardContent className="p-4">
          <div className="flex flex-col gap-2 sm:flex-row">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-faint" />
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    run();
                  }
                }}
                placeholder="e.g. Where is the ZIP path traversal check?"
                className="h-11 pl-10"
                aria-label="Search query"
              />
            </div>
            <div className="flex gap-2">
              <Select
                value={mode}
                onChange={(event) => setMode(event.target.value as SearchMode)}
                className="h-11 w-28"
                aria-label="Search mode"
              >
                <option value="hybrid">Hybrid</option>
                <option value="vector">Vector</option>
                <option value="keyword">Keyword</option>
              </Select>
              <Button
                variant="primary"
                className="h-11"
                onClick={() => run()}
                loading={search.isPending}
                disabled={!query.trim()}
                icon={<Sparkles className="h-4 w-4" />}
              >
                Search
              </Button>
            </div>
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => setAdvanced((value) => !value)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-[11px] transition-colors",
                advanced || activeFilterCount > 0
                  ? "border-copper/30 bg-copper/10 text-copper"
                  : "border-line text-muted hover:border-line-strong hover:text-parchment",
              )}
            >
              <Filter className="h-3 w-3" />
              Filters
              {activeFilterCount > 0 ? (
                <span className="rounded-full bg-copper/20 px-1.5 font-mono text-[9px]">
                  {activeFilterCount}
                </span>
              ) : null}
            </button>
            <Select
              value={String(limit)}
              onChange={(event) => setLimit(Number(event.target.value))}
              className="h-8 w-24 text-[11px]"
              aria-label="Number of results"
            >
              <option value="5">5 results</option>
              <option value="10">10 results</option>
              <option value="20">20 results</option>
            </Select>
            {activeFilterCount > 0 ? (
              <button
                type="button"
                onClick={() => setFilters(EMPTY_FILTERS)}
                className="inline-flex items-center gap-1 text-[10px] text-faint hover:text-parchment"
              >
                <X className="h-3 w-3" />
                Clear filters
              </button>
            ) : null}
          </div>

          {advanced ? (
            <div className="mt-3 grid gap-3 rounded-xl border border-line/70 bg-canvas/30 p-3 sm:grid-cols-2 lg:grid-cols-4">
              {(
                [
                  ["file_path", "Exact file path", "docs/setup.md"],
                  ["file_type", "File type", "code, pdf, markdown"],
                  ["language", "Language", "python, typescript"],
                  ["symbol_type", "Symbol type", "function, class"],
                ] as Array<[keyof FilterState, string, string]>
              ).map(([key, label, placeholder]) => (
                <div key={key}>
                  <Label className="mb-1 text-[9px]">{label}</Label>
                  <Input
                    value={filters[key]}
                    onChange={(event) => updateFilter(key, event.target.value)}
                    placeholder={placeholder}
                    className="h-9 text-[11px]"
                  />
                </div>
              ))}
            </div>
          ) : null}
        </CardContent>
      </Card>

      {search.isPending ? (
        <div className="flex items-center gap-2 py-10 text-xs text-muted">
          <Loader2 className="h-4 w-4 animate-spin text-copper" />
          Searching the local index…
        </div>
      ) : search.isError ? (
        <EmptyState
          icon={<Search className="h-4 w-4" />}
          title="Search failed"
          description={errorMessage(search.error)}
          action={<Button onClick={() => run()}>Try again</Button>}
        />
      ) : search.data ? (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-[11px] text-muted">
              {pluralize(search.data.total, "result")} for{" "}
              <span className="text-parchment">“{search.data.query}”</span>
              {elapsed !== null ? ` · ${elapsed} ms` : ""}
            </p>
            <div className="flex items-center gap-2">
              <Badge mono tone="copper">
                {search.data.mode}
              </Badge>
              <Badge mono>{search.data.total} chunks</Badge>
            </div>
          </div>
          {results.length === 0 ? (
            <EmptyState
              icon={<Search className="h-4 w-4" />}
              title="No matching chunks"
              description="Try a broader query, switch to keyword mode, or remove a filter. Search only sees files that have been uploaded and indexed."
            />
          ) : (
            <div className="space-y-3">
              {results.map((result) => (
                <ResultCard
                  key={result.chunk_id}
                  result={result}
                  onOpen={() => setViewing(result)}
                />
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-5 py-6">
          <div className="text-center">
            <p className="font-serif text-xl text-parchment">
              What are you looking for?
            </p>
            <p className="mt-1 text-xs text-muted">
              Hybrid search fuses semantic similarity with full-text ranking.
            </p>
          </div>
          <div className="mx-auto flex max-w-2xl flex-wrap justify-center gap-2">
            {EXAMPLES.map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => {
                  setQuery(example);
                  run(example);
                }}
                className="rounded-full border border-line bg-surface-2/50 px-3 py-1.5 text-[11px] text-muted transition-colors hover:border-copper/30 hover:text-parchment"
              >
                {example}
              </button>
            ))}
          </div>
        </div>
      )}

      <SourceViewer
        open={Boolean(viewing)}
        onClose={() => setViewing(null)}
        documentId={viewing?.document_id}
        projectId={projectId}
        highlight={
          viewing
            ? {
                startLine: viewing.start_line,
                endLine: viewing.end_line,
                pageNumber: viewing.page_number,
              }
            : undefined
        }
      />
    </div>
  );
}
