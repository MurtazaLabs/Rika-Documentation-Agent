"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import {
  ArrowUpRight,
  FolderKanban,
  MoreHorizontal,
  Pencil,
  Plus,
  Search,
  Trash2,
} from "lucide-react";

import {
  CreateProjectDialog,
  DeleteProjectDialog,
  RenameProjectDialog,
} from "@/components/projects/project-dialogs";
import { Button, buttonClasses } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Menu, MenuItem, MenuSeparator } from "@/components/ui/menu";
import { PageHeader } from "@/components/ui/page-header";
import { ProjectAvatar } from "@/components/ui/project-avatar";
import { CardSkeleton } from "@/components/ui/skeleton";
import { useProjects } from "@/hooks/use-api";
import type { Project } from "@/lib/types";
import { pluralize, relativeTime } from "@/lib/utils";

function ProjectsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const projects = useProjects({ limit: 200 });
  const [createOpen, setCreateOpen] = useState(false);
  const [renaming, setRenaming] = useState<Project | null>(null);
  const [deleting, setDeleting] = useState<Project | null>(null);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    if (searchParams.get("create") === "1") {
      setCreateOpen(true);
      router.replace("/projects");
    }
  }, [router, searchParams]);

  const items = useMemo(() => {
    const all = projects.data?.items ?? [];
    const needle = filter.trim().toLowerCase();
    if (!needle) return all;
    return all.filter(
      (project) =>
        project.name.toLowerCase().includes(needle) ||
        (project.description ?? "").toLowerCase().includes(needle),
    );
  }, [filter, projects.data?.items]);

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Library"
        title="Projects"
        description="Each project is an isolated library: its own files, index, symbols and conversations. Nothing crosses between them."
        actions={
          <>
            <Link href="/conversations" className={buttonClasses("secondary", "md")}>
              Conversations
            </Link>
            <Button
              variant="primary"
              onClick={() => setCreateOpen(true)}
              icon={<Plus className="h-4 w-4" />}
            >
              New project
            </Button>
          </>
        }
      />

      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div className="relative w-full sm:max-w-xs">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-faint" />
          <Input
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            placeholder="Filter projects…"
            className="pl-9"
            aria-label="Filter projects"
          />
        </div>
        <p className="text-[11px] text-faint">
          {projects.data
            ? `${pluralize(items.length, "project")}${
                filter ? ` of ${projects.data.total}` : ""
              }`
            : "Loading projects…"}
        </p>
      </div>

      {projects.isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2, 3, 4, 5].map((index) => (
            <CardSkeleton key={index} />
          ))}
        </div>
      ) : projects.isError ? (
        <EmptyState
          icon={<FolderKanban className="h-4 w-4" />}
          title="Could not load projects"
          description={
            projects.error instanceof Error
              ? projects.error.message
              : "Check that the API is running and reachable."
          }
          action={
            <Button onClick={() => projects.refetch()}>Try again</Button>
          }
        />
      ) : items.length === 0 ? (
        <EmptyState
          icon={<FolderKanban className="h-4 w-4" />}
          title={filter ? "No matching projects" : "No projects yet"}
          description={
            filter
              ? "Try a different name or description."
              : "Create your first project, then upload a repository, documentation set or archive. Rika indexes everything locally."
          }
          action={
            filter ? (
              <Button variant="ghost" onClick={() => setFilter("")}>
                Clear filter
              </Button>
            ) : (
              <Button
                variant="primary"
                onClick={() => setCreateOpen(true)}
                icon={<Plus className="h-3.5 w-3.5" />}
              >
                Create a project
              </Button>
            )
          }
        />
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {items.map((project) => (
            <li key={project.id}>
              <div className="group relative flex h-full flex-col rounded-2xl border border-line bg-surface/80 p-5 transition-colors hover:border-line-strong hover:bg-surface">
                <div className="flex items-start gap-3">
                  <ProjectAvatar name={project.name} size="lg" />
                  <div className="min-w-0 flex-1">
                    <Link
                      href={`/projects/${project.id}`}
                      className="block truncate font-serif text-xl leading-tight tracking-[-0.02em] text-parchment outline-none after:absolute after:inset-0 after:rounded-2xl focus-visible:after:ring-2 focus-visible:after:ring-copper/50"
                    >
                      {project.name}
                    </Link>
                    <p className="mt-1 text-[10px] text-faint">
                      Updated {relativeTime(project.updated_at)}
                    </p>
                  </div>
                  <div className="relative z-10 -mr-1 -mt-1">
                    <Menu
                      label={`Actions for ${project.name}`}
                      trigger={<MoreHorizontal className="h-4 w-4" />}
                    >
                      <MenuItem
                        icon={<ArrowUpRight className="h-3.5 w-3.5" />}
                        onSelect={() => router.push(`/projects/${project.id}`)}
                      >
                        Open workspace
                      </MenuItem>
                      <MenuItem
                        icon={<Pencil className="h-3.5 w-3.5" />}
                        onSelect={() => setRenaming(project)}
                      >
                        Rename
                      </MenuItem>
                      <MenuSeparator />
                      <MenuItem
                        danger
                        icon={<Trash2 className="h-3.5 w-3.5" />}
                        onSelect={() => setDeleting(project)}
                      >
                        Delete project
                      </MenuItem>
                    </Menu>
                  </div>
                </div>

                <p className="mt-4 line-clamp-3 min-h-[3.25rem] text-xs leading-relaxed text-muted">
                  {project.description?.trim() || "No description yet."}
                </p>

                <div className="mt-auto flex items-center justify-between gap-3 border-t border-line/60 pt-4">
                  <Link
                    href={`/projects/${project.id}/chat`}
                    className="relative z-10 text-[11px] text-copper hover:underline"
                  >
                    Ask Rika →
                  </Link>
                  <Link
                    href={`/projects/${project.id}/files`}
                    className="relative z-10 text-[11px] text-muted hover:text-parchment"
                  >
                    Files
                  </Link>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}

      <CreateProjectDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={(project) => router.push(`/projects/${project.id}`)}
      />
      {renaming ? (
        <RenameProjectDialog
          project={renaming}
          open={Boolean(renaming)}
          onClose={() => setRenaming(null)}
        />
      ) : null}
      {deleting ? (
        <DeleteProjectDialog
          project={deleting}
          open={Boolean(deleting)}
          onClose={() => setDeleting(null)}
        />
      ) : null}
    </div>
  );
}

function ProjectsFallback() {
  return (
    <div className="space-y-7">
      <div className="h-24 animate-pulse rounded-2xl bg-surface-2/40" />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {[0, 1, 2, 3, 4, 5].map((index) => (
          <CardSkeleton key={index} />
        ))}
      </div>
    </div>
  );
}

export default function ProjectsPage() {
  return (
    <Suspense fallback={<ProjectsFallback />}>
      <ProjectsContent />
    </Suspense>
  );
}
