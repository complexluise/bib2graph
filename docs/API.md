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
> §convenciones CLI.
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
> abajo). Ver §2 + §convenciones CLI.
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
> `max_results 80` → `curate --from-csv curacion.csv` 10 `accepted` → `enrich --max-citing 25` →
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
> **`<workspace>/exports/`** (resolución vía `resolve_workspace`, igual que `build`; modo degenerado =
> dir hermano del `.duckdb`, sin regresión). **`b2g status`** suma el campo aditivo
> **`data["networks_cache_stale"]: bool`** + un `warnings` accionable cuando el `networks/.corpus_hash`
> sellado **no coincide** con el `corpus_hash` del corpus vivo (aviso "ejecutá `b2g build`"; **NO**
> regenera — invalidación por hash, no build-system, ADR 0029). `schema="1"` intacto. `Workspace` ganó
> `read_networks_corpus_hash()` e `is_networks_cache_stale(live_hash)` (los accessors
> `snapshots_dir`/`exports_dir`/`networks_dir` ya existían). Ver §convenciones CLI.

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
subcomando lleva `--json` (envelope estable/versionado) y exit codes (`0` éxito · `1` uso · `2`
datos · `3` dependencia · `4` red · `5` store/snapshot corrupto o bloqueado). **Sin estado entre
invocaciones:** el estado vive en el `library.duckdb` del **workspace** (opciones globales
**opcionales** `--workspace`/`--store`, ver abajo).

**Set de 17 subcomandos** (decisión del PO, ADR 0021 §A — **amplía** este doc, que antes listaba 9
y dejaba `accept`/`reject` como "solo programático"; el 12° `monitor` se agregó en el cleanup
pre-v0.3; el 13° `enrich` en el Ciclo 8a, ADR
[0025](decisiones/0025-enricher-cocitacion-openalex.md); el 14° `init` con el workspace, ADR
[0029](decisiones/0029-workspace-por-investigacion.md); el 15° `curate` con la curación a escala,
#22 + #26; el 16° `networks` con la capa declarativa YAML, Hito 9; el 17° `restore` con la
rehidratación de corpus curado sin red, Ciclo 9a, ADR
[0030](decisiones/0030-ecuacion-declarativa-corpus-ejemplo.md)):

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
  `observed_refs_count` a su envelope JSON. `inspect`, `validate`.
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
  Con `--spec`, todos estos parámetros vienen del YAML (paridad 1:1 flag ⇄ campo). **Combinar
  cualquier flag de OpenAlex (`--exclude`/`--max-results`/`--native`/`--email`/`--min-year`/`--max-year`)
  con `--from-bib` → error de uso, exit 1** (falla fuerte, no ignora en silencio). En modo `--native`,
  `--min-year`/`--max-year` no se aplican (nativo = sin traducción).
- **`restore`** (ADR [0030](decisiones/0030-ecuacion-declarativa-corpus-ejemplo.md), Ciclo 9a, 17°
  subcomando): **rehidrata un corpus ya curado desde un parquet, SIN red** — inverso de `snapshot`,
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
- **`monitor`** (cleanup pre-v0.3): re-chequea OpenAlex por **citantes nuevos** del corpus (forward
  chaining **batcheado**, AS-BUILT #21: reusa `fetch_citing_batch` con cap por semilla, scope
  `is_seed`), mergea los candidatos nuevos a la biblioteca viva y **transiciona a `MONITORED`** vía
  `apply_transition(state, "monitor", round)` (paso 8 del ciclo, Ellis). `data` =
  `{new_candidates, total_papers, loop_state, round}`; `--email` para el polite pool; `--json` con
  `schema="1"`. **Sin pre-check de capacidad** (a diferencia de `chain`): instancia `OpenAlexSource`
  fijo, que **siempre** tiene `fetch_citing` (asimetría deliberada con `chain`, que acepta
  `--direction` variable y sí pre-chequea). Errores accionables: sin corpus/estado previo →
  `DataError` (exit 2). Con `monitor`, **`MONITORED` deja de ser inalcanzable**.
