# ROADMAP · Núcleo y biblioteca viva (Hitos 0–3 + 1.5)

> ← Volver al [índice del ROADMAP](README.md)

---

## Hito 0 — Andamiaje del proyecto · ✅ TERMINADO

**Alcance**

- Estructura del paquete y `pyproject.toml` con **núcleo** (`pyarrow`, `pydantic`, `networkx`,
  `click`, `tqdm`, **`duckdb`**, **`httpx`** como cliente OpenAlex) y extras opt-in (`[bibtex]`,
  `[zotero]`, `[s2]`, `[neo4j]`, `[viz]`, `[dedup]`, `[llm]`). **La lista canónica de extras vive
  en `pyproject.toml`** (fuente de verdad); el ADR 0005 fija el *principio* (núcleo liviano +
  import perezoso), no la lista, que crece por hito. *(El extra `[llm]` se declaró en Hito 0 pero quedó
  **eliminado** en R4 — ADR 0022: el producto no usa IA generativa.)*
- **Tooling LOCAL desde el día uno** (ADR 0006): `ruff`, `mypy`, `pytest`, `pre-commit` y
  `commitizen` (linter de Conventional Commits + `cz bump --dry-run` para previsualizar el bump).
  SemVer estricto, `CONTRIBUTING.md`. **La automatización de releases (`release-please` + CI/PyPI)
  está DISEÑADA pero AÚN NO conectada** (no existe `.github/`): el gate corre en local y el
  versionado/tag es manual por ahora.
- **Principios agente-native adoptados desde el inicio** (ADR 0010): convención de doble salida y
  exit codes documentada antes del primer comando.
- Configuración **inyectada**, sin secretos ni efectos de import.

**Historias:** ninguna directa (infraestructura). Habilita E2 (agente-native) desde el día uno.

**Criterios de aceptación (DoD)**

- `pip install -e ".[dev]"` instala el núcleo y el toolchain sin errores.
- `ruff check`, `ruff format --check`, `mypy src` y `pytest` corren en verde **en local** (el
  gate en CI queda pendiente de conectar `.github/`).
- `pre-commit install` deja los hooks activos; un commit que viola Conventional Commits o lint
  es rechazado.
- `b2g --help` no lanza `ModuleNotFoundError`: imprime el placeholder honesto y sale con código 1.
- Importar `bib2graph` no toca red, disco ni config (sin efectos de import).

**Tests (TDD — los justos)**

- Un *smoke test*: `import bib2graph` no tiene efectos colaterales (no abre red/archivos).
- Que el entry point `b2g` exista y el placeholder devuelva exit code 1.
- *No testear* el contenido del `pyproject` ni la config de ruff/mypy: lo verifican el linter/formatter locales (y el CI cuando se conecte).

**Se vuelve posible:** instalar el esqueleto y correr los hooks locales (pre-commit); el primer
commit respeta semver + changelog + pre-commit. (El gate en CI queda pendiente de conectar `.github/`.)

---

## Hito 1 — Núcleo: tabla canónica `Corpus` (PIEDRA ANGULAR) · ✅ TERMINADO

> **Construido** con **semántica de valor pura** sobre `pa.Table` (`src/bib2graph/corpus.py`):
> `accept`/`reject`/`merge`/`add_paper` hacen `to_pylist()` → mutar en memoria → reconstruir la
> tabla entera. El 2º giro lo **reencuadra**: ese contenedor migra a `TabularBackend` en el **Hito
> 1.5** (abajo). Las decisiones D1–D6 (ADR 0013) **se preservan como contrato**.

**Alcance**

- Schema Arrow + modelos Pydantic v2 para `Corpus` (columnas en [`API.md`](../API.md) §1.1),
  incluyendo el **estado de curación** (`is_seed`, `curation_status`, `provenance`) que sostiene
  la biblioteca viva (ADR 0009).
