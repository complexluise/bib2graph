# 26 — Retroalimentación: ¿es bib2graph realmente *agent-native*?

> **Género:** nota de retroalimentación / auditoría (nota primero; no es ADR ni doc
> canónico). Insumo para issues y, si cuaja el rumbo, para un ADR de posicionamiento.
> **Origen:** dos análisis **independientes** del CLI `b2g` contra el *Rubric for
> Agent-Native CLI Design* (los nueve principios del handbook), unificados acá:
> uno del PO y uno de un agente que auditó `src/bib2graph/` con tres barridos
> paralelos. Donde discreparon, se reconcilió **contra el código** (a prueba de `grep`).
> **Para qué:** saber, con evidencia `archivo:línea`, en qué ejes bib2graph es
> agent-native de verdad y cuáles son las tres grietas reales — separando lo que es
> *hueco* de lo que es *decisión de diseño por bajo blast radius*.
> **Auditoría as-built:** sobre `src/bib2graph/` en la rama `chore/retirar-exploracion`
> (estado 0.10.x). Las citas `archivo:línea` se verificaron contra el árbol.
> **Relacionadas:** `23-RETROALIMENTACION_bib2graph_agente.md` (fricción de uso real
> del mismo agente — el "último kilómetro"), `28-marco-software-donde-nos-paramos.md`
> (§2-bis: el Pilar 4 "CLI para agentes" es *fail-open advisory*, no *fail-closed*),
> `27-recibo-de-demo-functor-honesto.md` (el instinto del *functor honesto* que exige
> nombrar dónde el discurso cruza una frontera en silencio).

---

## TL;DR

bib2graph **es agent-native genuino en los ejes que importan para lo que es**: un CLI
de analítica local, determinista, sin blast radius destructivo multi-tenant. Lo es
**por construcción, no por vocabulario** — el posicionamiento "CLI = API para agentes"
(Nota 28, Pilar 4) se sostiene con `archivo:línea`, no con analogía prestada.

El rubric pide no sumar los nueve en un puntaje, sino mirar **dónde dos grietas juntas
crean riesgo**. Tres grietas reales, en orden de palanca:

1. **No hay introspección versionada de la superficie** (principio 9) — el agente que
   arranca en frío no puede preguntarle a la herramienta "qué comandos/flags tenés y en
   qué versión del contrato estás" por el mismo canal que usa para actuar; tiene que ir a
   `docs/API.md` (el *hop* débil).
2. **El error de red no distingue reintentable de no-reintentable** (principio 3) — todo
   cae en `NETWORK_ERROR`; es el **único hueco con daño documentado en uso real**: en la
   Nota 23 el agente abandonó la CLI y pegó directo contra OpenAlex con `urllib`,
   destruyendo la procedencia que es la razón de ser de la herramienta.
3. **Mutación precisa sin fricción** (interacción 8×7/4) — un `curate reject --ids …`
   bien formado, self-contained y con exit 0 limpio muta el corpus de forma persistente
   sin ninguna fricción ni declaración de blast radius.

Los principios 4–7 (trust & safety) están **relajados por diseño** y es aceptable: no hay
borrado de recursos, no hay estado compartido, el daño es local y recuperable por snapshot.
El propio rubric lo dice en su *worked example*: un CLI de analítica local no necesita la
misma postura de trust que uno que borra producción.

---

## Los nueve principios

### I. Legibilidad

**1. Salida estructurada, no narrada — `Sound`.**
Todo subcomando que devuelve datos expone `--json` vía el decorador compartido
`@json_option` (`cli/_options.py:69-91`), aplicado de forma pareja (`seed.py:388`,
`build.py:621`, `chain.py:345`, `read.py:103/168`, etc.), y emite un envelope versionado
`{schema, ok, command, exit_code, data, warnings, error}` con `ENVELOPE_SCHEMA_VERSION = "1"`
(`service/envelope.py:26`, `build_envelope` en `:29-59`). Se imprime una sola línea JSON con
`ensure_ascii=False` + `flush` — `jq` la consume sin preprocesar; UTF-8 forzado en la
frontera (`cli/__init__.py:82-95`). Sin *drift* por ancho de terminal: el modo humano usa
strings fijos (`emit_human`), no tablas. Único matiz benigno: un grupo sin subcomando
imprime *help* sin envelope (`skill.py:213`), pero eso no es un comando-que-devuelve-datos.

