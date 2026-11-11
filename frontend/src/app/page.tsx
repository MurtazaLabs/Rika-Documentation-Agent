"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  ArrowUpRight,
  FolderKanban,
  MessagesSquare,
  Plus,
  RefreshCw,
  Sparkles,
  Waypoints,
} from "lucide-react";

import { CreateProjectDialog } from "@/components/projects/project-dialogs";
import { Badge } from "@/components/ui/badge";
import { buttonClasses, Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Select, Textarea } from "@/components/ui/input";
import { ProgressBar } from "@/components/ui/progress";
import { ProjectAvatar } from "@/components/ui/project-avatar";
import { Skeleton } from "@/components/ui/skeleton";
import { DependencyRow, ReadinessPill } from "@/components/ui/status";
import {
  useConversations,
  useJobsForProjects,
  useProjects,
  useReadiness,
} from "@/hooks/use-api";
import type { Job, Project } from "@/lib/types";
import {
  conversationTitle,
  getRecentProjectIds,
  isActiveJob,
  pluralize,
  relativeTime,
  statusTone,
} from "@/lib/utils";

function StatCard({
  label,
  value,
  detail,
  icon,
  loading,
}: {
  label: string;
  value: string;
  detail: string;
  icon: ReactNode;
  loading?: boolean;
}) {
  return (
    <Card className="relative overflow-hidden">
      <div className="absolute inset-x-0 top-0 h-px bg-[linear-gradient(90deg,transparent,rgba(224,161,121,0.45),transparent)]" />
      <CardContent className="p-5">
        <div className="flex items-center justify-between">
          <p className="font-mono text-[9px] uppercase tracking-[0.2em] text-faint">
            {label}
          </p>
          <span className="text-faint">{icon}</span>
        </div>
        {loading ? (
          <Skeleton className="mt-4 h-8 w-16" />
        ) : (
          <p className="mt-3 font-serif text-[2rem] leading-none tracking-[-0.03em] text-parchment">
            {value}
          </p>
        )}
        <p className="mt-2 text-[11px] text-muted">{detail}</p>
      </CardContent>
    </Card>
  );
}

