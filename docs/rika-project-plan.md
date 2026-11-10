# Rika — Project Plan

**Project Name:** Rika  
**Assistant Persona:** Female AI assistant  
**Project Type:** Local Project-Intelligence RAG Assistant  
**Platform:** Windows  
**Primary Goal:** Build a private, locally running AI assistant that can ingest, index, search, understand, and answer questions about project documentation and source code.

---

# 1. Project Overview

Rika is a local AI-powered project-intelligence assistant designed to understand software projects, documentation, source code, configuration files, and other project resources.

Users will be able to create independent project workspaces and provide Rika with files, folders, ZIP archives, documents, and source code.

Rika will process these materials, extract their contents, generate embeddings, index them, and use Retrieval-Augmented Generation (RAG) to answer questions with references to the original sources.

Unlike a basic chatbot, Rika will maintain project-specific knowledge and use evidence from the selected project when answering questions.

## 1.1 Core Capabilities

Rika should support:

- Multiple independent projects.
- Individual file uploads.
- Multiple file uploads.
- Folder uploads.
- ZIP archive uploads.
- Drag-and-drop uploads.
- Clipboard paste for supported content.
- Document parsing.
- Source-code parsing.
- Semantic search.
- Keyword search.
- Hybrid retrieval.
- Context-aware conversations.
- Source citations.
- File and line references.
- Incremental indexing.
- Project architecture understanding.
- Cross-file code analysis.
- Local LLM inference.
- Local data storage.
- Background ingestion jobs.

## 1.2 Main Objective

Build a private local assistant that can answer questions such as:

- What does this project do?
- Explain the overall project architecture.
- Where is authentication implemented?
- Which files handle database operations?
- Explain this function.
- What happens when a user submits a request?
- Which APIs are available?
- How are the frontend and backend connected?
- Where is this configuration defined?
- Find all references to a particular function.
- Compare the documentation with the actual implementation.
- Identify possible bugs or inconsistencies.
- Explain how a particular feature works across multiple files.

Rika should provide evidence for its answers and clearly communicate when the available project information is insufficient.

---

# 2. Hardware and Development Environment

## 2.1 Available Hardware

| Component | Available Specification |
|---|---|
| Operating System | Windows |
| RAM | 16 GB |
| GPU | NVIDIA |
| GPU VRAM | 4 GB |
| CPU | To be identified |
| GPU Model | To be identified |
| Storage | To be verified |

## 2.2 Hardware Considerations

The system must be designed around limited GPU memory.

Recommended initial configuration:

- Use a relatively small quantized language model.
- Start with a 4K context window.
- Use conservative GPU layer offloading.
- Keep embedding generation on CPU initially if necessary.
- Use small embedding batches.
- Limit simultaneous inference requests.
- Monitor RAM and VRAM consumption.
- Increase model and context sizes only after performance testing.

A larger model is not automatically better if it makes the system unstable or too slow.

## 2.3 Development Software

| Software | Purpose |
|---|---|
| Python | Backend development |
| FastAPI | Backend API |
| PostgreSQL | Main database |
| pgvector | Vector storage |
| Redis | Job queue and caching |
| Celery | Background processing |
| llama.cpp | Local model inference |
| Next.js | Frontend framework |
| React | User interface |
| TypeScript | Frontend development |
| Tailwind CSS | UI styling |
| Docker Desktop | Local infrastructure |
| Git | Version control |
| VS Code | Development environment |

---

# 3. Technology Stack

## 3.1 Backend

**Python + FastAPI**

Responsibilities:

- API management.
- Project management.
- File uploads.
- Document processing.
- Code analysis.
- Embedding generation.
- Retrieval.
- RAG orchestration.
- Conversation management.
- Model communication.
- Background job coordination.

## 3.2 Database

**PostgreSQL + pgvector**

Responsibilities:

- Project metadata.
- Document metadata.
- Extracted content.
- Document chunks.
- Vector embeddings.
- Conversations.
- Messages.
- Indexing jobs.
- Code symbols.
- Project relationships.

