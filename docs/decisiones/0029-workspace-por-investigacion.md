# 0029 — Workspace por investigación: carpeta autocontenida + resolución ambiente

- **Estado:** Propuesta (pendiente de firma del PO; **no implementado**)
- **Fecha:** 2026-06-16
- **Enmienda (propuesta por este ADR):** [0009](0009-biblioteca-viva-duckdb.md) y
  [0019](0019-concurrencia-diferida.md) — la **unidad de persistencia** pasa de "1 archivo
  `.duckdb`" a "**1 workspace = 1 carpeta**" (el single-writer sobre el `.duckdb` sigue válido);
  [0021](0021-cli-agente-native-contrato.md) §E — `--store` deja de ser opción global
  **obligatoria** y pasa a **opcional** vía resolución ambiente.
- **Relacionada con:** [0016](0016-maquina-estados-lazo.md) (una investigación = una unidad de
  persistencia; el `CycleState`/loop-state vive en el `.duckdb`),
  [0017](0017-reproducibilidad-historia-snapshot.md) (el **snapshot** sigue siendo lo reproducible;
  redes/exports = cache regenerable), [0010](0010-agente-native-columna.md) (CLI agente-native).
- **Prerequisito de:** epic GUI [#34](https://github.com/complexluise/bib2graph/issues/34) (la GUI
  necesita una unidad de proyecto portable y abrible).
