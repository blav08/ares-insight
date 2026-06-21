FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

COPY app ./app
COPY scripts ./scripts

EXPOSE 8000
# Default: API. Hostingy (Render) predavaji port pres $PORT - shell forma ho
# expanduje; lokalne fallback na 8000.
CMD uvicorn ares_insight.api.main:app --host 0.0.0.0 --port ${PORT:-8000}
