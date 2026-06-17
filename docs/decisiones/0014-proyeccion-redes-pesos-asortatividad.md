# 0014 — Semántica de proyección de redes: tipo de nodo, peso, scope y asortatividad por proxy

- **Estado:** Aceptada
- **Fecha:** 2026-06-15
- **Decidido por:** IA (Claude Opus 4.8), validado por el Product Owner proxy
  (ver [`registro-ia.md`](registro-ia.md))
- **Relacionada con:** [0006](0006-tabla-canonica-y-networkspec.md) (tabla Arrow +
  `NetworkSpec`), [0007](0007-openalex-backbone.md) (OpenAlex backbone; refs y citantes
  ya en el corpus), [0013](0013-identidad-hash-merge-corpus.md) (identidad estable de papers).
- **Difiere a:** [0007](0007-openalex-backbone.md) §co-citación / Hito 8 (`OpenAlexEnricher`,
  2º nivel de fetch) la co-citación completa y el lookup ROR→país.

## Contexto

El Hito 2 implementa el núcleo de redes (API.md §7–10): los cinco proyectores, el analizador,
los exportadores y la fachada `Networks`. Para que esas funciones puras tuvieran un contrato
sin ambigüedad hubo que fijar cuatro cuestiones de semántica que no estaban resueltas en
API.md y que cambian lo que un consumidor observa del grafo:

1. **Qué es el peso de una arista** y cómo se filtra una red poco densa.
2. **Qué entidad es el nodo** en cada proyección.
3. **Qué arma `Networks.quick`** y por qué la co-citación no entra en el camino de baja fricción.
4. **Cómo se mide la asortatividad** cuando el atributo real (país/región) no está en el corpus
   y hay que usar un proxy. Esta tensión reaparece en el criterio geográfico del informe de
   calidad de co-citación (`min_countries`).

