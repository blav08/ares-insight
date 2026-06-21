"""Faze 3: Streamlit chatove UI.

Spusteni: streamlit run app/streamlit_app.py
Vola FastAPI /query endpoint (musi bezet, viz `make api`). URL se bere z
ARES_API_URL / config.api_url.

Ptas se cesky, dostanes ceskou odpoved + (rozbalovaci) pouzity Cypher a tabulku
podkladovych dat - aby slo odpoved overit proti zdroji (podminka ARES).
"""

import os

import requests
import streamlit as st

API_URL = os.environ.get("ARES_API_URL", "http://localhost:8000").rstrip("/")

st.set_page_config(page_title="ARES Insight", page_icon=":mag:")
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
        "- Ktere firmy sidli na stejne adrese?"
    )
    st.caption(f"API: {API_URL}")

if "messages" not in st.session_state:
    st.session_state.messages = []


def _render(msg: dict) -> None:
    st.markdown(msg["answer"])
    if msg.get("cypher"):
        with st.expander("Pouzity Cypher"):
            st.code(msg["cypher"], language="cypher")
    if msg.get("rows"):
        with st.expander(f"Podkladova data ({len(msg['rows'])} radku)"):
            st.dataframe(msg["rows"], use_container_width=True)


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
                data = {
                    "answer": f"Chyba pri volani API: {exc}",
                    "cypher": None,
                    "rows": [],
                }
        _render(data)

    st.session_state.messages.append({"role": "assistant", **data})
