"""Inicializace Langfuse klienta (LLM observability)."""

from ares_insight.config import settings


def get_langfuse():
    """Vrati nakonfigurovaneho Langfuse klienta (nebo None, kdyz chybi klice).

    TODO (Faze 2+): instrumentovat query chain - tracovat zvolenou cestu,
    vygenerovany Cypher, retrieval, latenci, tokeny, cenu.
    """
    if not settings.langfuse_secret_key:
        return None
    from langfuse import Langfuse

    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )
