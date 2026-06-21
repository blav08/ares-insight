"""Offline test extrakce podgrafu (Faze 5). connection.run je zmockovany."""

from ares_insight.query import subgraph


def test_fetch_subgraph_dedup(monkeypatch):
    fake_rows = [
        {"ico": "1", "name": "A a.s.",
         "people": [{"key": "novak|jan", "name": "Jan Novak"}],
         "addr_key": "am:5", "addr_text": "Praha 1"},
        {"ico": "2", "name": "B a.s.",
         "people": [{"key": "novak|jan", "name": "Jan Novak"}],
         "addr_key": "am:5", "addr_text": "Praha 1"},
    ]
    monkeypatch.setattr(subgraph.connection, "run", lambda *a, **k: fake_rows)
    g = subgraph.fetch_subgraph(["1", "2"])
    # 2 firmy + 1 osoba (slita) + 1 adresa (slita) = 4 uzly
    assert len(g["nodes"]) == 4
    assert sorted(n["type"] for n in g["nodes"]) == [
        "Address", "Company", "Company", "Person"
    ]
    # 2x STATUTAR + 2x SIDLO
    assert len(g["edges"]) == 4


def test_fetch_subgraph_empty():
    assert subgraph.fetch_subgraph([]) == {"nodes": [], "edges": []}
