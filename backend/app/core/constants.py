"""Shared constants."""

API_V1_PREFIX = "/api/v1"

REQUEST_ID_HEADER = "X-Request-ID"

# Subdirectories created under STORAGE_ROOT at startup.
STORAGE_SUBDIRECTORIES = ("uploads", "extracted", "temp", "backups")

# Width of the pgvector column, fixed at migration time (0002). It must equal
# EMBEDDING_DIMENSION in .env; check-models reports the model's real output
# size so the two can be compared before anything is written.
EMBEDDING_VECTOR_DIMENSION = 1024

# Dependencies the API cannot serve without. Model servers are reported as
# degraded instead: chat can be unavailable while the dashboard still works.
CRITICAL_DEPENDENCIES = ("postgres", "redis")
