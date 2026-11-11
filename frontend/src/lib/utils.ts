import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

import type { Document, Job } from "@/lib/types";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const DATE_FORMAT = new Intl.DateTimeFormat("en", {
  month: "short",
  day: "numeric",
  year: "numeric",
});

const TIME_FORMAT = new Intl.DateTimeFormat("en", {
  hour: "numeric",
  minute: "2-digit",
});

export function formatDate(value: string | Date) {
  return DATE_FORMAT.format(new Date(value));
}

export function formatTime(value: string | Date) {
  return TIME_FORMAT.format(new Date(value));
}

export function formatDateTime(value: string | Date) {
  return `${formatDate(value)} · ${formatTime(value)}`;
}

export function relativeTime(value: string | Date) {
  const date = new Date(value);
  const seconds = Math.round((date.getTime() - Date.now()) / 1000);
  const absolute = Math.abs(seconds);
  if (absolute < 45) return "just now";

  const formatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  if (absolute < 3600) return formatter.format(Math.round(seconds / 60), "minute");
  if (absolute < 86_400) return formatter.format(Math.round(seconds / 3600), "hour");
  if (absolute < 604_800) return formatter.format(Math.round(seconds / 86_400), "day");
  if (absolute < 2_592_000) {
    return formatter.format(Math.round(seconds / 604_800), "week");
  }
  if (absolute < 31_536_000) {
    return formatter.format(Math.round(seconds / 2_592_000), "month");
  }
  return formatter.format(Math.round(seconds / 31_536_000), "year");
}

export function formatBytes(bytes: number) {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const exponent = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1,
  );
  const value = bytes / 1024 ** exponent;
  return `${value >= 10 || exponent === 0 ? Math.round(value) : value.toFixed(1)} ${units[exponent]}`;
}

export function initials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "R";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}

const PROJECT_COLORS = [
  "text-[#e0a179] bg-[#e0a179]/10 border-[#e0a179]/25",
  "text-[#9db5a4] bg-[#9db5a4]/10 border-[#9db5a4]/25",
  "text-[#8ba9c7] bg-[#8ba9c7]/10 border-[#8ba9c7]/25",
  "text-[#d9b26f] bg-[#d9b26f]/10 border-[#d9b26f]/25",
  "text-[#c9a0c4] bg-[#c9a0c4]/10 border-[#c9a0c4]/25",
  "text-[#d98a8a] bg-[#d98a8a]/10 border-[#d98a8a]/25",
];

export function projectColor(name: string) {
  let hash = 0;
  for (let index = 0; index < name.length; index += 1) {
    hash = (hash * 31 + name.charCodeAt(index)) >>> 0;
  }
  return PROJECT_COLORS[hash % PROJECT_COLORS.length];
}

export function statusTone(status: string) {
  switch (status) {
    case "indexed":
    case "succeeded":
    case "ready":
      return "sage" as const;
    case "processing":
    case "running":
    case "queued":
    case "pending":
      return "gold" as const;
    case "failed":
    case "cancelled":
    case "unavailable":
      return "rose" as const;
    case "skipped":
    case "degraded":
      return "blue" as const;
    default:
      return "neutral" as const;
  }
}

export function isActiveJob(job: Job) {
  return job.status === "queued" || job.status === "running";
}

export function lineLabel(
  startLine: number | null,
  endLine: number | null,
  pageNumber: number | null,
) {
  if (startLine !== null && endLine !== null) {
    return startLine === endLine ? `L${startLine}` : `L${startLine}–${endLine}`;
  }
  if (startLine !== null) return `L${startLine}`;
  if (pageNumber !== null) return `p. ${pageNumber}`;
  return "source";
}

export function truncate(value: string, length: number) {
  if (value.length <= length) return value;
  return `${value.slice(0, length - 1).trimEnd()}…`;
}

export function pluralize(count: number, singular: string, plural?: string) {
  return `${count} ${count === 1 ? singular : (plural ?? `${singular}s`)}`;
}

export function errorMessage(error: unknown, fallback = "Something went wrong.") {
  if (error instanceof Error && error.message.trim()) return error.message;
  return fallback;
}

export function conversationTitle(title: string | null | undefined) {
  return title?.trim() || "Untitled conversation";
}

export type FileTreeNode =
  | {
      kind: "folder";
      name: string;
      path: string;
      children: FileTreeNode[];
    }
  | {
      kind: "file";
      name: string;
      path: string;
      document: Document;
    };

interface FolderBuilder {
  name: string;
  path: string;
  folders: Map<string, FolderBuilder>;
  files: Array<{ name: string; document: Document }>;
}

export function buildFileTree(documents: Document[]): FileTreeNode[] {
  const root: FolderBuilder = { name: "", path: "", folders: new Map(), files: [] };

  for (const document of documents) {
    const segments = document.original_path.split(/[\\/]/).filter(Boolean);
    if (segments.length === 0) continue;
    let folder = root;
    for (const segment of segments.slice(0, -1)) {
      const path = folder.path ? `${folder.path}/${segment}` : segment;
      let child = folder.folders.get(segment);
      if (!child) {
        child = { name: segment, path, folders: new Map(), files: [] };
        folder.folders.set(segment, child);
      }
      folder = child;
    }
    folder.files.push({
      name: segments[segments.length - 1],
      document,
    });
  }

  const convert = (folder: FolderBuilder): FileTreeNode[] => {
    const folders = [...folder.folders.values()]
      .sort((left, right) => left.name.localeCompare(right.name))
      .map<FileTreeNode>((child) => ({
        kind: "folder",
        name: child.name,
        path: child.path,
        children: convert(child),
      }));
    const files = folder.files
      .sort((left, right) => left.name.localeCompare(right.name))
      .map<FileTreeNode>((file) => ({
        kind: "file",
        name: file.name,
        path: file.document.original_path,
        document: file.document,
      }));
    return [...folders, ...files];
  };

  return convert(root);
}

export function countTreeItems(nodes: FileTreeNode[]): number {
  return nodes.reduce(
    (total, node) =>
      total + (node.kind === "file" ? 1 : countTreeItems(node.children)),
    0,
  );
}

const ACTIVE_PROJECT_KEY = "rika.active-project";
const RECENT_PROJECTS_KEY = "rika.recent-projects";

export function getActiveProjectId(): string | null {
  return readStorage<string | null>(ACTIVE_PROJECT_KEY, null);
}

export function setActiveProjectId(projectId: string | null) {
  writeStorage(ACTIVE_PROJECT_KEY, projectId);
}

export function getRecentProjectIds(): string[] {
  const value = readStorage<unknown>(RECENT_PROJECTS_KEY, []);
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

export function rememberProject(projectId: string) {
  setActiveProjectId(projectId);
  const recent = getRecentProjectIds().filter((item) => item !== projectId);
  writeStorage(RECENT_PROJECTS_KEY, [projectId, ...recent].slice(0, 6));
}

export function readStorage<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = window.localStorage.getItem(key);
    return raw === null ? fallback : (JSON.parse(raw) as T);
  } catch {
    return fallback;
  }
}

export function writeStorage(key: string, value: unknown) {
  if (typeof window === "undefined") return;
  try {
    if (value === null) {
      window.localStorage.removeItem(key);
    } else {
      window.localStorage.setItem(key, JSON.stringify(value));
    }
  } catch {
    // Storage can be unavailable in private windows; the UI still works.
  }
}

export async function copyText(value: string) {
  if (typeof navigator === "undefined" || !navigator.clipboard) return false;
  try {
    await navigator.clipboard.writeText(value);
    return true;
  } catch {
    return false;
  }
}
