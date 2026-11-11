"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ProgressBar } from "@/components/ui/progress";
import { useIntelligenceOverview } from "@/hooks/use-api";
import { formatBytes, pluralize } from "@/lib/utils";

import { FileButton, PanelError, PanelLoading, StatCard } from "./shared";

export function OverviewPanel({ projectId }: { projectId: string }) {
  const query = useIntelligenceOverview(projectId);

  if (query.isLoading) return <PanelLoading label="Summarising the project…" />;
  if (query.isError || !query.data) {
    return (
      <PanelError
        title="Could not read the project overview"
        error={query.error}
        onRetry={() => void query.refetch()}
      />
    );
  }

  const data = query.data;
  const maxLanguageFiles = Math.max(
    1,
    ...data.languages.map((language) => language.files),
  );
  const dependencies = data.dependencies;

  return (
    <div className="space-y-5">
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Files indexed"
          value={String(data.totals.files)}
          hint={`${pluralize(data.totals.code_files, "code file")} analysed`}
        />
        <StatCard
          label="Symbols"
          value={String(data.totals.symbols)}
          hint="functions, classes, methods and routes"
        />
        <StatCard
          label="Languages"
          value={String(data.totals.languages)}
          hint={data.languages.map((item) => item.language).join(", ") || "none detected"}
        />
        <StatCard
          label="Internal imports"
          value={String(dependencies.internal_edges)}
          hint={`${pluralize(dependencies.external_edges, "external import")}`}
        />
      </section>

      <section className="grid gap-5 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Languages</CardTitle>
              <p className="mt-1 text-[11px] text-muted">
                Where the code lives, by file count.
              </p>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {data.languages.length === 0 ? (
              <p className="py-3 text-center text-[11px] text-muted">
                No source files are indexed yet.
              </p>
            ) : (
              data.languages.map((language) => (
                <div key={language.language}>
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="text-[12px] text-parchment">
                      {language.language}
                    </span>
                    <span className="font-mono text-[10px] text-faint">
                      {pluralize(language.files, "file")} ·{" "}
                      {pluralize(language.symbols, "symbol")} ·{" "}
                      {formatBytes(language.bytes)}
                    </span>
                  </div>
                  <ProgressBar
                    value={(language.files / maxLanguageFiles) * 100}
                    className="mt-1.5"
                  />
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div>
              <CardTitle>Frameworks &amp; libraries</CardTitle>
              <p className="mt-1 text-[11px] text-muted">
                Detected from imports and manifest files.
              </p>
            </div>
          </CardHeader>
          <CardContent>
            {data.frameworks.length === 0 ? (
              <p className="py-3 text-center text-[11px] text-muted">
                Nothing recognisable was imported.
              </p>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {data.frameworks.map((framework) => (
                  <Badge
                    key={framework.name}
                    tone="copper"
                    title={framework.evidence.join("\n")}
                  >
                    {framework.name}
                    <span className="font-mono text-[9px] opacity-70">
                      {framework.files}
                    </span>
                  </Badge>
                ))}
              </div>
            )}
            <div className="mt-4 grid grid-cols-3 gap-2 rounded-xl border border-line/60 bg-canvas/30 px-3 py-2.5 text-center">
              <div>
                <p className="font-mono text-[9px] uppercase tracking-[0.1em] text-faint">
                  internal
                </p>
                <p className="mt-1 text-sm text-parchment">
                  {dependencies.internal_edges}
                </p>
              </div>
              <div>
                <p className="font-mono text-[9px] uppercase tracking-[0.1em] text-faint">
                  unresolved
                </p>
                <p className="mt-1 text-sm text-gold">
                  {dependencies.unresolved_edges}
                </p>
              </div>
              <div>
                <p className="font-mono text-[9px] uppercase tracking-[0.1em] text-faint">
                  external
                </p>
                <p className="mt-1 text-sm text-muted">
                  {dependencies.external_edges}
                </p>
              </div>
            </div>
            <p className="mt-2 text-[10px] leading-relaxed text-faint">
              Unresolved imports name this project&apos;s own package but point
              at files that are not indexed, so they are counted apart from
              external packages.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div>
              <CardTitle>Main directories</CardTitle>
              <p className="mt-1 text-[11px] text-muted">
                The busiest folders in the index.
              </p>
            </div>
          </CardHeader>
          <CardContent className="py-2">
            {data.directories.length === 0 ? (
              <p className="py-3 text-center text-[11px] text-muted">
                No directories yet.
              </p>
            ) : (
              <ul className="divide-y divide-line/50">
                {data.directories.slice(0, 8).map((directory) => (
                  <li
                    key={directory.path}
                    className="flex items-center justify-between gap-3 py-2"
                  >
                    <span className="truncate font-mono text-[11px] text-parchment">
                      {directory.path}
                    </span>
                    <span className="shrink-0 font-mono text-[10px] text-faint">
                      {directory.files}f · {directory.symbols}s ·{" "}
                      {formatBytes(directory.bytes)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div>
              <CardTitle>Entry points</CardTitle>
              <p className="mt-1 text-[11px] text-muted">
                Where execution or requests enter the project.
              </p>
            </div>
          </CardHeader>
          <CardContent className="space-y-2.5">
            {data.entry_points.length === 0 ? (
              <p className="py-3 text-center text-[11px] text-muted">
                No entry points were recognised.
              </p>
            ) : (
              data.entry_points.map((entry) => (
                <div
                  key={`${entry.path}:${entry.kind}`}
                  className="flex flex-wrap items-baseline gap-2"
                >
                  <FileButton projectId={projectId} path={entry.path} />
                  <Badge mono tone="blue">
                    {entry.kind}
                  </Badge>
                  {entry.detail ? (
                    <span className="text-[10px] text-faint">{entry.detail}</span>
                  ) : null}
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div>
              <CardTitle>Important modules</CardTitle>
              <p className="mt-1 text-[11px] text-muted">
                Ranked by how much the rest of the project depends on them.
              </p>
            </div>
          </CardHeader>
          <CardContent className="py-2">
            {data.important_modules.length === 0 ? (
              <p className="py-3 text-center text-[11px] text-muted">
                Import the code to rank its modules.
              </p>
            ) : (
              <ul className="divide-y divide-line/50">
                {data.important_modules.slice(0, 8).map((module) => (
                  <li key={module.path} className="flex items-center gap-2 py-2">
                    <div className="min-w-0 flex-1">
                      <FileButton projectId={projectId} path={module.path} />
                      <p className="mt-0.5 text-[10px] text-faint">
                        {pluralize(module.symbols, "symbol")} · imported by{" "}
                        {module.imported_by}
                      </p>
                    </div>
                    <Badge mono tone="violet">
                      {module.layer}
                    </Badge>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div>
              <CardTitle>Configuration</CardTitle>
              <p className="mt-1 text-[11px] text-muted">
                Config and manifest files the index recognised.
              </p>
            </div>
          </CardHeader>
          <CardContent className="py-2">
            {data.config_files.length === 0 ? (
              <p className="py-3 text-center text-[11px] text-muted">
                No configuration files were found.
              </p>
            ) : (
              <ul className="divide-y divide-line/50">
                {data.config_files.map((file) => (
                  <li
                    key={file.path}
                    className="flex items-center justify-between gap-3 py-2"
                  >
                    <FileButton projectId={projectId} path={file.path} />
                    <Badge mono>{file.kind}</Badge>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </section>

      <Card>
        <CardHeader>
          <div>
            <CardTitle>External packages</CardTitle>
            <p className="mt-1 text-[11px] text-muted">
              Third-party packages imported by the indexed code.
            </p>
          </div>
          <Badge mono>{pluralize(dependencies.packages.length, "package")}</Badge>
        </CardHeader>
        <CardContent>
          {dependencies.packages.length === 0 ? (
            <p className="py-3 text-center text-[11px] text-muted">
              No external imports were found.
            </p>
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {dependencies.packages.map((pkg) => (
                <Badge key={pkg.name} tone="neutral">
                  {pkg.name}
                  <span className="font-mono text-[9px] opacity-70">
                    {pkg.files}
                  </span>
                </Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
