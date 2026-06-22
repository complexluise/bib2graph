# 0036 — Identidad de fuente agnóstica: DOI como ancla universal, `source_id` genérico, motor de extracción intercambiable

- **Estado:** Aceptada
- **Fecha:** 2026-06-22
- **Decidido por el PO (2026-06-22):** el núcleo **no** debe acoplarse a `openalex_id`; OpenAlex es
  **un** motor de extracción (hoy, para probar), no **el** identificador del corpus.
- **Encuadre:** sesión con el PO (2026-06-22) + uso real reportado en el **informe técnico de la
  sesión de QA** (artefacto local de la sesión, **no versionado** en el repo; corpus de 540 papers,
  `with_doi: 490` → **50 sin DOI**; el dolor se concentró en el acoplamiento a `openalex_id`) + issue
  [#110](https://github.com/complexluise/bib2graph/issues/110) (flujo BibTeX end-to-end).
- **Enmienda explícita a:** [0007](0007-openalex-backbone.md) (OpenAlex como **backbone**: este ADR
  lo redefine como **un motor intercambiable**, no como la identidad del núcleo) y
  [0013](0013-identidad-hash-merge-corpus.md) (invierte la precedencia D1; toca D2 `corpus_hash` por
  cambio del `id` canónico).
- **Refuerza:** [0018](0018-source-agnostico-calidad.md) (contrato `Source` agnóstico: el núcleo deja
  de asumir la forma de OpenAlex también en la **identidad**, no solo en el enriquecimiento).
- **Relacionada con:** [0035](0035-ingesta-multipuerta-resolucion-doi.md) (resolución DOI→ID como
  servicio; este ADR baja la **dependencia** de que esa resolución ocurra para que el corpus exista),
  [0034](0034-etiquetado-tabla-tags-lateral.md) (precedente de **tabla lateral 1↔N** para la opción C
  de schema), [0015](0015-corpus-tabular-backend.md) (D1/D2 son contrato del `TabularBackend`).

## Contexto

La identidad canónica de un paper (D1, ADR 0013) tiene hoy la precedencia
**`openalex_id > doi > título+año`** — `src/bib2graph/corpus.py:67` (`_compute_id`, docstring y rama
en `corpus.py:86-88`). El `id` canónico de la **mayoría** de los papers es, en la práctica, un hash
del `openalex_id`. Eso convirtió a OpenAlex —que el ADR 0007 eligió como **backbone de datos**— en el
**ancla de identidad del núcleo**, no solo en la fuente del enriquecimiento.

El acoplamiento es profundo y transversal, no un detalle de una fuente. Hay **~75 referencias a
`openalex_id`/`OPENALEX_ID` en 14 módulos** del paquete (grep sobre `src/bib2graph/`), con peso en el
núcleo y no solo en el adaptador de OpenAlex:

- `src/bib2graph/corpus.py` (10) — `_compute_id` (identidad).
- `src/bib2graph/schemas.py` (2) — columna `Col.OPENALEX_ID` en `CORPUS_SCHEMA` (`schemas.py:142`).
- `src/bib2graph/sources/openalex.py` (15), `src/bib2graph/enrichers/openalex.py` (5) — esperable: es
  el adaptador del motor.
- `src/bib2graph/foraging/scent.py` (11), `src/bib2graph/foraging/forager.py` (8) — **forrajeo**, que
  debería ser source-agnóstico, cruza por `openalex_id`.
- `src/bib2graph/cli/commands/curate.py` (12) — **CLI** acoplada al nombre del motor.
- `src/bib2graph/networks/clusters.py` (4), `src/bib2graph/service/reads.py` (2),
  `src/bib2graph/backends/duckdb.py` (2), `src/bib2graph/constants.py` (1),
  `src/bib2graph/cli/commands/monitor.py` (1), `src/bib2graph/sources/bibtex.py` (1).

El contrato lo refleja: `docs/API.md` documenta `openalex_id` como columna del schema
(`API.md:804-805`: "`openalex_id` … fuente primaria (ADR 0007)") y como **primer término de la
precedencia de identidad** (`API.md:865`). Es decir, el acoplamiento es **contrato vivo**, no solo
implementación.

El uso real lo volvió un cuello de botella. El informe técnico del tercero
(`informe_tecnico_bib2graph.md`) muestra que el flujo BibTeX se rompe porque, sin `openalex_id`
poblado, el corpus de archivo queda inerte (`§4.2`, `§5.4`), y que **490/540 papers tenían DOI** pero
la identidad se anclaba igual al motor. La decisión del PO (2026-06-22) cierra el principio de fondo:

> El **DOI es el identificador universal/ancla cuando existe**. `source_id` (el ID que devuelve el
> motor de extracción que se haya usado) es el **fallback** cuando no hay DOI. OpenAlex es **un**
> motor —hoy para probar— y deben poder enchufarse otros (**Semantic Scholar** y más). El núcleo no
> conoce el nombre del motor: el motor ya se registra en `provenance.source`
> (`src/bib2graph/schemas.py:55`, `ProvenanceEvent.source`, p. ej. `'openalex'`, `'bibtex'`).

Esto es **complementario** a ADR 0035: 0035 resuelve DOI→OpenAlex ID como servicio para **encender el
enriquecimiento**; este ADR quita la dependencia de que esa resolución ocurra para que el paper
**exista con identidad estable** (si tiene DOI, su `id` ya es `doi:…` sin pegarle a ningún motor).

## Decisión

**La identidad del núcleo es agnóstica al motor de extracción: el DOI es el ancla universal; el
`source_id` es un identificador de fuente genérico de fallback; el motor que lo produjo vive en la
procedencia, no en la identidad ni en el nombre de las columnas/funciones del núcleo.**

### D1' — Invertir la precedencia de identidad (enmienda a D1 de ADR 0013)

`_compute_id` pasa de `openalex_id > doi > título+año` a:

1. `doi` presente → `prefix = "doi"`, `valor = doi` normalizado (minúsculas, sin prefijo
   `https://doi.org/` / `http://doi.org/` — la normalización actual de `corpus.py:90-92`).
2. si no, `source_id` presente → `prefix = "src"` (o el prefijo que el PO confirme), `valor = source_id`.
3. si no → `prefix = "tt"`, `valor = f"{title.lower().strip()}|{year}"`.

El DOI es el identificador **interoperable entre motores** (un paper con DOI tiene el mismo `id`
venga de OpenAlex, de Semantic Scholar o de un `.bib`), lo que es exactamente lo que el núcleo necesita
para deduplicar cross-motor. El `source_id` deja de ser el ancla y pasa a ser el último recurso **antes**
de `título+año` (que sigue siendo frágil, como ya advierte ADR 0013 §Consecuencias).

> *Recomendación al `coder`:* tocar **solo** `src/bib2graph/corpus.py:67` (la función `_compute_id`,
> firma y ramas) cambia la identidad de todo el sistema; el resto del desacople (D-desacople) es
> renombrado/abstracción que no debe cambiar la semántica de identidad otra vez.

### D-desacople — el núcleo deja de nombrar a `openalex_id`

Los módulos de núcleo y de proceso (`corpus`, `schemas`/`constants`, `foraging/scent`,
`foraging/forager`, `networks/clusters`, `service/reads`, `cli/commands/curate` y `monitor`,
`backends/duckdb`) dejan de referirse a `openalex_id` y pasan a una **identidad de fuente abstracta**
(`source_id` + motor leído de `provenance.source`). El **adaptador** del motor
(`sources/openalex.py`, `enrichers/openalex.py`) sí conoce el formato concreto de OpenAlex y lo mapea
a `source_id` en el límite. Así, agregar un motor (Semantic Scholar) es **una `Source`/`Enricher`
nuevos** sin tocar el núcleo (criterio del PRD §10, reforzando ADR 0018).

### D-schema — generalizar el ID de fuente vía tabla lateral `external_ids` (opción C, decidida)

La columna `Col.OPENALEX_ID` de `CORPUS_SCHEMA` (`schemas.py:142`) deja de nombrar al motor. **El PO
decidió (2026-06-22) la opción (C): una tabla lateral `external_ids(paper_id, engine, id)` 1↔N.** Un
paper puede registrar los IDs que le asignaron **varios** motores a la vez (OpenAlex, Semantic Scholar,
…), unificados por el DOI como ancla (D1'); esto es lo que habilita **cruzar/deduplicar entre motores**
sin perder ningún ID. Tiene precedente directo en ADR 0034 (tabla lateral 1↔N para `tags`). El costo
asumido es un **join** para leer los IDs de motor. Las formas (A) columnas por-motor y (B) columna
genérica única quedan como alternativas rechazadas (ver §Alternativas).

### D-CLI — selector de motor

La CLI gana un selector de motor de extracción (`--source <engine>`, p. ej. `--source openalex`,
`--source semanticscholar`) en los comandos que pegan a un motor (ingesta/enrich/chain). Hoy el motor
está implícito en el código; explicitarlo es lo que hace al motor **intercambiable** de cara al
usuario. (Coherente con la convención CLI de `docs/API.md`; el nombre exacto del flag se confirma con
el contrato.)

## Consecuencias

- **(− costo único, acotado) Migración de los workspaces de ejemplo ya commiteados.** Invertir la
  precedencia (D1') **cambia el `id` canónico** de todos los papers que tienen DOI **y** `openalex_id`
  (la mayoría): hoy su `id` es `oa:…`, pasará a `doi:…`. Eso cambia el `corpus_hash` (D2, ADR 0013) y
  por lo tanto **toca el contrato D1/D2** y el gate de reproducibilidad R2 (ADR 0017). Afecta a
  `examples/valoraciones/` (corpus congelado commiteado, ADR 0030); el workspace
  `pensamiento-complejo-grafo` de la sesión **no se versiona**, así que queda fuera de la migración.
  **Es una migración real, única y acotada**: regenerar/relabelar el `id` y refrescar el
  hash esperado de los ejemplos. *Recomendación: tratarla como paso explícito del hito, con el corpus
  de ejemplo re-snapshoteado y el test de reproducibilidad actualizado en el mismo PR.*
- **(=) `source_id` NO se elimina.** Queda como fallback de identidad para works **sin DOI** y como
  llave para encender el enriquecimiento (ADR 0035). En el corpus de ejemplo, **50/540 sin DOI**; los
  citantes traídos por chaining a menudo **tampoco** traen DOI. Sin `source_id`, esos papers caerían a
  `título+año` (frágil) — por eso se conserva.
- **(+) `enrich` / `chain` / `foraging` se vuelven source-agnósticos.** Dejan de asumir `openalex_id`;
  operan sobre identidad abstracta. Esto es lo que destraba enchufar Semantic Scholar y otros motores
  sin re-arquitectura, y lo que permite cerrar el flujo BibTeX end-to-end (#110): un `.bib` con DOIs
  ya tiene identidad estable sin depender del motor.
- **(+) Enmienda explícita a 0007.** OpenAlex deja de ser "el backbone que ancla la identidad" y pasa
  a ser **un motor de extracción intercambiable** (hoy el de prueba). Sigue siendo un motor de primera
  para el **enriquecimiento** (refs/citantes); lo que cambia es que el **núcleo** ya no lo presupone en
  su identidad. 0007 queda como historia con esta enmienda referenciada.
- **(+) Refuerza 0018.** El contrato `Source` agnóstico se extiende de "qué campos entrega cada
  fuente" a "**el núcleo no se llama por la fuente**": la identidad y los nombres del núcleo dejan de
  asumir OpenAlex.
- **(− contrato) `docs/API.md` cambia.** Hay que actualizar la columna del schema (`API.md:804-805`),
  la precedencia de identidad (`API.md:865`), y la convención CLI (selector `--source`). Por regla del
  repo (CLAUDE.md / 0007), no se publica un motor en la CLI hasta que su `Source`/`Enricher` exista.
- **(− superficie CLI) Selector de motor nuevo.** Acotado: hoy el motor es único (OpenAlex), así que el
  default mantiene el comportamiento actual.

## Alternativas

### Sobre la identidad

- **Mantener el acoplamiento a `openalex_id` (statu quo).** Rechazada: ata el núcleo, la identidad y el
  contrato a un único proveedor (contra el principio del PRD §10 y ADR 0018), bloquea motores
  alternativos (Semantic Scholar) y deja inerte el flujo BibTeX cuando no hay resolución a OpenAlex
  (el dolor documentado en el informe técnico, `§4.2`/`§5.4`). El costo de no decidir lo paga cada
  usuario de archivo, repetidamente; el costo de migrar los ejemplos se paga **una vez**.

### Sobre el modelado del ID de fuente (sub-decisión D-schema — DECIDIDA: (C), 2026-06-22)

- **(A) Columnas por-motor** (`openalex_id`, `semanticscholar_id`, …). Explícito y sin join, pero el
  schema **crece con cada motor**: cada motor nuevo es una migración de schema. Reintroduce, multiplicado,
  el acoplamiento que este ADR busca remover.
- **(B) Una columna genérica `source_id` + el motor en `provenance.source`.** Liviana, sin join, reusa
  el campo que ya existe (`ProvenanceEvent.source`, `schemas.py:55`). Limitación: **un paper guarda el
  ID de un motor por vez** — si llega de dos motores, hay que elegir cuál persiste el `source_id` (o
  re-resolver), y no quedan ambos IDs disponibles para cruzar.
- **(C) Tabla lateral `external_ids(paper_id, engine, id)` 1↔N.** Un paper puede tener IDs de **varios**
  motores a la vez (clave para **cruzar/deduplicar entre motores**: el mismo paper resuelto por OpenAlex
  y por Semantic Scholar queda unificado por DOI y con ambos IDs registrados). Costo: un **join** para
  leer IDs de motor y una tabla más que mantener. Tiene **precedente directo** en el repo: ADR 0034 ya
  eligió una **tabla lateral 1↔N** para etiquetas (`tags`), por la misma razón (no inflar el schema
  canónico con cardinalidad variable).

> **Recomendación del arquitecto (no es la decisión; la toma el PO):** **(C), tabla lateral
> `external_ids`**, alineada con la dirección de este ADR (motores intercambiables y deduplicación
> **cross-motor**) y con el precedente de ADR 0034. El DOI sigue siendo el ancla de identidad (D1');
> `external_ids` registra, sin perder ninguno, los IDs que cada motor asignó al mismo paper, que es
> justamente lo que habilita cruzar OpenAlex ↔ Semantic Scholar.
> **Si se busca el menor costo de implementación a corto plazo**, **(B)** es el camino mínimo
> (renombrar la columna a `source_id`, sin tabla nueva ni join), a costa de no poder guardar dos IDs de
> motor a la vez — aceptable **solo si** el cruce cross-motor no es objetivo del primer hito. **(A) se
> desaconseja**: reintroduce el acoplamiento que el ADR remueve.
