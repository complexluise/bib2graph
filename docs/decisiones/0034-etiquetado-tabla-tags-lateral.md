# 0034 — Etiquetado: tabla de tags lateral en el store (tags libres → taxonomía fase 2)

- **Estado:** Propuesta
- **Fecha:** 2026-06-18
- **Relacionada con:** [0009](0009-biblioteca-viva-duckdb.md) (biblioteca viva = sustrato del
  etiquetado), [0023](0023-capa-constants-modelos-schema.md)/[0006](0006-tabla-canonica-y-networkspec.md)
  (`CORPUS_SCHEMA` deliberadamente cerrado), [0033](0033-producto-library-centric-grafo-proyeccion.md)
  (etiquetar es parte del ejercicio bibliotecario primario), [0011](0011-thesaurus-multilingue.md)/
  [0031](0031-preprocesamiento-automatico-en-ingesta.md) (tesauro/topics = camino a taxonomía),
  [0024](0024-orden-d3-columna-secuencia-duckdb.md) (patrón de tablas hermanas fuera del `corpus_hash`).
- **Encuadre:** Nota 16 §H1/§H1b +
  Nota 17 §BUG-2 + Nota 18.
  **Decidido por el PO (2026-06-18): tags libres ahora, tabla lateral, sin BIBFRAME.**
- **Epic:** GUI local [#34](https://github.com/complexluise/bib2graph/issues/34).

## Contexto

El reencuadre library-centric (ADR 0033) hace del **etiquetado** una operación primaria: el
investigador clasifica/cura a mano sobre la biblioteca viva, independiente de la topología de la red
(Nota 16 §H1). Hace falta un modelo para persistir los tags.

Hay dos restricciones de diseño que apuntan a la **misma** solución:

1. **`CORPUS_SCHEMA` es deliberadamente cerrado** (23 columnas, una fila por paper; ADR 0006/0023).
   Es la fuente única de verdad del modelo, validada por Pydantic ⇄ Arrow. Agregarle una columna
   `tags` rompería la disciplina "una sola tabla canónica" y mezclaría **curación/clasificación
   manual del usuario** (estado de trabajo, multivaluado, abierto) con **contenido bibliográfico**
   (cerrado, identitario).

2. **BUG-2 (Nota 17):** `backends.duckdb._arrow_table_from_con` castea la tabla al `CORPUS_SCHEMA`
   oficial; agregar columnas extra **rompe el casteo** (`field names not matching`). El tercero ya
   tuvo que **mover metadata a una tabla lateral** para esquivar la rigidez. El patrón lateral ya está
   probado en el repo: `referenced_but_not_fetched` y `loop_state_log` son tablas hermanas que viven en
   el mismo `.duckdb`, **fuera del `corpus_hash`**, preservadas por `overwrite_corpus` (ADR 0031 §4).

El etiquetado es multivaluado (N tags por paper, N papers por tag): no encaja en una columna escalar
ni en el modelo una-fila-por-paper. Una tabla relacional lateral es la forma natural.

## Decisión

**Los tags se persisten en una tabla LATERAL `paper_tags` en el store, hermana de `corpus`, sin tocar
`CORPUS_SCHEMA`. Tags libres ahora; camino a taxonomía controlada como fase 2.**

1. **Modelo de datos — tabla `paper_tags`** (forma tentativa, se fija en el AS-BUILT):
   `(paper_id TEXT, tag TEXT, added_at TIMESTAMP, by TEXT)`, con índice por `paper_id` y por `tag`.
   Relación N:N (un paper → muchos tags; un tag → muchos papers). **`tag` es texto libre** en fase 1
   (sin vocabulario controlado). `added_at` se inyecta en la frontera (R2/ADR 0017, mismo patrón que
   `decided_at`/`applied_at`).

2. **Lateral, no columna — por qué:** (a) no toca el `CORPUS_SCHEMA` cerrado ni su casteo Arrow
   (esquiva BUG-2); (b) separa **clasificación manual del usuario** de **contenido bibliográfico**
   (misma lógica por la que `provenance`/curación no contaminan la entidad); (c) reusa el patrón de
   tablas hermanas ya probado (`referenced_but_not_fetched`), preservado por `overwrite_corpus` en cada
   ingesta. **`paper_tags` queda FUERA del `corpus_hash`** (es estado de trabajo, no identidad del
   corpus — coherente con ADR 0017: el hash es contenido bibliográfico).

3. **Operaciones de servicio** (`service.tags`, ADR 0032): `add_tag`, `remove_tag`, `list_tags`,
   `tags_for_paper`, `papers_by_tag`. Adaptadores: API (`POST/DELETE /api/paper/{id}/tags`,
   `GET /api/tags`) + GUI (editor de tags en la ficha + filtro por tag). Subcomando CLI `b2g tag`
   **opcional/diferido** (sub-fork Nota 18 §2).

4. **Camino a taxonomía (FASE 2, no ahora):** tags libres → **vocabulario controlado** poblado desde
   lo que ya está en el dato (**Topics/Concepts de OpenAlex** atados a cada paper + tesauro propio ADR
   0011/0031) → **SKOS** solo si hace falta interoperar/exportar vocabularios. Requiere su propio
   encuadre (migración tags→términos, UI de jerarquía). **BIBFRAME 2.0 queda FUERA** (ADR 0033 §4): es
   re-fundar el producto como catálogo RDF sin pagar beneficio del flujo actual.

## Alcance — lo que este ADR NO decide (sub-fork del PO)

**BUG-2 motiva esta tabla pero no se resuelve del todo acá.** La pregunta general —*¿el backend debe
tolerar columnas extra arbitrarias del usuario en `corpus`, o el schema permanece cerrado?*— **toca el
contrato del store y queda como decisión separada del PO.** Este ADR resuelve **el caso de los tags**
(lateral, no columna), que es el caso real de la iterada. Si el PO quiere extensibilidad general del
schema (campos arbitrarios por paper), es un ADR propio. **Recomendación del arquitecto:** mantener
`corpus` cerrado y canalizar toda extensión del usuario por tablas laterales (el patrón que ya
funciona); no abrir el schema canónico. ← PO confirma o abre el debate.

## Consecuencias

- (+) **Etiquetado de primera clase sin tocar el modelo canónico** ni romper el casteo Arrow (esquiva
  BUG-2). Reusa un patrón ya probado y testeado en el repo.
- (+) **Separación limpia** contenido bibliográfico (cerrado) ↔ clasificación del usuario (abierto),
  coherente con cómo curación/procedencia ya no contaminan la entidad.
- (+) **Reproducibilidad intacta:** `paper_tags` fuera del `corpus_hash` → el snapshot sigue
  identificando el corpus por contenido bibliográfico, no por las etiquetas de trabajo.
- (+) **Camino a taxonomía abierto y acotado** (SKOS + OpenAlex topics), sin comprometerse a BIBFRAME.
- (−) **Una tabla hermana más que mantener** (snapshot, migración de schema del store, `overwrite_corpus`
  debe preservarla — igual que `referenced_but_not_fetched`).
- (−) **Tags libres = inconsistencia inicial** (sinónimos, mayúsculas, typos). Es deliberado en fase 1;
  la normalización/taxonomía es fase 2. La revisión asistida de clusters ambiguos (ya diferida a #34 en
  ADR 0031) podría aplicarse también a tags más adelante.
- (−) **Decisión de extensibilidad general del schema (BUG-2) queda abierta** — este ADR la acota a
  tags pero no la cierra (ver §Alcance).
