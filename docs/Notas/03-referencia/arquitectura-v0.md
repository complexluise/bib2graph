# ARQUITECTURA — bib2graph (estado real / as-built)

> Arquitectura tal como está construida hoy, no la deseada. Referencias a `archivo:línea`
> apuntan al código real. Fecha: 2026-06-14.

## 1. Vista de alto nivel

```
BibTeX ──► [ingesta] ──► Neo4j ──► [enriquecimiento] ──► Neo4j ──► [análisis] ──► GraphML + CSV
                          (Semantic Scholar)                      (NetworkX)
```

Neo4j es el sistema de registro. Las tres fases son **clases**, cada una instanciada con
credenciales de Neo4j; configuran la conexión global de neomodel vía
`config.DATABASE_URL = f"bolt://{user}:{password}@{host}"`.

## 2. Capas (CLI → orquestación → clases de fase)

```
bib2graph/cli.py        Click. Comandos en español. Define opciones comunes Neo4j.
        │               (cli.main es el entry point en pyproject.toml:10)
        ▼
bib2graph/main.py       Funciones de orquestación: ingestar_datos, enriquecer_datos,
        │               crear_relaciones_red, analizar_red, ejecutar_pipeline_completo,
        │               deduplicate_authors, deduplicate_keywords.
        │               Aquí vive la validación de parámetros, tqdm, logging y el
        │               mapeo TIPOS_REDES → método del analyzer.
        ▼
Clases de fase          BibliometricDataLoader      (consigue_los_articulos.py)
                        BibliometricDataEnricher    (enriquecimiento.py)
                        BibliometricNetworkAnalyzer (analisis_red.py)
                        KeywordDeduplicator         (deduplicacion_keywords.py)
        ▼
bib2graph/models.py     ODM neomodel sobre Neo4j (esquema del grafo).
bib2graph/config.py     Neo4jConfig (env), TIPOS_REDES, defaults, VERSION.
```

`__main__.py` permite `python -m bib2graph`. `__init__.py` re-exporta las tres clases y las
funciones de orquestación.

## 3. Las tres fases

### Fase 1 — Ingesta (`BibliometricDataLoader`, `consigue_los_articulos.py`)

1. `load_bibtex` parsea el `.bib` con `bibtexparser`.
2. `normalize_metadata` mapea cada entry a un dict común (solo `bibtex`; `csv`/`json` →
   `NotImplementedError`, líneas 66 y 99).
3. `create_graph_nodes` crea, por paper:
   - `Paper` (con `is_seed=True`),
   - `Publisher` (`PUBLISHED_BY`),
   - `RawAuthor` por cada autor crudo (`AUTHORED_RAW`),
   - `Keyword` (`HAS_KEYWORD`), `ResearchArea` (`RESEARCH_AREA`), `Institution`
     (`ASSOCIATED_WITH`).
   Todo con patrón get-or-create (`.nodes.get` / `except DoesNotExist` → `.save()`).

Flujo de archivo: `process_file` (un archivo) / `process_directory` (carpeta, por extensión).

### Fase 2 — Enriquecimiento (`BibliometricDataEnricher`, `enriquecimiento.py`)

1. `get_papers_to_enrich`: papers con DOI no vacío.
2. `enrich_from_semantic_scholar`: GET a `https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}`
   pidiendo `citations`, `references`, `authors` (con `authorId`, `externalIds`).
   - 403 con API key → reintenta **sin** key (endpoint público).
   - 404 → omite. 429 → espera 60s y omite ese paper.
3. `update_neo4j_with_enriched_data`:
   - crea `Paper` citados/referenciados (con `is_seed=False`) y relaciones `CITED` / `REFERENCES`;
   - crea/actualiza `Author` por `semantic_scholar_id` (o por nombre), enlaza `AUTHORED`;
   - conecta `RawAuthor` → `Author` (`NORMALIZED_AS`) cuando los nombres son similares
     (`similar_names`, fuzzy `token_sort_ratio`).
4. `enrich_all_papers`: itera todos los papers con `time.sleep(4)` entre cada uno (~0.25 RPS).

Tras el enriquecimiento, `enriquecer_datos` (`main.py:277`) ejecuta además:
`deduplicate_authors` (combina `Author` con el mismo `semantic_scholar_id`) y
`deduplicate_keywords` (`KeywordDeduplicator`).

> Nota: las ramas de `institutions` y `keywords` dentro de `update_neo4j_with_enriched_data`
> (líneas 264-289) iteran sobre claves que `enrich_from_semantic_scholar` **nunca rellena**
> (`enriched_data` solo trae `citations/references/authors`). Son código muerto hoy. Ver ROADMAP.

### Fase 3 — Análisis (`BibliometricNetworkAnalyzer`, `analisis_red.py`)

Patrón en dos pasos: **primero** crea la relación de red en Neo4j (Cypher `MERGE ... ON CREATE
SET r.weight`), **después** la extrae a un `networkx.Graph`.

| Red | Crear relación | Extraer |
|-----|----------------|---------|
| co-citación | `create_co_citation_relationships` → `CO_CITED_WITH` (refs compartidas entre `Paper {is_seed:True}`) | `extract_co_citation_network` (+ `generate_quality_report`) |
| colaboración autor | `create_author_collaboration_relationships` → `COLLABORATED_WITH` | `extract_author_collaboration_network` |
| colaboración institución | `create_institution_collaboration_relationships` → `COLLABORATED_WITH` | `extract_institution_collaboration_network` |
| co-ocurrencia keyword | `create_keyword_co_occurrence_relationships` → `CO_OCCURS_WITH` | `extract_keyword_co_occurrence_network` |

