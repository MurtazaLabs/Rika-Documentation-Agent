"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import {
  ChevronRight,
  FolderKanban,
  LayoutDashboard,
  Menu as MenuIcon,
  MessagesSquare,
  Plus,
  Settings2,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";

import { RikaWordmark } from "@/components/ui/brand";
import { buttonClasses } from "@/components/ui/button";
import { ProjectAvatar } from "@/components/ui/project-avatar";
import { ReadinessPill, StatusDot } from "@/components/ui/status";
import { useProject, useProjects, useReadiness } from "@/hooks/use-api";
import type { Project } from "@/lib/types";
import {
  cn,
  getActiveProjectId,
  rememberProject,
  setActiveProjectId,
} from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { href: "/projects", label: "Projects", icon: FolderKanban, exact: false },
  { href: "/conversations", label: "Conversations", icon: MessagesSquare, exact: false },
  { href: "/settings", label: "Settings", icon: Settings2, exact: false },
];

function isActive(pathname: string, href: string, exact: boolean) {
  if (exact) return pathname === href;
  return pathname === href || pathname.startsWith(`${href}/`);
}

function SidebarContent({
  pathname,
  projects,
  activeProjectId,
  onNavigate,
}: {
  pathname: string;
  projects: Project[];
  activeProjectId: string | null;
  onNavigate?: () => void;
}) {
  const readiness = useReadiness();

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between px-5 pb-5 pt-6">
        <Link href="/" onClick={onNavigate} className="group">
          <RikaWordmark />
        </Link>
        {onNavigate ? (
          <button
            type="button"
            onClick={onNavigate}
            className="rounded-lg p-1.5 text-faint hover:bg-surface-2 hover:text-parchment"
            aria-label="Close navigation"
          >
            <X className="h-4 w-4" />
          </button>
        ) : null}
      </div>

      <nav className="px-3" aria-label="Main navigation">
        <ul className="space-y-0.5">
          {NAV_ITEMS.map((item) => {
            const active = isActive(pathname, item.href, item.exact);
            const Icon = item.icon;
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  onClick={onNavigate}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "group relative flex h-9 items-center gap-3 rounded-lg px-3 text-[13px] transition-colors",
                    active
                      ? "bg-surface-2/90 text-parchment"
                      : "text-muted hover:bg-surface-2/50 hover:text-parchment",
                  )}
                >
                  {active ? (
                    <span className="absolute inset-y-2 left-0 w-[2px] rounded-full bg-copper" />
                  ) : null}
                  <Icon
                    className={cn(
                      "h-[15px] w-[15px]",
                      active ? "text-copper" : "text-faint group-hover:text-muted",
                    )}
                    strokeWidth={1.7}
                  />
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="mt-7 flex items-center justify-between px-5">
        <p className="font-mono text-[9px] uppercase tracking-[0.2em] text-faint">
          Projects
        </p>
        <Link
          href="/projects?create=1"
          onClick={onNavigate}
          className="rounded-md p-1 text-faint transition-colors hover:bg-surface-2 hover:text-copper"
          aria-label="Create a project"
        >
          <Plus className="h-3.5 w-3.5" />
        </Link>
      </div>

      <div className="mt-2 flex-1 overflow-y-auto px-3 pb-4">
        {projects.length === 0 ? (
          <p className="px-2 py-3 text-[11px] leading-relaxed text-faint">
            No projects yet. Create one to start indexing files.
          </p>
        ) : (
          <ul className="space-y-0.5">
            {projects.slice(0, 5).map((project) => {
              const active = project.id === activeProjectId;
              return (
                <li key={project.id}>
                  <Link
                    href={`/projects/${project.id}`}
                    onClick={() => {
                      rememberProject(project.id);
                      onNavigate?.();
                    }}
                    className={cn(
                      "group flex h-9 items-center gap-2.5 rounded-lg px-2 text-[12px] transition-colors",
                      active
                        ? "bg-surface-2/80 text-parchment"
                        : "text-muted hover:bg-surface-2/50 hover:text-parchment",
                    )}
                  >
                    <ProjectAvatar name={project.name} size="sm" />
                    <span className="min-w-0 flex-1 truncate">{project.name}</span>
                    <ChevronRight
                      className={cn(
                        "h-3 w-3 shrink-0 transition-opacity",
                        active
                          ? "text-copper opacity-100"
                          : "text-faint opacity-0 group-hover:opacity-100",
                      )}
                    />
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
        {projects.length > 5 ? (
          <Link
            href="/projects"
            onClick={onNavigate}
            className="mt-1 block px-2 text-[10px] text-faint transition-colors hover:text-copper"
          >
            All {projects.length} projects →
          </Link>
        ) : null}
      </div>

      <div className="border-t border-line/70 p-3">
        <div className="rounded-xl border border-line bg-surface-2/40 p-3.5">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-3.5 w-3.5 text-sage" />
            <p className="text-[11px] font-medium text-parchment">Local-first</p>
            <StatusDot
              tone={
                readiness.data?.status === "ready"
                  ? "ok"
                  : readiness.data
                    ? "warning"
                    : "idle"
              }
              className="ml-auto"
            />
          </div>
          <p className="mt-1.5 text-[10px] leading-relaxed text-faint">
            Files, embeddings and answers never leave this machine.
          </p>
        </div>
      </div>
    </div>
  );
}

function Breadcrumbs({ pathname }: { pathname: string }) {
  const projectMatch = pathname.match(/^\/projects\/([^/]+)(?:\/([^/]+))?/);
  const projectId = projectMatch?.[1];
  const section = projectMatch?.[2];
  const project = useProject(projectId);

  if (pathname === "/") {
    return <span className="text-[12px] text-muted">Dashboard</span>;
  }

  if (projectId) {
    return (
      <div className="flex min-w-0 items-center gap-2 text-[12px]">
        <Link href="/projects" className="hidden text-faint hover:text-parchment sm:inline">
          Projects
        </Link>
        <ChevronRight className="hidden h-3 w-3 text-faint sm:inline" />
        <Link
          href={`/projects/${projectId}`}
          className="max-w-[180px] truncate text-muted hover:text-parchment"
        >
          {project.data?.name ?? "Project"}
        </Link>
        <ChevronRight className="h-3 w-3 shrink-0 text-faint" />
        <span className="capitalize text-parchment">
          {section === "chat"
            ? "Chat"
            : section === "files"
              ? "Files"
              : section === "search"
                ? "Search"
                : "Overview"}
        </span>
      </div>
    );
  }

  const labels: Record<string, string> = {
    "/projects": "Projects",
    "/conversations": "Conversations",
    "/settings": "Settings",
    "/chat": "Chat",
  };

  return <span className="text-[12px] text-muted">{labels[pathname] ?? "Workspace"}</span>;
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null);
  const projectsQuery = useProjects({ limit: 8 });
  const readiness = useReadiness();
  const projects = projectsQuery.data?.items ?? [];
  const routeProjectId = pathname.match(/^\/projects\/([^/]+)/)?.[1] ?? null;
  const currentProjectId = routeProjectId ?? activeProjectId ?? projects[0]?.id ?? null;

  useEffect(() => {
    setActiveProjectId(getActiveProjectId());
  }, []);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (routeProjectId) {
      rememberProject(routeProjectId);
      setActiveProjectId(routeProjectId);
    }
  }, [routeProjectId]);

  const askHref = currentProjectId
    ? `/projects/${currentProjectId}/chat`
    : "/chat";

  return (
    <div className="min-h-dvh">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-[264px] border-r border-line/80 bg-canvas/85 backdrop-blur-xl lg:block">
        <SidebarContent
          pathname={pathname}
          projects={projects}
          activeProjectId={currentProjectId}
        />
      </aside>

      {mobileOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="absolute inset-0 bg-black/70 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
            aria-hidden="true"
          />
          <aside className="relative h-full w-[284px] border-r border-line bg-canvas shadow-2xl animate-[fade-in_150ms_ease-out]">
            <SidebarContent
              pathname={pathname}
              projects={projects}
              activeProjectId={currentProjectId}
              onNavigate={() => setMobileOpen(false)}
            />
          </aside>
        </div>
      ) : null}

      <div className="lg:pl-[264px]">
        <header className="sticky top-0 z-30 border-b border-line/70 bg-canvas/75 backdrop-blur-xl">
          <div className="mx-auto flex h-14 w-full max-w-[1440px] items-center gap-3 px-4 sm:px-7 lg:px-10">
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              className="rounded-lg p-1.5 text-muted hover:bg-surface-2 hover:text-parchment lg:hidden"
              aria-label="Open navigation"
            >
              <MenuIcon className="h-4 w-4" />
            </button>
            <Breadcrumbs pathname={pathname} />
            <div className="ml-auto flex items-center gap-2.5">
              <div className="hidden sm:block">
                <ReadinessPill
                  readiness={readiness.data}
                  loading={readiness.isLoading}
                />
              </div>
              <Link href={askHref} className={buttonClasses("primary", "sm")}>
                <Sparkles className="h-3.5 w-3.5" />
                Ask Rika
              </Link>
            </div>
          </div>
        </header>

        <main
          key={pathname}
          className="mx-auto w-full max-w-[1440px] px-4 pb-20 pt-7 sm:px-7 lg:px-10 lg:pt-9"
        >
          {children}
        </main>
      </div>
    </div>
  );
}
