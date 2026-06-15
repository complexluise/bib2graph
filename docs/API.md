# API — superficie pública de bib2graph

> Contratos de las costuras y del núcleo: el "producto" que ve quien la integra o la extiende.
> Son **bocetos de interfaz** (firmas + docstrings), no la implementación. El código es la fuente
> de verdad última; este doc describe el contrato que ese código debe cumplir. Fecha: 2026-06-15.
>
> **Reconciliado con el giro** (`Notas/04`–`07` archivadas) y los ADR
> [0007](decisiones/0007-openalex-backbone.md) (OpenAlex backbone),
> [0009](decisiones/0009-biblioteca-viva-duckdb.md) (biblioteca viva en DuckDB),
> [0010](decisiones/0010-agente-native-columna.md) (agente-native),
> [0011](decisiones/0011-thesaurus-multilingue.md) (thesaurus). Diseño de fondo en
> [`ARCHITECTURE.md`](ARCHITECTURE.md); método en [`metodología.md`](metodología.md). El `Corpus`
> sigue siendo una **tabla Arrow validada con Pydantic v2** (ADR 0006); `Paper`/`Author`/
> `Keyword`/`Institution` son **vistas derivadas**, no tipos del modelo.
>
> **Reconciliado con el 2º giro (2026-06-15):** el `Corpus` se respalda en un **`TabularBackend`
> (Protocol)** —`InMemoryBackend` puro / `DuckDBBackend` por defecto— y **delega las mutaciones**
> al backend (ADR [0015](decisiones/0015-corpus-tabular-backend.md)), en vez de la semántica de
> valor por copia en memoria del Hito 1. `corpus.to_arrow()` sigue siendo el **puente a los
> proyectores puros**. El estado del lazo (`LoopState`) vive en el backend persistente (ADR
> [0016](decisiones/0016-maquina-estados-lazo.md)). El contrato `Source` separa **mínimo universal
> vs enriquecimiento opcional** (ADR [0018](decisiones/0018-source-agnostico-calidad.md)).
>
> **Sincronizado con el Hito 3 (2026-06-15):** `DuckDBBackend` y `DuckDBStore` están **construidos**
> (§4/§4.1): mutación por SQL puro, `LoopState` (log append-only), fachada `DuckDBStore` con
> `.backend`, single-writer (`StoreLockedError`) y **carga perezosa** (PEP 562) para no acoplar el
> núcleo a duckdb.
>
> **Sincronizado con el Hito 4 (2026-06-15):** `OpenAlexSource` y `BibtexSource` están **construidos**
> (§2): traducción **passthrough** + reporte (traductor WoS diferido a v0.2), flag `native`,
> `cited_by_id` diferido al chaining/Enricher, `bibtexparser` como extra **`[bibtex]`**, credenciales
> inyectadas (ADR 0012) y `Manifest.openalex_version` poblada (ADR 0017). El método
> `Corpus.with_manifest()` (§1.2) es la API canónica que usan para sellar metadata. **Con el Hito 4,
> v0.1 queda feature-complete** (ver [`ROADMAP.md`](ROADMAP.md)).

## Convenciones

- Tipado estático en todas las firmas públicas. Las costuras se definen como `Protocol` o ABC.
- **Funciones puras** en el núcleo (proyectores, analizadores, preprocesador): sin red, sin
  estado global. El estado (biblioteca viva + `LoopState`) vive en el backend persistente
  (`DuckDBBackend`), no en la sesión.
- Estado de implementación: **`v1`** vs **`futuro`** (declarado, NO implementado — marcado como
  tal, no falsamente prometido; lección 5 de v0).

### Convenciones del CLI agente-native (ADR 0010; subcomandos en el Hito 6)

Cada subcomando lleva `--json` (salida estable/versionada) y exit codes (`0` éxito · `1` uso ·
`2` datos · `3` dependencia · `4` red · `5` store/snapshot corrupto o bloqueado). Sin estado entre
invocaciones: el estado vive en el archivo `.duckdb`. Subcomandos previstos:

- `seed`, `chain`, **`filter`** (filtros PRISMA deterministas: año/tipo/idioma/citas **con conteo
  en cada paso**), `build`, `export`, `snapshot`, **`status`** (expone el `LoopState`:
  `SEEDED/FORAGED/FILTERED/BUILT`, transiciones disponibles y conteos por `curation_status`).
- El **`accept`/`reject` programático sobrevive** (vía backend / `Corpus`) para agentes y la
  biblioteca viva (historia C4). La **curación interactiva rica (`curate`) y la GUI son futuro**:
  ahí empieza la GUI (no en v0.2). Ver [`ROADMAP.md`](ROADMAP.md) Hito 6.

---

## 1. Modelo de dominio — `Corpus` (núcleo, v1)

Wrapper sobre un **`TabularBackend`** (Protocol) cuyo contenido es una **tabla Arrow** (`pa.Table`)
con schema fijo por paper, validada con **Pydantic v2** (ADR 0006). El `Corpus` **delega las
mutaciones** al backend (ADR [0015](decisiones/0015-corpus-tabular-backend.md)): los métodos
siguen devolviendo un `Corpus` (semántica de valor a nivel de API), pero `accept`/`reject`/
`merge`/`add_paper` no reconstruyen la tabla entera en memoria — piden la operación al backend.

- **`InMemoryBackend`** — puro, sin I/O: *working set* efímero y backend de los **tests** (el
  núcleo se testea sin DuckDB). Es el comportamiento del Hito 1, movido al backend.
- **`DuckDBBackend`** — la **biblioteca viva** (ADR 0009): archivo `.duckdb` o `:memory:`,
  mutaciones por SQL `UPDATE`/`MERGE` por `id`. Es el **backend por defecto** con persistencia, y
  donde vive el `LoopState` (ADR [0016](decisiones/0016-maquina-estados-lazo.md)).

