"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  ChevronsDownUp,
  ChevronsUpDown,
  Eye,
  Folder,
  FolderOpen,
  MoreHorizontal,
  RefreshCw,
  Search,
  Trash2,
  FolderSearch,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Menu, MenuItem, MenuSeparator } from "@/components/ui/menu";
import { ProgressBar } from "@/components/ui/progress";
import { FileGlyph } from "@/components/ui/file-icon";
import type { Document, Job } from "@/lib/types";
import {
  buildFileTree,
  cn,
  countTreeItems,
  formatBytes,
  isActiveJob,
  statusTone,
  type FileTreeNode,
} from "@/lib/utils";

interface FileExplorerProps {
  documents: Document[];
  jobsByDocument: Map<string, Job>;
  filter: string;
  onFilterChange: (value: string) => void;
  onPreview: (document: Document) => void;
  onDelete: (document: Document) => void;
  onReindex: (document: Document) => void;
}

function filterTree(nodes: FileTreeNode[], needle: string): FileTreeNode[] {
  if (!needle) return nodes;
  const lower = needle.toLowerCase();
  const next: FileTreeNode[] = [];
  for (const node of nodes) {
    if (node.kind === "file") {
      if (node.document.original_path.toLowerCase().includes(lower)) {
        next.push(node);
      }
      continue;
    }
    const children = filterTree(node.children, needle);
    if (children.length > 0 || node.path.toLowerCase().includes(lower)) {
      next.push({ ...node, children });
    }
  }
  return next;
}

function allFolderPaths(nodes: FileTreeNode[], into = new Set<string>()) {
  for (const node of nodes) {
    if (node.kind === "folder") {
      into.add(node.path);
      allFolderPaths(node.children, into);
    }
  }
  return into;
}

