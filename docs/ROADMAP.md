# ROADMAP — bib2graph (secuencia de construcción desde cero)

> Secuencia de construcción **clean-room**, no una migración de v0. El orden es deliberado: el
> **núcleo puro y sus tests van primero**, después las **costuras por defecto** (store stateful
> y source OpenAlex) hasta tener el pipeline con biblioteca viva funcionando, y recién después
> lo opcional. Cada hito declara **qué historias de usuario satisface** (PRD §7), sus
> **criterios de aceptación** (DoD) y los **tests que se escriben** (TDD, los justos). Fecha:
> 2026-06-15.
>
> Reordenado tras el **giro** (`Notas/04`–`07`) y los ADR
> [0007](decisiones/0007-openalex-backbone.md) (OpenAlex backbone),
> [0008](decisiones/0008-wedge-forrajeo.md) (wedge = forrajeo),
> [0009](decisiones/0009-biblioteca-viva-duckdb.md) (biblioteca viva en DuckDB),
> [0010](decisiones/0010-agente-native-columna.md) (agente-native columna),
> [0011](decisiones/0011-thesaurus-multilingue.md) (thesaurus). Diseño objetivo en
> [`ARCHITECTURE.md`](ARCHITECTURE.md); contratos en [`API.md`](API.md) (ya reconciliado).
>
> **Estado de construcción (2026-06-15):** **Hitos 0, 1, 2, 1.5, 3 y 4 TERMINADOS** — con el Hito 4,
> el alcance de **v0.1 (Hitos 1–4 + 1.5) queda feature-complete**: "ecuación → redes desde código
> Python" es alcanzable end-to-end (sin CLI ni forrajeo, que son v0.2). Tras el **2º giro**
> (acta del PO; ADR [0015](decisiones/0015-corpus-tabular-backend.md)–[0019](decisiones/0019-concurrencia-diferida.md))
> se insertó un **Hito 1.5 — Rework de `Corpus` a `TabularBackend`** como el **paso inmediato
> siguiente, secuenciado por delante del Hito 3** (instrucción explícita del PO: el rework va
> antes del resto), **ya construido**. La parte del backend abstracto (`InMemoryBackend`) cayó en
> el núcleo (Hito 1.5); el `DuckDBBackend` quedó como la costura por defecto (Hito 3, **ya
> construido**: mutación por SQL puro + UDFs, `LoopState` log append-only, `DuckDBStore` fachada,
> single-writer, export perezoso).

## Principio de orden

De adentro hacia afuera: primero lo que no tiene dependencias externas (núcleo puro),
validándolo con tests; luego las costuras por defecto, primero la **local** (DuckDB, sin red) y
después la de **red** (OpenAlex); por último lo opcional. El núcleo puro nunca depende de una
costura.

## Mapa de releases (cortes de versión)

SemVer 0.y: la API es inestable hasta `1.0.0` (que requiere API estable + caso real
reproducido, ver [`VERSIONING.md`](../VERSIONING.md)). Cortes acordados:

- **v0.1 — pipeline mínimo end-to-end (Hitos 1–4, incl. el rework 1.5) · ✅ FEATURE-COMPLETE
  (2026-06-15):** de una **ecuación de búsqueda a las redes desde código Python**, sobre una
  **biblioteca viva en DuckDB**. Incluye `Corpus` (sobre `TabularBackend`),
  proyectores/analizadores/export, `DuckDBBackend`/`DuckDBStore` y `OpenAlexSource`/`BibtexSource`.
  Con el **Hito 4 terminado**, todas las piezas existen y se componen en código (ver el ejemplo de
  `API.md` §12). **Sin CLI ni forrajeo todavía** (eso es v0.2). Es el **primer release etiquetado**.
