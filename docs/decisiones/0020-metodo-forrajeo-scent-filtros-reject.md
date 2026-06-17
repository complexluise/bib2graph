# 0020 — Método de forrajeo: scent bibliométrico determinista, backward puro / forward red, y filtros que marcan `rejected`

- **Estado:** Aceptada · **enmendada 2026-06-15** (scent pasa de frecuencia de enlace a estructura
  bibliométrica; `explain_candidate` y `[llm]` eliminados — ver "Enmienda" al final)
- **Fecha:** 2026-06-15
- **Decidido por:** mixto — el **scent como frecuencia de enlace** y los **filtros que marcan
  `rejected` (no borran)** son **decisiones del Product Owner humano**; el resto (backward puro
  vs forward red, `keywords_id` pre/post-thesaurus, preview local-only) son decisiones de la IA
  (Claude) validadas por el PO proxy.
- **Relacionada con:** [0008](0008-wedge-forrajeo.md) (wedge = forrajeo asistido por *information
  scent*), [0011](0011-thesaurus-multilingue.md) (thesaurus multilingüe determinista),
  [0013](0013-identidad-hash-merge-corpus.md) (identidad `id` / `provenance` append-only),
  [0018](0018-source-agnostico-calidad.md) (mínimo universal vs enriquecimiento; reporte de
  calidad declarado)
- **Toca:** [0009](0009-biblioteca-viva-duckdb.md) (biblioteca viva; historia C4) — precisa que
  el filtrado PRISMA **no destruye** la biblioteca.

## Contexto

El Hito 5 construye la inserción de IA nº1 del ADR [0008](0008-wedge-forrajeo.md) (forrajeo
asistido) más el `Preprocessor` y los filtros de curación. El ADR 0008 fija el **flujo**
(ecuación → chaining rankeado por *information scent* → curación → redes) pero **no** define qué
es el *information scent* en concreto, ni cómo se computa cada dirección de chaining, ni qué le
pasa a un paper que un filtro excluye. Tres preguntas quedaban abiertas:

1. **¿Qué mide el *information scent*?** Las herramientas de *citation chasing* (ResearchRabbit,
   Inciteful, Connected Papers) usan señales diversas: co-citación, acoplamiento bibliográfico,
   centralidad de red. Cada una tiene un costo y una semántica distinta.
2. **¿Cómo se computa el chaining backward y el forward?** El schema del `Corpus` (API.md §1.1)
   trae `references_id` **inline** desde OpenAlex (las obras citadas), pero `cited_by_id` queda
   **vacío tras el seed** (diferido al chaining, decisión 4.c del Hito 4): los citantes requieren
   una llamada extra a la red.
3. **¿Qué le pasa a un paper excluido por un filtro PRISMA?** La biblioteca viva del ADR
   [0009](0009-biblioteca-viva-duckdb.md) es **stateful y curada en el tiempo**; un filtro que
   *borra* filas contradiría tanto la trazabilidad PRISMA (hay que poder reportar cuántos papers
   se excluyeron en cada paso) como la naturaleza acumulativa de la biblioteca.

## Decisión

### A. Scent = frecuencia de enlace con el corpus (decisión del PO)

El *information scent* de un candidato es la **frecuencia de enlace** de cita con el corpus
existente, en ambas direcciones, **no** acoplamiento bibliográfico, co-citación ni centralidad
de red:

- **Backward**: scent = nº de papers del corpus que listan al candidato en `references_id`.
- **Forward**: scent = nº de papers del corpus a los que el candidato cita (cuántos papers del
  corpus aparecen en las referencias del citante).

Es una **función pura** sobre conteos (`foraging.scent`), sin construir grafo, sin métricas de
red. El ranking es descendente por scent con **desempate por `id` ascendente** (estable ante
cualquier `PYTHONHASHSEED`).

### B. Backward puro (local) vs forward red

- **Backward chaining es puro y local**: los candidatos salen de `references_id`, que ya está en
  el corpus tras el seed. No toca la red. Los candidatos backward se materializan como **stubs
  id-only** (título placeholder `[candidate:{id}]`, `openalex_id` poblado, resto nulo): no
  contaminan las redes y son curables/enriquecibles después.
