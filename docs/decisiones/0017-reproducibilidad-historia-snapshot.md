# 0017 — Reproducibilidad por historia auditable + snapshot sellado, no por recómputo

- **Estado:** Aceptada · **enmendada 2026-06-15** (identidad vs procedencia; Louvain seeded — ver
  "Enmienda" al final)
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

## Enmienda — 2026-06-15 (identidad vs procedencia; reloj en la frontera; Louvain seeded)

> Motivada por el red-team del AS-BUILT v0.2
> ([Nota 06](../Notas/06-critica-as-built-v0.2.md), RAÍZ 2): el **principio de este ADR es
> correcto**, pero el **código no lo cumple** — el `corpus_hash` actual **incluye los timestamps de
> curación**, así que dos corridas que aceptan los mismos ids producen hash distinto y el snapshot
> **no** es reproducible bit a bit. El cuerpo del ADR (arriba) queda como historia; esta enmienda
> precisa el contrato correcto.

**Identidad (contenido) ≠ procedencia (auditoría).** Son dos ejes:

1. **Identidad — el `corpus_hash` se computa SOLO sobre contenido bibliográfico**, **excluyendo**
   `ProvenanceEvent`/timestamps. Dos corridas con el mismo contenido curado (mismos ids, mismo
   `curation_status`) tienen el **mismo** hash, aunque hayan ocurrido en momentos distintos. La
   identidad es del *qué*, no del *cuándo*.
2. **Procedencia — log append-only FUERA de la identidad.** El `provenance` (ADR
   [0013](0013-identidad-hash-merge-corpus.md) D4) sigue registrando cuándo/quién/por qué (para
   auditar PRISMA / vom Brocke), pero **no entra al hash**. Es modelado por `ProvenanceEvent(BaseModel)`
   (ADR [0023](0023-capa-constants-modelos-schema.md)).
3. **El reloj se inyecta en la frontera (CLI), no en el núcleo.** `accept`/`reject` y los filtros
   **reciben** el instante de decisión (o lo dejan que lo ponga la frontera), en vez de llamar
   `datetime.now(UTC)` dentro del núcleo. El núcleo vuelve a ser **determinista**.
4. **Análisis reproducible — Louvain con `random_state` derivado del content-hash.**
   `detect_communities(method="louvain")` se siembra con un `random_state` derivado del
   `corpus_hash` (y expone `resolution`), de modo que **mismo corpus → mismas comunidades**.

**Consecuencia:** el snapshot vuelve a ser **reproducible bit a bit** (cumple la promesa original) y
la pureza de `facade.py` ("mismo corpus + mismo spec → mismo `NetworkArtifact`") deja de estar rota.
**Recomendación para el `coder`:** ver ROADMAP **Hito R2** (`backends/memory.py:50-75,281`,
`corpus.py:386,403`, `networks/analyzer.py:120-129`).
