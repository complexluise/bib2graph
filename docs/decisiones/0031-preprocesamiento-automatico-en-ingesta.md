# 0031 — Preprocesamiento automático en la ingesta (normalize + dedup) y `rapidfuzz` al núcleo

- **Estado:** Aceptada · **AS-BUILT (2026-06-18)** (#88) · **supersede en parte** a
  [0026](0026-dedup-fuzzy-determinista.md) (el dedup deja de ser "función de librería sin
  subcomando" y pasa a ser automático en la ingesta) y a la enmienda `[dedup]` de
  [0005](0005-dependencias-extras.md) (el extra se elimina; `rapidfuzz` pasa a núcleo)
- **Fecha:** 2026-06-18
- **Decidido por:** IA (Claude Opus 4.8), validado por el Product Owner proxy
  (ver [`registro-ia.md`](registro-ia.md))
- **Relacionada con:** [0026](0026-dedup-fuzzy-determinista.md) (algoritmo de dedup determinista —
  intacto; cambia *cuándo y cómo* se invoca, no el *qué*), [0005](0005-dependencias-extras.md)
  (matriz de extras; `[dedup]` se elimina), [0011](0011-thesaurus-multilingue.md) (thesaurus
  determinista; queda como el ÚNICO paso explícito del preproc), [0017](0017-reproducibilidad-historia-snapshot.md)
  (R2 — reloj en la frontera; `applied_at` inyectado), [0022](0022-producto-sin-ia-generativa.md)
  (sin IA generativa; el dedup sigue siendo similitud de cadenas determinista),
  [0024](0024-orden-d3-columna-secuencia-duckdb.md) (upsert-concat D3 con `_seq`: la razón de
  `persist_replace`), [0016](0016-maquina-estados-lazo.md) (FSM; `thesaurus` es transversal, NO
  transiciona)

## Contexto

El ADR [0026](0026-dedup-fuzzy-determinista.md) (Hito 7) construyó el dedup fuzzy determinista
(`deduplicate_authors`/`deduplicate_keywords`) como **función de librería**, en el extra `[dedup]`
(import perezoso de `rapidfuzz`), **sin subcomando CLI**: el PO decidió entonces no exponerlo como
paso del producto. Resultado en la práctica: el corpus de la biblioteca viva **nunca se deduplicaba**
salvo que un programa llamara a las funciones a mano. El caso real (`examples/valoraciones/`,
ADR 0030) y las sesiones de QA mostraron que el corpus acumulado quedaba con variantes
casi-iguales de autores y keywords que ni `normalize` ni el thesaurus colapsan — exactamente lo
que el dedup existe para resolver — porque **nadie lo corría**.

Hay además un problema estructural con la deduplicación *cross-biblioteca*: cada ingesta
(`seed`/`seed_from_bib`/`chain`/`restore`) mergea el lote entrante en la biblioteca acumulada con
el **upsert-concat D3** (`_seq`, ADR 0024), que **concatena listas y deduplica solo por `id`**. Un
dedup que corriera solo sobre el lote entrante dejaría pasar variantes que ya viven en la
biblioteca; y un upsert posterior **reintroduciría** las variantes viejas junto a las nuevas. Para
que el corpus quede deduplicado de verdad hay que (a) deduplicar el corpus **completo ya mergeado**,
no el lote, y (b) **reemplazar** la tabla `corpus` en lugar de upsertear.

`rapidfuzz` como extra `[dedup]` con import perezoso solo se justificaba mientras el dedup era
opcional. Si el dedup es automático en cada ingesta, `rapidfuzz` es **requerido siempre**: un extra
opt-in para una capacidad del camino caliente es una trampa (instalación "mínima" que produce un
corpus sin deduplicar en silencio, contra la regla de 0005 "fallar fuerte, no degradar en silencio").

## Decisión

El preprocesamiento determinista se ejecuta **automáticamente en la ingesta**, `rapidfuzz` pasa al
**núcleo**, y el **thesaurus** queda como el único paso explícito del preproc.

1. **`normalize` + dedup AUTOMÁTICOS en la ingesta, punto único en la frontera.** Las cuatro rutas
   de ingesta (`seed`, `seed_from_bib`, `chain`, `restore`) aplican el helper de frontera
   **`cli/_ingest.py::normalize_and_dedup`** sobre el corpus **completo ya mergeado**
   (`existing.merge(incoming)` → `normalize_and_dedup` → persistir). El orden determinista es
   `Preprocessor().normalize` → `deduplicate_authors(0.92)` → `deduplicate_keywords(0.90)` (umbrales
   de 0026). Al correr sobre el corpus completo, la deduplicación es **cross-biblioteca** (ve toda
   la biblioteca acumulada, no solo el lote entrante). El **algoritmo de dedup de 0026 no cambia**
   (token_sort_ratio + Union-Find + canónico más-frecuente/desempate-id, determinista e idempotente);
   cambia *quién lo invoca y cuándo*.

2. **`rapidfuzz` pasa a `[project.dependencies]`; el extra `[dedup]` se ELIMINA.** El import en
   `preprocessors/dedup.py` deja de ser perezoso (es import de nivel de módulo). Esto supersede la
   enmienda `[dedup] = rapidfuzz>=3,<4` de [0005](0005-dependencias-extras.md): ya no hay extra que
   instalar, ni `ImportError` accionable que apunte a `uv sync --extra dedup`. Coherente con 0005
   "se declara todo lo que se importa": una dependencia del camino caliente va en el núcleo.

3. **El thesaurus es el ÚNICO paso explícito del preproc — `b2g thesaurus --from <archivo>`
   (18° subcomando), transversal al FSM.** `apply_thesaurus` requiere el mapeo curado del usuario,
   así que **no** puede ser automático. Se expone como subcomando propio que lee el corpus, aplica
   `Preprocessor.apply_thesaurus` y persiste **sin transicionar el `CycleState`** (mismo criterio que
   `enrich`/`curate`/`networks`, ADR 0016). El orden conceptual `normalize → thesaurus → dedup` de
   0026 se reordena en la práctica a `normalize + dedup` (automáticos, en la ingesta) y `thesaurus`
   (explícito, cuando el investigador tiene el mapeo); el thesaurus sobrescribe `keywords_id` y
   reemplaza la tabla (ver punto 4).

4. **`persist_replace` (store) / `overwrite_corpus` (backend): reemplazo de tabla, no upsert.** La
   ingesta automática y `thesaurus` persisten con `DuckDBStore.persist_replace` →
   `DuckDBBackend.overwrite_corpus`, que hace **DELETE + INSERT** de la tabla `corpus` (reasignando
   `_seq` desde 0, ADR 0024) **preservando las tablas hermanas** (`loop_state_log`,
   `referenced_but_not_fetched`). Es necesario porque el upsert-concat D3 (`persist`)
   **reintroduciría** las variantes que el dedup acaba de colapsar (concatena listas, deduplica solo
   por `id`). El `persist`/upsert normal **queda intacto** para el caso legítimo "mismo paper desde
   dos fuentes" (D3) y para los demás llamadores; `persist_replace` se usa SOLO donde ya tenés el
   corpus completo, normalizado y deduplicado en memoria.

5. **`normalize`/`apply_thesaurus` aceptan `applied_at` inyectado desde la frontera (R2).** El
   `PreprocRef` del `Manifest` sella el timestamp que la frontera CLI inyecta con un único
   `datetime.now(UTC)` por invocación (mismo patrón que `decided_at` en curación, ADR 0017). Sin
   `applied_at`, se usa `datetime.now(UTC)` (uso como librería independiente).

6. **`build`/`networks` siguen PUROS** (sin red, sin preproc implícito): el corpus ya entra
   deduplicado desde la ingesta. La pureza de los proyectores (ADR 0014) no se toca.

### Diferido a la epic GUI (#34)

- **Revisión asistida de clusters ambiguos.** Cuando un cluster fuzzy es dudoso (variantes en el
  borde del umbral), lo correcto es **sugerir N opciones canónicas y dejar elegir al humano**
  (determinista, vía los scores de `rapidfuzz`, **sin IA generativa** — coherente con ADR 0022). Eso
  requiere una superficie interactiva que el CLI no tiene; se **difiere a la epic GUI #34**. Hoy el
  dedup automático aplica el canónico determinista (más-frecuente/desempate-id) sin pedir
  confirmación.

## Consecuencias

- (+) **El corpus queda SIEMPRE normalizado y deduplicado cross-biblioteca** tras cualquier
  ingesta, sin que el usuario tenga que recordar correr nada. Cierra el drift "el dedup existía pero
  nadie lo corría" de 0026.
- (+) **Instalación sin trampas:** `rapidfuzz` en el núcleo elimina el extra opt-in que producía un
  corpus sin deduplicar en silencio. Coherente con 0005 ("fallar fuerte, no degradar en silencio").
- (+) **Punto único de preproc en la frontera** (`normalize_and_dedup`): una sola ruta, testeable,
  con el reloj inyectado (R2). El thesaurus, que necesita input humano, queda explícito y separado.
- (+) **`persist_replace` resuelve el reintroducir-variantes** del upsert-concat sin romper D3 para
  los demás llamadores ni perder las tablas hermanas.
- (−) **Costo O(n²) del dedup por ingesta (deuda conocida).** Al deduplicar el corpus **completo** en
  cada ingesta, el costo del clustering fuzzy crece con el tamaño de la biblioteca (no solo del
  lote). Aceptable a la escala actual (caso real: decenas–cientos de filas); la **optimización
  (blocking/índices, dedup incremental) es trabajo futuro** si aparece un corpus grande.
- (−) **Skip conocido #93:** `test_run_seed_from_bib_reseed_incrementa_ronda` queda **skip** — un
  crash `BibDataString`/`pyparsing` en un reseed **dentro del mismo proceso**, expuesto por el
  auto-dedup. **No afecta el CLI real** (cada invocación es un proceso nuevo; el crash es del estado
  global de `bibtexparser` al reentrar en el mismo proceso). Reabrible con su propio encuadre.
- (−) **0026 deja de describir el comportamiento como-construido** en cuanto a invocación: el dedup
  ya no es "función de librería sin subcomando" sino automático en la ingesta. 0026 queda como
  **historia inmutable** del algoritmo (que sigue vigente); este ADR lo marca **superseded-en-parte**.

> **AS-BUILT (2026-06-18, #88):** helper `src/bib2graph/cli/_ingest.py::normalize_and_dedup`
> cableado en `seed`/`seed_from_bib`/`chain`/`restore`; `rapidfuzz>=3,<4` en
> `[project.dependencies]` (extra `[dedup]` eliminado; `preprocessors/dedup.py` importa `rapidfuzz`
> a nivel de módulo); 18° subcomando `b2g thesaurus --from <archivo>`
> (`cli/commands/thesaurus.py`, transversal, no transiciona); `DuckDBStore.persist_replace` /
> `DuckDBBackend.overwrite_corpus` (DELETE+INSERT, preservan tablas hermanas, reasignan `_seq`);
> `Preprocessor.normalize`/`apply_thesaurus` aceptan `applied_at`. Deuda: O(n²) del dedup por
> ingesta (optimización futura) y skip #93.

---

> **Nota append-only — el "único paso explícito" `thesaurus` se retira como verbo (2026-06-28, #164,
> ADR [0038](0038-destino-verbos-huerfanos-0037.md)).** El punto 3 de la decisión arriba ("El
> thesaurus es el ÚNICO paso explícito del preproc — `b2g thesaurus --from <archivo>`, 18°
> subcomando") **se revisa**: el verbo `thesaurus` **se elimina** (no queda ni como alias). El ADR 0038
> ya lo anticipó (issue [#149](https://github.com/complexluise/bib2graph/issues/149), cerrada
> *invalid*); esta nota cierra el círculo en el 0031.
>
> - **La capacidad se preserva como flag `b2g build --thesaurus <archivo>`** (consolidación
>   cross-lingüe de keywords, ADR [0011](0011-thesaurus-multilingue.md) **intacto**): `build` aplica
>   `Preprocessor.apply_thesaurus` sobre `keywords_id` **antes** de scopear y proyectar, persiste el
>   corpus actualizado con `persist_replace` (punto 4, intacto) y suma un bloque aditivo
>   `data["thesaurus"]` (`keywords_mapped`/`keywords_total`/`aliases_loaded`/`applied_at`).
> - **El resto del 0031 sigue vigente:** `normalize` + dedup **automáticos en la ingesta** (puntos 1,
>   2, 4, 5) no cambian; `rapidfuzz` sigue en el núcleo. Lo único que cae es el *verbo* explícito: la
>   consolidación de keywords pasa de paso-CLI propio a flag de `build`. (Sutileza vs. el 0031: ya no
>   hay "único paso explícito" del preproc; el thesaurus es ahora un *opt-in de `build`*, no un verbo.)
