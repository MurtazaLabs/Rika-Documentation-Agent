# Rika

Rika is a local, privacy-first project-intelligence assistant. She ingests a
project's documentation and source code, then answers questions with cited file
paths and line ranges — running entirely on your machine.

The full specification lives in [`docs/rika-project-plan.md`](docs/rika-project-plan.md).

> **Status: Phases 4–7 complete.** Projects, uploads, document parsing, code
> intelligence, chunking, embedding, ingestion jobs and hybrid retrieval work
> end to end: every chunk is stored in PostgreSQL with a 1024-dimension vector
> and indexed with HNSW, source files also produce symbols and import edges,
> and `POST /projects/{id}/search` fuses pgvector and full-text results with
> citations. Answer generation and the UI land in later phases.

## Requirements

| Requirement | Notes |
|---|---|
| Windows | Target platform |
| Python 3.10+ | Verified with 3.10.11 |
| Docker Desktop | Runs PostgreSQL + pgvector and Redis (optional, see below) |
| Node.js 20+ | Frontend, Phase 9 |
| llama.cpp `llama-server` | Local chat + embedding inference |

Target hardware is a 4 GB NVIDIA GPU with 16 GB RAM, so models are sized
conservatively: partial CUDA offload, 4K context, one concurrent request, and
embeddings on CPU.

## Quickstart

```powershell
.\scripts\setup.ps1            # venv, dependencies, .env, storage, database, migrations
.\scripts\start.ps1 -WithWorker
```

Then check:

- API docs — <http://127.0.0.1:8000/docs>
- Liveness — <http://127.0.0.1:8000/health/live>
- Readiness — <http://127.0.0.1:8000/health/ready>

`setup.ps1` starts the database and queue (Compose or the portable services
below) and applies migrations. To apply them again later (new migration,
restored database), run `.\scripts\migrate.ps1`.

Stop everything with `.\scripts\stop.ps1` (add `-KeepInfrastructure` to leave the
database and queue running).

### Without Docker

`.tools\` can hold a portable PostgreSQL 16.15 + pgvector 0.8.6 cluster: no
admin rights, no Windows service, no system-wide install.

```powershell
# one-time: fetch a conda-forge PostgreSQL + pgvector (Windows pgvector builds target PG 16)
curl.exe -L -o .tools\micromamba.exe https://github.com/mamba-org/micromamba-releases/releases/latest/download/micromamba-win-64
.tools\micromamba.exe create -y -r .tools\mamba-root -p .tools\postgres -c conda-forge "postgresql=16" pgvector

.\scripts\postgres-local.ps1 -Action init     # .tools\pgdata + the rika database
.\scripts\postgres-local.ps1 -Action start
```

Redis has no official Windows build and no conda-forge package, so the portable
MSYS2 build from [redis-windows](https://github.com/redis-windows/redis-windows)
is used instead:

```powershell
curl.exe -L -o .tools\redis.zip https://github.com/redis-windows/redis-windows/releases/download/8.10.3/Redis-8.10.3-Windows-x64-msys2.zip
powershell -Command "Expand-Archive .tools\redis.zip -DestinationPath .tools"
Move-Item .tools\Redis-8.10.3-Windows-x64-msys2 .tools\redis

.\scripts\redis-local.ps1 -Action start
```

`redis-local.ps1` writes its config on start — loopback only, append-only
persistence in `.tools\redis-data`, port from `REDIS_URL` — and also accepts
`stop` and `status`.

The model servers work the same way (see [Model servers](#model-servers)).
All three helpers read their credentials/ports from `.env`, and `setup.ps1`,
`start.ps1` and `stop.ps1` use them automatically when Docker is missing.
The toolchain and binaries live under `.tools\` (git-ignored); the GGUF files
live under `models\` (also git-ignored). Delete those folders to remove the
servers, their data and the models.

### Manual setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Copy-Item .env.example .env
docker compose up -d
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload
```

## Health endpoints

| Endpoint | Behaviour |
|---|---|
| `GET /health/live` | 200 while the process is serving |
| `GET /health/ready` | Probes PostgreSQL, Redis and both model servers |

`/health/ready` returns:

- `ready` (200) — everything answered.
- `degraded` (200) — a model server is down; the API still works.
- `unavailable` (503) — PostgreSQL or Redis is down.

The body lists every probe with `name`, `status`, `critical` and `detail`, so a
failure names the dependency instead of returning a bare 503.

## API

All application endpoints live under `/api/v1`.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/projects` | Create a project |
| `GET` | `/projects` | List projects (`limit`, `offset`) |
| `GET` | `/projects/{id}` | Fetch one project |
| `PATCH` | `/projects/{id}` | Rename or re-describe; `null` clears the description |
| `DELETE` | `/projects/{id}` | Delete the project and everything under it |
| `GET` | `/projects/{id}/documents` | List that project's documents only |
| `GET` | `/documents/{id}` | Document metadata (never its server path) |
| `DELETE` | `/documents/{id}` | Remove the document, its chunks and its files |
| `POST` | `/documents/{id}/reindex` | Queue a fresh ingestion job |
| `POST` | `/projects/{id}/upload` | One or more files (`files`) |
| `POST` | `/projects/{id}/upload-folder` | Files plus their relative `paths` |
| `POST` | `/projects/{id}/upload-zip` | One ZIP archive |
| `POST` | `/projects/{id}/search` | Hybrid retrieval with metadata filters |
| `GET` | `/jobs/{id}` | Job status and progress |
| `GET` | `/projects/{id}/jobs` | List a project's jobs |
| `POST` | `/jobs/{id}/retry` | Re-queue a failed or cancelled job |

Errors use one shape: `{"error": {"code", "message", "details"}}`. Validation
failures return 422, unknown ids 404, oversized uploads 413, a job that cannot
be retried 409, and readiness 503 — never a bare 500.

## Ingestion

Uploads are validated and written to disk synchronously (bounded by
`MAX_UPLOAD_MB`), then queued. A Celery worker parses the file, analyses code,
chunks it and stores the chunks, updating `ingestion_jobs.progress` at each step
so the client can poll `GET /jobs/{id}`.

```text
upload → validate → store → job (queued) → worker:
  parse → (analyse code) → chunk → embed → store chunks/symbols → indexed
