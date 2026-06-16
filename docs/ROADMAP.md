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
> **Estado de construcción (2026-06-15):** **Hitos 0, 1, 2, 1.5, 3, 4, 5 y 6 CONSTRUIDOS**: el flujo
> `seed → chain → filter → build → export` corre de una **ecuación** a un **GraphML** **sin escribir
> código**, sobre la biblioteca viva. El Hito 6 (`b2g`, 11 subcomandos, envelope `--json` versionado,
> exit codes 0–5, `--store` global, `LoopState` automático) está en el ADR
> [0021](decisiones/0021-cli-agente-native-contrato.md); el forrajeo (`Forager`, `preview` sin red,
> filtros que marcan `rejected`) en el ADR
> [0020](decisiones/0020-metodo-forrajeo-scent-filtros-reject.md).
>
> ⚠️ **Ya NO se afirma "v0.2 con capacidades completas".** El **red-team de la
> [Nota 06](Notas/06-critica-as-built-v0.2.md)** encontró tres grietas en el corazón de la propuesta
> (forrajeo lineal con vocabulario de ciclo; "IA del producto" casi vapor; reproducibilidad rota),
> y el PO bloqueó un **nuevo modelo conceptual** (scent bibliométrico **sin IA**, FSM cíclico,
> identidad-vs-procedencia, capa constants/models; ADR
> [0022](decisiones/0022-producto-sin-ia-generativa.md)/[0023](decisiones/0023-capa-constants-modelos-schema.md)
> y enmiendas a 0008/0011/0016/0017/0020/0021). Por eso el roadmap ahora tiene **dos partes**: **(a)
> una tanda de REMEDIACIÓN (Hitos R1–R5) · ✅ COMPLETA (2026-06-16)** que cierra la brecha del
> AS-BUILT con el modelo nuevo, **antes** de los hitos nuevos; **(b) LO QUE VIENE** (Hitos 7–11,
> actualizados a la nueva realidad).
> La tanda R está secuenciada por **dependencia**, no por gravedad: **cimientos** (R1: capa
> constants/modelos/schema, ADR 0023, de la que todo depende) → **reproducibilidad/identidad** (R2:
> content-hash vs procedencia, reloj en la frontera, Louvain seeded, ADR 0017) → **ciclo** (R3: FSM
> cíclico `cycle.py`, `reseed`/ronda, curación transversal en `status`, ADR 0016/0021) → **scent
> bibliométrico** (R4: proyectores como olfato, retiro de `explain`/`[llm]`/tensiones, ADR
> 0020/0022/0008) → **robustez/escala** (R5: bulk-load, UTF-8 en la frontera, `except` anchos de la
> Nota 06). El `ARCHITECTURE.md` apunta a estos hitos por número (R1–R5).
> **Lo que falta** (primero la remediación R1–R5, luego v0.3+ → v1.0): Hitos 7 (dedup fuzzy), 8
> (`Enricher` co-citación), 9 (`NetworkSpec` YAML), 10 (viz) y 11 (Zotero/Neo4j). Tras el **2º giro**
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
reproducido, ver [`VERSIONING.md`](../VERSIONING.md)). El **mecanismo de release DISEÑADO es
`release-please`** (ver [`VERSIONING.md`](../VERSIONING.md) / ADR 0006), pero **aún no está
conectado** (no existe `.github/` ni CI). Mientras tanto, el versionado/tag se hace
**manual/local** y `commitizen` solo sirve para lintear commits y **previsualizar** el bump
(`cz bump --dry-run`); no es el publicador. Al 2026-06-15 existen los tags **anotados locales
`v0.1.0` y `v0.2.0`** (sin push); el **release publicado** (push de tags + artefactos) queda
**pendiente de conectar `release-please` + CI**. Cortes acordados:

- **v0.1 — pipeline mínimo end-to-end (Hitos 1–4, incl. el rework 1.5) · ✅ FEATURE-COMPLETE
  (2026-06-15):** de una **ecuación de búsqueda a las redes desde código Python**, sobre una
  **biblioteca viva en DuckDB**. Incluye `Corpus` (sobre `TabularBackend`),
  proyectores/analizadores/export, `DuckDBBackend`/`DuckDBStore` y `OpenAlexSource`/`BibtexSource`.
  Con el **Hito 4 terminado**, todas las piezas existen y se componen en código (ver el ejemplo de
  `API.md` §12). **Sin CLI ni forrajeo todavía** (eso es v0.2). **Tag local `v0.1.0`** creado el
  2026-06-15 (anotado, sin push).
> ⚠️ **Honestidad sobre "capacidades completas" (v0.2):** se refiere al *flujo* `seed → chain →
> filter → build → export`, NO a la totalidad del producto. Falta la **co-citación end-to-end**
> (Hito 8: `cited_by_id` está vacío tras el seed → 0 aristas hasta el 2º nivel de fetch), y el
> *information scent* es —en el AS-BUILT— una **heurística de frecuencia de enlace** (la remediación
> R4 lo eleva a scent bibliométrico vía proyectores). **Corrección 2026-06-15 (ADR 0022):** lo que
> antes figuraba acá como "stub/futuro de IA" —`explain_candidate`, el extra `[llm]` y la **máquina
> de tensiones**— **NO es futuro: se RETIRA** (el producto no usa IA generativa). Ver
> [`Notas/06-critica-as-built-v0.2.md`](Notas/06-critica-as-built-v0.2.md) y la **tanda R1–R5** abajo.

- **v0.2 — forrajeo + CLI agente-native (Hitos 5–6) · ✅ CAPACIDADES COMPLETAS (2026-06-15):**
  chaining rankeado, `Preprocessor`, filtros PRISMA (comando **`filter`**), `b2g status`
  (`LoopState`) y el CLI `b2g` con `--json`. **El forrajeo, el `Preprocessor` y los filtros (Hito 5)
  y el CLI agente-native (Hito 6) están construidos.** El CLI expone **11 subcomandos** (`seed`,
  `chain`, `filter`, `build`, `export`, `snapshot`, `status`, `inspect`, `validate`, `accept`,
  `reject`) con envelope `--json` versionado y exit codes 0–5 (ADR
  [0021](decisiones/0021-cli-agente-native-contrato.md)). El `accept`/`reject` programático
  sobrevive (ahora como subcomando CLI); la curación interactiva rica (`curate`) y la GUI son
  futuro. Acá se cumple el criterio "V1 hecha" del PRD §9 a nivel de *capacidades* (el número de
  versión sigue en 0.y). **Tag local `v0.2.0`** creado en HEAD el 2026-06-15 (anotado, sin push).
