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
> [`ARCHITECTURE.md`](ARCHITECTURE.md); método en [`metodología.md`](Notas/metodología.md). El `Corpus`
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
> v0.1 queda feature-complete** (ver [`ROADMAP.md`](ROADMAP/README.md)).
>
> **Sincronizado con el Hito 5 (2026-06-15):** `Forager`, `GrowthPreview`, `RankedCandidates`,
> `Preprocessor`, `FilterCriterion`/`apply_filters` están **construidos** (§5/§6). El *information
> scent* es **frecuencia de enlace** (no acoplamiento/centralidad); `preview` opera **sin red**
> (backward exacto local; forward no estimable → `chain`); los filtros PRISMA **marcan `rejected`
> (no borran)**; `apply_thesaurus` **sobrescribe `keywords_id` desde `keywords_raw`** (ADR
> [0020](decisiones/0020-metodo-forrajeo-scent-filtros-reject.md); thesaurus ADR 0011). `depth>1`
> lanza `NotImplementedError`; `explain_candidate` (B4) es un stub gateado en `[llm]`.
>
> **Sincronizado con el Hito 6 (2026-06-15):** el **CLI agente-native `b2g`** está **construido**
> (paquete `bib2graph.cli`, §convenciones): **12 subcomandos** (`seed`, `chain`, `filter`, `build`,
> `export`, `snapshot`, `status`, `inspect`, `validate`, `accept`, `reject`, **`monitor`**), **envelope
> JSON común versionado** (`schema="1"`), exit codes 0–5 mapeados **por tipo de error**, opción global
> `--store` (obligatoria) y `CycleState` que transiciona automáticamente por comando (ADR
> [0021](decisiones/0021-cli-agente-native-contrato.md)). **Con el Hito 6, las capacidades de v0.2
> (Hitos 5–6) quedan completas** (ver [`ROADMAP.md`](ROADMAP/README.md)). *(El 12° subcomando `monitor`
> —AS-BUILT del cleanup pre-v0.3— cierra el paso 8 del ciclo: `MONITORED` ahora es alcanzable.)*
>
> **Sincronizado con el Hito 8 — Ciclos 8a + 8b (2026-06-16):** la costura **`Enricher`** está
> **construida** (§3) y suma el **13° subcomando `enrich`** (refs→DOI **+ co-citación** sobre
> OpenAlex, núcleo; **NO** transiciona el `CycleState`). El Enricher vive en el **núcleo sobre
> OpenAlex**, no en `[s2]` (ADR [0025](decisiones/0025-enricher-cocitacion-openalex.md)). La
> **co-citación es end-to-end**: `enrich` puebla `cited_by_id` desde las semillas aceptadas (vía
> `OpenAlexSource.fetch_citing_batch`, §2) y `Networks.quick` devuelve **4 o 5 redes** según haya
> `cited_by_id` (§10). Flag `--max-citing`. **Hito 8 completo.**
>
> **Sincronizado con labels/decorate — #25 (AS-BUILT, 2026-06-16):** se agregó la **capa frontera
> `decorate`** (§7.1, `networks/decorate.py`) entre los proyectores puros (§7) y el export/GUI:
> inyecta `label` legible + atributos de nodo (`year`/`is_seed`/`curation_status`/`degree_centrality`/
> `community`) en los nodos. `Networks.quick`/`build` devuelven artefactos **decorados** (cableado en
> `facade.py:_build_artifact`); los proyectores **siguen puros** (ADR 0014). Cierra el hueco de la
> Nota 09 B3 (redes con id crudo, ilegibles en Gephi/VOSviewer).
>
> **Sincronizado con la tabla de clusters — #31 (AS-BUILT, 2026-06-17):** se agregó la función pura
> **`cluster_table(table, artifact)`** (§7.2, `networks/clusters.py`, re-exportada desde
> `networks/__init__.py`): resume cada comunidad de una red de **paper** (coupling/cocitación) en una
> fila (tamaño, conteos de curación, rango de años, top autores/keywords). **`b2g build`** ahora escribe
> `<workspace>/networks/<kind>/clusters.csv` (listas con separador `|`) cuando la red tiene comunidades,
> y el envelope `--json` suma `clusters_csv` **condicional** por red (§9/§convenciones CLI).
>
> **Sincronizado con el workspace — ADR [0029](decisiones/0029-workspace-por-investigacion.md)
> (AS-BUILT, 2026-06-16):** la unidad de persistencia es un **workspace = carpeta** (`workspace.json`
> + `library.duckdb` + `networks/`/`snapshots/`/`exports/`). `--store` pasó a **opcional** y se agregó
> **`--workspace`** (ambos opcionales, mutuamente excluyentes) con **resolución ambiente** (flag > env
> `B2G_WORKSPACE` > walk-up del cwd). Suma el **14° subcomando `init`**. El `.duckdb` suelto sigue
> válido (workspace degenerado). Ver §convenciones CLI.
>
> **Sincronizado con la curación a escala — #22 + #26 (AS-BUILT, 2026-06-16):** suma el **15°
> subcomando `curate`** (curación en lote vía CSV), con dos modos mutuamente excluyentes —`--dump`
> (escribe `curacion.csv`) y `--from-csv` (aplica decisiones en lote, idempotente)—. **Curación
> transversal:** no transiciona el `CycleState`. Cierra el hueco de la
> [Nota 09](Notas/09-sesion-qa-prueba-ecologia-valoraciones.md) B4/B5/P1 (no había dump CSV ni
> reimport en lote: la curación a escala no era viable). Ver §convenciones CLI.
>
> **Sincronizado con la capa declarativa NetworkSpec — Hito 9 (AS-BUILT, 2026-06-17):** `NetworkSpec`
> (§10) gana el campo **`resolution: float = 1.0`** (resolución de Louvain, fuera del `corpus_hash` —
> seed intacto, R2) y **`extra="forbid"`** (campo desconocido en el YAML → error accionable). Nueva
> función **`load_specs(redes.yaml)`** (carga/valida una lista de specs; clave raíz `networks:`) y el
> **16° subcomando `b2g networks --spec`** (construye cada red con `Networks.build` y el helper
> compartido `_write_artifacts`; mismo envelope que `build`; **NO** transiciona el `CycleState` ni
> sella `.corpus_hash`). `pyyaml` pasó a dependencia del núcleo (import perezoso). Ver §10 +
> §convenciones CLI. **(Actualización #159, ADR 0038):** esta capa declarativa fue **absorbida por
> `b2g build --spec`** —que **sí** transiciona y sella (decisión D1)—; `networks` queda como alias en
> **deprecación** (cierra 0.11.0). Ver §`build`.
>
> **Sincronizado con la capa declarativa de ecuación + `restore` — #33 / Ciclo 9a (AS-BUILT, 2026-06-17):**
> dos cambios de la capa declarativa (ADR [0030](decisiones/0030-ecuacion-declarativa-corpus-ejemplo.md)).
> **(1)** `b2g seed` gana un 2º modo declarativo **`--spec equation.yaml`** (mutuamente excluyente con
> `--equation`): carga la ecuación de un YAML con el modelo **`EquationSpec`** + loader
> `load_equation_spec` (`sources/equation.py`, Pydantic `extra="forbid"`, mismo patrón de errores que
> `load_specs`; §2). Los campos `min_year`/`max_year` ya existen en el modelo **(en Ciclo 9a aún no
> filtraban; desde el Ciclo 10 SÍ filtran contra OpenAlex — ver el banner de Ciclo 10 abajo)**. **(2)** Nuevo
> **17° subcomando `b2g restore --from-corpus <parquet>`** (`cli/commands/restore.py`): rehidrata un
> corpus **ya curado** desde un parquet **sin red** (inverso de `snapshot`; lee con `CORPUS_SCHEMA`,
> `Corpus.from_arrow`, merge+persist), preserva la curación (`decision`/`curation_status`/`is_seed`) y
> transiciona el `CycleState` a **`FILTERED`** (reusa la transición permisiva `filter`, ADR 0016; deja
> correr `build`/`networks` sin re-forrajeo). **NO** existe `seed --from-corpus` (la rehidratación es
> `restore`). En Ciclo 9a `seed --from-bib` estaba diferido; el **Ciclo 10 lo construyó** (ver banner
> abajo). Ver §2 + §convenciones CLI. **(Actualización #163, ADR 0038):** este `restore` plano pasa a
> **`snapshot restore`** (noun-verb del grupo `snapshot`, que se vuelve grupo `{create, restore}`); el
> verbo suelto `restore` queda como **alias deprecado** (shim que delega, `command="restore"` por
> backward-compat; retiro en #165). La capacidad no cambia. Ver §`snapshot`.
>
> **Sincronizado con el corpus de ejemplo + gate R2 — #33 / Ciclo 9b (AS-BUILT, 2026-06-17):**
> se materializa la convención **`examples/`** (§convención `examples/`) y se construye el primer
> ejemplo, **`examples/valoraciones/`** (corpus curado congelado de 137 filas + `equation.yaml` de
> procedencia + `README.md` + script de regeneración), excepción acotada al `.gitignore` de datos
> de usuario. Es el **caso real reproducible sin red** del gate #33: se rehidrata con
> `b2g restore --from-corpus examples/valoraciones/corpus.parquet` → `build` → `networks`/`clusters`.
> Un **gate R2** (`tests/unit/test_example_r2_gate.py`, 7 tests) verifica `corpus_hash` estable +
> composición de comunidades Louvain estable entre corridas (cierra el agujero R2 de la
> [Nota 09](Notas/09-sesion-qa-prueba-ecologia-valoraciones.md)). **#33 cerrado / 9a+9b completos**.
> (En 9b, `seed --from-bib` y `examples/bibtex/` quedaban diferidos —issue #50—; el **Ciclo 10 los
> construyó**, ver banner abajo.) Ver
> [ADR 0030](decisiones/0030-ecuacion-declarativa-corpus-ejemplo.md) §AS-BUILT 9b.
>
> **Sincronizado con el segundo camino de seed (BibTeX) + filtro de año — Ciclo 10 (AS-BUILT, 2026-06-17,
> cierra issue #50):** des-diferido lo que 9a había postergado (ADR
> [0030](decisiones/0030-ecuacion-declarativa-corpus-ejemplo.md) §AS-BUILT Ciclo 10). **(1)** `b2g seed`
> pasa a **TRES modos** mutuamente excluyentes: `--equation` / `--spec` / **`--from-bib <archivo.bib>`**
> (siembra desde BibTeX local **sin red**, `run_seed_from_bib` → `BibtexSource.load`; `SEEDED`/reseed;
> exit 3 si falta `bibtexparser`; combinar `--from-bib` con flags OpenAlex → exit 1). **(2)**
> `--min-year`/`--max-year` **ahora filtran de verdad** contra OpenAlex
> (`from_publication_date`/`to_publication_date` en el `filter`; expuestos como flags en `--equation` y
> como campos del YAML en `--spec`, paridad 1:1). **(3)** Nuevo ejemplo **`examples/bibtex/`** (`sample.bib`
> + README con receta 100% CLI) que demuestra el camino BibTeX. Ver §2 + §convenciones CLI + §convención
> `examples/`.
>
> **Sincronizado con `examples/valoraciones/` rehecho CLI-puro — Ciclo B (AS-BUILT, 2026-06-17):**
> materializa el principio **CLI-puro** del PO (ADR
> [0030](decisiones/0030-ecuacion-declarativa-corpus-ejemplo.md) §AS-BUILT Ciclo B). `build_corpus.py`
> **eliminado**: el ejemplo se arma y reproduce **100% por CLI** (`seed --spec equation.yaml`
> `max_results 80` → `curate apply curacion.csv` 10 `accepted` → `enrich --max-citing 25` →
> `snapshot`). Corpus = **~80 filas** (70 `candidate` + 10 `accepted` enriquecidas), **co-citación
> presente** (rala) — antes 137 filas / co-citación vacía (9b). Nuevo artefacto congelado
> **`curacion.csv`** (receta determinista de curación). Gate R2 ajustado (piso `n>=50`,
> `test_cocitacion_con_datos` con 5 redes). **La procedencia de un ejemplo deja de ser un script y
> pasa a ser la receta CLI del README + `equation.yaml` + `curacion.csv`** (supersede la convención de
> 9b/§2.1). Ver §convención `examples/` (§2.1).
>
> **Sincronizado con los remanentes del modelo workspace — #32 (AS-BUILT, 2026-06-17):** cierra lo
> que el ADR [0029](decisiones/0029-workspace-por-investigacion.md) dejó "fuera de corte".
> **`b2g snapshot` y `b2g export`** se resuelven por ambiente: `--out-dir` pasó de obligatorio a
> **override OPCIONAL**; sin él, `snapshot` escribe en **`<workspace>/snapshots/`** y `export` en
> **`<workspace>/exports/`** (resolución vía `resolve_workspace`, igual que `build`). **`b2g status`** suma el campo aditivo
> **`data["networks_cache_stale"]: bool`** + un `warnings` accionable cuando el `networks/.corpus_hash`
> sellado **no coincide** con el `corpus_hash` del corpus vivo (aviso "ejecutá `b2g build`"; **NO**
> regenera — invalidación por hash, no build-system, ADR 0029). `schema="1"` intacto. `Workspace` ganó
> `read_networks_corpus_hash()` e `is_networks_cache_stale(live_hash)` (los accessors
> `snapshots_dir`/`exports_dir`/`networks_dir` ya existían). Ver §convenciones CLI.
>
> **Sincronizado con la eliminación de `--store` — [#75](https://github.com/complexluise/bib2graph/issues/75) (BREAKING, 2026-06-17):**
> la opción global **`--store` se ELIMINA por completo** del CLI (ya no registrada en Click; pasarla
> da el error estándar `No such option: --store`). El **modo degenerado** (`.duckdb` suelto sin
> `workspace.json`) **deja de existir**: la única unidad canónica es la carpeta con `workspace.json`,
> y un `.duckdb` legacy se adopta con **`b2g init .`**. La resolución ambiente pierde la rama
> `--store`: `--workspace` > `B2G_WORKSPACE` > walk-up del cwd. Ver §convenciones CLI y ADR 0029
> (enmienda 2026-06-17).
>
> **Sincronizado con el preprocesamiento automático en la ingesta — #88 (AS-BUILT, 2026-06-18, ADR
> [0031](decisiones/0031-preprocesamiento-automatico-en-ingesta.md)):** `seed`/`seed_from_bib`/`chain`/
> `restore` aplican **`normalize` + dedup fuzzy automáticamente** sobre el corpus completo mergeado
> (helper `cli/_ingest.py::normalize_and_dedup`), así que **dejan el corpus siempre normalizado y
> deduplicado cross-biblioteca** (§6 + §11). Persisten con **`persist_replace`** (§4.1), no upsert.
> Nuevo **18° subcomando `b2g thesaurus --from <archivo>`** (único paso explícito del preproc,
> transversal al FSM). **`rapidfuzz` pasa al núcleo; el extra `[dedup]` se elimina.** `build`/`networks`
> siguen puros (el corpus ya entra deduplicado). Ver §6, §11, §4.1 y el listado de subcomandos.
>
> **Sincronizado con la capa de servicios neutral — Hito G1 del MVP GUI (AS-BUILT, 2026-06-18, ADR
> [0028](decisiones/0028-arquitectura-gui-api-capa-servicios.md)):** se materializa la **capa de
> servicios neutral `src/bib2graph/service/`** (§0). G1 **sube EL CONTRATO** desde `cli/`: el envelope
> versionado (`build_envelope`/`ENVELOPE_SCHEMA_VERSION`), la jerarquía de errores tipados (`B2GError`
> + subclases) y el **mapeo puro error→código** (`code_for`) ahora viven en `service/` (agnóstico de
> transporte: sin `print`/`sys.exit`/Click/FastAPI). `cli/_envelope.py` y `cli/_errors.py` pasan a
> **re-exportar** ese contrato y conservan solo el I/O del adaptador (`emit`/`emit_human`/`handle_errors`).
> **El contrato externo del CLI no cambia** (envelope `schema="1"`, exit codes 0–5, ADR 0021): los
> imports `from bib2graph.cli._envelope import build_envelope` / `from bib2graph.cli._errors import
> B2GError, …` resuelven a los **mismos objetos**. Es la primera mitad del ports & adapters del ADR 0028
> (el resto —`api/`, `b2g gui`, `frontend/`, lecturas `get_scent`/`get_network`/`search`— sigue siendo
> TARGET, no construido). Ver §0.
>
> **Sincronizado con las 6 lecturas de servicio — Hito G2 del MVP GUI (AS-BUILT, 2026-06-18, ADR
> [0028](decisiones/0028-arquitectura-gui-api-capa-servicios.md)):** `src/bib2graph/service/reads.py`
> suma las **6 lecturas read-only** que la SPA necesita y el CLI nunca expuso —`get_workspace`,
> `list_rounds`, `get_paper`, `get_scent`, `get_network`, `compare_rounds`— cada una sobre un
> `Workspace` resuelto, devolviendo `dict`/`list[dict]` serializable o lanzando `B2GError` (sin red, sin
> mutación, sin transición de ciclo). **El contrato externo del CLI no cambia** (`test_cli.py` intacto),
> así que **no requiere ADR nuevo**. Resuelve las bifurcaciones del encuadre como recomendado: ronda =
> snapshot sellado, scent = score de acoplamiento + vecinos, `get_network` = red de la ronda viva
> (cache por snapshot y `mutated_hubs` diferidos). El resto de la epic GUI (API/`b2g gui`/`frontend/`,
> G3–G5) **sigue TARGET**. Ver §0.1.
>
> **Sincronizado con la API local + `b2g gui` — Hito G3 del MVP GUI (AS-BUILT, 2026-06-18, ADR
> [0028](decisiones/0028-arquitectura-gui-api-capa-servicios.md)):** se construye la **API local
> FastAPI** (`src/bib2graph/api/`, §0.2): adaptador **delgado** sobre `service/` que expone **7
> endpoints** (6 lecturas de §0.1 + 1 escritura de curación), con **token Bearer efímero** (sin/
> inválido → **401**) y el **mapeo código→HTTP** del ADR 0028 §7 (`0`→200, `1`→400, `2`→422, `3`→501,
> `4`→502, `5`→**409**; excepción inesperada → **500** `INTERNAL_ERROR`). Reusa `service.build_envelope`
> y `service.code_for` (no reimplementa el contrato; el envelope `schema="1"` viaja íntegro en el body).
> El paquete `api/` **no importa de `cli/`**; el núcleo **no importa `fastapi`** (import perezoso). Sube
> a `service/curate.py` la **orquestación de accept/reject** (`accept_papers`/`reject_papers`/
> `curate_paper`, `decided_at` inyectado en la frontera): `run_accept`/`run_reject` del CLI quedan como
> **shims que delegan** (firma intacta). Entra el **19º subcomando `b2g gui`** (extra `[gui]` = `fastapi`
> + `uvicorn`; exit 3 si falta; bind `127.0.0.1`; sirve la SPA buildeada si existe — el frontend G4 aún
> no). **El contrato externo del CLI no cambia** (`test_cli.py` intacto) — no requiere ADR nuevo. La SPA
> (`frontend/`, G4) y el empaquetado (G5) **siguen TARGET**. Ver §0.2.
>
> **Sincronizado con la SPA `frontend/` + wiring del token — Hito G4 del MVP GUI (AS-BUILT, 2026-06-18,
> ADR [0028](decisiones/0028-arquitectura-gui-api-capa-servicios.md)):** se construye la **SPA**
> (`frontend/`, React 18 + Vite + TS + Cytoscape/fcose + Zustand + Tailwind + TanStack Query, **pnpm**),
> que consume los **7 endpoints reales** de §0.2 (cliente que des-envuelve el envelope `schema="1"`,
> ramea por `error.code` **string** y manda `Authorization: Bearer <token>`). **Cambia el wiring del
> token de `b2g gui`** (§0.2 abajo): la SPA necesita el token para autenticarse, así que `b2g gui` ya
> **no solo lo imprime** —ahora lo **inyecta en el `index.html` servido** (`cli/commands/gui.py::
> _make_index_response` reemplaza el placeholder `__B2G_TOKEN__`; ruta **`GET /`** sirve el HTML con
> token **sin** exigir Bearer, y `StaticFiles` —`html=False`— sirve los assets); el frontend lo lee de
> `window.__B2G_TOKEN__`. El contrato HTTP de los 7 endpoints (§0.2) **no cambia**. Solo quedaba
> TARGET el empaquetado (G5) —ya AS-BUILT, banner siguiente—. Ver §0.2.
>
> **Sincronizado con el empaquetado — Hito G5 del MVP GUI (AS-BUILT, 2026-06-18, ADR
> [0028](decisiones/0028-arquitectura-gui-api-capa-servicios.md)):** el wheel **vendorea el build del
> frontend** (`src/bib2graph/gui/static/`, gitignored) vía `[tool.hatch.build.targets.wheel.force-include]`
> de hatchling → `b2g gui` funciona **sin Node** desde el wheel; `ci.yml` suma el job `frontend`
> (lint/test/build JS, corre siempre) y `publish-testpypi.yml` hace `pnpm build` antes del `uv build`
> (`release-please.yml` no se tocó). **No cambia ningún contrato** (CLI ni HTTP) — no requiere ADR nuevo.
> **Con G5, los 5 hitos G1–G5 del MVP GUI están AS-BUILT**; lo único pendiente es el **gate #34**
> (validación con un tercero, criterio de aceptación de producto, **no** es construcción).
>
> **Sincronizado con la resolución DOI→`source_id` (flujo BibTeX e2e) — issues #110/#112 (AS-BUILT,
> ADR [0035](decisiones/0035-ingesta-multipuerta-resolucion-doi.md)):** se cierra el **GAP-1** del flujo
> BibTeX: los papers sembrados con `seed --from-bib` traen `doi` pero **no `source_id`**, y sin
> `source_id` los comandos `enrich`/`chain` devuelven **0**. Suma el **20° subcomando `b2g resolve`**
> (`cli/commands/resolve.py` → `service/resolve.py::resolve_dois`): filtra papers con `doi != NULL`
> **AND** `source_id IS NULL`, consulta OpenAlex (batcheado, `fetch_dois_to_openalex_ids`) y puebla
> `source_id`; **idempotente** (los que ya tienen `source_id` no se tocan) y **NO transiciona el
> `CycleState`** (ortogonal al lazo, igual que `enrich`). Además, **`seed --from-bib` gana el flag
> `--resolve`** que encadena la resolución en el mismo comando reusando el store ya abierto
> (`service/resolve.py::_resolve_dois_on_store`, **sin reabrir el `.duckdb`** — el reopen en el mismo
> proceso corrompía las UDFs de DuckDB → segfault exit 139, #110/#93). **GAP-2 / #112:** `--email`
> pasa a estar **permitido con `--from-bib`** cuando se usa junto a `--resolve` (se propaga al polite
> pool en la resolución). Solo `source_id` (no `external_ids`, diferido #120). Ver §2 + §convenciones
> CLI.
>
> **Sincronizado con la superficie CLI 0.10.0 — ADR [0037](decisiones/0037-superficie-cli-10-verbos-ciclo.md)
> + [0038](decisiones/0038-destino-verbos-huerfanos-0037.md) (AS-BUILT 2026-06-28, epic #167):** la
> superficie por acreción (~20 subcomandos) se **consolidó en 10 verbos del ciclo + 3 grupos noun-verb
> (`read`/`curate`/`snapshot`) + `gui` como excepción**, con una **ventana de deprecación** de 9 aliases
> (retiro 0.11.0). Cierres de este consolidado docs (#166): **`monitor` → `chain --since`** (#158:
> forrajeo incremental, fecha ISO o atajo `90d/6m/1y`, fuerza forward, transiciona a **`MONITORED`** —no
> existe `CHAINED`); **`enrich` absorbido** (#162: refs→DOI en `chain`, co-citación en `build` cuando hay
> aceptadas → `build` deja de ser estrictamente "puro/sin red"; bloque `data["enrichment"]`);
> **`thesaurus` retirado como verbo** (#164: la capacidad es `build --thesaurus`); **avisos de
> deprecación** a stderr + `warnings[]` (#165). El contrato de salida (envelope `schema="1"`, exit codes,
> FSM) **no cambia** (reorganización semántica). Ver §convenciones CLI (header "Superficie 0.10.0",
> §`chain`, §`build`, §`enrich`, §Avisos de deprecación). *(Banner de cierre; las notas AS-BUILT de
> arriba describen la acreción previa y quedan como historia inmutable.)*

## Convenciones

- Tipado estático en todas las firmas públicas. Las costuras se definen como `Protocol` o ABC.
- **Funciones puras** en el núcleo (proyectores, analizadores, preprocesador): sin red, sin
  estado global. El estado (biblioteca viva + `LoopState`) vive en el backend persistente
  (`DuckDBBackend`), no en la sesión.
- Estado de implementación: **`v1`** vs **`futuro`** (declarado, NO implementado — marcado como
  tal, no falsamente prometido; lección 5 de v0).

### Convenciones del CLI agente-native (ADR 0010 / 0021; construido en el Hito 6)

El CLI `b2g` (paquete `bib2graph.cli`, entry point `b2g = "bib2graph.cli:main"`) está
**construido** con el contrato del ADR [0021](decisiones/0021-cli-agente-native-contrato.md). Cada
subcomando lleva `--json` (envelope estable/versionado; también activable por entorno con
**`B2G_JSON=1`**, ver §Envelope JSON) y exit codes (`0` éxito · `1` uso · `2`
datos · `3` dependencia · `4` red · `5` store/snapshot corrupto o bloqueado). **Sin estado entre
invocaciones:** el estado vive en el `library.duckdb` del **workspace** (opción global **opcional**
`--workspace`; `--store` fue eliminada en [#75](https://github.com/complexluise/bib2graph/issues/75),
ver abajo).

**Superficie 0.10.0 — 10 verbos del ciclo + 3 grupos noun-verb + `gui` (excepción) + 9 aliases
deprecados** (AS-BUILT, ADR [0037](decisiones/0037-superficie-cli-10-verbos-ciclo.md) /
[0038](decisiones/0038-destino-verbos-huerfanos-0037.md)). La superficie por acreción del 0021 (que
llegó a ~20 subcomandos) se **consolidó** en una superficie que mapea 1:1 el ciclo de investigación
(*más es menos*). El conteo es **verificable contra `b2g --help`**:

- **10 verbos del ciclo:** `init`, `seed`, `chain`, `curate` (grupo), `build`, `read` (grupo),
  `export`, `snapshot` (grupo), `status`, `validate`. *(El par EXPORT/SNAPSHOT cuenta como uno; ver
  ADR 0037 §"Los 10 verbos".)*
- **3 grupos noun-verb:** **`read {list,stats,show,top}`** (#156/#157), **`curate
  {dump,apply,accept,reject,filter}`** (#155), **`snapshot {create,restore}`** (#163, ADR 0038).
- **`gui`** — fuera del set de 10 por diseño (excepción explícita, gobernada por ADR 0027/0028,
  gateada por #34; no es un paso del ciclo agents-first).
- **9 aliases deprecados** (siguen vivos con aviso a stderr, se eliminan en **0.11.0** — ADR 0038 P1):
  `accept`, `reject`, `filter`, `inspect`, `monitor`, `networks`, `enrich`, `restore`, `resolve`. Más el
  entry-point `bib2graph`→`b2g` y la opción `build --corpus-scope`→`build --scope`. Ver §Avisos de
  deprecación. **`thesaurus` NO es alias: se retiró por completo** (su capacidad es `build --thesaurus`,
  #164).

> **Historia de la acreción (contexto, no superficie objetivo):** el 0021 listaba 9 subcomandos y
> dejaba `accept`/`reject` como "solo programático"; luego crecieron `monitor` (cleanup pre-v0.3),
> `enrich` (Ciclo 8a, ADR 0025), `init` (workspace, ADR 0029), `curate` (#22+#26), `networks` (Hito 9),
> `restore` (Ciclo 9a, ADR 0030), `thesaurus` (#88, ADR 0031), `gui` (Hito G3, ADR 0028) y `resolve`
> (#110/#112, ADR 0035). Los ADR 0037/0038 los reorganizaron a la superficie de arriba. Las secciones
> por-comando de abajo describen cada verbo/grupo **en su forma 0.10.0**:

- `seed`, `chain`, **`filter`** (filtros PRISMA deterministas: año/tipo/idioma/citas **con conteo
  en cada paso**), `build`, `export`, `snapshot`, **`status`** (expone el ciclo: estado actual,
  transiciones disponibles y conteos por `curation_status`). **AS-BUILT R3 (2026-06-16):** el ciclo
  es el FSM cíclico `SEEDED/FORAGED/FILTERED/BUILT/MONITORED` (dominio en `bib2graph.cycle`) con
  **`reseed`**/contador de ronda; `status` **muestra `accept`/`reject` como acción siempre-disponible**
  (`curation_available`, curación transversal) + la **ronda** (`round`), campos aditivos que mantienen
  `schema="1"`. **AS-BUILT workspace (ADR 0029):** `status` suma el campo aditivo
  `workspace: {root, source}` (la raíz resuelta y de dónde salió — flag/env/cwd); `schema="1"`
  intacto. **AS-BUILT #32 (2026-06-17):** suma también el campo aditivo `networks_cache_stale: bool`
  (+ `warnings` accionable cuando la cache de `networks/` quedó obsoleta respecto al corpus vivo;
  avisa, NO regenera — ver §`build`/`export`/`snapshot` abajo). **AS-BUILT #54 (2026-06-17):** `status`
  suma el campo aditivo `referenced_not_fetched` (nº de IDs que el backward chaining observó sin
  materializar — tabla `referenced_but_not_fetched`, §4/§5; `schema="1"` intacto), y `b2g chain` suma
  `observed_refs_count` a su envelope JSON. **`read {list,stats,show,top}`** (grupo noun-verb,
  #156/#157 / ADR 0037 §b — ver §Grupo `read` abajo), `inspect` (**en deprecación**, #165: lo absorben `read show`
  para papers y `status` para manifest/FSM; **sigue vivo** hasta cerrarse #165), `validate`.
- **`seed`** (ADR [0030](decisiones/0030-ecuacion-declarativa-corpus-ejemplo.md), Ciclo 9a + Ciclo
  10 AS-BUILT 2026-06-17): tiene **exactamente TRES modos mutuamente excluyentes** (exactamente uno
  requerido; pasar más de uno o ninguno → error de uso, exit 1):
  - **`--equation '<texto>'`** — ecuación cruda en la línea de comandos (modo OpenAlex directo, con red).
  - **`--spec equation.yaml`** — la misma siembra OpenAlex parametrizada por un YAML versionable
    (clave raíz `equation:`; modelo `EquationSpec`, §2). Equivale a `--equation` + flags (mismo
    `executed_query`).
  - **`--from-bib <archivo.bib>`** — siembra desde un archivo BibTeX local, **sin red** (segundo
    camino de seed, cierra issue #50). Usa `BibtexSource.load` (`run_seed_from_bib` en
    `cli/commands/seed.py`); marca los papers `is_seed=True` / `curation_status='candidate'` y
    transiciona a `SEEDED` (o reseed → ronda++ si ya había estado, igual que los otros modos). El
    envelope `--json` lleva `{papers_added, total_papers, round, reseeded}` — **sin** `executed_query`
    ni `translation_report` (no aplican a BibTeX). Si falta `bibtexparser` (extra `[bibtex]`) →
    **`DependencyError`, exit 3** (patrón `[dedup]`); archivo inexistente / `.bib` mal formado →
    `DataError`, exit 2.

    **`--resolve` (solo con `--from-bib`; issues #110/#112, ADR
    [0035](decisiones/0035-ingesta-multipuerta-resolucion-doi.md)):** tras cargar el `.bib`, **encadena la
    resolución DOI→`source_id`** en el mismo comando (equivale a correr `b2g resolve` a continuación,
    abajo). Cierra el **GAP-1** del flujo BibTeX e2e: sin `source_id`, `enrich`/`chain` darían 0.
    Reusa el **store ya abierto** por seed (`service/resolve.py::_resolve_dois_on_store`) en vez de
    reabrir el `.duckdb`: el reopen en el mismo proceso corrompía las UDFs de DuckDB → segfault
    (exit 139, #110/#93). Cuando se pasa `--resolve`, el envelope `--json` **suma** `data["resolve"] =
    {resolved, total_with_doi, already_resolved, total_papers}` a las métricas de seed. **`--email`
    pasa a estar PERMITIDO con `--from-bib` cuando está `--resolve`** (se propaga al polite pool en la
    resolución; cierra GAP-2 / #112). **Reglas de uso (exit 1):** `--email` + `--from-bib` **sin**
    `--resolve` → error (`--email` solo sirve si hay resolución); `--resolve` **sin** `--from-bib` →
    error (sugiere `b2g resolve` para un corpus existente).

  **No existe `seed --from-corpus`** (la rehidratación de un parquet curado es `restore`, abajo).
  Flags ergonómicos de OpenAlex (#14 + #30, **solo con `--equation`/`--spec`**): **`--max-results INT`**
  propaga a `OpenAlexSource(max_results=...)` —sin flag, el default del source = 200— para exploración
  con muestras chicas (Nota 09 B1); **`--exclude TEXT`** (repetible) son **negaciones quirúrgicas**:
  cada término se inyecta **dentro** de la única expresión de búsqueda como
  `title_and_abstract.search:((query) AND NOT "<término>")` (el campo **no se repite**; el `AND NOT`
  va adentro del paréntesis) y queda en el
  `translation_report` del `SeedResult` (ejercicio consciente, query visible); ignorado con `--native`
  (query cruda); **`--min-year INT`/`--max-year INT`** (Ciclo 10) **filtran de verdad** contra OpenAlex
  agregando `from_publication_date:<min_year>-01-01` y/o `to_publication_date:<max_year>-12-31` como
  predicado de filtro **separado por coma, fuera** de la expresión `search` (sintaxis idiomática de
  rango; reportado en el `translation_report`).
  Con `--spec`, todos estos parámetros vienen del YAML (paridad 1:1 flag ⇄ campo). **Combinar los flags
  de OpenAlex `--exclude`/`--max-results`/`--native`/`--min-year`/`--max-year` con `--from-bib` → error
  de uso, exit 1** (falla fuerte, no ignora en silencio). **`--email` es la excepción** (#112): se
  permite con `--from-bib` cuando va junto a `--resolve` (ver `--resolve` arriba); `--email` +
  `--from-bib` sin `--resolve` → error. En modo `--native`, `--min-year`/`--max-year` no se aplican
  (nativo = sin traducción).
- **`snapshot restore`** (ADR [0030](decisiones/0030-ecuacion-declarativa-corpus-ejemplo.md), Ciclo 9a;
  **AS-BUILT #163, ADR 0038**: ex verbo plano `restore`, ahora **noun-verb del grupo `snapshot`** —ver
  §`snapshot`—; el verbo suelto `restore` **sigue vivo como alias deprecado**, shim que delega con
  `command="restore"` por backward-compat, retiro en #165): **rehidrata un corpus ya curado desde un
  parquet, SIN red** — inverso de `snapshot create`,
  como `load` es a `dump`. **`--from-corpus <parquet>`** (requerido) lee el parquet con el schema
  canónico (`CORPUS_SCHEMA`), lo hidrata con `Corpus.from_arrow`, hace merge con el corpus existente y
  persiste; **cero llamadas a `OpenAlexSource`, cero red**. **Preserva la curación** del parquet
  (`decision`/`curation_status`/`is_seed`: el merge respeta el `curation_status` más reciente, D3).
  **Transiciona el `CycleState` a `FILTERED`** (el corpus ya pasó curación ⇒ `build`/`networks` corren
  sin re-forrajeo ni re-filtrado; reusa la transición permisiva `filter` de la FSM, ADR 0016 — válida
  desde cualquier estado, incluido un store vacío `None`). La ronda se normaliza con
  `max(loop_round(), 1)` (evita ronda 0 en bases legacy pre-R3). `data` = `{papers_loaded,
  total_papers, state, round}`; `--json` con `schema="1"`. Errores accionables: parquet inexistente o
  con schema no canónico → `DataError` (exit 2). **No** es semilla: es restaurar estado terminado (por
  eso vive aparte de `seed`). El caso real reproducible que rehidrata `restore` es el corpus
  congelado bajo **`examples/valoraciones/`** (ver §convención `examples/` abajo).
- **`accept`** / **`reject`** (decisión del PO, ADR 0021 §A): curación programática por `--ids`,
  ahora **subcomandos CLI de primera clase** (no solo API de librería), para que un agente cure la
  biblioteca viva por subprocess (historia C4). **AS-BUILT #22/#26:** la curación **a escala** ya no es
  uno-a-uno —el subcomando **`curate`** (abajo) hace dump/import CSV en lote—; la **curación
  interactiva rica y la GUI siguen siendo futuro**. Ver [`ROADMAP.md`](ROADMAP/README.md) Hito 6.
- **`chain`** (paso CHAIN del ciclo): expande el corpus con candidatos rankeados por *information
  scent* (forward/backward chaining batcheado, §5). **`--direction [backward|forward|both]`** (default
  `both`), **`--depth`** (solo 1), **`--max-candidates`**, **`--max-citing`** (presupuesto de citantes
  por semilla en forward, default 50), **`--email`** (polite pool), **`--preview`** (dry-run: estima el
  crecimiento **sin** fetchear ni transicionar — backward exacto desde `references_id`; forward exacto
  solo si el corpus tiene `cited_by_id` poblado, si no avisa que requiere fetch). En el camino normal
  **transiciona a `FORAGED`** y corre **automáticamente la pasada de enriquecimiento refs→DOI** (#162,
  ver §`enrich`): el envelope `--json` suma el bloque aditivo `data["enrichment"]`. `data` =
  `{candidates_found, new_candidates, total_papers, direction, depth, ranking_preview,
  observed_refs_count, loop_state, round, enrichment}`.

  **`--since` — forrajeo incremental (#158, ADR 0037 §c; absorbe `monitor`):** trae **solo citantes
  publicados desde** una fecha. Acepta **fecha ISO `YYYY-MM-DD`** o **atajo relativo** (`90d` = 90 días,
  `6m` = 6 meses, `1y` = 1 año), parseado en la frontera CLI (`cli/_options.py::parse_since`, reloj
  R2/ADR 0017). **`--since` fuerza forward** y **transiciona a `MONITORED`** (no a `FORAGED`): es el paso
  MONITOR (Ellis) reexpresado como modo de `chain`. Reglas de dirección: **`backward` + `--since` →
  `UsageError` (exit 1)** (no tiene sentido); **`both` + `--since` → la ventana aplica solo al tramo
  forward** (`effective_direction=forward`). Guarda de portada (como el ex `monitor`): sin corpus/estado
  previo o corpus vacío → `DataError` (exit 2), sugiere `b2g seed`. **`b2g monitor` queda como alias
  deprecado** (retiro 0.11.0) que delega en `chain` con la acción FSM `monitor`. **AS-BUILT #158:** tras
  el merge, `chain --since` **deduplica** el corpus (ingesta normalizada, ADR 0031). **Corrección de
  drift:** `chain` (normal) transiciona a **`FORAGED`**, y `chain --since`/`monitor` a **`MONITORED`** —
  **no existe** ningún estado `CHAINED`.
- **`enrich`** (Hito 8 = Ciclos 8a + 8b, ADR
  [0025](decisiones/0025-enricher-cocitacion-openalex.md); **ABSORBIDO en `chain`/`build`** — #162,
  ADR 0038): el `OpenAlexEnricher` (§3) **deja de ser verbo propio**. Sus dos pasadas corren ahora
  automáticas en los pasos del ciclo, vía el helper único `cli/_enrich.py::enrich_corpus(corpus,
  source, *, max_citing, pass_name)`:
  - **Pasada 8a (`refs_doi`)** — resuelve `references_id`→`references_doi` (batching por OR): corre
    **automática en `chain`** (forrajeo).
  - **Pasada 8b (`cited_by`)** — co-citación: trae los citantes de las **semillas aceptadas** y
    mergea sus `openalex_id` en `cited_by_id` (unión idempotente; no crece el corpus): corre
    **automática en `build`** cuando hay semillas aceptadas (**no-op de red, cero requests, si no las
    hay**). Por eso **`build` ya NO es estrictamente "puro/sin red"** (ADR 0025 enmendado, #162): hace
    requests `cited_by` en build-time porque la co-citación necesita las aceptadas, recién disponibles
    tras curar.

  Ambos comandos suman el bloque **aditivo `data["enrichment"]`** al `--json` (`refs_resolved`/
  `refs_total_unique` y/o `citing_new`/`citing_targets`, solo las claves de las pasadas ejecutadas).
  `build` suma además **`--email`** y **`--max-citing`** (tope de citantes por semilla en la pasada
  `cited_by`). **`b2g enrich` queda como alias deprecado** (retiro 0.11.0, ver §Avisos de deprecación)
  que corre ambas pasadas (`pass_name="both"`) y **NO transiciona el `CycleState`**.
- **`thesaurus` — RETIRADO como verbo (#164, ADR 0038).** El subcomando `b2g thesaurus` **ya no
  existe** (no queda ni como alias; la issue [#149](https://github.com/complexluise/bib2graph/issues/149)
  constató que no implementaba un tesauro como tal). La capacidad —consolidación cross-lingüe de
  keywords (ADR [0011](decisiones/0011-thesaurus-multilingue.md), `Preprocessor.apply_thesaurus`, §6)—
  **se preserva como flag `b2g build --thesaurus <archivo>`** (JSON formato ADR 0011): `build` aplica el
  thesaurus sobre `keywords_id` **antes** de scopear/proyectar, persiste con **`persist_replace`** (§4.1)
  y suma el bloque aditivo `data["thesaurus"] = {keywords_mapped, keywords_total, aliases_loaded,
  applied_at}`. (Coherente con el ADR 0031 enmendado: `normalize`+dedup siguen automáticos en la
  ingesta; lo que cae es el *verbo* explícito.)
- **`init`** (ADR [0029](decisiones/0029-workspace-por-investigacion.md)): **scaffold de un
  workspace**. `b2g init <name>` crea `<name>/` con `workspace.json` + `library.duckdb` +
  `networks/`/`snapshots/`/`exports/`; **`b2g init .`** inicializa el cwd. Si la carpeta ya es un
  workspace → error (`WorkspaceExistsError`). **NO transiciona** el `CycleState`. `data` =
  `{root, name, ...}`; `--json` con `schema="1"`.
- **`curate`** (#22 + #26 origen; **grupo noun-verb AS-BUILT #155**, ADR 0037 (b)): **grupo de
  curación** con cinco subcomandos —`{dump, apply, accept, reject, filter}`—. Reorganiza la superficie
  de curación a `b2g curate <verbo>` (decisión (b) del ADR
  [0037](decisiones/0037-superficie-cli-10-verbos-ciclo.md), 2° grupo noun-verb tras `read`).
  **`b2g curate` sin subcomando → help + exit 0.**
  **BREAKING (autorizado por ADR 0037 (b), sin alias):** la **forma-flag** `curate --dump` /
  `curate --from-csv` fue **ELIMINADA**; `curate --all` también (usar `--scope all`). La lógica vive en
  `service/curate.py` (fuente única, ver §0); el CLI solo parsea y delega.

  **La transición del FSM la define el VERBO, no el grupo** (precedente D1 de #159): **`curate filter`
  transiciona a `FILTERED`**; `dump`/`apply`/`accept`/`reject` son **transversales** (NO transicionan,
  disponibles en cualquier estado del lazo). Esto matiza la regla previa "curate es transversal" —cierta
  como bloque, ahora por-verbo (ver enmienda en el ADR 0037).

  - **`curate dump`** (= ex `--dump`) escribe un CSV revisable offline (Excel/Calc). Default
    `<workspace>/exports/curacion.csv`; **`--out`** lo override. **`--scope [candidates|seeds|all]`**
    (default `candidates`) elige qué papers volcar: `candidates` = forrajeados a revisar
    (`curation_status == 'candidate'` **AND** `is_seed == False`, **excluye semillas** —arregla #72,
    donde el dump arrastraba seeds); `seeds` = semillas originales (`is_seed == True`); `all` = todo el
    corpus. **`--all` ELIMINADO** (usar `--scope all`). Sin candidatos (scope `candidates`/`seeds`
    vacío) → error accionable que sugiere `--scope all` o `b2g chain`. Columnas (16, orden estable):
    `id, source_id, title, year, authors, venue, doi, keywords, cited_by_count, references_count,
    is_seed, openalex_url, scent_score, cluster, decision, note`. **Todas read-only salvo `decision` y
    `note`** (las editables por el humano). `venue` sale de `source`; `keywords` se une con `" | "`
    (igual que `authors`); `openalex_url` es una **columna derivada OpenAlex-específica**: se construye
    `https://openalex.org/<source_id>` solo cuando el `source_id` parece un ID de OpenAlex (`W…`), si no
    queda vacía. **`cited_by_count`/`references_count` hoy salen vacías**: no existen como escalares en
    el schema canónico de 23 columnas, así que la columna queda como placeholder para llenado manual
    (limitación conocida, no falla). `decision` refleja el `curation_status` actual
    (`candidate`→`undecided`, `accepted`→`accepted`, `rejected`→`rejected`). `data` =
    `{csv_path, papers_exported, columns}`. Transversal (NO transiciona).
  - **`curate apply <csv>`** (= ex `--from-csv`) aplica las decisiones en lote y persiste:
    `accepted`→`accept`, `rejected`→`reject`, `undecided`→no-op (case-insensitive). **Idempotente**
    (reimportar el mismo CSV = mismo `corpus_hash`; el reloj `decided_at` se inyecta en la **frontera
    CLI**, R2/ADR 0017, fuera de la identidad). **Validación accionable** (exit 2): CSV sin
    `id`/`decision` → error que nombra las columnas requeridas; `decision` con un valor fuera de
    `{accepted, rejected, undecided}` → error con los valores válidos. **IDs huérfanos** (en el CSV pero
    no en el corpus) **NO se aplican** y se reportan en `not_found_count` + aviso humano (cierra el no-op
    silencioso). `data` = `{accepted_count, rejected_count, skipped_count, not_found_count, total_rows}`
    —los `*_count` de accept/reject cuentan papers **efectivamente** encontrados y marcados, no filas del
    CSV. Transversal (NO transiciona).
  - **`curate accept --ids ... [--by NOMBRE]`** / **`curate reject --ids ... [--by NOMBRE]`**: aceptan
    o rechazan papers por ID (curación uno-a-uno o en lote por flags). Comparten la lógica de servicio
    (`accept_papers`/`reject_papers`) con los verbos sueltos `accept`/`reject` (que quedan INTACTOS como
    alias deprecados, retiro 0.11.0 — ver §verbos huérfanos y ADR 0038). Transversales (NO transicionan).
  - **`curate filter`** (flags PRISMA `--year-gte`/`--year-lte`, `--language`, `--type`,
    `--min-citations`): aplica criterios de inclusión/exclusión MARCANDO `rejected` (no borra; conserva
    la trazabilidad PRISMA) con conteo por paso. **Transiciona el `CycleState` a `FILTERED`** (único
    verbo del grupo que transiciona). Comparte `filter_corpus` con el verbo suelto `filter` (alias
    deprecado, retiro 0.11.0).
  - **`note` es advisory:** hace round-trip en `dump` pero **se ignora en `apply`** (`ProvenanceEvent`
    no tiene campo de anotación; persistirla → ADR futuro). **`scent_score` best-effort** (vacío hasta
    que el Forager guarde `scent` en provenance) y **`cluster` siempre vacío** (integración con redes
    diferida). `--json` con `schema="1"` en todos los subcomandos.
- **`networks`** (Hito 9, **EN DEPRECACIÓN — absorbido por `build --spec`**, ADR 0037 (a) / 0038,
  ventana cierra 0.11.0): **capa declarativa** — construye redes desde un YAML versionable.
  **`b2g networks --spec <redes.yaml>`** carga la lista de specs con `load_specs` (§10;
  clave raíz `networks:`), construye cada red con `Networks.build` y escribe artefactos con el helper
  compartido **`_write_artifacts`** (extraído de `build.py`): mismos GraphML + `metrics.json` +
  `clusters.csv` que `build`, en `<out-dir>/<kind>/`. La carga YAML + proyección la comparte con
  `build --spec` vía **`_build_from_spec_file`** (fuente única; frontera con #165). **`--out-dir`**
  override (default `<workspace>/networks/`); resolución de store/workspace idéntica a `build`
  (`resolve_workspace`). `--json` con `schema="1"`, mismo formato que `build` (lista de redes en
  `data["networks"]`, con `clusters_csv` condicional). **Diferencia clave con `build --spec`:**
  `networks` es **ad-hoc transversal al lazo** y **NO** transiciona el `CycleState` ni sella
  `networks/.corpus_hash` (mismo criterio que `curate`); `build --spec` **sí** lo hace (decisión D1,
  ADR 0038 — ver §`build`). **Recomendado:** usá `build --spec` (paso BUILD pleno). Errores
  accionables: YAML malformado / spec inválida → `DataError` (exit 2); falta `python-louvain` →
  `DependencyError` (exit 3).
- **`gui`** (Hito G3 del MVP GUI, AS-BUILT 2026-06-18, ADR
  [0028](decisiones/0028-arquitectura-gui-api-capa-servicios.md), 19° subcomando): **levanta la API
  local FastAPI** (§0.2) con `uvicorn` y sirve la SPA buildeada de `gui/static/` si existe (AS-BUILT G4;
  el build local lo genera, el wheel lo incluirá en G5). Genera un **token Bearer efímero**
  (`secrets.token_urlsafe(32)`), lo **inyecta en el `index.html` servido** (ruta `GET /`, placeholder
  `__B2G_TOKEN__` → `window.__B2G_TOKEN__`; ver §0.2 "Wiring del token") e imprime URL + token al
  arrancar. Flags: **`--host`** (default `127.0.0.1`, local-first — no expone red), **`--port`** (default
  `8765`), **`--no-browser`** (no abre el browser). Requiere el extra **`[gui]`** (`fastapi` + `uvicorn`,
  import perezoso): si falta → `DependencyError`, **exit 3** con sugerencia `uv sync --extra gui`. **NO
  transiciona** el `CycleState`. La API es un adaptador delgado sobre `service/` (reusa el envelope
  `schema="1"` + `code_for`, no reimplementa el contrato); el mapeo código→HTTP y la auth viven en §0.2.
- **`resolve`** (issues #110/#112, AS-BUILT, ADR
  [0035](decisiones/0035-ingesta-multipuerta-resolucion-doi.md), 20° subcomando): **resuelve los DOIs del
  corpus a IDs de OpenAlex (`source_id`)** — cierra el **GAP-1** del flujo BibTeX e2e. Los papers
  sembrados con `seed --from-bib` traen `doi` pero **no `source_id`**; sin `source_id`,
  `enrich`/`chain` devuelven **0**. `resolve` filtra los papers con `doi != NULL` **AND**
  `source_id IS NULL`, consulta OpenAlex (batcheado, `OpenAlexSource.fetch_dois_to_openalex_ids` vía
  `service/resolve.py::resolve_dois`) y **puebla `source_id`** en esas filas; persiste con
  `persist_replace`. **Idempotente:** los papers que ya tienen `source_id` no se tocan (re-correr da
  el mismo resultado). Solo `source_id` (no `external_ids`, diferido #120). Flags: **`--email`**
  (polite pool de OpenAlex, recomendado), **`--json`** (envelope `schema="1"`) y la resolución de
  workspace por ambiente (`--workspace` global, igual que los demás). `data` =
  `{resolved, total_with_doi, already_resolved, total_papers}`. **NO transiciona el `CycleState`**
  (ortogonal al lazo, igual que `enrich`). Errores accionables: falla de red contra OpenAlex →
  `NetworkError` (exit 4); store bloqueado → `StoreError` (exit 5). La misma resolución se puede
  encadenar en la siembra con `seed --from-bib --resolve` (§`seed` arriba), que reusa el store abierto
  sin reabrir el `.duckdb` (`_resolve_dois_on_store`).

**`--workspace` global (OPCIONAL).** Va en el grupo `b2g`, **antes** del subcomando. Una
investigación = un **workspace** (carpeta marcada por `workspace.json`; ADR
[0029](decisiones/0029-workspace-por-investigacion.md), AS-BUILT). El estado vive en su
`library.duckdb`; el CLI es stateful **vía archivo**, no vía proceso.

- **`--workspace <carpeta>`** apunta a la raíz de un workspace. **`--store` fue ELIMINADA del CLI
  ([#75](https://github.com/complexluise/bib2graph/issues/75), BREAKING):** ya no está registrada
  como opción global, así que pasarla produce el **error estándar de Click** (`No such option:
  --store`). El **modo degenerado** (`.duckdb` suelto sin `workspace.json`) **dejó de existir**: un
  `.duckdb` legacy se adopta con **`b2g init .`** en su carpeta.
- **Resolución ambiente** cuando no se pasa `--workspace` (patrón git/cargo), precedencia de mayor a
  menor: (1) `--workspace` explícito, (2) `B2G_WORKSPACE` (variable de entorno), (3) **walk-up** del
  cwd buscando `workspace.json`. Sin ninguno → **error accionable** que sugiere `b2g init`.

**`build` y `export` separados** (decisión del PO, ADR 0021 §B): `build` computa `Networks.quick`
(4 redes) y escribe artefactos a `<workspace>/networks/<kind>/` (+ transiciona a `BUILT`);
`export --format graphml|csv` **relee** esos artefactos (fuente resuelta vía `ws.networks_dir`) y
los serializa (sin transición). **AS-BUILT #32 (2026-06-17):** `export --out-dir` pasó a **override
OPCIONAL** — sin él, escribe en **`<workspace>/exports/`** (resolución ambiente como `build`).
**AS-BUILT #31 (2026-06-17):** `build` también escribe **`clusters.csv`** (tabla de
resumen de comunidades, §7.2) en `<networks_dir>/<kind>/` **solo** para redes de **paper** con
comunidades detectadas (listas con separador `|`); en el envelope `--json`, cada entrada de
`data["networks"]` suma `clusters_csv` (ruta del archivo) **condicionalmente** —solo cuando ese
archivo se generó—. **Qué artefactos emite cada red:** **todas** escriben `network.graphml` +
`metrics.json`; **`clusters.csv` lo emiten ÚNICAMENTE las redes de paper** —`bibliographic_coupling`
y `cocitation`— (con comunidades). Las redes `author_collab`, `institution_collab` y
`keyword_cooccurrence` **NO** emiten `clusters.csv` **por diseño**: sus nodos ya son
autores/instituciones/keywords, y `cluster_table` (§7.2) resume comunidades **de papers** cruzando
nodo→corpus por `Col.ID` — ese mapeo no existe para nodos que no son papers, así que devuelve `[]`
(no crash) y el comando omite el archivo. Lo mismo aplica a `b2g networks --spec` (comparten
`_write_artifacts`).

**`build` — dos modos, una superficie (AS-BUILT #159, ADR 0037 (a)(e) + 0038):** `build` absorbe la
capacidad de `networks` vía `--spec`, sin perder el one-shot.

- **`build` (sin `--spec`) = modo quick:** computa `Networks.quick` (4-5 redes principales).
- **`build --spec <redes.yaml>` = modo declarativo:** carga la lista de specs con `load_specs`
  (§10, clave raíz `networks:`) y construye cada red con `Networks.build`. El helper compartido
  `_build_from_spec_file` (en `build.py`) es la **fuente única** para `build --spec` y para el alias
  `networks` (frontera con #165). **A diferencia de `networks`** (alias en deprecación, ortogonal al
  lazo, NO transiciona), **`build --spec` SÍ transiciona el FSM a `BUILT` y sella `.corpus_hash`** —es
  un paso BUILD pleno (decisión PO **D1**, ADR 0038).

**`--scope [all|accepted|seeds]` (default `all`, ADR 0038 P2):** filtra el corpus por estado de
curación **antes** de proyectar (vía `Corpus.scoped`, §1.2). **Default `all`** = corpus completo (el
one-shot corre sin curar). `accepted` = semillas (`is_seed=True`) + papers aceptados; `seeds` = solo
semillas. Aplica en **ambos** modos (quick y spec). El `networks/.corpus_hash` se sella con el hash
del corpus **FILTRADO** (no del vivo completo), y `clusters.csv`/`decorate` reflejan exactamente ese
subset (sin drift). Si el scope deja **0 papers**: **exit 0** + `warning` accionable ("corré
`b2g curate`… o usá `--scope=all`") — **no** es error; escribe `networks/` vacío con `.corpus_hash`
vacío. **NO confundir con `NetworkSpec.scope` (§10):** ejes distintos. `--scope` filtra el **corpus
entero** por curación (un input al `build`); `NetworkSpec.scope` (`full`/`seeds_only`) es **por-red
declarativa** sobre `is_seed`.

- **`--corpus-scope [all|accepted|seeds_only]` = alias DEPRECADO (oculto en `--help`):** vocab
  antiguo previo a #159. Sigue funcionando con **aviso a stderr** y tiene precedencia si se pasa junto
  a `--scope`; **la ventana cierra en 0.11.0** (ADR 0038 P1). Su vocab (`seeds_only`) es el vocab
  interno de `Corpus.scoped`; `--scope seeds` mapea a él.

**`--min-weight N` (solo modo quick):** descarta aristas con peso < N (default 1 = sin filtro). **Solo
aplica sin `--spec`.** Con `--spec`, cada red usa el `min_weight` declarado en su YAML por-red, y
pasar **`--min-weight` junto a `--spec` emite un warning a stderr** ("se ignora con `--spec`") — no
falla, pero el valor del CLI se descarta.

**`--thesaurus <archivo>` (#164, absorbe el verbo retirado `b2g thesaurus`):** aplica un thesaurus
multilingüe curado (JSON formato ADR [0011](decisiones/0011-thesaurus-multilingue.md)) sobre
`keywords_id` **antes** de scopear y proyectar, y persiste el corpus actualizado con `persist_replace`
(§4.1). Suma el bloque aditivo `data["thesaurus"] = {keywords_mapped, keywords_total, aliases_loaded,
applied_at}`. Thesaurus inexistente/mal formado → `DataError` (exit 2).

**`--email` / `--max-citing` (#162, pasada de co-citación):** `build` corre **automáticamente la pasada
`cited_by`** del Enricher (§`enrich`) cuando hay **semillas aceptadas** —puebla `cited_by_id` para la
red de co-citación—; **`--max-citing INTEGER`** acota los citantes por semilla y **`--email`** va al
polite pool de OpenAlex. **Sin semillas aceptadas la pasada es no-op (cero requests).** Suma el bloque
aditivo `data["enrichment"]` (`citing_new`/`citing_targets`). Por esto `build` **ya no es
estrictamente puro/sin red** (ADR 0025 enmendado); los proyectores sí siguen puros (ADR 0014).

**Diagnóstico de red-vacía en build-time (ADR 0037 §(e), no-divergencia con status-time):** `build`
reusa `predict_build_preview` (la **misma** fuente que usa `status`) para diagnosticar redes que salen
vacías. En modo humano va como `warning` a stderr; en `--json` va en el envelope como
**`data["empty_networks"]`** — una lista de `{kind, reason, fix_command}`, **separada** de
`data["warnings"]` (que queda reservado para avisos **corpus-level**, p. ej. el scope con 0 papers).
Si una red sale vacía por el `min_weight` del YAML (modo spec), el `reason` **culpa al spec**
(no al `--min-weight` del CLI) y `fix_command=None`.

**Esquema de respuesta `--json` (`data`):** `networks_built`, `artifacts_dir`, `corpus_hash`,
**`scope`** = **token CLI** (`seeds`/`accepted`/`all`, gancho estable para #160 maturity),
**`corpus_scope`** = vocab interno (`seeds_only`/…, backward-compat), `networks` (lista, con
`clusters_csv` condicional), `warnings` (corpus-level), `empty_networks` (diagnóstico por-red) y
**`maturity`** (bloque aditivo del one-shot, AS-BUILT #160 — ver Apéndice `maturity`; `curated`
deriva del **corpus completo** pre-scope, `scope` reusa este `data["scope"]`, `empty_networks` es la
lista de `kind` extraída de `data["empty_networks"]` sin duplicar `reason`/`fix_command`; presente
también en el early-return de corpus vacío), **`enrichment`** (#162, métricas de la pasada `cited_by`:
`citing_new`/`citing_targets`; presente aun cuando es no-op) y **`thesaurus`** (#164, presente solo si
se pasó `--thesaurus`).
Invariante: envelope `schema="1"`, exit codes y FSM intactos; todo lo de #159/#160/#162/#164 es
**aditivo**.

> **No-divergencia es por-corpus.** La garantía de no-divergencia entre el diagnóstico de red-vacía de
> `build` y el de `status` (ADR 0037 §(e)) es **sobre el mismo corpus de entrada**. Con `--scope != all`,
> `predict_build_preview` corre sobre el **corpus filtrado**, así que los conteos del `reason` pueden
> diferir legítimamente de los de `status` sobre el corpus completo. La **lógica es fuente única**; lo
> que varía es el corpus que se le pasa.

**Grupo `snapshot {create, restore}` — TERCER grupo noun-verb del CLI (#163, ADR 0038).** Para alojar
`snapshot restore` (= ex verbo plano `restore`, ADR 0038), **`snapshot` deja de ser verbo plano y se
vuelve grupo noun-verb** —mismo patrón que `read` (1°, #156/#157) y `curate` (2°, #155)—. `snapshot`
**sin subcomando** imprime la ayuda y sale **exit 0**; el `command` del envelope usa la **ruta
completa** (`"snapshot create"` / `"snapshot restore"`). **BREAKING (autorizado por ADR 0038, sin
alias):** el `snapshot` plano → **`snapshot create`** (mismo criterio que el BREAKING de `curate`).
**La transición la define el VERBO** (precedente D1 de #159): `snapshot create` **NO** transiciona,
`snapshot restore`→`FILTERED`. **Fuente única en `service/snapshot.py`** (`run_snapshot`/`run_restore`,
servicio neutral con `decided_at` inyectado en la frontera, ADR 0017): `snapshot create`,
`snapshot restore` y el shim del verbo suelto `restore` (alias deprecado, retiro #165) **delegan** en
ella.

- **`snapshot create`** (= ex `snapshot` plano, AS-BUILT #32): sella una foto reproducible del estado
  vivo (parquet + `manifest.json`, ADR 0017). **`--out-dir` pasó a override OPCIONAL** — sin él,
  escribe en **`<workspace>/snapshots/`** (resolución ambiente vía `resolve_workspace`, igual que
  `build`). **NO transiciona** el `CycleState`. Su `--json.data` —`snapshot_dir`, `corpus_hash`,
  `total_papers`, `schema_version`— suma el bloque aditivo **`maturity`** (AS-BUILT #160, ver Apéndice
  `maturity`): `scope="all"`, `empty_networks=[]` (no proyecta redes), `curated` desde el corpus vivo
  (`run_snapshot` lleva el bloque, coherente con `build`/`read top`).
- **`snapshot restore`** (= ex verbo plano `restore`): rehidrata un corpus curado desde un parquet
  **sin red** (mergea+dedup, preserva la curación), **transiciona a `FILTERED`**. Semántica completa
  en §`snapshot restore` (arriba). El verbo suelto `restore` queda como **alias deprecado** (shim que
  delega con `command="restore"`; retiro #165).

> **Follow-up (BAJO, #175):** `service/snapshot.py` duplica `normalize_and_dedup` respecto del helper
> `cli/_ingest.py`. Es deuda DRY, **no** afecta el contrato; se resuelve en su issue, no aquí.

**Staleness de la cache de redes (AS-BUILT #32, 2026-06-17):** `b2g status` suma el campo aditivo
`data["networks_cache_stale"]: bool` (`schema="1"` intacto) y, cuando es `true`, un `warnings`
accionable ("ejecutá `b2g build`"). Lo dispara que el `networks/.corpus_hash` **sellado** por el
último `build` **no coincida** con el `corpus_hash` del corpus vivo (calculado con el **mismo**
`compute_corpus_hash(corpus.to_arrow())` que `build` usa para sellar → sin falsos positivos). Si la
cache **no existe** (nunca se corrió `build`), **no** es stale. `status` **avisa, NO regenera**:
invalidación por hash, **no** un build-system (ADR [0029](decisiones/0029-workspace-por-investigacion.md)).

**Transiciones automáticas del ciclo** (ADR 0021 §F; AS-BUILT R3): `seed`→`SEEDED`,
**`chain`→`FORAGED`** (chaining normal), **`chain --since`→`MONITORED`** (#158: forrajeo incremental;
el alias deprecado `monitor` transiciona igual, vía la acción FSM `monitor`), `filter`→`FILTERED`,
**`curate filter`→`FILTERED`** (#155: dentro del grupo `curate` la transición la define el VERBO, no el
grupo —precedente D1 de #159), `build`→`BUILT`,
**`snapshot restore`→`FILTERED`** (Ciclo 9a, ADR 0030/0038: el corpus restaurado ya pasó curación;
reusa la transición permisiva `filter`; el verbo suelto `restore` —alias deprecado— transiciona igual).
**No existe un estado `CHAINED`:** `chain` va a `FORAGED` y `chain --since` a `MONITORED`.
`accept`/`reject`/**`curate {dump,apply,accept,reject}`**/**`read`**/`export`/**`snapshot create`**/`status`/`inspect`/`validate`/el alias `enrich`/el alias `networks`
**no transicionan** (los verbos transversales de `curate` y **`read`** son transversales/lectura pura
—**salvo `curate filter`**, que sí transiciona; el enriquecimiento absorbido en `chain`/`build` y el
alias `networks` son ortogonales al lazo, ADR 0025 / Hito 9). El estado
destino lo dicta `bib2graph.cycle.apply_transition`
(fuente única de verdad; los comandos no hardcodean el destino). `seed` con **estado previo** se trata
como **`reseed`** (loop-back a `SEEDED`, ronda++, acumula sobre lo curado).

**Grupo `read {list,stats,show,top}` — primer grupo noun-verb del CLI (#156/#157, ADR
[0037](decisiones/0037-superficie-cli-10-verbos-ciclo.md) §b).** Es lectura pura del corpus (no
transiciona el ciclo, §arriba). `read` **sin subcomando** imprime la ayuda y sale con **exit 0**
(no es error de uso). El campo `command` del envelope usa la **ruta completa** del grupo noun-verb:
`"read list"` / `"read stats"` / `"read show"` / `"read top"` (convención para grupos: comando =
`<grupo> <verbo>`, no solo el grupo). `read top` (la **salida de investigación** del 0037 §b) se
materializó en #157 (antes diferido). La lógica vive en `service/reads.py` (`list_papers`,
`corpus_stats`, `get_paper` extendido, `get_top` — §0.1), exportada en `service/__init__.py`.

- **`read list`** — lista papers del corpus. Filtros (combinables, AND): `--query TEXT` (substring
  **case-insensitive sobre el título únicamente**), `--status {candidate,accepted,rejected}`,
  `--seeds` / `--candidates` (por `is_seed`), `--year INT`. Envelope:
  `data = {papers: [{id, title, year, curation_status, is_seed}], count: int}`.
- **`read stats --group-by {status,year,is_seed}`** (default `status`) — conteos agrupados. Envelope:
  `data = {group_by: str, total: int, groups: [{key, count}]}`. Un valor de `--group-by` fuera del
  `Choice` es **error de uso de Click → exit 1** (coherente con ADR 0010 uso=1/datos=2 y con todos
  los `Choice` del repo; **no** es exit 2).
- **`read show --id <ID>`** — delega en `service.get_paper(ws, ident)` (§0.1; resuelve **id | doi |
  source_id**, prioridad id>doi>source_id, ADR 0036). Envelope: `data =` la **fila completa** del
  corpus (~14 campos: `id, source_id, doi, title, year, abstract, is_seed, curation_status,
  authors_raw, authors_id, keywords_id, references_id, cited_by_id, provenance`). `--id` que no
  matchea ningún id/doi/source_id → `DataError`, **exit 2**.
- **`read top`** — la **salida de investigación** (#157): un envelope con **dos bloques** sobre redes
  recomputadas en tiempo de lectura (**no requiere `build` previo**; mismo camino que `get_network`).
  Flags: `--top N` / `-n` (default 10), `--kind` (`Choice` sobre los 5 `NetworkKind`, **default
  `bibliographic_coupling`**), `--json`. Envelope:
  `data = {kind, top, central: [{id, title, degree_centrality, community?}],
  cocitation: [{source, source_title, target, target_title, weight}], reason?, fix_command?,
  maturity}`. El bloque **`maturity`** (aditivo del one-shot, AS-BUILT #160 — ver Apéndice `maturity`)
  está **SIEMPRE presente**: `scope="all"`, `empty_networks=["cocitation"]` cuando la co-citación
  quedó vacía (si no, `[]`), `curated` desde el corpus. **No** duplica `reason`/`fix_command` (esos
  viven en el bloque honest-empty de abajo).
  - **`central`** — top `N` nodos de la red `--kind` por `degree_centrality` desc. En redes de paper
    (`bibliographic_coupling`/`cocitation`) `title` es el **título completo** (join id→title); en
    redes de autor/institución/keyword cae al `label` (nombre de la entidad).
  - **`cocitation`** — **SIEMPRE** la red `cocitation` (independiente de `--kind`): top `N` aristas
    por `weight` desc, con título de ambos extremos.
  - **`--kind` default `bibliographic_coupling`** porque es **robusto en el one-shot frío**: se
    calcula desde las referencias propias del corpus (no necesita `enrich`/`chain --forward`), así la
    salida estrella entrega valor temprano. La **co-citación** necesita datos *forward* (`cited_by_id`).
  - **Contrato honest-empty (exit 0, no error).** Si la red `cocitation` está vacía (corpus sin
    `cited_by_id`, p. ej. un one-shot sin `enrich`/`chain --forward`) → **exit 0** + bloque
    `cocitation: []` + `reason`/`fix_command` (tomados de `predict_build_preview`). **No** es
    `DataError`. `reason`/`fix_command` aparecen **solo** en ese caso.
  - **Exit codes:** `--kind` inválido → **exit 1** (UsageError de `Choice`, fuera del envelope, §abajo);
    `get_top` llamado desde el servicio con `kind` inválido o `n <= 0` → `DataError`, **exit 2**
    (defensa de la capa neutral). Un fallo genuino de construcción de red → `DataError`, exit 2 (≠ vacío).

`inspect` (verbo plano) **sigue vivo pero en deprecación** (#165): `read show` lo absorbe para
papers y `status` para manifest/FSM. **No** está removido en este hito.

**Grupo `curate {dump,apply,accept,reject,filter}` — SEGUNDO grupo noun-verb del CLI (#155, ADR
[0037](decisiones/0037-superficie-cli-10-verbos-ciclo.md) §b).** Mismo patrón que `read`: `curate`
**sin subcomando** imprime la ayuda y sale con **exit 0**; el `command` del envelope usa la **ruta
completa** (`"curate dump"`, `"curate apply"`, `"curate accept"`, `"curate reject"`,
`"curate filter"`). La semántica de cada verbo está arriba (§`curate`). **A diferencia de `read`
(transversal entero), la transición la define el VERBO** (precedente D1 de #159): solo
`curate filter` transiciona a `FILTERED` (vía `apply_transition`, fuente única); el resto es
transversal. La lógica vive en `service/curate.py` (fuente única CLI/FastAPI, §0):
**`run_curate_dump`**, **`run_curate_from_csv`** (el verbo `apply`), **`filter_corpus`** y
`accept_papers`/`reject_papers`. **`filter_corpus(store_path, *, year_gte, year_lte, language,
type_in, min_citations, decided_at)`** recibe el **reloj `decided_at` inyectado** por ambos callers
(el subcomando `curate filter` y el verbo suelto `filter`), preservando la neutralidad de servicio
(ADR [0017](decisiones/0017-reproducibilidad-historia-snapshot.md): el reloj entra por la frontera,
no por el servicio). **BREAKING:** la forma-flag `curate --dump`/`--from-csv` y `--all` fueron
eliminadas sin alias (autorizado por ADR 0037 §b).

**Envelope JSON común y versionado** (ADR 0021 §C): en modo `--json`, cada subcomando emite **un
objeto JSON** con `schema="1"`:

```json
{
  "schema": "1",
  "ok": true,
  "command": "seed",
  "exit_code": 0,
  "data": { },
  "warnings": [],
  "error": null
}
```

En error conocido: `ok=false`, `data={}`, `error={"code": <CODE>, "message": <accionable>}`. Los
exit codes se mapean **por tipo de error** (ADR 0021 §D): `DataError`→2, `ImportError`/
`DependencyError`/`NotImplementedError`→3, `httpx.HTTPError`→4, `StoreLockedError`/`OSError`→5.
**R5:** `AttributeError` ya **no** se mapea en el decorador (un bug real no se disfraza de "capacidad
faltante"); la capacidad-de-source-faltante se convierte en `DependencyError` con un **pre-check
`hasattr` en el comando** (p. ej. `chain` antes del `Forager`). Un `AttributeError` inesperado se
propaga limpio.

**Borde: el error de uso sale SIN envelope.** Ante un error de uso (p. ej. una opción requerida
faltante, una opción desconocida como `--store` —eliminada en #75—, o ningún workspace resoluble),
Click aborta el parseo **antes** de entrar al comando: se emite el mensaje de uso de Click en **stderr** y
exit code `1`, **sin** envelope JSON. El envelope versionado solo cubre errores que ocurren
**dentro** de la ejecución del comando.

**stdout puro en modo JSON (ENFORCED, ADR 0021 §C; verificado #151).** En modo JSON (por `--json`
o por `B2G_JSON`, abajo) stdout emite **exactamente una línea**: el envelope `schema="1"` — y nada
más. Esto vale **también en el camino de error** (`ok=false` → envelope en stdout, no en stderr). El
texto de modo humano (progreso, avisos legibles) va a **stderr**, nunca a stdout. Un agente parsea
una línea JSON por invocación con la garantía de que stdout no trae ruido.

**`B2G_JSON` — modo JSON por entorno (env var; #151, enmienda ADR 0021 §C).** Además del flag
`--json` (por-comando, **post-verbo**: `b2g <cmd> --json` — la posición **no cambió**), el modo JSON
se activa con la variable de entorno **`B2G_JSON`**:

- **Valores truthy** (case-insensitive): `1`, `true`, `yes`. Cualquier otra cosa (ausente, `0`,
  `false`, `no`, vacío) = modo humano.
- **Alcance:** **todos** los comandos, incluido `init`. No hay que pasar `--json` en cada llamada.
- **Precedencia:** `--json` explícito **gana**; si no está, `B2G_JSON` truthy activa el modo JSON.
  **No existe `--no-json`** (no se puede forzar modo humano teniendo `B2G_JSON` truthy salvo
  desetear/cambiar la env var).
- **Recomendación agents-first:** un agente hace **`export B2G_JSON=1` una vez** al inicio de la
  sesión y corre todo el ciclo (`init → seed → chain → … → export`) sin repetir `--json`.

Aditivo y retrocompatible: el envelope `schema="1"`, los exit codes y la FSM **no cambian** (ver
ADR [0021](decisiones/0021-cli-agente-native-contrato.md) §C, enmienda 2026-06-27).

**Apéndice — bloque `maturity` del one-shot (AS-BUILT #160, ADR [0037](decisiones/0037-superficie-cli-10-verbos-ciclo.md) §f; FORMA fijada aquí por delegación de ADR [0038](decisiones/0038-destino-verbos-huerfanos-0037.md) P3).**
Los artefactos del camino **one-shot** llevan un bloque **aditivo** `data["maturity"]` que **se
autodeclara borrador sin pulir**: honestidad **por construcción** (vom Brocke/PRISMA hecho
self-description), para que ni un agente que optimiza por `exit 0` ni un humano apurado confundan un
one-shot con un resultado terminado. **Aditivo: `schema="1"` intacto.**

```json
"maturity": {"curated": false, "scope": "all", "saturated": false, "empty_networks": []}
```

- **Forma estable: SIEMPRE 4 claves** (orden y tipos fijos). El bloque no muta de forma según el caso.

| clave | tipo | valores | regla de derivación |
|---|---|---|---|
| `curated` | `bool` | `true`/`false` | `true` si el corpus **completo** (`corpus_full`, **antes** del filtro de `--corpus-scope`) tiene **≥1 paper** con `curation_status` ∈ {`accepted`, `rejected`}. Refleja si hay decisiones de curación aplicadas, **independiente** del scope y del FSM. |
| `scope` | `str` \| `null` | token CLI (`all`/`accepted`/`seeds`…) \| `null` | En `build` reusa `data["scope"]` (el **token CLI** tal como se tipeó, no el vocab interno `seeds_only`). En `snapshot create` y `read top` es `"all"`. `null` si no aplica. |
| `saturated` | `bool` | **`false` constante** | **Siempre `false`** en one-shot: el PO decidió **no sobre-afirmar**. Gancho futuro (documentado en el código): comparar `referenced_refs_count()` entre rondas de `enrich` para detectar convergencia de referencias. |
| `empty_networks` | `list[str]` | lista de `kind` (puede ser `[]`) | **Solo los tokens `kind`** de las redes vacías. `reason`/`fix_command` **NO se duplican** acá — siguen viviendo en `data["empty_networks"]` (lista de dicts `{kind, reason, fix_command}`) de `build`. En `build` se extraen de ahí; en `read top` es `["cocitation"]` si la co-citación quedó vacía; en `snapshot create` es `[]`. |

- **Dónde aparece (PRESENTE SIEMPRE):** `build` (incluido el early-return de corpus vacío),
  `snapshot create` y `read top`. **AUSENTE** en `read list`, `read stats` y `read show` (lecturas tabulares,
  no artefactos one-shot) — no llevan `maturity`.
- **Función pura:** lo calcula `service.maturity.compute_maturity(corpus, *, scope, empty_network_kinds)`
  (sin I/O, re-exportada desde `bib2graph.service`), invariante de neutralidad de transporte intacta
  (§0).

### Avisos de deprecación (AS-BUILT #165, ADR [0038](decisiones/0038-destino-verbos-huerfanos-0037.md) P1)

La consolidación 0.10.0 retira solapamientos **sin romper de una**: los nombres viejos siguen
funcionando durante 0.10.x con un **aviso de deprecación**, y **se eliminan en 0.11.0** (criterio por
versión, no fecha). El helper único es `cli/_deprecation.py::emit_deprecation`.

**Formato canónico** (exacto):

```text
AVISO: '<viejo>' está deprecado y se eliminará en 0.11.0; usá '<nuevo>'.
```

- **Canal: stderr SIEMPRE** (modo humano y modo `--json`), nunca stdout — preserva el stdout puro de
  una línea-envelope (#151). En `--json`, el mismo mensaje se propaga además al **`warnings[]`
  top-level** del envelope (no a `data`), enhebrado vía `build_envelope(..., warnings=[msg])`.
- **No cambia el contrato:** el alias delega en la misma lógica de servicio (fuente única) y conserva
  su `command`/envelope; `schema="1"`, exit codes y FSM intactos.

**Los 9 verbos deprecados** (alias vivo con aviso → forma canónica):

| Alias deprecado | Forma canónica |
|---|---|
| `b2g accept` | `b2g curate accept` |
| `b2g reject` | `b2g curate reject` |
| `b2g filter` | `b2g curate filter` |
| `b2g inspect` | `b2g read show` (papers) / `b2g status` (manifest/FSM) |
| `b2g monitor` | `b2g chain --since` |
| `b2g networks` | `b2g build --spec` |
| `b2g enrich` | `b2g chain` (refs→DOI) + `b2g build` (co-citación) |
| `b2g restore` | `b2g snapshot restore` |
| `b2g resolve` | `b2g seed --resolve` |

**Además** (mismo corte 0.11.0):

- **Entry-point `bib2graph` → `b2g`** (`main_bib2graph_alias` emite el aviso y delega en `main`).
- **Opción `build --corpus-scope` → `build --scope`** (deprecación de **flag**, oculta en `--help`;
  el vocab viejo `seeds_only` sigue aceptado y tiene precedencia si se pasan ambos).

**`thesaurus` NO está en esta lista:** se **retiró por completo** (sin alias). Su capacidad vive como
`b2g build --thesaurus <archivo>` (#164, ver §`build`).

---

## 0. Capa de servicios `service/` — contrato neutral compartido (AS-BUILT G1, ADR 0028)

> **AS-BUILT del Hito G1 del MVP GUI (2026-06-18, ADR
> [0028](decisiones/0028-arquitectura-gui-api-capa-servicios.md)).** Documenta una decisión **ya
> tomada y firmada** (ADR 0028 Aceptada, PO 2026-06-18): el contrato del envelope/errores **sube** de
> `cli/` a una capa neutral. **El contrato externo del CLI no cambia** (envelope `schema="1"`, exit
> codes 0–5, ADR 0021) — por eso este movimiento **no requiere un ADR nuevo**.

`src/bib2graph/service/` es la **capa de servicios neutral** de la que CLI (y, como TARGET, la API)
son adaptadores delgados (ADR 0028, inversión de dependencia ports & adapters). G1 sube **EL CONTRATO**
que antes vivía en `cli/_envelope.py`/`cli/_errors.py`. Las **lecturas read-only de la SPA**
(`get_scent`/`get_network`/`compare_rounds`/…) **se construyeron en G2** (`service/reads.py`, AS-BUILT
2026-06-18 — ver §0.1). La migración de la **orquestación** (`run_<cmd>`) a `service/` **sigue siendo
TARGET** (no construida en G1/G2).

**Invariante de neutralidad de transporte (estricta).** `service/` es **agnóstica de transporte**:
**sin `print`, `sin sys.exit`, sin Click, sin FastAPI**. Es el límite que mantiene el contrato
reutilizable por cualquier adaptador. El I/O (`emit`/`emit_human` en `cli/_envelope.py`,
`handle_errors`/`_emit_error_envelope` en `cli/_errors.py`) **se queda en el adaptador CLI**.

**Contrato público** (re-exportado desde `bib2graph.service.__init__`):

```python
# service/envelope.py — envelope JSON común y versionado
ENVELOPE_SCHEMA_VERSION: str = "1"   # versión del contrato del envelope (ADR 0021)

def build_envelope(
    *,
    command: str,
    ok: bool,
    data: dict[str, Any],
    exit_code: int,
    warnings: list[str] | None = None,
    error: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Construye el envelope JSON estable del contrato (schema="1").
    {schema, ok, command, exit_code, data, warnings, error}. Función pura, sin I/O."""


# service/errors.py — jerarquía de errores tipados (ADR 0021)
class B2GError(Exception):
    """Base de los errores accionables. Atributos de clase: exit_code: int, code: str;
    instancia: .message. Subclases con su (exit_code, code):"""
    exit_code: int = 1
    code: str = "B2G_ERROR"

class UsageError(B2GError):      exit_code = 1; code = "USAGE_ERROR"       # uso (opción faltante/inválida)
class DataError(B2GError):       exit_code = 2; code = "DATA_ERROR"        # schema/ids/filtro inválido
class DependencyError(B2GError): exit_code = 3; code = "DEPENDENCY_ERROR"  # ImportError / capacidad faltante
class NetworkError(B2GError):    exit_code = 4; code = "NETWORK_ERROR"     # httpx.HTTPError / timeout
class StoreError(B2GError):      exit_code = 5; code = "STORE_ERROR"       # store/snapshot bloqueado o corrupto


def code_for(exc: BaseException) -> int:
    """Mapeo PURO error→exit code (0–5, ADR 0021), sin I/O ni sys.exit:
    B2GError → su .exit_code; OSError (incl. StoreLockedError) → 5; ImportError → 3;
    httpx.HTTPError → 4. Excepción no mapeada → TypeError (el llamador decide).
    Lo usan la capa de servicio y los adaptadores para derivar exit code / HTTP status
    sin duplicar la política."""


# service/maturity.py — bloque maturity del one-shot (#160, ADR 0037 §f / 0038 P3)
def compute_maturity(
    corpus: Corpus, *, scope: str | None, empty_network_kinds: list[str]
) -> dict[str, Any]:
    """Bloque maturity para el --json de build/snapshot create/read top (ver Apéndice maturity).
    Función PURA, sin I/O. Devuelve EXACTAMENTE 4 claves:
    {curated: bool, scope: str|None, saturated: bool, empty_networks: list[str]}.
    curated = corpus tiene ≥1 paper con curation_status ∈ {accepted, rejected};
    saturated = False constante (one-shot never over-claims; gancho futuro referenced_refs_count);
    empty_networks = solo los kind (reason/fix_command NO se duplican)."""
```

**Adaptadores (el contrato se re-exporta, no se duplica).** `cli/_envelope.py` y `cli/_errors.py`
hacen `from bib2graph.service... import ...` y re-exportan los **mismos objetos**, así que los imports
existentes del CLI y los tests (`from bib2graph.cli._envelope import build_envelope`,
`from bib2graph.cli._errors import B2GError, DataError, …`) siguen funcionando sin cambios. El
decorador `handle_errors` (CLI) conserva su propia escalera `try/except` por tipo de error + el
`sys.exit` y la emisión del envelope de error; `code_for` es el mapeo puro disponible para los
adaptadores (incluida la API TARGET, que lo traducirá a HTTP status, ADR 0028 §7). El mapeo de
`code_for` y el de `handle_errors` describen la **misma política** (ADR 0021 §D).

### 0.1 Lecturas de servicio `service/reads.py` — las 6 lecturas de la SPA (AS-BUILT G2, ADR 0028)

> **AS-BUILT del Hito G2 del MVP GUI (2026-06-18, ADR
> [0028](decisiones/0028-arquitectura-gui-api-capa-servicios.md)).** Documenta una decisión **ya tomada**:
> G2 expone en `service/` las lecturas read-only que la SPA necesita y que el CLI **nunca tuvo como
> subcomando** (scent, red por kind, rondas, diff de rondas, paper por id). **El contrato externo del CLI
> no cambia** (`tests/unit/test_cli.py` intacto) — por eso este movimiento **no requiere un ADR nuevo**.
> Forma del encuadre y bifurcaciones resueltas: [`ROADMAP/05-gui.md`](ROADMAP/05-gui.md) §G2.

`src/bib2graph/service/reads.py` expone las **6 funciones de lectura de la SPA (G2)** más las que
absorbió el **grupo CLI `read`** (#156/#157: `list_papers`, `corpus_stats`, `get_top` — §Grupo
`read`); todas re-exportadas desde `bib2graph.service.__init__`. Cada una recibe un **`Workspace` ya
resuelto** (la resolución ambiente
vive en el adaptador CLI, ADR 0029), abre el store **read-only**, y devuelve un `dict`/`list[dict]`
**serializable** o lanza un `B2GError` tipado. **Sin red, sin mutación, sin transición de ciclo**;
determinismo R2 (mismo corpus → misma lectura). Decisiones de producto resueltas (bifurcaciones
B-G2-1/2/3): **ronda = snapshot sellado** (no el contador `loop_round`), `get_scent` = **score de
acoplamiento real + vecinos** (no 4 paneles cosméticos del mock), `get_network` = **red de la ronda
viva recomputada** (cache `networks/` por snapshot diferida a G3).

```python
def get_workspace(ws: Workspace) -> dict[str, Any]:
    """Estado del workspace activo. Devuelve:
    {name, root, created_at, bib2graph_version, source, loop_state (str|None),
     round (int), total_papers (int), counts_by_status (dict[str,int]),
     transitions_available (list[str]), curation_available (list[str]),
     networks_cache_stale (bool)}. Raises StoreError."""

def list_rounds(ws: Workspace) -> list[dict[str, Any]]:
    """Snapshots sellados (vía Workspace.list_snapshots()) + una entrada sintética "live".
    Por snapshot: {id, corpus_hash, created_at, total_papers, schema_version}.
    Entrada viva: {id="live", round, loop_state, total_papers}. Raises StoreError.
    Ronda = snapshot (B-G2-1 Opción A); el contador loop_round se ve en la entrada "live"."""

def get_paper(ws: Workspace, ident: str) -> dict[str, Any]:
    """Fila del corpus (CORPUS_SCHEMA) resuelta por identidad source-agnóstica
    (ADR 0036): `ident` matchea contra **id | doi | source_id**, con prioridad
    `id` > `doi` > `source_id` (devuelve el primer match). Devuelve:
    {id, source_id, doi, title, year, abstract, is_seed, curation_status,
     authors_raw, authors_id, keywords_id, references_id, cited_by_id,
     provenance (list, parseada del JSON)}.
    Raises DataError si `ident` no matchea ningún id/doi/source_id;
    StoreError si el store falla.
    NOTA: el parámetro se renombró `paper_id`→`ident` (#156); el caller
    `api/routers/reads.py` lo pasa posicional (sin ruptura). `read show --id`
    delega en esta lectura (§Convenciones CLI · grupo `read`)."""

def get_scent(ws: Workspace, paper_id: str) -> dict[str, Any]:
    """Score de acoplamiento bibliográfico real + vecinos compartidos (B-G2-2). Devuelve:
    {paper_id, score (int = nº de corpus-papers con >=1 referencia compartida),
     coupling (list[{paper_id, title, weight}], ordenada por peso desc),
     references (list[{paper_id, title}] resueltas al corpus),
     cited_by (list[{paper_id, title}] resueltos al corpus)}.
    Raises DataError si el id no existe; StoreError si el store falla."""

def get_network(ws: Workspace, kind: str) -> dict[str, Any]:
    """Red de la ronda VIVA recomputada con Networks.build + decorate (B-G2-3; función pura,
    Louvain seeded por corpus_hash, R2). `kind` en NetworkKind del núcleo
    (bibliographic_coupling, cocitation, author_collab, institution_collab,
     keyword_cooccurrence). Devuelve:
    {nodes (list[{id, label, degree_centrality, community?, year?, is_seed?, curation_status?}]),
     edges (list[{source, target, weight}]),
     metrics ({n_nodes, n_edges, density, num_components, avg_clustering, n_communities})}.
    Raises DataError si kind es inválido o la red no se puede construir; StoreError si el store falla."""

def compare_rounds(ws: Workspace, round_a: str, round_b: str) -> dict[str, Any]:
    """EL DIFERENCIADOR (ADR 0027). Diff entre dos snapshots por Col.ID; "live" usa el corpus vivo.
    Devuelve:
    {round_a, round_b, added_paper_ids (ids en b no en a), removed_paper_ids (ids en a no en b),
     mutated_hubs ([], DIFERIDO — requiere redes por snapshot, B-G2-3),
     metrics_change (list[{metric, before, after}], hoy con n_papers; las métricas por red
       solo aparecen si ambos snapshots tienen networks/<kind>/metrics.json, que hoy no se
       materializa por snapshot)}.
    Raises DataError si un snapshot no existe o no tiene corpus.parquet; StoreError si el store falla."""


# --- Lecturas absorbidas por el grupo CLI `read` (#156/#157; ver §Grupo `read`) ---

def list_papers(ws: Workspace, *, query=None, status=None, is_seed=None, year=None) -> dict[str, Any]:
    """Lista mínima del corpus con filtros AND (todos opcionales). Devuelve:
    {papers: [{id, title, year, curation_status, is_seed}], count: int}.
    query = substring case-insensitive sobre el título; status = curation_status exacto;
    is_seed True/False; year exacto. Raises StoreError. (Detrás de `read list`.)"""

def corpus_stats(ws: Workspace, *, group_by="status") -> dict[str, Any]:
    """Conteos agrupados por status (default) | year | is_seed. Devuelve:
    {group_by, total, groups: [{key, count}]}. Raises DataError si group_by inválido;
    StoreError si el store falla. (Detrás de `read stats`.)"""

def get_top(ws: Workspace, *, n=10, kind="bibliographic_coupling") -> dict[str, Any]:
    """Salida de investigación (#157): nodos centrales + pares de co-citación con título,
    sobre redes recomputadas (NO requiere `build`; mismo camino que get_network). Devuelve:
    {kind, top, central: [{id, title, degree_centrality, community?}],
     cocitation: [{source, source_title, target, target_title, weight}], reason?, fix_command?,
     maturity}.
    `central` = top n nodos de la red `kind` por degree_centrality desc (título completo en redes
    de paper; label de entidad en author/institution/keyword). `cocitation` = SIEMPRE la red
    cocitation, top n aristas por weight desc.
    Honest-empty: co-citación vacía (sin cited_by_id) → bloque [] + reason/fix_command
    (de predict_build_preview), NO error. `maturity` (aditivo, #160, ver Apéndice `maturity`):
    SIEMPRE presente, scope="all", empty_networks=["cocitation"] si la co-citación quedó vacía.
    Raises DataError si kind inválido, n <= 0, o la red
    falla genuinamente; StoreError si el store falla. (Detrás de `read top`.)"""
```

**Nota de fidelidad al núcleo.** Los campos del mock `app/src/` que el núcleo no sostiene **no se
inventaron**: `get_paper` expone `authors_raw`/`authors_id` (no objetos autor con ORCID), `get_scent`
no emite los 4 paneles cosméticos, `get_network` no entrega `modularity` ni un id de red persistido, y
`compare_rounds` deja `mutated_hubs=[]` mientras no haya redes por snapshot. El encuadre campo-por-campo
y los "mock-no-sostenido" están en [`ROADMAP/05-gui.md`](ROADMAP/05-gui.md) §G2.

### 0.2 API local `api/` — la frontera HTTP de la SPA (AS-BUILT G3, ADR 0028)

> **AS-BUILT del Hito G3 del MVP GUI (2026-06-18, ADR
> [0028](decisiones/0028-arquitectura-gui-api-capa-servicios.md)).** Documenta una decisión **ya
> tomada**: la API local es un **adaptador de transporte** sobre `service/` (§0/§0.1). **El contrato
> externo del CLI no cambia** (`tests/unit/test_cli.py` intacto; envelope `schema="1"`, exit codes 0–5,
> ADR 0021) — por eso este movimiento **no requiere un ADR nuevo**. Encuadre y bifurcaciones resueltas:
> [`ROADMAP/05-gui.md`](ROADMAP/05-gui.md) §G3.

`src/bib2graph/api/` es la **API local FastAPI**: un adaptador **delgado** sobre la capa de servicios
neutral (§0). **No reimplementa lógica ni contrato** —reusa `service.build_envelope` y `service.code_for`—
y **no importa de `cli/`**; ambos frontends cuelgan de `service/`. El **núcleo no importa `fastapi`**:
todo `fastapi`/`uvicorn` se importa **perezosamente** dentro de `create_app`/`run_gui`, y vienen en el
extra **`[gui]`** = `fastapi` + `uvicorn` (§7 de [`ARCHITECTURE.md`](ARCHITECTURE.md)).

**Fábrica de la app.** `create_app(ws, *, token, cors_origins=None) -> FastAPI` (`api/app.py`, re-export
en `api/__init__.py`) monta los routers, el CORS (default `http://localhost:5173` +
`http://127.0.0.1:5173`, el Vite dev-server de G4), la seguridad y dos *exception handlers* globales
(`B2GError` y `Exception`). El `Workspace` se inyecta una sola vez (**singleton por proceso**, no se
resuelve por request — la resolución ambiente vive en el adaptador CLI `b2g gui`).

**Endpoints (7).** Cada lectura llama a la función homónima de `service/reads.py` (§0.1) y la escritura a
`service/curate.py`; el resultado se envuelve con `build_ok_response` (envelope `ok=true`, HTTP 200).
Las lecturas que devuelven lista se envuelven en un dict con clave semántica (`rounds`) para respetar la
firma `build_envelope(data: dict)`.

| Método | Ruta | Servicio (`service/`) | Forma de `data` |
|---|---|---|---|
| GET | `/api/workspace` | `reads.get_workspace(ws)` | dict de estado del workspace (§0.1) |
| GET | `/api/rounds` | `reads.list_rounds(ws)` | `{"rounds": [...]}` (snapshots + entrada `live`) |
| GET | `/api/paper/{id}` | `reads.get_paper(ws, id)` | fila del corpus (§0.1; `id` resuelve id\|doi\|source_id, ADR 0036) |
| GET | `/api/paper/{id}/scent` | `reads.get_scent(ws, id)` | score de acoplamiento + vecinos (§0.1) |
| GET | `/api/network/{kind}` | `reads.get_network(ws, kind)` | `{nodes, edges, metrics}` (§0.1) |
| GET | `/api/compare?a=&b=` | `reads.compare_rounds(ws, a, b)` | diff de rondas (§0.1) |
| POST | `/api/paper/{id}/curate` | `curate.curate_paper(ws.library_path, id, decision=…)` | `{accepted_count\|rejected_count, ids}` |

El body del POST es `{"decision": "accepted"|"rejected"}` (modelo Pydantic `CurateRequest`); otra
`decision` → `DataError` (422). El endpoint de curación toma el **`WriteLock` global serializado** (una
escritura a la vez, ADR 0028 §6 / ADR 0019) e **inyecta `decided_at` en la frontera API** (`datetime.now(UTC)`;
R2/ADR 0017) — el servicio nunca llama `datetime.now()`. La curación de un paper **es una mutación
puntual** y por eso toma `ws.library_path` (la ruta al `.duckdb`), no el workspace completo.

**Autenticación — Bearer token efímero** (`api/security.py`, Nota 12 C.3). El token se genera en el
arranque de `b2g gui` con `secrets.token_urlsafe(32)` y se inyecta en `create_app`. Cada endpoint
depende de `require_token` (`api/deps.py`), que lee `Authorization: Bearer <token>` (esquema
`HTTPBearer(auto_error=False)`) y, si **falta o es inválido**, lanza `HTTPException(status_code=401)`. La
verificación usa `secrets.compare_digest` (tiempo constante). El **401 de auth es del adaptador HTTP**,
no del contrato de exit codes 0–5 (la auth no existe en el CLI).

**Mapeo código→HTTP** (`api/envelopes.py`, ADR 0028 §7). Los *exception handlers* convierten la
excepción en `JSONResponse` con el envelope `schema="1"` íntegro en el body (la SPA lee `error.code`, no
depende del status); el status sale de `code_for(exc)` (la misma política pura de §0) traducido así:

| Exit code (contrato) | Error | HTTP |
|---|---|---|
| 0 | éxito | **200** |
| 1 | `UsageError` | **400** |
| 2 | `DataError` | **422** |
| 3 | `DependencyError` | **501** |
| 4 | `NetworkError` | **502** |
| 5 | `StoreError` (bloqueado/corrupto) | **409** |
| — | excepción **inesperada** (no mapeada por `code_for`) | **500** (`error.code = "INTERNAL_ERROR"`) |

El **500** es deliberadamente distinto del 409: una excepción no mapeada es un **bug interno**, no un
conflicto de store; devolver 409 sugeriría a la SPA reintentar (`code_for` lanza `TypeError` ante una
excepción no mapeada y el handler la convierte en 500). El **401 de auth** corta **antes** de llegar a
este mapeo (es la dependencia `require_token`).

**Operaciones largas (v1, ADR 0028 §6).** Ejecución **síncrona** + lock global serializado; jobs
async/SSE de progreso **diferidos** (no en v1; el `5`→409 es el caso "store ocupado", el **retry
cross-process queda diferido** — B-G3-3).

**Migración de la orquestación de curación a `service/`.** Con G3, `service/curate.py` **sube desde
`cli/`** la orquestación de `accept`/`reject`: expone `accept_papers(store_path, ids, *, by, decided_at)`,
`reject_papers(...)` (gemelas) y `curate_paper(store_path, paper_id, *, decision, by, decided_at)` (wrapper
de un solo paper que valida `decision ∈ {accepted, rejected}`). Todas verifican que los ids existan
(`DataError` si faltan), abren el store con `_open_writable` (`StoreLockedError`/`OSError` → `StoreError`)
e **inyectan `decided_at`** desde la frontera. **`run_accept`/`run_reject` (CLI) quedan como shims que
delegan**, con su firma intacta (`by="cli"`, `decided_at` inyectado), así que `test_cli.py` no cambia.

**Extensión #155 (grupo `curate` noun-verb).** `service/curate.py` consolida la **fuente única** de
toda la curación (CLI y FastAPI): suma **`run_curate_dump`** (= `curate dump`), **`run_curate_from_csv`**
(= `curate apply`) y **`filter_corpus(store_path, *, year_gte, year_lte, language, type_in,
min_citations, decided_at)`** (= `curate filter` y el verbo suelto `filter`) a las ya existentes
`accept_papers`/`reject_papers`/`curate_paper`. `filter_corpus` recibe el **reloj `decided_at`
inyectado** por ambos callers (subcomando y verbo suelto) → neutralidad de servicio restaurada
(ADR [0017](decisiones/0017-reproducibilidad-historia-snapshot.md): el reloj entra por la frontera,
no por el servicio). Las funciones de comando del CLI quedan como **shims que delegan**.

**Subcomando `b2g gui`.** Ver [`ARCHITECTURE.md`](ARCHITECTURE.md) §6.3 y §convenciones CLI (19°
subcomando): levanta `uvicorn.run` sobre `create_app`, sirve la SPA buildeada de `gui/static/` **si
existe**, imprime URL + token, bind `127.0.0.1` (default puerto 8765). Falta del extra `[gui]` →
`DependencyError` (exit 3, mensaje accionable `uv sync --extra gui`).

**Wiring del token (AS-BUILT G4, B-G4-3).** La SPA necesita el token Bearer para autenticarse, así que
`b2g gui` **no lo entrega solo por stdout**: cuando el frontend está buildeado (`gui/static/index.html`
existe), monta una ruta **`GET /`** (`serve_index`) que lee ese `index.html` y reemplaza el placeholder
**`__B2G_TOKEN__`** con el token efímero (`cli/commands/gui.py::_make_index_response` →
`HTMLResponse`); **`GET /` no exige Bearer** (es el bootstrap del HTML, no un endpoint de datos). Los
**assets** (JS/CSS/fuentes) los sirve `StaticFiles(directory=gui/static, html=False)` montado en `/`
**sin** modificación. El frontend lee el token de **`window.__B2G_TOKEN__`** (inyectado en el HTML) y lo
manda en `Authorization: Bearer <token>` a los 7 endpoints. Si el frontend **no** está buildeado, `b2g
gui` avisa por stderr y deja **solo la API** disponible. *(Reemplaza el plan del encuadre G4 §5, que
preveía `StaticFiles(..., html=True)`: el AS-BUILT usa `html=False` + ruta `GET /` propia para poder
inyectar el token.)*

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

> **Nota de construcción:** el rework del **Hito 1.5 está hecho** (ver [`ROADMAP.md`](ROADMAP/README.md),
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
| `id` | `string` | no | id interno estable (hash de `doi`/`source_id`; ver §1.1 *Identidad*, ADR [0036](decisiones/0036-identidad-source-id-agnostica-doi-ancla.md)) |
| `source_id` | `string` | sí | id del **motor de extracción** que entregó el paper (p. ej. `W...` para OpenAlex). Agnóstico al motor (ADR [0036](decisiones/0036-identidad-source-id-agnostica-doi-ancla.md)): el nombre del motor vive en `provenance.source`, no en la columna |
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

> **Tabla lateral `external_ids(paper_id, engine, id)` (ADR
> [0036](decisiones/0036-identidad-source-id-agnostica-doi-ancla.md), opción C — INFRA PRESENTE, SIN
> POBLAR):** el backend expone los métodos `external_ids_for(paper_id)` y `all_external_ids()`
> (`src/bib2graph/backends/base.py`) para registrar, 1↔N, los IDs que cada motor (OpenAlex, Semantic
> Scholar, …) asignó al mismo paper, unificados por el DOI como ancla. **Hoy esta tabla NO se puebla
> todavía**: su consumo —el cruce/deduplicación **cross-motor**— está diferido a la llegada del 2º
> motor (follow-up [#120](https://github.com/complexluise/bib2graph/issues/120)). La identidad y la
> dedup actuales se resuelven solo por el `id` canónico (DOI primero; ver §1.1 *Identidad*).

> **TARGET (capa base, ADR [0023](decisiones/0023-capa-constants-modelos-schema.md), Hito R1):** los
> nombres de columna salen de `bib2graph.constants.Col(StrEnum)` y `curation_status` de
> `CurationStatus(StrEnum)` (fuente única; matan los string-literals dispersos). `PaperRow` (Pydantic)
> es la **única** definición de fila y `CORPUS_SCHEMA` (Arrow) se **deriva/verifica** de ella (no
> duplicada a mano). El evento de `provenance` es un **`ProvenanceEvent(BaseModel)`** con parseo que
> **falla ruidoso** ante JSON corrupto. Se **mantiene** "`Paper`/`Author`/… = vistas derivadas, no
> tipos".
>
> **AS-BUILT (identidad vs procedencia, ADR [0017](decisiones/0017-reproducibilidad-historia-snapshot.md)
> enmendado, Hito R2 ✅ 2026-06-16):** el `corpus_hash` (D2) se computa **solo sobre contenido
> bibliográfico**, **excluyendo** `provenance`/timestamps (la procedencia audita, no identifica;
> `curation_status` **sí** entra, es contenido curado). Por eso dos corridas que aceptan los mismos
> ids dan el **mismo** hash. `accept`/`reject` (y los filtros `apply_filter`/`apply_filters`) **reciben
> el instante** (`decided_at`) inyectado desde la frontera CLI; el núcleo usa `datetime.now(UTC)` solo
> como **fallback de librería** cuando no se inyecta `decided_at` (fuera de la identidad, no rompe la
> reproducibilidad). *(El §1.2 abajo conserva la nota histórica del AS-BUILT v0.2 roto.)*

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

**`id` estable y determinista** (ADR [0013](decisiones/0013-identidad-hash-merge-corpus.md), D1;
precedencia invertida por ADR [0036](decisiones/0036-identidad-source-id-agnostica-doi-ancla.md), D1'):
`id = f"{prefix}:{sha256(valor)[:16]}"` con precedencia `doi` normalizado (`doi:`) → `source_id`
(`src:`) → `title+year` (`tt:`). El **DOI es el ancla universal e interoperable entre motores** (un
paper con DOI tiene el mismo `id` venga de OpenAlex, de Semantic Scholar o de un `.bib`); `source_id`
es el fallback para papers sin DOI, antes de caer a `title+year` (frágil). El mismo paper produce el
mismo `id` entre corridas; es la base de la dedup en `merge` y en la biblioteca viva.

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

    def scoped(self, scope: str) -> "Corpus":
        """Vista PURA por estado de curación: devuelve un Corpus NUEVO con el subconjunto de filas
        (no muta el original). Valores: `'all'` = corpus completo; `'accepted'` = `is_seed == True`
        OR `curation_status == 'accepted'`; `'seeds_only'` = `is_seed == True`. Scope inválido →
        `ValueError` accionable. Determinista: dos llamadas con el mismo scope dan corpora con el
        mismo `corpus_hash` (subset estable). `'all'` reusa el backend; los otros materializan el
        filtro en un `InMemoryBackend`. Lo usa `b2g build --scope` (vocab CLI `seeds`→`seeds_only`;
        alias deprecado `--corpus-scope` usa este vocab interno) para sellar el hash del
        corpus FILTRADO. Issue #56 / #159. **NO confundir con `NetworkSpec.scope`** (§10): aquel es un
        eje por-red (`full`/`seeds_only`) sobre `is_seed`; `scoped()` filtra el corpus entero por
        curación antes de proyectar."""

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
    def accept(self, ids: list[str], *, by: str = "human", decided_at: datetime | None = None) -> "Corpus":
        """Marca papers como 'accepted' y AGREGA un evento al log de provenance. Devuelve Corpus nuevo.
        `decided_at` se inyecta desde la frontera CLI (Hito R2, ADR 0017); `None` → el backend usa
        `datetime.now(UTC)` como fallback de librería. El `decided_at` NO entra al `corpus_hash`."""
    def reject(self, ids: list[str], *, by: str = "human", decided_at: datetime | None = None) -> "Corpus": ...
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
  el contenido de la tabla, nunca campos volátiles del Manifest (D2). **AS-BUILT (Hito R2, ADR 0017
  enmendado, ✅ 2026-06-16):** el hash **excluye `provenance`/timestamps** (identidad = contenido
  bibliográfico; la procedencia audita, no identifica) pero **incluye `curation_status`** (contenido
  curado). *(Histórico v0.2 roto: incluía `provenance` con timestamps → rompía la reproducibilidad
  bit a bit; R2 lo corrigió.)* Ver la nota AS-BUILT de §1.1.
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
- **R5 — `lib_version` desconocida = `"unknown"`** (cambio de comportamiento): si
  `importlib.metadata` no resuelve la versión instalada de `bib2graph`, el fallback es **`"unknown"`**,
  no `"0.0.0"`. Una versión inventada entraba al `Manifest` y mentía sobre la reproducibilidad; `"unknown"`
  es honesto.
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
    def apply_curation(self, ids: list[str], *, action: str, by: str,
                       decided_at: str | None = None) -> "TabularBackend": ...
        # accept/reject: AGREGA un evento al log `provenance` (action/decided_by/decided_at).
        # `decided_at` (ISO8601 UTC) inyectado desde la frontera (Hito R2, ADR 0017);
        # `None` → fallback `datetime.now(UTC)` (uso como librería). NO entra al corpus_hash.
    def filter_view(self, view: Literal["seeds", "candidates", "accepted"]) -> pa.Table: ...
        # Vista filtrada (is_seed / curation_status == 'candidate' | 'accepted').
    def corpus_hash(self) -> str: ...        # D2, order-independent, sobre el contenido
    def __len__(self) -> int: ...
    def __eq__(self, other: object) -> bool: ...   # igualdad canónica por corpus_hash (D2)

    # AS-BUILT #54 (2026-06-17): tabla hermana `referenced_but_not_fetched` (append-only, par de
    # loop_state_log) — los IDs que el backward chaining OBSERVA sin materializar en el corpus (§5).
    # FUERA de la tabla `corpus` y del corpus_hash (son estado, no contenido; ADR 0017).
    def add_referenced_refs(self, ref_ids: list[str], *, cycle_round: int) -> "TabularBackend": ...
        # Registra IDs observados (idempotente por existencia de `ref_id`; observed_at = now() del backend).
    def referenced_refs_count(self) -> int: ...    # nº de IDs observados distintos
    def referenced_refs(self) -> pa.Table: ...     # los IDs observados (ref_id, cycle_round, observed_at)
```

> **AS-BUILT #54 (2026-06-17) — `referenced_but_not_fetched`.** El backward chaining (§5) dejó de
> crear filas-fantasma `[candidate:W...]` en el `corpus`. Sus IDs observados se registran en esta
> tabla append-only (hermana de `loop_state_log`), implementada por `DuckDBBackend` (DDL + migración
> liviana + copia en snapshot/`_clone`) e `InMemoryBackend`. **No entra al `corpus_hash`** (tabla
> aparte, no columna del corpus → no toca el schema de [ADR 0013](decisiones/0013-identidad-hash-merge-corpus.md);
> coherente con [ADR 0017](decisiones/0017-reproducibilidad-historia-snapshot.md): es estado, no
> contenido). Materializar un observado a fila real vía `fetch_works_by_ids` (#55) está diferido a #71.

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

    def seed(self, query: str, *, exclude: list[str] | None = None) -> "SeedResult":
        """Siembra desde una ecuación de búsqueda. Devuelve el Corpus + la query ejecutada
        y el reporte de traducción (qué mapeó, qué se aproximó, qué se descartó).
        `exclude` (negaciones quirúrgicas, opcional): cada término se inyecta DENTRO de la
        única expresión `title_and_abstract.search:((query) AND NOT "<término>")` (el campo
        NO se repite) y se REPORTA en el
        translation_report (query visible, ejercicio consciente). Las comillas internas del
        término se sanean. Ignorado con `native=True` (query cruda). Una Source que no siembra
        por ecuación (p. ej. BibtexSource) lanza NotImplementedError."""
    def load(self, path: str) -> Corpus:
        """Siembra desde un archivo (export/pearls). is_seed=True."""

class SeedResult(BaseModel):
    corpus: Corpus
    executed_query: str        # la query OpenAlex EXACTA ejecutada (consciencia, ADR 0007)
    translation_report: list[str]   # mapeos limpios / aproximados / descartados (p. ej. NEAR no soportado) + negaciones aplicadas (exclude, #30)
```

**Capa declarativa de la ecuación — `EquationSpec` + `load_equation_spec`** (Ciclo 9a, ADR
[0030](decisiones/0030-ecuacion-declarativa-corpus-ejemplo.md); `src/bib2graph/sources/equation.py`).
Empaqueta los parámetros de `b2g seed` en un YAML versionable (el artefacto "qué se busca"), **análogo
a `NetworkSpec`/`load_specs`** del Hito 9. Clave raíz **`equation:`** (objeto, **no** lista — una
ecuación por archivo). El modo `b2g seed --spec equation.yaml` (§convenciones CLI) carga la spec y la
mapea a `run_seed`; equivale a `--equation` + flags.

```python
class EquationSpec(BaseModel):
    """Configuración declarativa de una ecuación de búsqueda (ADR 0030).
    model_config = ConfigDict(extra="forbid"): campo desconocido en el YAML → error accionable."""
    query: str                          # requerido (no vacío) — la ecuación de búsqueda
    exclude: list[str] = []             # #30 — AND NOT "…" DENTRO de la search:((query) AND NOT "…")
    max_results: int | None = None      # #14 — tope (None → default del source, 200)
    native: bool = False                # passthrough crudo a OpenAlex (sin traducción)
    min_year: int | None = None         # DECLARADO, AÚN NO FILTRA (ver nota)
    max_year: int | None = None         # DECLARADO, AÚN NO FILTRA (ver nota)

def load_equation_spec(path: str | Path) -> EquationSpec:
    """Carga/valida la EquationSpec desde un YAML (clave raíz `equation:`).
    Errores accionables (mismo patrón que `load_specs`): YAML malformado → ValueError;
    clave raíz ausente → ValueError; campo desconocido/tipo incorrecto → ValueError
    citando archivo + campo. Importación perezosa de PyYAML."""
```

> **`min_year`/`max_year`: filtran de verdad (Ciclo 10, 2026-06-17).** En el corte 9a estos campos
> estaban en `EquationSpec` pero `OpenAlexSource.seed` no los aplicaba; el **Ciclo 10 los conectó**:
> `_translate`/`seed` agregan `from_publication_date:<min_year>-01-01` y/o
> `to_publication_date:<max_year>-12-31` al `filter` de OpenAlex (sintaxis idiomática de rango,
> concatenada con coma) y lo reportan en el `translation_report`. Expuestos además como flags
> **`--min-year`/`--max-year`** en `b2g seed --equation` (paridad 1:1 con el YAML); en `--native` no
> se aplican. Todos los campos (`query`/`exclude`/`max_results`/`native`/`min_year`/`max_year`) mapean
> 1:1 al `run_seed`: la capa declarativa empaqueta los flags ya soportados.

| Implementación | Estado | Notas |
|----------------|--------|-------|
| `OpenAlexSource` | **v1 (construido, Hito 4)** | **Referencia/backbone**, sobre `httpx`. Entrega mínimo + enriquecimiento: refs inline + afiliaciones per-autor + instituciones; `cited_by_id` queda **diferido** al chaining/`Enricher` (no se trae en el seed). Traducción **passthrough** —envuelve la ecuación en `title_and_abstract.search:(...)` y **reporta** los límites WoS (NEAR/comodín/tags) sin traducirlos; el traductor WoS→OpenAlex es v0.2. Flag `native=True` (query cruda). **Negaciones (`exclude`, #30):** `seed(..., exclude=[...])` y `_translate(exclude=...)` inyectan cada `AND NOT "<término>"` **DENTRO** de la única expresión `title_and_abstract.search:((query) AND NOT "<término>")` (el campo **no se repite**; el filtro de año queda como predicado separado por coma **fuera** de la expresión `search`) y lo **reportan en el `translation_report`** (query visible); comillas internas saneadas; **ignorado con `native=True`**. *(Sintaxis **validada contra OpenAlex real** vía test `@pytest.mark.network`, 2026-06-17: la forma vieja con el campo repetido devolvía 0 resultados.)* Credenciales inyectadas (arg → `OPENALEX_API_KEY` → `~/.openalex/credentials` → polite pool; ADR 0012). Cursor paging con tope `max_results` (param de `__init__`, default 200; **`b2g seed --max-results INT`** lo propaga para exploración con muestras chicas, Nota 09 B1). Puebla `Manifest.openalex_version` (header o fecha del fetch; ADR 0017). `transport` inyectable (tests con `MockTransport`, sin red en CI). |
| `BibtexSource` | **v1, secundaria (construido, Hito 4)** | Sembrar desde *pearls* vía `load()`. Extra **`[bibtex]`** (import perezoso de `bibtexparser`, ADR 0005); acceso defensivo (fix del bug T1: campos faltantes sin `KeyError`). Mínimo universal. `seed()` lanza `NotImplementedError` (BibTeX no siembra por ecuación). **R5:** un `.bib` con error de parseo grave → `ValueError` accionable (antes lo tragaba en silencio); un `.bib` sin entradas válidas / con entradas omitidas por falta de título → `UserWarning` (no no-op silencioso). Carga bulk con `from_arrow`. |
| `ScieloSource` / `RedalycSource` / `LaReferenciaSource` | futuro | Fuentes regionales, mínimo universal. Declaradas, no implementadas (ADR 0018). |
| `RisSource` / `CsvSource` | futuro | No implementados. |

> **AS-BUILT #78 (2026-06-17) — el forward materializa metadata REAL (ADR
> [0020](decisiones/0020-metodo-forrajeo-scent-filtros-reject.md) §AS-BUILT #78).** Se agrega
> `OpenAlexSource.fetch_citing_batch_with_works` (abajo): el forward chaining (§5) deja de persistir
> placeholders `[candidate:W...]` y materializa filas reales conservando la metadata que
> `fetch_citing_batch` ya traía y descartaba (**cero red extra**). `fetch_citing_batch` queda intacto
> (thin wrapper). Gate verde, 645 tests.

**Capacidades de `OpenAlexSource` fuera del Protocol `Source`** (específicas del backbone, no
contrato universal; las consumen el `Forager` y el `Enricher`):

- **`fetch_citing(openalex_id) -> list[dict]`** (singular, Forager forward chaining): `GET
  works?filter=cites:`, con retry/backoff ante 429/5xx (R5). No cambió en el Hito 8.
- **`fetch_citing_batch(ids, *, max_per_paper, since: date | None = None) -> dict[seed_id, list[citer_id]]`** (Hito 8b, ADR
  [0025](decisiones/0025-enricher-cocitacion-openalex.md)): trae los citantes de un conjunto de
  semillas **batcheando por OR** (`cites:W1|W2|...`, lotes ≤50), pagina por cursor y **atribuye
  página a página** (cruza `referenced_works` del citante con el set objetivo, por short-id). **`since`
  (#158, forrajeo incremental):** filtra los citantes a los publicados desde esa fecha agregando
  `,from_publication_date:<since.isoformat()>` al `filter` de OpenAlex (lo usa `chain --since`). Con
  **presupuesto por semilla**: corta la paginación cuando **todas** las semillas del lote alcanzan
  `max_per_paper` (acota el *fetch*, no solo la columna; **sin starvation** entre semillas; mata el
  N+1 diferido de R5). Lo consume el `OpenAlexEnricher` (§3) para poblar `cited_by_id`. **AS-BUILT
  #78 (2026-06-17): firma y contrato INTACTOS** —sigue devolviendo solo el mapeo de atribución— pero
  internamente es un **thin wrapper** sobre `_fetch_citing_pages` que **descarta `works_map`** (la
  metadata que ya viaja en la misma request). El Enricher 8b no cambia.
- **`fetch_citing_batch_with_works(ids, *, max_per_paper, since: date | None = None) -> tuple[dict[seed_id, list[citer_id]], dict[citer_id, work]]`**
  (#78, 2026-06-17, Forager forward chaining; `since` #158): la **variante que conserva la metadata**. Misma red,
  mismo batcheo/atribución/presupuesto que `fetch_citing_batch` (comparten `_fetch_citing_pages`),
  pero devuelve además el `works_map` (`citer_id → work JSON con _FIELDS`) que `fetch_citing_batch`
  tira. **Cero red extra**: la metadata ya venía en la query de citantes y antes se descartaba. La
  consume `Forager._fetch_forward` para materializar filas REALES (título/año/autores) en vez de
  placeholders `[candidate:W...]`. Ver §5 y ADR
  [0020](decisiones/0020-metodo-forrajeo-scent-filtros-reject.md) §AS-BUILT #78.
- **`fetch_dois_for(ids) -> dict`** (Hito 8a): resuelve `references_id`→DOI batcheando por OR (lotes
  ≤100, `select=id,doi`).
- **`fetch_works_by_ids(ids) -> Corpus`** (#55): materializa works arbitrarios desde sus IDs OpenAlex,
  batcheando por OR (`openalex_id:W1|W2|...`, lotes ≤100, reusa `_fetch_batch_select`). Devuelve un
  `Corpus` con `is_seed=False`, `curation_status=CANDIDATE`, `provenance[action="fetched_by_id"]`. IDs
  inexistentes se **omiten sin error**; orden **determinista** (filas ordenadas por `id` canónico);
  lista vacía → `Corpus` vacío **sin tocar la red**. Es el primitivo que materializa lo observado por
  el backward chaining (ver #54). Reusa `_work_to_row` parametrizado (`is_seed`/`action`), que centraliza
  el mapeo JSON→Arrow para `seed`/`fetch_citing`/`fetch_works_by_ids`/forward chaining (sin duplicar).
  **AS-BUILT #78 (2026-06-17): `_work_to_row` ganó `chaining_hop: int | None = None` y
  `source_tag: str = "openalex"`** (defaults backward-compat → los callers viejos no cambian); el
  forward chaining lo invoca con `chaining_hop=1, source_tag="chaining:forward"` para materializar
  citantes reales. *(Validado contra OpenAlex real vía test `@pytest.mark.network`.)*

**Reporte de cobertura/calidad** (concepto declarado, concreto **v0.2+**; ADR 0018): por
seed/source, mide % de refs resueltas, % con DOI, distribución idioma/región y completitud del
enriquecimiento. Alimenta el juicio humano de **cuándo cambiar de Source** y acota la
incertidumbre del ranking por *information scent* sobre datos parciales. Se declara como contrato
en v0.1 (función pura sobre `pa.Table`), sin cablearse vacío (lección 5).

### 2.1 Convención `examples/` — corpus de ejemplo commiteado (AS-BUILT #33 / 9b · CLI-puro Ciclo B, 2026-06-17)

`examples/` es la **única** excepción al `.gitignore` de datos de usuario (ADR
[0030](decisiones/0030-ecuacion-declarativa-corpus-ejemplo.md)): un corpus real, curado y reducido
(CC0/OpenAlex) commiteado al árbol para servir de **caso real reproducible sin red** (gate #33 →
epic GUI #34). Reglas:

- **Un ejemplo = una carpeta de propósito ÚNICO** (`examples/<nombre>/`), autocontenida; no se
  mezclan tipos de artefacto. Cada carpeta lleva:
  - **`corpus.parquet`** — corpus curado y congelado (con `decision`/`curation_status`/`is_seed`
    ya marcados), schema canónico `CORPUS_SCHEMA`. **Parquet/CSV, NUNCA `.duckdb`** (la biblioteca
    viva es estado mutable no determinista; el parquet es export sellado y diff-friendly, ADR
    0006/0009/0017).
  - **`equation.yaml`** — la ecuación de procedencia (cargable con `EquationSpec`, §2). Documenta
    "de qué búsqueda salió este corpus"; **no** es el comando del gate.
  - **`curacion.csv`** *(cuando el ejemplo pasa por curación)* — las decisiones de curación
    congeladas que `b2g curate apply` consume: **receta determinista** de curación (aplicarlo
    al corpus sembrado produce el mismo estado, independiente de cuándo se corra).
  - **`README.md`** — qué demuestra y con qué comandos se arma/reproduce. **Es la procedencia:**
    la **receta CLI** documentada (armado con red + reproducción offline), no un script.
- **Cómo se restaura:** `b2g snapshot restore --from-corpus examples/<nombre>/corpus.parquet`
  (§`snapshot restore`; #163/ADR 0038 — el verbo suelto `restore` sigue funcionando como alias
  deprecado, retiro #165) rehidrata el corpus **sin red** en el `library.duckdb` de un workspace
  temporal, preserva la curación y transiciona a `FILTERED`; luego `build` → `networks`/`clusters`
  corren localmente.
- **`.gitignore`:** `!examples/` trackea el ejemplo; `examples/**/*.duckdb` lo protege de que un
  store vivo se cuele. El resto de la política de datos de usuario no cambia.
- **Ejemplos existentes:**
  - **`examples/valoraciones/`** (Ciclo B, AS-BUILT 2026-06-17): **~80 filas** (70 `candidate` +
    10 `accepted` enriquecidos), armado **100% por CLI** (sin script): `seed --spec equation.yaml`
    (`max_results: 80`) → `curate apply curacion.csv` → `enrich --max-citing 25` → `snapshot create`
    (receta histórica; en la superficie 0.10.0 la co-citación corre en `build --max-citing 25`, ya que
    `enrich` quedó deprecado — #162).
    **Co-citación presente** (rala) + coupling/author/institution/keyword sustanciales. Verificado por
    el gate R2 `tests/unit/test_example_r2_gate.py` (`corpus_hash` estable + comunidades Louvain
    estables entre corridas; piso `n>=50`, las 5 redes con datos). Se rehidrata con
    `b2g snapshot restore --from-corpus`. Procedencia = receta CLI del README + `equation.yaml` + `curacion.csv`.
  - **`examples/bibtex/`** (Ciclo 10, AS-BUILT 2026-06-17): un `sample.bib` chico (10 entradas, con
    variedad deliberada de campos faltantes para ejercitar el parser defensivo) + `README.md` con la
    receta 100% CLI (`b2g init` → `b2g seed --from-bib examples/bibtex/sample.bib` → `b2g build`).
    Demuestra el segundo camino de seed (BibTeX local, sin red). El `.bib` queda trackeado por la
    excepción `!examples/` ya existente.

---

## 3. Costura `Enricher` — señal extra (opt-in, ya NO estructural)

Con OpenAlex como backbone, refs y citantes **ya vienen en el corpus** (ADR 0007). El `Enricher`
queda opt-in para **resolver `references` a DOI** y el **segundo nivel de fetch** (poblar
`cited_by_id` ≡ citantes compartidos — ver decisión F en ADR
[0025](decisiones/0025-enricher-cocitacion-openalex.md)) que habilita la **co-citación
end-to-end** (Hito 8 completo). El `Enricher` vive en el **núcleo,
sobre OpenAlex** (ADR 0025, decisión B), **no** en el extra `[s2]` (ese DoD pre-giro queda superado;
`[s2]` se reserva para un futuro `SemanticScholarEnricher` de señal adicional).

> **Superficie CLI (#162, ADR 0038):** el `Enricher` **ya no se invoca por un verbo propio**. La pasada
> refs→DOI corre automática en **`chain`** y la de co-citación (`cited_by`) en **`build`** (cuando hay
> aceptadas); el helper único es `cli/_enrich.py::enrich_corpus`. El verbo `b2g enrich` sobrevive como
> **alias deprecado** (retiro 0.11.0). Ver §convenciones CLI (§`enrich`, §`build`, §Avisos de deprecación).

```python
@runtime_checkable
class Enricher(Protocol):
    """Config (API keys) INYECTADA, nunca embebida. Sin ramas muertas. Rate limit/reintentos
    sin perder papers. Idempotente. NO transiciona el CycleState (ortogonal al lazo, ADR 0025)."""
    def enrich(self, corpus: Corpus) -> Corpus: ...
```

| Implementación | Estado | Aporta |
|----------------|--------|--------|
| `OpenAlexEnricher` | **v1, opt-in (Hito 8 = Ciclos 8a + 8b construidos)** | `enrich(corpus)` hace **2 pasadas**. **8a (refs→DOI):** reúne los `references_id` únicos, los resuelve **batcheando por OR** (lotes ≤100, `openalex_id:W1\|W2\|...`, `select=id,doi`) y rellena `references_doi` por lookup; registra `EnricherRef(name="openalex_references_doi", …)` en el `Manifest` (idempotente: reemplaza por nombre, no duplica). **8b (co-citación):** para las **semillas aceptadas** (`is_seed=True AND curation_status=accepted`) trae sus citantes vía `OpenAlexSource.fetch_citing_batch` (§2) y **mergea los `openalex_id` de los citantes en `cited_by_id`** (unión idempotente). **NO** materializa citantes como filas (no crece el corpus; decisión A). Constructor con **`max_citing_per_paper`** (tope **por semilla**, acota el fetch). Frontera: el Source hace I/O + atribución + acotamiento; el Enricher **solo une**. |
| `SemanticScholarEnricher` | futuro | señal de citas adicional (reserva del `[s2]`, no estructural) |
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
`corpus_hash`, `__len__`, `__eq__` y —AS-BUILT #54 (2026-06-17)— `add_referenced_refs(ref_ids, *,
cycle_round)`/`referenced_refs_count()`/`referenced_refs()` (tabla hermana append-only
`referenced_but_not_fetched`, fuera del `corpus_hash`; §1.4 + §5). El `DuckDBBackend` lo implementa en
SQL (Hito 3); el `Store` de abajo es la costura de persistencia/intercambio **externa**, distinta del
backend del `Corpus`.

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
    def persist(self, corpus: Corpus) -> None: ...       # merge idempotente por id (upsert-concat D3) en la biblioteca viva
    def persist_replace(self, corpus: Corpus) -> None: ...# DELETE+INSERT de la tabla `corpus`: el estado en disco
                                                          # queda EXACTAMENTE el corpus dado; preserva las tablas
                                                          # hermanas (loop_state_log, referenced_but_not_fetched)
    def load(self) -> Corpus: ...                         # corpus acumulado, respaldado por el DuckDBBackend
    @property
    def backend(self) -> "DuckDBBackend": ...            # acceso al backend para las extensiones de abajo
```

> **`persist_replace` vs `persist` (#88, ADR [0031](decisiones/0031-preprocesamiento-automatico-en-ingesta.md)).**
> La **ingesta automática** (`seed`/`seed_from_bib`/`chain`/`restore`) y la pasada **`build
> --thesaurus`** (#164) persisten
> con **`persist_replace`** (→ `DuckDBBackend.overwrite_corpus`, DELETE+INSERT reasignando `_seq`
> desde 0, ADR 0024), porque ya tienen el corpus **completo, normalizado y deduplicado** en memoria y
> el upsert-concat D3 (`persist`) **reintroduciría** las variantes que el dedup cross-biblioteca acaba
> de colapsar. **`persist`/upsert queda intacto** para el resto de los llamadores (caso "mismo paper
> desde dos fuentes", D3). Ambos preservan las tablas hermanas.

**Extensiones del `DuckDBBackend`, FUERA del Protocol `Store`/`TabularBackend`** (se acceden vía
`store.backend.…`): son específicas de DuckDB y no parte del contrato genérico:

```python
class DuckDBBackend:
    # ... cumple TabularBackend (§1.4) ...
    def loop_state(self) -> "CycleState | None": ...     # estado actual del ciclo (None si no hubo transiciones)
    def loop_round(self) -> int: ...                     # contador de ronda (0 sin estado; 1 primera; 2+ re-sembrados)
    def set_loop_state(self, state: "CycleState", *, cycle_round: int | None = None) -> None: ...
                                                         # registra una transición + ronda (log append-only, permisiva)
    def query(self, sql: str) -> pa.Table: ...           # consulta SQL de SOLO lectura sobre el corpus
```

**El ciclo es un concepto de dominio puro** (`bib2graph.cycle`, **AS-BUILT R3, 2026-06-16**); el
backend **solo lo persiste**:

```python
# bib2graph/cycle.py — dominio puro, sin DuckDB (ADR 0016 enmendado, R3)
class CycleState(StrEnum):
    SEEDED = "SEEDED"; FORAGED = "FORAGED"; FILTERED = "FILTERED"; BUILT = "BUILT"; MONITORED = "MONITORED"

def apply_transition(state: CycleState | None, action: str, round: int) -> tuple[CycleState, int]: ...
    # reseed → (SEEDED, round+1); seed/chain/filter/build/monitor → estado de cadena, misma ronda
def available_transitions(state: CycleState | None) -> list[str]: ...   # transiciones de ciclo desde el estado
CURATION_ACTIONS: list[str] = ["accept", "reject"]                      # transversal: siempre disponible, no transiciona
```

El estado + la **ronda** se persisten en `loop_state_log` (append-only; estado actual = última fila;
columna `round`); las transiciones son **permisivas** (ADR 0016: no se bloquea ningún salto). `reseed`
es de **primera clase** (loop-back a `SEEDED` + ronda++, acumula sobre lo curado); `seed.py` lo cablea
cuando hay estado previo. **Fuente única de verdad:** `chain`/`filter`/`build` derivan su destino de
`apply_transition`, no de un literal. **`MONITORED`** es **alcanzable** vía **`b2g chain --since`**
(#158, forrajeo incremental; el alias deprecado `b2g monitor` delega), que dispara
`apply_transition(state, "monitor", round)` (paso 8 del ciclo).
El comando `b2g status` consume `loop_state()`/`loop_round()`/`available_transitions()` y expone
`curation_available`/`round` (ver §convenciones CLI).

> **Alias `LoopState` retirado (cleanup pre-v0.3):** el código usa **solo `CycleState`** (de
> `bib2graph.cycle`). El alias transicional `LoopState = CycleState` de `backends/duckdb.py` **se
> eliminó** (también de `stores/duckdb.py`); los call-sites migraron a `CycleState`.

> **Carga perezosa (PEP 562):** `DuckDBBackend` y `DuckDBStore` se exponen vía `__getattr__` en
> `bib2graph/__init__.py`, de modo que **`import bib2graph` NO importa `duckdb`** (el núcleo
> permanece puro y testeable sin DuckDB). Solo `bib2graph.DuckDBBackend` / `bib2graph.DuckDBStore`
> cargan el módulo bajo demanda. `CycleState` (y su alias `LoopState`) y `StoreLockedError` se
> importan desde `bib2graph.backends.duckdb` (o `bib2graph.stores.duckdb`); `bib2graph.cycle`
> (`CycleState`/`apply_transition`/`available_transitions`/`CURATION_ACTIONS`) es **núcleo puro**, sin
> DuckDB.

---

## 5. Núcleo — Forrajeo / chaining (asistencia algorítmica, SIN IA — construido, Hito 5 + R4)

> **AS-BUILT R4 (2026-06-16) — ADR [0020](decisiones/0020-metodo-forrajeo-scent-filtros-reject.md)
> enmendado / [0022](decisiones/0022-producto-sin-ia-generativa.md)):** el *information scent* es
> **estructura bibliométrica determinista** que consume el primitivo público `collect_item_to_papers`
> de los proyectores (§7), **sin LLM ni embeddings**. El forrajeo (costura) **depende del núcleo de
> proyección** (puro), nunca al revés. El producto **no usa IA generativa**.
> `explain_candidate`/`foraging/explain.py`/`[llm]` quedaron **eliminados**.

> **AS-BUILT #54 (2026-06-17) — ADR [0020](decisiones/0020-metodo-forrajeo-scent-filtros-reject.md)
> §AS-BUILT #54:** el backward chaining **deja de persistir placeholders** en el corpus. Los IDs
> observados salen por `RankedCandidates.observed_refs` y se persisten en la tabla hermana
> `referenced_but_not_fetched` (§4), **fuera del `corpus_hash`** (arregla la contaminación previa).
> El **forward arrastra el mismo footgun** (placeholder de título), abierto como **#78** — NO está
> limpio. Materializador on-demand diferido a #71. Gate verde, 636 tests.

> **AS-BUILT #78 (2026-06-17) — ADR [0020](decisiones/0020-metodo-forrajeo-scent-filtros-reject.md)
> §AS-BUILT #78:** el **forward chaining ya NO persiste placeholders** `[candidate:W...]` — materializa
> **filas REALES** (título/año/autores) con la metadata que `fetch_citing_batch` ya traía de la red y
> descartaba (opción A1, **cero red extra**, vía el método nuevo `fetch_citing_batch_with_works`, §2).
> `_build_forward_candidate_row` eliminado. **Asimetría deliberada** (no incoherencia): el backward
> *observa sin materializar* (refs numerosas, no curadas, sin metadata local → `referenced_but_not_fetched`),
> el forward *materializa* (citantes pocos, acotados por cap, **se curan**, metadata ya en la request).
> Regla común: **el corpus nunca contiene placeholders**. Con esto, el materializador on-demand #71
> queda **solo para backward**. Gate verde, **645 tests**, verifier PASA.

El *information scent* es **estructura bibliométrica de cita con el corpus** (ADR
[0020](decisiones/0020-metodo-forrajeo-scent-filtros-reject.md), AS-BUILT R4). Es una **función pura**
sobre el primitivo `collect_item_to_papers` (índice `{ref → corpus-papers que lo citan}`):

- **Backward** (puro, local): scent = **fuerza de co-citación con el corpus** = nº de corpus-papers
  que listan al candidato en `references_id` (cuántos corpus-papers co-citan al candidato). No toca la
  red (las referencias ya vienen en el corpus tras el seed).
- **Forward** (requiere red): scent = **fuerza de citación directa al corpus** = nº de corpus-papers a
  los que el candidato cita directamente (señal primaria, robusta: siempre > 0 para un citante real).
  Exige traer los citantes vía `source.fetch_citing(...)` (ver abajo). El acoplamiento bibliográfico
  queda como señal secundaria. *(El AS-BUILT inicial midió **acoplamiento puro** y degenera a 0 con
  referencias ralas; se **corrigió a citación directa dentro de R4** — `compute_forward_scent` calcula
  `forward_score(Y) = |{ref ∈ Y.references_id : ref ∈ corpus_ids}|` y emite con `direct > 0`. Ver ADR
  0020 AS-BUILT.)*
- **Centralidad** del candidato: **diferida** (viz); el DoD "y/o" se cumple con
  co-citación + citación-directa.

El ranking es descendente por scent con **desempate por `id` ascendente** (estable ante cualquier
`PYTHONHASHSEED`).

```python
Direction = Literal["backward", "forward", "both"]   # bib2graph.foraging.Direction

class Forager:
    """Orquesta el chaining sobre un Source, rankeando candidatos por *information scent*
    bibliométrico (co-citación backward / citación directa forward, ADR 0008/0020/0022).
    El scent consume el primitivo de proyectores. Solo el Forager toca la red; el núcleo
    de scent es puro."""
    def __init__(self, source: Source, *, depth: int = 1, max_candidates: int | None = None,
                 max_citing_per_paper: int = 50) -> None:
        """depth=1 por defecto; depth>1 lanza NotImplementedError (futuro v0.3+).
        max_candidates = tope configurable del ranking (None = sin límite).
        max_citing_per_paper = tope de citantes POR SEMILLA en el forward batcheado (default 50;
        acota el fetch vía fetch_citing_batch; CLI `--max-citing`). AS-BUILT #21 (2026-06-16)."""

    def preview(self, corpus: Corpus, *, direction: Direction = "both") -> "GrowthPreview":
        """'Esta expansión sumaría ~N papers' SIN traerlos. Opera SOLO localmente, SIN red.
        Backward: estimación EXACTA local desde references_id. Forward: NO estimable sin red
        (cited_by_id está vacío tras el seed) → estima el nº de SEMILLAS a forrajear (is_seed,
        SIN filtrar curation_status) con by_direction['forward']=0 y forward_requires_fetch=True;
        el conteo de citantes reales solo llega con chain(). NO muta el corpus."""

    def chain(self, corpus: Corpus, *, direction: Direction = "both",
              since: date | None = None) -> "RankedCandidates":
        """Computa candidatos (curation_status='candidate', is_seed=False) rankeados por scent.
        Devuelve SOLO los candidatos nuevos (no mergeados): el humano hace
        corpus.merge(ranked.corpus). NO muta el corpus de entrada. Sella Manifest.chaining.
        `since` (#158, forrajeo incremental): propaga a fetch_citing_batch(since=) →
        from_publication_date en OpenAlex; solo afecta el tramo forward. Lo usa `b2g chain --since`
        (transición a MONITORED)."""

class GrowthPreview(BaseModel):
    estimated_new: int             # total estimable localmente (forward=0 si requiere fetch)
    by_direction: dict[str, int]   # {'backward': N, 'forward': 0 si requiere fetch}
    direction: Direction
    forward_requires_fetch: bool = False   # True si se pidió forward/both → forward desconocido sin red

class RankedCandidates(BaseModel):
    corpus: Corpus                     # SOLO los candidatos nuevos (no mergeado con el corpus semilla).
                                       # Forward (#78): materializa filas con metadata REAL (título/año/
                                       # autores), NO placeholders — vía fetch_citing_batch_with_works.
                                       # Backward (#54): NO materializa filas — observa, ver observed_refs.
    ranking: list[tuple[str, float]]   # (id, information_scent), desc scent / asc id
    observed_refs: list[str] = []      # AS-BUILT #54 (2026-06-17): IDs observados por el backward SIN
                                       # materializarlos en .corpus (orden de ranking, respeta
                                       # max_candidates). El backward observa; el forward materializa.
                                       # b2g chain los persiste en `referenced_but_not_fetched` (§4),
                                       # fuera del corpus_hash. Materializar = diferido a #71.

# RETIRADO (ADR 0022): `explain_candidate` y el extra `[llm]` se ELIMINAN del producto.
# El producto no usa IA generativa. El "porqué" de un candidato lo explica la ESTRUCTURA
# VISIBLE (con qué del corpus se acopla/co-cita), no un LLM. Ver ROADMAP Hito R4.
# (En el AS-BUILT v0.2 existía como stub gateado en [llm]; la remediación lo borra.)
```

**Notas de contrato** (Hito 5, ADR [0020](decisiones/0020-metodo-forrajeo-scent-filtros-reject.md)):

- **Forward chaining requiere `source.fetch_citing_batch(ids, *, max_per_paper)`** (§2). **R5:** el
  **comando `chain` hace un pre-check `hasattr(source, "fetch_citing")`** y lanza `DependencyError`
  accionable (exit 3) si el source no lo soporta —el forager queda agnóstico de la capa
  CLI/`_errors`; un `AttributeError` genuino dentro del chaining ya no se disfraza de "source sin
  forward". **No se amplió el Protocol `Source`** (§2) — `fetch_citing`/`fetch_citing_batch` son
  capacidad de `OpenAlexSource`, no contrato universal. Una `Source` de solo-mínimo (ADR 0018) no
  habilita forward chaining.
- **AS-BUILT (#21, 2026-06-16) — forward chaining batcheado + cap por semilla, scope `is_seed`.** El
  `Forager.chain(direction="forward"/"both")` **ya no hace N+1** (`fetch_citing` por fila): **reusa
  `OpenAlexSource.fetch_citing_batch`** (§2 — batcheo OR ≤50 + presupuesto por semilla + retry/backoff),
  matando el N+1 de requests. El `Forager.__init__` toma **`max_citing_per_paper`** (tope de citantes
  **por semilla**, default **50**); el CLI lo expone como **`--max-citing`** en `b2g chain`. **El
  alcance del forward es `is_seed=True`** —**todas** las semillas sembradas, **SIN** filtrar por
  `curation_status`— porque el chaining corre **antes** de la curación (ciclo
  `SEEDED→FORAGED→…`→ curación transversal; las semillas nacen `candidate`; ADR
  [0020](decisiones/0020-metodo-forrajeo-scent-filtros-reject.md), Nota 09). **La restricción a
  semillas `accepted` NO es del Forager — es del `Enricher`** (Hito 8b, §3, post-curación). No
  confundir: el Forager expande la frontera (pre-curación, sobre `is_seed`); el Enricher pobla
  `cited_by_id` para la co-citación (post-curación, sobre `accepted`). *(El drift inverso —documentar
  el Forager forrajeando solo `accepted`— fue la causa del bug que este AS-BUILT cierra.)*
- **`preview` del forward sin red (#21):** estima el **nº de semillas a forrajear** (`is_seed`) sin
  emitir requests, manteniendo `forward_requires_fetch=True` (el conteo de citantes reales solo llega
  con `chain`). **`b2g chain --since`** (#158, ex `monitor`) usa este mismo forward batcheado.
- **`fetch_citing` (singular) con retry/backoff** ante 429/5xx (`_fetch_all_with_retry`: exponential
  backoff, 3 intentos) sigue disponible; el forward del Forager lo consume ahora vía la variante
  **batcheada** `fetch_citing_batch`.
- **AS-BUILT (#54, 2026-06-17) — el backward NO materializa stubs: observa sin contaminar.** El
  backward chaining **ya no crea filas-fantasma `[candidate:W...]` en el corpus** (revierte el
  comportamiento de Hito 5 — la promesa de "no contaminan" era **falsa**: los stubs llegaron a ser
  ~la mitad del corpus y entraban al `corpus_hash`; Notas 09/12). Los IDs observados por el ranking
  backward salen por **`RankedCandidates.observed_refs: list[str]`** (orden de ranking, respeta
  `max_candidates`) y `b2g chain` los persiste en la tabla hermana **`referenced_but_not_fetched`**
  (§4), **fuera** del `corpus` y del `corpus_hash`. La materialización on-demand (rehidratar un
  observado a fila real vía `fetch_works_by_ids`, #55) está **diferida a #71** (con #78 cerrado, #71
  queda **solo para backward**). El **forward sí materializa** filas en `.corpus` —y **con #78
  (2026-06-17) lo hace con metadata REAL** (título/año/autores), **ya no** con placeholders
  `[candidate:W...]`: la metadata viaja en la misma request de citantes (`fetch_citing_batch_with_works`,
  §2). Asimetría deliberada: el backward observa, el forward materializa (ver §AS-BUILT #78 arriba).
- **`preview` y `chain` no mutan** el corpus de entrada (semántica de valor).

---

## 6. Núcleo — `Preprocessor` + filtros PRISMA (v1 — construido, Hito 5; auto-ingesta #88)

> **Sincronizado con el preprocesamiento automático en la ingesta — #88 (AS-BUILT, 2026-06-18,
> ADR [0031](decisiones/0031-preprocesamiento-automatico-en-ingesta.md)):** `normalize` (+ el dedup
> fuzzy de §11) corre **automáticamente en cada ingesta** vía el helper de frontera
> `cli/_ingest.py::normalize_and_dedup` (sobre el corpus completo mergeado). `apply_thesaurus`, que
> requiere el mapeo curado del usuario, se expone (**#164, ADR 0038**) como el flag
> **`b2g build --thesaurus <archivo>`** —el verbo suelto `b2g thesaurus` **se retiró** (ya no existe ni
> como alias); ver §`build` y §Avisos de deprecación—. Ambos métodos aceptan `applied_at` inyectado
> desde la frontera (R2, ADR 0017).

```python
class Preprocessor:
    """Determinístico e idempotente. La parte fuzzy vive en §11 (ahora núcleo, no extra). Registra un
    PreprocRef en el Manifest por cada operación aplicada. `applied_at` se inyecta desde la frontera
    (R2): un único datetime.now(UTC) por invocación, igual que `decided_at` en curación."""
    def normalize(self, corpus: Corpus, *, applied_at: datetime | None = None) -> Corpus:
        """Normalización CONSERVADORA (decisión b=A): authors_id (lowercase + quitar acentos +
        colapso de espacios) y language (subtag ISO 639-1 primario). SIN fuzzy (eso es el dedup,
        §11), SIN columna de periodización. Idempotente. NO muta el corpus de entrada. Corre
        AUTOMÁTICAMENTE en la ingesta (helper `normalize_and_dedup`, ADR 0031)."""
    def apply_thesaurus(self, corpus: Corpus, thesaurus: dict | Path, *,
                        applied_at: datetime | None = None) -> Corpus:
        """Lee keywords_raw y SOBRESCRIBE keywords_id con los conceptos canónicos del thesaurus
        multilingüe CURADO (en/es/pt), dict canónico→aliases en JSON o Path a ese JSON.
        Determinista e idempotente (ADR 0011). SIN fallback semántico/LLM (ADR 0011 enmendado /
        0022): lo que no matchea queda fuera, sin inventar conceptos con un modelo. Paso EXPLÍCITO
        (flag `b2g build --thesaurus`, #164), NO automático: requiere el mapeo del usuario (ADR 0031)."""
```

**Filtros de inclusión/exclusión** (funciones puras, flujo PRISMA; ADR
[0020](decisiones/0020-metodo-forrajeo-scent-filtros-reject.md)):

```python
class FilterCriterion(BaseModel):
    field: Literal["year", "type", "language", "min_citations"]
    op: Literal["gte", "lte", "in", "not_in", "eq"]
    value: int | str | list[str]
    # year: gte/lte · type: in/not_in (sobre research_areas) · language: eq/in/not_in
    # min_citations: gte (sobre len(cited_by_id))

def apply_filter(corpus: Corpus, criterion: FilterCriterion) -> tuple[Corpus, FilterStep]: ...
def apply_filters(corpus: Corpus, criteria: list[FilterCriterion]) -> tuple[Corpus, list[FilterStep]]:
    """Encadena los criterios en orden y SELLA Manifest.filters con todos los pasos
    (reemplaza: una corrida = una secuencia PRISMA). Devuelve (corpus_final, [FilterStep, ...])."""
```

**Notas de contrato** (Hito 5, ADR [0020](decisiones/0020-metodo-forrajeo-scent-filtros-reject.md)):

- **Los filtros MARCAN `rejected`, NO borran** (decisión del PO): un paper excluido queda en la
  tabla con `curation_status='rejected'` vía `corpus.reject(...)` (con el criterio como
  `provenance`/`decided_by`), nunca se borra. Coherente con la biblioteca viva (ADR
  [0009](decisiones/0009-biblioteca-viva-duckdb.md), C4) y el `provenance` append-only (ADR 0013,
  D4): la exclusión es curación **reversible y auditable**.
- **Conteo PRISMA por paso**: cada `FilterStep` lleva `count_before`/`count_after` contando los
  papers **no-rejected** (candidate + accepted) antes/después del filtro.
- **`keywords_id` es post-thesaurus**: hasta que se corre `apply_thesaurus`, `keywords_id` no es
  autoritativa (puede estar cruda o vacía); los proyectores de co-ocurrencia de keywords (§7)
  deben correr **después** del thesaurus.
- **R5 — campo/operador desconocido LANZA** (cambio de comportamiento): un `FilterCriterion` con un
  `field` no soportado, o un `op` inválido para ese campo, ahora lanza `ValueError` accionable (lista
  los campos/operadores válidos). **Antes era un no-op silencioso** (`return True` → el criterio no
  filtraba nada, escondiendo el error). Esto endurece el flujo PRISMA (sin exclusiones perdidas en
  silencio).
- **Símbolos públicos del Hito 5** (`from bib2graph import ...`): `Forager`, `GrowthPreview`,
  `RankedCandidates`, `Preprocessor`, `FilterCriterion`, `apply_filters`. `apply_filter` (singular)
  se importa desde `bib2graph.filters`. *(`explain_candidate` **se elimina** en la remediación —
  ADR 0022, Hito R4: ya no es parte de la superficie pública.)*

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
- **Co-citación:** el `CoCitationProjector` **no cambia** (decisión F, ADR 0025): cuenta
  **`cited_by_id` compartido** = los **citantes compartidos** de la metodología (la frase "citantes
  con sus citas" ≡ `cited_by_id` compartido). Proyecta con scope `seeds_only`. La co-citación
  **completa es end-to-end** (Hito 8 ✅): `b2g enrich` (8b) puebla `cited_by_id` con el 2º nivel de
  fetch del `OpenAlexEnricher` (ADR 0007/0025), y `Networks.quick` la incluye cuando esa columna
  está poblada (§10).
- **Los proyectores siguen PUROS — NO setean atributos de nodo** (ADR 0014, AS-BUILT #25): producen
  un `nx.Graph` con **ids crudos** como nodos (`doi:…`, `I185261750`, un ORCID), **sin** `label`. La
  legibilidad (label + atributos) la inyecta la **capa `decorate` (§7.1)**, que es la **frontera**
  entre la proyección pura y el export/GUI. Esta separación es deliberada (ADR 0014).

---

## 7.1 Frontera — `decorate` (label legible + atributos de nodo, v1, AS-BUILT #25)

`bib2graph.networks.decorate` es la **capa de frontera** entre los proyectores puros (§7) y los
exportadores (§9) / la GUI. Los proyectores devuelven grafos con **ids crudos** como nodos y **sin
atributos**; `decorate` transforma esos ids en **labels legibles** e inyecta atributos de
curación/comunidad/centralidad. Cierra el hueco de la Nota 09 B3 (las redes salían con `id` crudo,
ilegibles en Gephi/VOSviewer/Cytoscape).

```python
LABEL_MAX_CHARS: int = 60   # tope del label de paper; título largo → truncado + "..."

def decorate_graph(graph: nx.Graph, table: pa.Table, kind: str, *,
                   communities: dict[Any, int] | None = None) -> None:
    """Inyecta label + atributos en los nodos del grafo IN-PLACE (no copia; el llamador/
    exporter copia si necesita preservar el original). No muta el corpus ni la tabla.
    Determinista; no importa duckdb (núcleo puro)."""

def decorate(artifact: NetworkArtifact, table: pa.Table) -> None:
    """Atajo sobre decorate_graph: extrae kind y communities del NetworkArtifact.
    Es el punto de integración en facade.py (_build_artifact)."""
```

`networks/__init__.py` re-exporta `decorate`/`decorate_graph`.

**Atributos de nodo inyectados:**

| Atributo | Kinds | Origen |
|---|---|---|
| `label` | todos | string legible (mapeo por kind, abajo) |
| `degree_centrality` | todos | `float`, vía `nx.degree_centrality` |
| `year` | paper (coupling/cocitation) | `int` (ausente si `None` en el corpus) |
| `is_seed` | paper | `bool` |
| `curation_status` | paper | `string` |
| `community` | todos | `int`, **solo** si se provee `artifact.communities` |

**Mapeo de `label` por `NetworkKind`:**

| Kind | Nodo | `label` |
|---|---|---|
| `bibliographic_coupling` / `cocitation` | paper (`id`) | `"título (año)"`, truncado a `LABEL_MAX_CHARS` (60) + `"..."`; fallback al id crudo si no hay título |
| `author_collab` | `authors_id` | `authors_raw` correlativo al `authors_id` (fallback al id) |
| `institution_collab` | `institutions_id` | `institutions_raw` correlativo (fallback al id) |
| `keyword_cooccurrence` | `keywords_id` | la keyword (ya legible) |
| (kind desconocido) | — | fallback al id crudo (extensible, no falla) |

**Cableado:** `decorate` se aplica en `facade.py:_build_artifact`, de modo que `Networks.quick` /
`Networks.build` (§10) ya devuelven **artefactos decorados** y `b2g build`/`export` salen con `label`
legible sin pasos extra. **Los proyectores (§7) NO se tocan** (siguen puros, ADR 0014): la decoración
es la única capa que sabe de labels.

---

## 7.2 Núcleo — `cluster_table` (resumen de comunidades, v1, AS-BUILT #31)

`bib2graph.networks.cluster_table` es una **función pura** que cruza los nodos de una red con el
corpus para producir **una fila de resumen por comunidad**. Es el insumo tabular de la composición de
clusters (quién/qué/cuándo cae en cada comunidad), legible offline (Excel/Calc) y la base del
`clusters.csv` que escribe `b2g build` (§convenciones CLI).

> **Con `b2g build --corpus-scope` (#56):** el `clusters.csv` se computa sobre el corpus **FILTRADO**,
> así que sus filas/conteos reflejan **solo** los nodos del subset (`accepted` / `seeds_only`), no el
> corpus vivo completo. `build` pasa el mismo corpus filtrado a `cluster_table`, por lo que `size` y
> los `*_count` cuadran con los nodos del grafo (sin drift).

```python
def cluster_table(table: pa.Table, artifact: NetworkArtifact) -> list[dict[str, Any]]:
    """Una fila por comunidad de `artifact.communities`. Función pura (sin red, sin duckdb).
    Cruza nodo→fila por Col.ID (id canónico), NUNCA por source_id. Devuelve [] si el kind
    no es de paper o si no hay comunidades. Orden determinista por `cluster` ascendente."""
```

`networks/__init__.py` re-exporta `cluster_table`.

**Restricción a redes de paper (V1):** solo aplica a los kinds cuyo nodo es un `Col.ID`
(`bibliographic_coupling` / `cocitation`); para `author_collab`, `institution_collab` y
`keyword_cooccurrence` las comunidades agrupan entidades distintas a papers y la misma tabla no tiene
sentido en V1 → devuelve `[]` (no crash). Si `artifact.communities is None` también devuelve `[]`.
**Consecuencia en el CLI:** por esto **`clusters.csv` se emite ÚNICAMENTE para `bibliographic_coupling`
y `cocitation`** (§convenciones CLI / §9); las otras tres redes escriben `network.graphml` +
`metrics.json` pero **no** `clusters.csv`.

**Columnas de cada fila** (orden estable):

| Columna | Tipo | Origen |
|---|---|---|
| `cluster` | `int` | id de comunidad |
| `size` | `int` | nº de nodos en la comunidad (incluye nodos sin match en el corpus) |
| `seed_count` | `int` | nodos con `is_seed=True` |
| `candidate_count` | `int` | nodos con `curation_status='candidate'` |
| `accepted_count` | `int` | nodos con `curation_status='accepted'` |
| `year_min` / `year_max` | `int \| None` | rango de año (`None` si ningún nodo tiene año) |
| `year_mean` | `float \| None` | media de año redondeada a 1 decimal (`None` si no hay años) |
| `top_authors` | `list[str]` | hasta 5 autores más frecuentes, de **`authors_raw`** |
| `top_keywords` | `list[str]` | hasta 5 keywords más frecuentes, de **`keywords_id`** (post-thesaurus) |

**Notas de contrato** (#31, AS-BUILT 2026-06-17):

- **Cruce por `Col.ID`, no `source_id`** (lección B6 de la
  [Nota 09](Notas/09-sesion-qa-prueba-ecologia-valoraciones.md)): el nodo del grafo **es** un `Col.ID`
  (`doi:…`/`src:…`); indexar por `source_id` (`W…`) daría 0 cruces. Un nodo sin match en el corpus **suma al
  `size`** pero no aporta año/autores/keywords.
- **Determinista** (ADR [0017](decisiones/0017-reproducibilidad-historia-snapshot.md)): el top de
  autores/keywords se ordena por **`(-frecuencia, nombre alfabético ascendente)`** — desempate
  explícito que hace el resultado reproducible **independiente** del método de clustering
  (louvain/label_prop/greedy) y de `PYTHONHASHSEED`.
- **Pura:** sin red, sin `duckdb`; opera sobre `corpus.to_arrow()` + el `NetworkArtifact`. Combina con
  `community_composition` (§8, % por categoría) que mira el atributo, no la composición bibliográfica.

---

## 8. Núcleo — `Analyzer` (funciones puras, v1)

```python
def network_metrics(g: nx.Graph) -> dict:
    """Densidad, nº de componentes, clustering promedio."""

def centrality(g: nx.Graph) -> dict:
    """Centralidad de grado e intermediación por nodo."""

def detect_communities(g: nx.Graph, method: str = "louvain", *,
                       random_state: int | None = None) -> dict:
    """method ∈ {'louvain', 'label_prop', 'greedy_modularity'}. Louvain requiere
    `python-louvain` (DECLARADO); si falta, FALLA explícito (lección 7).
    `random_state` (Hito R2, ADR 0017): semilla determinista de Louvain. `facade.py` la
    deriva del `corpus_hash` de contenido (`_louvain_seed_from_hash`) → comunidades
    reproducibles entre corridas. `None` = Louvain sin semilla. (`resolution`: Hito 9.)"""

def assortativity(g: nx.Graph, *, attribute: str | None = None,
                  by_degree: bool = True, proxy: str | None = None) -> dict:
    """Asortatividad por un ATRIBUTO categórico configurable (p. ej. 'region') y/o por grado.
    `attribute` y sus categorías son config del USUARIO (no hardcodear; crítica #5).
    `proxy` documenta si el atributo es un proxy (p. ej. 'affiliation_per_paper'): se reporta
    en el output como disclaimer ('fácil pero consciente'). Validado en el sandbox IED."""

def community_composition(g: nx.Graph, communities: dict, attribute: str) -> dict:
    """% de cada categoría del atributo dentro de cada comunidad.
    (Composición bibliográfica de las comunidades de una red de paper → `cluster_table`, §7.2.)"""

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
  de filas determinista. El `label` (y `year`/`is_seed`/`curation_status`/`community`) lo inyecta la
  capa `decorate` (§7.1) antes del export, no el exporter.
- **`GraphMLExporter`** escribe esos atributos como node attributes, **omite** los atributos con
  valor `None` (Gephi / `nx.write_graphml` no los admiten) y **no muta** el grafo original (opera
  sobre una copia).
- **`clusters.csv` (AS-BUILT #31):** además de `network.graphml` + `metrics.json`, **`b2g build`**
  escribe `<networks_dir>/<kind>/clusters.csv` cuando la red es de **paper** y tiene comunidades
  (`cluster_table` no vacío, §7.2). Una fila por comunidad; las columnas de lista (`top_authors`/
  `top_keywords`) se serializan **con separador `|`**. No lo emite un `Exporter` —lo arma el comando
  `build` a partir de `cluster_table`—; las redes sin comunidades o no-paper no generan el archivo.
  **Solo lo generan `bibliographic_coupling` y `cocitation`**: `author_collab`, `institution_collab`
  y `keyword_cooccurrence` emiten `network.graphml` + `metrics.json` pero **no** `clusters.csv`, por
  diseño (sus nodos no son papers; ver §7.2).

---

## 10. Capa declarativa — `NetworkSpec` (v0.2, capa declarativa AS-BUILT Hito 9)

```python
class NetworkSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")   # Hito 9: campo desconocido en el YAML → error
                                                 # accionable (no se ignora en silencio)
    kind: NetworkKind        # R5: enum de constants.py (fuente única, ADR 0023);
                             # antes era un Literal[...] duplicado (eliminado)
    min_weight: int = 1
    min_year: int | None = None
    max_year: int | None = None
    scope: Literal["full", "seeds_only"] = "full"
    clustering: Literal["louvain", "label_prop", "greedy_modularity"] | None = "louvain"
    resolution: float = 1.0  # Hito 9: resolución de Louvain (python-louvain best_partition).
                             # Default 1.0 = comportamiento anterior. Ignorado en label_prop/
                             # greedy_modularity (sin error). FUERA del corpus_hash (param de spec,
                             # no de contenido — como min_weight/scope; el seed de Louvain sigue
                             # siendo función pura del corpus_hash, R2).
    assortativity_attribute: str | None = None     # p. ej. "region"
    layout: Literal["spring", "kamada_kawai", "circular"] | None = None
    keyword_filter: list[str] | None = None  # Issue #113: sub-red temática. Filtra el corpus ANTES
                                             # de proyectar a los papers cuyo keywords_raw matchee
                                             # (ANY, substring, case-insensitive) algún término.
                                             # None/[] = sin filtro. Param de spec, FUERA del
                                             # corpus_hash (como min_weight/scope).


def load_specs(path: str | Path) -> list[NetworkSpec]:
    """Carga y valida una lista de NetworkSpec desde YAML (Hito 9). Re-exportada desde
    bib2graph.networks. Clave raíz `networks:` = lista; cada entrada se valida con
    NetworkSpec(**entry) (no se redefine el schema). Errores accionables (ValueError):
    YAML malformado, falta de raíz `networks:`, entrada no-dict, y ValidationError citando
    archivo + `red #<idx>` (0-based) + campo."""

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
        """Arma las specs razonables y devuelve sus artefactos (caso 'investigador, baja
        fricción'). Devuelve **4 o 5 redes**: coupling (full), co-autoría, institución, co-word
        siempre; la **co-citación** se incluye (→5) cuando el corpus tiene `cited_by_id` poblado
        (tras `b2g enrich`, Hito 8b) y se **omite graceful** (log) si está vacío (→4).
        Los artefactos vienen **decorados** (label legible + atributos de nodo, §7.1)."""
```

**Modo quick** (v1) cubre baja fricción; **modo spec** (Hito 9, YAML) cubre el pipeline declarativo
versionable, vía `load_specs(redes.yaml)` + `Networks.build` por red (y el subcomando `b2g
networks --spec`, §convenciones CLI).

**Sub-redes temáticas (`keyword_filter`, issue #113):** cada red declarada puede acotar el corpus a
un tema antes de proyectar — útil para comparar sub-redes (p. ej. T4 vs T7) sin pre-filtrar el corpus
entero ni escribir scripts. El match es **ANY** (un paper entra si algún término matchea), por
**substring case-insensitive** sobre `keywords_raw` (display names). `None`/`[]` = sin filtro.

```yaml
networks:
  - kind: keyword_cooccurrence
    keyword_filter: ["complex", "ecolog"]   # papers con keywords tipo "Complexity"/"Ecological..."
  - kind: bibliographic_coupling
    keyword_filter: ["assessment"]
```

**Notas de contrato** (Hito 2, ADR [0014](decisiones/0014-proyeccion-redes-pesos-asortatividad.md)):

- **`Networks.quick` arma 4 o 5 redes** (D3, AS-BUILT Hito 8b): coupling `full`, co-autoría,
  institución y co-word **siempre** (4); suma la **co-citación** (→5) cuando el corpus tiene
  `cited_by_id` poblado por `b2g enrich` (2º nivel de fetch del `OpenAlexEnricher`, ADR 0025), y la
  **omite avisándolo por log** (→4) si esa columna está vacía (no se corrió `enrich`). El
  `CoCitationProjector` también queda disponible vía
  `Networks.build(corpus, NetworkSpec(kind="cocitation"))`.
- **`NetworkSpec` es un hook mínimo en v1** (modelo Pydantic ya consumido por `build`/`quick`); el
  símbolo público re-exportado desde `bib2graph` es `NetworkArtifact` (no `NetworkSpec`, que se
  importa desde `bib2graph.networks`).
- **AS-BUILT Hito 9 (2026-06-17) — capa declarativa YAML.** `NetworkSpec` gana `model_config =
  ConfigDict(extra="forbid")` (campo desconocido → error) y el campo **`resolution: float = 1.0`**
  (resolución de Louvain, propagada por `_build_artifact` a
  `community_louvain.best_partition(..., resolution=...)`; **ignorada** en `label_prop`/
  `greedy_modularity`). `resolution` queda **fuera del `corpus_hash`** (es param de spec, no de
  contenido — como `min_weight`/`scope`), así que el seed de Louvain sigue siendo función pura del
  `corpus_hash` (R2) y la reproducibilidad/equivalencia de comunidades se mantienen. **`load_specs`**
  (en `networks/spec.py`, re-exportada desde `bib2graph.networks`) carga la lista de specs desde un
  YAML con clave raíz `networks:`; cada entrada se valida con `NetworkSpec(**entry)`. Errores
  accionables (`ValueError`): YAML malformado, falta de raíz `networks:`, entrada no-dict, y
  `ValidationError` citando archivo + `red #<idx>` (0-based) + campo. Ejemplo `redes.yaml`:

  ```yaml
  networks:
    - kind: bibliographic_coupling
      min_weight: 2
      resolution: 1.5
    - kind: author_collab
      clustering: label_prop
  ```

  Se ejecuta vía el subcomando **`b2g networks --spec redes.yaml`** (§convenciones CLI). DoD del
  Hito 9 cubierto, incluida la **equivalencia build≡quick** (nodos + aristas + comunidades).

  **Ejemplo mínimo de `networks.yaml` válido** (copiable) — clave raíz `networks:` = lista; lo único
  obligatorio de cada entrada es **`kind`**:

  ```yaml
  networks:
    - kind: bibliographic_coupling
  ```

  **Campos válidos de cada entrada** (nombres exactos; `kind` obligatorio, el resto con default):

  | Campo | Valores / tipo | Default | Obligatorio |
  |---|---|---|---|
  | `kind` | `bibliographic_coupling` · `cocitation` · `author_collab` · `institution_collab` · `keyword_cooccurrence` | — | **sí** |
  | `min_weight` | `int` (peso mínimo de arista) | `1` | no |
  | `min_year` | `int` | `null` | no |
  | `max_year` | `int` | `null` | no |
  | `scope` | `full` · `seeds_only` | `full` | no |
  | `clustering` | `louvain` · `label_prop` · `greedy_modularity` · `null` | `louvain` | no |
  | `resolution` | `float` (solo Louvain; ignorado en los demás) | `1.0` | no |
  | `assortativity_attribute` | `str` (atributo categórico, p. ej. `region`) | `null` | no |
  | `layout` | `spring` · `kamada_kawai` · `circular` · `null` | `null` | no |

  **`NetworkSpec` usa `extra="forbid"`:** cualquier campo fuera de la tabla **se rechaza** con un
  `ValueError` accionable (no se ignora en silencio). Error común: **`name:` NO es un campo** — no hay
  forma de nombrar una red en el spec; usá un comentario YAML (`#`) si querés anotarla.
- **AS-BUILT #25 — artefactos decorados:** `_build_artifact` (en `facade.py`) aplica `decorate`
  (§7.1) sobre el grafo, así que `build`/`quick` devuelven artefactos con `label` legible + atributos
  de nodo (`year`/`is_seed`/`curation_status`/`degree_centrality`/`community`) listos para el export
  y la GUI. Los proyectores (§7) siguen puros (ADR 0014).

---

## 11. Deduplicación fuzzy — AUTOMÁTICA en la ingesta (`rapidfuzz` núcleo, v1 — construido, Hito 7 + #88)

> **Sincronizado con el preprocesamiento automático en la ingesta — #88 (AS-BUILT, 2026-06-18,
> ADR [0031](decisiones/0031-preprocesamiento-automatico-en-ingesta.md)):** el dedup deja de ser
> "función de librería sin subcomando" (corte 0026) y pasa a ejecutarse **automáticamente en cada
> ingesta** (`seed`/`seed_from_bib`/`chain`/`restore`). **`rapidfuzz` pasa al núcleo**
> (`[project.dependencies]`); **el extra `[dedup]` se ELIMINA** y el import deja de ser perezoso. El
> **algoritmo** de 0026 (token_sort_ratio + Union-Find + canónico) **no cambia**: cambia *quién lo
> invoca y cuándo*. La consolidación de keywords (thesaurus) es el único paso **no automático** del
> preproc y se expone como el flag **`b2g build --thesaurus`** (#164; el verbo `b2g thesaurus` se
> retiró — §convenciones CLI, §6).

**Dedup fuzzy determinista** con `rapidfuzz` (núcleo desde #88): el complemento aproximado de la
normalización conservadora del `Preprocessor` (§6). Las funciones siguen exportadas desde
`bib2graph.preprocessors`, pero **se invocan automáticamente** desde el helper de frontera
`cli/_ingest.py::normalize_and_dedup`, no a mano. Operan sobre la columna `_id`
(`authors_id`/`keywords_id`), **nunca** sobre `_raw`.

```python
# Helper de frontera — punto único de la ingesta (cli/_ingest.py)
def normalize_and_dedup(corpus: Corpus, *, applied_at: datetime | None = None) -> Corpus:
    """normalize → deduplicate_authors(0.92) → deduplicate_keywords(0.90), en ese orden, sobre el
    corpus COMPLETO YA MERGEADO (existing + incoming) ⇒ dedup CROSS-BIBLIOTECA. NO aplica thesaurus
    (eso es el flag explícito `b2g build --thesaurus`, #164). `applied_at` se inyecta desde la frontera (R2)."""

# Funciones de librería (ADR 0026, intactas; ahora invocadas por el helper, no a mano)
def deduplicate_authors(corpus: Corpus, *, threshold: float = 0.92) -> Corpus:
    """Colapsa variantes de `authors_id` por similitud de nombres (fuzzy DETERMINISTA). Lo trivial
    ya lo hizo el Preprocessor (§6); esto es el complemento aproximado."""

def deduplicate_keywords(corpus: Corpus, *, threshold: float = 0.90) -> Corpus:
    """Colapsa variantes de `keywords_id` fuera del thesaurus por similitud de cadenas."""
```

**Notas de contrato** (Hito 7 + #88, ADR [0026](decisiones/0026-dedup-fuzzy-determinista.md) /
[0031](decisiones/0031-preprocesamiento-automatico-en-ingesta.md)):

- **Automático en la ingesta, cross-biblioteca:** las cuatro rutas
  (`seed`/`seed_from_bib`/`chain`/`restore`) hacen `existing.merge(incoming)` →
  `normalize_and_dedup(corpus_completo)` → `store.persist_replace(...)`. Corre sobre el corpus
  **completo** (no el lote) para deduplicar contra toda la biblioteca acumulada; se persiste con
  **`persist_replace`** (DELETE+INSERT, §4.1) porque el upsert-concat D3 (`persist`) reintroduciría
  las variantes colapsadas. `build`/`networks` siguen **puros** (el corpus ya entra deduplicado).
- **`threshold` por-campo** (autores `0.92` / keywords `0.90`; **ambas** lo reciben): se compara con
  `rapidfuzz.fuzz.token_sort_ratio` (0–100) contra `threshold * 100`. Umbrales fijos en
  `cli/_ingest.py` (ADR 0031).
- **Determinista e idempotente:** los pares ≥ umbral forman **componentes conexas** vía Union-Find
  (iteración ordenada); el **canónico** del cluster es la variante más frecuente (papers distintos)
  con desempate por `id` ascendente; se preserva el **orden de primera aparición** y **nunca se toca
  `_raw`**. Mismo corpus + threshold + versión de `rapidfuzz` → mismo resultado (verificado
  cross-`PYTHONHASHSEED`); converge en una pasada. **NO usa IA** (similitud de cadenas, no
  semántica/LLM; ADR [0022](decisiones/0022-producto-sin-ia-generativa.md)).
- **`rapidfuzz` en el núcleo (#88):** `rapidfuzz>=3,<4` en `[project.dependencies]`; el import de
  `preprocessors/dedup.py` es de nivel de módulo (ya **no** perezoso, ya **no** hay extra `[dedup]`
  ni `uv sync --extra dedup`). Registra un `PreprocRef` en el `Manifest` con
  `{library, rapidfuzz_version, scorer, threshold, n_clusters_collapsed}` (reproducibilidad a igual
  versión del scorer, ADR 0017).
- **Campos en V1:** autores + keywords. **Instituciones diferidas** (`institutions_id` no está
  normalizada determinísticamente hoy). `splink` (record-linkage probabilístico) **diferido a
  post-V1** (ADR 0026).
- **Diferido a la epic GUI (#34):** la **revisión asistida de clusters ambiguos** (sugerir N
  canónicos → el humano elige, determinista vía scores de `rapidfuzz`, **sin IA generativa**) requiere
  superficie interactiva; hoy el dedup automático aplica el canónico determinista sin confirmar
  (ADR 0031). **Deuda conocida:** el dedup por ingesta es O(n²) sobre el corpus completo
  (optimización futura) y `test_run_seed_from_bib_reseed_incrementa_ronda` queda **skip** (#93,
  crash `BibDataString`/`pyparsing` en reseed mismo-proceso; no afecta el CLI real).

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

### 12.2 Con forrajeo y thesaurus (Hito 5 — construido)

`Forager`/`Preprocessor`/filtros están **construidos** (Hito 5). El *information scent* es
frecuencia de enlace; `preview` opera sin red (forward → `chain`); los filtros marcan `rejected`:

```python
from bib2graph import (
    OpenAlexSource, Forager, Preprocessor, FilterCriterion, apply_filters,
)

# 2') Forrajear: candidatos rankeados por information scent (depth=1, preview SIN red)
forager = Forager(OpenAlexSource(email="luis@sostaina.com"), depth=1, max_candidates=300)
prev = forager.preview(seed.corpus)                     # backward exacto; forward → chain
print(prev.estimated_new, prev.forward_requires_fetch)  # p. ej. 142  True
ranked = forager.chain(seed.corpus)                     # forward fetchea citantes
# AS-BUILT #54: el backward observa sin materializar → ranked.observed_refs (no van a ranked.corpus);
# AS-BUILT #78: el forward materializa filas con metadata REAL (no placeholders). Ver §5.

# 3') Curar lo forrajeado, normalizar y aplicar el thesaurus multilingüe determinista
corpus = seed.corpus.merge(ranked.corpus).accept(ids=[...]).reject(ids=[...])
corpus = Preprocessor().normalize(corpus)
corpus = Preprocessor().apply_thesaurus(corpus, Path("thesaurus_ied.json"))  # puebla keywords_id

# 4') Filtrar (PRISMA): marca rejected, NO borra; sella Manifest.filters con los conteos
corpus, steps = apply_filters(corpus, [
    FilterCriterion(field="year", op="gte", value=2010),
    FilterCriterion(field="language", op="in", value=["en", "es", "pt"]),
])
for s in steps:
    print(s.name, s.count_before, "→", s.count_after)
```

### 12.3 Por CLI agente-native (Hito 6 — construido)

El mismo flujo, sin escribir Python, vía `b2g`: se **inicia el workspace una vez** y, trabajando
**dentro** de su carpeta, los comandos se resuelven por ambiente (sin `--store` repetido). Una línea
JSON por comando:

```bash
b2g init ied                                    # crea ./ied/ (workspace.json + library.duckdb + networks/…)
cd ied                                           # a partir de acá el workspace se resuelve por cwd
b2g seed --equation '"unequal ecological exchange"' --max-results 50 \
         --exclude "blockchain" --exclude "machine learning" \
         --email luis@sostaina.com --json   # --max-results: muestra chica · --exclude (repetible): negaciones, quedan en el translation_report
b2g chain --direction both --max-candidates 300 --max-citing 50 --json
b2g filter --year-gte 2010 --language en --language es --json
b2g accept --ids doi:abc123 --ids doi:def456 --json
b2g build --json                                 # escribe networks/ + sella networks/.corpus_hash
b2g export --format graphml --out-dir redes/ --json
b2g status --json     # CycleState + round + curation_available + workspace + conteos
```

Migración de un `.duckdb` legacy: corré **`b2g init .`** en su carpeta para adoptarlo como
workspace (`--store` y el modo degenerado fueron eliminados en
[#75](https://github.com/complexluise/bib2graph/issues/75)).

El **modo declarativo** (`NetworkSpec` desde un YAML versionable) está **construido** y se invoca con
**`b2g build --spec redes.yaml`** (AS-BUILT #159): un YAML versionable describe qué redes calcular.

```bash
# Pipeline declarativo desde un YAML versionable (dentro del workspace)
b2g build --spec redes.yaml --json      # carga load_specs(redes.yaml) → Networks.build por red →
                                        # escribe networks/<kind>/ (GraphML + metrics.json + clusters.csv)
                                        # transiciona a BUILT y sella .corpus_hash (D1, ADR 0038)
```

`b2g build --spec` es un **paso BUILD pleno**: transiciona el `CycleState` a `BUILT` y sella
`networks/.corpus_hash`. El alias `b2g networks --spec` (**en deprecación**, cierra 0.11.0) hace lo
mismo pero **NO** transiciona ni sella (ad-hoc transversal al lazo). Ver §convenciones CLI.
