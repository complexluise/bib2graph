# 29 — Jubilar `docs/Notas/`: debate a Discussions, histórico a Wiki, contrato queda en el repo

> **Estado:** propuesta, pendiente de revisión del PO (2026-07-01).
> **Naturaleza:** Nota de propuesta. **No es ADR todavía** — el ADR baja después de
> revisarla. Esta nota documenta el cambio **antes** de ejecutarse porque rompe una
> convención del repo (la existencia misma de `docs/Notas/` como superficie viva).
>
> ⚠️ **BREAKING CHANGE.** Aunque no toca código, cambia:
> - la convención de género (Notas-archivo jubilan, debate va a Discussions);
> - el estado de ADRs vigentes (0032/0033 → Rechazadas; 0035 → Aceptada en el índice);
> - la ruta de `docs/metodologia.md` (sale de `docs/Notas/`, vive en `docs/`);
> - la existencia de 6 archivos (`NO-HACER-COMMIT-*` se borran);
> - la creación de 4 Discussions y 3 categorías de Wiki que no existían.
>
> Por todo esto se documenta como breaking en el commit (`BREAKING CHANGE:` en el footer
> del commit o `feat!:`), independientemente de que no toque código.

## 1. El problema

`docs/Notas/` acumula **31 Notas + 6 borradores + 3 documentos de glosario/método**.
Para un investigador o desarrollador nuevo en el repo:

- No sabe **cuál es contrato, cuál es debate, cuál es histórico, cuál es borrador**.
- Están mezcladas con la doc viva (`docs/API.md`, `docs/ARCHITECTURE.md`, `docs/PRD.md`).
- Algunas son densas y narrativas (`Nota 18 — flujo canónico de biblioteca`,
  `Nota 28 — marco de software`), pensadas para que el PO debata consigo mismo, no para
  que un dev nuevo las lea.
- Las más viejas (07, 08, 10, 12, 16) son de la era GUI local — ya **supersedidas por
  ADR 0040 (retiro de la GUI)** — pero siguen vivas en disco.

Sumado a eso:

- Hay **4 ADRs en estado Propuesta** (0032, 0033, 0034) que perdieron su consumidor con
  el retiro de la GUI local (0040). Zombies.
- Hay **2 ADRs perdidos del filesystem** (0042, 0044) que existen en git pero no están
  en el árbol actual. Drift.
- Hay **5 Notas que encierran debates vivos** (22 frontera, 25 multi-proveedor,
  27 recibo de demo, 28 posicionamiento, 23 retroalimentación agente) que merecen un
  hogar mejor que `docs/Notas/`.

## 2. La dirección

Reencuadre de la partición de géneros (que hoy está implícita en la skill `flujo` y se
vuelve explícita acá):

| Género | Dónde vive hoy | Dónde vive mañana | Por qué |
|---|---|---|---|
| Contrato del producto (qué hace) | `docs/API.md`, `docs/ARCHITECTURE.md`, `docs/PRD.md` | igual | Se mueve en lockstep con el código; PR + CI obligatorio |
| Decisión (por qué) | `docs/decisiones/0001–0043` | igual | Inmutable, citado desde código y otros docs |
| Plan / roadmap | `docs/ROADMAP/` | igual | Cambia con cada hito |
| Reglas del repo | `CONTRIBUTING.md`, `AGENTS.md` | igual | Cómo se trabaja; cómo contribuyen humanos y agentes |
| **Debate vivo (tensión, propuesta)** | **`docs/Notas/` (mezclado)** | **GitHub Discussions (con encabezado estándar)** | Las Discussions viven en el lugar donde realmente se debate; pueden cerrarse sin dejar basura en el repo |
| **Mapa / onboarding / glosario / historia** | **`docs/Notas/` (mezclado)** | **GitHub Wiki** | Estable, narrativo, no requiere PR |
| **Historial / rastro muerto** | **`docs/Notas/` (mezclado)** | **`docs/_archivo/` con `.no-commit`** (no versionado) | Cosas que el PO ya no quiere vivas pero no quiere borrar |
| Borradores del PO | `docs/Notas/NO-HACER-COMMIT-*` | **borrar** | No son notas; son work-in-progress |

**La regla "no se crean Notas-archivo nuevas" se mantiene — pero la práctica de crearlas
se jubila.** Las que existen, se mueven.

## 3. Lo que cambia