PostgreSQL will be the primary persistent database.

## 3.3 Background Processing

**Redis + Celery**

Responsibilities:

- File processing.
- Archive extraction.
- Document parsing.
- Code analysis.
- Chunking.
- Embedding generation.
- Index updates.
- Reindexing.
- Retry management.

Heavy ingestion tasks should not block normal API requests.

## 3.4 Local AI Inference

**llama.cpp**

Responsibilities:

- Local chat inference.
- Embedding inference where supported.
- Streaming responses.
- Model configuration.
- GPU offloading.

The application should communicate with llama.cpp through its server interface.

## 3.5 Frontend

**Next.js + React + TypeScript**

Responsibilities:

- Dashboard.
- Project management.
- File explorer.
- Upload interface.
- Chat interface.
- Citation viewer.
- Indexing progress.
- Settings.

---

# 4. High-Level Architecture

```text
                         USER
                           |
                           v
                  NEXT.JS FRONTEND
                           |
                           v
                    FASTAPI BACKEND
                           |
          +----------------+----------------+
          |                |                |
          v                v                v
    PROJECT SERVICE   INGESTION SERVICE   CHAT SERVICE
          |                |                |
          |                v                v
          |           REDIS QUEUE       RAG ENGINE
          |                |                |
          |                v                |
          |          CELERY WORKERS         |
          |                |                |
          |                v                v
          |          FILE PARSERS       RETRIEVAL
          |                |                |
          |                v                |
          |          CODE ANALYSIS           |
          |                |                |
          |                v                |
          |             CHUNKING             |
          |                |                |
          |                v                |
          |            EMBEDDINGS            |
          |                |                |
          +----------------+----------------+
                           |
                           v
                  POSTGRESQL + PGVECTOR
                           |
                           v
                      LLAMA.CPP
                           |
                           v
                     RIKA RESPONSE
                           |
                           v
                   NEXT.JS FRONTEND
```

---

# 5. Project Management

Rika must support multiple independent project workspaces.

Each project should have its own:

- Project metadata.
- Uploaded files.
- Directory structure.
- Extracted content.
- Document chunks.
- Embeddings.
- Code symbols.
- Dependencies.
- Conversations.
- Indexing history.

## 5.1 Project Operations

Users should be able to:

- Create a project.
- Rename a project.
- Update project descriptions.
- Delete a project.
- Open a project.
- View project statistics.
- View indexed documents.
- Search project content.
- Chat with Rika about that project.

## 5.2 Project Isolation

Every document, chunk, embedding, conversation, and retrieval query must be associated with a project.

Rika must never retrieve content from another project unless an explicitly authorized cross-project feature is implemented.

Project isolation must be enforced at the database and service layers.

---

# 6. File Ingestion System

## 6.1 Supported Input Methods

Rika should support:

1. Individual file uploads.
2. Multiple file uploads.
3. Folder uploads.
4. ZIP archive uploads.
5. Drag-and-drop.
6. Clipboard file paste.
7. Clipboard image paste.
8. Clipboard text paste.
9. Direct code paste.
10. Direct text input.

Clipboard support will depend on browser permissions and available clipboard APIs.

## 6.2 Supported Document Formats

| Format | Extension | Parser |
|---|---|---|
| PDF | .pdf | PyMuPDF |
| Word | .docx | python-docx |
| PowerPoint | .pptx | python-pptx |
| Excel | .xlsx | openpyxl |
| CSV | .csv | Python CSV / pandas |
| Text | .txt | Native Python |
| Markdown | .md | Markdown parser |
| JSON | .json | Native Python |
| YAML | .yaml, .yml | PyYAML |
| TOML | .toml | tomllib |
| XML | .xml | ElementTree |
| HTML | .html | BeautifulSoup |

Optional support:

- Scanned PDFs.
- OCR.
- Images.
- Additional office formats.

## 6.3 Supported Source-Code Formats

