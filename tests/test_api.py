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


def test_stats(monkeypatch):
    from ares_insight.graph import connection

    fake = [{"companies": 2363, "persons": 3481, "addresses": 1226, "ingested_at": "2026-11-05"}]
    monkeypatch.setattr(connection, "run", lambda *a, **k: fake)

    res = main.stats()
    assert res.companies == 2363
    assert res.ingested_at == "2026-11-05"
    assert isinstance(res.semantic_enabled, bool)


def test_stats_db_down(monkeypatch):
    from ares_insight.graph import connection

    def boom(*a, **k):
        raise RuntimeError("no db")

    monkeypatch.setattr(connection, "run", boom)
    with pytest.raises(HTTPException) as exc:
        main.stats()
    assert exc.value.status_code == 503


def test_warmup_retries_transient_error(monkeypatch):
    from ares_insight.graph import connection

    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("SSLEOFError")
        return [{"ok": 1}]

    monkeypatch.setattr(connection, "run", flaky)
    monkeypatch.setattr(connection, "close_driver", lambda: None)
    monkeypatch.setattr("time.sleep", lambda s: None)
    assert main.warmup()["db"] == "ok"
    assert calls["n"] == 2
