# ARQUITECTURA — bib2graph (objetivo / north star)

> Arquitectura **deseada** de la V1, no un estado as-built. El as-built de v0 (con sus
> problemas) está en [`Notas/03-referencia/arquitectura-v0.md`](Notas/03-referencia/arquitectura-v0.md)
> y NO debe tomarse como objetivo. Fecha: 2026-06-15.
>
> Reconcilia este doc con el **giro** (`Notas/04`–`07`) y el [`PRD.md`](PRD.md) reescrito.
> Decisiones que lo sustentan, en [`decisiones/`](decisiones/): tabla canónica Arrow
> [0006](decisiones/0006-tabla-canonica-y-networkspec.md); **OpenAlex backbone**
> [0007](decisiones/0007-openalex-backbone.md); **wedge = forrajeo**
> [0008](decisiones/0008-wedge-forrajeo.md); **biblioteca viva en DuckDB**
> [0009](decisiones/0009-biblioteca-viva-duckdb.md); **agente-native columna**
> [0010](decisiones/0010-agente-native-columna.md); **thesaurus**
> [0011](decisiones/0011-thesaurus-multilingue.md). El método bibliométrico está en
> [`metodología.md`](metodología.md).
>
> **Cambios mayores respecto a la versión previa de este doc:** la fuente de referencia pasó de
> **BibTeX a OpenAlex** (ADR 0007); la persistencia por defecto pasó de **snapshot inmutable /
> InMemoryStore** a un **`Store` stateful en DuckDB** (biblioteca viva; ADR 0009), con el
> snapshot demotado a *export*; se agregaron al núcleo el **forrajeo/chaining** y el **thesaurus
> multilingüe**.

## 1. Idea en un párrafo

`bib2graph` es **un núcleo puro rodeado de costuras**. El **núcleo puro** opera sobre un
`Corpus` en memoria (una **tabla canónica Arrow**) y nunca hace red ni servidores: proyecta el
corpus a redes, las analiza y las exporta, y normaliza/cura la tabla. Alrededor hay costuras:
**`Source`** (sembrar el corpus — *OpenAlex por defecto* desde una ecuación de búsqueda; BibTeX
secundaria), el **forrajeo/chaining** (expandir el corpus rankeando candidatos por *information
scent*), **`Store`** (persistir — *DuckDB stateful por defecto*: la **biblioteca viva**) y
`Enricher` (señal extra, opt-in). El flujo **no es lineal**: es el **ciclo iterativo** de
exploración (sembrar → forrajear → curar → la idea muta → re-sembrar), y la biblioteca viva en
DuckDB es el sustrato que lo sostiene entre corridas.

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
                        │  (stateful)  │  corridas, log de procedencia + LoopState (ADR 0016).
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
secundarias/futuras. La **máquina de tensiones** (inserción de IA nº2) es **v2** (ADR 0008). Solo
se publica lo que existe.

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
solo `is_seed` (rediseño validado en el sandbox IED).

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
- **Informe de calidad** de la co-citación según [`metodología.md`](metodología.md) §4, con
  umbrales **configurables**.

### 3.4 `Exporter` — resultados → archivos

GraphML y CSV (nodos y aristas). I/O de salida puro y predecible, sin backend.

### 3.5 Forrajeo / chaining (inserción de IA nº1)

Orquestación pura sobre la costura `Source`: dado el corpus actual, computa candidatos por
**backward chaining** (referencias de las semillas) y **forward chaining** (citantes), y los
**rankea por *information scent***. El *information scent* concreto (decidido en el Hito 5, ADR
[0020](decisiones/0020-metodo-forrajeo-scent-filtros-reject.md)) es la **frecuencia de enlace de
cita con el corpus** —backward: nº de papers del corpus que listan al candidato; forward: nº de
papers del corpus a los que el candidato cita— una **función pura sobre conteos**, **no**
acoplamiento bibliográfico, co-citación ni centralidad de red. Reglas (ADR 0008, nota 07):
**profundidad 1 por defecto** (`depth>1` lanza `NotImplementedError`); **preview de crecimiento**
("sumaría ~N papers") **sin red** —backward exacto local; forward no estimable sin fetch
(`forward_requires_fetch`)— y **tope** (`max_candidates`) configurable antes de traer; **pool
cortés** de OpenAlex. Forward exige `source.fetch_citing(...)` (capacidad de `OpenAlexSource`, **no**
del Protocol `Source`). Un **paso opcional de IA** (`explain_candidate`, stub gateado en `[llm]`)
explica *por qué* un candidato es relevante — **sin decidir** por el humano.

