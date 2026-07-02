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
> `../ROADMAP.md` (Hito 6) y [`../API.md`](../API.md) (§convenciones CLI).

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

---

## 2026-06-16 — Hito R3 (Ciclo: FSM cíclico de dominio `cycle.py` + `reseed`/ronda + curación transversal)

> Implementa la enmienda 2026-06-15 de los ADR
> [0016](0016-maquina-estados-lazo.md)/[0021](0021-cli-agente-native-contrato.md) (RAÍZ 1 de la Nota
> 06, la parte del lazo). El **modelo** (FSM cíclico de dominio, `reseed` de primera clase, curación
> transversal, backend solo persiste) es **del PO/ADR**; lo de abajo son las decisiones **de
> implementación** que tomó la IA al construirlo. El verifier **APRUEBA CON RESERVAS**; la reserva
> principal (chain/filter/build no pasaban por el dominio) **ya se cerró** con el fix posterior (filas
> R3.4 + test domain-tied). Verifier final: **275 tests** verdes (R3 + 9 del fix), mypy strict / ruff
> limpios; núcleo sigue importando sin `duckdb`. El steering arquitectónico (2026-06-16) confirma la
> **coherencia** con el ADR 0016 enmendado / ARCHITECTURE.md / Nota 05.

| # | Decisión | Por qué | Reversibilidad | Validada por humano |
|---|----------|---------|----------------|---------------------|
| R3.1 | **Diseño de `cycle.py` (dominio puro): `apply_transition(state, action, round) → (state, round)` + `available_transitions(state)` + `CURATION_ACTIONS`**, con transiciones **permisivas** (la acción nombrada lleva a su estado de cadena; no se bloquean saltos) y `reseed` como única acción que incrementa la ronda. El enum `CycleState` (5 estados) sale del backend al núcleo | El ADR 0016 enmendado §1 manda el ciclo como **concepto de dominio puro y testeable**; una función pura `(estado, ronda, acción) → (estado, ronda)` lo hace verificable **sin** DuckDB y deja al backend como mero persistidor. `available_transitions` mapea cada estado a sus acciones lógicas (mapa, no guardia) | Media: cambiar la forma de la función toca los call-sites (`seed`/`chain`/`filter`/`build`/`status`) | Sí (PO proxy / ADR 0016; verifier PASA) |
| R3.2 | **Alias transicional `LoopState = CycleState`** en `backends/duckdb.py` (no se borró `LoopState` de golpe) | Evita romper imports históricos (`from bib2graph.backends.duckdb import LoopState` en `stores/duckdb.py`, tests, docs) en el mismo commit que mueve el dominio; el rename completo es un barrido aparte | Alta: borrar el alias es mecánico (migrar call-sites a `CycleState`). **Queda como recomendación: retirar pre-1.0** | Sí (PO proxy; verifier PASA) |
| R3.3 | **Persistencia de `round` por migración liviana** (columna `round INTEGER DEFAULT 0` en `loop_state_log`; `ALTER TABLE … ADD COLUMN` envuelto en `contextlib.suppress(CatalogException)` para bases pre-R3; `loop_round()` devuelve 0 si NULL/sin filas; `set_loop_state(state, *, cycle_round=None)` conserva la ronda si no se pasa) | El contador de ronda necesita persistirse junto al estado (log append-only ya existente, ADR 0016/decisión 3.b). DuckDB no admite `ADD COLUMN NOT NULL`, así que nullable + default 0; la migración es segura pre-1.0 (sin datos reales en uso). `_clone()` copia también `round` | Alta: la columna es aditiva; revertir exigiría dropearla (sin datos en producción) | Sí (PO proxy; verifier PASA) |
| R3.4 | **`chain`/`filter`/`build` DERIVAN su estado destino de `apply_transition`** (no de un literal `LoopState.X`): `current = loop_state(); round = loop_round(); new_state, new_round = apply_transition(current, action, round); set_loop_state(new_state, cycle_round=new_round)`. **Cierra el gap que marcó el verifier.** Atado por `tests/unit/test_r3_commands_domain.py` (parametrizado, 9 casos) | El verifier observó que el AS-BUILT inicial dejaba los comandos hardcodeando el estado destino, duplicando la verdad del dominio. Enrutar por `apply_transition` hace de `cycle.py` la **fuente única**: si cambian las reglas, los comandos las siguen y el test lo detecta | Media: revertir a literales re-abre el gap (test rojo) | **Sí — fix posterior al verifier** (steering: gap cerrado) |
| R3.5 | **`seed` cablea `reseed` cuando hay estado previo** (estado previo ⇒ `apply_transition(prev, "reseed", round)` → `SEEDED`, ronda++; sin estado previo ⇒ `apply_transition(None, "seed", round)`); el payload de `seed` suma `round` y `reseeded` | "La idea muta" (Bates, Nota 05 §3): re-sembrar sobre la biblioteca viva debe **acumular** (el merge ya lo hace) y **contar la ronda**, no ser una corrida tirada. Es lo que el ADR 0016 prometía (historia A5) | Alta: la rama es local a `seed.py`; los campos del payload son aditivos | Sí (PO proxy / ADR 0016; verifier PASA) |
| R3.6 | **`status` expone `curation_available=["accept","reject"]` SIEMPRE + `round`** (campos **aditivos** en `data`, **manteniendo `schema="1"`**); `transitions_available` pasa a derivarse de `available_transitions` (tabla local `_TRANSITIONS` retirada) e incluye `reseed`; `accept.py`/`reject.py` documentan "curación transversal, no transiciona" | La enmienda del ADR 0016/0021 manda que el mapa del lazo **no oculte** lo único irreductiblemente humano (Nota 05 §4). Mantener `schema="1"` es **decisión del PO** (2026-06-16: campos nuevos no rompen a los agentes — solo agregan; bumpear sería ruido). Derivar de `available_transitions` mata el drift entre la tabla de `status` y el dominio | Media: quitar los campos sí bumpearía el schema; mantenerlos es contrato | **Sí — decisión del PO** (`schema="1"` aditivo) |
| R3.7 | **Cosmético `round` → `cycle_round`** en el kwarg de `set_loop_state` (`set_loop_state(state, *, cycle_round=None)`), no `round=` | Evita sombrear el builtin `round()` y la columna SQL `round` en la firma pública del backend; el verifier lo marcó como cosmético y quedó resuelto | Alta: rename local del kwarg | Sí (PO proxy; verifier PASA) |

