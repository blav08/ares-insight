"""Faze 5: extrakce podgrafu kolem firem pro vizualizaci v UI.

Pro zadana ICO vytahne z Neo4j okoli (statutari + sidlo + sdilene adresy) a
vrati uzly/hrany ve formatu nezavislem na vizualizacni knihovne:
  {"nodes": [{id, label, type}], "edges": [{source, target, label}]}
"""

from __future__ import annotations

from ares_insight.graph import connection

_MAX_ICOS = 12


def fetch_subgraph(icos: list[str]) -> dict:
    """Vrati podgraf (uzly + hrany) kolem zadanych firem."""
    icos = [i for i in (icos or []) if i][:_MAX_ICOS]
    if not icos:
        return {"nodes": [], "edges": []}

    rows = connection.run(
        """
        UNWIND $icos AS ico
        MATCH (c:Company {ico: ico})
        OPTIONAL MATCH (p:Person)-[:DIRECTOR_OF]->(c)
        OPTIONAL MATCH (c)-[:REGISTERED_AT]->(a:Address)
        RETURN c.ico AS ico, c.name AS name,
               collect(DISTINCT {key: p.person_key, name: p.name}) AS people,
               a.address_key AS addr_key, a.text AS addr_text
        """,
        icos=icos,
    )

    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def add(node_id: str, label: str, ntype: str) -> None:
        if node_id and node_id not in nodes:
            nodes[node_id] = {"id": node_id, "label": label or node_id, "type": ntype}

    for r in rows:
        cid = f"c:{r['ico']}"
        add(cid, r["name"] or r["ico"], "Company")
        for person in r["people"]:
            if not person or not person.get("key"):
                continue
            pid = f"p:{person['key']}"
            add(pid, person.get("name") or "?", "Person")
            edges.append({"source": pid, "target": cid, "label": "STATUTAR"})
        if r["addr_key"]:
            aid = f"a:{r['addr_key']}"
            add(aid, r["addr_text"] or "adresa", "Address")
            edges.append({"source": cid, "target": aid, "label": "SIDLO"})

    return {"nodes": list(nodes.values()), "edges": edges}