- **v0.2 — forrajeo + CLI agente-native (Hitos 5–6):** chaining rankeado, `Preprocessor`,
  filtros PRISMA (comando **`filter`**), `b2g status` (`LoopState`) y la CLI `--json`. El
  `accept`/`reject` programático sobrevive; la curación interactiva rica (`curate`) y la GUI son
  futuro. Acá se cumple el criterio "V1 hecha" del PRD §9 a nivel de *capacidades* (el número de
  versión sigue en 0.y).
- **v0.3+ — opcionales (Hitos 7–9):** dedup fuzzy, `Enricher` de co-citación, `NetworkSpec`.
- **1.0.0:** API congelada + caso real (IED/semiconductores) reproducido.

Este mapa es la autoridad sobre el alcance de cada tag; las etiquetas de versión que aparecen
inline en hitos sueltos se refieren a la madurez de esa capacidad, no al corte de release.

## Cómo leer cada hito

Cada hito declara cuatro cosas, en este orden:

1. **Alcance** — qué se construye.
2. **Historias** — qué historias del PRD §7 (épicas A–E) se cumplen o se habilitan.
3. **Criterios de aceptación (DoD)** — el hito está "hecho" cuando todo esto es verdad.
4. **Tests (TDD — los justos)** — los pocos tests de alto valor que se escriben *antes* del
   código. Ver la disciplina abajo.

## Disciplina de tests (TDD selectivo)

**TDD es la regla**: en el núcleo puro se escribe el test antes que el código (rojo → verde →
refactor). Pero **no se testea cada cosa** — un test de bajo valor es deuda, no seguro. Criterio
para decidir:

**SÍ se testea** (hay lógica, un contrato, o riesgo de regresión):

- **Transformaciones puras con entrada/salida conocida**: proyectores sobre grafos sintéticos
  con resultado calculado a mano; analizadores; normalización.
- **Invariantes**: idempotencia (`merge`, `normalize`, `apply_thesaurus`, `enrich`), dedup por
  `id`/`doi`, hash estable de snapshot.
- **Validación de schema**: el camino feliz **y 1–2 fallas** (columna faltante, tipo incorrecto).
  No el producto cartesiano de todas las columnas.
- **Reglas de negocio con borde**: ranking por *information scent* (orden correcto), preview/tope
  del forrajeo, exit codes del CLI, contrato `--json` (que no driftee).
- **Lo que rompió antes**: cada bug entra con un test de regresión (p. ej. el bug de
  `bibtexparser`, T1 del sandbox).
- **Costuras de red**: contra **API simulada** (`httpx.MockTransport`/`responses`). **Nunca red
  en CI.**

**NO se testea** (sin lógica, o el test solo re-escribe la implementación):

- Wrappers finos y *passthroughs* (getters, `to_arrow`, delegaciones directas).
- El plumbing de Click (se testea la **función** detrás del comando, no el parser de Click).
- `tqdm`/`print`/logging; el cliente HTTP de terceros en sí (se **mockea**, no se testea OpenAlex).
- Parametrización exhaustiva de casos triviales que comparten una sola rama de código.

Marcadores: `unit` (puro, sin red ni I/O — default), `integration` (red/servicios, mockeados o
Testcontainers). El núcleo es todo `unit`.

---

## Hito 0 — Andamiaje del proyecto · ✅ TERMINADO

**Alcance**

- Estructura del paquete y `pyproject.toml` con **núcleo** (`pyarrow`, `pydantic`, `networkx`,
  `click`, `tqdm`, **`duckdb`**, **`httpx`** como cliente OpenAlex) y extras declarados pero
  mínimos (`[zotero]`, `[s2]`, `[neo4j]`, `[viz]`, `[dedup]`, `[llm]`; ADR 0005).
- **Tooling desde el día uno** (ADR 0006): `ruff`, `mypy`, `pytest`, `pre-commit`, `commitizen`,
  `release-please`, GitHub Actions. SemVer estricto, `CHANGELOG.md` auto, `CONTRIBUTING.md`.
- **Principios agente-native adoptados desde el inicio** (ADR 0010): convención de doble salida y
  exit codes documentada antes del primer comando.