**2. El contrato tiene una sola forma — `Sound`.**
Una sola flag de salida estructurada (`--json`, declarada una vez en `_options.py:85`);
sin variantes `--output`/`--pretty`. Activación alternativa uniforme por entorno
(`B2G_JSON` truthy, `_options.py:33-46`). Naming consistente: grupos noun-verb
(`read|curate|snapshot <verbo>`) + verbos planos del ciclo, gobernado por ADR. Las
divergencias son **explícitas y justificadas**: `--format` aparece solo en `export`
(`export.py:123`) porque ahí el formato es del *archivo*, no de la salida del comando; y
`seed` exige exactamente uno de `--equation/--spec/--from-bib` (`seed.py:425-444`) — el
patrón que el rubric pide. La única erosión son 9 aliases deprecados (`inspect`→`read show`,
`enrich`→`chain/build`…) presentes hasta 0.11.0: inconsistencia transicional documentada
(ADR 0038), no incidental.

**3. Outcome por exit code y taxonomía estable — `Sound`, con un caveat de granularidad.**
Exit codes 0–5 tipados y documentados (`service/errors.py:8-13`, ADR 0021), con función de
mapeo **pura** `code_for(exc)` (`service/errors.py:71-97`) — la política vive en un solo
lugar. 6 `error.code` semánticos (`USAGE_ERROR`, `DATA_ERROR`, `DEPENDENCY_ERROR`,
`NETWORK_ERROR`, `STORE_ERROR`, `B2G_ERROR`); el decorador `@handle_errors` (`cli/_errors.py:91-148`)
garantiza el envelope de error sin duplicar `try/except`. Tres clases de falla son
distinguibles sin leer stderr (uso→1, datos→2, dependencia→3, red→4, store→5).
**El caveat (donde los dos análisis discreparon, reconciliado):** estructuralmente es
`Sound`; pero **dentro** de `NETWORK_ERROR`/exit 4, no se distingue `429` (reintentable con
backoff) de `504`/query-demasiado-compleja (no-reintentable) — todo colapsa al mismo código
(`sources/openalex.py:150`, `cli/_errors.py:140-145`). Es el failure mode literal del
principio ("un retry loop no puede separar transitorio de permanente") y la Nota 23 lo vivió
(Pedido #3). El retry/backoff existe pero es **interno** (`openalex.py:70`,
`_RETRY_STATUS_CODES`), invisible al caller.

### II. Trust & Safety *(cuadrante de baja relevancia para esta herramienta)*

**4. Reversibilidad visible antes de comprometer — `Partial`.**
Existe: `chain --preview` es un dry-run real (estima crecimiento sin fetchear ni
transicionar, `chain.py:322-333`); `build` predice redes vacías con `reason`/`fix_command`
accionables (`build.py:312,445`); `curate dump`→`curate apply` es un round-trip offline
reversible mientras no se aplica (`curate.py:139,193`). Falta: no hay `--dry-run` en
`curate filter/accept/reject`, `snapshot create/restore` ni `init`; ninguno muestra
footprint antes de comprometerse. Y la **idempotencia existe pero no se declara**:
`curate apply` y los `Source.persist` son idempotentes (ADR 0009), pero el envelope no
expone `idempotent: bool` que le diga al agente "reintentá sin miedo". Mitigado fuerte por
bajo blast radius: store DuckDB local, sin `delete/reset/purge`, `snapshot restore` como red.