Las reglas de identidad/hash/merge (ADR [0013](decisiones/0013-identidad-hash-merge-corpus.md),
D1/D2/D3) son **contrato que cada backend cumple** (InMemory en Python, DuckDB en SQL).
`corpus.to_arrow()` es el puente estable a los proyectores/analizadores puros (§7–§8): **solo
cambia el contenedor, no el núcleo de análisis**.

> **Nota de construcción:** el rework del **Hito 1.5 está hecho** (ver [`ROADMAP.md`](ROADMAP.md),
> "Hito 1.5"). El `Corpus` ya **delega en `self._backend: TabularBackend`** (no guarda `self._table`);
> el `InMemoryBackend` (núcleo puro, semántica de valor) está implementado en
> `src/bib2graph/backends/`. El `DuckDBBackend` (costura por defecto) **también está construido**
> (Hito 3, `src/bib2graph/backends/duckdb.py`). El núcleo **no importa `duckdb`**: `DuckDBBackend` y
> `DuckDBStore` se exponen por **carga perezosa** (PEP 562, `__getattr__`) — `import bib2graph` no
> arrastra duckdb.

**Símbolos públicos del Hito 1/1.5** (`from bib2graph import ...`): `Corpus`, `Manifest`,
`CorpusSnapshot`, `SchemaError` (la excepción de contrato que lanzan `Corpus.from_arrow()` y
`add_paper()` al violarse el schema canónico), y —del rework del Hito 1.5— `TabularBackend`
(Protocol) e `InMemoryBackend` (ver §1.4).

### 1.1 Schema de la tabla (columnas canónicas)

| Columna | Tipo Arrow | Nullable | Notas |
|---|---|---|---|
| `id` | `string` | no | id interno estable (hash de `openalex_id`/`doi`) |
| `openalex_id` | `string` | sí | id de OpenAlex (`W...`); fuente primaria (ADR 0007) |
| `doi` | `string` | sí | DOI normalizado |
| `title` | `string` | no | título completo |
| `year` | `int32` | sí | año de publicación |
| `abstract` | `string` | sí | |
| `source` | `string` | sí | revista / venue |
| `language` | `string` | sí | código ISO 639-1 |
| `publisher` | `string` | sí | atributo, no entidad |
| `research_areas` | `list[string]` | — | atributos, no entidades |
| `is_seed` | `bool` | no | `True` si entró por la ecuación/semilla; `False` si lo trajo el chaining |
| `curation_status` | `string` | no | `candidate` / `accepted` / `rejected` (biblioteca viva) |
| `provenance` | `string` | sí | JSON: **lista de eventos** (log append-only). Cada evento `{action, equation_id, chaining_hop, source, fetched_at, decided_by, decided_at}`. Ver nota abajo (ADR [0013](decisiones/0013-identidad-hash-merge-corpus.md)) |
| `authors_raw` / `authors_id` | `list[string]` | — | nombres crudos / ids canónicos (ORCID si hay) |
| `authors_affiliations` | `list[string]` | — | **per-autor** (de OpenAlex `authorships`); habilita geografía/asortatividad |
| `keywords_raw` / `keywords_id` | `list[string]` | — | crudos / canónicos (post-thesaurus) |
| `institutions_raw` / `institutions_id` | `list[string]` | — | crudos / ids canónicos (ROR si hay) |
| `references_id` | `list[string]` | — | obras citadas (ids OpenAlex); **vienen de OpenAlex**, no de un Enricher |
| `references_doi` | `list[string]` | — | refs resueltas a DOI (las puebla un Enricher opt-in; OpenAlex las da como URLs internas) |
| `cited_by_id` | `list[string]` | — | citantes (ids OpenAlex); habilita forward chaining y co-citación |

El schema exacto vive en `bib2graph.schemas`. La validación se hace en `Corpus.from_arrow()` y en
cada `Source.seed()/load()`.

**`provenance` es un log append-only** (ADR [0013](decisiones/0013-identidad-hash-merge-corpus.md),
D4), no un objeto único: la columna `string` guarda un JSON que es una **lista de eventos**. Cada
evento tiene la forma:

```json
{
  "action": "fetched | accepted | rejected",
  "equation_id": "string | null",
  "chaining_hop": "int | null",
  "source": "string | null",
  "fetched_at": "ISO8601 | null",
  "decided_by": "string | null",
  "decided_at": "ISO8601 | null"
}
```

`accept()`/`reject()` **agregan** un evento (`action='accepted'`/`'rejected'`, con `decided_by` y
`decided_at`) sin borrar los previos. `None`/cadena vacía equivalen a "sin eventos".

**`id` estable y determinista** (ADR [0013](decisiones/0013-identidad-hash-merge-corpus.md), D1):
`id = f"{prefix}:{sha256(valor)[:16]}"` con precedencia `openalex_id` (`oa:`) → `doi` normalizado
(`doi:`) → `title+year` (`tt:`). El mismo paper produce el mismo `id` entre corridas; es la base
de la dedup en `merge` y en la biblioteca viva.

### 1.2 `Corpus` (wrapper)

