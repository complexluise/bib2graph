# ROADMAP — bib2graph (secuencia de construcción desde cero)

> Secuencia de construcción **clean-room**, no una migración de v0. El orden es deliberado: el
> **núcleo puro y sus tests van primero**, después las **costuras por defecto** (store stateful
> y source OpenAlex) hasta tener el pipeline con biblioteca viva funcionando, y recién después
> lo opcional. Cada hito declara **qué se vuelve posible/testeable**. Fecha: 2026-06-15.
>
> Reordenado tras el **giro** (`Notas/04`–`07`) y los ADR
> [0007](decisiones/0007-openalex-backbone.md) (OpenAlex backbone),
> [0008](decisiones/0008-wedge-forrajeo.md) (wedge = forrajeo),
> [0009](decisiones/0009-biblioteca-viva-duckdb.md) (biblioteca viva en DuckDB),
> [0010](decisiones/0010-agente-native-columna.md) (agente-native columna),
> [0011](decisiones/0011-thesaurus-multilingue.md) (thesaurus). Diseño objetivo en
> [`ARCHITECTURE.md`](ARCHITECTURE.md); contratos en [`API.md`](API.md) (*pendiente de
> reconciliar*).

## Principio de orden

De adentro hacia afuera: primero lo que no tiene dependencias externas (núcleo puro),
validándolo con tests; luego las costuras por defecto, primero la **local** (DuckDB, sin red) y
después la de **red** (OpenAlex); por último lo opcional. El núcleo puro nunca depende de una
costura.

---

## Hito 0 — Andamiaje del proyecto

- Estructura del paquete y `pyproject.toml` con **núcleo** (`pyarrow`, `pydantic`, `networkx`,
  `click`, `tqdm`, **`duckdb`**, **cliente OpenAlex**) y extras declarados pero mínimos
  (`[zotero]`, `[s2]`, `[neo4j]`, `[viz]`, `[dedup]`, `[llm]`; ADR 0005).
- **Tooling desde el día uno** (ADR 0006): `ruff`, `mypy`, `pytest`, `pre-commit`, `commitizen`,
  `release-please`, GitHub Actions. SemVer estricto, `CHANGELOG.md` auto, `CONTRIBUTING.md`.
- **Principios agente-native adoptados desde el inicio** (ADR 0010): convención de doble salida y
  exit codes documentada antes del primer comando.
- Configuración **inyectada**, sin secretos ni efectos de import.

**Se vuelve posible:** instalar el esqueleto y correr CI; el primer commit respeta semver +
changelog + pre-commit.

---

## Hito 1 — Núcleo: tabla canónica `Corpus` (PIEDRA ANGULAR)

- Schema Arrow + modelos Pydantic v2 para `Corpus` (columnas en `API.md` §1), incluyendo el
  **estado de curación** (`is_seed`, `curation_status`, `provenance`) que sostiene la biblioteca
  viva (ADR 0009).
- `Corpus` wrapper: `from_arrow`, `to_arrow`, `add_paper`, `merge` (idempotente por `id`/`doi`),
  `seeds`, `materialize`.
- `Snapshot` **exportable**: `corpus.parquet` + `manifest.json` (hash, schema_version,
  lib_version, fuentes, filtros/conteos, fecha).
- **Tests unitarios** sobre tablas chiquitas: construcción, dedup, idempotencia de `merge`,
  export+reload, hash estable.

**Se vuelve posible:** representar un corpus en memoria, exportar un snapshot reproducible y
releerlo. **Sin servidores, sin red.** La testabilidad que v0 nunca tuvo.

---

## Hito 2 — Núcleo: proyectores + analizadores + exportadores + `Networks.quick`

- `Projector` (función pura `pa.Table → nx.Graph`): **acoplamiento bibliográfico sobre corpus
  completo** (ciudadano de primera), co-autoría, instituciones, co-ocurrencia de keywords; y
  co-citación (documentando su prerrequisito de segundo nivel de fetch).
- `Analyzer`: métricas, centralidad, comunidades (fallo explícito si falta `python-louvain`),
  **asortatividad** (atributo categórico configurable + grado) y **composición de comunidades**
  con **disclaimer de proxy**, informe de calidad ([`metodología.md`](metodología.md) §4) con
  umbrales **configurables**.
- `Exporter` (GraphML, CSV). `Networks.build(corpus, spec)` (hook) y `Networks.quick(corpus)`.
- **Tests** sobre grafos sintéticos con resultados conocidos.

**Se vuelve posible:** dado un `Corpus`, producir las redes, métricas, comunidades y
asortatividad, y exportarlas — todo puro y testeado.

---

## Hito 3 — Costura por defecto (local): `DuckDBStore` stateful (biblioteca viva)

- `DuckDBStore` (núcleo, **por defecto**; ADR 0009): persiste la tabla Arrow **entre corridas** +
  tablas de **procedencia y decisiones de curación** (aceptar/rechazar). Query SQL sobre el
  corpus. `snapshot()` exporta el estado vivo a un snapshot sellado.
- **Tests** con DuckDB en proceso (sin servidores): persistir, releer, acumular entre "corridas",
  registrar procedencia, exportar snapshot.

