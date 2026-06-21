"""Faze 2: text-to-Cypher nad Neo4j grafem.

Vlastni rizena pipeline (LangChain komponenty + Claude Haiku):
  1) LLM vygeneruje Cypher z ceskeho dotazu (zna schema grafu),
  2) Cypher se ocisti (fences, koncove carky) a projde READ-ONLY guardem
     JESTE PRED spustenim -> pres prirozeny jazyk nejde do grafu zapsat,
  3) spusti se nad Neo4j; pri syntakticke chybe se chyba jednou posle zpet
     LLM k oprave (error-correction smycka),
  4) z vyslednych radku LLM slozi ceskou odpoved.

Vraci {answer, cypher, rows} - radky drzi odpoved overitelnou (podminka ARES).
Oproti black-box GraphCypherQAChain mame plnou kontrolu: guard pred spustenim,
sebeoprava Cypheru a graceful chyby misto padu.
"""

from __future__ import annotations

import logging
import re

from ares_insight.config import settings

logger = logging.getLogger(__name__)

CYPHER_GENERATION_TEMPLATE = """Jsi expert na Neo4j a jazyk Cypher. Prevedes dotaz
v cestine na JEDEN Cypher dotaz nad grafem ceskych firem (data z ARES).

Schema grafu:
{schema}

Domenove napovedy (cesky -> graf):
- "firma", "spolecnost", "a.s." -> uzel Company (vlastnosti: ico, name, legal_form, founded, nace)
- "jednatel", "statutar", "clen predstavenstva", "ve vedeni" -> vztah (Person)-[:DIRECTOR_OF]->(Company)
- Osoba (Person) ma vlastnosti: name (s diakritikou, na zobrazeni), name_norm
  (mala pismena bez diakritiky, na vyhledavani), year_of_birth, citizenship.
- HLEDANI OSOBY PODLE JMENA: vzdy pres p.name_norm a hledany vyraz preved na
  mala pismena bez diakritiky, porovnavej pres CONTAINS. Napr. "Libor Horák" i
  "Libor Horak" -> WHERE p.name_norm CONTAINS "libor horak". Do RETURN dej p.name.
- "sidlo", "adresa", "sidli na" -> vztah (Company)-[:REGISTERED_AT]->(Address)
- "stejna adresa", "sdili sidlo", "propojeni pres adresu" -> (Company)-[:SHARES_ADDRESS_WITH]-(Company)
- "propojeni pres lidi / statutary" -> dve Company sdilejici stejnou Person pres DIRECTOR_OF
- "vznikla po roce X" -> Company.founded je text "YYYY-MM-DD", porovnavej napr. c.founded >= "2020-01-01"
- "obor IT / NACE 62 / 63" -> Company.nace je seznam; pouzij napr. ANY(x IN c.nace WHERE x STARTS WITH "62")

Pravidla:
- Vrat POUZE cteci dotaz (MATCH/OPTIONAL MATCH/WITH/RETURN). NIKDY nepouzij
  CREATE, MERGE, DELETE, SET, REMOVE, DROP ani zapisove CALL/LOAD CSV.
- Pouzivej jen labely a vztahy ze schematu vyse.
- RETURN nesmi koncit carkou; uved presny seznam vlastnosti oddeleny carkami.
- Kdyz dotaz zada pocet ("kolik"), pouzij count(). Jinak vracej konkretni
  uzly/vlastnosti uzitecne pro odpoved (u firem vzdy i c.ico a c.name).
- Rozumne omez vystup (napr. LIMIT 50), pokud dotaz nerika jinak.
- Vrat jen samotny Cypher, bez vysvetleni a bez markdown obalu.

Dotaz: {question}
Cypher:"""

CYPHER_FIX_SUFFIX = """

Predchozi Cypher selhal s chybou:
{error}

Vrat opraveny Cypher (jen samotny dotaz, bez vysvetleni)."""

CYPHER_QA_TEMPLATE = """Jsi asistent, ktery odpovida cesky nad daty z rejstriku ARES.
Mas k dispozici vysledek Cypher dotazu (kontext). Odpovez strucne a vecne v cestine.

Pravidla:
- Vychazej VYHRADNE z kontextu nize. Nic si nedomyslej.
- Kdyz je kontext prazdny, napis, ze k dotazu nebyla nalezena zadna data.
- U firem zminuj nazev a ICO, at je odpoved overitelna.

Kontext:
{context}

Dotaz: {question}
Odpoved:"""

