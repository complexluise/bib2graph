# ROADMAP · Fuentes, forrajeo y CLI (Hitos 4–6)

> ← Volver al [índice del ROADMAP](README.md)

## Hito 4 — Costura por defecto (red): `OpenAlexSource` + `BibtexSource` · ✅ TERMINADO

> **Construido** así: `src/bib2graph/sources/` con `Source` (Protocol), `SeedResult` (valida
> `corpus: Corpus` en runtime vía `arbitrary_types_allowed`, sin circularidad), `OpenAlexSource` y
> `BibtexSource`. **Con este hito, v0.1 (Hitos 1–4 + 1.5) queda feature-complete.**
> `OpenAlexSource(*, email=None, api_key=None, transport=None, base_url=…, max_results=200)`:
> traducción **PASSTHROUGH** (envuelve la ecuación en `title_and_abstract.search:(...)` y **reporta**
> los límites del ADR [0007](../decisiones/0007-openalex-backbone.md) — NEAR / comodín / tags WoS — sin
> traducirlos; el **traductor WoS→OpenAlex queda diferido a v0.2**); flag `native=True` en `seed()`
> para pasar la query cruda. Cliente `httpx` con **transport inyectable** (tests con `MockTransport`,
> sin red en CI), credenciales inyectadas (arg → `OPENALEX_API_KEY` → `~/.openalex/credentials` →
> polite pool, ADR [0012](../decisiones/0012-openalex-credenciales.md)), **cursor paging** con tope
> `max_results`, mapeo a las 22 columnas (refs inline; `cited_by_id=[]` **diferido al
> chaining/Enricher**; afiliaciones per-autor; `abstract` reconstruido defensivo del
> `abstract_inverted_index`) y **puebla `Manifest.openalex_version`** (header `x-openalex-api-version`
> o fecha ISO del fetch, ADR [0017](../decisiones/0017-reproducibilidad-historia-snapshot.md)) +
> `equations`. `BibtexSource` (extra **`[bibtex]`**, import perezoso de `bibtexparser`): acceso
> defensivo (fix del bug T1, campos faltantes sin `KeyError`), mínimo universal; `seed()` lanza
> `NotImplementedError` (BibTeX no siembra por ecuación → usar `load()`). Semillas con `is_seed=True`,
> `curation_status="candidate"` y evento de provenance. Nuevo `Corpus.with_manifest()` como API
> pública para actualizar el manifest sin tocar el backend (lo reusarán Forager/Enricher/Filter).
> Verifier PASA (**133 tests** verdes; mypy/ruff limpios; núcleo sin `duckdb`). Decisiones de
> implementación de la IA en [`decisiones/registro-ia.md`](../decisiones/registro-ia.md) (Hito 4).

**Alcance**

- `OpenAlexSource` (ADR 0007, API.md §2 sobre `httpx`): implementación de referencia del **contrato
  `Source` agnóstico** (ADR [0018](../decisiones/0018-source-agnostico-calidad.md)) — entrega el
  **mínimo universal** (id/título/año/autores/keywords) **y** el **enriquecimiento completo**
  (`references_id` + `cited_by_id` + afiliaciones **per-autor** + instituciones). Traduce la
  **ecuación de búsqueda** a query OpenAlex, expone la **query ejecutada + reporte de traducción**
  (`SeedResult`) y **puebla `Manifest.openalex_version`** al sembrar (ancla la foto, ADR
  [0017](../decisiones/0017-reproducibilidad-historia-snapshot.md)). **Pool cortés** (email inyectado;
  API key opcional desde feb-2026, ADR [0012](../decisiones/0012-openalex-credenciales.md)). Escape
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
> [0020](../decisiones/0020-metodo-forrajeo-scent-filtros-reject.md). Verifier PASA (**192 tests**
> verdes; preview network-free corregido). Decisiones de implementación de la IA en
> [`decisiones/registro-ia.md`](../decisiones/registro-ia.md) (Hito 5). El comando CLI **`filter`** y la
> curación interactiva llegan en el Hito 6.
>
> ⚠️ **Reconciliación 2026-06-15 (ADR [0022](../decisiones/0022-producto-sin-ia-generativa.md)):** lo
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
> [0021](../decisiones/0021-cli-agente-native-contrato.md). Verifier PASA (**214 tests** verdes;
> mypy/ruff limpios; el núcleo sigue importando sin `duckdb`). Decisiones de implementación de la IA
> en [`decisiones/registro-ia.md`](../decisiones/registro-ia.md) (Hito 6).

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
- **`status`** expone el `LoopState` (ADR [0016](../decisiones/0016-maquina-estados-lazo.md)):
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
