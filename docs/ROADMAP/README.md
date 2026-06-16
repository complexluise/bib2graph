# ROADMAP — bib2graph (secuencia de construcción desde cero)

> Secuencia de construcción **clean-room**, no una migración de v0. El orden es deliberado: el
> **núcleo puro y sus tests van primero**, después las **costuras por defecto** (store stateful
> y source OpenAlex) hasta tener el pipeline con biblioteca viva funcionando, y recién después
> lo opcional. Cada hito declara **qué historias de usuario satisface** (PRD §7), sus
> **criterios de aceptación** (DoD) y los **tests que se escriben** (TDD, los justos). Fecha:
> 2026-06-15.
>
> Reordenado tras el **giro** (`Notas/04`–`07`) y los ADR
> [0007](../decisiones/0007-openalex-backbone.md) (OpenAlex backbone),
> [0008](../decisiones/0008-wedge-forrajeo.md) (wedge = forrajeo),
> [0009](../decisiones/0009-biblioteca-viva-duckdb.md) (biblioteca viva en DuckDB),
> [0010](../decisiones/0010-agente-native-columna.md) (agente-native columna),
> [0011](../decisiones/0011-thesaurus-multilingue.md) (thesaurus). Diseño objetivo en
> [`ARCHITECTURE.md`](../ARCHITECTURE.md); contratos en [`API.md`](../API.md) (ya reconciliado).
>
> **Estado de construcción (2026-06-15):** **Hitos 0, 1, 2, 1.5, 3, 4, 5 y 6 CONSTRUIDOS**: el flujo
> `seed → chain → filter → build → export` corre de una **ecuación** a un **GraphML** **sin escribir
> código**, sobre la biblioteca viva. El Hito 6 (`b2g`, 11 subcomandos, envelope `--json` versionado,
> exit codes 0–5, `--store` global, `LoopState` automático) está en el ADR
> [0021](../decisiones/0021-cli-agente-native-contrato.md); el forrajeo (`Forager`, `preview` sin red,
> filtros que marcan `rejected`) en el ADR
> [0020](../decisiones/0020-metodo-forrajeo-scent-filtros-reject.md).
>
> ⚠️ **Ya NO se afirma "v0.2 con capacidades completas".** El **red-team de la
> [Nota 06](../Notas/06-critica-as-built-v0.2.md)** encontró tres grietas en el corazón de la propuesta
> (forrajeo lineal con vocabulario de ciclo; "IA del producto" casi vapor; reproducibilidad rota),
> y el PO bloqueó un **nuevo modelo conceptual** (scent bibliométrico **sin IA**, FSM cíclico,
> identidad-vs-procedencia, capa constants/schemas (con `ProvenanceEvent`); ADR
> [0022](../decisiones/0022-producto-sin-ia-generativa.md)/[0023](../decisiones/0023-capa-constants-modelos-schema.md)
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
> **Lo que falta** (tras la remediación R1–R5 y el **Hito 8 ✅** —`Enricher` co-citación end-to-end—,
> hacia v1.0): Hitos 7 (dedup fuzzy), 9 (`NetworkSpec` YAML), 10 (viz) y 11 (Zotero/Neo4j). Tras el **2º giro**
> (acta del PO; ADR [0015](../decisiones/0015-corpus-tabular-backend.md)–[0019](../decisiones/0019-concurrencia-diferida.md))
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
reproducido, ver [`VERSIONING.md`](../../VERSIONING.md)). El **mecanismo de release es
`release-please`** (ver [`VERSIONING.md`](../../VERSIONING.md) / ADR 0006), **ya conectado**
(`.github/workflows/` + CI). `commitizen` queda para lintear commits y **previsualizar** el bump
(`cz bump --dry-run`); no es el publicador. Los tags **`v0.1.0`, `v0.2.0` y `v0.3.0` ya están
publicados en `origin`** (con su GitHub Release); lo que sigue **pendiente es la publicación a
PyPI** (decisión del PO: por ahora solo GitHub Releases, hasta configurar *trusted publishing*
OIDC), no el push de tags. Cortes acordados:

- **v0.1 — pipeline mínimo end-to-end (Hitos 1–4, incl. el rework 1.5) · ✅ FEATURE-COMPLETE
  (2026-06-15):** de una **ecuación de búsqueda a las redes desde código Python**, sobre una
  **biblioteca viva en DuckDB**. Incluye `Corpus` (sobre `TabularBackend`),
  proyectores/analizadores/export, `DuckDBBackend`/`DuckDBStore` y `OpenAlexSource`/`BibtexSource`.
  Con el **Hito 4 terminado**, todas las piezas existen y se componen en código (ver el ejemplo de
  `API.md` §12). **Sin CLI ni forrajeo todavía** (eso es v0.2). **Tag `v0.1.0`** creado el
  2026-06-15, **publicado en `origin`**.
> ⚠️ **Honestidad sobre "capacidades completas" (v0.2):** se refiere al *flujo* `seed → chain →
> filter → build → export`, NO a la totalidad del producto. En v0.1/v0.2 faltaba la **co-citación
> end-to-end** (`cited_by_id` quedaba vacío tras el seed → 0 aristas hasta el 2º nivel de fetch);
> el **Hito 8 ✅ (Ciclos 8a + 8b)** la cerró: `b2g enrich` puebla `cited_by_id`. Y el
> *information scent* es —en el AS-BUILT— una **heurística de frecuencia de enlace** (la remediación
> R4 lo eleva a scent bibliométrico vía proyectores). **Corrección 2026-06-15 (ADR 0022):** lo que
> antes figuraba acá como "stub/futuro de IA" —`explain_candidate`, el extra `[llm]` y la **máquina
> de tensiones**— **NO es futuro: se RETIRA** (el producto no usa IA generativa). Ver
> [`Notas/06-critica-as-built-v0.2.md`](../Notas/06-critica-as-built-v0.2.md) y la **tanda R1–R5** abajo.

- **v0.2 — forrajeo + CLI agente-native (Hitos 5–6) · ✅ CAPACIDADES COMPLETAS (2026-06-15):**
  chaining rankeado, `Preprocessor`, filtros PRISMA (comando **`filter`**), `b2g status`
  (`LoopState`) y el CLI `b2g` con `--json`. **El forrajeo, el `Preprocessor` y los filtros (Hito 5)
  y el CLI agente-native (Hito 6) están construidos.** El CLI expone **13 subcomandos** (`seed`,
  `chain`, `filter`, `build`, `export`, `snapshot`, `status`, `inspect`, `validate`, `accept`,
  `reject`, **`monitor`**, **`enrich`**) con envelope `--json` versionado y exit codes 0–5 (ADR
  [0021](../decisiones/0021-cli-agente-native-contrato.md)). El 12° **`monitor`** (cleanup pre-v0.3)
  re-chequea citantes nuevos del corpus y transiciona a `MONITORED`; el 13° **`enrich`** (Hito 8,
  ADR [0025](../decisiones/0025-enricher-cocitacion-openalex.md)) resuelve refs→DOI **+ co-citación
  end-to-end** (`--max-citing`) y **no transiciona** el ciclo. El `accept`/`reject` programático
  sobrevive (ahora como subcomando CLI); la curación interactiva rica (`curate`) y la GUI son
  futuro. Acá se cumple el criterio "V1 hecha" del PRD §9 a nivel de *capacidades* (el número de
  versión sigue en 0.y). **Tag `v0.2.0`** creado el 2026-06-15, **publicado en `origin`**.
