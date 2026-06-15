# 0009 — Biblioteca viva stateful en DuckDB como núcleo; el snapshot pasa a export

- **Estado:** Aceptada
- **Fecha:** 2026-06-15
- **Relacionada con:** [0006](0006-tabla-canonica-y-networkspec.md),
  [0007](0007-openalex-backbone.md)
- **Supersede (parcialmente):** el **`InMemoryStore` por defecto** de
  [0003](0003-persistencia-opcional.md) y el **"snapshot inmutable, sin in-memory store"** de
  [0006](0006-tabla-canonica-y-networkspec.md). El resto de 0006 (tabla Arrow + Pydantic,
  NetworkSpec, tooling/semver) **sigue vigente**.

## Contexto

El giro (Nota 04 §3) define el corpus como una **biblioteca viva y curada** que **se cultiva en
el tiempo** (*berry growing*; Nota 05 §2 bonus, *Information Farming*, arXiv 2601.12544), **no**
como el export de una sola corrida. El ciclo humano es **iterativo** (Nota 05 §3): la idea muta
y se vuelve a sembrar **acumulando sobre lo ya curado**.

El diseño previo asumía lo contrario: corpus **sin estado**, con `InMemoryStore` por defecto
(ADR 0003) y **snapshot inmutable** sellado por corrida (ADR 0006). La Nota 04 §6.2 marcó esta
tensión como **"incompatible — reconciliar a nivel modelo de datos"**. El PO decidió la
biblioteca viva desde V1.0.

## Decisión

El **núcleo de V1.0 tiene un `Store` con estado basado en DuckDB embebido**, como persistencia
**por defecto** (no como extra opcional). El corpus **persiste entre corridas**: aceptar/rechazar
candidatos, crecer y curar, con un **log de procedencia** (qué ecuación, qué chaining, qué
decisión humana, cuándo).

El **snapshot deja de ser el modelo de datos** y pasa a ser un **export derivable del estado
vivo**: una foto sellada (tabla + manifest con hash, schema_version, lib_version, fecha/versión
de OpenAlex) para **reportar y reproducir** (PRISMA / vom Brocke). **Reproducibilidad por
historia auditable + snapshot exportable**, no por inmutabilidad.

**Zotero** queda como **costura externa opt-in en V1.1** (extra `[zotero]`), **no** como la
persistencia núcleo de 1.0.

## Consecuencias

- **DuckDB entra al núcleo** (deja de ser el extra `[duckdb]` opcional del diseño previo).
- La **tabla canónica Arrow** (ADR 0006) **sigue siendo la representación**; DuckDB la persiste
  con estado, más tablas de **procedencia/decisiones de curación**.
- Se **gana el lazo del ciclo**: la query/idea puede mutar y volver a sembrar sin perder lo
  acumulado (historias A5, C4 del PRD).
- **Costo**: se pierde la simplicidad del "sin estado". Hay que manejar **identidad estable de
  papers entre corridas**, **migraciones de schema** sobre un store vivo, y concurrencia básica.
  El snapshot exportable preserva la reproducibilidad pese al estado.
- `ParquetStore` puede subsistir como **formato de export/intercambio** del snapshot, no como la
  persistencia por defecto.
- Hay que **reescribir `ARCHITECTURE.md` §6.2** y **reordenar `ROADMAP.md`** (el store DuckDB
  stateful sube a un hito temprano del núcleo).
