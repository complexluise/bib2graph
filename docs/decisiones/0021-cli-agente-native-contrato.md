# 0021 — Contrato del CLI agente-native `b2g`: set de subcomandos, envelope JSON y exit codes

- **Estado:** Aceptada
- **Fecha:** 2026-06-15
- **Decidido por:** mixto — el **set de 11 subcomandos** (en particular incluir `accept`/`reject`)
  y la **separación `build`/`export`** son **decisiones del Product Owner humano**; el resto
  (forma del envelope JSON y su versionado, mapeo de errores a exit codes por tipo de excepción,
  `--store` global, transiciones automáticas de `LoopState` por comando) son decisiones de la IA
  (Claude) validadas por el PO proxy.
- **Relacionada con:** [0010](0010-agente-native-columna.md) (CLI agente-native como columna
  primaria — este ADR **concreta** su contrato), [0016](0016-maquina-estados-lazo.md) (`LoopState`
  y transiciones permisivas), [0019](0019-concurrencia-diferida.md) (single-writer →
  `StoreLockedError` → exit 5).
- **Toca:** [0009](0009-biblioteca-viva-duckdb.md) (el estado vive en el archivo `.duckdb`, no en
  la sesión), [0020](0020-metodo-forrajeo-scent-filtros-reject.md) (comando `filter` y los
  filtros que marcan `rejected`).

## Contexto

El ADR [0010](0010-agente-native-columna.md) fijó el **principio** ("la CLI agente-native es
superficie primaria desde el primer comando", con doble salida, exit codes 0–5, errores
accionables y sin estado entre invocaciones) pero **no** el contrato concreto: qué subcomandos
existen, qué forma tiene exactamente la salida `--json`, ni cómo se mapea cada clase de error a un
exit code. El Hito 6 (CLI como producto) construye ese contrato y obliga a decidir cuatro cosas que
quedaban abiertas:

1. **¿Cuál es el set exacto de subcomandos?** El ADR 0010 y `API.md` §convenciones listaban un set
   provisional (`seed`, `chain`, `filter`, `build`, `export`, `snapshot`, `status`, `inspect`,
   `validate`) y decían que el `accept`/`reject` "programático sobrevive vía `Corpus`/backend".
   ¿Esa curación programática se expone como subcomando CLI o queda solo como API de librería?
2. **¿Una sola operación `build`+`export` o dos comandos separados?** El cómputo de redes
   (`Networks.quick`) y su serialización a un formato concreto (GraphML/CSV) son pasos distintos
   con costos distintos.
3. **¿Qué forma tiene la salida `--json`?** El ADR 0010 pide "estructurado, estable y versionado"
   sin especificar la estructura.
4. **¿Cómo se mapea cada error a un exit code?** El ADR 0010 fija los códigos 0–5 por significado,
   pero no qué excepción de Python produce cada uno.

## Decisión

### A. Set de subcomandos, incluyendo `accept`/`reject` (decisión del PO)

> **Cleanup pre-v0.3 (2026-06-16):** el set creció a **12 subcomandos** con el alta de **`monitor`**
> (ver enmienda al final). El texto original (11) queda como historia.

El CLI `b2g` expone **11 subcomandos** (original; **12 con `monitor`** desde el cleanup pre-v0.3):

`seed`, `chain`, `filter`, `build`, `export`, `snapshot`, `status`, `inspect`, `validate`,
**`accept`**, **`reject`** (+ **`monitor`**, cleanup pre-v0.3).

Esto **amplía** el set provisional de `API.md` §convenciones (que listaba 9 y dejaba `accept`/
`reject` como "sobrevive programáticamente"): el PO decidió que la curación programática
(`accept`/`reject` por `--ids`) **es un subcomando CLI de primera clase**, no solo API de
librería — para que un agente cure la biblioteca viva por subprocess sin escribir Python (historia
C4). La **curación interactiva rica (`curate`) y la GUI siguen siendo futuro**: `accept`/`reject`
son deterministas y sin estado interactivo.

### B. `build` y `export` son comandos separados (decisión del PO)

- **`build`** computa las redes con `Networks.quick` (acoplamiento sobre corpus completo,
  co-autoría, instituciones, co-word, y co-citación si `cited_by_id` está poblado tras `enrich`,
  Hito 8b → **4 o 5 redes**) y **escribe artefactos intermedios a disco**
  (`<store_dir>/networks/<kind>/network.graphml` + `metrics.json`). Transiciona el `LoopState` a
  `BUILT`.
