.PHONY: install lint test neo4j-up neo4j-down ingest query api ui

install:
	pip install -e ".[dev]"

lint:
	ruff check .

test:
	pytest -q

neo4j-up:
	docker compose up -d

neo4j-down:
	docker compose down

ingest:
	python scripts/run_ingest.py

query:
	python scripts/run_query.py

api:
	uvicorn ares_insight.api.main:app --reload

ui:
	streamlit run app/streamlit_app.py