- **v0.3 — remediación (Hitos R1–R5) · ✅ COMPLETA (2026-06-16):** cierra la brecha AS-BUILT↔TARGET del red-team (Nota 06) y
  del modelo nuevo (ADR 0022/0023 + enmiendas): capa `constants`/`schemas` (con `ProvenanceEvent`) única,
  identidad-vs-procedencia con reproducibilidad bit a bit, FSM cíclico de dominio (`cycle.py`) con
  curación transversal visible, scent bibliométrico vía proyectores (sin IA), y robustez (bulk-load,
  UTF-8, footguns). **Es un breaking change de comportamiento interno** (el `corpus_hash` cambia al
  excluir timestamps; el `LoopState` se mueve a `cycle.py`), pero **no rompe el flujo de 10 minutos**
  ni el contrato `--json` externo. Sin esto, el claim de reproducibilidad y de "ciclo no lineal" no
  se sostiene (Nota 06, RAÍZ 1/2).
- **v0.4+ — opcionales (Hitos 7–9):** dedup fuzzy, `Enricher` de co-citación (**Hito 8 ✅**:
  refs→DOI + co-citación end-to-end), `NetworkSpec`.
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

> **Sobre los conteos "N tests verdes" por hito.** Las cifras que aparecen en los
> archivos de hito (`73`/`98`/`133`/`192`/`214`/`247`/`275`/`291`/`319`/…) son
> **snapshots históricos** del momento en que se cerró cada hito; **no** se
> actualizan retroactivamente (son historia). La **cuenta autoritativa actual** la
> da el CI (`uv run pytest`, en `.github/workflows/ci.yml`), que es la **fuente de
> verdad del gate** — no estos números.

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


## Índice del ROADMAP

Este ROADMAP se divide en cuatro tramos por grupos de hitos. Este README es el documento
limpio y actual; el cuerpo de cada hito vive en su archivo:

- **[01 · Núcleo y biblioteca viva (Hitos 0–3 + 1.5)](01-nucleo-v0.1.md)** — andamiaje, `Corpus`,
  proyectores/analizadores/export, rework a `TabularBackend` y `DuckDBBackend`/`DuckDBStore`.
  **v0.1 ✅ feature-complete.**
- **[02 · Fuentes, forrajeo y CLI (Hitos 4–6)](02-fuentes-forrajeo-cli-v0.2.md)** — `OpenAlexSource`/
  `BibtexSource`, `Forager`/`Preprocessor`/filtros PRISMA y el CLI `b2g` agente-native.
  **v0.2 ✅ capacidades completas.**
- **[03 · Remediación R1–R5 (v0.3)](03-remediacion-r1-r5-v0.3.md)** — cierra la brecha AS-BUILT↔TARGET
  del red-team (Nota 06): capa `constants`/`schemas`, identidad-vs-procedencia reproducible, FSM
  cíclico (`cycle.py`), scent bibliométrico (sin IA) y robustez. **v0.3 ✅ remediación completa.**
- **[04 · Lo que viene (Hitos 7–11 + costuras futuras)](04-lo-que-viene.md)** — dedup fuzzy,
  `Enricher` de co-citación, `NetworkSpec` YAML, viz, Zotero/Neo4j. **Lo que viene (hacia v1.0).**


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
| D1 cinco proyecciones | 2 + 8 ✅ (co-citación) | co-citación end-to-end vía `b2g enrich` (8b); `Networks.quick` → 4/5 redes según `cited_by_id` |
| D2 métricas y comunidades | 2 | |
| D3 asortatividad + composición + proxy | 2 | |
| D4 export GraphML/CSV | 2 | |
| E1 snapshot reproducible | 1 + 6 ✅ | `Corpus.snapshot` + `b2g snapshot` |
| E2 CLI `--json` + exit codes | 0 (principios) + 6 ✅ (CLI) + cleanup pre-v0.3 ✅ (`monitor`) + 8 ✅ (`enrich`) | `b2g` **13 subcomandos** (Hito 6 entregó 11; `monitor` se sumó en el cleanup pre-v0.3 → `MONITORED`; `enrich` en el Hito 8 —refs→DOI + co-citación, `--max-citing`—, ADR 0025, sin transición), envelope `--json` versionado, exit 0–5 (ADR 0021) |

