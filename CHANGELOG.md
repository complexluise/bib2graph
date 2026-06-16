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

## [0.4.0](https://github.com/complexluise/bib2graph/compare/v0.3.3...v0.4.0) (2026-06-16)


### Features

* **cli:** CLI agente-native b2g con 11 subcomandos (Hito 6) ([b4f5054](https://github.com/complexluise/bib2graph/commit/b4f505470a1968c7889ac480fb1d2273c8b01496))
* **cli:** comando b2g monitor + CycleState única + merge sin SQL interpolado ([32e89d8](https://github.com/complexluise/bib2graph/commit/32e89d85cca61864f1ed618277e1114616b6ac3c))
* **corpus:** implementar la tabla canónica Corpus, schemas y snapshot (Hito 1) ([091f9fd](https://github.com/complexluise/bib2graph/commit/091f9fda7e3682e96603866449dda0dfb91a3e23))
* esqueleto del paquete bib2graph (CLI + paquete) ([06197be](https://github.com/complexluise/bib2graph/commit/06197bec2473604abd9d4c9d0db897b872608194))
* **exploracion:** sandbox IED con datos reales de OpenAlex ([0c34983](https://github.com/complexluise/bib2graph/commit/0c349836474882b954927871faff2691b35bc908))
* **foraging:** forrajeo + Preprocessor + filtros PRISMA (Hito 5) ([89b385a](https://github.com/complexluise/bib2graph/commit/89b385a7d5612274558775c28214177f75438885))
* **networks:** proyectores, analizadores, exportadores y Networks.quick (Hito 2) ([b6e8b77](https://github.com/complexluise/bib2graph/commit/b6e8b776eb0e53b10fb16f94963a098869ded3f7))
* **remediation:** R3 — ciclo de dominio (cycle.py) fiel a la Nota 05 (ADR 0016) ([9fddb71](https://github.com/complexluise/bib2graph/commit/9fddb715cc3121f45bbe9e52cf893b07732e017e))
* **remediation:** R4 — scent bibliométrico vía proyectores; sin IA generativa (ADR 0020/0022) ([869f1bd](https://github.com/complexluise/bib2graph/commit/869f1bd12e4b4c978482e409348f0973d0a7b059))
* **remediation:** R5 — robustez/escala: bulk-load, UTF-8, retry, footguns (cierra RAÍZ 3) ([b7ff3ee](https://github.com/complexluise/bib2graph/commit/b7ff3eed0bb3e6dcb8fc9180727b0b34ab1686c4))
* **sources:** OpenAlexSource y BibtexSource — cierra v0.1 (Hito 4) ([29ae360](https://github.com/complexluise/bib2graph/commit/29ae360e36a88a8deb6031974a7ebf34337cff5a))
* **stores:** DuckDBBackend, DuckDBStore y LoopState con mutación SQL (Hito 3) ([97e9925](https://github.com/complexluise/bib2graph/commit/97e992555caaadd518133da2ff8771a33d391426))


### Bug Fixes

* **ci:** fijar release-please target-branch a main ([#16](https://github.com/complexluise/bib2graph/issues/16)) ([314774f](https://github.com/complexluise/bib2graph/commit/314774fd2bd534cece9a39cc24d4a46de0334f78))


### Documentation

* actualizar README al estado real (giro + 2o giro, v0.1 feature-complete) ([4538b6b](https://github.com/complexluise/bib2graph/commit/4538b6b099341400c8c68175dee4ece73fcbda7d))
* ADR 0021 (contrato CLI), sync Hito 6 y auditoría de artefactos ([6865adf](https://github.com/complexluise/bib2graph/commit/6865adffb407eef2ffadd10472d0dd1d23457ffb))
* **adr:** ADR 0013 (identidad, hash y merge) y sincronía de API.md (Hito 1) ([55e0bf4](https://github.com/complexluise/bib2graph/commit/55e0bf4c96401aaa52d312dc7d6e935284aa69eb))
* **adr:** ADR 0014 (proyección de redes, pesos, asortatividad) y sincronía (Hito 2) ([119e9cf](https://github.com/complexluise/bib2graph/commit/119e9cfd72dc7630c67dd63d83c337f8a134e096))
* **adr:** ADR 0020 (método de forrajeo: scent, filtros-reject) y sincronía (Hito 5) ([d1e24ae](https://github.com/complexluise/bib2graph/commit/d1e24aeb69fd7693c86e2ddcf09c472267f25591))
* **adr:** añadir ADR 0012 (credenciales OpenAlex) y registro de decisiones IA ([67ec021](https://github.com/complexluise/bib2graph/commit/67ec02190503b8e7bfbe6dea51fa07098906990a))
* **adr:** registro de decisiones 0001–0011 (OpenAlex, wedge, biblioteca viva, agente-native, thesaurus) ([f340e80](https://github.com/complexluise/bib2graph/commit/f340e80bcc7690e339c8fadbefbfe01c029d5038))
* **adr:** segundo giro — ADR 0015–0019 y reconciliación (TabularBackend, lazo, reproducibilidad) ([541cbd9](https://github.com/complexluise/bib2graph/commit/541cbd974d52c064a8832dc8e31c3fa13009087f))
* **api:** reconciliar API.md con el giro (OpenAlexSource, DuckDBStore stateful, forrajeo, thesaurus, asortatividad) ([dd8561c](https://github.com/complexluise/bib2graph/commit/dd8561c717b70f9a360bd1b340ea11584a90f6f7))
* **arch:** ADR 0024 (orden D3 vía _seq) + saneamiento de coherencia ([e6f0e51](https://github.com/complexluise/bib2graph/commit/e6f0e5124bf3da8f1e900ed75128e06198e839d0))
* **arch:** formalizar el modelo conceptual v2 (núcleo) — ARCH + ADRs + Nota 05 + metodología ([f9c52b3](https://github.com/complexluise/bib2graph/commit/f9c52b37166507e28f9a984dbc187c1609bef14f))
* **archivo:** archivar notas 06/07 ya promovidas al PRD/ADR ([b728691](https://github.com/complexluise/bib2graph/commit/b728691df9a1fef554bfafec15e965e9581dfca8))
* **arch:** steering R2 — sincronizar docs con identidad-vs-procedencia ([ed9e87a](https://github.com/complexluise/bib2graph/commit/ed9e87a15b6198ead27c30d127d9807d886d988e))
* **arch:** steering R3 — sincronizar docs con el ciclo de dominio ([c62e375](https://github.com/complexluise/bib2graph/commit/c62e3752c978995ca72902539d4f606b05e3e5a1))
* **arch:** steering R4 — scent bibliométrico, sin IA, forward = citación directa ([9002f65](https://github.com/complexluise/bib2graph/commit/9002f651128fe73da0400d5f6c57627a94dde4ea))
* **arch:** steering R5 + cierre de la tanda de remediación R1–R5 ([2f007dc](https://github.com/complexluise/bib2graph/commit/2f007dc29ab13253f3cc698fc64fae9fe7c5a8cf))
* arquitectura objetivo de la V1 reconciliada con el giro ([ab80808](https://github.com/complexluise/bib2graph/commit/ab808080912d959658921acf014a828a0e1d5fa5))
* barrido total de coherencia + tanda de remediación R1–R5 en el ROADMAP ([6487d8f](https://github.com/complexluise/bib2graph/commit/6487d8fed8b2ab9248f25cc872435e7c68fa3c8e))
* **contributing:** documentar el flujo GitFlow-lite (dev/main) + CI en dev ([665988c](https://github.com/complexluise/bib2graph/commit/665988cd6e84fd6523779c280d3245e5156ca43d))
* **contributing:** flujo GitFlow-lite (dev/main) + CI en dev ([1e17869](https://github.com/complexluise/bib2graph/commit/1e17869e81e9d2ddf932d4baacdd542fe5051155))
* ejemplo API §12 en dos bloques (v0.1 corre / v0.2 objetivo) y lista canónica de extras ([2e4bb4a](https://github.com/complexluise/bib2graph/commit/2e4bb4a402932546ce621ccd336db8b76d14ee62))
* meta del proyecto (README, contribución, versionado, release) ([a926800](https://github.com/complexluise/bib2graph/commit/a926800ae02d50ece9e2d8a4dbd13123024e45af))
* método bibliométrico y análisis de referentes/crítica base ([077046b](https://github.com/complexluise/bib2graph/commit/077046b300e7e4e182cd2bd632a95e918389ea78))
* **notas:** notas de proceso del rediseño (giro IA-in-the-loop, ciclo humano, lecciones v0) ([588626a](https://github.com/complexluise/bib2graph/commit/588626a6a63786a98a1b37f6a99355ab44b63017))
* poner el CHANGELOG Unreleased al día (v0.1 + Hito 5) ([a075c92](https://github.com/complexluise/bib2graph/commit/a075c92e69801c05bddbaaee2181f6334f26897f))
* PRD de la V1 (giro a OpenAlex + biblioteca viva + forrajeo asistido) ([87c386c](https://github.com/complexluise/bib2graph/commit/87c386c725622beeeb4458a6f523a6c22d7394de))
* reconciliar docs con el giro y atar el ROADMAP a las historias ([cbcbfbb](https://github.com/complexluise/bib2graph/commit/cbcbfbbab77d616ca1d3d0d0204fe362f4e94a44))
* reconciliar PRD/ARCHITECTURE/ROADMAP con el 2o giro y sincronía del Hito 3 ([d87be9a](https://github.com/complexluise/bib2graph/commit/d87be9ae95dd395635d0f4b6e99796df107b2926))
* red-team multiperspectiva del v0.2 as-built + correcciones de honestidad ([e09b56c](https://github.com/complexluise/bib2graph/commit/e09b56cd59908b1a8200988a29daa22e65b29d56))
* ROADMAP a carpeta + saneamiento de coherencia y enlaces ([82e69c3](https://github.com/complexluise/bib2graph/commit/82e69c3206e8dfc0cd3cb724d9a709e0864d17d9))
* ROADMAP a carpeta + saneamiento de coherencia y enlaces ([7aa0a4e](https://github.com/complexluise/bib2graph/commit/7aa0a4e15d253cb583f2ab213a3ed00f3e408721))
* roadmap de construcción de la V1 reordenado ([1b0d3f6](https://github.com/complexluise/bib2graph/commit/1b0d3f664a2070b010781a01a508e1e96d9b2349))
* **roadmap:** lockear decisiones del PO sobre la remediación ([382fca1](https://github.com/complexluise/bib2graph/commit/382fca125df51579e47868329303baa5d8bd5828))
* **roadmap:** R1 terminado (capa constants/modelos/schema) ([336c4f0](https://github.com/complexluise/bib2graph/commit/336c4f047305a48dbcb61304b130d3697d9afceb))
* sincronizar docs con el Hito 1.5 (TabularBackend) ([2b8a84b](https://github.com/complexluise/bib2graph/commit/2b8a84bb7879049d28de72a0bd7fbf171ab0df21))
* sincronizar docs con el Hito 4 y marcar v0.1 feature-complete ([2a2fe76](https://github.com/complexluise/bib2graph/commit/2a2fe766b99ad05f0270df2388cb92df52d68cdc))
* sincronizar estado as-built y encuadre de release ([fc59b04](https://github.com/complexluise/bib2graph/commit/fc59b04709930ed7341556bd6ff52154213fa381))
* sync a v0.3 — monitor, CycleState única, merge; batching→Hito 8; AGENTS/README/PRD ([c1ff328](https://github.com/complexluise/bib2graph/commit/c1ff3288d8227737aedebf0087ecad9b9d7468a9))

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
