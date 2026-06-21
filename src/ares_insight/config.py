"""Centralni nastaveni + definice vyrezu dat.

Hodnoty se nacitaji z .env (viz .env.example). Vyrez dat (NACE/region/forma) je
zamerne v configu, aby se dal trivialne menit bez zasahu do kodu.

Vyrez Faze 1 (rozhodnuti v projektu): NACE 62/63 (IT), sidlo Praha, jen a.s.
(pravni forma 121). Duvod: akciovky maji predstavenstva (vic clenu) -> bohatsi
graf vztahu, a cely vyrez (~2 700 firem) se bezpecne vejde do AuraDB Free.

Poznamky k realnemu ARES API (overeno proti live API, Faze 1):
- vyhledavaci endpoint ma strop 1000 vysledku na dotaz -> velke mnoziny se
  shardiji po pražskych spravnich obvodech (`spravni_obvody`).
- filtr `czNace` bere jen kody realne ulozene v indexu; pouzitelne jsou
  divizni "62" a "63" (granularni 5-mistne nejsou naplnene).
- filtr neumi rok vzniku -> `founded_from_year` se aplikuje az klientsky.
"""

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Neo4j ---
    # Pozn.: AuraDB credentials soubor pouziva NEO4J_USERNAME a u nekterych
    # instanci je uzivatel = ID instance (ne "neo4j"). Cteme proto i
    # NEO4J_USERNAME, aby slo Aura texták vlozit primo bez prejmenovani.
    neo4j_uri: str = Field(default="bolt://localhost:7687")
    neo4j_user: str = Field(
        default="neo4j",
        validation_alias=AliasChoices("neo4j_user", "neo4j_username"),
    )
    neo4j_password: str = Field(default="local-dev-password")
    # Jmeno databaze. U nekterych Aura instanci != "neo4j" (= ID instance).
    neo4j_database: str = Field(default="neo4j")

    # --- Anthropic ---
    anthropic_api_key: str = Field(default="")
    anthropic_model: str = Field(default="claude-haiku-4-5-20251001")
    # Max poctu radku z grafu predanych LLM k synteze odpovedi (Faze 2).
    query_top_k: int = Field(default=50)

    # --- API / UI (Faze 3) ---
    # URL, na ktere Streamlit UI vola FastAPI /query.
    api_url: str = Field(default="http://localhost:8000")

    # --- Langfuse ---
    langfuse_public_key: str = Field(default="")
    langfuse_secret_key: str = Field(default="")
    langfuse_host: str = Field(default="https://cloud.langfuse.com")

    # --- ARES API ---
    ares_base_url: str = Field(
        default="https://ares.gov.cz/ekonomicke-subjekty-v-be/rest"
    )
    # Strankovani vyhledavani (max velikost stranky, kterou API povoli).
    ares_page_size: int = Field(default=500)
    # Tvrdy strop vyhledavani na jeden dotaz (dany API).
    ares_max_results_per_query: int = Field(default=1000)
    # Throttling, aby se zustalo vyrazne pod limitem 500 dotazu/min na API.
    ares_requests_per_minute: int = Field(default=200)
    ares_timeout_s: float = Field(default=30.0)
    ares_max_retries: int = Field(default=3)

    # --- Vyrez dat (rozhodnuti Faze 1) ---
    # CZ-NACE: 62 = cinnosti v oblasti IT, 63 = informacni cinnosti.
    nace_prefixes: list[str] = Field(default=["62", "63"])
    # Pravni formy: 121 = akciova spolecnost. (112 = s.r.o., kdyby se vyrez rozsiril.)
    legal_forms: list[str] = Field(default=["121"])
    # Region (sidlo). Praha = kod obce 554782.
    region: str = Field(default="Praha")
    kod_obce: int = Field(default=554782)
    # Pražske spravni obvody (kodSpravnihoObvodu) pro shardovani dotazu nad 1000.
    spravni_obvody: list[int] = Field(
        default=[
            19, 27, 35, 43, 51, 60, 78, 86, 94, 108,
            116, 124, 132, 140, 147, 159, 167, 175, 183,
            191, 205, 213, 221,
        ]
    )
    # Volitelne: jen firmy vznikle od tohoto roku (None = bez limitu).
    # API to neumi -> aplikuje se klientsky po stazeni.
    founded_from_year: int | None = Field(default=None)


settings = Settings()