- **`enrich`** (Hito 8 = Ciclos 8a + 8b, ADR
  [0025](decisiones/0025-enricher-cocitacion-openalex.md)): corre el `OpenAlexEnricher` (§3) sobre
  la biblioteca viva en **2 pasadas**. **8a:** resuelve `references_id`→`references_doi` (batching
  por OR) y registra el `EnricherRef` en el `Manifest` (idempotente). **8b:** la pasada de
  **co-citación** trae los citantes de las **semillas aceptadas** y **mergea sus `openalex_id` en
  `cited_by_id`** (unión idempotente; no crece el corpus). Flags: `--email` (polite pool),
  `--api-key` (opcional), **`--max-citing INTEGER`** (tope de citantes **por semilla**, acota el
  fetch), `--json`. `data` = `{enriched, references_resolved, ...}`. **NO transiciona el
  `CycleState`** (ortogonal al lazo): se puede enriquecer en cualquier estado sin perturbar el FSM.
  `build` sigue puro/sin red.
- **`init`** (ADR [0029](decisiones/0029-workspace-por-investigacion.md)): **scaffold de un
  workspace**. `b2g init <name>` crea `<name>/` con `workspace.json` + `library.duckdb` +
  `networks/`/`snapshots/`/`exports/`; **`b2g init .`** inicializa el cwd. Si la carpeta ya es un
  workspace → error (`WorkspaceExistsError`). **NO transiciona** el `CycleState`. `data` =
  `{root, name, ...}`; `--json` con `schema="1"`.