Initial languages:

- Python.
- JavaScript.
- TypeScript.
- Java.
- C.
- C++.
- C#.
- Go.
- Rust.
- PHP.
- SQL.
- HTML.
- CSS.
- JSON.
- YAML.

Tree-sitter will be used for syntax-aware source-code analysis where grammars are available.

## 6.4 File Processing Pipeline

```text
UPLOAD
   |
   v
VALIDATION
   |
   v
FILE STORAGE
   |
   v
JOB CREATION
   |
   v
BACKGROUND QUEUE
   |
   v
FILE TYPE DETECTION
   |
   v
PARSING
   |
   v
CODE ANALYSIS
   |
   v
CHUNKING
   |
   v
EMBEDDING GENERATION
   |
   v
DATABASE STORAGE
   |
   v
INDEXED
```

## 6.5 File Validation

The ingestion system must:

- Validate file extensions.
- Validate file signatures where appropriate.
- Enforce upload size limits.
- Enforce archive extraction limits.
- Detect duplicate files.
- Prevent ZIP path traversal.
- Prevent archive decompression bombs.
- Preserve original file paths.
- Record processing errors.
- Avoid executing uploaded files.

## 6.6 Incremental Indexing

Rika should not reprocess every file whenever a project changes.

Use content hashing to identify changes.

Expected behavior:

- New file: parse and index.
- Unchanged file: skip processing.
- Modified file: reprocess and replace its index.
- Deleted file: remove associated chunks and symbols.
- Renamed file: update path metadata and references.
- Failed file: preserve the error and allow retry.

---

# 7. Document Parsing

## 7.1 Parser Architecture

Implement a common parser interface.

Each parser should return normalized content with metadata.

Example:

```json
{
  "file_path": "docs/architecture.pdf",
  "file_type": "pdf",
  "content": "Extracted document text...",
  "metadata": {
    "page_number": 4,
    "section": "System Architecture"
  },
  "warnings": []
}
```

## 7.2 Parsing Requirements

Preserve:

- Original file path.
- Page numbers.
- Headings.
- Sections.
- Tables where practical.
- Spreadsheet sheet names.
- Slide numbers.
- Code line numbers.
- Parsing warnings.
- Extraction metadata.

## 7.3 OCR

OCR should be an optional capability for scanned documents and images.

OCR should not be required for the initial MVP.

---

# 8. Source-Code Intelligence

Rika should understand source code structurally rather than treating every source file as plain text.

## 8.1 Tree-sitter Integration

Use Tree-sitter to extract:

- Functions.
- Methods.
- Classes.
- Interfaces.
- Types.
- Imports.
- Constants.
- API route declarations where supported.
- Source line ranges.
- Parent-child symbol relationships.

## 8.2 Symbol Metadata

Example:

```json
{
  "project_id": "project-123",
  "file_path": "backend/app/services/auth.py",
  "symbol_name": "authenticate_user",
  "symbol_type": "function",
  "language": "python",
  "start_line": 15,
  "end_line": 42
}
```

## 8.3 Project Relationships

Rika should gradually build:

- Import graphs.
- Module relationships.
- Function relationships.
- Class relationships.
- API relationships.
- Database model relationships.
- Dependency information.

These relationships will support more advanced questions.

---

# 9. Chunking Strategy

Chunking is one of the most important parts of the RAG system.

Rika should use different strategies for different content types.

## 9.1 Document Chunking

For ordinary documents:

- Respect headings.
- Preserve paragraphs.
- Keep related content together.
- Split oversized sections.
- Preserve page and section metadata.

## 9.2 Code Chunking

For source code:

- Prefer complete functions.
- Prefer complete classes.
- Preserve symbol names.
- Preserve parent scope.
- Preserve imports where useful.
- Split oversized symbols carefully.
- Preserve line ranges.

## 9.3 Chunk Metadata

Every chunk should include:

- Project ID.
- Document ID.
- File path.
- Content type.
- Language.
- Symbol name where applicable.
- Start line.
- End line.
- Page number where applicable.
- Content hash.
- Embedding model identifier.

