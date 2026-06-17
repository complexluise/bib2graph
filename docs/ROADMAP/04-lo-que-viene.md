> ← Volver al [índice del ROADMAP](README.md)

# LO QUE VIENE (Hitos 7–11, actualizados a la nueva realidad)

> **Tras la remediación R1–R5.** Estos hitos son los opcionales/de cierre hacia v1.0, ya
> reconciliados con el modelo nuevo (sin IA generativa, scent bibliométrico, FSM cíclico).

## Hito 7 — Deduplicación fuzzy (extra `[dedup]`) — **COMPLETO ✅**

> **Hito 7 COMPLETO ✅ (2026-06-16, ADR [0026](../decisiones/0026-dedup-fuzzy-determinista.md)):**
> `deduplicate_authors`/`deduplicate_keywords` con **`rapidfuzz`** (determinista), **autores +
> keywords** (instituciones **diferidas** — `institutions_id` no está normalizada
> determinísticamente hoy). **Función de librería, sin subcomando CLI** (decisión del PO). `splink`
> (probabilístico/pesado) **diferido a post-V1**.

**Alcance**

- `deduplicate_authors(corpus, *, threshold=0.92)` / `deduplicate_keywords(corpus, *,
  threshold=0.90)` (lo fuzzy; el determinístico ya está en el `Preprocessor` del Hito 5; API.md §11).
  Operan sobre `_id` (no `_raw`), después de normalize → thesaurus.

**Historias:** refina **C1** (autores limpios de duplicados aproximados; instituciones diferidas) y
**C2** (keywords fuera del thesaurus).

**Criterios de aceptación (DoD)**

- **✅** Combina variantes por similitud por encima de un `threshold` **por-campo** configurable;
  **determinista** (`token_sort_ratio` + Union-Find + canónico más-frecuente/desempate-id) e
  idempotente.
- **✅** Importación **perezosa** del extra `[dedup]` (= `rapidfuzz`): sin él, `ImportError` claro que
  apunta al extra (`uv sync --extra dedup`).

**Tests (TDD — los justos)**

- Mapeo de un par de nombres/keywords casi-iguales por encima/por debajo del umbral.
- Que sin el extra instalado el error sea explícito (mock del import faltante).

**Se vuelve posible:** redes de autor/keyword limpias de duplicados aproximados.

---

## Hito 8 — `Enricher` opt-in: resolución de refs + co-citación (núcleo OpenAlex)

> **Partición (ADR [0025](../decisiones/0025-enricher-cocitacion-openalex.md), 2026-06-16) — Hito 8
> COMPLETO ✅:** el hito se hizo en **2 ciclos**. **8a ✅:** costura `Enricher` + refs→DOI + subcomando
> `b2g enrich`. **8b ✅:** co-citación end-to-end (poblar `cited_by_id`), **solo seeds aceptadas + tope
> configurable** (`--max-citing`). El Enricher vive en el **núcleo sobre OpenAlex**, **no** en el extra `[s2]`: ese
> `[s2]` era residuo pre-giro (ADR [0007](../decisiones/0007-openalex-backbone.md): S2 ya no es
> estructural) y queda **reservado** para un futuro `SemanticScholarEnricher` de señal adicional.

**Alcance**

- `Enricher` (ya **no estructural**; ADR 0007/0025, API.md §3): **resolver `references_id` a DOI
  canónico** (T8, **8a ✅**) y el **segundo nivel de fetch** (citantes ≡ `cited_by_id` compartido) que
  habilita la **co-citación** completa (**8b ✅**). El 2º nivel **solo puebla `cited_by_id`**; los
  citantes NO se materializan como filas del corpus (eso es del `Forager` + curación; decisión A).
- **Batching-por-OR de `fetch_citing`** (seguimiento heredado de R5, encuadrado acá por el arquitecto
  2026-06-16, **resuelto en 8b ✅**): R5 entregó **retry/backoff** pero **difirió** el batching. El
  **2º nivel de fetch de este hito** lo materializa: **`OpenAlexSource.fetch_citing_batch`** agrupa
  varios `cites:` en una query `cites:W1|W2|...` (lotes ≤50) con **presupuesto por semilla**, matando
  el N+1 de requests (mejora de performance, no de correctitud: el N+1 ya era resiliente al
  rate-limit). Ver registro-ia R5.3 y "Cleanup pre-v0.3" C-seguimientos.
- **Forward chaining del `Forager` batcheado (#21) · ✅ HECHO (2026-06-16):** el forward del
  **`Forager`** (`b2g chain`/`b2g monitor`) también dejó de hacer N+1 — **reusa
  `fetch_citing_batch`** (mismo primitivo del 8b), suma **cap por semilla**
  `max_citing_per_paper`/**`--max-citing`** (default 50) y **preview sin red** (estima nº de semillas
  a forrajear). **Scope = `is_seed=True`** (todas las semillas, **sin** filtrar `curation_status`): el
  chaining precede a la curación; la restricción a `accepted` es del **Enricher** (8b), no del Forager
  (ADR [0020](../decisiones/0020-metodo-forrajeo-scent-filtros-reject.md) AS-BUILT #21; API.md §5).
  Gate verde, **422 tests**.

**Historias:** completa **D1** para la red de **co-citación** end-to-end (la más cara) y la
interoperabilidad de referencias cross-source (OpenAlex ↔ `.bib`).

**Criterios de aceptación (DoD)**

- **8a ✅** `enrich` es **idempotente** (reemplaza el `EnricherRef` por nombre, no duplica) y no pierde
  papers ante rate limit/reintentos. Subcomando `b2g enrich` propio; **NO** transiciona el `CycleState`
  (ortogonal al lazo, decisión C). `build` sigue puro/sin red.
- **8a ✅** Resuelve `references_id` → `references_doi` **batcheando por OR** (lotes ≤100,
  `openalex_id:W1|W2|...`, `select=id,doi`).
- **8b ✅** El 2º nivel habilita `CoCitationProjector` completo poblando `cited_by_id` (el projector
  **no cambia**: cuenta `cited_by_id` compartido = citantes compartidos; decisión F). Solo seeds
  aceptadas + tope configurable (`max_citing_per_paper` / `--max-citing`). `Networks.quick` devuelve
  **4 o 5 redes** según haya `cited_by_id` (incluye co-citación si está poblado; la omite graceful si
  no).
- **8b ✅** **`fetch_citing_batch` batchea por OR** (`cites:W1|W2|...`, lotes ≤50) con presupuesto
  por semilla: el N+1 de R5 deja de hacer una request por paper, sin starvation entre semillas
  (mejora de performance; el retry/backoff de R5 se conserva).
- Config/keys **inyectadas**, sin ramas muertas. **Sin red en CI** (mock). Núcleo sin importar
  `duckdb`; sin red al importar.

**Tests (TDD — los justos)**

- Resolución refs→DOI sobre respuesta mockeada; idempotencia del `enrich`.
- Que el 2º nivel pueble lo que la co-citación necesita (sobre datos mock).
- *No testear* el rate limiter en tiempo real; sí la política de reintento con un cliente mock.

**Se vuelve posible:** la red de **co-citación** end-to-end y la interoperabilidad de referencias
cross-source.

---

## Hito 9 — Capa declarativa: `NetworkSpec` (v0.2) — **COMPLETO ✅**

> **Hito 9 COMPLETO ✅ (2026-06-17):** `NetworkSpec` gana **carga declarativa desde YAML** vía
> **`load_specs(path)`** (`networks/spec.py`, re-exportada desde `bib2graph.networks`; esquema raíz
> `networks:` = lista, cada entrada validada con `NetworkSpec(**entry)`, errores accionables citando
> archivo + `red #<idx>` + campo). Suma el campo **`resolution: float = 1.0`** (resolución de Louvain,
> propagada por `_build_artifact` a `best_partition(..., resolution=...)`; ignorada en `label_prop`/
> `greedy_modularity`; **fuera del `corpus_hash`** → seed de Louvain intacto, R2) y
> **`extra="forbid"`** (campo desconocido → error). Nuevo **16° subcomando `b2g networks --spec
> <yaml>`** (escribe artefactos con el helper compartido `_write_artifacts`; mismo envelope que
> `build`; **NO** transiciona el `CycleState` ni sella `.corpus_hash`). `pyyaml` promovido al núcleo
> (import perezoso). Gate verde, **516 tests**. Ver API.md §10 + §convenciones CLI.

**Alcance**

- `NetworkSpec` como `BaseModel` con loader YAML (API.md §10); `b2g networks --spec redes.yaml
  --json`.
- **Parámetros por algoritmo de clustering** — entre ellos `resolution` de Louvain (diferido de
  **R2**, ADR 0017 punto 4): el `random_state` ya es seeded desde R2; aquí se expone `resolution`
  (y demás params) vía la spec declarativa.

**Historias:** profundiza **E1/E2** (pipelines reproducibles versionados en git: un YAML describe
qué se calcula). Abre la puerta a un GUI (editor de `NetworkSpec`).

**Criterios de aceptación (DoD)**

- **✅** Un `redes.yaml` válido carga y valida; uno inválido falla con error accionable.
- **✅** `Networks.build(corpus, spec)` desde YAML es **equivalente** a la spec correspondiente de
  `Networks.quick` (nodos + aristas + comunidades).

**Tests (TDD — los justos)**

- **✅** Carga/validación de un YAML válido y uno inválido (2 casos).
- **✅** Equivalencia `build(spec)` ≡ la spec de `quick` para una red.

**Se vuelve posible:** pipelines reproducibles versionados en git. Abre la puerta a un GUI.

---

## Hito 10 — Visualización (extra `[viz]`) — **REEVALUADO: DIFERIDO (absorbido por la epic GUI #34)**

> **Reevaluación 2026-06-17 (architect, encuadre pre-GUI):** este hito —figuras estáticas
> `matplotlib`/`seaborn` por red— **se difiere y se absorbe en la epic GUI
> [#34](https://github.com/complexluise/bib2graph/issues/34)**. Razón: la GUI es **exactamente**
> la capa de lectura visual de la estructura intelectual (historia D), y su MVP es **read-only
> visualizar** (Nota 10/T-MVP). Construir ahora figuras estáticas separadas sería trabajo
> tirado o duplicado cuando llegue la SPA. **No es "terreno pre-GUI".** La **capa de export
> visual** que sí es separable (layout determinista, atributos de nodo para herramientas
> externas) **ya existe**: `networks/decorate.py` (#25 ✅, `label`/`year`/`is_seed`/`community`/
> `degree_centrality`) + `clusters.csv` (#31 ✅) hacen que el GraphML abra legible en
> Gephi/VOSviewer/Cytoscape **sin código**. Es decir, el "core/export" de viz pre-GUI **ya está
> cubierto**; lo que queda (render propio) es la GUI. **Verdadero alcance restante = render
> dentro de #34**, no un extra `[viz]` aparte.

**Alcance (original — diferido)**

- Figuras de redes/comunidades con `matplotlib`/`seaborn`, fuera del núcleo liviano.

**Historias:** apoyo visual a **D** (lectura de la estructura intelectual) — **cubierto por #34**.

**Criterios de aceptación (DoD)**

- Genera una figura por red sin romper el núcleo liviano; import **perezoso** de `[viz]`.

**Tests (TDD — los justos)**

- Que la función produzca un objeto figura / archivo (smoke test); **no** comparar píxeles.

---

## Hito 11 — Costuras externas de biblioteca/persistencia (Zotero/Neo4j) — **DESCARTADO (decisión del PO, 2026-06-17)**

> **Decisión del PO (2026-06-17):** **no se hace.** Ni `ZoteroStore` ni `Neo4jStore` son
> necesarios. La biblioteca viva propia (DuckDB) es el corazón de V1.0 (ADR 0009/0002) y la GUI
> se construye **sobre el workspace local**, no sobre integraciones externas. Se retira del
> ROADMAP; si en el futuro aparece demanda real (p.ej. round-trip con un Zotero existente), se
> reabrirá como un hito nuevo con su propio encuadre. No bloquea nada.

---

## Costuras futuras (NO planificadas — declaradas explícitamente)

Marcadas como no implementadas hasta que exista decisión de producto y código real (lección 5):

- `Source`: `RisSource`, `CsvSource`.
- `Enricher`: `CrossRefEnricher`, `ScopusEnricher`.
- Tool schemas JSON / servidor MCP → posterior, si la demanda lo justifica. El CLI ya cubre la
  frontera programática desde el Hito 6.

No se prometen ni se cablean clientes que no se usan.

## Backlog / ideas pendientes (sin hito ni DoD todavía)

- **Labels legibles en los nodos de las redes (#25) · ✅ HECHO (2026-06-16):** las redes salían con
  `id` crudo (`oa:…`, `I185261750`, un ORCID), ilegibles en Gephi/VOSviewer/Cytoscape (síntoma B3 de
  la [Nota 09](../Notas/09-sesion-qa-prueba-ecologia-valoraciones.md)). Se agregó la **capa frontera
  `decorate`** (`networks/decorate.py`: `decorate_graph`/`decorate`) entre los proyectores puros y el
  export/GUI, aplicada en `facade.py:_build_artifact`: inyecta `label` legible (mapeo por
  `NetworkKind`; paper → `"título (año)"` truncado a `LABEL_MAX_CHARS`=60) + atributos de nodo
  (`year`/`is_seed`/`curation_status`/`degree_centrality`/`community`). `Networks.quick`/`build`
  devuelven artefactos **decorados**; los proyectores **siguen puros** (ADR
  [0014](../decisiones/0014-proyeccion-redes-pesos-asortatividad.md) AS-BUILT #25). Reemplaza el
  workaround local `_label_for_kind` de `prueba/06_redes_y_grafos.py`. Ver API.md §7.1.
- **Tabla de clusters a CSV (#31) · ✅ HECHO (2026-06-17):** las redes salían con comunidades en el
  GraphML pero sin una vista tabular legible de **qué cae en cada cluster** (composición por comunidad).
  Se agregó la **función pura `cluster_table(table, artifact)`** (`networks/clusters.py`, re-exportada
  desde `networks/__init__.py`): una fila por comunidad con `cluster, size, seed_count, candidate_count,
  accepted_count, year_min, year_max, year_mean, top_authors, top_keywords`. **Solo redes de paper**
  (coupling/cocitación; redes de autor/keyword/institución → `[]`, no crash). Cruza nodo→fila por
  **`Col.ID`** (lección B6 de la [Nota 09](../Notas/09-sesion-qa-prueba-ecologia-valoraciones.md), no
  `openalex_id`); `top_authors` de `authors_raw`, `top_keywords` de `keywords_id`. **Determinista**
  (desempate `(-freq, nombre alfabético)`, reproducible cross-`PYTHONHASHSEED` y entre métodos de
  clustering; ADR [0017](../decisiones/0017-reproducibilidad-historia-snapshot.md)). **`b2g build`**
  escribe `<networks_dir>/<kind>/clusters.csv` (listas con separador `|`) cuando la red tiene
  comunidades, y el envelope `--json` suma `clusters_csv` **condicional** por red. Gate verde, **498
  tests**. Ver `API.md` §7.2 + §9 + §convenciones CLI.
- **Workspace por investigación · ✅ HECHO (2026-06-16, ADR
  [0029](../decisiones/0029-workspace-por-investigacion.md); issues #32/#38/#39):** cada investigación
  = una carpeta auto-contenida (`workspace.json` + `library.duckdb` + `networks/`/`snapshots/`/
  `exports/`), en vez de un `.duckdb` suelto. Evolucionó el modelo "una investigación = un archivo"
  (enmienda a ADR [0009](../decisiones/0009-biblioteca-viva-duckdb.md) /
  [0019](../decisiones/0019-concurrencia-diferida.md)). Construido: módulo `workspace.py`, **14°
  subcomando `b2g init`**, `--store` opcional + `--workspace` con resolución ambiente; el `.duckdb`
  suelto sigue válido (workspace degenerado). Prerequisito de la epic GUI local
  ([#34](https://github.com/complexluise/bib2graph/issues/34),
  [Nota 07](../Notas/07-frontend-tool-for-thought.md)). **Remanentes cerrados · ✅ HECHO (2026-06-17,
  #32):** `b2g snapshot`/`b2g export` ya resuelven por workspace (`--out-dir` pasó a override opcional
  → `<workspace>/snapshots|exports/`; modo degenerado = dir hermano) y `b2g status` suma
  `networks_cache_stale: bool` + `warnings` cuando el `networks/.corpus_hash` no coincide con el
  corpus vivo (**avisa, NO regenera**: invalidación por hash, no build-system). `Workspace` ganó
  `read_networks_corpus_hash()`/`is_networks_cache_stale()`. **El modelo workspace queda COMPLETO**
  (sin remanentes). Gate verde, **534 tests**.
- **Caso real reproducido: ecuación declarativa + `restore` + corpus de ejemplo (#33, ADR
  [0030](../decisiones/0030-ecuacion-declarativa-corpus-ejemplo.md)) · ✅ HECHO (9a+9b, 2026-06-17) ·
  #33 CERRADO:** prerequisito del gate de la epic GUI [#34](https://github.com/complexluise/bib2graph/issues/34)
  (un tercero reproduce el lazo end-to-end sobre un corpus real, **sin red**) — **cubierto**.
  - **9a ✅ HECHO (2026-06-17):** **(1)** capa declarativa de la ecuación — `EquationSpec` +
    `load_equation_spec` (`sources/equation.py`, Pydantic `extra="forbid"`, clave raíz `equation:`,
    errores accionables como `load_specs`) y **2º modo de `b2g seed`: `--spec equation.yaml`**
    (mutuamente excluyente con `--equation`; mismo `executed_query`). `min_year`/`max_year` están en el
    modelo pero **aún no filtran** contra OpenAlex (filtro de año = trabajo futuro; no se promete
    capacidad inexistente). **(2)** **17° subcomando `b2g restore --from-corpus <parquet>`**
    (`cli/commands/restore.py`): rehidrata un corpus **ya curado sin red** (inverso de `snapshot`;
    `CORPUS_SCHEMA` → `Corpus.from_arrow` → merge+persist), **preserva la curación**
    (`decision`/`curation_status`/`is_seed`) y transiciona el `CycleState` a **`FILTERED`** (reusa la
    transición permisiva `filter`, ADR [0016](../decisiones/0016-maquina-estados-lazo.md); deja correr
    `build`/`networks` sin re-forrajeo). Ronda normalizada con `max(loop_round(), 1)` (evita ronda 0 en
    bases legacy pre-R3). Gate verde, **564 tests**. Ver `API.md` §2 + §convenciones CLI.
  - **9b ✅ HECHO (2026-06-17):** **workspace de ejemplo `examples/valoraciones/`** (corpus curado
    congelado en `corpus.parquet`, **137 filas: 7 `accepted` / 130 `candidate` / 107 seeds**, reducción
    determinista del corpus real del PO CC0/OpenAlex + `equation.yaml` de procedencia + `README.md` +
    `build_corpus.py` de regeneración) como **excepción al `.gitignore`** de datos de usuario
    (`!examples/` + regla defensiva `examples/**/*.duckdb`). El **gate de reproducibilidad R2**
    (`tests/unit/test_example_r2_gate.py`, 7 tests) corre `restore --from-corpus` → `build` →
    `networks`/`clusters` **sin red** sobre el corpus real y verifica **`corpus_hash` estable** +
    **comunidades Louvain deterministas entre corridas** (cierra el agujero R2 de la
    [Nota 09](../Notas/09-sesion-qa-prueba-ecologia-valoraciones.md)). **Con 9b, #33 queda CERRADO** y
    el gate de #34 cubierto. Gate verde, **571 tests**. Ver `API.md` §2.1.
  - **Diferido (reabrible, fuera del ADR 0030; issue #50):** **`b2g seed --from-bib <archivo.bib>`**
    (2º camino de seed por BibTeX — cablear el `BibtexSource.load` ya existente al CLI) y su ejemplo
    **`examples/bibtex/`**.
- **Curación a escala vía CSV (#22 dump + #26 import) · ✅ HECHO (2026-06-16):** marcar papers de a
  uno con `accept`/`reject --ids` no escala (síntomas B4/B5/P1 de la
  [Nota 09](../Notas/09-sesion-qa-prueba-ecologia-valoraciones.md)). Se agregó el **15° subcomando
  `b2g curate`** (`cli/commands/curate.py`) con dos modos mutuamente excluyentes: **`--dump`** escribe
  `curacion.csv` (default `<workspace>/exports/`; `--out` override; `--all` para todo el corpus, default
  solo candidatos) para revisar offline en Excel/Calc, y **`--from-csv`** aplica las decisiones en lote
  (`accepted`→accept / `rejected`→reject / `undecided`→no-op). Columnas: `id, openalex_id, title, year,
  authors, scent_score, cluster, decision, note` (solo `decision`/`note` editables). **Idempotente**
  (reimportar = mismo `corpus_hash`; `decided_at` inyectado en la frontera, R2/ADR
  [0017](../decisiones/0017-reproducibilidad-historia-snapshot.md)), **validación accionable** y reporte
  de **IDs huérfanos** (`not_found_count`, cierra el no-op silencioso). **Curación transversal** (NO
  transiciona el `CycleState`; ADR [0016](../decisiones/0016-maquina-estados-lazo.md) enmendado R3).
  **Fuera de este corte:** `note` es **advisory** (round-trip en el dump, ignorada al importar —
  `ProvenanceEvent` no tiene campo de anotación; persistirla sería un ADR futuro); `scent_score`
  best-effort (vacío hasta que el Forager guarde scent en provenance) y `cluster` diferido (integración
  con redes). Gate verde, **459 tests**. Ver `API.md` §convenciones CLI.

- **Ergonomía de `b2g seed` (#14 `--max-results` + #30 `--exclude`) · ✅ HECHO (2026-06-16):** dos
  flags que afinan el seed sin tocar el contrato `Source`. **`--max-results INT` (#14)** propaga a
  `OpenAlexSource(max_results=...)` (sin flag = default del source, 200) para explorar con muestras
  chicas (síntoma B1 de la [Nota 09](../Notas/09-sesion-qa-prueba-ecologia-valoraciones.md)).
  **`--exclude TEXT` repetible (#30)** son **negaciones quirúrgicas**: `seed(..., exclude=[...])` y
  `_translate(exclude=...)` agregan `AND NOT title_and_abstract.search:"<término>"` por término al
  filtro y las **reportan en el `translation_report`** del `SeedResult` (ejercicio consciente, query
  visible); comillas internas saneadas; **ignorado con `native=True`**. *(La sintaxis NOT no se validó
  contra la API real —mock—; plausible/coherente con el passthrough.)* Gate verde, **476 tests**. Ver
  `API.md` §2 + §convenciones CLI.

> **RETIRADO del producto (ADR [0022](../decisiones/0022-producto-sin-ia-generativa.md), 2026-06-15):**
> el **fallback fuzzy/semántico del thesaurus por LLM** y la **"máquina de tensiones"** (la antigua
> "inserción de IA nº2") **ya no son costuras futuras: se borran**. El producto **no usa IA
> generativa**; el extra `[llm]` se elimina (Hito R4). El sensemaking de tensiones es **humano**,
> asistido por las redes. El **dedup fuzzy del thesaurus** que sí queda (Hito 7) es **determinista**
> (`rapidfuzz`, extra `[dedup]`; Hito 7 ✅), no semántico/LLM. La única "inteligencia" que asiste es el
> **scent bibliométrico** (Hito R4), que no es IA.

---
