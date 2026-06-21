"""Faze 2: text-to-Cypher nad Neo4j grafem.

Pouziva LangChain GraphCypherQAChain s Claudem: prelozi cesky dotaz na Cypher,
spusti ho a z vyslednych radku slozi odpoved.
"""

from ares_insight.config import settings  # noqa: F401  (pouzije se ve Fazi 2)


def build_chain():
    """Sestavi GraphCypherQAChain (Neo4jGraph + ChatAnthropic).

    TODO (Faze 2):
      - from langchain_neo4j import Neo4jGraph, GraphCypherQAChain
      - from langchain_anthropic import ChatAnthropic
      - zapojit settings.neo4j_* a settings.anthropic_*
      - predat schema, aby LLM znal labely/vztahy
    """
    raise NotImplementedError("Faze 2: postavit text-to-Cypher chain")


def answer_question(question: str) -> dict:
    """Spusti chain pro jeden dotaz. Vraci {answer, cypher, rows}.

    TODO (Faze 2): obalit build_chain(); zachytit vygenerovany Cypher + radky,
    aby UI mohlo zobrazit podkladova data (podminka ARES: drzet to overitelne).
    """
    raise NotImplementedError("Faze 2")