- `Corpus` wrapper (API.md §1.2): `from_arrow`, `to_arrow`, `seeds`, `candidates`, `accepted`,
  `add_paper`, `merge` (idempotente por `id`/`openalex_id`/`doi`), `accept`/`reject` (registran
  decisión en `provenance`), `materialize`.
- `Manifest` + `CorpusSnapshot` (API.md §1.3): `snapshot()` exporta `corpus.parquet` +
  `manifest.json` (hash, `schema_version`, `lib_version`, fuentes, filtros/conteos, fecha).

**Historias:** sostiene **A4** (ecuación/decisiones registradas en `provenance`/`Manifest`),
**C4** (modelo de datos de la biblioteca viva: `curation_status`, `accept`/`reject`) y **E1**
(snapshot reproducible). Es habilitante de casi todo lo demás.

**Criterios de aceptación (DoD)**

- `Corpus.from_arrow` valida con Pydantic y **falla ruidoso** ante schema incorrecto.
- `merge` es idempotente: `c.merge(c) == c` (mismo conteo, mismos `id`).
- `accept`/`reject` devuelven un `Corpus` nuevo (semántica de valor) y escriben la decisión en
  `provenance`.
- `snapshot()` → reload reconstruye un `Corpus` equivalente; `corpus_hash` es **estable** entre
  corridas para el mismo contenido.
- Sin red ni servidores en todo el hito.

**Tests (TDD — los justos)**

- Construcción desde tabla válida; **falla** ante columna faltante y ante tipo incorrecto (2 casos).
- Idempotencia de `merge` + dedup por `doi` y por `openalex_id` (un caso con duplicados mixtos).
- `accept`/`reject` cambian `curation_status` y registran `provenance`; el original no muta.
- Round-trip `snapshot` → reload con `corpus_hash` estable.
- *No testear* `to_arrow` ni getters de vistas (`seeds`/`candidates`/`accepted`) más allá de un
  filtro mínimo: son proyecciones triviales.

**Se vuelve posible:** representar un corpus en memoria, exportar un snapshot reproducible y
releerlo. **Sin servidores, sin red.** La testabilidad que v0 nunca tuvo.

---

## Hito 2 — Núcleo: proyectores + analizadores + exportadores + `Networks.quick` · ✅ TERMINADO

> Decisiones del hito en el ADR [0014](../decisiones/0014-proyeccion-redes-pesos-asortatividad.md).
> Los proyectores/analizadores son **funciones puras sobre `pa.Table`** y **no cambian** con el
> rework del Hito 1.5: consumen `corpus.to_arrow()`, indiferentes al backend.

**Alcance**

- `Projector` (API.md §7, función pura `pa.Table → nx.Graph`): **acoplamiento bibliográfico
  sobre corpus completo** (ciudadano de primera), co-autoría, instituciones, co-ocurrencia de
  keywords; y co-citación (documentando su prerrequisito de segundo nivel de fetch).
- `Analyzer` (API.md §8): métricas, centralidad, comunidades (fallo explícito si falta
  `python-louvain`), **asortatividad** (atributo categórico configurable + grado) y **composición
  de comunidades** con **disclaimer de proxy**, informe de calidad
  ([`metodología.md`](../Notas/metodología.md) §4) con umbrales **configurables** (`QualityThresholds`).
- `Exporter` (GraphML, CSV). `Networks.build(corpus, spec)` (hook) y `Networks.quick(corpus)`.

**Historias:** **D1** (las cinco proyecciones), **D2** (métricas y comunidades), **D3**
(asortatividad + composición + disclaimer de proxy), **D4** (export GraphML/CSV).

**Criterios de aceptación (DoD)**

- Cada proyector, sobre un grafo sintético chico, produce las aristas y pesos calculados a mano.
- El acoplamiento opera sobre el **corpus completo** (no solo `is_seed`); co-citación documenta
  su `scope="seeds_only"` y dependencia del 2º nivel.
- `detect_communities(method="louvain")` **falla explícito** si falta `python-louvain` (no
  degrada en silencio).
- `assortativity` toma el atributo de config del usuario y emite el **disclaimer de proxy** en el
  output cuando se le pasa `proxy=...`.
