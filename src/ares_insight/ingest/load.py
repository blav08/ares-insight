"""Faze 1: nacteni entit do Neo4j.

Vse pres MERGE (idempotentni) a davkovane UNWIND kvuli vykonu. Constraints z
graph.schema zaroven zajisti dedup na urovni DB. Na konci se Cypherem odvodi
vztah SHARES_ADDRESS_WITH mezi firmami na stejne adrese.
"""

from __future__ import annotations

import logging

from ares_insight.graph import connection
from ares_insight.graph.schema import (
    ADDRESS,
    COMPANY,
    DIRECTOR_OF,
    PERSON,
    REGISTERED_AT,
    SHARES_ADDRESS_WITH,
)
from ares_insight.ingest.transform import Entities

logger = logging.getLogger(__name__)

_BATCH = 500


def _run_batched(query: str, rows: list[dict], key: str = "rows") -> None:
    for i in range(0, len(rows), _BATCH):
        connection.run(query, **{key: rows[i : i + _BATCH]})


def load(entities: Entities) -> dict[str, int]:
    """Aplikuje schema a upsertuje uzly + vztahy. Vraci statistiky."""
    connection.apply_schema()

    _run_batched(
        f"""
        UNWIND $rows AS r
        MERGE (c:{COMPANY} {{ico: r.ico}})
        SET c.name = r.name,
            c.legal_form = r.legal_form,
            c.founded = r.founded,
            c.nace = r.nace,
            c.address_text = r.address_text
        """,
        entities.companies,
    )

    _run_batched(
        f"""
        UNWIND $rows AS r
        MERGE (p:{PERSON} {{person_key: r.person_key}})
        SET p.name = r.name,
            p.name_norm = r.name_norm,
            p.year_of_birth = r.year_of_birth,
            p.citizenship = r.citizenship
        """,
        entities.persons,
    )

    _run_batched(
        f"""
        UNWIND $rows AS r
        MERGE (a:{ADDRESS} {{address_key: r.address_key}})
        SET a.text = r.text,
            a.municipality = r.municipality,
            a.city_district = r.city_district,
            a.street = r.street,
            a.psc = r.psc,
            a.country = r.country
        """,
        entities.addresses,
    )

    _run_batched(
        f"""
        UNWIND $rows AS r
        MATCH (c:{COMPANY} {{ico: r.ico}})
        MATCH (a:{ADDRESS} {{address_key: r.address_key}})
        MERGE (c)-[:{REGISTERED_AT}]->(a)
        """,
        entities.registered_at,
    )

    _run_batched(
        f"""
        UNWIND $rows AS r
        MATCH (p:{PERSON} {{person_key: r.person_key}})
        MATCH (c:{COMPANY} {{ico: r.ico}})
        MERGE (p)-[d:{DIRECTOR_OF}]->(c)
        SET d.role = r.role, d.since = r.since
        """,
        entities.director_of,
    )

    derive_shared_address()

    stats = {
        "companies": len(entities.companies),
        "persons": len(entities.persons),
        "addresses": len(entities.addresses),
        "registered_at": len(entities.registered_at),
        "director_of": len(entities.director_of),
    }
    logger.info("Load hotovo: %s", stats)
    return stats


def backfill_name_norm() -> int:
    """Doplni p.name_norm na existujicich Person uzlech (migrace bez re-ingestu).

    Pocita se v Pythonu z p.name (fold_name), aby fold diakritiky byl shodny s
    ingestem. Vraci pocet aktualizovanych uzlu.
    """
    from ares_insight.ingest.transform import fold_name

    rows = connection.run(
        f"MATCH (p:{PERSON}) WHERE p.name IS NOT NULL RETURN "
        f"p.person_key AS key, p.name AS name"
    )
    updates = [{"key": r["key"], "norm": fold_name(r["name"])} for r in rows]
    _run_batched(
        f"UNWIND $rows AS r MATCH (p:{PERSON} {{person_key: r.key}}) "
        f"SET p.name_norm = r.norm",
        updates,
    )
    logger.info("Backfill name_norm: %d osob", len(updates))
    return len(updates)


def derive_shared_address() -> None:
    """Odvodi (Company)-[:SHARES_ADDRESS_WITH]-(Company) pro firmy na stejne adrese.

    Nesmerovany vztah modelujeme jednou hranou na dvojici (c1.ico < c2.ico), aby
    nevznikaly duplikaty. Adresy s velkym poctem firem (virtualni sidla) by
    nadelaly kvadraticky moc hran - proto strop na pocet firem na adrese.
    """
    connection.run(
        f"""
        MATCH (a:{ADDRESS})<-[:{REGISTERED_AT}]-(c:{COMPANY})
        WITH a, collect(c) AS firms
        WHERE size(firms) > 1 AND size(firms) <= 50
        UNWIND firms AS c1
        UNWIND firms AS c2
        WITH c1, c2 WHERE c1.ico < c2.ico
        MERGE (c1)-[:{SHARES_ADDRESS_WITH}]-(c2)
        """
    )
