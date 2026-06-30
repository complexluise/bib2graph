# 28 — El marco de software: dónde nos paramos

> **Género:** nota de posicionamiento (nota primero; no es ADR ni doc canónico).
> **Origen:** charla PO ↔ agente sobre "unidad de trabajo / ciclo de trabajo" + un
> `/deep-research` con 5 ángulos de búsqueda, fuentes citadas y verificación.
> **Para qué:** saber *dónde nos paramos* y nombrar el marco de software que sostiene a
> bib2graph, más allá del dominio de investigación. Insumo para un futuro ADR/ensayo si cuaja.
> **Auditoría as-built (2026-06-28):** los §2 se contrastaron contra `src/bib2graph/` (el
> ejercicio del *functor honesto* de la Nota 27); el veredicto —qué sostiene el código vs. qué
> estira el vocabulario— vive en el nuevo **§2-bis**.
> **Relacionadas:** `27-recibo-de-demo-functor-honesto.md` (el instinto del functor honesto
> que vigila esta nota), `20_ciclo_investigacion_hallazgos_teoricos.md`,
> `NO-HACER-COMMIT-nota-separacion-alcance-bib2graph.md` (frontera bib2graph ↔ producto),
> `04-direccion-ia-in-the-loop.md`, `07-frontend-tool-for-thought.md`.

---

## TL;DR

No hay **un** nombre canónico que cubra todo bib2graph: hay **cuatro tradiciones de software
que convergen sobre el mismo principio a distinta granularidad**. El banner más preciso y
defendible:

> **"Reproducibilidad direccionada por contenido aplicada al trabajo de conocimiento"**
> — en su forma operativa: **un *build system hermético* para la revisión de literatura, con
> núcleo funcional puro y CLI como API para agentes.**

El principio único que ata las cinco piezas:

> **transformación determinista (pura) + identidad por hash del contenido (input, transformación,
> entorno) + reuso/invalidación por esa clave.**

Es, literalmente, lo que afirman Bazel y Nix para el *build* de software. bib2graph **traslada
ese patrón —maduro y formalizado— al artefacto de la revisión bibliográfica**, tomando el
`corpus_hash` como la *derivation/action key* de una revisión.

Frase de arquitectura para tener a mano:

> **bib2graph = Functional Core (Arrow puro) → Service Layer neutral de transporte →
> Ports & Adapters para N transportes, con identidad del corpus direccionada por contenido y
> procedencia append-only.**
> FCIS nombra el *centro*; Hexagonal nombra el *borde*; el build hermético nombra la
> *garantía*; "tools for thought determinista" nombra el *propósito*.

---

## 1. El marco unificador (las cuatro tradiciones que convergen)

