# 0016 — Máquina de estados del lazo; no-linealidad de primera clase; una investigación por archivo

- **Estado:** Aceptada · **enmendada 2026-06-15** (FSM cíclico con `reseed` de primera clase,
  contador de ronda, curación transversal, `cycle.py` en el dominio — ver "Enmienda" al final)
- **Fecha:** 2026-06-15
- **Relacionada con:** [0008](0008-wedge-forrajeo.md) (wedge = forrajeo),
  [0009](0009-biblioteca-viva-duckdb.md) (biblioteca viva en DuckDB),
  [0015](0015-corpus-tabular-backend.md) (`Corpus` sobre `TabularBackend`),
  `../Notas/05-ciclo-investigacion-humano.md`

## Contexto

El PRD (§1–§2) y el ADR 0008 declaran que el flujo **no es un pipeline lineal** sino un **ciclo
iterativo** (Bates / Ellis / Kuhlthau): se siembra, se forrajea, se cura, la idea muta y se
**vuelve a sembrar** acumulando sobre lo curado (*berrypicking* / *berry growing*). Pero esa
no-linealidad estaba descrita en prosa, no **modelada**: nada en el sistema sabe en qué punto del
lazo está una investigación, y humanos e IAs no comparten un mapa explícito del estado.

Sin un estado explícito, una IA que orquesta `bib2graph` por CLI (ADR 0010) no puede saber si
"ya sembró", "ya forrajeó pero no curó", o "está lista para construir redes" — tendría que
inferirlo del contenido del corpus, frágilmente.

Además, el ADR 0009 dejó la biblioteca viva en DuckDB pero no definió **cuántas investigaciones**
caben en un archivo ni dónde vive el estado del lazo.

## Decisión

Modelar el ciclo como una **máquina de estados explícita** (`LoopState`):

```
SEEDED → FORAGED → FILTERED → BUILT
```

con **transiciones permisivas**: se puede **re-sembrar desde casi cualquier estado** (la idea
muta — es *berrypicking*, no un pipeline rígido). El lazo `…→ SEEDED` siempre está disponible;
los estados no son una escalera de un solo sentido.

- El **`LoopState` vive en la biblioteca viva** (el backend persistente DuckDB, ADR
  [0015](0015-corpus-tabular-backend.md)), **no** en el `Corpus` efímero. El `Corpus` que circula
  por el pipeline no carga el estado del lazo; lo lleva el archivo vivo.
- **Una investigación = un archivo `.duckdb`** con su propio `LoopState`. **No hay tabla
  `investigations`**: varias investigaciones son **varios archivos**. Esto mantiene cada
  investigación autocontenida, portable y diffeable, y encaja con la limitación single-writer de
  DuckDB ([0017](0017-reproducibilidad-historia-snapshot.md) /
  [0019](0019-concurrencia-diferida.md)).
- Un comando **`b2g status`** expone el `LoopState` (estado actual, transiciones disponibles,
  conteos por `curation_status`): humanos e IAs **comparten el mismo mapa del lazo**.

## Consecuencias

- **La no-linealidad pasa a ser propiedad del sistema, no solo del discurso.** El re-sembrado
  (historia A5) tiene un estado al que volver; el lazo `2→3→4→1` del PRD es observable.
- **Agente-native real** (ADR 0010): una IA consulta `b2g status --json`, sabe en qué punto está
  y qué puede hacer a continuación, sin inferirlo del contenido.
- **Aislamiento por archivo:** una investigación por `.duckdb` evita el acople entre líneas de
  trabajo y simplifica el backup/versionado. El costo es que **no hay** una vista unificada de
  varias investigaciones en V1 (sería un índice de archivos, futuro).
- **Transiciones permisivas, no validación rígida:** el sistema no bloquea "saltos" (p. ej.
  re-sembrar tras `BUILT`); registra la transición. Esto evita imponer un orden que contradiga a
  Bates/Ellis/Kuhlthau, al costo de que el `LoopState` es un **mapa**, no un guardia.
