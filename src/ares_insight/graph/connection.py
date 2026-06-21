"""Tenky wrapper nad Neo4j driverem."""

from neo4j import Driver, GraphDatabase

from ares_insight.config import settings

_driver: Driver | None = None


def get_driver() -> Driver:
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
    return _driver


def close_driver() -> None:
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None


def run(query: str, **params) -> list[dict]:
    """Spusti Cypher dotaz a vrati zaznamy jako list dictu."""
    with get_driver().session(database=settings.neo4j_database) as session:
        result = session.run(query, **params)
        return [record.data() for record in result]


def apply_schema() -> None:
    """Vytvori constraints a indexy. Idempotentni. Spustit jednou (Faze 1)."""
    from ares_insight.graph.schema import SCHEMA_STATEMENTS

    for stmt in SCHEMA_STATEMENTS:
        run(stmt)
