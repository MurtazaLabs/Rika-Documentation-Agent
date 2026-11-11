"use client";

import {
  Suspense,
  useEffect,
  useRef,
  useState,
} from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  ArrowUp,
  History,
  Loader2,
  Sparkles,
  SquarePen,
  X,
} from "lucide-react";

import { ChatMessageView, type ChatThreadMessage } from "@/components/chat/chat-message";
import { ConversationPanel } from "@/components/chat/conversation-panel";
import { SourceViewer } from "@/components/source-viewer";
import { RikaMark } from "@/components/ui/brand";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import {
  useConversation,
  useConversations,
  useDeleteConversation,
} from "@/hooks/use-api";
import { streamChat } from "@/lib/api";
import type {
  Citation,
  ConversationMessage,
  ConversationSummary,
} from "@/lib/types";
import {
  conversationTitle,
  errorMessage,
  pluralize,
} from "@/lib/utils";

const SUGGESTIONS = [
  "Give me a tour of this project.",
  "Where is the entry point, and what does it start?",
  "How is data persisted and validated?",
  "What should I read first to understand the architecture?",
];

function toThreadMessage(message: ConversationMessage): ChatThreadMessage {
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    citations: message.citations,
    createdAt: message.created_at,
    grounded: message.citations.length > 0,
  };
}

