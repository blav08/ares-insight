"""Faze 1: stazeni vyrezu dat z ARES (REST API).

Vyrez = NACE 62/63, sidlo Praha, jen a.s. (viz config). Pro tenhle objem
(~2 700 firem) je REST API praktictejsi nez bulk dump celeho CR: stahujeme
cilene jen co potrebujeme.

Dva endpointy:
- POST /ekonomicke-subjekty/vyhledat  -> seznam firem (zaklad + sidlo + NACE)
- GET  /ekonomicke-subjekty-vr/{ico}  -> VR zaznam vc. statutarniho organu (osoby)

Omezeni API (overeno live):
- vyhledavani vraci max 1000 vysledku na dotaz; pokud je shoda > 1000, API dotaz
  rovnou odmitne -> shardujeme po spravnich obvodech Prahy.
- velikost stranky max ~500; stránkujeme přes start/pocet.
- limit 500 dotazu/min -> throttlujeme (viz config.ares_requests_per_minute).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator

import requests

from ares_insight.config import settings

logger = logging.getLogger(__name__)

_SEARCH_URL = f"{settings.ares_base_url}/ekonomicke-subjekty/vyhledat"
_VR_URL = f"{settings.ares_base_url}/ekonomicke-subjekty-vr"


class _RateLimiter:
    """Jednoduchy throttler: min. odstup mezi dotazy podle requests_per_minute."""

    def __init__(self, per_minute: int) -> None:
        self._min_interval = 60.0 / max(per_minute, 1)
        self._last = 0.0

    def wait(self) -> None:
        now = time.monotonic()
        sleep_for = self._min_interval - (now - self._last)
        if sleep_for > 0:
            time.sleep(sleep_for)
        self._last = time.monotonic()


_limiter = _RateLimiter(settings.ares_requests_per_minute)


def _post(url: str, json_body: dict) -> dict:
    """POST s throttlingem a retry/backoff. Vraci rozparsovany JSON."""
    for attempt in range(1, settings.ares_max_retries + 1):
        _limiter.wait()
        try:
            resp = requests.post(
                url, json=json_body, timeout=settings.ares_timeout_s,
                headers={"accept": "application/json"},
            )
            if resp.status_code == 429:
                raise requests.HTTPError("429 Too Many Requests")
            if resp.status_code == 400:
                # ARES vraci business chyby (vc. "prilis mnoho vysledku") jako 400
                # se strukturovanym telem {kod, subKod, popis}. Telo vratime a
                # rozhodnuti nechame na volajicim (napr. _count -> shardovani).
                try:
                    body = resp.json()
                except ValueError:
                    body = {}
                if body.get("kod"):
                    return body
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            if attempt == settings.ares_max_retries:
                raise
            backoff = 2.0 * attempt
            logger.warning("POST %s selhal (%s), retry za %.0fs", url, exc, backoff)
            time.sleep(backoff)
    return {}  # nedosazitelne


def _get(url: str) -> dict | None:
    """GET s throttlingem a retry. 404 -> None (firma nema VR zaznam)."""
    for attempt in range(1, settings.ares_max_retries + 1):
        _limiter.wait()
        try:
            resp = requests.get(
                url, timeout=settings.ares_timeout_s,
                headers={"accept": "application/json"},
            )
            if resp.status_code == 404:
                return None
            if resp.status_code == 429:
                raise requests.HTTPError("429 Too Many Requests")
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            if attempt == settings.ares_max_retries:
                logger.error("GET %s selhal definitivne: %s", url, exc)
                return None
            backoff = 2.0 * attempt
            logger.warning("GET %s selhal (%s), retry za %.0fs", url, exc, backoff)
            time.sleep(backoff)
    return None


def _build_filter(nace: str, *, kod_obce: int, obvod: int | None) -> dict:
    sidlo: dict = {"kodObce": kod_obce}
    if obvod is not None:
        sidlo["kodSpravnihoObvodu"] = obvod
    return {
        "czNace": [nace],
        "pravniForma": settings.legal_forms,
        "sidlo": sidlo,
    }


def _paged_search(base_filter: dict) -> Iterator[dict]:
    """Stránkuje jeden vyhledavaci filtr (predpoklada total <= 1000)."""
    start = 0
    page = settings.ares_page_size
    while True:
        body = {**base_filter, "start": start, "pocet": page}
        data = _post(_SEARCH_URL, body)
        subjects = data.get("ekonomickeSubjekty", [])
        if not subjects:
            break
        yield from subjects
        start += len(subjects)
        total = data.get("pocetCelkem")
        if total is not None and start >= total:
            break
        if start >= settings.ares_max_results_per_query:
            break


def _count(base_filter: dict) -> int | None:
    """Vrati pocetCelkem, nebo None pokud shoda presahuje povoleny strop."""
    data = _post(_SEARCH_URL, {**base_filter, "start": 0, "pocet": 1})
    if data.get("subKod") == "VYSTUP_PRILIS_MNOHO_VYSLEDKU":
        return None
    return data.get("pocetCelkem", 0)


def fetch_companies() -> list[dict]:
    """Stahne firmy vyrezu (zaklad + sidlo). Dedup podle ICO.

    Pro kazdy NACE zkusi jeden dotaz; kdyz shoda presahne 1000, shardne ho po
    pražskych spravnich obvodech. Volitelne klientsky vyfiltruje rok vzniku.
    """
    by_ico: dict[str, dict] = {}
    for nace in settings.nace_prefixes:
        whole = _build_filter(nace, kod_obce=settings.kod_obce, obvod=None)
        if _count(whole) is not None:
            shards = [whole]
        else:
            logger.info("NACE %s > 1000, shardim po spravnich obvodech", nace)
            shards = [
                _build_filter(nace, kod_obce=settings.kod_obce, obvod=o)
                for o in settings.spravni_obvody
            ]
        for shard in shards:
            for subj in _paged_search(shard):
                by_ico[subj["ico"]] = subj
        logger.info("NACE %s: zatim %d unikatnich firem", nace, len(by_ico))

    companies = list(by_ico.values())
    if settings.founded_from_year is not None:
        companies = [
            c for c in companies if _founded_year(c) is not None
            and _founded_year(c) >= settings.founded_from_year
        ]
    logger.info("Celkem firem ve vyrezu: %d", len(companies))
    return companies


def _founded_year(company: dict) -> int | None:
    d = company.get("datumVzniku")  # "YYYY-MM-DD"
    if d and len(d) >= 4 and d[:4].isdigit():
        return int(d[:4])
    return None


def fetch_statutory(ico: str) -> dict | None:
    """Stahne VR zaznam firmy (statutarni organ + osoby). None kdyz neexistuje."""
    return _get(f"{_VR_URL}/{ico}")


def fetch_slice() -> list[dict]:
    """Stahne cely vyrez: firmy + jejich VR zaznam.

    Vraci list surovych zaznamu: {"company": <search subj>, "vr": <vr zaznam|None>}.
    VR se tahne per firma (1 GET/firma) -> u ~2 700 firem je to nejdrazsi cast.
    """
    companies = fetch_companies()
    records: list[dict] = []
    n = len(companies)
    for i, company in enumerate(companies, 1):
        vr_resp = fetch_statutory(company["ico"])
        vr_zaznam = None
        if vr_resp and vr_resp.get("zaznamy"):
            vr_zaznam = vr_resp["zaznamy"][0]
        records.append({"company": company, "vr": vr_zaznam})
        if i % 200 == 0 or i == n:
            logger.info("VR staženo %d/%d", i, n)
    return records
