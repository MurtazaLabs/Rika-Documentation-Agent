"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  ArrowUpRight,
  MessagesSquare,
  MoreHorizontal,
  Search,
  Trash2,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button, buttonClasses } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input, Select } from "@/components/ui/input";
import { Menu, MenuItem } from "@/components/ui/menu";
import { PageHeader } from "@/components/ui/page-header";
import { ProjectAvatar } from "@/components/ui/project-avatar";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import {
  useConversations,
  useDeleteConversation,
  useProjects,
} from "@/hooks/use-api";
import type { ConversationSummary } from "@/lib/types";
import {
  conversationTitle,
  errorMessage,
  pluralize,
  relativeTime,
} from "@/lib/utils";

export default function ConversationsPage() {
  const conversations = useConversations(undefined, 100);
  const projects = useProjects({ limit: 200 });
  const deleteConversation = useDeleteConversation();
  const { toast } = useToast();
  const [filter, setFilter] = useState("");
  const [projectFilter, setProjectFilter] = useState("all");
  const [deleting, setDeleting] = useState<ConversationSummary | null>(null);

  const projectById = useMemo(
    () =>
      new Map(
        (projects.data?.items ?? []).map((project) => [project.id, project]),
      ),
    [projects.data?.items],
  );

  const items = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    return (conversations.data?.items ?? []).filter((conversation) => {
      if (projectFilter !== "all" && conversation.project_id !== projectFilter) {
        return false;
      }
      if (!needle) return true;
      const project = projectById.get(conversation.project_id);
      return (
        conversationTitle(conversation.title).toLowerCase().includes(needle) ||
        (project?.name ?? "").toLowerCase().includes(needle)
      );
    });
  }, [conversations.data?.items, filter, projectById, projectFilter]);

  const confirmDelete = () => {
    if (!deleting) return;
    const target = deleting;
    deleteConversation.mutate(target.id, {
      onSuccess: () => {
        toast({
          title: "Conversation deleted",
          description: conversationTitle(target.title),
          tone: "success",
        });
        setDeleting(null);
      },
      onError: (error) =>
        toast({
          title: "Could not delete conversation",
          description: errorMessage(error),
          tone: "error",
        }),
    });
  };

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="History"
        title="Conversations"
        description="Every thread is scoped to its project, with the retrieved sources kept alongside each answer."
        actions={
          <Link href="/projects" className={buttonClasses("secondary", "md")}>
            Open a project
          </Link>
        }
      />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-1 flex-col gap-2 sm:max-w-xl sm:flex-row">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-faint" />
            <Input
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
              placeholder="Search conversations…"
              className="pl-9"
              aria-label="Search conversations"
            />
          </div>
          <Select
            value={projectFilter}
            onChange={(event) => setProjectFilter(event.target.value)}
            aria-label="Filter by project"
            className="sm:w-56"
          >
            <option value="all">All projects</option>
            {(projects.data?.items ?? []).map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </Select>
        </div>
        <p className="text-[11px] text-faint">
          {conversations.data
            ? `${pluralize(items.length, "conversation")}${
                filter || projectFilter !== "all"
                  ? ` of ${conversations.data.total}`
                  : ""
              }`
            : "Loading conversations…"}
        </p>
      </div>

      {conversations.isLoading ? (
        <div className="space-y-2">
          {[0, 1, 2, 3, 4].map((index) => (
            <Skeleton key={index} className="h-16 w-full" />
          ))}
        </div>
      ) : conversations.isError ? (
        <EmptyState
          icon={<MessagesSquare className="h-4 w-4" />}
          title="Could not load conversations"
          description={errorMessage(conversations.error)}
          action={
            <Button onClick={() => conversations.refetch()}>Try again</Button>
          }
        />
      ) : items.length === 0 ? (
        <EmptyState
          icon={<MessagesSquare className="h-4 w-4" />}
          title={
            filter || projectFilter !== "all"
              ? "No matching conversations"
              : "No conversations yet"
          }
          description={
            filter || projectFilter !== "all"
              ? "Try a different title or project."
              : "Open a project and ask Rika a question. Threads appear here with their message counts and sources."
          }
          action={
            filter || projectFilter !== "all" ? (
              <Button
                variant="ghost"
                onClick={() => {
                  setFilter("");
                  setProjectFilter("all");
                }}
              >
                Clear filters
              </Button>
            ) : (
              <Link href="/projects" className={buttonClasses("primary", "md")}>
                Browse projects
              </Link>
            )
          }
        />
      ) : (
        <Card className="overflow-hidden">
          <ul className="divide-y divide-line/60">
            {items.map((conversation) => {
              const project = projectById.get(conversation.project_id);
              return (
                <li key={conversation.id}>
                  <div className="group flex items-center gap-3 px-4 py-3.5 transition-colors hover:bg-surface-2/40 sm:px-5">
                    {project ? (
                      <ProjectAvatar name={project.name} size="md" />
                    ) : (
                      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-line bg-surface-2 text-faint">
                        <MessagesSquare className="h-4 w-4" />
                      </span>
                    )}
                    <Link
                      href={`/projects/${conversation.project_id}/chat?conversation=${conversation.id}`}
                      className="min-w-0 flex-1"
                    >
                      <p className="truncate text-[13px] font-medium text-parchment">
                        {conversationTitle(conversation.title)}
                      </p>
                      <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[10px] text-faint">
                        <span>{project?.name ?? "Project"}</span>
                        <span>·</span>
                        <span>
                          {pluralize(conversation.message_count, "message")}
                        </span>
                        <span>·</span>
                        <span>{relativeTime(conversation.updated_at)}</span>
                      </p>
                    </Link>
                    <Badge tone="neutral" className="hidden sm:inline-flex">
                      {relativeTime(conversation.updated_at)}
                    </Badge>
                    <Link
                      href={`/projects/${conversation.project_id}/chat?conversation=${conversation.id}`}
                      className="hidden h-8 items-center gap-1 rounded-lg border border-line px-2.5 text-[10px] text-muted transition-colors hover:border-line-strong hover:text-parchment sm:inline-flex"
                    >
                      Open <ArrowUpRight className="h-3 w-3" />
                    </Link>
                    <Menu
                      label="Conversation actions"
                      trigger={<MoreHorizontal className="h-4 w-4" />}
                    >
                      <MenuItem
                        danger
                        icon={<Trash2 className="h-3.5 w-3.5" />}
                        onSelect={() => setDeleting(conversation)}
                      >
                        Delete conversation
                      </MenuItem>
                    </Menu>
                  </div>
                </li>
              );
            })}
          </ul>
        </Card>
      )}

      <ConfirmDialog
        open={Boolean(deleting)}
        onClose={() => setDeleting(null)}
        onConfirm={confirmDelete}
        title="Delete this conversation?"
        description={
          deleting
            ? `“${conversationTitle(deleting.title)}” and its messages will be removed. The project's files and index are not affected.`
            : ""
        }
        confirmLabel="Delete conversation"
        loading={deleteConversation.isPending}
      />
    </div>
  );
}
