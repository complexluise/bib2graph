# Exploración de arquitecturas alternativas

> **Estado:** borrador para discusión. No es propuesta cerrada; cada sección termina con
> preguntas abiertas. La idea es comparar formas de modelar el `Corpus` y el pipeline para
> elegir antes de reescribir `docs/ARCHITECTURE.md` y `docs/API.md`.
>
> **Fecha:** 2026-06-14.
> **Audiencia objetivo acordada:** investigador académico (ad-hoc, baja fricción) **y**
> herramienta interna repetible (reproducibilidad, versionado). Las dos cosas a la vez:
> la combinación más exigente.
> **Stack acordado:** Arrow como contrato de tabla + DuckDB opcional para queries.
> **Reproducibilidad acordada:** snapshot inmutable con hash + metadatos.
> **Decisiones vigentes que NO se renuegan** (siguen valiendo porque son de producto, no de
> modelo): ADRs 0001 (herramienta reutilizable), 0002 (núcleo agnóstico al backend),
> 0003 (persistencia opcional), 0004 (enriquecimiento opcional), 0005 (extras).

## 0. Por qué explorar (qué no cierra del diseño actual)

El `Corpus` como cuatro `dict` indexados + dataclasses (`Paper`, `Author`, `Keyword`,
`Institution`) funciona como contrato, pero tiene costos concretos:

- **Merge, dedup e idempotencia** requieren escribir código a mano cuatro veces (una por
  entidad) y luego reglas para reconciliar listas (`author_ids`, `keyword_ids`,
  `reference_dois`). El código de `Corpus.merge` actual va a ser ~150 líneas solo para
  algo que un `groupby` resuelve.
- **Parsing de campos opcionales** se repite en `BibtexSource`, en cada `Enricher`, en
  `deduplicate_authors`, en `deduplicate_keywords`. El "acceso defensivo" del AGENTS.md
  no contesta *dónde* se normaliza; lo hace cada uno por su lado.
- **`is_seed` y `reference_dois` como campos de `Paper`** mezclan datos bibliográficos
  con estado de pipeline. Esto es el síntoma de no separar "lo que vino" de "cómo se
  procesó".
- **No hay artefacto serializable nativo**: un corpus no se puede guardar a parquet y
  volver a leer, ni hacer un diff entre dos corpus. Para el caso "herramienta interna
  repetible" eso es bloqueante.
- **La representación interna es 4 diccionarios, no una tabla**, así que cualquier
  analizador nuevo (Pandas, Polars, SQL, spark) tiene que mapear de/a el `Corpus` cada
  vez.

Bibliometrix (R) lo resolvió hace 8 años: **un data frame "bibliométrico" canónico**
(`AU`, `DE`, `CR`, `PY`, `SO`, `C1`, `AB`, `DI`…) es **la representación intermedia
única**. Todo el pipeline se hace sobre esa tabla. Las entidades OO son derivadas. Eso
es lo que vamos a evaluar acá en versión Python/Arrow.

---

## 1. Candidatas

Cuatro arquitecturas a comparar. Las tres primeras son reescrituras de la
representación del `Corpus`; la cuarta cambia la forma del pipeline entero.

### A. "Bibliometrix-style": tabla canónica única, todo derivado

**Idea central.** Hay **una sola tabla Arrow** (`CorpusTable`) con una fila por paper
y columnas canónicas: `id`, `doi`, `title`, `year`, `abstract`, `is_seed`,
`authors_raw` (lista[str]), `authors_id` (lista[str] ya canónica),
`keywords_raw`, `keywords_id`, `institutions_raw`, `institutions_id`,
`references_doi` (lista[str]), `source`, `language`, `provenance` (json con
fuente/fecha/enricher). Las entidades `Author`, `Keyword`, `Institution` son **vistas
derivadas** vía `groupby` sobre la tabla. El `Corpus` es un *wrapper* delgado sobre
la tabla con helpers (`seeds()`, `add_paper()`, `merge()`, `to_arrow()`,
`from_arrow()`).

