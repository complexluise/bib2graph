# Registro de decisiones tomadas por la IA

> Bitácora de las decisiones que **tomó la IA** (Claude) de forma autónoma mientras avanza el
> ROADMAP hacia la v1.0, por pedido del Product Owner humano. Complementa el
> [registro de ADRs](README.md): las decisiones **arquitectónicas** van a un ADR numerado (con
> la línea `Decidido por: IA`); las decisiones **de implementación / proceso** más chicas se
> anotan acá.
>
> Convención: cada decisión registra **fecha**, **qué se decidió**, **por qué**, su
> **reversibilidad** y si fue **validada por el humano**. Si una decisión de la IA resulta
> equivocada, se corrige con una entrada nueva (no se reescribe la historia).

## Cómo se marca la autoría de la IA

- **ADRs:** campo `- **Decidido por:** IA (Claude ...)` en el encabezado.
- **Commits:** los hace la IA; el trailer `Co-Authored-By: Claude` ya lo refleja.
- **Decisiones de proceso/implementación:** una entrada en este archivo.

---

## 2026-06-15 — Sprint 0 (preparación / andamiaje)

| # | Decisión | Por qué | Reversibilidad | Validada por humano |
|---|----------|---------|----------------|---------------------|
| 0.1 | **`httpx` como cliente OpenAlex** (en vez de `pyalex` u otro SDK) | Testeable con `httpx.MockTransport` sin red en CI; control fino de la query y del reporte de traducción (ADR 0007) | Media: cambiar de cliente afecta solo la costura `OpenAlexSource` | Pendiente (asumida) |
| 0.2 | **`python-louvain` en el núcleo**, no en un extra | Louvain es la detección de comunidades por defecto (API.md §8); declararlo evita el bug de v0 (lección 7) | Alta: mover a extra `[community]` es trivial | Pendiente (asumida) |
| 0.3 | **`dev` en `[tool.uv] dev-dependencies`**, no como extra publicable | uv 0.4.16 no estabiliza PEP 735; así las dev-deps no se publican a PyPI | Alta | Sí (uv-native pedido por el humano) |
| 0.4 | **Pin de Python 3.12** en `.python-version` (`requires-python >=3.11`) | 3.12 estable y disponible local; deja 3.11 como piso de compatibilidad | Alta | Pendiente (asumida) |
| 0.5 | **Smoke tests mínimos del Hito 0** (import sin efectos + placeholder CLI), no más | Disciplina TDD selectiva del ROADMAP: testear solo lo que tiene contrato/riesgo | Alta | Sí (criterio del ROADMAP) |
| 0.6 | **ADR 0012** (credenciales OpenAlex: email + key opcional inyectados) | Cerrar el detalle de la key obligatoria-desde-feb-2026 antes del Hito 4 | N/A (registro) | Sí (el humano pidió el ADR) |
| 0.7 | **Commits a `main`** (sin feature branches ni GitHub por ahora) | El repo es solo-local sin remoto; la historia previa ya commitea docs a `main` | Alta | Sí (humano: "no GitHub por el momento") |

> **Decisiones del Product Owner humano** (no de la IA, registradas para contexto): adoptar uv;
> alcance de v0.1 = Hitos 1–4; objetivo v1.0 vía `/feature-cycle`; sin GitHub por ahora.

---

## 2026-06-15 — Hito 1 (Corpus: núcleo de la tabla canónica)

> Las decisiones **arquitectónicas** de este hito (D1 `id` estable, D2 `corpus_hash`
> order-independent, D3 reglas de `merge`, D4 `provenance` como log append-only, y la igualdad de
> `Corpus` vía `corpus_hash`) van en el ADR
> [0013](0013-identidad-hash-merge-corpus.md), no como filas acá. Lo de abajo son las decisiones
> **de implementación / proceso** del hito.

| # | Decisión | Por qué | Reversibilidad | Validada por humano |
|---|----------|---------|----------------|---------------------|
| 1.1 | **Manifest D5: campos obligatorios sin default vs opcionales con default** (`schema_version`, `corpus_hash`, `lib_version`, `created_at` obligatorios; `equations=[]`, `chaining=None`, `preprocessors=[]`, `filters=[]`, `enrichers=[]`, `openalex_version=None`). El `Corpus` en memoria lleva `corpus_hash=""` y el hash real se sella en `snapshot()`/`CorpusSnapshot` | Un Manifest se puede construir desde un `Corpus` recién sembrado sin conocer aún el contenido completo; obligar todo rompería la semántica de valor. El hash es derivable del contenido, no un dato de entrada | Alta: agregar/quitar defaults no rompe el parquet ni el contrato público (round-trip JSON) | Sí (PO proxy) |
| 1.2 | **`schema_version` D6: solo se escribe y round-tripea en Hito 1** (sin lógica de rechazo por incompatibilidad) | No hay todavía migraciones ni un store vivo donde versiones distintas convivan; agregar rechazo ahora sería especular. Se difiere al hito con migraciones sobre DuckDB (ADR 0009) | Alta: agregar la lógica de compatibilidad es aditivo | Sí (PO proxy) |
| 1.3 | **Fix de determinismo: `Corpus.__eq__` canónico vía `corpus_hash` + orden de `merge` por primera aparición** (antes `__eq__` usaba `pa.Table.equals`, sensible al orden) | `pa.Table.equals` daba falsos negativos ante el mismo contenido en distinto orden de filas/listas y era frágil ante `PYTHONHASHSEED` (21 tests bajo 12 seeds). La igualdad por `corpus_hash` es consistente con D2; `merge` emite un orden determinista para snapshots diffeables | Media: cambia la semántica observable de `==` y del orden de filas; revertir exigiría re-tocar tests. Consistente con el ADR 0013 | Sí (PO proxy; verifier PASA) |

> Las decisiones D1–D4 (arquitectónicas) están en el ADR
> [0013](0013-identidad-hash-merge-corpus.md). El símbolo público `SchemaError` se exporta desde
> `__init__.py` (ver `API.md` §1).

---

## 2026-06-15 — Hito 2 (proyectores + analizadores + exportadores + `Networks.quick`)

> Las decisiones **arquitectónicas** de este hito (D1 peso = conteo crudo + `min_weight`, D2 tipo
> de nodo por proyección, D3 `quick` sin co-citación, D4 asortatividad por atributo configurable
> con proxy, y la nota del proxy de país en `min_countries`) van en el ADR
> [0014](0014-proyeccion-redes-pesos-asortatividad.md), no como filas acá. Lo de abajo son las
> decisiones **de implementación / proceso** del hito. El verifier PASA (56 tests verdes bajo 2
> `PYTHONHASHSEED`).

| # | Decisión | Por qué | Reversibilidad | Validada por humano |
|---|----------|---------|----------------|---------------------|
| 2.1 | **Estructura en paquetes `networks/`** (`projectors`, `analyzer`, `spec`, `facade`) **y `exporters/`** (`graphml`, `csv`), no módulos planos | Separa proyección, análisis, datos y fachada; cada archivo de API.md §7–10 mapea a un módulo. Los símbolos públicos se re-exportan desde `__init__.py` (`API.md` §1) | Alta: mover/fusionar módulos no cambia la superficie pública (los símbolos salen del `__init__`) | Sí (PO proxy; verifier PASA) |
| 2.2 | **`NetworkSpec` MÍNIMO como hook** en `spec.py`: el modelo Pydantic existe y `Networks.build`/`quick` lo consumen, pero la carga desde YAML + validación avanzada se difieren | API.md §10 marca `NetworkSpec` como v0.2/hook desde v1; implementar el loader YAML ahora sería especular antes del Hito 9. Se expone `NetworkArtifact` (no `NetworkSpec`) en `__init__.__all__` por ahora | Alta: completar el modelo + loader es aditivo (Hito 9), no rompe `build`/`quick` | Sí (PO proxy; criterio del ROADMAP) |
| 2.3 | **`types-networkx>=3.6.1.20260612` en dev-dependencies** (`[tool.uv]`); `nx.Graph` se usa genérico solo bajo `TYPE_CHECKING` (`_Graph` alias) y plano en runtime | Tipar las firmas públicas que devuelven/consumen grafos (convención API.md: tipado estático) sin que `nx.Graph[...]` rompa en runtime (los stubs hacen `Graph` genérico, el runtime no) | Alta: quitar el stub solo afecta el chequeo estático, no el runtime | Sí (uv-native; ADR 0.3 dev-deps) |
| 2.4 | **`detect_communities(method="louvain")` y `Networks.build` fallan fuerte si falta `python-louvain`** (no degradan en silencio): `ImportError` explícito con el comando de instalación; en `_build_artifact`, la `ImportError` se re-lanza (otras excepciones de clustering sí se loguean y dejan `communities=None`) | Lección 7 de v0: la detección por defecto que falla en silencio fue un bug real. `python-louvain` está en el núcleo (ADR 0.2), así que su ausencia es un error de entorno, no un caso a degradar | Media: cambiar a degradación silenciosa exigiría re-tocar tests y contradice la lección 7 | Sí (PO proxy; verifier PASA) |
| 2.5 | **D5 — formato de export** (`CsvExporter`/`GraphMLExporter`): `aristas.csv` = `source,target,weight`; `nodos.csv` = `id,label` + atributos de nodo + métricas (degree/betweenness/community) unidas por id; GraphML escribe esos atributos como node attributes, **omite** atributos con valor `None` (Gephi/`write_graphml` no los admiten) y **copia el grafo** para no mutar el original. Orden de filas determinista (aristas por `(source,target)`, nodos por `id`) | Da artefactos directamente abribles en pandas / Gephi-VOSviewer-Cytoscape sin post-proceso; omitir `None` evita contaminar tipos en Gephi; no mutar el grafo respeta la pureza del núcleo | Alta: agregar columnas o cambiar nombres de archivo es aditivo; revertir el copy-on-export es trivial | Sí (PO proxy; verifier PASA) |
| 2.6 | **D6 — `cocitation_quality_report` devuelve `{criterio:{valor,umbral,pasa,...}}` + `overall_pass`, sin score ponderado**; mantiene los 4 umbrales de `QualityThresholds` (200 / 0.90 / 5 / 10). El criterio `min_countries` usa `institutions_id` como **proxy** de países, con un disclaimer en su entrada del dict | Un score ponderado escondería qué criterio falló e impondría pesos arbitrarios; el dict por criterio es transparente y accionable (metodología §4). El proxy de país es lo disponible en Hito 2 (sin lookup ROR→país, que llega en Hito 8 — ver ADR 0014) | Alta: agregar un score agregado o refinar el proxy es aditivo; los umbrales ya son configurables vía `QualityThresholds` | Sí (PO proxy; verifier PASA) |

> Las decisiones D1–D4 (arquitectónicas) y la nota del proxy de país en `min_countries` están en
> el ADR [0014](0014-proyeccion-redes-pesos-asortatividad.md). Símbolos públicos nuevos del hito
> en `__init__.py` (ver `API.md` §1, §7–10): los 5 proyectores, `Networks`, `NetworkArtifact`,
> `GraphMLExporter`, `CsvExporter`, `network_metrics`, `centrality`, `detect_communities`,
> `assortativity`, `community_composition`, `cocitation_quality_report`, `QualityThresholds`.

---

## 2026-06-15 — 2º giro (tensiones de arquitectura tras el Hito 2)

> Las decisiones de este giro son **arquitectónicas y las tomó el Product Owner humano** (acta
> acordada); por eso van en ADRs numerados **sin** el campo `Decidido por: IA`. La IA solo las
> **formalizó en docs** (los 5 ADR nuevos + enmiendas + reconciliación de PRD/ARCHITECTURE/API/
> ROADMAP). Se anotan acá para contexto, no como decisiones autónomas de la IA.

| ADR | Decisión del PO | Acta |
|---|---|---|
| [0015](0015-corpus-tabular-backend.md) | `Corpus` sobre `TabularBackend` (Protocol); `InMemoryBackend` puro + `DuckDBBackend` por defecto; mutaciones delegadas, no copia en memoria. Enmienda 0006, reencuadra 0009 | Punto 3 del acta |
| [0016](0016-maquina-estados-lazo.md) | Máquina de estados del lazo `SEEDED→FORAGED→FILTERED→BUILT` (transiciones permisivas); `LoopState` en el backend; una investigación = un archivo `.duckdb`; `b2g status` | Punto 5 |
| [0017](0017-reproducibilidad-historia-snapshot.md) | Reproducibilidad por historia auditable + snapshot sellado, no por recómputo; `openalex_version` ancla la foto | Punto 2 |
| [0018](0018-source-agnostico-calidad.md) | `Source` agnóstico: mínimo universal (id/título/año/autores/keywords) vs enriquecimiento opcional (refs/citantes/afiliaciones); reporte de calidad declarado (concreto v0.2+) | Puntos 1 y 7 |
| [0019](0019-concurrencia-diferida.md) | Concurrencia single-writer = limitación conocida; resolver post-v1.0 | Punto 6 |

> **Borde de decisión (IA):** el acta numeraba los ADR como `0014`–`0018`, pero `0014` ya estaba
> tomado por el ADR de proyección de redes (Hito 2). Para no reescribir historia, los ADR nuevos
> usan **`0015`–`0019`**. La separación `filter`/`curate` (punto 4 del acta) **no recibió ADR
> propio**: es una decisión de superficie CLI/roadmap, no de arquitectura — se refleja en
> [`../ROADMAP.md`](../ROADMAP.md) (Hito 6) y [`../API.md`](../API.md) (§convenciones CLI).

---

## 2026-06-15 — Hito 1.5 (Rework: `Corpus` sobre `TabularBackend` + `InMemoryBackend`)

> La **decisión arquitectónica de fondo es del Product Owner humano**: el `Corpus` se respalda en
> un `TabularBackend` (Protocol), `InMemoryBackend` puro + `DuckDBBackend` por defecto, mutaciones
> delegadas — está en el ADR [0015](0015-corpus-tabular-backend.md) (enmienda 0006, reencuadra
> 0009), **sin** el campo `Decidido por: IA`. Lo de abajo son las decisiones **de implementación**
> que tomó la IA al construir ese rework. El verifier PASA (73 tests verdes bajo 2 `PYTHONHASHSEED`,
> núcleo sin `duckdb`).

| # | Decisión | Por qué | Reversibilidad | Validada por humano |
|---|----------|---------|----------------|---------------------|
| 1.5.1 | **`_compute_corpus_hash` queda como alias** en `corpus.py` → `backends.memory.compute_corpus_hash` (misma función) | Preserva el import histórico de los tests del Hito 1 (`from bib2graph.corpus import _compute_corpus_hash`) sin debilitarlos ni duplicar la lógica del hash (D2 vive una sola vez, en el backend) | Alta: borrar el alias solo afecta el import histórico; la función canónica no se mueve | Sí (PO proxy; verifier PASA) |
| 1.5.2 | **`_compute_id` (D1) permanece en `corpus.py`**, no en `backends/`; `Corpus.add_paper` calcula el `id` y valida la fila ANTES de delegar al backend | Evita un import circular `corpus ↔ backends`; deja el cálculo de identidad y la validación `PaperRow` en el borde del `Corpus`. El Protocol documenta que el `id` llega **ya calculado** al backend | Media: mover `_compute_id` al backend exigiría romper el ciclo de otro modo (p. ej. un módulo `identity`) | Sí (PO proxy; verifier PASA) |
| 1.5.3 | **`InMemoryBackend` con semántica de valor** (cada operación devuelve una instancia nueva); conserva la estrategia table-rebuild del Hito 1 (mutación en Python sobre listas de dicts), sin optimizar | Mantiene la semántica inmutable del `Corpus` del Hito 1 y tests deterministas; optimizar la escala es trabajo del `DuckDBBackend` (Hito 3), no del backend puro de tests/working-set | Alta: cambiar a mutación in-place del backend in-memory es aditivo y aislado | Sí (PO proxy; verifier PASA) |
| 1.5.4 | **`TabularBackend` con `@runtime_checkable`** | Permite `isinstance(x, TabularBackend)` en chequeos defensivos y en la parametrización de la suite de contrato, sin imponer herencia (sigue siendo structural typing) | Alta: quitar el decorador solo deshabilita el `isinstance` en runtime, no el contrato estático | Sí (PO proxy; verifier PASA) |
| 1.5.5 | **Suite de contrato de backend parametrizada** (`tests/unit/test_backends.py`): los invariantes D1/D2/D3 (dedup por `id`, orden por primera aparición, `corpus_hash` order-independent, idempotencia de `merge`, accept/reject que agregan evento de provenance) se escriben una vez y se parametrizan por backend | Garantiza que `InMemoryBackend` y el futuro `DuckDBBackend` (Hito 3) cumplan **el mismo contrato** con los mismos casos; mitiga el riesgo de divergencia entre implementaciones (ADR 0015 §Consecuencias) | Alta: agregar `DuckDBBackend` a la parametrización es aditivo; ningún caso se reescribe | Sí (PO proxy; verifier PASA) |

> Las reglas D1/D2/D3 (arquitectónicas) están en el ADR
> [0013](0013-identidad-hash-merge-corpus.md), elevadas a **contrato del backend** por el ADR
> [0015](0015-corpus-tabular-backend.md). Símbolos públicos nuevos del hito en `__init__.py`
> (ver [`../API.md`](../API.md) §1.4): `TabularBackend`, `InMemoryBackend`.

---

## 2026-06-15 — Hito 3 (`DuckDBBackend`/`DuckDBStore`: biblioteca viva en DuckDB)

> La **decisión de fondo es del Product Owner humano** y está en los ADR del 2º giro: la **mutación
> por SQL puro** (en vez de read-all → rebuild) es lo que el ADR
> [0015](0015-corpus-tabular-backend.md) ordena (`DuckDBBackend` muta por `UPDATE`/`MERGE` por `id`,
> honrando D1/D2/D3 del ADR [0013](0013-identidad-hash-merge-corpus.md)), y el `LoopState` /
> single-writer vienen de los ADR [0016](0016-maquina-estados-lazo.md) /
> [0019](0019-concurrencia-diferida.md). Esas filas **NO** son "Decidido por IA". Lo de abajo, salvo
> la fila marcada **(PO)**, son las decisiones **de implementación** que tomó la IA al construir el
> hito. El verifier PASA (**98 tests** verdes; el núcleo sigue importando sin `duckdb`).

| # | Decisión | Por qué | Reversibilidad | Validada por humano |
|---|----------|---------|----------------|---------------------|
| 3.0 **(PO)** | **Mutación por SQL puro** en `DuckDBBackend` (upsert `INSERT … ON CONFLICT (id) DO UPDATE` + merge campo a campo en SQL: `COALESCE` escalares, `list_sort(list_distinct(list_concat(...)))` listas preservando `NULL`, UDFs para `provenance`/`curation_status`), no read-all → rebuild. **Honra el ADR [0015](0015-corpus-tabular-backend.md)** | Es el mandato del ADR 0015 (escala sin copiar la tabla; las mutaciones viven en el backend, en SQL). Decisión arquitectónica **del PO**, no autónoma de la IA | Baja: revertir contradice el ADR 0015 | **Sí — decisión del PO** (ADR 0015) |
| 3.b | **`LoopState` como log append-only** (tabla `loop_state_log` con `state` + `recorded_at`; estado actual = última fila por `recorded_at`), en vez de una columna de estado mutable única | El ADR [0016](0016-maquina-estados-lazo.md) pide **transiciones permisivas** y un mapa, no un guardia: un log preserva la historia de transiciones (auditable, consistente con `provenance` append-only D4) y "estado actual = última fila" lo deriva trivialmente | Alta: colapsar a una sola fila de estado es aditivo; el log es un superconjunto | Sí (PO proxy; verifier PASA) |
| 3.c | **`:memory:` soportado** además de archivo (sin `path` → `:memory:`) | La suite de contrato de backend (Hito 1.5) parametriza `DuckDBBackend` sin tocar disco; `:memory:` permite correr esos casos rápido y sin I/O, igualando el rol de `InMemoryBackend` en los tests | Alta: quitar `:memory:` solo afectaría la ergonomía de los tests | Sí (PO proxy; verifier PASA) |
| 3.d | **Columnas `LIST(VARCHAR)` nativas de DuckDB** para las 11 columnas de lista; **`provenance` como `VARCHAR`** (JSON serializado), no como estructura nativa | Las listas nativas permiten el merge D3 en SQL puro (`list_sort`/`list_distinct`/`list_concat`); `provenance` queda VARCHAR porque su merge (unión de eventos únicos, log) es lógica de dominio que ya vive verificada en `backends.memory` y se reusa por UDF (equivalencia byte a byte con InMemory) | Media: cambiar `provenance` a `STRUCT[]` nativo exigiría reescribir el merge y los helpers compartidos | Sí (PO proxy; verifier PASA) |
| 3.e | **`DuckDBStore` como fachada delgada** (`persist`/`load` + `.backend`) y **export perezoso (PEP 562)** de `DuckDBBackend`/`DuckDBStore` desde `bib2graph/__init__.py` vía `__getattr__` | El núcleo **no debe importar `duckdb`** (ADR 0015 / lección de v0): el `__getattr__` perezoso mantiene `import bib2graph` libre de duckdb (smoke test del Hito 0 sigue verde) y el `DuckDBStore` separa el Protocol `Store` (persist/load) de las extensiones DuckDB-específicas (`loop_state`/`set_loop_state`/`query`), expuestas vía `.backend` | Alta: pasar a import directo solo rompería el smoke test del Hito 0; mover métodos al Protocol es aditivo | Sí (PO proxy; verifier PASA) |
| 3.f | **Decisiones menores del coder:** `LoopState` como `StrEnum`; UDFs con `null_handling=FunctionNullHandling.SPECIAL` (para que reciban NULLs y no se cortocircuiten); `contextlib.suppress(duckdb.CatalogException)` al registrar las UDFs (catálogo compartido entre conexiones del mismo archivo); reordenamiento D3 (primera aparición) por `ORDER BY CASE id …` tras el upsert; `_clone()` de `:memory:` que exporta+recarga el estado (no se puede compartir una conexión in-memory) y copia el `loop_state_log`; lectura vía `to_arrow_table()` con `cast(CORPUS_SCHEMA)` | Detalles forzados por la semántica de DuckDB (UDF null-handling, catálogo compartido, in-memory no compartible) y por preservar D2/D3 exactos contra `InMemoryBackend`. Sin estos, el merge SQL o las UDFs divergirían del backend puro o fallarían al compartir archivo | Alta cada uno: son detalles locales del backend; ninguno cambia la superficie pública ni el contrato | Sí (PO proxy; verifier PASA) |
| 3.g | **`StoreLockedError(OSError)`** mapea la `duckdb.IOException` de archivo bloqueado a un error accionable; el exit code `5` queda **a cablear en el CLI (Hito 6)** | ADR [0019](0019-concurrencia-diferida.md): single-writer es límite conocido; el backend traduce el error de bloqueo a uno accionable (no corrompe), pero el mapeo a exit code es responsabilidad del CLI, que aún no existe | Alta: el código y el cableado al CLI son aditivos | Sí (PO proxy; verifier PASA) |

> Símbolos del hito (carga perezosa, ver [`../API.md`](../API.md) §4/§4.1): `DuckDBBackend`,
> `DuckDBStore` (vía `bib2graph.__getattr__`); `LoopState`, `StoreLockedError` (desde
> `bib2graph.backends.duckdb` / `bib2graph.stores.duckdb`). `DuckDBBackend` reusa la suite de
> contrato de backend del Hito 1.5 (D1/D2/D3), ahora parametrizada también con él.

---

## 2026-06-15 — Hito 4 (`OpenAlexSource` + `BibtexSource`: costura de siembra por red)

> Las **decisiones de contrato/arquitectura** de este hito ya viven en ADRs previos y **no** se
> re-deciden acá: `Source` agnóstico (mínimo universal vs enriquecimiento) en
> [0018](0018-source-agnostico-calidad.md); OpenAlex backbone + límites WoS en
> [0007](0007-openalex-backbone.md); credenciales en [0012](0012-openalex-credenciales.md);
> `openalex_version` que ancla la foto en [0017](0017-reproducibilidad-historia-snapshot.md);
> `bibtexparser` como extra en [0005](0005-dependencias-extras.md). Las filas marcadas **(PO)** son
> decisiones del Product Owner humano de este ciclo (registradas para contexto, no autónomas de la
> IA); el resto son decisiones **de implementación** que tomó la IA. **Con el Hito 4, v0.1 queda
> feature-complete.** El verifier PASA (**133 tests** verdes; mypy/ruff limpios; núcleo sin `duckdb`).

| # | Decisión | Por qué | Reversibilidad | Validada por humano |
|---|----------|---------|----------------|---------------------|
| 4.0 **(PO)** | **`bibtexparser` como extra `[bibtex]`**, no en el núcleo | BibTeX es una **fuente secundaria** (sembrar desde *pearls*); el núcleo no debe arrastrarla. Coherente con la política de extras del ADR [0005](0005-dependencias-extras.md) | Media: mover al núcleo es aditivo pero contradiría 0005 | **Sí — decisión del PO** |
| 4.1 **(PO)** | **Semillas con `curation_status="candidate"`** (no `accepted`): `is_seed` y `curation_status` son **ejes ortogonales** | Sembrar marca **procedencia** (`is_seed=True`), no **aceptación**: el juicio humano de curar (accept/reject) es un paso aparte (biblioteca viva, C4). Una semilla puede rechazarse sin perder su `is_seed` | Media: cambiar el default tocaría el modelo de curación y tests | **Sí — decisión del PO** |
| 4.a | **Traducción ecuación→OpenAlex PASSTHROUGH + reporte** (envuelve en `title_and_abstract.search:(...)` y **reporta** NEAR/comodín/tags WoS sin traducirlos); el **traductor WoS→OpenAlex (A2) se difiere a v0.2** | Un traductor WoS completo es trabajo grande y especulativo para v0.1; el passthrough ya cumple A1 (sembrar por ecuación) y A2 a nivel de **consciencia** (la query ejecutada + qué se descartó son visibles en `SeedResult`). Construir el traductor ahora arriesgaría regresiones sin caso real que lo valide | Alta: agregar el traductor es aditivo (el passthrough queda como `native`/fallback); ningún contrato cambia | Sí (PO proxy; verifier PASA) |
| 4.b | **Flag `native=True` en `seed()`** (escape hatch): pasa la query **cruda** sin envolver ni reportar | Da una vía consciente para usuarios que ya escriben sintaxis OpenAlex nativa (filtros, `from_publication_date`, etc.) sin pelear con el wrapper passthrough; es el "escape hatch" que pide el ADR 0007 | Alta: quitar el flag solo elimina el atajo, no rompe el camino por defecto | Sí (PO proxy; verifier PASA) |
| 4.c | **`max_results=200` + cursor paging; `cited_by_id` diferido al chaining/Enricher** (el seed lo deja `[]`) | El cursor paging acota el costo de red por seed (tope configurable); traer **citantes** por paper en el seed multiplicaría las llamadas y pertenece al **forward chaining** (Hito 5) / 2º nivel del `Enricher` (Hito 8), no a la siembra. Las **referencias** sí vienen inline (OpenAlex las da en el work) | Alta: subir el tope o adelantar `cited_by_id` es aditivo; el schema ya admite la columna | Sí (PO proxy; verifier PASA) |
| 4.d | **`transport` de httpx inyectable** en `OpenAlexSource.__init__` (`transport=None` → cliente real; `MockTransport` en tests) | Cumple "costuras de red contra API simulada, nunca red en CI" (ROADMAP, disciplina de tests) sin un wrapper extra: el `MockTransport` se inyecta directo y el cliente real es el default | Alta: es un parámetro opt-in; el default no cambia el comportamiento de producción | Sí (PO proxy; verifier PASA) |
| 4.e | **`Corpus.with_manifest(manifest) -> Corpus`** como API pública canónica para sellar metadata (lo usa `seed()` para poblar `openalex_version`/`equations`) | El source necesita escribir en el Manifest **sin** tocar el backend ni reconstruir el corpus; `with_manifest` lo hace con semántica de valor y `corpus_hash` invariante (el hash es sobre la tabla, no el manifest). Lo reusarán Forager/Enricher/Filter | Alta: es aditivo a la superficie de `Corpus`; no cambia ningún contrato existente | Sí (PO proxy; verifier PASA) |
| 4.f | **`SeedResult.corpus` validado en runtime vía `arbitrary_types_allowed`** (import directo de `Corpus` en `sources.base`), **sin** `model_rebuild()` ni referencia diferida | `corpus.py` **no** importa `sources`, así que el import directo de `Corpus` no crea circularidad; `arbitrary_types_allowed` basta para que Pydantic acepte un `Corpus` (que no es `BaseModel`). Evita la fragilidad de las forward-refs + `model_rebuild` | Alta: pasar a forward-ref + rebuild es posible si surgiera un ciclo, pero hoy no hace falta | Sí (PO proxy; verifier PASA) |

> Símbolos públicos nuevos del hito en `__init__.py` (import **directo** — httpx es núcleo, sin
> efectos de import; ver [`../API.md`](../API.md) §2): `OpenAlexSource`, `BibtexSource`, `Source`
> (Protocol), `SeedResult`. El nuevo método `Corpus.with_manifest()` se documenta en
> [`../API.md`](../API.md) §1.2. No se abrió ADR nuevo: el contrato del hito está cubierto por los
> ADR 0005/0007/0012/0017/0018.

---

## 2026-06-15 — Hito 5 (Forrajeo + `Preprocessor` + filtros PRISMA)

> Las **decisiones de método** de este hito son **arquitectónicas** y van al ADR
> [0020](0020-metodo-forrajeo-scent-filtros-reject.md), no como filas acá: el **scent = frecuencia
> de enlace** y los **filtros que marcan `rejected` (no borran)** son **decisiones del PO**
> (marcadas `Decidido por: mixto` en el ADR); backward puro vs forward red, `keywords_id`
> pre/post-thesaurus y el `preview` local-only son de la IA validadas por el PO proxy. Lo de abajo
> son las decisiones **de implementación / proceso** que tomó la IA al construir el hito. El verifier
> PASA (**192 tests** verdes; el preview network-free quedó corregido; núcleo sin `duckdb`).

| # | Decisión | Por qué | Reversibilidad | Validada por humano |
|---|----------|---------|----------------|---------------------|
| 5.1 | **Estructura en paquetes `foraging/`** (`scent` puro, `base`, `forager`, `explain`), **`preprocessors/`** (`normalize`, `thesaurus`, `preprocessor`) y **`filters/`** (`prisma`), no módulos planos | Separa el cómputo puro de scent del orquestador que toca la red; cada módulo de API.md §5–§6 mapea a un archivo. Los símbolos públicos se re-exportan desde `__init__.py` (`Forager`, `GrowthPreview`, `RankedCandidates`, `Preprocessor`, `FilterCriterion`, `apply_filters`); `explain_candidate`/`apply_filter` quedan en su sub-paquete | Alta: mover/fusionar módulos no cambia la superficie pública | Sí (PO proxy; verifier PASA) |
| 5.2 | **`preview` local-only con `forward_requires_fetch`** (`by_direction["forward"]=0` cuando se pide forward/both): backward se estima exacto desde `references_id`, forward NO se estima sin red | `cited_by_id` está vacío tras el seed (decisión 4.c, Hito 4); estimar forward exigiría `fetch_citing` (red), y el `preview` debe ser barato y honesto. El flag deja claro al llamador que el conteo real llega con `chain()` (corrige el preview que antes tocaba red) | Media: estimar forward sin red es imposible con el schema actual; el flag es el contrato honesto | Sí (PO proxy; verifier PASA) |
| 5.3 | **Forward chaining exige `source.fetch_citing(openalex_id)`** y falla con `AttributeError` accionable si falta; **NO se amplió el Protocol `Source`** (§2). `OpenAlexSource.fetch_citing` calcula el `id` D1 de cada citante con la misma función que `add_paper` | `fetch_citing` (`GET works?filter=cites:`) es capacidad de OpenAlex, no contrato universal: una `Source` de solo-mínimo (ADR 0018) no debe verse forzada a implementarlo. Calcular el `id` en el source deja a `Forager`/`compute_forward_scent` identificar candidatos sin recomputar | Media: subir `fetch_citing` al Protocol obligaría a toda Source; revertir el cálculo del id duplicaría D1 | Sí (PO proxy; verifier PASA) |
| 5.4 | **Candidatos backward = stubs id-only** (título placeholder `[candidate:{id}]`, `openalex_id` poblado, resto nulo; `is_seed=False`, `curation_status='candidate'`, `provenance` con `chaining_hop=1`) | Backward solo aporta el id (sale de `references_id`); fabricar metadata sería inventar datos. El placeholder pasa la validación del schema sin contaminar las redes (no tienen autores/keywords reales); se enriquecen después. **Gap conocido:** quedan id-only hasta un enrich/curación posterior | Alta: enriquecer los stubs es aditivo (Hito 8) | Sí (PO proxy; verifier PASA) |
| 5.5 | **`apply_thesaurus` SOBRESCRIBE `keywords_id` desde `keywords_raw`** (no fusiona) | El schema (API.md §1.1) ya dice que `keywords_id` son "canónicos post-thesaurus": antes del thesaurus no es autoritativa. Sobrescribir hace la operación idempotente y predecible (el thesaurus es la única fuente de los canónicos). Precisado en el ADR 0020 (D) | Alta: cambiar a merge exigiría re-tocar tests de idempotencia | Sí (PO proxy; verifier PASA) |
| 5.6 | **`normalize` conservador**: `authors_id` (lowercase + acentos + espacios) y `language` (ISO 639-1 primario); **sin fuzzy, sin columna de periodización** | El fuzzy es del extra `[dedup]` (Hito 7, lección 5: no adelantar); la "periodización" del API.md §6 previo no tenía contrato claro ni caso que la valide, así que no se inventó una columna nueva. Idempotente | Alta: agregar periodización/fuzzy es aditivo | Sí (PO proxy; verifier PASA) |
| 5.7 | **`apply_filters` SELLA `Manifest.filters` reemplazando** (una corrida = una secuencia PRISMA), con `count_before/after` por `FilterStep` contando papers **no-rejected** | Una corrida de filtros describe **su** secuencia PRISMA; acumular mezclaría corridas distintas. El `provenance` por paper (append-only, D4) ya guarda cada rechazo individual, así que no se pierde historia. **Gap conocido:** no hay un historial de todas las corridas de filtro a nivel Manifest | Media: pasar a acumular cambiaría la semántica del reporte PRISMA | Sí (PO proxy; verifier PASA) |
| 5.8 | **`explain_candidate` (B4) = stub gateado en `[llm]`**: firma real + import perezoso del extra; sin extra → `ImportError` accionable, con extra → `NotImplementedError` (la llamada LLM no está construida) | El forrajeo debe funcionar sin LLM (B4 es opcional). El stub fija el contrato y el aislamiento del extra sin prometer una capacidad inexistente (lección 5). La integración LLM es v0.2 | Alta: construir la llamada LLM es aditivo | Sí (PO proxy; criterio del ROADMAP) |

> **Decisiones del PO de este ciclo** (en el ADR [0020](0020-metodo-forrajeo-scent-filtros-reject.md),
> registradas acá para contexto): scent = **frecuencia de enlace** (descarta acoplamiento/centralidad);
> alcance Hito 5 completo (forrajeo + thesaurus + filtros); **filtros marcan `rejected`, no borran**
> (biblioteca viva + trazabilidad PRISMA).
>
> **Gaps conocidos declarados** (no construidos, marcados para no falsear el estado): (a) candidatos
> backward **id-only** — se enriquecen luego (Hito 8); (b) `Manifest.filters` **reemplaza** — no hay
> historial de corridas de filtro a nivel Manifest (sí en `provenance` por paper); (c) el **reporte de
> calidad** del ADR [0018](0018-source-agnostico-calidad.md) sigue **declarado, no construido**
> (concreto v0.2+). Símbolos públicos nuevos en `__init__.py`: ver [`../API.md`](../API.md) §5–§6.

---

## 2026-06-15 — Hito 6 (CLI agente-native `b2g` como producto)

> Las **decisiones de contrato** de este hito son **arquitectónicas** y van al ADR
> [0021](0021-cli-agente-native-contrato.md): el **set de 11 subcomandos** (incl. `accept`/`reject`)
> y la **separación `build`/`export`** son **decisiones del PO** (marcadas como tal en el ADR); la
> forma del envelope JSON versionado, el mapeo de exit codes por tipo de excepción, el `--store`
> global y las transiciones automáticas de `LoopState` son de la IA validadas por el PO proxy. Lo de
> abajo son las decisiones **de implementación / proceso** que tomó la IA al construir el CLI. El
> verifier PASA (**214 tests** verdes; mypy/ruff limpios; el núcleo sigue importando sin `duckdb`).

| # | Decisión | Por qué | Reversibilidad | Validada por humano |
|---|----------|---------|----------------|---------------------|
| 6.0 **(PO)** | **Set de 11 subcomandos con `accept`/`reject` como CLI** (no solo API de librería) y **`build`/`export` separados** | El PO decidió exponer la curación programática (`accept`/`reject` por `--ids`) como subcomando de primera clase para agentes (C4), y separar el cómputo de redes (`build` → artefactos a disco + `BUILT`) de su serialización (`export` → formato pedido, sin transición). Amplía lo que decía `API.md` §convenciones | Baja: revertir contradice el ADR 0021 | **Sí — decisión del PO** (ADR 0021) |
| 6.1 | **Paquete `cli/` (no `cli.py`) en 3 capas**: grupo Click + opción global `--store` (`cli/__init__.py`) → un módulo por comando en `cli/commands/` con una **función núcleo `run_<cmd>(store_path, ...)` testeable sin Click** → helpers compartidos (`_envelope`, `_errors`, `_store`) | El ROADMAP manda testear **la función detrás del comando**, no el parser de Click; separar `run_<cmd>` del decorador Click lo permite. Un módulo por comando mantiene cada subcomando aislado y el grupo trivial de leer | Alta: fusionar módulos no cambia la superficie (`b2g <cmd>`); el entry point sigue siendo `bib2graph.cli:main` | Sí (PO proxy; verifier PASA) |
| 6.2 | **Envelope JSON con `build_envelope`/`emit` centralizados** (`cli/_envelope.py`), `schema="1"` como constante (`ENVELOPE_SCHEMA_VERSION`); `emit` imprime **una línea JSON** con `default=str` y `ensure_ascii=False` | El contrato `--json` debe ser idéntico entre los 11 comandos (ADR 0021 §C); una sola función constructora evita drift. `default=str` serializa tipos no-JSON (fechas) sin romper; `ensure_ascii=False` preserva acentos | Alta: cambiar la forma bumpea `schema`; los comandos no se reescriben (todos llaman `build_envelope`) | Sí (PO proxy; verifier PASA) |
| 6.3 | **Decorador `@handle_errors(command)` que captura por tipo y mapea a exit codes** (`B2GError`→propio · `OSError`/`StoreLockedError`→5 · `ImportError`/`AttributeError`→3 · `httpx.HTTPError`→4); jerarquía `B2GError` (`UsageError`/`DataError`/`DependencyError`/`NetworkError`/`StoreError`) con `exit_code`+`code` por clase | Mapeo uniforme y testeable (un caso por código, ADR 0021 §D) sin que cada comando reinvente el try/except; la captura **por tipo** de `httpx.HTTPError` cubre toda la jerarquía de red (ConnectError/Timeout/…) en exit 4 | Media: cambiar el mapeo toca el decorador y sus tests; la jerarquía es aditiva | Sí (PO proxy; verifier PASA) |
| 6.4 | **`open_store` helper** (`cli/_store.py`) que traduce `StoreLockedError`/`OSError` a `StoreError` (exit 5) en la apertura del store, reusado por todos los comandos | Centraliza el manejo del bloqueo single-writer (ADR 0019) para que ningún comando repita el try/except; el decorador captura `StoreError` y emite exit 5 | Alta: inlinear el helper es trivial | Sí (PO proxy; verifier PASA) |
| 6.5 | **Transiciones de `LoopState` automáticas tras persistir** (`seed`→SEEDED, `chain`→FORAGED, `filter`→FILTERED, `build`→BUILT); `accept`/`reject`/`export`/`snapshot`/`status`/`inspect`/`validate` **no transicionan** | El usuario/agente no debería gestionar el lazo a mano; el comando que muta el corpus avanza el estado (transiciones permisivas, ADR 0016). Curar (`accept`/`reject`) no es una fase del flujo, así que no mueve el lazo | Alta: las transiciones son permisivas; cambiar a qué estado salta cada comando es local | Sí (PO proxy; verifier PASA) |
| 6.6 | **Tabla `_TRANSITIONS` en `status`** mapea estado actual → próximos comandos disponibles (informativa, derivada del lazo permisivo de ADR 0016) | `b2g status` debe mostrar "próximos pasos" a humanos e IAs (ADR 0016: comparten el mapa). Como las transiciones son permisivas, la tabla es una **guía**, no un guardia que bloquee saltos | Alta: la tabla es presentación; ampliarla no cambia el comportamiento del lazo | Sí (PO proxy; verifier PASA) |
| 6.7 | **`build` escribe artefactos intermedios a `<store_dir>/networks/<kind>/` y `export` los relee de disco**; `metrics.json` filtra a tipos JSON-serializables; las comunidades se fusionan como atributo de nodo `community` en el GraphML | Separar `build`/`export` (ADR 0021 §B) exige un punto de intercambio: el directorio `networks/` junto al store. **Gap conocido:** `export` relee GraphML en vez de recibir artefactos en memoria — acoplamiento por disco, precio de desacoplar los pasos | Media: pasar a artefactos en memoria exigiría unir `build`/`export` o un cache | Sí (PO proxy; verifier PASA) |

> **Decisiones del PO de este ciclo** (en el ADR [0021](0021-cli-agente-native-contrato.md),
> registradas acá para contexto): set de **11 subcomandos** con `accept`/`reject` como CLI (amplía
> `API.md` §convenciones); **`build` y `export` separados**.
>
> **Gaps conocidos declarados** (no construidos): (a) `export` relee artefactos de **disco** (no en
> memoria); (b) `b2g networks --spec redes.yaml` del ejemplo declarativo (`API.md` §12.2) es del
> **Hito 9**, no construido; (c) un `OSError` del store no relacionado con el bloqueo igual cae en
> exit 5 (conservador). El entry point `b2g = "bib2graph.cli:main"` ya estaba declarado desde el
> Hito 0; el Hito 6 reemplaza el placeholder por los 11 subcomandos reales.

---

## 2026-06-16 — Hito R2 (Reproducibilidad / identidad: content-hash vs procedencia + Louvain seeded)

> Implementa la enmienda 2026-06-15 del ADR
> [0017](0017-reproducibilidad-historia-snapshot.md) (RAÍZ 2 de la Nota 06). El **principio**
> (identidad de contenido ≠ procedencia de auditoría; reloj en la frontera; Louvain seeded) es del
> ADR/PO; lo de abajo son las decisiones **de implementación** que tomó la IA al construirlo. El
> verifier **APRUEBA CON RESERVAS** (247 tests verdes, 13 nuevos en `test_r2_reproducibility.py`;
> mypy strict / ruff limpios; núcleo sigue importando sin `duckdb`), dejando dos puntos al steering
> arquitectónico (resueltos en las filas R2.1 y R2.5).

| # | Decisión | Por qué | Reversibilidad | Validada por humano |
|---|----------|---------|----------------|---------------------|
| R2.1 | **El núcleo conserva un fallback `datetime.now(UTC)`** en `_apply_curation_to_rows` (`backends/memory.py`) cuando `decided_at is None`; las tres fronteras CLI (`accept`/`reject`/`filter`) **siempre** inyectan, así que el path real nunca lo toca | Mantiene `corpus.accept(ids)` ergonómico como **librería** sin obligar a pasar un reloj. **No** contradice el objetivo de R2 (hash determinista) porque el `decided_at` **no entra al hash** (identidad excluye provenance): la reproducibilidad bit a bit está garantizada *por construcción*, venga el timestamp inyectado o del fallback. El **arquitecto aceptó el fallback como contrato documentado** y ajustó la redacción del ADR 0017 (punto 3) para que sea honesta ("el reloj se inyecta en la frontera; el núcleo solo usa `datetime.now()` como fallback de librería, fuera de la identidad"), en vez de "el núcleo nunca toca el reloj" | Media: hacer el núcleo 100% clock-free exigiría `decided_at` requerido y rompería `corpus.accept(ids)`; queda como opción del PO si algún día se quiere pureza total (ver recomendación) | **Sí — steering arquitectónico** (ADR 0017 reconciliado) |
| R2.2 | **Mecanismo `decided_at: datetime \| None` (parámetro), no `clock: Callable`** en `accept`/`reject`/`apply_filter(s)` | (a) Simplifica la firma; (b) los tests inyectan el instante exacto sin construir closures; (c) ergonomía de librería (sin argumento → fallback razonable). Un `Callable` agregaría indirección sin beneficio en este dominio (un único instante por invocación) | Alta: cambiar a `clock` es local a la firma; los callers ya pasan un `datetime` | Sí (PO proxy; verifier PASA) |
| R2.3 | **`filter.py` inyecta un único `decided_at` para todos los pasos PRISMA** de la invocación (`apply_filters(corpus, criteria, decided_at=now)`), no uno por criterio | Una corrida de filtrado es **una** decisión en el tiempo; un solo timestamp hace la procedencia coherente y el resultado idéntico entre corridas. `apply_filters` propaga el mismo `decided_at` a cada `apply_filter` | Alta: pasar a timestamp por paso es aditivo | Sí (PO proxy; verifier PASA) |
| R2.4 | **Derivación del seed de Louvain: `int(corpus_hash[:8], 16) % 2**31`** (`_louvain_seed_from_hash`, `facade.py`), threadeado por `_build_artifact` solo cuando `clustering == "louvain"` | Toma 32 bits del content-hash y los acota a `[0, 2^31-1]` (rango positivo de int32 que acepta `python-louvain`). Determinista y barato; "mismo corpus → mismo seed → mismas comunidades". Derivar del content-hash (no del que incluía provenance) garantiza que la reproducibilidad de comunidades herede la de identidad | Alta: cambiar la derivación (p. ej. usar el hash completo mód 2^31) es local a la función; no cambia la API | Sí (PO proxy; verifier PASA) |
| R2.5 | **`resolution` de Louvain NO se implementó — diferido a Hito 9** (NetworkSpec declarativo), pese a que el punto 4 del ADR 0017 / el DoD de R2 lo pedían | R2 entrega la pata que importa para la **identidad/reproducibilidad** (el `random_state` seeded). `resolution` es un parámetro de **tuning** del clustering que pertenece a la capa declarativa por algoritmo (`NetworkSpec` + YAML, Hito 9), no a la corrección de reproducibilidad. El **arquitecto reconcilió** el DoD/ADR/ROADMAP para reflejar el diferimiento honestamente (no dejar un criterio del DoD sin cumplir sin nota) | Alta: exponer `resolution` en el Hito 9 es aditivo (el `random_state` ya está) | **Sí — steering arquitectónico** (DoD/ADR 0017/ROADMAP reconciliados) |

> **Reconciliación de docs (arquitecto, 2026-06-16):** ADR 0017 (redacción del fallback honesta +
> `resolution` diferido + `filter.py` en la lista de fronteras), ROADMAP (Hito R2 ✅ + DoD
> reconciliado + `resolution`→Hito 9), ARCHITECTURE.md (§6.2 AS-BUILT R2), API.md (§1.1/§1.2/§8/§10:
> `decided_at`, hash content-only, Louvain seeded).
>
> **Recomendación de código (no implementada — queda al PO):** si alguna vez se quiere el núcleo
> **100% clock-free**, hacer `decided_at` **requerido** en `_apply_curation_to_rows`/`apply_curation`
> y mover el fallback a un helper de frontera (p. ej. `corpus.accept(ids)` resolviendo `now()` antes
> de delegar). Hoy **no es necesario**: el objetivo de R2 (hash determinista) ya está cumplido porque
> el hash excluye provenance, y el fallback es una conveniencia de librería legítima.
