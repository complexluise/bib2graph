# 0052 — Red tipada en el Arrow del corpus: `network_type` + aristas + comunidades + métricas por nodo

- **Estado:** **Propuesta** (2026-10-11). El PO resolvió las cinco bifurcaciones de fondo en la
  sesión de encuadre (2026-10-11, ver §Resolución del PO). Pendiente: PR a `dev` con la implementación
  + tests + actualización de `docs/API.md`. Milestone **0.15.0**.
- **Fecha:** 2026-10-11
- **Decidido por:** el **PO resolvió las bifurcaciones de fondo** (forma del Arrow, multi-red,
  métrica, modo sin-red, ids de aristas vs ids de citas); el **encuadre** (red como struct anidado en
  la tabla `papers`, aditivo sobre 0050/0051, no toca `corpus_hash`) es síntesis de la IA (architect).
- **Origen:** issue [#316](https://github.com/complexluise/bib2graph/issues/316) (solicitud externa del
  consumidor programático del Arrow — la "capa de red" del MVP del consumidor, ruta crítica). Secuela
  de [0050](0050-contrato-export-corpus-arrow-bibtex-ecuacion.md) (el contrato del export del corpus
  sin la red). Encuadre previo: la red de acoplamiento/co-citación se computaba en `Networks.build`
  pero **se exportaba aparte** como `network.graphml` + `clusters.csv`; el Arrow del corpus (#293/0050
  D4) entregaba solo la tabla `papers` y la metadata de ecuación. Cierra ese hueco: el consumidor
  recibe, en **un solo archivo autoverificable**, el corpus Y la red tipada.

## Contexto

