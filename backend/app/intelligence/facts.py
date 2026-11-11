"""Load one project's indexed facts and resolve its internal module graph.

Everything the intelligence layer reports is derived from these rows, so this
module exists to make the rest of the package pure: no session, no queries, and
cheap to reuse across several analyses in one request.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Document, DocumentChunk, ProjectDependency, ProjectSymbol
from app.services.project_service import get_project

# One very large file should not decide how much memory an analysis request
# uses; the tail beyond this is irrelevant to structure and configuration checks.
MAX_FILE_LINES = 8000


@dataclass(slots=True)
class SymbolFact:
    id: uuid.UUID
    name: str
    qualified_name: str
    symbol_type: str
    start_line: int
    end_line: int
    metadata: dict[str, Any]

    @property
    def signature(self) -> str | None:
        value = self.metadata.get("signature")
        return str(value) if value else None

    @property
    def doc(self) -> str | None:
        value = self.metadata.get("doc")
        return str(value) if value else None

    @property
    def parent(self) -> str | None:
        value = self.metadata.get("parent")
        return str(value) if value else None


@dataclass(slots=True)
class ImportFact:
    reference: str
    dependency_type: str


@dataclass(slots=True)
class FileFacts:
    document_id: uuid.UUID
    path: str
    file_type: str
    language: str | None
    size: int
    # Rebuilt by line number, because chunk text overlaps and splitting the
    # stored chunks on newlines would shift every line after the first chunk.
    lines: list[str] = field(default_factory=list)
    symbols: list[SymbolFact] = field(default_factory=list)
    imports: list[ImportFact] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    def slice_lines(self, start: int, end: int) -> str:
        """Text between two 1-based, inclusive line numbers."""
        if not self.lines:
            return ""
        first = max(1, start)
        last = min(len(self.lines), end)
        return "\n".join(self.lines[first - 1:last])

    @property
    def name(self) -> str:
        return self.path.rsplit("/", 1)[-1]

    @property
    def directory(self) -> str:
        return self.path.rsplit("/", 1)[0] if "/" in self.path else ""

    @property
    def is_code(self) -> bool:
        return self.file_type in {"code"} or bool(self.language)


@dataclass(slots=True)
class ProjectFacts:
    project_id: uuid.UUID
    name: str
    description: str | None
    files: list[FileFacts]

    @property
    def code_files(self) -> list[FileFacts]:
        return [file for file in self.files if file.is_code]

    @property
    def symbols(self) -> list[SymbolFact]:
        return [symbol for file in self.files for symbol in file.symbols]

    def by_path(self, path: str) -> FileFacts | None:
        return next((file for file in self.files if file.path == path), None)


async def load_facts(session: AsyncSession, project_id: uuid.UUID) -> ProjectFacts:
    """Read a project's documents, symbols, imports and chunk text in four queries."""
    project = await get_project(session, project_id)

    documents = list(
        await session.scalars(
            select(Document)
            .where(Document.project_id == project_id)
            .order_by(Document.original_path)
        )
    )
    files = {
        document.id: FileFacts(
            document_id=document.id,
            path=document.original_path,
            file_type=document.file_type,
            language=None,
            size=document.size,
        )
        for document in documents
    }
    if not files:
        return ProjectFacts(project_id=project.id, name=project.name,
                            description=project.description, files=[])

    chunks = list(
        await session.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.project_id == project_id)
            .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
        )
    )
    grouped: dict[uuid.UUID, list[DocumentChunk]] = {}
    for chunk in chunks:
        file = files.get(chunk.document_id)
        if file is None:
            continue
        if file.language is None:
            file.language = chunk.language
        grouped.setdefault(chunk.document_id, []).append(chunk)
    for document_id, document_chunks in grouped.items():
        files[document_id].lines = _assemble_lines(document_chunks)

    symbols = list(
        await session.scalars(
            select(ProjectSymbol)
            .where(ProjectSymbol.project_id == project_id)
            .order_by(ProjectSymbol.document_id, ProjectSymbol.start_line)
        )
    )
    for symbol in symbols:
        file = files.get(symbol.document_id)
        if file is None:
            continue
        file.symbols.append(
            SymbolFact(
                id=symbol.id,
                name=symbol.symbol_name,
                qualified_name=symbol.qualified_name or symbol.symbol_name,
                symbol_type=symbol.symbol_type,
                start_line=symbol.start_line,
                end_line=symbol.end_line,
                metadata=dict(symbol.metadata_ or {}),
            )
        )

    dependencies = list(
        await session.scalars(
            select(ProjectDependency).where(ProjectDependency.project_id == project_id)
        )
    )
    for dependency in dependencies:
        file = files.get(dependency.source_document_id)
        if file is None:
            continue
        file.imports.append(
            ImportFact(
                reference=dependency.target_reference,
                dependency_type=dependency.dependency_type,
            )
        )

    return ProjectFacts(
        project_id=project.id,
        name=project.name,
        description=project.description,
        files=list(files.values()),
    )


