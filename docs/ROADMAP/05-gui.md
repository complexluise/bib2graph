# ROADMAP · GUI local (Hitos G1–G5) — **TARGET, gateado por #34**

> ← Volver al [índice del ROADMAP](README.md)

---

> ⚠️ **TARGET, NO as-built.** Toda esta epic es la **GUI local "tool for thought"**
> ([#34](https://github.com/complexluise/bib2graph/issues/34)), encuadrada por los ADR
> [0027](../decisiones/0027-pivote-posicionamiento-gui-local.md) (pivote de posicionamiento,
> Aceptada 2026-06-18) y [0028](../decisiones/0028-arquitectura-gui-api-capa-servicios.md)
> (arquitectura: capa de servicios neutral + adaptadores, Aceptada 2026-06-18) y la
> [Nota 12](../Notas/12-arquitectura-gui-encuadre.md) (revisión 2026-06-18). Fecha del plan: 2026-06-18.
>
> **El gate de éxito/descarte ([#34](https://github.com/complexluise/bib2graph/issues/34)) va AL
> FINAL, no antes:** un **tercero** (tesista/docente distinto del autor) usa la GUI **sin ayuda**
> para reproducir/curar el caso `examples/valoraciones/`. Si no lo logra, la dirección de la GUI se
> **revisa** antes de promoverla a oficial (ADR 0027 §Gate). El roadmap construye el vertical mínimo
> **hacia** ese gate; los ADR de arquitectura ya están firmados, así que **G1 puede empezar ahora**
> (no espera al gate; el gate valida el producto terminado).

> **Diferencia con los tramos 01–04.** Aquellos son **as-built** (hitos construidos). Este es un
> **plan a futuro**: el alcance, la secuencia y las bifurcaciones para el PO. Las cifras de tests son
> **objetivos "los justos"**, no snapshots — la cuenta autoritativa la sigue dando el CI
> (ver README §Disciplina de tests).

## Principio rector (de ADR 0028)

**Una sola verdad de orquestación y de contrato.** CLI y API son **adaptadores delgados** de una
**capa de servicios neutral** `src/bib2graph/service/` (sin `print`, `sys.exit`, Click ni FastAPI).
El contrato externo del CLI —envelope `schema="1"`, jerarquía `B2GError`, exit codes 0–5
(ADR [0021](../decisiones/0021-cli-agente-native-contrato.md))— **NO cambia** en ningún hito de esta
epic. Cada hito mantiene el gate verde (`ruff`/`mypy`/`pytest`) **sin tocar los tests del CLI**.

El prototipo `app/` (frontend React mock + server FastAPI embrión) es **referencia UX desechable**,
**no** se porta: el `frontend/` de G4 nace nuevo y su cliente TS se siembra del contrato real.

---

## Hito G1 — Capa de servicios neutral + contrato subido; CLI = adaptador

**Alcance**

- Crear `src/bib2graph/service/` y **subir el contrato** que hoy vive en `cli/`: el envelope
  `schema="1"` (`build_envelope`/`ENVELOPE_SCHEMA_VERSION`, hoy `cli/_envelope.py`), la **jerarquía
  de errores tipados** (`B2GError` + subclases, hoy `cli/_errors.py`) y el **mapeo error→código**
  (hoy embebido en `handle_errors`). La capa es **agnóstica de transporte**.
- `cli/_envelope.py` y `cli/_errors.py` pasan a **re-exportar** desde `service/` (no se borran): los
  imports existentes del CLI y de los tests (`from bib2graph.cli._errors import DataError`,
  `from bib2graph.cli._envelope import build_envelope`) **siguen funcionando idénticos**. La parte de
  **I/O** del CLI (`emit`/`emit_human`/`print`/`sys.exit` y el decorador `handle_errors` que llama a
  `sys.exit`) **se queda en `cli/`** — eso es lo propio del adaptador.
- Establecer el **patrón de servicio** (cómo se expone una operación de orquestación, agnóstica de
  transporte, devolviendo `data: dict` o lanzando `B2GError`) **sin** mover de golpe las 18+ funciones
  `run_<cmd>`. G1 fija la capa y el contrato; la migración de la orquestación es **incremental**
  (G2 y posteriores), coherente con el end-state del ADR 0028 (CLI y API ambos adaptadores).

**Historias (PRD §7):** ninguna directa de usuario. Es **infraestructura** que habilita **E2**
(contrato agente-native, ahora compartible por la API) y **desbloquea** toda la épica D vía la API
(G2/G3). Cierra el drift ya iniciado (`app/server/errors.py` con su `envelope()` duplicado).

**Criterios de aceptación (DoD)**

- Existe `src/bib2graph/service/` con el envelope, los errores y el mapeo error→código, **sin
  importar** `click`, `fastapi`, ni hacer `print`/`sys.exit`.
- `cli/_envelope.py` y `cli/_errors.py` **re-exportan** desde `service/`; `from bib2graph.cli._errors
  import B2GError, DataError, …` y `from bib2graph.cli._envelope import build_envelope,
  ENVELOPE_SCHEMA_VERSION` resuelven a los **mismos** objetos.
- **El contrato externo es idéntico:** mismo envelope (`schema="1"`, mismas claves), mismos exit codes
  0–5 para los mismos errores. **Los tests del CLI pasan SIN modificarse** (`tests/unit/test_cli.py`
  es la red de seguridad — ver abajo).
- `cli` vuelve a no depender de ningún otro frontend; `service/` no importa `cli/`.
- Gate verde completo (`ruff check . && ruff format --check . && mypy src && pytest`).

**Tests (TDD — los justos)**

- **`tests/unit/test_cli.py` no se toca** y queda verde: es la prueba de que el contrato externo no
  driftó (ya cubre forma del envelope —líneas ~150/172— y los exit codes 1/2/3/5 —líneas
  ~363/378/405/531—). Es la **red de seguridad** del refactor.
- **1–2 tests nuevos de `service/`** (los justos): que `service.build_envelope(...)` produce el
  envelope canónico `schema="1"` y que el **mapeo error→código** devuelve 0–5 para cada subclase de
  `B2GError` (camino feliz + 1 falla por código). No re-testear lo que `test_cli.py` ya cubre vía
  re-export.

**Se vuelve posible:** que la API (G3) reuse el **mismo** contrato sin importar `cli/` ni
reimplementarlo, y que las lecturas de servicio (G2) cuelguen de una capa neutral.

---

## Hito G2 — Lecturas de servicio que el CLI no expone

> **AS-BUILT (2026-06-18).** Construido en `feat/gui-g1-capa-servicios` (verifier PASA, gate verde).
> `src/bib2graph/service/reads.py` expone las **6 lecturas read-only** (cada una recibe un `Workspace`
> resuelto, abre el store en modo lectura y devuelve un `dict`/`list[dict]` serializable o lanza un
> `B2GError`): `get_workspace`, `list_rounds`, `get_paper`, `get_scent`, `get_network`,
> `compare_rounds` (el diferenciador). Las 3 bifurcaciones se resolvieron como recomendado: **B-G2-1 =
> Opción A** (ronda = snapshot sellado; `list_rounds` usa el nuevo helper `Workspace.list_snapshots()`
> y agrega una entrada sintética `id="live"`); **B-G2-2** (`get_scent` = score de acoplamiento real +
> vecinos `coupling`/`references`/`cited_by`, NO 4 paneles cosméticos); **B-G2-3** (`get_network`
> recomputa la red de la ronda **viva** con `Networks.build`+`decorate`; `kind` inválido → `DataError`;
> la cache `networks/` por snapshot queda diferida a G3 y `mutated_hubs` de `compare_rounds` queda `[]`).
> El **contrato externo del CLI no cambió** (`tests/unit/test_cli.py` intacto). Firmas exactas y forma
> de los DTO de retorno: ver [`API.md`](../API.md) §0.1. El resto de la epic (API/`b2g gui`/`frontend/`,
> G3–G5) **sigue TARGET**.

**Alcance**

- Exponer en `service/` **funciones de lectura** que la SPA necesita y que el CLI **nunca tuvo como
  subcomando** (hallazgo de Nota 12 punto 2 sobre el mock `app/src/mock/api.ts`): scent de un paper,
  `network(round, kind)`, listado de rondas, **diff entre rondas** (el "git de la investigación", el
  diferenciador de ADR 0027) y `paper(id)`. La convergencia es en **servicios**, no en subcomandos
  artificiales.
- Estas lecturas son **read-only sobre el workspace** (ADR 0029): abren el store, leen, no transicionan
  el `CycleState` ni mutan el corpus. Son la materia prima de la lectura visual de la GUI.
- Migrar **incrementalmente** la orquestación de algunos `run_<cmd>` de lectura a `service/` cuando
  comparten lógica con estas funciones (p. ej. la lectura que hoy hace `run_status`/`run_inspect`),
  re-exportando desde `cli/commands/` para no romper imports — primer paso real del end-state 0028.

**Historias (PRD §7):** habilita la **épica D (lectura visual)** vía API/SPA — **D1** (las cinco
proyecciones leídas por `(round, kind)`), **D2** (métricas/comunidades servidas), **D3**
(composición/asortatividad por comunidad, ya calculadas por los proyectores). Habilita **E1**
(comparar snapshots/rondas = diff de rondas). El scent sirve **B3** (ranking por estructura) en la GUI.

**Criterios de aceptación (DoD)**

- `service/` expone lecturas para: scent de un paper, `network(round, kind)`, rondas, diff de rondas,
  paper por id. Cada una devuelve `data: dict` serializable (o lanza `B2GError` tipado).
- **Sin red, sin mutación, sin transición de ciclo.** Determinismo coherente con R2 (mismo corpus →
  misma lectura).
- El CLI no regresiona (sus tests siguen verdes); lo migrado se re-exporta.

**Tests (TDD — los justos)**

- Una lectura representativa contra un corpus sintético chico: `network(round, kind)` devuelve los
  nodos/aristas esperados; **diff de rondas** sobre dos rondas conocidas devuelve el delta correcto
  (alto valor: es el diferenciador). No testear cada getter.

**Se vuelve posible:** que la API (G3) sirva la lectura visual sin forzar granularidad imperativa de
CLI (riesgo de producto de Nota 12).

### Contrato de las 6 lecturas de G2 (encuadre 2026-06-18)

> **Reconciliado con el AS-BUILT (2026-06-18):** este encuadre se construyó tal cual, con las 3
> bifurcaciones resueltas como recomendado (B-G2-1 Opción A: ronda = snapshot; B-G2-2: scent = score de
> acoplamiento + vecinos; B-G2-3: `get_network` solo la ronda viva). La firma real de cada lectura toma
> el `Workspace` resuelto como primer argumento (`get_paper(ws, paper_id)`, `compare_rounds(ws,
> round_a, round_b)`, etc.) — el encuadre de abajo las escribió sin `ws` por brevedad. El contrato
> definitivo (firmas y DTO de retorno) vive en [`API.md`](../API.md) §0.1.

> Encuadre del arquitecto antes de construir. Las firmas devuelven `dict` serializable o lanzan
> `B2GError` tipado (agnóstico de transporte, ADR 0028). **El origen de cada campo está anclado al
> núcleo real**; los campos del mock `app/src/` que el núcleo no sostiene hoy se marcan abajo.

**Hallazgo de scoping (bifurcación PO).** El mock modela `Round` como entidad de primera clase con
`id`, `parent_id`, `paper_ids[]`, `network_id`, `cycle_state`. **El núcleo no tiene eso.** "Ronda" hoy
es un **contador entero** en `loop_state_log (state, round, recorded_at)` sobre **un único corpus vivo**
(`cycle.py` `apply_transition`: `reseed` incrementa el contador). No hay corpus por ronda ni grafo de
parentesco. La materialización real de "una foto de la investigación" son los **snapshots sellados**
(`<workspace>/snapshots/<dir>/` con `manifest.json` + parquet, `corpus.snapshot()`). Ver bifurcación
B-G2-1 abajo: G2 define `Round`/`compare_rounds` **sobre snapshots**, no sobre el contador.

- `get_workspace() -> dict` — origen: `Workspace.resolve()` (`workspace.py`).
  - `name` ← `manifest.name`; `root` ← `ws.root`; `created_at` ← `manifest.created_at`;
    `bib2graph_version` ← `manifest.bib2graph_version`; `source` ← `ws.source`;
    `loop_state` ← `backend.loop_state()` (str|null); `round` ← `backend.loop_round()` (int);
    `total_papers` ← `len(corpus)`; `counts_by_status` ← GROUP BY `curation_status`.
  - Mock-no-sostenido: `id` (no existe; usar `name`). Reusar `run_status` (migrar su lectura a servicio).

- `list_rounds() -> list[dict]` — origen: **snapshots sellados** (`ws.snapshots_dir`) + `loop_state_log`.
  - Por snapshot: `id` ← nombre del dir; `corpus_hash` ← `manifest.corpus_hash`;
    `created_at` ← mtime del dir o campo del manifest; `total_papers` ← filas del parquet;
    `schema_version` ← `manifest.schema_version`. La ronda **viva** (sin snapshot) se incluye como
    entrada sintética con `id="live"`, `round` ← `loop_round()`, `loop_state` ← `loop_state()`.
  - Mock-no-sostenido: `parent_id`, `paper_ids[]` (no se persiste linaje; `paper_ids` se deriva del
    parquet del snapshot bajo demanda en `compare_rounds`, no se materializa en el listado),
    `network_id`, `label`.

- `get_paper(paper_id: str) -> dict` — origen: fila del corpus (`CORPUS_SCHEMA`, `corpus.py`).
  - `id` ← `Col.ID`; `openalex_id` ← `Col.OPENALEX_ID`; `doi` ← `Col.DOI`; `title` ← `Col.TITLE`;
    `year` ← `Col.YEAR`; `abstract` ← `Col.ABSTRACT`; `is_seed` ← `Col.IS_SEED`;
    `curation_status` ← `Col.CURATION_STATUS`; `authors_raw` ← `Col.AUTHORS_RAW`;
    `keywords_id` ← `Col.KEYWORDS_ID`; `references_id` ← `Col.REFERENCES_ID`;
    `cited_by_id` ← `Col.CITED_BY_ID`; `provenance` ← `ProvenanceEvent.parse_list(Col.PROVENANCE)`.
  - Lanza `DataError` si el id no existe (como `run_inspect`). Migrar la lectura de `run_inspect --id`.
  - Mock-no-sostenido: `authors[]` como objetos `{id,name,orcid}` (el núcleo guarda `authors_raw[]`
    paralelo a `authors_id[]`; no hay ORCID ni objeto autor — exponer ambas listas, no objetos);
    `community`/`degree_centrality` (son **de red**, no del paper — viven en `get_network`, no acá);
    `round_added` (no se persiste por paper; lo más cercano es `provenance[].chaining_hop`).

- `get_scent(paper_id: str) -> dict` — origen: `foraging/scent.py` + índices de `projectors.py`.
  - El scent del núcleo es **score escalar** (`compute_backward_scent`/`compute_forward_scent` → ranking
    por `rank_candidates`), no las 4 listas del mock. Forma realista anclada a lo que el núcleo da hoy:
    `paper_id`; `coupling` ← lista `{paper_id, title, weight}` de corpus-papers que **comparten
    referencias** con el paper (acoplamiento bibliográfico vía `collect_item_to_papers` sobre
    `references_id`); `references` ← `references_id` resueltos a `{paper_id, title}` cuando el id está
    en el corpus; `cited_by` ← `cited_by_id` resueltos igual.
  - Mock-no-sostenido / a confirmar con PO (bifurcación B-G2-2): `citations`/`coupling` con pesos
    arbitrarios `1+degree*3` (cosmético del mock); `coauthors` con `shared_papers` (computable de
    `authors_id`, pero **no es scent** — es co-autoría); `keywords` con `weight` decreciente (cosmético).
    `compute_*_scent` está pensado para **candidatos fuera del corpus** (forrajeo), no para un paper ya
    dentro. Para B3 ("¿por qué este candidato?") en la GUI, el scent honesto es el **score de
    acoplamiento** y los vecinos compartidos, no 4 paneles inventados.

- `get_network(round: str, kind: str) -> dict` — origen: artefactos en `<workspace>/networks/<kind>/`
  (`b2g build`/`b2g networks`) o recomputo con `Networks.build` + `decorate`.
  - `kind` usa los valores de `NetworkKind` del **núcleo** (`bibliographic_coupling`, `cocitation`,
    `author_collab`, `institution_collab`, `keyword_cooccurrence`) — **NO** los del mock (`co_citation`,
    `co_authorship`, `co_occurrence`, `institutions`): el frontend nuevo se siembra de estos.
  - `nodes[]`: `{id, label, degree_centrality, community?, year?, is_seed?, curation_status?}` ← atributos
    inyectados por `decorate.decorate_graph` (label/degree siempre; year/is_seed/curation/community solo
    en redes de paper). `edges[]`: `{source, target, weight}` ← aristas del `nx.Graph`.
    `metrics`: `{n_nodes, n_edges, density, num_components, avg_clustering, n_communities}` ←
    `network_metrics(g)` + conteos del grafo + nº de comunidades distintas en `artifact.communities`.
  - Mock-no-sostenido: `modularity` (no lo computa `network_metrics` hoy — omitir o derivar aparte);
    `id`/`round_id` de red (no hay entidad red persistida con id; la clave es `(round,kind)`).
    Para `round`: en G2 v1, `kind` se lee del `networks/` del corpus **vivo** (la cache de build); el
    parámetro `round` apunta a un snapshot (ver B-G2-1) — si no hay redes por snapshot, `get_network`
    solo sirve la ronda viva y lanza `DataError` accionable para snapshots sin redes construidas.

- `compare_rounds(a: str, b: str) -> dict` — **el diferenciador** (ADR 0027). Origen: dos snapshots
  sellados (parquets) cargados read-only y diffeados por `Col.ID`.
  - `round_a`, `round_b`; `added_paper_ids` ← `ids(b) - ids(a)`; `removed_paper_ids` ← `ids(a) - ids(b)`;
    `metrics_change` ← `[{metric, before, after}]` con `n_papers` (filas de cada parquet) y, si ambos
    snapshots tienen `networks/` construido, `n_communities`/`density` por kind (de los `metrics.json`).
  - Mock-no-sostenido: `mutated_hubs` con `degree_before/after` (requiere red por snapshot con
    centralidad comparable; **diferido** salvo que ambos snapshots tengan redes construidas — marcar
    como campo opcional vacío si no hay datos, no inventarlo).

### Bifurcaciones para el PO (G2)

- **B-G2-1 — ¿"Ronda" = snapshot o = contador?** Recomiendo: el contrato `Round`/`compare_rounds` de G2
  se ancla a **snapshots sellados** (`b2g snapshot`), que son las únicas fotos reproducibles del corpus.
  El `loop_round` entero se expone como metadato del workspace, no como entidad navegable. Implica que el
  journey de validación debe **tomar snapshots** entre rondas para que el diff tenga dos lados. ¿Lo
  aceptás, o querés materializar rondas de primera clase (corpus por ronda + linaje) — lo que es un
  cambio de modelo de datos y un ADR nuevo?
- **B-G2-2 — Forma de `get_scent`.** El scent del núcleo es un **score de acoplamiento** para candidatos,
  no los 4 paneles del mock (coupling/citations/coauthors/keywords con pesos cosméticos). Recomiendo
  exponer el scent honesto (score + vecinos compartidos) y dejar co-autoría/keywords como vistas
  separadas si la UX las pide. ¿Confirmás, o querés que G2 calcule los 4 paneles (más superficie, pesos
  a definir)?
- **B-G2-3 — `get_network(round=...)`.** En v1 solo hay `networks/` para el corpus vivo (una cache por
  workspace). Servir redes **por snapshot** exige construirlas por snapshot (no existe hoy). Recomiendo:
  G2 sirve la red de la ronda viva; `round` distinto de "live" sin redes → `DataError` accionable. ¿OK?

---

## Hito G3 — API local (FastAPI) + extra `[gui]` + subcomando `b2g gui` (19º)

**Alcance**

- `src/bib2graph/api/` (**costura opt-in**): FastAPI **delgado** que llama a `service/`, **reusa el
  mismo envelope** y traduce el código del contrato a **HTTP status** (mapeo ADR 0028 §7:
  `0`→200, `1`→400, `2`→422, `3`→501, `4`→502, `5`→409/503; el envelope viaja igual en el body, la SPA
  lee `error.code`). Bind **`127.0.0.1`** + **token efímero** (Nota 12 C.3). **Import perezoso**: el
  núcleo no importa `fastapi`.
- **Operaciones largas (v1, ADR 0028 §6):** ejecución **síncrona** + **lock global serializado** (una
  escritura a la vez; mantiene single-writer de ADR 0019). Jobs async/SSE de progreso **diferidos**.
- **Extra `[gui]`** = `fastapi` + `uvicorn` (ADR 0005), cierra la deuda de instalarlos a mano.
- **Subcomando `b2g gui` (19º)** (`cli/commands/gui.py`): levanta uvicorn sobre la API, sirve los
  assets pre-build del frontend (de G4), abre el browser. Es el adaptador de "arranque local".
- Retirar `app/server/errors.py` (su `envelope()` duplicado) a favor del contrato neutral de G1.

**Historias (PRD §7):** **E2** extendida (el contrato agente-native ahora también por HTTP, no solo
CLI). Es el transporte que habilita toda la épica D en la SPA (G4).

**Criterios de aceptación (DoD)**

- `uv sync --extra gui` instala `fastapi`+`uvicorn`; sin el extra, importar el núcleo **no** falla
  (import perezoso) y `b2g gui` da error accionable **exit 3** (dependencia faltante) — coherente con
  el contrato.
- La API bindea **solo** `127.0.0.1`, exige el **token efímero**, serializa escrituras con el **lock
  global**, y **reusa** `service.build_envelope` (no reimplementa el envelope).
- El mapeo código→HTTP es el de ADR 0028 §7; el body lleva el envelope `schema="1"` íntegro.
- `b2g gui` arranca la API y sirve los static; el **20º+** y demás contratos CLI no regresionan.

**Tests (TDD — los justos)**

- El mapeo **código→HTTP** (un caso por código 0–5; alto valor, es contrato nuevo) con la API en
  modo test (sin red real, store sintético).
- Que la API **rechaza** sin token y **acepta** con token (1 test de seguridad).
- *No testear* uvicorn/el browser de `b2g gui` (plumbing); sí la **función** que arma la app.

**Se vuelve posible:** que la SPA hable HTTP/JSON con el workspace local reusando el contrato.

---

## Hito G4 — Frontend nuevo (`frontend/`) contra la API real

**Alcance**

- **SPA NUEVA** (Vite/TS) en `frontend/` (monorepo Python+JS). **NO se porta** `app/src/` (mock
  desechable): se construye de cero, **alta calidad de diseño** (Notas
  [07](../Notas/07-frontend-tool-for-thought.md)/[08](../Notas/08-referentes-frontend.md)/[10](../Notas/10-sintesis-contextualizacion-gui.md):
  tool-for-thought no-lineal, UX-first, grafo-lienzo). Su cliente TS se siembra del contrato real
  (envelope `schema="1"`), no del mock.
- **MVP read-only-first:** lectura visual de la estructura (épica D) — proyecciones, comunidades,
  composición, scent — y **diff de rondas** (diferenciador ADR 0027). La **curación** (C4:
  aceptar/rechazar) entra como segunda capa una vez sólida la lectura.
- El build se **vendorea** a `src/bib2graph/gui/static/` (lo sirve `b2g gui`); `frontend/` **no** va al
  wheel (su build sí, en G5). Usar **pnpm**, nunca npm (preferencia firme del PO).

**Historias (PRD §7):** materializa la **épica D completa** como lectura visual (la GUI *es* la capa
de lectura visual — Hito 10 viz absorbido aquí, ROADMAP 04) — **D1/D2/D3** visualizadas, **E1** como
diff de rondas; luego **C4** (aceptar/rechazar/curación) en la GUI, complementando la curación CLI/CSV
(`b2g curate`). **B3** (scent) como guía visual del candidato.

**Criterios de aceptación (DoD)**

- La SPA carga contra la **API real** (no mock), lee `error.code` del envelope, y renderiza al menos:
  una red por `(round, kind)`, comunidades/composición, y el **diff de rondas**.
- Curación (aceptar/rechazar) escribe vía API → `service/` → workspace, **respetando el lock global**
  y sin romper la reproducibilidad (R2).
- Calidad de diseño revisada (no es el mock `app/`): el `app/` puede borrarse o quedar como referencia
  archivada (bifurcación PO, abajo).

**Tests (TDD — los justos)**

- Tests JS **simples** del cliente contra el contrato (forma del envelope, manejo de `error.code`) y
  smoke de los componentes clave (render de una red, del diff). **No** suite E2E pesada en CI todavía.
- *No testear* pixel-perfect ni cada componente; sí el contrato cliente↔API.

**Se vuelve posible:** la lectura visual no-lineal y la curación desde la GUI sobre el workspace local.

---

## Hito G5 — Empaquetado (wheel con frontend buildeado + CI JS)

**Alcance**

- **El wheel incluye el frontend buildeado** en `src/bib2graph/gui/static/` → `b2g gui` funciona **sin
  Node** instalado (ADR 0028 §5, Nota 12 B.1).
- **Job de CI de frontend** (lint/test/build JS con pnpm) + **build del frontend en el release** (B.3).
- Cierra la epic a nivel de empaquetado para el usuario semi-técnico (ADR 0027): `uv sync --extra gui`
  + `b2g gui`, sin tocar Node.

**Historias (PRD §7):** ninguna directa; hace **instalable y distribuible** todo lo anterior (cierra
el canal pip/uv de ADR 0027).

**Criterios de aceptación (DoD)**

- El wheel instalado **sin Node** corre `b2g gui` y sirve la SPA buildeada.
- El CI tiene un job JS (lint/test/build) y el release buildea el frontend antes de empacar.
- `release-please` sigue siendo el publicador (no se bumpea versión ni se edita CHANGELOG a mano).

**Tests (TDD — los justos)**

- Smoke: que el wheel incluye `gui/static/` y que `b2g gui` levanta sin Node (test de empaquetado, no
  E2E del browser).

**Se vuelve posible:** distribuir la GUI a un tercero por pip/uv — **precondición del gate #34**.

---

## Gate #34 — validación con un tercero (criterio éxito/descarte, AL FINAL)

> **No es un hito de construcción:** es el **criterio de aceptación de la epic** (ADR 0027 §Gate). Un
> **tesista/docente distinto del autor** instala (`uv sync --extra gui`), corre `b2g gui` y
> **reproduce/cura `examples/valoraciones/` sin ayuda**. **Éxito** → la GUI se promueve a oficial.
> **Descarte** → se revisa la dirección antes de promoverla (no se da por cumplido aquí). Ver
> [Nota 09](../Notas/09-sesion-qa-prueba-ecologia-valoraciones.md) (sesión QA con tercero) como
> referencia de método.

---

## Idea parqueada (NO es hito) — sugerencias de IA para curación en el CLI

> **Backlog/idea, no planificada.** Asistencia de IA que **sugiera** (no decida) curación en el CLI,
> **marcada explícitamente como sugerencia**. **Tensión con ADR
> [0022](../decisiones/0022-producto-sin-ia-generativa.md)** (el producto no usa IA generativa) y
> **riesgo de sobre-ingeniería**. No es hito ni tiene DoD; se registra para no perderla. Reabrirla
> requeriría un ADR que reconcilie con 0022 y una decisión de producto del PO. El "porqué" de un
> candidato lo da hoy la **estructura visible** (scent bibliométrico, redes), no un LLM.
