# 0048 — Camino único de co-citación: `chain forward` puebla `cited_by_id`

- **Estado:** Aceptada
- **Fecha:** 2026-07-18
- **Decidido por:** **Product Owner humano** (2026-07-18). La elección entre el **camino implícito**
  (que el forrajeo hacia adelante, que ya existe, pueble además `cited_by_id`) y un **camino
  explícito** (un comando/flag nuevo tipo `build --cocitation` que orqueste `accept → chain forward
  → build`) es **decisión del PO**: eligió el camino implícito. El **encuadre** —diagnosticar que hoy
  no hay un camino feliz único a la red de co-citación, que tres comandos tocan `cited_by_id` y
  ninguno lo completa solo, y que sumar superficie tensiona con la poda de "10 verbos"— es **síntesis
  de la IA (architect) validada por el PO**.
- **Relacionada con:** [0025](0025-enricher-cocitacion-openalex.md) (`Enricher` opt-in: refs→DOI +
  co-citación — la pasada 8b poblaba `cited_by_id` **solo sobre semillas aceptadas**; este ADR fija
  que la co-citación se puebla en **`chain forward`**, el forrajeo que ya trae los citantes, y **no**
  en un `enrich` suelto ni condicionada a `accepted`), [0020](0020-metodo-forrajeo-scent-filtros-reject.md)
  (**método de forrajeo:** `forward` = **red de citantes** — `chain forward` ya trae los citantes;
  este ADR solo hace que, de paso, complete el campo que la proyección necesita),
  [0014](0014-proyeccion-redes-pesos-asortatividad.md) (**la co-citación es una proyección**: el
  `CoCitationProjector` cuenta `cited_by_id` compartido — **no cambia**; solo cambia **quién** puebla
  su insumo), [0037](0037-superficie-cli-10-verbos-ciclo.md)/[0038](0038-destino-verbos-huerfanos-0037.md)
  (**poda: por qué NO un comando nuevo** — la superficie se consolidó a 10 verbos y `enrich` se
  absorbió en `chain`/`build`; un `build --cocitation` reabriría superficie que estos ADR cerraron),
  [0016](0016-maquina-estados-lazo.md) (**FSM del lazo:** `chain` transiciona a `CHAINED`; este ADR
  **no** cambia la transición).
- **No introduce IA** (coherente con [0022](0022-producto-sin-ia-generativa.md)): es un cambio de
  qué campo puebla un comando determinista ya existente; sin modelo generativo.
