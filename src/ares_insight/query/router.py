"""Faze 5: router - rozhodne, kterou cestou dotaz zodpovedet.

- "cypher"   = strukturovana cesta (text-to-Cypher): pocty, vztahy, filtry,
  konkretni jmena/adresy - presne, nad strukturou grafu.
- "semantic" = vektorova cesta: volnejsi/tematicke dotazy ("firmy zamerene na ..."),
  kde se hodi podobnostni hledani nad embeddingy firem.

Nejdriv levna heuristika (klicova slova); kdyz je dotaz nejasny, rozhodne LLM.
Default je "cypher" - je presnejsi a data jsou primarne strukturovana.
"""

from __future__ import annotations

import re
import unicodedata

_STRUCTURED_HINTS = (
    "kolik", "pocet", "statutar", "jednatel", "predstavenstv", "adres", "sidl",
    "vznikl", "vic nez", "mene nez", "seznam", "vypis", "propojen", "stejne",
    "ico", "nejvic", "kdo je",
)
_SEMANTIC_HINTS = (
    "zamer", "podobn", "tematicky", "cim se zabyva", "co dela", "specializ",
    "oblast", "o firmach", "typ firem",
)


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"\s+", " ", text).strip()


def heuristic_route(question: str) -> str | None:
    """Rychla heuristika; None kdyz je dotaz nejednoznacny."""
    q = _fold(question)
    if any(h in q for h in _STRUCTURED_HINTS):
        return "cypher"
    if any(h in q for h in _SEMANTIC_HINTS):
        return "semantic"
    return None


_ROUTER_PROMPT = """Rozhodni, jak zodpovedet dotaz nad grafem ceskych firem.
Odpovez jednim slovem:
- "cypher" pro presne strukturovane dotazy (pocty, vztahy, filtry, konkretni
  jmena/adresy, statutari, sidla).
- "semantic" pro volnejsi tematicke dotazy o zamereni firem.

Dotaz: {question}
Odpoved (cypher/semantic):"""


def route(question: str, llm=None) -> str:
    """Vrati "cypher" nebo "semantic"."""
    h = heuristic_route(question)
    if h is not None:
        return h
    if llm is None:
        return "cypher"
    try:
        msg = llm.invoke(_ROUTER_PROMPT.format(question=question))
        ans = getattr(msg, "content", str(msg)).lower()
    except Exception:  # noqa: BLE001 - pri chybe routeru padni na bezpecny default
        return "cypher"
    return "semantic" if "semantic" in ans else "cypher"
