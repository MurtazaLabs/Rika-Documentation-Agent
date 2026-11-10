-- Runs once, on first initialisation of the Rika database.
-- The vector extension must exist before the migrations create
-- document_chunks.embedding; migration 0002 fixes that column at vector(1024)
-- and adds its HNSW index, matching EMBEDDING_DIMENSION in .env.
CREATE EXTENSION IF NOT EXISTS vector;