**5. Secretos fuera del razonamiento — `Sound` en la superficie viva, residuo en el alias deprecado.**
*(Reconciliación de una contradicción entre los dos análisis, resuelta contra el código.)*
No requiere credenciales. La API key de OpenAlex es opcional y, en los comandos **vivos**
(`seed/chain/build`), entra **solo por env var** `OPENALEX_API_KEY` (`openalex.py:413`,
`api_key or os.environ.get(...)`) y viaja en header `Authorization: Bearer` (`openalex.py:431`),
nunca como arg ni en el envelope — el agente no la ve. **El residuo:** `--api-key` como flag
literal existe **solo en el alias deprecado `enrich`** (`enrich.py:102-105`), que se retira
en 0.11.0 (ADR 0038, #165). Es el anti-patrón del principio 5 (key en el contexto del
agente, eco-able por inyección), pero **acotado a una superficie que ya está muriendo**.
El `--email` del polite pool no es secreto (identificador de cortesía).

**6. Canales de input con distinto peso de confianza — `Partial`.**
Validación mínima y **sin distinción de canal**: `--workspace/--spec/--from-bib/--from-corpus`
se tratan como `click.Path()` y se pasan a `Path(...)`; un valor que el agente rellenó desde
contenido externo se valida igual que una env var puesta por el humano. `click.Path(exists=True)`
valida existencia, no origen ni *path-traversal* (`seed.py:215`); la ecuación solo se valida
no-vacía (`seed.py:90`). Defensa **implícita, no declarada**: el walk-up de workspace tiene
superficie limitada (busca `workspace.json` hacia arriba, `workspace.py:282`), y los inputs
peligrosos (ecuación, CSV de curación) tienen daño ~0 porque OpenAlex sanitiza del lado
servidor y el FS es local single-user. El principio no se aplica, pero el blast radius lo
vuelve tolerable.

**7. Riesgo escalonado, no plano — `Partial`.**
Hay tiering **funcional** pero no **legible**: lectura sin efecto (`status/validate/read/export`)
< escritura idempotente que transiciona el FSM (`seed/build/snapshot create`) < mutación
transversal persistente que NO transiciona (`curate accept/reject`, `curate.py`) <
irreversible (`snapshot restore` sobrescribe el corpus vivo; `init` sobre carpeta existente
lanza `WorkspaceExistsError` — defensa, no preview). Pero **nada en el contrato agrupa
comandos por blast radius**: no hay `--force`, ni confirmación, ni docstring "this is
destructive"; el lector lo deduce de la prosa. El extremo verdaderamente destructivo del
espectro (borrado) directamente **no existe**, así que la planicie es benigna — coincide con
el hallazgo de la Nota 28 §2-bis: *fail-open advisory* por diseño (ADR 0021).

### III. Composabilidad & Estabilidad del contrato

**8. Self-contained, no session-stateful — `Sound`, con un caveat de workspace ambiente.**
Cada comando es invocable en frío: papers por `--id` obligatorio con resolución id>doi>source_id
(`read.py:205`, ADR 0036); `read top` recomputa sin `build` previo (`reads.py:746`); cada
comando devuelve identificadores explícitos en `data` (`seed`→`papers_added/total_papers/round`,
`snapshot create`→`snapshot_dir/corpus_hash`). No hay "opera sobre el último creado"; el canal
entre invocaciones es **el archivo** (`library.duckdb` del workspace), no memoria de sesión —
ésta es la propiedad que hace a `b2g` sobrevivir la compactación de contexto.
**El caveat (donde los dos análisis discreparon):** la identidad del *recurso* es explícita y
`Sound`; pero **cuál workspace** es ambiente — precedencia `--workspace` > `B2G_WORKSPACE` >
walk-up desde cwd (`workspace.py:246-286`). Un agente que cambia de cwd sin flag opera
**silenciosamente sobre otra investigación**. La precedencia está documentada y es
overridable (eso lo deja en `Sound`), pero el modo ambiente es un residuo de estado implícito
que conviene volver **legible** (ver recomendaciones).