```

**Formats.** Text, Markdown, JSON, YAML, TOML, XML, HTML, CSV/TSV, PDF (PyMuPDF),
DOCX (python-docx), PPTX (python-pptx), XLSX (openpyxl) and source code in the
languages Rika targets — see `backend/app/ingestion/formats.py` for the exact
extension list. Code chunks are tagged `content_type=code` with their language.
Images and OCR are not accepted yet rather than silently producing empty
documents. A scanned PDF fails with a clear error instead of an empty index.

**Document structure.** Parsers return structural segments as well as flat text,
so citations keep the source's own coordinates. PDF pages become
`page_number`; DOCX headings become `heading`/`section`/`section_path` and
tables are flattened to `cell | cell` rows; PPTX slides keep
`slide_number`/`title`; XLSX sheets keep `sheet_name`/`row`/`column` counts.
Markdown and HTML split on headings outside fenced code blocks, and chunks carry
the section path. No `[page 3]` markers are injected into chunk text: the
metadata carries the structure instead.

**Source code.** Files are parsed with Tree-sitter, using the grammars bundled in
`tree-sitter-language-pack` (no runtime downloads) for Python,
JavaScript/TypeScript, Java, C#, Go, Rust, PHP, Ruby, Kotlin, Swift, C/C++, SQL,
CSS, Bash, PowerShell, Vue and Svelte. One syntax-tree pass yields functions,
methods, classes, interfaces, types, constants and HTTP routes with their line
ranges, parents and signatures, plus import/include/require edges. Chunking is
symbol-aware: small files stay whole, top-level definitions become chunks,
oversized classes are split into header/child/tail pieces and oversized
functions into line ranges that keep the same `symbol_name`. Symbols are stored
in `project_symbols`, their names also on `document_chunks.symbol_name`, and
import edges in `project_dependencies` for later retrieval and impact analysis.

**Safety.** Extensions are allow-listed, PDF and OOXML container signatures are
checked, and binary content is refused. Uploaded code is only ever read as text —
never imported or executed. Archive paths are normalised (`..`, absolute paths and
drive letters rejected), symlinks and encrypted entries are refused, and file
count, expanded size and compression ratio are capped (`MAX_ARCHIVE_FILES`,
`MAX_ARCHIVE_EXPANDED_MB`). A rejected request leaves no rows and no files.

**Incremental behaviour.** Identical content is skipped as a duplicate; a
changed file at a known path replaces its bytes and its index; re-indexing
replaces the old chunks, symbols and dependencies instead of appending to them.
A failed parse is recorded on both the job and the document, and
`POST /jobs/{id}/retry` re-queues it without re-uploading.

Chunks are line-aligned (`start_line`/`end_line`, `CHUNK_SIZE_CHARS` with
`CHUNK_OVERLAP_CHARS`) and each one is embedded before it is stored: the
worker sends `EMBEDDING_BATCH_SIZE` chunks per request to the embedding server,
checks every vector is 1024 wide, and writes the vector together with the model
name in `document_chunks.embedding_model`. Embedding happens *before* the old
chunks are replaced, so an embedding server that is down fails the job and
leaves the document's previous index untouched.

A model whose output is not 1024 wide is refused rather than stored: vector
width is baked into the column and its HNSW index, so swapping embedding models
means a schema revision plus a reindex.

## Retrieval

`POST /api/v1/projects/{id}/search` retrieves candidate chunks, not answers.
The default `hybrid` mode runs two independent queries and fuses them:

- pgvector cosine similarity over `document_chunks.embedding` (HNSW index).
- PostgreSQL full-text search over the generated `search_vector` column
  (GIN index), using `websearch_to_tsquery('simple', ...)` so identifiers,
  routes and configuration keys stay exact.

Fusion uses Reciprocal Rank Fusion with `k = 60`. Results are deduplicated by
chunk id, so a chunk found by both signals appears once with both component
scores. `mode` can be `vector` or `keyword` to measure each signal separately.
No reranker is applied until the baseline has been evaluated.

```json
{
  "query": "where is the archive path validated?",
  "mode": "hybrid",
  "limit": 10,
  "filters": {
    "file_type": "code",
    "language": "python",
    "directory": "backend/app/ingestion",
    "symbol_type": "function",
    "document_type": "code",
    "file_path": "backend/app/ingestion/archive.py"
  }
}
```

Every filter is optional and they combine with AND. `project_id` is not
accepted in the body: the URL is the isolation boundary. Each result carries
its citation — `file_path`, `symbol_name`, `start_line`/`end_line`,
`page_number`, `language`, `content_type` — plus `rank`, `score`,
`vector_score`, `keyword_score` and `matched_by`.

The query is embedded with the configured embedding model. A query vector
whose width does not match the stored `vector(1024)` column is refused with a
`model_server_error`; it is never compared against incompatible vectors.

PostgreSQL is the production retrieval path. The SQLite test fallback computes
cosine similarity and term scores in Python so ranking, filters and
deduplication are exercised without pretending SQLite is a vector database.

### Retrieval evaluation

The curated cases live in
[`backend/evaluation/retrieval_cases.json`](backend/evaluation/retrieval_cases.json).
They ask realistic questions about this repository and name the expected
evidence (file path plus symbol/page/line when relevant).

Index the repository as one project (a ZIP without `.venv`, `.tools` and
`models` is enough), then run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m evaluation.run_retrieval_eval --project-id <project-uuid>
```

The report contains per-case and aggregate Recall@5, Recall@10, precision,
citation correctness and duplicate result frequency. Add `--mode vector` or
`--mode keyword` to record single-signal baselines before considering a
reranker.

## Database

PostgreSQL with pgvector (`pgvector/pgvector:pg17` in Compose). Ten tables: `projects`, `documents`,
`document_chunks`, `file_versions`, `conversations`, `messages`,
`ingestion_jobs`, `project_symbols`, `project_dependencies`, `model_configs`.

Every content table carries `project_id`, and deletes cascade from `projects`,
so project isolation is a schema property rather than something each query has
to remember. `project_symbols` and `project_dependencies` are filled for every
indexed code file and cascade from their source document, so deleting or
re-indexing a file cannot leave stale symbols behind.

Migrations live in `backend/app/database/migrations/` and are driven by
`DATABASE_URL` from `.env`:

```powershell
.\scripts\migrate.ps1                        # upgrade to head
.\scripts\migrate.ps1 -Revision base -Downgrade
```

The schema is verified on PostgreSQL 16.15 with pgvector 0.8.6 and asyncpg —
see the test section — so the same migration is exercised on 16 (the portable
cluster) and 17 (Compose).

`document_chunks.embedding` is a `vector(1024)` column with a cosine HNSW index
(`m = 16`, `ef_construction = 64`), both created by migration `0002` once
`check-models` had reported the real model width. The width is a literal in the
migration so the same revision always produces the same database;
`EMBEDDING_DIMENSION` in `.env` must agree with it.

Migration `0003` adds `document_chunks.search_vector`, a stored generated
`tsvector` column (symbol name weight A, content B, source path C), and its GIN
index. PostgreSQL keeps it in sync on every chunk insert, so ingestion needs no
second write and re-indexing cannot leave a stale keyword index. Keyword
retrieval queries it with `websearch_to_tsquery('simple', ...)`.

## Configuration

All settings come from environment variables or `.env` (environment wins). See
[`.env.example`](.env.example) for the full list.

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://rika:change-me@127.0.0.1:5432/rika` | Async PostgreSQL DSN |
| `REDIS_URL` | `redis://127.0.0.1:6379/0` | Celery broker and cache |
| `CHAT_BASE_URL` / `CHAT_MODEL_NAME` | `:8080` | Chat model server |
| `EMBEDDING_BASE_URL` / `EMBEDDING_MODEL_NAME` | `:8081` | Embedding server |
| `EMBEDDING_DIMENSION` | `1024` | Must match the model's output and the vector column |
| `EMBEDDING_BATCH_SIZE` | `16` | Chunks embedded per request |
| `EMBEDDING_TIMEOUT` | `120` | Seconds allowed per embedding batch |
| `STORAGE_ROOT` | `storage` | Uploads, extracted text, temp, backups |
| `MAX_UPLOAD_MB` | `100` | Per-file upload limit |
| `MAX_ARCHIVE_FILES` / `MAX_ARCHIVE_EXPANDED_MB` | `5000` / `1000` | ZIP safety limits |
| `CHUNK_SIZE_CHARS` / `CHUNK_OVERLAP_CHARS` | `1200` / `200` | Chunk window and overlap |

`POSTGRES_*` in `.env` also configures the Compose containers; keep them in sync
with `DATABASE_URL`.

## Operator CLI

Run from `backend/`:

```powershell
..\.venv\Scripts\python.exe -m app.cli check-config   # effective settings, passwords masked
..\.venv\Scripts\python.exe -m app.cli check-models   # model servers + embedding dimension
..\.venv\Scripts\python.exe -m app.cli check-worker   # enqueue rika.ping and wait for a result
```

`check-models` prints the embedding model's actual output dimension. It must
equal `EMBEDDING_DIMENSION` and the width written into migration `0002`; a
mismatch is reported at startup, refused by the ingestion pipeline, and cannot
be mixed in one index.

## Model servers

`llama-server` exposes an OpenAI-compatible API (`/v1/models`,
`/v1/embeddings`, `/v1/chat/completions`), which is what the client targets.
Rika runs two instances: chat on `:8080`, embeddings on `:8081`.

| Role | Model | Quantisation | Placement |
| --- | --- | --- | --- |
| Chat | Qwen3-4B-Instruct-2507 | Q4_K_M (~2.4 GB) | GPU, 4096-token context |
| Embeddings | Qwen3-Embedding-0.6B | Q8_0 (~610 MB) | CPU, so the GPU stays free |

The chat model fits a 4 GB card together with its KV cache (about 3.2 GB in
use); embeddings are a 0.6B model and do not need the GPU. On a larger card,
change `--n-gpu-layers 0` in `scripts\llama-local.ps1` for the embedding server.
The chat model is the instruct tune, so answers arrive in `message.content`;
the base Qwen3-4B returns its text in `reasoning_content` instead. Any Qwen3
4B GGUF works as a drop-in file in `models\llm`.

### Install (once)

