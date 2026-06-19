# AGENTS.md — bib2graph

> Guía para agentes que operen en este repositorio. El proyecto es una **reescritura
> clean-room** construida de adentro hacia afuera (docs → núcleo puro y tests → costuras).
> **Estado (v0.3): Hitos 0–6 + 1.5 construidos, remediación R1–R5 COMPLETA, Hito 8 COMPLETO**
> (Enricher OpenAlex: refs→DOI + co-citación end-to-end) **y Hito 7 COMPLETO** (dedup fuzzy
> determinista `rapidfuzz`, **automático en la ingesta desde #88; `rapidfuzz` en el núcleo, sin extra
> `[dedup]`** — ADR 0031), tras el red-team de la Nota 06 y el modelo
> nuevo (ADR 0022/0023; el producto **no usa IA generativa** — el desarrollo SÍ es asistido por IA,
> pero el scent es bibliométrico determinista) **y el Hito 9 COMPLETO** (capa declarativa
> `NetworkSpec` YAML: `load_specs` + `resolution` + 16° subcomando `b2g networks`). Ver
> `docs/ROADMAP/` y "Estado actual" abajo. El diseño objetivo vive en
> `docs/ARCHITECTURE.md`; los contratos
> públicos en `docs/API.md`; el producto en `docs/PRD.md`; las reglas que motivan este código en
> `docs/Notas/01-lecciones-v0.md`. Las decisiones vigentes tras **el giro** son los ADR
> [0007](docs/decisiones/0007-openalex-backbone.md) (OpenAlex backbone),
> [0008](docs/decisiones/0008-wedge-forrajeo.md) (wedge = forrajeo),
> [0009](docs/decisiones/0009-biblioteca-viva-duckdb.md) (biblioteca viva en DuckDB),
> [0010](docs/decisiones/0010-agente-native-columna.md) (agente-native columna) y
> [0011](docs/decisiones/0011-thesaurus-multilingue.md) (thesaurus), sobre la base del
> [0006](docs/decisiones/0006-tabla-canonica-y-networkspec.md) (tabla canónica Arrow).

## Estado actual

- **Hitos 0–6 + 1.5 CONSTRUIDOS y remediación R1–R5 COMPLETA** (v0.3, 2026-06-16): de una
  ecuación de búsqueda a las redes bibliométricas, desde código Python **o** desde el CLI `b2g`,
  sobre una biblioteca viva en DuckDB. El árbol `src/bib2graph/` tiene ~30 módulos: `constants.py`
  y `schemas.py` (capa base, R1; `ProvenanceEvent` vive en `schemas.py`, no hay `models.py`),
  `corpus.py`, `cycle.py` (FSM cíclico de dominio, R3),
  `backends/` (`TabularBackend` + `InMemoryBackend` + `DuckDBBackend`), `stores/`
  (`DuckDBStore`), `sources/` (`OpenAlexSource`, `BibtexSource`), `foraging/` (`Forager`,
  scent bibliométrico), `preprocessors/` (normalize + dedup automáticos en la ingesta + thesaurus
  explícito), `filters/` (PRISMA),
  `networks/` (proyectores, analyzer, spec, facade), `sources/equation.py` (capa declarativa de la
  ecuación, 9a), `exporters/` (GraphML, CSV) y `cli/`.
  El **CLI `b2g` es real** —paquete `cli/` con 19 subcomandos en `cli/commands/`, no un
  placeholder (el 16° `b2g networks` es la capa declarativa YAML del Hito 9; el 17° `b2g restore`
  rehidrata un corpus curado sin red, Ciclo 9a; el 18° `b2g thesaurus` aplica el thesaurus curado,
  único paso explícito del preproc, #88, abajo; el 19° `b2g gui` levanta la API local FastAPI, Hito G3
  del MVP GUI, ADR 0028)—.
  **645 tests verdes** (mypy/ruff limpios; el núcleo importa sin `duckdb`). Entre las
  redes, la **composición de comunidades es exportable**: `networks/cluster_table` (función pura)
  resume cada comunidad de una red de paper en una fila y `b2g build` la escribe como `clusters.csv`
  (#31, AS-BUILT 2026-06-17; ver `docs/API.md` §7.2). **`b2g snapshot`/`b2g export` resuelven por
  workspace** (`--out-dir` override opcional → `<workspace>/snapshots|exports/`) y **`b2g status` avisa
  de staleness** de la cache de redes (`networks_cache_stale`; avisa, no regenera) — remanentes del
  modelo workspace cerrados (#32, AS-BUILT 2026-06-17; ver el bullet de workspace abajo).
- **Hito 9 COMPLETO — capa declarativa `NetworkSpec` YAML** (AS-BUILT 2026-06-17): `NetworkSpec`
  (`networks/spec.py`) suma el campo **`resolution: float = 1.0`** (resolución de Louvain, **fuera del
  `corpus_hash`** → seed intacto) y **`extra="forbid"`**. Nueva función **`load_specs(path)`**
  (re-exportada desde `networks/`; esquema raíz `networks:`, errores accionables citando archivo +
  `red #<idx>` + campo). **16° subcomando `b2g networks --spec <yaml>`** (`cli/commands/networks.py`):
  carga el YAML → `Networks.build` por red → escribe artefactos con el helper compartido
  `_write_artifacts` (mismos GraphML + metrics.json + clusters.csv que `build`); **NO** transiciona el
  `CycleState` ni sella `.corpus_hash` (transversal al lazo, como `enrich`/`curate`). `pyyaml` pasó a
  dependencia del núcleo (import perezoso). **516 tests verdes**. Ver `docs/API.md` §10.
- **MVP GUI — Hitos G1–G5 COMPLETOS · build entero del MVP (AS-BUILT 2026-06-18, ADR
  [0028](docs/decisiones/0028-arquitectura-gui-api-capa-servicios.md)):** los 5 hitos de construcción
  están **AS-BUILT** en `feat/gui-g1-capa-servicios` — G1 (capa de servicios neutral + contrato subido),
  G2 (6 lecturas read-only en `service/reads.py`), G3 (API local FastAPI + extra `[gui]` + 19º
  subcomando `b2g gui`), G4 (SPA `frontend/`), G5 (empaquetado). Lo único pendiente es el **gate #34**
  (un tercero usa la GUI sin ayuda para reproducir/curar `examples/valoraciones/`), que **NO es
  construcción**: es el criterio de aceptación/descarte de producto de la epic, al final (ADR 0027
  §Gate). Detalle por hito en `docs/ROADMAP/05-gui.md`.
  - **G4 — SPA `frontend/`** (paquete JS del monorepo, **`pnpm` —nunca npm**): React 18 + Vite + TS
    estricto + Cytoscape/fcose + Zustand + Tailwind + TanStack Query, dirección visual **D-2
    "Observatorio"** (oscuro, grafo-céntrico, design tokens propios en `tailwind.config.js`). Consume los
    **7 endpoints reales** de la API G3 (`src/{client,types,store,components,lib,styles}`): 3 columnas
    (rondas/grafo/candidato) + curar (refetch, sin Louvain client-side) + diff de rondas; cliente tipado
    que des-envuelve `schema="1"` (`error.code` **string**, header `Bearer`) y tipos que espejan los DTO
    reales. **Wiring del token (B-G4-3):** `b2g gui` **inyecta el token en el `index.html` servido**
    (`cli/commands/gui.py::_make_index_response` reemplaza el placeholder `__B2G_TOKEN__`; ruta `GET /`
    sirve el HTML con token sin exigir Bearer, `StaticFiles` —`html=False`— sirve los assets); el frontend
    lo lee de `window.__B2G_TOKEN__`. El **build** sale a `src/bib2graph/gui/static/` (`outDir`,
    `base: "./"`) y **NO se commitea** (gitignoreado). **Tests vitest (14).**
  - **G5 — empaquetado:** el wheel **vendorea el build del frontend** vía
    `[tool.hatch.build.targets.wheel.force-include]` de hatchling (`src/bib2graph/gui/static` →
    `bib2graph/gui/static`) → `b2g gui` funciona **sin Node** desde el wheel; clone fresco sin `pnpm
    build` previo → `uv build` **falla ruidosamente** (no wheel mudo). `ci.yml` suma el job **`frontend`**
    (setup-node 20 + pnpm `install`/`lint`/`test:run`/`build`, corre siempre); `publish-testpypi.yml`
    hace `pnpm build` **antes** del `uv build` (Trusted Publishing intacto, `release-please.yml` no se
    tocó). `tests/unit/test_packaging_config.py` (**2 tests**) guarda la config `force-include`. Ver
    §`frontend/` abajo, `docs/API.md` §0.2 y `docs/ROADMAP/05-gui.md` §G5.
- **#88 — preprocesamiento automático en la ingesta (AS-BUILT 2026-06-18, ADR
  [0031](docs/decisiones/0031-preprocesamiento-automatico-en-ingesta.md)):** `normalize` + dedup
  fuzzy corren **automáticamente** en `seed`/`seed_from_bib`/`chain`/`restore` (helper
  `cli/_ingest.py::normalize_and_dedup` sobre el corpus **completo mergeado** ⇒ dedup
  **cross-biblioteca**); el corpus queda siempre normalizado y deduplicado. **`rapidfuzz` pasa al
  núcleo** (`[project.dependencies]`; **el extra `[dedup]` se elimina**, import ya no perezoso).
  Nuevo **18° subcomando `b2g thesaurus --from <archivo>`** (único paso explícito del preproc,
  transversal al FSM). La ingesta y `thesaurus` persisten con **`persist_replace`** /
  `overwrite_corpus` (DELETE+INSERT, preservan tablas hermanas; evita que el upsert-concat D3
  reintroduzca variantes). `build`/`networks` siguen puros. Deuda conocida: dedup O(n²) por ingesta
  (optimización futura) y skip #93 (`test_run_seed_from_bib_reseed_incrementa_ronda`, crash
  `BibDataString`/`pyparsing` en reseed mismo-proceso; no afecta el CLI real). La **revisión asistida
  de clusters ambiguos** se difiere a la epic GUI #34. Ver `docs/API.md` §6/§11/§4.1.
