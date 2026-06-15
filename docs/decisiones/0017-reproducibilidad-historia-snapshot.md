# 0017 — Reproducibilidad por historia auditable + snapshot sellado, no por recómputo

- **Estado:** Aceptada
- **Fecha:** 2026-06-15
- **Relacionada con:** [0007](0007-openalex-backbone.md) (OpenAlex backbone),
  [0009](0009-biblioteca-viva-duckdb.md) (biblioteca viva; snapshot = export),
  [0013](0013-identidad-hash-merge-corpus.md) (`corpus_hash`, log de procedencia),
  [0016](0016-maquina-estados-lazo.md) (máquina de estados del lazo)
- **Precisa:** el principio 8 del [PRD](../PRD.md) §6 ("reproducibilidad por historia auditable +
  snapshot exportable, no por inmutabilidad"), declarando **por qué** el recómputo no sirve.

## Contexto

El ADR 0009 ya estableció que la persistencia es una **biblioteca viva** y que el snapshot es un
**export derivable**, con reproducibilidad **por historia auditable + snapshot exportable**, no
por inmutabilidad. Faltaba declarar explícitamente **el hecho que lo obliga**: que **re-ejecutar
la misma ecuación contra OpenAlex NO garantiza el mismo corpus**.

OpenAlex **cambia en el tiempo** (ADR 0007 lo nota como advertencia de reproducibilidad): se
agregan obras, se corrigen referencias, cambia la cobertura. Una ecuación idéntica corrida hoy y
en seis meses devuelve conjuntos distintos. Por lo tanto, la **ecuación + la query ejecutada NO
son un artefacto reproducible por sí solas**: documentan *qué se pidió*, no *qué se obtuvo*.

## Decisión

El **artefacto reproducible es el snapshot sellado**, no el recómputo de la ecuación. La
reproducibilidad se sostiene en dos patas, ambas ya presentes en el modelo:

1. **Historia auditable** — el log de procedencia append-only (`provenance`, ADR
   [0013](0013-identidad-hash-merge-corpus.md) D4) y el `Manifest` registran qué ecuación, qué
   query OpenAlex ejecutada, qué salto de chaining, qué filtros (conteos PRISMA) y qué decisión
   humana, y cuándo. Eso hace la corrida **reportable y auditable** (PRISMA / vom Brocke).
2. **Snapshot sellado** — la foto (`corpus.parquet` + `manifest.json`) con `corpus_hash` (D2) es
   el artefacto que se versiona (git-lfs / DVC) y que **otro investigador reproduce bit a bit**,
   sin volver a llamar a OpenAlex.

El **`openalex_version`** del `Manifest` **ancla la foto a la versión/fecha del snapshot de
OpenAlex usado**. Declararlo es obligatorio para que el snapshot sea interpretable: dice "este
corpus corresponde a OpenAlex en tal estado". Sin ese ancla, dos snapshots de la misma ecuación
en fechas distintas no son comparables.

**Reproducir = re-sellar/releer el snapshot**, no re-correr la ecuación. Re-correr la ecuación es
**re-investigar** (legítimo, pero produce un corpus nuevo, no el mismo).

## Consecuencias

- **Queda claro qué promete la herramienta:** reproducir *un resultado* (el snapshot), no
  *recuperar* el mundo de OpenAlex en una fecha pasada. Honestidad sobre el límite de la fuente.
- **El `openalex_version` deja de ser opcional en la práctica:** sigue siendo un campo del
  `Manifest` con default `None` (D5), pero el `OpenAlexSource` (Hito 4) **debe** poblarlo al
  sembrar, y un snapshot con `openalex_version=None` se reporta como **menos reproducible**
  (entra en el reporte de calidad, ADR [0018](0018-source-agnostico-calidad.md)).
- **Refuerza el ADR 0016:** el archivo vivo cambia (la idea muta, el corpus crece); el snapshot
  congela un punto del lazo. El `LoopState` del instante puede sellarse en el snapshot.
- **No reabre el ADR 0009:** lo precisa. El snapshot ya era "export sellado"; este ADR fija que
  **es la unidad de reproducibilidad** y por qué el recómputo no la sustituye.
- **Recomendación para el `coder`:** ningún cambio de núcleo nuevo respecto al Hito 1 (el
  `snapshot()` ya sella `corpus_hash`); el **Hito 4** (`OpenAlexSource`) debe poblar
  `Manifest.openalex_version` al sembrar, y el reporte de calidad (Hito 5+, ADR 0018) debe marcar
  los snapshots sin ancla de versión.
