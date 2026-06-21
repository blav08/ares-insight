"""Faze 3: Streamlit chatove UI.

Spusteni: streamlit run app/streamlit_app.py
Vola FastAPI /query endpoint (nebo query modul primo pro lokalni vyvoj).
"""

import streamlit as st

st.set_page_config(page_title="ARES Insight", page_icon=":mag:")
st.title("ARES Insight")
st.caption("Ptej se cesky na ceske firmy a jejich vztahy. Data: ARES (otevrena data MF).")

# TODO (Faze 3): chat input -> volani API -> render odpovedi + tabulka zdroju.
st.info("Faze 3: tady bude chatove rozhrani.")