> **Reservas del verifier:** la principal (chain/filter/build fuera del dominio) **quedó cerrada**
> (R3.4 + test domain-tied); el cosmético (`round`→`cycle_round`) **resuelto** (R3.7). **No hay
> reservas de código abiertas.**
>
> **Recomendaciones de código (no implementadas — quedan al PO):** (a) **retirar el alias
> `LoopState = CycleState` pre-1.0** (migrar `stores/duckdb.py`, tests y docs a `CycleState`); (b) si
> alguna vez se construye el paso 8 del ciclo, agregar un comando **`b2g monitor`** que dispare la
> transición a `MONITORED` (hoy el estado existe en el modelo pero ningún comando lo alcanza).
>
> **Reconciliación de docs (arquitecto, 2026-06-16):** ADR 0016 (nota "implementado en R3"), ADR 0021
> (envelope de `status` con `curation_available`/`round` aditivos, `schema="1"`), ROADMAP (Hito R3 ✅ +
> banner as-built), ARCHITECTURE.md (§5.5 FSM → `cycle.py` AS-BUILT R3), API.md (§convenciones CLI +
> bloque `cycle.py`), CHANGELOG (R3 marcado). La Nota 05
> ya describía el ciclo correcto y **no requirió cambios** (R3 la **implementa**, no la corrige).

---

## 2026-06-16 — Hito R4 (Scent bibliométrico vía proyectores + retiro de IA del producto)