export function FileExplorer({
  documents,
  jobsByDocument,
  filter,
  onFilterChange,
  onPreview,
  onDelete,
  onReindex,
}: FileExplorerProps) {
  const tree = useMemo(() => buildFileTree(documents), [documents]);
  const visibleTree = useMemo(
    () => filterTree(tree, filter.trim()),
    [filter, tree],
  );
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current || documents.length === 0) return;
    initialized.current = true;
    setExpanded(
      new Set(
        tree
          .filter((node): node is Extract<FileTreeNode, { kind: "folder" }> =>
            node.kind === "folder",
          )
          .map((node) => node.path),
      ),
    );
  }, [documents.length, tree]);

  const toggle = (path: string) => {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  const isOpen = (path: string) => filter.trim() !== "" || expanded.has(path);

  const renderNode = (node: FileTreeNode, depth: number) => {
    if (node.kind === "folder") {
      const open = isOpen(node.path);
      const count = countTreeItems(node.children);
      return (
        <li key={`folder:${node.path}`}>
          <button
            type="button"
            onClick={() => toggle(node.path)}
            className="flex w-full items-center gap-2 rounded-lg py-2 pr-2 text-left transition-colors hover:bg-surface-2/50"
            style={{ paddingLeft: `${depth * 16 + 8}px` }}
            aria-expanded={open}
          >
            {open ? (
              <ChevronDown className="h-3.5 w-3.5 shrink-0 text-faint" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5 shrink-0 text-faint" />
            )}
            {open ? (
              <FolderOpen className="h-4 w-4 shrink-0 text-copper/80" />
            ) : (
              <Folder className="h-4 w-4 shrink-0 text-copper/70" />
            )}
            <span className="min-w-0 flex-1 truncate text-xs text-parchment">
              {node.name}
            </span>
            <span className="font-mono text-[9px] text-faint">{count}</span>
          </button>
          {open ? (
            <ul>{node.children.map((child) => renderNode(child, depth + 1))}</ul>
          ) : null}
        </li>
      );
    }

    const document = node.document;
    const job = jobsByDocument.get(document.id);
    const active = job ? isActiveJob(job) : false;
    const failed = job?.status === "failed" || document.status === "failed";

    return (
      <li key={`file:${document.id}`}>
        <div
          className="group flex items-start gap-2 rounded-lg py-1.5 pr-1 transition-colors hover:bg-surface-2/50"
          style={{ paddingLeft: `${depth * 16 + 28}px` }}
        >
          <button
            type="button"
            onClick={() => onPreview(document)}
            className="flex min-w-0 flex-1 items-start gap-2 text-left focus-visible:outline-none"
          >
            <FileGlyph document={document} className="mt-0.5" />
            <span className="min-w-0 flex-1">
              <span className="flex items-center gap-2">
                <span className="truncate text-xs text-parchment">
                  {node.name}
                </span>
                <Badge
                  tone={
                    failed ? "rose" : active ? "gold" : statusTone(document.status)
                  }
                  className="shrink-0"
                >
                  {active && job ? `${job.progress}%` : document.status}
                </Badge>
              </span>
              <span className="mt-0.5 block truncate font-mono text-[9px] text-faint">
                {formatBytes(document.size)}
                {document.original_path.includes("/")
                  ? ` · ${document.original_path.slice(0, document.original_path.lastIndexOf("/"))}`
                  : ""}
              </span>
              {active && job ? (
                <ProgressBar value={job.progress} className="mt-1.5 max-w-48" />
              ) : null}
            </span>
          </button>
          <Menu
            label={`Actions for ${document.original_path}`}
            trigger={<MoreHorizontal className="h-3.5 w-3.5" />}
            className="opacity-60 transition-opacity group-hover:opacity-100"
          >
            <MenuItem
              icon={<Eye className="h-3.5 w-3.5" />}
              onSelect={() => onPreview(document)}
            >
              Preview source
            </MenuItem>
            <MenuItem
              icon={<RefreshCw className="h-3.5 w-3.5" />}
              onSelect={() => onReindex(document)}
              disabled={active}
            >
              Reindex
            </MenuItem>
            <MenuSeparator />
            <MenuItem
              danger
              icon={<Trash2 className="h-3.5 w-3.5" />}
              onSelect={() => onDelete(document)}
            >
              Delete document
            </MenuItem>
          </Menu>
        </div>
      </li>
    );
  };

  return (
    <div className="flex min-h-0 flex-col">
      <div className="flex flex-col gap-2 border-b border-line/70 px-4 py-3 sm:flex-row sm:items-center">
        <div className="relative min-w-0 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-faint" />
          <Input
            value={filter}
            onChange={(event) => onFilterChange(event.target.value)}
            placeholder="Filter by filename or path…"
            className="h-9 pl-9"
            aria-label="Filter files"
          />
        </div>
        <div className="flex items-center gap-1">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setExpanded(allFolderPaths(visibleTree))}
            icon={<ChevronsUpDown className="h-3.5 w-3.5" />}
          >
            Expand all
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setExpanded(new Set())}
            icon={<ChevronsDownUp className="h-3.5 w-3.5" />}
          >
            Collapse
          </Button>
        </div>
      </div>

      {visibleTree.length === 0 ? (
        <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
          <FolderSearch className="h-8 w-8 text-faint" />
          <p className="mt-3 text-xs font-medium text-parchment">
            No matching files
          </p>
          <p className="mt-1 text-[11px] text-muted">
            {filter ? "Try a different filename or path." : "Upload files to start."}
          </p>
          {filter ? (
            <Button
              size="sm"
              variant="ghost"
              className="mt-3"
              onClick={() => onFilterChange("")}
            >
              Clear filter
            </Button>
          ) : null}
        </div>
      ) : (
        <ul
          className={cn("flex-1 overflow-y-auto px-2 py-2", "max-h-[62vh]")}
        >
          {visibleTree.map((node) => renderNode(node, 0))}
        </ul>
      )}
    </div>
  );
}
