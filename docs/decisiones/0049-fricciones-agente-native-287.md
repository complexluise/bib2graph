# 0049 — Cuatro fricciones agent-native del lazo (curate multi-id, `seed --preview`, retry en `seed`, hint de co-citación en `build`)

- **Estado:** Aceptada
- **Fecha:** 2026-07-18
- **Decidido por:** mixto. La decisión de fondo —**bajar los "pasos hasta la primera entrega
  aceptable"** atacando juntas las cuatro fricciones que un agente encuentra al correr el lazo, como un
  solo release aditivo (0.13.0) sin reabrir contrato de envelope/exit/FSM— es **decisión del Product
  Owner humano**, encuadrada por la métrica que el PO usa para priorizar. El **encuadre** —que las
  cuatro comparten la misma forma (recortan un paso o una fricción del camino natural sin sumar verbos),
  que cada una mapea a una fricción concreta del issue [#287](https://github.com/complexluise/bib2graph/issues/287),
  y que ninguna rompe el contrato de [0021](0021-cli-agente-native-contrato.md)— es **síntesis de la IA
  (architect) validada por el PO**.
- **Extiende [0043](0043-posicionamiento-agent-native-cli.md)** (posicionamiento agent-native del CLI)
  **sin cambiarlo.** El 0043 fijó que ser agent-native es una postura verificable contra un rubric de
  diseño; este ADR es su aplicación operativa: cada una de las cuatro fricciones se mide contra el
  criterio del PO —**"pasos hasta la primera entrega aceptable"**— y se salda de forma **aditiva**
  (una forma nueva de identificador, un flag `--preview`, un reintento interno, un warning de
  descubribilidad), sin tocar el envelope `schema="1"`, los exit codes 0–5 ni la FSM del lazo.
- **Relacionada con:**
  - **#1 (curate multi-id) → [0036](0036-identidad-source-id-agnostica-doi-ancla.md)** (identidad
    `source_id`-agnóstica con DOI-ancla): `curate accept`/`reject` adoptan la **misma resolución de
    identidad** que `read show` (`get_paper`), con prioridad **id > doi > source_id**; el helper
    compartido `service/_identity.py::resolve_idents` **es** esa política de 0036, ahora fuente única
    reusada por curate y read.
  - **#3 (retry en `seed`) → [0012](0012-openalex-credenciales.md)** (credenciales/rate limit de
    OpenAlex): `seed` reintenta ante 429/5xx con el **mismo backoff** que el forrajeo forward; al agotar,
    aflora el **mismo `NetworkError`/exit 4 con mensaje accionable** que 0012 ya fija — sin cambio de
    contrato.
  - **#5 (hint de co-citación en `build`) → [0025](0025-enricher-cocitacion-openalex.md)** (enricher
    de co-citación **gated en `accepted`**) y **[0048](0048-camino-unico-cocitacion-chain-forward-cited-by.md)**
    (`chain forward` puebla `cited_by_id`): el warning **apunta al camino de 0048** sin tocar el gate de
    0025; es descubribilidad, no un cambio de comportamiento del enricher.
- **No introduce IA** (coherente con [0022](0022-producto-sin-ia-generativa.md)): las cuatro son
  ergonomía de un CLI **determinista** —resolución de identificadores por lookup, traducción de ecuación
  ya existente expuesta en dry-run, reintento de red, un warning derivado del estado del corpus—. No hay
  modelo generativo.