> Implementa las enmiendas 2026-06-15 de los ADR
> [0020](0020-metodo-forrajeo-scent-filtros-reject.md) (scent = proyectores),
> [0022](0022-producto-sin-ia-generativa.md) (el producto no usa IA) y
> [0008](0008-wedge-forrajeo.md) (tensiones retiradas). Cierra la RAÍZ 1 (parte de IA) de la
> Nota 06. **291 tests** verdes, mypy strict / ruff limpios; el
> núcleo de scent depende del núcleo de proyección (puro), no al revés. **Verifier: APRUEBA CON
> RESERVAS** (3 cuestiones de método); el **steering arquitectónico (2026-06-16)** las resolvió.

| # | Decisión | Por qué | Reversibilidad | Validada por humano |
|---|----------|---------|----------------|---------------------|
| R4.1 | **`compute_backward/forward_scent` consumen el primitivo público `collect_item_to_papers`** (extraído a `networks/projectors.py` y re-exportado) en vez de reimplementar `Counter`/`sum`. El forrajeo (costura) **depende del núcleo de proyección**, nunca al revés | El ADR 0020 enmendado §1 manda que el scent "use los proyectores" como olfato. Extraer el índice inverso `{ref → papers que lo citan}` como primitivo público lo comparte entre proyectores y scent sin construir un `nx.Graph` por candidato (olfato barato y determinista) | Media: cambiar el primitivo toca proyectores y scent a la vez | Sí (PO proxy / ADR 0020; verifier PASA) |
| R4.2 | **Backward ratificado como _fuerza de co-citación con el corpus_** (`backward_score(X) = |{Pi ∈ corpus : X ∈ Pi.references_id}|`), NO "conteo plano sin sentido" | Numéricamente coincide con el viejo conteo, pero su **semántica es estructural**: `X` referenciado por `N` corpus-papers está **co-citado `N` veces dentro del corpus** (columna de `X` en la matriz de co-citación). Cumple el DoD ("no por conteo plano"): mide una propiedad de red, vía el primitivo de proyectores. Se renombra el concepto en docstrings/docs de "frecuencia de enlace" → "fuerza de co-citación con el corpus" | Alta: es ratificación + rename de concepto, no cambia el cómputo | **Sí — steering arquitectónico** (ADR 0020 AS-BUILT) |
| R4.3 | **Forward = _fuerza de citación directa al corpus_** (señal primaria), NO acoplamiento puro. El AS-BUILT inicial lo implementó como acoplamiento (`refs compartidas Y↔corpus`), que **degeneraba a 0** con `references_id` ralas (común tras `seed`) y **descartaba el citante directo como candidato**. **Fix IMPLEMENTADO dentro de R4**: `compute_forward_scent` calcula `forward_score(Y) = |{ref ∈ Y.references_id : ref ∈ corpus_ids}|`, siempre > 0 para un citante real, y emite con `direct > 0`; acoplamiento queda secundario | El forward chaining busca **citantes**; un citante directo NO necesariamente comparte refs con el corpus-paper que cita → el acoplamiento es la medida equivocada para esta dirección. La citación directa rankea por cuán embebido está el citante en mi corpus (Wohlin, snowballing forward), robusta y siempre informativa | Media: el fix fue local a `compute_forward_scent` | **Sí — steering arquitectónico** (recomendación de código explícita, **implementada dentro de R4**; 293 tests verdes, mypy/ruff OK) |
| R4.4 | **Centralidad de red del candidato: DIFERIDA** (viz), no exigida para cerrar R4 | El DoD listaba "acoplamiento **/** co-citación **/** centralidad" con un **"y/o"**: pide señal estructural de red, no las tres. Con backward = co-citación + forward = citación-directa el espíritu se cumple. La centralidad requiere construir el grafo completo por candidato (costo que excede el olfato barato y determinista de R4). DoD reconciliado honestamente | Alta: agregar una señal de centralidad es aditivo (mejora futura) | **Sí — steering arquitectónico** (DoD reconciliado) |
| R4.5 | **`explain_candidate`, `foraging/explain.py` y el extra `[llm]` ELIMINADOS** de la superficie pública y de `pyproject.toml` (ADR 0022) | El producto no usa IA generativa; el "porqué" de un candidato lo da la estructura visible, no un LLM. El stub vacío era deuda/vapor (Nota 06 RAÍZ 1) | Baja: re-introducir IA sería una **decisión nueva** (ADR nuevo), no un default | **Sí — decisión del PO** (ADR 0022) |

