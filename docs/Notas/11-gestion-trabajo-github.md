# Gestión del trabajo en GitHub — propuesta de superficie única

> Nota de trabajo. Captura la decisión de **dónde vive qué** entre el repo y GitHub
> (Issues / Project / Discussions) para evitar duplicación entre `docs/ROADMAP/` y la
> superficie de GitHub. Fecha: 2026-06-16. Estado: **propuesta a discutir con el PO**,
> no implementada aún.

## Motivación

El repo `bib2graph` carga con una disciplina fuerte de planificación versionada
(`docs/ROADMAP/`, `docs/decisiones/`, `docs/Notas/`, `CHANGELOG.md` manejado por
`release-please`, ramas `dev`/`main`, PRs por idea). El plan en markdown vive con el
código, es diffable, lo lee un agente al abrir el repo, y se actualiza en el mismo
PR que toca el dominio.

A la vez, GitHub ofrece una **superficie de trabajo** que el repo no tiene: estado
mutable, asignado, board visual, suscripciones, menciones, vínculos nativos a PRs y
commits. La pregunta que destraba esta nota es: **¿reemplazamos el `docs/ROADMAP/`
por GitHub, lo espejamos, o lo dejamos como está y usamos GitHub para otra cosa?**

## Lo que hace bien cada lugar

**`docs/ROADMAP/` en el repo (markdown versionado):**
- Vive con el código; un PR que cambia el dominio puede traer su sección de roadmap
  actualizada en el mismo diff.
- Se linkea desde cualquier lado (CI, ADRs, docstrings, issues, README).
- Diffable, grepeable, anclable (permalinks por línea, mismo hash para siempre).
- Renderiza en GitHub sin nada extra.
- Es la **única fuente** que un agente/LLM puede leer para entender qué viene.

**GitHub Issues / Project / Discussions:**
- Estado mutable (abierto/cerrado, asignado, prioridad, columna en board).
- Vinculación nativa a PRs y commits (`Closes #N`, `Fixes #N`).
- Notificaciones, menciones, `@`-asignaciones, code review.
- Vistas filtrables y agrupables (Roadmap, Backlog, Por Área).
- Sirven para **conversar, asignar, trackear avance de una unidad de trabajo**.

Las dos superficies son **diferentes en naturaleza**, no versiones distintas de lo
mismo:

- **ROADMAP** = qué hay que hacer y por qué (plan, cuasi-inmutable, declarativo).
- **Issues/Project** = quién lo está haciendo, en qué estado está, cuándo se cierra
  (trabajo, mutable, operativo).

## Las tres estrategias y por qué solo una sobrevive

### A. Reemplazo total

Borrar `docs/ROADMAP/`, mover todo a Issues/Project de GitHub.

- ❌ Pierde el anclaje código↔plan: un PR que toca el dominio no puede actualizar el
  plan en el mismo diff.
- ❌ Los ADRs (`docs/decisiones/`) referencian el plan y los links a issues son
  frágiles (sin permalinks a líneas concretas, rotos si el repo se mueve).
- ❌ Un agente que abre el repo para entender el dominio no ve "qué viene" sin
  además consumir la API de GitHub.
- ❌ Conclusión: te dejás sin plan, solo con tareas.

### B. Espejo

`docs/ROADMAP/` + Project de GitHub en paralelo, ambos describen lo mismo.

- ⚠️ Funciona, pero **solo si una de las dos superficies es derivada** de la otra
  y hay un sync explícito.
- ⚠️ Sin sync, diverge en ~2 semanas (siempre).
- ⚠️ Es la respuesta conservadora cuando no se anima a una a elegir.

### C. Plan en repo, trabajo en GitHub *(propuesta)*

- `docs/ROADMAP/` = plan. **Fuente de verdad del plan.** Describe el DoD de cada
  hito, qué historias del PRD §7 cumple, qué tests TDD se escriben.
- GitHub Issues = unidades de trabajo **abiertas cuando se empieza** el hito, no
  planeadas todas de antemano. 1 issue por hito, body = checklist del DoD
  copiada del ROADMAP.
- GitHub Project = board operativo (Status, Hito, Área, Prioridad) — derivado de
  los issues, no del ROADMAP.
