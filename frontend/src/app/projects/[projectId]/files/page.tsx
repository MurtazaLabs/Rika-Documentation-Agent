"use client";

import { Suspense, useEffect, useMemo, useRef, useState, type DragEvent } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import {
  AlertCircle,
  ClipboardPaste,
  FileArchive,
  FolderUp,
  Loader2,
  RefreshCw,
  UploadCloud,
  Waypoints,
} from "lucide-react";

import { WorkerWarning } from "@/components/projects/worker-warning";
import { SourceViewer } from "@/components/source-viewer";
import { FileExplorer } from "@/components/workspace/file-explorer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { ProgressBar } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import {
  useAllDocuments,
  useDeleteDocument,
  useJobs,
  useReindexDocument,
  useRetryJob,
  useUploadFiles,
  useUploadFolder,
  useUploadZip,
} from "@/hooks/use-api";
import type { Document, Job, UploadResult } from "@/lib/types";
import {
  errorMessage,
  isActiveJob,
  pluralize,
  relativeTime,
  statusTone,
} from "@/lib/utils";

function uploadSummary(result: UploadResult) {
  const added = result.items.filter((item) => !item.duplicate).length;
  const duplicates = result.items.filter((item) => item.duplicate).length;
  const parts: string[] = [];
  if (duplicates > 0) parts.push(`${pluralize(duplicates, "duplicate")} ignored`);
  if (result.skipped.length > 0) {
    parts.push(`${pluralize(result.skipped.length, "unsupported entry", "unsupported entries")} skipped`);
  }
  if (result.jobs.length > 0) {
    parts.push(`${pluralize(result.jobs.length, "indexing job")} queued`);
  }
  return {
    title:
      added > 0
        ? `${pluralize(added, "file")} added`
        : "Nothing new to add",
    description: parts.join(" · ") || "The upload completed.",
  };
}