> **Reservas del verifier:** RESERVA 2 (forward degenera a 0) → el arquitecto la convirtió en
> **recomendación de código** (R4.3): revertir el forward a citación directa; **se implementó dentro de
> R4** (la elimina-IA y el scent-vía-proyectores **están cerrados y verificados**).
> RESERVA 1 (backward = conteo) → **ratificada como co-citación** (R4.2), es measure bibliométrico
> legítimo. RESERVA 3 (centralidad del DoD) → **diferida** (R4.4), el "y/o" del DoD se cumple.
>
> **Veredicto del arquitecto:** **R4 ✅ TERMINADO** — la parte de cierre (sin IA, scent-vía-proyectores,
> dependencia forrajeo→núcleo) está hecha y verificada, y el **fix del forward** (citación directa) se
> **implementó dentro de R4** (`compute_forward_scent`, 293 tests verdes). R4 no deja seguimiento abierto.
>
> **Reconciliación de docs (arquitecto, 2026-06-16):** ADR 0020 (AS-BUILT: fórmulas reales,
> backward=co-citación, forward=citación-directa **implementada**, centralidad diferida),
> ADR 0022 (AS-BUILT: sin IA construido), ROADMAP (Hito R4 ✅ TERMINADO + DoD reconciliado),
> ARCHITECTURE.md (§3.5 scent→proyectores AS-BUILT R4), API.md (§5 scent bibliométrico construido),
> CHANGELOG (R4 marcado). README/AI_DISCLOSURE/AGENTS ya describían el retiro de `[llm]`/IA en pasado y
> **no requirieron limpieza adicional**. La Nota 05 §4 ya
> prometía "la bibliometría ES el information scent" y **no requirió cambios** (R4 la **implementa**).

---

## 2026-06-16 — Hito R5 (Robustez / escala: bulk-load, UTF-8 en la frontera, footguns de la Nota 06)

> Último hito de la tanda de remediación. **No cambia el modelo conceptual; endurece lo construido.**
> Cierra la RAÍZ 3 (no corre a escala + bug del contrato agente-native) y el catálogo de secundarios de
> la Nota 06. **319 tests** verdes
> (`tests/unit/test_r5_robustness.py` + ajustes), mypy strict / ruff check+format limpios.
> **Verifier: APRUEBA** (reservas cerradas). Con R5 la **tanda R1–R5 queda COMPLETA**.

