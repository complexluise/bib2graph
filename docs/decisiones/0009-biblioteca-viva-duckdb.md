# 0009 — Biblioteca viva stateful en DuckDB como núcleo; el snapshot pasa a export

- **Estado:** Aceptada
- **Fecha:** 2026-06-15
- **Relacionada con:** [0006](0006-tabla-canonica-y-networkspec.md),
  [0007](0007-openalex-backbone.md)
- **Supersede (parcialmente):** el **`InMemoryStore` por defecto** de
  [0003](0003-persistencia-opcional.md) y el **"snapshot inmutable, sin in-memory store"** de
  [0006](0006-tabla-canonica-y-networkspec.md). El resto de 0006 (tabla Arrow + Pydantic,
  NetworkSpec, tooling/semver) **sigue vigente**.
- **Reencuadrado (2026-06-15, 2º giro) por [0015](0015-corpus-tabular-backend.md):** DuckDB deja
  de ser un **`Store` opcional aparte** que persiste un `Corpus` Arrow y pasa a ser el **backend
  por defecto del `Corpus`** (`DuckDBBackend`, vía el Protocol `TabularBackend`), con mutaciones
  por SQL `UPDATE`/`MERGE` por `id` en vez de copia en memoria. Sigue siendo **costura** (el punto
  de extensión persiste), y la **biblioteca viva, el snapshot=export y la reproducibilidad por
  historia** de este ADR **siguen vigentes**. El "por qué del recómputo no basta" se precisa en
  [0017](0017-reproducibilidad-historia-snapshot.md); el estado del lazo (`LoopState`,
  una investigación = un archivo `.duckdb`) se modela en
  [0016](0016-maquina-estados-lazo.md); la concurrencia single-writer se declara en
  [0019](0019-concurrencia-diferida.md).

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

## Enmienda — la unidad de persistencia pasa a "workspace/carpeta" (PROPUESTA, 2026-06-16)

> **Propuesta por [0029](0029-workspace-por-investigacion.md) (estado *Propuesta*, no implementado).**
> El cuerpo queda como historia; la biblioteca viva stateful en DuckDB **no cambia**.

Este ADR estableció la biblioteca viva sobre **un archivo `.duckdb`**. El ADR
[0029](0029-workspace-por-investigacion.md) propone que la **unidad de persistencia** pase de "1
archivo" a "**1 workspace = 1 carpeta**" (marcada por `workspace.json`), que contiene el
`library.duckdb` + `networks/` + `snapshots/` + `exports/`. El **corpus, la procedencia, las
decisiones de curación y el loop-state siguen viviendo dentro del `.duckdb`** (sin duplicarse en el
manifest); las redes/exports son cache regenerable y el snapshot sigue siendo lo reproducible (ADR
0017). Es una **formalización de una convención emergente** (`b2g build` ya escribe
`<store_dir>/networks/`), no una revisión del modelo de datos. **Hasta que 0029 se firme e
implemente, la unidad as-built sigue siendo el `.duckdb` suelto.**
