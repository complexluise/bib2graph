# 06 — Crítica del AS-BUILT v0.2 (red team multi-perspectiva)

> Red team adversarial del **código construido** (no del diseño): v0.2, Hitos 0–6 + 1.5.
> Cinco lentes —**arquitectura, producto, funcionamiento, rigor científico, fidelidad al
> ciclo humano de la [Nota 05](05-ciclo-investigacion-humano.md)**— corridas contra el
> repositorio tal cual está. Hermano de [`critica-base.md`](critica-base.md) (que rompió el
> *diseño*) y de [`01-lecciones-v0.md`](01-lecciones-v0.md) (postmortem de v0). El objetivo es
> el mismo: romper a propósito lo que tenemos para que la próxima vuelta nazca de una crítica
> honesta. Las referencias `archivo:línea` apuntan al código de v0.2 verificado el 2026-06-15.
> Fecha: 2026-06-15.

## Tesis central

v0.2 expió bien los pecados de v0 (núcleo puro, costuras tipadas, OpenAlex, biblioteca viva,
CLI) — pero al pasar del diseño al código aparecieron **tres grietas que tocan el corazón de la
propuesta**: el lazo de investigación es lineal con vocabulario de ciclo, la IA que vende el
producto es casi vapor, y la "pureza/reproducibilidad" —el valor central— está rota en varios
lugares concretos. Además, no corre a escala y un bug rompe el contrato agente-native en
Windows. Nada de esto es retórica: cada punto tiene su `archivo:línea`.

---

## LO MÁS GRAVE

### RAÍZ 1 — Pipeline con vocabulario de ciclo; la IA del lazo es casi vapor

La [Nota 05](05-ciclo-investigacion-humano.md) §3 hace de la **no-linealidad** (el lazo
2→3→4→1) la propiedad central, y dice explícitamente que "cualquier diseño que asuma un
pipeline lineal contradice a Bates, Ellis y Kuhlthau a la vez". El AS-BUILT es justo eso:

- **Máquina de estados lineal.** `LoopState = SEEDED→FORAGED→FILTERED→BUILT`
  (`src/bib2graph/backends/duckdb.py:67-78`) es el orden lineal "query → resultados → fin". La
  no-linealidad existe solo como comentario ("transiciones permisivas: no se bloquea ningún
  salto"), no como modelo de las fases. El CLI transiciona automáticamente en ese orden
  (`seed→SEEDED … build→BUILT`).
- **La curación —la fase "irreductiblemente humana" (Nota 05 §4, pasos 0/4/7)— no es parte del
  lazo.** `accept`/`reject` **no transicionan** estado (`cli/commands/accept.py:104`: "No
  transiciona el LoopState") y **no aparecen** en `transitions_available` de `status`
  (`cli/commands/status.py:19-34`: el mapa lista `seed/chain/filter/build/export/snapshot/
  inspect/validate`, nunca `accept`/`reject`). Un humano (o un agente) que lea el mapa del lazo
  **no ve la curación**, que es precisamente lo único irreductiblemente humano.
- **De los 2 puntos de inserción de IA de la Nota 05, entregamos 1, y ese 1 no tiene IA.** La
  Nota 05 §4 promete (L79-80) que "la **bibliometría ES el information scent**: las redes de
  citación/coupling le dan a la IA mejor olfato que los embeddings… Mapea a los **proyectores**".
  El código rankea por **conteo aritmético de citas directas**: `compute_backward/forward_scent`
  son `Counter`/`sum` sobre `references_id`/`cited_by_id` (`foraging/scent.py:27-125`), **sin
  proyectores, sin grafo, sin bibliometría**. La Inserción 2 (sensemaking/tensiones, el "máximo
  valor" según Nota 05 §4) **no existe**; `explain_candidate` —el único gancho de LLM— es
  `NotImplementedError` permanente (`foraging/explain.py:47`) y el extra `[llm]` está vacío.

**Matiz de honestidad:** el ADR [0020](../decisiones/0020-metodo-forrajeo-scent-filtros-reject.md)
**ya es honesto** — define el scent como "frecuencia de enlace, **no** acoplamiento/co-citación/
centralidad" y marca `explain_candidate` como stub. La sobre-venta no está en el ADR; está en
la **Nota 05** (que aún promete bibliometría-como-scent) y en **README/AI_DISCLOSURE**, que
dicen "el producto incorpora IA en el lazo (forrajeo y curación asistidos)" cuando el forrajeo
es un conteo y la curación es 100% humana.

**Recomendaciones (código + decisión PO):**
1. (PO) Decidir si el scent debe **convertirse** en lo que la Nota 05 promete (bibliometría real
   como olfato) o si la Nota 05 / README / AI_DISCLOSURE deben **bajar la promesa** a "heurística
   de frecuencia de enlace". Hoy hay drift entre la Nota 05 y el ADR 0020.
2. (coder) Si la curación es fase del lazo, debería figurar en `transitions_available` y/o tener
   su propio estado (`CURATED`) — o documentar explícitamente que la curación es transversal,
   no un estado.

### RAÍZ 2 — Reproducibilidad / pureza (el valor central) rota en 3 lugares

`facade.py:6` promete: "Ambos métodos son estáticos y **puros**: mismo corpus + mismo spec →
mismo `NetworkArtifact`". El ADR [0017](../decisiones/0017-reproducibilidad-historia-snapshot.md)
promete que "otro investigador reproduce **bit a bit**" un snapshot por su `corpus_hash`. Tres
roturas concretas:

- **Reloj en el núcleo.** `accept`/`reject` estampan `datetime.now(UTC)` en el evento de
  provenance (`backends/memory.py:281`), y `compute_corpus_hash` **hashea todos los campos de
  cada fila, incluido `provenance`** (`backends/memory.py:50-75`). Por lo tanto, **dos corridas
  que aceptan los mismos ids producen `corpus_hash` distintos** → el snapshot no es reproducible
  bit a bit, contradiciendo el ADR 0017 y `facade.py:6`. Es exactamente el "reloj en el núcleo"
  que el rediseño decía haber eliminado. *(Esto entra a `corpus.py:386,403` vía `apply_curation`.)*
- **Comunidades no deterministas.** `detect_communities(method="louvain")` llama
  `community_louvain.best_partition(g)` **sin `random_state` ni `resolution`**
  (`networks/analyzer.py:120-129`) → las comunidades cambian entre corridas. Contradice la
  promesa de pureza de `facade.py:6`.
- **Co-citación parcial sin aviso.** El `CoCitationProjector` proyecta desde los `cited_by_id`
  que tengas en la tabla (`networks/projectors.py:299-327`); tras el seed `cited_by_id` está
  vacío (diferido al chaining/Enricher). El resultado no es un "subset fiel" sino un **artefacto
  de qué citantes fetcheaste**, y `Networks.build(... kind="cocitation")` **no emite warning ni
  marca el artifact como parcial**. El disclaimer existe solo en el docstring del proyector.

**Recomendaciones (todas de código):**
1. (coder) Excluir `provenance` (o al menos los timestamps de decisión) del `corpus_hash`, **o**
   eliminar `datetime.now()` del núcleo e inyectar el reloj. Sin esto, el snapshot no cumple
   ADR 0017.
2. (coder) Pasar `random_state` (y exponer `resolution`) a Louvain.
3. (coder) Que `build(kind="cocitation")` emita un warning / marque `partial=True` en el
   artifact cuando no haya pasado por el 2º nivel de fetch.

### RAÍZ 3 — No corre a escala + bug que rompe el contrato agente-native

- **O(n²) en toda carga.** Cada `add_paper` llama `_clone()`, que **re-upserta la tabla entera**
  (`backends/duckdb.py:319,368`: `_clone` → `_upsert_table` itera todas las filas). Todos los
  caminos de carga (seed/load OpenAlex, BibTeX, forager) usan ese loop fila-a-fila. Existe el
  bulk `Corpus.from_arrow` y **no se usa** en los loaders.
- **N+1 de red en forward chaining.** El forrajeo forward hace **1 HTTP por paper**
  (`foraging/forager.py:307` → `sources/openalex.py:394-425`), **sin batching ni retry para
  429/5xx**. Con un corpus mediano son cientos de requests seriales y frágiles ante rate limit.
- **BUG VERIFICADO — acentos corruptos en Windows.** El envelope JSON usa
  `json.dumps(..., ensure_ascii=False)` pero **no fuerza UTF-8 en stdout**
  (`cli/_envelope.py:67`). En Windows (consola cp1252 por defecto) un agente recibe `ecuaci�n`
  en vez de `ecuación`. **Rompe el contrato "agente-native"** que es columna del producto (ADR
  0010/0021), y afecta también `--help`.

**Recomendaciones (todas de código):**
1. (coder) Usar el bulk `from_arrow` en los loaders en vez del loop `add_paper`/`_clone`.
2. (coder) Batchear `fetch_citing` y agregar retry/backoff para 429/5xx.
3. (coder) Forzar `sys.stdout`/`stderr` a UTF-8 (o `encoding="utf-8"` explícito) en el entry
   point del CLI. Es el arreglo de mayor impacto/menor costo de toda la lista.

> **RESUELTO en R5 (2026-06-16):** bulk-load (`Corpus.from_arrow` en los cuatro loaders) y UTF-8 en la
> frontera (`_force_utf8`) implementados; el N+1 de red ganó **retry/backoff** (el batching-por-OR quedó
> diferido como mejora de performance). Ver ROADMAP Hito R5 y registro-ia R5.1–R5.3. *(Hallazgos arriba
> = rastro histórico, sin reescribir.)*

### CONSTANTS — no hay módulo de constantes

No existe un módulo de constantes: ~62 nombres de columna viven como **string-literal**
repartidos en 14 archivos (`"references_id"`, `"cited_by_id"`, …), y los valores de
`curation_status` (`candidate`/`accepted`/`rejected`) se redefinen como literales en múltiples
módulos (`schemas.py`, `backends/memory.py`, `backends/duckdb.py`, `filters/prisma.py`,
`cli/commands/validate.py` — verificado: 11 archivos contienen estos literales). Un typo en una
columna no falla en tiempo de import; es una clase de bug latente (eco de la lección 4 de v0:
drift de esquema).

**Recomendación (coder):** `constants.py` con `class Col(StrEnum)` y `class
CurationStatus(StrEnum)`; reemplazar los literales por referencias.
**Lo bueno (en justicia):** los **exit codes** ya están centralizados en la jerarquía
`B2GError` (`cli/_errors.py`) — el patrón correcto, solo falta replicarlo para columnas/estados.

### MODELS — la decisión "vistas derivadas" se sostiene; faltan 2 modelos reales

La decisión de v0.2 de que `Paper`/`Author`/`Keyword`/`Institution` son **vistas derivadas, no
tipos** **es correcta y se sostiene** — NO hay que crear clases-entidad. El dolor está en dos
estructuras informales que sí piden modelo:

- **(a) El evento de provenance.** Es un `dict` por string-keys construido a mano en ≥4 sitios y
  parseado con un `except` que **se traga JSON corrupto en silencio** (`backends/memory.py:78-95`,
  `_parse_provenance`: `except (json.JSONDecodeError, TypeError): return []`). → `ProvenanceEvent(BaseModel)`.
- **(b) `PaperRow` y `CORPUS_SCHEMA`** están duplicados a mano (22 campos) → una sola fuente de
  verdad.
- **Patrón frágil relacionado:** el `Manifest` se reconstruye campo-a-campo en 5+ sitios
  (`sources/openalex.py:462`, `foraging/forager.py:259`, `filters/prisma.py:198`,
  `preprocessors/preprocessor.py:58,107`, `corpus.py:462`) → usar `model_copy(update=...)`.

**Recomendaciones (coder):** `ProvenanceEvent(BaseModel)`; deduplicar `PaperRow`↔`CORPUS_SCHEMA`;
`Manifest.model_copy(update=...)`.

### RIGOR CIENTÍFICO — el doc que da nombre a todo define mal el método

- **`docs/metodología.md` define MAL la co-citación.** El Cypher de ejemplo
  (`metodología.md:50-56`) es `(p1)-[:REFERENCES]->(ref)<-[:REFERENCES]-(p2)` = **referencias
  compartidas** = **acoplamiento bibliográfico**, NO co-citación (que es **citantes**
  compartidos). Irónicamente, la prosa del fundamento (`metodología.md:9`, "ambos son
  referenciados por un tercer documento") **sí** describe bien la co-citación: el documento se
  contradice a sí mismo, y el algoritmo que muestra es el equivocado. El **código está bien**
  (`networks/projectors.py:299-327` usa `cited_by_id` = citantes compartidos): es el **doc** el
  que miente, en el método que da nombre a todo el proyecto.
- **`metodología.md` está desincronizado una arquitectura entera.** Habla de Neo4j/Cypher,
  Semantic Scholar/Scopus, BibTeX como entrada, umbrales hardcodeados (≥200/≥90%/5 países/≥10
  autores) — todo **pre-giro OpenAlex**. Es el documento más drifteado del repo.
- **Desambiguación de autores sobre-prometida.** Sin ORCID, la identidad de autor cae al display
  name normalizado (`sources/openalex.py:211-214`, `preprocessors/normalize.py:40-54`) →
  falsos merges/splits en co-autoría. `metodología.md:27,104` afirma que "se resuelven
  duplicidades / se reducen ambigüedades en nombres de autores" — sobre-promesa.
- **`min_countries` es teatro de calidad.** El proxy cuenta **instituciones únicas**, no países
  (`networks/analyzer.py:314-321`: `unique_insts` sobre `institutions_id`), así que la métrica
  Norte-Sur que el caso IED necesita **casi siempre da verde**. *(En justicia: el report incluye
  un campo `proxy` honesto en `analyzer.py:349-352`.)*
- **Forrajeo por scent = sesgo de confirmación / efecto Mateo.** Rankear candidatos por cuánto
  ya se conectan con tu corpus refuerza lo central y popular. Presentarlo como compatible con la
  exhaustividad PRISMA es delicado: el ADR
  [0020](../decisiones/0020-metodo-forrajeo-scent-filtros-reject.md) cubre PRISMA en el **conteo
  de exclusiones**, no en el **sesgo de selección aguas arriba** del propio scent.

**BIEN (reconocer):** el **acoplamiento bibliográfico** es correcto y determinista; los **filtros
marcan `rejected` sin borrar** (trazable PRISMA, reversible); el **ADR 0017**
(reproducir = re-leer el snapshot, no re-correr la ecuación) es epistemológicamente correcto —
su problema no es el principio sino que el `corpus_hash` no lo cumple (RAÍZ 2).

### PRODUCTO — ¿producto, o instrumento de un paper?

La lente más incómoda. La pregunta dura: **¿es un producto, o un instrumento muy bien
documentado para un paper sobre tu propia metodología?** Las señales apuntan a lo segundo:

- **Caso único = IED** (tu paper); thesaurus ~6% curado, sobre IED.
- **El wedge entregado (forrajeo) es el prerequisito commodity** que ResearchRabbit / Inciteful /
  Connected Papers ya hacen — y las propias Notas
  ([04 §5](04-direccion-ia-in-the-loop.md), [05 §6](05-ciclo-investigacion-humano.md)) dijeron
  que **NO es el hueco**. El **moat** (la máquina de tensiones, Inserción 2) se difirió a v2
  (ROADMAP, "Costuras futuras").
- **"v0.2 capacidades completas / V1 feature-complete" sobre-vende** (README:15,
  ROADMAP §"Mapa de releases"): co-citación end-to-end (Hito 8) y el único gancho de IA
  (`explain_candidate`) son stubs/futuros.
- **Las barreras de adopción se apilan:** Python+CLI, sin GUI, sin viz, solo OpenAlex,
  GraphML→insight ajeno, alpha hecho-con-IA. "Enseñable en una tarde"
  ([`referentes.md`](referentes.md) §5) **contradice** "requiere Python/CLI" (PRD §3, L107).
- **Riesgo OpenAlex tier-1 subestimado:** ya pide API key desde feb-2026; muta (de ahí el ADR
  0017); la co-citación da **0 aristas** con datos reales hasta el Hito 8.

**Recom #1 (PO):** conseguir **UN usuario real, distinto del autor, en un dominio distinto a
IED**, que complete el flujo de 10 minutos. Es la prueba que más decide producto-vs-instrumento.

**BIEN (reconocer):** la **honestidad técnica documentada** (disclaimers de proxy, "qué no se
probó", ADRs que admiten trade-offs) está **muy por encima del promedio** del nicho. El problema
no es que los límites no se conozcan: es que se **documentan-y-difieren** en vez de llegar al
usuario o resolverse.

---

## Catálogo de secundarios (con `archivo:línea`)

- **`@handle_errors` casi sin testear** (`cli/_errors.py` ~51% cobertura; ningún test asserta
  `exit_code==4`; los tests de 3/5 mockean la unidad bajo prueba). `except` demasiado anchos:
  **rama muerta** en el manejo de `OSError` (`_errors.py:139-147`: el `if isinstance(...,
  StoreLockedError)` y el `else` hacen lo mismo, exit 5); `AttributeError`→"Capacidad no
  disponible" es **engañoso** (un bug real se reporta como capacidad faltante,
  `_errors.py:155-159`); `except Exception` en `detect_communities` traga el fallo
  (`networks/facade.py:104`: red sin comunidades en silencio); `_lib_version` con fallback
  `"0.0.0"` mete **versión falsa** en el `Manifest` (`corpus.py:46-53`).
- **`b2g status`/`validate` auto-crean el store** ante un typo en `--store` (footgun verificado).
- **`.bib` roto se traga sin warning** (`sources/bibtex.py:206,210`); **filtros PRISMA con
  campo/op desconocido → no-op silencioso** (`filters/prisma.py:115`).
- **`cocitation_quality_report` recibe `g` que ignora** (parámetro muerto, `networks/analyzer.py:277`)
  — anti-patrón que [`ARCHITECTURE.md`](../ARCHITECTURE.md) §8 dice evitar.
- **`_QUICK_KINDS` duplica el `Literal` de `NetworkSpec.kind`** (`networks/facade.py:39` vs
  `networks/spec.py:42-48`).
- **SQL por interpolación de strings en `merge`** (`backends/duckdb.py:417,423`) — hoy seguro
  (los ids son hashes) pero frágil.
- **Docstrings de scent mienten sobre la dirección** (`foraging/scent.py:11,80` vs la impl en
  `:114`).

> **RESUELTO en R5 (2026-06-16), salvo lo indicado:** rama muerta de `_errors.py`, `AttributeError`
> engañoso (→ `DependencyError` por pre-check en el borde CLI), `except Exception` de
> `detect_communities`, `_lib_version` `"0.0.0"`→`"unknown"`, auto-creación del store
> (`open_store_readonly`), `.bib`/filtros PRISMA silenciosos (→ raise/warning), param muerto `g`, y
> `_QUICK_KINDS`/`Literal` duplicado (→ `NetworkKind` fuente única) están **cerrados**. Los docstrings
> de scent ya se corrigieron en **R4**. **No resueltos (decisión consciente):** el **SQL por
> interpolación en `merge`** (hoy seguro porque los ids son hashes; queda como mejora de robustez
> futura). Ver registro-ia R5.4–R5.6. *(Hallazgos arriba = rastro histórico, sin reescribir.)*

---

## Mapa de impacto en los docs

Clasificación: **(1)** corrección factual/honestidad, bajo riesgo → **aplicada ya**;
**(2)** decisión del PO, estratégica → **recomendada, no aplicada**; **(3)** cambio de código
→ recomendación para el `coder`/feature-cycle.

| Documento | Qué afirma hoy que la crítica contradice | Cambio | Clase |
|---|---|---|---|
| `docs/metodología.md` | Cypher de co-citación es en realidad **acoplamiento** (`:50-56`); arquitectura **Neo4j/Scopus/BibTeX** entera; "se resuelven duplicidades de autores" (`:27,104`) | Aplicado: nota de corrección al inicio + al Cypher marcando que define acoplamiento, que el código usa citantes (`cited_by_id`), que la arquitectura es OpenAlex/DuckDB, y que la desambiguación de autores es parcial (sin ORCID → display name). Reescritura completa = decisión del PO | (1) parcial + (2) |
| `README.md` | "v0.2 con **capacidades completas**" (`:15`); "el **producto incorpora IA** en el lazo (forrajeo y curación asistidos)" (`:43`) | Aplicado: "capacidades completas" → matizado; el claim de IA-en-el-producto → "heurística de frecuencia de enlace + curación humana; la IA (LLM/tensiones) es futura" | (1) |
| `AI_DISCLOSURE.md` | "**IA en el producto** — la librería usa IA y heurísticas… el forrajeo rankea por *information scent*… curación asistida" (`:29-34`) | Aplicado: precisado que el scent es **heurística determinista de frecuencia de enlace** (no LLM/embeddings), que la curación es **decisión humana** (no asistida por IA), y que el único gancho LLM (`explain_candidate`) es **stub** | (1) |
| `docs/ROADMAP.md` | "v0.2 **capacidades completas**" / "criterio V1 hecha" (`:21,65`) | Aplicado: añadida nota de honestidad de que co-citación end-to-end (Hito 8) y `explain_candidate` son futuros; el resto del reordenamiento (adelantar tensiones) = decisión del PO | (1) parcial + (2) |
| `CHANGELOG.md` | "v0.2 con capacidades completas" (`:23`); "ranking por *information scent*" sin matiz (`:27-29`) | Aplicado: "information scent" anotado como "= frecuencia de enlace (heurística, no IA)"; "capacidades completas" matizado | (1) |
| `docs/decisiones/0017-*.md` | "otro investigador reproduce **bit a bit**" (`:34`) — pero el `corpus_hash` incluye timestamps de curación | **No tocado** (ADR aceptado = historia). El principio es correcto; lo roto es el código. → recom. al coder (RAÍZ 2). Si se decide enmendar el ADR, es decisión del PO | (3) + (2) |
| `docs/decisiones/0020-*.md` | Ya es honesto (scent = frecuencia de enlace; `explain_candidate` stub) | **No tocado** — es la fuente de verdad correcta; el drift está en Nota 05/README, no acá | — |
| `docs/decisiones/0016-*.md` | `LoopState` lineal SEEDED→…→BUILT; la curación no es estado | **No tocado** (ADR aceptado). ¿La curación debería ser fase del lazo? = decisión del PO | (2) |
| `docs/decisiones/0008-*.md` | wedge = forrajeo; tensiones a v2 | **No tocado**. ¿Adelantar el moat (tensiones)? = decisión del PO | (2) |
| `docs/decisiones/0014-*.md` | Comunidades/asortatividad como parte del análisis "puro" | **No tocado**. Louvain no determinista = recom. al coder | (3) |
| `docs/decisiones/0021-*.md` | Contrato CLI agente-native (envelope `--json`) | **No tocado** (ADR aceptado). El bug UTF-8 que viola el contrato = recom. al coder | (3) |
| `docs/PRD.md` | "fácil PERO consciente" + "primer flujo de 10 min como contrato" (`:107`) vs barreras de adopción apiladas | **No tocado** — la tensión enseñable-vs-CLI es decisión de posicionamiento del PO | (2) |
| `docs/ARCHITECTURE.md` | §8 dice evitar parámetros muertos; pureza de proyectores | **No tocado** — el drift es del código (param muerto `g`, Louvain), no del doc | (3) |
| `docs/API.md` | Contratos de proyectores/scent | **No tocado** — si se renombra/redefine el scent, el doc lo sigue; pendiente de la decisión PO de RAÍZ 1 | (2) |
| Nota 05 (`05-ciclo-investigacion-humano.md`) | "la **bibliometría ES el information scent**… mapea a los **proyectores**" (`:79-80`) | **No tocado** (es Nota de exploración/registro). El drift con el ADR 0020 = decisión del PO: ¿elevar el scent a bibliometría, o bajar la Nota? | (2) |

---

## Lo que está BIEN (en justicia, no todo es escombro)

- **Honestidad técnica documentada** muy por encima del promedio del nicho (disclaimers de proxy,
  "qué no se probó", ADRs que admiten trade-offs).
- **Acoplamiento bibliográfico** correcto y determinista; **co-citación** bien implementada en el
  código (el error está en el doc).
- **Exit codes centralizados** en la jerarquía `B2GError` (`cli/_errors.py`) — el patrón que
  falta replicar para columnas/estados.
- La decisión **"`Paper`/`Author`/… = vistas derivadas, no tipos"** se sostiene: no hay que
  crear clases-entidad.
- **Filtros que marcan `rejected` sin borrar**: trazabilidad PRISMA real y curación reversible.
- **ADR 0017** epistemológicamente correcto (reproducir = re-leer snapshot).

---

## Decisiones que quedan para el PO (priorizadas)

1. **IA-en-el-producto: ¿real o reposicionar el claim?** Hoy el scent es un conteo y la curación
   es 100% humana; README/AI_DISCLOSURE/Nota 05 venden IA. ¿Se construye la bibliometría-como-scent
   y/o las tensiones, o se baja la promesa? (Toca RAÍZ 1, Nota 05, README, AI_DISCLOSURE.)
2. **Producto vs instrumento-de-paper:** conseguir **un usuario real fuera de IED** que complete
   el flujo de 10 min — o asumir explícitamente el rol de instrumento.
3. **Roadmap:** ¿adelantar el moat (máquina de tensiones, ADR 0008) por delante de los Hitos
   commodity (dedup, viz)?
4. **El lazo:** ¿la curación es una **fase del ciclo** (estado/transición visible) o transversal?
   (Toca ADR 0016, `status`.)
5. **`metodología.md`:** ¿reescritura completa al stack OpenAlex/DuckDB, o se mantiene como
   documento histórico del estudio de semiconductores? (Aplicada ya la corrección factual mínima.)
6. **ADR 0017:** ¿enmendar para reconocer que el `corpus_hash` actual incluye timestamps (y por
   tanto la reproducibilidad bit-a-bit depende del arreglo de código de RAÍZ 2)?
