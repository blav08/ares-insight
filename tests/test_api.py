"""Offline testy FastAPI vrstvy. Volame handlery primo (bez HTTP/sit/LLM),
answer_question je zmockovany."""

import pytest
from fastapi import HTTPException

from ares_insight.api import main
from ares_insight.api.main import QueryRequest


def test_health():
    assert main.health() == {"status": "ok"}


def test_query_ok(monkeypatch):
    def fake_answer(question: str) -> dict:
        return {
            "answer": "V databazi jsou 2 firmy.",
            "cypher": "MATCH (c:Company) RETURN count(c)",
            "rows": [{"pocet": 2}],
        }

    monkeypatch.setattr(main.cypher_chain, "answer_question", fake_answer)
    resp = main.query(QueryRequest(question="Kolik firem?"))
    assert resp.answer.startswith("V databazi")
    assert resp.cypher.startswith("MATCH")
    assert resp.rows == [{"pocet": 2}]


def test_query_empty_question():
    with pytest.raises(HTTPException) as exc:
        main.query(QueryRequest(question="   "))
    assert exc.value.status_code == 400


def test_query_wraps_errors(monkeypatch):
    def boom(question: str) -> dict:
        raise RuntimeError("neo4j down")

    monkeypatch.setattr(main.cypher_chain, "answer_question", boom)
    with pytest.raises(HTTPException) as exc:
        main.query(QueryRequest(question="cokoliv"))
    assert exc.value.status_code == 500