- **v0.3 — remediación (Hitos R1–R5) · ✅ COMPLETA (2026-06-16):** cierra la brecha AS-BUILT↔TARGET del red-team (Nota 06) y
  del modelo nuevo (ADR 0022/0023 + enmiendas): capa `constants`/`models`/`schemas` única,
  identidad-vs-procedencia con reproducibilidad bit a bit, FSM cíclico de dominio (`cycle.py`) con
  curación transversal visible, scent bibliométrico vía proyectores (sin IA), y robustez (bulk-load,
  UTF-8, footguns). **Es un breaking change de comportamiento interno** (el `corpus_hash` cambia al
  excluir timestamps; el `LoopState` se mueve a `cycle.py`), pero **no rompe el flujo de 10 minutos**
  ni el contrato `--json` externo. Sin esto, el claim de reproducibilidad y de "ciclo no lineal" no
  se sostiene (Nota 06, RAÍZ 1/2).
- **v0.4+ — opcionales (Hitos 7–9):** dedup fuzzy, `Enricher` de co-citación, `NetworkSpec`.
- **1.0.0:** API congelada + caso real (IED) reproducido por un usuario distinto del autor (Nota 06,
  PRODUCTO).

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

## Hito 5 — Forrajeo/chaining + `Preprocessor` + filtros de curación · ✅ TERMINADO

> **Construido** así: `src/bib2graph/foraging/` (`Forager(source, *, depth=1, max_candidates=None)`
> con `preview` **sin red** —backward exacto local, `forward_requires_fetch` cuando se pide
> forward/both— y `chain` rankeado por *information scent* = **frecuencia de enlace** —`scent.py`
> puro, sin acoplamiento/centralidad—; `explain_candidate` stub gateado en `[llm]`);
> `src/bib2graph/preprocessors/` (`normalize` conservador + `apply_thesaurus` que **sobrescribe
> `keywords_id` desde `keywords_raw`**, multilingüe en/es/pt, idempotente); `src/bib2graph/filters/`
> (`apply_filter`/`apply_filters` puros que **marcan `rejected` —NO borran—** con conteo PRISMA por
> `FilterStep` y sellan `Manifest.filters`). Forward chaining usa `OpenAlexSource.fetch_citing` (no
> amplió el Protocol `Source`); `depth>1` → `NotImplementedError`. ADR
> [0020](decisiones/0020-metodo-forrajeo-scent-filtros-reject.md). Verifier PASA (**192 tests**
> verdes; preview network-free corregido). Decisiones de implementación de la IA en
> [`decisiones/registro-ia.md`](decisiones/registro-ia.md) (Hito 5). El comando CLI **`filter`** y la
> curación interactiva llegan en el Hito 6.
>
> ⚠️ **Reconciliación 2026-06-15 (ADR [0022](decisiones/0022-producto-sin-ia-generativa.md)):** lo
> de este hito relativo a IA queda **superado** — el *information scent* = frecuencia de enlace se
> **eleva a scent bibliométrico vía proyectores** en el **Hito R4**, y `explain_candidate` + el extra
> `[llm]` (historia B4) se **eliminan** (el producto no usa IA generativa). El registro de abajo
> describe el AS-BUILT v0.2 tal como se construyó; las menciones a `explain_candidate`/`[llm]`/B4 se
> leen como **historia**, retiradas por R4.

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

## Hito 6 — CLI agente-native como API (HITO DE PRODUCTO) · ✅ TERMINADO

> **Construido** así: paquete `src/bib2graph/cli/` (no `cli.py` plano) en **3 capas** — grupo Click
> con opción global obligatoria `--store` (`cli/__init__.py`) → un módulo por comando en
> `cli/commands/` con una **función núcleo `run_<cmd>(store_path, ...)` testeable sin Click** →
> helpers compartidos (`_envelope` con `schema="1"`, `_errors` con el decorador `@handle_errors`,
> `_store` con `open_store`). **11 subcomandos** (`seed`, `chain`, `filter`, `build`, `export`,
> `snapshot`, `status`, `inspect`, `validate`, **`accept`**, **`reject`**; los dos últimos y la
> separación `build`/`export` son **decisiones del PO**). **Envelope JSON común versionado** por
> comando; **exit codes 0–5 mapeados por tipo de excepción** (`DataError`→2, `ImportError`/
> `AttributeError`/`NotImplementedError`→3, `httpx.HTTPError`→4, `StoreLockedError`/`OSError`→5;
> *R5 cambió `AttributeError`→3 por `DependencyError`→3 con pre-check en el borde — ver Hito R5*);
> `--store` global (sin estado entre invocaciones, el estado vive en el `.duckdb`). El **`LoopState`
> transiciona automáticamente** por comando (`seed`→SEEDED, `chain`→FORAGED, `filter`→FILTERED,
> `build`→BUILT; el resto no transiciona). `build` computa `Networks.quick` + escribe artefactos a
> `<store_dir>/networks/`; `export` los relee y serializa (GraphML/CSV). El error de uso "sin
> `--store`" sale **sin envelope** (Click aborta el parseo: stderr + exit 1). ADR
> [0021](decisiones/0021-cli-agente-native-contrato.md). Verifier PASA (**214 tests** verdes;
> mypy/ruff limpios; el núcleo sigue importando sin `duckdb`). Decisiones de implementación de la IA
> en [`decisiones/registro-ia.md`](decisiones/registro-ia.md) (Hito 6).

**Alcance**

