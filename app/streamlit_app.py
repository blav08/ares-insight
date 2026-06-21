"""Faze 3 + 5: Streamlit chatove UI.

Spusteni: streamlit run app/streamlit_app.py
Vola FastAPI /query (a /subgraph pro vizualizaci). URL z ARES_API_URL / secrets.

Ptas se cesky, dostanes ceskou odpoved + (rozbalovaci) pouzity Cypher, tabulku
podkladovych dat a interaktivni graf vztahu (Faze 5) - aby slo odpoved overit
proti zdroji (podminka ARES).
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

_NODE_COLORS = {"Company": "#f59e0b", "Person": "#3b82f6", "Address": "#10b981"}
_ICO_RE = re.compile(r"^\d{8}$")


def _resolve_api_url() -> str:
    """ARES_API_URL: nejdriv Streamlit secrets, pak env, pak lokalni default."""
    try:
        if "ARES_API_URL" in st.secrets:
            return str(st.secrets["ARES_API_URL"]).rstrip("/")
    except Exception:  # noqa: BLE001 - chybejici secrets.toml nesmi shodit UI
        pass
    return os.environ.get("ARES_API_URL", "http://localhost:8000").rstrip("/")


API_URL = _resolve_api_url()


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


st.set_page_config(page_title="ARES Insight", page_icon=":mag:", layout="wide")
st.title("ARES Insight")
st.caption(
    "Ptej se cesky na ceske firmy a jejich vztahy. Data: ARES (otevrena data MF)."
)

with st.sidebar:
    st.subheader("Priklady dotazu")
    st.markdown(
        "- Kolik firem je celkem v databazi?\n"
        "- Najdi firmy, kde je statutarem Libor Horak.\n"
        "- Ktere firmy maji vic nez tri statutary?\n"
        "- Vypis 5 osob, ktere jsou statutarem v nejvice firmach.\n"
        "- Firmy zamerene na vyvoj softwaru"
    )
    st.caption(f"API: {API_URL}")

if "messages" not in st.session_state:
    st.session_state.messages = []


def _render_graph(graph: dict) -> None:
    if not (_HAS_AGRAPH and graph and graph.get("nodes")):
        return
    nodes = [
        Node(
            id=n["id"],
            label=n["label"][:40],
            color=_NODE_COLORS.get(n["type"], "#9ca3af"),
            size=18 if n["type"] == "Company" else 12,
        )
        for n in graph["nodes"]
    ]
    edges = [
        Edge(source=e["source"], target=e["target"], label=e.get("label", ""))
        for e in graph["edges"]
    ]
    config = Config(width=900, height=500, directed=True, physics=True,
                    nodeHighlightBehavior=True, collapsible=False)
    with st.expander(f"Graf vztahu ({len(nodes)} uzlu)", expanded=True):
        st.caption("Oranzova = firma, modra = osoba, zelena = adresa")
        agraph(nodes=nodes, edges=edges, config=config)


def _render(msg: dict) -> None:
    path = msg.get("path")
    if path:
        label = {"cypher": "strukturovana (text-to-Cypher)", "semantic": "vektorova"}
        st.caption(f"Cesta: {label.get(path, path)}")
    st.markdown(msg["answer"])
    if msg.get("cypher"):
        with st.expander("Pouzity Cypher"):
            st.code(msg["cypher"], language="cypher")
    if msg.get("rows"):
        with st.expander(f"Podkladova data ({len(msg['rows'])} radku)"):
            st.dataframe(msg["rows"], use_container_width=True)
    _render_graph(msg.get("graph"))


# Historie konverzace
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant":
            _render(msg)
        else:
            st.markdown(msg["content"])

question = st.chat_input("Zeptej se cesky...")
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Hledam v grafu..."):
            try:
                resp = requests.post(
                    f"{API_URL}/query", json={"question": question}, timeout=120
                )
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException as exc:
                data = {"answer": f"Chyba pri volani API: {exc}", "rows": []}
            icos = _extract_icos(data.get("rows", []))
            if icos:
                data["graph"] = _fetch_subgraph(icos)
        _render(data)

    st.session_state.messages.append({"role": "assistant", **data})