- **`export`** **relee** esos artefactos de build y los **serializa** al formato pedido
  (`--format graphml|csv`) en el `--out-dir`. **No** recomputa redes y **no** transiciona el
  `LoopState`.

Separarlos permite computar una vez y exportar a varios formatos/destinos sin recalcular, y deja
`build` como el paso que avanza la máquina de estados.

### C. Envelope JSON común y versionado (`schema="1"`)

Cada subcomando con `--json` emite **un único objeto JSON** con la estructura estable:

```json
{
  "schema": "1",
  "ok": true,
  "command": "seed",
  "exit_code": 0,
  "data": { },
  "warnings": [],
  "error": null
}
```

- `schema` es la **versión del contrato** (`"1"` hasta que se declare una ruptura).
- En éxito: `ok=true`, `error=null`, `data` con el payload del comando.
- En error conocido: `ok=false`, `data={}`, `error={"code": <CODE>, "message": <accionable>}`.
- `warnings` transporta avisos no fatales (p. ej. el `translation_report` de `seed`).

El envelope es **lo único que el comando imprime en stdout en modo `--json`**: un agente parsea una
línea JSON por invocación.

### D. Exit codes mapeados por **tipo de error** (no por comando)

El decorador `@handle_errors(command)` captura excepciones por tipo y las traduce a exit codes
(ADR 0010), de forma uniforme para los 11 comandos:

| Exit | Significado | Origen (excepción) |
|------|-------------|--------------------|
| `0` | éxito | — |
| `1` | uso (opción faltante/inválida) | `UsageError` / errores de parseo de Click |
| `2` | datos (schema inválido, ids inexistentes, criterio de filtro vacío) | `DataError` |
| `3` | dependencia/capacidad faltante | `ImportError` (extra ausente) · `DependencyError` (capacidad de source faltante, p. ej. sin `fetch_citing` — ver enmienda R5) · `NotImplementedError` (p. ej. `depth>1`) |
| `4` | red no disponible | `httpx.HTTPError` y subclases (captura **por tipo**, toda la jerarquía) |
| `5` | store/snapshot bloqueado o corrupto | `StoreLockedError` / `OSError` (single-writer, ADR 0019) |

> **Enmienda R5 (2026-06-16) — `AttributeError` ya NO se mapea a exit 3 en el decorador.** El AS-BUILT
> capturaba `AttributeError` en `@handle_errors` y lo emitía como "Capacidad no disponible" (exit 3).
> Eso **disfrazaba bugs reales** (un `AttributeError` genuino dentro de `chain`/`merge`/`_fetch_forward`
> se reportaba como "el source no soporta forward"). R5 separa las dos cosas (Nota 06, catálogo de
> secundarios):
> - La conversión **capacidad-de-source-faltante → `DependencyError` (exit 3)** es responsabilidad del
>   **borde CLI**: el comando hace un **pre-check explícito** (`chain.py` verifica
>   `hasattr(source, "fetch_citing")` antes de instanciar el `Forager`) y lanza `DependencyError` con
>   un mensaje accionable. El **forager queda agnóstico de `_errors`** (núcleo puro; no importa la capa
>   CLI).
> - Un **`AttributeError` inesperado se propaga limpio** (falla accionable/visible), ya no se traga.
> - **Rama muerta colapsada:** el `if isinstance(exc, StoreLockedError)` / `else` de la rama `OSError`
>   hacía lo mismo en ambas ramas (exit 5); R5 lo simplificó a un único `except OSError → exit 5`.
>
> **Enmienda R5 — comandos de solo lectura no auto-crean el store.** `status`/`validate` usaban
> `open_store`, que **crea un `.duckdb` vacío** ante un typo en `--store` (footgun verificado, Nota 06).
> R5 agrega `open_store_readonly` (`cli/_store.py`): verifica que el archivo exista y, si no, lanza
> `StoreError` accionable ("el store no existe… iniciá con `b2g seed`"). `status`/`validate` la usan;
> los comandos de **escritura** conservan `open_store` (crear-si-falta es su comportamiento correcto).

### E. `--store` global + sin estado entre invocaciones (tensión núcleo-valor)