- Export GraphML/CSV abre limpio en Gephi/pandas (nodos + aristas).

**Tests (TDD — los justos)**

- Un grafo sintético por proyector con resultado conocido (5 tests acotados).
- `network_metrics`/`centrality` sobre un grafo cuyo valor esperado se conoce.
- Comunidades: que el fallo por dependencia faltante sea **explícito** (un test que mockea la
  ausencia); no testear la calidad del clustering de Louvain en sí.
- `assortativity` con atributo configurable + presencia del disclaimer de proxy.
- Round-trip de export (escribir → releer → mismas aristas) para GraphML; *no* re-testear cada
  formato exhaustivamente.

**Se vuelve posible:** dado un `Corpus`, producir las redes, métricas, comunidades y
asortatividad, y exportarlas — todo puro y testeado.

---

## Hito 1.5 — Rework: `Corpus` sobre `TabularBackend` + `InMemoryBackend` (NÚCLEO) · ✅ TERMINADO

> **Inserción del 2º giro, secuenciada por delante del Hito 3** (instrucción del PO). Migró el
> contenedor del `Corpus` del Hito 1 sin cambiar el contrato D1–D6 (ADR 0013) ni los proyectores
> puros (Hito 2). ADR [0015](../decisiones/0015-corpus-tabular-backend.md); enmienda 0006, reencuadra
> 0009. Es **núcleo puro** (la parte DuckDB cae en el Hito 3).
>
> **Construido** así: `src/bib2graph/backends/` con `TabularBackend` (Protocol `@runtime_checkable`)
> e `InMemoryBackend` (semántica de valor; cada operación devuelve una instancia nueva, heredando
> la lógica del Hito 1). El `Corpus` dejó de guardar `self._table` y **delega** en
> `self._backend: TabularBackend`; `from_arrow(table, *, backend=None)` usa `InMemoryBackend` por
> defecto. El **núcleo no importa `duckdb`**. D1/D2/D3 quedaron como **contrato del backend**,
> verificado por una **suite de contrato parametrizada por backend** (`tests/unit/test_backends.py`),
> lista para sumar `DuckDBBackend` en el Hito 3. Verifier PASA (73 tests verdes bajo 2 seeds, núcleo
> sin DuckDB). Las decisiones de implementación de la IA están en
> [`decisiones/registro-ia.md`](../decisiones/registro-ia.md) (Hito 1.5).

**Alcance**

- Extraer **`TabularBackend` (Protocol)** en `src/bib2graph/backends/`: operaciones mínimas
  `to_arrow`, `add_paper`, `merge`, `apply_curation` (accept/reject), `filter_view`
  (seeds/candidates/accepted), `corpus_hash`, `__len__`, igualdad por hash.
- **`InMemoryBackend`**: mover ahí la lógica actual de `corpus.py` (mutación en Python). El
  `Corpus` **delega** en `self._backend` en vez de operar `self._table` directo.
- El **núcleo NO importa `duckdb`**: depende del Protocol. `corpus.to_arrow()` sigue siendo el
  puente a los proyectores/analizadores puros.
- Las reglas **D1/D2/D3 (ADR 0013) suben a contrato del backend**; el `InMemoryBackend` las cumple
  en Python (idéntico al Hito 1).

**Historias:** ninguna nueva; **preserva** A4/C4/E1 (modelo de la biblioteca viva) y **habilita**
el Hito 3 (`DuckDBBackend`) sin acoplar el núcleo a DuckDB.

**Criterios de aceptación (DoD)**

- `Corpus.from_arrow(table)` usa `InMemoryBackend` por defecto; `accept`/`reject`/`merge`/
  `add_paper` delegan al backend y **no** reconstruyen toda la tabla en el `Corpus`.
- D1 (`id` estable), D2 (`corpus_hash` order-independent vía `to_arrow()`) y D3 (orden e
  idempotencia de `merge`) **se conservan**: los tests del Hito 1 pasan sin cambios de semántica.
