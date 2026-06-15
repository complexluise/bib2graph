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

### A. Set de 11 subcomandos, incluyendo `accept`/`reject` (decisión del PO)

El CLI `b2g` expone **11 subcomandos**:

`seed`, `chain`, `filter`, `build`, `export`, `snapshot`, `status`, `inspect`, `validate`,
**`accept`**, **`reject`**.

Esto **amplía** el set provisional de `API.md` §convenciones (que listaba 9 y dejaba `accept`/
`reject` como "sobrevive programáticamente"): el PO decidió que la curación programática
(`accept`/`reject` por `--ids`) **es un subcomando CLI de primera clase**, no solo API de
librería — para que un agente cure la biblioteca viva por subprocess sin escribir Python (historia
C4). La **curación interactiva rica (`curate`) y la GUI siguen siendo futuro**: `accept`/`reject`
son deterministas y sin estado interactivo.

### B. `build` y `export` son comandos separados (decisión del PO)

- **`build`** computa las redes con `Networks.quick` (4 redes: acoplamiento sobre corpus completo,
  co-autoría, instituciones, co-word) y **escribe artefactos intermedios a disco**
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
| `3` | dependencia/capacidad faltante | `ImportError` (extra ausente) · `AttributeError` (p. ej. source sin `fetch_citing`) · `NotImplementedError` (p. ej. `depth>1`) |
| `4` | red no disponible | `httpx.HTTPError` y subclases (captura **por tipo**, toda la jerarquía) |
| `5` | store/snapshot bloqueado o corrupto | `StoreLockedError` / `OSError` (single-writer, ADR 0019) |

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