- GitHub Discussions = conversaciones y red-teams futuros (categoría "Red-team /
  crítica"). Las futuras `docs/Notas/07-…md` arrancan como Discussion con el .md
  como cuerpo y el ADR/fix de cierre se linkea como comentario fijado.
- Hechos retroactivos (hitos ya cerrados) viven en `CHANGELOG.md` y en los tags.
  **No se duplican en GitHub.**

Con C: **cero duplicación**, **cero sync**. El ROADMAP dice el DoD; el issue dice
"estoy trabajando en esto y voy por la checklist". Una fuente decide, la otra
apunta.

## La pregunta que destraba

**¿El ROADMAP describe trabajo planeado a futuro, o describe trabajo en curso?**

- **Planeado a futuro** (Hito 9, 10+): es plan, no trabajo. Vive en `docs/`. Los
  issues se abren **al arrancar** el hito, no antes.
- **En curso** ahora mismo: es trabajo, debería ser un issue abierto. El
  `docs/ROADMAP/` se reduce a la "historia" (por qué existió cada hito, qué PRD
  cumple), no al estado actual.

En este repo es **lo primero**: el Hito 9 está documentado en
`docs/ROADMAP/hito-09-…md` con DoD, no hay issue, no se está trabajando en él
ahora. Eso es **plan**, no **trabajo**.

## Propuesta concreta

1. **No tocar `docs/ROADMAP/`.** Es plan. Diffable, vive con el código, lo lee un
   agente al abrir el repo. El PO lo actualiza en el mismo PR que toca el dominio
   si hace falta.
2. **No migrar nada retroactivo.** No crear issues "Hito 8" ya cerrado. Está en el
   `CHANGELOG.md` y en los tags (`v0.3.0`, etc.).
3. **Al arrancar el Hito 9 (y siguientes):** abrir **un** issue por hito con
   título `[Hito N] <título corto>`, body = checklist copiado del DoD de
   `docs/ROADMAP/hito-NN-…md`, label `hito-N`, milestone del próximo tag.
4. **Project de GitHub repo-linked** con campos mínimos: **Status** (Todo /
   In progress / In review / Done), **Hito** (9, 10, 11, 12+), **Área** (corpus,
   sources, foraging, preprocessors, filters, enrichers, networks, exporters,
   stores, cli, docs), **Prioridad** (P0/P1/P2). Vistas: **Roadmap** (agrupada
   por Hito, columnas Status), **Backlog** (filtro `Status=Todo`), **Por Área**.
5. **PR template** (`.github/PULL_REQUEST_TEMPLATE.md`) con sección `## Project`
   que pida Hito, Área y `Closes #N`. Regla de agente: al abrir el PR, mover el
   item a **In progress**; al mergear, a **Done**.
6. **Discussions** activadas con categoría **Red-team / crítica** (Discussion, no
   Q&A). Las futuras `docs/Notas/07-…md` arrancan como Discussion con el .md como
   cuerpo; el ADR de cierre se linkea como comentario fijado.
7. **Reglas de uso** documentadas en `AGENTS.md` o `CONTRIBUTING.md` (corto,
   un párrafo): "un issue por hito en curso, abierto al arrancar; body = checklist
   del DoD; cierre en CHANGELOG + tag vía release-please".

## Lo que se gana / se pierde

**Ganas:**
- Una sola fuente de verdad por tipo de cosa (plan en `docs/`, trabajo en
  GitHub).
- Cero sync, cero duplicación.
- El repo se entiende solo, sin tener que mirar GitHub.
- El plan queda versionado con el código que describe.
- Board visual sin overhead de plan paralelo.

**Perdés:**
- La ilusión de que "todo está en GitHub". No lo está ni debería: GitHub es la
  **superficie de trabajo**, el repo es la **superficie de conocimiento**.
  Mezclar las dos te cuesta.
- El "camino recorrido" en el board. Compensa con `CHANGELOG.md`, tags y
  releases de GitHub, que son la memoria histórica del proyecto.

## Riesgos y cosas a vigilar

- **`gh project` en user namespace con link a repo** funciona, pero algunos
  automatismos nativos (auto-add de PRs al Project) requieren que el repo esté
  en la **misma org** que el Project. Como el Project será user-owned, los PRs
  se agregan al Project **a mano** en el PR template, o vía una Action custom
  (`gh-project-sync.yml`).
- **PR template**: si ya existe, mergear el cambio en vez de pisarlo.
- **Discussions**: requiere que el repo las tenga habilitadas (Settings → General
  → Discussions); activarlas antes de crear la categoría.
- **Migrar retroactivos dispara notificaciones**: al no migrar, este riesgo
  desaparece.

## Orden de ejecución propuesto

1. `gh auth refresh -s project` (un solo vez, si el token no tiene el scope).
2. Activar Discussions (UI) y crear la categoría **Red-team / crítica** (UI).
3. `gh project create --owner <USER> --title "bib2graph roadmap"` y
   `gh project link <N> --owner <USER> --repo bib2graph`.
4. `gh project field-create` × 3 (Status, Hito, Área, Prioridad).
5. Crear las tres vistas en la UI de GitHub (no hay CLI para vistas compuestas).
6. Editar el PR template (merge si ya existe, no pisar).
7. Agregar un párrafo con la regla de uso en `AGENTS.md` (cerca de la sección
   "Flujo de trabajo").
8. **Hito 9**: abrir el primer issue siguiendo la convención
   `[Hito 9] <título>`, body con checklist del DoD, label `hito-9`, milestone
   `v0.4`.

## Cierre

La propuesta evita el camino conservador del espejo y el camino riesgoso del
reemplazo. La regla de oro es: **lo que describe trabajo futuro vive en el repo
porque es plan; lo que describe trabajo en curso vive en GitHub porque es
operación.** Ninguno de los dos necesita al otro para existir, pero el link
entre ambos (`Closes #N` en el PR, link al issue en el body del hito cuando se
arranca) hace que el board y el roadmap cuenten la misma historia sin
duplicarse.