- Configuración **inyectada**, sin secretos ni efectos de import.

**Historias:** ninguna directa (infraestructura). Habilita E2 (agente-native) desde el día uno.

**Criterios de aceptación (DoD)**

- `pip install -e ".[dev]"` instala el núcleo y el toolchain sin errores.
- `ruff check`, `ruff format --check`, `mypy src` y `pytest` corren en verde en local y en CI.
- `pre-commit install` deja los hooks activos; un commit que viola Conventional Commits o lint
  es rechazado.
- `b2g --help` no lanza `ModuleNotFoundError`: imprime el placeholder honesto y sale con código 1.
- Importar `bib2graph` no toca red, disco ni config (sin efectos de import).

**Tests (TDD — los justos)**

- Un *smoke test*: `import bib2graph` no tiene efectos colaterales (no abre red/archivos).
- Que el entry point `b2g` exista y el placeholder devuelva exit code 1.
- *No testear* el contenido del `pyproject` ni la config de ruff/mypy: lo verifica el propio CI.

**Se vuelve posible:** instalar el esqueleto y correr CI; el primer commit respeta semver +
changelog + pre-commit.

---

## Hito 1 — Núcleo: tabla canónica `Corpus` (PIEDRA ANGULAR) · ✅ TERMINADO

> **Construido** con **semántica de valor pura** sobre `pa.Table` (`src/bib2graph/corpus.py`):
> `accept`/`reject`/`merge`/`add_paper` hacen `to_pylist()` → mutar en memoria → reconstruir la
> tabla entera. El 2º giro lo **reencuadra**: ese contenedor migra a `TabularBackend` en el **Hito
> 1.5** (abajo). Las decisiones D1–D6 (ADR 0013) **se preservan como contrato**.

**Alcance**

- Schema Arrow + modelos Pydantic v2 para `Corpus` (columnas en [`API.md`](API.md) §1.1),
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

> Decisiones del hito en el ADR [0014](decisiones/0014-proyeccion-redes-pesos-asortatividad.md).
> Los proyectores/analizadores son **funciones puras sobre `pa.Table`** y **no cambian** con el
> rework del Hito 1.5: consumen `corpus.to_arrow()`, indiferentes al backend.

**Alcance**

- `Projector` (API.md §7, función pura `pa.Table → nx.Graph`): **acoplamiento bibliográfico
  sobre corpus completo** (ciudadano de primera), co-autoría, instituciones, co-ocurrencia de
  keywords; y co-citación (documentando su prerrequisito de segundo nivel de fetch).
- `Analyzer` (API.md §8): métricas, centralidad, comunidades (fallo explícito si falta
  `python-louvain`), **asortatividad** (atributo categórico configurable + grado) y **composición
  de comunidades** con **disclaimer de proxy**, informe de calidad
  ([`metodología.md`](metodología.md) §4) con umbrales **configurables** (`QualityThresholds`).
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
> puros (Hito 2). ADR [0015](decisiones/0015-corpus-tabular-backend.md); enmienda 0006, reencuadra
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
> [`decisiones/registro-ia.md`](decisiones/registro-ia.md) (Hito 1.5).

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
> [`decisiones/registro-ia.md`](decisiones/registro-ia.md) (Hito 3).

**Alcance**

- **`DuckDBBackend`** (núcleo, **backend por defecto**; ADR 0009 reencuadrado por
  [0015](decisiones/0015-corpus-tabular-backend.md), API.md §4): respalda el `Corpus` con estado,
  **mutación por SQL `UPDATE`/`MERGE` por `id`** (no copia en memoria), cumpliendo D1/D2/D3 (ADR
  0013) en SQL. Persiste el contenido Arrow **entre corridas** + tablas de **procedencia,
  decisiones de curación** y el **`LoopState`** (ADR [0016](decisiones/0016-maquina-estados-lazo.md):
  `SEEDED→FORAGED→FILTERED→BUILT`, transiciones permisivas; **una investigación = un archivo
  `.duckdb`**). `DuckDBStore` es su fachada de costura (`persist`/`load`). Query SQL sobre el
  corpus. El snapshot se exporta desde el estado vivo (`store.load().snapshot(...)`).
