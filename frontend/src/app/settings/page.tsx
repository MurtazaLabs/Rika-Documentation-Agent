"use client";

import type { ReactNode } from "react";
import {
  Boxes,
  Cpu,
  Database,
  Info,
  Lock,
  RefreshCw,
  Server,
  Settings2,
  SlidersHorizontal,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { DependencyRow, ReadinessPill } from "@/components/ui/status";
import { PageHeader } from "@/components/ui/page-header";
import { API_BASE } from "@/lib/api";
import { useReadiness, useSettings } from "@/hooks/use-api";
import { errorMessage, pluralize } from "@/lib/utils";

function Row({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string | number | null;
  mono?: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-line/50 py-2.5 last:border-0">
      <dt className="text-[11px] text-muted">{label}</dt>
      <dd
        className={
          mono
            ? "max-w-[60%] break-all text-right font-mono text-[10px] text-parchment"
            : "max-w-[60%] text-right text-[11px] text-parchment"
        }
      >
        {value ?? "—"}
      </dd>
    </div>
  );
}

function ModelCard({
  title,
  icon,
  modelName,
  baseUrl,
  timeout,
  healthy,
  children,
}: {
  title: string;
  icon: ReactNode;
  modelName: string;
  baseUrl: string;
  timeout: number;
  healthy?: boolean;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-start gap-3">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-line bg-surface-2/60 text-copper">
            {icon}
          </span>
          <div className="min-w-0">
            <CardTitle>{title}</CardTitle>
            <p className="mt-1 truncate font-mono text-[10px] text-muted">
              {modelName}
            </p>
          </div>
        </div>
        <Badge tone={healthy === false ? "rose" : healthy ? "sage" : "neutral"}>
          {healthy === false ? "offline" : healthy ? "online" : "unknown"}
        </Badge>
      </CardHeader>
      <CardContent>
        <dl>
          <Row label="Server" value={baseUrl} mono />
          <Row label="Timeout" value={`${timeout}s`} />
          {children}
        </dl>
      </CardContent>
    </Card>
  );
}

export default function SettingsPage() {
  const settings = useSettings();
  const readiness = useReadiness();

  if (settings.isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-24 w-full" />
        <div className="grid gap-4 lg:grid-cols-2">
          {[0, 1, 2, 3].map((index) => (
            <Skeleton key={index} className="h-64 w-full" />
          ))}
        </div>
      </div>
    );
  }

  if (settings.isError || !settings.data) {
    return (
      <EmptyState
        icon={<Settings2 className="h-4 w-4" />}
        title="Could not load settings"
        description={errorMessage(settings.error)}
        action={<Button onClick={() => settings.refetch()}>Try again</Button>}
      />
    );
  }

  const data = settings.data;
  const checks = readiness.data?.checks ?? [];
  const chatCheck = checks.find((check) => check.name === "chat_model");
  const embeddingCheck = checks.find((check) => check.name === "embedding_model");
  const otherChecks = checks.filter(
    (check) => !["chat_model", "embedding_model"].includes(check.name),
  );

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Configuration"
        title="Settings"
        description="A read-only view of how this local instance is configured. Values come from .env and are loaded when the API starts."
        actions={
          <>
            <ReadinessPill
              readiness={readiness.data}
              loading={readiness.isLoading}
            />
            <Button
              variant="secondary"
              onClick={() => {
                settings.refetch();
                readiness.refetch();
              }}
              icon={<RefreshCw className="h-3.5 w-3.5" />}
            >
              Refresh
            </Button>
          </>
        }
      />

      <div className="flex items-start gap-3 rounded-2xl border border-gold/25 bg-gold/5 px-4 py-3.5">
        <Lock className="mt-0.5 h-4 w-4 shrink-0 text-gold" />
        <div>
          <p className="text-xs font-medium text-parchment">
            Read-only by design
          </p>
          <p className="mt-1 text-[11px] leading-relaxed text-muted">
            Change values in <code className="font-mono text-[10px] text-gold">.env</code>{" "}
            and restart the API and model servers. Connection strings,
            credentials and CORS origins are never sent to this page.
          </p>
        </div>
      </div>

      <section className="grid gap-4 lg:grid-cols-2">
        <ModelCard
          title="Chat model"
          icon={<Cpu className="h-4 w-4" />}
          modelName={data.chat.model_name}
          baseUrl={data.chat.base_url}
          timeout={data.chat.timeout_seconds}
          healthy={chatCheck ? chatCheck.status === "ok" : undefined}
        >
          <Row label="Temperature" value={data.chat.temperature} />
          <Row label="Max reply tokens" value={data.chat.max_tokens} />
          <Row label="Retrieved chunks" value={data.chat.context_chunks} />
          <Row
            label="Context budget"
            value={`${data.chat.context_max_chars.toLocaleString()} chars`}
          />
          <Row
            label="History budget"
            value={`${data.chat.history_max_chars.toLocaleString()} chars`}
          />
          <Row
            label="Prompt ceiling"
            value={`${data.chat.prompt_max_chars.toLocaleString()} chars`}
          />
        </ModelCard>

        <ModelCard
          title="Embedding model"
          icon={<Boxes className="h-4 w-4" />}
          modelName={data.embedding.model_name}
          baseUrl={data.embedding.base_url}
          timeout={data.embedding.timeout_seconds}
          healthy={embeddingCheck ? embeddingCheck.status === "ok" : undefined}
        >
          <Row label="Vector dimension" value={data.embedding.dimension} />
          <Row label="Batch size" value={data.embedding.batch_size} />
          <Row
            label="Distance"
            value="Cosine similarity"
          />
          <Row
            label="Embedding identity"
            value="Stored per chunk; dimensions never mixed"
          />
        </ModelCard>

        <Card>
          <CardHeader>
            <div className="flex items-start gap-3">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-line bg-surface-2/60 text-copper">
                <Database className="h-4 w-4" />
              </span>
              <div>
                <CardTitle>Storage</CardTitle>
                <p className="mt-1 text-[11px] text-muted">
                  Uploaded files and runtime data stay under this root.
                </p>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <dl>
              <Row label="Root" value={data.storage.root} mono />
              <Row
                label="Max upload"
                value={`${data.storage.max_upload_mb} MB`}
              />
              <Row
                label="Max archive entries"
                value={data.storage.max_archive_files.toLocaleString()}
              />
              <Row
                label="Max expanded archive"
                value={`${data.storage.max_archive_expanded_mb} MB`}
              />
              <Row
                label="Preview ceiling"
                value="400,000 characters shown"
              />
            </dl>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-start gap-3">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-line bg-surface-2/60 text-copper">
                <SlidersHorizontal className="h-4 w-4" />
              </span>
              <div>
                <CardTitle>Chunking &amp; indexing</CardTitle>
                <p className="mt-1 text-[11px] text-muted">
                  The index is local; chunk budgets are character-based.
                </p>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <dl>
              <Row
                label="Chunk size"
                value={`${data.indexing.chunk_size_chars.toLocaleString()} chars`}
              />
              <Row
                label="Chunk overlap"
                value={`${data.indexing.chunk_overlap_chars.toLocaleString()} chars`}
              />
              <Row label="Retrieval" value="Hybrid: vector + full-text (RRF)" />
              <Row label="Reranker" value="Not installed (baseline first)" />
            </dl>
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <div>
              <CardTitle>System health</CardTitle>
              <p className="mt-1 text-[11px] text-muted">
                Live probes from the API; refreshed automatically every 30
                seconds.
              </p>
            </div>
            <Button
              size="icon"
              variant="ghost"
              onClick={() => readiness.refetch()}
              aria-label="Refresh health"
              icon={<RefreshCw className="h-3.5 w-3.5" />}
            />
          </CardHeader>
          <CardContent className="px-5 py-2">
            {readiness.isLoading ? (
              <div className="space-y-2 py-2">
                {[0, 1, 2, 3].map((index) => (
                  <Skeleton key={index} className="h-9 w-full" />
                ))}
              </div>
            ) : otherChecks.length === 0 ? (
              <p className="py-6 text-center text-xs text-muted">
                No infrastructure checks were reported.
              </p>
            ) : (
              <div className="divide-y divide-line/60">
                {otherChecks.map((check) => (
                  <DependencyRow key={check.name} check={check} />
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div>
              <CardTitle>About this instance</CardTitle>
              <p className="mt-1 text-[11px] text-muted">
                Everything runs on this machine.
              </p>
            </div>
            <Info className="h-4 w-4 text-faint" />
          </CardHeader>
          <CardContent>
            <dl>
              <Row label="Application" value={`${data.app_name} ${data.version}`} />
              <Row label="Environment" value={data.environment} />
              <Row label="API" value={API_BASE} mono />
              <Row label="Configuration source" value={data.source} mono />
              <Row
                label="Restart required"
                value={data.restart_required ? "Yes, after .env changes" : "No"}
              />
              <Row
                label="Checks"
                value={`${checks.filter((check) => check.status === "ok").length}/${checks.length} answering`}
              />
            </dl>
            <div className="mt-4 flex items-start gap-2 rounded-xl border border-line/70 bg-canvas/40 px-3 py-2.5">
              <Server className="mt-0.5 h-3.5 w-3.5 shrink-0 text-faint" />
              <p className="text-[10px] leading-relaxed text-muted">
                {pluralize(checks.length, "dependency", "dependencies")}{" "}
                checked. Models are served by llama.cpp on the configured
                base URLs; no hosted inference is used.
              </p>
            </div>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
