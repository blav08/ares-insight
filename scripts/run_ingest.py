"""Entrypoint: spusti celou ingest pipeline (Faze 1).

ARES (vyhledat + VR) -> normalizace na entity -> nacteni do Neo4j.
Spust pres `make ingest` (potrebuje bezici Neo4j a naplnene .env).
"""

import logging

from ares_insight.graph import connection
from ares_insight.ingest import fetch, load, transform

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s"
)
logger = logging.getLogger("ingest")


def main() -> None:
    logger.info("Stahuji vyrez z ARES...")
    raw = fetch.fetch_slice()
    logger.info("Staženo %d firem, normalizuji...", len(raw))

    entities = transform.to_entities(raw)
    logger.info(
        "Entity: %d firem, %d osob, %d adres, %d director_of, %d registered_at",
        len(entities.companies),
        len(entities.persons),
        len(entities.addresses),
        len(entities.director_of),
        len(entities.registered_at),
    )

    logger.info("Nacitam do Neo4j...")
    stats = load.load(entities)
    connection.close_driver()
    logger.info("Ingest done. %s", stats)


if __name__ == "__main__":
    main()