**Pipeline.**

```
1. Source.load(path)            → CorpusTable (append rows, is_seed=True)
2. [Enricher].enrich(table)     → CorpusTable (update rows, no rows nuevas)
3. [Preprocessor]               → CorpusTable (normaliza, dedup fuzzy opcional)
4. [Snapshot] seal()            → CorpusSnapshot (tabla + hash + manifest)
5. Network.from(table, kind=...)→ nx.Graph (función pura)
6. Analyzer / Exporter
```

**Pros.**

- ~50% menos código que la v1 en merge/dedup: groupby y joins hacen el trabajo.
- Interoperabilidad nativa con pandas/polars/duckdb (Arrow es el denominador común).
- **Serialización trivial** (`pa.parquet.write_table`) → el snapshot inmutable es
  un `parquet` + un `manifest.json` con hash y parámetros. Reproducibilidad casi
  gratis.
- Tests unitarios sobre tablas chiquitas con resultados conocidos son inmediatos.
- `is_seed` y `provenance` son **columnas de la tabla**, no atributos de dataclass:
  no contaminan la entidad con estado de pipeline.

**Contras.**

- "Tipos" se pierden: una columna `list[str]` no enforza que `keyword_ids` sean
  ids válidos de `Keyword`. Antes lo decía el tipo. Solución: una capa de
  *schemas* Arrow validados en `from_arrow()` (pydantic / msgspec / pyarrow
  schema).
- Para casos de uso muy OO (ej. mutar un autor y propagar) sigue siendo menos
  cómodo que tener `Author` como objeto. Pero esos casos son raros en
  bibliometría: el "objeto" natural es la fila de la tabla.
- Cambio grande: hay que reescribir `Corpus` desde cero. Pero está en Hito 1, no
  hay código todavía → costo bajo.

**Compatibilidad con ADRs 1–5.** 1 ✅ · 2 ✅ (DuckDB opcional como store) ·
3 ✅ (Store = tabla Arrow o tabla DuckDB) · 4 ✅ (Enricher opera sobre la tabla) ·
5 ✅ (pandas/Arrow/DuckDB conviven como extras).

**Compatibilidad con audiencia doble.** Académico: `bib2graph.load("x.bib")` →
tabla → 4 redes con un click. Repetible: snapshot = `parquet` + `manifest.json`,
versionable en git-lfs o DVC. ✅.

**Preguntas abiertas.**

- ¿Pydantic / msgspec para validar el schema, o pyarrow schema puro?
- ¿Las listas (`authors_id`, `references_doi`) como columnas anidadas Arrow
  (`pa.list_`) o como string JSON / repeated columns? Las anidadas son más
  expresivas pero menos compatibles con pandas viejos.
- ¿La normalización de autores (parsing de "Smith, J. y García, M.") vive en
  Source o en un Preprocessor? **Propuesta:** en Source para la primera versión
  cruda, y en Preprocessor para la canonización con S2.

---

### B. "Event sourcing" / append-only log

**Idea central.** El `Corpus` es un **log inmutable de eventos** (`paper_added`,
`author_normalized`, `enricher_added_refs`, `seed_promoted`, …). El estado
"actual" se reconstruye *folding* el log. Cada evento lleva timestamp, autor del
proceso y snapshot opcional.

**Pros.**

- Reproducibilidad perfecta: reproducir un corpus es re-correr el log.
- Auditoría completa: sabés exactamente cuándo y cómo se agregó cada fila.
- Natural para "herramienta interna repetible".

**Contras.**

- **Complejidad enorme** para un pipeline que en su mayoría es lineal.
- Reconstruir el estado actual cada vez (o mantener índices materializados) es
  costoso.
