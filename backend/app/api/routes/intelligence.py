"""Project intelligence endpoints (§13): overview, architecture and analyses.

All responses are derived from the stored index, so they are cheap enough to
recompute per request and never call a model. Defects carry an explicit
confidence: ``confirmed`` when the index settles the question, ``possible`` when
a human still needs to look.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.intelligence import (
    ArchitectureRead,
    DocsReportRead,
    FindingsReportRead,
    ImportAnalysisRead,
    OverviewRead,
    RequestFlowRead,
    SymbolDetailRead,
    SymbolHitRead,
)
from app.database.session import get_session
from app.intelligence import architecture, code, docs_check, findings, overview
from app.intelligence.facts import load_facts

router = APIRouter(prefix="/projects/{project_id}/intelligence", tags=["intelligence"])


@router.get(
    "/overview",
    response_model=OverviewRead,
    summary="Project overview",
    description=(
        "Languages, main directories, detected frameworks, entry points, "
        "configuration files, the most depended-on modules and the import split "
        "between internal modules and external packages."
    ),
)
async def project_overview(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> OverviewRead:
    return OverviewRead(**overview.overview(await load_facts(session, project_id)))


@router.get(
    "/architecture",
    response_model=ArchitectureRead,
    summary="Architecture analysis",
    description=(
        "Layers and the import edges between them, ORM tables with columns and "
        "foreign keys, HTTP handlers with the modules they pull in, and what each "
        "layer is responsible for."
    ),
)
async def project_architecture(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ArchitectureRead:
    return ArchitectureRead(
        **architecture.architecture(await load_facts(session, project_id))
    )


@router.get(
    "/routes",
    response_model=list[RequestFlowRead],
    summary="Discover HTTP endpoints",
    description=(
        "Routes extracted from the source for the frameworks the parser "
        "supports, with the mount prefix taken from the file's APIRouter."
    ),
)
async def project_routes(
    project_id: uuid.UUID,
    method: str | None = Query(None, min_length=1, max_length=16),
    session: AsyncSession = Depends(get_session),
) -> list[RequestFlowRead]:
    facts = await load_facts(session, project_id)
    return [RequestFlowRead(**flow) for flow in code.routes(facts, method=method)]


@router.get(
    "/symbols",
    response_model=list[SymbolHitRead],
    summary="Search functions, classes and routes",
    description=(
        "Substring search over symbol names and qualified names, optionally "
        "filtered by symbol type or file path."
    ),
)
async def search_symbols(
    project_id: uuid.UUID,
    q: str | None = Query(None, max_length=200),
    symbol_type: str | None = Query(None, max_length=32),
    path: str | None = Query(None, max_length=500),
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> list[SymbolHitRead]:
    facts = await load_facts(session, project_id)
    hits = code.search_symbols(
        facts, query=q, symbol_type=symbol_type, path=path, limit=limit
    )
    return [SymbolHitRead(**_without_route(hit)) for hit in hits]


@router.get(
    "/symbols/{symbol_id}",
    response_model=SymbolDetailRead,
    summary="Explain one symbol",
    description=(
        "Definition text from the indexed lines, docstring, signature, imports of "
        "its file, importers, sibling symbols and textual references. References "
        "are lexical matches, not a resolved call graph."
    ),
)
async def symbol_detail(
    project_id: uuid.UUID,
    symbol_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> SymbolDetailRead:
    facts = await load_facts(session, project_id)
    detail = code.symbol_detail(facts, symbol_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Symbol not found"
        )
    return SymbolDetailRead(**detail)


@router.get(
    "/imports",
    response_model=ImportAnalysisRead,
    summary="Analyse one file's imports",
    description=(
        "Every stored import of a file, whether it resolves inside the project, "
        "and which other files import this one."
    ),
)
async def import_analysis(
    project_id: uuid.UUID,
    path: str = Query(..., min_length=1, max_length=500),
    session: AsyncSession = Depends(get_session),
) -> ImportAnalysisRead:
    facts = await load_facts(session, project_id)
    result = code.import_analysis(facts, path)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Code file not found"
        )
    return ImportAnalysisRead(**result)


@router.get(
    "/docs",
    response_model=DocsReportRead,
    summary="Compare documentation with the implementation",
    description=(
        "README route tables against discovered routes, documented tables against "
        "ORM tables, .env.example against settings, and markdown links against the "
        "indexed files."
    ),
)
async def docs_comparison(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> DocsReportRead:
    return DocsReportRead(**docs_check.compare(await load_facts(session, project_id)))


@router.get(
    "/findings",
    response_model=FindingsReportRead,
    summary="Investigate possible defects",
    description=(
        "Broken internal imports, classes used without an import, duplicate "
        "implementations, bare excepts, TODO markers and configuration drift. "
        "Each finding is labelled confirmed or possible."
    ),
)
async def bug_investigation(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> FindingsReportRead:
    return FindingsReportRead(
        **findings.investigate(await load_facts(session, project_id))
    )


def _without_route(hit: dict) -> dict:
    """Route rows still carry a label in ``signature``; only keep real signatures."""
    if hit.get("symbol_type") == "route":
        return {**hit, "signature": None, "doc": None}
    return hit