_WRITE_KEYWORDS = re.compile(
    r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|LOAD\s+CSV|CALL\s+dbms|"
    r"CALL\s+apoc\.\w+\.(create|merge|delete|set))\b",
    re.IGNORECASE,
)


def is_read_only(cypher: str) -> bool:
    """True, kdyz Cypher neobsahuje zadnou zapisovou klauzuli."""
    return not _WRITE_KEYWORDS.search(cypher or "")


def _strip_fences(cypher: str) -> str:
    """Odstrani pripadny ```cypher ... ``` obal, kdyby ho LLM pridal."""
    text = (cypher or "").strip()
    text = re.sub(r"^```(?:cypher)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _sanitize(cypher: str) -> str:
    """Opravi bezne preklepy LLM: koncove carky pred klauzuli / na konci."""
    text = _strip_fences(cypher)
    text = re.sub(
        r",\s*(LIMIT|ORDER\s+BY|SKIP|RETURN|WITH|UNION)\b",
        r" \1",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r",\s*$", "", text.strip())
    return text.strip()


def _llm():
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(
        model=settings.anthropic_model,
        api_key=settings.anthropic_api_key,
        temperature=0,
        timeout=60,
    )


def _graph():
    from langchain_neo4j import Neo4jGraph

    return Neo4jGraph(
        url=settings.neo4j_uri,
        username=settings.neo4j_user,
        password=settings.neo4j_password,
        enhanced_schema=True,
    )


def _langfuse_callbacks() -> list:
    """Langfuse callback handler v listu (prazdny list, kdyz chybi klice)."""
    if not settings.langfuse_secret_key:
        return []
    try:
        from langfuse.callback import CallbackHandler

        return [
            CallbackHandler(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
            )
        ]
    except Exception as exc:  # noqa: BLE001 - observability nesmi shodit dotaz
        logger.warning("Langfuse callback se nepodarilo inicializovat: %s", exc)
        return []


def _invoke_text(llm, prompt: str, config: dict) -> str:
    msg = llm.invoke(prompt, config=config)
    return getattr(msg, "content", str(msg)).strip()


def answer_question(question: str) -> dict:
    """Spusti pipeline pro jeden dotaz. Vraci {answer, cypher, rows}."""
    from neo4j.exceptions import CypherSyntaxError

    llm = _llm()
    graph = _graph()
    config = {"callbacks": _langfuse_callbacks()}
    schema = graph.schema

    base_prompt = CYPHER_GENERATION_TEMPLATE.format(schema=schema, question=question)
    cypher = _sanitize(_invoke_text(llm, base_prompt, config))

    if not is_read_only(cypher):
        logger.error("Zablokovan zapisovy Cypher: %s", cypher)
        return {
            "answer": "Dotaz byl zamitnut: vygenerovany Cypher nebyl jen pro cteni.",
            "cypher": cypher,
            "rows": [],
        }

    rows: list = []
    try:
        rows = graph.query(cypher)
    except CypherSyntaxError as exc:
        logger.warning("Cypher syntax error, zkousim opravu: %s", exc)
        fix_prompt = base_prompt + CYPHER_FIX_SUFFIX.format(error=str(exc)) + (
            f"\nPuvodni Cypher:\n{cypher}"
        )
        cypher = _sanitize(_invoke_text(llm, fix_prompt, config))
        if not is_read_only(cypher):
            return {
                "answer": "Dotaz byl zamitnut: opraveny Cypher nebyl jen pro cteni.",
                "cypher": cypher,
                "rows": [],
            }
        try:
            rows = graph.query(cypher)
        except CypherSyntaxError as exc2:
            logger.error("Cypher se nepodarilo opravit: %s", exc2)
            return {
                "answer": "Nepodarilo se sestavit platny dotaz. Zkus ho preformulovat.",
                "cypher": cypher,
                "rows": [],
            }

    rows = rows[: settings.query_top_k]
    qa_prompt = CYPHER_QA_TEMPLATE.format(context=str(rows), question=question)
    answer = _invoke_text(llm, qa_prompt, config)
    return {"answer": answer, "cypher": cypher, "rows": rows}