- **Forward chaining requiere red**: `cited_by_id` está vacío tras el seed, así que traer los
  citantes exige `Source.fetch_citing(openalex_id)` (`GET works?filter=cites:`). El `Forager`
  **exige ese método al `source`** y falla ruidoso si no lo tiene; **no se amplió el Protocol
  `Source`** (ADR [0018](0018-source-agnostico-calidad.md)) — `fetch_citing` es capacidad de
  `OpenAlexSource`, no contrato universal.
- **El `preview` opera sin red** (control de crecimiento del ADR 0008): backward se estima
  **exacto** localmente; forward **no es estimable sin fetch**, así que el preview reporta
  `forward_requires_fetch=True` y `by_direction["forward"]=0` — el conteo real solo llega con
  `chain(direction="forward"/"both")`.

`depth=1` es lo único implementado; `depth>1` lanza `NotImplementedError` (futuro v0.3+).

### C. Filtros PRISMA marcan `rejected`, NO borran (decisión del PO)

Los filtros de inclusión/exclusión (año / tipo / idioma / mínimo de citas) son **funciones
puras** que **marcan los papers excluidos con `curation_status='rejected'`** vía `corpus.reject(...)`
(con `provenance` del filtro como `decided_by`), **nunca borran filas**. Cada filtro registra el
conteo PRISMA (`count_before`/`count_after`, contando los papers **no-rejected**) en un
`FilterStep`, y `apply_filters` **sella `Manifest.filters`** (reemplaza: una corrida = una
secuencia de filtros).

Esto **toca el ADR [0009](0009-biblioteca-viva-duckdb.md)** (biblioteca viva, historia C4): un
paper rechazado sigue en la biblioteca, auditable, y puede re-aceptarse — el filtrado es una
**decisión de curación registrada**, no una pérdida de datos. Es coherente con el `provenance`
append-only (ADR [0013](0013-identidad-hash-merge-corpus.md), D4).

### D. `keywords_id` se sobrescribe desde `keywords_raw` (precisión del schema)

`Preprocessor.apply_thesaurus` lee `keywords_raw` y **sobrescribe** `keywords_id` con los
conceptos canónicos del thesaurus (en/es/pt; idempotente; ADR
[0011](0011-thesaurus-multilingue.md)). Esto precisa la nota del schema (API.md §1.1) que ya
decía que `keywords_id` son los "canónicos (post-thesaurus)": antes de aplicar el thesaurus,
`keywords_id` no es autoritativa; el thesaurus es lo que la puebla. `normalize` es **conservador**
(lowercase/trim/acentos en `authors_id`, `language` a ISO 639-1 primario); **sin fuzzy** (eso es
`[dedup]`, Hito 7) y **sin columna de periodización**.

## Consecuencias

- **Costo cero / determinismo total** en el scent: la frecuencia de enlace es un conteo puro,
  reproducible y barato (no construye grafo ni corre algoritmos de centralidad). El **trade-off**
  es que ignora estructura más rica (un candidato muy central pero poco co-citado con el corpus
  rankea bajo); se aceptó a favor de la simplicidad y la consciencia (el investigador entiende
  por qué un candidato sube: "lo citan N papers de mi corpus").
- **Backward es gratis y reproducible** (sin red, estimable en `preview`); **forward cuesta una
  llamada por paper** y solo se cuantifica al ejecutarlo. El `preview` honesto
  (`forward_requires_fetch`) evita prometer una estimación que no se puede dar sin red.
- **`fetch_citing` queda como capacidad de `OpenAlexSource`**, no del Protocol `Source`: una
  fuente que solo da el mínimo universal (ADR 0018) **no habilita forward chaining**, y el
  `Forager` lo dice claro en vez de fallar oscuro. Trade-off: el forward chaining no es
  source-agnóstico.
- **La biblioteca nunca pierde un paper por filtrar**: trazabilidad PRISMA completa y curación
  reversible (coherente con ADR 0009/0013). **Costo**: las vistas y conteos deben distinguir
  `rejected` de ausente; el `corpus_hash` incluye los rechazados (son contenido, no ruido).
- **`Manifest.filters` reemplaza, no acumula**: una corrida de `apply_filters` describe **la
  secuencia PRISMA de esa corrida**. Re-filtrar sella una secuencia nueva. (Gap conocido: si se
  quisiera un historial de todas las corridas de filtro, hoy no se guarda — el `provenance` por
  paper sí registra cada rechazo.)
