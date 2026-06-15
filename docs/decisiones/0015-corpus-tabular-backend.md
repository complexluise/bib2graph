# 0015 — `Corpus` sobre `TabularBackend`; DuckDB backend por defecto

- **Estado:** Aceptada
- **Fecha:** 2026-06-15
- **Relacionada con:** [0002](0002-modelo-agnostico-backend.md) (núcleo agnóstico de backend),
  [0006](0006-tabla-canonica-y-networkspec.md) (tabla Arrow + Pydantic),
  [0009](0009-biblioteca-viva-duckdb.md) (biblioteca viva en DuckDB),
  [0013](0013-identidad-hash-merge-corpus.md) (identidad/hash/merge)
- **Enmienda:** [0006](0006-tabla-canonica-y-networkspec.md) (el `Corpus` deja de ser un
  objeto-valor sobre `pa.Table` cruda) y **reencuadra** [0009](0009-biblioteca-viva-duckdb.md)
  (DuckDB pasa a ser el **backend por defecto** del `Corpus`, sigue siendo costura, ya no un
  "`Store` opcional aparte").

## Contexto

Terminados los Hitos 0–2, el `Corpus` del Hito 1 (`src/bib2graph/corpus.py`) tiene **semántica
de valor pura**: `accept`/`reject`/`merge`/`add_paper` hacen `table.to_pylist()` → mutar en
Python → reconstruir la tabla Arrow **entera**. Eso fue correcto para el núcleo testeable del
Hito 1, pero **no escala**: cada decisión de curación reconstruye toda la tabla en memoria, y la
**biblioteca viva** (ADR 0009) necesita persistir y mutar entre corridas sobre colecciones que
crecen con el tiempo. Antes de construir el Hito 3 (`DuckDBStore`) hay que resolver **dónde
viven las mutaciones**.

El diseño previo separaba dos cosas que en realidad son una: el `Corpus` (objeto-valor Arrow,
ADR 0006) y un `Store` DuckDB **aparte** que lo persiste (ADR 0009 §Consecuencias, ROADMAP Hito
3). Eso obliga a dos modelos de mutación (en memoria por valor, en DuckDB por SQL) y a un
trasiego constante tabla↔store. El momento de corregirlo es ahora (barato: Hito 2 recién
terminado, Hito 3 sin construir).

La tensión de fondo: queremos **escala y persistencia** (DuckDB, SQL `UPDATE`/`MERGE` por `id`
en vez de copia en memoria) **sin** romper el principio de **núcleo puro agnóstico de backend**
(ADR 0002) ni la lección de v0 (que el núcleo no dependa de un servidor para existir ni para
testearse).

## Decisión

El `Corpus` se respalda en un **`TabularBackend` (Protocol)**, no en una `pa.Table` cruda. El
**núcleo NO importa `duckdb` directamente**: depende del Protocol, recibe la implementación
inyectada.

Dos implementaciones de referencia:

- **`InMemoryBackend`** — puro, sin I/O. Es el *working set* efímero y el backend de los **tests**
  (el núcleo se testea sin DuckDB instalado). Hereda la lógica actual de `corpus.py` (mutación
  en Python sobre listas de dicts).
- **`DuckDBBackend`** — la **biblioteca viva** (ADR 0009). Archivo `.duckdb` o `:memory:`.
  Mutaciones por **SQL `UPDATE`/`MERGE` por `id`**, no por copia en memoria. Es el **backend por
  defecto** del `Corpus` cuando hay persistencia.

Las **mutaciones se delegan al backend**: `Corpus.accept`/`reject`/`merge`/`add_paper` ya no
reconstruyen la tabla entera en Python; piden la operación al `TabularBackend`, que la cumple a
su manera (InMemory en Python; DuckDB en SQL). Las **reglas de identidad/hash/merge del
[ADR 0013](0013-identidad-hash-merge-corpus.md) (D1/D2/D3) se mantienen como contrato**: cada
backend debe cumplirlas (InMemory replicando la lógica Python; DuckDB expresándolas en SQL).