- **Recomendación para el `coder`:** el `LoopState` (enum + transición + timestamp) y la tabla que
  lo persiste caen en el **Hito 3** (`DuckDBBackend`/`DuckDBStore`); el comando `b2g status` en el
  **Hito 6** (CLI). Ver ROADMAP Hitos 3 y 6.
- **Tensión declarada:** la máquina de estados es del **archivo vivo**; el **snapshot** (ADR
  [0017](0017-reproducibilidad-historia-snapshot.md)) es una foto que puede incluir el `LoopState`
  del instante sellado, pero no es donde vive.

## Enmienda — 2026-06-15 (FSM cíclico de dominio; `reseed` de primera clase; curación transversal)

> Motivada por el red-team del AS-BUILT v0.2
> (Nota 06, RAÍZ 1): este ADR prometía no-linealidad de
> primera clase, pero el AS-BUILT la entregó como un enum **lineal** (`SEEDED→FORAGED→FILTERED→BUILT`)
> enterrado en `backends/duckdb.py:67-78`, con la no-linealidad reducida a un comentario
> ("transiciones permisivas") y la curación **invisible** en el mapa. El cuerpo del ADR (arriba)
> queda como historia; esta enmienda precisa el modelo correcto.

1. **El ciclo es un concepto de DOMINIO puro y testeable** — módulo nuevo `cycle.py` (núcleo): el
   modelo de estados + las reglas de transición viven ahí; el **backend solo lo persiste** (el
   `LoopState` deja de estar definido dentro de `backends/duckdb.py`).
2. **FSM cíclico fiel a la Nota 05:**

   ```
   SEEDED ─(chain)→ FORAGED ─(filter)→ FILTERED ─(build)→ BUILT ─(monitor)→ MONITORED
      ▲                                                                          │
      └──────────────────────── reseed = "la idea muta" ◄─────────────────────────┘
   ```

   con la transición de **PRIMERA CLASE `reseed`** (loop-back a `SEEDED`), que **incrementa un
   CONTADOR DE RONDA** y **acumula sobre lo curado**. La no-linealidad pasa a ser **propiedad del
   sistema** (lo que este ADR prometía y el AS-BUILT no cumplía), no un comentario. `MONITORED`
   modela el paso 8 del ciclo (el comando que lo dispara puede ser futuro; el estado existe).
3. **La curación es TRANSVERSAL.** `accept`/`reject` están disponibles **en cualquier estado**, **no
   transicionan** el lazo, pero `b2g status` **debe** mostrarlas como **acción siempre-disponible**
   (hoy las oculta de `transitions_available`). Es lo único irreductiblemente humano (Nota 05 §4,
   pasos 0/4/7): el mapa del lazo no puede esconderlo.

**Consecuencia:** humanos e IAs ven un mapa que (a) refleja el ciclo real, no un pipeline; (b)
cuenta las rondas; (c) muestra la curación. **Recomendación para el `coder`:** ver ROADMAP **Hito
R3** (extraer `cycle.py`; `cli/commands/status.py:19-34` debe incluir `accept`/`reject` como
siempre-disponibles; `cli/commands/accept.py:104` ya no transiciona — eso queda, pero `status` debe
exponerlas).

### Implementado en R3 (2026-06-16)

La enmienda está **construida** (ROADMAP Hito R3 ✅). As-built:

- **`src/bib2graph/cycle.py` es la sede del dominio** (puro, sin DuckDB): `CycleState`
  (`SEEDED`/`FORAGED`/`FILTERED`/`BUILT`/`MONITORED`), `apply_transition(state, action, round)
  → (state, round)`, `available_transitions(state)` y `CURATION_ACTIONS = ["accept", "reject"]`.
  El enum de estados **salió** de `backends/duckdb.py`; el backend solo persiste (columna `round`
  añadida a `loop_state_log` por migración liviana; `loop_round()` / `set_loop_state(state, *,
  cycle_round=...)`).
