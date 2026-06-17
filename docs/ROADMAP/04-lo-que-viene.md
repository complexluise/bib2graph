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

## Hito 9 — Capa declarativa: `NetworkSpec` (v0.2)

**Alcance**

- `NetworkSpec` como `BaseModel` con loader YAML (API.md §10); `b2g networks --spec redes.yaml
  --json`.
- **Parámetros por algoritmo de clustering** — entre ellos `resolution` de Louvain (diferido de
  **R2**, ADR 0017 punto 4): el `random_state` ya es seeded desde R2; aquí se expone `resolution`
  (y demás params) vía la spec declarativa.

**Historias:** profundiza **E1/E2** (pipelines reproducibles versionados en git: un YAML describe
qué se calcula). Abre la puerta a un GUI (editor de `NetworkSpec`).

**Criterios de aceptación (DoD)**

- Un `redes.yaml` válido carga y valida; uno inválido falla con error accionable.
- `Networks.build(corpus, spec)` desde YAML es **equivalente** a la spec correspondiente de
  `Networks.quick`.

**Tests (TDD — los justos)**

- Carga/validación de un YAML válido y uno inválido (2 casos).
- Equivalencia `build(spec)` ≡ la spec de `quick` para una red.

**Se vuelve posible:** pipelines reproducibles versionados en git. Abre la puerta a un GUI.

---

## Hito 10 — Visualización (extra `[viz]`)

**Alcance**

- Figuras de redes/comunidades con `matplotlib`/`seaborn`, fuera del núcleo liviano.

**Historias:** apoyo visual a **D** (lectura de la estructura intelectual).

**Criterios de aceptación (DoD)**

- Genera una figura por red sin romper el núcleo liviano; import **perezoso** de `[viz]`.

**Tests (TDD — los justos)**

- Que la función produzca un objeto figura / archivo (smoke test); **no** comparar píxeles.

---

## Hito 11 — Costuras externas de biblioteca/persistencia (post-V1)

**Alcance**

- **`ZoteroStore`** (extra `[zotero]`, **V1.1**): sincronizar la biblioteca viva con una
  colección Zotero (leer semillas / devolver lo aceptado). Costura opt-in, no el corazón (ADR
  0009).
- **`Neo4jStore`** (extra `[neo4j]`, post-V1.2): adaptador tabla→grafo para consultas Cypher.
  **Ya no es sustrato** (ADR 0002).

**Historias:** extiende **C4** (biblioteca viva sincronizable con Zotero) como costura opt-in.

**Criterios de aceptación (DoD)**

- Round-trip Zotero (leer semillas / escribir aceptados) contra cliente mockeado; `integration`
  contra Neo4j efímera (Testcontainers) para el adaptador.

**Tests (TDD — los justos)**

- Round-trip Zotero sobre cliente mock.
- `Neo4jStore` marcado `integration` (Testcontainers o driver mockeado), fuera del gate `unit`.

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
- **Workspace por investigación · ✅ HECHO (2026-06-16, ADR
  [0029](../decisiones/0029-workspace-por-investigacion.md); issues #32/#38/#39):** cada investigación
  = una carpeta auto-contenida (`workspace.json` + `library.duckdb` + `networks/`/`snapshots/`/
  `exports/`), en vez de un `.duckdb` suelto. Evolucionó el modelo "una investigación = un archivo"
  (enmienda a ADR [0009](../decisiones/0009-biblioteca-viva-duckdb.md) /
  [0019](../decisiones/0019-concurrencia-diferida.md)). Construido: módulo `workspace.py`, **14°
  subcomando `b2g init`**, `--store` opcional + `--workspace` con resolución ambiente; el `.duckdb`
  suelto sigue válido (workspace degenerado). Prerequisito de la epic GUI local
  ([#34](https://github.com/complexluise/bib2graph/issues/34),
  [Nota 07](../Notas/07-frontend-tool-for-thought.md)). **Fuera de este corte:** `snapshot`/`export`
  aún con `--out-dir` explícito; staleness solo sella el hash (sin aviso/regeneración automática).
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

> **RETIRADO del producto (ADR [0022](../decisiones/0022-producto-sin-ia-generativa.md), 2026-06-15):**
> el **fallback fuzzy/semántico del thesaurus por LLM** y la **"máquina de tensiones"** (la antigua
> "inserción de IA nº2") **ya no son costuras futuras: se borran**. El producto **no usa IA
> generativa**; el extra `[llm]` se elimina (Hito R4). El sensemaking de tensiones es **humano**,
> asistido por las redes. El **dedup fuzzy del thesaurus** que sí queda (Hito 7) es **determinista**
> (`rapidfuzz`, extra `[dedup]`; Hito 7 ✅), no semántico/LLM. La única "inteligencia" que asiste es el
> **scent bibliométrico** (Hito R4), que no es IA.

---
