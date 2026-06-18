# ROADMAP · GUI local (Hitos G1–G5) — **TARGET, gateado por #34**

> ← Volver al [índice del ROADMAP](README.md)

---

> ⚠️ **TARGET, NO as-built.** Toda esta epic es la **GUI local "tool for thought"**
> ([#34](https://github.com/complexluise/bib2graph/issues/34)), encuadrada por los ADR
> [0027](../decisiones/0027-pivote-posicionamiento-gui-local.md) (pivote de posicionamiento,
> Aceptada 2026-06-18) y [0028](../decisiones/0028-arquitectura-gui-api-capa-servicios.md)
> (arquitectura: capa de servicios neutral + adaptadores, Aceptada 2026-06-18) y la
> [Nota 12](../Notas/12-arquitectura-gui-encuadre.md) (revisión 2026-06-18). Fecha del plan: 2026-06-18.
>
> **El gate de éxito/descarte ([#34](https://github.com/complexluise/bib2graph/issues/34)) va AL
> FINAL, no antes:** un **tercero** (tesista/docente distinto del autor) usa la GUI **sin ayuda**
> para reproducir/curar el caso `examples/valoraciones/`. Si no lo logra, la dirección de la GUI se
> **revisa** antes de promoverla a oficial (ADR 0027 §Gate). El roadmap construye el vertical mínimo
> **hacia** ese gate; los ADR de arquitectura ya están firmados, así que **G1 puede empezar ahora**
> (no espera al gate; el gate valida el producto terminado).

> **Diferencia con los tramos 01–04.** Aquellos son **as-built** (hitos construidos). Este es un
> **plan a futuro**: el alcance, la secuencia y las bifurcaciones para el PO. Las cifras de tests son
> **objetivos "los justos"**, no snapshots — la cuenta autoritativa la sigue dando el CI
> (ver README §Disciplina de tests).

## Principio rector (de ADR 0028)

**Una sola verdad de orquestación y de contrato.** CLI y API son **adaptadores delgados** de una
**capa de servicios neutral** `src/bib2graph/service/` (sin `print`, `sys.exit`, Click ni FastAPI).
El contrato externo del CLI —envelope `schema="1"`, jerarquía `B2GError`, exit codes 0–5
(ADR [0021](../decisiones/0021-cli-agente-native-contrato.md))— **NO cambia** en ningún hito de esta
epic. Cada hito mantiene el gate verde (`ruff`/`mypy`/`pytest`) **sin tocar los tests del CLI**.

El prototipo `app/` (frontend React mock + server FastAPI embrión) es **referencia UX desechable**,
**no** se porta: el `frontend/` de G4 nace nuevo y su cliente TS se siembra del contrato real.

---

## Hito G1 — Capa de servicios neutral + contrato subido; CLI = adaptador

**Alcance**

- Crear `src/bib2graph/service/` y **subir el contrato** que hoy vive en `cli/`: el envelope
  `schema="1"` (`build_envelope`/`ENVELOPE_SCHEMA_VERSION`, hoy `cli/_envelope.py`), la **jerarquía
  de errores tipados** (`B2GError` + subclases, hoy `cli/_errors.py`) y el **mapeo error→código**
  (hoy embebido en `handle_errors`). La capa es **agnóstica de transporte**.
- `cli/_envelope.py` y `cli/_errors.py` pasan a **re-exportar** desde `service/` (no se borran): los
  imports existentes del CLI y de los tests (`from bib2graph.cli._errors import DataError`,
  `from bib2graph.cli._envelope import build_envelope`) **siguen funcionando idénticos**. La parte de
  **I/O** del CLI (`emit`/`emit_human`/`print`/`sys.exit` y el decorador `handle_errors` que llama a
  `sys.exit`) **se queda en `cli/`** — eso es lo propio del adaptador.
- Establecer el **patrón de servicio** (cómo se expone una operación de orquestación, agnóstica de
  transporte, devolviendo `data: dict` o lanzando `B2GError`) **sin** mover de golpe las 18+ funciones
  `run_<cmd>`. G1 fija la capa y el contrato; la migración de la orquestación es **incremental**
  (G2 y posteriores), coherente con el end-state del ADR 0028 (CLI y API ambos adaptadores).

**Historias (PRD §7):** ninguna directa de usuario. Es **infraestructura** que habilita **E2**
(contrato agente-native, ahora compartible por la API) y **desbloquea** toda la épica D vía la API
(G2/G3). Cierra el drift ya iniciado (`app/server/errors.py` con su `envelope()` duplicado).

**Criterios de aceptación (DoD)**

- Existe `src/bib2graph/service/` con el envelope, los errores y el mapeo error→código, **sin
  importar** `click`, `fastapi`, ni hacer `print`/`sys.exit`.
- `cli/_envelope.py` y `cli/_errors.py` **re-exportan** desde `service/`; `from bib2graph.cli._errors
  import B2GError, DataError, …` y `from bib2graph.cli._envelope import build_envelope,
  ENVELOPE_SCHEMA_VERSION` resuelven a los **mismos** objetos.
- **El contrato externo es idéntico:** mismo envelope (`schema="1"`, mismas claves), mismos exit codes
  0–5 para los mismos errores. **Los tests del CLI pasan SIN modificarse** (`tests/unit/test_cli.py`
  es la red de seguridad — ver abajo).
- `cli` vuelve a no depender de ningún otro frontend; `service/` no importa `cli/`.
- Gate verde completo (`ruff check . && ruff format --check . && mypy src && pytest`).

**Tests (TDD — los justos)**

- **`tests/unit/test_cli.py` no se toca** y queda verde: es la prueba de que el contrato externo no
  driftó (ya cubre forma del envelope —líneas ~150/172— y los exit codes 1/2/3/5 —líneas
  ~363/378/405/531—). Es la **red de seguridad** del refactor.
- **1–2 tests nuevos de `service/`** (los justos): que `service.build_envelope(...)` produce el
  envelope canónico `schema="1"` y que el **mapeo error→código** devuelve 0–5 para cada subclase de
  `B2GError` (camino feliz + 1 falla por código). No re-testear lo que `test_cli.py` ya cubre vía
  re-export.

**Se vuelve posible:** que la API (G3) reuse el **mismo** contrato sin importar `cli/` ni
reimplementarlo, y que las lecturas de servicio (G2) cuelguen de una capa neutral.

---

## Hito G2 — Lecturas de servicio que el CLI no expone

**Alcance**

- Exponer en `service/` **funciones de lectura** que la SPA necesita y que el CLI **nunca tuvo como
  subcomando** (hallazgo de Nota 12 punto 2 sobre el mock `app/src/mock/api.ts`): scent de un paper,
  `network(round, kind)`, listado de rondas, **diff entre rondas** (el "git de la investigación", el
  diferenciador de ADR 0027) y `paper(id)`. La convergencia es en **servicios**, no en subcomandos
  artificiales.
- Estas lecturas son **read-only sobre el workspace** (ADR 0029): abren el store, leen, no transicionan
  el `CycleState` ni mutan el corpus. Son la materia prima de la lectura visual de la GUI.
- Migrar **incrementalmente** la orquestación de algunos `run_<cmd>` de lectura a `service/` cuando
  comparten lógica con estas funciones (p. ej. la lectura que hoy hace `run_status`/`run_inspect`),
  re-exportando desde `cli/commands/` para no romper imports — primer paso real del end-state 0028.

**Historias (PRD §7):** habilita la **épica D (lectura visual)** vía API/SPA — **D1** (las cinco
proyecciones leídas por `(round, kind)`), **D2** (métricas/comunidades servidas), **D3**
(composición/asortatividad por comunidad, ya calculadas por los proyectores). Habilita **E1**
(comparar snapshots/rondas = diff de rondas). El scent sirve **B3** (ranking por estructura) en la GUI.

**Criterios de aceptación (DoD)**

- `service/` expone lecturas para: scent de un paper, `network(round, kind)`, rondas, diff de rondas,
  paper por id. Cada una devuelve `data: dict` serializable (o lanza `B2GError` tipado).
- **Sin red, sin mutación, sin transición de ciclo.** Determinismo coherente con R2 (mismo corpus →
  misma lectura).
- El CLI no regresiona (sus tests siguen verdes); lo migrado se re-exporta.

**Tests (TDD — los justos)**

- Una lectura representativa contra un corpus sintético chico: `network(round, kind)` devuelve los
  nodos/aristas esperados; **diff de rondas** sobre dos rondas conocidas devuelve el delta correcto
  (alto valor: es el diferenciador). No testear cada getter.

**Se vuelve posible:** que la API (G3) sirva la lectura visual sin forzar granularidad imperativa de
CLI (riesgo de producto de Nota 12).

---

## Hito G3 — API local (FastAPI) + extra `[gui]` + subcomando `b2g gui` (19º)

**Alcance**

- `src/bib2graph/api/` (**costura opt-in**): FastAPI **delgado** que llama a `service/`, **reusa el
  mismo envelope** y traduce el código del contrato a **HTTP status** (mapeo ADR 0028 §7:
  `0`→200, `1`→400, `2`→422, `3`→501, `4`→502, `5`→409/503; el envelope viaja igual en el body, la SPA
  lee `error.code`). Bind **`127.0.0.1`** + **token efímero** (Nota 12 C.3). **Import perezoso**: el
  núcleo no importa `fastapi`.
- **Operaciones largas (v1, ADR 0028 §6):** ejecución **síncrona** + **lock global serializado** (una
  escritura a la vez; mantiene single-writer de ADR 0019). Jobs async/SSE de progreso **diferidos**.
- **Extra `[gui]`** = `fastapi` + `uvicorn` (ADR 0005), cierra la deuda de instalarlos a mano.
- **Subcomando `b2g gui` (19º)** (`cli/commands/gui.py`): levanta uvicorn sobre la API, sirve los
  assets pre-build del frontend (de G4), abre el browser. Es el adaptador de "arranque local".
- Retirar `app/server/errors.py` (su `envelope()` duplicado) a favor del contrato neutral de G1.

**Historias (PRD §7):** **E2** extendida (el contrato agente-native ahora también por HTTP, no solo
CLI). Es el transporte que habilita toda la épica D en la SPA (G4).

**Criterios de aceptación (DoD)**

- `uv sync --extra gui` instala `fastapi`+`uvicorn`; sin el extra, importar el núcleo **no** falla
  (import perezoso) y `b2g gui` da error accionable **exit 3** (dependencia faltante) — coherente con
  el contrato.
- La API bindea **solo** `127.0.0.1`, exige el **token efímero**, serializa escrituras con el **lock
  global**, y **reusa** `service.build_envelope` (no reimplementa el envelope).
- El mapeo código→HTTP es el de ADR 0028 §7; el body lleva el envelope `schema="1"` íntegro.
- `b2g gui` arranca la API y sirve los static; el **20º+** y demás contratos CLI no regresionan.

**Tests (TDD — los justos)**

- El mapeo **código→HTTP** (un caso por código 0–5; alto valor, es contrato nuevo) con la API en
  modo test (sin red real, store sintético).
- Que la API **rechaza** sin token y **acepta** con token (1 test de seguridad).
- *No testear* uvicorn/el browser de `b2g gui` (plumbing); sí la **función** que arma la app.

**Se vuelve posible:** que la SPA hable HTTP/JSON con el workspace local reusando el contrato.

---

## Hito G4 — Frontend nuevo (`frontend/`) contra la API real

**Alcance**

- **SPA NUEVA** (Vite/TS) en `frontend/` (monorepo Python+JS). **NO se porta** `app/src/` (mock
  desechable): se construye de cero, **alta calidad de diseño** (Notas
  [07](../Notas/07-frontend-tool-for-thought.md)/[08](../Notas/08-referentes-frontend.md)/[10](../Notas/10-sintesis-contextualizacion-gui.md):
  tool-for-thought no-lineal, UX-first, grafo-lienzo). Su cliente TS se siembra del contrato real
  (envelope `schema="1"`), no del mock.
- **MVP read-only-first:** lectura visual de la estructura (épica D) — proyecciones, comunidades,
  composición, scent — y **diff de rondas** (diferenciador ADR 0027). La **curación** (C4:
  aceptar/rechazar) entra como segunda capa una vez sólida la lectura.
- El build se **vendorea** a `src/bib2graph/gui/static/` (lo sirve `b2g gui`); `frontend/` **no** va al
  wheel (su build sí, en G5). Usar **pnpm**, nunca npm (preferencia firme del PO).

**Historias (PRD §7):** materializa la **épica D completa** como lectura visual (la GUI *es* la capa
de lectura visual — Hito 10 viz absorbido aquí, ROADMAP 04) — **D1/D2/D3** visualizadas, **E1** como
diff de rondas; luego **C4** (aceptar/rechazar/curación) en la GUI, complementando la curación CLI/CSV
(`b2g curate`). **B3** (scent) como guía visual del candidato.

**Criterios de aceptación (DoD)**

- La SPA carga contra la **API real** (no mock), lee `error.code` del envelope, y renderiza al menos:
  una red por `(round, kind)`, comunidades/composición, y el **diff de rondas**.
- Curación (aceptar/rechazar) escribe vía API → `service/` → workspace, **respetando el lock global**
  y sin romper la reproducibilidad (R2).
- Calidad de diseño revisada (no es el mock `app/`): el `app/` puede borrarse o quedar como referencia
  archivada (bifurcación PO, abajo).

**Tests (TDD — los justos)**

- Tests JS **simples** del cliente contra el contrato (forma del envelope, manejo de `error.code`) y
  smoke de los componentes clave (render de una red, del diff). **No** suite E2E pesada en CI todavía.
- *No testear* pixel-perfect ni cada componente; sí el contrato cliente↔API.

**Se vuelve posible:** la lectura visual no-lineal y la curación desde la GUI sobre el workspace local.

---

## Hito G5 — Empaquetado (wheel con frontend buildeado + CI JS)

**Alcance**

- **El wheel incluye el frontend buildeado** en `src/bib2graph/gui/static/` → `b2g gui` funciona **sin
  Node** instalado (ADR 0028 §5, Nota 12 B.1).
- **Job de CI de frontend** (lint/test/build JS con pnpm) + **build del frontend en el release** (B.3).
- Cierra la epic a nivel de empaquetado para el usuario semi-técnico (ADR 0027): `uv sync --extra gui`
  + `b2g gui`, sin tocar Node.

**Historias (PRD §7):** ninguna directa; hace **instalable y distribuible** todo lo anterior (cierra
el canal pip/uv de ADR 0027).

**Criterios de aceptación (DoD)**

- El wheel instalado **sin Node** corre `b2g gui` y sirve la SPA buildeada.
- El CI tiene un job JS (lint/test/build) y el release buildea el frontend antes de empacar.
- `release-please` sigue siendo el publicador (no se bumpea versión ni se edita CHANGELOG a mano).

**Tests (TDD — los justos)**

- Smoke: que el wheel incluye `gui/static/` y que `b2g gui` levanta sin Node (test de empaquetado, no
  E2E del browser).

**Se vuelve posible:** distribuir la GUI a un tercero por pip/uv — **precondición del gate #34**.

---

## Gate #34 — validación con un tercero (criterio éxito/descarte, AL FINAL)

> **No es un hito de construcción:** es el **criterio de aceptación de la epic** (ADR 0027 §Gate). Un
> **tesista/docente distinto del autor** instala (`uv sync --extra gui`), corre `b2g gui` y
> **reproduce/cura `examples/valoraciones/` sin ayuda**. **Éxito** → la GUI se promueve a oficial.
> **Descarte** → se revisa la dirección antes de promoverla (no se da por cumplido aquí). Ver
> [Nota 09](../Notas/09-sesion-qa-prueba-ecologia-valoraciones.md) (sesión QA con tercero) como
> referencia de método.

---

## Idea parqueada (NO es hito) — sugerencias de IA para curación en el CLI

> **Backlog/idea, no planificada.** Asistencia de IA que **sugiera** (no decida) curación en el CLI,
> **marcada explícitamente como sugerencia**. **Tensión con ADR
> [0022](../decisiones/0022-producto-sin-ia-generativa.md)** (el producto no usa IA generativa) y
> **riesgo de sobre-ingeniería**. No es hito ni tiene DoD; se registra para no perderla. Reabrirla
> requeriría un ADR que reconcilie con 0022 y una decisión de producto del PO. El "porqué" de un
> candidato lo da hoy la **estructura visible** (scent bibliométrico, redes), no un LLM.
