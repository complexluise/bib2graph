# ARQUITECTURA — bib2graph (objetivo / north star)

> Arquitectura **deseada** de la V1, no un estado as-built. El as-built de v0 (con sus
> problemas) está en [`Notas/03-referencia/arquitectura-v0.md`](Notas/03-referencia/arquitectura-v0.md)
> y NO debe tomarse como objetivo. Fecha: 2026-06-15.
>
> Reconcilia este doc con el **giro** (`Notas/04`–`06`) y el [`PRD.md`](PRD.md) reescrito.
> Decisiones que lo sustentan, en [`decisiones/`](decisiones/): tabla canónica Arrow
> [0006](decisiones/0006-tabla-canonica-y-networkspec.md); **OpenAlex backbone**
> [0007](decisiones/0007-openalex-backbone.md); **wedge = forrajeo**
> [0008](decisiones/0008-wedge-forrajeo.md); **biblioteca viva en DuckDB**
> [0009](decisiones/0009-biblioteca-viva-duckdb.md); **agente-native columna**
> [0010](decisiones/0010-agente-native-columna.md); **thesaurus**
> [0011](decisiones/0011-thesaurus-multilingue.md). El método bibliométrico está en
> [`metodología.md`](Notas/metodología.md).
>
> **AS-BUILT vs TARGET (importante):** este doc describe el diseño **objetivo** tras el red-team
> de la [Nota 06](Notas/06-critica-as-built-v0.2.md). Donde el código v0.2 difiere del objetivo,
> el bloque está marcado **`TARGET`** (lo que debe construirse) y/o **`AS-BUILT v0.2`** (lo que hay
> hoy). La tanda de **remediación** que cierra esa brecha está secuenciada **por dependencia** en el
> [`ROADMAP.md`](ROADMAP/README.md) (Hitos **R1–R5**), antes de los hitos nuevos: **R1** cimientos
> (constants/modelos/schema), **R2** identidad-vs-procedencia (hash/reloj/Louvain), **R3** ciclo
> (`cycle.py`/`reseed`/curación transversal), **R4** scent bibliométrico (proyectores; retiro de
> IA), **R5** robustez (bulk-load/UTF-8/footguns).
>
> **Decisión bloqueada por el PO (2026-06-15) — el producto NO usa IA generativa.** La
> "inteligencia" que asiste el forrajeo es **estructura bibliométrica como *information scent***,
> **determinista y reproducible** (acoplamiento / co-citación / centralidad sobre el corpus), **sin
> LLM ni embeddings**. Se **elimina** `explain_candidate`, el módulo `foraging/explain.py` y el
> extra `[llm]`; la **"máquina de tensiones" / sensemaking asistido por IA se quita del alcance por
> completo** (no se difiere: se borra del producto). El sensemaking sigue siendo **humano**,
> asistido por las redes — no por IA. Queda **un solo** sentido de "AI-in-the-loop": el *desarrollo*
> es asistido por IA; el *producto* no usa IA. Ver ADR [0020](decisiones/0020-metodo-forrajeo-scent-filtros-reject.md)
> (scent bibliométrico), [0008](decisiones/0008-wedge-forrajeo.md) (tensiones removidas) y
> [0022](decisiones/0022-producto-sin-ia-generativa.md) (el producto no usa IA generativa).
>
> **Cambios mayores respecto a la versión previa de este doc:** la fuente de referencia pasó de
> **BibTeX a OpenAlex** (ADR 0007); la persistencia por defecto pasó de **snapshot inmutable /
> InMemoryStore** a un **`Store` stateful en DuckDB** (biblioteca viva; ADR 0009), con el
> snapshot demotado a *export*; se agregaron al núcleo el **forrajeo/chaining** y el **thesaurus
> multilingüe**; se incorporó una **capa base de vocabulario + modelos** (`constants` / `schemas`,
> con `ProvenanceEvent` consolidado en `schemas.py` —no en un `models.py` aparte—, ADR
> [0023](decisiones/0023-capa-constants-modelos-schema.md)) y el **ciclo como
> dominio puro** (`cycle.py` con FSM cíclico, ADR 0016 enmendado); y se **retiró la rama de IA**
> generativa (ADR 0022).

## 1. Idea en un párrafo

`bib2graph` es **un núcleo puro rodeado de costuras**, apoyado en una **capa base de vocabulario
y modelos**. La **capa base** (`constants`, `schemas`; ADR
[0023](decisiones/0023-capa-constants-modelos-schema.md)) es la **fuente única** de nombres de
columna, estados de curación, tipos de red y del evento de procedencia (`ProvenanceEvent` vive en
`schemas.py`, no en un `models.py` separado) — todo el resto depende de ella. El **núcleo puro** opera sobre un `Corpus` en memoria (una **tabla canónica Arrow**) y nunca
hace red ni servidores: proyecta el corpus a redes, las analiza y las exporta, normaliza/cura la
tabla, y **modela el ciclo** de investigación como una máquina de estados de dominio (`cycle.py`,
ADR [0016](decisiones/0016-maquina-estados-lazo.md)). Alrededor hay costuras: **`Source`** (sembrar
el corpus — *OpenAlex por defecto* desde una ecuación de búsqueda; BibTeX secundaria), el
**forrajeo/chaining** (expandir el corpus rankeando candidatos por *information scent* — **estructura
bibliométrica determinista, sin IA**), **`Store`** (persistir — *DuckDB stateful por defecto*: la
**biblioteca viva**) y `Enricher` (señal extra, opt-in). El flujo **no es lineal**: es el **ciclo
iterativo** de exploración (sembrar → forrajear → curar → la idea muta → re-sembrar), y la
biblioteca viva en DuckDB es el sustrato que lo sostiene entre corridas.