- **Origen:** sub-issue [#270](https://github.com/complexluise/bib2graph/issues/270) (P1b de la
  auditoría AX [#204](https://github.com/complexluise/bib2graph/issues/204)), **Bloque A del release
  0.12.0**. Fricción **P1** de la auditoría: el lazo end-to-end `seed → chain forward → curate accept
  → build` produce redes de co-citación **vacías** sin señal clara de por qué.

## Contexto

La **red de co-citación** es una proyección determinista (ADR
[0014](0014-proyeccion-redes-pesos-asortatividad.md)): el `CoCitationProjector` cuenta los
**`cited_by_id` compartidos** entre papers (dos papers están co-citados cuando comparten citantes).
Su insumo es la columna `cited_by_id`; si esa columna está vacía, la red sale vacía.

Hoy **tres comandos tocan `cited_by_id` y ninguno lo completa solo** en el camino del lazo:

1. **`enrich`** (verbo **deprecado**, alias que se elimina en 0.11.0 — ADR
   [0038](0038-destino-verbos-huerfanos-0037.md); capacidad viva del ADR
   [0025](0025-enricher-cocitacion-openalex.md)) puebla `cited_by_id` en su **pasada 8b**, pero
   **solo sobre papers `accepted`** (`is_seed=True AND curation_status=accepted`). Requiere haber
   curado antes, y es un verbo que ya no se anuncia.
2. **`build`** hereda esa misma pasada 8b (ADR 0025, nota append-only del 0038): corre la co-citación
   automáticamente **cuando hay semillas aceptadas** — por eso `build` dejó de ser "puro/sin red".
   También condicionado a `accepted`.
3. **`chain forward`** (forrajeo hacia adelante = **red de citantes**, ADR
   [0020](0020-metodo-forrajeo-scent-filtros-reject.md)) **ya trae los citantes** de las semillas
   para hacer el chaining, pero **NO puebla `cited_by_id`**: usa esa información para proponer
   candidatos y se descarta.

El resultado: un agente que corre el lazo natural `seed → chain forward → curate accept → build`
obtiene una **red de co-citación vacía** sin señal clara de la causa. La información de citantes
**estuvo disponible** durante `chain forward` —el comando que la fue a buscar— pero no se persistió
en el campo que la proyección consume. No hay un **camino feliz único** a la co-citación; hay tres
comandos que la tocan a medias, dos de ellos atados a `accepted` y uno deprecado. Esa es la fricción
**P1** de la auditoría AX ([#204](https://github.com/complexluise/bib2graph/issues/204)): el lazo
end-to-end no cierra.

## Decisión

**`chain forward` puebla `cited_by_id`** además de la metadata del citante que ya materializa.

- El **forrajeo hacia adelante** ya va a OpenAlex a buscar los **citantes** de las semillas (ADR 0020:
  `forward` = red de citantes). Con esta decisión, esa misma pasada **completa el campo `cited_by_id`**
  de los papers alcanzados, dejando listo el insumo del `CoCitationProjector` (ADR 0014).
- Es el **camino implícito**: el lazo existente `seed → chain forward → curate accept → build`
  **"just works"** — `build` proyecta la red de co-citación porque `cited_by_id` ya viene poblado del
  chaining, sin un comando ni un flag que el agente tenga que descubrir.
- **Alcance:** esta decisión cambia **qué campo puebla** `chain forward` (suma `cited_by_id` a la
  metadata del citante). **NO** cambia el envelope `schema="1"`, los exit codes, ni la FSM del lazo
  (`chain`→`CHAINED`, ADR [0016](0016-maquina-estados-lazo.md)/[0021](0021-cli-agente-native-contrato.md)).
  El `CoCitationProjector` (ADR 0014) **no se toca**: sigue contando `cited_by_id` compartido; solo
  cambia **quién** llena su insumo.
- **La implementación, los tests y el cambio de `docs/API.md` viven en el issue
  [#270](https://github.com/complexluise/bib2graph/issues/270)**, no en este ADR (coherente con cómo
  0044/0045 dejaron la edición de `API.md` para el hito de implementación).

## Consecuencias

- (+) **El lazo end-to-end cierra con el camino natural.** `seed → chain forward → curate accept →
  build` produce una red de co-citación **no vacía** sin superficie nueva. Se disuelve la fricción P1
  de [#204](https://github.com/complexluise/bib2graph/issues/204): el agente no tiene que descubrir un
  verbo/flag ni saber que la co-citación vive escondida en `build` o en el `enrich` deprecado.
- (+) **No crece la superficie CLI.** Se respeta la poda a 10 verbos (ADR 0037/0038): la co-citación
  se puebla dentro de un comando que ya existe y ya hace la petición de citantes, no en uno nuevo.
- (+) **La co-citación deja de estar atada a `accepted`.** El chaining forward puebla `cited_by_id`
  al traer los citantes, no en build-time condicionado a la curación. El camino se vuelve **más
  transparente**: quien pidió los citantes (chain) es quien deja el campo listo.
- (+) **El `CoCitationProjector` no cambia** (ADR 0014): sigue siendo función pura sobre
  `cited_by_id`. La proyección permanece determinista y reproducible (ADR 0022/0017).
- (−) **Se solapa transitoriamente con la pasada 8b heredada en `build`/`enrich`** (ADR 0025 / nota
  0038). La unión sobre `cited_by_id` es **idempotente** (ADR 0025: "mergea… unión, idempotente"),
  así que poblarla desde `chain forward` y desde `build` no duplica ni corrompe. Reconciliar dónde
  vive definitivamente la pasada 8b —y si `build` deja de hacer red al recibir el insumo ya poblado—
  es **trabajo del issue #270**, no de este ADR; aquí se fija el **principio** (chain forward la
  puebla), no la limpieza de código.
- (−) **`chain forward` hace un poco más de trabajo de persistencia** (escribe `cited_by_id` de los
  papers alcanzados). Es información que el comando **ya trajo** de la red; el costo incremental es de
  escritura, no de I/O de red adicional.
- **`docs/API.md` a precisar en la implementación.** La sección de `chain` debe declarar que `chain
  forward` puebla `cited_by_id`, y la de `build` / la co-citación reconciliarse con este camino. *Esa
  edición es trabajo del `coder` al implementar #270, no parte de este ADR.*

## Alternativas

- **Comando/flag explícito `build --cocitation`** (un flag —o comando— nuevo que orqueste `accept →
  chain forward --mode cite → build` en un paso, materializando la co-citación bajo demanda).
  **Rechazada:**
  - **Suma superficie nueva justo cuando la poda la está reduciendo.** El ADR 0037/0038 consolidó la
    superficie a **10 verbos** y **absorbió** `enrich` en `chain`/`build` precisamente para no tener
    verbos por acreción; un `build --cocitation` reabre superficie que esos ADR cerraron y tensiona
    con el conteo "10 verbos".
  - **Menos transparente para un agente.** Un flag/comando nuevo es algo que hay que **descubrir**; si
    el agente no lo conoce, vuelve a obtener la red vacía sin señal. El camino implícito hace que el
    lazo que el agente ya corre —`chain forward`— produzca el insumo, sin conocimiento previo.
- **Dejar la co-citación solo en `build`/`enrich` (statu quo) y solo documentarla mejor.**
  **Rechazada:** es exactamente la fricción P1 de [#204](https://github.com/complexluise/bib2graph/issues/204).
  La co-citación queda atada a `accepted` y escondida en un verbo deprecado (`enrich`) o en un efecto
  lateral de `build`; el camino `chain forward` —el que fue a buscar los citantes— sigue tirando esa
  información. Documentar un camino confuso no lo vuelve un camino feliz único.
