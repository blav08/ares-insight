"""Faze 2/3: formatovani finalni odpovedi + zdrojovych dat pro UI.

Zobrazeni podkladovych radku drzi odpovedi overitelne a respektuje podminku ARES
(nezkreslovat zdroj). Pouziva se v CLI (Faze 2) i pozdeji v UI (Faze 3).
"""

from __future__ import annotations

from typing import Any

_MAX_ROWS = 50


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


def format_sources(rows: list[dict]) -> str:
    """Vykresli podpurne radky jako markdown tabulku.

    Sloupce se odvodi ze sjednoceni klicu vsech radku (zachova poradi prvniho
    vyskytu). Prazdny vstup -> srozumitelna hlaska.
    """
    if not rows:
        return "_Zadna podkladova data._"

    columns: list[str] = []
    for row in rows:
        if isinstance(row, dict):
            for key in row:
                if key not in columns:
                    columns.append(key)
    if not columns:
        return "_Zadna podkladova data._"

    shown = rows[:_MAX_ROWS]
    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join("---" for _ in columns) + " |"
    lines = [header, sep]
    for row in shown:
        cells = [_fmt(row.get(c)) if isinstance(row, dict) else "" for c in columns]
        lines.append("| " + " | ".join(cells) + " |")

    if len(rows) > _MAX_ROWS:
        lines.append(f"\n_(zobrazeno {_MAX_ROWS} z {len(rows)} radku)_")
    return "\n".join(lines)
