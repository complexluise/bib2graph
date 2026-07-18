# 0038 — Destino de los 5 verbos huérfanos del 0037 y parámetros de implementación: el conteo "10 verbos" se vuelve real

- **Estado:** Aceptada
- **Fecha:** 2026-06-27
- **Decidido por:** **Product Owner humano** (decisión tomada 2026-06-27). El destino de cada verbo
  huérfano (`gui`/`enrich`/`restore`/`thesaurus`/`resolve`) y los tres parámetros de implementación
  (versión de cierre de la ventana de deprecación, default de `build --scope`, dónde se fija la forma
  del bloque `maturity`) son **decisiones del PO**. El **encuadre** —*"el conteo de 10 verbos del 0037
  era contable hasta despachar los huérfanos; este ADR lo vuelve real"*— es **síntesis de la IA
  (architect) validada por el PO**.
- **Enmienda a:** [0037](0037-superficie-cli-10-verbos-ciclo.md) (Superficie CLI 0.10.0: 10 verbos
  agents-first). Este ADR **completa** el 0037: el 0037 consolidó a 10 verbos los solapamientos que
  catalogó la Discussion [#127](https://github.com/complexluise/bib2graph/discussions/127), pero
  **no nombró** cinco subcomandos que la superficie real tenía por acreción (`gui`, `enrich`,
  `restore`, `thesaurus`, `resolve`). Sin despacharlos, el "10" del 0037 era **ficción contable**: el
  CLI exponía más verbos de los que el ADR declaraba. Este ADR fija el destino de cada uno y **cierra
  los parámetros que el 0037 dejó abiertos** (criterio de cierre de la ventana de deprecación (d),
  default de `build --scope`, y dónde vive la forma estable del `maturity` (f)). **No revierte** el
  0037 ni el contrato: el **envelope `schema="1"`, los exit codes y el FSM del lazo se preservan**
  (ADR [0021](0021-cli-agente-native-contrato.md) §C/§D/§F).
- **Relacionada con:** [0021](0021-cli-agente-native-contrato.md) (contrato del CLI: este ADR sigue
  consolidando su superficie sin tocar el envelope), [0027](0027-pivote-posicionamiento-gui-local.md)
  /[0028](0028-arquitectura-gui-api-capa-servicios.md) (`gui` se rige por estos ADR y queda **fuera**
  del set de 10, como excepción explícita), [0035](0035-ingesta-multipuerta-resolucion-doi.md)
  (`seed --resolve` como ruta única de resolución DOI→OpenAlex; retira `resolve` suelto),
  [0030](0030-ecuacion-declarativa-corpus-ejemplo.md) (donde `restore` nació como verbo plano; pasa a
  `snapshot restore`), [0031](0031-preprocesamiento-automatico-en-ingesta.md) (donde `thesaurus`
  quedó como "único paso explícito"; este ADR **revisa esa parte** — ver Consecuencias),
  [0011](0011-thesaurus-multilingue.md) (thesaurus de keywords),
  [0025](0025-enricher-cocitacion-openalex.md) (Enricher opt-in: `enrich` se absorbe en
  `chain`/`build`), [0029](0029-workspace-por-investigacion.md) (resolución por ambiente; el alias de
  entry-point `bib2graph`→`b2g` entra a la ventana de deprecación).
- **No introduce IA** (coherente con [0022](0022-producto-sin-ia-generativa.md)): es reorganización
  de superficie y fijación de parámetros; sin modelo generativo.
- **Origen:** revisión post-merge del [0037](0037-superficie-cli-10-verbos-ciclo.md) (PR
  [#150](https://github.com/complexluise/bib2graph/pull/150)/[#153](https://github.com/complexluise/bib2graph/pull/153)):
  al inventariar la superficie real contra los 10 verbos declarados, quedaron **5 subcomandos sin
  asignar**. Decisión del PO 2026-06-27.
- **Issues:** [#149](https://github.com/complexluise/bib2graph/issues/149) (*"thesaurus.py no
  implementa un tesauro"*, cerrada como **invalid**) — contexto del retiro de `thesaurus`.

## Contexto

El [0037](0037-superficie-cli-10-verbos-ciclo.md) declaró una superficie 0.10.0 de **10 verbos** que
mapean el ciclo de investigación, absorbiendo los seis solapamientos del
[#127](https://github.com/complexluise/bib2graph/discussions/127) (`networks`→`build --spec`,
`inspect`→`status`/`read`, `accept`/`reject`/`filter`→`curate …`, `monitor`→`chain --since`,
"doctor"→campos de `status`). Pero el 0037 razonó sobre los **solapamientos catalogados**, no sobre
el **inventario completo** del CLI. La superficie real —que el propio 0037 describe como "~20
subcomandos por acreción"— incluía **cinco verbos que el ADR no nombró**:

1. **`gui`** — lanza la GUI local (ADR [0027](0027-pivote-posicionamiento-gui-local.md)
   /[0028](0028-arquitectura-gui-api-capa-servicios.md)), gateada por
   [#34](https://github.com/complexluise/bib2graph/issues/34).
2. **`enrich`** — enriquecimiento opt-in (refs→DOI + co-citación) del Enricher,
   ADR [0025](0025-enricher-cocitacion-openalex.md).
3. **`restore`** — restaura un corpus curado (sin red) desde snapshot, ADR
   [0030](0030-ecuacion-declarativa-corpus-ejemplo.md).
4. **`thesaurus`** — paso de normalización de keywords, marcado en
   [0031](0031-preprocesamiento-automatico-en-ingesta.md) como "único paso explícito (18° subcomando,
   transversal)".
5. **`resolve`** — resolución DOI→OpenAlex como verbo suelto (la otra ruta, `seed --resolve`, ya
   existe por ADR [0035](0035-ingesta-multipuerta-resolucion-doi.md)).

Mientras estos cinco sigan vivos como verbos planos, **"10 verbos" es un número que el código
desmiente**: un agente que lista `--help` ve más superficie de la que el contrato declara, y vuelve
el mismo problema que el 0037 quería cerrar (superficie ilegible, puertas paralelas). La pregunta de
este ADR no es de diseño nuevo, sino de **higiene del contrato**: *¿dónde va cada huérfano para que
el conteo del 0037 sea verdad?* — y, de paso, **cerrar los tres parámetros que el 0037 dejó
abiertos**.

## Decisión

**Cada uno de los 5 verbos huérfanos se reabsorbe, se reparenta o se retira, de modo que la
superficie del ciclo quede en los 10 verbos del 0037 más `gui` como excepción explícita y
gobernada por su propio ADR.** Es reorganización **semántica**; el contrato de salida
(envelope/exit/FSM) **no cambia**.

### Destino de los 5 huérfanos

| Verbo | Destino | Por qué |
|-------|---------|---------|
| `gui` | **SE MANTIENE, fuera del set de 10.** No entra al ciclo CLI agents-first; no se retira. | Tiene su propio gobierno: ADR [0027](0027-pivote-posicionamiento-gui-local.md) (pivote GUI) y [0028](0028-arquitectura-gui-api-capa-servicios.md) (arquitectura GUI/API), gateado por [#34](https://github.com/complexluise/bib2graph/issues/34). Es una **superficie distinta** (lanzador de la GUI local), no un paso del ciclo agents-first; excluirla del conteo es honesto, no omitirla. |
| `enrich` | **Se absorbe en `build`/`chain`** (deja de ser verbo suelto). | El enriquecimiento (refs→DOI + co-citación, ADR [0025](0025-enricher-cocitacion-openalex.md)) es parte del forrajeo (`chain`) y de la materialización de redes (`build`), no un paso aparte del ciclo. Un verbo independiente duplica superficie para lo que el paso correspondiente ya hace. |
| `restore` | **Pasa a `snapshot restore`** (noun-verb del grupo `snapshot`). | `restore` es la operación inversa de `snapshot`: ambos son reproducibilidad de corpus. Agruparlos bajo el sustantivo `snapshot` (mismo patrón noun-verb que `curate …`/`read …` del 0037) hace legible que pertenecen al mismo paso EXPORT/SNAPSHOT. **Conserva la capacidad** que fijó el ADR [0030](0030-ecuacion-declarativa-corpus-ejemplo.md); solo cambia el nombre. |
| `thesaurus` | **Se retira (verbo eliminado).** | La issue [#149](https://github.com/complexluise/bib2graph/issues/149) (cerrada **invalid**) constató que `thesaurus.py` *"no implementa un tesauro"*. Como verbo explícito carga una promesa que el código no cumple. **Revisa la parte del [0031](0031-preprocesamiento-automatico-en-ingesta.md) que lo nombró "único paso explícito"** (ver Consecuencias). |
| `resolve` | **Se retira como verbo suelto.** Su ruta única es `seed --resolve`. | El ADR [0035](0035-ingesta-multipuerta-resolucion-doi.md) ya definió la resolución DOI→OpenAlex como **servicio compartido** expuesto vía `seed --resolve` (ya implementado). Un `resolve` plano es una segunda puerta para lo mismo: exactamente el tipo de solapamiento que el 0037 retira. |

**Resultado:** la superficie del ciclo queda en los **10 verbos del 0037**
(`init`, `seed`, `chain`, `curate`, `build`, `read`, `export`/`snapshot`, `status`, `validate`), con
`snapshot restore` como noun-verb dentro de `snapshot`, **más `gui`** como excepción explícita
gobernada por 0027/0028. El número "10" del 0037 deja de ser contable y pasa a ser **verificable
contra `--help`**.

### Parámetros de implementación fijados por el PO

- **(P1) La ventana de deprecación cierra en la versión `0.11.0` (criterio por versión).** Los
  aliases de retrocompat introducidos por el 0037 (d) —`networks`, `accept`, `reject`, `inspect`,
  `monitor`— **más** `resolve` (retirado aquí) **y el alias de entry-point `bib2graph`→`b2g`— siguen
  funcionando con aviso de deprecación durante 0.10.x y **se eliminan en 0.11.0**. Esto **cierra el
  cabo suelto del 0037 (d)**, que dejó "fecha/criterio de cierre a fijar". Criterio = **versión**, no
  fecha calendario.
- **(P2) El default de `build --scope` es `all`.** Coherente con la historia one-shot del 0037 (el
  default corre **sin curar**) y con el ejemplo de `maturity` del propio 0037 (`scope:"all"`).
- **(P3) La forma estable del bloque `maturity` (0037 (f)) la fija el architect como apéndice en
  [`docs/API.md`](../API.md) durante la implementación** —no en este ADR—. Aquí solo se registra
  **dónde** vive esa especificación; su schema concreto (campos, tipos) es trabajo del hito de
  implementación, como campo **aditivo** que preserva `schema="1"`.

### Invariantes preservados

- **Envelope `schema="1"`, exit codes y FSM del lazo intactos** (ADR 0021, 0016, 0010). Mover/retirar
  verbos no cambia la forma de la salida ni el mapeo de errores.
- **Ninguna capacidad de dominio se pierde:** el enriquecimiento sigue (dentro de `chain`/`build`,
  0025), el restore sigue (`snapshot restore`, 0030), la resolución DOI sigue (`seed --resolve`,
  0035). Solo `thesaurus` se retira como **verbo** (su lugar como paso de normalización se resuelve en
  la implementación — ver Consecuencias).

## Consecuencias

**Lo que se gana**

- **El conteo del 0037 se vuelve verdad.** Lo que `--help` lista coincide con lo que el contrato
  declara: 10 verbos del ciclo + `gui` (excepción documentada). Desaparece la brecha entre el ADR y la
  superficie real que motivó este ADR.
- **Menos puertas paralelas.** `enrich`/`resolve` dejan de duplicar lo que `chain`/`build` y
  `seed --resolve` ya hacen; `restore` se vuelve legible como parte de `snapshot`.
- **La ventana de deprecación tiene fin cierto** (P1): los aliases no quedan vivos
  indefinidamente; 0.11.0 es el corte.

**Lo que cuesta**

- **`docs/API.md` a actualizar en la implementación** (trabajo del `coder`, no de este ADR): retirar
  `enrich`/`thesaurus`/`resolve` del contrato, mover `restore`→`snapshot restore`, documentar `gui`
  como excepción al set de 10, fijar el default `build --scope=all` (P2) y sumar el apéndice
  `maturity` (P3). Recomendación: revisar las menciones a estos verbos en el contrato actual y en los
  golden tests `--json`.
- **Tests de contrato y aliases a ajustar:** sumar el aviso de deprecación de `resolve` y del
  entry-point `bib2graph`, y el corte programado para 0.11.0.

**Tensiones que hay que mirar (drift honesto)**

- **`thesaurus` vs ADR [0031](0031-preprocesamiento-automatico-en-ingesta.md).** El 0031 declaró
  `thesaurus` como **"único paso explícito (18° subcomando, transversal)"** del preprocesamiento.
  Retirarlo como verbo **revisa esa parte del 0031** (no la revierte entera: el 0031 ya volvió
  *normalize + dedup* **automáticos en la ingesta**; lo que cae es el único paso que había quedado
  explícito). **Pregunta abierta para el `coder`/PO:** ¿la normalización de keywords se **pliega a la
  ingesta automática** (coherente con el espíritu del 0031) o **se elimina** junto con el verbo? La
  issue [#149](https://github.com/complexluise/bib2graph/issues/149) (invalid) sugiere que la
  implementación actual no era un tesauro real; conviene **confirmar el destino de la funcionalidad**,
  no solo del verbo, en el hito de implementación. *Este ADR retira el verbo; el destino del paso de
  normalización debe quedar explícito en `docs/API.md`.* Relacionada: ADR
  [0011](0011-thesaurus-multilingue.md).
- **`restore` vs ADR [0030](0030-ecuacion-declarativa-corpus-ejemplo.md).** El 0030 (AS-BUILT)
  nombró `restore` como verbo plano. `snapshot restore` es **renombre semántico**, no pérdida de
  capacidad; aun así, es un cambio de superficie pública que `docs/API.md` y la guía de usuario deben
  reflejar.

## Alternativas

- **Dejar los 5 huérfanos como verbos sueltos.** Rechazada: vuelve el "10" del 0037 una **ficción
  contable** —el problema exacto que el 0037 quería cerrar (superficie ilegible, puertas paralelas)
  reaparece por la puerta de atrás—. La higiene del contrato exige despacharlos.
- **Meter `gui` dentro del set de 10.** Rechazada: `gui` no es un paso del ciclo agents-first; es una
  superficie distinta con su propio gobierno (0027/0028) y gate (#34). Forzarla al set mezcla dos
  contratos. Excluirla **explícitamente** es más honesto que disimularla en el conteo.
- **Retirar `enrich` por completo (no absorberlo).** Rechazada: el enriquecimiento es capacidad de
  dominio viva (ADR 0025); lo que sobra es el **verbo**, no la función. Se absorbe en `chain`/`build`.
- **Mantener `resolve` como verbo y deprecar `seed --resolve`.** Rechazada: contradice el ADR
  [0035](0035-ingesta-multipuerta-resolucion-doi.md), que fijó la resolución como **servicio
  compartido** con `seed --resolve` como ruta de ingesta. Se conserva la ruta del 0035; se retira el
  verbo suelto.
- **Cerrar la ventana de deprecación por fecha calendario en vez de por versión.** Rechazada (P1):
  el criterio por **versión (0.11.0)** es verificable, reproducible y no depende del calendario de
  release; es coherente con cómo el proyecto versiona (release-please).

## Enmienda 2026-06-27 (append-only) — corrige el gap de P1: `filter` también entra a la ventana (#155)

> Anotación append-only (no revierte nada de arriba). Surge de la implementación del grupo `curate`
> noun-verb (sub-issue [#155](https://github.com/complexluise/bib2graph/issues/155)): al absorber
> `filter` en `curate filter` se constató que **P1 omitió `filter`** de la lista de aliases en
> deprecación.

El parámetro **(P1)** enumeró los aliases que cierran en `0.11.0` como *"`networks`, `accept`,
`reject`, `inspect`, `monitor` —más `resolve` y el entry-point `bib2graph`"*. Pero el ADR
[0037](0037-superficie-cli-10-verbos-ciclo.md) (decisión (b)) absorbió **`accept`/`reject`/`filter`**
en el grupo `curate`: los tres verbos planos quedan como alias deprecados. P1 listó `accept` y
`reject` pero **omitió `filter`** —un gap, no una decisión—.

**Corrección:** el verbo suelto **`filter` se suma a la ventana de deprecación**, con el mismo
criterio que `accept`/`reject`: sigue funcionando **con aviso** durante 0.10.x y **se elimina en
0.11.0**, como alias deprecado del nuevo **`curate filter`**. (`filter` y `curate filter` comparten la
lógica de servicio `filter_corpus`, fuente única; el suelto es un shim que delega.) El resto de P1 no
cambia. AS-BUILT del grupo `curate` en [`../API.md`](../API.md) §`curate`.

## Enmienda 2026-06-27 (append-only) — fija el detalle de `restore`→`snapshot restore`: `snapshot` se vuelve grupo noun-verb y el plano → `snapshot create` [BREAKING] (#163)

> Anotación append-only (gemela de las enmiendas D1 (#159) / #155; no revierte nada de arriba). Surge
> de la implementación del sub-issue [#163](https://github.com/complexluise/bib2graph/issues/163). La
> **Decisión** de arriba ya fijó que `restore` pasa a **`snapshot restore`** (tabla de huérfanos +
> Consecuencias §`restore` vs 0030, líneas ~85/154-157), pero **no explicitó** qué pasa con el verbo
> `snapshot` mismo. La implementación lo resuelve: para alojar `snapshot restore`, **`snapshot` deja
> de ser verbo plano y se vuelve grupo noun-verb** —y eso obliga a renombrar el `snapshot` plano—.

El ADR decidió el **destino** de `restore` (→ `snapshot restore`) pero no el **detalle del grupo**.
Concretamente, al volverse `snapshot` un grupo:

- **(a) `snapshot` es ahora grupo noun-verb `{create, restore}`** —el **3er grupo del CLI**, mismo
  patrón que `read` (1°, #156/#157) y `curate` (2°, #155): `snapshot` **sin subcomando** imprime la
  ayuda y sale **exit 0**; el `command` del envelope usa la **ruta completa** (`"snapshot create"` /
  `"snapshot restore"`).
- **(b) El `snapshot` plano → `snapshot create`** —**BREAKING, sin alias**, mismo criterio que el
  BREAKING de `curate` (decisión (b) del 0037, forma-flag eliminada sin alias). `snapshot create` es
  el ex `snapshot` plano sin cambios de semántica: sella la foto reproducible (parquet +
  `manifest.json`, ADR 0017), **NO transiciona** el `CycleState` y **lleva el bloque `maturity`** del
  one-shot (AS-BUILT #160, coherente con `build`/`read top`).
- **(c) `snapshot restore` es el ex `restore`** (mergea+dedup, preserva la curación, **transiciona a
  `FILTERED`** reusando la transición permisiva `filter`, ADR 0016/0030). El **verbo suelto `restore`
  queda INTACTO como alias deprecado** (shim que delega; su envelope lleva `command="restore"` por
  backward-compat). Su **retiro se agenda en #165** (junto con `inspect`), no en este hito.
- **(d) Fuente única en `service/snapshot.py`** (`run_snapshot`/`run_restore`, servicio neutral con
  reloj `decided_at` inyectado en la frontera, ADR 0017): `snapshot create`, `snapshot restore` y el
  shim `restore` suelto **delegan** en ella. `run_snapshot` lleva el bloque `maturity` (de #160).

**Invariantes intactos:** envelope `schema="1"`, exit codes y la forma del FSM no cambian; `create`
**NO** transiciona, `restore`→`FILTERED` (igual que antes). Esta enmienda solo fija el detalle del
grupo y el BREAKING que la Decisión no explicitó. AS-BUILT en [`../API.md`](../API.md) §`snapshot`.

> **Follow-up (BAJO, #175):** la implementación dejó `normalize_and_dedup` duplicado en
> `service/snapshot.py` respecto del helper de `cli/_ingest.py`. Es deuda de DRY, **no** afecta el
> contrato; se trata en su propio issue, no aquí.

## Enmienda 2026-06-28 (append-only) — corrige el gap de P1: `enrich` también entra a la ventana, y consolida los 9 aliases (#162/#165)

> Anotación append-only (gemela de la enmienda `filter` de 2026-06-27; no revierte nada de arriba).
> Surge de absorber `enrich` en `chain`/`build` ([#162](https://github.com/complexluise/bib2graph/issues/162))
> y de la implementación de la capa de deprecación ([#165](https://github.com/complexluise/bib2graph/issues/165)).

El parámetro **(P1)** enumeró los aliases que cierran en `0.11.0` como *"`networks`, `accept`,
`reject`, `inspect`, `monitor` —más `resolve` y el entry-point `bib2graph`"*. Pero la tabla de
huérfanos de la **Decisión** de arriba absorbe **`enrich`** en `chain`/`build`: el verbo plano queda
como alias deprecado. P1 **omitió `enrich`** —el **mismo gap** que ya se corrigió para `filter` (#155)
y que aplica también a `restore` (→ `snapshot restore`, #163)—; no es una decisión, es una omisión.

**Corrección:** el verbo suelto **`enrich` se suma a la ventana de deprecación**, con el mismo criterio
que `accept`/`reject`/`filter`/`restore`: sigue funcionando **con aviso** durante 0.10.x y **se elimina
en 0.11.0**, como alias que delega en la misma lógica (`cli/_enrich.py::enrich_corpus`, fuente única;
ver nota append-only del ADR [0025](0025-enricher-cocitacion-openalex.md)).

**Lista completa de los 9 aliases deprecados** (alias vivo con aviso a stderr hasta 0.11.0), tal como
los registra `cli/_deprecation.py` (#165):

| Alias deprecado | Forma canónica |
|---|---|
| `b2g accept` | `b2g curate accept` |
| `b2g reject` | `b2g curate reject` |
| `b2g filter` | `b2g curate filter` |
| `b2g inspect` | `b2g read show` / `b2g status` |
| `b2g monitor` | `b2g chain --since` |
| `b2g networks` | `b2g build --spec` |
| `b2g enrich` | `b2g chain` (+ `b2g build`) |
| `b2g restore` | `b2g snapshot restore` |
| `b2g resolve` | `b2g seed --resolve` |

**Más** el entry-point `bib2graph` → `b2g` y la opción **`build --corpus-scope` → `build --scope`**
(mismo corte 0.11.0). `thesaurus` **no** está en esta lista: se **retira por completo** (sin alias);
su capacidad vive como `build --thesaurus` (#164; nota append-only del ADR
[0031](0031-preprocesamiento-automatico-en-ingesta.md)). AS-BUILT de la capa de avisos en
[`../API.md`](../API.md) §Avisos de deprecación.

## Enmienda 2026-07-18 (append-only) — el retiro de P1 no ocurrió en 0.11.0; se ejecuta en 0.12.0 (#207)

> Anotación append-only (no revierte nada de arriba). Fija la versión real del retiro que P1 y sus
> enmiendas agendaron nominalmente para 0.11.0.

El parámetro **(P1)** —y sus enmiendas de `filter` (#155) y `enrich` (#162/#165)— fijaron el cierre de
la ventana de deprecación en **`0.11.0`** (criterio por versión). **Ese retiro no se ejecutó en esa
versión:** 0.11.0 salió mínima (solo lo ya acumulado en `dev`), sin la poda de superficie. El retiro
se **ejecuta en `0.12.0`** ([#207](https://github.com/complexluise/bib2graph/issues/207)). El criterio
por versión de P1 no cambia (sigue siendo *por versión, no fecha*); solo se corrige **cuál** versión
materializa el corte.

**AS-BUILT del retiro (0.12.0, BREAKING, verificable contra `src/bib2graph/cli/__init__.py`):**

- Los **9 aliases deprecados** (`accept`, `reject`, `filter`, `inspect`, `monitor`, `networks`,
  `enrich`, `restore`, `resolve`) **ya no se registran**: invocarlos da el error estándar de Click
  (`No such command`). Sus formas canónicas son las de la tabla de la enmienda #162/#165 (arriba).
- El **entry-point legado `bib2graph`** se retiró (queda solo `b2g`).
- El flag **`build --corpus-scope`** se retiró (queda `build --scope`, default `all`).
- El módulo `cli/_deprecation.py` (helper único de avisos) se eliminó.

**Superficie final verificable = 12 registros exactos:** los **10 verbos del ciclo** (`init`, `seed`,
`chain`, `build`, `export`, `status`, `validate` planos + los grupos `curate`, `read`, `snapshot`) **+
`skill` + `schema`** (meta). Invariantes intactos: envelope `schema="1"`, exit codes 0–5 y la forma del
FSM no cambian. AS-BUILT del contrato en [`../API.md`](../API.md) §Convenciones del CLI y §Formas
canónicas de los verbos retirados.
