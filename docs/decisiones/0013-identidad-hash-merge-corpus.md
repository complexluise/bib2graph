# 0013 — Identidad estable de papers, hash de corpus order-independent y reglas de merge

- **Estado:** Aceptada
- **Fecha:** 2026-06-15
- **Decidido por:** IA (Claude Opus 4.8), validado por el Product Owner proxy
  (ver [`registro-ia.md`](registro-ia.md))
- **Relacionada con:** [0006](0006-tabla-canonica-y-networkspec.md) (tabla Arrow + Pydantic),
  [0007](0007-openalex-backbone.md) (OpenAlex backbone),
  [0009](0009-biblioteca-viva-duckdb.md) (biblioteca viva stateful en DuckDB)
- **Cierra la tensión abierta de:** [0009](0009-biblioteca-viva-duckdb.md) §Consecuencias
  ("hay que manejar **identidad estable de papers entre corridas**").
- **Reencuadrado (2026-06-15, 2º giro) por [0015](0015-corpus-tabular-backend.md):** las reglas
  D1 (`id` estable), D2 (`corpus_hash` order-independent) y D3 (`merge` campo a campo) **siguen
  vigentes como contrato**, pero **suben de "implementación del `Corpus`" a "contrato del
  `TabularBackend`"**: cada backend debe cumplirlas a su manera (`InMemoryBackend` en Python,
  `DuckDBBackend` en SQL `UPDATE`/`MERGE` por `id`). El `corpus_hash` (D2) se computa siempre
  sobre el contenido (`corpus.to_arrow()`), nunca sobre detalles del backend. D4 (`provenance`
  como log append-only), D5/D6 (Manifest) no cambian.

## Contexto

El ADR 0009 movió el corpus a una **biblioteca viva** que acumula entre corridas (aceptar/
rechazar candidatos, crecer, curar) y dejó explícitamente abierto un costo: **manejar la
identidad estable de papers entre corridas** y la reproducibilidad por historia auditable +
snapshot exportable. El Hito 1 (núcleo de la tabla canónica `Corpus`) tuvo que resolver, para
poder implementar `merge` idempotente, `snapshot()` con hash reproducible y una igualdad de
`Corpus` insensible al orden, cuatro decisiones acopladas que cambian el contrato:

1. Cómo se computa el `id` de un paper de forma **determinista y estable entre corridas**
   (necesario para deduplicar al fundir en la biblioteca viva).
2. Cómo se computa el `corpus_hash` para que dos corridas con el **mismo contenido** en
   distinto orden produzcan el **mismo hash** (reproducibilidad del snapshot).
3. Cómo se fusionan dos filas con el mismo `id` sin perder la decisión humana ni la procedencia
   (merge idempotente sobre la biblioteca viva).
4. Qué forma toma `provenance`. El contrato previo de `API.md` §1.1 lo describía como un
   **objeto único** `{equation_id, chaining_hop, source, fetched_at, decided_by, decided_at}`,
   pero la biblioteca viva exige un **log append-only**: un paper puede ser fetcheado, luego
   aceptado, luego re-fetcheado en otra corrida, y cada evento debe sobrevivir.

## Decisión

### D1 — `id` estable y determinista

`id = f"{prefix}:{sha256(valor).hexdigest()[:16]}"`, con precedencia de la fuente del `valor`:

1. `openalex_id` presente → `prefix = "oa"`, `valor = openalex_id`.
2. si no, `doi` presente → `prefix = "doi"`, `valor = doi` normalizado (minúsculas, sin prefijo
   `https://doi.org/` ni `http://doi.org/`).
3. si no → `prefix = "tt"`, `valor = f"{title.lower().strip()}|{year}"`.

Es **determinista y estable entre corridas**: el mismo paper produce el mismo `id` siempre, lo
que habilita dedup en `merge` y en la biblioteca viva.

### D2 — `corpus_hash` order-independent

El hash es **insensible al orden** de filas y de elementos dentro de las columnas `list[string]`:
se ordenan las filas por `id`, se ordenan los elementos de cada columna de lista, se serializa con
`json.dumps(sort_keys=True)` y se aplica `sha256`. Hashea **solo el contenido de la tabla**,
**nunca** campos volátiles del `Manifest` (`created_at`, `lib_version`, etc.). Es la definición
autoritativa de "mismo contenido".

> **Precisado por ADR [0017](0017-reproducibilidad-historia-snapshot.md) (enmienda 2026-06-15,
> Hito R2 ✅ 2026-06-16):** "contenido" = **contenido bibliográfico + `curation_status`**, pero
> **excluye `provenance`** (log de auditoría con timestamps). El texto original de este D2 incluía
> `provenance` en el hash, lo que rompía la reproducibilidad bit a bit (dos corridas que aceptaban
> los mismos ids daban hashes distintos por los timestamps de curación). R2 corrigió: la identidad
> es del *qué* (contenido), no del *cuándo* (procedencia). El `provenance` sigue siendo D4 (log
> append-only) fuera de la identidad.

