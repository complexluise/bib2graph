# Changelog

Todos los cambios notables de `bib2graph` se documentan acá. El formato sigue
[Keep a Changelog](https://keepachangelog.com/es/1.1.0/), y este proyecto
adopta [Semantic Versioning](https://semver.org/lang/es/) (ver
[`VERSIONING.md`](./VERSIONING.md)).

El changelog se **auto-genera** desde Conventional Commits con
[`release-please`](https://github.com/googleapis/release-please). El PR de
release es revisable antes de mergear.

## [Unreleased]

### Added
- **El giro** (`docs/Notas/04`–`07`): IA in the loop, ciclo de investigación
  humano, definición de producto V1, decisiones abiertas.
- ADRs del giro: `0007` (OpenAlex backbone), `0008` (wedge = forrajeo),
  `0009` (biblioteca viva en DuckDB), `0010` (agente-native como columna),
  `0011` (thesaurus multilingüe), `0012` (credenciales de OpenAlex: email + API
  key opcional, inyectados).
- `docs/PRD.md` reescrito (V1): ecuación → biblioteca viva → redes; historias de
  usuario (épicas A–E).
- `docs/ROADMAP.md`: cada hito atado a las historias del PRD §7, con criterios de
  aceptación (DoD), nota de tests TDD selectivos y tabla de trazabilidad
  historias↔hitos.
- `CHANGELOG.md` (este archivo), `CONTRIBUTING.md` (Conventional Commits),
  `VERSIONING.md` (SemVer estricto).
- `AGENTS.md` para agentes que operen en el repo (build/lint/test, convenciones
  Python, punteros a docs).

### Changed
- **OpenAlex pasa a ser el backbone de datos** (ADR 0007): BibTeX queda como
  `Source` secundaria; el enricher Semantic Scholar deja de ser estructural.
- **Persistencia por defecto: `DuckDBStore` stateful** (biblioteca viva, ADR
  0009). El snapshot deja de ser el modelo de datos y pasa a ser un **export
  sellado** derivable del estado vivo.
- `docs/ARCHITECTURE.md` y `docs/API.md` reconciliados con el giro (OpenAlex,
  DuckDB, `Forager`, `explain_candidate`, `QualityThresholds`).
- `docs/ROADMAP.md`: 12 hitos (0–11), con `Networks.quick` en Hito 2, DuckDB en
  Hito 3, OpenAlex en Hito 4, forrajeo/thesaurus/filtros en Hito 5, CLI como API
  en Hito 6, NetworkSpec pública en Hito 9 (v0.2).
- `pyproject.toml`: `duckdb`, `httpx` y `python-louvain` al núcleo; extras
  `[zotero]`, `[s2]`, `[neo4j]`, `[dedup]`, `[viz]`, `[llm]`.

### Deprecated
- **Snapshot inmutable / `InMemoryStore` / `ParquetStore` como persistencia por
  defecto** (premisa de ADR 0003 y de la versión previa de 0006): superados por
  la biblioteca viva en DuckDB (ADR 0009). `ParquetStore` queda solo como formato
  de export/intercambio.

### Notes
- **Casi no hay código todavía** (Hito 0 en andamiaje): `pyproject.toml`,
  `src/bib2graph/__init__.py` y un placeholder de CLI. El núcleo arranca con el
  Hito 1 (`Corpus`).
