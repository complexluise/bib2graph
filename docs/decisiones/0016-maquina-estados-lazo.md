# 0016 — Máquina de estados del lazo; no-linealidad de primera clase; una investigación por archivo

- **Estado:** Aceptada · **enmendada 2026-06-15** (FSM cíclico con `reseed` de primera clase,
  contador de ronda, curación transversal, `cycle.py` en el dominio — ver "Enmienda" al final)
- **Fecha:** 2026-06-15
- **Relacionada con:** [0008](0008-wedge-forrajeo.md) (wedge = forrajeo),
  [0009](0009-biblioteca-viva-duckdb.md) (biblioteca viva en DuckDB),
  [0015](0015-corpus-tabular-backend.md) (`Corpus` sobre `TabularBackend`),
  [`../Notas/05-ciclo-investigacion-humano.md`](../Notas/05-ciclo-investigacion-humano.md)

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
  **Hito 6** (CLI). Ver [ROADMAP](../ROADMAP.md) Hitos 3 y 6.
- **Tensión declarada:** la máquina de estados es del **archivo vivo**; el **snapshot** (ADR
  [0017](0017-reproducibilidad-historia-snapshot.md)) es una foto que puede incluir el `LoopState`
  del instante sellado, pero no es donde vive.

## Enmienda — 2026-06-15 (FSM cíclico de dominio; `reseed` de primera clase; curación transversal)

> Motivada por el red-team del AS-BUILT v0.2
> ([Nota 06](../Notas/06-critica-as-built-v0.2.md), RAÍZ 1): este ADR prometía no-linealidad de
> primera clase, pero el AS-BUILT la entregó como un enum **lineal** (`SEEDED→FORAGED→FILTERED→BUILT`)
> enterrado en `backends/duckdb.py:67-78`, con la no-linealidad reducida a un comentario
> ("transiciones permisivas") y la curación **invisible** en el mapa. El cuerpo del ADR (arriba)
> queda como historia; esta enmienda precisa el modelo correcto.

1. **El ciclo es un concepto de DOMINIO puro y testeable** — módulo nuevo `cycle.py` (núcleo): el
   modelo de estados + las reglas de transición viven ahí; el **backend solo lo persiste** (el
   `LoopState` deja de estar definido dentro de `backends/duckdb.py`).
2. **FSM cíclico fiel a la [Nota 05](../Notas/05-ciclo-investigacion-humano.md):**

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
