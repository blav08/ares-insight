"""CLI pro Fazi 2: zeptej se cesky na firmy a jejich vztahy (text-to-Cypher).

Pouziti:
  python scripts/run_query.py "Ktere firmy sidli na stejne adrese jako ICO 27074358?"
  python scripts/run_query.py            # interaktivni rezim (prazdny radek/ctrl+C konci)

Potrebuje naplneny graf (Faze 1), bezici Neo4j a ANTHROPIC_API_KEY v .env.
"""

import logging
import sys

from ares_insight.config import settings
from ares_insight.graph import connection
from ares_insight.query import answer, cypher_chain

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s | %(message)s")


def _ask(question: str) -> None:
    result = cypher_chain.answer_question(question)
    print("\n=== Odpoved ===")
    print(result["answer"] or "(prazdna odpoved)")
    if result.get("cypher"):
        print("\n=== Pouzity Cypher ===")
        print(result["cypher"])
    print("\n=== Podkladova data ===")
    print(answer.format_sources(result.get("rows", [])))
    print()


def main() -> None:
    if not settings.anthropic_api_key:
        print("Chybi ANTHROPIC_API_KEY v .env - bez nej Faze 2 nepobezi.")
        sys.exit(1)

    args = sys.argv[1:]
    if args:
        _ask(" ".join(args))
    else:
        print("Interaktivni rezim. Napis dotaz cesky (prazdny radek konci).")
        try:
            while True:
                q = input("\n> ").strip()
                if not q:
                    break
                _ask(q)
        except (EOFError, KeyboardInterrupt):
            pass

    connection.close_driver()


if __name__ == "__main__":
    main()