- **`curate`** (#22 + #26, AS-BUILT 2026-06-16): **curación en lote vía CSV** —cierra el hueco de la
  [Nota 09](Notas/09-sesion-qa-prueba-ecologia-valoraciones.md) B4/B5/P1 (la curación a escala no era
  viable con `accept`/`reject` por `--ids` uno a uno). **Dos modos mutuamente excluyentes** (exactamente
  uno; pasar ambos o ninguno → error de uso, exit 1):
  - **`--dump`** escribe un CSV revisable offline (Excel/Calc). Default
    `<workspace>/exports/curacion.csv`; **`--out`** lo override. **`--scope [candidates|seeds|all]`**
    (default `candidates`) elige qué papers volcar: `candidates` = forrajeados a revisar
    (`curation_status == 'candidate'` **AND** `is_seed == False`, **excluye semillas** —arregla #72,
    donde el dump arrastraba seeds); `seeds` = semillas originales (`is_seed == True`); `all` = todo el
    corpus. **`--all`** queda como **alias deprecado de `--scope all`** (tiene precedencia si se pasan
    ambos). Sin candidatos (scope `candidates`/`seeds` vacío) → error accionable que sugiere `--scope all`
    o `b2g chain`. Columnas (16, orden estable): `id, openalex_id, title, year, authors, venue, doi,
    keywords, cited_by_count, references_count, is_seed, openalex_url, scent_score, cluster, decision,
    note`. **Todas read-only salvo `decision` y `note`** (las editables por el humano). `venue` sale de
    `source`; `keywords` se une con `" | "` (igual que `authors`); `openalex_url` se deriva del
    `openalex_id` (`https://openalex.org/<id>`). **`cited_by_count`/`references_count` hoy salen vacías**:
    no existen como escalares en el schema canónico de 23 columnas, así que la columna queda como
    placeholder para llenado manual (limitación conocida, no falla). `decision` refleja el
    `curation_status` actual (`candidate`→`undecided`, `accepted`→`accepted`, `rejected`→`rejected`).
    `data` = `{csv_path, papers_exported, columns}`.
  - **`--from-csv <archivo>`** aplica las decisiones en lote y persiste: `accepted`→`accept`,
    `rejected`→`reject`, `undecided`→no-op (case-insensitive). **Idempotente** (reimportar el mismo CSV
    = mismo `corpus_hash`; el reloj `decided_at` se inyecta en la **frontera CLI**, R2/ADR 0017, fuera
    de la identidad). **Validación accionable** (exit 2): CSV sin `id`/`decision` → error que nombra las
    columnas requeridas; `decision` con un valor fuera de `{accepted, rejected, undecided}` → error con
    los valores válidos. **IDs huérfanos** (en el CSV pero no en el corpus) **NO se aplican** y se
    reportan en `not_found_count` + aviso humano (cierra el no-op silencioso). `data` =
    `{accepted_count, rejected_count, skipped_count, not_found_count, total_rows}` —los `*_count` de
    accept/reject cuentan papers **efectivamente** encontrados y marcados, no filas del CSV.
  - **`note` es advisory:** hace round-trip en el dump pero **se ignora al importar** (`ProvenanceEvent`
    no tiene campo de anotación; persistirla → ADR futuro). **`scent_score` best-effort** (vacío hasta
    que el Forager guarde `scent` en provenance) y **`cluster` siempre vacío** (integración con redes
    diferida). **Curación TRANSVERSAL: `curate` NO transiciona el `CycleState`** (disponible en cualquier
    estado del lazo, igual que `accept`/`reject`; ADR 0016 enmendado R3). `--json` con `schema="1"`.
- **`networks`** (Hito 9, AS-BUILT 2026-06-17): **capa declarativa** — construye redes desde un YAML
  versionable. **`b2g networks --spec <redes.yaml>`** carga la lista de specs con `load_specs` (§10;
  clave raíz `networks:`), construye cada red con `Networks.build` y escribe artefactos con el helper
  compartido **`_write_artifacts`** (extraído de `build.py`): mismos GraphML + `metrics.json` +
  `clusters.csv` que `build`, en `<out-dir>/<kind>/`. **`--out-dir`** override (default
  `<workspace>/networks/`); resolución de store/workspace idéntica a `build` (`resolve_workspace`).
  `--json` con `schema="1"`, mismo formato que `build` (lista de redes en `data["networks"]`, con
  `clusters_csv` condicional). **Ejecución ad-hoc transversal al lazo: NO transiciona el `CycleState`
  ni sella `networks/.corpus_hash`** (mismo criterio que `enrich`/`curate`). Errores accionables:
  YAML malformado / spec inválida → `DataError` (exit 2); falta `python-louvain` → `DependencyError`
  (exit 3).

**`--workspace` / `--store` globales (ambos OPCIONALES, mutuamente excluyentes).** Van en el grupo
`b2g`, **antes** del subcomando. Una investigación = un **workspace** (carpeta marcada por
`workspace.json`; ADR [0029](decisiones/0029-workspace-por-investigacion.md), AS-BUILT). El estado
vive en su `library.duckdb`; el CLI es stateful **vía archivo**, no vía proceso.

- **`--workspace <carpeta>`** apunta a la raíz de un workspace; **`--store <archivo.duckdb>`** apunta
  a un `.duckdb` suelto (**workspace degenerado**, retrocompatible — los artefactos caen en su dir
  hermano). Pasarlos **juntos** = error de uso (exit 1).
- **Resolución ambiente** cuando no se pasa ninguno (patrón git/cargo), precedencia de mayor a menor:
  (1) `--workspace`/`--store` explícito, (2) `B2G_WORKSPACE` (variable de entorno), (3) **walk-up**
  del cwd buscando `workspace.json`. Sin ninguno → **error accionable** que sugiere `b2g init`.

**`build` y `export` separados** (decisión del PO, ADR 0021 §B): `build` computa `Networks.quick`
(4 redes) y escribe artefactos a `<workspace>/networks/<kind>/` (+ transiciona a `BUILT`);
`export --format graphml|csv` **relee** esos artefactos (fuente resuelta vía `ws.networks_dir`) y
los serializa (sin transición). **AS-BUILT #32 (2026-06-17):** `export --out-dir` pasó a **override
OPCIONAL** — sin él, escribe en **`<workspace>/exports/`** (resolución ambiente como `build`; modo
degenerado = dir hermano del `.duckdb`). **AS-BUILT #31 (2026-06-17):** `build` también escribe **`clusters.csv`** (tabla de
resumen de comunidades, §7.2) en `<networks_dir>/<kind>/` **solo** para redes de **paper** con
comunidades detectadas (listas con separador `|`); en el envelope `--json`, cada entrada de
`data["networks"]` suma `clusters_csv` (ruta del archivo) **condicionalmente** —solo cuando ese
archivo se generó—.