| # | Decisión | Por qué | Reversibilidad | Validada por humano |
|---|----------|---------|----------------|---------------------|
| R5.1 | **Bulk-load en los cuatro loaders** (seed/load OpenAlex, BibTeX, Forager): construir la tabla Arrow de una vez con `Corpus.from_arrow` + helper `corpus._rows_with_ids` (precomputa el `id` D1 por fila), en vez del loop `add_paper`/`_clone` | Cada `add_paper`→`_clone` re-upserteaba la tabla entera (O(n²), Nota 06 RAÍZ 3). El bulk `from_arrow` ya existía y no se usaba en los loaders; mismo resultado, carga lineal | Media: el helper es local a `corpus.py`; los loaders vuelven al loop trivialmente | Sí (PO proxy / Nota 06; verifier PASA) |
| R5.2 | **UTF-8 en la frontera CLI** (`cli/__init__.py:main` → `_force_utf8()`: reconfigura `sys.stdout`/`stderr` a UTF-8 con guarda `hasattr(..., "reconfigure")` + `suppress(Exception)`, **antes** de que Click lea argumentos) | El envelope `--json` usa `ensure_ascii=False`; en la consola cp1252 de Windows los acentos salían corruptos (`ecuaci�n`), rompiendo el contrato agente-native (BUG VERIFICADO, Nota 06 RAÍZ 3). Es el arreglo de mayor impacto/menor costo | Alta: `_force_utf8` es una función aislada, quitable | Sí (PO proxy / Nota 06; verifier PASA) |
| R5.3 | **Retry/backoff en `fetch_citing`** (`_fetch_all_with_retry`: 429/5xx → exponential backoff, 3 intentos); **batching-por-OR NO implementado** | El forward chaining hace N+1 requests; sin retry, un rate-limit de OpenAlex (429) hacía fallar un corpus mediano (falla de **correctitud/robustez**). El batching-por-OR (agrupar `cites:` en una query) lo pedía el spec **"si es factible"** → se evaluó **mejora de PERFORMANCE**, no de correctitud, y **quedó diferido** (el N+1 persiste, pero ahora resiliente). Decisión consciente: priorizar robustez sobre throughput en R5 | Media (retry: local a `OpenAlexSource`). **El batching diferido queda como recomendación de seguimiento** | **Sí — steering** (DoD reconciliado: retry sí, batching diferido) |
| R5.4 | **`AttributeError`→`DependencyError` es responsabilidad del BORDE CLI, no del forager.** `@handle_errors` deja de capturar `AttributeError`; el comando `chain` hace un **pre-check `hasattr(source, "fetch_citing")`** y lanza `DependencyError` (exit 3) accionable; un `AttributeError` inesperado se propaga limpio | El AS-BUILT capturaba `AttributeError` en el decorador como "Capacidad no disponible", **disfrazando bugs reales** de "dependencia faltante" (Nota 06, footgun gemelo). Mover la conversión al borde mantiene el **forager agnóstico de `_errors`** (núcleo puro) y hace visible cualquier bug genuino. Toca el contrato del ADR 0021 §D (exit 3) — reconciliado | Media: el pre-check es local a `chain.py`; revertir re-abre el footgun | **Sí — steering** (ADR 0021 §D enmendado) |
| R5.5 | **`open_store_readonly` para comandos de solo lectura** (`status`/`validate`): falla con `StoreError` accionable si el `.duckdb` no existe, en vez de auto-crear uno vacío. Los comandos de escritura conservan `open_store` | Footgun verificado (Nota 06): `b2g status --store typo.duckdb` creaba un store vacío en silencio, ocultando el typo. Crear-si-falta es correcto en escritura, peligroso en lectura | Alta: `open_store_readonly` es aditivo; los dos comandos eligen la variante | Sí (PO proxy / Nota 06; verifier PASA) |
| R5.6 | **Los 6 footguns restantes cerrados sin enmascarar:** (a) rama muerta `OSError` de `_errors.py` (`if/else` que hacía lo mismo → un único `except OSError → 5`); (b) `except Exception` de `detect_communities` (`facade.py`) eliminado (solo `ImportError` se re-lanza, lo demás propaga); (c) PRISMA campo/op desconocido → `ValueError` accionable (antes `return True` no-op); (d) `.bib` parseo grave → `ValueError`, vacío/sin-título → `UserWarning`; (e) param muerto `g` de `cocitation_quality_report` quitado; (f) `_lib_version` fallback `"0.0.0"`→`"unknown"`; (g) `NetworkSpec.kind: NetworkKind` (sin `Literal` duplicado) | Todos son **no-ops silenciosos / ramas-params muertos / versión inventada** que esconden bugs (Nota 06, catálogo de secundarios). Principio: **fallar/avisar accionable, nunca tragar** (lección 7, AGENTS.md) | Alta cada uno (cambios locales y aditivos) | Sí (PO proxy / Nota 06; verifier PASA) |

