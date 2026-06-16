# 0025 — `Enricher` opt-in sobre OpenAlex (núcleo): refs→DOI + co-citación

- **Estado:** Aceptada · **AS-BUILT parcial (2026-06-16)** (Ciclo **8a** implementado en esta rama;
  **8b** pendiente)
- **Fecha:** 2026-06-16
- **Relacionada con:** [0007](0007-openalex-backbone.md) (OpenAlex backbone; el Enricher deja de ser
  estructural y S2 se demota), [0004](0004-enriquecimiento-opcional.md) (principio de enriquecimiento
  opt-in, nunca obligatorio, keys inyectadas), [0014](0014-proyeccion-redes-pesos-asortatividad.md)
  (semántica del `CoCitationProjector`), [0021](0021-cli-agente-native-contrato.md) (set de
  subcomandos del CLI), [`metodología.md`](../metodología.md) (co-citación = citantes compartidos)

## Contexto

El Hito 8 ([ROADMAP/04](../ROADMAP/04-lo-que-viene.md)) materializa la costura `Enricher` opt-in
para resolver `references_id`→`references_doi` y habilitar la **co-citación** end-to-end. El DoD
original del hito lo encuadraba sobre el extra **`[s2]`** (Semantic Scholar), residuo del diseño
**pre-giro** previo al [ADR 0007](0007-openalex-backbone.md): cuando la entrada era BibTeX, el único
camino a las listas de referencias era un enricher S2 **estructural**. Tras el ADR 0007, OpenAlex ya
trae referencias y citantes, así que ese encuadre `[s2]` quedó desalineado con la arquitectura real.

El hito es grande para un solo ciclo, por lo que se **parte en dos**:

- **8a** — costura `Enricher` + resolución refs→DOI + subcomando `b2g enrich`.
- **8b** — poblar `cited_by_id` (2º nivel) y co-citación end-to-end, solo sobre semillas aceptadas y
  con un tope configurable.

## Decisión

**El `Enricher` vive en el núcleo, sobre OpenAlex**, no en un extra. Es la costura opt-in del ADR
0004/0007, ahora as-built.

- **Contrato `Enricher`** (`enrichers/base.py`): `Protocol` `@runtime_checkable` con
  `enrich(corpus: Corpus) -> Corpus`. **Idempotente** (re-correr no duplica trabajo ni efectos),
  **config/keys inyectadas** (nunca embebidas), **no pierde papers** ante rate limit/reintentos, sin
  ramas muertas. El núcleo **no importa `duckdb`**; no hay red al importar; **sin red en CI**
  (`MockTransport`).
- **`[s2]` queda superado para el Enricher estructural** (supersede el DoD pre-giro del Hito 8): el
  enricher de referencia es **OpenAlex en el núcleo** (decisión B del PO). El nombre `[s2]` se
  **reserva** para un futuro `SemanticScholarEnricher` de **señal adicional** (no estructural), no
  como camino a co-citación.
- **`enrich` es subcomando CLI propio** (decisión C del PO): `cli/commands/enrich.py`,
  `run_enrich(store_path, *, email, api_key, transport)`. **NO transiciona el `CycleState`** (es
  **ortogonal** al lazo del FSM, ADR 0016/0021). `build` sigue **puro/sin red**.

### Ciclo 8a (HECHO, as-built)

- `OpenAlexEnricher` (`enrichers/openalex.py`) reúne los **`references_id` únicos** del corpus, los
  resuelve a DOI **batcheando por OR** (lotes ≤ 100, filtro `openalex_id:W1|W2|...`,
  `select=id,doi`) y rellena **`references_doi`** alineado por lookup.
- Registra un `EnricherRef(name="openalex_references_doi", params=...)` en el `Manifest`;
  **idempotente** = reemplaza por nombre, no duplica.
- Métodos nuevos en `sources/openalex.py`: `fetch_dois_for(ids) -> dict` y `_fetch_batch_select`.

### Ciclo 8b (PENDIENTE)

- **Poblar `cited_by_id`** (2º nivel) y co-citación end-to-end, **solo sobre semillas aceptadas** y
  con un **tope configurable**.
- **(Decisión A del PO)** el 2º nivel **solo poblará `cited_by_id`**; los citantes **NO** se
  materializan como filas del corpus. Crecer el corpus con citantes es trabajo del **`Forager` +
  curación** (chaining forward + accept/reject), no del Enricher.

### Co-citación: el `CoCitationProjector` no cambia (decisión F del PO)

El `CoCitationProjector` (ADR [0014](0014-proyeccion-redes-pesos-asortatividad.md)) **no se toca**:
cuenta **`cited_by_id` compartido** = los **citantes compartidos** de la
[`metodología.md`](../metodología.md). La frase de los docs "citantes con sus citas" se **reconcilia**
documentando que el 2º nivel se materializa como **`cited_by_id`** (8b): "citantes con sus citas" ≡
**`cited_by_id` compartido**, que es lo que el projector ya consume.

## Consecuencias

- (+) **La co-citación deja de depender de un enricher estructural externo** (ADR 0007 cerrado a
  nivel de código): el camino es OpenAlex en el núcleo, opt-in.
- (+) **`enrich` ortogonal al lazo**: se puede enriquecer en cualquier estado sin perturbar el FSM;
  `build` permanece puro y reproducible.
- (+) **Batching por OR** mata el N+1 de requests del 2º nivel (mejora de performance; el
  retry/backoff de R5 se conserva).
- (−) **El DoD del Hito 8 quedaba encuadrado en `[s2]`**: este ADR lo supersede; el `[s2]` pasa a
  reserva para señal adicional futura. Los docs (ROADMAP/04, ARCHITECTURE §4.2, API §3) se sincronizan.
- (−) **La co-citación completa sigue gateada por 8b**: hasta poblar `cited_by_id` (2º nivel),
  `Networks.quick` omite la co-citación (avisa por log), como ya documenta API §10.

> **AS-BUILT parcial (2026-06-16):** **8a implementado** en esta rama (`b2g enrich`, refs→DOI,
> `OpenAlexEnricher`), **13 subcomandos** (era 12: se suma `enrich`). **341 tests verdes.** **8b
> pendiente** (co-citación end-to-end).