function IndexingPanel({
  projectId,
  jobs,
  documents,
}: {
  projectId: string;
  jobs: Job[];
  documents: Document[];
}) {
  const retry = useRetryJob(projectId);
  const { toast } = useToast();
  const documentById = useMemo(
    () => new Map(documents.map((document) => [document.id, document])),
    [documents],
  );
  const sorted = useMemo(
    () =>
      [...jobs].sort(
        (left, right) =>
          new Date(right.created_at).getTime() -
          new Date(left.created_at).getTime(),
      ),
    [jobs],
  );
  const active = sorted.filter(isActiveJob);

  const retryJob = (job: Job) => {
    retry.mutate(job.id, {
      onSuccess: () =>
        toast({ title: "Job re-queued", tone: "success" }),
      onError: (error) =>
        toast({
          title: "Could not retry job",
          description: errorMessage(error),
          tone: "error",
        }),
    });
  };

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Indexing</CardTitle>
          <p className="mt-1 text-[11px] text-muted">
            {active.length > 0
              ? `${pluralize(active.length, "job")} running`
              : "Queue is idle"}
          </p>
        </div>
        <Badge tone={active.length > 0 ? "gold" : "neutral"} mono>
          {active.length > 0 ? "working" : "idle"}
        </Badge>
      </CardHeader>
      <CardContent className="p-3">
        {sorted.length === 0 ? (
          <p className="px-2 py-6 text-center text-[11px] leading-relaxed text-muted">
            Upload a file and its parsing, chunking and embedding jobs will
            appear here.
          </p>
        ) : (
          <ul className="max-h-[42vh] space-y-1 overflow-y-auto">
            {sorted.slice(0, 12).map((job) => {
              const document = job.document_id
                ? documentById.get(job.document_id)
                : undefined;
              return (
                <li
                  key={job.id}
                  className="rounded-lg border border-line/60 bg-canvas/30 px-3 py-2.5"
                >
                  <div className="flex items-center gap-2">
                    <Waypoints className="h-3 w-3 shrink-0 text-faint" />
                    <p className="min-w-0 flex-1 truncate text-[11px] text-parchment">
                      {document?.original_path ??
                        `${job.job_type} job`}
                    </p>
                    <Badge tone={statusTone(job.status)}>{job.status}</Badge>
                  </div>
                  {isActiveJob(job) ? (
                    <ProgressBar value={job.progress} className="mt-2" />
                  ) : null}
                  <div className="mt-1.5 flex items-center justify-between gap-2">
                    <p className="min-w-0 truncate text-[9px] text-faint">
                      {relativeTime(job.created_at)}
                      {job.error_message ? ` · ${job.error_message}` : ""}
                    </p>
                    {job.status === "failed" ? (
                      <button
                        type="button"
                        onClick={() => retryJob(job)}
                        disabled={retry.isPending}
                        className="inline-flex shrink-0 items-center gap-1 text-[10px] text-copper hover:underline disabled:opacity-50"
                      >
                        <RefreshCw className="h-3 w-3" />
                        Retry
                      </button>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function FilesContent() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();
  const documents = useAllDocuments(projectId);
  const jobs = useJobs(projectId, 100);
  const uploadFiles = useUploadFiles(projectId);
  const uploadFolder = useUploadFolder(projectId);
  const uploadZip = useUploadZip(projectId);
  const deleteDocument = useDeleteDocument(projectId);
  const reindexDocument = useReindexDocument(projectId);

  const [filter, setFilter] = useState("");
  const [preview, setPreview] = useState<Document | null>(null);
  const [deleting, setDeleting] = useState<Document | null>(null);
  const [dragging, setDragging] = useState(false);
  const dragDepth = useRef(0);
  const filesInput = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement>(null);
  const zipInput = useRef<HTMLInputElement>(null);
  const openedFromLink = useRef(false);

  const documentItems = documents.data?.items ?? [];
  const jobItems = jobs.data?.items ?? [];

  useEffect(() => {
    folderInput.current?.setAttribute("webkitdirectory", "");
    folderInput.current?.setAttribute("directory", "");
  }, []);

  useEffect(() => {
    const requested = searchParams.get("document");
    if (!requested || openedFromLink.current || documents.isLoading) return;
    const match = documentItems.find((document) => document.id === requested);
    if (match) {
      openedFromLink.current = true;
      setPreview(match);
    }
  }, [documentItems, documents.isLoading, searchParams]);

  const jobsByDocument = useMemo(() => {
    const map = new Map<string, Job>();
    for (const job of jobItems) {
      if (!job.document_id) continue;
      const current = map.get(job.document_id);
      if (
        !current ||
        new Date(job.created_at).getTime() >
          new Date(current.created_at).getTime()
      ) {
        map.set(job.document_id, job);
      }
    }
    return map;
  }, [jobItems]);

  const uploading =
    uploadFiles.isPending || uploadFolder.isPending || uploadZip.isPending;

  const notifyResult = (result: UploadResult) => {
    const summary = uploadSummary(result);
    toast({
      ...summary,
      tone: "success",
    });
  };

  const sendFiles = (files: File[]) => {
    if (files.length === 0) return;
    if (files.length === 1 && files[0].name.toLowerCase().endsWith(".zip")) {
      uploadZip.mutate(files[0], {
        onSuccess: notifyResult,
        onError: (error) =>
          toast({
            title: "Upload failed",
            description: errorMessage(error),
            tone: "error",
          }),
      });
      return;
    }
    uploadFiles.mutate(files, {
      onSuccess: notifyResult,
      onError: (error) =>
        toast({
          title: "Upload failed",
          description: errorMessage(error),
          tone: "error",
        }),
    });
  };

  useEffect(() => {
    const onPaste = (event: ClipboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target?.closest("input, textarea, [contenteditable='true']")) return;
      const files = Array.from(event.clipboardData?.files ?? []);
      if (files.length === 0) return;
      event.preventDefault();
      sendFiles(files);
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
    // sendFiles closes over the current mutations; that is fine for a page-local listener.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    dragDepth.current = 0;
    setDragging(false);
    sendFiles(Array.from(event.dataTransfer.files));
  };

  const openPreview = (document: Document) => {
    setPreview(document);
    if (searchParams.get("document")) {
      router.replace(`/projects/${projectId}/files`);
    }
  };

  const closePreview = () => {
    setPreview(null);
    if (searchParams.get("document")) {
      router.replace(`/projects/${projectId}/files`);
    }
  };

  const confirmDelete = () => {
    if (!deleting) return;
    deleteDocument.mutate(deleting.id, {
      onSuccess: () => {
        toast({
          title: "Document deleted",
          description: deleting.original_path,
          tone: "success",
        });
        if (preview?.id === deleting.id) setPreview(null);
        setDeleting(null);
      },
      onError: (error) =>
        toast({
          title: "Could not delete document",
          description: errorMessage(error),
          tone: "error",
        }),
    });
  };

  const reindex = (document: Document) => {
    reindexDocument.mutate(document.id, {
      onSuccess: () => {
        toast({
          title: "Reindex queued",
          description: document.original_path,
          tone: "success",
        });
      },
      onError: (error) =>
        toast({
          title: "Could not reindex",
          description: errorMessage(error),
          tone: "error",
        }),
    });
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-col justify-between gap-3 md:flex-row md:items-end">
        <div>
          <h2 className="font-serif text-2xl tracking-[-0.02em] text-parchment">
            Files
          </h2>
          <p className="mt-1 text-[12px] leading-relaxed text-muted">
            Upload files, folders or ZIP archives. Parsing and embeddings run
            locally; nothing is executed.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input
            ref={filesInput}
            type="file"
            multiple
            className="hidden"
            onChange={(event) => {
              sendFiles(Array.from(event.target.files ?? []));
              event.target.value = "";
            }}
          />
          <input
            ref={folderInput}
            type="file"
            multiple
            className="hidden"
            onChange={(event) => {
              const entries = Array.from(event.target.files ?? []).map(
                (file) => ({
                  file,
                  path: file.webkitRelativePath || file.name,
                }),
              );
              if (entries.length > 0) {
                uploadFolder.mutate(entries, {
                  onSuccess: notifyResult,
                  onError: (error) =>
                    toast({
                      title: "Folder upload failed",
                      description: errorMessage(error),
                      tone: "error",
                    }),
                });
              }
              event.target.value = "";
            }}
          />
          <input
            ref={zipInput}
            type="file"
            accept=".zip,application/zip"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) {
                uploadZip.mutate(file, {
                  onSuccess: notifyResult,
                  onError: (error) =>
                    toast({
                      title: "Archive upload failed",
                      description: errorMessage(error),
                      tone: "error",
                    }),
                });
              }
              event.target.value = "";
            }}
          />
          <Button
            variant="primary"
            size="sm"
            onClick={() => filesInput.current?.click()}
            loading={uploadFiles.isPending}
            icon={<UploadCloud className="h-3.5 w-3.5" />}
          >
            Upload files
          </Button>
          <Button
            size="sm"
            onClick={() => folderInput.current?.click()}
            loading={uploadFolder.isPending}
            icon={<FolderUp className="h-3.5 w-3.5" />}
          >
            Folder
          </Button>
          <Button
            size="sm"
            onClick={() => zipInput.current?.click()}
            loading={uploadZip.isPending}
            icon={<FileArchive className="h-3.5 w-3.5" />}
          >
            ZIP
          </Button>
        </div>
      </div>

      {uploading ? (
        <div className="flex items-center gap-3 rounded-xl border border-copper/25 bg-copper/5 px-4 py-3">
          <Loader2 className="h-4 w-4 animate-spin text-copper" />
          <div className="min-w-0 flex-1">
            <p className="text-[11px] font-medium text-parchment">
              Uploading and queueing files…
            </p>
            <p className="mt-0.5 text-[10px] text-faint">
              Large imports are validated first, then indexed in the background.
            </p>
          </div>
        </div>
      ) : null}

      {documents.isError ? (
        <EmptyState
          icon={<AlertCircle className="h-4 w-4" />}
          title="Could not load files"
          description={
            documents.error instanceof Error
              ? documents.error.message
              : "Check that the API is reachable."
          }
          action={<Button onClick={() => documents.refetch()}>Try again</Button>}
        />
      ) : (
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1.75fr)_minmax(280px,1fr)]">
          <div
            className="relative"
            onDragEnter={(event) => {
              event.preventDefault();
              dragDepth.current += 1;
              setDragging(true);
            }}
            onDragOver={(event) => event.preventDefault()}
            onDragLeave={(event) => {
              event.preventDefault();
              dragDepth.current = Math.max(0, dragDepth.current - 1);
              if (dragDepth.current === 0) setDragging(false);
            }}
            onDrop={onDrop}
          >
            <Card className="overflow-hidden">
              <div className="flex flex-col gap-2 border-b border-line/70 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-[11px] text-muted">
                  {documents.isLoading
                    ? "Loading files…"
                    : `${pluralize(documentItems.length, "file")} in this project`}
                </p>
                <p className="inline-flex items-center gap-1.5 text-[10px] text-faint">
                  <ClipboardPaste className="h-3 w-3" />
                  Drop files here or paste with Ctrl+V
                </p>
              </div>
              {documents.isLoading ? (
                <div className="space-y-2 p-4">
                  {[0, 1, 2, 3, 4].map((index) => (
                    <Skeleton key={index} className="h-9 w-full" />
                  ))}
                </div>
              ) : documentItems.length === 0 ? (
                <div className="p-4">
                  <EmptyState
                    icon={<UploadCloud className="h-4 w-4" />}
                    title="No files yet"
                    description="Upload source code, PDFs, Office files, Markdown, data files or a ZIP archive. Rika parses and embeds them locally."
                    action={
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => filesInput.current?.click()}
                        icon={<UploadCloud className="h-3.5 w-3.5" />}
                      >
                        Choose files
                      </Button>
                    }
                    className="border-0"
                  />
                </div>
              ) : (
                <FileExplorer
                  key={projectId}
                  documents={documentItems}
                  jobsByDocument={jobsByDocument}
                  filter={filter}
                  onFilterChange={setFilter}
                  onPreview={openPreview}
                  onDelete={setDeleting}
                  onReindex={reindex}
                />
              )}
            </Card>

            {dragging ? (
              <div className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center rounded-2xl border-2 border-dashed border-copper/70 bg-canvas/85 backdrop-blur-sm">
                <div className="text-center">
                  <UploadCloud className="mx-auto h-8 w-8 text-copper" />
                  <p className="mt-2 text-sm font-medium text-parchment">
                    Drop to upload
                  </p>
                  <p className="mt-1 text-[11px] text-muted">
                    A single .zip is treated as an archive; everything else is
                    uploaded as files.
                  </p>
                </div>
              </div>
            ) : null}
          </div>

          <div className="space-y-5">
            <WorkerWarning />
            <IndexingPanel
              projectId={projectId}
              jobs={jobItems}
              documents={documentItems}
            />
            <Card>
              <CardHeader>
                <CardTitle>How indexing works</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {[
                  ["Validate & store", "Paths, size and file type are checked before anything is written."],
                  ["Parse & chunk", "Documents and code are parsed, then split on natural boundaries."],
                  ["Embed & index", "Chunks are embedded locally and indexed for hybrid search."],
                ].map(([title, body], index) => (
                  <div key={title} className="flex gap-3">
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-line font-mono text-[9px] text-faint">
                      {index + 1}
                    </span>
                    <div>
                      <p className="text-[11px] font-medium text-parchment">
                        {title}
                      </p>
                      <p className="mt-0.5 text-[10px] leading-relaxed text-muted">
                        {body}
                      </p>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      <SourceViewer
        open={Boolean(preview)}
        onClose={closePreview}
        documentId={preview?.id}
        projectId={projectId}
      />

      <ConfirmDialog
        open={Boolean(deleting)}
        onClose={() => setDeleting(null)}
        onConfirm={confirmDelete}
        title="Delete this document?"
        description={
          deleting
            ? `“${deleting.original_path}” and its chunks, embeddings and jobs will be removed. This cannot be undone.`
            : ""
        }
        confirmLabel="Delete document"
        loading={deleteDocument.isPending}
      />
    </div>
  );
}

export default function FilesPage() {
  return (
    <Suspense
      fallback={
        <div className="space-y-4">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-96 w-full" />
        </div>
      }
    >
      <FilesContent />
    </Suspense>
  );
}