El estudio de semiconductores que originó el método (crítica #2 del sandbox IED) pedía que el
**acoplamiento bibliográfico** —barato, mira hacia adelante, no necesita 2º nivel de fetch—
fuera ciudadano de primera y operara sobre el **corpus completo**, no solo sobre las semillas.
La **co-citación**, en cambio, es la proyección más cara: depende de traer los citantes con sus
propias citas, lo que recién está disponible tras el `OpenAlexEnricher` del Hito 8
(ADR [0007](0007-openalex-backbone.md)).

## Decisión

### D1 — Peso = conteo crudo; filtro `min_weight`

El peso de una arista es el **conteo crudo de ítems compartidos** entre los dos extremos
(papers co-firmados, keywords co-ocurrentes, referencias o citantes compartidos). No se
normaliza (sin Jaccard, sin coseno de Salton) en este hito. El filtrado de redes hiperdensas se
hace con el parámetro `min_weight` (default `1` = sin filtro): se descarta toda arista con
`weight < min_weight`.

### D2 — Tipo de nodo por proyección

| Proyección | Nodo | Columna |
|---|---|---|
| Co-autoría | **entidad** (autor) | `authors_id` |
| Colaboración institucional | **entidad** (institución) | `institutions_id` |
| Co-ocurrencia de keywords | **entidad** (keyword) | `keywords_id` |
| Acoplamiento bibliográfico | **paper** | `id` (sobre `references_id`) |
| Co-citación | **paper** | `id` (sobre `cited_by_id`) |

En co-autoría / instituciones / co-word el nodo es la entidad que co-ocurre; en acoplamiento y
co-citación el nodo es el paper y la arista representa referencias/citantes compartidos.

### D3 — `Networks.quick` no incluye co-citación

`Networks.quick` arma cuatro redes con configuración razonable: **acoplamiento (scope `full`)**,
co-autoría, colaboración institucional y co-ocurrencia de keywords. **No** incluye co-citación,
porque ésta requiere el 2º nivel de fetch del `OpenAlexEnricher` (Hito 8); `quick` lo **avisa por
log** al construir. El `CoCitationProjector` sí existe y es invocable a propósito vía
`Networks.build(corpus, NetworkSpec(kind="cocitation"))`, con scope por defecto `seeds_only`:
proyecta sobre los citantes ya presentes en `cited_by_id`, lo cual es válido para ese subset pero
no es la co-citación completa hasta el enriquecimiento del Hito 8.

### D4 — Asortatividad por atributo configurable, con proxy explícito

`assortativity(g, *, attribute=None, by_degree=True, proxy=None)` mide asortatividad por un
**atributo categórico configurable por el usuario** (no se hardcodea ningún campo como `region`;
crítica #5) y/o por grado. Cuando se pasa `proxy`, el dict de salida incluye una clave
`proxy_disclaimer` que advierte que el atributo es un proxy del campo real, no el campo real
("fácil pero consciente"). El **proxy de país** se deriva de `authors_affiliations` (per-paper) en
el momento de asignar atributos a los nodos, fuera de la función pura.

### Nota — proxy de país en `min_countries` (informe de calidad de co-citación)

El criterio geográfico del `cocitation_quality_report` (`min_countries`) usa, en Hito 2,
`institutions_id` como **proxy** de la diversidad de países: cuenta ids de institución únicos como
aproximación al número de países. El output marca el proxy con un disclaimer. El refinamiento real
(lookup ROR→país) queda para el Hito 8, junto con la co-citación completa.

## Consecuencias

- **El acoplamiento es ciudadano de primera y reproducible sin red:** opera sobre el corpus
  completo desde el Hito 2, sin depender de ningún Enricher (las refs ya vienen de OpenAlex,
  ADR 0007). Cierra la crítica #2.
- **La semántica de cada red es inequívoca:** quien consume un `NetworkArtifact` sabe qué es un
  nodo y qué significa un peso, y puede ralear con `min_weight` sin sorpresas.
- **`quick` es honesto sobre lo que omite:** no promete co-citación que aún no puede sostener
  (lección 5 de v0: no prometer de más); avisa por log y deja el `CoCitationProjector` disponible
  para el uso consciente.
- **La asortatividad y el `min_countries` son honestos sobre el proxy:** el disclaimer evita
  leer un proxy de país como dato duro. El costo es que el lookup ROR→país real queda diferido al
  Hito 8; hasta entonces, estos números son orientativos.
- **Peso crudo, no normalizado:** simple y predecible, pero comparar densidades entre redes de
  distinto tamaño exige cuidado. Migrar a un peso normalizado (Salton/Jaccard) sería aditivo y
  reversible (parámetro extra del proyector), no rompe el contrato actual.

## AS-BUILT — capa `decorate` separada de los proyectores (2026-06-16, #25)

Al implementar el label legible en los nodos (#25; síntoma en la Nota 09 B3: las redes salían con
`id` crudo —`oa:…`, `I185261750`, un ORCID— ilegibles en Gephi/VOSviewer/Cytoscape) se **confirmó
la pureza de los proyectores de D2**: los proyectores (`networks/projectors.py`) **siguen siendo
funciones puras sobre `pa.Table`** y **NO setean ningún atributo de nodo** (devuelven el grafo con
ids crudos, sin `label`).

La legibilidad y los atributos para export/GUI viven en una **capa de frontera separada**,
`bib2graph.networks.decorate` (`decorate_graph`/`decorate`), aplicada en `facade.py:_build_artifact`
—no en los proyectores—. Inyecta en los nodos: `label` (mapeo por `NetworkKind`: paper →
`"título (año)"` truncado a `LABEL_MAX_CHARS`=60; autor/institución → nombre `*_raw` correlativo;
keyword → la keyword), `degree_centrality` (todos) y, para paper, `year`/`is_seed`/`curation_status`;
`community` opcional desde `artifact.communities`. Así `Networks.quick`/`build` devuelven artefactos
**decorados** sin contaminar el núcleo puro de proyección. Contrato en API.md §7.1.

Esta separación es coherente con D2 (el proyector solo decide qué entidad es el nodo) y con la
convención del repo "núcleo puro vs frontera": la proyección no sabe de presentación. (Nota
aditiva; no modifica la decisión original.)