Los **proyectores y analizadores siguen siendo funciones puras sobre `pa.Table`** (ADR 0006,
[0014](0014-proyeccion-redes-pesos-asortatividad.md)): consumen `corpus.to_arrow()`. **Solo
cambia el contenedor del `Corpus`, no el núcleo de análisis**: `to_arrow()` es el puente
estable entre la biblioteca viva (cualquier backend) y el núcleo puro de proyección.

## Consecuencias

- **Escala sin servidores.** DuckDB embebido muta por SQL por `id`; las decisiones de curación
  dejan de copiar toda la tabla. La biblioteca viva crece sin penalización cuadrática.
- **Núcleo puro preservado** (ADR 0002): el núcleo depende del Protocol `TabularBackend`, no de
  `duckdb`. Los tests usan `InMemoryBackend` y **no necesitan DuckDB** — la lección de v0 (núcleo
  testeable sin I/O) sigue en pie.
- **El `Store` deja de ser una costura aparte.** DuckDB pasa de "`Store` que persiste un Corpus
  Arrow" (ADR 0009) a "backend por defecto del Corpus". La costura sigue existiendo (es el punto
  de extensión: `ZoteroStore`/`Neo4jStore` siguen siendo destinos opt-in), pero el respaldo
  primario de la biblioteca viva es el `DuckDBBackend`.
- **El contrato del ADR 0013 sube de "implementación del Corpus" a "contrato del backend".** Cada
  backend debe garantizar `id` estable (D1), `corpus_hash` order-independent (D2) y las reglas de
  `merge` (D3). El `corpus_hash` se computa siempre sobre el contenido (vía `to_arrow()`), nunca
  sobre detalles del backend.
- **Costo (rework del Hito 1).** Hay que migrar `src/bib2graph/corpus.py`. Detalle accionable
  para el `coder` en el milestone "Hito 1.5 — Rework de `Corpus`" del [ROADMAP](../ROADMAP.md);
  resumen:
  - Extraer un `TabularBackend` (Protocol) en `src/bib2graph/backends/` (o módulo nuevo).
    Operaciones mínimas: `add_paper`, `merge`, `set_curation`/`apply_curation`,
    `to_arrow`, `filter_view` (seeds/candidates/accepted), `corpus_hash`, `__len__`, `__eq__`
    por hash.
  - `InMemoryBackend`: mover ahí la lógica actual de `corpus.py` (los helpers `_merge_rows`,
    `_merge_curation_status`, `_merge_list_field`, `_compute_corpus_hash`, `_apply_curation`,
    `_rows_to_table`). El `Corpus` deja de operar `self._table` directamente y delega en
    `self._backend`.
  - `DuckDBBackend`: las mismas operaciones en SQL (`UPDATE`/`MERGE` por `id`); el merge campo a
    campo y la resolución de `curation_status` (D3) se expresan en SQL/UDF respetando el ADR 0013.
    Cae en el Hito 3 (la costura de red/persistencia), no en el rework de núcleo.
  - `Corpus.from_arrow` / `add_paper` / `merge` / `accept` / `reject` / `materialize` /
    `snapshot` (en `corpus.py`) pasan a **delegar** en el backend; `snapshot()` sigue sellando el
    hash D2 vía `to_arrow()`.
  - **Preservar** `_compute_id` (D1), la semántica de `__eq__` por `corpus_hash` (D2) y el orden
    determinista de `merge` (D3) como contrato verificado por tests del backend.
  - **Tests:** los tests del Hito 1 (`tests/unit/`) corren contra `InMemoryBackend` por defecto;
    agregar un set de tests de **contrato de backend** (mismos invariantes D1/D2/D3) parametrizado
    para que `DuckDBBackend` lo cumpla cuando llegue en el Hito 3.
- **Riesgo:** dos implementaciones del mismo contrato pueden divergir. Se mitiga con el set de
  tests de contrato compartido (mismos casos, ambos backends).
