"use client";

import {
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import * as api from "@/lib/api";
import type {
  ChatRequest,
  Document,
  Job,
  Project,
  SearchRequest,
  UploadResult,
  UUID,
} from "@/lib/types";
import { isActiveJob } from "@/lib/utils";

export const keys = {
  projects: (params?: object) => ["projects", params ?? {}] as const,
  project: (id: UUID) => ["project", id] as const,
  documents: (id: UUID) => ["documents", id] as const,
  jobs: (id: UUID) => ["jobs", id] as const,
  conversations: (projectId?: UUID) => ["conversations", projectId ?? "all"] as const,
  conversation: (id: UUID, projectId?: UUID) =>
    ["conversation", id, projectId ?? "all"] as const,
  preview: (documentId: UUID, projectId?: UUID) =>
    ["preview", documentId, projectId ?? "all"] as const,
  readiness: ["readiness"] as const,
  settings: ["settings"] as const,
};

export function useProjects(params: { limit?: number; offset?: number } = {}) {
  return useQuery({
    queryKey: keys.projects(params),
    queryFn: () => api.listProjects(params),
  });
}

export function useProject(projectId: UUID | undefined) {
  return useQuery({
    queryKey: keys.project(projectId ?? ""),
    queryFn: () => api.getProject(projectId as UUID),
    enabled: Boolean(projectId),
  });
}

function invalidateProject(
  queryClient: ReturnType<typeof useQueryClient>,
  projectId?: UUID,
) {
  queryClient.invalidateQueries({ queryKey: ["projects"] });
  if (projectId) {
    queryClient.invalidateQueries({ queryKey: keys.project(projectId) });
    queryClient.invalidateQueries({ queryKey: keys.documents(projectId) });
    queryClient.invalidateQueries({ queryKey: keys.jobs(projectId) });
  }
}

export function useCreateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.createProject,
    onSuccess: (project) => {
      queryClient.setQueryData<Project>(keys.project(project.id), project);
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

export function useUpdateProject(projectId: UUID) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { name?: string; description?: string | null }) =>
      api.updateProject(projectId, payload),
    onSuccess: (project) => {
      queryClient.setQueryData(keys.project(projectId), project);
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

export function useDeleteProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.deleteProject,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["projects"] }),
  });
}

export function useDocuments(projectId: UUID | undefined, limit = 200) {
  return useQuery({
    queryKey: [...keys.documents(projectId ?? ""), limit],
    queryFn: () => api.listDocuments(projectId as UUID, { limit }),
    enabled: Boolean(projectId),
    refetchInterval: (query) => {
      const documents = query.state.data?.items ?? [];
      return documents.some(
        (document) =>
          document.status === "pending" || document.status === "processing",
      )
        ? 3000
        : false;
    },
  });
}

/**
 * Read every document, page by page.
 *
 * The API caps a page at 200; a file explorer must not silently hide the rest
 * of a large import, so this follows ``total`` until the list is complete.
 */
export function useAllDocuments(projectId: UUID | undefined) {
  return useQuery({
    queryKey: [...keys.documents(projectId ?? ""), "all"],
    queryFn: async () => {
      const first = await api.listDocuments(projectId as UUID, {
        limit: 200,
        offset: 0,
      });
      const items = [...first.items];
      for (let offset = first.items.length; offset < first.total; offset += 200) {
        const page = await api.listDocuments(projectId as UUID, {
          limit: 200,
          offset,
        });
        if (page.items.length === 0) break;
        items.push(...page.items);
      }
      return { items, total: first.total };
    },
    enabled: Boolean(projectId),
    refetchInterval: (query) => {
      const documents = query.state.data?.items ?? [];
      return documents.some(
        (document) =>
          document.status === "pending" || document.status === "processing",
      )
        ? 3000
        : false;
    },
  });
}

export function useJobs(projectId: UUID | undefined, limit = 50) {
  return useQuery({
    queryKey: [...keys.jobs(projectId ?? ""), limit],
    queryFn: () => api.listJobs(projectId as UUID, { limit }),
    enabled: Boolean(projectId),
    refetchInterval: (query) => {
      const jobs = query.state.data?.items ?? [];
      return jobs.some(isActiveJob) ? 2500 : false;
    },
  });
}