### 3.1. Estructura de carpetas del repo

```
docs/
├── PRD.md                     (sin cambios)
├── ARCHITECTURE.md            (sin cambios)
├── API.md                     (sin cambios)
├── ROADMAP/                   (sin cambios)
├── decisiones/                (sin cambios en estructura)
│   ├── README.md              (3 filas actualizadas: 0032/0033 Rechazadas, 0035 Aceptada)
│   ├── 0001–0043.md           (0032 y 0033 marcados como Rechazada — Supersedida por 0040)
│   └── 0034-etiquetado-tabla-tags-lateral.md   (nota de estado agregada: "referencia técnica reusable")
├── metodologia.md             (movido desde docs/Notas/, vive en docs/ como autoridad de método)
├── Notas/                     (jubilada — ver §3.2)
└── _archivo/                  (NUEVO — ver §3.2)
    ├── .no-commit             (sentinel: explica que esto no se versiona)
    └── notas/                 (todo el contenido de docs/Notas/ movido acá, sin selección)
```

### 3.2. Destino de `docs/Notas/` — todo se mueve, la selección se hace después

`docs/Notas/` se mueve **completo** a `docs/_archivo/notas/` con `mv` (preservando historia
via git). Esto incluye las 31 notas, los 6 borradores `NO-HACER-COMMIT-*`, los subdirectorios
`02-exploracion/` y `03-referencia/`, y los 3 docs sueltos (`critica-base.md`,
`metodología.md`, `referentes.md`).

**No se hace selección manual acá.** El criterio rector es: si el PO (o quien revise)
quiere resurrectar algo, está en `_archivo/`. La selección fina de qué sube al Wiki o a
Discussions se hace en una segunda pasada, con tiempo, no en bloque.

Después del movimiento:

- `docs/metodologia.md` se **extrae de `_archivo/notas/`** y se mueve a `docs/metodologia.md`
  como documento vivo (autoridad de método). Es la única Nota que vive en el repo porque
  su rol es ser referencia de método, no contrato ni debate.
- Las **reglas duras** de la `Nota 01 — lecciones de v0` se **extraen** a `CONTRIBUTING.md`
  y `AGENTS.md` (ya están citadas en ambos; la nota se borra de `_archivo/notas/` si su
  contenido ya vive en otra parte).
- Los **6 borradores `NO-HACER-COMMIT-*`** se **borran** de `_archivo/notas/`. No eran
  notas, eran work-in-progress del PO.

### 3.3. ADRs zombies

Los ADRs 0032, 0033, 0034 son Propuesta de la era GUI y perdieron su consumidor con el
retiro de la GUI local (0040):

- **0032 (`capa-servicios-duena-del-flujo`)** → estado cambia a **"Rechazada — Supersedida
  por 0040"**. Encabezado: 1 línea. Cuerpo: 1 bloque de Enmienda fechado (3 líneas)
  explicando que la GUI murió y `service/` se conserva parcialmente.
- **0033 (`producto-library-centric-grafo-proyeccion`)** → mismo tratamiento. La idea
  "BIBFRAME fuera" sobrevive como decisión implícita; se anota en `docs/metodologia.md`
  si el PO lo decide (no requiere ADR propio).
- **0034 (`etiquetado-tabla-tags-lateral`)** → se queda como **Propuesta-referencia
  técnica**. Una línea en el bloque de estado: "Referencia técnica para tablas laterales
  (`referenced_but_not_fetched`, `loop_state_log`); no se promueve porque el consumidor
  (GUI) murió. BUG-2 (extensibilidad del schema) queda como decisión abierta del PO."

El `docs/decisiones/README.md` se actualiza con 3 líneas: 0032 → Rechazada, 0033 →
Rechazada, 0035 → Aceptada (drift menor del índice).

### 3.4. ADRs perdidos del filesystem (0042, 0044)

- **0042 (Semantic Scholar como 2º motor)** — existe en commit `a27aa09`, no está en el
  árbol actual, README sí lo lista. **Decisión propuesta: dejarlo así.** El código
  existe, los issues referencian el número. Si alguien reporta fricción, se recupera en
  una PR de hygiene aparte. **No incluir en este cambio** (sería inflar el breaking
  change).
- **0044 (precedencia de inclusión manual en curate)** — existe en commit `3417c68`,
  mismo caso. Misma decisión: dejar así.

