# 0053 — Multi-proveedor: selección por investigación, coexistencia por proveedor (carriles) e identidad sin DOI

- **Estado:** Aceptada (decisión del PO, 2026-11-21)
- **Fecha:** 2026-11-21
- **Decidido por:** el **PO** tomó las tres decisiones de fondo (D1 en
  [#251](https://github.com/complexluise/bib2graph/issues/251), D2 en
  [#253](https://github.com/complexluise/bib2graph/issues/253), D3 en
  [#254](https://github.com/complexluise/bib2graph/issues/254), comentarios del 2026-11-21). El
  **modelo de datos concreto** de D2 (carriles con PK `(id, provider)`, curación por `id`, migración),
  la regla de normalización exacta de D3 y el plan de cortes son **síntesis de la IA (architect)**
  contra el código de `dev` (base `96d10ed`).
- **Epic:** [#256](https://github.com/complexluise/bib2graph/issues/256). **Cortes:** #251 → #255 →
  #253 → #254 → #252 (ver §Plan de cortes).
- **Enmienda a:** [0036](0036-identidad-source-id-agnostica-doi-ancla.md) (un `id` canónico puede tener
  **varios registros**, uno por proveedor; la clave `tt` cambia; se realiza el D-CLI `--source`),
  [0031](0031-preprocesamiento-automatico-en-ingesta.md) (`normalize_and_dedup` y `persist_replace`
  pasan a ser **intra-carril**), [0029](0029-workspace-por-investigacion.md) (`workspace.json` deja de
  ser solo marcador: gana `source`), [0013](0013-identidad-hash-merge-corpus.md) D3 (el upsert-concat
  ocurre dentro de un carril, nunca entre carriles) y [0042](0042-semantic-scholar-segundo-motor.md) D4
  (el `engine` de `external_ids` y la etiqueta de procedencia de S2 usan el token `s2`, no
  `semanticscholar`).
- **Relacionada con:** [0018](0018-source-agnostico-calidad.md) (contrato `Source`),
  [0024](0024-orden-d3-columna-secuencia-duckdb.md) (`_seq`, ahora por carril),
  [0035](0035-ingesta-multipuerta-resolucion-doi.md) (resolución DOI→id),
  [0044](0044-precedencia-inclusion-manual-en-curate.md) (precedencia de curación),
  [0046](0046-skill-distribucion-agnostica-proveedor.md) (precedente: proveedor modelado como **dato**),
  [0050](0050-contrato-export-corpus-arrow-bibtex-ecuacion.md)/[0052](0052-red-tipada-en-arrow-corpus.md)
  (export Arrow y su consumidor externo), [0016](0016-maquina-estados-lazo.md) (FSM),
  [0017](0017-reproducibilidad-historia-snapshot.md) (R2), Nota
  [25](../Notas/25-multiproveedor-requerimientos.md) (tensiones 2, 3 y 4).
- **Supuesto:** el PR [#250](https://github.com/complexluise/bib2graph/pull/250)
  (`SemanticScholarSource`, ADR 0042) se mergea a `dev` **antes** que el primer corte de este ADR.

## Contexto

ADR 0036 dejó el núcleo agnóstico al motor (`_compute_id`: `doi > source_id > tt`, `source_id`
genérico, tabla lateral `external_ids`) y **difirió al 2º motor** dos cosas: el selector CLI
`--source` y la población de `external_ids`. El PR #250 trajo ese 2º motor (`SemanticScholarSource`,
ADR 0042), pero **no se puede usar de punta a punta**:

- El CLI instancia `OpenAlexSource` a mano en `cli/commands/seed.py:94,120`,
  `cli/commands/chain.py:264,307`, `cli/commands/build.py:382,392` (pasada `cited_by`) y, para
  `seed --from-bib --resolve`, en `service/resolve.py:110,142`. `cli/_enrich.py:24-76` tipa el source
  como `OpenAlexSource` y construye `OpenAlexEnricher`.
- El `Forager` importa `from bib2graph.sources.openalex import _work_to_row`
  (`foraging/forager.py:64`) y lo usa para mapear los citantes forward (`forager.py:709`); el
  `works_map` de S2 tiene otro shape (`_paper_to_row`).

Además, con dos motores aparecen las tensiones que la Nota 25 dejó abiertas: (2) qué pasa cuando el
**mismo DOI** llega de dos proveedores con metadatos distintos, (3) qué identidad tienen los papers
**sin DOI** (DOAJ: ~2/3 sin DOI según el probe) y (4) cómo se **elige** el proveedor.

Hechos del código actual que condicionan el diseño:

- **Una sola tabla, PK `id`.** `corpus` en DuckDB (`backends/duckdb.py:66-93`) tiene
  `id VARCHAR NOT NULL PRIMARY KEY`; el upsert D3 (`_build_upsert_sql`, `duckdb.py:187-243`) hace
  `ON CONFLICT (id)` con `COALESCE(excluded.x, corpus.x)` en escalares y concat-dedup en listas. Si
  dos proveedores escriben el mismo DOI, **el último pisa los escalares y las listas se mezclan**.
- **Las listas de citas viven en el espacio de ids del proveedor.** `references_id`/`cited_by_id` son
  ids del motor (`W…` en OpenAlex, `paperId` en S2), y los proyectores de acoplamiento/cocitación los
  comparan entre sí (`networks/projectors.py:212,348`). Mezclar registros de dos proveedores en una
  fila (o en un corpus) **mezcla espacios de ids** y degrada esas redes en silencio.
- **Operaciones de tabla completa.** `overwrite_corpus` hace `DELETE FROM corpus` sin filtro
  (`duckdb.py:1243-1279`) — es el `persist_replace` de toda ingesta (ADR 0031 punto 4). Tres lecturas
  usan SQL crudo sobre `corpus` (`cli/commands/status.py:91-92`, `service/reads.py:118-119,702-703`).
- **`corpus_hash` es del contenido de la tabla** (`backends/memory.py:67-107`): excluye `provenance`
  y las columnas de red; ordena por `id`.
- **Curación en la fila.** `curation_status` es columna de `CORPUS_SCHEMA`; el merge de dos filas
  del mismo `id` resuelve con `_merge_curation_status` (`backends/memory.py:203-237`: gana la decisión
  humana más reciente por `decided_at` en `provenance`, desempate por prioridad).
- **Identidad sin DOI.** `_compute_id` (`corpus.py:54-94`) usa `src:` si hay `source_id`, y solo cae a
  `tt:` = `sha256(title.lower().strip() + "|" + year)` cuando **no hay ni DOI ni `source_id`**.
- **Nombres ya ocupados por "source".** `Col.SOURCE = "source"` es la **revista/venue**
  (`schemas.py:183`); `Workspace.source` es el **origen de la resolución** del workspace
  (`workspace.py:152-157`: `flag|env|cwd|init`), y se emite como `data.workspace.source` (ADR 0045
  3b). El PO eligió `--source` / `workspace.json.source` para la superficie; adentro hay que usar otro
  nombre.

## Decisión

Vocabulario de este ADR: **proveedor** = motor de extracción (`openalex`, `s2`, `doaj`);
**carril** = el conjunto de registros de un proveedor dentro de una investigación.

### D1 — Selección de proveedor: default por investigación + `--source` por invocación (#251)

1. **`workspace.json` gana el campo `source`** (default `openalex`; valores `openalex | s2 | doaj`).
   Fija el proveedor de la investigación. Workspaces existentes **sin** el campo se leen como
   `openalex` (compat por default del modelo, sin reescribir el archivo, sin migración).
   `WORKSPACE_SCHEMA_VERSION` **no** cambia (campo aditivo con default).
2. **`--source <proveedor>`** pisa el default **por invocación**. Precedencia:
   `--source` > `workspace.json.source` > `openalex`. **Un proveedor por invocación**; mezclar =
   correr el mismo verbo con distintos `--source`. No hay `--source a,b` ni variable de entorno (no
   decidido; fuera de este ADR).
3. **Dónde aplica.** En los comandos que instancian una `Source`: `seed` (ecuación y
   `--from-bib --resolve`), `chain` y `build` (pasada `cited_by`). Desde D2 también en **todo
   comando que lee el corpus**, porque elegir proveedor es elegir carril: `curate`, `read`, `status`,
   `export`, `snapshot create` y `validate`. `snapshot restore` **no** lo toma: restaura en el carril
   que declara el snapshot (ver D2). `init` gana `--source` para escribir el default al crear la
   investigación. **No hay verbo nuevo** (la poda de 0037/0038 se respeta).
4. **Proveedor como dato, no como `if`** (precedente ADR 0046). Un registro declarativo
   `sources/registry.py` mapea cada `Provider` a su fábrica y sus **capacidades**
   (`seed`, `seed_filters`, `backward`, `forward`, `enrich_cited_by`, `enrich_refs_doi`,
   `resolve_doi`). Pedir una capacidad que el proveedor no tiene falla **antes de tocar la red**, con
   error tipado accionable (mismo criterio que el pre-check actual de `chain.py:308-322`:
   `DependencyError`, exit 3). Nunca se ignora un flag en silencio (p. ej. `seed --source s2
   --exclude …` es error, no un `--exclude` descartado).
5. **El `Forager` deja de importar a OpenAlex.** Toda `Source` con capacidad `forward` expone un
   método público `work_to_row(work, *, equation_id, fetched_at, is_seed, action, chaining_hop,
   source_tag, source_kind) -> dict` (duck-typed, como `fetch_citing_batch`); el `Forager` mapea con
   `self._source.work_to_row(...)`. `OpenAlexSource.work_to_row` envuelve `_work_to_row`;
   `SemanticScholarSource.work_to_row` envuelve `_paper_to_row`.
6. **Un token por proveedor en todo el sistema.** El valor del CLI es el valor persistido: `Provider`
   (`StrEnum` en `constants.py`) con `openalex`, `s2`, `doaj`. Se usa igual en `workspace.json.source`,
   `--source`, la columna `provider` (D2), `external_ids.engine` (#255), `equations.engine` y
   `ProvenanceEvent.source` de los fetch del proveedor. Esto **enmienda el literal** de ADR 0042 D4
   (`engine="semanticscholar"`) y el default `source_tag="semanticscholar"` de `_paper_to_row`: pasan a
   `s2`. El costo es cero porque S2 no es usable por CLI hasta #251, así que no hay datos en el campo
   con la etiqueta vieja.
7. **Nombres internos.** Como "source" ya significa venue (`Col.SOURCE`) y origen de resolución
   (`Workspace.source`), en Python se usa **`provider`**: `Workspace.provider`, `Col.PROVIDER`,
   `Provider`. El envelope agrega **`data.provider = {"name": …, "origin": "flag"|"workspace"|"default"}`**
   (aditivo, `schema="1"` intacto); **no** se toca `data.workspace.source`.
8. **No se publica un proveedor en el CLI antes de que su `Source` exista** (regla de 0036): en #251
   el `click.Choice` es `openalex|s2`; `doaj` entra con #252. Un `workspace.json` con un valor no
   implementado es error accionable que lista los válidos.

### D2 — Coexistencia por proveedor (carriles); no hay precedencia ni vista unificada (#253)

**Reemplaza la "precedencia de campos"** que planteaba #253. Un DOI = un `id` canónico (D1' de 0036
**se mantiene**), pero ese `id` puede tener **un registro por proveedor guardado lado a lado; ninguno
pisa al otro**. No hay vista unificada derivada: `build` y toda lectura del corpus **eligen un
carril** con `--source` (default = `workspace.json.source`) y operan solo sobre sus registros.
Comparar proveedores = dos builds.

#### D2.1 — Modelo de datos: columna `provider` + PK compuesta, en la misma tabla `corpus`

- **`CORPUS_SCHEMA` gana `provider` (`pa.string()`, no-nullable)**, en el bloque de identificadores
  (después de `id`), y `PaperRow` el campo homónimo; `Col.PROVIDER = "provider"`.
- **DuckDB:** `corpus.provider VARCHAR NOT NULL`, **`PRIMARY KEY (id, provider)`**. El upsert D3 pasa a
  `ON CONFLICT (id, provider)`: el merge D3 (COALESCE / concat-dedup / UDFs) ocurre **solo dentro de
  un carril**. Dos proveedores nunca se mergean.
- **Invariante: un `Corpus` en memoria es siempre mono-proveedor.** El store guarda varios carriles;
  todo lo que sale del store (`DuckDBStore.load()`) es **un** carril. Por eso proyectores, dedup,
  `scoped`, curación por lote, `decorate`, exportadores y `compute_corpus_hash` **no cambian**: dentro
  de un `Corpus` el `id` sigue siendo único. `Corpus.merge` / `InMemoryBackend.merge` de dos corpora
  con proveedores distintos **falla fuerte** (`ProviderMismatchError`), no mezcla. Se agrega
  `Corpus.provider -> str | None` (el carril, o `None` si está vacío).
- **Backend atado a un carril.** `DuckDBBackend(table=None, *, path=None, provider=DEFAULT_PROVIDER)`,
  `DuckDBStore(path, provider=…)`, `service.store.open_store(path, provider=…)`,
  `cli._store.open_store_readonly(path, provider=…)`. `_clone()` conserva el carril. Al abrir, el
  backend crea en su conexión una vista temporal **`corpus_lane`**
  (`SELECT * FROM main.corpus WHERE provider = '<carril>'`; el carril es un `Provider` validado, no
  input libre). **Toda lectura** del backend (`_arrow_table_from_con`, `filter_view`, `__len__`,
  `MAX(_seq)`) y `query(sql)` usan `corpus_lane`. **Toda escritura** va a `corpus` sellando
  `provider = <carril>`. Si una fila entrante trae otro `provider`, la escritura **falla**
  (`ProviderMismatchError`): esto atrapa una `Source` que olvidó sellar su carril.
  `overwrite_corpus` pasa a `DELETE FROM corpus WHERE provider = ?`. Los tres llamadores de SQL crudo
  (`status.py:92`, `reads.py:119`, `reads.py:703`) pasan a `FROM corpus_lane`.
- **`_seq` (ADR 0024) es por carril:** el orden de primera aparición se mide dentro del carril;
  `overwrite_corpus` reasigna `_seq` solo para el carril que reescribe.
- **¿Quién sella `provider`?** Cada `Source` sella su token en las filas que produce, así un `Corpus`
  recién sembrado ya es autodescriptivo y hashea con su carril. `BibtexSource` (que no es proveedor)
  recibe `provider` por argumento; la frontera CLI le pasa el carril activo.
- **Tablas hermanas.** Con espacio de ids o conteos propios del proveedor, ganan columna
  `provider` (default = carril legacy en la migración) y se leen filtradas por carril:
  `referenced_but_not_fetched` (ids `W…` vs `paperId`), `filter_log` (conteos PRISMA por carril) y
  `enricher_log`. `equations` **ya tiene** `engine`: se filtra por `engine = carril` al reconstruir
  `manifest.equations` en `DuckDBStore.load()` (`stores/duckdb.py`) y, por lo tanto, en la regla
  "1 ecuación → `equation_hash`" del Arrow (ADR 0050 D3). `external_ids` ya es por `engine`.
  `loop_state_log` **queda por workspace** (ver §Riesgos R6).

**Por qué columna + PK compuesta y no tabla por proveedor:** una sola DDL, un solo upsert y una sola
migración. El esquema no crece con cada proveedor (el mismo argumento con el que 0036 descartó las
"columnas por motor"). Y el carril queda **dentro de la fila**, de modo que el hash, el snapshot y el
Arrow lo sellan sin mecanismo aparte.

#### D2.2 — Curación por `id` (el paper), no por `(id, provider)` (el registro)

**Recomendación del architect, adoptada en este ADR:** el estado de curación es **del paper**. Se
cura un trabajo científico según un criterio de inclusión PRISMA; no se cura el registro que un
proveedor devolvió de ese trabajo. Si la curación fuera por registro, aceptar un paper en `openalex`
lo dejaría `candidate` en `s2`, y comparar los dos builds confundiría dos variables (el proveedor y
la curación). Además haría falta re-curar cada paper por proveedor, y los conteos PRISMA divergirían
entre builds de la misma investigación.

Materialización: **invariante sincronizado en escritura.** `curation_status` sigue siendo columna de
cada fila (no se toca `CORPUS_SCHEMA` ni la lectura simple), pero el backend garantiza que **todas
las filas de un mismo `id` tienen el mismo `curation_status` en todos los carriles**:

- Un helper `_sync_curation_across_lanes(ids)` se llama al final de `_upsert_table`,
  `overwrite_corpus`, `add_paper` y `apply_curation`. Para cada `id` tocado, calcula el estado
  efectivo con un **fold de `_merge_curation_status`** sobre las filas de ese `id` en todos los
  carriles, que es la regla vigente de dos filas extendida a N filas (gana la decisión humana más
  reciente por `decided_at`; desempate por prioridad). Después escribe ese estado en todas esas
  filas.
- El **evento de curación** (`ProvenanceEvent`) se agrega solo a la fila del carril donde se decidió,
  porque la auditoría queda en ese carril. Las filas hermanas reciben el estado, no el evento.
- Consecuencias: un paper aceptado en `openalex` que después llega por `s2` **entra aceptado**; un
  `curate filter` sobre `s2` **no** rechaza un paper aceptado en `openalex` (ADR 0044, porque el
  filtro ve el estado efectivo); `is_seed` **sí** es por carril (dice "entró como semilla en este
  carril", que es procedencia y no juicio).
- Límite: la curación solo "viaja" entre carriles cuando el `id` coincide, es decir, para papers con
  DOI (ver §Riesgos R3).

#### D2.3 — `corpus_hash`, `normalize_and_dedup`, procedencia, snapshot, cache y Arrow

- **`corpus_hash` sella el carril sin mecanismo nuevo:** `provider` es columna del contenido, así que
  dos carriles con metadatos idénticos dan hashes distintos. `compute_corpus_hash` **no cambia**.
  Costo único: el hash de todo corpus existente cambia una vez (se agrega la columna). Eso refresca el
  sello de `networks/.corpus_hash` (status avisa *stale* una vez) y la semilla de Louvain de los
  ejemplos (las particiones de `examples/valoraciones` pueden renumerarse).
- **`normalize_and_dedup` (ADR 0031, `preprocessors/pipeline.py:35`) es intra-carril por
  construcción.** Recibe `existing.merge(incoming)` de **un** carril, así que el dedup fuzzy de
  autores y keywords "cross-biblioteca" pasa a significar "en todo el carril". `persist_replace`
  reescribe solo ese carril. No hay dedup ni canónico de autores **entre** carriles, y eso es
  deliberado: comparar carriles incluye comparar cómo cada proveedor nombra a los autores.
- **Procedencia:** sin cambios de modelo. `ProvenanceEvent.source` de los fetch lleva el token del
  proveedor (D1.6). Los eventos `chaining:*` conservan su `source_tag` (ADR 0020), y el carril lo da
  la columna `provider`.
- **Snapshot:** `snapshot create` fotografía **un** carril (el parquet lleva la columna `provider`).
  `snapshot restore` restaura en el carril que declara el parquet. Si el parquet trae más de un
  proveedor, falla. `SCHEMA_VERSION` (`schemas.py:29`, versión del corpus en el `Manifest`, distinta
  del envelope) pasa de `"1"` a `"2"`. Para leer snapshots `"1"`, `CorpusSnapshot.corpus`
  (`corpus.py:638-650`) completa `provider = "openalex"` si falta la columna (lectura compat, igual que
  `_provenance_compat`).
- **Cache `networks/` (ADR 0029):** sigue siendo **una** cache. `build` sella además
  `networks/.provider`, y `status` compara el `.corpus_hash` contra el hash vivo **del carril
  sellado**, no del carril default, para que no haya falsos *stale*. Comparar dos proveedores sin
  pisar la cache = segundo build con `--out-dir`.
- **Export Arrow (ADR 0050/0052):** la columna `provider` es **aditiva**, así que la regla de §1.7 de
  API.md ("aditivo es seguro") se cumple y `tests/unit/test_arrow_schema_contract.py` sigue verde. La
  metadata del schema gana la clave `provider` (aditiva, como `network_type`). `export --format arrow`
  **falla** si `networks/.provider` ≠ carril pedido, porque adherir la red de un carril a los papers de
  otro rompería el cierre `papers.id ↔ network_edges[].neighbor_id` (ADR 0052). Exportar un carril ≠
  `openalex` agrega un **warning** (ver §Riesgos R4).

#### D2.4 — Migración de stores existentes (one-shot, en `_setup()`)

- Nueva tabla **`store_meta(key VARCHAR PRIMARY KEY, value VARCHAR)`** con `schema_version`. Ausente
  = `"1"`. Reemplaza el patrón "intentar `ALTER` y suprimir la excepción" para migraciones que no son
  idempotentes por sí mismas. Los `ALTER` previos de `_setup()` (`duckdb.py:477-497`) quedan como
  están.
- **v1 → v2 (en una transacción):** `CREATE TABLE corpus_v2` (DDL nueva con `provider` y PK
  compuesta) → `INSERT … SELECT` de todas las filas con `provider = <carril legacy>` y el `_seq`
  intacto → `DROP TABLE corpus` → `ALTER TABLE corpus_v2 RENAME TO corpus`. DuckDB no permite cambiar
  la PK en el lugar, por eso se reconstruye la tabla. Después, `ADD COLUMN provider` en las tablas
  hermanas de D2.1 y `store_meta.schema_version = "2"`. Al reabrir el store, la migración no se repite.
- **Carril legacy = `workspace.json.source` vigente al migrar (default `openalex`)**, no `openalex`
  fijo. Así, un workspace creado con `source: s2` entre #251 y #253 queda bien etiquetado. El backend
  no conoce el workspace: `Workspace` le pasa `legacy_provider` al abrir el store.
- **Registros de BibTeX:** se etiquetan con el carril legacy, igual que el resto. Es coherente con la
  regla hacia adelante: **`seed --from-bib` ingesta en el carril activo**, porque un `.bib` no es un
  proveedor (no está en el enum de D1) y el flujo `from-bib → resolve/enrich → chain` (ADR 0035)
  completa esos registros **en el lugar** con el proveedor del carril. La procedencia conserva
  `source="bibtex"`, que es la verdad sobre el origen. Para tener el `.bib` en dos carriles se corre
  `seed --from-bib` con cada `--source`.
- **Sin downgrade:** un bib2graph anterior no puede escribir un store v2, porque su
  `ON CONFLICT (id)` no encuentra la restricción única. El respaldo previo a actualizar es
  `b2g snapshot` (ADR 0017). El release lo declara como cambio de formato del store.

### D3 — Identidad sin DOI: normalización fuerte, match exacto (#254)

El fallback `tt` de `_compute_id` (`corpus.py:87-90`) pasa de `title.lower().strip()` a una clave
**normalizada fuerte**, **match exacto**, función pura del registro (sin fuzzy, sin consultar el
corpus):

```python
def _title_key(title: str) -> str:
    s = title.casefold()                                    # 1. casefold PRIMERO (ver nota)
    s = unicodedata.normalize("NFKD", s)                    # 2. descomposición de compatibilidad
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")  # 3. sin diacríticos
    s = "".join(" " if unicodedata.category(c).startswith("P") else c for c in s)  # 4. puntuación → espacio
    return " ".join(s.split())                              # 5. espacios colapsados + strip

valor = f"{_title_key(title)}|{year}"   # año exacto; year None → "None", como hoy
```

- **Orden casefold → NFKD → quitar marcas.** Si se hace al revés, `casefold` puede generar marcas
  nuevas que quedan sin quitar: `"İ".casefold()` devuelve `"i̇"`, una `i` seguida de U+0307 combinante.
- **La puntuación se reemplaza por espacio y no se borra**, para no partir el mismo título:
  `Self-Organization` y `Self organization` → `self organization`. Si se borrara, uno daría
  `selforganization` y el otro `self organization`.
- **Los símbolos (`S*`) se conservan** (`C++` ≠ `C`): "sin puntuación" es la categoría Unicode `P*`,
  no todo lo no alfanumérico.
- **Alcance real:** la rama `tt` solo corre cuando **no hay DOI ni `source_id`**. Con la precedencia
  actual, el beneficiario directo es la ingesta de archivo (BibTeX/RIS sin DOI). Los registros de
  proveedor casi siempre traen su id → `src:` (ver §Riesgos R3).
- **Las ramas `doi` y `src` no cambian**: sus digests son idénticos antes y después.
- **Migración (cambia los ids `tt:` existentes):** `SCHEMA_VERSION` y `store_meta.schema_version`
  pasan de `"2"` a `"3"`. En `_setup()`, la migración v2→v3 recalcula **solo** los ids con prefijo
  `tt:` con la clave nueva. Mantiene el prefijo y **no** re-ancla a `doi:`/`src:` aunque la fila haya
  ganado DOI o `source_id` después (re-anclar sería otra decisión de identidad, fuera de este ADR). Las
  filas que colisionan **dentro de un carril** se fusionan con `_merge_rows` (semántica D3, ADR 0013),
  que es el efecto buscado: `Café` y `Cafe` del mismo año son el mismo paper. Se remapea
  `external_ids.paper_id` y se re-sincroniza la curación (D2.2). Los snapshots con
  `schema_version < "3"` recalculan sus `tt:` al cargarse, para que `restore` no duplique papers.
- **Medido en `examples/valoraciones/corpus.parquet`:** 80 papers, 75 `doi:`, 5 `src:` y **0 `tt:`**.
  D3 no cambia el hash del ejemplo commiteado.

## Alternativas descartadas

- **Precedencia de campos entre proveedores** (la propuesta original de #253: por fuente, último que
  escribe o por completitud). Rechazada por el PO. Cualquier política de precedencia **destruye**
  información de un proveedor, vuelve el resultado dependiente del orden de ingesta (o de una regla
  que hay que justificar campo por campo) y, sobre todo, **mezcla espacios de ids** en
  `references_id`/`cited_by_id`, lo que rompe en silencio el acoplamiento y la cocitación. El upsert
  actual (`ON CONFLICT (id)` + `COALESCE`) **ya es** una precedencia implícita ("último no-nulo
  gana"): D2 la elimina entre proveedores en vez de formalizarla.
- **Vista unificada derivada** (registros por proveedor + una vista "fusionada" para build). Rechazada
  por el PO. Reintroduce la precedencia por otra puerta (la vista necesita una regla de fusión) y hace
  que un build dependa de qué proveedores se corrieron. Comparar proveedores explícitamente (dos
  builds) es más honesto y más simple.
- **Identidad sin DOI por similitud (fuzzy) de título.** Rechazada por el PO. Deja de ser función
  pura del registro (el id dependería del resto del corpus y del orden de llegada) y produce
  **falsos merges** (títulos genéricos, series "Parte I/II", traducciones) que son irreversibles una
  vez fusionados. El match exacto sobre clave normalizada acepta falsos *splits*, que se ven y se
  arreglan, a cambio de cero falsos merges por similitud.
- **Tabla por proveedor** (`corpus_openalex`, `corpus_s2`, …). Rechazada: el esquema crece con cada
  proveedor y la DDL, el upsert y las migraciones se multiplican.
- **Curación por `(id, provider)`.** Rechazada (D2.2): hace re-curar por proveedor y confunde la
  comparación entre carriles.
- **Curación en una tabla lateral `curation(id, …)` con la columna como derivada.** Viable y más
  normalizada, pero obliga a reimplementar en SQL la regla de `_merge_curation_status` (que vive en la
  procedencia) y a mantener sincronizadas dos fuentes de verdad en cada `persist_replace`. El
  invariante sincronizado en escritura reutiliza la función existente y deja intactas las lecturas.
- **`provider` como columna interna (como `_seq`) fuera de `CORPUS_SCHEMA`.** Rechazada: el
  `corpus_hash` no sellaría el carril sin un "salt" aparte, y el snapshot y el Arrow no serían
  autodescriptivos.

## Consecuencias

- **(+) S2 queda usable de punta a punta** (`seed`/`chain`/`build --source s2`), y agregar DOAJ es "una
  `Source` + una fila en el registro".
- **(+) Ningún proveedor pierde datos frente a otro.** Cada build es reproducible y su hash dice de
  qué carril salió.
- **(+) El blast radius es chico.** El "`Corpus` mono-proveedor" deja proyectores, dedup, export y
  hash sin cambios; el cambio se concentra en `backends/duckdb.py`, `stores/duckdb.py`,
  `workspace.py`, el registro de proveedores y la frontera CLI.
- **(−) Cambio de contrato** (`docs/API.md`): columna nueva en §1.1, `--source` en las convenciones
  CLI, `data.provider` en el envelope, `workspace.json.source`, metadata Arrow `provider`. Cada corte
  actualiza la parte de API.md que toca, en su propio PR.
- **(−) Formato del store v1→v2→v3, one-way.** El hash de todo corpus existente cambia una vez (D2) y
  los ids `tt:` cambian una vez (D3).
- **(−) Almacenamiento duplicado por carril** (un paper en dos proveedores = dos filas) y dedup
  O(n²) por carril (deuda de 0031, que no empeora).
- **(=) `external_ids` (#255) queda parcialmente redundante** con `(id, provider, source_id)` de las
  filas por carril. Se mantiene porque ya es contrato, registra ids resueltos sin materializar el
  registro (p. ej. resolución DOI→id) y es la vista barata "qué ids tiene este paper en cada motor".

## Riesgos

Ninguno cambia las decisiones del PO; son cuidados de implementación o temas a decidir después.

- **R1 — La ventana entre #251 y #253 mezcla proveedores en una sola tabla.** Con el orden de cortes
  dado, después de #251 se puede correr `seed --source s2` en una investigación `openalex` y el
  upsert `ON CONFLICT (id)` **fusionaría** los registros: exactamente lo que D2 prohíbe, y además
  irreversible. **Mitigación (DoD de #251):** un *guard* transitorio rechaza (exit 2, sin escribir)
  `--source` ≠ `workspace.json.source` cuando el corpus no está vacío. #253 lo retira.
- **R2 — Una operación de tabla completa sin filtrar por carril borra los otros carriles.**
  `overwrite_corpus` hoy hace `DELETE FROM corpus` sin `WHERE`, y lo usa toda ingesta. Basta un camino
  olvidado para que sembrar en `s2` borre `openalex`. **Mitigación:** vista `corpus_lane` para todas
  las lecturas, `DELETE … WHERE provider = ?`, un test de no-interferencia (hash del carril A idéntico
  antes y después de ingestar en B) y un test guardarraíl que falla si aparece `FROM corpus` crudo
  fuera de `backends/`.
- **R3 — Sin DOI, la identidad es por proveedor, y D3 alcanza menos de lo que supuso #254.**
  `_compute_id` usa `src:` (hash del id **del proveedor**) antes que `tt:`. Un paper sin DOI tiene un
  `id` distinto en cada proveedor (`src:hash(W…)` ≠ `src:hash(paperId)`), así que su curación
  **no viaja** entre carriles (D2.2), y D3 no lo unifica porque nunca llega a la rama `tt`. #254
  supuso que los papers DOAJ sin DOI "caen a título+año". Eso solo ocurre si `DoajSource` deja
  `source_id` vacío. **Recomendación (#252):** que `DoajSource` llene `source_id` con el id de
  artículo DOAJ (identidad estable dentro de su carril, que bajo D2 es lo que importa). Si el PO quiere
  que la curación de papers sin DOI viaje entre proveedores, eso es **re-anclar** la precedencia
  (p. ej. `tt` antes que `src` para ciertos proveedores): decisión nueva, no cubierta acá.
- **R4 — Contrato del consumidor externo del Arrow.** API.md §1.7 dice que `source_id`/`references_id`
  "deben seguir siendo ids OpenAlex del mismo namespace (`W…`)": el consumidor cruza `references_id`
  con `source_id`. Un export del carril `s2`/`doaj` es **coherente por dentro** (D2 garantiza un solo
  namespace por archivo), pero **no es `W…`**. Un consumidor que asuma OpenAlex lo ingesta sin error y
  arma un grafo vacío o incorrecto. **Mitigación:** metadata Arrow `provider` + warning al exportar
  carriles ≠ `openalex`, y **coordinar con el consumidor antes** de anunciar exports multi-proveedor.
  Sin D2 sería peor: un archivo mezclaría namespaces.
- **R5 — Una sola cache `networks/` para varios carriles.** Dos builds con distinto `--source` se pisan,
  y `status`/`export` podrían comparar o adherir la red de un carril sobre otro. **Mitigación:**
  `networks/.provider` sellado, `status` compara contra el carril sellado y `export --format arrow`
  falla ante un carril distinto. Comparar sin pisar = `--out-dir`.
- **R6 — La FSM es por investigación, no por carril.** `loop_state_log` queda único: `seed --source s2`
  después de un `build` de `openalex` cuenta como *reseed* (ronda++), y `status.next_best_action` no
  distingue carriles. **Se acepta** en este epic, porque el ciclo es de la investigación y no del
  proveedor. Una FSM por carril sería un ADR aparte si el uso real lo pide.
- **R7 — La migración v1→v2 reconstruye la tabla `corpus`.** Es destructiva si se interrumpe a medias.
  **Mitigación:** una sola transacción, test de migración sobre un `.duckdb` legacy fixture (con
  `_seq` y orden verificados) y recomendación de `snapshot` antes de actualizar (release notes).

## Plan de cortes

Un corte = un issue = un PR a `dev` (pueden partirse más, nunca mezclarse). Cada corte actualiza la
sección de `docs/API.md` que toca y lleva sus tests primero (TDD). Gate de siempre:
`uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest`. Sin red en
CI: todos los proveedores se prueban con `httpx.MockTransport`.

### Corte 1 — #251: selector `--source` + wiring del `Forager` (D1)

**DoD**

- [ ] `constants.py`: `class Provider(StrEnum)` con `OPENALEX = "openalex"` y `S2 = "s2"`
      (DOAJ entra en #252); `DEFAULT_PROVIDER = Provider.OPENALEX`.
- [ ] `workspace.py`: `WorkspaceManifest.source: Provider = DEFAULT_PROVIDER` (valor desconocido →
      error accionable que lista los válidos); propiedad **`Workspace.provider`** (no reutilizar
      `Workspace.source`); `Workspace.init(path, name, *, source=DEFAULT_PROVIDER)`.
- [ ] `cli/commands/init.py`: `b2g init <name> --source <p>` escribe `"source"` en `workspace.json`.
- [ ] `sources/registry.py` (nuevo): `Capability` (`StrEnum`: `seed`, `seed_filters`, `backward`,
      `forward`, `enrich_cited_by`, `enrich_refs_doi`, `resolve_doi`); `ProviderSpec(factory,
      capabilities)`; `PROVIDERS: dict[Provider, ProviderSpec]`; `make_source(provider, *, email,
      api_key, transport, max_results)`; `require(provider, capability)` → `DependencyError` (exit 3)
      que nombra el proveedor y la capacidad. OpenAlex declara todas las capacidades; S2 declara
      `seed`, `backward`, `forward` y `enrich_cited_by`, y **no** `seed_filters`, `enrich_refs_doi`
      ni `resolve_doi`. Verificar contra `SemanticScholarSource` mergeado.
- [ ] `cli/_options.py`: decorador `source_option` (mismo patrón que `json_option`; `click.Choice` desde
      `PROVIDERS`, default `None`) y `resolve_provider(flag, ws) -> tuple[Provider, origin]` con
      `origin ∈ {"flag", "workspace", "default"}`.
- [ ] `seed.py:94,120`, `chain.py:264,307`, `build.py:382,392`: `OpenAlexSource(...)` →
      `make_source(provider, ...)`. `seed` con `--native/--exclude/--min-year/--max-year` sobre un
      proveedor sin `seed_filters` → error antes de la red. `seed --from-bib --resolve` exige
      `resolve_doi`. `seed --preview --source s2` devuelve la query nativa y el `translation_report`
      "sin traducción" de ADR 0042 D3, sin red. El pre-check de `chain.py:308-322` pasa a
      `require(provider, FORWARD)`.
- [ ] `cli/_enrich.py`: el parámetro `source` deja de tiparse `OpenAlexSource`. Cada pasada
      (`refs_doi`, `cited_by`) verifica su capacidad: si falta, la pasada **se omite con warning**
      en `data.warnings` (nunca en silencio). Verificar que la firma de
      `SemanticScholarSource.fetch_citing_batch` es la que llama `enrichers/openalex.py:243`.
- [ ] `foraging/forager.py`: se elimina el import de `forager.py:64`; `forager.py:709` usa
      `self._source.work_to_row(...)`. `OpenAlexSource.work_to_row` (envuelve `_work_to_row`) y
      `SemanticScholarSource.work_to_row` (envuelve `_paper_to_row`, que gana `source_kind` y
      `equation_id: str | None`). `_paper_to_row(source_tag=...)` pasa de `"semanticscholar"` a `"s2"`.
- [ ] `seed.py:156`: `engine=eq_ref.engine or "openalex"` → el proveedor activo.
- [ ] Envelope de `seed`/`chain`/`build`: `data.provider = {"name", "origin"}` (aditivo).
- [ ] **Guard transitorio (R1):** `--source` ≠ `workspace.json.source` con corpus no vacío → exit 2,
      sin escribir, mensaje que apunta a `b2g init --source` o a #253. Comentario `# TODO(#253)`.
- [ ] `docs/API.md`: convención CLI `--source` (precedencia, `data.provider`), `workspace.json.source`,
      `init --source`.

**Tests TDD mínimos**

- `test_workspace_sin_source_es_openalex` (JSON legacy → `provider == "openalex"`, `origin == "default"`).
- `test_init_source_s2_escribe_manifest` / `test_workspace_source_invalido_error_accionable`.
- `test_resolve_provider_precedencia` (flag > workspace > default).
- `test_seed_source_s2_mock` (MockTransport S2: filas con `provenance.source == "s2"`, ecuación con
  `engine == "s2"`).
- `test_chain_forward_source_s2_usa_work_to_row` (forward S2 mockeado: candidatos con metadata real) +
  `test_forager_no_importa_openalex` (`"_work_to_row" not in vars(bib2graph.foraging.forager)`).
- `test_capacidad_faltante_falla_antes_de_red` (transport que falla si se lo llama; exit 3).
- `test_seed_s2_con_exclude_es_error` / `test_from_bib_resolve_s2_es_error`.
- `test_guard_mezcla_proveedores_pre_253` (exit 2 y `corpus_hash` intacto).
- `test_build_s2_cited_by_y_refs_doi_omitida_con_warning`.
- Regresión: la suite existente sin `--source` queda verde sin tocar sus expectativas.

### Corte 2 — #255: `external_ids` por engine (D4 de 0042)

**DoD**

- [ ] `DuckDBStore.register_external_ids(corpus, engine: Provider)`: para cada fila con
      `source_id` no nulo, `add_external_id(id, engine, source_id)` (`backends/duckdb.py:992`,
      idempotente por PK `(paper_id, engine)`).
- [ ] Llamado después de cada persistencia de ingesta en `seed` (ecuación, `--from-bib` tras
      `--resolve`), `chain`, `build` (pasada `cited_by`) y `snapshot restore`, con
      `engine = proveedor activo`. En #253 la llamada **se muda adentro** del backend atado a carril
      (`engine = carril`) para que ningún camino pueda olvidarla.
- [ ] `engine` usa los tokens `Provider` (`openalex`, `s2`), no `semanticscholar` (D1.6).
- [ ] `service/resolve.py:21`: se quita la nota "NO puebla `external_ids` (diferido, #120)".
- [ ] `docs/API.md` §4.1: `external_ids` poblada (quién escribe, cuándo, valores de `engine`).

**Tests TDD mínimos**

- `test_seed_openalex_registra_external_ids` / `test_seed_s2_registra_external_ids` (mock).
- `test_external_ids_no_altera_corpus_hash` (mismo hash con y sin registro).
- `test_external_ids_idempotente` (re-seed no duplica) / `test_fila_sin_source_id_no_registra`.

### Corte 3 — #253: coexistencia por carriles (D2)

Si el PR queda grande, partirlo en **3a** (store: esquema, carril, migración, curación) y **3b**
(CLI: `--source` en comandos de lectura, `build`/`status`/`export`/`snapshot`), en ese orden.

**DoD**

- [ ] `schemas.py`: `Col.PROVIDER` en `CORPUS_SCHEMA` (no-nullable, después de `id`) y en `PaperRow`;
      `SCHEMA_VERSION = "2"`. Las fuentes sellan su token y `BibtexSource` recibe `provider`.
- [ ] `backends/duckdb.py`: DDL con `provider` + `PRIMARY KEY (id, provider)`; upsert
      `ON CONFLICT (id, provider)`; constructor con `provider` y `legacy_provider`; vista temporal
      `corpus_lane`; lecturas sobre `corpus_lane`; `overwrite_corpus` con
      `DELETE … WHERE provider = ?`; `ProviderMismatchError` ante una fila de otro carril; `_seq` por
      carril; `_sync_curation_across_lanes` (D2.2) en `_upsert_table`/`overwrite_corpus`/
      `add_paper`/`apply_curation`; `store_meta` + migración v1→v2 transaccional (D2.4); columna
      `provider` en `referenced_but_not_fetched`, `filter_log` y `enricher_log`.
- [ ] `backends/memory.py` / `corpus.py`: `merge` con proveedores distintos → `ProviderMismatchError`;
      `Corpus.provider`; compat de snapshot `"1"` en `CorpusSnapshot.corpus`.
- [ ] `stores/duckdb.py`, `service/store.py`, `cli/_store.py`, `workspace.py`: `provider` /
      `legacy_provider` de punta a punta; `load()` filtra `equations` por `engine = carril`.
- [ ] SQL crudo: `status.py:92`, `reads.py:119`, `reads.py:703` → `FROM corpus_lane`.
- [ ] `source_option` en `curate`, `read`, `status`, `export`, `snapshot create` y `validate`;
      `snapshot restore` usa el carril del parquet. **Se retira el guard de R1.**
- [ ] `build`: sella `networks/.provider`. `status`: staleness contra el carril sellado y bloque
      aditivo `data.providers = {<carril>: <n_papers>}` (conteo, no vista unificada).
      `export --format arrow`: metadata `provider`, error si la red es de otro carril, warning si
      el carril ≠ `openalex`.
- [ ] `examples/valoraciones`: re-snapshot si el gate R2 lo exige (el hash cambia por la columna).
- [ ] `docs/API.md`: §1.1 (columna), §1.2 (`Corpus.provider`, `merge`), §1.6/§1.8 (metadata
      `provider`), §4/§4.1 (carriles, `store_meta`, migración), convención CLI (`--source` en lectura).

**Tests TDD mínimos**

- `test_mismo_doi_dos_carriles_coexisten` (2 filas `(id, openalex)` y `(id, s2)`; ningún título pisado).
- `test_ingesta_en_carril_no_toca_otro` (hash de `openalex` idéntico antes y después de
  `seed`+`chain` en `s2`).
- `test_build_usa_solo_su_carril` (nodos = filas del carril) +
  `test_corpus_hash_distingue_carriles` (contenido idéntico salvo `provider` → hashes distintos).
- `test_migracion_v1_a_v2` (fixture `.duckdb` con la DDL vieja: filas → carril legacy, `_seq` y orden
  preservados, `store_meta.schema_version == "2"`, segunda apertura no-op) +
  `test_migracion_usa_source_del_workspace` (`source: s2` → filas `s2`).
- `test_curacion_por_id_propaga_entre_carriles` (aceptar en A → B lee aceptado; rechazar después en
  B → ambos rechazados) + `test_invariante_curacion_un_estado_por_id`
  (`GROUP BY id HAVING COUNT(DISTINCT curation_status) > 1` vacío tras cada operación).
- `test_carril_nuevo_hereda_curacion` / `test_filter_respeta_aceptado_de_otro_carril` (ADR 0044).
- `test_dedup_intra_carril` (variantes de autor en `s2` no alteran `authors_id` de `openalex`).
- `test_merge_corpus_proveedores_distintos_falla` / `test_escritura_fila_de_otro_carril_falla`.
- `test_snapshot_v1_compat_restore_en_openalex` / `test_restore_usa_carril_del_parquet`.
- `test_status_counts_por_carril` / `test_status_stale_contra_carril_sellado`.
- `test_export_arrow_metadata_provider` / `test_export_arrow_red_de_otro_carril_falla`.
- `test_equation_hash_por_carril` (una ecuación por carril → cada Arrow trae la suya).
- `test_no_sql_crudo_sobre_corpus_fuera_de_backends` (guardarraíl de R2).
- `tests/unit/test_arrow_schema_contract.py` sigue verde (columna aditiva).

### Corte 4 — #254: clave `tt` normalizada fuerte (D3)

**DoD**

- [ ] `corpus.py`: `_title_key` (D3) y rama `tt` de `_compute_id` = `f"{_title_key(title)}|{year}"`;
      docstring con la regla y el orden.
- [ ] `SCHEMA_VERSION = "3"`; migración v2→v3 en `_setup()` (solo ids `tt:`, prefijo conservado,
      fusión de colisiones por carril con `_merge_rows`, remapeo de `external_ids.paper_id`,
      re-sincronización de curación, `store_meta.schema_version == "3"`); compat de snapshot `< "3"`
      (recalcula `tt:` al cargar).
- [ ] `docs/API.md` §1.1 (precedencia de identidad, clave `tt`).

**Tests TDD mínimos** (en `tests/unit/test_compute_id.py`)

- **Falsos splits que deben unirse** (misma clave): `Café y Complejidad` / `Cafe y complejidad`;
  `Self-Organization` / `Self organization`; `"  Título   con  espacios "` / `Título con espacios`;
  `Straße` / `STRASSE`; `İstanbul` / `istanbul` (orden casefold→NFKD); `ＡＢＣ` (ancho completo) /
  `ABC`; `Title.` / `Title`; comillas tipográficas / rectas.
- **Falsos merges que deben seguir separados** (claves distintas): mismo título con años 2019/2020;
  `year=None` / `2020`; `C++ programming` / `C programming`; `Parte I` / `Parte II`; mismas palabras
  en otro orden.
- **Pureza y no-regresión:** misma entrada → mismo id; digests `doi:`/`src:` **idénticos** a los
  actuales (valores dorados).
- **Migración:** store v2 con `tt` de `Café`/`Cafe` del mismo año → una fila fusionada y
  `external_ids` remapeado; filas `doi:`/`src:` intactas; hash de `examples/valoraciones` sin cambios
  (0 `tt:`).

### Corte 5 — #252: `DoajSource`, 1ª fuente Sur-global

**DoD**

- [ ] `sources/doaj.py`: `DoajSource` cumple `Source` (`seed` por query; `load` → error accionable,
      como `BibtexSource.seed`). Mapeo DOAJ→schema DOI-first, **`source_id` = id de artículo DOAJ**
      (R3). Sella `provider = "doaj"` y `ProvenanceEvent.source = "doaj"`. Sin key para search,
      backoff ante 429/5xx con el subcode de ADR 0045.
- [ ] `Provider.DOAJ`; fila en `PROVIDERS` con capacidad **solo `seed`** (sin grafo de citas);
      `click.Choice` y `workspace.json.source` aceptan `doaj`.
- [ ] `chain --source doaj` → `DependencyError` antes de la red. `build --source doaj`: redes sin citas
      (coautoría, keywords) normales; las de citas salen vacías con warning honesto (sin error).
- [ ] `docs/API.md` §2: DOAJ (mínimo vs enriquecimiento, capacidades).

**Tests TDD mínimos**

- `test_doaj_seed_mock` (ES/PT; filas con `provider == "doaj"`).
- `test_doaj_sin_doi_usa_src_no_tt` / `test_doaj_con_doi_mismo_id_que_openalex`.
- `test_doaj_429_reintenta_y_mapea_subcode`.
- `test_chain_doaj_falla_antes_de_red` / `test_build_doaj_redes_de_citas_vacias_con_warning`.
- `test_workspace_source_doaj_valido`.

## Relacionada con / toca

- Código: `src/bib2graph/{constants,schemas,corpus,workspace}.py`, `backends/{duckdb,memory}.py`,
  `stores/duckdb.py`, `service/{store,resolve,reads}.py`, `sources/{registry,openalex,semanticscholar,
  bibtex,doaj}.py`, `foraging/forager.py`, `cli/{_options,_store,_enrich}.py`,
  `cli/commands/{init,seed,chain,build,curate,read,status,export,snapshot,validate}.py`.
- Docs: `docs/API.md` (por corte), notas append-only en
  [0029](0029-workspace-por-investigacion.md), [0031](0031-preprocesamiento-automatico-en-ingesta.md)
  y [0036](0036-identidad-source-id-agnostica-doi-ancla.md).

## Enmienda (2026-11-21) — Corte 1 (#251) as-built: guard R1 sin condición de corpus y detalles de superficie

Append-only; el texto de arriba queda como historia.

1. **Guard R1 (§Riesgos R1 y DoD del Corte 1): se quita la condición "cuando el corpus no está
   vacío".** Se eligió la opción (a): en **todo comando que escribe** —`seed` en todas sus variantes
   (`--equation`, `--spec`, `--from-bib` con o sin `--resolve`), `chain` y `build`— un `--source`
   explícito distinto de `workspace.json.source` sale con **exit 2 sin escribir, haya o no corpus**.
   Motivo: la verificación mostró que `init` → `seed --source s2` (corpus vacío, el guard viejo no
   dispara) → `chain` (sin `--source`, resuelve `openalex` del workspace) fusionaba carriles: el
   corpus vacío no protege, porque el `workspace.json` sigue declarando otro proveedor. Para usar otro
   proveedor antes de #253: **`b2g init --source <p>`** (una investigación por proveedor). El guard se
   retira en #253, como estaba previsto. Los `--preview` no escriben y no lo disparan.
2. **`chain --preview` valida como el modo normal:** capacidad por `--direction` (`forward`/`backward`)
   y `--budget` con proveedor ≠ `openalex`, aunque no haga red.
3. **Flags exclusivos de OpenAlex fuera del registro de capacidades.** `--email` (polite pool) con un
   proveedor ≠ `openalex` → `UsageError` exit 1 en `seed`/`chain`/`build`; `chain --budget` con
   proveedor ≠ `openalex` → `UsageError` exit 1. Cumplen D1.4 ("nunca se ignora un flag en
   silencio"), pero como `if` y con exit 1, no como capacidad con exit 3. Si aparece un 3er proveedor
   con polite pool o presupuesto, conviene pasarlos al registro (`Capability`).
4. **El test `test_build_s2_cited_by_y_refs_doi_omitida_con_warning` del Corte 1** describe un caso que
   `build` no tiene: `build` solo corre la pasada `cited_by` (que S2 declara). La omisión con warning
   de `refs_doi` ocurre en **`chain`**.
5. **`chain --since` con `s2`** se aproxima por año (S2 no tiene filtro de fecha nativo:
   `SemanticScholarSource` descarta citantes con `year < since.year`). Queda documentado en
   `docs/API.md` como límite del proveedor.

## Enmienda (2026-11-21) — Corte 2 (#255) as-built: `external_ids` poblada

Append-only; el DoD de arriba queda como historia (no se tildan las casillas).

1. **Hecho según el DoD:** `DuckDBStore.register_external_ids(corpus, engine: Provider) -> int`
   registra `(id, engine, source_id)` para cada fila con `source_id` no nulo. Es idempotente por la PK
   `(paper_id, engine)`, queda fuera de `corpus_hash` y `engine` usa el token `Provider`. Se quitó la
   nota "NO puebla" de `service/resolve.py`. `docs/API.md` §4.1 documenta quién escribe, cuándo y qué
   valores toma `engine`. Esto realiza D4 de 0042 y cierra #120 junto con el Corte 1.
2. **Puntos de llamada** (al **final** de cada ingesta, tras `set_loop_state` y la persistencia de
   ecuación / enricher refs; escritura **bulk** en una sentencia): `seed` (ecuación/spec), `seed --from-bib`
   (una vez tras la siembra, donde las filas BibTeX sin `source_id` no se registran, y otra tras
   `--resolve`, que registra **solo** las filas resueltas), `chain`, `build` (pasada `cited_by`) y
   `snapshot restore`. Salvo `--resolve`, cada llamada registra **todo** el corpus persistido. Es correcto mientras rija el guard R1
   (un proveedor por workspace).
3. **`--resolve` registra siempre `engine='openalex'`** (`Provider.OPENALEX` fijo en
   `service/resolve.py`), no el proveedor activo: la resolución DOI→id solo existe en OpenAlex. Con la
   capacidad `resolve_doi` y el guard R1 hoy coincide con el proveedor activo.
4. **`snapshot restore` recibe `provider` = `workspace.json.source`** (el CLI no tiene `--source` en
   `restore`; `run_restore(..., provider=DEFAULT_PROVIDER)` para llamadas directas). **Riesgo conocido
   hasta #253:** restaurar un parquet traído con S2 en una investigación `openalex` (o al revés)
   registra el `engine` equivocado. #253 lo corrige, porque ahí el carril sale del parquet.
5. **Huérfanos — resuelto en este corte:** `persist_replace` vacía `corpus` pero no `external_ids`;
   por eso `add_external_ids_bulk` borra en la misma operación las filas cuyo `paper_id` ya no está en
   `corpus` (p. ej. una fila `src:` que ganó DOI). Precondición: llamar con el corpus ya persistido.