- El núcleo importa `bib2graph` **sin** `duckdb` (los tests corren sin DuckDB instalado).
- Existe un set de **tests de contrato de backend** parametrizable (mismos invariantes D1/D2/D3),
  que `DuckDBBackend` reusará en el Hito 3.

**Tests (TDD — los justos)**

- Re-apuntar los tests del Hito 1 (`tests/unit/test_corpus*.py`, `test_*` de merge/accept/snapshot)
  al `Corpus` sobre `InMemoryBackend` (deben pasar sin cambiar expectativas).
- Suite de **contrato de backend** (parametrizada por backend): idempotencia de `merge`, dedup por
  `id`, orden por primera aparición, `corpus_hash` estable y order-independent, accept/reject que
  agregan evento de provenance.
- *No testear* el passthrough `Corpus → backend` más allá de un caso por operación.

**Recomendación concreta para el `coder`** (no escribir código aquí; apuntar a `archivo:símbolo`):

- `src/bib2graph/corpus.py:Corpus` — dejar de guardar `self._table`; guardar `self._backend:
  TabularBackend`. `table` (property) → `self._backend.to_arrow()`.
- `src/bib2graph/corpus.py:Corpus.from_arrow` — aceptar `backend: TabularBackend | None`
  (default `InMemoryBackend`), validar con `validate_table`, construir el backend desde la tabla.
- `Corpus.add_paper` / `Corpus.merge` / `Corpus._apply_curation` (`accept`/`reject`) /
  `Corpus.materialize` / `Corpus.seeds` / `Corpus.candidates` / `Corpus.accepted` →
  **delegar** en el backend.
- `Corpus.snapshot` / `Corpus.__eq__` / `Corpus.__len__` → calcular sobre `self._backend.to_arrow()`
  / `self._backend.corpus_hash()`; `snapshot()` sigue sellando `corpus_hash` (D2).
- **Mover al `InMemoryBackend`** los helpers de módulo de `corpus.py`: `_merge_rows`,
  `_merge_curation_status`, `_merge_list_field`, `_merge_scalar`, `_latest_human_decided_at`,
  `_parse_provenance`, `_apply_curation` (lógica), `_rows_to_table`, `_compute_corpus_hash`,
  `_CURATION_PRIORITY`, `_LIST_COLS`. **Preservar** `_compute_id` (D1) accesible al backend.
- **No tocar** `src/bib2graph/networks/` ni `src/bib2graph/exporters/` (funciones puras sobre
  `pa.Table`): consumen `corpus.to_arrow()`, indiferentes al backend.
- **Tests a ajustar:** `tests/unit/test_*` que construyen `Corpus` siguen igual (default
  InMemory); agregar `tests/unit/test_backends.py` con la suite de contrato parametrizada.
- **Diferir al Hito 3:** `DuckDBBackend` (SQL `UPDATE`/`MERGE` por `id`), `LoopState` y el manejo
  single-writer.

**Se vuelve posible:** mutar/escalar el corpus sin copiar la tabla entera, y enchufar
`DuckDBBackend` (Hito 3) sin que el núcleo dependa de DuckDB. Núcleo puro testeable sin I/O.

---

## Hito 3 — Costura por defecto (local): `DuckDBBackend`/`DuckDBStore` stateful (biblioteca viva) · ✅ TERMINADO