### D3 — `merge` idempotente, combinación por campo

Dedup por `id`. Al fundir dos filas con el mismo `id`:

- **Escalares:** el no-nulo gana; si ambos no-nulos, gana el de `other`.
- **Columnas de lista:** unión deduplicada y ordenada. Si ambos lados son `None`, se preserva
  `None` (no se normaliza a `[]`) para mantener la idempotencia `c.merge(c) == c`.
- **`curation_status`:** gana la decisión humana más reciente según `provenance.decided_at`; con
  fallback de precedencia `accepted` > `rejected` > `candidate` cuando no hay decisión humana o
  empatan los timestamps.
- **`provenance`:** unión de eventos únicos (ver D4).

El **orden de filas del resultado es determinista por primera aparición**: primero las filas de
`self` en su orden original, luego las filas nuevas de `other` (las que no estaban en `self`) en
el orden en que aparecen en `other`. `merge` es idempotente.

> **AS-BUILT — Cleanup pre-v0.3 (2026-06-16):** en `DuckDBBackend`, el orden de primera aparición (D3)
> ya **NO se materializa interpolando ids crudos en el SQL.** El AS-BUILT construía
> `... WHERE id IN ('<id1>', ...) ORDER BY CASE id WHEN '<id>' THEN <pos> ... END` con f-strings sobre
> los ids (seguro entonces porque los ids son hashes hex, pero **frágil** —SQL construido con datos—;
> footgun catalogado en la Nota 06, `backends/duckdb.py:417,423`). El cleanup lo reemplazó por: **leer
> todas las filas** (`SELECT * FROM corpus`), **ordenarlas en Python** por el orden de aparición
> precomputado (`existing_ids + new_ids_in_order`) y **reinsertar**. Mismo orden determinista D3
> (regresión verde), **sin** SQL parametrizado por ids. La **alternativa de un CTE con `VALUES`** (pasar
> el orden como tabla de parámetros) quedó **descartada**: el ordenamiento en Python es más simple para
> el tamaño de corpus objetivo y no acopla el orden a un dialecto SQL.

### D4 — `provenance` como log append-only

`provenance` es una columna `string` cuyo JSON es una **lista de eventos** (log append-only), no
un objeto único. Cada evento tiene la forma:

```json
{
  "action": "fetched | accepted | rejected",
  "equation_id": "string | null",
  "chaining_hop": "int | null",
  "source": "string | null",
  "fetched_at": "ISO8601 | null",
  "decided_by": "string | null",
  "decided_at": "ISO8601 | null"
}
```

`accept`/`reject` **agregan** un evento (con `action='accepted'`/`'rejected'`, `decided_by`,
`decided_at`) sin borrar los previos. Esto **ajusta el contrato de `API.md` §1.1**, que describía
`provenance` como objeto único.

### Igualdad de `Corpus` vía `corpus_hash`

`Corpus.__eq__` se define como **igualdad canónica vía `corpus_hash`** (D2): dos `Corpus` son
iguales sii tienen el mismo contenido semántico, independientemente del orden de filas y del
orden interno de las columnas de lista, y robusta ante cualquier `PYTHONHASHSEED`. No compara el
`Manifest` ni el orden de `pa.Table`.

## Consecuencias

- **Se cierra la tensión abierta del ADR 0009:** la identidad estable de papers entre corridas
  queda resuelta por D1; la reproducibilidad del snapshot por D2.
- **`merge` sobre la biblioteca viva es seguro:** idempotente, no pierde decisiones humanas ni
  procedencia, y produce un orden de filas determinista (auditable / diffeable).
- **El log de procedencia es auditable:** cada fetch y cada decisión humana quedan como eventos
  inmutables; habilita PRISMA / vom Brocke (reproducibilidad por historia, ADR 0009).
- **Costo de contrato:** `API.md` §1.1 cambia (`provenance` = lista de eventos) y §1.2 documenta
  la semántica de `__eq__` y el orden de `merge`. El `id` por `title+year` (`tt:`) es frágil ante
  variaciones de título/año; es el último recurso cuando faltan `openalex_id` y `doi`.
- **`schema_version` no participa del hash ni de la identidad** y, en este hito, no tiene lógica
  de rechazo por incompatibilidad (ver `registro-ia.md`, Hito 1, D6); queda para un hito
  posterior cuando haya migraciones sobre el store vivo.