- **`reseed` es de primera clase:** `apply_transition(state, "reseed", r) = (SEEDED, r+1)`. Lo
  cablea `seed.py`: si hay estado previo, la siembra se trata como `reseed` (ronda++, acumula sobre
  lo curado); si no, primera siembra (`seed` → `SEEDED`, ronda→1).
- **Fuente única de verdad:** `chain.py`/`filter.py`/`build.py` **derivan** su estado destino de
  `apply_transition`, no de un literal (cierra el gap que el verifier marcó). Un test domain-tied
  (`tests/unit/test_r3_commands_domain.py`) lo ata: si cambian las reglas en `cycle.py`, los comandos
  las siguen.
- **Curación transversal:** `accept.py`/`reject.py` documentan "no transiciona"; `status.py` expone
  `curation_available=["accept","reject"]` **siempre** + `round`, usando `available_transitions`.
- **Alias transicional:** `backends/duckdb.py` mantiene `LoopState = CycleState` por
  compatibilidad de imports. **A retirar pre-1.0** (recomendación de código abierta).
- **`MONITORED`** existe en el modelo y en las reglas de transición, pero **ningún comando lo
  dispara todavía** (futuro; un eventual `b2g monitor`).

Verifier: **APRUEBA** (275 tests; mypy strict / ruff limpios). La reserva del verifier
(chain/filter/build no pasaban por el dominio) quedó **cerrada** con el fix posterior.

### Cleanup pre-v0.3 (2026-06-16) — `MONITORED` alcanzable; alias `LoopState` retirado

Dos seguimientos abiertos de R3 (arriba) quedan **CERRADOS**:

- **`MONITORED` ya NO es inalcanzable.** Se construyó el comando **`b2g monitor`** (12° subcomando):
  re-chequea OpenAlex por **citantes nuevos** del corpus (forward chaining), mergea los candidatos
  nuevos a la biblioteca viva y transiciona vía `apply_transition(state, "monitor", round)`. El paso 8
  del ciclo (monitoreo, Ellis) deja de ser un estado del modelo sin compuerta: ahora es **reachable**.
  La regla `monitor` se agregó a `_AVAILABLE_TRANSITIONS` desde `BUILT` y desde `MONITORED` (re-monitoreo
  idempotente del estado). Contrato del comando: ADR [0021](0021-cli-agente-native-contrato.md).
- **El alias `LoopState = CycleState` se RETIRÓ** (la recomendación "a retirar pre-1.0"): el código usa
  **solo `CycleState`** (de `bib2graph.cycle`). Se eliminó de `backends/duckdb.py` y `stores/duckdb.py`;
  los call-sites migraron. No queda una segunda clase para el mismo concepto.

### AS-BUILT — `restore` reusa la transición permisiva `filter` (2026-06-17, Ciclo 9a)

> **No es una enmienda al modelo: es una nota de uso.** El comando `b2g restore --from-corpus`
> (ADR [0030](0030-ecuacion-declarativa-corpus-ejemplo.md), 17° subcomando) **no introduce una
> transición nueva** en la FSM. Rehidrata un corpus **ya curado** y necesita dejar el lazo en un estado
> que habilite `build`/`networks` sin re-forrajeo; para eso **reusa la transición `filter` → `FILTERED`**
> ya existente (`cycle.py:_CHAIN_TRANSITIONS`). La FSM es **permisiva** (este ADR, "transiciones
> permisivas, no validación rígida"): `apply_transition(state, "filter", round)` es válida desde
> cualquier estado actual, incluido un store vacío (`None`), donde `restore` sintetiza un `SEEDED`
> ficticio antes de aplicar `filter`. La ronda se normaliza con `max(loop_round(), 1)` para no persistir
> ronda 0 en bases legacy (pre-R3, `round=NULL`) ni en stores vacíos. Como la transición ya estaba
> cubierta por la permisividad de la FSM, **no se modifica `cycle.py` ni el cuerpo de esta enmienda**;
> esta nota solo deja registrado el reuso (el docstring de `restore.py` lo cita como "ADR 0016
> enmendado §1"). Ver API.md §`restore` y §convenciones CLI.
