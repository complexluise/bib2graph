# 0044 — Precedencia de la inclusión manual sobre el filtro PRISMA en `curate filter`: `accepted` gana

- **Estado:** Aceptada
- **Fecha:** 2026-06-30
- **Decidido por:** **Product Owner humano** (2026-06-30). El PO eligió la opción "respetar
  `accepted`": la inclusión manual gana sobre el criterio automático. El **encuadre** (clasificar el
  hallazgo como *footgun invisible* y traer las tres opciones de precedencia) es síntesis de la IA
  (arquitecto) validada por el PO.
- **Precisa:** [0020](0020-metodo-forrajeo-scent-filtros-reject.md) **§C** ("Filtros PRISMA marcan
  `rejected`, NO borran"). 0020 §C fijó **qué** hace un filtro (marca `rejected`, no borra) pero **no**
  fijó **sobre qué papers puede actuar** respecto de una decisión de inclusión humana previa. Este ADR
  precisa ese scope: el filtro **nunca** actúa sobre `accepted`. No revierte 0020 §C (los filtros
  siguen marcando `rejected`, sin borrar, con conteo PRISMA); lo acota.
- **Relacionada con:** [0016](0016-maquina-estados-lazo.md) (enmienda 2026-06-15: la **curación es
  transversal** y `accept`/`reject` son "lo único irreductiblemente humano" — la aceptación manual es
  una decisión de inclusión del humano, no una etiqueta que un filtro masivo pueda pisar),
  [0037](0037-superficie-cli-10-verbos-ciclo.md) (**enmienda D2**: dentro del grupo `curate`, la
  transición la define el verbo; **`curate filter`→`FILTERED`** — este ADR fija la **política de
  precedencia** de ese mismo verbo, sin tocar su transición), [0009](0009-biblioteca-viva-duckdb.md) /
  [0013](0013-identidad-hash-merge-corpus.md) (biblioteca viva, curación reversible y `provenance`
  append-only: la re-aceptación sigue disponible), [0022](0022-producto-sin-ia-generativa.md)
  (determinismo/honestidad: el motor no toma decisiones silenciosas que el humano no pidió).
- **Origen:** issue [#233](https://github.com/complexluise/bib2graph/issues/233) — en una corrida e2e
  autónoma del CLI (2026-06-30, sobre `examples/valoraciones/`), `curate filter` reclasificó a
  `rejected` **2 papers** que estaban `accepted` a mano, **sin aviso**. Clase **footgun invisible**:
  `exit 0`, sin señal, con pérdida silenciosa de una decisión de inclusión humana. Encuadre:
  [Nota 22](../Notas/22-marco-software-donde-nos-paramos.md) (frontera bib2graph/producto: honestidad
  y determinismo; "el humano decide la inclusión").

## Contexto

`curate filter` (ADR [0037](0037-superficie-cli-10-verbos-ciclo.md), decisión (b) + enmienda D2)
aplica criterios de inclusión/exclusión tipo PRISMA (`--year-gte`/`--year-lte`, `--language`,
`--type`, `--min-citations`) marcando `curation_status='rejected'` a los papers que **no pasan** el
criterio, sin borrarlos (ADR [0020](0020-metodo-forrajeo-scent-filtros-reject.md) §C). La lógica pura
vive en `filters/prisma.py` (`apply_filter`/`apply_filters`), invocada por
`service/curate.py:filter_corpus`.

El único paper que hoy el filtro **excluye del set a rechazar** es el que **ya está** `rejected` (para
no re-rechazarlo). Un paper `accepted` **manualmente** que no cumple el criterio **sí** es candidato a
`rejected`. Ese es el hallazgo de #233: un filtro masivo pisó, sin aviso, dos decisiones de inclusión
humanas.

Esto contradice dos principios ya registrados:

1. **La curación es lo irreductiblemente humano** (ADR [0016](0016-maquina-estados-lazo.md), enmienda
   2026-06-15, §3): `accept`/`reject` son la decisión que el sistema **no** toma por el investigador.
   Un `accepted` es una afirmación explícita de "este entra".
2. **Honestidad y determinismo, sin decisiones silenciosas** (Nota 22 / ADR
   [0022](0022-producto-sin-ia-generativa.md)): un criterio automático que revierte, sin señal, una
   inclusión humana es exactamente el tipo de sorpresa que el motor determinista no debe producir.

La pregunta abierta: **cuando un criterio masivo alcanza a un paper `accepted` a mano, ¿quién gana?**

## Decisión

**La inclusión manual gana: `curate filter` NUNCA mueve un paper `accepted` → `rejected`.**

- El filtro actúa **solo** sobre papers **no aceptados** (estado `candidate` y demás no-aceptados). Un
  paper con `curation_status='accepted'` queda **intacto** aunque no cumpla el criterio del filtro; el
  filtro lo **omite** del conjunto a rechazar (igual que ya omite a los `rejected`).
- **Racional:** coherente con "el humano decide la inclusión" (Nota 22) y con la curación como acto
  irreductiblemente humano (ADR 0016 §3). Un filtro masivo es una herramienta de **cribado del
  candidato**, no un mecanismo para revertir inclusiones humanas explícitas. La aceptación manual es
  una señal de mayor autoridad que un criterio de barrido.
- **Alcance:** esta decisión fija la **política de precedencia** del verbo `curate filter`. **No**
  toca su transición (`curate filter`→`FILTERED`, ADR 0037 D2), ni el marcado `rejected`-no-borra (ADR
  0020 §C), ni el conteo PRISMA por paso, ni el determinismo del filtro.
- **Nota de trabajo futuro (NO parte de esta decisión):** si más adelante hiciera falta un *reset
  duro*, la evolución natural del default seguro sería un flag **`--force` explícito** que permita al
  filtro rechazar `accepted` **con aviso accionable** (p. ej. *"N accepted fueron rechazados por el
  criterio X: …"*). Se deja **mencionado como evolución posible**, no decidido aquí; requeriría su
  propio encuadre (y probablemente una precisión de contrato en `docs/API.md`).

## Consecuencias

- **Se cierra el footgun de #233.** Ningún `curate filter` puede revertir una inclusión humana en
  silencio. El default es **seguro por construcción**: lo que el investigador aceptó, se queda.
- **El conteo PRISMA sigue siendo honesto.** `count_before`/`count_after` ya se computan sobre los
  papers **no-rejected** (candidate + accepted, ADR 0020 §C / `API.md` §curate); con esta decisión los
  `accepted` simplemente **nunca abandonan** ese conjunto por efecto de un filtro. El reporte de
  cribado describe qué se excluyó del **candidato**, que es lo que PRISMA quiere contar en la etapa de
  screening.
- **La reversibilidad se conserva** (ADR 0009/0013): si el investigador **quiere** que un `accepted`
  salga, lo hace explícito con `curate reject --ids ...` — decisión humana registrada en `provenance`,
  no efecto lateral de un barrido.
- **Determinismo intacto** (ADR 0022): el filtro sigue siendo función pura y reproducible; solo cambia
  el conjunto sobre el que puede marcar `rejected` (excluye `accepted`, como ya excluía `rejected`).
- **Costo / trade-off:** un usuario que **sí** quisiera un cribado destructivo total (rechazar todo lo
  que no cumpla, incluido lo aceptado) hoy **no** tiene un atajo masivo; debe rechazar a mano los
  `accepted` que quiera sacar. Es el costo aceptado del default seguro, y es exactamente el hueco que
  el futuro `--force` (arriba) cubriría si la necesidad aparece.
- **`docs/API.md` a precisar en la implementación.** La sección de `curate filter` (§curate y las
  "Notas de contrato" del ADR 0020) debe declarar que el filtro **omite `accepted`**. *Esa edición es
  trabajo del `coder` al implementar #233, no parte de este ADR* (coherente con cómo 0037/0038 dejaron
  la edición de `API.md` para el hito de implementación).

### Recomendación para el `coder` (implementación de #233)

**Archivo/símbolo:** `src/bib2graph/filters/prisma.py:179-184` (`apply_filter`, construcción de
`ids_to_reject`).

**Cambio:** hoy el guard excluye solo `CurationStatus.REJECTED`; sumar la exclusión de
`CurationStatus.ACCEPTED` para que el filtro **omita** los aceptados:

    ids_to_reject = [
        str(row[Col.ID])
        for row in rows
        if row.get(Col.CURATION_STATUS)
           not in (CurationStatus.REJECTED, CurationStatus.ACCEPTED)   # ← accepted intocable
        and not _passes(row, criterion)
    ]

- **Test (TDD, ancla la semántica):** corpus con un paper `accepted` que **no** cumple el criterio
  (p. ej. `year=2005` con `--year-gte 2010`) → tras `curate filter` sigue `accepted` (no pasa a
  `rejected`); un paper `candidate` que no cumple sí pasa a `rejected`. Regresión directa del #233
  sobre `examples/valoraciones/`.
- **`filter_corpus`** (`service/curate.py:391`) no necesita cambio: consume la lógica pura de
  `prisma.py`. Verificar que el conteo PRISMA por paso sigue coherente (los `accepted` ya estaban del
  lado `count_before`/`count_after`).

## Alternativas

- **Avisar / requerir `--force`** (el filtro **puede** rechazar `accepted`, pero emite advertencia
  accionable —"N accepted fueron rechazados: …"— y/o exige `--force`). **Rechazada como default:** sigue
  permitiendo la **pérdida silenciosa** si el usuario no lee la advertencia, y `exit 0` con salida
  masiva es fácil de no leer (justo el modo de fallo de #233). La **idea del `--force`** se **reserva**
  como evolución futura del default seguro (ver "Nota de trabajo futuro"), no como comportamiento por
  omisión.
- **Conducta actual (el filtro pisa `accepted` por diseño), solo documentarla.** **Rechazada:** es el
  footgun mismo — máximo riesgo de pérdida silenciosa de decisiones humanas, y contradice de frente la
  Nota 22 (honestidad/determinismo) y el ADR 0016 §3 (la curación es lo irreductiblemente humano).
  Documentar un comportamiento peligroso no lo hace seguro.