### 3.6 `Preprocessor` — normalización (núcleo)

Determinístico e idempotente: canonicalización **conservadora** de nombres de autor
(`authors_id`: lowercase + acentos + espacios) y `language` (ISO 639-1 primario), y
**normalización de keywords vía thesaurus multilingüe** (en/es/pt; dict `canónico → aliases` en
JSON portable; ADR 0011). Lo *fuzzy* (dedup aproximado de autores) vive en el extra `[dedup]`;
el **fallback semántico/LLM del thesaurus** es v0.2.

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

### 4.2 `Enricher` — señal extra (opt-in)

Con OpenAlex como backbone, **deja de ser estructural** (ADR 0007). Queda opt-in para:
**resolver `references` a DOI canónico** (OpenAlex las da como URLs internas — T8 del sandbox) y
el **segundo nivel de fetch** (citantes con sus citas) que habilita la co-citación. S2/CrossRef/
Scopus: futuras. Reglas: config inyectada (nunca embebida), sin ramas muertas, rate limit y
reintentos sin perder papers.

### 4.3 `Store` / backend de persistencia (biblioteca viva)

**Por defecto: `DuckDBBackend` stateful** (ADR 0009 reencuadrado por
[0015](decisiones/0015-corpus-tabular-backend.md)): la **biblioteca viva** es el **backend por
defecto del `Corpus`**, no un `Store` aparte. Persiste el contenido Arrow **entre corridas**, más
tablas de **procedencia, decisiones de curación** (aceptar/rechazar) y el **`LoopState`** (ADR
[0016](decisiones/0016-maquina-estados-lazo.md)). Muta por SQL `UPDATE`/`MERGE` por `id` (no copia
en memoria). Soporta query SQL. Es **núcleo**, no extra. **Una investigación = un archivo
`.duckdb`** (single-writer; concurrencia diferida, ADR
[0019](decisiones/0019-concurrencia-diferida.md)).

El **snapshot** es un **export sellado** del estado vivo (ver §6.2), no la persistencia en sí;
`ParquetStore` puede servir como **formato de export/intercambio**. La costura `Store` sigue
siendo el punto de extensión para destinos externos: **`ZoteroStore`** (sincronizar la biblioteca
con una colección Zotero) es **opt-in en V1.1** (`[zotero]`); **`Neo4jStore`** es adaptador opt-in
post-V1 (`[neo4j]`): un destino más, **ya no el sustrato** (ADR 0002).

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

La no-linealidad se modela como una **máquina de estados explícita** (`LoopState`:
`SEEDED → FORAGED → FILTERED → BUILT`, con **transiciones permisivas** — re-sembrar desde casi
cualquier estado; ADR [0016](decisiones/0016-maquina-estados-lazo.md)). El `LoopState` vive en el
backend persistente (`DuckDBBackend`), no en el `Corpus` efímero, y se expone con `b2g status`:
humanos e IAs comparten el mismo mapa del lazo.

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
   global obligatoria `--store`, y un comando Click por subcomando que sólo parsea flags y delega.
2. **Capa de funciones núcleo** (`run_<cmd>(store_path, ...)` en cada módulo de comando):
   **testeable sin Click**, contiene la lógica del subcomando. El ROADMAP testea esta función, no
   el parser de Click.