## 9.4 Chunking Requirements

- Avoid splitting small functions unnecessarily.
- Avoid mixing unrelated sections.
- Preserve traceability.
- Keep chunks within model context constraints.
- Make chunking configurable.
- Test chunking against real project files.

---

# 10. Embedding System

## 10.1 Initial Candidate

Qwen3-Embedding-0.6B is a candidate embedding model.

Its runtime compatibility, output dimensions, quantization options, and resource requirements must be verified before final selection.

## 10.2 Embedding Responsibilities

- Generate embeddings for document chunks.
- Generate embeddings for code chunks.
- Generate embeddings for search queries.
- Process batches efficiently.
- Track embedding model versions.
- Validate vector dimensions.
- Store vectors in pgvector.

## 10.3 Important Requirements

- Query and document embeddings must use compatible model configurations.
- Embedding dimensions must match the database vector column.
- Model changes require an explicit reindexing strategy.
- Unchanged files should not generate unnecessary embeddings.

---

# 11. Retrieval System

Rika should use hybrid retrieval instead of relying exclusively on vector similarity.

## 11.1 Vector Search

Use pgvector to find semantically similar chunks.

Useful for:

- Conceptual questions.
- Paraphrased questions.
- Natural-language explanations.
- Related functionality.

## 11.2 Keyword Search

Use PostgreSQL full-text search.

Useful for:

- Function names.
- Class names.
- API routes.
- Error messages.
- Configuration keys.
- Exact identifiers.

## 11.3 Hybrid Retrieval

Combine:

1. Vector similarity.
2. Keyword relevance.
3. Metadata filters.
4. Result fusion.
5. Deduplication.
6. Optional reranking.

Reciprocal Rank Fusion can be used to combine ranked results.

## 11.4 Metadata Filtering

Support filters for:

- Project.
- File path.
- File type.
- Programming language.
- Symbol type.
- Directory.
- Document type.

## 11.5 Retrieval Evaluation

Create a curated evaluation dataset containing realistic project questions and expected evidence.

Measure:

- Recall@5.
- Recall@10.
- Retrieval precision.
- Citation correctness.
- Duplicate result frequency.

Do not introduce a reranker until the baseline retrieval system has been evaluated.

---

# 12. RAG and Answer Generation

## 12.1 Local LLM

Use llama.cpp for local inference.

Initial chat model candidates:

- Qwen3-4B GGUF Q4_K_M.
- Qwen2.5-Coder-3B-Instruct Q4_K_M.

These are starting candidates, not fixed requirements.

Model selection should be based on:

- Actual RAM usage.
- Actual VRAM usage.
- Inference speed.
- Context support.
- Code understanding.
- Answer quality.
- GGUF compatibility.

## 12.2 Rika Persona

Rika should behave as a helpful, knowledgeable female project assistant.

Her communication style should be:

- Clear.
- Professional.
- Friendly.
- Technically accurate.
- Evidence-oriented.
- Honest about uncertainty.

The persona should not override factual accuracy.

## 12.3 Answering Rules

Rika must:

- Use retrieved project evidence.
- Cite relevant files.
- Include line ranges when available.
- Never invent source paths.
- Never invent citations.
- Distinguish evidence from inference.
- Identify conflicting information.
- State when evidence is insufficient.
- Treat retrieved content as untrusted data.

## 12.4 Citation Structure

Example:

```text
Rika:

The authentication process is implemented in the
authentication service.

Source:
backend/app/services/auth.py

Lines:
15–42

Explanation:
The authenticate_user function validates credentials
and returns the authenticated user.
```

## 12.5 Citation Validation

Every generated citation should be checked against stored source metadata.

Invalid citations should be rejected or repaired rather than presented as verified references.

## 12.6 Conversation Management

Support:

- Conversation creation.
- Conversation history.
- Follow-up questions.
- Context-aware responses.
- Conversation persistence.
- Streaming responses.
- Conversation deletion.