### 3.5. Discussions nuevas — el nuevo hogar del debate vivo

Se abren **4 Discussions** con un encabezado estándar que las haga útiles como referencia
futura:

```markdown
## Pregunta

[Una pregunta concreta, no un resumen de la Nota]

## Contexto

Esta discusión nace de `docs/Notas/NN-titulo.md` (archivado en `docs/_archivo/notas/`).
[5–10 líneas de la tensión]

## Si esta discusión converge, qué cambia

- ADR nuevo (¿#XXXX?) con la decisión formal, O
- Cerrar como "no resuelve" sin ADR

## Estado

- [ ] Discusión abierta
```

Las 4 Discussions que se abren:

1. **"Frontera de producto: ¿qué entra y qué no en bib2graph?"** — origen `Nota 22`.
   Tensión: bib2graph como herramienta vs como suite. Cierra el hueco que ningún ADR
   fija con esa claridad (0022 cubre "sin IA"; 0008 cubre forrajeo; "no interpreta, no
   gestiona investigación" no está).
2. **"Multi-proveedor: cómo priorizar el 2º motor y la capa Sur-global"** — origen
   `Nota 25`. Tensión: S2 vs DOAJ vs SciELO vs CrossRef; el probe empírico ya hizo la
   criba pero el orden de implementación no está.
3. **"Extensión de `maturity`: `crossed_red` / `assumed_judgment` / `orphans`"** —
   origen `Nota 27`. Tensión: el bloque `maturity` actual (`curated`, `scope`,
   `saturated`, `empty_networks`) ya está documentado en `docs/API.md`;该不该 extenderlo
   con recibos de juicio humano.
4. **"Posicionamiento de bib2graph: ¿qué tradiciones reivindicamos?"** — origen
   `Nota 28`. Tensión: 5 pilares (FCIS, Hexagonal, build hermético, Unix-for-agents,
   tools-for-thought determinista); §2-bis de calibración honesta (build hermético =
   solo dirección por contenido, no cache-hit; hash plano no Merkle; CLI fail-open
   advisory).

### 3.6. Wiki — el nuevo hogar de lo narrativo

Se crean **3 categorías** en el Wiki del repo (la Wiki está habilitada):

- **Wiki / Historia** — `Nota 04` (dirección IA-in-the-loop), `Nota 06` (red-team v0.2),
  `Nota 07/08/10/12/16` (era GUI), `Nota 13/14/15/17/19` (QA/sesión). Son rastros del
  proceso.
- **Wiki / Papers en progreso** — `Nota 20_ciclo_investigacion_hallazgos_teoricos`,
  `Nota 24_referente-snowballing-comparacion`. Son insumos del paper que el PO está
  escribiendo.
- **Wiki / QA / footguns** — tabla consolidada de bugs footgun-invisible encontrados en
  sesiones (extraídos de las Notas de QA).

## 4. Por qué es BREAKING (aunque sea docs)

- **Cambia la convención de género.** Cualquier nota o debate futuro que se hubiera
  puesto en `docs/Notas/` ahora va a Discussions. Es un cambio de flujo de trabajo, no
  solo de archivos.
- **Borra 6 archivos** (`NO-HACER-COMMIT-*`). Aunque sean borradores, son archivos que
  existían en disco.
- **Mueve archivos a una carpeta no versionada** (`docs/_archivo/`). Un dev que espera
  encontrar todo en git se va a sorprender.
- **Cambia el estado de ADRs vigentes** (0032, 0033 → Rechazadas; 0035 → Aceptada en el
  índice). Quien referencie estos ADRs por nombre debe saber que ya no son propuestas
  activas.
- **Abre 4 Discussions y crea 3 categorías de Wiki** que no existían. La fricción para
  el PO es administrativa (crear las Discussions manualmente o vía API).

Por todo esto **debe documentarse como breaking en el commit** (`BREAKING CHANGE:` en
el footer del commit o `feat!:`), independientemente de que no toque código.

## 5. Lo que NO se hace (explícito)

- **No se borra `docs/Notas/`** — se mueve a `_archivo/`.
- **No se borran los ADRs zombies** — se marcan como Rechazados.
- **No se crea** ADR 0045 (frontera) ni 0046 (posicionamiento). Esas ideas van a
  Discussions; si convergen, recién bajan a ADR.
- **No se recuperan** los ADRs 0042 y 0044 perdidos del filesystem. Si alguien reporta
  fricción, se hace en una PR aparte.
- **No se toca código.** Es 100% docs.
- **No se hace selección fina de qué sube a Wiki** en este pase. La selección se hace
  en una segunda iteración, con tiempo.

## 6. Plan de ejecución (cuando el PO apruebe esta Nota)

5 PRs + apertura/cierre de Discussions, todos `docs/chore`, ninguno toca código:

| # | PR | Archivos | Tipo |
|---|---|---|---|
| 1 | `chore(docs)!: jubilar docs/Notas/ → docs/_archivo/notas/` | ~37 movidos + 6 borrados + 1 sentinel | `chore!` (breaking) |
| 2 | `docs(adr)!: rechazar 0032/0033 (Supersedidas por 0040) + fix README 0035 + nota en 0034` | 4 archivos | `docs!` (breaking en docs vivos) |
| 3 | `docs(meta): tabla de géneros de documentación en AGENTS.md` | 1 archivo | `docs` |
| 4 | `docs(meta): extracto de reglas duras de la Nota 01 a CONTRIBUTING.md` | 1 archivo | `docs` |
| 5 | `docs!: extraer docs/metodologia.md desde _archivo/notas/` a `docs/metodologia.md` (autoridad de método)` | 1 archivo movido + refs actualizadas | `docs!` (cambio de path) |

Y fuera de PRs:

- 4 Discussions abiertas (vía `gh` o web UI).
- 3 categorías de Wiki creadas.

**Orden sugerido:** PR 1 (mover Notas) → PR 2 (rechazar zombies) → PR 5 (`metodologia`)
→ PR 3 (AGENTS) → PR 4 (CONTRIBUTING). Cada PR es independiente en archivos, no hay
conflictos entre ellos.

## 7. Riesgos y rollback

- **Riesgo 1:** un dev nuevo busca una Nota específica y no la encuentra en
  `docs/Notas/`. **Mitigación:** el README y `AGENTS.md` explican la nueva partición; el
  `_archivo/` está local (no requiere red) para quien quiera consultar.
- **Riesgo 2:** los ADRs rechazados (0032/0033) se referencian desde código o docs como
  si siguieran vigentes. **Mitigación:** buscar refs antes de cerrar el PR; actualizar
  las refs para que apunten al ADR que sí está vigente.
- **Riesgo 3:** la Wiki está habilitada pero las categorías requieren crear páginas
  manualmente. **Mitigación:** si crear las 3 categorías resulta engorroso, basta con
  crear las páginas vacías con un índice que apunte a las Discussions.
- **Rollback:** todos los cambios son revertibles con `git revert`. `_archivo/` es local
  pero el contenido sigue en git hasta el merge.

## 8. Preguntas abiertas para el PO

1. Las 4 Discussions se abren **antes** del movimiento de Notas (para que las Notas
   referencien Discussions vivas) o **después** (para que las Discussions referencien
   las Notas archivadas)? — **Decidido:** mantener 2 Discussions separadas (Frontera y
   Posicionamiento son debates distintos, no se fusionan).
2. ¿Las categorías de Wiki se crean como páginas vacías con índice, o se sube el
   contenido de las Notas relevantes directamente? — **Decidido:** Wiki habilitada, se
   crean las 3 categorías.
3. La extracción de la `Nota 01` a `CONTRIBUTING.md` y `AGENTS.md` — ¿se hace como
   parte de este breaking (PR 4) o se difiere a una PR aparte (menos superficie de
   cambio)? — **Pendiente.**
4. ¿Se mantiene el número `29` para esta Nota (siguiente correlativo) o se usa otra
   convención dado que la Nota se archiva a sí misma? — **Decidido:** `29`, siguiente
   correlativo. Es la última Nota que se mueve.

## 9. Meta

Esta es la **última Nota-archivo que se escribe en `docs/Notas/`**. Después de aprobada
y ejecutada, la carpeta se mueve completa a `docs/_archivo/notas/` y la convención
cambia para siempre: cualquier debate futuro va a GitHub Discussions primero; si
converge en decisión firme, baja a ADR; si no, queda como Discussion cerrada. La
práctica de crear Notas-archivo se jubila junto con la regla que la prohíbe.

La Nota en sí se archiva en `docs/_archivo/notas/29-…md` después de ejecutarse — meta:
una Nota que se archiva a sí misma.