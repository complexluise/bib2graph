# Changelog

Todos los cambios notables de `bib2graph` se documentan acá. El formato sigue
[Keep a Changelog](https://keepachangelog.com/es/1.1.0/), y este proyecto
adopta [Semantic Versioning](https://semver.org/lang/es/) (ver
[`VERSIONING.md`](./VERSIONING.md)).

Este changelog lo **gestionará `release-please`** (mecanismo de release diseñado; ver
[`VERSIONING.md`](./VERSIONING.md) y ADR 0006): su PR de release actualizará esta sección
desde los Conventional Commits. Como ese tooling **aún no está conectado** (no existe
`.github/` ni CI), por ahora las secciones se **mantienen a mano** antes de cada tag —con
`cz bump --dry-run` como ayuda de preview local— y la fuente de verdad es la historia de
commits.

## [Unreleased]

> **Modelo nuevo bloqueado por el PO (2026-06-15)** tras el red-team del AS-BUILT v0.2
> ([Nota 06](docs/Notas/06-critica-as-built-v0.2.md)): el **producto no usa IA generativa** (ADR
> 0022); **capa base** `constants`/`models`/`schemas` única (ADR 0023); enmiendas a
> 0008/0011/0016/0017/0020/0021. La **tanda de remediación R1–R5** del [roadmap](docs/ROADMAP.md) lo
> implementa **antes** de los Hitos 7–11. Esta sección documenta el diseño nuevo; el código se
> entrega por hito R.

### Changed (modelo / docs — diseño objetivo)
- **El producto NO usa IA generativa** (ADR 0022): el *information scent* del forrajeo deja de ser
  una heurística de frecuencia de enlace y pasa a **scent bibliométrico determinista vía proyectores**
  (acoplamiento/co-citación/centralidad), **sin LLM ni embeddings** (Hito R4). Un solo sentido de
  "AI-in-the-loop": el desarrollo es asistido por IA; el producto no.
- **Identidad ≠ procedencia** (ADR 0017 enmendado): el `corpus_hash` se computa **solo sobre contenido
  bibliográfico** (excluye `provenance`/timestamps); el reloj se inyecta en la **frontera CLI**;
  Louvain corre con `random_state` derivado del content-hash → **snapshot reproducible bit a bit**
  (Hito R2).
- **Ciclo = FSM cíclico de dominio** (`cycle.py`, ADR 0016 enmendado): `SEEDED→FORAGED→FILTERED→
  BUILT→MONITORED` con **`reseed`** (loop-back a `SEEDED` + contador de ronda, acumula) de primera
  clase; **curación transversal** visible en `b2g status` (ADR 0021 enmendado) (Hito R3).
- **Capa base de vocabulario + modelos** (ADR 0023): `constants.py` (`Col`/`CurationStatus`/
  `NetworkKind`) como fuente única de literales; `ProvenanceEvent(BaseModel)` con parseo que **falla
  ruidoso**; `PaperRow` ⇄ `CORPUS_SCHEMA` de una sola fuente (Hito R1).

### Removed (diseño objetivo)
- **`explain_candidate`, `foraging/explain.py` y el extra `[llm]`** se **eliminan** (ADR 0022): el
  producto no usa IA generativa (Hito R4).
- **La "máquina de tensiones"** (antigua "inserción de IA nº2") se **retira del producto** —no se
  difiere a v2, se borra (ADR 0008 enmendado). El **fallback semántico/LLM del thesaurus** también se
  retira (ADR 0011 enmendado): el thesaurus es curado y determinista.

### Fixed (objetivo — Hito R5)
- **UTF-8 en la frontera CLI** (envelope `--json` con acentos corruptos en Windows cp1252, Nota 06
  RAÍZ 3); **fin del O(n²) en carga** (bulk `Corpus.from_arrow` en los loaders); retry/backoff en
  `fetch_citing`; y los `except` anchos/footguns de la Nota 06 (rama muerta de `_errors.py`,
  auto-creación del store, `.bib`/filtros silenciosos, param muerto `g`, fallback `_lib_version`
  `"0.0.0"`).

> Próximo (tras R1–R5): **Hito 7** (deduplicación fuzzy, extra `[dedup]`).

## [0.2.0] - 2026-06-15

> **Hitos 5 y 6.** Forrajeo + CLI agente-native: el flujo `seed → chain → filter →
> build → export` corre de una **ecuación** a un **GraphML** **sin escribir código**,
> sobre la biblioteca viva. v0.2 con capacidades completas **del flujo** (no del producto:
> co-citación end-to-end y `explain_candidate`/`[llm]` quedan como stubs/futuros). Tag local
> anotado `v0.2.0` (publicación pendiente).

### Added
- **Forrajeo** (`Forager`: chaining backward/forward, ranking por *information
  scent* = **frecuencia de enlace** —heurística determinista, no IA/LLM—, `preview`
  sin red, filtros PRISMA que marcan `rejected`, `Preprocessor` + thesaurus
  multilingüe). `explain_candidate` (extra `[llm]`) es **stub**. ADR 0008/0011/0020.
- **CLI agente-native `b2g`** (`cli/`): 11 subcomandos (`seed`/`chain`/`filter`/
  `accept`/`reject`/`build`/`export`/`snapshot`/`status`/`inspect`/`validate`),
  envelope `--json` versionado, exit codes 0–5, `--store` global sin estado,
  transiciones `LoopState` automáticas. ADR 0021.

## [0.1.0] - 2026-06-15

> **Hitos 1–4 (+ rework 1.5).** Pipeline mínimo end-to-end: de una **ecuación de
> búsqueda a las redes bibliométricas desde código Python**, sobre una biblioteca
> viva en DuckDB. Tag local anotado `v0.1.0` (publicación pendiente).

### Added
- **Núcleo `Corpus`** (tabla canónica Arrow + Pydantic v2): identidad estable
  (`id`), `merge` idempotente, `accept`/`reject` con `provenance` (log de
  eventos), `snapshot`/`CorpusSnapshot` con `corpus_hash` reproducible. ADR 0013.
- **`TabularBackend` (Protocol) + `InMemoryBackend`** (núcleo puro) y
  **`DuckDBBackend`** (biblioteca viva por defecto: mutación por SQL, `LoopState`,
  single-writer); `DuckDBStore` como fachada de costura. El núcleo no importa
  `duckdb` (carga perezosa). ADR 0015/0016/0019.
- **Redes** (`networks/`): proyectores (acoplamiento, co-citación, co-autoría,
  instituciones, co-word), analizadores (métricas, centralidad, comunidades,
  asortatividad, calidad), exportadores GraphML/CSV, `Networks.quick`. ADR 0014.
- **Costuras `Source`** (`OpenAlexSource` con traducción de ecuación + reporte de
  límites; `BibtexSource`, extra `[bibtex]`). ADR 0007/0012/0017/0018.
- **2º giro** (ADR 0015–0019): `Corpus` sobre `TabularBackend`, máquina de estados
  del lazo (`LoopState`), reproducibilidad por snapshot sellado, `Source`
  agnóstico (mínimo universal vs enriquecimiento), concurrencia single-writer.
- **Migración a uv** como gestor del proyecto (lockfile, `.python-version`,
  dev-dependencies); `docs/decisiones/registro-ia.md` (decisiones tomadas por la
  IA); ADR 0012–0020; reescritura de PRD/ARCHITECTURE/API/ROADMAP/README.

### Changed
- **OpenAlex** es el backbone de datos (ADR 0007); BibTeX pasa a `Source`
  secundaria. **Persistencia por defecto: biblioteca viva DuckDB** como backend
  del `Corpus` (ADR 0009/0015); el snapshot es un export sellado, no el modelo.

### Deprecated
- **Snapshot inmutable / `InMemoryStore` / `ParquetStore` como persistencia por
  defecto** (premisa de ADR 0003 y de la versión previa de 0006): superados por
  la biblioteca viva en DuckDB. `ParquetStore` queda declarado, no implementado.