- **Origen:** issue [#287](https://github.com/complexluise/bib2graph/issues/287), **release 0.13.0**.
  Auditoría de fricciones del lazo agent-native: qué le cuesta a un agente llegar de cero a una primera
  entrega utilizable.

## Contexto

El PO prioriza por una métrica concreta: **cuántos pasos (y cuánta fricción por paso) hay hasta la
primera entrega aceptable** de un agente que corre el lazo `seed → chain → curate → build → read`. El
issue [#287](https://github.com/complexluise/bib2graph/issues/287) audita ese lazo y detecta cuatro
fricciones que **no** son grietas de contrato (a diferencia de las del [0045](0045-cerrar-tres-grietas-agent-native.md)),
sino pasos de más o fallos evitables en el camino natural:

1. **`curate accept`/`reject` sólo aceptaban el id interno.** Un agente que acaba de leer un paper por
   `read show` (que ya resuelve **id | doi | source_id**, ADR [0036](0036-identidad-source-id-agnostica-doi-ancla.md))
   tenía que **traducir** el DOI o el `source_id` de vuelta al id interno para curarlo. Dos comandos del
   mismo lazo hablaban dialectos de identidad distintos.

2. **No había forma barata de ver a qué se traduce una ecuación.** Para saber qué query de OpenAlex
   genera un `--equation`, había que **ejecutar el seed** (gastar red/cuota y materializar corpus). El
   agente no podía iterar la ecuación en seco. `chain` ya tenía `--preview`; `seed` no.

3. **`seed` fallaba a la primera con un `429`.** El forrajeo forward ya reintentaba con backoff
   (ADR [0012](0012-openalex-credenciales.md)), pero `seed` no compartía ese camino: un rate limit
   transitorio en el **primer** paso del lazo lo abortaba, obligando al agente a re-planear ante un error
   que era reintentable.

4. **La red de co-citación vacía empujaba a "aceptar en masa".** Tras [0048](0048-camino-unico-cocitacion-chain-forward-cited-by.md),
   la co-citación se puebla en `chain forward`; pero si el agente **no** corrió `chain forward` y llega a
   `build` con semillas y ninguna aceptada, obtiene la red vacía **sin señal** de cuál es el camino
   barato. La tentación (documentada) es **aceptar los 298 candidatos** sólo para que la pasada 8b de
   `build` compute algo — contaminando la curación para un efecto de cómputo.

## Decisión

Se **saldan las cuatro fricciones en el release 0.13.0**, cada una **aditiva** y sin tocar el contrato
de 0021 (envelope `schema="1"`, exit codes 0–5, FSM). La implementación y sus tests viven en el issue
[#287](https://github.com/complexluise/bib2graph/issues/287) (rama `feat/287-fricciones-agente-native`);
el cambio de `docs/API.md` acompaña este ADR.

### #1 — `curate accept`/`reject` aceptan id, DOI crudo o `source_id`

Ambos verbos resuelven cada `--ids` por las **tres formas**, con prioridad **id > doi > source_id**
—**idéntica a `read show`** (ADR [0036](0036-identidad-source-id-agnostica-doi-ancla.md))—. La
resolución se extrae a un **helper compartido `service/_identity.py::resolve_idents`**, reusado por
`curate` y por `read.get_paper`: una sola política de identidad para todo el lazo. Si un identificador
no resuelve, el **error lista los no resueltos** y aclara que se aceptan las tres formas.

### #2 — `b2g seed --preview`

Flag nuevo de **dry-run**: traduce la ecuación y **muestra la query de OpenAlex**
(`title_and_abstract.search:(...)`) **sin fetchear ni tocar el corpus**. **Sólo válido con
`--equation`/`--spec`** (con `--from-bib` → `UsageError` exit 1: no hay traducción que previsualizar).
**Corta antes de resolver workspace** → funciona **sin `b2g init`** y **no** transiciona la FSM. En
`--json` emite el envelope estándar con **`data.preview = true`**, **`data.executed_query`** y
**`data.translation_report`**. Es el análogo de `chain --preview` para el paso SEED. De paso, el
`--help` de `--equation` documenta que los **términos se combinan en AND** (más términos ⇒ menos
resultados), para que ante 0 papers el agente **afloje** la ecuación en vez de agregarle términos.

### #3 — `seed` reintenta ante 429/5xx con backoff

`seed` **comparte el camino de reintento del forrajeo forward** (3 intentos, backoff exponencial). Es
**interno**: al agotar los reintentos afloran los **mismos exit codes** y el **mismo mensaje accionable**
(declarar `--email` / configurar la key) que ya fija [0012](0012-openalex-credenciales.md). **Sin cambio
de contrato.**

### #4 (issue #5) — `build` apunta a `chain forward` cuando la co-citación sale vacía

Si hay **semillas pero ninguna aceptada** y `cited_by_id` está vacío, `build` agrega un **warning** que
apunta a **`b2g chain forward`** para poblar `cited_by_id` (camino de [0048](0048-camino-unico-cocitacion-chain-forward-cited-by.md))
**sin aceptar en masa**. Es **sólo descubribilidad**: **no cambia el gate del enricher** —la pasada 8b
de co-citación sigue atada a `accepted` ([0025](0025-enricher-cocitacion-openalex.md))—; sólo hace
visible el camino barato que ya existe.

## Consecuencias

**Lo que se gana**

- **El lazo tiene menos pasos hasta la primera entrega.** #1 elimina la traducción de identidad entre
  `read` y `curate`; #2 deja iterar la ecuación en seco antes de gastar red; #3 no aborta el primer paso
  por un error reintentable; #4 muestra el camino barato a la co-citación en vez de invitar a contaminar
  la curación. La métrica del PO baja en las cuatro.
- **Identidad de fuente única.** `service/_identity.py::resolve_idents` centraliza la política de 0036:
  `curate` y `read` **no pueden** volver a divergir en cómo resuelven un identificador.
- **Coherencia entre pasos.** `seed --preview` replica el patrón de `chain --preview`; `seed` retry
  replica el patrón de reintento del forward. El lazo se vuelve más predecible: los mismos gestos
  funcionan en pasos distintos.
- **Sin superficie nueva de verbos** y **sin bump de contrato**: un flag (`--preview`), una forma extra
  de identificador, un warning y un reintento interno. Consumidores que ignoran lo nuevo siguen
  funcionando.

**Lo que cuesta**

- **Cuatro cambios a `docs/API.md`** (curate accept/reject, seed `--preview` + AND, seed retry, build
  hint), acompañando este ADR.
- **Disciplina de "aditivo, no rompé".** El PR de #287 debe verificar que exit codes, envelope y FSM
  quedan intactos; en particular que #4 **no** toca el gate del enricher (un cambio ahí contradiría 0025
  y exigiría su propio ADR).
- **Deuda reconocida, no saldada.** #4 alivia el síntoma (descubribilidad) pero **no** desacopla la
  co-citación de `accepted`; ese desacople queda para un ADR futuro (ver Alternativas).

## Alternativas

- **#1: un verbo/flag aparte para curar por DOI/`source_id`.** **Descartada:** suma superficie para algo
  que es política de identidad, no un verbo nuevo. La identidad ya está resuelta en 0036 y expuesta en
  `read show`; lo correcto es **reusar** esa resolución (helper compartido), no clonar el camino.
- **#2: dejar la previsualización sólo en `chain --preview` / documentar la traducción en prosa.**
  **Descartada:** la traducción de la ecuación ocurre en `seed`, no en `chain`; el agente que quiere ver
  su query **antes** de sembrar no tenía canal barato. Un `seed --preview` cierra el *hop* por el mismo
  canal de invocación (principio agent-native de 0043).
- **#3: dejar que `seed` falle y que el agente reintente.** **Descartada:** el forward ya reintenta;
  hacer que `seed` **no** lo haga es una asimetría gratuita que empuja lógica de retry al agente para un
  error transitorio conocido. El reintento interno es más simple y no cambia el contrato al agotar.
- **#5 (build): flag `build --cited-by`** (que `build` poblara `cited_by_id` bajo demanda antes de
  proyectar). **Descartada:** [0048](0048-camino-unico-cocitacion-chain-forward-cited-by.md) ya **rechazó
  reabrir superficie CLI** para la co-citación (el `build --cocitation`) por la poda a 10 verbos
  (ADR 0037/0038); reintroducir `build --cited-by` reabriría exactamente esa puerta. Se optó por
  **descubribilidad** (el warning que apunta a `chain forward`, el camino que 0048 ya bendijo) y se
  **difiere** el **desacople del gate del enricher** (que `build` pudiera poblar/computar co-citación sin
  exigir `accepted`) a un **ADR futuro** — es una decisión de comportamiento que merece su propio
  registro, no un flag colado en este release.
- **#5: `build` acepta automáticamente para poder computar.** **Descartada:** contamina la curación
  (marca `accepted` papers que el humano/agente no aceptó) para un efecto de cómputo. El warning
  preserva la separación entre curar y computar.

## Fuera de alcance (diferido, no en 0.13.0)

- **Fricción #7 — dedup de versiones cross-DOI** (misma obra con preprint + versión publicada bajo DOIs
  distintos): **diferida**. Solapa con el issue existente
  [#254](https://github.com/complexluise/bib2graph/issues/254); se trata allí para no duplicar la
  decisión.
- **Fricción #4 del issue — batch en `curate`** (curar lotes grandes con una ergonomía mejor que
  enumerar `--ids`): **diferida** fuera de 0.13.0. `curate apply <csv>` ya cubre el lote offline; el
  batch inline queda para un ciclo posterior si la fricción persiste.
