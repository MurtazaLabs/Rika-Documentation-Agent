"use client";

import { useMemo, useState } from "react";
import {
  MessageSquarePlus,
  MessagesSquare,
  MoreHorizontal,
  Search,
  Trash2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Menu, MenuItem } from "@/components/ui/menu";
import { Skeleton } from "@/components/ui/skeleton";
import type { ConversationSummary, UUID } from "@/lib/types";
import {
  cn,
  conversationTitle,
  pluralize,
  relativeTime,
} from "@/lib/utils";

export function ConversationPanel({
  conversations,
  activeId,
  loading,
  onNew,
  onSelect,
  onDelete,
  className,
}: {
  conversations: ConversationSummary[];
  activeId: UUID | null;
  loading: boolean;
  onNew: () => void;
  onSelect: (conversationId: UUID) => void;
  onDelete: (conversation: ConversationSummary) => void;
  className?: string;
}) {
  const [filter, setFilter] = useState("");

  const filtered = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    if (!needle) return conversations;
    return conversations.filter((conversation) =>
      conversationTitle(conversation.title)
        .toLowerCase()
        .includes(needle),
    );
  }, [conversations, filter]);

  return (
    <div className={cn("flex h-full min-h-0 flex-col", className)}>
      <div className="border-b border-line/70 p-3">
        <div className="flex items-center justify-between">
          <p className="font-mono text-[9px] uppercase tracking-[0.2em] text-faint">
            History
          </p>
          <button
            type="button"
            onClick={onNew}
            className="inline-flex h-7 w-7 items-center justify-center rounded-lg text-faint transition-colors hover:bg-surface-2 hover:text-copper"
            aria-label="Start a new conversation"
            title="New conversation"
          >
            <MessageSquarePlus className="h-3.5 w-3.5" />
          </button>
        </div>
        <Button
          variant="secondary"
          size="sm"
          className="mt-2.5 w-full justify-start"
          onClick={onNew}
          icon={<MessageSquarePlus className="h-3.5 w-3.5" />}
        >
          New conversation
        </Button>
        {conversations.length > 5 ? (
          <div className="relative mt-2">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3 w-3 -translate-y-1/2 text-faint" />
            <Input
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
              placeholder="Filter history…"
              className="h-8 pl-8 text-[11px]"
              aria-label="Filter conversations"
            />
          </div>
        ) : null}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {loading ? (
          <div className="space-y-2 p-1">
            {[0, 1, 2, 3].map((index) => (
              <Skeleton key={index} className="h-12 w-full" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="px-3 py-8 text-center">
            <MessagesSquare className="mx-auto h-5 w-5 text-faint" />
            <p className="mt-2 text-[11px] text-muted">
              {filter ? "No matching conversations." : "No conversations yet."}
            </p>
            <p className="mt-1 text-[10px] leading-relaxed text-faint">
              Ask a question to start a thread. Follow-ups reuse the same
              project context.
            </p>
          </div>
        ) : (
          <ul className="space-y-0.5">
            {filtered.map((conversation) => {
              const active = conversation.id === activeId;
              return (
                <li key={conversation.id}>
                  <div
                    className={cn(
                      "group relative flex items-start gap-1 rounded-lg transition-colors",
                      active
                        ? "bg-surface-2 text-parchment"
                        : "text-muted hover:bg-surface-2/60 hover:text-parchment",
                    )}
                  >
                    {active ? (
                      <span className="absolute inset-y-2 left-0 w-[2px] rounded-full bg-copper" />
                    ) : null}
                    <button
                      type="button"
                      onClick={() => onSelect(conversation.id)}
                      className="min-w-0 flex-1 px-2.5 py-2 text-left"
                    >
                      <span className="block truncate text-[11.5px] leading-snug">
                        {conversationTitle(conversation.title)}
                      </span>
                      <span className="mt-0.5 block text-[9px] text-faint">
                        {pluralize(conversation.message_count, "message")} ·{" "}
                        {relativeTime(conversation.updated_at)}
                      </span>
                    </button>
                    <Menu
                      label="Conversation actions"
                      trigger={<MoreHorizontal className="h-3.5 w-3.5" />}
                      className="mr-1 mt-1.5 shrink-0 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100"
                    >
                      <MenuItem
                        danger
                        icon={<Trash2 className="h-3.5 w-3.5" />}
                        onSelect={() => onDelete(conversation)}
                      >
                        Delete conversation
                      </MenuItem>
                    </Menu>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <div className="border-t border-line/70 px-3 py-2.5">
        <p className="text-[9px] leading-relaxed text-faint">
          History is scoped to this project and stored locally.
        </p>
      </div>
    </div>
  );
}