- Casi nadie en el ecosistema bibliométrico lo hace. Es reinventar la rueda.
- Difícil de testear unitariamente: los tests son sobre el fold, no sobre el
  estado.

**Compatibilidad.** Sobrevive, pero **recomendación: descarte**. La audiencia
académica no lo va a apreciar, y la repetible lo consigue más barato con un
snapshot inmutable (A) + un `manifest.json` con la lista de operaciones
realizadas. Es el mismo poder, 10% de la complejidad.

**Preguntas abiertas.** ¿Hay alguna razón real (legal, regulatoria) para querer
auditoría por evento? Si no, descartar.

---

### C. "Grafo de primera": nx.Graph como contrato central

**Idea central.** Invertir la jerarquía: el `Corpus` **es** un `networkx.MultiDiGraph`
donde nodos = entidades, aristas = relaciones con tipo. Los "proyectores" pasan a
ser subgrafos; los "analizadores" son algoritmos sobre el grafo completo.

**Pros.**

- Co-citación, acoplamiento bibliográfico, citación y colaboración conviven
  naturalmente en un solo grafo heterogéneo.
- NetworkX ya da el álgebra (componer, subgrafo, induced subgraphs).

**Contras.**

- **Es justamente lo que v0 hacía mal**: el grafo como modelo de datos te obliga
  a tener un "loader" (que era Neo4j o un dict) y "todo depende del grafo".
  Reproducir v0 con otra tech.