> **PARCIALMENTE CONSTRUIDO (2026-06-18) — frontends de frontera + capa de servicios neutral, ADR
> [0027](decisiones/0027-pivote-posicionamiento-gui-local.md)/[0028](decisiones/0028-arquitectura-gui-api-capa-servicios.md)
> (Aceptados; GUI gateada por [#34](https://github.com/complexluise/bib2graph/issues/34)).** La **capa
> de servicios neutral `src/bib2graph/service/` ya existe** (G1: contrato subido desde `cli/`; G2:
> 6 lecturas read-only en `service/reads.py`, AS-BUILT 2026-06-18). La **API local** (FastAPI) y la
> **SPA** (`frontend/`) **siguen TARGET, NO implementadas** (§4.4). Sobre ese núcleo + costuras se
> montan **tres frontends de frontera** — **CLI**
> (`b2g`, Click, la columna agente-native, ADR 0010/0021) · **API local** (FastAPI, opt-in `[gui]`) ·
> **SPA** (frontend "tool for thought" en `frontend/`). Los tres **convergen en una capa de servicios
> neutral** `src/bib2graph/service/` (agnóstica de transporte: sin `print`, `sys.exit`, Click ni
> FastAPI) que contiene **la orquestación** (lo que hoy es `run_<cmd>`) **+ el contrato** (envelope
> `schema="1"`, jerarquía de errores `B2GError`, mapeo error→código) **subido desde `cli/`**. CLI y API
> son **adaptadores delgados** sobre `service/`; ninguno importa al otro. El **contrato externo
> (`schema="1"`, exit codes) NO cambia**. Detalle en §4.4 y §6.3.

## 2. Vista de alto nivel

```
   ecuación de búsqueda
          │  (traducción + reporte de traducción, ADR 0007)
          ▼
   ┌──────────────┐      ┌─────────────┐      ┌────────────┐     ┌──────────┐
   │   Source     │ ───► │   CORPUS    │ ───► │ Projector  │ ──► │ Network  │ ──► Analyzer
   │  OpenAlex    │      │ tabla Arrow │      │ coupling   │     │ networkx │     (métricas,
   │ (BibTeX 2ª)  │      │ (1 fila/    │      │ co-citación│     └──────────┘      centralidad,
   └──────────────┘      │  paper)     │      │ co-autoría │          │           comunidades,
          ▲              │  is_seed,   │      │ keyword    │          ▼           asortatividad)
          │ chaining     │  status,    │      │ institución│     ┌──────────┐          │
   ┌──────────────┐      │  provenance │      └────────────┘     │ Exporter │          ▼
   │  FORRAJEO    │◄────►│  + refs/    │             ▲           │GraphML/CSV│   ┌──────────┐
   │ back/forward │      │  citas      │             │           └──────────┘   │ informe  │
   │ rank=scent   │      │  (OpenAlex) │             │                          │ calidad  │
   └──────────────┘      └─────────────┘      ┌────────────┐                    └──────────┘
   (preview, tope,              ▲             │Preprocessor│
    profundidad 1)              │             │ normalize +│
                                ▼             │ thesaurus  │
                        ┌─────────────┐       └────────────┘
                        │ DuckDBBackend│  BACKEND POR DEFECTO del CORPUS (biblioteca viva,
                        │  del CORPUS  │  ADR 0015): stateful, acepta/rechaza, crece entre
                        │  (stateful)  │  corridas, log de procedencia + estado del ciclo
                        │              │  (CycleState + ronda; dominio en cycle.py, ADR 0016).
                        │ DuckDBStore  │  Snapshot = export sellado. 1 archivo = 1 escritor
                        │  = fachada   │  (single-writer, ADR 0019). Store/Zotero(1.1)/Neo4j
                        │ Store→Zotero │  = costura externa opt-in, NO la persistencia primaria.
                        └─────────────┘
```

El **`DuckDBBackend` es el backend por defecto del `Corpus`** (ADR
[0015](decisiones/0015-corpus-tabular-backend.md)), no un `Store` separado: persiste, muta por SQL
`UPDATE`/`MERGE` por `id` y aloja el `LoopState` (ADR
[0016](decisiones/0016-maquina-estados-lazo.md)). El **`DuckDBStore` es su fachada** de costura
(`persist`/`load`); la costura `Store` sigue siendo el punto de extensión externo
(`ZoteroStore`/`Neo4jStore`, opt-in). Lo marcado `(BibTeX 2ª)`, `Zotero(1.1)`, `Neo4j` son costuras
secundarias/futuras. La **máquina de tensiones** (sensemaking asistido por IA) **se retiró del
producto** (ADR [0008](decisiones/0008-wedge-forrajeo.md) / [0022](decisiones/0022-producto-sin-ia-generativa.md)):
el sensemaking lo hace el **humano**, leyendo las redes — no hay IA generativa en el producto. Solo
se publica lo que existe.

> **TARGET (2026-06-18) — frontends → capa de servicios neutral, ADR
> [0028](decisiones/0028-arquitectura-gui-api-capa-servicios.md) (Aceptado; gateado por
> [#34](https://github.com/complexluise/bib2graph/issues/34) — NO implementado).** El diagrama de
> arriba es el **flujo de datos del núcleo**. La GUI agrega tres frontends de frontera que **convergen
> en una capa de servicios neutral** (no en `run_<cmd>` directo: ese ajuste es la corrección del
> 2026-06-18 sobre el encuadre original — `run_<cmd>` solo devuelve el payload `data`, mientras el
> contrato vivía en `cli/`):
>
> ```
>    SPA (JS, grafo-lienzo) ──HTTP/JSON──► API local (FastAPI, 127.0.0.1, opt-in [gui])
>    CLI b2g (Click) ──────────────────────────────────────┐                │
>                                                           ▼                ▼
>                       capa de servicios NEUTRAL  src/bib2graph/service/
>                       (orquestación = lo que hoy es run_<cmd>
>                        + contrato: envelope schema="1", errores B2GError, mapeo→código)
>                                                           ▼
>                       NÚCLEO PURO (corpus, cycle, projectors, analyzer) + costuras
> ```
>
> CLI y API son **adaptadores delgados** de `service/`; el CLI traduce el código a exit code y la API a
> HTTP status (§6.3, §4.4). El contrato externo (`schema="1"`, exit codes) **no cambia**.

## 3. El núcleo (puro, sin red ni servidores)

Dependencias del núcleo puro: `pyarrow`, `pydantic`, `networkx`, `click`, `tqdm`. **Nada de red
ni servidores** en proyección/análisis/normalización: todo el núcleo es unitariamente testeable
con tablas sintéticas. (El `Source` OpenAlex y el `Store` DuckDB se instalan por defecto y sí
hacen I/O, pero son **costuras**: el núcleo puro no depende de ellas — ver §4.)

### 3.1 `Corpus` — el contrato central (tabla canónica Arrow sobre un `TabularBackend`)

El `Corpus` es la **única fuente de verdad del modelo** y el formato que circula por el
pipeline. Su contenido es **una sola tabla Arrow** (`pa.Table`) con schema fijo por paper,
validada por el wrapper público con **Pydantic v2** (ADR 0006). `Paper`/`Author`/`Keyword`/
`Institution` **no son tipos del modelo**: son **vistas derivadas** vía `groupby + explode`.

**El `Corpus` se respalda en un `TabularBackend` (Protocol) y delega las mutaciones** (ADR
[0015](decisiones/0015-corpus-tabular-backend.md)): `InMemoryBackend` (puro, tests + working set
efímero) o `DuckDBBackend` (biblioteca viva por defecto, mutación por SQL `UPDATE`/`MERGE` por
`id`). El **núcleo no importa `duckdb`**: depende del Protocol. `corpus.to_arrow()` es el **puente
estable a los proyectores/analizadores puros** — solo cambia el *contenedor*, no el núcleo de
análisis. Las reglas de identidad/hash/merge (ADR
[0013](decisiones/0013-identidad-hash-merge-corpus.md), D1/D2/D3) son contrato que cada backend
cumple a su manera.

**AS-BUILT R5 — bulk-load (Nota 06 RAÍZ 3):** los loaders (seed/load OpenAlex, BibTeX, Forager)
construyen la tabla Arrow **de una vez** con `Corpus.from_arrow` (precomputando los `id` con el helper
`corpus._rows_with_ids`), en vez del loop `add_paper`/`_clone` que **re-upserteaba la tabla entera por
fila** (O(n²)). Cargar un corpus mediano deja de ser cuadrático.

**Columnas** (esquema completo en [`API.md`](API.md) §1 — *pendiente de reconciliar*):

- Identidad/metadatos: `id` (interno estable), `openalex_id`, `doi`, `title`, `year`,
  `abstract`, `source`, `language`, `publisher`, `research_areas`.
- **Estado de pipeline / curación** (no contamina la entidad): `is_seed` (bool),
  `curation_status` (`candidate` / `accepted` / `rejected`), `provenance` (JSON: ecuación, salto
  de chaining, fuente, fecha, decisión humana — base del **log de procedencia**, ADR 0009).
- **Relaciones de entrada** (datos crudos): `authors_raw` / `authors_id`,
  `authors_affiliations` (**per-autor**, de OpenAlex), `keywords_raw` / `keywords_id`,
  `institutions_raw` / `institutions_id`, `references_id`/`references_doi` y `cited_by_id`
  (**de OpenAlex**, ya no de un Enricher — ADR 0007).
- **Relaciones derivadas** (las producen los Proyectores, NO viven en el corpus):
  `BIB_COUPLED_WITH`, `CO_CITED_WITH`, `COLLABORATED_WITH`, `CO_OCCURRENCE`.

### 3.2 `Projector` — corpus → red

Toma un `Corpus` y devuelve un `networkx.Graph` ponderado:

| Red | Proyección | Insumo en el corpus | Costo |
|-----|------------|---------------------|-------|
| **acoplamiento bibliográfico** | papers que **comparten referencias** | `references_id` (OpenAlex, ya en el corpus) | barato; **sobre corpus completo**, no solo semillas |
| co-citación | papers **citados juntos** | `cited_by_id` + citas de los citantes | **el más caro** (2º nivel de fetch) |
| colaboración de autores | autores que co-firman | `authors_id` | barato |
| colaboración de instituciones | instituciones vía co-firmas | `institutions_id` | barato |
| co-ocurrencia de keywords | keywords juntas en un paper | `keywords_id` (normalizadas por thesaurus) | barato |

**Verdad de dependencias (ADR 0007):** con OpenAlex como backbone, las referencias y los
citantes **ya vienen en el corpus**; el `Enricher` deja de ser estructural. El **acoplamiento**
(barato, mira hacia adelante, usa refs que las semillas ya traen) es **ciudadano de primera**
(crítica #2). La **co-citación** sigue siendo la más cara: necesita los citantes *con sus
propias citas* (segundo nivel de fetch). El acoplamiento opera sobre el **corpus completo**, no
solo `is_seed` (rediseño validado en el sandbox IED). **AS-BUILT (Hito 8b ✅):** ese 2º nivel ya está
cableado end-to-end — `b2g enrich` puebla `cited_by_id` (vía `OpenAlexSource.fetch_citing_batch`,
§4.2) y `Networks.quick` incluye la co-citación cuando esa columna está poblada.

### 3.3 `Analyzer` — red → resultados

Funciones puras sobre `networkx.Graph`:

- **Métricas de red:** densidad, componentes, clustering.
- **Centralidad:** grado, intermediación.
- **Comunidades:** Louvain, propagación, modularidad voraz (con score). Louvain depende de
  `python-louvain`: se **declara** y, si falta, **falla fuerte** (lección 7).
- **Asortatividad** (validado en el sandbox IED): por un **atributo categórico configurable**
  (p. ej. región geográfica) y **por grado**, más la **composición de cada comunidad** por ese
  atributo. Las métricas que dependen de un **proxy** (p. ej. afiliación por-paper vs per-autor)
  se reportan **con el disclaimer del proxy** ("fácil pero consciente"). El atributo y sus
  categorías son **config del usuario**, no umbrales hardcodeados (crítica #5).
- **Informe de calidad** de la co-citación según [`metodología.md`](Notas/metodología.md) §4, con
  umbrales **configurables**.

### 3.4 `Exporter` — resultados → archivos

GraphML y CSV (nodos y aristas). I/O de salida puro y predecible, sin backend.

### 3.5 Forrajeo / chaining (asistido por estructura bibliométrica, SIN IA)

Orquestación pura sobre la costura `Source`: dado el corpus actual, computa candidatos por
**backward chaining** (referencias de las semillas) y **forward chaining** (citantes), y los
**rankea por *information scent***. El *information scent* es **estructura bibliométrica
determinista y reproducible**, **sin LLM ni embeddings** (ADR
[0020](decisiones/0020-metodo-forrajeo-scent-filtros-reject.md) actualizado;
[0022](decisiones/0022-producto-sin-ia-generativa.md)): el forrajeo **consume el núcleo de
proyección** (§3.2, primitivo `collect_item_to_papers`) — un candidato rankea por cuánto se co-cita
(backward) o cita directamente (forward) respecto del corpus curado.

- **`AS-BUILT R4` (2026-06-16):** el scent consume el primitivo público `collect_item_to_papers`
  de `networks/projectors.py` (lo que la [Nota 05](Notas/05-ciclo-investigacion-humano.md) §4
  promete): el forrajeo (costura) **depende del núcleo de proyección** (puro), nunca al revés.
  Sigue siendo **función pura y determinista** (mismo corpus → mismo ranking).
  - **Backward** = **fuerza de co-citación con el corpus**: `|{Pi ∈ corpus : X ∈ Pi.references_id}|`
    (cuántos corpus-papers co-citan al candidato; es la columna de `X` en la matriz de co-citación).
  - **Forward** = **fuerza de citación directa al corpus** (señal primaria): a cuántos corpus-papers
    cita el candidato directamente — robusta, siempre > 0 para un citante real.
    `forward_score(Y) = |{ref ∈ Y.references_id : ref ∈ corpus_ids}|` (emite con `direct > 0`). *(El
    AS-BUILT inicial de R4 implementó el forward como **acoplamiento puro**, que degenera a 0 con
    referencias ralas; se **corrigió a citación directa dentro de R4** — ver ADR
    [0020](decisiones/0020-metodo-forrajeo-scent-filtros-reject.md) AS-BUILT.)*
  - **Centralidad** de red del candidato: **diferida** (viz); el DoD "y/o" se cumple con
    co-citación + citación-directa.

Reglas (ADR 0008, nota 07): **profundidad 1 por defecto** (`depth>1` lanza `NotImplementedError`);
**preview de crecimiento** ("sumaría ~N papers") **sin red** —backward exacto local; forward no
estimable sin fetch (`forward_requires_fetch`)— y **tope** (`max_candidates`) configurable antes de
traer; **pool cortés** de OpenAlex. Forward exige `source.fetch_citing(...)` (capacidad de
`OpenAlexSource`, **no** del Protocol `Source`). **No hay paso de IA:** `explain_candidate`, el
módulo `foraging/explain.py` y el extra `[llm]` quedan **eliminados** (ADR 0022) — el "porqué" de un
candidato lo explica la **estructura visible** (con qué del corpus se acopla/co-cita), no un LLM.

> **Sesgo de confirmación (Nota 06, rigor):** rankear por estructura ya presente refuerza lo central
> y popular (efecto Mateo). El scent es ayuda de **priorización**, no de **exhaustividad**: la
> exhaustividad PRISMA la sostienen los filtros y el conteo de exclusiones, no el scent.

### 3.6 `Preprocessor` — normalización (núcleo)

Determinístico e idempotente: canonicalización **conservadora** de nombres de autor
(`authors_id`: lowercase + acentos + espacios) y `language` (ISO 639-1 primario), y
**normalización de keywords vía thesaurus multilingüe** (en/es/pt; dict `canónico → aliases` en
JSON portable; ADR 0011). Lo *fuzzy* (dedup aproximado de autores y keywords) corre
**automáticamente en la ingesta** con `rapidfuzz` **en el núcleo** (ADR
[0031](decisiones/0031-preprocesamiento-automatico-en-ingesta.md), #88 — **supersede** en parte
[0026](decisiones/0026-dedup-fuzzy-determinista.md): el dedup deja de ser función de librería y el
extra `[dedup]` se elimina, `rapidfuzz` pasa al núcleo; `splink` sigue diferido a post-V1). **No hay fallback
semántico/LLM del thesaurus** (ADR
[0011](decisiones/0011-thesaurus-multilingue.md) enmendado / 0022): el thesaurus es **curado y
determinista**; lo que no matchea queda fuera, sin inventar conceptos con un modelo.

## 4. Las costuras (puntos de extensión)

Contratos tipados y estables (Protocols / ABCs; ver [`API.md`](API.md)). El núcleo no conoce
implementaciones concretas: las recibe inyectadas.

### 4.1 `Source` — sembrar un corpus

Convierte una entrada externa en `Corpus`. El contrato es **agnóstico de la forma de OpenAlex**
(ADR [0018](decisiones/0018-source-agnostico-calidad.md)): separa el **mínimo universal**
(`id`, `title`, `year`, `authors_raw`, `keywords_raw` — habilita ya co-autoría y co-word) del
**enriquecimiento opcional** (`references_id`/`references_doi`, `cited_by_id`, afiliaciones
per-autor, `institutions_id` — habilita acoplamiento, co-citación, instituciones, asortatividad).
Una `Source` que solo entrega el mínimo es legítima; los proyectores de enriquecimiento producen
redes parciales y lo reportan (no fallan). Esto habilita fuentes regionales (SciELO, Redalyc, La
Referencia) sin obligarlas a entregar lo que no tienen.

**Implementación de referencia: OpenAlex** (ADR 0007): traduce la **ecuación de búsqueda** a una
query OpenAlex, muestra la **query ejecutada + reporte de traducción** (qué mapeó limpio, qué se
aproximó, qué se descartó), y trae mínimo + enriquecimiento completo (`references_id`,
`cited_by_id`, afiliaciones per-autor) y ancla `Manifest.openalex_version` (ADR
[0017](decisiones/0017-reproducibilidad-historia-snapshot.md)). Power-users pueden pasar query
OpenAlex nativa (escape hatch). **`BibtexSource` es `Source` secundaria** para sembrar desde
*pearls* conocidos (acceso defensivo a campos; el sandbox documenta un bug de `bibtexparser` que
exige un pre-procesador). SciELO/Redalyc/La Referencia, RIS/CSV: futuras, no publicadas. Un
**reporte de cobertura/calidad** por seed/source (concreto v0.2+, ADR 0018) mide qué tan completa
es la fuente y alimenta el juicio de cuándo cambiar de `Source`.

### 4.2 `Enricher` — señal extra (opt-in, núcleo sobre OpenAlex)

Con OpenAlex como backbone, **deja de ser estructural** (ADR 0007). Vive en el **núcleo sobre
OpenAlex** (no en `[s2]`; ADR [0025](decisiones/0025-enricher-cocitacion-openalex.md)). El **Hito 8
está completo** (Ciclos 8a + 8b): `OpenAlexEnricher.enrich` hace **2 pasadas**. **8a** — **resolver
`references_id` a DOI canónico** (OpenAlex las da como URLs internas — T8 del sandbox; batching por
OR, idempotente vía `EnricherRef` en el `Manifest`). **8b** — el **segundo nivel de fetch** habilita
la **co-citación end-to-end**: trae los citantes de las **semillas aceptadas** (vía
`OpenAlexSource.fetch_citing_batch`: batcheo OR ≤50 con presupuesto por semilla) y **mergea sus
`openalex_id` en `cited_by_id`** (unión idempotente); **solo puebla `cited_by_id`**, no crece el
corpus (decisión A). El tope `max_citing_per_paper` **acota el fetch por semilla**. El subcomando
`b2g enrich` (flag `--max-citing`) es propio y **no transiciona el `CycleState`**. S2/CrossRef/Scopus:
futuras (`[s2]` reservado para señal adicional). Reglas: config inyectada (nunca embebida), sin ramas
muertas, rate limit y reintentos sin perder papers.

### 4.3 `Store` / backend de persistencia (biblioteca viva)

**Por defecto: `DuckDBBackend` stateful** (ADR 0009 reencuadrado por
[0015](decisiones/0015-corpus-tabular-backend.md)): la **biblioteca viva** es el **backend por
defecto del `Corpus`**, no un `Store` aparte. Persiste el contenido Arrow **entre corridas**, más
tablas de **procedencia, decisiones de curación** (aceptar/rechazar) y el **`LoopState`** (ADR
[0016](decisiones/0016-maquina-estados-lazo.md)). Muta por SQL `UPDATE`/`MERGE` por `id` (no copia
en memoria). **Cleanup pre-v0.3:** el `merge` ya **no interpola ids crudos** en el SQL (eliminado el
`CASE WHEN`/`IN (...)` con f-strings); lee las filas y **ordena en Python** por orden de aparición
antes de reinsertar (orden determinista D3 preservado, sin construir SQL con datos). Soporta query
SQL. Es **núcleo**, no extra. **Una investigación = un workspace** (carpeta autocontenida con su
`library.duckdb` marcada por `workspace.json`; AS-BUILT ADR
[0029](decisiones/0029-workspace-por-investigacion.md), enmienda #75: la carpeta es la **única**
unidad canónica —el modo degenerado del `.duckdb` suelto fue eliminado—); el `library.duckdb` sigue
siendo single-writer (concurrencia diferida, ADR
[0019](decisiones/0019-concurrencia-diferida.md)).

El **snapshot** es un **export sellado** del estado vivo (ver §6.2), no la persistencia en sí;
`ParquetStore` puede servir como **formato de export/intercambio**. La costura `Store` sigue
siendo el punto de extensión para destinos externos: **`ZoteroStore`** (sincronizar la biblioteca
con una colección Zotero) es **opt-in en V1.1** (`[zotero]`); **`Neo4jStore`** es adaptador opt-in
post-V1 (`[neo4j]`): un destino más, **ya no el sustrato** (ADR 0002).

> **AS-BUILT (2026-06-16) — workspace por investigación, ADR
> [0029](decisiones/0029-workspace-por-investigacion.md):** la **unidad de persistencia es el
> workspace = una carpeta** (`workspace.json` + `library.duckdb` + `networks/` + `snapshots/` +
> `exports/`), formalizando la convención emergente de que `build` ya escribía `<store_dir>/networks/`.
> El corpus/procedencia/curación/loop-state siguen en el `.duckdb`; redes/exports = cache regenerable
> sellada por `corpus_hash` (`b2g build` graba `networks/.corpus_hash`); el snapshot sigue siendo lo
> reproducible (§6.2). El `.duckdb` suelto sigue válido como **workspace degenerado** (sin migración
> forzada). Enmienda 0009/0019; single-writer sin cambios. **Acotado en este corte:**
> `snapshot`/`export` aún usan `--out-dir` explícito; la staleness solo sella el hash (sin aviso ni
> regeneración automática todavía).
>
> **SUPERADO (#75, 2026-06-17):** el modo degenerado se eliminó — la carpeta con `workspace.json` es
> la **única** unidad canónica y un `.duckdb` legacy se adopta con `b2g init .` (ver ADR 0029,
> enmienda 2026-06-17).

### 4.4 `LocalApiServer` / API local (costura opt-in, `[gui]`) — `TARGET`, NO implementado

> **PARCIALMENTE CONSTRUIDO (2026-06-18) — ADR
> [0028](decisiones/0028-arquitectura-gui-api-capa-servicios.md) (Aceptado; GUI gateada por
> [#34](https://github.com/complexluise/bib2graph/issues/34)).** La **capa de servicios neutral
> `src/bib2graph/service/` YA existe**: G1 subió el contrato (envelope/errores/`code_for`, §0 de
> [`API.md`](API.md)) y **G2 (AS-BUILT 2026-06-18) construyó las 6 lecturas read-only de la SPA** en
> `service/reads.py` —`get_workspace`/`list_rounds`/`get_paper`/`get_scent`/`get_network`/
> `compare_rounds`, cada una sobre un `Workspace` resuelto (ADR 0029), devolviendo `dict` serializable o
> `B2GError`, sin red/mutación/transición— justamente las lecturas que el CLI nunca expuso (ver
> [`API.md`](API.md) §0.1 y [`ROADMAP/05-gui.md`](ROADMAP/05-gui.md) §G2). Lo que **sigue TARGET, NO
> construido**: la **API** (`src/bib2graph/api/`, FastAPI), el subcomando **`b2g gui`** y la **SPA**
> (`frontend/`) — no se construyen hasta validar el caso real con un tercero (ADR 0027). El prototipo
> `app/server/` es *throwaway* (referencia), con un `envelope()` propio que se **retira** a favor del
> contrato neutral. El resto de esta sección describe el diseño **objetivo** de esa frontera de
> servidor.

La **API local** es una **costura nueva de servidor** (no del núcleo): un adaptador **delgado** sobre
la capa de servicios neutral `src/bib2graph/service/`, en `src/bib2graph/api/` (FastAPI). No
reimplementa lógica ni contrato: **reusa el mismo envelope `schema="1"` y la jerarquía de errores
`B2GError`** que `service/` sube desde `cli/`, y traduce el **código del contrato a HTTP status**.

- **Local-first, sin hosting:** bind a **`127.0.0.1`** + **token efímero** (no expone red; ADR 0027).
- **Import perezoso:** el núcleo **no importa `fastapi`/`uvicorn`**; solo el adaptador API y el
  subcomando `b2g gui` los importan, y vienen en el extra **`[gui]`** (§7).
- **Funciones de lectura que el CLI nunca expuso (AS-BUILT G2):** `service/reads.py` ya añade las
  lecturas que la SPA necesita y no mapean 1:1 a subcomandos —`get_workspace`, `list_rounds`,
  `get_paper`, `get_scent`, `get_network` (por kind, ronda viva), `compare_rounds` (diff de rondas, el
  diferenciador)— por eso la convergencia es en **servicios**, no en **comandos**. La API (TARGET) las
  consumirá vía HTTP. Ver [`API.md`](API.md) §0.1.
- **Mapeo código→HTTP** (adaptador API, el envelope viaja igual en el body — la SPA lee `error.code`,
  no depende del status): `0`→200 · `1` (uso)→400 · `2` (datos)→422 · `3` (dependencia)→501 · `4`
  (red)→502 · `5` (store bloqueado/corrupto)→409/503.
- **Operaciones largas (v1):** `seed`/`enrich`/`build` bloquean (red, Louvain) y el store es
  **single-writer** (ADR [0019](decisiones/0019-concurrencia-diferida.md)). La API v1 es **síncrona** +
  **lock global serializado** (una escritura a la vez). **Jobs async/SSE y reabrir 0019 quedan
  diferidos** (no en v1).

El **frontend SPA** vive en `frontend/` (monorepo Vite/TS); su build se **vendorea** a
`src/bib2graph/gui/static/` y **va al wheel** (la GUI funciona sin Node). El subcomando **`b2g gui`**
(ver §6.3) es el adaptador de "arranque local": levanta uvicorn sobre la API, sirve los assets
pre-build y abre el browser.

## 5. Flujo de datos (ciclo iterativo, no pipeline lineal)

```
0. (humano) idea / pregunta difusa
1. Source(OpenAlex).seed(ecuación)        ──►  Corpus (semillas) + query registrada
2. Forrajeo.chain(corpus, depth=1)        ──►  candidatos rankeados por scent  ◄─┐
3. (humano) aceptar/rechazar + filtros    ──►  Corpus curado (status, conteos)   │
   Preprocessor.normalize(corpus)         ──►  nombres + keywords (thesaurus)     │
4. (humano) la idea/ecuación MUTA ─────────────────────────────────────────────►─┘  (re-sembrar)
5. Store(DuckDB).persist(corpus)          ──►  biblioteca viva (entre corridas)
6. Projector.project(corpus)              ──►  networkx.Graph (5 redes)
7. Analyzer.analyze(graph)                ──►  métricas / comunidades / asortatividad / calidad
8. Exporter.export(...) · Store.snapshot()──►  GraphML/CSV + snapshot reproducible
```

El lazo **2→3→4→1** (la query y la idea mutan; Bates/Ellis/Kuhlthau) es la propiedad central:
la biblioteca viva existe para que ese lazo no pierda lo acumulado (PRD §1–§2).

La no-linealidad se modela como una **máquina de estados explícita** (ADR
[0016](decisiones/0016-maquina-estados-lazo.md) enmendado). Es un **concepto de dominio puro y
testeable** — el módulo **`bib2graph.cycle`**: el modelo de estados + las reglas de transición viven
en el núcleo; el **backend solo lo persiste** (**AS-BUILT R3, 2026-06-16**).

`cycle.py` expone `CycleState` (`SEEDED/FORAGED/FILTERED/BUILT/MONITORED`),
`apply_transition(state, action, round) → (state, round)`, `available_transitions(state)` y
`CURATION_ACTIONS`. El enum de estados **dejó de vivir** en `backends/duckdb.py`; el backend persiste
el estado y la **ronda** en `loop_state_log` (`loop_round()` / `set_loop_state`). **Cleanup pre-v0.3:**
el alias transicional `LoopState = CycleState` **se retiró** (de `backends/duckdb.py` y
`stores/duckdb.py`); el código usa **una sola** clase, `CycleState`.

FSM **cíclico** fiel a la [Nota 05](Notas/05-ciclo-investigacion-humano.md):

```
SEEDED ──chain──► FORAGED ──filter──► FILTERED ──build──► BUILT ──monitor──► MONITORED
   ▲                                                                              │
   └──────────────────────── reseed (la idea muta) ◄──────────────────────────────┘
                     (loop-back a SEEDED; incrementa el contador de RONDA;
                      acumula sobre lo curado — la no-linealidad es del sistema)
```

- **`reseed` es transición de primera clase** ("la idea muta"): `apply_transition(state, "reseed", r)
  = (SEEDED, r+1)`. Lo cablea `seed.py`: si hay estado previo, la siembra es un re-sembrado (ronda++,
  acumula sobre lo curado). Es lo que el ADR 0016 prometía y el AS-BUILT lineal no cumplía.
- **Fuente única de verdad:** `chain`/`filter`/`build` **derivan** su estado destino de
  `apply_transition` (no de un literal); un test domain-tied lo ata.
- **`MONITORED`** modela el paso 8 del ciclo (monitoreo) y es **alcanzable** desde el cleanup
  pre-v0.3: el comando **`b2g monitor`** lo dispara (re-chequea OpenAlex por citantes nuevos del
  corpus vía forward chaining, mergea los candidatos nuevos y transiciona).
- **La curación es TRANSVERSAL:** `accept`/`reject` están disponibles **en cualquier estado**, **no
  transicionan**; `b2g status` las muestra **siempre** en `curation_available` (separado de
  `transitions_available`) y expone el contador de `round`.

El estado del lazo vive en el backend persistente (`DuckDBBackend`), no en el `Corpus` efímero, y se
expone con `b2g status`: humanos e IAs comparten el mismo mapa del lazo. El **reloj se inyecta en la
frontera** (CLI), no en el núcleo (§6.2).

## 6. Configuración, persistencia y reproducibilidad

### 6.1 Configuración inyectada

- **Una sola fuente de configuración**, construida explícitamente y pasada a quien la necesita.
  **Sin efectos de import** (en v0, importar seteaba `config.DATABASE_URL`).
- **Sin secretos embebidos** (en v0 había triple `DATABASE_URL` y clave S2 hardcodeada).
- Credenciales y el **email del pool cortés de OpenAlex** (y la **API key opcional** desde
  feb-2026) se inyectan por config/CLI o entorno, nunca embebidos (ADR
  [0012](decisiones/0012-openalex-credenciales.md)). Sin key, el `Source` corre en polite pool.

### 6.2 Persistencia por defecto: biblioteca viva en DuckDB + snapshot exportable

La persistencia por defecto es **stateful**: el `DuckDBBackend` conserva el corpus **entre
corridas** (ADR 0009/0015). Reproducibilidad por **historia auditable** (el log de procedencia: qué
ecuación, qué salto de chaining, qué decisión humana, cuándo) **+ snapshot exportable**, **no por
recómputo** (ADR [0017](decisiones/0017-reproducibilidad-historia-snapshot.md)): re-ejecutar la
misma ecuación contra OpenAlex NO garantiza el mismo corpus (OpenAlex cambia en el tiempo). El
artefacto reproducible es el **snapshot**; el `openalex_version` del Manifest lo ancla a la
versión/fecha de OpenAlex usada.

**Identidad (contenido) vs procedencia (auditoría)** (ADR
[0017](decisiones/0017-reproducibilidad-historia-snapshot.md), enmienda 2026-06-15):

- **`AS-BUILT` (R2, ✅ 2026-06-16):** el `corpus_hash` se computa **solo sobre contenido
  bibliográfico**, **excluyendo** `provenance`/`ProvenanceEvent` con sus timestamps (sigue
  incluyendo `curation_status`, que es contenido curado). La **procedencia es un log append-only
  fuera de la identidad** (sirve para auditar, no para identificar). Dos corridas que aceptan los
  mismos ids dan ahora el **mismo** `corpus_hash` → el snapshot es reproducible bit a bit (cumple el
  ADR 0017 y `facade.py`). El **reloj se inyecta en la frontera** (CLI): `accept`/`reject`/`filter`
  reciben `decided_at`; el núcleo conserva un **fallback `datetime.now(UTC)`** para uso como librería
  sin `decided_at` (no afecta la identidad, que excluye provenance — ADR 0017 punto 3). **Louvain**
  corre con un `random_state` **derivado del content-hash** (`_louvain_seed_from_hash`) → comunidades
  reproducibles. (`resolution` de Louvain **diferido a Hito 9**, NetworkSpec.) Ver ROADMAP **Hito R2**.
- **`HISTÓRICO — AS-BUILT v0.2` (roto, pre-R2):** `accept`/`reject` estampaban `datetime.now(UTC)`
  en el evento de procedencia (reloj en el núcleo), y `compute_corpus_hash` hasheaba **todos** los
  campos, incluido `provenance` con sus timestamps → dos corridas que aceptaban los mismos ids daban
  `corpus_hash` distintos. R2 lo corrigió.

El **snapshot** es un **export sellado** del estado vivo en un instante: `corpus.parquet` + un
`manifest.json` con `schema_version`, `corpus_hash`, `lib_version`, `openalex_version`/fecha,
`sources`, `chaining` (profundidad, topes), `preprocessors`, `filters` (conteos PRISMA),
`created_at`. Sirve para **reportar (PRISMA / vom Brocke) y reproducir**, y se versiona en
git-lfs/DVC. A diferencia del diseño previo, el snapshot **no es** la persistencia: es una **foto
derivable** de una biblioteca que sigue viva.

### 6.3 CLI agente-native como columna primaria (ADR 0010 / 0021)

La CLI es **superficie primaria desde el primer comando**, no un adorno futuro: cada subcomando
con **doble salida** (humana + `--json` estable/versionado), **exit codes** claros (`0` éxito ·
`1` uso · `2` datos · `3` dependencia faltante · `4` red no disponible · `5` store/snapshot
corrupto), **errores accionables**, `--help` rico y **eficiencia de tokens**. **Sin estado entre
invocaciones**: el estado vive en el `Store` DuckDB, no en la sesión. Tool schemas JSON / MCP son
trabajo posterior, pero la API se **diseña con estos principios desde el hito 1**.

**As-built (Hito 6, ADR [0021](decisiones/0021-cli-agente-native-contrato.md)):** el CLI es un
**paquete `bib2graph.cli/`** (no un `cli.py` plano) con **3 capas**:

1. **Capa Click** (`cli/__init__.py` + `cli/commands/<cmd>.py`): el grupo `b2g` con la opción
   global **opcional** `--workspace` (`--store` fue eliminada en #75), y un comando Click por
   subcomando que sólo parsea flags y delega.
2. **Capa de funciones núcleo** (`run_<cmd>(store_path, ...)` en cada módulo de comando):
   **testeable sin Click**, contiene la lógica del subcomando. El ROADMAP testea esta función, no
   el parser de Click.
3. **Capa de envelope/errores** (`cli/_envelope.py`, `cli/_errors.py`, `cli/_store.py`): el
   envelope JSON versionado (`schema="1"`) compartido y el decorador `@handle_errors` que **mapea
   errores a exit codes por tipo de excepción** (`DataError`→2, `ImportError`/`DependencyError`/
   `NotImplementedError`→3, `httpx.HTTPError`→4, `StoreLockedError`/`OSError`→5). **AS-BUILT R5:**
   `AttributeError` ya **no** se captura en el decorador (no se disfraza un bug de "capacidad
   faltante"); la capacidad-de-source-faltante se convierte en `DependencyError` mediante un
   **pre-check `hasattr` en el borde** (p. ej. `chain.py` antes del `Forager`). Ver ADR 0021 §D.

Son **18 subcomandos** (`seed`, `chain`, `filter`, `build`, `export`, `snapshot`, `status`,
`inspect`, `validate`, `accept`, `reject`, **`monitor`**, **`enrich`**, **`init`**, **`curate`**,
**`networks`**, **`restore`**, **`thesaurus`**); el 18° **`thesaurus`** —único paso de
normalización explícito— lo sumó el ADR [0031](decisiones/0031-preprocesamiento-automatico-en-ingesta.md)
(#88, 2026-06-18). `build`/`export` están
**separados** y el `CycleState` transiciona automáticamente por comando (ADR 0021). El 12°
**`monitor`** (cleanup pre-v0.3) re-chequea citantes nuevos del corpus (forward chaining) y
transiciona a `MONITORED`. El 13° **`enrich`** (Hito 8 = Ciclos 8a + 8b, ADR
[0025](decisiones/0025-enricher-cocitacion-openalex.md)) corre el `OpenAlexEnricher` (refs→DOI +
co-citación, flag `--max-citing`) y **no transiciona** el ciclo (ortogonal al lazo). El 14°
**`init`** (AS-BUILT ADR [0029](decisiones/0029-workspace-por-investigacion.md)) hace scaffold de un
workspace (carpeta + `workspace.json` + `library.duckdb` + `networks/`/`snapshots/`/`exports/`;
`b2g init .` inicializa el cwd) y **no transiciona** el ciclo. El 15° **`curate`** (#22 + #26) hace
curación a escala vía CSV (dump/import en lote, transversal: **no transiciona** el ciclo). El 16°
**`networks`** (Hito 9, AS-BUILT 2026-06-17) construye redes desde un YAML declarativo
(`b2g networks --spec <yaml>`, `load_specs` + `Networks.build` por red, helper compartido
`_write_artifacts`) y **no transiciona** el ciclo ni sella `.corpus_hash` (transversal al lazo). El 17°
**`restore`** (Ciclo 9a, ADR [0030](decisiones/0030-ecuacion-declarativa-corpus-ejemplo.md)) rehidrata el
corpus desde un parquet curado **sin red** (inverso de `snapshot`; preserva `decision`/`curation_status`/
`is_seed`) y transiciona a `FILTERED` (reusa la transición permisiva `filter`, ADR 0016). El error de uso (p. ej.
una opción desconocida como `--store` —eliminada en #75—, o ningún workspace resoluble) sale **sin
envelope** (Click aborta el parseo: stderr + exit 1).

**AS-BUILT R5 — UTF-8 en la frontera (Nota 06 RAÍZ 3):** `main()` llama `_force_utf8()` (reconfigura
`sys.stdout`/`stderr` a UTF-8, con guarda por si la stream no es reconfigurable) **antes de que Click
lea nada**. Sin esto, el envelope `--json` (`ensure_ascii=False`) y `--help` corrompen acentos en la
consola cp1252 de Windows (`ecuaci�n`), rompiendo el contrato agente-native. **AS-BUILT R5 — store de
solo lectura:** `status`/`validate` usan `open_store_readonly` (`cli/_store.py`), que **no auto-crea**
el `.duckdb` ante un workspace mal apuntado (falla accionable); los comandos de escritura conservan
`open_store`.

> **AS-BUILT (2026-06-16) — `--store` opcional + `--workspace` + `b2g init`, ADR
> [0029](decisiones/0029-workspace-por-investigacion.md):** con el modelo workspace, `--store` dejó de
> ser opción global **obligatoria** y pasó a **opcional**, y se agregó **`--workspace`** (ambos
> opcionales y **mutuamente excluyentes** — juntos = error de uso). La unidad es una **carpeta
> workspace** (`workspace.json`), resuelta por ambiente (patrón git/cargo: walk-up del cwd).
> Precedencia: `--workspace`/`--store` explícito > `B2G_WORKSPACE` (env) > workspace del cwd. Sin flag
> y sin workspace resoluble → error accionable que sugiere `b2g init`. Entró el subcomando **`b2g init
> <name>`** (scaffold de la carpeta; `b2g init .` inicializa el cwd) → el conteo de subcomandos pasó de
> **13 a 14**. El `.duckdb` suelto sigue funcionando (workspace "degenerado", sin migración forzada).
> Es un cambio **suave/aditivo** del contrato (la resolución ambiente solo cubre el flag ausente). El
> `status` suma el campo aditivo `workspace: {root, source}` (`schema="1"` intacto).
>
> **SUPERADO (#75, 2026-06-17, BREAKING):** `--store` se **eliminó por completo** del CLI (pasarla da
> el error estándar de Click `No such option`) y el modo degenerado dejó de existir. Queda solo
> `--workspace` (opcional) + resolución ambiente; un `.duckdb` legacy se adopta con `b2g init .`. Ver
> ADR 0029 / 0021 (enmiendas 2026-06-17).

> **TARGET (2026-06-18) — el CLI es uno de tres frontends de frontera; `b2g gui`, ADR
> [0028](decisiones/0028-arquitectura-gui-api-capa-servicios.md) (Aceptado; gateado por
> [#34](https://github.com/complexluise/bib2graph/issues/34) — NO implementado).** El CLI deja de ser
> el único frontend: pasa a ser **un adaptador** (junto con la API local, §4.4) sobre la **capa de
> servicios neutral** `src/bib2graph/service/`. El contrato (envelope `schema="1"`, jerarquía
> `B2GError`, mapeo error→exit-code) **sube** de `cli/` a `service/`; el CLI conserva solo Click +
> `emit`/`emit_human` + `sys.exit`. El **contrato externo (`schema="1"`, exit codes 0–5) NO cambia**
> (enmienda 0021 sin romper el contrato).
>
> Entra un subcomando nuevo **`b2g gui`** (levanta uvicorn sobre la API + sirve los assets pre-build
> del frontend + abre el browser; adaptador de "arranque local"). **Conteo:** hoy el CLI tiene
> **18 subcomandos** (verificado: 18 `add_command` en `src/bib2graph/cli/__init__.py`, incl.
> `thesaurus` agregado por ADR [0031](decisiones/0031-preprocesamiento-automatico-en-ingesta.md)),
> así que `b2g gui` sería el **19º** (consistente con el AS-BUILT de §6.3 —18 incl. `thesaurus`—, el
> ADR 0028 §3 y la [Nota 12](Notas/12-arquitectura-gui-encuadre.md) punto 6, todos alineados a "18 → 19º").

## 7. Layout de dependencias (extras)

```
core         pyarrow, pydantic, networkx, click, tqdm,
             duckdb, rapidfuzz, <cliente OpenAlex>      (siempre; biblioteca viva + backbone +
                                                         dedup fuzzy determinista en ingesta)
[zotero]     pyzotero                                   ─┐
[s2]         (cliente Semantic Scholar; reservado para   │ costuras / capacidades opcionales
              señal adicional, NO el Enricher —ADR 0025)  │
[neo4j]      neomodel / driver oficial                   │ (futuras marcadas como no
[viz]        matplotlib, seaborn                          │ implementadas)                    ─┘
```

> El extra **`[dedup]` se eliminó** (ADR [0031](decisiones/0031-preprocesamiento-automatico-en-ingesta.md),
> #88): `rapidfuzz` pasó al **núcleo** porque el dedup ahora es automático en la ingesta (supersede en
> parte ADR [0026](decisiones/0026-dedup-fuzzy-determinista.md) / la enmienda `[dedup]` de ADR
> [0005](decisiones/0005-dependencias-extras.md)).

El extra **`[llm]` se elimina** (ADR [0022](decisiones/0022-producto-sin-ia-generativa.md)): el
producto no usa IA generativa, así que no hay cliente LLM ni para forrajeo ni para thesaurus.

> **TARGET (2026-06-18) — extra `[gui]`, ADR
> [0028](decisiones/0028-arquitectura-gui-api-capa-servicios.md) (Aceptado; gateado por
> [#34](https://github.com/complexluise/bib2graph/issues/34) — NO implementado).** Nuevo extra
> **`[gui]` = `fastapi` + `uvicorn`** (ADR [0005](decisiones/0005-dependencias-extras.md)), **import
> perezoso**: el núcleo no importa `fastapi`; solo el adaptador `api/` y el subcomando `b2g gui` los
> usan. Cierra la deuda actual (instalados a mano en el prototipo `app/`, no declarados). El **wheel
> incluye el frontend buildeado** (`src/bib2graph/gui/static/`) → `b2g gui` funciona **sin Node**. CI
> suma un **job de frontend** (lint/test/build JS) + build del frontend en el release (B.3 de Nota 12).

`python-louvain` se **declara** (núcleo o extra de análisis), nunca usado sin declarar (lección
7). `notebook`/Jupyter es **solo dev**, jamás runtime (ADR 0005).

**Capa base de vocabulario + modelos** (ADR [0023](decisiones/0023-capa-constants-modelos-schema.md),
`TARGET`): por debajo de todo, `bib2graph.constants` (`Col(StrEnum)`, `CurationStatus(StrEnum)`,
`NetworkKind`) es la **fuente única** de nombres de columna/estados/tipos de red (mata los ~62
string-literals dispersos en 14 archivos, Nota 06 CONSTANTS); `ProvenanceEvent(BaseModel)` —definido
en `schemas.py`, no en un `models.py` separado— es la fuente única del evento de procedencia (Nota 06
MODELS); `schemas.py` aloja también la **única** definición de fila (`PaperRow` ⇄ `CORPUS_SCHEMA`
derivado/verificado, no duplicado a mano). Se **mantiene** la
decisión "`Paper`/`Author`/`Keyword`/`Institution` = vistas derivadas, no tipos". El grafo de
dependencias va **de abajo hacia arriba**: `constants/schemas` → núcleo puro (`corpus`, `cycle`,
`projectors`, `analyzer`) → costuras (`sources`, `foraging` [consume el núcleo de proyección],
`stores`) → `cli`. El núcleo nunca depende de una costura. Ver ROADMAP **Hito R1**.

## 8. Por qué este diseño (mapa a las lecciones de v0)

| Decisión arquitectónica | Anti-patrón de v0 que evita |
|-------------------------|-----------------------------|
| Corpus (tabla Arrow) como contrato | Neo4j *era* el modelo; nada existía sin servidor |
| Núcleo puro sin red en proyección/análisis | Único test era "¿importa el paquete?" |
| OpenAlex backbone (refs/citas gratis) | Enricher S2 estructural: clave embebida, ramas muertas |
| Contratos tipados de costuras | `progress_callback` a métodos que no lo aceptaban |
| Modelo documentado una vez | `Institution.address` / `CITED_BY` inexistentes |
| Solo publicar lo real | Clientes CrossRef/Scopus inicializados y nunca consultados |
| Config inyectada, sin side-effects | Triple `DATABASE_URL`, clave S2 embebida |
| Declarar lo que se importa | `python-louvain` usado pero ausente de `pyproject.toml` |
| Fallar/avisar accionable, nunca no-op silencioso (R5) | `except` anchos que tragan bugs; ramas/params muertos; versión inventada en el Manifest |

> **AS-BUILT R5 — footguns cerrados (Nota 06, catálogo de secundarios).** R5 eliminó los anti-patrones
> que **enmascaran fallos**: el `except Exception` de `detect_communities` (`facade.py`) que tragaba el
> error (ahora solo `ImportError` se re-lanza, lo demás se propaga); el `AttributeError`→exit-3
> "engañoso" (→ pre-check en el borde, §6.3); la **rama muerta** de `_errors.py` (`OSError` con `if/else`
> que hacía lo mismo); el **filtro PRISMA / `.bib` con campo-op/parseo desconocido = no-op silencioso**
> (ahora `ValueError`/warning accionable); el **param muerto `g`** de `cocitation_quality_report`; el
> fallback `_lib_version` `"0.0.0"` (versión inventada en el `Manifest` → `"unknown"`, honesto); y el
> `Literal` duplicado de `NetworkSpec.kind` (→ `NetworkKind`, fuente única). Principio: **sin no-ops
> silenciosos** — el comportamiento silencioso pasa a fallar/avisar accionable o se elimina la rama muerta.

## 9. Tensiones resueltas

1. **Representación interna del corpus:** ✅ tabla Arrow única + wrapper Pydantic (ADR 0006).
2. **Fuente de referencia:** ✅ **OpenAlex** (ADR 0007); BibTeX secundaria. El Enricher deja de
   ser estructural.
3. **Biblioteca viva vs. snapshot inmutable** (abierta en Nota 04 §6.2): ✅ **biblioteca viva
   stateful en DuckDB**; el snapshot pasa a **export** (ADR 0009). Tras el 2º giro, ese sustrato es
   el **`DuckDBBackend` del `Corpus`** (backend por defecto, no un `Store` aparte; ADR 0015) y
   reproducir = re-leer el snapshot, no re-correr la ecuación (ADR 0017). Resuelta a nivel modelo de
   datos.
4. **Wedge** (abierto en Nota 05 §6): ✅ **forrajeo asistido** por estructura bibliométrica
   determinista; la **máquina de tensiones se retira del producto** (ADR 0008/0022), no se difiere.
5. **Agente-native:** ✅ **columna primaria** desde el hito 1 (ADR 0010), ya no extra futuro.
6. **Normalización multilingüe de keywords:** ✅ **thesaurus curado determinista** en V1; fuzzy a
   v0.2 (ADR 0011).
7. **Driver Neo4j:** ✅ irrelevante al modelo; adaptador opt-in post-V1.
8. **`NetworkSpec`:** hook `Networks.build` desde v0.1; API congelada en v0.2 (ADR 0006).

## 10. Estado de la documentación

Los canónicos — [`PRD.md`](PRD.md), este doc, [`API.md`](API.md), [`ROADMAP.md`](ROADMAP/README.md) y los
[ADR 0007–0011](decisiones/) — están **reconciliados** con el giro, y luego con el **2º giro** (ADR
[0015](decisiones/0015-corpus-tabular-backend.md)–[0019](decisiones/0019-concurrencia-diferida.md):
`Corpus` sobre `TabularBackend` con `DuckDBBackend` por defecto, `LoopState`, reproducibilidad por
snapshot, `Source` agnóstico, single-writer). El contrato del CLI agente-native está en el ADR
[0021](decisiones/0021-cli-agente-native-contrato.md). Las notas de proceso ya promovidas viven en
[`_archivo/`](_archivo/). Implementación por hitos: **Hitos 0–6 + 1.5 construidos** (núcleo,
biblioteca viva, fuentes, forrajeo y el CLI `b2g`). Tras el **red-team de la
[Nota 06](Notas/06-critica-as-built-v0.2.md)** y el **nuevo modelo conceptual bloqueado por el PO**
(scent bibliométrico sin IA, FSM cíclico, identidad-vs-procedencia, capa constants/schemas), este doc
describe el **TARGET**; la brecha con el AS-BUILT se cierra con la **tanda de remediación R1–R5** del
[`ROADMAP.md`](ROADMAP/README.md), **antes** de los Hitos 7–11. (Ya no se afirma "v0.2 con capacidades
completas": ese claim era parte de la sobre-venta que la Nota 06 corrigió.)
