# 0028 — Arquitectura GUI/API/frontend: capa de servicios neutral + adaptadores

- **Estado:** Aceptada — **firmada por el PO (2026-06-18)** ("de acuerdo con el plan; acepto que es más
  superficie, pero es necesario para la adopción"). Es el **TARGET**: GUI gateada por
  [#34](https://github.com/complexluise/bib2graph/issues/34); el código se construye tras 0027 firmado
  (ya) y el caso real validado por un tercero.
- **Fecha:** 2026-06-18
- **Gateado por:** [0027](0027-pivote-posicionamiento-gui-local.md) (pivote de posicionamiento). No se
  baja a `ARCHITECTURE.md` ni se escribe código hasta que 0027 se firme.
- **Enmienda/afecta a:** [0021](0021-cli-agente-native-contrato.md) (el envelope `schema="1"`, la
  jerarquía de errores y el mapeo→exit-code **suben** de `cli/` a una capa de servicios neutral; el CLI
  pasa a ser un adaptador de esa capa — el contrato externo `schema="1"` y los exit codes **no cambian**);
  [0019](0019-concurrencia-diferida.md) (un server de larga vida reintroduce concurrencia; ver
  §Operaciones largas — se mantiene single-writer en v1, no se reabre 0019 todavía).
- **Relacionada con:** [0010](0010-agente-native-columna.md) (CLI columna),
  [0029](0029-workspace-por-investigacion.md) (workspace = unidad que la API abre),
  [0005](0005-dependencias-extras.md) (extras + núcleo liviano — nuevo extra `[gui]`).
- **Epic:** GUI local [#34](https://github.com/complexluise/bib2graph/issues/34).

## Contexto

La [Nota 12](../Notas/12-arquitectura-gui-encuadre.md) (revisada 2026-06-18) encuadró la arquitectura:
la GUI agrega un **4º frontend (SPA)** y una **costura nueva de servidor (API local)**, sin romper
"núcleo puro + costuras". El principio es **no tener dos implementaciones de la lógica de negocio**: CLI
y API deben compartir la orquestación.

El encuadre original (2026-06-16) decía que los tres frontends **"convergen en `run_<cmd>`"** (en
`cli/commands/`). Al leer el código (esta sesión) se vio que **esa capa de convergencia no existe como
tal**:

- `run_<cmd>(store_path, …) -> dict` devuelve **solo el payload `data`** y lanza **excepciones tipadas**
  (`B2GError` con `exit_code`/`code`). Eso sí es reusable.
- Pero **el contrato del envelope `schema="1"`, la jerarquía de errores y el mapeo→exit-code viven en
  `cli/`** (`_envelope.py`/`_errors.py`), junto con el I/O (`print`, `sys.exit`, `stderr`).

Hacer "converger en `run_<cmd>`" forzaría a la API a **importar de `cli/`** (y `cli` deja de ser hoja,
queda atada al otro frontend) o a **reimplementar el contrato** — drift que **ya empezó**: el prototipo
`app/server/errors.py` tiene su propio `envelope()` duplicado. Además, el contrato que la SPA necesita
**no mapea 1:1 a subcomandos** (p. ej. `scent` de un paper, `network` por `(round, kind)`, `search`
**no tienen subcomando** hoy): la convergencia debe ser en **servicios**, no en **comandos**.

## Decisión

**Invertir la dependencia (ports & adapters): una capa de servicios neutral de la que CLI y API son
adaptadores delgados.**

### 1. Capa de servicios neutral — `src/bib2graph/service/`

Agnóstica de transporte: **sin `print`, `sys.exit`, Click ni FastAPI**. Contiene:

- **La orquestación** (lo que hoy es `run_<cmd>`): operaciones de escritura/lazo (`seed`, `chain`,
  `filter`, `build`, `enrich`, `curate`, `snapshot`, …) y **funciones de lectura** que el CLI nunca
  expuso (`get_scent`, `get_network(round, kind)`, `search_papers`, …) que la SPA sí necesita.
- **El contrato**, subido desde `cli/`: el envelope `schema="1"` (`build_envelope`), la jerarquía de
  errores tipados (`B2GError` y subclases) y el **mapeo error→código** (hoy en `handle_errors`).

### 2. CLI y API = adaptadores

- **CLI** (`cli/`): Click + `emit`/`emit_human` (I/O) + `sys.exit`. Llama a `service/`, formatea el
  envelope para stdout y traduce el código a `exit code`. El contrato externo (envelope `schema="1"`,
  exit codes 0–5, ADR 0021) **no cambia**.
- **API** (`src/bib2graph/api/`, **costura opt-in**): FastAPI delgado que llama a `service/`, reusa el
  **mismo** envelope y traduce el código a **HTTP status**. Bind `127.0.0.1` + **token efímero**
  (C.3 de Nota 12). Import perezoso; el núcleo no importa `fastapi`.

### 3. `b2g gui` — nuevo subcomando (18º)

Levanta uvicorn sobre la API + sirve los assets pre-build del frontend + abre el browser. Es el
adaptador de "arranque local" de la GUI.

### 4. Frontend — `frontend/` (monorepo)

SPA (Vite/TS) en `frontend/`; su build se **vendorea** a `src/bib2graph/gui/static/` y **va al wheel**
(la GUI funciona sin Node instalado, B.1). El prototipo `app/src/` es **throwaway** (referencia UX); su
cliente TS (`src/client/`) es la semilla del cliente real contra el contrato.

### 5. Empaquetado y extras

- **Extra `[gui]`** = `fastapi` + `uvicorn` (ADR 0005), import perezoso. Cierra la deuda actual
  (instalados a mano, no declarados).
- **El wheel incluye el frontend buildeado** → `b2g gui` funciona sin Node.
- **Job de CI de frontend** (lint/test/build JS) + build del frontend en el release (B.3).

### 6. Operaciones largas y lock (v1)

`seed`/`enrich`/`build` bloquean (red, Louvain) y el store es **single-writer** (ADR 0019). En v1:
**ejecución síncrona** + **lock global serializado** en la API (una operación de escritura a la vez).
**Jobs async/SSE de progreso y reabrir la concurrencia (0019) quedan diferidos** — se evalúan si la UX
lo exige, no antes.

### 7. Mapeo código→HTTP

El código del contrato (0–5) se traduce a HTTP en el adaptador API: `0`→200; `1` (uso)→400; `2`
(datos)→422; `3` (dependencia)→501; `4` (red)→502; `5` (store bloqueado/corrupto)→409/503. El envelope
viaja **igual** en el body (la SPA lee `error.code`, no depende del status).

## Consecuencias

- (+) **Una sola verdad de orquestación y de contrato.** CLI y API comparten `service/`; se elimina el
  drift del envelope (no más `app/server/errors.py` duplicado).
- (+) **`cli` vuelve a ser hoja:** ya no es importado por la API; ambos dependen de `service/`.
- (+) **La SPA obtiene la lectura que necesita** (`scent`/`network`/`search`) sin forzar subcomandos
  artificiales ni granularidad imperativa de CLI (riesgo de producto de Nota 12, punto 2).
- (+) **Empaquetado simple para el usuario semi-técnico** (0027): `uv sync --extra gui` + `b2g gui`,
  sin Node.
- (−) **Refactor de fondo:** subir el contrato (envelope/errores/mapeo) de `cli/` a `service/` y
  re-cablear los subcomandos como adaptadores. Toca muchos archivos y sus tests (aunque el contrato
  externo no cambie). Es el costo central de hacerlo bien ahora en vez de tarde.
- (−) **Nueva superficie:** `service/`, `api/`, `gui/static/`, `frontend/` + el subcomando `b2g gui`,
  todos a construir y testear.
- (−) **CI más pesado:** job JS nuevo + build del frontend en el release (B.3).
- (−) **Mapeo código→HTTP a mantener** y **lock global** que serializa escrituras (latencia aceptada en
  v1; jobs async si molesta).
- (−) **Versionado:** el envelope `schema="1"` es compartido, pero los **payloads** de CLI (agente-native,
  ADR 0021) y de la SPA pueden evolucionar a ritmos distintos; se versiona el payload por endpoint si
  divergen, manteniendo el envelope estable.