- CLI (Click) delgado: **11 subcomandos** — `seed`, `chain`, **`filter`**, `build`, `export`,
  `snapshot`, **`status`**, `inspect`, `validate`, **`accept`**, **`reject`** (los dos últimos,
  decisión del PO que **amplía** el set de 9 de API.md §convenciones; ADR 0021). **Cada subcomando
  con `--json` (envelope versionado), exit codes (0–5) por tipo de error, errores accionables,
  `--help` rico** (ADR 0010/0021, API.md §convenciones). Sin estado entre invocaciones (el estado
  vive en el archivo `.duckdb`, opción global `--store`).
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

# TANDA DE REMEDIACIÓN (Hitos R1–R5) — cerrar la brecha AS-BUILT ↔ TARGET

> **Va ANTES de los Hitos 7–11.** El red-team de la [Nota 06](Notas/06-critica-as-built-v0.2.md)
> y el modelo nuevo bloqueado por el PO (ADR [0022](decisiones/0022-producto-sin-ia-generativa.md)/
> [0023](decisiones/0023-capa-constants-modelos-schema.md) + enmiendas a 0008/0011/0016/0017/0020/0021)
> dejaron una brecha entre lo construido (v0.2) y el diseño objetivo (`ARCHITECTURE.md`, bloques
> `TARGET`). Esta tanda la cierra, **secuenciada por dependencia** (no por gravedad): nada de arriba
> se construye sobre cimientos que aún no existen.
>
> **Disciplina de la tanda:** es **refactor con la suite verde como red de seguridad** (214 tests al
> entrar). Cada hito R **preserva el comportamiento observable** salvo donde el ADR enmendado dice lo
> contrario (p. ej. R2 **cambia** el `corpus_hash` a propósito; R4 **elimina** `explain_candidate`).
> El núcleo sigue importando **sin `duckdb`**. El contrato `--json` externo del CLI **no driftea**
> (salvo el campo nuevo de curación en `status`, R3). Los tests viejos que codifican el AS-BUILT roto
> (p. ej. un test que espera `corpus_hash` distinto por timestamps) se **actualizan** al TARGET.

---

## Hito R1 — Cimientos: capa `constants` / `models` / `schemas` única · ✅ TERMINADO (2026-06-16)

> Primero porque **todo lo demás depende de esto** (ADR
> [0023](decisiones/0023-capa-constants-modelos-schema.md)): `constants/models` es la capa más baja
> del grafo de dependencias (`constants/models` → núcleo puro → costuras → CLI). Cierra CONSTANTS y
> MODELS de la [Nota 06](Notas/06-critica-as-built-v0.2.md). Es un refactor transversal **sin cambio
> de comportamiento observable** (la base segura sobre la que se apoyan R2–R4).

**Alcance**

- **`bib2graph/constants.py`** (capa base): `class Col(StrEnum)` con **todos** los nombres de columna
  del schema (§1.1 de API.md), `class CurationStatus(StrEnum)` (`candidate`/`accepted`/`rejected`) y
  `class NetworkKind(StrEnum)` (los 5 tipos de red). Reemplazar los **~62 string-literals** de columna
  (14 archivos) y los literales de `curation_status` (11 archivos) por referencias a estos enums.
- **`ProvenanceEvent(BaseModel)`** (fuente única del evento de procedencia:
  `{action, equation_id, chaining_hop, source, fetched_at, decided_by, decided_at}`), con
  construcción y **parseo que falla ruidoso** ante JSON corrupto (cierra el `_parse_provenance` que
  hoy hace `except … : return []` en silencio).
- **`schemas.py` como única definición de fila:** `PaperRow` (Pydantic) autoritativa; `CORPUS_SCHEMA`
  (Arrow) **derivado/verificado** de ella (no duplicado a mano en paralelo). Test que falla si
  driftean.
- **`Manifest.model_copy(update=...)`** en los 5+ sitios que hoy lo reconstruyen campo a campo.
- **Se mantiene** "`Paper`/`Author`/`Keyword`/`Institution` = vistas derivadas, no tipos" (ADR 0023):
  **no** se crean clases-entidad.

**Historias:** ninguna nueva (deuda de base); **habilita** R2 (excluir `ProvenanceEvent`/timestamps
del hash limpiamente) y blinda A4/C4 (procedencia honesta).

**Criterios de aceptación (DoD)**

- Un **typo de columna falla en import/type-check** (mypy), no en runtime tardío.
- No quedan string-literals de columna ni de `curation_status` fuera de `constants.py` (verificable
  con un grep en CI/local; el patrón ya existe para los exit codes en `cli/_errors.py`).
- `PaperRow` ⇄ `CORPUS_SCHEMA` provienen de **una** fuente: un test verifica que no driftean.
- `ProvenanceEvent` **falla ruidoso** ante JSON corrupto (no `return []`).
- La suite del Hito 1–6 pasa **sin cambios de expectativa** (refactor sin cambio de comportamiento).

**Tests (TDD — los justos)**

- `PaperRow` ⇄ `CORPUS_SCHEMA`: un test de equivalencia de campos/tipos (falla si se desincronizan).
- `ProvenanceEvent`: round-trip + **falla explícita** ante JSON corrupto (reemplaza el swallow).
- *No testear* cada enum miembro por separado (trivial); sí un test de que el schema usa `Col`.

**Recomendaciones para el `coder`** (`archivo:símbolo`):

- Crear `src/bib2graph/constants.py` (`Col`, `CurationStatus`, `NetworkKind`) y
  `src/bib2graph/models.py` (`ProvenanceEvent`). Reemplazar literales en `schemas.py`,
  `backends/memory.py`, `backends/duckdb.py`, `filters/prisma.py`, `cli/commands/validate.py` y los
  demás (Nota 06 CONSTANTS: 11 archivos con literales de estado, 14 con literales de columna).
- `backends/memory.py:78-95` (`_parse_provenance`): el `except (json.JSONDecodeError, TypeError):
  return []` debe **fallar** (o registrar y relanzar), no tragarse el corrupto.
- `schemas.py`: derivar/verificar `CORPUS_SCHEMA` desde `PaperRow` (hoy 22 campos duplicados a mano).
- `Manifest`: `model_copy(update=...)` en `sources/openalex.py:462`, `foraging/forager.py:259`,
  `filters/prisma.py:198`, `preprocessors/preprocessor.py:58,107`, `corpus.py:462`.