**Se vuelve posible:** una **biblioteca viva** que crece y se cura entre corridas, sin
infraestructura. El estado deja de vivir en la sesión.

---

## Hito 4 — Costura por defecto (red): `OpenAlexSource`

- `OpenAlexSource` (ADR 0007): traduce la **ecuación de búsqueda** a query OpenAlex, expone la
  **query ejecutada + reporte de traducción**, y trae metadatos + `references_id` + `cited_by_id`
  + afiliaciones **per-autor**. **Pool cortés** (email inyectado). Escape hatch: query nativa.
- `BibtexSource` **secundaria** (sembrar desde *pearls*), con el pre-procesador que corrige el
  bug de `bibtexparser` (T1 del sandbox).
- **Tests** con respuestas de la API **simuladas** (`responses`/`httpx.MockTransport`); **sin red
  en CI**.

**Se vuelve posible:** sembrar el corpus desde una ecuación consciente (o un `.bib`), con la
query registrada para reproducir.

---

## Hito 5 — Forrajeo/chaining + `Preprocessor` núcleo

- **Forrajeo** (inserción de IA nº1; ADR 0008): backward/forward chaining sobre OpenAlex,
  **ranking por *information scent***, **profundidad 1** (opt-in 2), **preview de crecimiento** y
  **tope**.
- `Preprocessor` núcleo: `normalize` (nombres, periodización) + **thesaurus multilingüe
  determinista** (en/es/pt, JSON portable; ADR 0011). Idempotente.
- **Tests** del ranking, del preview/tope y del thesaurus (idempotencia, multilingüe).

**Se vuelve posible:** expandir el corpus con candidatos rankeados (no lista plana) y normalizar
keywords multilingües para que la red de co-word no quede dispersa.

---

## Hito 6 — CLI agente-native como API (HITO DE PRODUCTO)

- CLI (Click) delgado: `seed`, `chain`, `curate`, `build`, `export`, `snapshot`, `inspect`,
  `validate`. **Cada subcomando con `--json`, exit codes (0–5), errores accionables, `--help`
  rico** (ADR 0010). Sin estado entre invocaciones (el estado vive en DuckDB).
- **Tests de contrato** de la salida `--json` (que no driftee).

**Se vuelve posible:** el **primer flujo de 10 minutos** — de una **ecuación** a un **GraphML**,
sobre una **biblioteca viva**, **sin escribir código ni servidores**. Un agente puede orquestar
`bib2graph` vía subprocess + JSON. *(Criterio "V1 hecha" del PRD §9.)*

---

## Hito 7 — Deduplicación fuzzy (extra `[dedup]`)

- `deduplicate_authors` / `deduplicate_keywords` (lo fuzzy; el determinístico ya está en el
  `Preprocessor` del Hito 5). **Tests** de similitud y mapeo.

**Se vuelve posible:** redes de autor/keyword limpias de duplicados aproximados.

---

## Hito 8 — `Enricher` opt-in: resolución de refs + co-citación (extra `[s2]`)

- `Enricher` (ya **no estructural**; ADR 0007): **resolver `references` a DOI canónico** (T8) y el
  **segundo nivel de fetch** (citantes con sus citas) que habilita la **co-citación** completa.
- **Tests** con API simulada; sin red en CI.

**Se vuelve posible:** la red de **co-citación** end-to-end (la más cara) y la interoperabilidad
de referencias cross-source (OpenAlex ↔ `.bib`).

---

## Hito 9 — Capa declarativa: `NetworkSpec` (v0.2)

- `NetworkSpec` como `BaseModel` con loader YAML; `b2g networks --spec redes.yaml --json`.
- **Tests** de carga/validación y equivalencia con `Networks.quick`.

**Se vuelve posible:** pipelines reproducibles versionados en git (un YAML describe qué se
calcula). Abre la puerta a un GUI (editor de `NetworkSpec`).

---

## Hito 10 — Visualización (extra `[viz]`)

- Figuras de redes/comunidades con `matplotlib`/`seaborn`, fuera del núcleo liviano.

---

## Hito 11 — Costuras externas de biblioteca/persistencia (post-V1)

- **`ZoteroStore`** (extra `[zotero]`, **V1.1**): sincronizar la biblioteca viva con una colección
  Zotero (leer semillas / devolver lo aceptado). Costura opt-in, no el corazón (ADR 0009).
- **`Neo4jStore`** (extra `[neo4j]`, post-V1.2): adaptador tabla→grafo para consultas Cypher.
  **Ya no es sustrato** (ADR 0002).

---

## Costuras futuras (NO planificadas — declaradas explícitamente)

Marcadas como no implementadas hasta que exista decisión de producto y código real (lección 5):

- `Source`: `RisSource`, `CsvSource`.
- `Enricher`: `CrossRefEnricher`, `ScopusEnricher`.
- **Fallback fuzzy/semántico del thesaurus** (embeddings o LLM, extra `[llm]`) → v0.2 (ADR 0011).
- **Máquina de tensiones** (inserción de IA nº2) → **v2** (ADR 0008).
- Tool schemas JSON / servidor MCP → posterior, si la demanda lo justifica. El CLI ya cubre la
  frontera programática desde el Hito 6.

No se prometen ni se cablean clientes que no se usan.
