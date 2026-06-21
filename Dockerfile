FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

COPY app ./app
COPY scripts ./scripts

EXPOSE 8000
# Default: API. Pro Streamlit UI prepis CMD.
CMD ["uvicorn", "ares_insight.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