```python
class Corpus:
    """Wrapper sobre un TabularBackend + un Manifest (ADR 0015).

    Lo que circula por el pipeline: Source lo siembra, el Forager lo expande,
    el humano lo cura, el Preprocessor lo normaliza, el backend lo persiste (biblioteca
    viva), los Projectors lo consumen vía to_arrow(). Las mutaciones se DELEGAN al
    backend (InMemoryBackend puro / DuckDBBackend por defecto): la API mantiene
    semántica de valor (devuelve Corpus), pero no copia la tabla entera en memoria.
    """
    manifest: Manifest

    @classmethod
    def from_arrow(cls, table: pa.Table, *, backend: "TabularBackend | None" = None) -> "Corpus":
        """Valida con Pydantic y construye el Corpus sobre `backend` (default InMemoryBackend).
        Falla ruidoso si el schema no coincide."""

    def to_arrow(self) -> pa.Table:
        """Materializa el contenido del backend como pa.Table. Puente a los proyectores puros."""
    def seeds(self) -> pa.Table:        """Vista is_seed == True."""
    def candidates(self) -> pa.Table:   """Vista curation_status == 'candidate'."""
    def accepted(self) -> pa.Table:     """Vista curation_status == 'accepted' (la biblioteca curada)."""

    def with_manifest(self, manifest: Manifest) -> "Corpus":
        """Devuelve un Corpus nuevo con el MISMO contenido y otro Manifest (semántica de valor:
        el original no muta). No toca el backend; el `corpus_hash` no cambia (el hash es sobre la
        tabla, no sobre el Manifest). API canónica para que las costuras (Source/Forager/Filter)
        sellen su metadata —p. ej. `OpenAlexSource.seed()` puebla `openalex_version`/`equations`—
        sin reconstruir el corpus. v1 (Hito 4)."""

    def add_paper(self, row: dict) -> "Corpus":
        """Valida la fila (PaperRow) y agrega el paper. Calcula `id` (D1) si no viene."""
    def merge(self, other: "Corpus") -> "Corpus":
        """Combina deduplicando por `id` (idempotente). Combinación por campo: escalar no-nulo
        gana (ambos no-nulos → `other`); columnas de lista = unión deduplicada (preserva `None`);
        `curation_status` por decisión humana más reciente (`provenance.decided_at`), fallback
        `accepted`>`rejected`>`candidate`; `provenance` = unión de eventos únicos (log).
        Orden de filas: **primera aparición** (filas de `self` en orden, luego las nuevas de
        `other`). Ver ADR 0013 (D3)."""
    def accept(self, ids: list[str], *, by: str = "human") -> "Corpus":
        """Marca papers como 'accepted' y AGREGA un evento al log de provenance. Devuelve Corpus nuevo."""
    def reject(self, ids: list[str], *, by: str = "human") -> "Corpus": ...
    def materialize(self, view: Literal["author", "keyword", "institution"]) -> pa.Table: ...
    def snapshot(self, path: Path) -> "CorpusSnapshot":
        """Exporta una FOTO sellada del estado actual (parquet + manifest.json) para reportar/
        reproducir. CALCULA el `corpus_hash` real (D2) y lo escribe en el Manifest del snapshot.
        NO es la persistencia (eso es el Store DuckDB); es un export derivable."""

    def __eq__(self, other: object) -> bool:
        """Igualdad canónica vía `corpus_hash` (D2): mismo contenido semántico, insensible al
        orden de filas y al orden interno de las columnas de lista; no compara el Manifest.
        Robusta ante cualquier `PYTHONHASHSEED`. Ver ADR 0013."""
```

**Notas de contrato** (Hito 1, ADR [0013](decisiones/0013-identidad-hash-merge-corpus.md)):

- **`__eq__` es por `corpus_hash`, no por `pa.Table.equals`:** dos `Corpus` con el mismo contenido
  en distinto orden de filas (o de elementos de listas) son iguales. El `corpus_hash` hashea solo
  el contenido de la tabla (incluye `curation_status` y `provenance`), nunca campos volátiles del
  Manifest (D2).
- **`merge` emite filas en orden determinista** (primera aparición): habilita diffs y snapshots
  reproducibles. Es idempotente: `c.merge(c) == c`.

**Backend y estado del lazo** (2º giro, ADR [0015](decisiones/0015-corpus-tabular-backend.md) /
[0016](decisiones/0016-maquina-estados-lazo.md)):

- **Las mutaciones se delegan al `TabularBackend`.** D1/D2/D3 son contrato que cada backend
  cumple: `InMemoryBackend` en Python, `DuckDBBackend` por SQL `UPDATE`/`MERGE` por `id`. El
  `corpus_hash` (D2) se computa siempre sobre `to_arrow()`, nunca sobre detalles del backend.
- **El `LoopState`** (`SEEDED → FORAGED → FILTERED → BUILT`, transiciones permisivas) vive en el
  **backend persistente** (`DuckDBBackend`), **no** en el `Corpus` efímero. **Una investigación =
  un archivo `.duckdb`**. El `LoopState` y su persistencia **están construidos** (Hito 3: enum
  `StrEnum` + tabla `loop_state_log` append-only; estado actual = última fila); se exponen vía
  `DuckDBBackend.loop_state()`/`set_loop_state()` (ver §4). El comando `b2g status` que lo presenta
  llega en el Hito 6.

### 1.3 `Manifest` y `CorpusSnapshot`

```python
class Manifest(BaseModel):
    """Metadatos del Corpus. Se serializa a manifest.json junto al parquet del snapshot."""
    # Obligatorios (sin default) — D5
    schema_version: str
    corpus_hash: str
    lib_version: str
    created_at: datetime
    # Con default — D5
    openalex_version: str | None = None          # versión/fecha del snapshot de OpenAlex usado
    equations: list[EquationRef] = []            # ecuaciones + query OpenAlex ejecutada + reporte de traducción
    chaining: ChainingParams | None = None       # profundidad, topes, dirección
    preprocessors: list[PreprocRef] = []         # normalize + thesaurus aplicados
    filters: list[FilterStep] = []               # criterios incl/excl con conteos (flujo PRISMA)
    enrichers: list[EnricherRef] = []            # opcional (resolución de refs / 2º nivel)

class CorpusSnapshot:
    """Carpeta con corpus.parquet + manifest.json: EXPORT sellado del estado vivo en un instante.
    Reproducible y versionable (git-lfs / DVC). No es la biblioteca viva, es su foto."""
    path: Path
    manifest: Manifest

    @property
    def corpus(self) -> Corpus: ...
```

