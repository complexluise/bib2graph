# Changelog

Todos los cambios notables de `bib2graph` se documentan acá. El formato sigue
[Keep a Changelog](https://keepachangelog.com/es/1.1.0/), y este proyecto
adopta [Semantic Versioning](https://semver.org/lang/es/) (ver
[`VERSIONING.md`](./VERSIONING.md)).

El changelog se **auto-genera** desde Conventional Commits con
[`release-please`](https://github.com/googleapis/release-please) cuando haya
CI/GitHub. **Hasta entonces, la sección `[Unreleased]` se mantiene a mano** (la
fuente de verdad es la historia de commits); al conectar `release-please` toma el
control y la reconcilia.

## [Unreleased]

> **v0.1 feature-complete** (Hitos 0–4 + 1.5) + **Hitos 5 y 6** construidos: de
> una ecuación de búsqueda a las redes bibliométricas, **desde código Python o
> desde el CLI `b2g`**, sobre una biblioteca viva en DuckDB. v0.2 con capacidades
> completas (forrajeo + CLI agente-native). Resumen por capacidad (no commit a
> commit):

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
- **Forrajeo** (`Forager`: chaining backward/forward, ranking por *information
  scent* = frecuencia de enlace, `preview` sin red, filtros PRISMA que marcan
  `rejected`, `Preprocessor` + thesaurus multilingüe). ADR 0008/0011/0020.
- **CLI agente-native `b2g`** (`cli/`): 11 subcomandos (`seed`/`chain`/`filter`/
  `accept`/`reject`/`build`/`export`/`snapshot`/`status`/`inspect`/`validate`),
  envelope `--json` versionado, exit codes 0–5, `--store` global sin estado,
  transiciones `LoopState` automáticas. ADR 0021.
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
