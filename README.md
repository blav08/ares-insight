# ARES Insight

Konverzacni **GraphRAG** nad ceskymi otevrenymi firemnimi daty (ARES). Ptas se cesky
na firmy a jejich vztahy, system pod kapotou prohleda graf (Neo4j) pres text-to-Cypher
(LangChain + Claude) a vrati odpoved i s podkladovymi daty.

> Data: ARES - otevrena data Ministerstva financi. Skutecne majitele (ESM, od 12/2025
> neverejne) projekt vedome neresi.

## Stack
Python · Neo4j (AuraDB) · LangChain (GraphCypherQAChain) · Claude (Anthropic) ·
FastAPI · Streamlit · Langfuse · Docker · GitHub Actions

## Struktura
```
src/ares_insight/
  config.py            # nastaveni + definice vyrezu dat (NACE, region, rok)
  ingest/              # Faze 1: fetch -> transform -> load do Neo4j
  graph/               # Neo4j driver + schema (uzly, vztahy, indexy)
  query/               # Faze 2: text-to-Cypher + synteza odpovedi
  api/                 # Faze 3: FastAPI /query
  observability/       # Langfuse
app/streamlit_app.py   # Faze 3: chatove UI
scripts/run_ingest.py  # spusteni ingestu
```

## Setup (Faze 0)

### 1. Prostredi
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

### 2. Externi ucty (zaloz si je sam, klice dej do .env)
- **Neo4j AuraDB Free** - https://neo4j.com/product/auradb/ -> vytvor free instanci,
  uloz URI + heslo z credentials souboru. (Free tier ma limit uzlu/vztahu a po par
  dnech necinnosti se uspi - da se probudit.)
- **Anthropic API klic** - https://console.anthropic.com -> API key.
- **Langfuse** - https://cloud.langfuse.com -> novy projekt -> public + secret key.

Pro lokalni vyvoj nemusis hned na AuraDB - rozjed lokalni Neo4j:
```bash
make neo4j-up      # docker compose: Neo4j na localhost:7474 / :7687
```
(heslo v .env nech `local-dev-password`, at sedi s compose)

### 3. Vyrez dat
V `src/ares_insight/config.py` jsou parametry vyrezu - default: NACE 62/63 (IT), Praha.
Pokud bude slice moc velky na free tier, zuz ho (`founded_from_year`, uzsi NACE).

## Prikazy
```bash
make lint      # ruff
make test      # pytest
make ingest    # naplnit graf (Faze 1)
make api       # FastAPI (Faze 3)
make ui        # Streamlit (Faze 3)
```

## Overeni grafu (po ingestu)

Otevri Neo4j Browser (http://localhost:7474, login `neo4j` / heslo z `.env`) a spust:

```cypher
// Pocty uzlu a vztahu
MATCH (n) RETURN labels(n)[0] AS typ, count(*) ORDER BY count(*) DESC;
MATCH ()-[r]->() RETURN type(r) AS vztah, count(*) ORDER BY count(*) DESC;

// Firma se statutary a sidlem
MATCH (p:Person)-[:DIRECTOR_OF]->(c:Company)-[:REGISTERED_AT]->(a:Address)
RETURN p, c, a LIMIT 25;

// Firmy sdilejici adresu (vztah, ktery ARES sam neumi)
MATCH (c1:Company)-[:SHARES_ADDRESS_WITH]-(c2:Company) RETURN c1, c2 LIMIT 50;

// Osoba ve vice firmach (propojeni pres statutary)
MATCH (p:Person)-[:DIRECTOR_OF]->(c:Company)
WITH p, count(c) AS firem WHERE firem > 1
RETURN p.name, firem ORDER BY firem DESC LIMIT 20;
```

Referencni objem vyrezu (NACE 62/63, Praha, a.s.): ~2 300 firem, ~3 400 osob,
~1 200 adres, ~4 200 vztahu DIRECTOR_OF.

## Roadmapa
- [x] Faze 0 - kostra, setup, vyrez
- [x] Faze 1 - ingest (ARES -> Neo4j)
- [ ] Faze 2 - text-to-Cypher Q&A
- [ ] Faze 3 - FastAPI + Streamlit
- [ ] Faze 4 - Docker, CI/CD, deploy, Langfuse (<- live URL)
- [ ] Faze 5 - vektorova cesta, viz grafu, verejne zakazky
