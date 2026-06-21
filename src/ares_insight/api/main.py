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


@app.get("/health")
def health():
    return {"status": "ok"}


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