**Notas de contrato** (Hito 1, ADR [0013](decisiones/0013-identidad-hash-merge-corpus.md); D5/D6):

- **`corpus_hash` se calcula al sellar.** El Manifest del `Corpus` en memoria lleva
  `corpus_hash=""` (placeholder); el hash real (D2) se computa en `snapshot()` y vive en el
  `CorpusSnapshot.manifest`. No tratar el hash del Manifest en memoria como autoritativo.
- **Obligatorios vs default** (D5): `schema_version`, `corpus_hash`, `lib_version`, `created_at`
  no tienen default; el resto sí (`equations=[]`, `chaining=None`, `preprocessors=[]`,
  `filters=[]`, `enrichers=[]`, `openalex_version=None`).
- **`schema_version`** (D6): en Hito 1 solo se escribe y se round-tripea (sin lógica de rechazo
  por incompatibilidad; queda para un hito posterior con migraciones sobre el store vivo).

### 1.4 `TabularBackend` (Protocol) e `InMemoryBackend` (núcleo, v1)

El **contenedor** del `Corpus` es un `TabularBackend` (Protocol `@runtime_checkable`); el `Corpus`
**delega** en él (ADR [0015](decisiones/0015-corpus-tabular-backend.md)). El núcleo depende **solo
del Protocol** (no de `duckdb`). Las **mutaciones tienen semántica de valor**: cada operación
devuelve una **instancia nueva** del backend; la original no muta. `id` ya viene calculado por
`Corpus.add_paper` (D1 se valida antes de delegar). Las reglas D1/D2/D3 (ADR
[0013](decisiones/0013-identidad-hash-merge-corpus.md)) son **contrato de este Protocol**: cada
implementación las cumple a su manera (InMemory en Python, DuckDB en SQL).

```python
@runtime_checkable
class TabularBackend(Protocol):
    """Respalda el contenido del Corpus. Cumple D1/D2/D3 (ADR 0013).
    Implementaciones: InMemoryBackend (puro, tests) / DuckDBBackend (biblioteca viva, Hito 3)."""

    def to_arrow(self) -> pa.Table: ...
        # Contenido completo como tabla Arrow canónica. Puente a los proyectores puros.
    def add_paper(self, row: dict) -> "TabularBackend": ...
        # `id` ya calculado y fila ya validada por Corpus.add_paper. Devuelve backend nuevo.
    def merge(self, other_table: pa.Table) -> "TabularBackend": ...
        # Fusión D3: orden por primera aparición (filas de self, luego nuevas), dedup por `id`.
    def apply_curation(self, ids: list[str], *, action: str, by: str) -> "TabularBackend": ...
        # accept/reject: AGREGA un evento al log `provenance` (action/decided_by/decided_at).
    def filter_view(self, view: Literal["seeds", "candidates", "accepted"]) -> pa.Table: ...
        # Vista filtrada (is_seed / curation_status == 'candidate' | 'accepted').
    def corpus_hash(self) -> str: ...        # D2, order-independent, sobre el contenido
    def __len__(self) -> int: ...
    def __eq__(self, other: object) -> bool: ...   # igualdad canónica por corpus_hash (D2)
```

| Implementación | Estado | Notas |
|----------------|--------|-------|
| `InMemoryBackend` | **v1** | **Núcleo puro, sin I/O.** *Working set* efímero y backend de los tests (el núcleo se testea sin DuckDB). Semántica de valor; hereda la lógica del Hito 1 (mutación en Python sobre listas de dicts, table-rebuild). No persiste. |
| `DuckDBBackend` | **v1, por defecto** | La **biblioteca viva** (ADR 0009/0015): **construido** (Hito 3). Mutación por SQL puro (`INSERT … ON CONFLICT (id) DO UPDATE` + merge D3 en SQL/UDF), persiste entre corridas (`.duckdb` o `:memory:`), aloja el `LoopState` (ADR 0016). Pasa la suite de contrato de backend (D1/D2/D3). Carga **perezosa** (PEP 562): no se importa con `import bib2graph`. Ver §4. |

`TabularBackend` e `InMemoryBackend` son **símbolos públicos v1** (`from bib2graph import
TabularBackend, InMemoryBackend`). El contrato D1/D2/D3 se verifica con una **suite parametrizada
por backend** (`tests/unit/test_backends.py`), ahora parametrizada **también con `DuckDBBackend`**
(Hito 3, construido): el backend SQL cumple los mismos invariantes que el InMemory.

---

## 2. Costura `Source` — sembrar un corpus

El contrato `Source` es **agnóstico de la forma de OpenAlex** (ADR
[0018](decisiones/0018-source-agnostico-calidad.md)): separa lo que **todo** corpus necesita para
existir de lo que **algunas** fuentes pueden o no entregar.

- **Mínimo universal** (obligatorio para toda `Source`): `id`, `title`, `year`, `authors_raw`,
  `keywords_raw`. Habilita ya las redes de **co-autoría** y **co-ocurrencia de keywords**.
- **Enriquecimiento opcional** (la `Source` puede omitirlo; el schema admite nulos): `references_id`
  / `references_doi`, `cited_by_id`, `authors_affiliations` (per-autor), `institutions_id`.
  Habilita acoplamiento, co-citación, redes de instituciones y asortatividad geográfica.

Una `Source` que solo provee el mínimo es **ciudadana legítima** (habilita fuentes
latinoamericanas — SciELO, Redalyc, La Referencia — sin obligarlas a entregar lo que no tienen);
los proyectores de enriquecimiento producen redes parciales sobre esos papers y lo **reportan**
(no fallan). *(El contrato se declara en v0.1; las fuentes nuevas e impl son posteriores.)*