function ChatContent() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const initialConversation = searchParams.get("conversation");
  const [conversationId, setConversationId] = useState<string | null>(
    initialConversation,
  );
  const [thread, setThread] = useState<ChatThreadMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [deleting, setDeleting] = useState<ConversationSummary | null>(null);
  const [viewing, setViewing] = useState<Citation | null>(null);
  const [localTitle, setLocalTitle] = useState<string | null>(null);

  const conversations = useConversations(projectId, 50);
  const conversation = useConversation(conversationId ?? undefined, projectId);
  const deleteConversation = useDeleteConversation(projectId);

  const seededFor = useRef<string | null>(null);
  const lastParam = useRef<string | null>(initialConversation);
  const lastAsk = useRef<string | null>(null);
  const stickToBottom = useRef(true);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const controllerRef = useRef<AbortController | null>(null);

  const conversationParam = searchParams.get("conversation");
  const askParam = searchParams.get("ask");
  const title = conversation.data
    ? conversationTitle(conversation.data.title)
    : (localTitle ?? "New conversation");

  const urlFor = (id: string | null) =>
    `/projects/${projectId}/chat${id ? `?conversation=${id}` : ""}`;

  // Browser back/forward changes the URL without remounting this page.
  useEffect(() => {
    if (conversationParam === lastParam.current) return;
    lastParam.current = conversationParam;
    setConversationId(conversationParam);
    seededFor.current = null;
    setThread([]);
    setStreamError(null);
  }, [conversationParam]);

  // Seed the thread once per conversation. Streamed turns update it locally,
  // so later refetches must not overwrite a live answer.
  useEffect(() => {
    if (!conversationId || !conversation.data) return;
    if (seededFor.current === conversationId) return;
    seededFor.current = conversationId;
    setThread(conversation.data.messages.map(toThreadMessage));
  }, [conversation.data, conversationId]);

  // A question handed over from the dashboard or overview page.
  useEffect(() => {
    if (!askParam || askParam === lastAsk.current) return;
    lastAsk.current = askParam;
    setInput(askParam);
    window.requestAnimationFrame(() => textareaRef.current?.focus());
  }, [askParam]);

  useEffect(() => {
    const node = textareaRef.current;
    if (!node) return;
    node.style.height = "0px";
    node.style.height = `${Math.min(node.scrollHeight, 160)}px`;
  }, [input]);

  useEffect(() => {
    const node = scrollRef.current;
    if (!node || !stickToBottom.current) return;
    node.scrollTop = node.scrollHeight;
  }, [thread]);

  useEffect(() => () => controllerRef.current?.abort(), []);

  const focusComposer = () => {
    window.requestAnimationFrame(() => textareaRef.current?.focus());
  };

  const startNewChat = () => {
    if (streaming) return;
    setConversationId(null);
    seededFor.current = null;
    lastParam.current = null;
    setThread([]);
    setStreamError(null);
    setHistoryOpen(false);
    setLocalTitle(null);
    router.replace(urlFor(null), { scroll: false });
    focusComposer();
  };

  const openConversation = (id: string) => {
    if (streaming || id === conversationId) {
      setHistoryOpen(false);
      return;
    }
    setConversationId(id);
    seededFor.current = null;
    lastParam.current = id;
    setThread([]);
    setStreamError(null);
    setHistoryOpen(false);
    setLocalTitle(null);
    router.replace(urlFor(id), { scroll: false });
  };

  const send = async (raw?: string) => {
    const question = (raw ?? input).trim();
    if (!question || streaming) return;

    setInput("");
    setStreamError(null);
    stickToBottom.current = true;
    if (!conversationId) {
      setLocalTitle(question.length > 80 ? `${question.slice(0, 79)}…` : question);
    }

    const controller = new AbortController();
    controllerRef.current = controller;
    let started = false;

    const stamp = Date.now();
    const userId = `local-user-${stamp}`;
    const assistantId = `local-assistant-${stamp}`;
    const now = new Date().toISOString();

    setThread((current) => [
      ...current,
      {
        id: userId,
        role: "user",
        content: question,
        citations: [],
        createdAt: now,
      },
      {
        id: assistantId,
        role: "assistant",
        content: "",
        citations: [],
        createdAt: now,
        streaming: true,
      },
    ]);
    setStreaming(true);

    let accumulated = "";
    let completed = false;

    const patch = (update: Partial<ChatThreadMessage>) => {
      setThread((current) =>
        current.map((message) =>
          message.id === assistantId ? { ...message, ...update } : message,
        ),
      );
    };

    try {
      await streamChat(
        projectId,
        {
          message: question,
          conversation_id: conversationId,
        },
        {
          onStart: (data) => {
            started = true;
            seededFor.current = data.conversation_id;
            lastParam.current = data.conversation_id;
            setConversationId(data.conversation_id);
            patch({ retrievedChunks: data.retrieved_chunks });
            router.replace(urlFor(data.conversation_id), { scroll: false });
          },
          onToken: (delta) => {
            accumulated += delta;
            patch({ content: accumulated });
          },
          onCitations: (citations) => {
            patch({ citations });
          },
          onDone: (response) => {
            completed = true;
            accumulated = response.answer;
            patch({
              content: response.answer,
              citations: response.citations,
              warnings: response.warnings,
              grounded: response.grounded,
              retrievedChunks: response.retrieved_chunks,
              streaming: false,
            });
          },
        },
        controller.signal,
      );

      if (!completed) {
        if (accumulated.trim()) {
          patch({ content: accumulated, streaming: false });
        } else {
          patch({
            streaming: false,
            error: "The stream ended before an answer arrived.",
          });
        }
      }
    } catch (error) {
      if (controller.signal.aborted) return;
      const message = errorMessage(
        error,
        "The answer could not be generated.",
      );
      if (!started) {
        setThread((current) =>
          current.filter(
            (message) => message.id !== userId && message.id !== assistantId,
          ),
        );
        setInput(question);
        setLocalTitle(null);
      }
      setStreamError(message);
      patch({ streaming: false, error: message });
    } finally {
      if (controllerRef.current === controller) controllerRef.current = null;
      setStreaming(false);
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      queryClient.invalidateQueries({ queryKey: ["conversation"] });
      focusComposer();
    }
  };

  const confirmDelete = () => {
    if (!deleting) return;
    const target = deleting;
    deleteConversation.mutate(target.id, {
      onSuccess: () => {
        toast({ title: "Conversation deleted", tone: "success" });
        setDeleting(null);
        if (target.id === conversationId) {
          startNewChat();
        }
      },
      onError: (error) =>
        toast({
          title: "Could not delete conversation",
          description: errorMessage(error),
          tone: "error",
        }),
    });
  };

  const onScroll = () => {
    const node = scrollRef.current;
    if (!node) return;
    const distance = node.scrollHeight - node.scrollTop - node.clientHeight;
    stickToBottom.current = distance < 120;
  };

  const showEmptyState =
    !conversation.isLoading && thread.length === 0 && !streaming;

  return (
    <div className="overflow-hidden rounded-2xl border border-line bg-surface/60">
      <div className="grid h-[calc(100dvh-18rem)] min-h-[600px] lg:grid-cols-[250px_minmax(0,1fr)]">
        <aside className="hidden min-h-0 border-r border-line/70 bg-canvas/30 lg:block">
          <ConversationPanel
            conversations={conversations.data?.items ?? []}
            activeId={conversationId}
            loading={conversations.isLoading}
            onNew={startNewChat}
            onSelect={openConversation}
            onDelete={setDeleting}
          />
        </aside>

        <div className="flex min-h-0 min-w-0 flex-col">
          <header className="flex items-center justify-between gap-3 border-b border-line/70 px-4 py-3">
            <div className="flex min-w-0 items-center gap-2.5">
              <button
                type="button"
                onClick={() => setHistoryOpen(true)}
                className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-line text-muted transition-colors hover:bg-surface-2 hover:text-parchment lg:hidden"
                aria-label="Open conversation history"
              >
                <History className="h-3.5 w-3.5" />
              </button>
              <RikaMark className="hidden h-6 w-6 sm:block" />
              <div className="min-w-0">
                <p className="truncate text-xs font-medium text-parchment">
                  {title}
                </p>
                <p className="mt-0.5 text-[9px] text-faint">
                  {conversation.data
                    ? pluralize(conversation.data.messages.length, "message")
                    : "Grounded in this project's indexed files"}
                </p>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-1.5">
              <Badge tone="sage" mono className="hidden sm:inline-flex">
                local
              </Badge>
              <Button
                size="sm"
                variant="ghost"
                onClick={startNewChat}
                disabled={streaming}
                icon={<SquarePen className="h-3.5 w-3.5" />}
                className="hidden sm:inline-flex"
              >
                New
              </Button>
            </div>
          </header>

          <div
            ref={scrollRef}
            onScroll={onScroll}
            className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6"
          >
            {conversation.isLoading && thread.length === 0 ? (
              <div className="mx-auto max-w-3xl space-y-6">
                <Skeleton className="ml-auto h-14 w-2/3" />
                <div className="flex gap-3">
                  <Skeleton className="h-7 w-7 rounded-full" />
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-3 w-1/3" />
                    <Skeleton className="h-24 w-full" />
                  </div>
                </div>
              </div>
            ) : conversation.isError && thread.length === 0 ? (
              <div className="mx-auto max-w-xl rounded-2xl border border-rose/25 bg-rose/5 px-5 py-4 text-center">
                <AlertCircle className="mx-auto h-5 w-5 text-rose" />
                <p className="mt-2 text-sm font-medium text-parchment">
                  This conversation could not be loaded.
                </p>
                <p className="mt-1 text-[11px] leading-relaxed text-muted">
                  {errorMessage(conversation.error)}
                </p>
                <Button
                  size="sm"
                  className="mt-3"
                  onClick={startNewChat}
                  icon={<SquarePen className="h-3.5 w-3.5" />}
                >
                  Start a new conversation
                </Button>
              </div>
            ) : showEmptyState ? (
              <div className="mx-auto flex h-full max-w-2xl flex-col items-center justify-center text-center">
                <RikaMark className="h-14 w-14" />
                <p className="mt-4 font-mono text-[9px] uppercase tracking-[0.22em] text-copper">
                  Ask this project
                </p>
                <h2 className="mt-2 font-serif text-3xl tracking-[-0.03em] text-parchment">
                  Evidence first,
                  <br />
                  then an answer.
                </h2>
                <p className="mt-3 max-w-md text-xs leading-relaxed text-muted">
                  Rika retrieves passages from this project&apos;s index,
                  answers from them and cites every source. If the evidence is
                  not there, it says so instead of guessing.
                </p>
                <div className="mt-6 grid w-full gap-2 sm:grid-cols-2">
                  {SUGGESTIONS.map((suggestion) => (
                    <button
                      key={suggestion}
                      type="button"
                      onClick={() => send(suggestion)}
                      className="rounded-xl border border-line bg-canvas/40 px-3.5 py-3 text-left text-[11px] leading-relaxed text-muted transition-colors hover:border-copper/30 hover:bg-surface-2/60 hover:text-parchment"
                    >
                      <Sparkles className="mb-1.5 h-3 w-3 text-copper" />
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="mx-auto max-w-3xl space-y-7">
                {thread.map((message) => (
                  <ChatMessageView
                    key={message.id}
                    message={message}
                    onOpenCitation={setViewing}
                  />
                ))}
              </div>
            )}
          </div>

          {streamError ? (
            <div className="mx-4 mb-1 flex items-start gap-2 rounded-xl border border-rose/25 bg-rose/5 px-3 py-2 text-[10px] leading-relaxed text-rose sm:mx-6">
              <AlertCircle className="mt-0.5 h-3 w-3 shrink-0" />
              <span className="flex-1">{streamError}</span>
              <button
                type="button"
                onClick={() => setStreamError(null)}
                className="rounded p-0.5 hover:bg-rose/10"
                aria-label="Dismiss error"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          ) : null}

          <div className="border-t border-line/70 bg-canvas/30 p-3 sm:p-4">
            <div className="mx-auto max-w-3xl">
              <div className="flex items-end gap-2 rounded-2xl border border-line bg-canvas/70 p-1.5 transition-colors focus-within:border-copper/40">
                <textarea
                  ref={textareaRef}
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      send();
                    }
                  }}
                  rows={1}
                  maxLength={8000}
                  placeholder={
                    streaming
                      ? "Rika is answering…"
                      : "Ask about this project — cite the source if you can."
                  }
                  disabled={streaming}
                  aria-label="Question for Rika"
                  className="max-h-40 min-h-9 flex-1 resize-none bg-transparent px-2.5 py-2 text-[13px] leading-relaxed text-parchment placeholder:text-faint focus:outline-none disabled:opacity-60"
                />
                <Button
                  size="icon"
                  variant="primary"
                  className="h-9 w-9 shrink-0 rounded-xl"
                  onClick={() => send()}
                  disabled={!input.trim() || streaming}
                  aria-label="Send question"
                >
                  {streaming ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <ArrowUp className="h-4 w-4" />
                  )}
                </Button>
              </div>
              <div className="mt-1.5 flex items-center justify-between gap-3 px-1 text-[9px] text-faint">
                <span>Enter to send · Shift+Enter for a new line</span>
                <span className="hidden sm:inline">
                  Open a citation to verify the exact lines.
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {historyOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="absolute inset-0 bg-black/70 backdrop-blur-sm"
            onClick={() => setHistoryOpen(false)}
            aria-hidden="true"
          />
          <aside className="relative h-full w-[300px] border-r border-line bg-canvas shadow-2xl animate-[fade-in_150ms_ease-out]">
            <div className="flex items-center justify-between border-b border-line/70 px-4 py-3">
              <span className="text-xs font-medium text-parchment">
                Conversation history
              </span>
              <button
                type="button"
                onClick={() => setHistoryOpen(false)}
                className="rounded-lg p-1.5 text-faint hover:bg-surface-2 hover:text-parchment"
                aria-label="Close history"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="h-[calc(100%-3.25rem)]">
              <ConversationPanel
                conversations={conversations.data?.items ?? []}
                activeId={conversationId}
                loading={conversations.isLoading}
                onNew={startNewChat}
                onSelect={openConversation}
                onDelete={setDeleting}
              />
            </div>
          </aside>
        </div>
      ) : null}

      <SourceViewer
        open={Boolean(viewing)}
        onClose={() => setViewing(null)}
        documentId={viewing?.document_id}
        projectId={projectId}
        highlight={
          viewing
            ? {
                startLine: viewing.start_line,
                endLine: viewing.end_line,
                pageNumber: viewing.page_number,
              }
            : undefined
        }
      />

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

function ChatFallback() {
  return (
    <div className="grid min-h-[600px] gap-5 rounded-2xl border border-line bg-surface/60 p-5 lg:grid-cols-[250px_minmax(0,1fr)]">
      <div className="hidden space-y-3 border-r border-line/70 pr-5 lg:block">
        <Skeleton className="h-9 w-full" />
        {[0, 1, 2, 3].map((index) => (
          <Skeleton key={index} className="h-12 w-full" />
        ))}
      </div>
      <div className="flex flex-col justify-between gap-6">
        <div className="flex items-center gap-2 text-xs text-muted">
          <Loader2 className="h-4 w-4 animate-spin text-copper" />
          Loading conversation…
        </div>
        <Skeleton className="h-20 w-full" />
      </div>
    </div>
  );
}

export default function ChatPage() {
  return (
    <Suspense fallback={<ChatFallback />}>
      <ChatContent />
    </Suspense>
  );
}