**Se vuelve posible:** una base de vocabulario que el type-checker protege; el refactor de R2–R4 se
apoya en `Col`/`CurationStatus`/`ProvenanceEvent` en vez de literales.

---

## Hito R2 — Reproducibilidad / identidad: content-hash vs procedencia + Louvain seeded · ✅ TERMINADO (2026-06-16)

> Segundo porque **necesita `ProvenanceEvent` (R1)** para separar identidad de procedencia con
> limpieza. Cierra la RAÍZ 2 de la [Nota 06](Notas/06-critica-as-built-v0.2.md) y la enmienda
> 2026-06-15 del ADR [0017](decisiones/0017-reproducibilidad-historia-snapshot.md). Es el hito que
> **cambia el `corpus_hash` a propósito** (breaking interno): dos corridas que aceptan los mismos ids
> pasan a dar el **mismo** hash.
>
> ✅ **As-built (2026-06-16):** `compute_corpus_hash` excluye `provenance` (sigue incluyendo
> `curation_status`); el reloj se inyecta desde las **tres** fronteras de curación (`accept`,
> `reject` y **`filter`** vía `apply_filters(decided_at=…)`); el núcleo conserva un **fallback
> `datetime.now(UTC)`** documentado para uso como **librería** sin `decided_at` (no afecta la
> identidad, que excluye provenance — ver ADR 0017 enmienda punto 3); Louvain seeded con
> `random_state` derivado del content-hash (`_louvain_seed_from_hash`). **247 tests** verdes
> (13 nuevos en `test_r2_reproducibility.py`), mypy strict / ruff limpios. **`resolution`
> diferido a Hito 9** (NetworkSpec declarativo) — ver DoD abajo y ADR 0017 punto 4.

**Alcance**

- **Identidad (contenido) ≠ procedencia (auditoría):** `compute_corpus_hash` se computa **solo sobre
  contenido bibliográfico**, **excluyendo** `provenance` (`ProvenanceEvent`/timestamps). La
  procedencia es un **log append-only fuera de la identidad** (auditar, no identificar).
- **Reloj en la frontera, no en el núcleo:** `accept`/`reject`/`filter` **reciben el instante**
  (`decided_at`) como parámetro inyectado desde el CLI. El núcleo conserva un **fallback
  `datetime.now(UTC)`** documentado para uso como librería sin `decided_at` (no afecta la identidad,
  que excluye provenance) — ADR 0017 enmendado, punto 3.
- **Louvain seeded:** `detect_communities(method="louvain")` corre con `random_state` **derivado del
  content-hash** → comunidades **reproducibles** entre corridas. (`resolution` **diferido a Hito 9**,
  NetworkSpec — ver DoD.)

**Historias:** cierra **E1** de verdad (el snapshot **sí** se reproduce bit a bit) y endurece **A4**
(procedencia auditable separada de la identidad).

**Criterios de aceptación (DoD)**

- ✅ **Dos corridas que aceptan los mismos ids producen el mismo `corpus_hash`** (antes diferían por
  los timestamps) → el snapshot es reproducible bit a bit (cumple el ADR 0017 y `facade.py:6`).
  `test_corpus_hash_estable_ante_timestamps_distintos`.
- ✅ `accept`/`reject`/`filter` inyectan `decided_at` desde la **frontera** (CLI). **Reconciliado:** el
  núcleo conserva un **fallback `datetime.now(UTC)`** cuando se usa como **librería** sin `decided_at`
  (ergonomía de `corpus.accept(ids)`); el fallback **no** rompe el DoD porque el `decided_at` no entra
  al hash (identidad ≠ procedencia, ADR 0017 punto 3). El contrato honesto: "el reloj se inyecta en la
  frontera; el núcleo solo usa `datetime.now()` como fallback de librería, fuera de la identidad". El
  path real de la CLI nunca toca el fallback.
- ✅ `detect_communities(..., method="louvain", random_state=…)` da **la misma partición** entre
  corridas para el mismo grafo (seed derivado del content-hash, `_louvain_seed_from_hash`).
  ⚠️ **`resolution` DIFERIDO a Hito 9** (NetworkSpec): el punto 4 del ADR 0017 / el alcance original
  pedían exponer `resolution`; se difiere al hito donde `NetworkSpec` gana parámetros por algoritmo
  vía YAML. R2 entrega la pata reproducible (el `random_state` seeded), que es la que importa para
  la identidad; `resolution` queda en el default de `python-louvain`. Diferimiento aditivo.
- ✅ La suite pasa (247 verdes); no había test viejo que esperara hashes distintos por timestamps.

**Tests (TDD — los justos)**

- **Hash estable bajo curación:** aceptar los mismos ids en dos corridas → mismo `corpus_hash`
  (regresión directa de RAÍZ 2).
- Reloj inyectado: `accept(ids, decided_at=…)` registra el instante recibido; el núcleo no toca el
  reloj de sistema (un test que pasa un instante fijo y verifica el evento).
- Louvain determinista: misma partición en dos corridas sobre un grafo sintético.

**As-built (`archivo:símbolo`):**

- ✅ `backends/memory.py` (`compute_corpus_hash`): **excluye** la columna `provenance` del hash
  (sigue incluyendo `curation_status`); order-independent intacto.
- ✅ `backends/memory.py` (`_apply_curation_to_rows`, `apply_curation`) y `corpus.py`
  (`accept`/`reject` con `decided_at: datetime | None`): reciben `decided_at` desde la frontera;
  **fallback `datetime.now(UTC)`** cuando es `None` (uso como librería).
- ✅ `filters/prisma.py` (`apply_filter`/`apply_filters` con `decided_at`) + `cli/commands/filter.py`
  (inyecta un único `datetime.now(UTC)` para todos los pasos PRISMA de la invocación).
- ✅ `cli/commands/accept.py`, `reject.py` inyectan `datetime.now(UTC)`.
- ✅ `networks/facade.py` (`_louvain_seed_from_hash`, threadeado por `_build_artifact`) +
  `networks/analyzer.py` (`detect_communities(..., random_state=…)`): Louvain seeded con el
  content-hash. ⚠️ `resolution` **NO** expuesto — **diferido a Hito 9** (ver DoD).