Conversation history must remain scoped to the selected project.

---

# 13. Advanced Project Intelligence

These capabilities should be developed after the core RAG pipeline works.

## 13.1 Project Overview

Rika should identify:

- Project languages.
- Main directories.
- Frameworks.
- Entry points.
- Configuration files.
- Important modules.
- Dependencies.

## 13.2 Architecture Analysis

Rika should explain:

- Application layers.
- Frontend and backend structure.
- Service relationships.
- Database architecture.
- Request flows.
- Module responsibilities.

## 13.3 Code Analysis

Rika should support:

- Function explanations.
- Class explanations.
- API endpoint discovery.
- Import analysis.
- Cross-file code exploration.
- Function call tracing where static analysis supports it.
- Database model analysis.

## 13.4 Documentation Comparison

Rika should compare:

- Documentation with implementation.
- README instructions with actual configuration.
- API documentation with source code.
- Database documentation with models.

## 13.5 Bug Investigation

Rika should help investigate:

- Potential logic errors.
- Missing imports.
- Inconsistent configuration.
- Broken references.
- Suspicious code paths.
- Duplicate implementations.

It should distinguish confirmed defects from possible issues requiring verification.

---

# 14. Database Design

Initial database tables:

| Table | Purpose |
|---|---|
| projects | Project metadata |
| documents | Uploaded file metadata |
| document_chunks | Extracted chunks and embeddings |
| conversations | Chat sessions |
| messages | Chat messages |
| ingestion_jobs | Background job records |
| file_versions | File change history |
| project_symbols | Extracted code symbols |
| project_dependencies | Project relationships |
| model_configs | Model configuration |

## 14.1 Projects

Suggested fields:

- id
- name
- description
- created_at
- updated_at
- settings

## 14.2 Documents

Suggested fields:

- id
- project_id
- original_path
- stored_path
- filename
- file_type
- content_hash
- size
- status
- created_at
- updated_at

## 14.3 Document Chunks

Suggested fields:

- id
- project_id
- document_id
- chunk_index
- content
- embedding
- content_type
- language
- symbol_name
- start_line
- end_line
- page_number
- metadata

## 14.4 Conversations

Suggested fields:

- id
- project_id
- title
- created_at
- updated_at

## 14.5 Messages

Suggested fields:

- id
- conversation_id
- role
- content
- citations
- created_at

## 14.6 Ingestion Jobs

Suggested fields:

- id
- project_id
- document_id
- job_type
- status
- progress
- attempts
- error_message
- created_at
- started_at
- completed_at

---

# 15. API Design

Use versioned API routes.

Base path:

```text
/api/v1
```

## 15.1 Health

```text
GET /health/live
GET /health/ready
```

## 15.2 Projects

```text
POST   /api/v1/projects
GET    /api/v1/projects
GET    /api/v1/projects/{id}
PATCH  /api/v1/projects/{id}
DELETE /api/v1/projects/{id}
```

## 15.3 Uploads

```text
POST /api/v1/projects/{id}/upload
POST /api/v1/projects/{id}/upload-folder
POST /api/v1/projects/{id}/upload-zip
```

## 15.4 Documents

```text
GET    /api/v1/projects/{id}/documents
GET    /api/v1/documents/{id}
DELETE /api/v1/documents/{id}
POST   /api/v1/documents/{id}/reindex
```

## 15.5 Jobs

```text
GET  /api/v1/jobs/{id}
GET  /api/v1/projects/{id}/jobs
POST /api/v1/jobs/{id}/retry
```

## 15.6 Search

```text
POST /api/v1/projects/{id}/search
```

## 15.7 Chat

```text
POST /api/v1/projects/{id}/chat
```

## 15.8 Conversations

```text
GET    /api/v1/conversations
GET    /api/v1/conversations/{id}
DELETE /api/v1/conversations/{id}
```

---

# 16. Frontend Design

## 16.1 Dashboard

