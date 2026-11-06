"""Faze 3: FastAPI app s endpointem /query.

Tenka HTTP vrstva nad query.cypher_chain.answer_question. UI (Streamlit) i
pripadni dalsi klienti volaji /query a dostanou odpoved + vygenerovany Cypher
+ podkladove radky (kvuli overitelnosti, podminka ARES).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from ares_insight.query import cypher_chain

logger = logging.getLogger(__name__)

app = FastAPI(title="ARES Insight API")


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    answer: str
    cypher: str | None = None
    rows: list[dict[str, Any]] = []
    path: str | None = None  # "cypher" | "semantic" - kterou cestou se odpovedelo


class StatsResponse(BaseModel):
    companies: int
    persons: int
    addresses: int
    ingested_at: str | None = None  # ISO date of the last ingest (None if unknown)
    semantic_enabled: bool  # lets the UI hide examples that need the vector path


class SubgraphRequest(BaseModel):
    icos: list[str] = []


class SubgraphResponse(BaseModel):
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/warmup")
def warmup():
    """Lehky keep-alive: tukne na Neo4j (RETURN 1) bez LLM - drzi AuraDB Free
    vzhuru (paklize se vola pravidelne) a probudi Render. Zadne tokeny."""
    import time

    from ares_insight.graph import connection

    # Retry: right after a Render cold start the first Bolt/TLS connection to
    # Aura sometimes fails transiently (seen as SSLEOFError). One failed attempt
    # should not make the daily keep-alive look like an outage.
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            connection.run("RETURN 1 AS ok")
            break
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            connection.close_driver()  # drop possibly broken pooled connections
            time.sleep(2 * (attempt + 1))
    else:
        raise HTTPException(status_code=503, detail=f"db: {last_exc}") from last_exc
    return {"status": "ok", "db": "ok"}


@app.get("/stats", response_model=StatsResponse)
def stats() -> StatsResponse:
    """Live dataset size for the UI info text (no LLM, one cheap Cypher query)."""
    from ares_insight.config import settings
    from ares_insight.graph import connection

    # COUNT {} subqueries count each label independently in a single round trip.
    # OPTIONAL MATCH keeps the row even when no :Meta node exists yet
    # (ingested_at is then null). A pattern comprehension can't be used here:
    # Cypher requires it to contain a relationship.
    query = (
        "OPTIONAL MATCH (m:Meta {key: 'ingest'}) "
        "RETURN COUNT { (:Company) } AS companies, "
        "COUNT { (:Person) } AS persons, "
        "COUNT { (:Address) } AS addresses, "
        "m.ingested_at AS ingested_at"
    )
    try:
        row = connection.run(query)[0]
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"db: {exc}") from exc
    return StatsResponse(**row, semantic_enabled=settings.enable_semantic)


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest) -> QueryResponse:
    question = (req.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Prazdny dotaz.")
    try:
        result = cypher_chain.answer_question(question)
    except Exception as exc:  # noqa: BLE001 - chybu prevedeme na HTTP 500
        logger.exception("Dotaz selhal")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return QueryResponse(
        answer=result.get("answer", ""),
        cypher=result.get("cypher") or None,
        rows=result.get("rows", []),
        path=result.get("path"),
    )


@app.post("/subgraph", response_model=SubgraphResponse)
def subgraph(req: SubgraphRequest) -> SubgraphResponse:
    from ares_insight.query import subgraph as sg

    try:
        data = sg.fetch_subgraph(req.icos)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Subgraph selhal")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return SubgraphResponse(nodes=data["nodes"], edges=data["edges"])