**`build --corpus-scope [all|accepted|seeds_only]` (AS-BUILT #56):** filtra el corpus por estado de
curación **antes** de proyectar (vía `Corpus.scoped`, §1.2). **Default `all`** = corpus completo
(opt-in, sin cambio de comportamiento). `accepted` = semillas (`is_seed=True`) + papers aceptados;
`seeds_only` = solo semillas. El `networks/.corpus_hash` se sella con el hash del corpus **FILTRADO**
(no del vivo completo), y `clusters.csv`/`decorate` reflejan exactamente ese subset (sin drift). Si el
scope deja **0 papers**: **exit 0** + `warning` accionable ("corré `b2g curate`… o usá
`--corpus-scope=all`") — **no** es error; escribe `networks/` vacío con `.corpus_hash` vacío. El
envelope `--json` suma `data["corpus_scope"]` (y `warnings`). **NO confundir con `NetworkSpec.scope`
(§10):** ejes distintos. `--corpus-scope` filtra el **corpus entero** por curación (un input al
`build`); `NetworkSpec.scope` (`full`/`seeds_only`) es **por-red declarativa** sobre `is_seed`.

**`snapshot` (AS-BUILT #32, 2026-06-17):** `b2g snapshot` sella una foto reproducible del estado vivo
(parquet + `manifest.json`, ADR 0017). **`--out-dir` pasó a override OPCIONAL** — sin él, escribe en
**`<workspace>/snapshots/`** (resolución ambiente vía `resolve_workspace`, igual que `build`); en modo
degenerado (`--store` suelto) cae en el dir hermano del `.duckdb` (sin regresión). No transiciona el
`CycleState`.

**Staleness de la cache de redes (AS-BUILT #32, 2026-06-17):** `b2g status` suma el campo aditivo
`data["networks_cache_stale"]: bool` (`schema="1"` intacto) y, cuando es `true`, un `warnings`
accionable ("ejecutá `b2g build`"). Lo dispara que el `networks/.corpus_hash` **sellado** por el
último `build` **no coincida** con el `corpus_hash` del corpus vivo (calculado con el **mismo**
`compute_corpus_hash(corpus.to_arrow())` que `build` usa para sellar → sin falsos positivos). Si la
cache **no existe** (nunca se corrió `build`), **no** es stale. `status` **avisa, NO regenera**:
invalidación por hash, **no** un build-system (ADR [0029](decisiones/0029-workspace-por-investigacion.md)).

**Transiciones automáticas del ciclo** (ADR 0021 §F; AS-BUILT R3): `seed`→`SEEDED`, `chain`→`FORAGED`,
`filter`→`FILTERED`, `build`→`BUILT`, **`monitor`→`MONITORED`** (cleanup pre-v0.3),
**`restore`→`FILTERED`** (Ciclo 9a, ADR 0030: el corpus restaurado ya pasó curación; reusa la
transición permisiva `filter`);
`accept`/`reject`/**`curate`**/`export`/`snapshot`/`status`/`inspect`/`validate`/**`enrich`**/**`networks`**
**no transicionan** (`curate` es curación transversal; `enrich` y `networks` son ortogonales al lazo,
ADR 0025 / Hito 9). El estado
destino lo dicta `bib2graph.cycle.apply_transition`
(fuente única de verdad; los comandos no hardcodean el destino). `seed` con **estado previo** se trata
como **`reseed`** (loop-back a `SEEDED`, ronda++, acumula sobre lo curado).

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

**Borde: el error de uso sale SIN envelope.** Ante un error de uso (p. ej. `--workspace` y `--store`
juntos, una opción requerida faltante, o ningún store/workspace resoluble), Click aborta el parseo
**antes** de entrar al comando: se emite el mensaje de uso de Click en **stderr** y
exit code `1`, **sin** envelope JSON. El envelope versionado solo cubre errores que ocurren
**dentro** de la ejecución del comando.

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

    def scoped(self, scope: str) -> "Corpus":
        """Vista PURA por estado de curación: devuelve un Corpus NUEVO con el subconjunto de filas
        (no muta el original). Valores: `'all'` = corpus completo; `'accepted'` = `is_seed == True`
        OR `curation_status == 'accepted'`; `'seeds_only'` = `is_seed == True`. Scope inválido →
        `ValueError` accionable. Determinista: dos llamadas con el mismo scope dan corpora con el
        mismo `corpus_hash` (subset estable). `'all'` reusa el backend; los otros materializan el
        filtro en un `InMemoryBackend`. Lo usa `b2g build --corpus-scope` para sellar el hash del
        corpus FILTRADO. Issue #56. **NO confundir con `NetworkSpec.scope`** (§10): aquel es un
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
- **`fetch_citing_batch(ids, *, max_per_paper) -> dict[seed_id, list[citer_id]]`** (Hito 8b, ADR
  [0025](decisiones/0025-enricher-cocitacion-openalex.md)): trae los citantes de un conjunto de
  semillas **batcheando por OR** (`cites:W1|W2|...`, lotes ≤50), pagina por cursor y **atribuye
  página a página** (cruza `referenced_works` del citante con el set objetivo, por short-id). Con
  **presupuesto por semilla**: corta la paginación cuando **todas** las semillas del lote alcanzan
  `max_per_paper` (acota el *fetch*, no solo la columna; **sin starvation** entre semillas; mata el
  N+1 diferido de R5). Lo consume el `OpenAlexEnricher` (§3) para poblar `cited_by_id`. **AS-BUILT
  #78 (2026-06-17): firma y contrato INTACTOS** —sigue devolviendo solo el mapeo de atribución— pero
  internamente es un **thin wrapper** sobre `_fetch_citing_pages` que **descarta `works_map`** (la
  metadata que ya viaja en la misma request). El Enricher 8b no cambia.
- **`fetch_citing_batch_with_works(ids, *, max_per_paper) -> tuple[dict[seed_id, list[citer_id]], dict[citer_id, work]]`**
  (#78, 2026-06-17, Forager forward chaining): la **variante que conserva la metadata**. Misma red,
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
    congeladas que `b2g curate --from-csv` consume: **receta determinista** de curación (aplicarlo
    al corpus sembrado produce el mismo estado, independiente de cuándo se corra).
  - **`README.md`** — qué demuestra y con qué comandos se arma/reproduce. **Es la procedencia:**
    la **receta CLI** documentada (armado con red + reproducción offline), no un script.
- **Cómo se restaura:** `b2g restore --from-corpus examples/<nombre>/corpus.parquet` (§2.`restore`)
  rehidrata el corpus **sin red** en el `library.duckdb` de un workspace temporal, preserva la
  curación y transiciona a `FILTERED`; luego `build` → `networks`/`clusters` corren localmente.
- **`.gitignore`:** `!examples/` trackea el ejemplo; `examples/**/*.duckdb` lo protege de que un
  store vivo se cuele. El resto de la política de datos de usuario no cambia.
- **Ejemplos existentes:**
  - **`examples/valoraciones/`** (Ciclo B, AS-BUILT 2026-06-17): **~80 filas** (70 `candidate` +
    10 `accepted` enriquecidos), armado **100% por CLI** (sin script): `seed --spec equation.yaml`
    (`max_results: 80`) → `curate --from-csv curacion.csv` → `enrich --max-citing 25` → `snapshot`.
    **Co-citación presente** (rala) + coupling/author/institution/keyword sustanciales. Verificado por
    el gate R2 `tests/unit/test_example_r2_gate.py` (`corpus_hash` estable + comunidades Louvain
    estables entre corridas; piso `n>=50`, las 5 redes con datos). Se rehidrata con
    `b2g restore --from-corpus`. Procedencia = receta CLI del README + `equation.yaml` + `curacion.csv`.
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
`apply_transition`, no de un literal. **`MONITORED`** es **alcanzable** desde el cleanup pre-v0.3: el
comando **`b2g monitor`** lo dispara (`apply_transition(state, "monitor", round)`, paso 8 del ciclo).
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

    def chain(self, corpus: Corpus, *, direction: Direction = "both") -> "RankedCandidates":
        """Computa candidatos (curation_status='candidate', is_seed=False) rankeados por scent.
        Devuelve SOLO los candidatos nuevos (no mergeados): el humano hace
        corpus.merge(ranked.corpus). NO muta el corpus de entrada. Sella Manifest.chaining."""

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
  con `chain`). `b2g monitor` usa este mismo forward batcheado.
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

## 6. Núcleo — `Preprocessor` + filtros PRISMA (v1 — construido, Hito 5)

```python
class Preprocessor:
    """Determinístico e idempotente. La parte fuzzy vive en [dedup] (§11). Registra un
    PreprocRef en el Manifest por cada operación aplicada."""
    def normalize(self, corpus: Corpus) -> Corpus:
        """Normalización CONSERVADORA (decisión b=A): authors_id (lowercase + quitar acentos +
        colapso de espacios) y language (subtag ISO 639-1 primario). SIN fuzzy (eso es [dedup],
        §11), SIN columna de periodización. Idempotente. NO muta el corpus de entrada."""
    def apply_thesaurus(self, corpus: Corpus, thesaurus: dict | Path) -> Corpus:
        """Lee keywords_raw y SOBRESCRIBE keywords_id con los conceptos canónicos del thesaurus
        multilingüe CURADO (en/es/pt), dict canónico→aliases en JSON o Path a ese JSON.
        Determinista e idempotente (ADR 0011). SIN fallback semántico/LLM (ADR 0011 enmendado /
        0022): lo que no matchea queda fuera, sin inventar conceptos con un modelo."""
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
  un `nx.Graph` con **ids crudos** como nodos (`oa:…`, `I185261750`, un ORCID), **sin** `label`. La
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
    Cruza nodo→fila por Col.ID (id canónico), NUNCA por openalex_id. Devuelve [] si el kind
    no es de paper o si no hay comunidades. Orden determinista por `cluster` ascendente."""
```

`networks/__init__.py` re-exporta `cluster_table`.

**Restricción a redes de paper (V1):** solo aplica a los kinds cuyo nodo es un `Col.ID`
(`bibliographic_coupling` / `cocitation`); para redes de **autor/keyword/institución** las comunidades
agrupan entidades distintas a papers y la misma tabla no tiene sentido en V1 → devuelve `[]` (no
crash). Si `artifact.communities is None` también devuelve `[]`.

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

- **Cruce por `Col.ID`, no `openalex_id`** (lección B6 de la
  [Nota 09](Notas/09-sesion-qa-prueba-ecologia-valoraciones.md)): el nodo del grafo **es** un `Col.ID`
  (`oa:…`); indexar por `openalex_id` (`W…`) daría 0 cruces. Un nodo sin match en el corpus **suma al
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
- **AS-BUILT #25 — artefactos decorados:** `_build_artifact` (en `facade.py`) aplica `decorate`
  (§7.1) sobre el grafo, así que `build`/`quick` devuelven artefactos con `label` legible + atributos
  de nodo (`year`/`is_seed`/`curation_status`/`degree_centrality`/`community`) listos para el export
  y la GUI. Los proyectores (§7) siguen puros (ADR 0014).

---

## 11. Deduplicación fuzzy (extra `[dedup]`, v1 — construido, Hito 7)

**Construido** (Hito 7, ADR [0026](decisiones/0026-dedup-fuzzy-determinista.md)). Dedup fuzzy
**determinista** con `rapidfuzz` (extra `[dedup]`, import perezoso): el complemento aproximado de la
normalización conservadora del `Preprocessor` (§6). **Funciones de librería**, exportadas desde
`bib2graph.preprocessors` (no hay subcomando CLI — decisión del PO). Operan sobre la columna `_id`
(`authors_id`/`keywords_id`), **nunca** sobre `_raw`, y corren **después** de `normalize` y
`apply_thesaurus` (orden: normalize → thesaurus → dedup).

```python
def deduplicate_authors(corpus: Corpus, *, threshold: float = 0.92) -> Corpus:
    """Colapsa variantes de `authors_id` por similitud de nombres (fuzzy DETERMINISTA). Lo trivial
    ya lo hizo el Preprocessor (§6); esto es el complemento aproximado. Requiere extra [dedup]."""

def deduplicate_keywords(corpus: Corpus, *, threshold: float = 0.90) -> Corpus:
    """Colapsa variantes de `keywords_id` fuera del thesaurus por similitud de cadenas. Requiere
    extra [dedup]."""
```

**Notas de contrato** (Hito 7, ADR [0026](decisiones/0026-dedup-fuzzy-determinista.md)):

- **`threshold` por-campo** (autores `0.92` / keywords `0.90`; **ambas** lo reciben): se compara con
  `rapidfuzz.fuzz.token_sort_ratio` (0–100) contra `threshold * 100`.
- **Determinista e idempotente:** los pares ≥ umbral forman **componentes conexas** vía Union-Find
  (iteración ordenada); el **canónico** del cluster es la variante más frecuente (papers distintos)
  con desempate por `id` ascendente; se preserva el **orden de primera aparición** y **nunca se toca
  `_raw`**. Mismo corpus + threshold + versión de `rapidfuzz` → mismo resultado (verificado
  cross-`PYTHONHASHSEED`); converge en una pasada. **NO usa IA** (similitud de cadenas, no
  semántica/LLM; ADR [0022](decisiones/0022-producto-sin-ia-generativa.md)).
- **Extra `[dedup]` con import perezoso:** sin él, `ImportError` accionable → `uv sync --extra
  dedup`. Registra un `PreprocRef` en el `Manifest` con `{library, rapidfuzz_version, scorer,
  threshold, n_clusters_collapsed}` (reproducibilidad a igual versión del scorer, ADR 0017).
- **Campos en V1:** autores + keywords. **Instituciones diferidas** (`institutions_id` no está
  normalizada determinísticamente hoy). `splink` (record-linkage probabilístico) **diferido a
  post-V1** (ADR 0026).

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
b2g accept --ids oa:abc123 --ids oa:def456 --json
b2g build --json                                 # escribe networks/ + sella networks/.corpus_hash
b2g export --format graphml --out-dir redes/ --json
b2g status --json     # CycleState + round + curation_available + workspace + conteos
```

Retrocompat: `b2g --store biblioteca.duckdb seed …` (sin `init`, `.duckdb` suelto = workspace
degenerado) sigue siendo válido.

El **modo declarativo** (`b2g networks --spec redes.yaml`, `NetworkSpec` desde YAML) está
**construido** (Hito 9, AS-BUILT 2026-06-17): un YAML versionable describe qué redes calcular.

```bash
# Hito 9: pipeline declarativo desde un YAML versionable (dentro del workspace)
b2g networks --spec redes.yaml --json   # carga load_specs(redes.yaml) → Networks.build por red →
                                        # escribe networks/<kind>/ (GraphML + metrics.json + clusters.csv)
```

`b2g networks` es **ad-hoc / transversal al lazo**: **NO** transiciona el `CycleState` ni sella
`networks/.corpus_hash` (igual criterio que `enrich`/`curate`). Ver §convenciones CLI.