Display:

- Project count.
- Recently accessed projects.
- Recent conversations.
- Indexing jobs.
- Model status.
- System health.

## 16.2 Project Management

Features:

- Create project.
- Rename project.
- Delete project.
- Open project.
- View project details.

## 16.3 Project Workspace

Features:

- File explorer.
- Folder navigation.
- Upload files.
- Upload folders.
- Upload ZIP archives.
- Drag-and-drop.
- Clipboard paste.
- Document status.
- Indexing progress.
- Project search.

## 16.4 Chat Interface

Features:

- Chat with Rika.
- Select active project.
- Stream responses.
- Follow-up questions.
- View citations.
- Open source files.
- Display source line ranges.
- Browse conversation history.

## 16.5 Settings

Features:

- Chat model configuration.
- Embedding model configuration.
- Context size.
- GPU offloading.
- Storage location.
- Upload limits.
- Indexing settings.

---

# 17. Security and Privacy

Rika is intended to run locally and should minimize external data exposure.

## 17.1 File Security

- Never execute uploaded code.
- Validate uploaded files.
- Prevent ZIP path traversal.
- Limit archive extraction.
- Protect storage directories.
- Exclude sensitive files by default where appropriate.

## 17.2 Project Security

- Enforce project isolation.
- Validate document ownership.
- Validate conversation ownership.
- Restrict database queries by project.
- Prevent accidental cross-project retrieval.

## 17.3 Prompt Injection Protection

Retrieved documents and source code must be treated as untrusted content.

Instructions found inside uploaded files must not override Rika's system instructions or application security rules.

## 17.4 Local Privacy

- Bind local services to localhost where possible.
- Avoid unnecessary external APIs.
- Keep models locally stored.
- Do not transmit project content to external services by default.
- Avoid logging secrets or sensitive file contents.
- Document any optional network-dependent functionality.

---

# 18. Reliability and Performance

## 18.1 Background Processing

Use Celery workers for expensive ingestion operations.

## 18.2 Idempotency

Repeated jobs should not create duplicate chunks or inconsistent indexes.

## 18.3 Error Handling

Track:

- File validation errors.
- Parser errors.
- Embedding errors.
- Database errors.
- Model errors.
- Retrieval errors.
- Worker failures.

## 18.4 Resource Management

- Limit concurrent ingestion tasks.
- Limit embedding batch sizes.
- Limit simultaneous model requests.
- Use bounded queues.
- Monitor RAM and VRAM.
- Support job retries.
- Support cancellation where practical.

## 18.5 Incremental Updates

When a document changes:

1. Detect its new content hash.
2. Mark the document for reprocessing.
3. Parse the new content.
4. Generate new chunks.
5. Generate embeddings.
6. Replace the old index transactionally.
7. Update symbol metadata.
8. Mark the job complete.

Do not leave stale chunks after a successful update.

---

# 19. Testing and Quality Assurance

## 19.1 Unit Tests

Test:

- File validation.
- ZIP extraction.
- Document parsers.
- Code parsers.
- Chunking.
- Embedding generation.
- Retrieval.
- Citation validation.
- Project services.

## 19.2 Integration Tests

Test:

- Database connectivity.
- Project CRUD.
- Upload pipeline.
- Background jobs.
- Embedding storage.
- Hybrid retrieval.
- RAG generation.
- Conversation persistence.

## 19.3 Security Tests

Test:

- ZIP path traversal.
- Oversized files.
- Decompression bombs.
- Malformed documents.
- Project isolation.
- Prompt injection.
- Secret file handling.

## 19.4 Evaluation Targets

Initial targets:

- 100% project isolation in automated tests.
- 100% generated citations resolve to stored sources in the citation test set.
- No uploaded source code is executed.
- No stale chunks remain after successful reindexing.
- At least 85% Recall@5 on a curated retrieval evaluation set.

These are targets to measure, not assumed results.

---

# 20. Repository Structure

