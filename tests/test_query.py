"""Offline testy Faze 2: formatovani zdroju + read-only guard. Zadna sit/LLM."""

from ares_insight.query.answer import format_sources
from ares_insight.query.cypher_chain import _strip_fences, is_read_only


def test_format_sources_basic():
    rows = [
        {"ico": "1", "name": "A a.s."},
        {"ico": "2", "name": "B a.s."},
    ]
    md = format_sources(rows)
    assert "| ico | name |" in md
    assert "| 1 | A a.s. |" in md
    assert "| 2 | B a.s. |" in md


def test_format_sources_empty():
    assert "Zadna" in format_sources([])


def test_format_sources_list_values():
    md = format_sources([{"nace": ["62", "63"]}])
    assert "62, 63" in md


def test_read_only_guard_allows_match():
    assert is_read_only("MATCH (c:Company) RETURN c LIMIT 5")


def test_read_only_guard_blocks_writes():
    assert not is_read_only("MATCH (c:Company) DETACH DELETE c")
    assert not is_read_only("CREATE (c:Company {ico:'x'})")
    assert not is_read_only("MATCH (c:Company) SET c.name='x'")
    assert not is_read_only("MERGE (c:Company {ico:'1'})")


def test_strip_fences():
    assert _strip_fences("```cypher\nMATCH (n) RETURN n\n```") == "MATCH (n) RETURN n"
    assert _strip_fences("MATCH (n) RETURN n") == "MATCH (n) RETURN n"
