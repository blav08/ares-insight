"""Faze 3 + 5: Streamlit chatove UI.

Spusteni: streamlit run app/streamlit_app.py
Vola FastAPI /query (a /subgraph pro vizualizaci). URL z ARES_API_URL / secrets.

Ptas se cesky, dostanes ceskou odpoved + (rozbalovaci) pouzity Cypher, tabulku
podkladovych dat a interaktivni graf vztahu (Faze 5) - aby slo odpoved overit
proti zdroji (podminka ARES).

Vizualni vrstva: theme v .streamlit/config.toml (indigo + slate paleta),
custom CSS nize (Inter, badge pro cestu, legenda grafu, mobilni breakpointy).
"""

import os
import re

import requests
import streamlit as st

try:
    from streamlit_agraph import Config, Edge, Node, agraph

    _HAS_AGRAPH = True
except Exception:  # noqa: BLE001 - kdyz komponenta chybi, graf se proste neukaze
    _HAS_AGRAPH = False

_NODE_COLORS = {"Company": "#F59E0B", "Person": "#4F46E5", "Address": "#10B981"}
_EDGE_COLORS = {"STATUTAR": "#4F46E5", "SIDLO": "#10B981"}
_ICO_RE = re.compile(r"^\d{8}$")

# Hlavni plocha: 4 rychle startovni dotazy (prvni dojem, kazdy ukazuje jinou schopnost)
_HERO_EXAMPLES = [
    "Kolik firem je celkem v databázi?",
    "Najdi firmy, kde je statutárem Libor Horák.",
    "Na které adrese sídlí nejvíc firem?",
]
# 4th hero slot depends on whether the API has the vector path enabled
# (on Render Free it is off: the embedding model does not fit into 512 MB RAM).
_HERO_SEMANTIC = "Firmy zaměřené na vývoj softwaru"
_HERO_FALLBACK = "Která firma v databázi vznikla nejdříve?"
# Sidebar groups that only make sense with the semantic (vector) path.
_SEMANTIC_GROUPS = {"Tematické hledání"}

# Sidebar: JINE dotazy nez v hlavni plose, seskupene podle typu -> je videt,
# co vsechno system umi (strukturovana i semanticka cesta).
_SIDEBAR_EXAMPLES = {
    "Počty a statistiky": [
        "Kolik firem vzniklo po roce 2020?",
        "Které firmy mají víc než tři statutáry?",
    ],
    "Lidé ve vedení": [
        "Vypiš 5 osob, které jsou statutárem v nejvíce firmách.",
        "Ve kterých firmách působí lidé s příjmením Novák?",
        "Kolik osob je statutárem ve více než třech firmách?",
    ],
    "Propojení firem": [
        "Které dvojice firem sdílejí nejvíc společných statutárů?",
        "Které firmy sídlí na stejné adrese a zároveň sdílejí statutára?",
    ],
    "Tematické hledání": [
        "Firmy specializované na kybernetickou bezpečnost",
        "Firmy zaměřené na datovou analytiku a umělou inteligenci",
    ],
}

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* Typografie: Inter pro text, ale nechat ikonove fonty na pokoji */
html, body, p, li, input, textarea, button, h1, h2, h3, h4,
[data-testid="stMarkdownContainer"] {
    font-family: 'Inter', 'Source Sans Pro', sans-serif;
}
[data-testid="stIconMaterial"] {
    font-family: 'Material Symbols Rounded' !important;
}
h1 { letter-spacing: -0.02em; font-weight: 700; }

/* Uzsi obsahovy sloupec = citelnejsi chat (i pri layout="wide") */
.block-container { max-width: 1100px; padding-top: 2.2rem; }

/* Kod (Cypher) - mensi, at neprebiji odpoved */
code, pre { font-size: 0.85rem !important; }

