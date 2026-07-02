# 0024 — Orden D3 en DuckDB vía columna de secuencia interna (`_seq`)

- **Estado:** Aceptada · **AS-BUILT (2026-06-16)** (implementado en esta rama)
- **Fecha:** 2026-06-16
- **Decidido por:** IA (Claude Opus 4.8), validado por el Product Owner proxy
  (ver [`registro-ia.md`](registro-ia.md))
- **Relacionada con:** [0013](0013-identidad-hash-merge-corpus.md) (identidad/hash/merge D1–D3:
  el contrato de orden que esta decisión materializa), [0015](0015-corpus-tabular-backend.md)
  (`Corpus` sobre `TabularBackend`; el contrato D1–D3 es del backend, no del `Corpus`)

## Contexto

El contrato **D3** ([ADR 0013](0013-identidad-hash-merge-corpus.md)) exige que `merge` preserve el
**orden de primera aparición**: primero las filas de `self` en su orden original, luego las filas
nuevas de `other` (las que no estaban en `self`) en su orden de aparición.

El AS-BUILT previo de `DuckDBBackend` lo lograba con un **`DELETE FROM corpus` + reinserción fila
por fila** en cada `merge` (reescribía la tabla entera). La causa raíz: `_arrow_table_from_con` leía
`SELECT * FROM corpus` **sin `ORDER BY`**, y el `rowid` de DuckDB **no es estable tras un upsert**
(MVCC interno = delete + insert), así que no se podía confiar en `ORDER BY rowid` para reconstruir
el orden de primera aparición. La única forma de garantizar D3 era reescribir físicamente toda la
tabla en el orden correcto en cada `merge`.

La Nota 06 / el review marcaron ese **full-rewrite por
merge** como la única operación con olor a ineficiencia real (no un bug) del backend: en una
**biblioteca viva** (ADR 0009) que mergea en **cada ronda de chaining/reseed**, reescribir toda la
tabla por fila escala mal con el tamaño del corpus.

## Decisión

Agregar una columna interna **`_seq BIGINT`** a la tabla `corpus`:

- **No** es parte de `CORPUS_SCHEMA` (ADR 0006/0023): es un **detalle de implementación del
  backend**, no del contrato de fila.
- Se asigna **explícitamente en el `INSERT`** (monótona creciente, en orden de tabla) y **no** se
  toca en el `ON CONFLICT DO UPDATE`: las filas existentes **conservan su `_seq` original** = su
  primera aparición.
- Las lecturas usan `SELECT * EXCLUDE (_seq) FROM corpus ORDER BY _seq`.

Con eso, `merge` se reduce a `_clone()` + `_upsert_table(other)` y el **orden D3 emerge del
`ORDER BY _seq`**. **Se elimina el `DELETE` + reinserción fila por fila.**

## Consecuencias

- (+) **`merge` deja de reescribir toda la tabla por fila**: el orden D3 se mantiene por la columna
  persistida, no recomputándolo en cada merge.
- (+) **D1 (`id` estable) y D2 (`corpus_hash` order-independent sobre `to_arrow()`) intactos**: el
  hash se computa siempre sobre el contenido vía `to_arrow()`, nunca sobre `_seq`.
- (+) **`to_arrow()` / `filter_view` siguen devolviendo EXACTAMENTE `CORPUS_SCHEMA`** (sin `_seq`):
  el `EXCLUDE (_seq)` mantiene el puente estable con el núcleo de proyección.
- (−) **Se agrega una columna persistida** → migración liviana para bases `.duckdb` pre-0.4:
  `ALTER TABLE corpus ADD COLUMN _seq BIGINT` + backfill
  `UPDATE corpus SET _seq = rowid WHERE _seq IS NULL` (el `rowid` como proxy del orden histórico
  al momento de migrar; estable porque la migración no upsertea).
- (−) **`query(sql)`** (la extensión SQL libre read-only del backend) **expone `_seq`** si el
  usuario hace `SELECT * FROM corpus`: queda documentado como **detalle interno** del backend, no
  parte del schema público.
- **Equivalencia byte-a-byte con `InMemoryBackend` preservada**, verificada por la suite de
  contrato de backend (`tests/unit/test_backends.py`): ambos backends cumplen D1/D2/D3 idénticamente.

> **AS-BUILT (2026-06-16):** implementado en esta rama. Reemplaza el AS-BUILT de D3 anotado en el
> [ADR 0013](0013-identidad-hash-merge-corpus.md) (cleanup pre-v0.3: "leer todo, ordenar en Python,
> reinsertar"), que era correcto pero seguía reescribiendo la tabla por merge. **327 tests verdes,
> mypy strict / ruff limpios.**