- **Ciclo B — `examples/valoraciones/` rehecho 100% por CLI (AS-BUILT 2026-06-17, ADR
  [0030](docs/decisiones/0030-ecuacion-declarativa-corpus-ejemplo.md) §Ciclo B):** materializa el
  principio **CLI-puro** del PO. `build_corpus.py` **eliminado**; el ejemplo se arma y reproduce
  **por CLI** (`seed --spec equation.yaml` `max_results 80` → `curate --from-csv curacion.csv` 10
  `accepted` → `enrich --max-citing 25` → `snapshot`). Corpus = **~80 filas, 10 `accepted`
  enriquecidas, co-citación presente** (rala) — antes 137 filas / co-citación vacía (9b). Nuevo
  artefacto congelado **`curacion.csv`** (receta determinista de curación). Gate R2 ajustado (piso
  `n>=50`, `test_cocitacion_con_datos` con 5 redes). **La procedencia de un ejemplo deja de ser un
  script y pasa a ser la receta CLI del README + `equation.yaml` + `curacion.csv`** (supersede la
  convención de 9b). **598 tests por defecto** (los 2 `network` quedan fuera del gate). Ver
  `docs/API.md` §2.1.
- **Ciclo 10 — `seed --from-bib` + filtro de año real (AS-BUILT 2026-06-17, ADR
  [0030](docs/decisiones/0030-ecuacion-declarativa-corpus-ejemplo.md) §Ciclo 10, cierra #50):**
  `b2g seed` pasa a **3 modos** mutuamente excluyentes (`--equation` / `--spec` / **`--from-bib
  <archivo.bib>`**, este último sin red vía `BibtexSource.load`; `SEEDED`/reseed; exit 3 si falta
  `bibtexparser`; combinar `--from-bib` con flags OpenAlex → exit 1). `min_year`/`max_year`
  **ahora filtran de verdad** contra OpenAlex (`from_publication_date`/`to_publication_date`;
  flags `--min-year`/`--max-year` en `--equation` + campos del YAML en `--spec`). Nuevo ejemplo
  **`examples/bibtex/`** (`sample.bib` + README CLI-puro). **594 tests verdes.** Ver `docs/API.md` §2.
- **Ciclo 9a — ecuación declarativa + `restore`** (AS-BUILT 2026-06-17, ADR
  [0030](docs/decisiones/0030-ecuacion-declarativa-corpus-ejemplo.md)): **(1)** `b2g seed` tenía
  entonces **2 modos** (`--equation` / **`--spec equation.yaml`**) — `EquationSpec` + `load_equation_spec`
  (`sources/equation.py`, Pydantic `extra="forbid"`; `min_year`/`max_year` aún no filtraban en 9a;
  **filtran desde el Ciclo 10**, arriba). **(2)** Nuevo **17° subcomando `b2g restore --from-corpus
  <parquet>`** (`cli/commands/restore.py`): rehidrata un corpus **ya curado sin red** (inverso de
  `snapshot`; `CORPUS_SCHEMA` → `Corpus.from_arrow` → merge+persist), preserva la curación y
  transiciona a **`FILTERED`** (reusa la transición permisiva `filter`, ADR 0016). **No** hay
  `seed --from-corpus` (es `restore`); `seed --from-bib` estaba diferido en 9a y **se construyó en el
  Ciclo 10** (arriba). Ver `docs/API.md` §2 + §convenciones CLI.
- **Ciclo 9b — corpus de ejemplo + gate R2 · #33 CERRADO** (AS-BUILT 2026-06-17, ADR
  [0030](docs/decisiones/0030-ecuacion-declarativa-corpus-ejemplo.md)): se construye la convención
  **`examples/`** (corpus curado congelado por carpeta: `corpus.parquet` + `equation.yaml` de
  procedencia + `README.md` + script determinista de regeneración; ver `docs/API.md` §2.1) y su primer
  ejemplo, **`examples/valoraciones/`** (137 filas: 7 `accepted`, 130 `candidate`, 107 seeds; corpus
  real del PO reducido determinísticamente, CC0/OpenAlex). Excepción acotada al `.gitignore` (`!examples/`
  + regla defensiva `examples/**/*.duckdb`). El **gate R2** (`tests/unit/test_example_r2_gate.py`,
  7 tests) corre `restore --from-corpus` → `build` → `networks` **sin red** sobre el corpus real y
  asserta `corpus_hash` estable + composición de comunidades Louvain estable entre corridas (cierra el
  agujero R2 de la [Nota 09](docs/Notas/09-sesion-qa-prueba-ecologia-valoraciones.md)). Con esto **#33
  queda cerrado** (caso real reproducible = gate de la epic GUI #34); `seed --from-bib` y
  `examples/bibtex/` siguen diferidos (issue #50). Ver `docs/API.md` §2.1.
- **Hito 8 COMPLETO** (Ciclos 8a + 8b, ADR
  [0025](docs/decisiones/0025-enricher-cocitacion-openalex.md)): el `OpenAlexEnricher` (opt-in,
  núcleo) hace 2 pasadas — **refs→DOI** (8a) **+ co-citación end-to-end** (8b): pobla `cited_by_id`
  trayendo los citantes de las semillas aceptadas vía `OpenAlexSource.fetch_citing_batch` (batcheo OR
  ≤50 con presupuesto por semilla) y los une (idempotente, sin crecer el corpus). `b2g enrich` con
  `--max-citing` (tope por semilla); `Networks.quick` → 4 o 5 redes según haya `cited_by_id`.
- **Forward chaining materializa metadata REAL** (#78, 2026-06-17, AS-BUILT CERRADO): el forward del
  `Forager` (`b2g chain`) **ya no persiste placeholders `[candidate:W...]`** — materializa filas reales
  (título/año/autores). Causa raíz: `fetch_citing_batch` traía la metadata completa (`_FIELDS`) y la
  descartaba; el fix A1 (cero red extra) la conserva vía el método nuevo
  **`OpenAlexSource.fetch_citing_batch_with_works(ids, *, max_per_paper) -> (attribution, works_map)`**
  (`fetch_citing_batch` queda intacto, thin wrapper). `_build_forward_candidate_row` eliminado; `_work_to_row`
  ganó `chaining_hop`/`source_tag` (defaults backward-compat). **Asimetría deliberada** con el backward
  (#54): el backward observa sin materializar, el forward materializa (citantes pocos, acotados, se curan,
  metadata ya en la request). Con #78, el materializador on-demand #71 queda **solo para backward**.
  **645 tests verdes**, verifier PASA. Ver `docs/API.md` §2 (`fetch_citing_batch_with_works`)/§5 y ADR
  [0020](docs/decisiones/0020-metodo-forrajeo-scent-filtros-reject.md) §AS-BUILT #78.
- **Backward chaining sin placeholders** (#54, 2026-06-17): el backward del `Forager`
  (`b2g chain`) **ya no persiste filas-fantasma `[candidate:W...]` en el corpus** (revierte el
  comportamiento de Hito 5 — la promesa de "no contaminan" era **falsa**: los stubs llegaron a ser
  ~la mitad del corpus y entraban al `corpus_hash`; Notas 09/12). Los IDs observados salen por
  `RankedCandidates.observed_refs` y `b2g chain` los persiste en la tabla append-only hermana
  **`referenced_but_not_fetched`** (`backends/base.py` Protocol + `DuckDBBackend`/`InMemoryBackend`:
  `add_referenced_refs`/`referenced_refs_count`/`referenced_refs`), **fuera del `corpus_hash`** (arregla
  la contaminación previa). `b2g status` suma `referenced_not_fetched`; `b2g chain` suma
  `observed_refs_count`. **El forward arrastraba el MISMO footgun**, **cerrado en #78** (arriba). Ver
  `docs/API.md` §5/§4 y ADR [0020](docs/decisiones/0020-metodo-forrajeo-scent-filtros-reject.md)
  §AS-BUILT #54.
- **Forward chaining del `Forager` batcheado** (#21, 2026-06-16): el forward del `Forager`
  (`b2g chain`/`b2g monitor`) **ya no es N+1** — reusa `OpenAlexSource.fetch_citing_batch` (batcheo OR
  + cap por semilla `max_citing_per_paper`/`--max-citing`, default 50) con preview sin red. **Opera
  sobre `is_seed=True`** (todas las semillas, **sin** filtrar `curation_status`): el chaining precede a
  la curación; la restricción a `accepted` es del **Enricher** (Hito 8b), no del Forager. Ver
  `docs/API.md` §5 y ADR [0020](docs/decisiones/0020-metodo-forrajeo-scent-filtros-reject.md) AS-BUILT #21.
- **Labels legibles en las redes** (#25, 2026-06-16): las redes ahora salen con `label` legible
  (más `year`/`is_seed`/`curation_status`/`degree_centrality`/`community`) vía la nueva **capa
  frontera `decorate`** (`networks/decorate.py`), aplicada en `facade.py:_build_artifact`; `b2g
  build`/`export` exportan grafos legibles en Gephi/VOSviewer. Los proyectores **siguen puros** (ADR
  0014). Cierra el hueco de la Nota 09 B3 (redes con id crudo). Ver `docs/API.md` §7.1.
- **Tanda de remediación R1–R5 COMPLETA** (v0.3, 2026-06-16). Tras el red-team del AS-BUILT
  ([`docs/Notas/06-critica-as-built-v0.2.md`](docs/Notas/06-critica-as-built-v0.2.md)) el PO bloqueó
  un **modelo nuevo** (ADR [0022](docs/decisiones/0022-producto-sin-ia-generativa.md)/
  [0023](docs/decisiones/0023-capa-constants-modelos-schema.md) + enmiendas), ya construido:
  **R1** — **capa base** `constants.py`/`schemas.py` única (con `ProvenanceEvent` en `schemas.py`,
  no en un `models.py`); **R2** — **identidad ≠
  procedencia** (el `corpus_hash` excluye timestamps, reloj en la frontera, Louvain seeded);
  **R3** — **FSM cíclico de dominio** `cycle.py` (sale del backend) con `reseed`/ronda + curación
  transversal en `status`; **R4** — **scent bibliométrico vía proyectores**, **el producto NO usa
  IA generativa** (se eliminaron `foraging/explain.py`, `explain_candidate`, el extra `[llm]` y la
  "máquina de tensiones"); **R5** — robustez (bulk-load, UTF-8 en la frontera, retry, footguns).
  Ver `docs/ROADMAP/` (Hitos R1–R5). Tras la remediación se construyeron el **Hito 8** (Enricher
  OpenAlex: refs→DOI + co-citación end-to-end) y el **Hito 7 ✅** (dedup fuzzy determinista
  `rapidfuzz`: `deduplicate_authors`/`deduplicate_keywords`; ADR
  [0026](docs/decisiones/0026-dedup-fuzzy-determinista.md) — **automático en la ingesta y `rapidfuzz`
  al núcleo desde #88, ADR [0031](docs/decisiones/0031-preprocesamiento-automatico-en-ingesta.md)**),
  el **Hito 9 ✅** (`NetworkSpec`
  YAML) y el **Ciclo #33 ✅** (ecuación declarativa + `restore` + corpus de ejemplo, 9a+9b). Con #33
  cerrado, **todo el terreno pre-GUI está completo**; lo que sigue es la epic GUI #34. El entorno se
  levanta con `uv sync`.
- **Fundación workspace COMPLETA** (ADR
  [0029](docs/decisiones/0029-workspace-por-investigacion.md), AS-BUILT 2026-06-16; issues
  [#32](https://github.com/complexluise/bib2graph/issues/32)/
  [#38](https://github.com/complexluise/bib2graph/issues/38)/
  [#39](https://github.com/complexluise/bib2graph/issues/39)): una investigación = un **workspace =
  carpeta** (`workspace.json` + `library.duckdb` + `networks/`/`snapshots/`/`exports/`). Nuevo módulo
  `src/bib2graph/workspace.py` (`Workspace`, `WorkspaceManifest`; el núcleo NO importa `duckdb`) +
  **14° subcomando `b2g init`**. Se agregó **`--workspace`** (opcional) con **resolución ambiente**
  (flag > env `B2G_WORKSPACE` > walk-up del cwd buscando `workspace.json`).
  `b2g status` suma `workspace: {root, source}`; `b2g build` sella `networks/.corpus_hash`. **422
  tests verdes**, 14 subcomandos. Flujo: `b2g init <name>` → trabajar **dentro** de la carpeta.
  **Remanentes cerrados (#32, AS-BUILT 2026-06-17):** `b2g snapshot`/`b2g export` ya
  resuelven por workspace (`--out-dir` pasó a override opcional → `<workspace>/snapshots|exports/`)
  y `b2g status` suma `networks_cache_stale: bool` + `warnings`
  accionable cuando el `networks/.corpus_hash` no coincide con el corpus vivo (**avisa, NO regenera**:
  invalidación por hash, no build-system). `Workspace` ganó `read_networks_corpus_hash()` /
  `is_networks_cache_stale()`. Con esto el modelo workspace queda **completo** (no quedan remanentes).
  **BREAKING (#75, 2026-06-17):** la opción `--store` se **eliminó por completo** del CLI (pasarla da
  el error estándar de Click `No such option`) y el **modo degenerado dejó de existir** — la carpeta
  con `workspace.json` es la **única** unidad canónica; un `.duckdb` legacy se adopta con `b2g init .`.
- **Curación a escala vía CSV** (#22 + #26, 2026-06-16): nuevo **15° subcomando `b2g curate`**
  (`cli/commands/curate.py`) con dos modos mutuamente excluyentes — **`--dump`** escribe
  `curacion.csv` (default `<workspace>/exports/`; `--out` override; `--all` para todo el corpus, default
  solo candidatos) para revisión offline en Excel/Calc, y **`--from-csv`** aplica las decisiones en
  lote (`accepted`→accept / `rejected`→reject / `undecided`→no-op), **idempotente** (reimportar = mismo
  `corpus_hash`; `decided_at` inyectado en la frontera, R2) y con **validación accionable** + reporte de
  **IDs huérfanos** (`not_found_count`, cierra el no-op silencioso). `note` advisory (round-trip,
  ignorado al importar); `scent_score` best-effort, `cluster` diferido. **Curación transversal** (NO
  transiciona el `CycleState`). Cierra el hueco de la
  [Nota 09](docs/Notas/09-sesion-qa-prueba-ecologia-valoraciones.md) B4/B5/P1 (sin dump CSV ni reimport
  en lote, la curación a escala no era viable). **476 tests verdes**, 15 subcomandos. Ver
  `docs/API.md` §convenciones CLI.
- **Ergonomía de `b2g seed` (#14 + #30, 2026-06-16):** **`--max-results INT`** propaga a
  `OpenAlexSource(max_results=...)` (sin flag = default 200) para explorar con muestras chicas;
  **`--exclude TEXT`** (repetible) son negaciones quirúrgicas que inyectan cada `AND NOT "<término>"`
  **dentro** de la única expresión `title_and_abstract.search:((query) AND NOT "<término>")` (el campo
  **no se repite**; la forma vieja con campo repetido devolvía 0 en OpenAlex, corregido AS-BUILT
  2026-06-17, fix de #30 validado contra la API real vía test `@pytest.mark.network`) y se **reportan
  en el `translation_report`** del `SeedResult` (query visible, ignorado con `--native`). Cierra el síntoma
  B1 de la [Nota 09](docs/Notas/09-sesion-qa-prueba-ecologia-valoraciones.md). **476 tests verdes**.
  Ver `docs/API.md` §2 + §convenciones CLI.
- Toda la información del producto, la arquitectura, los contratos y la secuencia de
  construcción está en `docs/`. **Leer `docs/ROADMAP/` antes de tocar nada**: cada hito declara
  qué historias del PRD §7 cumple, sus criterios de aceptación (DoD) y los tests TDD que se
  escriben. El orden es deliberado (núcleo puro → costura local DuckDB → costura red OpenAlex →
  forrajeo → CLI → opcionales).
- **No hay Cursor rules** (`.cursor/`, `.cursorrules`) ni Copilot rules
  (`.github/copilot-instructions.md`).
- **El modelo de dominio es una tabla Arrow** (no 4 dicts + dataclasses). Las "entidades"
  son vistas derivadas. Validación con Pydantic v2. Detalle en `docs/API.md` §1.
- **La persistencia por defecto es `DuckDBStore` stateful** — la **biblioteca viva** (ADR 0009):
  acumula entre corridas, con tablas de procedencia/curación. Es **núcleo**, no extra. El
  **snapshot** (`CorpusSnapshot`: parquet + `manifest.json`) es un **export sellado** derivable
  del estado vivo, no la persistencia en sí; `ParquetStore` es solo formato de export.
- **OpenAlex es el backbone de datos** (ADR 0007): trae refs + citantes + afiliaciones per-autor.
  BibTeX es `Source` secundaria. El enricher S2 ya **no es estructural**.
- **El CLI es la API para LLM/agentes** (Hito 6). Subprocess + JSON stdout, exit codes
  claros, sin estado entre invocaciones (el estado vive en DuckDB).

## Flujo de trabajo (ramas dev/main) — LEER ANTES DE TOCAR GIT

Modelo **GitFlow-lite** con dos ramas protegidas (PR + CI verde obligatorios; nunca
pushear directo). Detalle en [`CONTRIBUTING.md`](CONTRIBUTING.md) §Modelo de ramas.

- **`dev`** — rama de **integración** y **default del repo**. Acá se **acumula** el trabajo.
  Protección no-estricta.
- **`main`** — rama **estable / de release**. Solo recibe `dev` al liberar y el PR de release.
  Protección **estricta** (la rama del PR debe estar actualizada con `main` antes de mergear).

Flujo de un cambio (agente o humano):

```
git checkout dev && git pull
git checkout -b feat/lo-que-sea        # ramear SIEMPRE desde dev
# ...commits Conventional Commits...
git push -u origin feat/lo-que-sea
gh pr create --base dev                # PR a dev (NO a main)
# CI verde (lint + test 3.11/3.12) → es el gate
gh pr merge --squash --delete-branch   # 1 commit conventional limpio por idea
```

**Dos tipos de PR, no confundir:**
1. **PR de trabajo** (`feat/...` → `dev`): lo abrís vos/el agente a mano. Squash al mergear.
2. **PR de release** (`chore(main): release X.Y.Z`): lo crea **`release-please` solo**; no se
   crea a mano. Ver §Comandos de release.

**Liberar** (cuando hay varias cosas en `dev`, no por cada cambio): PR `dev → main` con
**merge commit** (NO squash, para que release-please vea los `feat`/`fix`) → release-please
abre su PR de release → mergearlo crea el tag + GitHub Release.

**Reglas para agentes:** ramear desde `dev`; nunca commitear directo a `dev`/`main`; un PR =
una idea; el commit/PR sigue Conventional Commits (abajo); no bumpear versión ni editar
`CHANGELOG.md` a mano (lo hace release-please).

## Tooling de agentes Claude Code (`.claude/`)

El repo versiona su propia config de Claude Code para que **el equipo herede los roles y los
guardarraíles** al clonar (project-level **gana** sobre la config de usuario). Se versiona
`.claude/settings.json` + `.claude/agents/` + `.claude/hooks/`; queda ignorado el estado local
(`settings.local.json`, `worktrees/`, `System_prompt.md`).

**Subagentes** (`.claude/agents/*.md`), afinados a bib2graph y con **una frontera dura por rol**
("cada uno es responsable de sus artefactos"):

| Agente | Dueño de | Frontera (mecánica) |
|---|---|---|
| `architect` | `docs/` (+ docs raíz) | hook le niega escribir `src/`/`tests/` |
| `coder` | `src/` + `tests/` | hook le niega escribir `docs/`/README/AGENTS/CONTRIBUTING |
| `verifier` | nada (read-only) | sin `Write`/`Edit` en `tools` |

Los orquesta `feature-cycle` (PO → architect → coder → verifier → architect).

**Hooks `PreToolUse`** — hacen cumplir las reglas de forma **mecánica** (corren **incluso en modo
bypass**, son más fuertes que los permisos). Se invocan con `uv run --no-sync --quiet python`
(no `python` pelado: garantiza el intérprete vía uv y silencia el warning de deprecación):

- **`hooks/guard.py`** (global, en `settings.json`): bloquea `npm` (usar pnpm), `pip install`
  (usar uv), `git push` a `main`/`dev`, `git commit` estando parado en `main`/`dev`, y editar
  `CHANGELOG.md` a mano. Son las reglas duras de §Flujo de trabajo, vueltas imposibles de violar.
- **`hooks/fence.py`** (por agente, en el frontmatter de `coder`/`architect`): aplica la frontera
  de la tabla de arriba según los directorios/archivos que recibe como argumento.

**Caveat operativo:** los **agentes cargan al iniciar la sesión** (un agente nuevo o un cambio a
su frontmatter no toma efecto hasta reiniciar). Los **hooks de `settings.json` sí recargan en
caliente**. Si un guardarraíl bloquea algo legítimo, se afloja editando el script en
`.claude/hooks/`.

## Comandos de build / lint / test

El proyecto se gestiona con **uv** (entorno + lockfile + versión de Python). **No** uses
`pip install` ni edites `[project.dependencies]` a mano: uv mantiene `pyproject.toml` y
`uv.lock` sincronizados. Comandos canónicos (siempre `uv run`, sin activar el venv):

- **Setup dev completo:** `uv sync` (crea `.venv`, instala núcleo + dev-deps desde `uv.lock`)
  y `uv run pre-commit install`.
- **Con una capacidad opcional:** `uv sync --extra bibtex` (siembra BibTeX) o `uv sync --extra gui`
  (`fastapi` + `uvicorn` para `b2g gui` / la API local, AS-BUILT G3, ADR 0028) — los dos extras poblados
  hoy. Sin dev-deps: `uv sync --no-dev`. *(No hay extra `[llm]`: **se eliminó** en la remediación
  R4 — el producto no usa IA generativa, ADR 0022. Tampoco hay extra `[dedup]`: `rapidfuzz` pasó al
  núcleo en #88 porque el dedup es automático en la ingesta, ADR 0031.)*
- **Agregar dependencias:** `uv add <pkg>` (núcleo) · `uv add --dev <pkg>` (desarrollo) ·
  `uv add --optional <extra> <pkg>` (capacidad opcional).
- **Tests (toda la suite):** `uv run pytest`
- **Un solo archivo:** `uv run pytest tests/unit/test_corpus.py -x`
- **Un solo test:** `uv run pytest tests/unit/test_corpus.py::test_merge_idempotente -xvs`
- **Por marcador:** `uv run pytest -m unit` / `uv run pytest -m integration` (los tests que
  toquen red o Neo4j se marcan `integration` y usan Testcontainers o mocks; el núcleo va en
  `unit`). El marcador **`network`** es aparte: tests que pegan a la **API real de OpenAlex**
  (no mock) — **fuera del gate por defecto** (`addopts -m "not network"`); se corren explícitos con
  `uv run pytest -m network`. Los `integration` de DuckDB/store **sí** quedan en el gate.
- **Lint:** `uv run ruff check .` y `uv run ruff format --check .` (así lo corre el CI; `exploracion/` excluido)
- **Tipos:** `uv run mypy src`
- **Todo en uno (gate de CI):** `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest`

Regla de Hito 0: el **tooling LOCAL** —uv, linter (`ruff`), tipos (`mypy`), tests
(`pytest`), hooks (`pre-commit`) y **commitizen** (linter de Conventional Commits +
`cz bump --dry-run` para previsualizar el bump)— quedó configurado desde el día uno
(ADR 0006/0010). El mismo gate (`ruff` + `mypy` + `pytest`) corre **en CI** en cada push
a `main`/`dev` y en cada PR (`.github/workflows/ci.yml`). La **automatización de releases
(`release-please`) YA está conectada** (`.github/workflows/release-please.yml`); falta solo
la publicación a PyPI (ver §Comandos de release). La versión de Python la fija
`.python-version` (3.12; `requires-python >=3.11`).

## Comandos de release

`release-please` **YA está conectado** (`.github/workflows/release-please.yml`): vigila
`main` y, cuando llegan commits liberables (vía el merge `dev → main`), abre/actualiza
**un** PR `chore(main): release X.Y.Z` con el `CHANGELOG.md` + bump de `pyproject.toml`;
al mergearlo crea el tag `vX.Y.Z` y el **GitHub Release**. Pre-1.0: `feat`→minor,
`fix`→patch, breaking→minor. **No publica a PyPI** (decisión del PO: solo GitHub Releases
por ahora). `commitizen` **no** es el publicador: es (a) el linter de Conventional Commits
(hook de `pre-commit`) y (b) preview del bump con `cz bump --dry-run`.

- **Hacer un commit conventional:** `uv run cz commit` (interactivo, recomendado).
- **Previsualizar qué versión saldría:** `uv run cz bump --dry-run` (solo preview, no publica).
- **No bumpear/taggear a mano:** lo hace release-please al mergear su PR de release.
- **Tags publicados en `origin`:** `v0.1.0`, `v0.2.0`, `v0.3.0`, `v0.3.1` (GitHub Releases).
- **Caveat:** el PR de release **no dispara CI** (los commits del `GITHUB_TOKEN` no disparan
  workflows); se mergea con **bypass de admin** hasta que exista el secret `RELEASE_PLEASE_TOKEN`.

Detalle en [`CONTRIBUTING.md`](CONTRIBUTING.md) y [`VERSIONING.md`](VERSIONING.md).

## Convenciones de código (Python)

### Estilo y formato

- **PEP 8 + `ruff format`** (ancho 88). Sin debates de estilo: el formatter decide.
- **Docstrings** en español (la doc y los comentarios de los ADRs están en español; mantener
  el idioma del proyecto). Una línea para funciones triviales, multilínea con secciones
  `Args:` / `Returns:` / `Raises:` para lo demás.
- **Sin comentarios innecesarios.** El código se explica solo. Los docstrings justifican el
  *por qué*, no el *qué*.
- `from __future__ import annotations` en todos los módulos del paquete.

### Imports

- **No hay efectos de import** (lección 6 de v0). Importar un módulo nunca debe tocar config,
  red, disco ni estado global.
- Dependencias opcionales (extras) se importan de forma **perezosa** dentro de la función que
  las usa, con un mensaje de error claro que apunte al extra faltante.
- Orden: stdlib → third-party → local, separados por línea en blanco. `ruff` lo enforce.

### Tipos

- **Tipado estático en todas las firmas públicas** (`docs/API.md` §Convenciones). El núcleo
  y las costuras son `Protocol` o ABC; las implementaciones concretas los cumplen.
- **Modelos de datos serializables** (`Manifest`, `NetworkSpec`, configs) son **Pydantic
  v2** (`BaseModel`), no dataclasses. Esto da validación, serialización JSON nativa y
  compatibilidad con el CLI/JSON-schema.
- Para entidades internas efímeras (ej. dataclasses para vistas materializadas en tests),
  usar `dataclass(frozen=True)`. **No** son parte del contrato público.
- Para campos opcionales: `str | None`, nunca `Optional[str]` (mypy + ruff lo prefieren).
- Colecciones mutables en dataclasses: `field(default_factory=list)` o `dict`.

### Naming

- **snake_case** para funciones, métodos, variables, módulos.
- **PascalCase** para clases (`Corpus`, `BibtexSource`, `CoCitationProjector`).
- **UPPER_SNAKE** solo para constantes reales (`MIN_WEIGHT_DEFAULT = 1`).
- Costuras terminan con su rol: `XxxSource`, `XxxEnricher`, `XxxStore`, `XxxProjector`,
  `XxxExporter`, `XxxPreprocessor`. Esto las hace localizables con grep y respeta el
  vocabulario del `docs/API.md`.
- **No nombrar cosas como v0** (`enriquecimiento.py`, `analisis/`, scripts ad-hoc). El
  producto es genérico; los nombres deben reflejar el dominio, no el estudio que valida.

### Estructura de paquetes (fijada en ADR 0006)

```
src/bib2graph/
  __init__.py
  constants.py         # CAPA BASE (ADR 0023, Hito R1): Col/CurationStatus/NetworkKind (StrEnum),
                       # fuente única de literales. Todo lo demás depende de esta capa.
  corpus.py            # Corpus, Manifest, CorpusSnapshot (wrapper sobre tabla Arrow)
  schemas.py           # CAPA BASE (ADR 0023): PaperRow (Pydantic) ÚNICA fuente; CORPUS_SCHEMA (Arrow)
                       # derivado/verificado; ProvenanceEvent(BaseModel) consolidado acá (NO hay
                       # models.py separado), parseo que falla ruidoso
  cycle.py             # FSM CÍCLICO de dominio puro (ADR 0016 enmendado, Hito R3): SEEDED→…→
                       # MONITORED + reseed/ronda. Sale del backend; el backend solo lo persiste.
  sources/             # OpenAlexSource (núcleo, backbone); BibtexSource (secundaria, cableada al CLI
                       # como seed --from-bib, 3er modo sin red —ADR 0030 Ciclo 10, #50);
                       # equation.py (EquationSpec + load_equation_spec, capa declarativa de la
                       # ecuación —seed --spec, 9a); RIS, CSV (futuro, no publicar)
  backends/            # TabularBackend (Protocol) + InMemoryBackend (núcleo puro) +
                       # DuckDBBackend (biblioteca viva, carga perezosa de duckdb; persiste cycle).
                       # #54: tabla hermana referenced_but_not_fetched (IDs observados por el backward
                       # sin materializar) → add_referenced_refs/referenced_refs_count/referenced_refs,
                       # fuera del corpus_hash
  foraging/            # Forager (chaining + ranking por scent BIBLIOMÉTRICO vía proyectores, Hito R4).
                       # SIN explain.py / explain_candidate / [llm] (eliminados, ADR 0022)
  preprocessors/       # normalize + dedup fuzzy DETERMINISTA (rapidfuzz NÚCLEO, automáticos en la
                       # ingesta, ADR 0031) + thesaurus multilingüe DETERMINISTA explícito, sin
                       # fallback LLM
  filters/             # filtros de inclusión/exclusión con conteo PRISMA (núcleo)
  enrichers/           # OpenAlexEnricher opt-in, NÚCLEO (Hito 8 ✅: refs→DOI 8a + co-citación 8b → pobla cited_by_id);
                       # Enricher Protocol; S2 ([s2]) reservado para señal adicional, NO el Enricher (ADR 0025)
  networks/            # Projector, Analyzer, NetworkSpec (resolution + extra="forbid"), load_specs (YAML, Hito 9),
                       # NetworkArtifact, Networks, cluster_table (#31)
  exporters/           # GraphML, CSV
  service/             # CAPA DE SERVICIOS NEUTRAL (ADR 0028, AS-BUILT G1+G2+G3 del MVP GUI): contrato
                       # compartido por CLI/API, agnóstico de transporte (sin print/sys.exit/Click/
                       # FastAPI). envelope.py = build_envelope + ENVELOPE_SCHEMA_VERSION; errors.py =
                       # jerarquía B2GError (+ Usage/Data/Dependency/Network/StoreError) + code_for
                       # (mapeo puro error→exit code 0–5). reads.py (G2 ✅) = 6 lecturas read-only de la SPA
                       # sobre un Workspace resuelto: get_workspace/list_rounds/get_paper/get_scent/
                       # get_network/compare_rounds (ronda=snapshot; sin red/mutación/transición; API.md §0.1).
                       # curate.py (G3 ✅) = orquestación de curación SUBIDA desde cli/: accept_papers/
                       # reject_papers/curate_paper (toma store_path; decided_at inyectado en la frontera);
                       # run_accept/run_reject del CLI son shims que delegan (firma intacta). API.md §0.2.
                       # cli/ re-exporta el contrato (subido desde cli/_envelope.py·_errors.py) y conserva
                       # solo el I/O del adaptador. La migración del resto de la orquestación run_<cmd> sigue TARGET.
  api/                 # API LOCAL FastAPI (ADR 0028, AS-BUILT G3 del MVP GUI): adaptador DELGADO sobre
                       # service/ (NO importa de cli/; el núcleo NO importa fastapi —import perezoso, extra
                       # [gui]). app.py = create_app(ws, *, token, cors_origins); routers/reads.py (6 GET)
                       # + routers/curate.py (POST); security.py = token Bearer efímero; deps.py = workspace
                       # singleton + require_token (401) + WriteLock global; envelopes.py = mapeo código→HTTP
                       # (0→200,1→400,2→422,3→501,4→502,5→409; inesperado→500 INTERNAL_ERROR), reusa
                       # service.build_envelope/code_for. La SPA (frontend/, G4) y el empaquetado del wheel
                       # (G5: force-include) están AS-BUILT; solo queda el gate #34 (validación, no build). API.md §0.2.
  stores/              # DuckDBStore (núcleo, por defecto: biblioteca viva);
                       # ParquetStore (export); ZoteroStore ([zotero], V1.1);
                       # Neo4jStore ([neo4j], post-V1)
  cli/                 # paquete de 3 capas (Click → run_<cmd>() núcleo → envelope/errores);
                       # _ingest.py = helper normalize_and_dedup (auto-preproc en la ingesta, ADR 0031);
                       # cli/commands/ = 19 subcomandos (incl. monitor FSM→MONITORED, enrich refs→DOI + co-citación,
                       # init scaffold de workspace —ADR 0029, curate dump/import CSV —#22+#26,
                       # networks capa declarativa YAML —Hito 9, restore rehidrata corpus curado sin
                       # red →FILTERED —ADR 0030/9a, thesaurus aplica thesaurus curado transversal —#88/ADR 0031,
                       # gui levanta la API local FastAPI —Hito G3 del MVP GUI/ADR 0028, extra [gui];
                       # G4: _make_index_response inyecta el token en el index.html servido vía ruta GET /).
                       # CLI = API
                       # para LLM y agentes (Hito 6, ARCHITECTURE.md §6.3). No es un cli.py plano.
  workspace.py         # Workspace (init/open/resolve; snapshots_dir/exports_dir/networks_dir;
                       # read_networks_corpus_hash/is_networks_cache_stale —staleness #32) +
                       # WorkspaceManifest (ADR 0029): la carpeta es la unidad de persistencia;
                       # resolución ambiente; import perezoso de DuckDBStore
tests/
  unit/                # tests puros, sin red ni I/O (default)
  integration/         # red / APIs externas / Neo4j; @pytest.mark.integration
```

La estructura es orientativa (ADR 0006): un módulo plano (`corpus.py`) o un paquete
(`sources/`) es decisión del implementador según crezca. Lo fijo son los **nombres del
dominio** y los **contratos de `docs/API.md`**.

### `frontend/` — la SPA (paquete JS, NO Python; AS-BUILT G4, ADR 0028)

El **único subárbol JS** del repo. El resto del monorepo es Python con **uv**; `frontend/` es
JavaScript con **`pnpm` (SIEMPRE pnpm, nunca npm** — preferencia firme del PO). Es la SPA "tool for
thought" del MVP GUI (React 18 + Vite + TS estricto + Cytoscape/fcose + Zustand + Tailwind + TanStack
Query), dirección visual **D-2 "Observatorio"** (oscuro, grafo-céntrico; design tokens propios en
`tailwind.config.js`).

```
frontend/                       # NO va al wheel; su build (gui/static/) sí (vendoreado vía force-include, G5)
  package.json                  # packageManager: pnpm@…; scripts dev/build/test:run/lint
  pnpm-lock.yaml                # lockfile reproducible
  vite.config.ts                # outDir → ../src/bib2graph/gui/static ; base "./" ; alias @ → frontend/src
  index.html                    # placeholder del token (<meta b2g-token> + window.__B2G_TOKEN__)
  src/{client,types,store,components,lib,styles}/   # cliente tipado, DTO espejo, estado, UI
  src/__tests__/                # vitest (14)
```

Comandos (desde `frontend/`): **`pnpm lint`** (`tsc --noEmit`) · **`pnpm test:run`** (vitest, 14) ·
**`pnpm build`** (`tsc --noEmit && vite build` → escribe `src/bib2graph/gui/static/`). El **alias `@`**
resuelve a `frontend/src/`. El **build output** (`src/bib2graph/gui/static/`) está **gitignoreado**
(no se commitea; lo vendorea el wheel vía `force-include`, G5 AS-BUILT). El cliente consume los 7 endpoints reales de la API G3
(`docs/API.md` §0.2): des-envuelve el envelope `schema="1"`, ramea por `error.code` (**string**) y
manda `Authorization: Bearer <token>` (token leído de `window.__B2G_TOKEN__`, inyectado por `b2g gui`
en el `index.html` servido).

### Manejo de errores

- **Fallar fuerte, no en silencio** (lección 7 de v0). Si falta una dependencia requerida
  (p. ej. `python-louvain` para `detect_communities(method="louvain")`), lanzar un error
  **explícito y temprano** con un mensaje que diga qué instalar. Nunca degradar a otra
  estrategia en silencio.
- **Nada de `try/except` que oculte incompatibilidades de contrato** (lección 3 de v0). Si
  una función recibe una firma distinta, la llamada debe fallar ruidosamente, no
  enmascararse.
- **Acceso defensivo a campos de entrada** (lección de v0 con `research-areas`): usar
  `entry.get("author")` o `entry.get("author", [])`, no acceso directo. En BibTeX con
  `bibtexparser`, los campos opcionales faltan seguido.
- **Idempotencia.** `Corpus.merge` y los `Enricher.enrich` deben ser idempotentes:
  re-ejecutarlos sobre el mismo corpus no debe duplicar datos.
- **Exit codes del CLI** (Hito 6): `0` éxito, `1` error de uso, `2` error de datos, `3`
  dependencia faltante, `4` red no disponible, `5` store/snapshot corrupto. Sin estado entre
  invocaciones.

### Configuración y secretos

- **Una sola fuente de configuración**, construida explícitamente y pasada a quien la use.
  **Ningún secreto embebido como literal** (lección 1 de v0). API keys de S2, credenciales de
  Neo4j, etc., se inyectan por config / CLI / entorno; **nunca** un default secreto en
  código.
- **Sin contraseñas por defecto.** Si falta una credencial requerida, error claro.
- Sin `os.environ.get("X", "default_literal")` para secretos. Para lo no-secreto, defaults
  explícitos y documentados.

### Modelado de dominio (tabla canónica)

- El `Corpus` se documenta **una sola vez** (`docs/API.md` §1): el schema de columnas de la
  tabla Arrow + la API del wrapper + el `Manifest` + el `CorpusSnapshot`. Los docstrings
  del código deben coincidir con esa sección. Nada de columnas divergentes con campos
  inexistentes (lección 4 de v0: `Institution.address`, `Paper(note=...)`, `CITED_BY`).
- Las "entidades" (`Paper`, `Author`, `Keyword`, `Institution`) **no son tipos del
  modelo**. Si el código define dataclasses con esos nombres, son **vistas temporales**
  para tests/debugging vía `Corpus.materialize(...)`, no contrato público.
- **Relaciones derivadas** (`CO_CITED_WITH`, `COLLABORATED_WITH`, `CO_OCCURS_WITH`) **no
  viven en el corpus**: son salida de un `Projector`. Si aparecen como columna de la
  tabla, está mal.
- `is_seed` distingue el corpus original (ecuación/semillas) del traído por el **forrajeo/
  chaining**. El **acoplamiento bibliográfico** se proyecta sobre el **corpus completo** (no solo
  semillas; ciudadano de primera, crítica #2); la **co-citación** usa `scope="seeds_only"` y
  requiere el 2º nivel de fetch (el más caro). Ver `docs/API.md` §7.

### Funciones puras en el núcleo

- Proyectores, analizadores y la lógica de deduplicación son **funciones puras** sobre
  `pa.Table` o `nx.Graph`. Sin I/O, sin red, sin estado global, sin servidor. Esto es lo
  que permite tests rápidos y reproducibles (la victoria de v0 que faltaba en v0).
- Los `Store`, `Source`, `Enricher` y `Preprocessor` **sí** pueden tener I/O y red; ese es
  su trabajo. Pero las interfaces se inyectan, no se construyen dentro del núcleo.
- `Networks.build(corpus, spec)` y `Networks.quick(corpus)` son funciones puras: mismo
  corpus + mismo spec → mismo `NetworkArtifact`.

### CLI como API para LLM y agentes

- Cada subcomando expone `--json` con salida estructurada (un objeto por corrida,
  estable y versionado).
- Exit codes claros (ver §Manejo de errores).
- Sin estado entre invocaciones: cada llamada es independiente. El agente orquesta
  orquestando subprocess.
- Tool schemas JSON y/o servidor MCP son trabajo futuro (post-v0.3). El CLI ya
  alcanza como frontera programática.

### Publicar solo lo que existe

- Las costuras futuras (`RisSource`, `CsvSource`, `CrossRefEnricher`, `ScopusEnricher`,
  tool schemas JSON, MCP) **no se mencionan en el README ni en `__init__.py` hasta que
  existan** (lección 5 de v0). Documentarlas en `docs/API.md` con estado "futuro — no
  implementado" es válido; importarlas o listarlas en extras sin código real, no.
- Si un cliente de una API externa se inicializa, debe usarse. No cablear imports muertos.

## Tests

> **TDD selectivo.** En el núcleo, el test va **antes** del código. Pero **no se testea cada
> cosa**: se testea donde hay lógica, un contrato o riesgo de regresión; no wrappers finos,
> plumbing de Click, ni el cliente HTTP de terceros. La disciplina completa (qué SÍ / qué NO) y
> los tests concretos por hito están en `docs/ROADMAP/` (§"Disciplina de tests" + cada hito).

- **El núcleo se testea primero, sin red ni servidores** (Hitos 1 y 2). Tests sobre
  `Corpus`, proyectores y analizadores con datos sintéticos pequeños y **resultados
  conocidos** calculados a mano.
- **Tests para `Source`**: `OpenAlexSource` contra respuestas **mockeadas**
  (`httpx.MockTransport`), incluyendo el parser defensivo del `abstract_inverted_index`;
  `BibtexSource` sobre `.bib` con campos opcionales ausentes (regresión del bug T1 / `KeyError`).
- **Tests para `Forager`**: orden del ranking por *information scent*, preview/tope sin mutar el
  corpus.
- **Tests para `DuckDBStore`**: persistir → releer en instancia nueva (acumulación entre
  corridas), idempotencia de `persist`, procedencia/curación recuperables — DuckDB en proceso.
- **Tests para `Enricher`** con respuestas de la API **mockeadas**. **Sin red en CI.**
- **Tests para `Neo4jStore`** contra una Neo4j efímera (Testcontainers) o mockeando el
  driver. Marcados como `integration`.
- **Tests para `CorpusSnapshot`**: sellar, recargar, comparar `corpus_hash` estable,
  detectar `schema_version` incompatible.
- **Tests de contrato `--json` del CLI** (Hito 6): la forma de la salida no driftea; mapeo de
  errores a exit codes.
- Cada test debe poder correr en aislamiento: nada de orden implícito, nada de
  fixtures que compartan estado mutable entre tests.

## Estructura de un commit / PR (Conventional Commits)

Mensajes en español, imperativo, formato
[Conventional Commits](https://www.conventionalcommits.org/) estricto:

```
<tipo>(<alcance>): <descripción corta en imperativo, español, sin punto final>

<cuerpo opcional: por qué, no qué>

<footer opcional: BREAKING CHANGE: ... o referencia a issue>
```

Tipos: `feat` (Added), `fix` (Fixed), `refactor` (Changed), `perf` (Changed),
`docs` (no release), `test` (no release), `chore` (no release), `build` (no
release), `ci` (no release), `style` (no release). Alcance sugerido:
`corpus`, `sources`, `foraging`, `preprocessors`, `filters`, `enrichers`,
`networks`, `exporters`, `stores`, `cli`. Detalle completo en
[`CONTRIBUTING.md`](CONTRIBUTING.md).

- Cambios de código van con su test en el mismo commit/PR.
- Cambios a contratos públicos (`docs/API.md`) se discuten en un ADR nuevo en
  `docs/decisiones/` antes de mergear.
- Breaking changes: `BREAKING CHANGE:` en el footer del commit. Bumpea MINOR
  (o MAJOR si estamos en `1.x+`). Ver [`VERSIONING.md`](VERSIONING.md).

## Versionado

**SemVer estricto** (`MAJOR.MINOR.PATCH`). Mientras la mayor sea `0`, la API
se considera inestable: cualquier cambio visible al usuario (no bugfix) bumpa
MINOR. El congelamiento en `1.0.0` requiere API pública estable, cobertura de
tests razonable y un caso real validado (el caso **IED** reproducido; ver PRD §10).
Detalle y tabla de ejemplos en [`VERSIONING.md`](VERSIONING.md).

## Changelog

**Keep a Changelog**. El `CHANGELOG.md` lo **gestiona `release-please`** (ya conectado): su
PR de release agrega la sección nueva desde los Conventional Commits que llegan a `main`. Las
secciones por debajo de `[0.3.0]` son el historial previo a la conexión (mantenido a mano); de
ahí en adelante las gestiona el bot. `cz bump --dry-run` sigue sirviendo como preview local.
Plantilla en [`docs/RELEASE_TEMPLATE.md`](docs/RELEASE_TEMPLATE.md).

## Dónde mirar primero según la tarea

- Empezar cualquier hito → `docs/ROADMAP/`: historias (PRD §7), criterios de
  aceptación (DoD) y los tests TDD a escribir.
- Tocar el modelo de datos → `docs/API.md` §1, `docs/ARCHITECTURE.md` §3,
  [ADR 0006](docs/decisiones/0006-tabla-canonica-y-networkspec.md).
- Añadir una red nueva → `docs/ARCHITECTURE.md` §3.2, tabla de proyectores en
  `docs/API.md` §7.
- Sembrar / forrajear → `docs/API.md` §2 (`Source`/OpenAlex) y §5 (`Forager`),
  [ADR 0007](docs/decisiones/0007-openalex-backbone.md),
  [ADR 0008](docs/decisiones/0008-wedge-forrajeo.md).
- Persistencia / biblioteca viva → `docs/API.md` §4,
  [ADR 0009](docs/decisiones/0009-biblioteca-viva-duckdb.md).
- Normalización / thesaurus → `docs/API.md` §6,
  [ADR 0011](docs/decisiones/0011-thesaurus-multilingue.md).
- Añadir una costura (`Source` / `Enricher` / `Store`) → `docs/API.md` §2-4, ADR
  correspondiente, `docs/Notas/01-lecciones-v0.md` (reglas 1, 3, 5, 6, 7).
- CLI agente-native → `docs/API.md` §convenciones, `docs/ARCHITECTURE.md` §6.3,
  [ADR 0010](docs/decisiones/0010-agente-native-columna.md) (Hito 6).
- Capa D / `NetworkSpec` → `docs/API.md` §10, se libera en v0.3+ (Hito 9).
- Decisiones de dependencias / extras → `docs/decisiones/0005-...`.
- Cambios al método bibliométrico (qué cuenta como co-citación, umbrales) →
  `docs/Notas/metodología.md`.