```python
class Source(Protocol):
    """Convierte una entrada externa en un Corpus. Acceso a campos DEFENSIVO (sin KeyError).
    Debe entregar el MÍNIMO UNIVERSAL (id, title, year, authors_raw, keywords_raw); el
    enriquecimiento (refs/citantes/afiliaciones/instituciones) es OPCIONAL (ADR 0018)."""

    def seed(self, query: str) -> "SeedResult":
        """Siembra desde una ecuación de búsqueda. Devuelve el Corpus + la query ejecutada
        y el reporte de traducción (qué mapeó, qué se aproximó, qué se descartó).
        Una Source que no siembra por ecuación (p. ej. BibtexSource) lanza NotImplementedError."""
    def load(self, path: str) -> Corpus:
        """Siembra desde un archivo (export/pearls). is_seed=True."""

class SeedResult(BaseModel):
    corpus: Corpus
    executed_query: str        # la query OpenAlex EXACTA ejecutada (consciencia, ADR 0007)
    translation_report: list[str]   # mapeos limpios / aproximados / descartados (p. ej. NEAR no soportado)
```

| Implementación | Estado | Notas |
|----------------|--------|-------|
| `OpenAlexSource` | **v1 (construido, Hito 4)** | **Referencia/backbone**, sobre `httpx`. Entrega mínimo + enriquecimiento: refs inline + afiliaciones per-autor + instituciones; `cited_by_id` queda **diferido** al chaining/`Enricher` (no se trae en el seed). Traducción **passthrough** —envuelve la ecuación en `title_and_abstract.search:(...)` y **reporta** los límites WoS (NEAR/comodín/tags) sin traducirlos; el traductor WoS→OpenAlex es v0.2. Flag `native=True` (query cruda). Credenciales inyectadas (arg → `OPENALEX_API_KEY` → `~/.openalex/credentials` → polite pool; ADR 0012). Cursor paging con tope `max_results=200`. Puebla `Manifest.openalex_version` (header o fecha del fetch; ADR 0017). `transport` inyectable (tests con `MockTransport`, sin red en CI). |
| `BibtexSource` | **v1, secundaria (construido, Hito 4)** | Sembrar desde *pearls* vía `load()`. Extra **`[bibtex]`** (import perezoso de `bibtexparser`, ADR 0005); acceso defensivo (fix del bug T1: campos faltantes sin `KeyError`). Mínimo universal. `seed()` lanza `NotImplementedError` (BibTeX no siembra por ecuación). |
| `ScieloSource` / `RedalycSource` / `LaReferenciaSource` | futuro | Fuentes regionales, mínimo universal. Declaradas, no implementadas (ADR 0018). |
| `RisSource` / `CsvSource` | futuro | No implementados. |

**Reporte de cobertura/calidad** (concepto declarado, concreto **v0.2+**; ADR 0018): por
seed/source, mide % de refs resueltas, % con DOI, distribución idioma/región y completitud del
enriquecimiento. Alimenta el juicio humano de **cuándo cambiar de Source** y acota la
incertidumbre del ranking por *information scent* sobre datos parciales. Se declara como contrato
en v0.1 (función pura sobre `pa.Table`), sin cablearse vacío (lección 5).

---

## 3. Costura `Enricher` — señal extra (opt-in, ya NO estructural)

Con OpenAlex como backbone, refs y citantes **ya vienen en el corpus** (ADR 0007). El `Enricher`
deja de ser el camino para co-citación; queda opt-in para **resolver `references` a DOI** y el
**segundo nivel de fetch** (citantes con sus citas).

```python
class Enricher(Protocol):
    """Config (API keys) INYECTADA, nunca embebida. Sin ramas muertas. Rate limit/reintentos
    sin perder papers. Idempotente."""
    def enrich(self, corpus: Corpus) -> Corpus: ...
```

| Implementación | Estado | Aporta |
|----------------|--------|--------|
| `OpenAlexEnricher` | **v1, opt-in** | resuelve `references_id`→`references_doi`; 2º nivel de citantes → habilita co-citación completa |
| `SemanticScholarEnricher` | futuro | señal de citas adicional |
| `CrossRefEnricher` / `ScopusEnricher` | futuro | No implementados. |

---

## 4. Costura `Store` / backend de persistencia (biblioteca viva)

Tras el 2º giro (ADR [0015](decisiones/0015-corpus-tabular-backend.md)), la persistencia por
defecto es el **`DuckDBBackend`** del `Corpus`: DuckDB deja de ser un `Store` que persiste un
`Corpus` Arrow aparte y pasa a ser el **backend por defecto** del `Corpus` (mutaciones por SQL
`UPDATE`/`MERGE` por `id`). El `Store` sigue siendo la **costura/punto de extensión** para
destinos externos opt-in (Zotero, Neo4j). El `LoopState` (ADR 0016) vive en el backend
persistente.

El contrato `TabularBackend` (Protocol) y su firma completa viven en **§1.4** (núcleo): `to_arrow`,
`add_paper`, `merge(other_table: pa.Table)`, `apply_curation(ids, *, action, by)`, `filter_view`,
`corpus_hash`, `__len__`, `__eq__`. El `DuckDBBackend` lo implementa en SQL (Hito 3); el `Store` de
abajo es la costura de persistencia/intercambio **externa**, distinta del backend del `Corpus`.

```python
class Store(Protocol):
    """Costura de persistencia/intercambio externa. El respaldo por defecto del Corpus es el
    DuckDBBackend; esta costura cubre destinos opt-in (Zotero, Neo4j) y export (Parquet)."""
    def persist(self, corpus: Corpus) -> None:
        """Funde el corpus en la biblioteca viva (merge idempotente + log de procedencia)."""
    def load(self) -> Corpus:
        """Devuelve el corpus ACUMULADO (estado entre corridas)."""
```