class ModuleResolver:
    """Map an import reference to another file in the same project, or to a package.

    Import graphs are stored exactly as written, so this deliberately accepts
    several spellings: Python dotted modules, relative JavaScript specifiers,
    ``@/`` aliases and repository-rooted paths.
    """

    def __init__(self, files: list[FileFacts]) -> None:
        self._by_dotted: list[tuple[str, str]] = []
        self._paths = {file.path for file in files}
        for file in files:
            if not file.is_code:
                continue
            dotted = _dotted(file.path)
            if dotted:
                self._by_dotted.append((dotted, file.path))
        # Longest first so ``app.core.config`` wins over ``config``.
        self._by_dotted.sort(key=lambda item: len(item[0]), reverse=True)

    def resolve(self, source: FileFacts, reference: str) -> str | None:
        """Return the project-relative path an import points at, if any."""
        candidate = _normalise(source, reference)
        if not candidate:
            return None
        if "." in candidate and candidate in self._paths:
            return candidate
        dotted = candidate.replace("/", ".").strip(".")
        for module, path in self._by_dotted:
            if dotted == module or dotted.endswith("." + module):
                return path
            if module.endswith("." + dotted) and dotted.count(".") >= 1:
                return path
        return None

    def looks_internal(self, reference: str) -> bool:
        """Whether an unresolved import still claims to be project code."""
        text = reference.strip().strip("'\";")
        if text.startswith((".", "@/")):
            return True
        return False


def _assemble_lines(chunks: list[DocumentChunk]) -> list[str]:
    """Rebuild a file from its chunks, keyed by the line numbers they stored.

    Re-indexing overlaps neighbouring chunks, so the same line can appear twice.
    The first occurrence wins and the result is line-addressable again.
    """
    positions: dict[int, str] = {}
    orphans: list[str] = []
    highest = 0
    for chunk in chunks:
        if chunk.start_line is None:
            orphans.append(chunk.content)
            continue
        for offset, line in enumerate(chunk.content.split("\n")):
            number = chunk.start_line + offset
            if number > MAX_FILE_LINES:
                break
            positions.setdefault(number, line)
            highest = max(highest, number)
    if not positions:
        return "".join(orphans).split("\n")[:MAX_FILE_LINES]
    return [positions.get(number, "") for number in range(1, highest + 1)]


def _dotted(path: str) -> str:
    name = path
    for suffix in (".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    if name.endswith("/__init__") or name.endswith("/index"):
        name = name.rsplit("/", 1)[0]
    return name.replace("/", ".")


def _normalise(source: FileFacts, reference: str) -> str:
    text = reference.strip().strip("'\";").strip()
    if not text:
        return ""
    # ``from x import y`` style leftovers are not stored, but be tolerant.
    if text.startswith("from "):
        text = text[5:].split(" import ")[0].strip()
    text = text.replace("\\", "/")

    if text.startswith("@/"):
        return text[2:]
    if text.startswith("./") or text.startswith("../"):
        base = source.directory.split("/") if source.directory else []
        parts = list(base)
        for part in text.split("/"):
            if part in {"", "."}:
                continue
            if part == "..":
                if parts:
                    parts.pop()
                continue
            parts.append(part)
        return "/".join(parts)
    return text