- **Single-writer** (ADR [0019](decisiones/0019-concurrencia-diferida.md)): 1 archivo = 1
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

## Hito 4 — Costura por defecto (red): `OpenAlexSource` + `BibtexSource` · ✅ TERMINADO

> **Construido** así: `src/bib2graph/sources/` con `Source` (Protocol), `SeedResult` (valida
> `corpus: Corpus` en runtime vía `arbitrary_types_allowed`, sin circularidad), `OpenAlexSource` y
> `BibtexSource`. **Con este hito, v0.1 (Hitos 1–4 + 1.5) queda feature-complete.**
> `OpenAlexSource(*, email=None, api_key=None, transport=None, base_url=…, max_results=200)`:
> traducción **PASSTHROUGH** (envuelve la ecuación en `title_and_abstract.search:(...)` y **reporta**
> los límites del ADR [0007](decisiones/0007-openalex-backbone.md) — NEAR / comodín / tags WoS — sin
> traducirlos; el **traductor WoS→OpenAlex queda diferido a v0.2**); flag `native=True` en `seed()`
> para pasar la query cruda. Cliente `httpx` con **transport inyectable** (tests con `MockTransport`,
> sin red en CI), credenciales inyectadas (arg → `OPENALEX_API_KEY` → `~/.openalex/credentials` →
> polite pool, ADR [0012](decisiones/0012-openalex-credenciales.md)), **cursor paging** con tope
> `max_results`, mapeo a las 22 columnas (refs inline; `cited_by_id=[]` **diferido al
> chaining/Enricher**; afiliaciones per-autor; `abstract` reconstruido defensivo del
> `abstract_inverted_index`) y **puebla `Manifest.openalex_version`** (header `x-openalex-api-version`
> o fecha ISO del fetch, ADR [0017](decisiones/0017-reproducibilidad-historia-snapshot.md)) +
> `equations`. `BibtexSource` (extra **`[bibtex]`**, import perezoso de `bibtexparser`): acceso
> defensivo (fix del bug T1, campos faltantes sin `KeyError`), mínimo universal; `seed()` lanza
> `NotImplementedError` (BibTeX no siembra por ecuación → usar `load()`). Semillas con `is_seed=True`,
> `curation_status="candidate"` y evento de provenance. Nuevo `Corpus.with_manifest()` como API
> pública para actualizar el manifest sin tocar el backend (lo reusarán Forager/Enricher/Filter).
> Verifier PASA (**133 tests** verdes; mypy/ruff limpios; núcleo sin `duckdb`). Decisiones de
> implementación de la IA en [`decisiones/registro-ia.md`](decisiones/registro-ia.md) (Hito 4).

**Alcance**

- `OpenAlexSource` (ADR 0007, API.md §2 sobre `httpx`): implementación de referencia del **contrato
  `Source` agnóstico** (ADR [0018](decisiones/0018-source-agnostico-calidad.md)) — entrega el
  **mínimo universal** (id/título/año/autores/keywords) **y** el **enriquecimiento completo**
  (`references_id` + `cited_by_id` + afiliaciones **per-autor** + instituciones). Traduce la
  **ecuación de búsqueda** a query OpenAlex, expone la **query ejecutada + reporte de traducción**
  (`SeedResult`) y **puebla `Manifest.openalex_version`** al sembrar (ancla la foto, ADR
  [0017](decisiones/0017-reproducibilidad-historia-snapshot.md)). **Pool cortés** (email inyectado;
  API key opcional desde feb-2026, ADR [0012](decisiones/0012-openalex-credenciales.md)). Escape
  hatch: query nativa. Parser defensivo del `abstract_inverted_index`. Las fuentes regionales
  (SciELO/Redalyc/La Referencia, solo mínimo universal) quedan declaradas, no implementadas (ADR
  0018).
