"""Jednorazova migrace: doplni p.name_norm na existujicich Person uzlech a
zalozi textovy index. Pouzij po upgradu z grafu nactenoho pred zavedenim
name_norm - bez nutnosti re-ingestu z ARES.

  python scripts/backfill_name_norm.py
"""

import logging

from ares_insight.graph import connection
from ares_insight.ingest import load

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    connection.apply_schema()  # zalozi i TEXT index person_name_norm
    n = load.backfill_name_norm()
    connection.close_driver()
    print(f"Hotovo, name_norm doplnen u {n} osob.")


if __name__ == "__main__":
    main()