`--store <archivo.duckdb>` es una **opción global del grupo** (en el grupo `b2g`, antes del
subcomando), **obligatoria**. El núcleo es puro y **sin estado de sesión** (ADR 0010/0015), pero el
**valor** del producto exige continuidad entre invocaciones (la biblioteca viva). Esa tensión se
resuelve haciendo que **todo el estado viva en el archivo `.duckdb`**: el CLI es stateful **vía
archivo**, no vía proceso. Dos `b2g` consecutivos comparten estado solo a través de `--store`.

**Consecuencia de borde — el error de uso sale sin envelope:** si falta `--store` (o una opción
requerida del subcomando), Click aborta el parseo **antes** de entrar a la función del comando, así
que **no hay envelope JSON**: se emite el mensaje de uso de Click en stderr y exit code `1`. El
envelope versionado solo aplica a errores que ocurren **dentro** de la ejecución del comando.

### F. Transiciones de `LoopState` automáticas por comando

Los comandos que mutan el corpus avanzan la máquina de estados (ADR
[0016](0016-maquina-estados-lazo.md), transiciones **permisivas**) **automáticamente** tras
persistir con éxito:

| Comando | Transición |
|---------|-----------|
| `seed` | → `SEEDED` |
| `chain` | → `FORAGED` |
| `filter` | → `FILTERED` |
| `build` | → `BUILT` |
| `export`, `snapshot`, `status`, `inspect`, `validate`, `accept`, `reject` | **no transicionan** |

`accept`/`reject` mutan curación pero **no** mueven el lazo (curar no es una fase del flujo
exploratorio). `status` lee y presenta el estado actual + las transiciones disponibles.

> **Enmienda 2026-06-15 (curación transversal en `status`):** que `accept`/`reject` **no
> transicionen** es correcto, pero el AS-BUILT también las **oculta** de `transitions_available`
> (`cli/commands/status.py:19-34`), dejando invisible lo único irreductiblemente humano. Tras la
> enmienda del ADR [0016](0016-maquina-estados-lazo.md) (curación transversal), **`b2g status` debe
> mostrar `accept`/`reject` como acción SIEMPRE-disponible** (en cualquier estado), separada de las
> transiciones del lazo. Además, el FSM gana `reseed` (loop-back a `SEEDED` con contador de ronda) y
> el estado `MONITORED`: `status` debe reflejarlos. Ver ROADMAP **Hito R3**. El bug **UTF-8 en
> Windows** (`cli/_envelope.py:67`: `ensure_ascii=False` sin forzar UTF-8 en stdout → acentos
> corruptos, rompe el contrato agente-native) se corrige en ROADMAP **Hito R5**.

> **Implementado en R3 (2026-06-16):** el envelope `--json` de `status` (sección C) suma dos campos
> en `data`, **aditivos** y que **mantienen `schema="1"`** (decisión del PO 2026-06-16: campos nuevos
> no rompen a los agentes, no se bumpea la versión del contrato):
> - **`curation_available`**: `["accept", "reject"]` **siempre** (curación transversal — disponible en
>   cualquier estado, no transiciona). Antes de R3 `transitions_available` nunca las listaba (bug
>   cerrado); ahora viven en un campo propio, separado de las transiciones del lazo.
> - **`round`**: contador de ronda (`0` sin estado · `1` primera ronda · `2+` re-sembrados).
>
> Además, `transitions_available` ahora se deriva de `bib2graph.cycle.available_transitions` (no de la
> tabla `_TRANSITIONS` local, retirada) y **refleja el ciclo**: incluye `reseed` cuando hay estado
> previo. La tabla F (transiciones automáticas por comando) **sigue vigente**; `seed` agrega la
> semántica `reseed` (estado previo → ronda++) cablada en `seed.py`. `MONITORED` está en el modelo
> pero **ningún comando lo dispara** aún. El bug UTF-8 sigue pendiente (Hito R5).

## Consecuencias

- **Un agente orquesta todo el flujo de 10 minutos por subprocess + JSON** sin escribir Python:
  `seed → chain → filter → (accept/reject) → build → export`, parseando un envelope estable por
  llamada y ramificando por `exit_code`. La frontera programática del producto queda cubierta sin
  tool schemas ni MCP (que siguen siendo futuro, ROADMAP §costuras futuras).
- **`accept`/`reject` como CLI** cierra C4 a nivel de agente (curar la biblioteca viva sin
  librería), al costo de **dos comandos más** que mantener bajo el contrato del envelope.