- `BibtexSource` **secundaria** (sembrar desde *pearls*), con el pre-procesador que corrige el
  bug de `bibtexparser` (T1 del sandbox).

**Historias:** **A1** (sembrar por ecuación), **A2** (query ejecutada + reporte de traducción
visibles), **A3** (sembrar por papers semilla / `.bib`), y completa **A4** (query registrada en
el `Manifest`).

**Criterios de aceptación (DoD)**

- `seed(ecuación)` devuelve un `SeedResult` con `executed_query` exacta y `translation_report`
  (qué mapeó, qué se aproximó, qué se descartó — p. ej. `NEAR` no soportado).
- El corpus sembrado trae el **mínimo universal** (id/título/año/autores/keywords) **+**
  `references_id`, `cited_by_id` y afiliaciones per-autor (enriquecimiento; ADR 0018).
- `seed()` **puebla `Manifest.openalex_version`** con la versión/fecha de OpenAlex usada (ancla de
  reproducibilidad; ADR 0017).
- El email del pool cortés y la API key se **inyectan** (nunca embebidos); sin credencial el
  source corre en polite pool, no rompe.
- `BibtexSource` parsea entradas con campos opcionales ausentes **sin `KeyError`** (acceso
  defensivo) y aplica el pre-procesador del bug conocido.
- **Sin red en CI**: todo contra `httpx.MockTransport`.

**Tests (TDD — los justos)**

- Traducción ecuación→query: un caso limpio y uno con límite reportado (NEAR/comodín).
- Parseo de una respuesta OpenAlex **mockeada** → corpus con refs/citantes/afiliaciones.
- Parser defensivo del `abstract_inverted_index` (presente → texto; ausente → `None`).
- `BibtexSource` sobre un `.bib` con campos faltantes (regresión del bug T1).
- *No testear* el cliente `httpx` en sí ni la red real.

**Se vuelve posible:** sembrar el corpus desde una ecuación consciente (o un `.bib`), con la
query registrada para reproducir.

---

## Hito 5 — Forrajeo/chaining + `Preprocessor` + filtros de curación

**Alcance**

- **Forrajeo** (inserción de IA nº1; ADR 0008, API.md §5): `Forager` con backward/forward
  chaining sobre OpenAlex, **ranking por *information scent***, **profundidad 1** (opt-in 2),
  **preview de crecimiento** y **tope** (`max_candidates`). `explain_candidate` es el **paso
  opcional de IA** (extra `[llm]`) que explica *por qué* un candidato es relevante — sin decidir.
- `Preprocessor` núcleo (API.md §6): `normalize` (nombres, periodización) + **thesaurus
  multilingüe determinista** (en/es/pt, JSON portable; ADR 0011). Idempotente.
- **Filtros de inclusión/exclusión** (función pura, núcleo): año, tipo, idioma, mínimo de citas,
  con **conteo en cada paso** (flujo PRISMA) volcado a `Manifest.filters`.

**Historias:** **B1** (back/forward chaining), **B2** (profundidad + preview de crecimiento),
**B3** (ranking por estructura), **B4** (explicación opcional de IA, `[llm]`), **C1** (normalización
de autores/instituciones determinista), **C2** (thesaurus multilingüe) y **C3** (filtros con
conteo PRISMA).

**Criterios de aceptación (DoD)**

- `chain` devuelve candidatos `curation_status="candidate"` **rankeados** por scent (orden
  verificable); `preview` estima "~N papers" **sin** traerlos.
- `depth=1` por defecto, `max_candidates` se respeta como tope.
- `normalize` y `apply_thesaurus` son **idempotentes** y el thesaurus colapsa equivalentes
  multilingües (p. ej. *unequal exchange* ≡ *intercambio ecológico desigual*).