`b2g export --format arrow` ([#293](https://github.com/complexluise/bib2graph/issues/293),
[ADR 0050](0050-contrato-export-corpus-arrow-bibtex-ecuacion.md) D4) entrega hoy un Arrow con la
**tabla de papers** del corpus + la metadata de ecuación (`equation_hash` de #292, objeto ecuación de
#291). **No entrega la red tipada** que el forrajeo produce. La red vive aparte como artefactos de
build (`<workspace>/networks/<kind>/network.graphml` + `clusters.csv`); un consumidor externo del
Arrow **no la recibe en el mismo archivo** y tiene que recomponer el cruce downstream — trabajo
redundante, expuesto a drift y a errores de join.

Un consumidor externo del Arrow (el "consumidor programático" del ADR 0050 §"Constraints") necesita
la **red tipada junto al corpus, en un mismo gesto**, porque:

- El cruce `papers.id ↔ edges.source_id_a / source_id_b` debe ser exacto; si el consumidor recompone
  el grafo en su lado, todo drift entre el grafo de `b2g build` y el Arrow se vuelve silencio
  (papers "huérfanos" en la red, aristas "huérfanas" sin paper).
- Las **comunidades** y la **centralidad intra-comunidad** son atributos del nodo **en su red**;
  exportarlas separadas obliga al consumidor a hacer un join frágil entre archivos heterogéneos.
- La red cambia con el `b2g build` (clústering, resolución, filtro de peso). Exportar la del build
  más reciente con la red del corpus vivo en el mismo Arrow cierra la trazabilidad.

Lo que **ya está en 0.14.0** (no se pide de nuevo, base reusable):
- `Networks.build(corpus, spec)` y `Networks.quick(corpus)` (`networks/facade.py`) producen
  `NetworkArtifact(graph, metrics, communities, assortativity, layout, spec)`.
- `network_metrics` + `detect_communities` (`networks/analyzer.py`) ya corren Leiden/Louvain/
  `label_prop`/`greedy_modularity` con resolución configurable (Hito 9, `NetworkSpec.resolution`).
- `decorate_graph` (`networks/decorate.py`) ya inyecta `label`/`degree_centrality`/atributos de paper
  en el grafo (Hito 0.3, #25).
- `cluster_table` (`networks/clusters.py`, #31) ya resume cada comunidad de una red de paper en una
  fila con `cluster`/`size`/`seed_count`/`candidate_count`/`accepted_count`/`year_min`/
  `year_max`/`year_mean`/`top_authors`/`top_keywords`.
- `export --format arrow` + envelope `schema="1"` ([ADR 0021](0021-cli-agente-native-contrato.md) /
  [0045](0045-cerrar-tres-grietas-agent-native.md)) con la metadata de ecuación embebida
  ([ADR 0050](0050-contrato-export-corpus-arrow-bibtex-ecuacion.md) D3).

## Decisión

Se extiende `b2g export --format arrow` para que el consumidor externo reciba, **en el mismo archivo
Feather/IPC** (autoverificable, una sola familia de archivos), la **red tipada** del `b2g build` más
reciente sobre el corpus scopeado. La extensión es **aditiva** sobre [ADR 0050](0050-contrato-export-corpus-arrow-bibtex-ecuacion.md) D4: el
schema del Arrow gana columnas y metadata; **ningún constraint duro del consumidor programático
(ADR 0050 §"Constraints") se toca**.

### D1 — Forma del Arrow: columnas struct anidadas en la tabla `papers`

Una sola `pa.Table` estándar (Arrow IPC / Feather). El archivo sigue siendo legible por
`pyarrow.feather.read_table` / DuckDB / pandas / polars **sin librerías nuevas**. La red se
materializa como **columnas struct anidadas** en la tabla `papers` (no como multi-tabla: Arrow IPC
estándar no soporta múltiples `RecordBatch` heterogéneos en un solo archivo sin hacks no estándar).

Nuevas columnas en la tabla `papers` (todas **pobladas si y solo si** el corpus tiene red computada;
ausentes —no `null`/no vacías— si el corpus no tiene red, ver D4):

| Columna | Tipo Arrow | Semántica |
|---|---|---|
| `community_id` | `int64` (no-null) | Id de la comunidad del paper en la red. Negativo = outlier/no asignado. |
| `degree_weighted` | `int64` (no-null) | Suma de los pesos de las aristas del paper en la red. |
| `intra_community_pagerank` | `float64` (no-null) | PageRank del paper **restringido al subgrafo de su comunidad**, ponderado por `weight`. Ver D3. |
| `network_edges` | `list<struct<neighbor_id: string, weight: int64>>` (no-null) | Aristas **salientes** del paper: `neighbor_id` = `Col.ID` del vecino (Lección B6 de Nota 09); `weight` = peso de la arista. Lista vacía si el nodo está aislado. |
| `network_communities` | `list<struct<community_id: int64, size: int64, modularity: float64>>` (no-null) | Comunidades presentes en la red, **una sola vez por paper** (idénticas para todos los papers de la misma exportación — es la partición global). Lista de un solo elemento si la partición tiene 1 comunidad. |

**Cruce estable:** el `neighbor_id` de `network_edges` es el `Col.ID` canónico del paper vecino
(`doi:…` cuando hay DOI, `source_id:…` cuando no, `tt:…` cuando tampoco — la misma regla que el resto
del corpus). El consumidor joinea con `papers.id` por igualdad exacta de string. **No** se exportan
aristas con `source_id` crudo: el `source_id` ya está como columna de `papers` (constraint del
consumidor programático, ADR 0050).

**`network_type` en la metadata del schema Arrow** (extiende la metadata de 0050 D3 — aditivo,
convive con `equation_hash`/`equation_expression`/`equation_id`):

| Clave | Valor | Cuándo |
|---|---|---|
| `network_type` | `"bibliographic_coupling"` \| `"cocitation"` \| ausente | Una red por Arrow. Ver D2. |
| `network_type_algo` | `"louvain"` \| `"label_prop"` \| `"greedy_modularity"` | Solo presente si `network_type` está presente. Refleja el `clustering` del `NetworkSpec` del `b2g build` que produjo la red. |
| `network_resolution` | float como string | Solo presente si `network_type` está presente. Refleja la `resolution` del `NetworkSpec`. |
| `network_scope` | `"full"` \| `"seeds_only"` | Solo presente si `network_type` está presente. Refleja el `scope` del `NetworkSpec`. |

La metadata es **inmutable** una vez escrita (como el resto de la metadata del schema Arrow). El
consumidor la lee y, si `network_type` está ausente, sabe que la exportación es **modo degradado**
(D4).

### D2 — Una red configurable por Arrow, default acoplamiento

El `b2g build` produce un conjunto de redes (5 kinds: `bibliographic_coupling`, `cocitation`,
`author_collab`, `institution_collab`, `keyword_cooccurrence`; las que apliquen al corpus). El Arrow
exporta **una sola red** por archivo, seleccionable por el usuario:

- **Default:** `bibliographic_coupling` (la red de acoplamiento es la más robusta en one-shot, la
  primera del `Networks.quick` y la que el caso de uso del consumidor programático declara como
  primaria, #316).
- **Override:** nuevo flag **`--network-type`** en `b2g export --format arrow` con los valores del
  `NetworkKind` StrEnum existente (no se introduce un literal nuevo; reusa la fuente única,
  [ADR 0023](0023-capa-constants-modelos-schema.md)).
- **Kinds no-papers (`author_collab`, `institution_collab`, `keyword_cooccurrence`):** los nodos de
  esas redes **no son papers**; el struct anidado `network_edges`/`network_communities` no aplica
  (no se puede "anclar por paper" en una red de autores). Para esos kinds:
  - El export Arrow **no incluye** la red (columnas de red ausentes, `network_type` ausente en
    metadata). El envelope `--json` lleva `warnings: ["network_type=<kind> not supported in Arrow
    export; use --format graphml for this kind"]`. Honesto, no inventa.
  - **Multi-red en un mismo Arrow queda diferida** a 0.16.0+ si surge la necesidad (la Nota 33
    §"Tramo A/B" ya lo preveía como estabilización con feedback).

El consumidor que quiera las 5 redes llama a `b2g export --format arrow --network-type <kind>` por
cada una, o usa `--format graphml` para la familia completa (`<workspace>/networks/<kind>/`).

### D3 — Métricas: `degree_weighted` + PageRank intra-comunidad

Las dos métricas por nodo en columnas planas (D1) son:

- **`degree_weighted`** — `sum(weight for neighbor in graph.neighbors(node))` por nodo, sobre el
  grafo del `NetworkArtifact`. Entero no-negativo. Barato, determinista, comparable. **Ya** se
  computa en `Networks.build` implícitamente (los pesos viven en el grafo); se proyecta en el Arrow
  como una nueva columna. El `decorate_graph` actual (Hito 0.3, #25) expone `degree_centrality`
  (grado normalizado por `n-1`) para el GraphML; **se conserva** (el GraphML no cambia). La nueva
  columna `degree_weighted` es aditiva, no reemplaza.

- **`intra_community_pagerank`** — `nx.pagerank(graph.subgraph(community_nodes), weight="weight")`
  evaluado en el nodo. PageRank **restringido al subgrafo inducido por la comunidad**, ponderado
  por `weight`. Racional:
  - **Robusto al tamaño**: una comunidad de 5 nodos y una de 500 dan PageRanks comparables (es una
    medida de centralidad relativa dentro del subgrafo).
  - **Interpretable bibliométricamente**: "el paper más central de su grupo" es la pregunta
    bibliométrica estándar para elegir representantes de comunidad (es el uso típico en
    `b2g read top` y similares).
  - **Determinista** (PageRank es determinista para grafo fijo, semilla fija, `weight` fija).
  - **Computable en el grafo del `NetworkArtifact`**: no requiere cambios en `Networks.build`, solo
    una función pura nueva en `networks/` (`intra_community_pagerank(graph, communities) ->
    dict[node, float]`).
  - **Barato**: `|V|` PageRanks pequeños (uno por subgrafo, no uno global), suma total O(|V| + |E|).

**Por qué PageRank intra-comunidad y no `betweenness` o `degree_weighted` solo:** betweenness es
O(|V|·|E|) — prohibitiva en comunidades grandes; degree ponderado es trivialmente la suma de
adyacencias y no captura estructura interna del subgrafo (un nodo conectado a todos los demás con
peso 1 tiene el mismo `degree_weighted` que un nodo conectado a uno solo con peso 99, pero
estructuralmente son muy distintos). PageRank intra-comunidad es el punto medio: robusto, sensible a
la estructura, y barato.

**Alternativa descartada: exportar las 3 métricas (degree_weighted, PageRank, betweenness).** Costo
de存储 y cómputo no se justifica para el MVP; el consumidor que las quiera puede computarlas del
grafo (`network_edges` es suficiente para reconstruir el subgrafo y aplicar `nx.betweenness` si lo
necesita). El struct `network_edges` está completo para eso.

### D4 — Modo degradado honesto: corpus sin red

`b2g export --format arrow` sobre un corpus al que **no se le corrió `b2g build`** (o se corrió pero
falló, o se restauró de un snapshot anterior al build): el Arrow se exporta **igual**, pero las
**columnas de red están ausentes** (no `null`/no vacías — el Arrow no las trae; el schema no las
declara). `network_type` ausente en metadata. El envelope `--json` lleva un warning explícito:

```json
{
  "warnings": [
    "no network computed; run 'b2g build' first to attach a typed network to the export"
  ]
}
```

El exit code es **0** (export exitoso, modo degradado documentado). El consumidor sabe leer la
ausencia de `network_type` en la metadata del schema como "esto es un corpus pelado" y obrar en
consecuencia (no es un error, es una feature).

**Por qué no exportamos structs vacíos con `null`/`[]`:** ocuparía espacio y **mentiría** sobre la
presencia de una red que no existe. La forma del Arrow cambia con y sin red; el consumidor **debe**
validar la presencia/ausencia de las columnas de red (es la disciplina que el constraint
"rompen-en-silencio" del ADR 0050 §"Constraints" ya impone).

### D5 — Envelope `--json` aditivo (sin romper `schema="1"`)

El envelope de `b2g export --format arrow` (que ya es `schema="1"`, aditivo sobre
[ADR 0021](0021-cli-agente-native-contrato.md) / [0045](0045-cerrar-tres-grietas-agent-native.md))
gana **campos aditivos** en `data` (no toca `schema`):

| Campo | Tipo | Cuándo |
|---|---|---|
| `network_type` | string \| null | Refleja la metadata del Arrow. `null` si modo degradado. |
| `network_nodes` | int | Nº de nodos en la red (papers con al menos una arista). `0` si modo degradado. |
| `network_edges` | int | Nº de aristas en la red. `0` si modo degradado. |
| `network_communities` | int | Nº de comunidades detectadas. `0` si modo degradado. |
| `network_modularity` | float \| null | Modularidad de Newman de la partición (`nx.community.modularity`). `null` si modo degradado. |
| `network_type_algo` | string \| null | `"louvain"` \| `"label_prop"` \| `"greedy_modularity"`. `null` si modo degradado. |
| `network_resolution` | float \| null | Resolución del `NetworkSpec`. `null` si modo degradado. |

Estos campos son **informativos** (el consumidor puede sacarlos del Arrow leyendo la metadata y las
columnas, pero tenerlos en el envelope le evita parsear el schema). El bloque `maturity` existente
(ADR 0050 §"D4 maturity stamp") se mantiene intacto.

## Consecuencias

### Lo que se gana

- **El consumidor recibe la red tipada en un solo archivo**, sin recompongo ni join downstream. El
  cierre `papers.id ↔ network_edges[].neighbor_id` es exacto por construcción.
- **La trazabilidad corpus↔red se cierra**: el `network_type`/`network_type_algo`/`network_resolution`
  en la metadata del schema Arrow documentan **bajo qué `NetworkSpec` se computó la red**, no solo
  *qué* red es. Si el usuario cambia el `b2g build` y reexporta, los metadatos cambian; el consumidor
  puede validar coherencia.
- **`PageRank intra-comunidad` da un ranking comparable entre comunidades** — el insumo natural para
  "elegir el paper representativo de cada comunidad" (el caso de uso del consumidor programático del
  #316).
- **El export Arrow queda usable para los 4 `NetworkKind` que existen** (acoplamiento y co-citación
  con red; los demás sin red y con warning — sin error, sin caída).
- **Modo degradado honesto**: el corpus pelado se exporta sin red y con un warning en el envelope;
  el consumidor no tiene que defending parsing de un Arrow que podría no tener la red.

### Lo que cuesta

- **Cambio de contrato público**: el schema del Arrow del export gana columnas y metadata. Es aditivo
  (no toca constraints duros del consumidor programático, ADR 0050 §"Constraints"), pero el
  consumidor que ya ingiere el Arrow **debe tolerar columnas ausentes** (no es breaking para
  consumidores que respetan el contrato, pero hay que verificarlo en el test de constraints). El
  `docs/API.md` se actualiza.
- **Cómputo nuevo en el export**: `intra_community_pagerank` se calcula al exportar. Costo: O(|V|+|E|)
  en total (suma de PageRanks sobre subgrafos disjuntos). Para corpus típicos de bibliometría
  (cientos a miles de papers) es < 1s; para corpus de millones de papers hay que benchmarkear
  (deuda 0.16.0, performance).
- **El export Arrow se acopla al `Networks.build`**: si no hay build previo, no hay red. Esto ya es
  así conceptualmente (las redes viven en `<workspace>/networks/<kind>/`); este ADR lo hace
  explícito en el export. No es una nueva restricción, es documentación de una dependencia existente.
- **Multi-red diferida**: si un usuario quiere las 5 redes en un Arrow, tiene que correr 5 `b2g
  export` (uno por `--network-type`). Es deliberado (D2). El costo se reevalúa con feedback de
  usuarios en el Tramo B (Nota 33).
- **`network_edges` puede ser grande** para papers muy conectados (degree alto). Arrow lo maneja
  nativo (`list<struct>` es eficiente en Feather/IPC), pero el archivo puede pesar más que el corpus
  pelado. Trade-off explícito.

### Lo que no cambia (constraints vivos)

- **`source_id`/`references_id` siguen siendo ids OpenAlex `W…`** (ADR 0050 §"Constraints"). Las
  aristas en `network_edges` **no usan** `source_id` — usan `Col.ID` (DOI-ancla). El `source_id` sigue
  en su columna actual de la tabla `papers` (constraint duro del consumidor programático).
- **`curation_status` ∈ `{candidate, accepted, rejected}`** — sin cambios.
- **`is_seed` no-null** — sin cambios.
- **`corpus_hash` intacto** ([ADR 0013](0013-identidad-hash-merge-corpus.md) D2 /
  [0017](0017-reproducibilidad-historia-snapshot.md) R2): las nuevas columnas y la metadata se
  proyectan desde artefactos de build, no modifican el contenido bibliográfico. El hash del corpus
  sigue siendo de la tabla `papers` original, sin las columnas de red. **El hash del Arrow exportado
  cambia** (más bytes, más metadata) — pero el `corpus_hash` de la biblioteca viva no.
- **Envelope `schema="1"` intacto**: la entrega es aditiva sobre `data`, no sobre `schema` (los
  campos de red son del Arrow, no del envelope del CLI). El bloque `maturity` del envelope se
  mantiene.
- **No se introduce IA** ([ADR 0022](0022-producto-sin-ia-generativa.md)): clustering Leiden/Louvain
  y PageRank son funciones deterministas. Sin fallback generativo.

## Alternativas descartadas

- **Multi-tabla real en Arrow IPC** (varios `RecordBatch` heterogéneos en el mismo archivo con
  sidecar JSON). **Rechazada:** Arrow IPC estándar no lo soporta sin hacks no estándar. El consumidor
  tendría que entender el sidecar y un wrapper de lectura. El struct anidado en una sola tabla es
  Arrow estándar y se lee con `pyarrow`/`duckdb`/`polars` sin código nuevo.
- **Tabla larga con discriminador `kind`** (una sola `pa.Table` con `kind: papers | edges |
  communities`, el consumidor hace `WHERE kind = 'edges'`). **Rechazada:** es el anti-patrón EAV
  aplicado a Arrow; pierde el cruce directo con la tabla `papers`. El struct anidado es más legible
  y más performante.
- **Un Arrow por concern** (`corpus.arrow` + `edges.arrow` + `communities.arrow`, un directorio
  auto-contenido). **Rechazada:** rompe el principio de "un archivo autoverificable" del ADR 0050
  D4. El consumidor tendría que validar **varios** archivos, no uno. Pierde la ventaja del
  `equation_hash` en metadata (que ya está en el único archivo del 0050).
- **Exportar las 3 métricas (degree_weighted, PageRank, betweenness).** **Rechazada:** betweenness es
  O(|V|·|E|) y la métrica no es crítica para el caso de uso del consumidor (que quiere "el paper
  representativo de su comunidad" — PageRank intra-comunidad basta). El consumidor que quiera
  betweenness puede computarla del struct `network_edges` (suficiente para reconstruir el subgrafo).
- **PageRank global** (no restringido a la comunidad). **Rechazada:** PageRank global es dominado
  por papers muy conectados al resto del corpus; no refleja "centralidad **dentro** del grupo". La
  pregunta del consumidor es intra-comunidad, no global.
- **Betweenness intra-comunidad.** **Rechazada** por costo (O(|V|·|E|) por subgrafo, puede ser
  lento en comunidades grandes) y porque el caso de uso del consumidor es "elegir
  representativo", no "encontrar puentes".
- **Multi-red en un mismo Arrow** (un struct `networks: list<struct<network_type, edges,
  communities>>`). **Diferida a 0.16.0+**: el struct puede explotar de tamaño si hay 5 redes con
  miles de aristas cada una. Decidir bajo demanda (Tramo B, Nota 33).
- **Structs vacíos cuando no hay red** (`network_edges=[]`, `network_type=null` en metadata).
  **Rechazada:** ocupa espacio y miente. La ausencia de columnas + warning en el envelope es más
  honesta.
- **Exit code distinto si no hay red.** **Rechazada:** el export **sí** salió bien; el modo degradado
  es una feature, no un error. Exit 0 + warning en `data.warnings` es la disciplina del envelope
  `schema="1"`.
- **Kinds no-papers con tablas/structs anidados distintos** (autores como `list<struct<author_id,
  ...>>`). **Diferida a 0.16.0+**: requiere definir el schema de "red de autores" en el Arrow, que es
  otra conversación. Para el MVP, los kinds no-papers salen sin red y con warning; el consumidor
  que los quiera usa `--format graphml` (que ya tiene el camino).

## Resolución del PO (2026-10-11)

El PO resolvió las cinco bifurcaciones que este ADR había dejado abiertas. Se registran acá; el
cuerpo del ADR ya las folded.

1. **Forma del Arrow = columnas struct anidadas en la tabla `papers`** (D1). El struct es
   `network_edges: list<struct<neighbor_id, weight>>` + `network_communities:
   list<struct<community_id, size, modularity>>` + 3 columnas planas (`community_id`,
   `degree_weighted`, `intra_community_pagerank`). Arrow IPC estándar, sin hacks.

2. **Una red por Arrow, configurable** (D2). Default `bibliographic_coupling`; override con
   `--network-type <kind>`. Kinds no-papers salen sin red y con warning. Multi-red en un mismo Arrow
   diferida a 0.16.0+.

3. **`intra_community_pagerank` ponderado por `weight`** (D3). Función pura nueva
   `intra_community_pagerank(graph, communities) -> dict[node, float]` en `networks/`. PageRank
   restringido al subgrafo de la comunidad. Robusto al tamaño, comparable entre comunidades.

4. **Modo degradado honesto** (D4): sin red → columnas de red **ausentes** (no vacías), `network_type`
   ausente en metadata, warning en `data.warnings`, exit 0. El consumidor lee la ausencia de la
   metadata como "esto es un corpus pelado".

5. **Ids de aristas = `Col.ID` (DOI-ancla), NO `source_id`** (D1, lección B6 de Nota 09). El nodo
   del grafo del `NetworkArtifact` es `Col.ID`; el join downstream es por `papers.id` =
   `network_edges[].neighbor_id`. El `source_id` se queda en su columna de `papers` (constraint
   duro del consumidor programático, ADR 0050 §"Constraints"). Esta es **la decisión más
   contraintuitiva** del ADR pero la única que mantiene la coherencia con el modelo de identidad del
   corpus ([ADR 0036](0036-identidad-source-id-agnostica-doi-ancla.md) — DOI-ancla).

## Cambios concretos (DoD para el PR a `dev`)

- [ ] `networks/intra_community_pagerank.py` (núcleo puro) — función pura
      `intra_community_pagerank(graph: nx.Graph, communities: dict[Any, int], *,
      weight: str = "weight") -> dict[Any, float]`. Tests: grafo chico conocido, PageRank
      esperado a mano; grafo de un solo nodo; grafo sin comunidades (`{}`); subgrafo de un solo
      nodo (PageRank = 1.0 por convención de `nx.pagerank`).
- [ ] `exporters/arrow.py` extendido para poblar las nuevas columnas + metadata cuando hay
      `NetworkArtifact` disponible. Si no hay red, exporta solo la tabla `papers` original
      (modo degradado D4). Tests: round-trip Arrow con/sin red, metadata presente/ausente, schema
      estable.
- [ ] `cli/commands/export.py` gana `--network-type <kind>` (NetworkKind StrEnum). Flag opcional;
      default `bibliographic_coupling`. Validación: error accionable si el kind no aplica al
      corpus (p. ej. `cocitation` sin `cited_by_id`). Envelope `--json` gana los campos de D5.
- [ ] `docs/API.md` actualizado: nueva sección "Red tipada en el Arrow del corpus" con el schema
      de las nuevas columnas, la metadata del schema, y los campos del envelope. **Cambio de
      contrato público → este ADR es el ADR requerido.**
- [ ] `CHANGELOG.md` no se toca a mano (lo gestiona `release-please` al mergear).
- [ ] Tests de constraints del consumidor programático (ADR 0050 §"Constraints"): las columnas
      existentes no cambian de nombre/tipo/límite; las nuevas son aditivas; el ingest de un
      consumidor que ignora las nuevas columnas sigue funcionando.
- [ ] `corpus_hash` intacto: tests que exportan el mismo corpus con/sin red dan el mismo
      `corpus_hash`.
- [ ] Cierre del issue #316 al mergear.

## Relacionada con / toca

- **[0050](0050-contrato-export-corpus-arrow-bibtex-ecuacion.md)** — secuela: este ADR extiende el
  contrato de export del corpus con la red tipada. Aditivo sobre D1/D3/D4 (que ya están en 0.14.0).
  No toca D2 (diferida a 0.15.0 con su propio diseño, en 0050).
- **[#316](https://github.com/complexluise/bib2graph/issues/316)** — issue origen. Su DoD se cierra
  con este ADR.
- **[0014](0014-proyeccion-redes-pesos-asortatividad.md)** — semántica de proyección de redes. Este
  ADR **no toca** la lógica de `Networks.build` ni la del proyector; solo cambia **cómo se
  exporta** la red. Los proyectores siguen puros.
- **[0013](0013-identidad-hash-merge-corpus.md) D2** / **[0017](0017-reproducibilidad-historia-snapshot.md) R2** —
  `corpus_hash` excluye la red (las columnas de red se proyectan desde artefactos de build, no
  modifican el contenido bibliográfico). El hash del corpus sigue siendo de la tabla `papers`
  original, sin las columnas de red.
- **[0021](0021-cli-agente-native-contrato.md) / [0045](0045-cerrar-tres-grietas-agent-native.md)** —
  envelope `schema="1"` intacto. La entrega es aditiva sobre `data` (no sobre `schema`).
- **[0037](0037-superficie-cli-10-verbos-ciclo.md) / [0038](0038-destino-verbos-huerfanos-0037.md)** —
  no se suma un verbo nuevo. `b2g export --format arrow` gana `--network-type`; el conteo "10
  verbos + `skill` + `schema`" se mantiene.
- **[0036](0036-identidad-source-id-agnostica-doi-ancla.md)** — identidad de fuente agnóstica,
  DOI-ancla. Las aristas en `network_edges` usan `Col.ID` (DOI-ancla), no `source_id`. El
  `source_id` se queda en su columna de `papers` (constraint duro del consumidor programático).
- **[ADR 0022](0022-producto-sin-ia-generativa.md)** — sin IA. PageRank y Leiden/Louvain son
  funciones deterministas.
- **[ADR 0023](0023-capa-constants-modelos-schema.md)** — `--network-type` reusa el `NetworkKind`
  StrEnum existente. No se introduce un literal nuevo.
