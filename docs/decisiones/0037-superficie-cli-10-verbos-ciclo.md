# 0037 — Superficie CLI de 0.10.0: 10 verbos agents-first que mapean el ciclo de investigación; `status` como mapa

- **Estado:** Aceptada
- **Fecha:** 2026-06-26
- **Decidido por:** mixto. Las **cuatro decisiones (a)–(d)** —adoptar el set consolidado de **10
  verbos** como contrato de superficie 0.10.0, `curate`/`read` como **grupos noun-verb**, absorber
  `monitor` en `chain --since`, y dar **aliases de retrocompat** durante una ventana de deprecación—
  son **decisiones del Product Owner humano** (confirmadas (a)–(e) sobre la propuesta de convergencia
  de la Discussion [#127](https://github.com/complexluise/bib2graph/discussions/127)). El **encuadre**
  que las ordena —*"la superficie ES el ciclo de investigación"* y *`status` es el mapa que el agente
  lee para saber el próximo comando* (modelo mental tipo `git status`)— es **síntesis de la IA
  (Claude) validada por el PO**.
- **Enmienda a:** [0021](0021-cli-agente-native-contrato.md) (Contrato del CLI agente-native).
  Este ADR **consolida los 12 subcomandos del 0021 (y los que crecieron después) a 10 verbos**,
  absorbiendo `monitor`, `inspect` y `networks` en verbos existentes y agrupando la curación y la
  lectura como noun-verb. **No revierte** el 0021: el **envelope `schema="1"`, los exit codes y las
  transiciones del FSM se preservan** (es reorganización **semántica** de la superficie, no ruptura
  del contrato de salida).
- **Relacionada con:** [0010](0010-agente-native-columna.md) (CLI agente-native como columna
  primaria — este ADR **reordena** su superficie sin tocar el principio),
  [0016](0016-maquina-estados-lazo.md) (FSM cíclico del lazo: `status` sigue leyendo el mismo modelo),
  [0029](0029-workspace-por-investigacion.md) (workspace por investigación: `init` declara el host
  OpenAlex y resuelve por ambiente), [0035](0035-ingesta-multipuerta-resolucion-doi.md) (`--resolve`
  DOI→OpenAlex ya previsto), [0036](0036-identidad-source-id-agnostica-doi-ancla.md) (identidad
  source-agnóstica con DOI ancla: `seed --resolve` y el diagnóstico `source_id` se apoyan en eso),
  [0032](0032-capa-servicios-duena-del-flujo.md)/[0033](0033-producto-library-centric-grafo-proyeccion.md)
  (capa de servicios dueña del flujo / library-centric: la consolidación agents-first es la cara CLI
  de ese mismo flujo).
- **No introduce IA** (coherente con [0022](0022-producto-sin-ia-generativa.md)): todo el
  diagnóstico (`next_best_action`, red-vacía, readiness) es **determinista** —deriva del FSM y de
  conteos del corpus, sin modelo generativo.
- **Origen:** Discussion [#127](https://github.com/complexluise/bib2graph/discussions/127),
  comentario *"Propuesta de convergencia: superficie agents-first para 0.10.0 (más es menos)"*.
  Encuadre: [Nota 05](../Notas/05-ciclo-investigacion-humano.md) (el ciclo de investigación humano) y
  la **nota de sesión 20** (`docs/Notas/20-ax-agente-cli-redes-vacias.md` — AX de un agente en frío:
  *"redes vacías con cara de éxito"*; nota de sesión, **aún no versionada en `dev`**, citada como
  encuadre empírico).
- **Issues:** [#76](https://github.com/complexluise/bib2graph/issues/76) (skill E2E depende de
  `readiness`), [#132](https://github.com/complexluise/bib2graph/issues/132) (docs de usuario).

## Contexto

El ADR [0021](0021-cli-agente-native-contrato.md) fijó el contrato del CLI agente-native con un set
de subcomandos que **creció por acreción**: 11 originales → 12 con `monitor` (cleanup pre-v0.3) →
`init` (0029) → `thesaurus`/`restore` y demás. La superficie hoy ronda los **~20 subcomandos**, y la
Discussion [#127](https://github.com/complexluise/bib2graph/discussions/127) catalogó **seis
solapamientos** que un agente —y un humano— tienen que desambiguar sin que el dominio lo justifique:

1. **`build` vs `networks`** — dos puertas para construir redes (one-shot vs `--spec`).
2. **`inspect` (sin args) vs `status`** — dos formas de "ver dónde estoy".
3. **`inspect --id` vs una lectura de corpus** — leer un paper vive aparte de leer el corpus.
4. **`accept`/`reject`/`filter` sueltos** — la curación dispersa en tres verbos planos.
5. **`monitor` vs `chain`** — forrajeo incremental como comando aparte del forrajeo.
6. **el "doctor"/diagnóstico** tentado como comando nuevo — más superficie para decir lo que
   `status` ya debería decir.

Dos hechos de diseño ordenan la salida:

- **La superficie ES el ciclo de investigación.** La [Nota 05](../Notas/05-ciclo-investigacion-humano.md)
  modela el ciclo humano (Kuhlthau/Ellis/Bates/Pirolli/Wohlin): IDEA → SEMILLAS → CHAINING →
  BROWSING/DIFERENCIAR → ORGANIZAR → SENSEMAKING → CURAR → MONITOREAR, **iterativo y no lineal**. Una
  superficie que **mapea 1:1 ese ciclo** es legible sin manual: el verbo *es* el paso.
- **`status` es el mapa que el agente lee para saber el próximo comando** (modelo mental tipo
  `git status`). La **nota de sesión 20** documenta la trampa de un
  agente en frío: comandos que **devuelven éxito (`exit 0`) con redes vacías** —"cara de éxito" sin
  resultado de investigación—. El agente no tiene de dónde inferir el próximo paso ni por qué la red
  salió vacía. La cura no es un comando-doctor nuevo: es que `status` **diga el próximo mejor paso y
  diagnostique** la red vacía como **campos del mismo envelope** que el agente ya parsea.

La pregunta de 0.10.0 no es "qué comando falta" sino **"qué superficie hace legible el ciclo y deja
a `status` ser el mapa"** — *más es menos*.

## Decisión

**La superficie 0.10.0 es de 10 verbos que mapean el ciclo INIT → SEED → CHAIN → CURATE → BUILD →
READ → EXPORT/SNAPSHOT, con STATUS transversal como mapa.** Es reorganización **semántica** de la
superficie del 0021; el contrato de salida (envelope/exit/FSM) **no cambia**.

### Los 10 verbos (cada uno = un paso del ciclo)

| Verbo | Paso del ciclo | Qué hace / qué absorbe |
|-------|----------------|------------------------|
| `b2g init` | INIT | Crea el workspace; **declara el host OpenAlex y muestra el primer comando**; *folds* la fricción de la dependencia de red y el alias `bib2graph`≠`b2g`. |
| `b2g seed --from-bib FILE \| --from-equation Q` | SEED | **Dos puertas de ingesta** unificadas; `--resolve` (DOIs→OpenAlex, ADR 0035), `--email`, `--limit N`. |
| `b2g chain --back --forward` | CHAIN | Forrajeo con caps + filtros por defecto + progreso; **absorbe `monitor` como modo incremental `--since`** (decisión (c)). |
| `b2g curate {dump,apply,accept,reject,filter}` | CURATE | **Grupo noun-verb** (decisión (b)); absorbe `accept`/`reject`/`filter`; **quita el alias deprecado `--all`**. |
| `b2g build [--scope all\|accepted\|seeds] [--spec YAML] [--min-weight N]` | BUILD | Construye redes; **default corre SIN curar (one-shot)**; **warning + diagnóstico si una red sale vacía**; absorbe `networks` vía `--spec`. |
| `b2g read {list,stats,top,show}` | READ | **Grupo noun-verb** (decisión (b)); `list`/grep corpus, `stats --group-by`, **`top` = centrales + co-citación con título (salida de investigación, NUEVO)**, `show --id`; absorbe `inspect --id`. |
| `b2g export` / `b2g snapshot` | EXPORT/SNAPSHOT | Formatos extra / snapshot reproducible; **clarifica `export` vs la salida de `build`**. |
| `b2g status` | STATUS (transversal) | FSM + **readiness** + **`next_best_action`** + dependencies + **diagnóstico red-vacía**; **absorbe `inspect` sin args y el "doctor" SIN comando nuevo**, como **campos ADITIVOS** que preservan `schema="1"`. |
| `b2g validate` | — | Se mantiene sin cambios. |

**Total: `init`, `seed`, `chain`, `curate`, `build`, `read`, `export`, `snapshot`, `status`,
`validate` = 10 verbos** (`export`/`snapshot` cuentan como el par de salida).

### Sub-decisiones del PO

- **(a) Set consolidado de 10 verbos como contrato de superficie 0.10.0.** Reemplaza/enmienda los
  12 subcomandos del 0021 (y la acreción posterior). Lo que existía como verbo plano se absorbe en el
  verbo del paso de ciclo correspondiente.
- **(b) `curate` y `read` como grupos noun-verb** (no verbos planos). La curación (`dump`/`apply`/
  `accept`/`reject`/`filter`) y la lectura (`list`/`stats`/`top`/`show`) se agrupan por sustantivo;
  los verbos planos `accept`/`reject`/`filter`/`inspect --id` quedan absorbidos.
- **(c) `monitor` se absorbe en `chain --since`** (no se mantiene separado). El forrajeo incremental
  es el mismo forrajeo con una ventana temporal; deja de ser un verbo aparte (retira el 12°
  subcomando del 0021 como verbo independiente, conserva su semántica → `MONITORED`).
- **(d) Aliases de retrocompat** para los comandos consolidados (`build`/`networks`,
  `accept`/`reject`, `inspect`, `monitor`) durante una **ventana de deprecación**. No se rompe de una;
  los nombres viejos siguen funcionando (con aviso) hasta cerrar la ventana.

### Invariantes preservados (por qué esto NO rompe el contrato)

- **Envelope `schema="1"`, exit codes y FSM del lazo se preservan** (ADR 0021 §C/§D/§F, 0016, 0010).
  Reorganizar qué verbo invoca qué no cambia la forma de la salida ni el mapeo de errores.
- **`readiness`, `next_best_action` y el diagnóstico de red-vacía entran como campos ADITIVOS de
  `status`** —no como comando nuevo—. Respeta el **invariante de subcomandos del 0021** y repite el
  **mismo patrón que la enmienda R3** (que sumó `curation_available`/`round` al `data` de `status`
  **sin bumpear `schema`**, decisión del PO 2026-06-16: campos nuevos no rompen agentes).
- **Stdout puro en `--json`** (enmienda menor al 0021 §C: una línea JSON por invocación, sin ruido).
- **`--resolve`** ya estaba previsto por ADR [0035](0035-ingesta-multipuerta-resolucion-doi.md).
- **Identidad source-agnóstica (DOI ancla)** viene de ADR
  [0036](0036-identidad-source-id-agnostica-doi-ancla.md): `seed --resolve` y el diagnóstico
  `source_id` del red-vacía se apoyan en esa identidad.

### La historia one-shot (el ciclo legible sin curar)

El default de `build` corre **sin curar** (one-shot); el agente sigue el ciclo leyendo
`status --json.data.next_best_action` en cada punto:

```text
$ b2g init mi-investigacion        # INIT  → declara host OpenAlex, muestra el primer comando
$ b2g status --json                #        data.next_best_action = "seed"
$ b2g seed --from-bib refs.bib --resolve --email yo@ej.org
                                    # SEED  → ingesta + DOIs→OpenAlex (0035)
$ b2g status --json                #        data.next_best_action = "chain"
$ b2g chain --back --forward       # CHAIN → forrajeo con caps + filtros por defecto
$ b2g status --json                #        data.next_best_action = "build"
$ b2g build                        # BUILD → one-shot, SIN curar; si una red sale vacía:
                                    #        warning + diagnóstico (no "exito vacío", Nota 20)
$ b2g status --json                #        data.next_best_action = "read"
$ b2g read top                     # READ  → centrales + co-citación con título (salida de invest.)
$ b2g snapshot                     # SNAPSHOT → reproducible
```

`status` es el **mapa**: en cada punto dice dónde está el lazo (FSM), qué está listo (`readiness`),
cuál es el próximo mejor paso (`next_best_action`) y, si algo no va a producir resultado, **lo
diagnostica antes** —el agente no se queda con una "cara de éxito" vacía.

## Consecuencias

**Lo que se gana**

- **El ciclo se vuelve legible y one-shot.** La superficie mapea 1:1 los pasos de la
  [Nota 05](../Notas/05-ciclo-investigacion-humano.md); un agente (o un humano) infiere el flujo sin
  manual: el verbo *es* el paso. El default sin curar deja correr `init→seed→chain→build→read` de
  punta a punta.
- **Menos superficie, menos solapamiento.** De ~20 subcomandos con 6 solapamientos a **10 verbos**;
  `monitor`/`inspect`/`networks` y la curación/lectura dispersas dejan de ser puertas paralelas.
- **`status` como mapa cierra la trampa de la red vacía** (Nota 20) **sin comando nuevo**:
  `next_best_action` + diagnóstico red-vacía + `readiness` viven como campos aditivos del envelope
  que el agente ya parsea (habilita el skill E2E de [#76](https://github.com/complexluise/bib2graph/issues/76)).

**Lo que cuesta**

- **Ventana de deprecación a mantener** (decisión (d)): los aliases `build`/`networks`,
  `accept`/`reject`, `inspect`, `monitor` siguen vivos —con aviso— hasta cerrarla. Es superficie
  transitoria a documentar y testear, y una fecha/criterio de cierre a fijar.
- **`docs/API.md` a actualizar en la implementación.** Cambiar el contrato público de superficie
  exige reflejar los 10 verbos, los grupos noun-verb, `chain --since`, los campos aditivos de
  `status` y los aliases. *Este ADR registra ese cambio como consecuencia; la edición de `API.md` es
  trabajo del `coder` en el hito de implementación, no parte de este ADR.*
- **Tests de contrato `--json` a ajustar.** Los golden/schema por comando del 0021 cambian de nombre
  de comando y suman los campos aditivos de `status`; hay que reapuntarlos sin que el `schema` driftee
  (sigue `"1"`).

**Diferido a seguimiento (NO bloquea 0037)** — dos afinadas que el PO **difirió conscientemente**,
registradas en la Discussion [#127](https://github.com/complexluise/bib2graph/discussions/127#discussioncomment-17450871):

- **(e.5) `status` con preview por-red "qué se materializa si actúo ahora"** (modelo `git status`
  staged/unstaged): mover el diagnóstico de red-vacía de *build-time* a *status-time*. **No** es parte
  de 0037.
- **(e.6) Maturity-stamp del one-shot:** el artefacto del one-shot lleva un bloque `maturity`/
  `caveats` declarándose **borrador sin pulir** (corrió sin curar). **No** es parte de 0037.

Ambas quedan como follow-up consciente; entran (o no) por su propio ADR/issue.

## Alternativas

- **Verbos planos en vez de grupos noun-verb.** Mantener `accept`/`reject`/`filter`/`inspect` como
  verbos sueltos. Rechazada (decisión (b)): infla la superficie y dispersa la curación y la lectura en
  varios verbos sin sustantivo común; el agrupamiento noun-verb (`curate …`, `read …`) hace legible
  qué pertenece a qué paso del ciclo.
- **Mantener `monitor` como verbo separado.** Rechazada (decisión (c)): el forrajeo incremental es el
  mismo forrajeo con ventana temporal; un verbo aparte duplica el solapamiento (5) del #127.
  `chain --since` lo absorbe conservando la transición a `MONITORED`.
- **No dar aliases / romper de una.** Rechazada (decisión (d)): los nombres viejos están en skills y
  scripts de agentes ya escritos; romperlos sin ventana paga un costo de migración abrupto sin
  beneficio. La ventana de deprecación amortiza el cambio.
- **Un comando "doctor" nuevo para el diagnóstico.** Rechazada: agrega superficie para decir lo que
  `status` —el mapa— debe decir. El diagnóstico entra como **campos aditivos** del envelope de
  `status` (mismo patrón que R3 del 0021), respetando el invariante de subcomandos.