| Implementación | Estado | Notas |
|----------------|--------|-------|
| `DuckDBBackend` | **v1, por defecto** | **Biblioteca viva** (ADR 0009/0015): backend del `Corpus`, stateful, acumula entre corridas, **mutación por SQL puro** (`INSERT … ON CONFLICT (id) DO UPDATE` + merge D3 en SQL/UDF), log de procedencia/curación + `LoopState`, query SQL. Es **núcleo**, no extra. `:memory:` o archivo. (El `DuckDBStore` es su fachada de costura.) |
| `InMemoryBackend` | **v1** | Backend puro (tests + working set efímero). Sin I/O. No persiste. |
| `ParquetStore` | **futuro (no implementado)** | Formato de **export/intercambio** del snapshot. Hoy lo cubre `Corpus.snapshot()` (parquet + `manifest.json`); un `Store` de export dedicado solo se construye si hace falta (lección 5: no se publica vacío). |
| `ZoteroStore` | **futuro (V1.1, `[zotero]`)** | Sincroniza la biblioteca con una colección Zotero. Costura, no el corazón. |
| `Neo4jStore` | **futuro (post-V1, `[neo4j]`)** | Adaptador tabla→grafo para Cypher. Ya no es sustrato (ADR 0002). |

> **Concurrencia (ADR [0019](decisiones/0019-concurrencia-diferida.md)):** DuckDB es
> single-writer. V1 asume **1 archivo `.duckdb` = 1 escritor** (lecturas concurrentes OK). Si el
> archivo está bloqueado por otro escritor, `DuckDBBackend`/`DuckDBStore` lanzan `StoreLockedError`
> (subclase de `OSError`); el CLI (Hito 6) lo mapea al exit code `5`. Multi-escritor concurrente es
> post-v1.0.

### 4.1 `DuckDBStore` — fachada de costura + extensiones del backend (Hito 3, construido)

`DuckDBStore(path)` (en `bib2graph.stores.duckdb`, re-exportado perezosamente como
`bib2graph.DuckDBStore`) implementa el Protocol `Store` (`persist`/`load`) delegando en un
`DuckDBBackend` sobre el archivo. `load()` devuelve un `Corpus` respaldado por ese backend (las
mutaciones subsiguientes tocan el archivo en disco).

```python
class DuckDBStore:
    def __init__(self, path: str | Path) -> None: ...   # abre/crea el .duckdb; StoreLockedError si bloqueado
    def persist(self, corpus: Corpus) -> None: ...       # merge idempotente por id en la biblioteca viva
    def load(self) -> Corpus: ...                         # corpus acumulado, respaldado por el DuckDBBackend
    @property
    def backend(self) -> "DuckDBBackend": ...            # acceso al backend para las extensiones de abajo
```

**Extensiones del `DuckDBBackend`, FUERA del Protocol `Store`/`TabularBackend`** (se acceden vía
`store.backend.…`): son específicas de DuckDB y no parte del contrato genérico:

```python
class DuckDBBackend:
    # ... cumple TabularBackend (§1.4) ...
    def loop_state(self) -> "LoopState | None": ...      # estado actual del lazo (None si no hubo transiciones)
    def set_loop_state(self, state: "LoopState") -> None: ...  # registra una transición (log append-only, permisiva)
    def query(self, sql: str) -> pa.Table: ...           # consulta SQL de SOLO lectura sobre el corpus

class LoopState(StrEnum):   # ADR 0016 — vive en bib2graph.backends.duckdb
    SEEDED = "SEEDED"; FORAGED = "FORAGED"; FILTERED = "FILTERED"; BUILT = "BUILT"
```

`LoopState` se persiste en la tabla `loop_state_log` (append-only; estado actual = última fila);
las transiciones son **permisivas** (ADR 0016: no se bloquea ningún salto, p. ej. re-sembrar tras
`BUILT`). El comando `b2g status` (Hito 6) consume `loop_state()`.

> **Carga perezosa (PEP 562):** `DuckDBBackend` y `DuckDBStore` se exponen vía `__getattr__` en
> `bib2graph/__init__.py`, de modo que **`import bib2graph` NO importa `duckdb`** (el núcleo
> permanece puro y testeable sin DuckDB). Solo `bib2graph.DuckDBBackend` / `bib2graph.DuckDBStore`
> cargan el módulo bajo demanda. `LoopState` y `StoreLockedError` se importan desde
> `bib2graph.backends.duckdb` (o desde `bib2graph.stores.duckdb`).

---

## 5. Núcleo — Forrajeo / chaining (inserción de IA nº1, v1)

```python
class Forager:
    """Orquesta el chaining sobre un Source, rankeando candidatos por *information scent*
    (estructura bibliométrica), no por lista plana. ADR 0008; nota 07."""
    def __init__(self, source: Source, *, depth: int = 1, max_candidates: int | None = None) -> None:
        """depth=1 por defecto (opt-in a 2). max_candidates = tope configurable."""

    def preview(self, corpus: Corpus, *,
                direction: Literal["backward", "forward", "both"] = "both") -> "GrowthPreview":
        """'Esta expansión sumaría ~N papers' SIN traerlos (control de crecimiento)."""

    def chain(self, corpus: Corpus, *,
              direction: Literal["backward", "forward", "both"] = "both") -> "RankedCandidates":
        """Computa candidatos (curation_status='candidate') rankeados por scent."""

class RankedCandidates(BaseModel):
    corpus: Corpus                 # candidatos agregados, con scent_score
    ranking: list[tuple[str, float]]   # (id, information_scent)

def explain_candidate(corpus: Corpus, paper_id: str) -> str:
    """Paso OPCIONAL de IA: explica por qué un candidato es relevante / a qué conversación
    pertenece. NO decide por el humano (historia B4)."""
```

---

## 6. Núcleo — `Preprocessor` (v1)