Ninguna alcanza sola — y conviene nombrarlas juntas (síntesis de Yevtushenko: los patrones son
"suspiciously similar"; *"Ports and Adapters do not clarify how core is implemented, while
Functional Core - Imperative Shell does not clarify how shell should look like"*):

- **Functional Core, Imperative Shell** (Bernhardt) → la **naturaleza del centro**: puro,
  valor→valor. "Núcleo puro sobre tablas Arrow" es el functional core literal; los DataFrames
  Arrow son los *"simple values as boundaries"*.
- **Hexagonal / Ports & Adapters** (Cockburn) → la **forma del borde**: puertos (Protocols:
  `Source`/`Store`/`Projector`/`Enricher`) y adaptadores intercambiables. Intent canónico de
  Cockburn: *"Allow an application to equally be driven by users, programs, automated test or
  batch scripts"* = la promesa "muchos transportes (CLI/API/MCP) sobre el mismo servicio".
- **Build hermético / content-addressing** (Nix, Bazel) → la **garantía**: mismo input ⇒ mismo
  output ⇒ mismo hash.
- **Unix-for-agents** (encuadre 2025–2026) → el **vocabulario externo legitimador**: la
  herramienta determinista es la *seam* (costura) entre la capa no-determinista (el
  planificador/LLM) y la determinista (el ejecutor).

---

## 2. Los 5 pilares

### Pilar 1 — Arquitectura de núcleo puro (la forma del código)

- **Autores/obras:** Functional Core, Imperative Shell (Gary Bernhardt, *Boundaries*, SCNA
  2012); Hexagonal / Ports & Adapters (Alistair Cockburn, 2005); Clean/Onion; Repository +
  Service Layer + Unit of Work (Percival & Gregory, *Architecture Patterns with Python* /
  cosmicpython).
- **Cita ancla:** *"The shell can call the core, but the core cannot call the shell"* (Kenneth
  Lange, fiel a Bernhardt). Core = "immutable values and pure functions"; shell = "side-effectful,
  imperative stuff".
- **Cómo sostiene a bib2graph:** el motor se testea con valores (Arrow in → Arrow out), **sin
  mocks**; los Protocols son los *puertos* en versión Python; el `Store` ≈ Repository/UoW con
  log inmutable; la capa `service/` es el Service Layer agnóstico de transporte; "CLI = API para
  agentes" es un *primary adapter* cuyo puerto es el protocolo JSON/exit-code. **"Sin IA
  generativa" cae por la regla de dependencia:** lo no-determinista es shell/adaptador, nunca core.

### Pilar 2 — Build systems herméticos (el sustento del determinismo)

- **Autores/obras:** build hermético (Bazel); gestión funcional de paquetes (Nix, tesis de
  Dolstra *"The Purely Functional Software Deployment Model"*); caching causal de pipelines (Koji,
  arXiv 1901.01908); caching en experimentos de IR (arXiv 2504.09984); dbt (DAG incremental).
- **Cita ancla:** Bazel — *"a hermetic build system always returns the same output by isolating
  the build from changes to the host system"*; y el supuesto que lo habilita (IR 2504.09984):
  *"the same input will yield the same output"*.
- **Cómo sostiene a bib2graph:** el `corpus_hash` es **el *store path* de Nix / la *action key*
  de Bazel** — identidad por contenido, no por ubicación ni timestamp. **[CALIBRACIÓN as-built
  → §2-bis: la *identidad* por contenido es real (`backends/memory.py:65-99`); pero el
  *reuso/cache-hit* por esa clave —lo que hace de Bazel/Nix un *build system*— NO está
  construido: el código detecta staleness (`is_networks_cache_stale`) y **siempre recomputa**.]**
  La frontera hermética
  (Protocols, CLI stateless) aísla el efecto del núcleo determinista. **Caveat decisivo (IR):** el
  no-determinismo (GPU/LLM) **rompe** el supuesto de pureza que habilita el cache por hash;
  mantener el motor determinista *es la condición* para que el direccionamiento por contenido sea
  sólido.

### Pilar 3 — Procedencia e inmutabilidad (identidad ≠ tiempo)

- **Autores/obras:** Datomic / "database as a value" (Rich Hickey); Event Sourcing + CQRS (Greg
  Young / Fowler); Merkle DAG y content-addressing (Git, IPFS); W3C PROV (PROV-DM/O/N), con
  extensiones ProvONE y ProvCaRe.
- **Cita ancla:** IPFS — *"Any change in a node would alter its identifier and thus affect all
  the ascendants in the DAG, essentially creating a different DAG"* y *"two nodes with the same
  CID univocally represent exactly the same DAG"*. Datomic: la base "accumulates facts, rather
  than updates places, and... the past is immutable".
- **Cómo sostiene a bib2graph:** el `corpus_hash` es **content-addressing Merkle aplicado al
  corpus** ("mismo `corpus_hash` ⇒ misma revisión reproducible") — convierte la reproducibilidad
  en **propiedad estructural, no en promesa**. La procedencia append-only es Datomic/Event
  Sourcing: no se edita, se **acreta**; el workspace en un `corpus_hash` dado es un *valor
  inmutable* consultable *as-of*. W3C PROV es el vocabulario para **expresar** esa procedencia
  hacia afuera (Entity = registro/nodo, Activity = `enrich`/`project`, Agent = `Source`/`Enricher`).
- **[CALIBRACIÓN as-built → §2-bis]** Tres matices que el código obliga a precisar: (1) el
  `corpus_hash` es un **sha256 plano** de la tabla serializada (`backends/memory.py:65-99`) —
  *content-addressed*, **no** un Merkle DAG (no hay composición jerárquica de hashes); (2) la
  **procedencia** sí es append-only (`_merge_provenance`), pero el **corpus** se **reemplaza**
  (`overwrite_corpus`, DELETE+INSERT), no se acreta; (3) **no hay query *as-of***: el "valor
  inmutable en un `corpus_hash`" se materializa por **snapshot parquet congelado**, no por viaje
  temporal estilo Datomic.
- **[INCIERTO]** el wording exacto de las relaciones PROV (`wasGeneratedBy`, `used`,
  `wasDerivedFrom`, `wasAttributedTo`) y la cita literal de Hickey ("a fact... cannot be updated,
  only superseded") **no se verificaron contra fuente primaria** — confirmar antes de citar textual.

### Pilar 4 — Herramientas para agentes (la CLI como contrato)

- **Autores/obras:** Jim Clark/Docker ("MCP: tools for agents, not API"); Ugo Enyioha (8
  principios de CLI-para-agentes); Anthropic ("Code execution with MCP"); Deepak Babu Piskala
  (arXiv 2601.11672, filesystem como sustrato unificador); Jannik Reinhard (CLI vs MCP, eficiencia
  de tokens).
- **Cita ancla:** Clark — *"Treat tools as deterministic executors, treat agents as planners and
  evaluators"* (reglas: "deterministic, idempotent, fail closed, machine-checkable outcomes").
  Enyioha: *"If a human would use a CLI for it, the agent should too."*
- **Cómo sostiene a bib2graph:** la *seam* determinista/no-determinista de Clark **es** la
  frontera bib2graph (ejecutor) ↔ producto-con-IA (planificador). Los principios de Enyioha (JSON
  a stdout, exit codes con semántica fija, idempotencia, dry-run) mapean **1:1** con "CLI = API
  para agentes" y con el trabajo ya hecho (ADR 0037/0038, `--json` unificado #151/#168):
  **bib2graph no sigue una moda, implementa el patrón canónico.** Anthropic respalda "filtrar/
  transformar datos en código determinista antes de que lleguen al modelo" = el núcleo Arrow puro.
  Piskala da respaldo académico al "estado durable en archivos" (workspace + `corpus_hash`), no en
  la conversación. Reinhard aporta el "determinismo aprendido" (modelos entrenados en miles de
  millones de líneas de terminal) y datos de eficiencia (hasta ~35× menos tokens que MCP).

> **[CALIBRACIÓN as-built → §2-bis]** El mapeo con Clark es 1:1 en **tres** de sus cuatro
> atributos —*deterministic*, *idempotent*, *machine-checkable*— pero **no en *fail closed***:
> el CLI es *fail-open advisory* (`status.readiness` avisa; `cycle.py` permite las transiciones
> igual; ningún comando bloquea). Y **no es un descuido**: es decisión de diseño (un gate duro
> mataría el demo y la autonomía del agente, ADR 0021), con su antídoto ya teorizado en la
> **Nota 27** (el *recibo* `crossed_red` que vuelve cicatriz el cruce silencioso). Además,
> `--dry-run` existe **solo** en `chain --preview`, no como principio genérico del CLI.

### Pilar 5 — Tools for thought determinista (el propósito)

- **Autores/obras:** Engelbart ("Augmenting Human Intellect", 1962); Matuschak & Nielsen ("How
  can we develop transformative tools for thought?"); Matuschak ("sciences of the artificial" de
  Simon); marimo (notebook reactivo como DAG); ASReview LAB v.2 (PMC12416088).
- **Cita ancla:** marimo — *"reproducible by default"*, *"no hidden state"*, *"deterministic
  execution"* (vía análisis estático, "possible for us to implement with 100% correctness").
  Matuschak & Nielsen: "insight through making", combinar el **rigor** de la investigación con la
  iteración de producto.
- **Cómo sostiene a bib2graph:** ubica a bib2graph en el linaje Engelbart/Matuschak-Nielsen, pero
  en la **rama determinista del oficio** — materializa la mitad "rigor" del loop que casi nadie
  cierra. **marimo es el isomorfismo técnico directo:** *"reproducible by default, not by
  discipline"* es casi literal para el pitch. **ASReview es el "vecino honesto":** comparte
  transparencia, procedencia y humano-en-el-centro, pero su núcleo es **ML probabilístico** (active
  learning) y por eso solo logra resultados *"identical OR near-identical"*; bib2graph se diferencia
  por **determinismo duro garantizado por content-addressing**.

---

## 2-bis. Calibración contra el código (auditoría as-built, 2026-06-28)

> Antes de que esto cuaje en ADR/ensayo (§7), se auditó el **código real** (`src/bib2graph/`)
> contra las afirmaciones falsables del §2 — el ejercicio que pide la Nota 27 (el *functor
> honesto*): nombrar dónde el discurso cruza una frontera en silencio. **Veredicto: el espinazo
> se sostiene en el código; el vocabulario prestado de Nix/Bazel/Datomic/Clark estira en tres
> puntos.** Esto es lo que hay que decir con precisión para que el ensayo sea a prueba de `grep`.

| Pilar | As-built | Qué sostiene el código | Dónde el vocabulario estira |
|---|---|---|---|
| **1 — Núcleo puro** | ✅ cumple | regla de dependencia real (el núcleo importa sin `duckdb`/`click`/`fastapi`); funciones puras Arrow→Arrow; `service/` sin transporte; CLI de 3 capas | menor: `Preprocessor` es clase concreta, no `Protocol` (5/6 puertos sí lo son) |
| **2 — Build hermético** | ⚠️ parcial | `corpus_hash` por contenido, excluye timestamps y `resolution` (`backends/memory.py:65-99`) | **no hay reuso/invalidación por la clave**: detecta staleness y avisa, pero **siempre recomputa**. Es un *staleness checker*, no un build system con cache-hit |
| **3 — Procedencia / inmutabilidad** | ⚠️ parcial | procedencia **append-only** real (`_merge_provenance`) | `corpus_hash` = **sha256 plano** (no Merkle DAG); el **corpus se reemplaza** (DELETE+INSERT), solo la procedencia acreta; **no hay `as-of` query**, solo snapshots congelados |
| **4 — CLI para agentes** | ⚠️ mayormente | JSON-stdout puro, exit codes 0–5 tipados, idempotencia, stateless (`service/envelope.py`, `service/errors.py`) | **"fail closed" NO se cumple**: es *fail-open advisory* (`cycle.py` transiciones permisivas). `--dry-run` solo en `chain --preview`, no genérico |
| **5 — Determinista, sin IA generativa** | ✅ cumple | cero imports de LLM; scent bibliométrico determinista; Louvain seedeado del hash; reloj en la frontera | — |

**Las tres calibraciones para el ensayo (frases defendibles, no aspiracionales):**

1. **Pilar 2** → "corpus **direccionado por contenido** con **detección de staleness**", no
   "build system con reuso". El cache-hit por hash (estilo Bazel/Nix) es **roadmap, no as-built**:
   la identidad por contenido es real; el *reuso* por contenido no está construido.
2. **Pilar 3** → "hash **plano** content-addressed" (no Merkle DAG) + "**corpus replace /
   procedencia append-only**" (híbrido honesto, no inmutabilidad pura) + "viaje en el tiempo
   **por snapshots**, no `as-of` query (no es Datomic)".
3. **Pilar 4** → "ejecutor determinista + idempotente + **verificación *advisory* en la
   frontera**", **no** "fail closed". Acá la nota se ata sola con la **Nota 27**: el *fail-open*
   **es decisión de diseño** (un gate duro mataría el demo y la autonomía del agente, ADR 0021),
   y su antídoto honesto ya está teorizado —el **recibo** (`crossed_red`) que vuelve cicatriz el
   cruce silencioso. El marco **ya es consciente de su propia grieta**; solo el Pilar 4 la
   enunciaba con demasiada confianza al pegarle el "fail closed" de Clark.

**Lo que esto NO toca:** el espinazo —Functional Core + determinismo duro + sin IA generativa +
identidad por contenido + CLI-as-API— **es real y verificable con `archivo:línea`**. Es ~80% del
marco y se sostiene. Lo que sobra es analogía prestada que promete máquinas (cache-hit, `as-of`
query, gate duro) que son roadmap o decisión-contraria-deliberada — no as-built.

---

## 3. Prior art y huecos (honesto)

**Quién está cerca en cada eje:**

- **Arquitectura (FCIS + Hexagonal + Service Layer):** *cosmicpython* (Percival & Gregory) es la
  referencia Python de facto del esqueleto Repository+UoW+Service Layer+Ports&Adapters — lo más
  cercano al andamiaje de bib2graph. **Pero su core es un domain model OO (clases ricas), NO un
  functional core columnar sobre Arrow.** `ruiconti/cosmic` une FCIS+hexagonal+CQRS+DDD en una
  webapp (prueba de concepto de la fusión exacta, pero web/CQRS, no batch determinista ni Arrow).
- **Build hermético / content-addressing:** Nix/Guix y Bazel/Buck tienen el patrón completamente
  formalizado, *en software*. En datos/ML: dbt (DAG + incremental + manifest), Koji (1901.01908),
  pyterrier-caching/IR (2504.09984). DVC/Pachyderm/lakeFS acercan content-addressing a datasets
  **[INCIERTO: no verificados en esta sesión]**.
- **Procedencia inmutable:** Datomic es la implementación canónica de "accretion-only + tiempo
  first-class" (DB de propósito general, no open-source, no apunta a reproducibilidad científica).
  IPFS/Git/Merkle DAGs: content-addressing maduro a nivel de blobs. ProvONE/ProvCaRe y workflows
  científicos (Taverna, VisTrails, Kepler): provenance para reproducibilidad, sobre pipelines
  genéricos.
- **CLI-para-agentes:** Claude Code, Cursor y agentes CLI-nativos hacen la filosofía, pero son
  agentes de código genéricos, no motores de dominio. `git`/`docker`/`gh`/`jq` son prior art del
  *patrón*, no del *contenido*.
- **Tools for thought / dominio bibliométrico:** notas enlazadas (Roam/Obsidian/Tana) sin motor
  determinista; notebooks reactivos (marimo, linaje Observable) con motor pero genéricos; revisión
  sistemática (ASReview, Rayyan, Covidence) con núcleo ML/manual; mapeo de citas (Connected Papers,
  ResearchRabbit, Inciteful, Litmaps) que usan métodos bibliométricos/de red y "generally don't use
  language models" **[INCIERTO: vía búsqueda, no fetch directo]**, pero son SaaS cerrados, sin
  workspace local durable, sin `corpus_hash`, sin procedencia append-only, exploratorios más que
  pipeline reproducible.

**El hueco que ocupa bib2graph** (consistente en los cinco reportes): nadie combina,
**específicamente para revisión de literatura**, las cuatro propiedades a la vez:

1. motor **100% determinista** (no ML, no generativo);
2. corpus como **unidad durable direccionada por contenido** (`corpus_hash`);
3. **procedencia append-only** auditable;
4. **CLI como API para agentes** (subprocess/JSON/exit-codes/stateless).

Cada actor existente cae en una sola canasta: el ecosistema funcional-puro asume OO; el ecosistema
dataframe asume scripts imperativos sin puertos; el mundo PROV tiene el vocabulario pero rara vez
la garantía estructural por hash; Datomic/IPFS tienen la garantía estructural pero no el encuadre
de revisión de literatura; las tools-for-thought son notas (sin motor), notebooks (genéricos) o
revisión con ML (probabilística).

> **"Make/Nix para una revisión de literatura" — un tools-for-thought determinista bibliométrico —
> está vacante.** No se encontró prior art que lo nombre así.

**Honestidad sobre lo que NO es nuevo:** el patrón build-hermético, el content-addressing y la
CLI-para-agentes están todos formalizados y maduros *en sus dominios de origen*. **El aporte de
bib2graph es la composición y el traslado de dominio, no la invención de las piezas.** Matiz
narrativo: el discurso 2025-2026 sobre herramientas-para-agentes es **ingenieril** (tokens,
determinismo), **no epistémico**; el ángulo "antídoto al sesgo del related work" (#187) **no
aparece en ninguna fuente** — es diferencial narrativo propio, no respaldo externo.
**[INCIERTO:** si existe un proyecto académico bibliométrico que ya adopte explícitamente el
contrato CLI-para-agentes; no apareció.]

---

## 4. Dónde nos paramos (frases-ancla, precisas y defendibles)

1. **bib2graph es un *build system hermético para la revisión de literatura*:** el `corpus_hash`
   direccionado por contenido es a un corpus lo que el *store path* de Nix o la *action key* de
   Bazel son a un build — mismo contenido, mismo grafo, verificable. *(matiz as-built §2-bis: la
   **identidad** por contenido es real; el **reuso/cache-hit** por contenido —lo que completa la
   analogía con el build— es roadmap, no as-built.)*
2. **El determinismo no es una promesa de proceso sino una propiedad estructural:** porque el
   núcleo son funciones puras sobre tablas Arrow, mismo input ⇒ mismo output ⇒ mismo hash.
   *"Reproducible by default, not by discipline"* (en el sentido de marimo).
3. **La IA generativa queda fuera del motor por arquitectura, no por preferencia:** lo
   no-determinista rompe el supuesto de pureza que habilita el direccionamiento por contenido, así
   que el LLM es siempre adaptador/planificador, nunca núcleo (la *seam* de Clark).
4. **La procedencia se acreta, no se sobrescribe:** identidad ≠ tiempo (Datomic/Merkle/Event
   Sourcing) — el workspace en un `corpus_hash` dado es un valor inmutable y auditable; siempre se
   puede responder "¿de dónde salió este nodo o arista?". *(matiz as-built §2-bis: la
   **procedencia** se acreta; el **corpus** se reemplaza; el "valor inmutable" se materializa por
   **snapshot**, no por `as-of` query.)*
5. **La CLI es la API:** contrato estable (JSON a stdout, exit codes, idempotencia, stateless) para
   que un agente la componga como compone `git` o `docker` — bib2graph implementa el patrón canónico
   "tools for agents, not API", no una moda.

---

## 5. Fuentes (consolidadas, por tema)

**Tema 1 — Arquitectura núcleo puro**
- https://alistair.cockburn.us/hexagonal-architecture
- https://www.destroyallsoftware.com/talks/boundaries
- https://kennethlange.com/functional-core-imperative-shell/
- https://dev.to/siy/functional-core-with-ports-and-adapters-3m0g
- https://github.com/cosmicpython/book/blob/master/preface.asciidoc
- https://github.com/ruiconti/cosmic
- (`cosmicpython.com/book/preface` → HTTP 403; verificado vía espejo GitHub)

**Tema 2 — Build systems herméticos**
- https://bazel.build/basics/hermeticity *(leída)*
- https://en.wikipedia.org/wiki/Nix_(package_manager) *(leída)*
- https://arxiv.org/abs/1901.01908 *(abstract leído)*
- https://arxiv.org/html/2504.09984v1 *(leída)*
- https://edolstra.github.io/pubs/phd-thesis.pdf **[INCIERTO: referenciada, no fetcheada]**
- https://www.getdbt.com/blog/data-transformation-in-data-warehouse **[INCIERTO: solo búsqueda]**

**Tema 3 — Procedencia e inmutabilidad**
- https://vvvvalvalval.github.io/posts/2018-11-12-datomic-event-sourcing-without-the-hassle.html
- https://www.infoq.com/articles/Datomic-Information-Model/
- https://docs.ipfs.tech/concepts/merkle-dag/
- https://blogs.ncl.ac.uk/paolomissier/2021/02/07/w3c-prov-some-interesting-extensions-to-the-core-standard/

**Tema 4 — Herramientas para agentes**
- https://www.docker.com/blog/mcp-misconceptions-tools-agents-not-api/
- https://dev.to/uenyioha/writing-cli-tools-that-ai-agents-actually-want-to-use-39no
- https://www.anthropic.com/engineering/code-execution-with-mcp
- https://arxiv.org/html/2601.11672v1
- https://jannikreinhard.com/2026/02/22/why-cli-tools-are-beating-mcp-for-ai-agents/
- https://www.eficode.com/blog/unix-principles-guiding-agentic-ai-eternal-wisdom-for-new-innovations **[INCIERTO: no fetcheada en profundidad]**

**Tema 5 — Tools for thought determinista**
- https://numinous.productions/ttft/
- https://andymatuschak.org/sdac/
- https://pmc.ncbi.nlm.nih.gov/articles/PMC12416088/ (ASReview LAB v.2)
- https://marimo.io/blog/dataflow
- https://github.com/marimo-team/marimo
- https://onlinelibrary.wiley.com/doi/10.1111/ijmr.12381 **[INCIERTO: no fetcheada]**
- http://musingsaboutlibrarianship.blogspot.com/2024/06/all-about-citation-chasing-and-tools.html **[INCIERTO: no fetcheada]**

---

## 6. Pendientes de verificación (antes de citar textual o graduar a ADR)

> El lado **código** de los §2 ya se auditó contra `src/bib2graph/` (2026-06-28) → ver **§2-bis**.
> Lo de abajo son los pendientes **bibliográficos** (citas textuales y prior art).

- Wording literal de las relaciones **W3C PROV** contra la spec PROV-DM.
- Cita textual de **Hickey** ("a fact... cannot be updated, only superseded") contra la charla
  *The Database as a Value*.
- **DVC/Pachyderm/lakeFS** como content-addressing de datasets (no verificados aquí).
- Tesis de **Dolstra** (leer la fuente primaria) y página de **dbt**.
- Que **Connected Papers / ResearchRabbit / Inciteful / Litmaps** "no usan LLM" (vía Aaron Tay,
  sin fetch directo).
- Buscar prior art académico bibliométrico que ya adopte el **contrato CLI-para-agentes**.

---

## 7. Próximo paso sugerido (no ejecutado)

Si esto cuaja como rumbo y no solo como mapa: candidato a **graduar un ADR** que fije el
posicionamiento ("bib2graph = build hermético para revisión de literatura") y/o un ensayo
(Medium) reusando el §4. Antes, cerrar el §6. Nota primero — esto es el mapa, no la decisión.
