# 0032 — La capa de servicios es dueña del loop bibliográfico completo (extiende 0028)

- **Estado:** Propuesta
- **Fecha:** 2026-06-18
- **Extiende a:** [0028](0028-arquitectura-gui-api-capa-servicios.md) (capa de servicios neutral +
  adaptadores). 0028 subió a `service/` el **contrato** (envelope/errores/mapeo) + **6 lecturas** +
  **curación**; este ADR amplía el alcance de `service/` al **loop bibliográfico entero**.
- **Relacionada con:** [0010](0010-agente-native-columna.md)/[0021](0021-cli-agente-native-contrato.md)
  (CLI = adaptador), [0027](0027-pivote-posicionamiento-gui-local.md)/
  [0033](0033-producto-library-centric-grafo-proyeccion.md) (posicionamiento library-centric),
  [0035](0035-ingesta-multipuerta-resolucion-doi.md) (ingesta multi-puerta + resolución DOI→ID son
  operaciones de servicio).
- **Encuadre:** [Nota 18](../Notas/18-flujo-canonico-biblioteca.md) (flujo canónico paso a paso).
- **Epic:** GUI local [#34](https://github.com/complexluise/bib2graph/issues/34) (iterada post-MVP).

## Contexto

El ADR 0028 invirtió la dependencia (ports & adapters): CLI y API son adaptadores delgados de una
**capa de servicios neutral** `src/bib2graph/service/`. Pero el alcance que 0028 subió fue acotado: el
**contrato** (envelope `schema="1"`, `B2GError`, `code_for`), las **6 lecturas** de la SPA
(`service/reads.py`) y la **curación** (`service/curate.py`). El **resto de la orquestación**
—ingesta (`run_seed`/`run_seed_from_bib`), forrajeo (`run_chain`), enriquecimiento (`run_enrich`),
construcción de redes (`run_build`/`run_networks`), snapshot (`run_snapshot`)— **sigue viviendo en
`cli/commands/`**. El propio `ARCHITECTURE.md` lo marca: *"La migración del resto de la orquestación
`run_<cmd>` sigue TARGET."*

El reencuadre library-centric (Notas 16/17, ADR 0033) exige que la **GUI ejerza el loop bibliográfico
completo** (ingestar → buscar → etiquetar → curar → forrajear → proyectar), no solo leer y curar. Con
la orquestación a medio subir, cada operación nueva que la API/GUI necesita obliga a elegir entre
**importar de `cli/`** (rompe la hoja) o **reimplementar** (drift) — exactamente el problema que 0028
resolvió para el contrato, pero todavía abierto para la orquestación de escritura/lazo.

## Decisión

**La capa de servicios `src/bib2graph/service/` es la dueña ÚNICA del loop bibliográfico completo.**
Toda operación de dominio (ingesta por ambas puertas, resolución DOI→OpenAlex ID, enriquecimiento,
dedup ya automático, curación, etiquetado, forrajeo, proyección a redes, snapshot/diff) vive en
`service/` como **operación neutral de transporte** (sin `print`, `sys.exit`, Click ni FastAPI). CLI,
API y GUI son **adaptadores finos sobre la misma operación**.

1. **Migración de la orquestación restante a `service/`.** Las funciones `run_<cmd>` de
   `cli/commands/` que contienen lógica de dominio se mueven a módulos de `service/`
   (`service.ingest`, `service.forage`, `service.enrich`, `service.networks`, `service.snapshot`,
   `service.tags`, `service.resolve`, `service.reads.search_papers`). El módulo `cli/commands/<cmd>.py`
   queda como **adaptador**: parsea Click, resuelve workspace, llama al servicio, formatea el envelope.
   El patrón ya probado en G3 (`run_accept`/`run_reject` son shims que delegan a `service.curate`) se
   generaliza.

2. **Sin cambio de contrato externo.** El envelope `schema="1"`, los exit codes (0–5) y el mapeo
   código→HTTP **no cambian**. Los payloads `data` de cada operación se preservan (los tests de
   contrato `--json` los guardan).

3. **Migración POR DEMANDA, no big-bang.** El orden lo fija el ROADMAP, guiado por lo que la iterada
   GUI necesita primero: **ingesta de archivo + resolución DOI** (Puerta B, ADR 0035), **`search_papers`**
   (vista de Biblioteca), **`tags`** (ADR 0034), **`build`/`get_network`** (grafo). Las operaciones que
   hoy solo usa el CLI (`validate`, `inspect`) se difieren sin romper coherencia: el TARGET es claro,
   la secuencia es incremental. **No se bloquea la GUI esperando un refactor total.**

4. **Lecturas nuevas que el CLI nunca expuso** (`search_papers`, `papers_by_tag`) viven en `service/`
   aunque **no tengan subcomando CLI**. La convergencia es en **servicios**, no en **comandos** (mismo
   principio que 0028 §Contexto). Exponerlas como subcomando CLI es opcional/diferido (sub-fork del PO,
   Nota 18 §2).

## Consecuencias

- (+) **Una sola verdad de orquestación de extremo a extremo.** La GUI ejerce el loop completo sin que
  `api/` importe de `cli/` ni reimplemente lógica. Cierra el TARGET pendiente de 0028.
- (+) **`cli/` vuelve a ser hoja de verdad** (hoy es hoja para el contrato pero aún dueño de la
  orquestación de escritura). Todos los frontends cuelgan de `service/`.
- (+) **La iterada GUI agrega vistas, no lógica duplicada:** ingesta/búsqueda/tags/proyección son
  operaciones de servicio reusadas por CLI y GUI.
- (−) **Refactor amplio** (toca casi todos los `cli/commands/` y sus tests). Mitigado por: las
  `run_<cmd>` ya están aisladas del I/O; el contrato externo no cambia; la migración es por demanda.
- (−) **Riesgo de over-engineering si se hace big-bang.** Por eso la decisión 3 (por demanda): se sube
  lo que la GUI consume; lo demás espera evidencia de necesidad.
- (−) **Doble residencia temporal:** durante la migración incremental, algunas operaciones viven en
  `service/` y otras en `cli/commands/`. Aceptable y acotado por el ROADMAP; el shim-que-delega
  mantiene el contrato estable mientras tanto.
