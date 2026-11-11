"""Classify a file into an architecture layer.

The mapping is deliberately path-driven: in a repository that keeps API,
service and persistence modules in named packages this is exact, and for other
layouts it degrades to ``Other`` instead of guessing.
"""

from __future__ import annotations

LAYERS: dict[str, tuple[str, ...]] = {
    "API routes": ("api/routes", "apis", "controllers", "handlers"),
    "API schemas": ("api/schemas", "schemas", "dtos"),
    "Services": ("services",),
    "Database": ("database/models", "models", "entities", "repositories"),
    "Migrations": ("migrations", "alembic"),
    "Ingestion": ("ingestion", "parsers", "processing"),
    "Retrieval": ("retrieval", "search", "indexing"),
    "RAG": ("rag", "prompts", "llm/rag"),
    "Code intelligence": ("code_intelligence", "codeintel", "analysis"),
    "Workers": ("workers", "tasks", "jobs"),
    "Core": ("core", "config", "settings", "utils", "common", "lib"),
    "UI pages": ("src/app", "pages", "app/routes"),
    "UI components": ("components",),
    "UI client": ("hooks", "lib/api"),
    "Tests": ("tests", "test", "__tests__", "spec"),
    "Scripts": ("scripts",),
}

SIDES = {
    "UI pages": "frontend",
    "UI components": "frontend",
    "UI client": "frontend",
}


def layer_for(path: str) -> tuple[str, str]:
    """Return ``(layer, side)`` for a project-relative path."""
    lowered = path.lower()
    for layer, fragments in LAYERS.items():
        for fragment in fragments:
            if f"/{fragment}/" in f"/{lowered}/":
                side = SIDES.get(layer)
                if side is None:
                    side = "frontend" if lowered.startswith("frontend/") else "backend"
                return layer, side
    if lowered.startswith("frontend/"):
        return "Other", "frontend"
    if lowered.startswith(("backend/", "app/", "src/")):
        return "Other", "backend"
    return "Other", "other"
