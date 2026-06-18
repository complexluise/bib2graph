# ROADMAP · GUI local (Hitos G1–G5) — **MVP AS-BUILT (G1–G5), gate #34 pendiente**

> ← Volver al [índice del ROADMAP](README.md)

---

> ✅ **MVP AS-BUILT (2026-06-18) — los 5 hitos de construcción (G1–G5) están construidos.** Toda esta
> epic es la **GUI local "tool for thought"**
> ([#34](https://github.com/complexluise/bib2graph/issues/34)), encuadrada por los ADR
> [0027](../decisiones/0027-pivote-posicionamiento-gui-local.md) (pivote de posicionamiento,
> Aceptada 2026-06-18) y [0028](../decisiones/0028-arquitectura-gui-api-capa-servicios.md)
> (arquitectura: capa de servicios neutral + adaptadores, Aceptada 2026-06-18) y la
> [Nota 12](../Notas/12-arquitectura-gui-encuadre.md) (revisión 2026-06-18). Construida en
> `feat/gui-g1-capa-servicios`: G1 (capa de servicios + contrato), G2 (6 lecturas read-only),
> G3 (API local FastAPI + extra `[gui]` + `b2g gui`), G4 (SPA `frontend/`), G5 (empaquetado: el wheel
> incluye el frontend buildeado + job CI JS) — todos con banner AS-BUILT abajo.
>
> **Lo único pendiente es el gate #34, que NO es construcción:** un **tercero** (tesista/docente
> distinto del autor) usa la GUI **sin ayuda** para reproducir/curar el caso `examples/valoraciones/`.
> Si no lo logra, la dirección de la GUI se **revisa** antes de promoverla a oficial (ADR 0027 §Gate).
> El gate es el **criterio de aceptación de producto** de la epic, AL FINAL — no un hito de build.

> **Diferencia con los tramos 01–04.** Aquellos son **as-built** (hitos construidos); esta epic
> **también lo es ahora** (G1–G5). Las cifras de tests de los encuadres previos eran **objetivos "los
> justos"**, no snapshots — la cuenta autoritativa la sigue dando el CI (ver README §Disciplina de tests).

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

> **AS-BUILT (2026-06-18).** Construido en `feat/gui-g1-capa-servicios` (verifier PASA, gate verde, 743
> tests). `src/bib2graph/api/` es la **API local FastAPI** (adaptador delgado sobre `service/`, **no
> importa de `cli/`**; el núcleo no importa `fastapi` — import perezoso): `app.py`
> (`create_app(ws, *, token, cors_origins)` monta routers + CORS + handlers globales, workspace
> singleton), `routers/reads.py` (los **6 GET** de §0.1), `routers/curate.py` (el **POST** de curación),
> `security.py` (token Bearer efímero `secrets.token_urlsafe`), `deps.py` (workspace singleton +
> `require_token` 401 + `WriteLock` global), `envelopes.py` (mapeo código→HTTP, reusa
> `service.build_envelope`/`code_for`). **7 endpoints:** `GET /api/workspace`, `/api/rounds`,
> `/api/paper/{id}`, `/api/paper/{id}/scent`, `/api/network/{kind}`, `/api/compare?a=&b=`,
> `POST /api/paper/{id}/curate` (body `{decision}`). Sube a **`service/curate.py`** la orquestación de
> accept/reject (`accept_papers`/`reject_papers`/`curate_paper`, `decided_at` inyectado en la frontera);
> `run_accept`/`run_reject` quedan como **shims que delegan** (firma intacta). Entra el **19º subcomando
> `b2g gui`** (`cli/commands/gui.py`: uvicorn sobre la API, bind `127.0.0.1`, exit 3 si falta `[gui]`,
> sirve `gui/static/` si existe —frontend G4 aún no—) y el extra **`[gui]` = `fastapi` + `uvicorn`**
> (`pyproject.toml`). Las **4 bifurcaciones se resolvieron como recomendado** (ver §Bifurcaciones G3
> abajo): **B-G3-1** (auth = token Bearer efímero; sin/inválido → **401**), **B-G3-2** (código 5 →
> **409**; excepción inesperada → **500** `INTERNAL_ERROR`, NO 409), **B-G3-3** (**retry cross-process
> diferido**: v1 síncrona + lock global serializado), **B-G3-4** (curación API toma `ws.library_path`, no
> el workspace completo: mutar el corpus solo necesita la ruta al `.duckdb`). **El contrato externo del
> CLI no cambió** (`tests/unit/test_cli.py` intacto) — no requiere ADR nuevo. Contrato exacto de la API:
> [`API.md`](../API.md) §0.2. El resto de la epic (`frontend/` G4, empaquetado G5) **sigue TARGET**.

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

### Bifurcaciones G3 (resueltas, AS-BUILT 2026-06-18)

Las cuatro se resolvieron como recomendado y quedaron reflejadas en el AS-BUILT del banner y en
[`API.md`](../API.md) §0.2:

- **B-G3-1 — ¿cómo se autentica la API local?** Resuelto: **token Bearer efímero**
  (`secrets.token_urlsafe(32)` generado en el arranque de `b2g gui`, header
  `Authorization: Bearer <token>`, verificación `secrets.compare_digest`). Sin token / token inválido →
  **401** (dependencia `require_token`, fuera del contrato de exit codes 0–5: la auth no existe en el CLI).
- **B-G3-2 — código 5 (store) → ¿409 o 503?** Resuelto: **409** (conflicto de store ocupado/corrupto;
  `503` se descartó). Y una **excepción inesperada** (bug interno, no mapeada por `code_for`) → **500**
  `INTERNAL_ERROR`, deliberadamente distinto del 409 para no sugerirle a la SPA reintentar.
- **B-G3-3 — ¿retry de escrituras?** Resuelto: **diferido** — v1 es **síncrona + lock global
  serializado** (una escritura a la vez, mantiene single-writer ADR 0019); jobs async/SSE y retry
  cross-process quedan fuera de v1.
- **B-G3-4 — ¿la curación API toma el workspace o la ruta del store?** Resuelto: **`ws.library_path`**
  (la ruta al `.duckdb`), no el workspace completo — mutar el corpus paper-a-paper solo necesita el
  archivo; coherente con la firma de `service/curate.py` (`store_path`, compartida con los shims del CLI).

---

## Hito G4 — Frontend nuevo (`frontend/`) contra la API real

> **AS-BUILT (2026-06-18).** Construido en `feat/gui-g1-capa-servicios` (verifier PASA; ambos gates
> verdes: frontend `pnpm lint`/`pnpm test:run` —14— /`pnpm build`, Python 744 passed). La **SPA nueva
> nace en `frontend/`** (NO se portó `app/`): React 18 + Vite + TS estricto + Cytoscape/fcose + Zustand
> + Tailwind + **TanStack Query**, con **pnpm** (`package.json` `packageManager: pnpm@9.15.9`). Las
> bifurcaciones del PO se resolvieron así: **B-G4-1** stack = el recomendado (React/Vite/TS/Cytoscape/
> Zustand/Tailwind + TanStack Query); **B-G4-2** dirección visual = **D-2 "Observatorio"** (oscuro,
> grafo-céntrico, **design tokens propios** en `tailwind.config.js`); **B-G4-3** token = **inyectado en
> el `index.html` servido** (recomendado), no pegado a mano. **Qué se construyó:**
>
> - **`frontend/`** (`src/{client,types,store,components,lib,styles}` + `src/__tests__`): cliente TS
>   tipado que **des-envuelve el envelope `schema="1"`** (`error.code` **string**, header
>   `Authorization: Bearer`), tipos que **espejan los DTO reales** de §0.1/§0.2 (no el mock). UI de **3
>   columnas** (rondas · grafo · candidato) + **curar** (refetch tras curar, **sin Louvain
>   client-side** — las comunidades vienen decoradas del servidor) + **diff de rondas** (el
>   diferenciador). Consume los **7 endpoints reales** de G3. `vite.config.ts`: `build.outDir =
>   ../src/bib2graph/gui/static`, `base: "./"`, alias `@` → `frontend/src`. **Tests vitest (14).**
> - **`cli/commands/gui.py`** (wiring del token, B-G4-3): `b2g gui` ahora **inyecta el token** en el
>   `index.html` servido — `_make_index_response()` reemplaza el placeholder `__B2G_TOKEN__`; ruta **`GET
>   /`** sirve el HTML con token **sin** exigir Bearer, y `StaticFiles` (**`html=False`**) sirve los
>   assets. El frontend lee `window.__B2G_TOKEN__`. *(Reemplaza el plan de §5 abajo, que preveía
>   `StaticFiles(..., html=True)`: para poder inyectar el token se usa `html=False` + ruta `GET /`
>   propia.)*
> - **`.gitignore`**: suma `frontend/node_modules/`, `frontend/dist/` y `src/bib2graph/gui/static/`
>   (build output — **NO se commitea**; va al wheel en G5). `frontend/` **sí** se commitea (es código
>   fuente, a diferencia del prototipo `app/`, gitignoreado).
> - **`AGENTS.md`** suma la convención del paquete `frontend/` (JS con pnpm; comandos; alias; stack/D-2)
>   y **`docs/API.md` §0.2** documenta el wiring del token. **El contrato externo del CLI no cambió**
>   (`tests/unit/test_cli.py` intacto) ni el contrato HTTP de los 7 endpoints.
>
> **Sigue TARGET: G5** (empaquetado — vendorear el build al wheel + job CI JS) y el **gate #34**
> (validación con un tercero, al final). Contrato de la API: [`API.md`](../API.md) §0.2.

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

### Encuadre de G4 (arquitecto, 2026-06-18) — estructura, stack, cliente, componentes, wiring

> Encuadre **antes de construir** (mismo formato que G2/G3). G4 es el primer hito de la epic que
> **no es as-built**: define el vertical mínimo de la SPA contra la **API real de G3** (no el mock).
> El prototipo `app/` (ignorado en `.gitignore`, línea 44) es **referencia UX desechable** — NO se
> porta. El objetivo del PO es **alta calidad de diseño**, ejecución muy superior al prototipo.
> **Varias decisiones de abajo son del PO** (stack, dirección visual, entrega del token): ver
> §Bifurcaciones G4.

**Alcance del vertical mínimo (acotado).** Las **3 columnas** (RONDAS · GRAFO · CANDIDATO) + **curar**
(aceptar/rechazar) + **diff de rondas** (el diferenciador, ADR 0027). **NO** entra en G4: `expand`/
forrajeo desde la GUI (no hay endpoint), `search` (no hay endpoint), `reseed` desde la GUI (no hay
endpoint), anotaciones (`note` es advisory, no se persiste — API.md §curate). La SPA solo consume los
**7 endpoints reales** de G3 (API.md §0.2).

#### 1. Estructura propuesta de `frontend/` (monorepo Python + JS)

```
frontend/                       # NO va al wheel; su build (dist/) sí (G5)
├─ package.json                 # pnpm (packageManager: pnpm@…), scripts dev/build/test/lint
├─ pnpm-lock.yaml               # commiteado (lockfile reproducible)
├─ tsconfig.json                # TS estricto (noUncheckedIndexedAccess, strictNullChecks)
├─ vite.config.ts               # build.outDir → ../src/bib2graph/gui/static, base relativa
├─ index.html                   # entry; placeholder de inyección del token (ver §3/§5)
├─ public/
├─ src/
│  ├─ main.tsx                  # entry React
│  ├─ App.tsx                   # layout 3 columnas
│  ├─ client/                   # capa de cliente API tipada (semilla: app/src/client/, CORREGIDA)
│  │  ├─ http.ts                # apiFetch: envelope schema="1", Bearer, ApiError(error.code: string)
│  │  ├─ api.ts                 # las 7 llamadas tipadas (1:1 con los endpoints de G3)
│  │  └─ token.ts               # lee el token inyectado (ver bifurcación B-G4-3)
│  ├─ types/
│  │  └─ api.ts                 # tipos TS que ESPEJAN los DTO reales de §0.1/§0.2 (no el mock)
│  ├─ store/                    # estado global (selección, kind activo, rondas a comparar)
│  ├─ components/
│  │  ├─ workspace/  (Header)
│  │  ├─ rounds/     (RoundsColumn, RoundItem, NetworkKindToggle, CompareControl)
│  │  ├─ graph/      (GraphCanvas, GraphControls, GraphLegend)
│  │  ├─ candidate/  (CandidatePanel, ScentView, CurateActions)
│  │  ├─ diff/       (RoundDiffPanel)
│  │  └─ ui/         (Button, Badge, Tooltip, Spinner, ErrorBanner)
│  ├─ lib/           (format.ts, cytoscapeStyle.ts)
│  └─ styles/
└─ src/__tests__/    (vitest: client contra el contrato + smoke de render)
```

`gui/static/` (destino del build) **no existe hoy** y **no se commitea** (lo genera el build; va al
wheel en G5). Conviene agregar a `.gitignore`: `frontend/node_modules/`, `frontend/dist/`,
`src/bib2graph/gui/static/` (artefacto de build). El monorepo no tiene convenciones en `AGENTS.md`
todavía → **recomiendo** sumar una nota breve en `AGENTS.md` (`frontend/` = JS con pnpm; el resto es
Python con uv) en el mismo PR de G4.

#### 2. Stack recomendado (a confirmar PO — B-G4-1)

**Recomendación: mantener el stack del prototipo, ejecutado a mucha mayor calidad.** Es un stack
**probado para UX de grafos** y no hay razón técnica para cambiarlo; el salto de calidad es de
**diseño y ejecución**, no de tecnología.

| Capa | Recomendado | Por qué |
|---|---|---|
| Framework | **React 18** | Ecosistema, integración Cytoscape madura |
| Build | **Vite 5 + TS estricto** | `outDir` configurable → `gui/static/`; HMR para iterar diseño |
| Grafo | **Cytoscape.js + fcose** | Maduro/performante para ~100–500 nodos (tamaño real del corpus, ~80 en `examples/valoraciones/`) |
| Estado | **Zustand** | Liviano; el estado que cruza columnas es chico |
| Server-state | **TanStack Query** (NUEVO vs prototipo) | El prototipo era mock in-memory; contra API real conviene cache/refetch/estados de carga declarativos. Pequeña adición justificada |
| Estilos | **Tailwind CSS** + tokens de diseño propios | Velocidad; la calidad viene de un **design system propio** (tokens, no utilities genéricas sueltas) |
| Tests | **Vitest + RTL** | Integración nativa con Vite |

Cambio sugerido frente al prototipo: **agregar TanStack Query** (el mock no lo necesitaba; la API real
sí). El resto se mantiene. **Anti-stack** (no usar): Next.js/SSR (local-first), Redux/MobX (overkill),
component-libs opinionadas (MUI/Chakra) que frenan la dirección visual de alta calidad.

#### 3. Capa de cliente API tipada — espeja el contrato REAL (no el mock)

El cliente semilla `app/src/client/http.ts` tiene **dos drifts vs el contrato real de G3** que el
frontend nuevo debe corregir:

- **`error.code` es `string`, no `number`.** El envelope real lleva `error.code: "DATA_ERROR"` |
  `"INTERNAL_ERROR"` | … (códigos de `B2GError`, API.md §0/§0.2), NO un entero. El seed lo tipa
  `code: number` — **incorrecto**.
- **Falta el envelope completo y el Bearer.** El envelope real es
  `{schema, ok, command, exit_code, data, warnings, error}` (7 claves; el seed solo lee
  `{schema, data, warnings, error}`) y **toda** request necesita `Authorization: Bearer <token>`
  (el seed no manda token → todas darían 401).

Contrato del cliente nuevo (tipos TS que espejan los DTO reales):

```typescript
// envelope real (API.md §0/§0.2)
interface EnvelopeError { code: string; message: string }  // code es STRING
interface Envelope<T> {
  schema: "1"; ok: boolean; command: string; exit_code: number;
  data: T; warnings: string[]; error: EnvelopeError | null;
}

// DTOs que espejan service/reads.py (§0.1) y los routers (§0.2) — NO el mock app/src/types
type CurationStatus = "candidate" | "accepted" | "rejected";
type NetworkKind =            // los del NÚCLEO (NetworkKind), no los del mock
  | "bibliographic_coupling" | "cocitation"
  | "author_collab" | "institution_collab" | "keyword_cooccurrence";

interface WorkspaceState {    // GET /api/workspace
  name: string; root: string; created_at: string; bib2graph_version: string;
  source: string | null; loop_state: string | null; round: number;
  total_papers: number; counts_by_status: Record<string, number>;
  transitions_available: string[]; curation_available: string[];
  networks_cache_stale: boolean;
}
interface RoundEntry {        // GET /api/rounds → { rounds: RoundEntry[] }
  id: string; corpus_hash?: string; created_at?: string;
  total_papers: number; schema_version?: string;
  round?: number; loop_state?: string | null;   // solo en id="live"
}
interface Paper {             // GET /api/paper/{id}
  id: string; openalex_id: string | null; doi: string | null; title: string;
  year: number | null; abstract: string | null; is_seed: boolean;
  curation_status: CurationStatus;
  authors_raw: string[]; authors_id: string[];   // listas crudas, NO objetos Author/ORCID
  keywords_id: string[]; references_id: string[]; cited_by_id: string[];
  provenance: unknown[];
}
interface ScentNeighbor { paper_id: string; title: string; weight?: number }
interface Scent {             // GET /api/paper/{id}/scent
  paper_id: string; score: number;
  coupling: ScentNeighbor[]; references: ScentNeighbor[]; cited_by: ScentNeighbor[];
}                             // NO 4 paneles cosméticos del mock
interface NetworkNode {
  id: string; label: string; degree_centrality: number;
  community?: number; year?: number; is_seed?: boolean; curation_status?: CurationStatus;
}
interface NetworkData {       // GET /api/network/{kind}
  nodes: NetworkNode[]; edges: { source: string; target: string; weight: number }[];
  metrics: { n_nodes: number; n_edges: number; density: number;
             num_components: number; avg_clustering: number; n_communities: number };
}                             // NO modularity ni id de red persistido
interface RoundDiff {         // GET /api/compare?a=&b=
  round_a: string; round_b: string;
  added_paper_ids: string[]; removed_paper_ids: string[];
  mutated_hubs: unknown[];    // hoy [] (B-G2-3 diferido)
  metrics_change: { metric: string; before: number; after: number }[];
}
interface CurateResult {      // POST /api/paper/{id}/curate  body {decision}
  accepted_count?: number; rejected_count?: number; ids: string[];
}
```

`apiFetch` corregido: agrega `Authorization: Bearer <token>`, valida `schema==="1"`, y ante
`error !== null` lanza `ApiError(error.code, error.message)` con `code` **string** (la SPA ramea por
`error.code`, no por HTTP status — API.md §0.2). 401 (sin/token inválido) se maneja aparte (no lleva
el envelope estándar; es del adaptador HTTP).

#### 4. Pantallas/componentes del MVP, mapeados a endpoints reales

| Columna / panel | Componentes | Endpoint(s) real(es) |
|---|---|---|
| Header | `Header` (nombre, estado del lazo, ronda) | `GET /api/workspace` |
| **RONDAS** (izq) | `RoundsColumn`, `RoundItem`, `NetworkKindToggle`, `CompareControl` | `GET /api/rounds` (selección de A/B); toggle elige `kind` |
| **GRAFO** (centro) | `GraphCanvas` (Cytoscape+fcose), `GraphControls`, `GraphLegend` | `GET /api/network/{kind}` (color=community, tamaño=degree_centrality) |
| **CANDIDATO** (der) | `CandidatePanel`, `ScentView`, `CurateActions` | `GET /api/paper/{id}`, `GET /api/paper/{id}/scent`, `POST /api/paper/{id}/curate` |
| **DIFF** (overlay/panel) | `RoundDiffPanel` | `GET /api/compare?a=&b=` (added/removed + metrics_change) |

Notas de fidelidad (NO inventar lo que el núcleo no da): el grafo **NO** tiene Louvain client-side
(el prototipo lo hacía sobre el mock); las comunidades vienen **decoradas del servidor** en
`node.community`. Al curar, **NO** se recalcula Louvain en cliente: se refetch del workspace/red (el
recálculo real es server-side vía `b2g build`, fuera del MVP — mostrar `networks_cache_stale` como
aviso). `ScentView` muestra **score + vecinos** (coupling/references/cited_by), no 4 paneles. El
`CandidatePanel` no tiene botón "expandir" funcional (sin endpoint) — omitirlo o deshabilitarlo
explícito.

#### 5. Wiring build → static → `b2g gui`

> **Reconciliado con el AS-BUILT (2026-06-18):** el wiring del token se construyó por **inyección en el
> `index.html` servido** (B-G4-3, recomendado). Difiere de lo previsto abajo en un punto: en vez de
> `StaticFiles(..., html=True)`, el AS-BUILT usa **ruta `GET /` + `_make_index_response`** (que reemplaza
> el placeholder `__B2G_TOKEN__`) y `StaticFiles(..., html=False)` solo para los assets — necesario para
> poder inyectar el token. Ver el banner AS-BUILT de §G4 arriba y [`API.md`](../API.md) §0.2.

- **Build:** `vite build` con `build.outDir = "../src/bib2graph/gui/static"` y `base: "./"` (rutas
  relativas, para que sirva bajo cualquier mount). `pnpm build` deja `index.html` + assets ahí.
- **Servido:** `b2g gui` ya monta `StaticFiles(directory=gui/static, html=True)` **si existe**
  (`cli/commands/gui.py` líneas 73-91). G4 hace que ese directorio **exista** tras el build local;
  G5 lo vendorea al wheel y agrega el job CI.
- **Token — hueco real a resolver en G4 (ver B-G4-3):** hoy `b2g gui` **solo imprime el token a
  stdout** (`gui/commands/gui.py` líneas 100-102); **NO lo inyecta en el HTML servido**. El frontend
  necesita el token para autenticarse. Como `b2g gui` solo edita docs/recomienda aquí, **el arquitecto
  NO escribe ese cambio** — se recomienda al `coder`: en `cli/commands/gui.py`, en vez de
  `StaticFiles` plano para `index.html`, servir el `index.html` con el token inyectado (p. ej. un
  endpoint `GET /` que lee el `index.html` del build y reemplaza un placeholder
  `<meta name="b2g-token" content="__B2G_TOKEN__">`, o `window.__B2G_TOKEN__`). El cliente TS
  (`client/token.ts`) lo lee de ahí. **Decisión del PO sobre el mecanismo: B-G4-3.**

#### 6. Tests del frontend (vitest, los justos)

- **Cliente contra el contrato:** `apiFetch` des-envuelve `data` de un envelope `schema="1"` válido;
  ante `error !== null` lanza `ApiError` con `code` **string**; manda el header `Bearer`. (2-3 tests —
  alto valor, es la costura cliente↔API y donde el seed tenía drift.)
- **Smoke de render:** `GraphCanvas` monta con una `NetworkData` mínima; `RoundDiffPanel` renderiza
  added/removed de un `RoundDiff` conocido (el diferenciador). (2 tests.)
- **NO** E2E (Playwright/Cypress), **NO** pixel-perfect, **NO** un test por componente. El gate #34
  (tercero usando la GUI) es la validación de producto, no una suite E2E en CI.

#### 7. Dirección de diseño — 3 direcciones para que el PO elija (B-G4-2)

Principios transversales (para que **no** sea estética genérica de IA): (a) **el grafo es el héroe** —
las columnas laterales lo enmarcan, no compiten; (b) **una sola pantalla, sin modales que rompan el
flujo** (imagen mental de `app/ARCHITECTURE.md` §2); (c) **tipografía y espaciado de herramienta de
pensamiento**, no de dashboard; (d) **color con significado** (comunidad/curación), no decorativo;
(e) **design tokens propios** (no Tailwind utilities genéricas sueltas). Tres direcciones posibles
(decisión del PO):

- **D-1 · "Cuaderno de laboratorio" (analógico-cálido).** Fondo claro tipo papel, tipografía serif
  para títulos + mono para ids, acentos sobrios. Transmite "instrumento de investigación artesanal".
  Riesgo: legibilidad del grafo sobre fondo claro (cuidar contraste de nodos).
- **D-2 · "Observatorio" (oscuro, foco en el grafo).** Fondo oscuro neutro, el grafo brilla, comunidad
  por color saturado, UI cromáticamente apagada para no competir. Es la pista del prototipo pero
  ejecutada con rigor (jerarquía, densidad, microinteracciones). Más seguro para visualización de redes.
- **D-3 · "Editorial / atlas" (claro, denso en información, alto contraste).** Estética de publicación
  académica: rejilla estricta, alto contraste, datos densos y legibles, decoración mínima. Transmite
  seriedad metodológica. Riesgo: puede sentirse "frío" si no se cuida la microinteracción.

#### Bifurcaciones G4 (decisión del PO)

- **B-G4-1 — Stack.** Recomiendo **mantener** React+Vite+TS+Cytoscape(fcose)+Zustand+Tailwind
  (probado para UX de grafos) y **sumar TanStack Query** (la API real, a diferencia del mock, justifica
  cache/refetch declarativos). ¿Confirmás el stack, o querés cambiar alguna pieza?
- **B-G4-2 — Dirección visual.** Tres direcciones arriba (D-1 cuaderno / D-2 observatorio / D-3
  editorial). Es **tu** decisión y te importa mucho. ¿Cuál guía el diseño? (Se puede prototipar una y
  pivotar; no es irreversible, pero conviene elegir una para no diluir el esfuerzo.)
- **B-G4-3 — Cómo recibe el token el frontend.** Hoy `b2g gui` **solo imprime** el token a stdout (no
  lo inyecta en el HTML). Para que la SPA se autentique sin que el usuario copie/pegue el token,
  recomiendo **inyectarlo en el `index.html` servido** (placeholder `<meta>`/`window.__B2G_TOKEN__`
  reemplazado al servir). Alternativa más simple pero peor UX: el usuario pega el token en un campo.
  ¿Inyección en el HTML (recomendado) o pegado manual? (Implica un cambio chico en `cli/commands/gui.py`
  que ejecuta el `coder`, no el arquitecto.)
- **B-G4-4 — Destino del prototipo `app/`.** `app/` está en `.gitignore` (no commiteado) y es
  desechable. ¿Lo borrás del working tree, lo dejás como referencia local archivada, o lo movés a una
  rama/tag de archivo? (No bloquea G4; es higiene.)

---

## Hito G5 — Empaquetado (wheel con frontend buildeado + CI JS)

> **AS-BUILT (2026-06-18).** Construido en `feat/gui-g1-capa-servicios` (verifier PASA; gate verde).
> Es el **último hito de construcción** del MVP GUI. **Qué se construyó:**
>
> - **Inclusión en el wheel (B-G5-2 = `force-include`, recomendado).** `pyproject.toml`:
>   `[tool.hatch.build.targets.wheel.force-include]` mapea `src/bib2graph/gui/static` →
>   `bib2graph/gui/static`, vendoreando el build del frontend (gitignored) al wheel **sin commitearlo**
>   al VCS. Verificado: `unzip -l` del wheel lista `gui/static/index.html` + assets. **Clone fresco sin
>   `pnpm build` previo → `uv build` falla ruidosamente** (no wheel mudo). El `.gitignore` no se tocó
>   (B-G5 §5: `gui/static/` sigue gitignored + build, no commiteado).
> - **Job CI de frontend (B-G5-3 = siempre, recomendado).** `.github/workflows/ci.yml` suma el job
>   `frontend` (setup-node 20 + corepack/pnpm + `pnpm install --frozen-lockfile` / `lint` / `test:run` /
>   `build`), que **corre siempre** (no path-filtered): valida también la costura `frontend/` →
>   `gui/static/` que alimenta el wheel.
> - **Fix del canal de release (B-G5-1 = sí, autorizado).** `.github/workflows/publish-testpypi.yml`
>   inserta `setup-node` + `pnpm install --frozen-lockfile` + `pnpm build` **ANTES** del `uv build` (sin
>   esto el wheel publicado a TestPyPI saldría mudo). Trusted Publishing intacto; **`release-please.yml`
>   NO se tocó** (coherente con CLAUDE.md: no bumpear versión ni editar CHANGELOG a mano).
> - **Tests de empaquetado (los justos).** `tests/unit/test_packaging_config.py`: **2 tests** que
>   guardan la config `force-include` (clave presente + mapeo correcto). Son **guards de config**, no
>   construyen un wheel real ni levantan uvicorn — el job JS ya corre las 14 de vitest.
>
> **Las 3 bifurcaciones se resolvieron como recomendado:** **B-G5-1** (sí, parchear
> `publish-testpypi.yml`), **B-G5-2** (`force-include`, no build hook), **B-G5-3** (job CI JS siempre).
> El contrato externo del CLI no cambió; `release-please.yml` no se tocó → no requiere ADR nuevo.
>
> **Con G5, los 5 hitos del MVP GUI (G1–G5) están AS-BUILT** — el build entero está completo. Lo único
> pendiente es el **gate #34** (un tercero usa la GUI sin ayuda), que **NO es construcción**: es el
> criterio de aceptación/descarte de producto, al final (§Gate #34 abajo).

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

### Encuadre de G5 (arquitecto, 2026-06-18) — inclusión en el wheel, orden de build, CI JS

> Encuadre **antes de construir** (mismo formato que G2/G3/G4). El arquitecto **no escribe** el código de
> build/CI (es del coder); acá define el mecanismo de menor complejidad sobre el build-system **real** del
> repo y las bifurcaciones para el PO.

**Hallazgo verificado (la trampa de G5).** `gui/static/` **existe** localmente (lo dejó `pnpm build` de
G4) pero está **gitignored** (`.gitignore` línea 65). El build-system es **hatchling** (`pyproject.toml`
`[build-system]`), y hatchling **respeta el VCS por defecto**: lo gitignored **NO entra al wheel aunque
exista en el working tree**. Verificado empíricamente esta sesión: `uv build --wheel` produjo un wheel
**sin** `gui/static/` (solo aparece `cli/commands/gui.py`). Por lo tanto: **tener `pnpm build` corrido NO
basta** — hay que decirle a hatchling que **fuerce** la inclusión de ese directorio. Este es el cambio
central de G5; sin él, el wheel sale mudo y `b2g gui` cae al branch "frontend no construido aún".

**1. Mecanismo de inclusión (recomendado: `force-include` de hatchling).** Es el de **menor
complejidad** y no toca el flujo de release. En `pyproject.toml`, target wheel:

```toml
[tool.hatch.build.targets.wheel.force-include]
"src/bib2graph/gui/static" = "bib2graph/gui/static"
```

`force-include` mete el directorio en el wheel **ignorando el `.gitignore`** (es exactamente su
propósito: vendorear artefactos de build no versionados). El `.gitignore` se mantiene como está
(`gui/static/` sigue sin commitearse). **Trade-off conocido:** si `gui/static/` **no existe** al momento
de `uv build` (p. ej. en un clone fresco sin haber corrido `pnpm build`), hatchling falla o emite un wheel
mudo según versión — por eso el **orden de build** (§2) es parte del DoD: `pnpm build` SIEMPRE antes de
`uv build`. *(Alternativa descartada por más compleja: un build hook custom `hatch_build.py` que invoque
`pnpm build` dentro de `uv build` — ver §2 trade-offs y B-G5-2.)*

**2. Orden de build (recomendado: step de CI, NO build hook Python↔pnpm).** Quien llena `gui/static/` es
`pnpm build`; tiene que correr **antes** del `uv build`. Dos formas:

- **(A, recomendado) Step explícito en el workflow** que publica/empaca: `pnpm install --frozen-lockfile`
  → `pnpm build` → `uv build`. Simple, legible, sin acoplar Python a Node. **Costo:** un `uv build`
  **local** sin haber corrido `pnpm build` antes da wheel mudo — pero es el flujo natural (G4 ya documenta
  `pnpm build` como paso del frontend) y se mitiga con la verificación de §5.
- **(B, NO recomendado) Build hook de hatchling** (`hatch_build.py`) que invoca `pnpm build` desde dentro
  de `uv build`. **Ventaja:** `uv build` local incluye el frontend sin pasos manuales. **Costo alto:**
  acopla el build de Python a tener Node+pnpm disponibles (rompe `uv build` en runners/entornos sin Node,
  contradice "la GUI funciona sin Node" para el *consumidor* —aunque el hook es para el *productor*—, y
  mete lógica de orquestación de subprocess en el empaquetado). Va contra "menor complejidad".

**Recomiendo A.** El acoplamiento Python↔pnpm de B no paga frente a un step de 2 líneas en el workflow.

**3. Dónde corre el build del frontend en el release.** El repo **sí** tiene un canal de publicación:
`publish-testpypi.yml` (TestPyPI vía Trusted Publishing, **disparo manual** `workflow_dispatch`), y su
job hace `uv build` **directo sobre el checkout, sin pnpm** (líneas 34-36). **Ese es hoy el agujero
operativo:** si se dispara tal cual, el wheel publicado a TestPyPI sale **sin frontend**. El coder debe
insertar `setup-node` + `pnpm install --frozen-lockfile` + `pnpm build` **antes** del `uv build` en ese
workflow. `release-please.yml` **no** buildea ni publica artefactos (solo abre el PR de versión/changelog
y crea el tag+Release); **no se toca** — coherente con CLAUDE.md (no bumpear versión ni editar CHANGELOG a
mano). El PRD/ADR habla de "build del frontend en el release (B.3)": en el estado real eso aterriza en
**`publish-testpypi.yml`** (el único que produce wheel distribuible hoy), no en release-please.

**4. Job de CI de frontend (B.3) en `ci.yml`.** Un job nuevo `frontend` (paralelo a `lint`/`test`):
`setup-node` (Node 20 LTS) + `corepack enable` (pnpm viene pinneado por `packageManager: pnpm@9.15.9` en
`package.json`) → `pnpm install --frozen-lockfile` → `pnpm lint` (= `tsc --noEmit`) → `pnpm test:run` (las
14 de vitest) → `pnpm build` (valida que el build no rompe). **Recomendación: que corra siempre**, no solo
si cambió `frontend/`. Razón: el `pnpm build` también valida la costura `frontend/` → `gui/static/` que
alimenta el wheel, y un path-filter agrega complejidad (necesita `dorny/paths-filter` o `paths:` que
interactúa mal con branch protection si el job es required). El job es liviano (~1–2 min con cache de
pnpm). Si más adelante molesta, se filtra; en MVP, simple > óptimo.

**5. `gui/static/`: ¿commiteado o gitignored+build (actual)?** **Recomiendo mantener gitignored + build
(estado actual).** El ADR 0028 §5 dice "el build se vendorea al wheel"; lo que importa es que **el wheel
lo tenga**, no que esté en git. Commitearlo metería un artefacto binario derivado al historial (diffs
ruidosos, drift entre fuente y build commiteado, conflictos de merge en `assets/*.js` con hash). El
`force-include` (§1) cubre el requisito sin commitear nada. **No cambiar el `.gitignore`.**

**6. Verificación local (para el coder).** Reproduce el camino del wheel sin Node en el consumidor:

```bash
cd frontend && pnpm install --frozen-lockfile && pnpm build   # llena src/bib2graph/gui/static/
cd .. && uv build --wheel
unzip -l dist/bib2graph-*.whl | grep "gui/static"              # DEBE listar index.html + assets/
```

Hoy ese `grep` sale **vacío** (verificado esta sesión) — tras el `force-include` debe listar
`bib2graph/gui/static/index.html` y `bib2graph/gui/static/assets/*`. Smoke end-to-end opcional: instalar
el wheel en un venv **sin Node** (`pip install dist/bib2graph-*.whl[gui]`) y correr `b2g gui` apuntando a
un workspace de ejemplo — debe imprimir "Frontend servido desde: …" (no "frontend no construido aún").

**7. Tests (los justos).** El DoD ya pide el smoke correcto: **1 test de empaquetado** que verifique que
el wheel contiene `gui/static/index.html` (puede inspeccionar el `.whl` con `zipfile`, o assertar que
`importlib.resources.files("bib2graph") / "gui" / "static" / "index.html"` existe tras instalar). **No**
E2E del browser, **no** levantar uvicorn real en CI. El job JS (§4) ya corre las 14 de vitest; no duplicar
en pytest.

**8. Docs a sincronizar.** Ninguna además de este apunte. `AGENTS.md` ya documenta `frontend/` (G4). Si el
coder agrega el `force-include`, conviene un comentario en `pyproject.toml` (junto al target wheel)
explicando **por qué** `force-include` y no inclusión normal (porque `gui/static/` es build output
gitignored) — pero eso lo escribe el coder con el código.

### Bifurcaciones para el PO (G5)

- **B-G5-1 — ¿Se toca `publish-testpypi.yml` (el canal de release que manejás con cuidado)?** El wheel
  distribuible **hoy** sale de ese workflow, y hoy saldría **sin frontend** porque hace `uv build` directo
  sin pnpm. Recomiendo insertarle `setup-node` + `pnpm build` antes del `uv build`. **Es el único punto
  donde G5 toca tu flujo de release** — y es un agujero real, no cosmético. ¿Lo autorizás? (`release-please.yml`
  no se toca.)
- **B-G5-2 — Inclusión en el wheel: `force-include` (recomendado) vs build hook Python↔pnpm.** Recomiendo
  `force-include` (2 líneas en `pyproject.toml`, no acopla Python a Node, el orden de build lo garantiza
  el workflow). La alternativa (build hook que corre `pnpm build` dentro de `uv build`) hace que
  `uv build` local incluya el frontend automáticamente, pero **acopla el empaquetado a tener Node**
  instalado y rompe `uv build` donde no lo haya. ¿`force-include` (simple) o build hook (auto pero
  acoplado)?
- **B-G5-3 — Job CI JS: ¿siempre o solo si cambió `frontend/`?** Recomiendo **siempre** (valida también la
  costura que alimenta el wheel; el filtro agrega complejidad con branch protection). ¿OK, o preferís
  path-filter para ahorrar ~2 min cuando el PR es solo-Python?

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