**Se volvió posible:** la promesa central del producto —**reproducir bit a bit** un snapshot— deja de
ser falsa. El forrajeo/curación/análisis son deterministas de punta a punta.

---

## Hito R3 — Ciclo: FSM cíclico de dominio (`cycle.py`) + `reseed`/ronda + curación transversal · ✅ TERMINADO (2026-06-16)

> Tercero porque el ciclo se apoya en los cimientos (R1) y conviene que la identidad ya sea estable
> (R2) antes de modelar `reseed`/acumulación. Cierra la RAÍZ 1 (la parte del lazo) de la
> [Nota 06](Notas/06-critica-as-built-v0.2.md) y la enmienda 2026-06-15 de los ADR
> [0016](decisiones/0016-maquina-estados-lazo.md)/[0021](decisiones/0021-cli-agente-native-contrato.md).
>
> ✅ **As-built (2026-06-16):** `src/bib2graph/cycle.py` es el **dominio puro** (sin DuckDB):
> `CycleState` (`SEEDED/FORAGED/FILTERED/BUILT/MONITORED`), `apply_transition(state, action, round)
> → (state, round)`, `available_transitions(state)`, `CURATION_ACTIONS`. El enum de estados **salió**
> del backend; `backends/duckdb.py` solo persiste (columna `round` en `loop_state_log` por migración
> liviana; `loop_round()` / `set_loop_state(state, *, cycle_round=...)`) y mantiene el **alias
> transicional `LoopState = CycleState`** (a retirar pre-1.0). `reseed` es de primera clase
> (loop-back a `SEEDED` + ronda++): lo cablea `seed.py` (estado previo ⇒ re-sembrado, acumula).
> **Fuente única de verdad:** `chain`/`filter`/`build` **derivan** su estado destino de
> `apply_transition` (gap del verifier cerrado; test domain-tied en `test_r3_commands_domain.py`).
> `status` expone `curation_available`/`round` **aditivos** manteniendo `schema="1"`. `MONITORED`
> está en el modelo pero **sin comando que lo dispare** (futuro). **275 tests** verdes (R3 + 9
> domain-tied del fix), mypy strict / ruff limpios. Decisiones de implementación de la IA en
> [`decisiones/registro-ia.md`](decisiones/registro-ia.md) (Hito R3).

**Alcance**

- **`bib2graph/cycle.py` — FSM cíclico como concepto de dominio puro** (el enum y las reglas de
  transición salen del backend; el backend **solo lo persiste**): estados
  `SEEDED → FORAGED → FILTERED → BUILT → MONITORED`.
- **`reseed` como transición de primera clase** ("la idea muta"): vuelve a `SEEDED`, **incrementa un
  contador de RONDA** y **acumula** sobre lo curado (no es solo "transición permisiva"). Es lo que el
  ADR 0016 prometía y el AS-BUILT no cumplía.
- **`MONITORED`** modela el paso 8 del ciclo (Nota 05 §3). *(El comando que lo dispara puede ser
  futuro; el estado existe en el modelo.)*
- **Curación TRANSVERSAL:** `accept`/`reject` están disponibles **en cualquier estado**, **no
  transicionan**, pero `b2g status` **debe** mostrarlas como **acción siempre-disponible** (hoy las
  oculta) y exponer el **contador de ronda**. Humanos e IAs ven en el mapa lo único irreductiblemente
  humano.

**Historias:** cierra **A5** de verdad (re-sembrar que acumula con contador de ronda, no una corrida
tirada) y **C4** (la curación aparece en el mapa del lazo); refuerza **E2** (el `status` agente-native
no miente sobre el ciclo).

**Criterios de aceptación (DoD)**

- El modelo de estados + transiciones vive en `cycle.py` (núcleo puro, testeable **sin** DuckDB); el
  `DuckDBBackend` **solo lo persiste** (log append-only, ya existente).
- `reseed` vuelve a `SEEDED`, **incrementa la ronda** y conserva lo curado (un test de acumulación
  entre rondas).
- `b2g status` (humano y `--json`) muestra: estado actual, **transiciones disponibles**, **`accept`/
  `reject` como acción siempre-disponible**, **contador de ronda** y conteos por `curation_status`.
- El campo nuevo del envelope `--json` de `status` (`curation_available`/`round`) es **aditivo** y
  **mantiene `schema="1"`** (decisión del PO 2026-06-16: campos nuevos no rompen a los agentes, no se
  bumpea).

**Tests (TDD — los justos)**

- `cycle.py` puro: secuencia de transiciones válidas + `reseed` (loop-back a `SEEDED`, ronda++),
  **sin** DuckDB.
- Acumulación entre rondas: re-sembrar tras `BUILT` no pierde lo aceptado.
- Contrato `--json` de `status`: incluye `curation_available`/`round`/transiciones (golden/schema);
  no driftea.
- *No testear* el plumbing de Click de `status` (se testea `run_status`).

**Recomendaciones para el `coder`** (`archivo:símbolo`):

- Crear `src/bib2graph/cycle.py` y **mover** el enum `LoopState` (hoy `backends/duckdb.py:67-78`) +
  las reglas de transición al núcleo; el backend persiste, no define el dominio. (Renombrar a
  `CycleState`/`cycle` según prefiera el `coder`; el comando sigue siendo `status`.)
- `cli/commands/status.py:19-34`: agregar `accept`/`reject` como acción siempre-disponible y exponer
  el contador de ronda (hoy `transitions_available` nunca los lista).
- `cli/commands/accept.py:104` / `reject.py`: documentar explícitamente "curación transversal, no
  transiciona" (alineado con `status`).
- Cablear `reseed` (loop-back + ronda) en el flujo de `seed` cuando ya hay estado previo (acumula).

**Se vuelve posible:** el "ciclo no lineal" deja de ser solo prosa: `reseed`/ronda son de primera
clase y la curación —lo irreductiblemente humano— por fin figura en el mapa del lazo.

---

## Hito R4 — Scent bibliométrico vía proyectores + retiro de `explain`/`[llm]`/tensiones · ✅ TERMINADO (2026-06-16)

> **AS-BUILT (2026-06-16):** R4 reescribió `foraging/scent.py` para consumir el primitivo público
> `collect_item_to_papers` de `networks/projectors.py` (el forrajeo **depende del núcleo de
> proyección**, nunca al revés), y **eliminó** `foraging/explain.py`/`explain_candidate` y el extra
> `[llm]` (ADR 0022). **291 tests** verdes, mypy strict / ruff limpios. El **steering arquitectónico
> (2026-06-16)** resolvió tres cuestiones de método: **backward = fuerza de co-citación con el corpus**
> (ratificado), **forward = fuerza de citación directa al corpus** (señal primaria; el AS-BUILT inicial
> midió *acoplamiento puro* —que **degenera a 0** con referencias ralas— y se **corrigió a citación
> directa dentro de R4**) y **centralidad diferida** (no es requisito de cierre; el DoD "y/o" se cumple
> con co-citación + citación-directa). Ver AS-BUILT del ADR
> [0020](decisiones/0020-metodo-forrajeo-scent-filtros-reject.md) (fórmulas + recomendación de código
> del forward, **implementada**). **Cierre total:** `compute_forward_scent` calcula
> `forward_score(Y) = |{ref ∈ Y.references_id : ref ∈ corpus_ids}|` (citación directa, emite con
> `direct > 0`); la elimina-IA, el scent-vía-proyectores y el forward robusto **están cerrados**. R4 no
> deja seguimiento abierto.
>
> Cuarto porque el scent-vía-proyectores **consume el núcleo de proyección** (Hito 2, ya construido) y
> conviene tener identidad estable (R2) para que el ranking sea reproducible. Cierra la RAÍZ 1 (la
> parte de IA) de la [Nota 06](Notas/06-critica-as-built-v0.2.md) y las enmiendas 2026-06-15 de los
> ADR [0020](decisiones/0020-metodo-forrajeo-scent-filtros-reject.md) (scent = proyectores),
> [0022](decisiones/0022-producto-sin-ia-generativa.md) (el producto no usa IA) y
> [0008](decisiones/0008-wedge-forrajeo.md) (tensiones retiradas).

**Alcance**

- **El *information scent* pasa de frecuencia de enlace a proyectores:** un candidato rankea por
  cuánto se **acopla / co-cita / es central** respecto del corpus curado (consume `networks/` — el
  núcleo de proyección puro). Sigue siendo **función pura y determinista** (mismo corpus → mismo
  ranking); el forrajeo (costura) **depende del núcleo de proyección**, nunca al revés.
- **Eliminar la rama de IA del producto** (ADR 0022): borrar `foraging/explain.py` y `explain_candidate`
  de la superficie pública; **eliminar el extra `[llm]`** de `pyproject.toml`; quitar el fallback
  semántico/LLM del thesaurus (ADR 0011 enmendado: el thesaurus es curado y determinista, lo que no
  matchea queda fuera).
- **Retirar la "máquina de tensiones"** del alcance (ADR 0008/0022): **no se difiere a v2, se borra**
  del producto y de las "Costuras futuras". El sensemaking es **humano**, asistido por las redes.
- **Arreglar los docstrings de scent** que mienten sobre la dirección (Nota 06, secundarios).

**Historias:** **re-define B3** (ranking por estructura bibliométrica real, no por conteo plano);
**retira B4** (explicación opcional de IA) — deja de ser historia del producto.

**Criterios de aceptación (DoD)**

- `chain` rankea por **estructura bibliométrica** del candidato con el corpus (consume el primitivo
  `collect_item_to_papers` de `networks/`), **determinista** (mismo corpus → mismo orden). El DoD
  listaba "acoplamiento **/** co-citación **/** centralidad" (un **"y/o"**: pide señal estructural de
  red, no las tres). **AS-BUILT R4:** backward = **co-citación** (cuántos corpus-papers co-citan al
  candidato); forward = **citación directa al corpus** (señal primaria robusta) con acoplamiento como
  secundario. **Centralidad diferida** a viz (excede el olfato barato y determinista). Espíritu del
  DoD cumplido. *(El forward as-built fue acoplamiento puro y se corrigió a citación directa dentro de
  R4: `compute_forward_scent` emite con `direct > 0`.)*
- **No existe** `explain_candidate`, `foraging/explain.py` ni el extra `[llm]` (verificable: import
  falla, el extra no está en `pyproject.toml`). El thesaurus no tiene fallback LLM.
- El **sesgo de confirmación** (efecto Mateo) del scent queda documentado: el scent **prioriza**; la
  exhaustividad la sostienen los filtros PRISMA y el conteo de exclusiones, no el scent.
- La suite pasa; los tests de `explain_candidate`/`[llm]` se **retiran** (la capacidad ya no existe).

**Tests (TDD — los justos)**

- Ranking por scent-vía-proyectores: candidatos con acoplamiento/centralidad conocidos salen en el
  **orden** esperado, sobre un corpus sintético con resultado calculado a mano.
- Determinismo: mismo corpus → mismo ranking (regresión).
- Que `import` de `explain_candidate` **falle** (la superficie ya no lo expone).
- *No testear* la calidad bibliométrica del clustering en sí (ya cubierto en Hito 2).

**Recomendaciones para el `coder`** (`archivo:símbolo`):

- `foraging/scent.py:27-125`: reescribir `compute_backward/forward_scent` para consumir los
  **proyectores** (`networks/projectors.py`) en vez de `Counter`/`sum` sobre `references_id`/
  `cited_by_id`. El forrajeo depende del núcleo de proyección (no al revés).
- **Borrar** `foraging/explain.py` (`explain_candidate`, `NotImplementedError` en `:47`); quitarlo de
  la superficie pública (`bib2graph.foraging`).
- `pyproject.toml`: **eliminar el extra `[llm]`** (vacío). Quitar cualquier gate `[llm]` en
  `preprocessors/` (thesaurus sin fallback semántico).
- `foraging/scent.py:11,80` vs `:114`: corregir los docstrings que invierten la dirección.

