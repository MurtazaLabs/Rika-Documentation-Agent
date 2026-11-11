"""Response models for the project intelligence API (§13)."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


class Totals(BaseModel):
    files: int
    code_files: int
    symbols: int
    languages: int


class LanguageStat(BaseModel):
    language: str
    files: int
    symbols: int
    bytes: int


class DirectoryStat(BaseModel):
    path: str
    files: int
    symbols: int
    bytes: int


class FrameworkHit(BaseModel):
    name: str
    evidence: list[str]
    files: int


class EntryPointRead(BaseModel):
    path: str
    kind: str
    detail: str | None = None


class ConfigFileRead(BaseModel):
    path: str
    kind: str


class ImportantModuleRead(BaseModel):
    path: str
    layer: str
    symbols: int
    imported_by: int
    score: int


class PackageRead(BaseModel):
    name: str
    files: int


class DependencyRead(BaseModel):
    internal_edges: int
    # Imports that name the project's own package but point at files outside
    # the index; reported separately so a partial upload is never read as a bug.
    unresolved_edges: int = 0
    external_edges: int
    packages: list[PackageRead]


class OverviewRead(BaseModel):
    project_id: uuid.UUID
    name: str
    description: str | None
    totals: Totals
    languages: list[LanguageStat]
    directories: list[DirectoryStat]
    frameworks: list[FrameworkHit]
    entry_points: list[EntryPointRead]
    config_files: list[ConfigFileRead]
    important_modules: list[ImportantModuleRead]
    dependencies: DependencyRead


class LayerRead(BaseModel):
    name: str
    side: str
    files: int
    symbols: int
    imports_out: int
    imported_by: int


class LayerEdgeRead(BaseModel):
    source: str
    target: str
    count: int


class TableRead(BaseModel):
    table: str
    model: str | None
    file_path: str
    line: int
    columns: list[str]
    references: list[str]


class DatabaseRead(BaseModel):
    tables: list[TableRead]


class RequestFlowRead(BaseModel):
    method: str
    path: str
    handler: str
    file_path: str
    line: int
    framework: str | None
    imports: list[str]


class ResponsibilityModuleRead(BaseModel):
    path: str
    doc: str | None
    symbols: int
    side: str


class ResponsibilityRead(BaseModel):
    layer: str
    side: str
    modules: list[ResponsibilityModuleRead]


class ArchitectureRead(BaseModel):
    project_id: uuid.UUID
    layers: list[LayerRead]
    edges: list[LayerEdgeRead]
    database: DatabaseRead
    request_flows: list[RequestFlowRead]
    responsibilities: list[ResponsibilityRead]


class SymbolHitRead(BaseModel):
    id: uuid.UUID
    name: str
    qualified_name: str
    symbol_type: str
    path: str
    language: str | None
    start_line: int
    end_line: int
    signature: str | None
    doc: str | None


class ImportEdgeRead(BaseModel):
    reference: str
    dependency_type: str | None = None
    resolved_path: str | None = None
    external: bool | None = None


class ReferenceRead(BaseModel):
    path: str
    line: int
    snippet: str


class SymbolDetailRead(BaseModel):
    symbol: SymbolHitRead
    doc: str | None
    signature: str | None
    definition: str
    imports: list[ImportEdgeRead]
    imported_by: list[str]
    related_symbols: list[SymbolHitRead]
    references: list[ReferenceRead]


class ImportAnalysisRead(BaseModel):
    path: str
    imports: list[ImportEdgeRead]
    imported_by: list[str]
    symbols: list[SymbolHitRead]


class DocFindingRead(BaseModel):
    kind: str
    severity: str
    confirmed: bool
    message: str
    details: dict[str, Any]


class DocsReportRead(BaseModel):
    project_id: uuid.UUID
    readme: str | None
    routes: dict[str, int]
    findings: list[DocFindingRead]


class FindingRead(BaseModel):
    kind: str
    confidence: str
    severity: str
    message: str
    details: dict[str, Any]


class FindingsReportRead(BaseModel):
    project_id: uuid.UUID
    summary: dict[str, Any]
    findings: list[FindingRead] = Field(default_factory=list)