**9. La interfaz se auto-describe y está versionada — `Partial`. (La grieta convergente.)**
La *salida* está versionada: `ENVELOPE_SCHEMA_VERSION = "1"` en cada envelope
(`service/envelope.py:26`) detecta drift de contrato; ADRs 0037–0040 registran cambios de
superficie. **Pero no hay auto-descripción por el mismo canal:** no existe `b2g schema` /
`b2g --describe` que vuelque comandos, flags y el JSON-schema del envelope. El agente que
arranca en frío debe leer `docs/API.md` en prosa — el *hop* extra no confiable que el
principio señala. Además: el shape del envelope está descrito en prosa y duplicado en el
docstring de `build_envelope` (sin JSON-schema publicado), y `--version` muestra la versión
del paquete, no la del contrato. Si la herramienta cambiara `data["papers_added"]` →
`data["n_added"]` sin que SemVer lo marque como breaking, no habría señal mecánica.

---

## Tabla resumen

| # | Principio | Veredicto | Evidencia ancla |
|---|-----------|-----------|-----------------|
| 1 | Salida estructurada, no narrada | **Sound** | `service/envelope.py:26`; `_options.py:69-91` |
| 2 | Una sola forma de contrato | **Sound** | `_options.py:85`; `seed.py:425-444`; `export.py:123` |
| 3 | Exit codes + taxonomía estable | **Sound** *(caveat: red 429≠504)* | `service/errors.py:71-97`; `openalex.py:150` |
| 4 | Reversibilidad visible | **Partial** | `chain.py:322`; sin dry-run en curate/snapshot/init |
| 5 | Secretos fuera del reasoning | **Sound** (vivo) / residuo deprecado | `openalex.py:413`; `enrich.py:102` |
| 6 | Canales con distinto trust | **Partial** | `seed.py:215`; sin tagging de canal |
| 7 | Riesgo tiered, no plano | **Partial** | tiering funcional sin grading legible; sin `--force` |
| 8 | Comandos self-contained | **Sound** *(caveat: workspace ambiente)* | `read.py:205`; `reads.py:746`; `workspace.py:246-286` |
| 9 | Auto-descripción versionada | **Partial** | `envelope.py:26` sí; sin `b2g schema` |

---

## Interacciones (lo que el rubric pide priorizar)

No se suma: se mira dónde **dos grietas juntas** crean un riesgo que ninguna sola tiene.

1. **Sound (8) × Partial (7/4) — fricción ausente sobre acciones precisas.** Un
   `curate reject --ids W1 --ids W2 …` es self-contained, sin estado de sesión, con envelope
   versionado y exit 0 limpio — *y* muta el corpus de forma persistente, transversal, sin
   confirmación. El rubric señala exactamente esto: **la composabilidad que vuelve la
   herramienta placentera es lo que quita la fricción natural** que una herramienta menos
   componible habría tenido. Bounded porque el daño es local y recuperable (snapshots,
   procedencia append-only), pero el patrón está.

2. **Sound (3) × caveat — el agente rutea alrededor del motor.** La peor interacción por
   *consecuencia sistémica*, no por blast radius: `seed/chain` son las únicas operaciones
   externas, lentas y falibles. Sin subcódigo reintentable, el agente reintenta a ciegas, y
   la Nota 23 documenta el desenlace real — **abandonó la CLI y fue directo a OpenAlex con
   `urllib`**, perdiendo la trazabilidad que es la razón de existir de la herramienta. Una
   grieta de legibilidad fina (3) hace que el agente rutee alrededor del núcleo determinista.