- **`keywords_id` pre-thesaurus no es autoritativa**: los proyectores de co-ocurrencia de
  keywords (API.md §7) deben correr **después** de `apply_thesaurus` para leer canónicos; antes,
  `keywords_id` puede estar vacía o cruda.
- **`explain_candidate` (B4) queda como stub gateado en `[llm]`**: la firma existe y el error es
  accionable, pero la integración LLM es v0.2. El forrajeo y el ranking funcionan sin él.
  *(Superado por la enmienda de abajo: `explain_candidate` y `[llm]` se eliminan.)*

## Enmienda — 2026-06-15 (scent bibliométrico determinista; sin LLM)

> Motivada por el red-team del AS-BUILT v0.2
> ([Nota 06](../Notas/06-critica-as-built-v0.2.md), RAÍZ 1) y la decisión del PO de que **el producto
> no usa IA generativa** (ADR [0022](0022-producto-sin-ia-generativa.md)). El cuerpo del ADR (arriba)
> queda como historia; esta enmienda revierte la decisión **A** (scent = frecuencia de enlace) y
> elimina el stub LLM.

1. **El scent pasa de "frecuencia de enlace" a estructura bibliométrica.** El *information scent*
   usa los **PROYECTORES** —**acoplamiento / co-citación / centralidad** del candidato respecto del
   corpus curado— en vez del conteo aritmético de citas directas. Es lo que la
   [Nota 05](../Notas/05-ciclo-investigacion-humano.md) §4 siempre prometió ("la bibliometría ES el
   information scent… mapea a los proyectores"). Sigue siendo una **función pura y determinista**
   (mismo corpus → mismo ranking, mismo desempate por `id`), **sin LLM ni embeddings**. El forrajeo
   (costura) **depende del núcleo de proyección** (puro); el núcleo nunca de la costura.
2. **Se elimina `explain_candidate`, el módulo `foraging/explain.py` y el extra `[llm]`** (ADR 0022).
   El "porqué" de un candidato lo da la **estructura visible** (con qué del corpus se acopla/co-cita),
   no un modelo generativo. La historia B4 del PRD se reescribe a "explicación **estructural**, no de
   IA".
3. **Lo que NO cambia:** backward puro / forward red (decisión B), filtros que marcan `rejected`
   (decisión C), `apply_thesaurus` sobrescribe `keywords_id` (decisión D), `depth=1`, desempate por
   `id`. El **trade-off de sesgo de selección aguas arriba** del propio scent (efecto Mateo) se
   reconoce explícitamente: el scent prioriza, no garantiza exhaustividad — eso lo sostienen los
   filtros PRISMA.

**Recomendación para el `coder`:** ver ROADMAP **Hito R4** (`foraging/scent.py` consume proyectores;
borrar `foraging/explain.py`; quitar `[llm]` de `pyproject.toml`).

## AS-BUILT — 2026-06-16 (Hito R4: scent-vía-proyectores construido y verificado; resolución de método del arquitecto)

> El AS-BUILT de R4 reescribió `foraging/scent.py` para consumir el primitivo público
> `collect_item_to_papers` de `networks/projectors.py` (el forrajeo depende del núcleo de proyección,
> nunca al revés), y eliminó `foraging/explain.py`/`explain_candidate` y el extra `[llm]` (ADR 0022).
> 291 tests verdes, mypy strict / ruff limpios. El **arquitecto (2026-06-16)** resolvió tres
> cuestiones de **método bibliométrico** que el verifier dejó abiertas; las fórmulas as-built son:

### Backward = **fuerza de co-citación con el corpus** (ratificado)

    backward_score(X) = |{Pi ∈ corpus : X ∈ Pi.references_id}|

Numéricamente coincide con el viejo conteo, pero su **semántica es estructural**, no aritmética: un
candidato referenciado por `N` corpus-papers está **co-citado `N` veces dentro del corpus** (es la
columna de `X` en la matriz de co-citación que el `CoCitationProjector` proyecta, restringida al
corpus). Cumple el DoD ("no por conteo plano"): mide una propiedad de red (co-citación), se computa
vía el primitivo de los proyectores y es la señal de olfato correcta para el backward chaining —
**cuán compartido es `X` como antecedente del corpus curado**. Se renombra el concepto en
docstrings/docs de "frecuencia de enlace" a **"fuerza de co-citación con el corpus"**.

### Forward = **fuerza de citación directa al corpus** (señal primaria) + acoplamiento (secundaria)

El forward chaining busca **citantes** del corpus (`fetch_citing`). La señal de olfato natural y
robusta para esa dirección es **cuán embebido está el citante en mi corpus = a cuántos corpus-papers
cita directamente**:

    forward_score(Y) = |{Pi ∈ corpus : Pi ∈ Y.references_id}|      (señal primaria)

Esto es **siempre > 0 para un citante real** (por construcción `Y` cita al menos un corpus-paper, que
es lo que lo hizo aparecer en `fetch_citing`), y rankea por fuerza de citación directa, que es la
métrica correcta para "snowballing forward" (Wohlin). El **acoplamiento bibliográfico** (refs
compartidas `Y ↔ corpus`) queda como **señal secundaria/desempate**, no como medida primaria.

> **Estado del AS-BUILT vs esta resolución (IMPLEMENTADO en R4):** el primer código entregado por R4
> implementó el forward como **acoplamiento puro** (`|{Pi : Pi.references_id ∩ Y.references_id ≠ ∅}|`),
> que **degeneraba a 0** cuando el corpus tiene `references_id` ralas (estado común tras `seed`) y, peor,
> **descartaba el citante directo como candidato** si su acoplamiento era 0. El arquitecto resolvió
> **revertir el forward a citación directa** como medida primaria; el fix (ver "Recomendación de código"
> abajo) **se implementó dentro de R4**: `compute_forward_scent` calcula
> `forward_score(Y) = |{ref ∈ Y.references_id : ref ∈ corpus_ids}|` (citación directa) y **emite siempre
> que `direct > 0`**. 293 tests verdes, mypy/ruff OK. El forward ya **no** está incompleto para corpus
> de referencias ralas; R4 queda **cerrado del todo**.

### Centralidad = **diferida** (mejora futura)

El DoD listaba "acoplamiento / co-citación / centralidad" con un **"y/o"**: pedía señal estructural de
red, no las tres a la vez. Con **backward = co-citación** y **forward = citación-directa (+ acoplamiento
secundario)** el espíritu del DoD se cumple (el scent es estructura bibliométrica, no conteo plano). La
**centralidad de red** del candidato (p. ej. su grado/intermediación en la proyección del corpus) queda
como **mejora futura** (un hito de viz/redes): requiere construir el grafo completo por candidato,
un costo que excede el olfato barato y determinista que R4 entrega. Se reconcilia el DoD honestamente:
centralidad no es requisito de cierre de R4.

### Lo que NO cambia

Backward puro / forward red (decisión B), filtros `rejected` (C), `apply_thesaurus` (D), `depth=1`,
desempate por `id`. El sesgo de selección (efecto Mateo) sigue reconocido: el scent **prioriza**; la
exhaustividad la sostienen los filtros PRISMA.

### Recomendación de código (forward — **IMPLEMENTADA en R4**)

**Archivo/símbolo:** `src/bib2graph/foraging/scent.py:compute_forward_scent`.

**Estado:** ✅ **implementado dentro de R4** (2026-06-16). `compute_forward_scent` calcula
`forward_score(Y) = |{ref ∈ Y.references_id : ref ∈ corpus_ids}|` y emite siempre que `direct > 0`.
293 tests verdes, mypy strict / ruff limpios. La descripción del fix queda como rastro de la decisión.

**Problema (as-built inicial):** la primera fórmula medía acoplamiento puro `Y ↔ corpus` y solo emitía
candidatos con acoplamiento > 0 (`if coupled_corpus_papers:`), descartando citantes directos legítimos y
degenerando a 0 con corpus de referencias ralas.

**Fix aplicado — la señal primaria es citación directa al corpus:**

1. Construir `corpus_ids_present = {Col.ID y Col.OPENALEX_ID de cada corpus-paper}` (ya se construye
   para excluir duplicados; reusarlo).
2. Para cada citante `Y` en `citing_rows` (no presente en el corpus):
   `direct = |{ref ∈ Y.references_id : ref ∈ corpus_ids_present}|`
   (cuántos corpus-papers cita `Y` directamente). **Esta es la medida primaria del score.**
3. Emitir **siempre** el candidato cuando `direct > 0` (lo será para todo citante real traído por
   `fetch_citing`). No descartar por acoplamiento nulo.
4. *(Opcional, secundario)* mantener el acoplamiento como término de desempate fino: p. ej.
   `score = direct + ε · coupling` con `ε < 1` (o devolver ambos y desempatar en `rank_candidates`).
   Si se prefiere simplicidad, basta con `score = direct` (acoplamiento queda como mejora futura junto
   a centralidad).

**Corolario en `forager.py`:** `_fetch_forward` (`:323-327`) indexa `candidate_rows` solo para ids con
score > 0; con el fix, todo citante directo tendrá score > 0 y entrará al ranking — el citante real deja
de perderse. No requiere cambio adicional si el score primario es `direct`.

**Test sugerido (TDD):** corpus con `references_id` que **no** se solapan entre sí, y un citante `Y` que
cita a 2 corpus-papers pero **no comparte ninguna referencia** con ellos → con la fórmula as-built
`score(Y)=0` (se pierde); con el fix `score(Y)=2` (rankea por citación directa). Regresión que ancla la
semántica.

> **Decidido por:** **steering arquitectónico (2026-06-16)** — backward=co-citación ratificado,
> forward=citación-directa (revierte el acoplamiento puro del AS-BUILT), centralidad diferida.
> Reconciliado con el DoD del ROADMAP Hito R4.

## AS-BUILT — 2026-06-16 (#21: forward chaining batcheado + cap por semilla, scope `is_seed`)

> El cuerpo del ADR (decisión **B**) describía el forward chaining sobre `Source.fetch_citing(openalex_id)`
> **singular** —una request por paper (N+1)— y no fijaba un tope de citantes por semilla ni el scope
> exacto sobre el que opera. Esta nota anexa el AS-BUILT verificado (gate verde, 422 tests); **no
> reescribe** el cuerpo histórico.

1. **Forward ya no hace N+1: reusa `OpenAlexSource.fetch_citing_batch`.** El
   `Forager.chain(direction="forward"/"both")` agrupa los `cites:` en queries `cites:W1|W2|...` (lotes
   ≤50) con **presupuesto por semilla** (sin starvation) + retry/backoff, en vez de una request por
   fila. Es el mismo primitivo que el Enricher usa en 8b (ADR
   [0025](0025-enricher-cocitacion-openalex.md)); el batching-por-OR diferido en R5 queda así también
   cubierto para el Forager. `fetch_citing` singular sigue existiendo, pero el forward lo consume vía
   la variante batcheada.
2. **Cap por semilla `max_citing_per_paper` (default 50).** Nuevo parámetro de `Forager.__init__`,
   expuesto en el CLI como **`--max-citing`** en `b2g chain`. Acota el *fetch* (no solo la columna)
   por semilla.
3. **Scope = `is_seed=True` (todas las semillas sembradas, SIN filtrar `curation_status`).** El
   chaining corre **antes** de la curación (ciclo `SEEDED→FORAGED→…`→ curación transversal; las
   semillas nacen `candidate`, Nota 09). **La restricción a semillas `accepted` NO es del Forager —
   es del `Enricher`** (Hito 8b, post-curación): el Forager **expande la frontera** sobre `is_seed`,
   el Enricher **pobla `cited_by_id`** sobre `accepted`. Documentar el Forager forrajeando solo
   `accepted` fue el **drift que causó el bug** que este AS-BUILT cierra.
4. **`preview` del forward sin red** estima el nº de semillas a forrajear (`is_seed`) sin requests,
   manteniendo `forward_requires_fetch=True`. `b2g monitor` usa este mismo forward batcheado.

**Lo que NO cambia:** backward = co-citación con el corpus (puro/local), filtros `rejected` (C),
`apply_thesaurus` (D), `depth=1`, desempate por `id`, y la frontera "solo el Forager toca la red".

> **Decidido por:** AS-BUILT verificado del #21 (2026-06-16, rama `feat/forager-cap-batching`); gate
> verde, 422 tests. Ver `API.md` §5 y §2 (`fetch_citing_batch`).

## AS-BUILT — 2026-06-17 (#54: el backward deja de persistir placeholders; revierte el "no contaminan" de la decisión B)

> El cuerpo del ADR (decisión **B**) afirmaba que los candidatos backward se materializan como
> **stubs id-only** en el corpus (título placeholder `[candidate:{id}]`, resto nulo) y que **"no
> contaminan las redes"**. **Esa afirmación era FALSA** y este AS-BUILT la corrige; **no reescribe**
> el cuerpo histórico (queda como rastro del error). Gate verde, **636 tests**; verifier PASA. Rama
> `fix/backward-chaining-no-placeholders`.

### El "no contaminan" era falso — los stubs SÍ contaminaron

Las sesiones de QA con datos reales lo destaparon ([Nota 09](../Notas/09-sesion-qa-prueba-ecologia-valoraciones.md),
[Nota 12](../Notas/12-continuacion-sesion-valoraciones.md), "el bug de fondo del Forager"): los stubs
`[candidate:W...]` **sí contaminaron**. Llegaron a ser **~la mitad del corpus** (filas-fantasma sin
metadata real) y, peor, **entraron al `corpus_hash`** (eran filas del `corpus`, no ruido externo) —
rompiendo la reproducibilidad y las redes legibles. La promesa de "curables/enriquecibles después"
nunca tuvo un materializador que la sostuviera (la deuda quedó abierta como #71).

### Opción B implementada — observar sin materializar

El backward chaining **ya NO crea filas-fantasma en el corpus**. Los IDs observados (los candidatos
que el ranking backward detecta) se exponen por **`RankedCandidates.observed_refs: list[str]`** (campo
nuevo, en orden de ranking, respetando `max_candidates`) y se persisten en una **tabla append-only
hermana, `referenced_but_not_fetched`** (par de `loop_state_log`, **fuera** de la tabla `corpus`). El
ranking backward sobrevive intacto en `RankedCandidates.ranking`; se eliminó `_build_backward_candidate_row`.

- **Protocol `TabularBackend`** (`backends/base.py`): tres métodos nuevos —
  `add_referenced_refs(ref_ids, *, cycle_round)` (idempotente por existencia de `ref_id`),
  `referenced_refs_count()`, `referenced_refs()`—, implementados por `DuckDBBackend` (DDL + migración
  liviana + copia en snapshot/`_clone`; `observed_at` vía el `now()` del backend) e `InMemoryBackend`.
- **`b2g chain`** persiste los `observed_refs` en la tabla (con `cycle_round`) y suma
  `observed_refs_count` al envelope JSON. **`b2g status`** suma el campo aditivo `referenced_not_fetched`
  (`schema="1"` intacto).

### `corpus_hash` y materialización on-demand

El **`corpus_hash` NO incluye los observados** (viven en la tabla hermana, no en `corpus`): esto
**arregla la contaminación previa del hash** (antes los fantasmas SÍ entraban). El materializador
on-demand —rehidratar un observado a fila real del corpus vía `fetch_works_by_ids` (#55) cuando el
humano lo pida— está **diferido a #71** (NO construido en #54).

### Coherencia con otros ADR

- **NO toca [ADR 0013](0013-identidad-hash-merge-corpus.md):** el schema del `corpus` queda intacto;
  `referenced_but_not_fetched` es una tabla aparte, no una columna nueva.
- **Coherente con [ADR 0017](0017-reproducibilidad-historia-snapshot.md):** los IDs observados son
  **estado** (qué vio el forrajeo), **no contenido bibliográfico** → fuera del `corpus_hash`, igual que
  la procedencia y los timestamps. La identidad sigue siendo solo el contenido curado.

### Seguimiento — el forward tiene el MISMO footgun (#78, NO arreglado en #54)

El verifier confirmó que el **forward chaining arrastra el mismo problema**:
`_build_forward_candidate_row` materializa filas con **título placeholder `[candidate:W...]`** (IDs de
citantes sin metadata completa). #54 **solo arregló el backward**; el forward queda **abierto como
issue #78**. Honestidad de estado: el forward **NO está limpio** — sigue poniendo placeholders de
título en el corpus.

**Lo que NO cambia:** backward = co-citación con el corpus (puro/local), forward = citación directa,
filtros `rejected` (C), `apply_thesaurus` (D), `depth=1`, desempate por `id`, "solo el Forager toca la
red".

> **Decidido por:** AS-BUILT verificado del #54 (2026-06-17, rama `fix/backward-chaining-no-placeholders`);
> gate verde, 636 tests, verifier PASA. Ver `API.md` §5 (`observed_refs`) y §4 (`referenced_but_not_fetched`).

## AS-BUILT — 2026-06-17 (#78: el forward materializa metadata REAL; cierra el footgun de placeholder forward)

> Seguimiento directo del AS-BUILT #54 (que reconoció el footgun forward como abierto). El cuerpo del
> ADR (decisión **B**) describía el forward como dirección que **materializa filas** en el corpus, y
> el AS-BUILT inicial las creaba con **título placeholder `[candidate:W...]`** (IDs de citantes sin
> metadata). **Esa materialización era defectuosa** y este AS-BUILT la corrige; **no reescribe** el
> cuerpo histórico (queda como rastro). Gate verde, **645 tests**; verifier PASA. Rama
> `fix/forward-chaining-materialize`. **No reabre la decisión de método de forrajeo** (backward
> puro/forward red, scent, filtros): solo corrige *cómo* el forward materializa la metadata — por eso
> es enmienda al 0020, su dominio, y no un ADR nuevo.

### El forward también arrastraba el footgun — causa raíz: la metadata se traía y se descartaba

El verifier de #54 confirmó que el forward repetía el problema del backward: `_build_forward_candidate_row`
materializaba filas con título placeholder `[candidate:W...]`. La causa raíz, sin embargo, **no** era
falta de datos: `fetch_citing_batch` **ya pedía `_FIELDS` (metadata completa)** a OpenAlex y luego
**los descartaba**, devolviendo solo el mapeo de atribución `dict[str, list[str]]`. La metadata real
(título/año/autores) **ya viajaba en la misma request de red** y se tiraba.

### Opción A1 implementada — conservar la metadata que ya viaja (cero red extra)

El forward **ya NO persiste placeholders**; materializa **filas reales** (título/año/autores) **sin una
sola request adicional**:

- Se extrajo `_fetch_citing_pages` (privado, comparte paginación/atribución/presupuesto-por-semilla)
  que devuelve `(attribution, works_map)`.
- **`fetch_citing_batch(ids, *, max_per_paper) -> dict[str, list[str]]` queda como thin wrapper con su
  firma y contrato INTACTOS** (descarta `works_map`) → el `OpenAlexEnricher` (8b, §3 de API.md) **no
  se rompe**.
- **Método público nuevo `OpenAlexSource.fetch_citing_batch_with_works(ids, *, max_per_paper) ->
  (attribution, works_map)`**, que el `_fetch_forward` del Forager consume.
- `_work_to_row` ganó params `chaining_hop: int | None = None` y `source_tag: str = "openalex"`
  (defaults backward-compat; los callers viejos —`seed`/`fetch_citing`/`fetch_works_by_ids`— no
  cambian). El forward llama `_work_to_row(work, is_seed=False, chaining_hop=1,
  source_tag="chaining:forward")`.
- `_build_forward_candidate_row` **ELIMINADO**.

**Garantía verificada:** con `OpenAlexSource` real, todo citante atribuido está en `works_map` →
nunca cae al fallback-placeholder (ese fallback solo aplica a sources sintéticos de test).

### La regla común y la asimetría forward/backward (no es incoherencia)

La **regla común** que mata el footgun en ambas direcciones: **el corpus nunca contiene placeholders
`[candidate:W...]`**. Las direcciones la cumplen de forma distinta, y esa asimetría es **deliberada**,
no un descuido:

- **Backward observa sin materializar** (#54): las referencias son **numerosas**, **no se curan
  activamente** y **su metadata no viaja** en la request local del seed (solo IDs en `references_id`).
  Materializarlas inflaría el corpus con miles de filas-fantasma → se registran en la tabla hermana
  `referenced_but_not_fetched` y se rehidratan on-demand (#71).
- **Forward materializa** (#78): los citantes son **pocos** (acotados por `max_citing_per_paper`), **se
  curan** (el humano los acepta/rechaza), y **su metadata ya viene** en la misma request de red de
  `fetch_citing_batch_with_works`. Materializarlos con datos reales es lo correcto y es gratis.

Por eso #71 (materializador on-demand) queda, con #78 en A, **solo para backward**: el forward ya no
necesita rehidratar nada.

**Lo que NO cambia:** backward = co-citación con el corpus (puro/local), forward = citación directa,
filtros `rejected` (C), `apply_thesaurus` (D), `depth=1`, desempate por `id`, "solo el Forager toca la
red", y el contrato de `fetch_citing_batch` (intacto).

> **Decidido por:** AS-BUILT verificado del #78 (2026-06-17, rama `fix/forward-chaining-materialize`);
> gate verde, 645 tests, verifier PASA. Seguimiento de #54/#55. Ver `API.md` §2
> (`fetch_citing_batch_with_works`) y §5 (forward materializa metadata real).
