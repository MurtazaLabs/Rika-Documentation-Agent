"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  FileStack,
  MessagesSquare,
  Search,
  Sparkles,
  UploadCloud,
  Waypoints,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button, buttonClasses } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { FileGlyph } from "@/components/ui/file-icon";
import { ProgressBar } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useConversations,
  useDocuments,
  useJobs,
} from "@/hooks/use-api";
import type { Document } from "@/lib/types";
import {
  conversationTitle,
  formatBytes,
  isActiveJob,
  pluralize,
  relativeTime,
  statusTone,
} from "@/lib/utils";

function Metric({
  label,
  value,
  hint,
  loading,
}: {
  label: string;
  value: string;
  hint: string;
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
      <p className="mt-1.5 text-[10px] text-muted">{hint}</p>
    </div>
  );
}

function StatusBreakdown({ documents }: { documents: Document[] }) {
  const counts = useMemo(() => {
    const tally: Record<string, number> = {};
    for (const document of documents) {
      tally[document.status] = (tally[document.status] ?? 0) + 1;
    }
    return tally;
  }, [documents]);

  const rows = [
    { status: "indexed", tone: "sage" as const },
    { status: "processing", tone: "gold" as const },
    { status: "pending", tone: "gold" as const },
    { status: "failed", tone: "rose" as const },
  ];
  const total = Math.max(documents.length, 1);

  return (
    <div className="space-y-3">
      {rows.map(({ status, tone }) => {
        const count = counts[status] ?? 0;
        return (
          <div key={status}>
            <div className="flex items-center justify-between text-[11px]">
              <span className="capitalize text-muted">{status}</span>
              <span className="font-mono text-[10px] text-faint">{count}</span>
            </div>
            <ProgressBar
              value={(count / total) * 100}
              tone={tone}
              className="mt-1.5"
            />
          </div>
        );
      })}
      {Object.keys(counts)
        .filter(
          (status) =>
            !["indexed", "processing", "pending", "failed"].includes(status),
        )
        .map((status) => (
          <div
            key={status}
            className="flex items-center justify-between text-[11px]"
          >
            <span className="capitalize text-muted">{status}</span>
            <span className="font-mono text-[10px] text-faint">
              {counts[status]}
            </span>
          </div>
        ))}
    </div>
  );
}