Luego: `calculate_network_metrics`, `calculate_node_centrality_metrics`,
`detect_communities` (louvain / label propagation / greedy modularity),
`export_graph_to_graphml`, `export_graph_to_csv`. Existe también un
`extract_area_research_co_occurence_network` no expuesto en la CLI.

## 4. Esquema del grafo Neo4j (`models.py`)

**Nodos** (`StructuredNode`):

| Nodo | Propiedades clave |
|------|-------------------|
| `Paper` (hub) | `doi` (unique), `title`, `year`, `source`, `volume`, `issue`, `pages`, `month`, `issn`, `isbn`, `url`, `language`, `type`, `abstract`, `is_seed` |
| `RawAuthor` | `name` (index) |
| `Author` | `name` (index), `orcid` (index), `semantic_scholar_id` (unique) |
| `Keyword` | `name` (unique), `source_keyword` |
| `Institution` | `name` (unique) |
| `ResearchArea` | `name` (unique) |
| `Publisher` | `name` (unique), `address` |

**Relaciones** (origen → destino):

```
Paper      -[:CITED]->          Paper
Paper      -[:REFERENCES]->     Paper
Paper      -[:CO_CITED_WITH]-   Paper      (CoCitedRelationship.weight)
Author     -[:AUTHORED]->       Paper
RawAuthor  -[:AUTHORED_RAW]->   Paper
RawAuthor  -[:NORMALIZED_AS]->  Author
Paper      -[:HAS_KEYWORD]->    Keyword
Keyword    -[:CO_OCCURS_WITH]-  Keyword    (creada en análisis)
Paper      -[:ASSOCIATED_WITH]->Institution
Author     -[:AFFILIATED_WITH]->Institution
Paper      -[:RESEARCH_AREA]->  ResearchArea
Paper      -[:PUBLISHED_BY]->   Publisher
Author     -[:COLLABORATED_WITH]-Author    (creada en análisis)
Institution-[:COLLABORATED_WITH]-Institution (creada en análisis)
```

El split `RawAuthor` → `Author` es deliberado: nombres crudos del BibTeX normalizados a
nodos canónicos durante el enriquecimiento.

> **Fuentes de verdad del esquema** y su drift actual: `models.py` es la fuente autoritativa.
> El docstring de `analisis/agente_navegacion_grafo.py:7-37` documenta un esquema **divergente**
> (declara `Institution` con `address`, y una relación `Paper -[:CITED_BY]-> Paper` que no
> existe — el modelo tiene `CITED`). Ver ROADMAP §drift de esquema.

## 5. Configuración

- `Neo4jConfig` (`config.py:11`) lee `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` del entorno,
  con defaults `bolt://localhost:7687` / `neo4j` / *(sin password por seguridad)*.
- **`.env` no se autocarga** (`python-dotenv` no es dependencia). La CLI pasa los valores como
  defaults de las opciones Click.
- `TIPOS_REDES` (`config.py:42`) traduce clave CLI español → nombre de red interno usado en
  `main.py`/`analisis_red.py`.
- **Cada módulo de fase define además sus propios defaults hardcodeados** a nivel de módulo
  (`NEO4J_PASSWORD = "password"` en `consigue_los_articulos.py:19`, `enriquecimiento.py:50`,
  `analisis_red.py:19`) y configura `config.DATABASE_URL` al importarse. La ruta sana es
  pasar credenciales por la CLI; estos defaults son legado. Ver ROADMAP.

## 6. Dependencias externas

| Servicio | Cliente | Estado real |
|----------|---------|-------------|
| **Semantic Scholar** | `requests` directo + `pys2`/`s2` importado | **Usado** para citas/referencias/autores. Fallback a endpoint público en 403. |
| **CrossRef** | `crossrefapi` (`Works()`, instanciado en `__init__`) | **Inicializado pero no consultado** en el flujo de enriquecimiento. |
| **Scopus** | `elsapy` (`ElsClient`, solo si `SCOPUS_API_KEY`) | **Inicializado condicionalmente, no consultado.** |

Otras dependencias relevantes (`pyproject.toml`): `neomodel` (ODM), `networkx` (redes),
`bibtexparser`, `fuzzywuzzy` + `python-levenshtein` (matching), `pandas`, `matplotlib`/`seaborn`
(scripts de análisis), `tqdm`, `click`. Detección de comunidades Louvain depende de
`python-louvain` (importado como `community`), que **no figura en `pyproject.toml`**: si falta,
`detect_communities` cae a greedy modularity (`analisis_red.py:772-781`).

## 7. `analisis/` (scripts standalone) vs `bib2graph/` (paquete)

`analisis/` contiene scripts jupytext (formato de celdas `# %%`) que se conectan
**directamente a Neo4j** y escriben figuras en `analisis/figuras/`. **No son parte del
paquete** y **no usan el plumbing de config de la CLI**:

- `centralidad_keywords.py` — betweenness sobre la red de co-ocurrencia de keywords.
- `agente_navegacion_grafo.py` — funciones de consulta de alto nivel sobre el grafo para
  un agente; incluye el docstring de esquema mencionado en §4.
- Notebooks `.ipynb` de análisis bibliométrico, calidad de datos y estructura de redes.

Ambos scripts `.py` hardcodean su conexión con `NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD",
"12345678")` (`centralidad_keywords.py:27`, `agente_navegacion_grafo.py:46`) — un default
**distinto** del `"password"` del paquete. Conviven dos convenciones de conexión en el repo.

## 8. Tests

`tests/test_imports.py` cubre **solo importabilidad** del paquete, de las tres clases y la
presencia de `__version__`. No hay cobertura de lógica de pipeline, parsing, Cypher ni métricas.
No hay linter ni formatter configurado.