- **Issues:** [#32](https://github.com/complexluise/bib2graph/issues/32) (modelo workspace),
  [#38](https://github.com/complexluise/bib2graph/issues/38) (`b2g init`),
  [#39](https://github.com/complexluise/bib2graph/issues/39) (resolución ambiente).

## Contexto

Hoy la unidad de persistencia es **un archivo `.duckdb`** suelto: "una investigación = un archivo"
(ADR [0009](0009-biblioteca-viva-duckdb.md) / [0019](0019-concurrencia-diferida.md) /
[0016](0016-maquina-estados-lazo.md)). El estado del lazo, el corpus, la procedencia y las
decisiones de curación viven dentro de ese archivo. El CLI lo recibe con la opción global
**obligatoria** `--store <archivo.duckdb>` (ADR [0021](0021-cli-agente-native-contrato.md) §E).

Ese modelo ya **derivó de hecho** hacia una carpeta: `b2g build` **no** escribe solo el `.duckdb`,
sino que materializa los artefactos de red en **`<store_dir>/networks/<kind>/network.graphml` +
`metrics.json`** (ADR 0021 §B). Es decir, alrededor del `.duckdb` ya nace una carpeta con
subproductos — una **convención emergente sin nombre ni contrato**. A esto se suman tres tensiones:

1. **Portabilidad / GUI.** El epic GUI ([#34](https://github.com/complexluise/bib2graph/issues/34))
   necesita "abrir una investigación" como una unidad: db + redes + snapshots + exports juntos y
   movibles. Un `.duckdb` suelto cuyos artefactos viven en un dir hermano implícito no es portable
   ni autodescriptivo.
2. **Ergonomía del `--store` obligatorio.** El error de uso **más común** es olvidar `--store` (ADR
   0021 §E, Consecuencias): sale **fuera del envelope** (exit 1, stderr de Click). Repetir
   `--store mi.duckdb` en cada invocación es fricción tanto para el humano como para el agente.
3. **Onboarding.** No hay un gesto de "empezar una investigación nueva": el `.duckdb` se
   auto-crea al primer `seed`, sin estructura ni manifest que diga qué es.

Las sub-decisiones (qué marcador usa el workspace, qué flag, qué estructura de dirs, qué pasa con
los `.duckdb` existentes) se refinaron en la conversación de
[#32](https://github.com/complexluise/bib2graph/issues/32) y derivados; este ADR las fija.

## Decisión

**Una investigación = un workspace = una carpeta autocontenida.** Se formaliza la convención
emergente: la carpeta es la unidad de persistencia, portabilidad y "proyecto" para la GUI.

```
mi-investigacion/
├── workspace.json        # manifest mínimo (marcador del workspace)
├── library.duckdb        # la biblioteca viva (corpus + procedencia + curación + loop-state)
├── networks/             # cache de redes (build) — regenerable
├── snapshots/            # snapshots sellados (parquet + manifest) — reproducible
└── exports/              # exports a formatos (graphml/csv) — regenerable
```

- **`b2g init <name>`** scaffolds la carpeta con su estructura y `workspace.json`. **`b2g init .`**
  inicializa el **cwd** como workspace.
- **Resolución ambiente (patrón git/cargo).** `b2g` **camina hacia arriba** desde el cwd buscando
  un `workspace.json`. Precedencia, de mayor a menor:
  1. `--workspace`/`--store` explícito en la invocación,
  2. variable de entorno `B2G_WORKSPACE`,
  3. el workspace del cwd (subiendo hasta encontrar `workspace.json`).
- **Sin migración forzada.** Un `.duckdb` suelto sigue funcionando como **workspace "degenerado"**:
  `--store ruta.duckdb` apunta al archivo y los artefactos caen en su dir hermano como hoy. No se
  exige convertir investigaciones existentes.
- **`b2g status`** muestra el **workspace resuelto** (de dónde salió). Si no hay ninguno (ni
  `workspace.json` hacia arriba, ni env, ni flag), se emite un **error accionable** que sugiere
  `b2g init .` o pasar `--workspace`.

### Sub-decisiones resueltas

- **Marcador = `workspace.json`** (manifest **mínimo**): `{name, created_at, bib2graph_version,
  schema_version}`. El corpus, la procedencia y el loop-state **NO** se duplican acá: ya viven en
  `library.duckdb` (una pregunta = un doc; ADR 0009). El manifest es solo el marcador del límite del
  workspace (lo que `b2g` busca al caminar hacia arriba) + metadatos de versión.
- **Flag = `--workspace` primario, `--store` opcional/degenerado.** `--workspace <carpeta>` es la
  forma canónica; `--store <archivo.duckdb>` se conserva para apuntar a un `.duckdb` suelto (modo
  degenerado, retrocompatible). Ambos son **opcionales**: sin ellos, gana la resolución ambiente.
- **Estructura de directorios estándar y fija.** `networks/`, `snapshots/`, `exports/` son nombres
  convencionales (no configurables en V1): un workspace es reconocible y la GUI sabe dónde mirar.
- **Redes/exports = cache regenerable, sellada por `corpus_hash`.** Las redes de `networks/` y los
  `exports/` son **derivables** del estado vivo; se sellan con el `corpus_hash` del corpus que las
  produjo (ADR [0017](0017-reproducibilidad-historia-snapshot.md)). El artefacto **reproducible**
  sigue siendo el **snapshot** (parquet + manifest), no la cache. La **staleness** (cache cuyo
  `corpus_hash` ya no coincide con el del corpus) se maneja **avisando/regenerando**, **no** con un
  grafo de dependencias: es una invalidación por hash, no un build system.

## Consecuencias

- (+) **Portabilidad:** una investigación se mueve/comparte/respalda como una sola carpeta
  autocontenida y autodescriptiva (`workspace.json`).
- (+) **Prerequisito GUI ([#34](https://github.com/complexluise/bib2graph/issues/34)) cubierto:** la
  GUI abre una carpeta-proyecto con db + redes + snapshots + exports en su sitio.
- (+) **Onboarding:** `b2g init` es el gesto explícito de "empezar una investigación", con estructura
  y manifest desde el día cero (hoy el `.duckdb` nace implícito al primer `seed`).
- (+) **Ergonomía sin `--store`:** trabajar **dentro** de un workspace (o con `B2G_WORKSPACE`) elimina
  el `--store` repetido y el error de uso más común (ADR 0021 §E); el patrón git/cargo es familiar.
- (+) **Formaliza una convención emergente:** `b2g build` **ya** escribe `<store_dir>/networks/`; el
  workspace le da nombre, límite y manifest en vez de un dir hermano implícito.
- (+) **Retrocompatible:** sin migración forzada; el `.duckdb` suelto sigue siendo un workspace
  degenerado válido.
- (−) **Nueva capa `Workspace`** (resolución, scaffolding, lectura del manifest) a construir y testear;
  más superficie que un único archivo.
- (−) **Manejo de staleness por hash** en la cache (`networks/`/`exports/`): hay que sellar con
  `corpus_hash`, comparar y avisar/regenerar. Se acota deliberadamente a invalidación por hash (no un
  grafo de dependencias) para no convertir el producto en un build system.
- (−) **Cambio suave del contrato CLI** (ADR 0021 §E): `--store` deja de ser global obligatorio. Es
  aditivo/retrocompatible (la resolución ambiente solo **cubre** el caso en que falta el flag), pero
  toca el contrato público y exige sincronizar `docs/API.md`/`ARCHITECTURE.md` cuando se implemente.

> **PROPUESTA — no implementado (2026-06-16).** Mientras este ADR esté en estado *Propuesta*, el
> comportamiento **as-built** sigue siendo el de ADR 0009/0019/0021: unidad = `.duckdb`, `--store`
> global **obligatorio**, sin `b2g init` ni resolución ambiente. El flujo diario (CLAUDE.md /
> AGENTS.md / CONTRIBUTING.md / referencia del CLI) y los conteos as-built **no** se reescriben hasta
> que esto se implemente; los marcadores **TARGET** en `ARCHITECTURE.md` describen el objetivo, no el
> presente.