- **`build`/`export` separados** habilitan exportar a varios formatos sin recomputar, pero
  introducen un **acoplamiento por disco**: `export` depende de que `build` haya escrito los
  artefactos intermedios; si no existen, `export` falla con `DataError` (exit 2) y un mensaje que
  pide correr `build` primero. (Gap conocido: `export` relee GraphML de disco en vez de recibir los
  artefactos en memoria — es el precio de desacoplar los dos pasos vía el sistema de archivos.)
- **El envelope versionado (`schema="1"`)** habilita evolucionar la salida sin romper agentes: un
  cambio incompatible bumpea `schema`. **Costo**: tests de contrato `--json` (golden/schema) por
  comando para que la forma no driftee (ROADMAP, disciplina de tests).
- **Captura de errores por tipo** mantiene el mapeo de exit codes **uniforme y testeable** (un caso
  por código), sin que cada comando reinvente el manejo. **Trade-off**: un `OSError` no-bloqueo que
  no sea `StoreLockedError` igualmente cae en exit `5` (se trata cualquier `OSError` del store como
  "store inaccesible"); es conservador pero puede enmascarar un error de I/O no relacionado con el
  bloqueo.
- **`--store` global obligatorio** simplifica el modelo mental (una investigación = un archivo) pero
  hace que **el error de uso más común** (olvidar `--store`) salga **fuera del envelope** (exit 1,
  stderr de Click). Un agente debe tratar exit 1 sin envelope como error de invocación, no de
  dominio.
- **Las transiciones automáticas** dan un `LoopState` siempre consistente con el último comando
  mutador, sin que el usuario lo gestione. Como las transiciones son **permisivas** (ADR 0016), no
  hay guardia: re-sembrar tras `BUILT` está permitido y solo re-apunta el estado a `SEEDED`.

## Enmienda — Cleanup pre-v0.3 (2026-06-16): 12° subcomando `monitor`

> Cierra dos seguimientos de R3/R5 (alias `LoopState` retirado; `MONITORED` alcanzable — ver ADR
> [0016](0016-maquina-estados-lazo.md) §Cleanup pre-v0.3). Implementado + verificado (327 tests, mypy
> strict, ruff+format OK).

**El set pasa de 11 a 12 subcomandos** con el alta de **`monitor`** (paso 8 del ciclo, Ellis):

- **§A (set):** se agrega `monitor` → **12 subcomandos**. Re-chequea OpenAlex por **citantes nuevos**
  del corpus (forward chaining), mergea los candidatos nuevos a la biblioteca viva y transiciona a
  `MONITORED`. `--email` (polite pool); sin corpus/estado previo → `DataError` (exit 2, accionable).
- **§C (envelope):** el `data` de `monitor` es
  `{"new_candidates": <int>, "total_papers": <int>, "loop_state": <str>, "round": <int>}`, dentro del
  envelope común con **`schema="1"`** (sin bump; campo de payload nuevo, no cambia la forma del
  envelope). `--json` emite el objeto único de siempre.
- **§F (transiciones):** se agrega la fila **`monitor` → `MONITORED`**. La regla `monitor` está en
  `cycle.apply_transition` desde `BUILT` y desde `MONITORED` (re-monitoreo). El destino lo dicta el
  dominio (fuente única), como el resto de los comandos mutadores.
- **§D (pre-check de capacidad) — asimetría deliberada `monitor` vs `chain`:** `monitor` **NO** hace
  el pre-check `hasattr(source, "fetch_citing")` que sí hace `chain` (enmienda R5). El motivo es que
  `monitor` instancia **`OpenAlexSource` fijo** —que **siempre** tiene `fetch_citing`—, mientras que
  `chain` acepta una `--direction` variable y puede recibir una `Source` de solo-mínimo (ADR 0018)
  que no soporte forward; por eso `chain` pre-chequea y lanza `DependencyError` (exit 3) accionable, y
  `monitor` no necesita la guardia. La asimetría es **decisión documentada, no deuda**: el pre-check
  es responsabilidad del borde **solo donde la capacidad puede faltar**.

**Además, el alias `LoopState = CycleState` se RETIRÓ** del código (`backends/duckdb.py` y
`stores/duckdb.py`): el contrato usa **solo `CycleState`** (de `bib2graph.cycle`). Donde este ADR
dice "`LoopState`", léase `CycleState` (mismo concepto, una sola clase).

## Enmienda — `--store` deja de ser global obligatorio (AS-BUILT, 2026-06-16)

