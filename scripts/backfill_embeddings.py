"""Faze 5: spocita embeddingy firem a zalozi vektorovy index (bez re-ingestu).
Prvni spusteni stahne embedding model (~120 MB).

  python scripts/backfill_embeddings.py
"""

import logging

from ares_insight.graph import connection
from ares_insight.ingest import load

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    n = load.backfill_embeddings()
    connection.close_driver()
    print(f"Hotovo, embedding ulozen u {n} firem.")


if __name__ == "__main__":
    main()
