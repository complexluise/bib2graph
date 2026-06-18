# 12 — Encuadre de arquitectura: bajar la GUI (`b2g gui`) a ARCHITECTURE/PRD

> ⚠️ **NOTA DE ENCUADRE — decisiones PROPUESTAS, pendientes de firma del PO.** No es ADR ni diseño
> as-built. Captura el encuadre del architect para bajar la dirección de la GUI (Notas
> [07](07-frontend-tool-for-thought.md)/[08](08-referentes-frontend.md)/[10](10-sintesis-contextualizacion-gui.md))
> a la arquitectura, el PRD y la gestión de docs, y destapar las decisiones A–G. Fecha: 2026-06-16.
> Nada se implementa: la GUI sigue gateada (epic **#34**: núcleo → caso real → GUI).

---

## ⟳ Revisión 2026-06-18 (perspectiva actual)

> El cuerpo de abajo (2026-06-16) **se conserva como historia**. Este bloque actualiza el encuadre
> a la luz de tres cosas que pasaron *después* de escribirlo: (1) el **workspace se construyó** (ADR
> 0029, #32 cerrado); (2) apareció un **prototipo `app/`** (frontend mock desechable + un embrión de
> server FastAPI); y (3) al leer el código real (esta sesión) descubrimos **dónde vive de verdad la
> capa de convergencia**. Los cambios:

**1. La idea central se corrige: la convergencia es una CAPA DE SERVICIOS NEUTRAL, no `run_<cmd>` en
`cli/`.** El diagrama original ("los tres frontends convergen en `run_<cmd>` en `cli/commands/`")
subestima dónde está el contrato. Hoy `run_<cmd>(store_path, …)` devuelve **solo el payload `data`**;
el **envelope `schema="1"`, la jerarquía de errores tipados (`B2GError`) y el mapeo→exit-code viven en
`cli/`** (`_envelope.py`/`_errors.py`). Hacer "converger en `run_<cmd>`" forzaría a la API a importar
de `cli/` (y `cli` deja de ser hoja) o a **reimplementar el contrato** — drift que **ya empezó**
(`app/server/errors.py` tiene su propio `envelope()`). → La forma correcta es **invertir la
dependencia (ports & adapters)**: una capa neutral `src/bib2graph/service/` (agnóstica de transporte:
sin `print`, `sys.exit`, Click ni FastAPI) que contiene la orquestación (lo que hoy es `run_<cmd>`)
**+ el contrato (envelope, errores, mapeo a código), subido desde `cli/`**. **CLI y API son ambos
adaptadores delgados** que se cuelgan de los servicios y comparten todo lo que puedan. *(Acordado con
el PO 2026-06-18.)*

**2. El contrato de la SPA NO mapea 1:1 a subcomandos** (hallazgo del mock `app/src/mock/api.ts`):
`getScent(paperId)`, `getNetwork(roundId, kind)`, `searchPapers(...)` **no tienen subcomando CLI** (el
scent vive embebido en el grafo; search no existe). La capa de servicios debe exponer funciones de
**lectura** que el CLI nunca tuvo → otra razón por la que la convergencia va en *servicios*, no en
*comandos*. Cuidado de producto: si la API es un proxy fino de subcomandos, la GUI hereda granularidad
imperativa de CLI en vez del modelo "estado de la investigación" (Nota 07).

**3. Operaciones largas + lock single-writer (nuevo, para el ADR 0028):** `seed`/`enrich`/`build`
bloquean (red, Louvain) y `run_<cmd>` abre/cierra el store por llamada. Un server de larga vida
reintroduce la **concurrencia que el CLI nunca tuvo** (ADR 0019 la difirió) y el bloqueo HTTP es mala
UX. **Reco (pendiente de firma):** v1 **síncrono** + **lock global serializado**; **jobs async/SSE y
reabrir 0019 = diferidos**.

**4. El prototipo `app/` (no existía en el original).** `app/src/` = frontend React/Vite con mock
Zustand, **desechable** (referencia UX). `app/server/` = FastAPI standalone, solo `GET /api/workspace`,
envelope propio. **Destino:** el frontend es throwaway hasta `frontend/`; la API se **promueve** a
`src/bib2graph/api/` colgada de la capa de servicios; `app/server/errors.py` se retira a favor del
contrato neutral; el `src/client/` TS es la semilla del cliente real contra el contrato.

**5. Estado de las decisiones A–G hoy:**
- **A/B/C — vigentes, con el ajuste del punto 1.** C.2 se reformula: CLI y API son hermanos sobre la
  **capa de servicios neutral**, no sobre `run_<cmd>`. El árbol de repo suma `src/bib2graph/service/`.
- **D (docs) — vigente.**
- **E (workspace) — ✅ HECHA, ya no es propuesta:** ADR 0029 firmado, workspace construido, #32 cerrado.
- **F (posicionamiento) — vigente.**
- **G (ADRs) — renumerar:** **0029 ya es el workspace** (hecho), **0030** = ecuación declarativa.
  Quedan por escribir **0027 (pivote de posicionamiento, gatea)** y **0028 (arquitectura
  GUI/API/frontend + empaquetado + LA CAPA DE SERVICIOS del punto 1)**. La terna original "0027/0028/
  0029" ya no aplica para 0029.

**6. Drift numérico actualizado:** el CLI hoy tiene **17 subcomandos** (no 13) → `b2g gui` sería el
**18º** (no el 14º). Además (PO 2026-06-17, posterior a la nota): **Hito 10 (viz) absorbido en la GUI**
(es la capa de lectura visual) y **Hito 11 (Zotero/Neo4j) descartado** — no hay extra `[viz]` aparte.

---

## Idea central

La GUI **no rompe** la arquitectura "núcleo puro + costuras". Agrega un **4º frontend (la SPA)** y
una **costura nueva de servidor (API local)**. Los **tres frontends — CLI · API · SPA — convergen
en la misma capa `run_<cmd>`** (en `cli/commands/`), no en la API. El CLI sigue standalone
agente-native (ADR 0010); la API es **par** del CLI, no superior.

> ⟳ **Revisado 2026-06-18 (ver bloque arriba):** la convergencia **no** es en `run_<cmd>` (que solo
> devuelve el payload) sino en una **capa de servicios neutral** `src/bib2graph/service/` que también
> absorbe el contrato (envelope/errores/exit-code) hoy atrapado en `cli/`. CLI y API son **adaptadores**
> de esa capa.

```
   SPA (JS, grafo-lienzo) ──HTTP/JSON──► API local (FastAPI, 127.0.0.1, opt-in [gui])
   CLI b2g (Click) ───────────────────────────────┐         │
                                                   ▼         ▼
                              capa run_<cmd>(store_path, …)  + envelope schema="1"
                                                   ▼
                              NÚCLEO PURO (corpus, cycle, projectors, analyzer) + costuras
```

Dónde encaja en `ARCHITECTURE.md` (marcado **TARGET**): §1 (tres costuras de frontera) · §2
(diagrama: caja CLI·API·SPA → `run_<cmd>`) · nueva **§4.4 `LocalApiServer`** (HTTP/JSON delgado que
reusa el envelope; bind `127.0.0.1`; import perezoso) · §6.3 (reencuadrar a "frontends de frontera";
`b2g gui` = 14º subcomando) · §7 (extra `[gui]`) · §4.3 (workspace, ver E).

## Estructura de repo propuesta (monorepo Python + JS)

```
bib2graph/
├─ src/bib2graph/
│  ├─ cli/                 # YA: run_<cmd> + envelope (punto de convergencia)
│  ├─ api/                 # NUEVA costura (opt-in [gui]): FastAPI, routers→run_<cmd>, _security
│  ├─ gui/static/          # assets PRE-BUILDEADOS del frontend (van al wheel)
│  └─ cli/commands/gui.py  # b2g gui: uvicorn + sirve static + abre browser
├─ frontend/               # SPA (package.json/Vite); build → src/bib2graph/gui/static/ ; NO va al wheel
├─ docs/ … └─ tests/
```

## Plan de gestión de documentación

Separar por **audiencia** (una pregunta = un doc):
- **`docs/user/`** (NUEVO) — guía de tarea, tono no-arquitecto: instalar, flujo GUI, recetas CLI. *"¿cómo lo uso?"*
- **dev** — `ARCHITECTURE.md`, `PRD.md`. *"¿por qué así / cuál es el contrato?"*
- **`docs/reference/`** (NUEVO) — mover `API.md` ahí; **generar la referencia CLI desde `--help`** (frena el bloat). *"¿qué hace cada cosa?"*
- `decisiones/` (ADRs, "¿por qué se decidió X?"), `ROADMAP/` (plan), GitHub Issues (trabajo, ver Nota 11).

**Sitio de docs (mkdocs/Sphinx):** *todavía no.* Gatillo = publicar a PyPI **o** `docs/user/` > ~6-8
páginas. Antes es overhead; markdown del repo renderiza en GitHub y lo lee el agente.

## Decisiones A–G (PROPUESTAS — recomendación del architect, pendientes de firma)

- **A — Repo:** A.1 API como costura propia `src/bib2graph/api/` · A.2 SPA en `frontend/` **monorepo**
  (vendorear build a `gui/static/`) · A.3 `b2g gui` levanta uvicorn + sirve assets pre-build. *(💰 A.2: CI necesita job JS.)*
- **B — Empaquetado:** B.1 **el wheel incluye el frontend buildeado** (funciona sin Node) · B.2 `[gui]`
  = `fastapi`+`uvicorn`, import perezoso · B.3 **job de CI de frontend** + build JS en el release. *(💰 B.1/B.3: build JS en release + CI nuevo.)*
- **C — API:** C.1 HTTP/JSON **delgada que reusa el envelope `schema="1"`** · C.2 CLI y API **hermanos**
  sobre `run_<cmd>` (el CLI NO pasa por la API) · C.3 bind `127.0.0.1` + **token efímero**.
- **D — Docs:** adoptar la separación user/dev/reference; crear `docs/user/` solo cuando arranque la
  GUI; sin sitio aún; referencia CLI desde `--help`.
- **E — Persistencia (💰 modelo de datos):** adoptar **workspace por investigación** (carpeta =
  `library.duckdb` + `networks/` + snapshots/exports) **antes** de la GUI; **ADR que enmienda 0009/0019**
  (single-writer sigue válido; la unidad pasa a ser la carpeta). Issue #32.
- **F — Posicionamiento (💰 PRD):** enmendar PRD §3 (línea 125) y §5.2 (línea 223) como **bloque
  fechado**: entra GUI local opt-in para semi-técnicos (gateada #34); CLI sigue columna;
  hosting/MCP/Claude-Web **siguen fuera**. Requiere ADR 0027.
- **G — ADRs:** **tres** — **0027** pivote de posicionamiento (gatea) · **0028** arquitectura
  GUI/API/frontend + empaquetado (A/B/C) · **0029** workspace (E, enmienda 0009/0019). Nacen en estado
  **Propuesta**; 0027 primero. (D no necesita ADR: es organización de docs.)

## Drift detectado (para la sincronía posterior)

- PRD §3:125 y §5.2:223 ("sin GUI / fuera") contradicen la dirección → enmienda + ADR 0027.
- `ARCHITECTURE.md` §6.3 dice "13 subcomandos"; con `b2g gui` pasan a **14** (actualizar al sincronizar).
- Workspace ya en backlog (`ROADMAP/04-lo-que-viene.md`) → promover a ADR 0029.

## Estado y próximo paso

**Pendiente: firma del PO sobre A–G.** Con la firma: el architect redacta los borradores de **ADR
0027/0028/0029** (estado *Propuesta*), baja el **TARGET** a `ARCHITECTURE.md`/`PRD.md` y crea el
esqueleto de `docs/user/` **cuando** arranque la GUI. **Sin tocar código** (GUI gateada por #34).

> ✅ **FIRMADO 2026-06-18.** El PO aceptó A–G con el ajuste del bloque de revisión (la convergencia es
> la **capa de servicios neutral**, no `run_<cmd>`): *"de acuerdo con el plan; acepto que es más
> superficie, pero es necesario para la adopción"*. **ADR [0027](../decisiones/0027-pivote-posicionamiento-gui-local.md)
> y [0028](../decisiones/0028-arquitectura-gui-api-capa-servicios.md) → Aceptada.** E (workspace) ya era
> AS-BUILT (ADR 0029). **Resta** bajar el TARGET a `PRD.md` §3/§5.2 y `ARCHITECTURE.md` (§1, §2, nueva
> §4.4, §6.3, §7). Sigue **sin tocar código** (GUI gateada por #34).
