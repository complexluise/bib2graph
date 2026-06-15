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
- ADR 0006: tabla canónica Arrow + NetworkSpec + snapshot inmutable (decisión
  arquitectónica formal; sin código todavía).
- Doc de exploración `docs/Notas/02-exploracion/arquitecturas-alternativas.md` con
  cuatro arquitecturas candidatas y la justificación de A+D.
- `CHANGELOG.md` (este archivo), `CONTRIBUTING.md` (Conventional Commits),
  `VERSIONING.md` (SemVer estricto).
- `AGENTS.md` para agentes que operen en el repo (build/lint/test, convenciones
  Python, punteros a docs).

### Changed
- `docs/ARCHITECTURE.md`: §3 (modelo = tabla Arrow), §6 (persistencia por
  snapshot, sin in-memory store), §9 (tensiones resueltas en ADR 0006).
- `docs/API.md`: §1 (`Corpus` wrapper + schema Arrow + Pydantic),
  §5–7 (proyectores, analizadores, exportadores adaptados),
  §9 (ejemplo con snapshot), §10 (NetworkSpec, hook desde v0.1).
- `docs/ROADMAP.md`: 10 hitos, con `Networks.quick` en Hito 2, CLI como API
  en Hito 4, NetworkSpec pública en Hito 8 (v0.2).

### Deprecated
- `InMemoryStore` como costura: la persistencia por defecto pasa a ser
  `ParquetStore` + `CorpusSnapshot`. El nombre "in-memory" confundía
  (sonaba a "no persistir"); el `Snapshot` cubre ambos usos a costo similar.

### Notes
- **No hay código todavía** (Hito 0 aún no arrancó). Toda la base hasta acá
  es docs. La primera línea de código se escribe cuando se cree
  `pyproject.toml` y la estructura `src/bib2graph/`.