```text
rika/
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── dependencies.py
│   │   │
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   └── schemas/
│   │   │
│   │   ├── core/
│   │   │   ├── logging.py
│   │   │   ├── exceptions.py
│   │   │   └── security.py
│   │   │
│   │   ├── database/
│   │   │   ├── models/
│   │   │   ├── session.py
│   │   │   └── migrations/
│   │   │
│   │   ├── ingestion/
│   │   │   ├── upload.py
│   │   │   ├── validation.py
│   │   │   ├── archive.py
│   │   │   └── pipeline.py
│   │   │
│   │   ├── parsers/
│   │   │   ├── pdf.py
│   │   │   ├── docx.py
│   │   │   ├── pptx.py
│   │   │   ├── spreadsheet.py
│   │   │   ├── text.py
│   │   │   └── code.py
│   │   │
│   │   ├── code_intelligence/
│   │   │   ├── tree_sitter.py
│   │   │   ├── symbols.py
│   │   │   └── dependencies.py
│   │   │
│   │   ├── chunking/
│   │   ├── embeddings/
│   │   ├── retrieval/
│   │   ├── rag/
│   │   ├── llm/
│   │   ├── agent/
│   │   ├── conversations/
│   │   ├── services/
│   │   └── workers/
│   │
│   ├── tests/
│   ├── requirements.txt
│   └── alembic.ini
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── lib/
│   │   └── types/
│   │
│   ├── public/
│   └── package.json
│
├── models/
│   ├── llm/
│   ├── embeddings/
│   └── reranker/
│
├── storage/
│   ├── uploads/
│   ├── extracted/
│   ├── temp/
│   └── backups/
│
├── scripts/
│   ├── setup.ps1
│   ├── start.ps1
│   ├── stop.ps1
│   ├── backup.ps1
│   └── restore.ps1
│
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

---

# 21. Implementation Phases

| Phase | Description | Priority |
|---|---|---|
| 0 | Environment preparation | Critical |
| 1 | Project foundation | Critical |
| 2 | Database and project management | Critical |
| 3 | File upload system | Critical |
| 4 | Document parsing | Critical |
| 5 | Source-code intelligence | High |
| 6 | Chunking and embeddings | Critical |
| 7 | Hybrid retrieval | Critical |
| 8 | RAG and answer generation | Critical |
| 9 | Frontend development | High |
| 10 | Advanced project intelligence | Medium |
| 11 | Testing and optimization | Critical |
| 12 | Packaging and deployment | High |

## Development Order

Build the backend RAG pipeline first.

The first usable vertical slice should be:

1. Create a project.
2. Upload one document.
3. Parse the document.
4. Chunk the content.
5. Generate embeddings.
6. Store the chunks.
7. Search the project.
8. Ask Rika a question.
9. Generate an evidence-based answer.
10. Return valid citations.

Once this works reliably, expand to folders, ZIP archives, multiple formats, and source-code intelligence.

---

# 22. Initial Environment Configuration

Create `.env.example`:

```env
APP_NAME=Rika
APP_ENV=development
APP_DEBUG=true

APP_HOST=127.0.0.1
APP_PORT=8000

DATABASE_URL=postgresql+asyncpg://rika:change-me@127.0.0.1:5432/rika

REDIS_URL=redis://127.0.0.1:6379/0

CHAT_BASE_URL=http://127.0.0.1:8080
CHAT_MODEL_NAME=local-chat-model

EMBEDDING_BASE_URL=http://127.0.0.1:8081
EMBEDDING_MODEL_NAME=local-embedding-model
EMBEDDING_DIMENSION=VERIFY_BEFORE_USE

STORAGE_ROOT=../storage

MAX_UPLOAD_MB=100
MAX_ARCHIVE_FILES=5000
MAX_ARCHIVE_EXPANDED_MB=1000