3. **Partial (9) × Sound (8) — el agente que arranca en frío.** La auto-descripción faltante
   pesa **más** por la composabilidad: un agente puede levantar el tool en cualquier cwd y
   orquestar varios comandos, pero no puede verificar programáticamente qué comandos existen,
   qué flags aceptan, ni en qué versión del envelope está. Sumado al caveat de workspace
   ambiente (8), puede orquestar en frío contra el corpus equivocado sin señal.

**Lo que NO es problema** (la nota final del rubric): el CLI no toca producción multi-tenant,
no borra recursos remotos, no comparte credenciales. Los principios 4–7 pesan menos que en
una herramienta con blast radius real. Para un agente en una sesión de investigación larga,
la grieta de fondo es **9**: si la herramienta cambia un campo sin bump, el agente no se entera.

---

## Recomendaciones priorizadas (por palanca, corregidas contra el código)

Tres mejoras de bajo costo, atacando exactamente las interacciones de arriba. El orden es por
palanca real, no por cuál principio "puntúa peor".

1. **Exponer `b2g schema` — introspección versionada de la superficie** *(cierra P9 +
   interacción 3).* Subcomando meta que vuelca: lista de comandos, flags por comando, y el
   JSON-schema del envelope actual con su `ENVELOPE_SCHEMA_VERSION`. Misma familia que
   `skill add` (comando meta, fuera del ciclo, no transiciona FSM). Permite a un agente
   arrancar en frío sin el *hop* a `docs/API.md`. Es la grieta convergente de los dos análisis.

2. **Subcódigo de error de red `429` vs `504`** *(cierra el caveat de P3 + interacción 2 — la
   de daño documentado).* Distinguir en `error.code` (o un `error.subcode`) `RATE_LIMITED`
   (429, reintentable con backoff) de `UPSTREAM_TIMEOUT`/`QUERY_TOO_COMPLEX` (504, hay que
   simplificar la query). Es el **Pedido #3 de la Nota 23** y el único hueco que demostró
   expulsar al agente del motor. Fix chico (`openalex.py:150` ya distingue el status code
   internamente), efecto grande.

3. **Declarar idempotencia y blast radius en el envelope** *(cierra interacción 1 sin agregar
   flags).* Agregar al `data` (aditivo, no breaking) `side_effect ∈ {none, transversal,
   state_transition, destructive}` e `idempotent: bool` cuando aplique. Le da al agente la
   señal que hoy tiene que deducir de la prosa, sin meter confirmación interactiva (que
   mataría la autonomía — ADR 0021). Conecta con el "recibo" teorizado en la Nota 27.

**Nota sobre la credencial (lo que *no* hace falta hacer):** la recomendación intuitiva
"mover `OPENALEX_API_KEY` a env var" **ya está hecha** en la superficie viva
(`openalex.py:413`). El único `--api-key` literal vive en el alias deprecado `enrich`
(`enrich.py:102`), que se retira en 0.11.0 — el footgun de P5 **se cierra solo** con la
deprecación ya planificada. Acción mínima: no re-exponer `--api-key` en los verbos vivos
(y, opcionalmente, adelantar el retiro del flag en `enrich`).

---

## Pendientes (antes de graduar a ADR o abrir trabajo)

- Decidir si esto justifica un **ADR de posicionamiento** ("bib2graph implementa el contrato
  CLI-para-agentes; las grietas 3/8/9 son roadmap explícito, las relajaciones 4–7 son
  decisión por blast radius") o si queda como nota-mapa.
- Abrir issues para las tres recomendaciones (candidatos: `b2g schema`, subcódigo de red,
  `side_effect`/`idempotent` en envelope). Las tres caben sin romper el contrato de 10 verbos.
- Confirmar que ningún verbo vivo (`seed/chain/build`) re-introduzca `--api-key` al absorber
  `enrich` en 0.11.0.

---

*Unificación de dos auditorías independientes (PO + agente) contra el Rubric for Agent-Native
CLI Design. Evidencia `archivo:línea` verificada as-built. Sin datos personales.*