function QuickAsk({ projects }: { projects: Project[] }) {
  const router = useRouter();
  const [projectId, setProjectId] = useState("");
  const [question, setQuestion] = useState("");

  useEffect(() => {
    if (!projectId && projects.length > 0) setProjectId(projects[0].id);
  }, [projectId, projects]);

  const submit = () => {
    const trimmed = question.trim();
    if (!trimmed || !projectId) return;
    router.push(
      `/projects/${projectId}/chat?ask=${encodeURIComponent(trimmed)}`,
    );
  };

  return (
    <Card className="relative overflow-hidden border-copper/20 bg-[linear-gradient(160deg,rgba(224,161,121,0.08),rgba(19,17,16,0.9)_55%)]">
      <CardContent className="p-5">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-copper" />
          <p className="font-mono text-[9px] uppercase tracking-[0.2em] text-copper">
            Quick ask
          </p>
        </div>
        <p className="mt-3 font-serif text-xl leading-tight tracking-[-0.02em] text-parchment">
          Ask about anything you have indexed.
        </p>

        {projects.length === 0 ? (
          <p className="mt-3 text-xs leading-relaxed text-muted">
            Create a project and upload files first. Rika answers only from
            evidence it can retrieve.
          </p>
        ) : (
          <>
            <Select
              value={projectId}
              onChange={(event) => setProjectId(event.target.value)}
              className="mt-4"
              aria-label="Project to ask about"
            >
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </Select>
            <Textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Where is authentication handled, and what guards it?"
              rows={3}
              className="mt-2.5 min-h-20"
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  submit();
                }
              }}
            />
            <Button
              variant="primary"
              className="mt-2.5 w-full"
              onClick={submit}
              disabled={!question.trim()}
              icon={<ArrowRight className="h-3.5 w-3.5" />}
            >
              Continue in chat
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function JobRow({ job, project }: { job: Job; project?: Project }) {
  return (
    <div className="flex items-start gap-3 py-3">
      <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-line bg-surface-2/60 text-faint">
        <Waypoints className="h-3.5 w-3.5" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className="truncate text-xs text-parchment">
            {job.job_type === "reindex" ? "Reindex" : "Ingest"} ·{" "}
            {project?.name ?? "Project"}
          </p>
          <Badge tone={statusTone(job.status)} className="ml-auto shrink-0">
            {job.status}
          </Badge>
        </div>
        {isActiveJob(job) ? (
          <ProgressBar value={job.progress} className="mt-2" />
        ) : null}
        {job.error_message ? (
          <p className="mt-1 line-clamp-2 text-[10px] leading-relaxed text-rose">
            {job.error_message}
          </p>
        ) : (
          <p className="mt-1 text-[10px] text-faint">
            {relativeTime(job.created_at)}
            {isActiveJob(job) ? ` · ${job.progress}%` : ""}
          </p>
        )}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const projects = useProjects({ limit: 50 });
  const conversations = useConversations(undefined, 6);
  const readiness = useReadiness();
  const [recentIds, setRecentIds] = useState<string[]>([]);
  const [createOpen, setCreateOpen] = useState(false);

  useEffect(() => {
    setRecentIds(getRecentProjectIds());
  }, []);

  const items = projects.data?.items ?? [];
  const projectById = useMemo(
    () => new Map(items.map((project) => [project.id, project])),
    [items],
  );

  const orderedProjects = useMemo(() => {
    const rank = new Map(recentIds.map((id, index) => [id, index]));
    return [...items].sort((left, right) => {
      const leftRank = rank.get(left.id) ?? Number.MAX_SAFE_INTEGER;
      const rightRank = rank.get(right.id) ?? Number.MAX_SAFE_INTEGER;
      if (leftRank !== rightRank) return leftRank - rightRank;
      return (
        new Date(right.updated_at).getTime() -
        new Date(left.updated_at).getTime()
      );
    });
  }, [items, recentIds]);

  const recentProjects = orderedProjects.slice(0, 4);
  const jobs = useJobsForProjects(recentProjects.map((project) => project.id), 5);
  const activeJobs = jobs.jobs.filter(isActiveJob).length;
  const checks = readiness.data?.checks ?? [];
  const okChecks = checks.filter((check) => check.status === "ok").length;

  return (
    <div className="space-y-8">
      <section className="grid gap-6 lg:grid-cols-[minmax(0,1.5fr)_minmax(320px,1fr)]">
        <div className="relative">
          <p className="mb-3 font-mono text-[10px] uppercase tracking-[0.24em] text-copper">
            Local project intelligence
          </p>
          <h1 className="max-w-2xl font-serif text-[2.4rem] leading-[1.04] tracking-[-0.035em] text-parchment sm:text-[3.1rem]">
            Ask your project.
            <br />
            <span className="text-muted">Not the internet.</span>
          </h1>
          <p className="mt-4 max-w-xl text-[13px] leading-relaxed text-muted">
            Rika indexes the files you give it, retrieves the passages that
            matter and answers with citations. Everything — files, embeddings
            and generation — stays on this machine.
          </p>
          <div className="mt-6 flex flex-wrap items-center gap-2.5">
            <button
              type="button"
              onClick={() => setCreateOpen(true)}
              className={buttonClasses("primary", "md")}
            >
              <Plus className="h-4 w-4" />
              New project
            </button>
            <Link href="/projects" className={buttonClasses("secondary", "md")}>
              Browse projects
            </Link>
          </div>
        </div>

        <QuickAsk projects={orderedProjects.slice(0, 10)} />
      </section>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Projects"
          value={String(projects.data?.total ?? 0)}
          detail={
            projects.data
              ? pluralize(projects.data.total, "workspace")
              : "loading workspaces"
          }
          icon={<FolderKanban className="h-4 w-4" />}
          loading={projects.isLoading}
        />
        <StatCard
          label="Conversations"
          value={String(conversations.data?.total ?? 0)}
          detail="across every project"
          icon={<MessagesSquare className="h-4 w-4" />}
          loading={conversations.isLoading}
        />
        <StatCard
          label="Indexing"
          value={String(activeJobs)}
          detail={
            activeJobs === 0
              ? "no jobs running"
              : pluralize(activeJobs, "job") + " in flight"
          }
          icon={<Waypoints className="h-4 w-4" />}
          loading={jobs.isLoading}
        />
        <StatCard
          label="System"
          value={
            readiness.data
              ? readiness.data.status === "ready"
                ? "Ready"
                : readiness.data.status === "degraded"
                  ? "Degraded"
                  : "Down"
              : "—"
          }
          detail={
            checks.length > 0
              ? `${okChecks}/${checks.length} dependencies answering`
              : "health check unavailable"
          }
          icon={<Sparkles className="h-4 w-4" />}
          loading={readiness.isLoading}
        />
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Recent projects</CardTitle>
              <p className="mt-1 text-[11px] text-muted">
                Pick up where you left off.
              </p>
            </div>
            <Link
              href="/projects"
              className="inline-flex items-center gap-1 text-[11px] text-copper hover:underline"
            >
              All projects <ArrowUpRight className="h-3 w-3" />
            </Link>
          </CardHeader>
          <CardContent className="p-3">
            {projects.isLoading ? (
              <div className="space-y-2 p-2">
                {[0, 1, 2].map((index) => (
                  <Skeleton key={index} className="h-16 w-full" />
                ))}
              </div>
            ) : recentProjects.length === 0 ? (
              <EmptyState
                compact
                icon={<FolderKanban className="h-4 w-4" />}
                title="No projects yet"
                description="Create a project, upload a repository or document set, and Rika will index it locally."
                action={
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => setCreateOpen(true)}
                    icon={<Plus className="h-3.5 w-3.5" />}
                  >
                    Create a project
                  </Button>
                }
                className="border-0"
              />
            ) : (
              <ul className="space-y-1">
                {recentProjects.map((project) => (
                  <li key={project.id}>
                    <Link
                      href={`/projects/${project.id}`}
                      className="group flex items-center gap-3 rounded-xl px-3 py-3 transition-colors hover:bg-surface-2/60"
                    >
                      <ProjectAvatar name={project.name} />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[13px] font-medium text-parchment">
                          {project.name}
                        </p>
                        <p className="mt-0.5 truncate text-[11px] text-muted">
                          {project.description?.trim() ||
                            "No description yet."}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-[10px] text-faint">
                          {relativeTime(project.updated_at)}
                        </p>
                        <ArrowRight className="ml-auto mt-1 h-3.5 w-3.5 text-faint transition-transform group-hover:translate-x-0.5 group-hover:text-copper" />
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div>
              <CardTitle>Recent conversations</CardTitle>
              <p className="mt-1 text-[11px] text-muted">
                Every answer keeps its citations.
              </p>
            </div>
            <ReadinessPill
              readiness={readiness.data}
              loading={readiness.isLoading}
            />
          </CardHeader>
          <CardContent className="p-3">
            {conversations.isLoading ? (
              <div className="space-y-2 p-2">
                {[0, 1, 2].map((index) => (
                  <Skeleton key={index} className="h-12 w-full" />
                ))}
              </div>
            ) : (conversations.data?.items.length ?? 0) === 0 ? (
              <EmptyState
                compact
                icon={<MessagesSquare className="h-4 w-4" />}
                title="No conversations yet"
                description="Ask a question from any project workspace. Rika will keep the thread and its sources."
                className="border-0"
              />
            ) : (
              <ul className="divide-y divide-line/60">
                {conversations.data?.items.map((conversation) => {
                  const project = projectById.get(conversation.project_id);
                  return (
                    <li key={conversation.id}>
                      <Link
                        href={`/projects/${conversation.project_id}/chat?conversation=${conversation.id}`}
                        className="group flex items-start gap-3 px-3 py-3 transition-colors hover:bg-surface-2/50"
                      >
                        <MessagesSquare className="mt-0.5 h-3.5 w-3.5 shrink-0 text-faint group-hover:text-copper" />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-xs text-parchment">
                            {conversationTitle(conversation.title)}
                          </p>
                          <p className="mt-0.5 truncate text-[10px] text-faint">
                            {project?.name ?? "Project"} ·{" "}
                            {pluralize(conversation.message_count, "message")}
                          </p>
                        </div>
                        <span className="shrink-0 text-[10px] text-faint">
                          {relativeTime(conversation.updated_at)}
                        </span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            )}
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Indexing activity</CardTitle>
              <p className="mt-1 text-[11px] text-muted">
                Parsing, chunking and embedding jobs from recent projects.
              </p>
            </div>
            {activeJobs > 0 ? (
              <Badge tone="gold" mono>
                {activeJobs} active
              </Badge>
            ) : (
              <Badge tone="neutral">idle</Badge>
            )}
          </CardHeader>
          <CardContent className="px-5 py-2">
            {jobs.isLoading ? (
              <div className="space-y-2 py-2">
                {[0, 1].map((index) => (
                  <Skeleton key={index} className="h-12 w-full" />
                ))}
              </div>
            ) : jobs.jobs.length === 0 ? (
              <p className="py-6 text-center text-xs text-muted">
                No indexing jobs yet. Upload files in a workspace to start the
                pipeline.
              </p>
            ) : (
              <div className="divide-y divide-line/60">
                {jobs.jobs.map((job) => (
                  <JobRow
                    key={job.id}
                    job={job}
                    project={projectById.get(job.project_id)}
                  />
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div>
              <CardTitle>Model &amp; system health</CardTitle>
              <p className="mt-1 text-[11px] text-muted">
                Probed live from the API, including both model servers.
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
            ) : checks.length === 0 ? (
              <p className="py-6 text-center text-xs text-muted">
                The API did not report any dependency checks.
              </p>
            ) : (
              <div className="divide-y divide-line/60">
                {checks.map((check) => (
                  <DependencyRow key={check.name} check={check} />
                ))}
              </div>
            )}
            {readiness.data ? (
              <p className="border-t border-line/60 py-2.5 text-[10px] text-faint">
                {readiness.data.app} {readiness.data.version} ·{" "}
                {readiness.data.environment}
              </p>
            ) : null}
          </CardContent>
        </Card>
      </section>

      <CreateProjectDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={(project) => router.push(`/projects/${project.id}`)}
      />
    </div>
  );
}