```powershell
# llama.cpp prebuilt Windows binaries, plus the CUDA runtime that ships as a
# separate zip: no installer, no CUDA toolkit, no admin rights
curl.exe -L -o .tools\llama.zip https://github.com/ggml-org/llama.cpp/releases/download/b12212/llama-b12212-bin-win-cuda-12.4-x64.zip
curl.exe -L -o .tools\cudart.zip https://github.com/ggml-org/llama.cpp/releases/download/b12212/cudart-llama-bin-win-cuda-12.4-x64.zip
powershell -Command "Expand-Archive .tools\llama.zip -DestinationPath .tools\llama -Force; Expand-Archive .tools\cudart.zip -DestinationPath .tools\llama -Force"

# models (GGUF, git-ignored)
New-Item -ItemType Directory -Force models\llm, models\embeddings | Out-Null
curl.exe -L -o models\embeddings\Qwen3-Embedding-0.6B-Q8_0.gguf https://huggingface.co/Qwen/Qwen3-Embedding-0.6B-GGUF/resolve/main/Qwen3-Embedding-0.6B-Q8_0.gguf
curl.exe -L -o models\llm\Qwen3-4B-Instruct-2507-Q4_K_M.gguf https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/main/Qwen3-4B-Instruct-2507-Q4_K_M.gguf
```

The `cudart-` zip bundles the CUDA runtime, so no CUDA toolkit is installed; a
`llama-b*-bin-win-vulkan-x64` or `-cpu-x64` build is a drop-in replacement if
the GPU is unavailable. If llama.cpp already lives elsewhere, copy its `*.exe`
and `*.dll` into `.tools\llama` and keep `.env` unchanged.

Any GGUF works: the script loads the first `*.gguf` it finds in each folder.

### Run

```powershell
.\scripts\llama-local.ps1 -Action start     # both servers, waits until they answer
.\scripts\llama-local.ps1 -Action status
.\scripts\llama-local.ps1 -Action stop
```

`start` picks the discrete GPU from `llama-server --list-devices` (override with
`-Device CUDA0`; the lower its free memory, the lower `-ChatContext` should be),
launches both servers detached with logs in `.tools\llama-logs\`, and waits for
`/v1/models`. Each server's `--alias` is the configured model name, so readiness
and `check-models` see exactly what `.env` expects. `start.ps1` and `setup.ps1`
start the servers automatically when they are installed, and `stop.ps1` stops
them unless `-KeepInfrastructure` is given.

Verify the wiring:

```powershell
cd backend; ..\.venv\Scripts\python.exe -m app.cli check-models
curl.exe http://127.0.0.1:8000/health/ready
```

`check-models` probes both servers, generates one probe embedding and prints its
dimension. Set that value as `EMBEDDING_DIMENSION` in `.env` — ingestion refuses
to store vectors that do not match the column width. Qwen3-Embedding-0.6B
returns **1024**, and the repository's `.env` is already set to that value.
With both servers up, `/health/ready` reports `ready` (all four checks `ok`).

## Layout

```
backend/app/
  main.py              FastAPI app factory, lifespan, error handlers
  config.py            pydantic-settings
  cli.py               check-config / check-models / check-worker
  api/routes/          HTTP routes (health, projects, documents, uploads, jobs, search)
  api/v1/              versioned API router
  core/                logging, errors, middleware, constants
  database/            async engine, session, models, Alembic migrations
  ingestion/           formats, parsers, chunking, embeddings, archive safety, pipeline
  code_intelligence/   Tree-sitter access, symbols, dependencies, symbol-aware chunking
  retrieval/           vector/keyword search, metadata filters, RRF fusion, metrics
  llm/                 llama-server client
  services/            project, document, upload, job and retrieval services; system probes
  workers/             Celery app + tasks
backend/tests/
backend/evaluation/    curated retrieval cases and the baseline runner
docker/postgres/       pgvector init script
scripts/               setup / start / stop / migrate / backup / restore / postgres-local / redis-local
docs/                  project plan
```

## Tests

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest
```