> **Implementado por [0029](0029-workspace-por-investigacion.md) (ver su AS-BUILT).** El cuerpo de
> este ADR queda como historia; esta enmienda actualiza el §E al as-built.

El §E fijaba `--store` como **opción global del grupo, obligatoria**. Con el modelo "workspace por
investigación" (ADR [0029](0029-workspace-por-investigacion.md)), `--store` pasó a **opcional** y se
agregó **`--workspace`** (ambos opcionales): la unidad de persistencia deja de ser un `.duckdb`
suelto y pasa a ser una **carpeta workspace** (marcada por `workspace.json`), resuelta por
**ambiente** (patrón git/cargo: walk-up del cwd). Precedencia: `--workspace`/`--store` explícito >
`B2G_WORKSPACE` (env) > workspace del cwd. **`--workspace` y `--store` son mutuamente excluyentes**
(juntos = error de uso). `--workspace` es el flag primario; `--store` sobrevive para apuntar a un
`.duckdb` suelto (workspace "degenerado", retrocompatible). Sin flag y sin workspace resoluble → error
accionable que sugiere `b2g init`.

El cambio es **aditivo/retrocompatible**: la resolución ambiente solo cubre el caso en que falta el
flag; el resto del contrato (envelope `schema="1"`, exit codes, transiciones) **no cambia**. El set
de subcomandos pasa de 13 a **14** con el alta de `b2g init` (scaffold del workspace).

## Enmienda — `--store` eliminado del CLI (BREAKING, [#75](https://github.com/complexluise/bib2graph/issues/75), 2026-06-17)

> **Supera la enmienda 2026-06-16 de arriba** (que dejaba `--store` "opcional"). Aquella queda como
> historia; el §E pasa a su forma final. Implementado por la enmienda 2026-06-17 de
> [0029](0029-workspace-por-investigacion.md) (ver su detalle).

`--store` **se elimina por completo del CLI**: ya no está registrada como opción global en Click.
Pasarla produce el **error estándar de Click** (`No such option: --store`, con su exit code), no un
mensaje custom de migración. La **única forma canónica** de apuntar a la persistencia es
`--workspace <carpeta>` o la resolución ambiente (`B2G_WORKSPACE` > walk-up del cwd buscando
`workspace.json`). El modo degenerado (`.duckdb` suelto) **deja de existir**: un `.duckdb` legacy se
adopta como workspace con `b2g init .` en su carpeta. Es un **BREAKING change** del contrato CLI.

## Enmienda — `B2G_JSON` activa el modo JSON por entorno (2026-06-27, [#151](https://github.com/complexluise/bib2graph/issues/151))

> Enmienda **aditiva** al §C (envelope). El flag `--json` y su forma **no cambian**; el envelope
> `schema="1"`, los exit codes (§D) y la FSM (§F) quedan **intactos**. Complementa la enmienda al §C
> que reclamó el ADR [0037](0037-superficie-cli-10-verbos-ciclo.md) (stdout puro). Implementado +
> verificado (gate verde).

El §C declaraba que `--json` es **lo único** que el comando imprime en stdout. Esta enmienda fija dos
cosas que el AS-BUILT explicita:

1. **stdout puro ENFORCED.** En modo JSON, stdout emite **exactamente la línea-envelope**, incluido
   el **camino de error** (`ok=false` → envelope en stdout, no en stderr). El texto de modo humano va
   a **stderr**. Antes era contrato declarado; ahora está enforced y testeado.
2. **Activación por entorno con `B2G_JSON`.** El modo JSON se activa también con la variable de
   entorno **`B2G_JSON`** (truthy: `1`/`true`/`yes`, case-insensitive), con alcance a **todos** los
   comandos (incl. `init`). **Precedencia:** `--json` explícito > `B2G_JSON`. **No hay `--no-json`.**
   La **superficie de invocación del flag no cambia**: `--json` sigue siendo por-comando y
   **post-verbo** (`b2g <cmd> --json`), no se vuelve global. Caso de uso agents-first: `export
   B2G_JSON=1` una vez por sesión y no repetir el flag.

En código se unificó el flag vía un decorador compartido `@json_option` (`cli/_options.py`, con
`json_mode(local_flag)` que resuelve flag-o-entorno); es refactor interno, **no** cambia el contrato
externo. Documentado en `docs/API.md` §convenciones CLI (Envelope JSON / `B2G_JSON`).