```python
class Preprocessor:
    """Determinístico e idempotente. La parte fuzzy vive en [dedup] (§11)."""
    def normalize(self, corpus: Corpus) -> Corpus:
        """Canonicaliza nombres de autor, periodiza, normaliza idiomas."""
    def apply_thesaurus(self, corpus: Corpus, thesaurus: dict | Path) -> Corpus:
        """Normaliza keywords con un thesaurus multilingüe CURADO (en/es/pt), dict
        canónico→aliases en JSON. Determinista (ADR 0011). El fallback fuzzy/LLM es v0.2."""
```

---

## 7. Núcleo — `Projector` (funciones puras, v1)

```python
class Projector(Protocol):
    def project(self, table: pa.Table, *, min_weight: int = 1,
                scope: Literal["full", "seeds_only"] = "full") -> nx.Graph: ...
```

| Proyector | Estado | Insumo | Scope por defecto | Requiere Enricher |
|-----------|--------|--------|-------------------|-------------------|
| `BibliographicCouplingProjector` | **v1** | `references_id` | **`full`** (corpus completo) | No (refs ya en corpus) |
| `AuthorCollaborationProjector` | **v1** | `authors_id` | `full` | No |
| `InstitutionCollaborationProjector` | **v1** | `institutions_id` | `full` | No |
| `KeywordCoOccurrenceProjector` | **v1** | `keywords_id` (post-thesaurus) | `full` | No |
| `CoCitationProjector` | **v1** | `cited_by_id` + citas de citantes | `seeds_only` | **Sí** (2º nivel de fetch) |