3. **Capa de envelope/errores** (`cli/_envelope.py`, `cli/_errors.py`, `cli/_store.py`): el
   envelope JSON versionado (`schema="1"`) compartido y el decorador `@handle_errors` que **mapea
   errores a exit codes por tipo de excepción** (`DataError`→2, `ImportError`/`AttributeError`/
   `NotImplementedError`→3, `httpx.HTTPError`→4, `StoreLockedError`/`OSError`→5).

Son **11 subcomandos** (`seed`, `chain`, `filter`, `build`, `export`, `snapshot`, `status`,
`inspect`, `validate`, `accept`, `reject`); `build`/`export` están **separados** y el `LoopState`
transiciona automáticamente por comando (ADR 0021). El error de uso (p. ej. falta `--store`) sale
**sin envelope** (Click aborta el parseo: stderr + exit 1).

## 7. Layout de dependencias (extras)

```
core         pyarrow, pydantic, networkx, click, tqdm,
             duckdb, <cliente OpenAlex>                 (siempre; biblioteca viva + backbone)
[zotero]     pyzotero                                   ─┐
[s2]         (cliente Semantic Scholar)                  │ costuras / capacidades opcionales
[neo4j]      neomodel / driver oficial                   │ (futuras marcadas como no
[viz]        matplotlib, seaborn                          │ implementadas)
[dedup]      rapidfuzz / splink                          │
[llm]        (cliente LLM para B4 y thesaurus fuzzy v0.2)─┘
```

`python-louvain` se **declara** (núcleo o extra de análisis), nunca usado sin declarar (lección
7). `notebook`/Jupyter es **solo dev**, jamás runtime (ADR 0005).

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

## 9. Tensiones resueltas

1. **Representación interna del corpus:** ✅ tabla Arrow única + wrapper Pydantic (ADR 0006).
2. **Fuente de referencia:** ✅ **OpenAlex** (ADR 0007); BibTeX secundaria. El Enricher deja de
   ser estructural.
3. **Biblioteca viva vs. snapshot inmutable** (abierta en Nota 04 §6.2): ✅ **biblioteca viva
   stateful en DuckDB**; el snapshot pasa a **export** (ADR 0009). Tras el 2º giro, ese sustrato es
   el **`DuckDBBackend` del `Corpus`** (backend por defecto, no un `Store` aparte; ADR 0015) y
   reproducir = re-leer el snapshot, no re-correr la ecuación (ADR 0017). Resuelta a nivel modelo de
   datos.
4. **Wedge** (abierto en Nota 05 §6): ✅ **forrajeo asistido**; tensiones a **v2** (ADR 0008).
5. **Agente-native:** ✅ **columna primaria** desde el hito 1 (ADR 0010), ya no extra futuro.
6. **Normalización multilingüe de keywords:** ✅ **thesaurus curado determinista** en V1; fuzzy a
   v0.2 (ADR 0011).
7. **Driver Neo4j:** ✅ irrelevante al modelo; adaptador opt-in post-V1.
8. **`NetworkSpec`:** hook `Networks.build` desde v0.1; API congelada en v0.2 (ADR 0006).

## 10. Estado de la documentación

Los canónicos — [`PRD.md`](PRD.md), este doc, [`API.md`](API.md), [`ROADMAP.md`](ROADMAP.md) y los
[ADR 0007–0011](decisiones/) — están **reconciliados** con el giro, y luego con el **2º giro** (ADR
[0015](decisiones/0015-corpus-tabular-backend.md)–[0019](decisiones/0019-concurrencia-diferida.md):
`Corpus` sobre `TabularBackend` con `DuckDBBackend` por defecto, `LoopState`, reproducibilidad por
snapshot, `Source` agnóstico, single-writer). El contrato del CLI agente-native está en el ADR
[0021](decisiones/0021-cli-agente-native-contrato.md). Las notas de proceso ya promovidas viven en
[`_archivo/`](_archivo/). Implementación por hitos en curso (**Hitos 0–6 + 1.5 terminados**: núcleo,
biblioteca viva, fuentes, forrajeo y el CLI `b2g`; v0.2 con capacidades completas); ver
[`ROADMAP.md`](ROADMAP.md).
