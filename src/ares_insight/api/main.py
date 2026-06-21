"""Faze 3: FastAPI app s endpointem /query."""

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="ARES Insight API")


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    answer: str
    cypher: str | None = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest):
    """TODO (Faze 3): zavolat ares_insight.query.cypher_chain.answer_question
    a obalit Langfuse tracingem."""
    raise NotImplementedError("Faze 3: zapojit query pipeline")
