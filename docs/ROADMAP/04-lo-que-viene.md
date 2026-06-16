> ← Volver al [índice del ROADMAP](README.md)

# LO QUE VIENE (Hitos 7–11, actualizados a la nueva realidad)

> **Tras la remediación R1–R5.** Estos hitos son los opcionales/de cierre hacia v1.0, ya
> reconciliados con el modelo nuevo (sin IA generativa, scent bibliométrico, FSM cíclico).

## Hito 7 — Deduplicación fuzzy (extra `[dedup]`)

**Alcance**

- `deduplicate_authors` / `deduplicate_keywords` (lo fuzzy; el determinístico ya está en el
  `Preprocessor` del Hito 5; API.md §11).

**Historias:** refina **C1** (autores/instituciones limpios de duplicados aproximados) y **C2**
(keywords fuera del thesaurus).

**Criterios de aceptación (DoD)**

- Combina variantes por similitud por encima de un `threshold` configurable; idempotente.
- Importación **perezosa** del extra `[dedup]`: sin él, error claro que apunta al extra.

**Tests (TDD — los justos)**

- Mapeo de un par de nombres/keywords casi-iguales por encima/por debajo del umbral.
- Que sin el extra instalado el error sea explícito (mock del import faltante).

**Se vuelve posible:** redes de autor/keyword limpias de duplicados aproximados.

---

## Hito 8 — `Enricher` opt-in: resolución de refs + co-citación (extra `[s2]`)

**Alcance**

- `Enricher` (ya **no estructural**; ADR 0007, API.md §3): **resolver `references_id` a DOI
  canónico** (T8) y el **segundo nivel de fetch** (citantes con sus citas) que habilita la
  **co-citación** completa.
- **Batching-por-OR de `fetch_citing`** (seguimiento heredado de R5, encuadrado acá por el arquitecto
  2026-06-16): R5 entregó **retry/backoff** pero **difirió** el batching (agrupar varios `cites:` en
  una query `cites:W1|W2|...` para matar el N+1 de requests). El **2º nivel de fetch de este hito** es
  exactamente donde se vuelve a forrajear citantes/citas a escala, así que el batching **se hace acá**
  (mejora de performance, no de correctitud: el N+1 ya es resiliente al rate-limit). Ver registro-ia
  R5.3 y "Cleanup pre-v0.3" C-seguimientos.

**Historias:** completa **D1** para la red de **co-citación** end-to-end (la más cara) y la
interoperabilidad de referencias cross-source (OpenAlex ↔ `.bib`).

**Criterios de aceptación (DoD)**

- `enrich` es **idempotente** y no pierde papers ante rate limit/reintentos.
- Resuelve `references_id` → `references_doi`; el 2º nivel habilita `CoCitationProjector` completo.
- **`fetch_citing` batchea por OR** (`cites:W1|W2|...`) en el 2º nivel de fetch: el N+1 de R5 deja de
  hacer una request por paper (mejora de performance; el retry/backoff de R5 se conserva).
- Config/keys **inyectadas**, sin ramas muertas. **Sin red en CI** (mock).

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

> **RETIRADO del producto (ADR [0022](../decisiones/0022-producto-sin-ia-generativa.md), 2026-06-15):**
> el **fallback fuzzy/semántico del thesaurus por LLM** y la **"máquina de tensiones"** (la antigua
> "inserción de IA nº2") **ya no son costuras futuras: se borran**. El producto **no usa IA
> generativa**; el extra `[llm]` se elimina (Hito R4). El sensemaking de tensiones es **humano**,
> asistido por las redes. El **dedup fuzzy del thesaurus** que sí queda (Hito 7) es **determinista**
> (`rapidfuzz`/`splink`, extra `[dedup]`), no semántico/LLM. La única "inteligencia" que asiste es el
> **scent bibliométrico** (Hito R4), que no es IA.

---
