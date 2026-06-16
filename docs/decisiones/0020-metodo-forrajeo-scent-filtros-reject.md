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
