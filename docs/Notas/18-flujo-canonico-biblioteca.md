# 18 — Flujo canónico end-to-end: el ejercicio bibliotecario sobre la biblioteca viva

> ⚠️ **NOTA DE ENCUADRE (arquitectura) — no es ADR.** Mapea el **loop bibliográfico completo**
> paso a paso y lo encuadra contra la capa de servicios (ADR 0028), las dos puertas de ingesta y
> el reencuadre library-centric del producto. Fecha: 2026-06-18. Input canónico:
> [`16-retroalimentacion-gui-mvp.md`](16-retroalimentacion-gui-mvp.md) (prueba GUI del PO) +
> [`17-validacion-tercero-gate34.md`](17-validacion-tercero-gate34.md) (validación tercero, Gate #34).
> Las decisiones formales que esta nota encuadra viven en los ADR **0032** (servicio dueño del
> flujo), **0033** (posicionamiento library-centric), **0034** (etiquetado / tabla lateral) y
> **0035** (ingesta multi-puerta + resolución DOI→ID como servicio) — todos en *Propuesta*.

## Tesis

El MVP entró por el **grafo** (la operación sobre la red). El feedback real (Notas 16/17) invierte
el centro de gravedad: **el grafo es el destino, no la entrada**. El trabajo real es el **ejercicio
bibliotecario** sobre la **biblioteca viva** (ADR 0009): ingestar → buscar → navegar → etiquetar →
curar. La **red es una proyección** que se computa cuando la curación lo amerita. Esto **no
inventa** un eje nuevo: la Épica C del PRD (§7 "Ejercicio bibliotecario y biblioteca viva") ya
existía; lo que cambia es que **la vista de Biblioteca pasa a ser la superficie primaria**, no una
feature más, y que la **capa de servicios** (`service/`) pasa a ser **dueña del loop entero**, no
solo de lecturas + curación (extiende ADR 0028).

## El loop bibliográfico, paso a paso

Cada paso declara: **(a)** operación de servicio que lo posee (nombre tentativo en `service/`),
**(b)** adaptador que lo expone (subcomando CLI / endpoint API / vista GUI), **(c)** estado del
store que lee/escribe. Marca **[existe]** lo construido hoy, **[nuevo]** lo que falta, **[mover]**
lo que existe en `cli/commands/` y debe subir a `service/`.

### Paso 0 — Abrir / crear la investigación
- **(a)** `service.workspace.open/init` (resolución ambiente, ADR 0029).
- **(b)** CLI `b2g init` · API: `Workspace` singleton del proceso (lo abre `b2g gui`) · GUI: selector
  de workspace.
- **(c)** crea/lee `workspace.json` + `library.duckdb`. **[existe]**

### Paso 1 — Ingesta (DOS PUERTAS, misma cadena, mismo corpus vivo)

> La decisión del PO (Nota 17): **BibTeX/import-de-archivo es de primera clase**. El investigador
> descarga `.bib`/RIS/EndNote/CSV de fuentes institucionales; no todo arranca por una ecuación ni
> vive en OpenAlex. Las dos puertas **convergen en el MISMO corpus por la MISMA cadena** de servicio.

**Puerta A — online (ecuación → OpenAlex):**
- **(a)** `service.ingest.seed_from_equation` **[mover]** (hoy `run_seed`).
- **(b)** CLI `b2g seed --equation/--spec` **[existe]** · API/GUI: formulario de ecuación **[nuevo]**.
- **(c)** escribe `corpus` (merge + `normalize_and_dedup` cross-biblioteca, ADR 0031); `loop_state_log`
  → `SEEDED`/reseed (ronda++).

**Puerta B — archivo (BibTeX/RIS/EndNote/CSV descargado):**
- **(a)** `service.ingest.seed_from_file` **[mover/nuevo]** (hoy `run_seed_from_bib`, solo `.bib`).
- **(b)** CLI `b2g seed --from-bib` **[existe, solo .bib]** → ampliar a multi-formato **[nuevo]** ·
  API/GUI: drag-and-drop de archivo **[nuevo]**.
- **(c)** mismo destino que la Puerta A: `corpus` + misma cadena `normalize_and_dedup`; `loop_state_log`.

**Convergencia crítica (la resolución DOI→OpenAlex ID es una operación de servicio COMPARTIDA):**
- **(a)** `service.resolve.dois_to_openalex_ids` **[nuevo]** (la API `OpenAlexSource` necesita un
  `fetch_dois_to_openalex_ids(dois)` nuevo — hoy solo existe `fetch_works_by_ids` que parte de IDs ya
  OpenAlex, no de DOIs; GAP-1 de Nota 17).
- **(b)** CLI: nuevo `b2g resolve` o flag `--resolve` en `seed --from-bib` **[nuevo]** · API/GUI:
  paso del wizard de import / botón "resolver DOIs" **[nuevo]**.
- **(c)** lee `corpus` (`doi`, `openalex_id=NULL`), pega a OpenAlex, escribe `openalex_id` (acepta
  `--email` polite-pool, GAP-2). **Sin este paso, el corpus de la Puerta B tiene `openalex_id=NULL`
  → `enrich`/`chain` devuelven 0** (causa raíz GAP-1).

### Paso 2 — Buscar / navegar la biblioteca (la SUPERFICIE PRIMARIA, hoy ausente)
- **(a)** `service.reads.search_papers` **[nuevo]** (texto + campos + filtros — las tres, decisión PO
  Nota 16 §H1). Complementa las 6 lecturas G2 existentes (`get_paper`, `get_scent`, …).
- **(b)** CLI: `b2g search` opcional (no es el foco; la GUI sí) · API: `GET /api/papers?q=…&filter=…`
  **[nuevo]** · GUI: **vista de Biblioteca** (lista + búsqueda + filtros + ficha) **[nuevo, prioridad 1]**.
- **(c)** lee `corpus` (read-only); sin transición ni mutación.

### Paso 3 — Etiquetar (tags libres ahora; tabla LATERAL)
- **(a)** `service.tags.add_tag/remove_tag/list_tags/papers_by_tag` **[nuevo]**.
- **(b)** CLI: `b2g tag` opcional · API: `POST/DELETE /api/paper/{id}/tags`, `GET /api/tags` **[nuevo]**
  · GUI: editor de tags en la ficha + filtro por tag **[nuevo]**.
- **(c)** escribe una **tabla lateral nueva** `paper_tags` (hermana de `corpus`, NO toca
  `CORPUS_SCHEMA`; ver ADR 0034 y BUG-2). Fuera del `corpus_hash` (como `referenced_but_not_fetched`).

### Paso 4 — Curar (aceptar/rechazar — ya existe, transversal)
- **(a)** `service.curate.accept_papers/reject_papers/curate_paper` **[existe]** (G3).
- **(b)** CLI `b2g accept/reject` + `b2g curate` (CSV) **[existe]** · API `POST /api/paper/{id}/curate`
  **[existe]** · GUI: curación en la ficha / lista **[existe parcial, sobre el grafo; mover a Biblioteca]**.
- **(c)** escribe `corpus.curation_status` + `provenance` (`decided_at` inyectado en la frontera, R2).
  **Transversal: NO transiciona el `CycleState`** (ADR 0016).

### Paso 5 — Forrajear / enriquecer (expandir desde lo curado)
- **(a)** `service.forage.chain` **[mover]** (hoy `run_chain`) · `service.enrich.enrich`
  **[mover]** (hoy `run_enrich`; incluye co-citación 8b — afectado por BUG-1).
- **(b)** CLI `b2g chain` / `b2g enrich` **[existe]** · API/GUI: acciones "expandir" / "enriquecer"
  **[nuevo en API/GUI]**.
- **(c)** `chain` escribe `corpus` (candidatos) + `referenced_but_not_fetched` + transición FORAGED;
  `enrich` puebla `cited_by_id`/`references_doi` (transversal, no transiciona). **BUG-1 rompe la
  pasada 8b** (mismatch de formato `openalex_id`, ver abajo).

### Paso 6 — Proyectar a redes (el DESTINO, no la entrada)
- **(a)** `service.networks.build_network/get_network` **[parcial]** (`get_network` existe en G2;
  `build`/`networks --spec` viven en `cli/commands/` → **[mover]**).
- **(b)** CLI `b2g build` / `b2g networks` **[existe]** · API `GET /api/network/{kind}` **[existe]**
  · GUI: vista de grafo **[existe, con gaps: límite de nodos + bug nodo negro, Nota 16 §H2/§H4]**.
- **(c)** lee `corpus`; `build` escribe `networks/` (cache sellada por `corpus_hash`) + transición BUILT;
  `get_network`/`networks` puros, no transicionan.

### Paso 7 — Snapshot / diff de rondas (el "git de la investigación")
- **(a)** `service.snapshot.snapshot` **[mover]** · `service.reads.list_rounds/compare_rounds` **[existe]** (G2).
- **(b)** CLI `b2g snapshot` **[existe]** · API/GUI: timeline + diff de rondas **[existe en reads, falta UI]**.
- **(c)** escribe `<workspace>/snapshots/`; lee snapshots para el diff.

## Las dos puertas convergiendo (diagrama)

```
  Puerta A: ecuación ──► OpenAlexSource.seed ──┐
                                               │   service.resolve.dois_to_openalex_ids   [nuevo]
  Puerta B: .bib/.ris/.csv ─► *Source.load ──► │◄──(DOI→OpenAlex ID, compartida)──────────┘
                                               ▼
                              normalize_and_dedup (cross-biblioteca, ADR 0031)
                                               ▼
                              corpus vivo (DuckDB)  ── + paper_tags (lateral) [nuevo]
                                               ▼
        buscar/navegar/etiquetar/curar  ──►  forrajear/enriquecer  ──►  proyectar a redes
              (Biblioteca: superficie 1)         (BUG-1 acá)              (grafo: destino)
```

## Tensiones honestas (sub-forks para el PO)

1. **"Flujo completo a servicio" = mucha superficie.** Subir TODO `run_<cmd>` a `service/` es un
   refactor grande (ADR 0028 ya lo anticipó como "−"). **Riesgo de over-engineering bajo** porque
   las funciones `run_<cmd>` ya están aisladas del I/O de Click; el costo es mecánico, no de diseño.
   **Recomendación: mover por demanda** — sube primero lo que la GUI necesita (search, tags,
   ingesta de archivo con resolución, build), difiere lo que solo usa el CLI hoy (p. ej. `validate`,
   `inspect`) sin romper coherencia. El ADR 0032 declara el TARGET; el ROADMAP lo secuencia.
2. **¿`search` y `tags` necesitan subcomando CLI?** El CLI agente-native podría no necesitarlos
   (un agente hace SQL o usa `inspect`). **Recomendación: servicio sí (la API/GUI lo exige);
   subcomando CLI opcional/diferido.** ← PO decide si quiere paridad CLI.
3. **Granularidad de la resolución DOI→ID:** ¿paso automático dentro de `seed --from-bib` (opt-in con
   `--resolve`) o subcomando separado `b2g resolve`? Nota 17 propone ambas. **Recomendación:
   operación de servicio única + exponerla como flag `--resolve` Y como `b2g resolve`** (mismo
   servicio, dos adaptadores). ← PO confirma.
4. **Tabla lateral de tags vs. schema extensible (BUG-2):** son dos problemas distintos que comparten
   síntoma. Tags → tabla lateral (ADR 0034, decidido). La rigidez general del schema (columnas extra
   del usuario, BUG-2) **queda como decisión separada** del PO: ¿el backend debe tolerar columnas
   extra o el schema es deliberadamente cerrado? **No se resuelve acá.** ← PO decide (ver ADR 0034
   §Alcance).
5. **Grafo: límite de nodos + framework.** El cap de nodos es requisito (489/20.535 cuelga). El
   spike Sigma.js vs Cytoscape es medición, no decisión de arquitectura. Fuera del alcance de estos
   ADR (son work-items de la GUI). ← solo se nombra; no se decide acá.

## BUG-1 — detalle load-bearing (para el work-item)

`enrichers/openalex.py::_enrich_cited_by` arma `target_ids` desde `Col.OPENALEX_ID` **tal como vive
en el corpus** y luego busca `citing_dict.get(str(oa_id))`. Pero `OpenAlexSource.fetch_citing_batch`
normaliza su entrada con `_oa_id_short(...)` y **devuelve las keys en formato corto** (`Wxxx`). Si el
corpus guardó `openalex_id` con prefijo URL (`https://openalex.org/Wxxx` — el caso real del tercero),
el lookup **siempre falla → `[]`** y la pasada 8b queda inútil (`citing_new=0`). **Fix:** normalizar
`openalex_id` a un único formato en el borde (recomendado: el corto, coherente con `_work_to_row` que
ya emite corto) o que el lookup tolere ambas keys. Es política de una línea + test de regresión.
