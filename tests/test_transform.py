"""Offline testy normalizace (transform). Zadna sit - fixtures kopiruji tvar
realnych ARES odpovedi (overeno proti live API ve Fazi 1)."""

from ares_insight.ingest.transform import to_entities

_COMPANY = {
    "ico": "27074358",
    "obchodniJmeno": "Asseco Central Europe, a.s.",
    "pravniForma": "121",
    "datumVzniku": "2003-08-06",
    "czNace2008": ["62", "620", "63"],
    "sidlo": {
        "nazevObce": "Praha",
        "nazevUlice": "Budějovická",
        "nazevSpravnihoObvodu": "Praha 4",
        "psc": 14000,
        "nazevStatu": "Česká republika",
        "kodAdresnihoMista": 41405609,
        "textovaAdresa": "Budějovická 778/3a, Michle, 14000 Praha 4",
    },
}


def _vr(members):
    return {
        "ico": "27074358",
        "statutarniOrgany": [
            {"nazevOrganu": "představenstvo", "clenoveOrganu": members}
        ],
    }


def _member(jmeno, prijmeni, narozeni, *, vymaz=None):
    m = {
        "typAngazma": "STATUTARNI_ORGAN_CLEN",
        "clenstvi": {
            "clenstvi": {"vznikClenstvi": "2023-01-01"},
            "funkce": {"nazev": "Člen představenstva"},
        },
        "fyzickaOsoba": {
            "jmeno": jmeno,
            "prijmeni": prijmeni,
            "datumNarozeni": narozeni,
            "statniObcanstvi": "CZ",
            "adresa": {"textovaAdresa": "Nekde 1, Praha"},
        },
    }
    if vymaz:
        m["datumVymazu"] = vymaz
    return m


def test_basic_company_address_person():
    recs = [{"company": _COMPANY, "vr": _vr([_member("Jan", "Novák", "1980-01-01")])}]
    ent = to_entities(recs)
    assert len(ent.companies) == 1
    assert ent.companies[0]["ico"] == "27074358"
    assert len(ent.addresses) == 1
    assert ent.addresses[0]["address_key"] == "am:41405609"
    assert len(ent.persons) == 1
    assert ent.persons[0]["name"] == "Jan Novák"
    assert len(ent.registered_at) == 1
    assert len(ent.director_of) == 1
    assert ent.director_of[0]["role"] == "Člen představenstva"


def test_historic_members_excluded():
    recs = [
        {
            "company": _COMPANY,
            "vr": _vr(
                [
                    _member("Jan", "Novák", "1980-01-01"),
                    _member("Eva", "Stará", "1970-05-05", vymaz="2020-01-01"),
                ]
            ),
        }
    ]
    ent = to_entities(recs)
    assert len(ent.persons) == 1
    assert ent.persons[0]["name"] == "Jan Novák"


def test_person_dedup_across_companies():
    company2 = {**_COMPANY, "ico": "11111111", "obchodniJmeno": "Druha, a.s."}
    member = _member("Jan", "Novák", "1980-01-01")
    recs = [
        {"company": _COMPANY, "vr": _vr([member])},
        {"company": company2, "vr": _vr([member])},
    ]
    ent = to_entities(recs)
    assert len(ent.companies) == 2
    assert len(ent.persons) == 1  # stejna osoba slita
    assert len(ent.director_of) == 2  # ale dva vztahy
    # sdilena adresa -> stejny address_key, jeden uzel adresy
    assert len(ent.addresses) == 1


def test_company_without_vr():
    recs = [{"company": _COMPANY, "vr": None}]
    ent = to_entities(recs)
    assert len(ent.companies) == 1
    assert len(ent.persons) == 0
    assert len(ent.director_of) == 0
