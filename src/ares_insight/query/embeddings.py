"""Faze 5: textove embeddingy pro semantickou (vektorovou) cestu.

Pouziva fastembed (ONNX, bez torch) + multilingual model, ktery umi cesky.
Model `paraphrase-multilingual-MiniLM-L12-v2` ma 384 dimenzi -> sedi s vektorovym
indexem v graph/schema.py (VECTOR_INDEX_STATEMENT, 384, cosine). Tenhle model
(na rozdil od e5) nepouziva zadne query/passage prefixy.
"""

from __future__ import annotations

from functools import lru_cache

EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBED_DIM = 384


@lru_cache(maxsize=1)
def _model():
    # Import az tady - fastembed pri prvnim pouziti stahne model (~130 MB).
    from fastembed import TextEmbedding

    return TextEmbedding(model_name=EMBED_MODEL)


def embed_passages(texts: list[str]) -> list[list[float]]:
    """Embeddingy dokumentu (firem)."""
    return [vec.tolist() for vec in _model().embed(texts)]


def embed_query(text: str) -> list[float]:
    """Embedding dotazu."""
    vec = next(iter(_model().embed([text])))
    return vec.tolist()


def company_text(company: dict) -> str:
    """Textova reprezentace firmy pro embedding (jmeno + obor + sidlo)."""
    name = company.get("name") or ""
    nace = company.get("nace") or []
    nace_str = ", ".join(nace) if isinstance(nace, list) else str(nace)
    place = company.get("municipality") or company.get("address_text") or ""
    parts = [name]
    if nace_str:
        parts.append(f"obor NACE: {nace_str}")
    if place:
        parts.append(f"sidlo: {place}")
    return ". ".join(parts)