> **Cambios de comportamiento (importan para CHANGELOG/API):** PRISMA **lanza** ante campo/op
> desconocido (antes no-op); `status`/`validate` **ya no auto-crean** el store ante typo en `--store`;
> `.bib` roto **lanza**; `_lib_version` desconocida = `"unknown"` (antes `"0.0.0"`); `AttributeError`
> deja de mapearse a exit 3 en el decorador (la capacidad-faltante se detecta en el borde). **Ninguno
> toca `schema="1"` ni los exit codes externos del contrato** (exit 3 sigue siendo "dependencia/capacidad
> faltante", ahora vía `DependencyError` en vez de `AttributeError`).
>
> **Reservas del verifier:** cerradas (el verifier APRUEBA). **No hay reservas de código abiertas.**
>
> **Decisiones de seguimiento (no son de R5 — quedan al PO):** (a) **batching-por-OR de `fetch_citing`**
> (mejora de performance: matar el N+1 agrupando `cites:` en una query; R5 entregó solo retry) — candidato
> a un hito de performance o al Hito 8 (`Enricher` de co-citación); (b) sigue abierta la de R3: **retirar
> el alias `LoopState = CycleState` pre-1.0** y, si se construye el paso 8 del ciclo, agregar **`b2g
> monitor`** (el estado `MONITORED` existe en el modelo, sin comando que lo dispare).
>
> **Veredicto del arquitecto:** **R5 ✅ TERMINADO** — endurece sin cambiar el modelo conceptual; los
> cambios de comportamiento son consistentes con el contrato (la Nota 06 los pidió). R5 no deja
> seguimiento de **código** abierto (solo el batching diferido, que es mejora futura).
>
> **Reconciliación de docs (arquitecto, 2026-06-16):** ADR 0021 (§D enmendado: `AttributeError`→`DependencyError`
> en el borde, `open_store_readonly`), ADR 0023 (AS-BUILT: `NetworkSpec.kind: NetworkKind`, fuente única
> completada), ROADMAP (Hito R5 ✅ + banner as-built + DoD reconciliado: batching diferido; tanda R1–R5
> COMPLETA), ARCHITECTURE.md (§3.1 bulk-load, §6.3 UTF-8/store-readonly, §8 footguns), API.md (PRISMA
> lanza, store read-only, `.bib` lanza, `lib_version` "unknown", forward `DependencyError`+retry),
> CHANGELOG (R5 ✅ Fixed + Changed de comportamiento). La Nota 06
> recibió una nota corta de cierre (rastro histórico, sin reescribir hallazgos).

---

## 2026-06-16 — Cleanup pre-v0.3 (cerrar seguimientos abiertos de R3/R5)

> Tanda de limpieza **antes de v0.3**: cierra tres seguimientos que R3/R5 dejaron abiertos
> (alias `LoopState`, `MONITORED` sin comando, SQL del `merge` por interpolación). **No cambia el
> modelo conceptual.** Implementado + verificado: **327 tests** verdes, mypy strict, ruff check+format
> limpios.

| # | Decisión | Por qué | Reversibilidad | Validada por humano |
|---|----------|---------|----------------|---------------------|
| C.1 | **Alias `LoopState = CycleState` RETIRADO** (de `backends/duckdb.py` y `stores/duckdb.py`); el código usa **solo `CycleState`** (de `bib2graph.cycle`) | Cierra la recomendación abierta de R3.2 ("retirar pre-1.0"). Una sola clase para el concepto del ciclo elimina la ambigüedad de imports y la doble verdad | Alta: re-introducir el alias es mecánico (una línea), pero no hay motivo | **Sí — steering** (cierra R3.2) |
| C.2 | **Comando `b2g monitor` (12° subcomando)**: re-chequea OpenAlex por **citantes nuevos** del corpus (forward chaining), mergea los candidatos nuevos a la biblioteca viva y transiciona a **`MONITORED`** vía `apply_transition(state, "monitor", round)` (paso 8 del ciclo, Ellis). `data = {new_candidates, total_papers, loop_state, round}`, `schema="1"`; `--email`; sin corpus/estado previo → `DataError` (exit 2) | Cierra la recomendación abierta de R3/R5 ("`MONITORED` existe en el modelo, sin comando que lo dispare"). El estado deja de ser inalcanzable; el ciclo de Ellis queda completo en la CLI. Regla `monitor` añadida a `_AVAILABLE_TRANSITIONS` desde `BUILT` y `MONITORED` | Media: el comando es aditivo (módulo propio `cli/commands/monitor.py`); quitarlo vuelve `MONITORED` inalcanzable | **Sí — steering** (cierra R3/R5; ADR 0021 enmendado) |
| C.3 | **`monitor` SIN pre-check de capacidad `fetch_citing`** (asimetría deliberada con `chain`): instancia `OpenAlexSource` fijo, que **siempre** soporta forward; `chain` sí pre-chequea porque acepta `--direction` variable y puede recibir una `Source` de solo-mínimo | El pre-check `hasattr` (enmienda R5.4) es responsabilidad del borde **solo donde la capacidad puede faltar**. En `monitor` no puede faltar → la guardia sería ruido. Es **decisión documentada, no deuda** (ADR 0021 §D enmendado) | Alta: agregar el pre-check sería trivial si en el futuro `monitor` aceptara sources variables | **Sí — steering** (ADR 0021 §D) |
| C.4 | **`merge` de `DuckDBBackend` SIN interpolación de ids**: en vez de `... id IN ('<id>',...) ORDER BY CASE id WHEN ... END` con f-strings, lee todas las filas (`SELECT *`), **ordena en Python** por orden de aparición y reinserta. Orden determinista D3 preservado | Cierra el footgun catalogado en la Nota 06 (`backends/duckdb.py:417,423`): SQL construido con datos (hoy seguro porque los ids son hashes hex, pero frágil). La alternativa **CTE con `VALUES`** quedó **descartada** (ordenar en Python es más simple para el tamaño objetivo y no acopla a un dialecto SQL) | Media: cambio local al `merge`; revertir re-abre el footgun. D3 cubierto por regresión | **Sí — steering** (cierra footgun Nota 06; ADR 0013 AS-BUILT) |

> **Cambios de contrato (importan para CHANGELOG/API/ADRs):** **12 subcomandos** (era 11; `monitor` es el
> 12°); `monitor` transiciona `→ MONITORED` (tabla §F del ADR 0021); el alias `LoopState` ya no existe
> (el contrato usa `CycleState`). **`schema="1"` no se bumpea** (el `data` de `monitor` es payload nuevo,
> no cambia la forma del envelope).
>
> **Seguimientos restantes:** queda **uno** de código abierto — el **batching-por-OR de `fetch_citing`**
> (mejora de performance: matar el N+1 agrupando `cites:` en una query; R5 entregó solo retry/backoff).
> El arquitecto lo **encuadró en el Hito 8** (`Enricher` de co-citación), que es donde se hace el 2º nivel
> de fetch. Ver ROADMAP Hito 8. **No es deuda de correctitud** (el N+1 ya es resiliente al rate-limit). La
> asimetría del pre-check `monitor`/`chain` (C.3) **NO es seguimiento**: es decisión documentada (ADR 0021 §D).
>
> **Reconciliación de docs (arquitecto, 2026-06-16):** ADR 0016 (§Cleanup: `MONITORED` alcanzable, alias
> retirado), ADR 0021 (§Enmienda cleanup: 12° subcomando `monitor`, envelope, asimetría del pre-check),
> ADR 0013 (§AS-BUILT: merge sin interpolación, CTE descartado), ARCHITECTURE.md (`monitor`/`MONITORED`
> alcanzable, `CycleState` única, merge sin interpolación), API.md (subcomando `monitor` 12°, conteo 11→12),
> ROADMAP (seguimientos cerrados, batching → Hito 8, `monitor` ya no "futuro"), CHANGELOG (Added `monitor`,
> Changed/Fixed alias + merge).