- Los filtros registran el **conteo antes/después** en cada paso (trazabilidad PRISMA).
- `explain_candidate` está aislado en `[llm]`: el forrajeo funciona sin él.

**Tests (TDD — los justos)**

- Ranking: candidatos con scent conocido salen en el **orden** esperado.
- `preview`/tope: el preview no muta el corpus; `max_candidates` corta.
- Thesaurus: idempotencia + colapso multilingüe (un caso en/es/pt).
- `normalize`: canonicalización de un nombre con variantes.
- Filtros: conteos PRISMA correctos en una secuencia de 2–3 filtros.
- *No testear* la calidad semántica de `explain_candidate` (depende de un LLM): solo que se
  invoque opt-in y falle claro sin el extra.

**Se vuelve posible:** expandir el corpus con candidatos rankeados (no lista plana), normalizar
keywords multilingües y curar con trazabilidad PRISMA.

---

## Hito 6 — CLI agente-native como API (HITO DE PRODUCTO)

**Alcance**

- CLI (Click) delgado: `seed`, `chain`, **`filter`**, `build`, `export`, `snapshot`,
  **`status`**, `inspect`, `validate`. **Cada subcomando con `--json`, exit codes (0–5), errores
  accionables, `--help` rico** (ADR 0010, API.md §convenciones). Sin estado entre invocaciones (el
  estado vive en el archivo `.duckdb`).
- **`filter`** (decisión del 2º giro, punto 4 del acta): comando **determinista** de filtros
  PRISMA (año/tipo/idioma/mínimo de citas) **con conteo en cada paso** → `Manifest.filters`. Es el
  nombre v0.2 de lo que antes se llamaba `curate`.
- El **`accept`/`reject` programático sobrevive** (vía `Corpus`/backend, para agentes y la
  biblioteca viva — historia C4). La **curación interactiva rica (`curate`) y la GUI son futuro**:
  ahí empieza la GUI, **no** en v0.2.
- **`status`** expone el `LoopState` (ADR [0016](decisiones/0016-maquina-estados-lazo.md)):
  estado actual (`SEEDED/FORAGED/FILTERED/BUILT`), transiciones disponibles y conteos por
  `curation_status`. Humanos e IAs comparten el mismo mapa del lazo.
- `build`/`export` corren `Networks.quick`.

**Historias:** **E2** (cada paso por CLI con `--json` y exit codes), cierra **A5** (re-sembrar
sobre la biblioteca viva acumulada vía CLI) y expone **C3** (filtros con conteo) y **E1**
(`snapshot`). Integra A→D en el **primer flujo de 10 minutos**.

**Criterios de aceptación (DoD)**

- El flujo `seed → chain → filter → build → export` corre end-to-end de una **ecuación** a un
  **GraphML**, sobre una **biblioteca viva**, **sin escribir código ni servidores**.
- `b2g status` reporta el `LoopState` y los conteos de curación de forma consistente con el
  archivo `.duckdb`.
- Cada subcomando soporta `--json` con salida estructurada **estable/versionada**.
- Exit codes correctos: `0` éxito · `1` uso · `2` datos · `3` dependencia · `4` red · `5`
  store/snapshot corrupto **o bloqueado** (single-writer, ADR 0019).
- Sin estado entre invocaciones: dos `b2g` consecutivos comparten estado solo vía el archivo vivo.
- *Criterio "V1 hecha" del PRD §9* satisfecho.

**Tests (TDD — los justos)**

- **Contrato `--json`** de cada subcomando: forma del objeto de salida no driftea (golden/schema).
- Mapeo de errores a **exit codes** (uso, datos, red, dependencia) — un caso por código relevante.
- Un test end-to-end del flujo de 10 minutos (`seed → chain → filter → build → export`) con
  `Source`/red **mockeados** y DuckDB temporal.
