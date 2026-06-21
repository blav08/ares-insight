"""Faze 1: normalizace surovych ARES zaznamu na entity grafu.

Vstup: list zaznamu z fetch.fetch_slice() -> {"company": <search subj>, "vr": <vr|None>}.
Vystup: dataclass Entities s uzly (companies, persons, addresses) a vztahy
(director_of, registered_at). SHARES_ADDRESS_WITH se neodvozuje tady, ale az v
grafu (load.py) Cypherem nad sdilenymi adresami.

Dedup klice (stabilni napric firmami, aby se uzly slily):
- Company: ico
- Address: kodAdresnihoMista (kdyz chybi -> slug z textovaAdresa)
- Person:  prijmeni|jmeno|datumNarozeni (normalizovane); kdyz chybi datum,
  spadne na prijmeni|jmeno (slabsi dedup, viz pozn. nize)

Pozn.: clenove statutarniho organu mohou byt i pravnicke osoby; ve v1 bereme jen
fyzicke osoby (fyzickaOsoba) -> Person. Pravnicke osoby v predstavenstvu jsou u
ceskych a.s. okrajove a pridaly by dalsi typ vztahu; necham na pozdeji.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field


@dataclass
class Entities:
    companies: list[dict] = field(default_factory=list)
    persons: list[dict] = field(default_factory=list)
    addresses: list[dict] = field(default_factory=list)
    director_of: list[dict] = field(default_factory=list)
    registered_at: list[dict] = field(default_factory=list)


def _slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def fold_name(text: str) -> str:
    """Normalizuje jmeno na mala pismena bez diakritiky (pro vyhledavani).

    "Libor Horák" -> "libor horak". Pouziva se na property Person.name_norm a
    stejne se ma normalizovat hledany vyraz v dotazu (viz cypher prompt).
    """
    text = unicodedata.normalize("NFKD", text or "")
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"\s+", " ", text).strip()


def _address_key(adresa: dict) -> str | None:
    if not adresa:
        return None
    kod = adresa.get("kodAdresnihoMista")
    if kod is not None:
        return f"am:{kod}"
    txt = adresa.get("textovaAdresa")
    if txt:
        return f"tx:{_slug(txt)}"
    return None


def _address_node(key: str, adresa: dict) -> dict:
    return {
        "address_key": key,
        "text": adresa.get("textovaAdresa"),
        "municipality": adresa.get("nazevObce"),
        "city_district": adresa.get("nazevMestskeCastiObvodu")
        or adresa.get("nazevSpravnihoObvodu"),
        "street": adresa.get("nazevUlice"),
        "psc": adresa.get("psc"),
        "country": adresa.get("nazevStatu"),
    }


def _person_key(osoba: dict) -> str | None:
    jmeno = (osoba.get("jmeno") or "").strip()
    prijmeni = (osoba.get("prijmeni") or "").strip()
    if not (jmeno or prijmeni):
        return None
    narozeni = (osoba.get("datumNarozeni") or "").strip()
    base = f"{_slug(prijmeni)}|{_slug(jmeno)}"
    return f"{base}|{narozeni}" if narozeni else base


def _full_name(osoba: dict) -> str:
    parts = [osoba.get("jmeno"), osoba.get("prijmeni")]
    return " ".join(p for p in parts if p).title()


def _iter_current_members(vr_zaznam: dict):
    """Vrati aktualni cleny statutarniho organu (bez datumVymazu) jako fyz. osoby."""
    for organ in vr_zaznam.get("statutarniOrgany", []) or []:
        for clen in organ.get("clenoveOrganu", []) or []:
            if clen.get("datumVymazu"):
                continue  # historicky clen -> preskoc
            osoba = clen.get("fyzickaOsoba")
            if osoba:
                yield organ, clen, osoba


def to_entities(raw_records) -> Entities:
    """Mapuje surove ARES zaznamy -> Entities (uzly + vztahy), s dedupem."""
    ent = Entities()
    seen_companies: set[str] = set()
    seen_persons: set[str] = set()
    seen_addresses: set[str] = set()

    for rec in raw_records:
        company = rec.get("company") or {}
        ico = company.get("ico")
        if not ico or ico in seen_companies:
            continue
        seen_companies.add(ico)

        sidlo = company.get("sidlo") or {}
        addr_key = _address_key(sidlo)

        ent.companies.append(
            {
                "ico": ico,
                "name": company.get("obchodniJmeno"),
                "legal_form": company.get("pravniForma"),
                "founded": company.get("datumVzniku"),
                "nace": company.get("czNace2008") or company.get("czNace") or [],
                "address_text": sidlo.get("textovaAdresa"),
            }
        )

        if addr_key:
            if addr_key not in seen_addresses:
                seen_addresses.add(addr_key)
                ent.addresses.append(_address_node(addr_key, sidlo))
            ent.registered_at.append({"ico": ico, "address_key": addr_key})

        vr = rec.get("vr")
        if not vr:
            continue
        for organ, clen, osoba in _iter_current_members(vr):
            pkey = _person_key(osoba)
            if not pkey:
                continue
            if pkey not in seen_persons:
                seen_persons.add(pkey)
                full_name = _full_name(osoba)
                ent.persons.append(
                    {
                        "person_key": pkey,
                        "name": full_name,
                        "name_norm": fold_name(full_name),
                        "year_of_birth": (osoba.get("datumNarozeni") or "")[:4] or None,
                        "citizenship": osoba.get("statniObcanstvi"),
                    }
                )
            funkce = (clen.get("clenstvi") or {}).get("funkce") or {}
            ent.director_of.append(
                {
                    "person_key": pkey,
                    "ico": ico,
                    "role": funkce.get("nazev") or organ.get("nazevOrganu"),
                    "since": ((clen.get("clenstvi") or {}).get("clenstvi") or {}).get(
                        "vznikClenstvi"
                    ),
                }
            )

    return ent