The API tests build the same models on in-memory SQLite (`aiosqlite`), so CRUD,
uploads, validation, project-isolation and retrieval checks run without any
infrastructure. Queueing is stubbed, the ingestion pipeline is driven directly
and the embedding client is faked, so no worker, broker or model server is
needed. Parser tests build real PDF, DOCX, PPTX and XLSX files in a temporary
directory, and code-intelligence tests cover symbol ranges, parents, routes,
imports and the symbol-aware chunker. Retrieval tests cover RRF fusion and
deduplication, every metadata filter, project scope, query-vector width
refusal and the evaluation metrics. The health tests assert that probes fail
*gracefully* and that readiness maps critical failures to 503.

SQLite cannot prove pgvector, JSONB or database-level cascades, so the same
tests can run against a migrated PostgreSQL database. Point
`RIKA_TEST_DATABASE_URL` at one that `alembic upgrade head` has prepared; the
fixtures then use those tables and truncate them between tests instead of
building a schema with `create_all`:

```powershell
cd backend
$env:RIKA_TEST_DATABASE_URL = "postgresql+asyncpg://rika:change-me@127.0.0.1:5432/rika"
..\.venv\Scripts\python.exe -m pytest
```

Against PostgreSQL the retrieval tests exercise the real pgvector distance
operator, JSONB filters and the generated `search_vector` column rather than
the SQLite fallback.

The migration also compiles to plain SQL, without a server:

```powershell
cd backend
..\.venv\Scripts\python.exe -m alembic upgrade head --sql
```

## Phase status

| Phase | State |
|---|---|
| 1 — Foundation | Done: config, logging, health, Celery, Compose, scripts |
| 2 — Database and projects | Done: models, initial migration, project CRUD, document metadata |
| 3 — Uploads and ingestion | Done: uploads, archive safety, parsing, chunking, jobs, progress |
| 4 — Document parsing | Done: PDF pages, DOCX sections/tables, PPTX slides, XLSX sheets, Markdown/HTML sections; OCR still deferred |
| 5 — Code intelligence | Done: Tree-sitter symbols, routes, imports, parent links and symbol-aware chunking |
| 6 — Chunking and embeddings | Done: batched embeddings, 1024-dim `vector` column, HNSW index, model identity per chunk |
| 7 — Retrieval | Done: pgvector + full-text search, metadata filters, RRF fusion, citations, evaluation baseline |
| 8 — RAG and answer generation | Planned |
| 9 — Frontend | Planned |
| 10–12 — Intelligence, hardening, packaging | Planned |

## Troubleshooting

- **`docker: command not found`** — install Docker Desktop and run
  `docker compose up -d`, or use the portable cluster: `postgres-local.ps1
  -Action init` then `-Action start`.
- **`RIKA_TEST_DATABASE_URL points at a database without the schema`** — run
  `alembic upgrade head` against that database first.
- **Search fails mentioning `search_vector`** — the database predates migration
  `0003`; run `.\scripts\migrate.ps1` (or `alembic upgrade head`).
- **Readiness says `unavailable` with `postgres`/`redis` errors** — containers
  are not running, or `DATABASE_URL` disagrees with `POSTGRES_*`. Without Docker,
  start the portable services first: `postgres-local.ps1 -Action start` and
  `redis-local.ps1 -Action start`.
- **Readiness says `degraded`** — PostgreSQL and Redis are fine; the model
  servers on :8080/:8081 are not answering. Start or restart them with
  `.\scripts\llama-local.ps1 -Action start`, and check
  `.tools\llama-logs\chat.log` / `embedding.log` if they fail to come up.
- **Uploads succeed but jobs stay `queued`** — no Celery worker is running. Start
  one in `backend/` with `python -m celery -A app.workers.celery_app worker
  --loglevel=INFO`, then `POST /jobs/{id}/retry` for any job already queued.
- **Celery exits immediately on Windows** — the bundled `celery_app.py` selects
  the `solo` pool on Windows because `fork` is unavailable. Do not override it
  with `--pool=prefork`.
- **`check-models` fails** — no model server is listening on the configured
  port, or the GGUF is not loadable by your llama.cpp build. The log names the
  failing file; a truncated GGUF fails to load, so re-download it.
- **The chat server exits right after starting on a 4 GB card** — the context
  does not fit next to the model. Start with a smaller `-ChatContext` (for
  example `2048`), then raise it until VRAM is the limit.