export function useRetryJob(projectId: UUID) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.retryJob,
    onSuccess: () => invalidateProject(queryClient, projectId),
  });
}

/**
 * Merge the newest jobs from several projects.
 *
 * The API lists jobs per project, so the dashboard reads a small window from
 * each project it shows instead of inventing an aggregate endpoint.
 */
export function useJobsForProjects(projectIds: UUID[], limit = 6) {
  return useQueries({
    queries: projectIds.map((projectId) => ({
      queryKey: [...keys.jobs(projectId), 6] as const,
      queryFn: () => api.listJobs(projectId, { limit: 6 }),
      enabled: Boolean(projectId),
    })),
    combine: (results) => ({
      jobs: results
        .flatMap((result) => result.data?.items ?? [])
        .sort(
          (left, right) =>
            new Date(right.created_at).getTime() -
            new Date(left.created_at).getTime(),
        )
        .slice(0, limit),
      isLoading: results.some((result) => result.isLoading),
    }),
  });
}

function useUploadMutation<TArgs>(
  projectId: UUID,
  mutationFn: (args: TArgs) => Promise<UploadResult>,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: () => invalidateProject(queryClient, projectId),
  });
}

export function useUploadFiles(projectId: UUID) {
  return useUploadMutation<File[]>(projectId, (files) => api.uploadFiles(projectId, files));
}

export function useUploadFolder(projectId: UUID) {
  return useUploadMutation<Array<{ file: File; path: string }>>(
    projectId,
    (entries) => api.uploadFolder(projectId, entries),
  );
}

export function useUploadZip(projectId: UUID) {
  return useUploadMutation<File>(projectId, (file) => api.uploadZip(projectId, file));
}

export function useDeleteDocument(projectId: UUID) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.deleteDocument,
    onSuccess: () => invalidateProject(queryClient, projectId),
  });
}

export function useReindexDocument(projectId: UUID) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.reindexDocument,
    onSuccess: () => invalidateProject(queryClient, projectId),
  });
}

export function useSearchProject(projectId: UUID) {
  return useMutation({
    mutationFn: (payload: SearchRequest) => api.searchProject(projectId, payload),
  });
}

export function useConversations(projectId?: UUID, limit = 50) {
  return useQuery({
    queryKey: [...keys.conversations(projectId), limit],
    queryFn: () => api.listConversations({ project_id: projectId, limit }),
    placeholderData: (previous) => previous,
  });
}

export function useConversation(
  conversationId: UUID | undefined,
  projectId?: UUID,
) {
  return useQuery({
    queryKey: keys.conversation(conversationId ?? "", projectId),
    queryFn: () => api.getConversation(conversationId as UUID, projectId),
    enabled: Boolean(conversationId),
  });
}

export function useDeleteConversation(projectId?: UUID) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (conversationId: UUID) =>
      api.deleteConversation(conversationId, projectId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      queryClient.invalidateQueries({ queryKey: ["conversation"] });
    },
  });
}

export function useDocumentPreview(
  documentId: UUID | undefined,
  projectId?: UUID,
  enabled = true,
) {
  return useQuery({
    queryKey: keys.preview(documentId ?? "", projectId),
    queryFn: ({ signal }) =>
      api.previewDocument(documentId as UUID, projectId, signal),
    enabled: Boolean(documentId) && enabled,
  });
}

export function useReadiness() {
  return useQuery({
    queryKey: keys.readiness,
    queryFn: api.getReadiness,
    refetchInterval: 30_000,
    retry: false,
  });
}

export function useSettings() {
  return useQuery({
    queryKey: keys.settings,
    queryFn: api.getSettings,
    staleTime: 60_000,
  });
}

export function useChatMutation(projectId: UUID) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ChatRequest) => api.chat(projectId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      queryClient.invalidateQueries({ queryKey: ["conversation"] });
    },
  });
}

export type { Document, Job };