LOG_LEVEL=INFO
```

The embedding dimension must be verified against the actual selected model before creating the final vector column.

Never commit the real `.env` file.

---

# 23. MVP Definition of Done

The first working Rika MVP should satisfy these conditions:

- [ ] Rika runs locally on Windows.
- [ ] PostgreSQL and pgvector work.
- [ ] Redis works.
- [ ] FastAPI connects to infrastructure.
- [ ] Local chat inference works.
- [ ] Local embedding generation works.
- [ ] Embedding dimensions are verified.
- [ ] Users can create projects.
- [ ] Users can upload individual files.
- [ ] Documents can be parsed.
- [ ] Content can be chunked.
- [ ] Embeddings can be stored.
- [ ] Hybrid retrieval works.
- [ ] Rika can answer questions about indexed content.
- [ ] Citations resolve to real sources.
- [ ] Insufficient evidence is handled honestly.
- [ ] Project isolation tests pass.
- [ ] Reindexing does not leave stale chunks.
- [ ] Uploaded code is never executed.

A polished frontend is not required to prove the backend MVP.

---

# 24. Risks and Mitigation

| Risk | Mitigation |
|---|---|
| 4 GB VRAM is insufficient | Use smaller quantized models and conservative offloading |
| RAM usage becomes excessive | Limit batch sizes and concurrency |
| Embedding dimensions mismatch | Verify model dimensions before database migration |
| Large archives exhaust resources | Enforce archive limits |
| Malformed files break ingestion | Use per-file error handling |
| Retrieval misses relevant code | Use hybrid retrieval and symbol-aware chunks |
| LLM invents citations | Validate citations against stored metadata |
| Prompt injection | Treat retrieved content as untrusted |
| Stale chunks remain | Use transactional index replacement |
| Indexing blocks chat | Use background workers |
| Model changes invalidate embeddings | Track model versions and reindex when necessary |
| Parser support is incomplete | Maintain explicit format support and warnings |

---

# 25. Immediate Next Steps

Start with infrastructure rather than advanced AI features.

1. Identify the exact CPU and NVIDIA GPU models.
2. Verify Windows, Python, Node.js, Git, and Docker.
3. Create the Rika repository.
4. Create the initial folder structure.
5. Create `.env.example`.
6. Create `.gitignore`.
7. Set up the Python virtual environment.
8. Create a minimal FastAPI application.
9. Configure Docker Compose.
10. Start PostgreSQL with pgvector.
11. Start Redis.
12. Verify database connectivity.
13. Verify Redis connectivity.
14. Create a Celery test task.
15. Install and test llama.cpp.
16. Test chat inference.
17. Test embedding inference.
18. Verify the embedding dimensions.
19. Implement database models and migrations.
20. Implement project CRUD APIs.

Do not begin the complete ingestion pipeline until the infrastructure milestone passes.

---

# 26. First Milestone — Local Foundation

The first milestone is complete when:

- PostgreSQL with pgvector starts successfully.
- Redis starts successfully.
- FastAPI starts successfully.
- FastAPI connects to PostgreSQL.
- FastAPI connects to Redis.
- Celery can execute a test task.
- llama.cpp chat inference is reachable.
- The embedding service is reachable.
- Health endpoints report accurate readiness.
- Configuration and startup instructions are documented.

After this milestone, implement project management and then the first single-file ingestion-to-answer workflow.

---

# 27. Final Project Principles

Rika should be designed around the following principles:

1. **Local-first:** Keep project processing and inference local by default.
2. **Evidence-first:** Answers should be grounded in indexed project information.
3. **Traceability:** Every citation should point to a real source.
4. **Project isolation:** Separate project knowledge and conversations.
5. **Incremental processing:** Avoid unnecessary reindexing.
6. **Resource awareness:** Respect the available RAM and VRAM.
7. **Reliability:** Handle malformed files and failed jobs safely.
8. **Security:** Never execute uploaded source code.
9. **Modularity:** Keep parsers, retrieval, embeddings, and inference independent.
10. **Extensibility:** Allow additional languages, models, and document formats later.

Rika should never pretend to understand a project when the available indexed evidence does not support an answer.
