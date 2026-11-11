import type {
  ApiErrorBody,
  ChatRequest,
  ChatResponse,
  Citation,
  ConversationDetail,
  ConversationList,
  Document,
  DocumentList,
  DocumentPreview,
  Job,
  JobList,
  Project,
  ProjectList,
  Readiness,
  RuntimeSettings,
  SearchRequest,
  SearchResponse,
  UploadResult,
  UUID,
} from "@/lib/types";

export const API_BASE = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000"
).replace(/\/+$/, "");

export class ApiError extends Error {
  status: number;
  code: string;
  details?: Record<string, unknown>;

  constructor(
    message: string,
    status: number,
    code = "http_error",
    details?: Record<string, unknown>,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function parseError(response: Response): Promise<ApiError> {
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  const error = (payload as ApiErrorBody | null)?.error;
  return new ApiError(
    error?.message ?? `The request failed (${response.status}).`,
    response.status,
    error?.code ?? "http_error",
    error?.details,
  );
}

interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, headers, ...rest } = options;
  const isForm = body instanceof FormData;
  const response = await fetch(`${API_BASE}${path}`, {
    ...rest,
    cache: "no-store",
    headers: {
      Accept: "application/json",
      ...(isForm || body === undefined ? {} : { "Content-Type": "application/json" }),
      ...headers,
    },
    body:
      body === undefined
        ? undefined
        : isForm
          ? body
          : JSON.stringify(body),
  });

  if (!response.ok) throw await parseError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function query(params: Record<string, string | number | undefined | null>) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const serialized = search.toString();
  return serialized ? `?${serialized}` : "";
}

// -- projects ---------------------------------------------------------------
export const listProjects = (params: { limit?: number; offset?: number } = {}) =>
  request<ProjectList>(`/api/v1/projects${query(params)}`);

export const getProject = (projectId: UUID) =>
  request<Project>(`/api/v1/projects/${projectId}`);

export const createProject = (payload: { name: string; description?: string | null }) =>
  request<Project>("/api/v1/projects", { method: "POST", body: payload });

export const updateProject = (
  projectId: UUID,
  payload: { name?: string; description?: string | null },
) =>
  request<Project>(`/api/v1/projects/${projectId}`, {
    method: "PATCH",
    body: payload,
  });

export const deleteProject = (projectId: UUID) =>
  request<void>(`/api/v1/projects/${projectId}`, { method: "DELETE" });

// -- documents --------------------------------------------------------------
export const listDocuments = (
  projectId: UUID,
  params: { limit?: number; offset?: number } = {},
) =>
  request<DocumentList>(
    `/api/v1/projects/${projectId}/documents${query(params)}`,
  );

export const getDocument = (documentId: UUID) =>
  request<Document>(`/api/v1/documents/${documentId}`);

export const previewDocument = (
  documentId: UUID,
  projectId?: UUID,
  signal?: AbortSignal,
) =>
  request<DocumentPreview>(
    `/api/v1/documents/${documentId}/preview${query({ project_id: projectId })}`,
    { signal },
  );

export const deleteDocument = (documentId: UUID) =>
  request<void>(`/api/v1/documents/${documentId}`, { method: "DELETE" });

export const reindexDocument = (documentId: UUID) =>
  request<Job>(`/api/v1/documents/${documentId}/reindex`, { method: "POST" });

// -- jobs -------------------------------------------------------------------
export const listJobs = (
  projectId: UUID,
  params: { limit?: number; offset?: number } = {},
) =>
  request<JobList>(`/api/v1/projects/${projectId}/jobs${query(params)}`);

export const getJob = (jobId: UUID) => request<Job>(`/api/v1/jobs/${jobId}`);

export const retryJob = (jobId: UUID) =>
  request<Job>(`/api/v1/jobs/${jobId}/retry`, { method: "POST" });

// -- uploads ----------------------------------------------------------------
export async function uploadFiles(projectId: UUID, files: File[]) {
  const form = new FormData();
  for (const file of files) form.append("files", file);
  return request<UploadResult>(`/api/v1/projects/${projectId}/upload`, {
    method: "POST",
    body: form,
  });
}

export async function uploadFolder(
  projectId: UUID,
  entries: Array<{ file: File; path: string }>,
) {
  const form = new FormData();
  for (const entry of entries) {
    form.append("files", entry.file);
    form.append("paths", entry.path);
  }
  return request<UploadResult>(`/api/v1/projects/${projectId}/upload-folder`, {
    method: "POST",
    body: form,
  });
}

