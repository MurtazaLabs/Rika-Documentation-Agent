/** Shapes returned by the Rika FastAPI server. */

export type UUID = string;

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

export interface Project {
  id: UUID;
  name: string;
  description: string | null;
  settings: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ProjectList {
  items: Project[];
  total: number;
  limit: number;
  offset: number;
}

export interface Document {
  id: UUID;
  project_id: UUID;
  original_path: string;
  filename: string;
  file_type: string;
  content_hash: string;
  size: number;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface DocumentList {
  items: Document[];
  total: number;
  limit: number;
  offset: number;
}

export interface DocumentPreview {
  document_id: UUID;
  project_id: UUID;
  file_path: string;
  filename: string;
  file_type: string;
  language: string | null;
  source: "file" | "chunks" | "none";
  content: string;
  line_count: number | null;
  truncated: boolean;
  message: string | null;
}

export interface UploadedDocument {
  document: Document;
  duplicate: boolean;
}

export type JobType = "ingest" | "reindex" | "delete" | string;
export type JobStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled"
  | string;

export interface Job {
  id: UUID;
  project_id: UUID;
  document_id: UUID | null;
  job_type: JobType;
  status: JobStatus;
  progress: number;
  attempts: number;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface JobList {
  items: Job[];
  total: number;
  limit: number;
  offset: number;
}

export interface UploadResult {
  items: UploadedDocument[];
  jobs: Job[];
  skipped: string[];
}

export interface SearchFilters {
  file_path?: string | null;
  file_type?: string | null;
  language?: string | null;
  symbol_type?: string | null;
  directory?: string | null;
  document_type?: string | null;
}

export type SearchMode = "hybrid" | "vector" | "keyword";

export interface SearchRequest {
  query: string;
  mode?: SearchMode;
  limit?: number;
  filters?: SearchFilters;
}

export interface SearchResult {
  chunk_id: UUID;
  document_id: UUID;
  project_id: UUID;
  chunk_index: number;
  content: string;
  rank: number;
  score: number;
  vector_score: number | null;
  keyword_score: number | null;
  matched_by: Array<"vector" | "keyword">;
  file_path: string;
  filename: string;
  file_type: string;
  content_type: string;
  language: string | null;
  symbol_name: string | null;
  symbol_type: string | null;
  start_line: number | null;
  end_line: number | null;
  page_number: number | null;
  metadata: Record<string, unknown>;
}

export interface SearchResponse {
  query: string;
  mode: SearchMode;
  project_id: UUID;
  items: SearchResult[];
  total: number;
  limit: number;
}

export interface Citation {
  marker: string;
  chunk_id: UUID;
  document_id: UUID;
  file_path: string;
  filename: string;
  file_type: string;
  content_type: string;
  language: string | null;
  symbol_name: string | null;
  symbol_type: string | null;
  start_line: number | null;
  end_line: number | null;
  page_number: number | null;
  snippet: string;
  rank: number;
  retrieval_score: number;
}

export interface ChatRequest {
  message: string;
  conversation_id?: UUID | null;
  filters?: SearchFilters;
}

export interface ChatResponse {
  project_id: UUID;
  conversation_id: UUID;
  user_message_id: UUID;
  message_id: UUID;
  answer: string;
  citations: Citation[];
  warnings: string[];
  retrieved_chunks: number;
  grounded: boolean;
}

export interface ChatStartEvent {
  project_id: UUID;
  conversation_id: UUID;
  retrieved_chunks: number;
}

export type MessageRole = "user" | "assistant" | "system";

export interface ConversationMessage {
  id: UUID;
  role: MessageRole;
  content: string;
  citations: Citation[];
  created_at: string;
}

export interface ConversationSummary {
  id: UUID;
  project_id: UUID;
  title: string | null;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface ConversationList {
  items: ConversationSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface ConversationDetail {
  id: UUID;
  project_id: UUID;
  title: string | null;
  created_at: string;
  updated_at: string;
  messages: ConversationMessage[];
}

export interface DependencyCheck {
  name: string;
  status: "ok" | "error";
  critical: boolean;
  detail: string | null;
}

export interface Readiness {
  status: "ready" | "degraded" | "unavailable";
  app: string;
  version: string;
  environment: string;
  checks: DependencyCheck[];
}

export interface ModelServerSettings {
  base_url: string;
  model_name: string;
  timeout_seconds: number;
}

export interface ChatSettings extends ModelServerSettings {
  temperature: number;
  max_tokens: number;
  context_chunks: number;
  context_max_chars: number;
  history_max_chars: number;
  prompt_max_chars: number;
}

export interface EmbeddingSettings extends ModelServerSettings {
  dimension: number | null;
  batch_size: number;
}

export interface RuntimeSettings {
  app_name: string;
  environment: string;
  version: string;
  chat: ChatSettings;
  embedding: EmbeddingSettings;
  storage: {
    root: string;
    max_upload_mb: number;
    max_archive_files: number;
    max_archive_expanded_mb: number;
  };
  indexing: {
    chunk_size_chars: number;
    chunk_overlap_chars: number;
  };
  editable: boolean;
  source: string;
  restart_required: boolean;
}

// -- project intelligence (§13) ---------------------------------------------
export interface IntelligenceTotals {
  files: number;
  code_files: number;
  symbols: number;
  languages: number;
}

export interface LanguageStat {
  language: string;
  files: number;
  symbols: number;
  bytes: number;
}

export interface DirectoryStat {
  path: string;
  files: number;
  symbols: number;
  bytes: number;
}

export interface FrameworkHit {
  name: string;
  evidence: string[];
  files: number;
}

export interface EntryPoint {
  path: string;
  kind: string;
  detail: string | null;
}

export interface ConfigFile {
  path: string;
  kind: string;
}

export interface ImportantModule {
  path: string;
  layer: string;
  symbols: number;
  imported_by: number;
  score: number;
}

export interface PackageUsage {
  name: string;
  files: number;
}

export interface IntelligenceDependencies {
  internal_edges: number;
  unresolved_edges: number;
  external_edges: number;
  packages: PackageUsage[];
}

export interface IntelligenceOverview {
  project_id: UUID;
  name: string;
  description: string | null;
  totals: IntelligenceTotals;
  languages: LanguageStat[];
  directories: DirectoryStat[];
  frameworks: FrameworkHit[];
  entry_points: EntryPoint[];
  config_files: ConfigFile[];
  important_modules: ImportantModule[];
  dependencies: IntelligenceDependencies;
}

export interface ArchitectureLayer {
  name: string;
  side: string;
  files: number;
  symbols: number;
  imports_out: number;
  imported_by: number;
}

export interface LayerEdge {
  source: string;
  target: string;
  count: number;
}

export interface DatabaseTable {
  table: string;
  model: string | null;
  file_path: string;
  line: number;
  columns: string[];
  references: string[];
}

export interface RequestFlow {
  method: string;
  path: string;
  handler: string;
  file_path: string;
  line: number;
  framework: string | null;
  imports: string[];
}

export interface ResponsibilityModule {
  path: string;
  doc: string | null;
  symbols: number;
  side: string;
}

export interface Responsibility {
  layer: string;
  side: string;
  modules: ResponsibilityModule[];
}

export interface IntelligenceArchitecture {
  project_id: UUID;
  layers: ArchitectureLayer[];
  edges: LayerEdge[];
  database: { tables: DatabaseTable[] };
  request_flows: RequestFlow[];
  responsibilities: Responsibility[];
}

export interface SymbolHit {
  id: UUID;
  name: string;
  qualified_name: string;
  symbol_type: string;
  path: string;
  language: string | null;
  start_line: number;
  end_line: number;
  signature: string | null;
  doc: string | null;
}

export interface ImportEdge {
  reference: string;
  dependency_type: string | null;
  resolved_path: string | null;
  external: boolean | null;
}

export interface SymbolReference {
  path: string;
  line: number;
  snippet: string;
}

export interface SymbolDetail {
  symbol: SymbolHit;
  doc: string | null;
  signature: string | null;
  definition: string;
  imports: ImportEdge[];
  imported_by: string[];
  related_symbols: SymbolHit[];
  references: SymbolReference[];
}

export interface DocFinding {
  kind: string;
  severity: string;
  confirmed: boolean;
  message: string;
  details: Record<string, unknown>;
}

export interface DocsReport {
  project_id: UUID;
  readme: string | null;
  routes: { documented: number; implemented: number };
  findings: DocFinding[];
}

export type FindingConfidence = "confirmed" | "possible";

export interface IntelligenceFinding {
  kind: string;
  confidence: FindingConfidence;
  severity: string;
  message: string;
  details: Record<string, unknown>;
}

export interface FindingsSummary {
  confirmed: number;
  possible: number;
  by_kind: Record<string, number>;
}

export interface FindingsReport {
  project_id: UUID;
  summary: FindingsSummary;
  findings: IntelligenceFinding[];
}
