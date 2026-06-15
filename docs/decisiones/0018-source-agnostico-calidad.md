# 0018 — Contrato `Source` agnóstico (mínimo universal vs enriquecimiento opcional) + reporte de calidad declarado

- **Estado:** Aceptada
- **Fecha:** 2026-06-15
- **Relacionada con:** [0004](0004-enriquecimiento-opcional.md) (enriquecimiento opt-in),
  [0007](0007-openalex-backbone.md) (OpenAlex backbone),
  [0017](0017-reproducibilidad-historia-snapshot.md) (snapshot + `openalex_version`)

## Contexto

El contrato `Source` (API.md §2) y el schema del `Corpus` (API.md §1.1) están **modelados con la
forma de OpenAlex**: dan por hecho que toda fuente entrega `references_id`, `cited_by_id` y
afiliaciones per-autor. Eso es cierto para OpenAlex (ADR 0007), pero **excluye de facto** a las
fuentes latinoamericanas que el proyecto quiere habilitar — **SciELO, Redalyc, La Referencia** —
que típicamente entregan metadatos básicos (título, autores, año, keywords) pero **no** listas de
referencias resueltas ni citantes ni afiliaciones estructuradas.

Si el contrato obliga a entregar todo, una `Source` regional queda fuera o se ve forzada a
fabricar datos que no tiene. La crítica de fondo: el contrato confunde **lo que un corpus
necesita para existir** con **lo que OpenAlex casualmente provee**.

Relacionado: cuando un corpus se siembra de una fuente parcial, el **ranking por information
scent** (ADR 0008) opera sobre datos incompletos, y el investigador necesita saber **cuándo
cambiar de Source**. Hoy no hay forma de medir esa incertidumbre.

## Decisión

### A. Contrato `Source` agnóstico: mínimo universal vs enriquecimiento opcional

El contrato `Source` separa explícitamente:

- **Mínimo universal** (toda `Source` debe entregar): `id`, `title`, `year`, `authors`
  (`authors_raw`), `keywords` (`keywords_raw`). Es lo que hace que un paper exista en el corpus y
  habilita ya las redes de **co-autoría** y **co-ocurrencia de keywords**.
- **Enriquecimiento opcional** (una `Source` puede o no entregarlo): `references_id` /
  `references_doi`, `cited_by_id`, afiliaciones **per-autor** (`authors_affiliations`),
  `institutions_id`. Habilita acoplamiento, co-citación, redes de instituciones y asortatividad
  geográfica.

El schema del `Corpus` **ya admite nulos** en las columnas de enriquecimiento (API.md §1.1): el
cambio es de **contrato y expectativa**, no de schema. Una `Source` que solo provee el mínimo es
**ciudadana legítima**; los proyectores que dependen del enriquecimiento simplemente producen
redes vacías/parciales sobre los papers sin esos datos (y lo reportan, ver B).

Esto habilita **SciELO / Redalyc / La Referencia** como `Source` sin obligarlas a entregar lo que
no tienen. *(El contrato se declara en v0.1; las implementaciones de fuentes nuevas son
posteriores — futuras, marcadas como no implementadas, lección 5.)*

### B. Reporte de cobertura/calidad declarado (concreto v0.2+)

Se declara el **concepto** de un **reporte de cobertura/calidad por seed/source**: % de
referencias resueltas, % con DOI, distribución por idioma/región, completitud de los campos de
enriquecimiento. Ese reporte:

- alimenta el **juicio humano de cuándo cambiar de Source** (p. ej. "SciELO me dio cobertura pero
  0% de referencias; para acoplamiento necesito OpenAlex");
- **acota la incertidumbre del ranking por information scent** cuando opera sobre datos parciales;
- se cruza con el `openalex_version` / ausencia de ancla de versión (ADR
  [0017](0017-reproducibilidad-historia-snapshot.md)).

El **contrato `Source` agnóstico (A) se declara y se respeta en v0.1**; el **reporte concreto (B)
se implementa en v0.2+** (no se cablea vacío ahora — lección 5).

## Consecuencias

- **El núcleo deja de asumir la forma de OpenAlex.** Las redes baratas (co-autoría, co-word)
  funcionan con el mínimo universal; las caras (acoplamiento, co-citación, instituciones)
  dependen del enriquecimiento, que ya era opt-in (coherente con ADR 0004 y 0007).
- **Se abre la puerta a fuentes regionales** sin tocar el núcleo (cumple el criterio del PRD §10:
  "agregar una nueva `Source` no requiere modificar el núcleo").
- **El reporte de calidad da consciencia sobre datos parciales** ("fácil pero consciente"): el
  investigador sabe qué le falta antes de leer una red como verdad.
- **Costo:** ajustar API.md §2 (declarar mínimo vs enriquecimiento) y documentar que los
  proyectores de enriquecimiento degradan a parcial (no fallan) sobre fuentes mínimas. El reporte
  concreto es trabajo de v0.2+.
- **Recomendación para el `coder`:** en el **Hito 4**, `OpenAlexSource` sigue entregando todo
  (mínimo + enriquecimiento); el contrato `Source` (Protocol, API.md §2) documenta qué es
  obligatorio y qué opcional. El reporte de calidad (función pura sobre `pa.Table`) cae en el
  **Hito 5+** y se declara, sin implementarse, en la API hasta entonces.