export async function uploadZip(projectId: UUID, file: File) {
  const form = new FormData();
  form.append("file", file);
  return request<UploadResult>(`/api/v1/projects/${projectId}/upload-zip`, {
    method: "POST",
    body: form,
  });
}

// -- search -----------------------------------------------------------------
export const searchProject = (projectId: UUID, payload: SearchRequest) =>
  request<SearchResponse>(`/api/v1/projects/${projectId}/search`, {
    method: "POST",
    body: payload,
  });

// -- chat -------------------------------------------------------------------
export const chat = (projectId: UUID, payload: ChatRequest) =>
  request<ChatResponse>(`/api/v1/projects/${projectId}/chat`, {
    method: "POST",
    body: { ...payload, stream: false },
  });

export interface ChatStreamHandlers {
  onStart?: (data: {
    project_id: UUID;
    conversation_id: UUID;
    retrieved_chunks: number;
  }) => void;
  onToken?: (delta: string) => void;
  onCitations?: (citations: Citation[]) => void;
  onDone?: (response: ChatResponse) => void;
}

interface SseBlock {
  event: string;
  data: string;
}

function parseSseBlock(block: string): SseBlock | null {
  let event = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      data.push(line.slice(5).replace(/^ /, ""));
    }
  }
  if (data.length === 0) return null;
  return { event, data: data.join("\n") };
}

export async function streamChat(
  projectId: UUID,
  payload: ChatRequest,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
): Promise<ChatResponse | null> {
  const response = await fetch(`${API_BASE}/api/v1/projects/${projectId}/chat`, {
    method: "POST",
    cache: "no-store",
    headers: {
      Accept: "text/event-stream",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ ...payload, stream: true }),
    signal,
  });

  if (!response.ok) throw await parseError(response);
  if (!response.body) {
    throw new ApiError("The answer stream could not be opened.", 502, "stream_error");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let completed: ChatResponse | null = null;

  const consume = (block: string) => {
    const parsed = parseSseBlock(block);
    if (!parsed) return;
    let data: unknown;
    try {
      data = JSON.parse(parsed.data);
    } catch {
      return;
    }

    if (parsed.event === "start") {
      handlers.onStart?.(data as Parameters<NonNullable<typeof handlers.onStart>>[0]);
    } else if (parsed.event === "token") {
      const delta = (data as { delta?: unknown }).delta;
      if (typeof delta === "string") handlers.onToken?.(delta);
    } else if (parsed.event === "citations") {
      const citations = (data as { citations?: Citation[] }).citations;
      if (Array.isArray(citations)) handlers.onCitations?.(citations);
    } else if (parsed.event === "done") {
      completed = data as ChatResponse;
      handlers.onDone?.(completed);
    } else if (parsed.event === "error") {
      const error = data as { code?: string; message?: string };
      throw new ApiError(
        error.message ?? "The answer could not be generated.",
        502,
        error.code ?? "chat_error",
      );
    }
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      consume(block);
      boundary = buffer.indexOf("\n\n");
    }
  }

  if (buffer.trim()) consume(buffer);
  return completed;
}

// -- conversations ----------------------------------------------------------
export const listConversations = (
  params: { project_id?: UUID; limit?: number; offset?: number } = {},
) => request<ConversationList>(`/api/v1/conversations${query(params)}`);

export const getConversation = (conversationId: UUID, projectId?: UUID) =>
  request<ConversationDetail>(
    `/api/v1/conversations/${conversationId}${query({ project_id: projectId })}`,
  );

export const deleteConversation = (conversationId: UUID, projectId?: UUID) =>
  request<void>(
    `/api/v1/conversations/${conversationId}${query({ project_id: projectId })}`,
    { method: "DELETE" },
  );

// -- system -----------------------------------------------------------------
export async function getReadiness(): Promise<Readiness> {
  const response = await fetch(`${API_BASE}/health/ready`, {
    cache: "no-store",
    headers: { Accept: "application/json" },
  });
  if (response.status === 200 || response.status === 503) {
    return (await response.json()) as Readiness;
  }
  throw await parseError(response);
}

export const getSettings = () => request<RuntimeSettings>("/api/v1/settings");
