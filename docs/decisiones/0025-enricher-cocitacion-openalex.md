# 0025 — `Enricher` opt-in sobre OpenAlex (núcleo): refs→DOI + co-citación

- **Estado:** Aceptada · **AS-BUILT COMPLETO (2026-06-16)** (Ciclos **8a + 8b** implementados →
  Hito 8 completo)
- **Fecha:** 2026-06-16
- **Relacionada con:** [0007](0007-openalex-backbone.md) (OpenAlex backbone; el Enricher deja de ser
  estructural y S2 se demota), [0004](0004-enriquecimiento-opcional.md) (principio de enriquecimiento
  opt-in, nunca obligatorio, keys inyectadas), [0014](0014-proyeccion-redes-pesos-asortatividad.md)
  (semántica del `CoCitationProjector`), [0021](0021-cli-agente-native-contrato.md) (set de
  subcomandos del CLI), [`metodología.md`](../Notas/metodología.md) (co-citación = citantes compartidos)

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

### Ciclo 8b (HECHO, as-built)

- `OpenAlexEnricher.enrich(corpus)` hace ahora **2 pasadas**: refs→DOI (8a) **+** co-citación (8b).
  La pasada de co-citación toma las **semillas aceptadas** (`is_seed=True AND
  curation_status=accepted`), trae sus citantes y **mergea los `openalex_id` de esos citantes en
  `cited_by_id`** (unión, idempotente). Constructor con `max_citing_per_paper` (tope **por semilla**).
- **(Decisión A del PO, respetada)** el 2º nivel **solo puebla `cited_by_id`**; los citantes **NO**
  se materializan como filas del corpus (no crece el corpus). Crecer el corpus con citantes es
  trabajo del **`Forager` + curación** (chaining forward + accept/reject), no del Enricher.
- **Contrato `OpenAlexSource.fetch_citing_batch(ids, *, max_per_paper) -> dict[seed_id,
  list[citer_id]]`**: **batcheo por OR** (`cites:W1|W2|...`, lotes ≤50), pagina por cursor y
  **atribuye página a página** (cruza `referenced_works` del citante con el set objetivo, por
  short-id), con **presupuesto por semilla**: corta la paginación cuando **todas** las semillas del
  lote alcanzaron `max_per_paper`. `max_citing_per_paper` **acota el fetch por semilla**
  (decisión del PO: el tope acota el *fetch*, no solo la columna), **sin starvation** entre semillas
  del mismo lote, y mata el N+1 diferido de R5. `fetch_citing` singular (Forager) **no cambió**.
- **Frontera de responsabilidades:** el `Source` hace **I/O + atribución + acotamiento** (devuelve
  ya el mapa `seed → citantes` acotado); el `Enricher` **solo une** ese mapa en `cited_by_id`.
- **`Networks.quick` (`facade.py`)** incluye la red de **co-citación** cuando el corpus tiene
  `cited_by_id` poblado (→ **5 redes**) y la **omite graceful** (log) si está vacío (→ **4 redes**).
  El `CoCitationProjector` **no se modificó** (decisión F).
- CLI `b2g enrich` expone **`--max-citing INTEGER`**.

### Co-citación: el `CoCitationProjector` no cambia (decisión F del PO)

El `CoCitationProjector` (ADR [0014](0014-proyeccion-redes-pesos-asortatividad.md)) **no se toca**:
cuenta **`cited_by_id` compartido** = los **citantes compartidos** de la
[`metodología.md`](../Notas/metodología.md). La frase de los docs "citantes con sus citas" se **reconcilia**
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
- (+) **La co-citación es end-to-end** (8b hecho): `b2g enrich` puebla `cited_by_id` desde las
  semillas aceptadas y `Networks.quick` devuelve **5 redes** cuando hay `cited_by_id`; si no se
  corrió `enrich` (columna vacía), omite la co-citación graceful (avisa por log) → **4 redes**.

> **AS-BUILT COMPLETO (2026-06-16):** **8a + 8b implementados** → **Hito 8 completo**. `b2g enrich`
> (refs→DOI + co-citación, flag `--max-citing`), `OpenAlexEnricher` de 2 pasadas,
> `OpenAlexSource.fetch_citing_batch` (batcheo OR ≤50 con presupuesto por semilla),
> `Networks.quick` → 4/5 redes según `cited_by_id`. **13 subcomandos** (`enrich` incluido).
> **365 tests verdes** (mypy/ruff limpios).