/* Badge pro cestu routeru */
.ares-badge {
    display: inline-block; padding: 2px 10px; border-radius: 999px;
    font-size: 0.72rem; font-weight: 600; letter-spacing: 0.02em;
    margin-bottom: 6px;
}
.ares-badge.cypher   { background: #EEF2FF; color: #4338CA; }
.ares-badge.semantic { background: #ECFDF5; color: #047857; }

/* Legenda grafu - barevne cipy misto vety */
.ares-chip {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 2px 10px; border-radius: 999px; background: #F1F5F9;
    font-size: 0.75rem; margin-right: 6px; margin-bottom: 4px;
}
.ares-dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }

/* Nadpisy skupin prikladovych dotazu v sidebaru */
.ares-group {
    font-size: 0.72rem; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.06em; color: #64748B; margin: 0.9rem 0 0.35rem;
}

/* Stavova tecka API v sidebaru */
.ares-status { display: flex; align-items: center; gap: 7px; font-size: 0.8rem; }

/* Graf (iframe komponenty) nikdy nepretece na mobilu */
iframe { max-width: 100%; }

/* Mobil: mensi odsazeni, mensi titulek */
@media (max-width: 640px) {
    .block-container { padding-left: 0.8rem; padding-right: 0.8rem; padding-top: 1.2rem; }
    h1 { font-size: 1.5rem !important; }
}

/* Skryt Streamlit chrome - pusobi to jako produkt, ne demo */
#MainMenu, footer { visibility: hidden; }
</style>
"""


def _resolve_api_url() -> str:
    """ARES_API_URL: nejdriv Streamlit secrets, pak env, pak lokalni default."""
    try:
        if "ARES_API_URL" in st.secrets:
            return str(st.secrets["ARES_API_URL"]).rstrip("/")
    except Exception:  # noqa: BLE001 - chybejici secrets.toml nesmi shodit UI
        pass
    return os.environ.get("ARES_API_URL", "http://localhost:8000").rstrip("/")


API_URL = _resolve_api_url()


@st.cache_data(ttl=90, show_spinner=False)
def _api_alive(url: str) -> bool:
    """Zdravi API (cache 90 s, at se health nevola pri kazdem rerunu)."""
    try:
        return requests.get(f"{url}/health", timeout=4).ok
    except requests.RequestException:
        return False


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_stats(url: str) -> dict:
    """Live dataset size from API /stats (cache 1 h). Raises on failure on
    purpose: st.cache_data does not cache exceptions, so a sleeping API is
    retried on the next rerun instead of caching an empty result for an hour."""
    resp = requests.get(f"{url}/stats", timeout=10)
    resp.raise_for_status()
    return resp.json()


def _get_stats() -> dict | None:
    try:
        return _fetch_stats(API_URL)
    except Exception:  # noqa: BLE001 - API asleep/unreachable -> UI falls back
        return None


def _fmt_int(n: int) -> str:
    """2363 -> '2 363' (Czech thousands separator, non-breaking space)."""
    return f"{n:,}".replace(",", "\u00a0")


def _fmt_date(iso: str | None) -> str | None:
    """'2026-11-05' -> '5. 11. 2026'."""
    try:
        y, m, d = (int(x) for x in iso.split("-"))
    except Exception:  # noqa: BLE001
        return None
    return f"{d}. {m}. {y}"


def _data_caption(stats: dict | None) -> str:
    base = "Výřez dat: IT firmy (a.s.) se sídlem v Praze"
    tail = "Každá odpověď ukazuje použitý dotaz i podkladová data."
    if not stats:
        return f"{base}. {tail}"
    text = (
        f"{base} — {_fmt_int(stats['companies'])} firem, "
        f"{_fmt_int(stats['persons'])} osob, {_fmt_int(stats['addresses'])} adres"
    )
    as_of = _fmt_date(stats.get("ingested_at"))
    if as_of:
        text += f" (stav k {as_of})"
    return f"{text}. {tail}"


def _extract_icos(rows: list[dict]) -> list[str]:
    """Vytahne ICO (8 cislic) z libovolneho sloupce, jehoz nazev obsahuje 'ico'."""
    found: list[str] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        for key, val in row.items():
            if "ico" in key.lower() and isinstance(val, str) and _ICO_RE.match(val):
                if val not in found:
                    found.append(val)
    return found


def _fetch_subgraph(icos: list[str]) -> dict:
    try:
        resp = requests.post(f"{API_URL}/subgraph", json={"icos": icos}, timeout=60)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return {"nodes": [], "edges": []}


st.set_page_config(
    page_title="ARES Insight",
    page_icon=":mag:",
    layout="wide",
    initial_sidebar_state="auto",
)
st.markdown(_CSS, unsafe_allow_html=True)

st.title("ARES Insight")
st.caption(
    "Ptej se česky na české firmy a jejich vztahy — kdo s kým sdílí statutáry, "
    "kdo sídlí na stejné adrese. Data: ARES (otevřená data MF)."
)

stats = _get_stats()
# Unknown (API asleep) -> assume semantic is off: better to hide an example
# than to offer one that crashes the API.
semantic_on = bool(stats and stats.get("semantic_enabled"))

with st.sidebar:
    alive = _api_alive(API_URL)
    dot = "#10B981" if alive else "#F59E0B"
    label = "API běží" if alive else "API se probouzí (free tier, ~1 min)"
    st.markdown(
        f'<div class="ares-status"><span class="ares-dot" '
        f'style="background:{dot}"></span>{label}</div>',
        unsafe_allow_html=True,
    )
    st.divider()
    st.subheader("Další dotazy")
    for g, (group, examples) in enumerate(_SIDEBAR_EXAMPLES.items()):
        if group in _SEMANTIC_GROUPS and not semantic_on:
            continue
        st.markdown(f'<div class="ares-group">{group}</div>', unsafe_allow_html=True)
        for i, ex in enumerate(examples):
            if st.button(ex, key=f"ex_{g}_{i}", use_container_width=True):
                st.session_state.pending_question = ex
    st.divider()
    st.caption(_data_caption(stats))

if "messages" not in st.session_state:
    st.session_state.messages = []


def _legend_html() -> str:
    items = [
        ("Firma", _NODE_COLORS["Company"]),
        ("Osoba / statutár", _NODE_COLORS["Person"]),
        ("Adresa / sídlo", _NODE_COLORS["Address"]),
    ]
    chips = "".join(
        f'<span class="ares-chip"><span class="ares-dot" '
        f'style="background:{c}"></span>{t}</span>'
        for t, c in items
    )
    return f"<div>{chips}</div>"


def _render_graph(graph: dict) -> None:
    if not (_HAS_AGRAPH and graph and graph.get("nodes")):
        return
    nodes = [
        Node(
            id=n["id"],
            label=n["label"][:28],
            color=_NODE_COLORS.get(n["type"], "#9CA3AF"),
            size=22 if n["type"] == "Company" else 14,
        )
        for n in graph["nodes"]
    ]
    # Hrany bez textovych popisku (delaly v centru gulas) - typ nese barva.
    edges = [
        Edge(
            source=e["source"],
            target=e["target"],
            color=_EDGE_COLORS.get(e.get("label"), "#6B7280"),
        )
        for e in graph["edges"]
    ]
    config = Config(
        width=1000, height=560, directed=True, physics=True,
        nodeHighlightBehavior=True, highlightColor="#FDE68A", collapsible=False,
        node={"labelProperty": "label", "renderLabel": True},
        link={"labelProperty": "label", "renderLabel": False},
    )
    with st.expander(f"Graf vztahů · {len(nodes)} uzlů", expanded=True):
        st.markdown(_legend_html(), unsafe_allow_html=True)
        st.caption("Přibližování kolečkem, uzly jdou přetahovat.")
        agraph(nodes=nodes, edges=edges, config=config)


def _render(msg: dict) -> None:
    path = msg.get("path")
    if path:
        label = {
            "cypher": "strukturovaná cesta · text-to-Cypher",
            "semantic": "sémantická cesta · vektorové hledání",
        }
        st.markdown(
            f'<span class="ares-badge {path}">{label.get(path, path)}</span>',
            unsafe_allow_html=True,
        )
    st.markdown(msg["answer"])
    if msg.get("cypher"):
        with st.expander("Použitý Cypher"):
            st.code(msg["cypher"], language="cypher")
    if msg.get("rows"):
        with st.expander(f"Podkladová data · {len(msg['rows'])} řádků"):
            st.dataframe(msg["rows"], use_container_width=True, hide_index=True)
    _render_graph(msg.get("graph"))


# Prazdny stav: uvitani + klikatelne priklady primo v hlavni plose
if not st.session_state.messages:
    st.markdown("#### Na co se můžete ptát")
    cols = st.columns(2)
    hero = _HERO_EXAMPLES + [_HERO_SEMANTIC if semantic_on else _HERO_FALLBACK]
    for i, ex in enumerate(hero):
        if cols[i % 2].button(ex, key=f"hero_{i}", use_container_width=True):
            st.session_state.pending_question = ex

# Historie konverzace
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant":
            _render(msg)
        else:
            st.markdown(msg["content"])

question = st.chat_input("Zeptej se česky…")
if not question:
    question = st.session_state.pop("pending_question", None)

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Hledám v grafu…"):
            try:
                resp = requests.post(
                    f"{API_URL}/query", json={"question": question}, timeout=120
                )
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException as exc:
                data = {"answer": f"Chyba při volání API: {exc}", "rows": []}
            icos = _extract_icos(data.get("rows", []))
            if icos:
                data["graph"] = _fetch_subgraph(icos)
        _render(data)

    st.session_state.messages.append({"role": "assistant", **data})
    st.rerun()
