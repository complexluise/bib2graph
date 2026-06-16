# Changelog

Todos los cambios notables de `bib2graph` se documentan acá. El formato sigue
[Keep a Changelog](https://keepachangelog.com/es/1.1.0/), y este proyecto
adopta [Semantic Versioning](https://semver.org/lang/es/) (ver
[`VERSIONING.md`](./VERSIONING.md)).

Este changelog lo **gestiona `release-please`** (ya conectado; ver
[`VERSIONING.md`](./VERSIONING.md) y ADR 0006): su PR de release actualiza esta sección
desde los Conventional Commits y bumpea `pyproject.toml`. Al mergear ese PR se crea el tag
`vX.Y.Z` y el GitHub Release. Las secciones por debajo de `[0.3.0]` son el historial previo a
la conexión del tooling (se mantuvieron a mano); de acá en adelante las gestiona el bot.

## [0.3.3](https://github.com/complexluise/bib2graph/compare/v0.3.2...v0.3.3) (2026-06-16)


### Bug Fixes

* **ci:** fijar release-please target-branch a main ([#16](https://github.com/complexluise/bib2graph/issues/16)) ([314774f](https://github.com/complexluise/bib2graph/commit/314774fd2bd534cece9a39cc24d4a46de0334f78))

## [0.3.2](https://github.com/complexluise/bib2graph/compare/v0.3.1...v0.3.2) (2026-06-16)


### Documentation

* **agents:** documentar el flujo GitFlow-lite en AGENTS.md + crear CLAUDE.md ([#8](https://github.com/complexluise/bib2graph/issues/8)) ([76254a7](https://github.com/complexluise/bib2graph/commit/76254a7bdd2678edb7f1e35e1e0a050622d3f811))
* **arch:** ADR 0024 (orden D3 vía _seq) + saneamiento de coherencia ([e6f0e51](https://github.com/complexluise/bib2graph/commit/e6f0e5124bf3da8f1e900ed75128e06198e839d0))
* **contributing:** documentar el flujo GitFlow-lite (dev/main) + CI en dev ([665988c](https://github.com/complexluise/bib2graph/commit/665988cd6e84fd6523779c280d3245e5156ca43d))
* **contributing:** flujo GitFlow-lite (dev/main) + CI en dev ([1e17869](https://github.com/complexluise/bib2graph/commit/1e17869e81e9d2ddf932d4baacdd542fe5051155))

## [0.3.1](https://github.com/complexluise/bib2graph/compare/v0.3.0...v0.3.1) (2026-06-16)


### Documentation

* ROADMAP a carpeta + saneamiento de coherencia y enlaces ([82e69c3](https://github.com/complexluise/bib2graph/commit/82e69c3206e8dfc0cd3cb724d9a709e0864d17d9))
* ROADMAP a carpeta + saneamiento de coherencia y enlaces ([7aa0a4e](https://github.com/complexluise/bib2graph/commit/7aa0a4e15d253cb583f2ab213a3ed00f3e408721))

## [Unreleased]

## [0.3.0] - 2026-06-16

> **Remediación R1–R5 + cleanup.** Cierra la brecha AS-BUILT↔TARGET del red-team (Nota 06):
> identidad≠procedencia (hash determinista), ciclo de dominio `cycle.py`, scent bibliométrico
> sin IA generativa, robustez/hardening, comando `monitor`. El `corpus_hash` cambia a propósito
> (breaking interno) — de ahí el corte v0.3.

> **Modelo nuevo bloqueado por el PO (2026-06-15)** tras el red-team del AS-BUILT v0.2
> ([Nota 06](docs/Notas/06-critica-as-built-v0.2.md)): el **producto no usa IA generativa** (ADR
> 0022); **capa base** `constants`/`models`/`schemas` única (ADR 0023); enmiendas a
> 0008/0011/0016/0017/0020/0021. La **tanda de remediación R1–R5** del [roadmap](docs/ROADMAP/README.md) lo
> implementa **antes** de los Hitos 7–11. Esta sección documenta el diseño nuevo; el código se
> entrega por hito R.

### Added (cleanup pre-v0.3 — **2026-06-16**)
- **Comando `b2g monitor`** (12° subcomando): re-chequea OpenAlex por **citantes nuevos** del corpus
  (forward chaining), mergea los candidatos nuevos a la biblioteca viva y **transiciona a `MONITORED`**
  (paso 8 del ciclo, Ellis). `data = {new_candidates, total_papers, loop_state, round}`, envelope
  `schema="1"`; `--email` para el polite pool; sin corpus/estado previo → `DataError` (exit 2). Con esto
  **`MONITORED` deja de ser inalcanzable** (cierra el seguimiento de R3/R5). ADR 0021 (enmienda) / 0016.

### Changed (cleanup pre-v0.3 — **2026-06-16**)
- **Alias `LoopState = CycleState` RETIRADO**: el código usa **solo `CycleState`** (de
  `bib2graph.cycle`); se eliminó de `backends/duckdb.py` y `stores/duckdb.py` (cierra la recomendación
  "a retirar pre-1.0" de R3). Una sola clase para el concepto del ciclo.

### Fixed (cleanup pre-v0.3 — **2026-06-16**)
- **`merge` de `DuckDBBackend` ya NO interpola ids crudos en el SQL** (footgun de la Nota 06,
  `backends/duckdb.py:417,423`): se reemplazó el `... id IN ('<id>',...) ORDER BY CASE id WHEN ...` por
  leer las filas y **ordenar en Python** por orden de aparición antes de reinsertar. Orden determinista
  D3 preservado; sin SQL construido con datos. (La alternativa CTE quedó descartada.) ADR 0013 (AS-BUILT).

### Changed (modelo / docs — diseño objetivo)
- **El producto NO usa IA generativa** (ADR 0022, **Hito R4 ✅ 2026-06-16**): el *information scent*
  del forrajeo deja de ser una heurística de frecuencia de enlace y pasa a **scent bibliométrico
  determinista** que consume el primitivo `collect_item_to_papers` de los proyectores, **sin LLM ni
  embeddings**. As-built: backward = **fuerza de co-citación con el corpus**; forward = **fuerza de
  citación directa al corpus** (señal primaria; el AS-BUILT inicial midió acoplamiento puro y degeneraba
  a 0 con referencias ralas → corregido a citación directa **dentro de R4**:
  `forward_score(Y) = |{ref ∈ Y.references_id : ref ∈ corpus_ids}|`); **centralidad diferida**.
  Un solo sentido de "AI-in-the-loop": el desarrollo es asistido por IA; el producto no.
- **Identidad ≠ procedencia** (ADR 0017 enmendado, **Hito R2 ✅ 2026-06-16**): el `corpus_hash` se
  computa **solo sobre contenido bibliográfico** (excluye `provenance`/timestamps; incluye
  `curation_status`); el reloj se inyecta desde la **frontera CLI** (`accept`/`reject`/`filter` pasan
  `decided_at`), con un **fallback `datetime.now(UTC)`** para uso como librería (no afecta la
  identidad); Louvain corre con `random_state` derivado del content-hash → **snapshot reproducible
  bit a bit**. (`resolution` de Louvain **diferido a Hito 9**, NetworkSpec.)
- **Ciclo = FSM cíclico de dominio** (`cycle.py`, ADR 0016 enmendado, **Hito R3 ✅ 2026-06-16**):
  `SEEDED→FORAGED→FILTERED→BUILT→MONITORED` con **`reseed`** (loop-back a `SEEDED` + contador de
  **ronda**, acumula) de primera clase. El enum de estados **sale del backend** a `bib2graph.cycle`
  (dominio puro; el backend solo persiste — columna `round` en `loop_state_log`; alias transicional
  `LoopState = CycleState`, a retirar pre-1.0); `seed` con estado previo se trata como `reseed`;
  `chain`/`filter`/`build` derivan su destino de `apply_transition` (fuente única). **Curación
  transversal** visible en `b2g status`: campos `curation_available`/`round` **aditivos** que mantienen
  `schema="1"` (ADR 0021 enmendado). `MONITORED` está en el modelo, sin comando que lo dispare aún.
- **Capa base de vocabulario + modelos** (ADR 0023): `constants.py` (`Col`/`CurationStatus`/
  `NetworkKind`) como fuente única de literales; `ProvenanceEvent(BaseModel)` con parseo que **falla
  ruidoso**; `PaperRow` ⇄ `CORPUS_SCHEMA` de una sola fuente (Hito R1).

### Removed (diseño objetivo)
- **`explain_candidate`, `foraging/explain.py` y el extra `[llm]`** **eliminados** (ADR 0022,
  **Hito R4 ✅ 2026-06-16**): el producto no usa IA generativa (verificable: el import falla, el extra
  no está en `pyproject.toml`).
- **La "máquina de tensiones"** (antigua "inserción de IA nº2") se **retira del producto** —no se
  difiere a v2, se borra (ADR 0008 enmendado). El **fallback semántico/LLM del thesaurus** también se
  retira (ADR 0011 enmendado): el thesaurus es curado y determinista.

### Fixed (**Hito R5 ✅ 2026-06-16**)
- **UTF-8 en la frontera CLI** (`cli/__init__.py:main` → `_force_utf8()`): el envelope `--json`
  (`ensure_ascii=False`) y `--help` dejan de corromper acentos en Windows cp1252 (Nota 06 RAÍZ 3).
- **Fin del O(n²) en carga**: los cuatro loaders (seed/load OpenAlex, BibTeX, Forager) usan el bulk
  `Corpus.from_arrow` (+ helper `_rows_with_ids`) en vez del loop `add_paper`/`_clone` que re-upserteaba
  la tabla entera por fila.
- **`fetch_citing` con retry/backoff** ante 429/5xx (exponential backoff, 3 intentos). *(El **batching
  por OR** queda diferido —mejora de performance, el N+1 persiste pero ahora es resiliente al
  rate-limit—; ver ROADMAP Hito R5.)*
- **Footguns de la Nota 06** colapsados/eliminados: rama muerta de `OSError` en `_errors.py`;
  `except Exception` de `detect_communities` (`facade.py`) que enmascaraba fallos; param muerto `g` de
  `cocitation_quality_report`; `Literal` duplicado de `NetworkSpec.kind` → `NetworkKind` (fuente única).

### Changed (cambios de comportamiento — **Hito R5 ✅ 2026-06-16**)
> Endurecen el contrato (la Nota 06 los pidió: "sin no-ops silenciosos"). No tocan `schema="1"` ni los
> exit codes externos; sí cambian qué pasa ante entradas inválidas.
- **Filtros PRISMA LANZAN ante campo/operador desconocido** (`ValueError` accionable). Antes era un
  no-op silencioso (`return True` → no filtraba, escondiendo el error).
- **`status`/`validate` ya NO auto-crean el store** ante un typo en `--store` (`open_store_readonly` →
  `StoreError` si el archivo no existe). Antes creaban un `.duckdb` vacío en silencio.
- **`.bib` con error de parseo grave LANZA** `ValueError`; un `.bib` vacío / con entradas sin título
  → `UserWarning`. Antes se tragaba en silencio.
- **`AttributeError` ya no se mapea a exit 3 en `@handle_errors`**: la capacidad-de-source-faltante se
  convierte en `DependencyError` (exit 3) con un pre-check `hasattr` en el comando `chain`; un
  `AttributeError` genuino se propaga limpio (no se disfraza de "capacidad no disponible").
- **`Manifest.lib_version` desconocida = `"unknown"`** (antes `"0.0.0"`): no se inventa una versión
  falsa que mienta sobre la reproducibilidad.

> **Tanda de remediación R1–R5 COMPLETA** (2026-06-16). Próximo: **Hito 7** (deduplicación fuzzy,
> extra `[dedup]`).

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
