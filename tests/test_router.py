"""Offline testy routeru a textove reprezentace firmy (Faze 5). Zadny model/sit."""

from ares_insight.query.embeddings import company_text
from ares_insight.query.router import heuristic_route, route


def test_heuristic_structured():
    assert heuristic_route("Kolik firem je v databazi?") == "cypher"
    assert heuristic_route("Najdi statutary firmy X") == "cypher"
    assert heuristic_route("Které firmy sídlí na stejné adrese?") == "cypher"


def test_heuristic_semantic():
    assert heuristic_route("Firmy zamerene na kyberbezpecnost") == "semantic"
    assert heuristic_route("Čím se zabývá tahle oblast firem?") == "semantic"


def test_heuristic_ambiguous():
    assert heuristic_route("Řekni mi něco zajímavého") is None


def test_route_defaults_to_cypher_without_llm():
    # nejasny dotaz + zadny llm -> bezpecny default
    assert route("Řekni mi něco zajímavého", llm=None) == "cypher"


def test_route_uses_llm_for_ambiguous():
    class FakeMsg:
        content = "semantic"

    class FakeLLM:
        def invoke(self, prompt):
            return FakeMsg()

    assert route("Řekni mi něco zajímavého", llm=FakeLLM()) == "semantic"


def test_company_text():
    txt = company_text({"name": "ACME a.s.", "nace": ["62", "63"], "municipality": "Praha"})
    assert "ACME a.s." in txt
    assert "62, 63" in txt
    assert "Praha" in txt