- Tira a la basura la lección 2 de `lecciones-v0.md` ("el núcleo puro es la
  victoria de testabilidad"). Para testear un grafo necesitás cargarlo entero;
  con tabla testeás por slice.
- Sin biyección natural a parquet/Arrow → vuelve a perder el snapshot.
- La audiencia académica piensa en "papers", "autores", "red", no en "nodos
  con label".

**Compatibilidad.** Reta directamente a ADR 0002 (núcleo agnóstico al backend).
**Recomendación: descarte**. La opción A ya te da los beneficios de composición
sin atarte al grafo.

**Preguntas abiertas.** ¿Hay alguna red que **solo** se piense como heterogénea
(eg. redes multiplex autor-institución-país) que justifique esto? Si la respuesta
es sí, esa red se construye como `MultiDiGraph` **derivado** de la tabla (A), no
como sustrato.

---

### D. "Por-red": cada red es un config, no una vista

**Idea central.** En vez de un `Corpus` único y proyectores, el usuario
configura **cada red por separado** y la herramienta resuelve fuentes
faltantes a demanda. El `Corpus` es solo un *seed* de papers; cada `NetworkSpec`
declara qué necesita, qué filtros aplica, qué algoritmo de clustering, qué
layout, qué umbrales.

```yaml
networks:
  - kind: cocitation
    from: corpus://semiconductores-v3
    min_weight: 2
    min_year: 2000
    clustering: louvain
    layout: vos
  - kind: author_collab
    from: corpus://semiconductores-v3
    min_weight: 3
    clustering: louvain
    layout: fr
```

**Pros.**

- Coherente con cómo trabaja el investigador académico: piensa por red.
- Hace explícitas las decisiones metodológicas (umbrales, períodos, etc.) y
  las hace **reproducibles** por construcción.
- Coexiste bien con A: la `NetworkSpec` se evalúa sobre la tabla Arrow.

**Contras.**

- El archivo YAML es un DSL nuevo que hay que mantener.
- Para un uso muy interactivo (un script en Jupyter) es más fricción que
  ayuda.
- Implica cambios en CLI y en API pública.

**Compatibilidad.** Compatible con A y **recomendable como segunda capa** sobre
A. La pregunta es si lo metemos en v1 o lo dejamos para v2.

**Preguntas abiertas.** ¿La audiencia académica prefiere defaults implícitos
(`b2g networks` → te armo las 4 razonables) o configuración explícita
(`b2g networks --spec redes.yaml`)? Mi corazonada: ambos, con un modo
`--quick` para el primero y `--spec` para el segundo.

---

## 2. Tabla comparativa

| Criterio | A. Tabla canónica | B. Event sourcing | C. Grafo de primera | D. Por-red (config) |
|---|---|---|---|---|
| Complejidad de implementación | Media | Alta | Alta | Media |
| Testabilidad del núcleo | Alta | Baja | Media | Alta (si se apoya en A) |
| Snapshot inmutable nativo | ✅ parquet trivial | ✅ pero overkill | ❌ requiere serialización custom | ✅ si se apoya en A |
| Interoperabilidad pandas/polars/duckdb | ✅ nativa | ❌ | ❌ | ✅ si se apoya en A |
| Coherencia con lecciones v0 | ✅ refuerza 2, 4, 6 | ⚠️ neutral | ❌ revive 1 (grafo como modelo) | ✅ refuerza 1, 5 |
| Audiencia académica (UX) | ✅ simple | ❌ sobreingeniería | ⚠️ requiere conocer el grafo | ✅ con modo quick |
| Audiencia repetible (reproducibilidad) | ✅ muy alta | ✅✅ teórica, práctica costosa | ⚠️ media | ✅✅ si se apoya en A |
| Cumple ADRs 1–5 | ✅ | ✅ | ❌ rompe 0002 | ✅ |
| Costo de reescritura de ARCHITECTURE.md | Medio (sección 3 entero) | Alto | Alto | Medio |

## 3. Recomendación (provisional, a discutir)

**Adoptar A como base + D como segunda capa** (con `--quick` por default para
no asustar al académico). Descartar B y C.

Justificación:

- A resuelve el dolor concreto (merge, dedup, snapshot, interoperabilidad) sin
  romper los ADRs vigentes.
- Arrow/DuckDB es exactamente lo que acordamos, y A es la arquitectura donde
  ese stack luce natural.
- D no compite con A, se apoya: el `NetworkSpec` se evalúa sobre la tabla de A.
  Es la pieza que conecta "el modelo es chato" con "el investigador piensa
  por red".
- B y C son sobreingeniería: B no aporta más poder que A + manifest; C revive
  la v0 que ya decidimos no repetir.

## 4. Sketches de las piezas centrales (solo A, para discutir)

### 4.1 `Corpus` → `CorpusTable`

```python
import pyarrow as pa

PAPERS_SCHEMA = pa.schema([
    ("id", pa.string()),                 # id interno estable
    ("doi", pa.string()),                # nullable
    ("title", pa.string()),
    ("year", pa.int32()),
    ("abstract", pa.string()),
    ("is_seed", pa.bool_()),
    ("source", pa.string()),
    ("language", pa.string()),
    ("authors_raw", pa.list_(pa.string())),
    ("authors_id", pa.list_(pa.string())),
    ("keywords_raw", pa.list_(pa.string())),
    ("keywords_id", pa.list_(pa.string())),
    ("institutions_raw", pa.list_(pa.string())),
    ("institutions_id", pa.list_(pa.string())),
    ("references_doi", pa.list_(pa.string())),
    ("provenance", pa.string()),         # json: {source, fetched_at, enricher}
])

class Corpus:
    """Wrapper delgado sobre una tabla Arrow + un manifest."""
    table: pa.Table
    manifest: Manifest   # hash, sources, params, schema_version

    @classmethod
    def from_arrow(cls, table: pa.Table) -> "Corpus": ...
    def to_arrow(self) -> pa.Table: ...
    def seeds(self) -> pa.Table: ...   # is_seed == True
    def add_paper(self, row: dict) -> "Corpus": ...   # devuelve nuevo Corpus
    def merge(self, other: "Corpus") -> "Corpus": ... # groupby id/doi
    def seal(self) -> "CorpusSnapshot": ...            # hash + parquet
```

Las entidades `Author`, `Keyword`, `Institution` dejan de existir como tales
en el modelo. Son **vistas materializadas** (`pa.Table` derivada por
`groupby` + `explode`) que el `Projector` calcula si las necesita. Esto
mantiene el "modelo de dominio se documenta una vez" (lección 4): el dominio
es la tabla, no cuatro dataclasses divergentes.

### 4.2 Costuras, redefinidas chiquitas

- `Source.load(path) -> Corpus`  (idem hoy)
- `Enricher.enrich(corpus) -> Corpus` (idem hoy, pero opera sobre la tabla)
- `Preprocessor` (nuevo, núcleo): `normalize(corpus, *, ruleset) -> Corpus`
  — thesaurus, periodización, canónica de nombres. Idempotente.
- `Store` (idem hoy, pero la implementación por default escribe parquet; la
  `[neo4j]` mapea tabla → grafo)
- `NetworkSpec` (nuevo, segunda capa de D): declarativa, se evalúa sobre un
  `Corpus` sellado.

### 4.3 Snapshot inmutable

```python
@dataclass(frozen=True)
class CorpusSnapshot:
    path: Path              # carpeta con corpus.parquet + manifest.json
    manifest: Manifest

    @property
    def corpus(self) -> Corpus:
        return Corpus.from_arrow(parquet.read_table(self.path / "corpus.parquet"))
```

`Manifest` lleva: schema_version, hash de la tabla, fuentes y sus fechas,
parámetros de los preprocess aplicados, versión de la lib. Reproducibilidad
casi gratis: `b2g run --snapshot ./corpus-v3 --spec redes.yaml` puede
versionarse en git-lfs y la corrida queda atada al estado del corpus.

### 4.4 `NetworkSpec` (capa D, opt-in)

```python
@dataclass(frozen=True)
class NetworkSpec:
    kind: Literal["cocitation", "author_collab", "institution_collab",
                  "keyword_cooccurrence"]
    min_weight: int = 1
    min_year: int | None = None
    max_year: int | None = None
    clustering: Literal["louvain", "label_prop", "greedy_modularity"] | None = None
    layout: Literal["spring", "kamada_kawai", "circular"] | None = None
    seed_filter: Literal["all", "seeds_only"] = "seeds_only"
```

`Networks.build(snapshot, spec) -> NetworkArtifact` (grafo + métricas +
clusters + layout en uno). **Modo quick**: `Networks.quick(snapshot)` te arma
las 4 specs razonables y las devuelve.

## 5. Lo que cambia respecto al roadmap actual

Si adoptamos A+D, el `ROADMAP.md` se reorganiza así (los hitos se mantienen, se
ajusta el alcance interno):

- **Hito 1 — Núcleo: tabla `Corpus`** (en vez de 4 dataclasses).
  - Define el schema Arrow, `Corpus` wrapper, `Manifest`, `seal()`.
  - Tests sobre tablas chiquitas con resultados conocidos.
- **Hito 2 — Proyectores + analizadores + exportadores.**
  - Las "vistas" `Author`/`Keyword`/`Institution` son helpers, no tipos del
    modelo.
- **Hito 3 — `BibtexSource`** (igual).
- **Hito 4 — `InMemoryStore` (parquet) + CLI quick mode.**
- **Hito 5 — `Preprocessor` núcleo + `[dedup]`** (la normalización canónica
  entra al núcleo, lo fuzzy queda en el extra).
- **Hito 6 — `SemanticScholarEnricher`** (igual, opera sobre la tabla).
- **Hito 7 — `Neo4jStore`** (mapea tabla → grafo, no grafo → tabla).
- **Hito 8 — `NetworkSpec` + modo `--spec`** (la capa D).
- **Hito 9 — Visualización `[viz]`** (igual).

## 6. Decisiones cerradas (2026-06-14)

Las preguntas abiertas quedaron resueltas en la sesión de revisión. Esta sección
es la **fuente de verdad** hasta que el ADR 0006 se apruebe formalmente.

| # | Pregunta | Decisión |
|---|----------|----------|
| 1 | Validación de schema | **Pydantic** (v2) en el wrapper `Corpus`. PyArrow se usa solo como layout físico de la tabla. Si el rendimiento con Pydantic se vuelve cuello de botella, se migra a `msgspec.Struct` sin cambiar el contrato público (la validación queda detrás de la API). |
| 2 | Escala objetivo | Cientos → decenas/cientos de miles → millones de papers. Arrow + Parquet soportan esa escala sin cambios arquitectónicos; DuckDB entra como ayuda para queries que escanean columnas. **No se rediseña** el modelo para "millones" hasta que aparezca evidencia real. |
| 3 | DuckDB | **Extra opcional `[duckdb]`**, recomendado a partir de ~10⁴ papers o cuando se quiera query SQL sobre el corpus. Núcleo no lo requiere. |
| 4 | `NetworkSpec` | **v0.2.** El hook (la función pura que evalúa un spec) se diseña desde v0.1 para no romper compat cuando se libere. |
| 5 | Vistas `Author`/`Keyword`/`Institution` | **Tablas derivadas** por defecto. Dataclasses frozen *temporales* opcionales vía `Corpus.materialize(...)` para tests y debugging. No son parte del contrato público. |
| 6 | `is_seed` | **Columna** de la tabla en v0.1. Si el dominio crece (corpus con varias semillas, comparaciones), se promueve a tabla en una versión posterior. |
| 7 | `provenance` | **JSON string en una columna** (`provenance` por paper). La auditoría detallada puede venir de los logs de corrida del CLI, no del modelo. |

### Decisiones adicionales (mismo contexto de revisión)

- **In-memory store:** **fuera**. La persistencia por defecto es siempre un
  `Snapshot` (parquet + manifest.json en disco). El "in-memory" del diseño
  previo era confuso: su nombre sugería "no persiste" y eso bloqueaba el caso
  "herramienta interna repetible". El `Snapshot` resuelve ambos usos (un
  script ad-hoc y un pipeline repetible) y cuesta ms escribir un parquet.
  DuckDB queda como store opcional en `[duckdb]`.
- **Versionado:** **SemVer estricto**. `0.y.z` hasta congelar la API pública
  en `1.0.0`. Cada cambio breaking en `0.y` se documenta en el CHANGELOG
  con la nota `BREAKING`. Se automatiza con `release-please` desde
  Conventional Commits.
- **Changelog:** **Keep a Changelog** auto-generado por `release-please`
  (`CHANGELOG.md` en la raíz). El PR de release es revisable.
- **Hooks para LLM/agentes:** **CLI como API** en v0.1 (subprocess + JSON
  stdout, exit codes claros, sin estado). Tool schemas JSON y/o MCP quedan
  para v0.3+ según demanda real; el CLI ya es la frontera programática
  desde el día uno. Esto encaja con "la lib es la primera semilla para
  integrar con un agente".
- **Tooling de orden:** **estándar** — `ruff` (lint + format), `mypy`,
  `pytest`, `pre-commit`, `commitizen`, `release-please`, GitHub Actions.
  Configuración lista desde Hito 0.

## 7. Próximos pasos

1. Decidir A+B (probablemente A+D) en este doc o en su hilo de revisión.
2. Si A: escribir ADR `0006-arquitectura-tabla-canonica.md` con la decisión
   formal, derogando o ajustando lo que choque con `ARCHITECTURE.md` §3 y
   `API.md` §1.
3. Reescribir `docs/ARCHITECTURE.md` §3 (modelo) y `docs/API.md` §1
   (entidades → tabla) y §5–7 (proyectores, analizadores, exportadores
   adaptados).
4. Reorganizar `docs/ROADMAP.md` Hito 1 según §5 de este doc.
5. Recién entonces crear `pyproject.toml` y empezar Hito 0.