**Se vuelve posible:** el scent **es** la bibliometría que la Nota 05 promete (no un conteo), y el
producto queda **honesto: sin IA generativa** (ADR 0022). Un solo sentido de "AI-in-the-loop": el
desarrollo es asistido por IA; el producto no.

---

## Hito R5 — Robustez / escala: bulk-load, UTF-8 en la frontera, footguns de la Nota 06 · ✅ TERMINADO (2026-06-16)

> Último de la tanda: no cambia el modelo conceptual, **endurece** lo construido. Cierra la RAÍZ 3 y
> el catálogo de secundarios de la [Nota 06](Notas/06-critica-as-built-v0.2.md). Independiente de
> R1–R4 en su mayoría; se ubica al final para no mezclar refactor de modelo con hardening.
>
> **AS-BUILT (2026-06-16):** R5 reemplazó el loop `add_paper`/`_clone` por **bulk-load**
> (`Corpus.from_arrow` + helper `corpus._rows_with_ids`) en los cuatro loaders (seed/load OpenAlex,
> BibTeX, Forager), forzó **UTF-8 en la frontera** (`cli/__init__.py:main` → `_force_utf8()` antes de
> que Click lea nada) y agregó **retry/backoff** ante 429/5xx en `fetch_citing`
> (`_fetch_all_with_retry`, exp backoff, 3 intentos). Cerró los **8 footguns** del catálogo de
> secundarios. **319 tests** verdes (`test_r5_robustness.py` + ajustes), mypy strict / ruff
> check+format limpios. **Verifier: APRUEBA** (reservas cerradas).
>
> **DoD reconciliado honestamente — el batching-por-OR quedó DIFERIDO.** El DoD pedía que
> `fetch_citing` *"batchee y reintente 429/5xx"*; el AS-BUILT entrega **solo retry/backoff** (la pata
> de correctitud/robustez: un rate-limit ya no pierde papers). El **batching por OR** (agrupar varios
> `cites:` en una sola query para matar el N+1) **NO se implementó** — el spec lo pedía "si es
> factible" y queda como **mejora de PERFORMANCE futura** (el N+1 persiste, pero ahora es resiliente).
> Distinguir: el retry SÍ se hizo; el batching NO. (Ver registro-ia R5.3 y "Decisiones de seguimiento".)
>
> **Cierre de la tanda:** con R5 la **remediación R1–R5 queda COMPLETA** — la brecha AS-BUILT↔TARGET
> del red-team (Nota 06: RAÍZ 1, 2, 3 + secundarios) está cerrada. Lo que sigue son los Hitos 7–11
> (capacidades nuevas hacia v1.0), no remediación.

**Alcance**

- **Fin del O(n²) en carga:** los loaders (seed/load OpenAlex, BibTeX, forager) usan el bulk
  `Corpus.from_arrow` en vez del loop `add_paper`/`_clone` que re-upserta la tabla entera por fila.
- **UTF-8 en la frontera CLI:** forzar `sys.stdout`/`stderr` a UTF-8 (o `encoding="utf-8"` explícito)
  en el entry point, para que el envelope `--json` (`ensure_ascii=False`) y `--help` no corrompan
  acentos en Windows (cp1252). **Arreglo de mayor impacto/menor costo**; restaura el contrato
  agente-native (ADR 0010/0021) en Windows.
- **Batching + retry/backoff en forward chaining:** `fetch_citing` deja de hacer N+1 requests
  seriales sin reintento ante 429/5xx.
- **Footguns de la Nota 06 (catálogo de secundarios):**
  - **rama muerta en `_errors.py`** (manejo de `OSError`: el `if isinstance(..., StoreLockedError)`
    y el `else` hacen lo mismo) → simplificar; y `AttributeError`→"Capacidad no disponible" es
    **engañoso** (un bug real se reporta como dependencia faltante) → distinguir.
  - **auto-creación del store** ante typo en `--store` (`status`/`validate`) → no auto-crear en
    comandos de solo lectura.
  - **`.bib` roto / filtros PRISMA con campo-op desconocido = no-op silencioso** → warning o error
    accionable (no tragar).
  - **param muerto `g`** en `cocitation_quality_report` → quitarlo (anti-patrón que ARCHITECTURE §8
    dice evitar).
  - **`_lib_version` fallback `"0.0.0"`** mete versión falsa en el `Manifest` → fallar o marcar
    `unknown`, no inventar versión.
  - **`except Exception` en `detect_communities`** (`facade.py`) que traga el fallo → no enmascarar.
  - **`_QUICK_KINDS` duplica el `Literal` de `NetworkSpec.kind`** → fuente única (usar `NetworkKind`
    de R1).

**Historias:** ninguna nueva; **endurece** E2 (el contrato agente-native funciona en Windows) y todo
el flujo a escala mediana.

**Criterios de aceptación (DoD)**

- Cargar un corpus mediano no es O(n²) (los loaders usan `from_arrow`); un test/benchmark de no
  regresión razonable.
- En Windows, `b2g ... --json` y `--help` devuelven acentos correctos (UTF-8 forzado) — regresión del
  bug verificado de la Nota 06.
