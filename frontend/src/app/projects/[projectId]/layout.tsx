"use client";

import Link from "next/link";
import { useParams, usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import {
  Brain,
  FileStack,
  LayoutDashboard,
  MessagesSquare,
  MoreHorizontal,
  Pencil,
  Search,
  Sparkles,
  Trash2,
} from "lucide-react";

import {
  DeleteProjectDialog,
  RenameProjectDialog,
} from "@/components/projects/project-dialogs";
import { Button, buttonClasses } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Menu, MenuItem, MenuSeparator } from "@/components/ui/menu";
import { ProjectAvatar } from "@/components/ui/project-avatar";
import { Skeleton } from "@/components/ui/skeleton";
import { useProject } from "@/hooks/use-api";
import { cn, relativeTime, rememberProject } from "@/lib/utils";

const TABS = [
  { segment: "", label: "Overview", icon: LayoutDashboard },
  { segment: "files", label: "Files", icon: FileStack },
  { segment: "search", label: "Search", icon: Search },
  { segment: "chat", label: "Chat", icon: MessagesSquare },
  { segment: "intelligence", label: "Intelligence", icon: Brain },
];

export default function ProjectWorkspaceLayout({
  children,
}: {
  children: ReactNode;
}) {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
  const pathname = usePathname();
  const router = useRouter();
  const project = useProject(projectId);
  const [renameOpen, setRenameOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  useEffect(() => {
    if (projectId) rememberProject(projectId);
  }, [projectId]);

  if (project.isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Skeleton className="h-12 w-12 rounded-xl" />
          <div className="space-y-2">
            <Skeleton className="h-7 w-56" />
            <Skeleton className="h-3 w-80" />
          </div>
        </div>
        <Skeleton className="h-10 w-full max-w-md" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (project.isError || !project.data) {
    return (
      <EmptyState
        icon={<LayoutDashboard className="h-4 w-4" />}
        title="Project not found"
        description={
          project.error instanceof Error
            ? project.error.message
            : "This project may have been deleted."
        }
        action={
          <Link href="/projects" className={buttonClasses("primary", "md")}>
            Back to projects
          </Link>
        }
      />
    );
  }

  const data = project.data;
  const base = `/projects/${projectId}`;
  const tabBar = (
    <nav
      aria-label="Project sections"
      className="scrollbar-none -mb-px flex gap-1 overflow-x-auto border-b border-line/70"
    >
      {TABS.map((tab) => {
        const href = tab.segment ? `${base}/${tab.segment}` : base;
        const active =
          tab.segment === ""
            ? pathname === base || pathname === `${base}/`
            : pathname.startsWith(`${base}/${tab.segment}`);
        const Icon = tab.icon;
        return (
          <Link
            key={tab.segment || "overview"}
            href={href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "relative inline-flex items-center gap-2 whitespace-nowrap px-3.5 py-3 text-[12px] transition-colors",
              active
                ? "text-parchment"
                : "text-muted hover:text-parchment",
            )}
          >
            <Icon
              className={cn(
                "h-3.5 w-3.5",
                active ? "text-copper" : "text-faint",
              )}
              strokeWidth={1.7}
            />
            {tab.label}
            {active ? (
              <span className="absolute inset-x-2 -bottom-px h-[2px] rounded-full bg-copper" />
            ) : null}
          </Link>
        );
      })}
    </nav>
  );

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
        <div className="flex min-w-0 items-start gap-4">
          <ProjectAvatar name={data.name} size="lg" className="mt-0.5" />
          <div className="min-w-0">
            <p className="font-mono text-[9px] uppercase tracking-[0.2em] text-copper">
              Project
            </p>
            <h1 className="mt-1.5 truncate font-serif text-[2rem] leading-none tracking-[-0.03em] text-parchment md:text-[2.5rem]">
              {data.name}
            </h1>
            <p className="mt-2 max-w-2xl text-[12.5px] leading-relaxed text-muted">
              {data.description?.trim() || "No description yet."}
            </p>
            <p className="mt-1.5 text-[10px] text-faint">
              Updated {relativeTime(data.updated_at)}
            </p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <Link
            href={`${base}/chat`}
            className={buttonClasses("primary", "md")}
          >
            <Sparkles className="h-4 w-4" />
            Ask Rika
          </Link>
          <Menu
            label={`Actions for ${data.name}`}
            trigger={<MoreHorizontal className="h-4 w-4" />}
          >
            <MenuItem
              icon={<Pencil className="h-3.5 w-3.5" />}
              onSelect={() => setRenameOpen(true)}
            >
              Rename project
            </MenuItem>
            <MenuSeparator />
            <MenuItem
              danger
              icon={<Trash2 className="h-3.5 w-3.5" />}
              onSelect={() => setDeleteOpen(true)}
            >
              Delete project
            </MenuItem>
          </Menu>
        </div>
      </header>

      {tabBar}

      <div>{children}</div>

      <RenameProjectDialog
        project={data}
        open={renameOpen}
        onClose={() => setRenameOpen(false)}
      />
      <DeleteProjectDialog
        project={data}
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        onDeleted={() => {
          router.push("/projects");
        }}
      />
    </div>
  );
}