- `b2g status` devuelve el `LoopState` y conteos esperados tras una secuencia de comandos.
- *No testear* el parser de Click ni el `--help` literal; se testea la función detrás de cada
  comando, ya cubierta en Hitos 1–5.

**Se vuelve posible:** el **primer flujo de 10 minutos** — de una **ecuación** a un **GraphML**,
sobre una **biblioteca viva**, **sin escribir código ni servidores**. Un agente puede orquestar
`bib2graph` vía subprocess + JSON. *(Criterio "V1 hecha" del PRD §9.)*

---

## Hito 7 — Deduplicación fuzzy (extra `[dedup]`)

**Alcance**

- `deduplicate_authors` / `deduplicate_keywords` (lo fuzzy; el determinístico ya está en el
  `Preprocessor` del Hito 5; API.md §11).

**Historias:** refina **C1** (autores/instituciones limpios de duplicados aproximados) y **C2**
(keywords fuera del thesaurus).

**Criterios de aceptación (DoD)**

- Combina variantes por similitud por encima de un `threshold` configurable; idempotente.
- Importación **perezosa** del extra `[dedup]`: sin él, error claro que apunta al extra.

**Tests (TDD — los justos)**

- Mapeo de un par de nombres/keywords casi-iguales por encima/por debajo del umbral.
- Que sin el extra instalado el error sea explícito (mock del import faltante).

**Se vuelve posible:** redes de autor/keyword limpias de duplicados aproximados.

---

## Hito 8 — `Enricher` opt-in: resolución de refs + co-citación (extra `[s2]`)

**Alcance**

- `Enricher` (ya **no estructural**; ADR 0007, API.md §3): **resolver `references_id` a DOI
  canónico** (T8) y el **segundo nivel de fetch** (citantes con sus citas) que habilita la
  **co-citación** completa.

**Historias:** completa **D1** para la red de **co-citación** end-to-end (la más cara) y la
interoperabilidad de referencias cross-source (OpenAlex ↔ `.bib`).

**Criterios de aceptación (DoD)**

- `enrich` es **idempotente** y no pierde papers ante rate limit/reintentos.
- Resuelve `references_id` → `references_doi`; el 2º nivel habilita `CoCitationProjector` completo.
- Config/keys **inyectadas**, sin ramas muertas. **Sin red en CI** (mock).

**Tests (TDD — los justos)**

- Resolución refs→DOI sobre respuesta mockeada; idempotencia del `enrich`.
- Que el 2º nivel pueble lo que la co-citación necesita (sobre datos mock).
- *No testear* el rate limiter en tiempo real; sí la política de reintento con un cliente mock.

**Se vuelve posible:** la red de **co-citación** end-to-end y la interoperabilidad de referencias
cross-source.

---

## Hito 9 — Capa declarativa: `NetworkSpec` (v0.2)

**Alcance**

- `NetworkSpec` como `BaseModel` con loader YAML (API.md §10); `b2g networks --spec redes.yaml
  --json`.

**Historias:** profundiza **E1/E2** (pipelines reproducibles versionados en git: un YAML describe
qué se calcula). Abre la puerta a un GUI (editor de `NetworkSpec`).

**Criterios de aceptación (DoD)**

- Un `redes.yaml` válido carga y valida; uno inválido falla con error accionable.
- `Networks.build(corpus, spec)` desde YAML es **equivalente** a la spec correspondiente de
  `Networks.quick`.

**Tests (TDD — los justos)**

- Carga/validación de un YAML válido y uno inválido (2 casos).
- Equivalencia `build(spec)` ≡ la spec de `quick` para una red.

**Se vuelve posible:** pipelines reproducibles versionados en git. Abre la puerta a un GUI.

---

## Hito 10 — Visualización (extra `[viz]`)

**Alcance**

- Figuras de redes/comunidades con `matplotlib`/`seaborn`, fuera del núcleo liviano.

**Historias:** apoyo visual a **D** (lectura de la estructura intelectual).