- ~~`fetch_citing` batchea y~~ **reintenta 429/5xx sin perder papers** (sobre cliente mock).
  **AS-BUILT:** la pata de **retry/backoff** se cumple (`_fetch_all_with_retry`, exp backoff, 3
  intentos); el **batching por OR queda DIFERIDO** (mejora de performance — el spec lo pedía "si es
  factible"; el N+1 persiste pero ahora es resiliente al rate-limit, que era la falla de correctitud).
- Cada footgun del catálogo: el comportamiento silencioso pasa a **fallar/avisar accionable** o se
  elimina la rama muerta/param muerto/versión falsa. Sin no-ops silenciosos.

**Tests (TDD — los justos)**

- **UTF-8:** el envelope con un acento se decodifica bien forzando UTF-8 (regresión directa).
- `@handle_errors`: un caso por exit code **incluido `4`** (hoy sin assert) y el `5` real (no la
  rama muerta).
- `.bib` roto / filtro con campo-op desconocido → **warning/raise** (no no-op).
- Retry de `fetch_citing` ante 429/5xx sobre cliente mock (no en tiempo real).
- *No testear* el rate limiter en tiempo real ni el motor DuckDB.

**Recomendaciones para el `coder`** (`archivo:línea`, de la Nota 06):

- Loaders → bulk `Corpus.from_arrow` en vez de `add_paper`/`_clone` (`backends/duckdb.py:319,368`).
- UTF-8 en el entry point del CLI (`cli/_envelope.py:67` usa `ensure_ascii=False` sin forzar stdout).
- `foraging/forager.py:307` → `sources/openalex.py:394-425`: ~~batch +~~ retry/backoff para
  `fetch_citing`. **AS-BUILT:** retry/backoff implementado (`_fetch_all_with_retry`); batch-por-OR diferido.
- `cli/_errors.py:139-147` (rama muerta `OSError`), `:155-159` (`AttributeError` engañoso);
  `corpus.py:46-53` (`_lib_version` fallback `"0.0.0"`); `networks/facade.py:104` (`except Exception`
  en `detect_communities`); `sources/bibtex.py:206,210` (`.bib` silencioso);
  `filters/prisma.py:115` (filtro no-op); `networks/analyzer.py:277` (param muerto `g`);
  `networks/facade.py:39` vs `spec.py:42-48` (`_QUICK_KINDS` duplica `NetworkKind`);
  `backends/duckdb.py:417,423` (SQL por interpolación de strings en `merge` — hoy seguro, frágil).
- `status`/`validate` auto-crean el store ante typo en `--store` → no auto-crear en solo-lectura.

**Se vuelve posible:** bib2graph corre a escala mediana, el contrato agente-native funciona en
Windows, y desaparecen los no-ops silenciosos que esconden bugs.

---

# LO QUE VIENE (Hitos 7–11, actualizados a la nueva realidad)

> **Tras la remediación R1–R5.** Estos hitos son los opcionales/de cierre hacia v1.0, ya
> reconciliados con el modelo nuevo (sin IA generativa, scent bibliométrico, FSM cíclico).

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
- **Parámetros por algoritmo de clustering** — entre ellos `resolution` de Louvain (diferido de
  **R2**, ADR 0017 punto 4): el `random_state` ya es seeded desde R2; aquí se expone `resolution`
  (y demás params) vía la spec declarativa.

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
- Tool schemas JSON / servidor MCP → posterior, si la demanda lo justifica. El CLI ya cubre la
  frontera programática desde el Hito 6.

No se prometen ni se cablean clientes que no se usan.

> **RETIRADO del producto (ADR [0022](decisiones/0022-producto-sin-ia-generativa.md), 2026-06-15):**
> el **fallback fuzzy/semántico del thesaurus por LLM** y la **"máquina de tensiones"** (la antigua
> "inserción de IA nº2") **ya no son costuras futuras: se borran**. El producto **no usa IA
> generativa**; el extra `[llm]` se elimina (Hito R4). El sensemaking de tensiones es **humano**,
> asistido por las redes. El **dedup fuzzy del thesaurus** que sí queda (Hito 7) es **determinista**
> (`rapidfuzz`/`splink`, extra `[dedup]`), no semántico/LLM. La única "inteligencia" que asiste es el
> **scent bibliométrico** (Hito R4), que no es IA.

---

## Trazabilidad historias ↔ hitos (resumen)

| Historia (PRD §7) | Hito principal | Notas |
|---|---|---|
| A1 sembrar por ecuación | 4 | `OpenAlexSource.seed` |
| A2 query ejecutada + reporte | 4 | `SeedResult` |
| A3 sembrar por semillas/`.bib` | 4 | `BibtexSource` |
| A4 ecuación registrada/versionada | 1 + 4 | `provenance`/`Manifest` |
| A5 ecuaciones que mutan + acumular | 3 + 6 ✅ | biblioteca viva + re-seed por CLI (`b2g seed` acumula vía `--store`) |
| B1 back/forward chaining | 5 ✅ | `Forager.chain` (backward puro / forward red vía `fetch_citing`) |
| B2 profundidad + preview | 5 ✅ | `preview` SIN red (`forward_requires_fetch`), `max_candidates`; `depth>1` futuro |
| B3 ranking por estructura | 5 ✅ (frecuencia de enlace) → **R4** (proyectores) | as-built = frecuencia de enlace (ADR 0020); R4 lo eleva a scent **bibliométrico vía proyectores** (acoplamiento/co-citación/centralidad), determinista |
| ~~B4 explicación opcional de IA~~ | **RETIRADA** (R4) | `explain_candidate`/`[llm]` **eliminados** (ADR 0022): el producto no usa IA generativa. El "porqué" lo explica la estructura visible, no un LLM |
| C1 dedup/normalización autores/inst. | 5 ✅ (det.) + 7 (fuzzy) | `normalize` conservador construido; fuzzy en Hito 7 |
| C2 thesaurus multilingüe | 5 ✅ | `apply_thesaurus` (sobrescribe `keywords_id` desde `keywords_raw`) |
| C3 filtros incl/excl con conteo | 5 ✅ (lógica) + 6 ✅ (CLI `filter`) | flujo PRISMA; marcan `rejected`, no borran; `b2g filter` con conteos por paso |
| C4 aceptar/rechazar + biblioteca viva | 1 (modelo) + 1.5 (backend) + 3 (persist DuckDB) + 6 ✅ (CLI `accept`/`reject`) + 11 (Zotero) | `accept`/`reject` ahora subcomandos CLI (`b2g accept/reject --ids`); `curate`+GUI = futuro |
| D1 cinco proyecciones | 2 + 8 (co-citación) | |
| D2 métricas y comunidades | 2 | |
| D3 asortatividad + composición + proxy | 2 | |
| D4 export GraphML/CSV | 2 | |
| E1 snapshot reproducible | 1 + 6 ✅ | `Corpus.snapshot` + `b2g snapshot` |
| E2 CLI `--json` + exit codes | 0 (principios) + 6 ✅ (CLI) | `b2g` 11 subcomandos, envelope `--json` versionado, exit 0–5 (ADR 0021) |