El **acoplamiento** (barato, mira adelante) es ciudadano de primera y opera sobre el **corpus
completo** (crítica #2). La **co-citación** es la más cara (segundo nivel de fetch).

**Notas de contrato** (Hito 2, ADR [0014](decisiones/0014-proyeccion-redes-pesos-asortatividad.md)):

- **Peso = conteo crudo** de ítems compartidos (D1); `min_weight` (default 1) descarta aristas
  con `weight < min_weight`. Sin normalización (Salton/Jaccard) en v1.
- **Tipo de nodo** (D2): co-autoría / instituciones / co-word → la **entidad** es el nodo
  (`authors_id` / `institutions_id` / `keywords_id`); acoplamiento / co-citación → el **paper**
  (`id`) es el nodo.
- **Co-citación en Hito 2:** el `CoCitationProjector` proyecta desde `cited_by_id` con scope
  `seeds_only`; es válido para los citantes ya presentes en el corpus, pero la co-citación
  **completa** requiere el 2º nivel de fetch del `OpenAlexEnricher` (Hito 8, ADR 0007).

---

## 8. Núcleo — `Analyzer` (funciones puras, v1)

```python
def network_metrics(g: nx.Graph) -> dict:
    """Densidad, nº de componentes, clustering promedio."""

def centrality(g: nx.Graph) -> dict:
    """Centralidad de grado e intermediación por nodo."""

def detect_communities(g: nx.Graph, method: str = "louvain") -> dict:
    """method ∈ {'louvain', 'label_prop', 'greedy_modularity'}. Louvain requiere
    `python-louvain` (DECLARADO); si falta, FALLA explícito (lección 7)."""

def assortativity(g: nx.Graph, *, attribute: str | None = None,
                  by_degree: bool = True, proxy: str | None = None) -> dict:
    """Asortatividad por un ATRIBUTO categórico configurable (p. ej. 'region') y/o por grado.
    `attribute` y sus categorías son config del USUARIO (no hardcodear; crítica #5).
    `proxy` documenta si el atributo es un proxy (p. ej. 'affiliation_per_paper'): se reporta
    en el output como disclaimer ('fácil pero consciente'). Validado en el sandbox IED."""

def community_composition(g: nx.Graph, communities: dict, attribute: str) -> dict:
    """% de cada categoría del atributo dentro de cada comunidad."""

def cocitation_quality_report(corpus: Corpus, g: nx.Graph, *,
                              thresholds: "QualityThresholds | None" = None) -> dict:
    """Informe de calidad (metodología §4). Umbrales CONFIGURABLES (no fijos del estudio de
    semiconductores; crítica #5). Defaults sensatos si thresholds is None."""

class QualityThresholds(BaseModel):
    min_volume: int = 200
    min_doi_refs_pct: float = 0.90
    min_countries: int = 5
    min_recurrent_authors: int = 10
```

**Notas de contrato** (Hito 2, ADR [0014](decisiones/0014-proyeccion-redes-pesos-asortatividad.md)):

- **`assortativity` con `proxy`** añade una clave `proxy_disclaimer` al dict de salida (D4): el
  atributo es un proxy del campo real, no el campo real ("fácil pero consciente").
- **`cocitation_quality_report` devuelve `{criterio: {valor, umbral, pasa, ...}}` + `overall_pass`**
  (sin score ponderado; D6). El criterio `min_countries` usa `institutions_id` como **proxy** de
  países (cuenta ids de institución únicos) y lo marca con un disclaimer en su entrada; el lookup
  ROR→país real llega en el Hito 8.

---

## 9. Núcleo — `Exporter` (v1)

```python
class Exporter(Protocol):
    def export(self, g: nx.Graph, results: dict, out_dir: str) -> None: ...

class GraphMLExporter: ...   # v1 — para Gephi / VOSviewer / Cytoscape
class CsvExporter: ...       # v1 — nodos.csv + aristas.csv para pandas
```

**Notas de contrato** (Hito 2, ADR [0014](decisiones/0014-proyeccion-redes-pesos-asortatividad.md), D5):

- **`CsvExporter`** escribe `aristas.csv` (`source,target,weight`) y `nodos.csv` (`id,label` +
  atributos de nodo + métricas de `results` —degree/betweenness/community— unidas por id). Orden
  de filas determinista.
- **`GraphMLExporter`** escribe esos atributos como node attributes, **omite** los atributos con
  valor `None` (Gephi / `nx.write_graphml` no los admiten) y **no muta** el grafo original (opera
  sobre una copia).

---

## 10. Capa declarativa — `NetworkSpec` (v0.2, hook desde v1)

```python
class NetworkSpec(BaseModel):
    kind: Literal["bibliographic_coupling", "cocitation", "author_collab",
                  "institution_collab", "keyword_cooccurrence"]
    min_weight: int = 1
    min_year: int | None = None
    max_year: int | None = None
    scope: Literal["full", "seeds_only"] = "full"
    clustering: Literal["louvain", "label_prop", "greedy_modularity"] | None = "louvain"
    assortativity_attribute: str | None = None     # p. ej. "region"
    layout: Literal["spring", "kamada_kawai", "circular"] | None = None

class NetworkArtifact:
    graph: nx.Graph
    metrics: dict
    communities: dict | None
    assortativity: dict | None
    layout: dict | None
    spec: NetworkSpec

class Networks:
    @staticmethod
    def build(corpus: Corpus, spec: NetworkSpec) -> NetworkArtifact: ...
    @staticmethod
    def quick(corpus: Corpus) -> list[NetworkArtifact]:
        """Arma las specs razonables (coupling full, co-autoría, institución, co-word) y
        devuelve sus artefactos. Caso 'investigador, baja fricción'."""
```

**Modo quick** (v1) cubre baja fricción; **modo spec** (v0.2, YAML) cubre el pipeline declarativo
versionable.

**Notas de contrato** (Hito 2, ADR [0014](decisiones/0014-proyeccion-redes-pesos-asortatividad.md)):

- **`Networks.quick` arma 4 redes** (coupling `full`, co-autoría, institución, co-word) y **omite
  la co-citación**, avisándolo por log (D3): la co-citación completa requiere el 2º nivel de fetch
  del `OpenAlexEnricher` (Hito 8). El `CoCitationProjector` queda disponible vía
  `Networks.build(corpus, NetworkSpec(kind="cocitation"))`.
- **`NetworkSpec` es un hook mínimo en v1** (modelo Pydantic ya consumido por `build`/`quick`); la
  carga desde YAML y la validación avanzada son del Hito 9. El símbolo público re-exportado desde
  `bib2graph` es `NetworkArtifact` (no `NetworkSpec`, que se importa desde `bib2graph.networks`).

---

## 11. Deduplicación fuzzy (extra `[dedup]`, v1)

```python
def deduplicate_authors(corpus: Corpus) -> Corpus:
    """Combina autores por similitud de nombres (fuzzy). Lo determinístico ya lo hizo el
    Preprocessor (§6); esto es el complemento aproximado."""

def deduplicate_keywords(corpus: Corpus, *, threshold: float = 0.9) -> Corpus:
    """Similitud de cadenas para keywords fuera del thesaurus. Requiere extra [dedup]."""
```

---

## 12. Ejemplo de uso (ecuación → biblioteca viva → redes)

`DuckDBStore` se importa desde `bib2graph` (re-export **perezoso** vía PEP 562, §4.1): `import
bib2graph` no arrastra duckdb. `OpenAlexSource`/`BibtexSource`/`Networks`/`GraphMLExporter` están
**construidos** (Hitos 2 y 4).

### 12.1 Hoy (v0.1) — corre con lo construido

De una ecuación a las redes, curando a mano (sin forrajeo ni CLI todavía):

```python
from pathlib import Path
from bib2graph import OpenAlexSource, DuckDBStore, Networks, GraphMLExporter

# 1) Sembrar desde una ecuación consciente (query ejecutada + reporte de límites visibles)
seed = OpenAlexSource(email="luis@sostaina.com").seed(
    '"unequal ecological exchange" OR "intercambio ecológico desigual"')
print(seed.executed_query); print("\n".join(seed.translation_report))

# 2) Curar a mano (juicio humano): las semillas entran como `candidate`
corpus = seed.corpus.accept(ids=[...]).reject(ids=[...])

# 3) Persistir en la biblioteca viva (DuckDB; acumula entre corridas) + snapshot reproducible
store = DuckDBStore(Path("biblioteca.duckdb"))          # 1 archivo = 1 investigación (ADR 0015/0016)
store.persist(corpus)
snap = store.load().snapshot(Path("snapshots/ied-2026-06-15"))

# 4) Redes (acoplamiento sobre corpus completo, co-autoría, instituciones, co-word) + export
for art in Networks.quick(snap.corpus):
    GraphMLExporter().export(art.graph, art.metrics, out_dir=Path(f"redes/{art.spec.kind}"))
```

### 12.2 Objetivo (v0.2) — con forrajeo y thesaurus

`Forager`/`Preprocessor` son del **Hito 5 (aún no construidos)**; este es el pipeline objetivo:

```python
from bib2graph import OpenAlexSource, Forager, Preprocessor   # Forager/Preprocessor: v0.2

# 2') Forrajear: candidatos rankeados por information scent (depth=1, con preview de crecimiento)
forager = Forager(OpenAlexSource(email="luis@sostaina.com"), depth=1, max_candidates=300)
print(forager.preview(seed.corpus))                     # "sumaría ~N papers"
ranked = forager.chain(seed.corpus)

# 3') Curar lo forrajeado y normalizar (thesaurus multilingüe determinista)
corpus = seed.corpus.merge(ranked.corpus).accept(ids=[...]).reject(ids=[...])
corpus = Preprocessor().apply_thesaurus(corpus, Path("thesaurus_ied.json"))
```

Y el modo declarativo (v0.2) para pipelines repetibles vía CLI (Hito 6):

```bash
b2g networks --store biblioteca.duckdb --spec redes.yaml --json
```