**Criterios de aceptación (DoD)**

- Genera una figura por red sin romper el núcleo liviano; import **perezoso** de `[viz]`.

**Tests (TDD — los justos)**

- Que la función produzca un objeto figura / archivo (smoke test); **no** comparar píxeles.

---

## Hito 11 — Costuras externas de biblioteca/persistencia (post-V1)

**Alcance**

- **`ZoteroStore`** (extra `[zotero]`, **V1.1**): sincronizar la biblioteca viva con una
  colección Zotero (leer semillas / devolver lo aceptado). Costura opt-in, no el corazón (ADR
  0009).
- **`Neo4jStore`** (extra `[neo4j]`, post-V1.2): adaptador tabla→grafo para consultas Cypher.
  **Ya no es sustrato** (ADR 0002).

**Historias:** extiende **C4** (biblioteca viva sincronizable con Zotero) como costura opt-in.

**Criterios de aceptación (DoD)**

- Round-trip Zotero (leer semillas / escribir aceptados) contra cliente mockeado; `integration`
  contra Neo4j efímera (Testcontainers) para el adaptador.

**Tests (TDD — los justos)**

- Round-trip Zotero sobre cliente mock.
- `Neo4jStore` marcado `integration` (Testcontainers o driver mockeado), fuera del gate `unit`.

---

## Costuras futuras (NO planificadas — declaradas explícitamente)

Marcadas como no implementadas hasta que exista decisión de producto y código real (lección 5):

- `Source`: `RisSource`, `CsvSource`.
- `Enricher`: `CrossRefEnricher`, `ScopusEnricher`.
- **Fallback fuzzy/semántico del thesaurus** (embeddings o LLM, extra `[llm]`) → v0.2 (ADR 0011).
- **Máquina de tensiones** (inserción de IA nº2) → **v2** (ADR 0008).
- Tool schemas JSON / servidor MCP → posterior, si la demanda lo justifica. El CLI ya cubre la
  frontera programática desde el Hito 6.

No se prometen ni se cablean clientes que no se usan.

---

## Trazabilidad historias ↔ hitos (resumen)

| Historia (PRD §7) | Hito principal | Notas |
|---|---|---|
| A1 sembrar por ecuación | 4 | `OpenAlexSource.seed` |
| A2 query ejecutada + reporte | 4 | `SeedResult` |
| A3 sembrar por semillas/`.bib` | 4 | `BibtexSource` |
| A4 ecuación registrada/versionada | 1 + 4 | `provenance`/`Manifest` |
| A5 ecuaciones que mutan + acumular | 3 + 6 | biblioteca viva + re-seed por CLI |
| B1 back/forward chaining | 5 | `Forager.chain` |
| B2 profundidad + preview | 5 | `preview`, `max_candidates` |
| B3 ranking por estructura | 5 | *information scent* |
| B4 explicación opcional de IA | 5 | `explain_candidate` (`[llm]`) |
| C1 dedup/normalización autores/inst. | 5 (det.) + 7 (fuzzy) | |
| C2 thesaurus multilingüe | 5 | `apply_thesaurus` |
| C3 filtros incl/excl con conteo | 5 (lógica) + 6 (CLI `filter`) | flujo PRISMA |
| C4 aceptar/rechazar + biblioteca viva | 1 (modelo) + 1.5 (backend) + 3 (persist DuckDB) + 11 (Zotero) | `accept`/`reject` programático sobrevive (CLI/agentes); `curate`+GUI = futuro |
| D1 cinco proyecciones | 2 + 8 (co-citación) | |
| D2 métricas y comunidades | 2 | |
| D3 asortatividad + composición + proxy | 2 | |
| D4 export GraphML/CSV | 2 | |
| E1 snapshot reproducible | 1 + 6 | `snapshot` + CLI |
| E2 CLI `--json` + exit codes | 0 (principios) + 6 (CLI) | |
