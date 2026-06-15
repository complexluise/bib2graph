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
                        │    STORE    │  persistencia POR DEFECTO (biblioteca viva)
                        │ DuckDB      │  stateful: acepta/rechaza, crece entre corridas,
                        │ (stateful)  │  log de procedencia. Snapshot = export sellado.
                        │ Zotero(1.1) │  Neo4j adaptador opt-in post-V1.
                        └─────────────┘
```

Lo marcado `(BibTeX 2ª)`, `Zotero(1.1)`, `Neo4j` son costuras secundarias/futuras. La **máquina
de tensiones** (inserción de IA nº2) es **v2** (ADR 0008). Solo se publica lo que existe.

## 3. El núcleo (puro, sin red ni servidores)

Dependencias del núcleo puro: `pyarrow`, `pydantic`, `networkx`, `click`, `tqdm`. **Nada de red
ni servidores** en proyección/análisis/normalización: todo el núcleo es unitariamente testeable
con tablas sintéticas. (El `Source` OpenAlex y el `Store` DuckDB se instalan por defecto y sí
hacen I/O, pero son **costuras**: el núcleo puro no depende de ellas — ver §4.)

### 3.1 `Corpus` — el contrato central (tabla canónica Arrow)

El `Corpus` es la **única fuente de verdad del modelo** y el formato que circula por el
pipeline. Internamente es **una sola tabla Arrow** (`pa.Table`) con schema fijo por paper,
validada por el wrapper público con **Pydantic v2** (ADR 0006). `Paper`/`Author`/`Keyword`/
`Institution` **no son tipos del modelo**: son **vistas derivadas** vía `groupby + explode`.

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
**rankea por *information scent*** (acoplamiento/co-citación, centralidad). Reglas (ADR 0008,
nota 07): **profundidad 1 por defecto**, opt-in a 2; **preview de crecimiento** ("sumaría ~N
papers") y **tope** configurable antes de traer; **pool cortés** de OpenAlex. Un **paso opcional
de IA** explica *por qué* un candidato es relevante — **sin decidir** por el humano. La
distinción importa: el chaining para **construir redes** (coupling/co-citación) usa refs/citas
ya presentes y **no agranda** el set; el chaining para **crecer el corpus** (snowballing) es el
que aplica profundidad.

### 3.6 `Preprocessor` — normalización (núcleo)

Determinístico e idempotente: canonicalización de nombres de autor, periodización, y
**normalización de keywords vía thesaurus multilingüe** (en/es/pt; dict `canónico → aliases` en
JSON portable; ADR 0011). Lo *fuzzy* (dedup aproximado de autores) vive en el extra `[dedup]`;
el **fallback semántico/LLM del thesaurus** es v0.2.

## 4. Las costuras (puntos de extensión)

Contratos tipados y estables (Protocols / ABCs; ver [`API.md`](API.md)). El núcleo no conoce
implementaciones concretas: las recibe inyectadas.

### 4.1 `Source` — sembrar un corpus

Convierte una entrada externa en `Corpus`. **Implementación de referencia: OpenAlex** (ADR
0007): traduce la **ecuación de búsqueda** a una query OpenAlex, muestra la **query ejecutada +
reporte de traducción** (qué mapeó limpio, qué se aproximó, qué se descartó), y trae metadatos +
`references_id` + `cited_by_id`. Power-users pueden pasar query OpenAlex nativa (escape hatch).
**`BibtexSource` es `Source` secundaria** para sembrar desde *pearls* conocidos (acceso
defensivo a campos; el sandbox documenta un bug de `bibtexparser` que exige un pre-procesador).
RIS/CSV: futuras, no publicadas.

### 4.2 `Enricher` — señal extra (opt-in)

Con OpenAlex como backbone, **deja de ser estructural** (ADR 0007). Queda opt-in para:
**resolver `references` a DOI canónico** (OpenAlex las da como URLs internas — T8 del sandbox) y
el **segundo nivel de fetch** (citantes con sus citas) que habilita la co-citación. S2/CrossRef/
Scopus: futuras. Reglas: config inyectada (nunca embebida), sin ramas muertas, rate limit y
reintentos sin perder papers.

### 4.3 `Store` — persistencia (biblioteca viva)

**Por defecto: `DuckDBStore` stateful** (ADR 0009): la **biblioteca viva**. Persiste la tabla
Arrow **entre corridas**, más tablas de **procedencia y decisiones de curación**
(aceptar/rechazar). Soporta query SQL sobre el corpus. Es **núcleo**, no extra. El **snapshot**
es un **export sellado** del estado vivo (ver §6.2), no la persistencia en sí; `ParquetStore`
puede servir como **formato de export/intercambio**. **`ZoteroStore`** (sincronizar la
biblioteca con una colección Zotero) es **costura opt-in en V1.1** (`[zotero]`). **`Neo4jStore`**
es adaptador opt-in post-V1 (`[neo4j]`): un destino de persistencia más, **ya no el sustrato**
(ADR 0002).

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

## 6. Configuración, persistencia y reproducibilidad

### 6.1 Configuración inyectada

- **Una sola fuente de configuración**, construida explícitamente y pasada a quien la necesita.
  **Sin efectos de import** (en v0, importar seteaba `config.DATABASE_URL`).
- **Sin secretos embebidos** (en v0 había triple `DATABASE_URL` y clave S2 hardcodeada).
- Credenciales y el **email del pool cortés de OpenAlex** se inyectan por config/CLI o entorno.

### 6.2 Persistencia por defecto: biblioteca viva en DuckDB + snapshot exportable

La persistencia por defecto es **stateful**: un `DuckDBStore` que conserva el corpus **entre
corridas** (ADR 0009). Reproducibilidad por **historia auditable** (el log de procedencia: qué
ecuación, qué salto de chaining, qué decisión humana, cuándo) **+ snapshot exportable**.

El **snapshot** es un **export sellado** del estado vivo en un instante: `corpus.parquet` + un
`manifest.json` con `schema_version`, `corpus_hash`, `lib_version`, `openalex_version`/fecha,
`sources`, `chaining` (profundidad, topes), `preprocessors`, `filters` (conteos PRISMA),
`created_at`. Sirve para **reportar (PRISMA / vom Brocke) y reproducir**, y se versiona en
git-lfs/DVC. A diferencia del diseño previo, el snapshot **no es** la persistencia: es una **foto
derivable** de una biblioteca que sigue viva.

### 6.3 CLI agente-native como columna primaria (ADR 0010)

La CLI es **superficie primaria desde el primer comando**, no un adorno futuro: cada subcomando
con **doble salida** (humana + `--json` estable/versionado), **exit codes** claros (`0` éxito ·
`1` uso · `2` datos · `3` dependencia faltante · `4` red no disponible · `5` store/snapshot
corrupto), **errores accionables**, `--help` rico y **eficiencia de tokens**. **Sin estado entre
invocaciones**: el estado vive en el `Store` DuckDB, no en la sesión. Tool schemas JSON / MCP son
trabajo posterior, pero la API se **diseña con estos principios desde el hito 1**.

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
   stateful en DuckDB**; el snapshot pasa a **export** (ADR 0009). Resuelta a nivel modelo de
   datos.
4. **Wedge** (abierto en Nota 05 §6): ✅ **forrajeo asistido**; tensiones a **v2** (ADR 0008).
5. **Agente-native:** ✅ **columna primaria** desde el hito 1 (ADR 0010), ya no extra futuro.
6. **Normalización multilingüe de keywords:** ✅ **thesaurus curado determinista** en V1; fuzzy a
   v0.2 (ADR 0011).
7. **Driver Neo4j:** ✅ irrelevante al modelo; adaptador opt-in post-V1.
8. **`NetworkSpec`:** hook `Networks.build` desde v0.1; API congelada en v0.2 (ADR 0006).

## 10. Pendiente de reconciliar

[`API.md`](API.md) §1 (modelo `Corpus`) y §§ de costuras todavía reflejan el diseño previo
(BibTeX/S2, InMemoryStore). Reconciliarlo con este doc y los ADR 0007–0011 es el siguiente paso
de documentación (ver [`ROADMAP.md`](ROADMAP.md) y [`PRD.md`](PRD.md) §11).