> **Construido** así: `DuckDBBackend` (`src/bib2graph/backends/duckdb.py`) cumple el Protocol
> `TabularBackend` con **mutación por SQL puro** —`INSERT … ON CONFLICT (id) DO UPDATE` (upsert por
> `id`) + merge campo a campo en SQL (D3): `COALESCE` para escalares, `list_sort(list_distinct(
> list_concat(...)))` para listas preservando `NULL`— y **UDFs Python** para `curation_status` y
> `provenance`, que reusan los helpers de `InMemoryBackend` (`backends.memory`) para garantizar
> equivalencia byte a byte. El `corpus_hash` (D2) se computa siempre sobre `to_arrow()` con la misma
> función que InMemory. Soporta `:memory:` y archivo. El **`LoopState`** (enum + tabla
> `loop_state_log` append-only; estado actual = última fila; transiciones permisivas) y el **query
> SQL** son extensiones propias del backend (fuera del Protocol). El `DuckDBStore`
> (`src/bib2graph/stores/duckdb.py`) es la **fachada delgada** `persist`/`load` y expone `.backend`.
> **Single-writer** (ADR 0019): archivo bloqueado → `StoreLockedError` (subclase de `OSError`; exit
> code `5` a cablear en el CLI, Hito 6). El **núcleo no importa `duckdb`**: `DuckDBBackend`/
> `DuckDBStore` se exponen por **carga perezosa** (PEP 562, `__getattr__` en `__init__.py`), así
> `import bib2graph` no arrastra duckdb. `DuckDBBackend` pasa la suite de contrato de backend del
> Hito 1.5 (D1/D2/D3). Verifier PASA (98 tests). Decisiones de implementación de la IA en
> [`decisiones/registro-ia.md`](../decisiones/registro-ia.md) (Hito 3).

**Alcance**

- **`DuckDBBackend`** (núcleo, **backend por defecto**; ADR 0009 reencuadrado por
  [0015](../decisiones/0015-corpus-tabular-backend.md), API.md §4): respalda el `Corpus` con estado,
  **mutación por SQL `UPDATE`/`MERGE` por `id`** (no copia en memoria), cumpliendo D1/D2/D3 (ADR
  0013) en SQL. Persiste el contenido Arrow **entre corridas** + tablas de **procedencia,
  decisiones de curación** y el **`LoopState`** (ADR [0016](../decisiones/0016-maquina-estados-lazo.md):
  `SEEDED→FORAGED→FILTERED→BUILT`, transiciones permisivas; **una investigación = un archivo
  `.duckdb`**). `DuckDBStore` es su fachada de costura (`persist`/`load`). Query SQL sobre el
  corpus. El snapshot se exporta desde el estado vivo (`store.load().snapshot(...)`).
- **Single-writer** (ADR [0019](../decisiones/0019-concurrencia-diferida.md)): 1 archivo = 1
  escritor; lecturas concurrentes OK; archivo bloqueado → error accionable (exit code `5` a
  cablear en el CLI, Hito 6).

**Historias:** **C4** (biblioteca viva persistida en DuckDB que crece entre corridas con log de
procedencia) y base de **A5** (acumular a través de iteraciones / re-sembrado).

**Criterios de aceptación (DoD)**

- `persist` luego `load` en otra "corrida" (otra instancia) devuelve el corpus acumulado.
- `persist` es idempotente: persistir dos veces el mismo corpus no duplica filas.
- El **`DuckDBBackend` pasa la suite de contrato de backend del Hito 1.5** (D1/D2/D3) — misma
  semántica que `InMemoryBackend`, expresada en SQL.
- Las decisiones de curación, la procedencia y el **`LoopState`** quedan en sus tablas y
  sobreviven al reinicio; `b2g status` (Hito 6) lo lee.
- `store.load().snapshot(...)` produce un snapshot sellado válido (enlaza con Hito 1).
- Archivo bloqueado por otro escritor → error accionable (no corrupción), single-writer (ADR 0019).
- Todo corre con DuckDB **en proceso**, sin servidores.

**Tests (TDD — los justos)**

- La **suite de contrato de backend** (Hito 1.5) parametrizada también con `DuckDBBackend`.
- Persistir → releer en instancia nueva (acumulación entre corridas) sobre archivo temporal.
- Idempotencia de `persist` (sin filas duplicadas).
- Procedencia/curación/`LoopState` se registran y se recuperan; una transición de `LoopState`.
- *No testear* SQL arbitrario de DuckDB ni el motor en sí; sí una consulta representativa.

**Se vuelve posible:** una **biblioteca viva** que crece y se cura entre corridas, sin
infraestructura. El estado deja de vivir en la sesión.

---