export default function ProjectOverviewPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
  const router = useRouter();
  const documents = useDocuments(projectId);
  const jobs = useJobs(projectId, 20);
  const conversations = useConversations(projectId, 5);
  const [question, setQuestion] = useState("");

  const documentItems = documents.data?.items ?? [];
  const jobItems = jobs.data?.items ?? [];
  const activeJobs = jobItems.filter(isActiveJob);
  const failedJobs = jobItems.filter((job) => job.status === "failed");
  const indexedCount = documentItems.filter(
    (document) => document.status === "indexed",
  ).length;
  const totalBytes = documentItems.reduce(
    (sum, document) => sum + document.size,
    0,
  );
  const recentDocuments = useMemo(
    () =>
      [...documentItems]
        .sort(
          (left, right) =>
            new Date(right.updated_at).getTime() -
            new Date(left.updated_at).getTime(),
        )
        .slice(0, 6),
    [documentItems],
  );

  const submitQuestion = () => {
    const trimmed = question.trim();
    if (!trimmed) return;
    router.push(
      `/projects/${projectId}/chat?ask=${encodeURIComponent(trimmed)}`,
    );
  };

  return (
    <div className="space-y-5">
      {!documents.isLoading && documentItems.length === 0 ? (
        <Card className="border-copper/20 bg-[linear-gradient(150deg,rgba(224,161,121,0.08),rgba(19,17,16,0.92)_60%)]">
          <CardContent className="p-6">
            <div className="flex flex-wrap items-start justify-between gap-5">
              <div className="max-w-xl">
                <p className="font-mono text-[9px] uppercase tracking-[0.2em] text-copper">
                  Start here
                </p>
                <h2 className="mt-2 font-serif text-2xl tracking-[-0.02em] text-parchment">
                  Give Rika something to read.
                </h2>
                <p className="mt-2 text-xs leading-relaxed text-muted">
                  Upload a repository, a folder of documents or a ZIP archive.
                  Files are parsed, chunked and embedded locally, then Rika can
                  answer with citations back to the exact lines.
                </p>
                <div className="mt-4 flex flex-wrap gap-2">
                  <Link
                    href={`/projects/${projectId}/files`}
                    className={buttonClasses("primary", "md")}
                  >
                    <UploadCloud className="h-4 w-4" />
                    Upload files
                  </Link>
                  <Link
                    href={`/projects/${projectId}/search`}
                    className={buttonClasses("secondary", "md")}
                  >
                    <Search className="h-4 w-4" />
                    Search the index
                  </Link>
                </div>
              </div>
              <ol className="space-y-2.5 text-[11px] text-muted">
                {[
                  "Upload files, folders or archives",
                  "Wait for parsing and embeddings",
                  "Ask questions and open citations",
                ].map((step, index) => (
                  <li key={step} className="flex items-center gap-2.5">
                    <span className="flex h-5 w-5 items-center justify-center rounded-full border border-copper/30 font-mono text-[9px] text-copper">
                      {index + 1}
                    </span>
                    {step}
                  </li>
                ))}
              </ol>
            </div>
          </CardContent>
        </Card>
      ) : null}

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric
          label="Files"
          value={String(documents.data?.total ?? 0)}
          hint={formatBytes(totalBytes)}
          loading={documents.isLoading}
        />
        <Metric
          label="Indexed"
          value={String(indexedCount)}
          hint={
            documentItems.length > 0
              ? `${Math.round((indexedCount / documentItems.length) * 100)}% ready`
              : "nothing uploaded"
          }
          loading={documents.isLoading}
        />
        <Metric
          label="Indexing"
          value={String(activeJobs.length)}
          hint={
            failedJobs.length > 0
              ? `${pluralize(failedJobs.length, "failure")} to review`
              : "no failures"
          }
          loading={jobs.isLoading}
        />
        <Metric
          label="Conversations"
          value={String(conversations.data?.total ?? 0)}
          hint="scoped to this project"
          loading={conversations.isLoading}
        />
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <div className="space-y-5">
          <Card className="border-copper/15">
            <CardContent className="p-5">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-copper" />
                <p className="font-mono text-[9px] uppercase tracking-[0.2em] text-copper">
                  Ask this project
                </p>
              </div>
              <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                <input
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.preventDefault();
                      submitQuestion();
                    }
                  }}
                  placeholder="What does this project do, and where should I start?"
                  aria-label="Ask this project a question"
                  className="h-11 w-full rounded-xl border border-line bg-canvas/60 px-3.5 text-[13px] text-parchment placeholder:text-faint focus:border-copper/50 focus:outline-none focus:ring-2 focus:ring-copper/15"
                />
                <Button
                  variant="primary"
                  onClick={submitQuestion}
                  disabled={!question.trim()}
                  icon={<ArrowRight className="h-3.5 w-3.5" />}
                  className="shrink-0"
                >
                  Ask
                </Button>
              </div>
              <p className="mt-2 text-[10px] text-faint">
                Answers are grounded in retrieved evidence. Citations open the
                original lines.
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div>
                <CardTitle>Recent files</CardTitle>
                <p className="mt-1 text-[11px] text-muted">
                  The newest additions to this project&apos;s index.
                </p>
              </div>
              <Link
                href={`/projects/${projectId}/files`}
                className="inline-flex items-center gap-1 text-[11px] text-copper hover:underline"
              >
                All files <ArrowUpRight className="h-3 w-3" />
              </Link>
            </CardHeader>
            <CardContent className="p-3">
              {documents.isLoading ? (
                <div className="space-y-2 p-2">
                  {[0, 1, 2].map((index) => (
                    <Skeleton key={index} className="h-10 w-full" />
                  ))}
                </div>
              ) : recentDocuments.length === 0 ? (
                <EmptyState
                  compact
                  icon={<FileStack className="h-4 w-4" />}
                  title="No files yet"
                  description="Upload files to give Rika evidence to work with."
                  action={
                    <Link
                      href={`/projects/${projectId}/files`}
                      className={buttonClasses("secondary", "sm")}
                    >
                      Open files
                    </Link>
                  }
                  className="border-0"
                />
              ) : (
                <ul className="divide-y divide-line/60">
                  {recentDocuments.map((document) => (
                    <li key={document.id}>
                      <Link
                        href={`/projects/${projectId}/files?document=${document.id}`}
                        className="flex items-center gap-3 rounded-lg px-3 py-2.5 transition-colors hover:bg-surface-2/50"
                      >
                        <FileGlyph document={document} />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-xs text-parchment">
                            {document.original_path}
                          </p>
                          <p className="mt-0.5 text-[10px] text-faint">
                            {formatBytes(document.size)} ·{" "}
                            {relativeTime(document.updated_at)}
                          </p>
                        </div>
                        <Badge tone={statusTone(document.status)}>
                          {document.status}
                        </Badge>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-5">
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Index health</CardTitle>
                <p className="mt-1 text-[11px] text-muted">
                  Coverage across every uploaded file.
                </p>
              </div>
              <Waypoints className="h-4 w-4 text-faint" />
            </CardHeader>
            <CardContent>
              {documents.isLoading ? (
                <div className="space-y-3">
                  {[0, 1, 2, 3].map((index) => (
                    <Skeleton key={index} className="h-6 w-full" />
                  ))}
                </div>
              ) : documentItems.length === 0 ? (
                <p className="py-4 text-center text-xs text-muted">
                  Nothing indexed yet.
                </p>
              ) : (
                <StatusBreakdown documents={documentItems} />
              )}

              {failedJobs.length > 0 ? (
                <div className="mt-4 rounded-xl border border-rose/25 bg-rose/5 p-3">
                  <p className="text-[11px] font-medium text-rose">
                    {pluralize(failedJobs.length, "job")} failed
                  </p>
                  <p className="mt-1 line-clamp-2 text-[10px] leading-relaxed text-muted">
                    {failedJobs[0].error_message ??
                      "Open the files page to retry."}
                  </p>
                  <Link
                    href={`/projects/${projectId}/files`}
                    className="mt-2 inline-block text-[10px] text-copper hover:underline"
                  >
                    Review jobs →
                  </Link>
                </div>
              ) : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div>
                <CardTitle>Recent conversations</CardTitle>
                <p className="mt-1 text-[11px] text-muted">
                  Threads keep their retrieved sources.
                </p>
              </div>
              <MessagesSquare className="h-4 w-4 text-faint" />
            </CardHeader>
            <CardContent className="p-3">
              {conversations.isLoading ? (
                <div className="space-y-2 p-2">
                  {[0, 1].map((index) => (
                    <Skeleton key={index} className="h-10 w-full" />
                  ))}
                </div>
              ) : (conversations.data?.items.length ?? 0) === 0 ? (
                <EmptyState
                  compact
                  icon={<MessagesSquare className="h-4 w-4" />}
                  title="No conversations yet"
                  description="Ask the first question above."
                  className="border-0"
                />
              ) : (
                <ul className="divide-y divide-line/60">
                  {conversations.data?.items.map((conversation) => (
                    <li key={conversation.id}>
                      <Link
                        href={`/projects/${projectId}/chat?conversation=${conversation.id}`}
                        className="flex items-start gap-2.5 rounded-lg px-3 py-2.5 transition-colors hover:bg-surface-2/50"
                      >
                        <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-copper/70" />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-xs text-parchment">
                            {conversationTitle(conversation.title)}
                          </p>
                          <p className="mt-0.5 text-[10px] text-faint">
                            {pluralize(conversation.message_count, "message")} ·{" "}
                            {relativeTime(conversation.updated_at)}
                          </p>
                        </div>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
              <div className="border-t border-line/60 px-3 pb-1 pt-3">
                <Link
                  href={`/projects/${projectId}/chat`}
                  className="inline-flex items-center gap-1 text-[11px] text-copper hover:underline"
                >
                  <CheckCircle2 className="h-3 w-3" />
                  Start a new conversation
                </Link>
              </div>
            </CardContent>
          </Card>
        </div>
      </section>
    </div>
  );
}
