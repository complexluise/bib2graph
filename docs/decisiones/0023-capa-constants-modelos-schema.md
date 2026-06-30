# 0023 — Capa base de vocabulario + modelos: `constants`, `ProvenanceEvent`, schema única

- **Estado:** Aceptada
- **Fecha:** 2026-06-15
- **Decidido por:** Product Owner humano (tras el red-team de la
  [`../Notas/06-critica-as-built-v0.2.md`](../Notas/06-critica-as-built-v0.2.md), secciones CONSTANTS
  y MODELS)
- **Relacionada con:** [0006](0006-tabla-canonica-y-networkspec.md) (tabla canónica + schema Pydantic),
  [0013](0013-identidad-hash-merge-corpus.md) (`provenance` como log append-only),
  [0015](0015-corpus-tabular-backend.md) (`Corpus` sobre `TabularBackend`)

## Contexto

El red-team del AS-BUILT v0.2 ([Nota 06](../Notas/06-critica-as-built-v0.2.md)) encontró dos clases
de fragilidad de base:

- **No hay módulo de constantes.** ~62 nombres de columna viven como **string-literal** en 14
  archivos (`"references_id"`, `"cited_by_id"`, …); los valores de `curation_status`
  (`candidate`/`accepted`/`rejected`) se redefinen como literales en 11 archivos. Un typo en una
  columna **no falla en import**: es bug latente (eco de la lección 4 de v0, drift de esquema).
- **Estructuras informales que piden modelo.** El evento de procedencia es un `dict` por
  string-keys construido a mano en ≥4 sitios y parseado con un `except` que se **traga JSON corrupto
  en silencio**. `PaperRow` y `CORPUS_SCHEMA` están **duplicados a mano** (22 campos): dos fuentes de
  verdad para la fila.

La decisión de v0.2 de que `Paper`/`Author`/`Keyword`/`Institution` son **vistas derivadas, no
tipos** es correcta y **se mantiene** (Nota 06 MODELS): no se crean clases-entidad.

## Decisión

Introducir una **capa base de vocabulario + modelos**, por debajo del núcleo, como **fuente única**:

1. **`bib2graph.constants`** — `class Col(StrEnum)` (todos los nombres de columna), `class
   CurationStatus(StrEnum)` (`candidate`/`accepted`/`rejected`) y `NetworkKind` (tipos de red). Todo
   el código referencia estos enums; se eliminan los string-literals dispersos.
2. **`ProvenanceEvent(BaseModel)`** — fuente única del evento de procedencia
   (`{action, equation_id, chaining_hop, source, fetched_at, decided_by, decided_at}`), con parseo
   que **falla ruidoso** ante JSON corrupto (no `return []` en silencio).
3. **`schemas.py` como única definición de fila** — `PaperRow` (Pydantic) es autoritativa y
   `CORPUS_SCHEMA` (Arrow) se **deriva/verifica** de ella, en vez de mantenerse a mano en paralelo.

Se **mantiene** "`Paper`/`Author`/… = vistas derivadas, no tipos del modelo".

## Consecuencias

- **Un typo de columna falla en import/type-check**, no en runtime tardío: cierra la clase de bug
  latente que la lección 4 de v0 ya había mostrado.
- **El evento de procedencia tiene un solo constructor y un parseo honesto** (sin tragarse JSON
  corrupto); habilita además excluir limpiamente `ProvenanceEvent`/timestamps del `corpus_hash` (ADR
  [0017](0017-reproducibilidad-historia-snapshot.md) enmendado: identidad vs procedencia).
- **`PaperRow` ⇄ `CORPUS_SCHEMA` no pueden driftear**: una sola fuente, verificada.
- **Coste:** un refactor transversal (toca 14 archivos) sin cambiar comportamiento observable; debe
  hacerse con la suite verde como red de seguridad. Es la base sobre la que se apoyan los demás
  hitos de remediación (scent, FSM, identidad-vs-procedencia).
- **Posición en el grafo de dependencias:** `constants/models` es la **capa más baja**
  (`constants/models` → núcleo puro → costuras → CLI); nada de abajo importa hacia arriba.
- **Recomendación para el `coder`:** ver ROADMAP **Hito R1** (`archivo:símbolo` de los literales a
  reemplazar y de `_parse_provenance`).

> **AS-BUILT R1 (2026-06-16):** la capa `constants`/`ProvenanceEvent`/`schemas` única se construyó
> (ver [registro-ia](registro-ia.md) Hito R1).
>
> **Completado en R5 (2026-06-16) — `NetworkSpec.kind` usa `NetworkKind` directo.** El AS-BUILT inicial
> dejaba `NetworkSpec.kind` como un `Literal[...]` con los cinco tipos de red **duplicado** del
> `NetworkKind` de `constants.py` (la paridad se sostenía con un test). R5 cerró ese último resabio de
> doble verdad: `kind: NetworkKind` (`spec.py`), y `facade._projector_for_kind` compara contra los
> miembros del enum (`NetworkKind.BIBLIOGRAPHIC_COUPLING`, …) en vez de string-literals. **`NetworkKind`
> es ahora la fuente única real** (no validada por test de paridad: validada por el type-checker).
>
> **AS-BUILT (enmienda, 2026-06-22) — la dirección de autoridad del schema (§3) es la INVERSA.** El
> §3 de la Decisión declara **`PaperRow` (Pydantic) autoritativa** y dice que `CORPUS_SCHEMA` (Arrow)
> se "**deriva/verifica**" de ella. El AS-BUILT invierte la autoridad: **`CORPUS_SCHEMA` (Arrow) es la
> definición autoritativa** y **`PaperRow` se alinea campo a campo**. De las dos vías que el §3
> mencionaba, el AS-BUILT conserva la **verificación** y descarta la **derivación**: el invariante "no
> driftean" se sostiene por **paridad verificada por test** (`assert_schema_parity()` en `schemas.py`,
> que falla si los nombres/orden de campo divergen — comentario explícito: "`CORPUS_SCHEMA` sigue
> siendo la definición Arrow autoritativa; `PaperRow` se alinea"), no por generar uno desde el otro.
> **El fin anti-drift del §3 se cumple** (una sola verdad, imposible de driftear sin que falle el
> test/type-check); lo que cambia es la *dirección* de autoridad (`PaperRow` → `CORPUS_SCHEMA`). El
> texto del §3 queda como historia.
