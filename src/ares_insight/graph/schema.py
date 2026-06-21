"""Schema grafu: labely uzlu, typy vztahu a setup Cypher.

Pouzivame anglicke labely (Company, Person, Address...) misto ceskych. Duvody:
konvencni pro portfolio, lepe funguje s LLM-generovanym Cypher, citelne i pro
neceske recenzenty. Hodnoty vlastnosti (jmena atd.) zustavaji v puvodni cestine.
Kdyz chces ceske labely, zmen konstanty nize.
"""

# Labely uzlu
COMPANY = "Company"
PERSON = "Person"
ADDRESS = "Address"

# Typy vztahu
DIRECTOR_OF = "DIRECTOR_OF"  # (Person)-[:DIRECTOR_OF]->(Company)
REGISTERED_AT = "REGISTERED_AT"  # (Company)-[:REGISTERED_AT]->(Address)
SHARES_ADDRESS_WITH = "SHARES_ADDRESS_WITH"  # odvozeny (Company)-[]-(Company)

# Constraints + indexy. Idempotentni (IF NOT EXISTS). Spustit jednou ve Fazi 1.
SCHEMA_STATEMENTS = [
    f"CREATE CONSTRAINT company_ico IF NOT EXISTS "
    f"FOR (c:{COMPANY}) REQUIRE c.ico IS UNIQUE",
    f"CREATE CONSTRAINT person_key IF NOT EXISTS "
    f"FOR (p:{PERSON}) REQUIRE p.person_key IS UNIQUE",
    f"CREATE CONSTRAINT address_key IF NOT EXISTS "
    f"FOR (a:{ADDRESS}) REQUIRE a.address_key IS UNIQUE",
    f"CREATE INDEX company_name IF NOT EXISTS FOR (c:{COMPANY}) ON (c.name)",
]

# Vektorovy index pro semantickou cestu (Faze 5). Dimenze podle embedding
# modelu; 384 odpovida vetsine multilingual sentence-transformers.
VECTOR_INDEX_STATEMENT = (
    f"CREATE VECTOR INDEX company_embedding IF NOT EXISTS "
    f"FOR (c:{COMPANY}) ON (c.embedding) "
    f"OPTIONS {{indexConfig: {{"
    f"`vector.dimensions`: 384, `vector.similarity_function`: 'cosine'}}}}"
)
