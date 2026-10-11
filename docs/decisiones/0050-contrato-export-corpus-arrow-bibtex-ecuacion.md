# 0050 — Contrato de export del corpus: `equations` de 1ª clase, `equation_hash` en el Arrow, y `b2g export --format arrow|bibtex`

- **Estado:** **Aceptada** (2026-07-25). El PO resolvió las bifurcaciones — ver §Resolución del PO
  (2026-07-25) al final. **Corte 0.14.0 = D1 + D3 + D4**; **D2 se difiere a 0.15.0** (diseño fijado
  aquí, implementación después).
- **Fecha:** 2026-07-25
- **Decidido por:** encuadre de la IA (architect); **las bifurcaciones de fondo las decidió el Product
  Owner** (2026-07-25, ver §Resolución del PO). Milestone **0.14.0** (se lanza mañana, 2026-07-26).
- **Origen:** issues [#291](https://github.com/complexluise/bib2graph/issues/291) (ecuación como
  objeto de 1ª clase), [#292](https://github.com/complexluise/bib2graph/issues/292) (`equation_hash`
  en la metadata del Arrow) y [#293](https://github.com/complexluise/bib2graph/issues/293) (paraguas:
  `export --format arrow|bibtex`). Los tres tocan la **misma superficie** (`to_arrow()` + comando
  `export`) y se diseñan con **un solo ADR de contrato**, no tres PRs en paralelo (nota de alcance de
  #293).
- **Consumidor externo:** un **consumidor programático** carga corpus reales subiendo el **Arrow que
  produce bib2graph** (no ejecuta bib2graph en vivo todavía). Su **contrato de verificación** prevé
  **recomputar el `equation_hash` y rechazar la carga si no coincide** —**esa verificación aún no está
  implementada del lado del consumidor**, así que el `equation_hash` es contrato a futuro, no un
  bloqueante de 0.14.0—. La normalización del hash queda documentada exacta (DoD de #292) para cuando el
  consumidor la active. **El ingest del consumidor programático que corre HOY sí impone constraints
  duros sobre el schema del Arrow** (columnas/tipos/valores/límites): ver §Constraints del consumidor
  programático.
- **Relacionada con / toca:**
  - **[0013](0013-identidad-hash-merge-corpus.md)** (D4 — `provenance` como log append-only:
    `{action, equation_id, chaining_hop, source, fetched_at, decided_by, decided_at}`; D2 —
    `corpus_hash` order-independent). Este ADR **enmienda D4 en 0.15.0** sumando `source_kind` al evento
    (**aditivo**; `chaining_hop` se mantiene, lo lee el consumidor programático) y reencuadra `equation_id` como
    FK/denormalización (D1, en 0.14.0). **No toca D1/D2/D3 de 0013.**
  - **[0017](0017-reproducibilidad-historia-snapshot.md)** (R2 — identidad = contenido, no procedencia;
    el `corpus_hash` **excluye** `provenance`). El `equation_hash` de #292 es **otra cosa** que el
    `corpus_hash`: hashea la **ecuación**, no el contenido; no participa de la identidad del corpus.
  - **[0030](0030-ecuacion-declarativa-corpus-ejemplo.md)** (`equation.yaml` + `EquationSpec` +
    `Manifest.equations: list[EquationRef]`). **La ecuación YA es un objeto parcial:** existe
    `EquationRef(equation_id, query, translation_report)` sellado en el `Manifest` por
    `OpenAlexSource.seed`. Este ADR **promueve** ese objeto (le suma `engine`/`params`/`created_at`) y
    lo **persiste como tabla/objeto de 1ª clase**, no solo en el manifest de un snapshot.
  - **[0025](0025-enricher-cocitacion-openalex.md)** / **[0048](0048-camino-unico-cocitacion-chain-forward-cited-by.md)**
    (co-citación / forward chaining). El **overload de `equation_id` con `chaining:*`** que #291 quiere
    eliminar es exactamente el que hoy escriben `OpenAlexSource.fetch_citing`
    (`equation_id="chaining:forward:{id}"`, `forager.py` `source_tag="chaining:forward"`). `source_kind`
    desambigua "vino de una ecuación" vs "vino de encadenar citas".
  - **[0037](0037-superficie-cli-10-verbos-ciclo.md)** / **[0021](0021-cli-agente-native-contrato.md)**
    (superficie de 10 verbos; `export`/`snapshot` cuentan como **un** verbo). `export --format arrow|bibtex`
    **no suma un verbo**: extiende el `--format` de un verbo existente. Envelope `schema="1"`, exit codes
    y FSM **intactos** (`export` no transiciona).
  - **[0018](0018-source-agnostico-calidad.md)** (BibTeX como `Source` secundaria legítima;
    `BibtexSource.load` ya existe). El `export --format bibtex` es el **inverso**: serializar el corpus a
    `.bib`, no leerlo.
- **No introduce IA** (coherente con [0022](0022-producto-sin-ia-generativa.md)): serialización
  determinista + hash SHA-256 + una tabla lateral. Ningún modelo generativo.

## Contexto

bib2graph estampa cada paper con `provenance.equation_id` y `fetched_at`, lo que hace el corpus una
**proyección trazable de (ecuación, fecha)**. Un **usuario programático que integra el Arrow de
bib2graph** reportó, al consumirlo downstream (su ingest; cualquier harness), tres límites, observados
en un corpus real de 737 papers (89 seeds con `equation_id=eq-…`, 648 forrajeados con
`equation_id=chaining:forward`):

1. **La ecuación no se persiste como objeto en el corpus vivo.** El `Manifest.equations`
   (`EquationRef`, ADR 0030) existe, **pero solo se sella en el snapshot** (`manifest.json` junto al
   parquet). En el `library.duckdb` vivo la única huella de "qué búsqueda produjo esto" es el
   `equation_id` string suelto dentro del JSON de `provenance`. Un consumidor recibe *que hubo una
   ecuación*, no *cuál* (query, engine, límite, filtros).

2. **`equation_id` está sobrecargado.** El chaining reusa el mismo campo con pseudo-ids
   (`chaining:forward`, `chaining:forward:{openalex_id}`) y `chaining_hop=1`, mezclando "este paper
   vino de una ecuación" con "vino de encadenar citas". Son **orígenes distintos en un mismo campo**.
   Código real:
   - `sources/openalex.py:546` — seed: `equation_id = f"eq-{…}"`.
   - `sources/openalex.py:667` — `fetch_citing`: `equation_id = f"chaining:forward:{openalex_id}"`.
   - `foraging/forager.py:538,543` — `equation_id="chaining:forward"`, `source_tag="chaining:forward"`.
   - `sources/openalex.py:1173` — `load`: `equation_id = "load"`. (`sources/bibtex.py:119` →
     `equation_id=None`.)

3. **No hay export del corpus como archivo.** Hoy `b2g export` serializa **artefactos de build (redes)
   → GraphML/CSV** (`cli/commands/export.py`: lee `<ws>/networks/<kind>/network.graphml`). `Corpus.to_arrow()`
   existe a nivel de corpus/backend (`corpus.py:255`, `backends/*.py`), y `snapshot create` ya escribe
   `corpus.parquet` + `manifest.json`, **pero no hay `export` del corpus como Arrow con metadata de
   schema**, ni **export a BibTeX**. Para el flujo del consumidor programático (carga por Arrow
   verificable, #292) y para el investigador clásico (BibTeX a su gestor) falta serializar el *corpus*
   en sí, con la ecuación y su hash embebidos.

Para el consumidor programático, la clave es **verificable, no por confianza**: recomputa el
`equation_hash` desde la ecuación que el usuario confirmó y **rechaza el Arrow si no coincide**. Eso
exige que la normalización del hash esté **documentada de forma exacta y estable** (una vez publicada,
cambiarla rompe al consumidor programático).

## Decisión

Se fija el **contrato de export del corpus** en cuatro piezas acopladas. La **normalización canónica
del hash** (D3) es la única parte **irreversible una vez publicada** (el consumidor programático la
reproduce); el resto es aditivo.

### D1 — `equations` como objeto de 1ª clase + FK; `equation_id` string = denormalización/cache

- **Tabla/objeto `equations`** en el store vivo (tabla hermana en el `DuckDBBackend`, análoga a
  `loop_state_log`/`referenced_but_not_fetched`; en `InMemoryBackend`, estructura equivalente):

  | Campo | Tipo | Notas |
  |---|---|---|
  | `equation_id` | `string` (PK) | mismo formato que hoy: `eq-<YYYYMMDDTHHMMSS>` (seed). Estable, ya existe. |
  | `engine` | `string` | motor que ejecutó la búsqueda (`openalex`; futuro `s2`/`crossref`). |
  | `raw_query` | `string` | la ecuación **cruda** tal como la escribió el usuario (`EquationSpec.query` / `--equation`), **antes** de traducir a filtros OpenAlex. Es lo que el consumidor programático confirma y hashea (D3). |
  | `params_json` | `string` (JSON) | parámetros: `{exclude, max_results, native, min_year, max_year, executed_query, translation_report}`. Superconjunto de `EquationRef` (0030) + los flags de `seed`. |
  | `label` | `string \| null` | etiqueta humana opcional. |
  | `created_at` | `string` (ISO8601 UTC) | sello de creación de la ecuación. |

- **`provenance.equation_id` es la FK** a `equations.equation_id`. **La tabla `equations` es la fuente
  de verdad; el `equation_id` string en `provenance` es denormalización/cache.** Retrocompat total: los
  consumidores actuales que solo leen `provenance.equation_id` **no rompen** (el string sigue ahí).
- **Reusar, no inventar:** `Manifest.equations: list[EquationRef]` (ADR 0030) ya captura
  `equation_id/query/translation_report`. `EquationRef` **se extiende** con `engine`/`params`/`created_at`
  y pasa a **persistirse en la tabla** (no solo sellarse en el snapshot). El manifest sigue sellando la
  lista en el snapshot; la tabla la persiste en la biblioteca viva.
- **Chaining NO crea filas en `equations`.** Un citante forrajeado no vino de una ecuación; su origen se
  expresa con `source_kind` + `chaining_hop` (D2), no con una pseudo-ecuación. Esto **elimina** los
  pseudo-ids `chaining:*` como PK.

### D2 — `source_kind` (nuevo, aditivo) reemplaza el overload de `chaining:*` en el evento de procedencia — **DISEÑO FIJADO, implementación DIFERIDA a 0.15.0**

> **DIFERIDA a 0.15.0 (resolución del PO, 2026-07-25).** El **corte 0.14.0 es D1 + D3 + D4**. El
> **diseño** de D2 queda **fijado y congelado** en este ADR (para que el coder no lo reabra cuando
> aterrice), pero su **implementación es 0.15.0**. Consecuencia directa: la **migración de corpus con
> `chaining:*` (ver abajo) también se difiere con D2** — en 0.14.0 **no hay que migrar nada ni mantener
> un parser de compat**, porque `equation_id` sigue tal cual está hoy (incluidos los `chaining:*`). La
> elección **on-read vs migración escrita** se decide **cuando D2 aterrice** en 0.15.0, no ahora.

- El `ProvenanceEvent` (schemas.py, ADR 0013 D4) gana **un campo NUEVO, aditivo**:
  - `source_kind: "seed_equation" | "chaining_forward" | "chaining_backward" | null`
- **`chaining_hop` NO se renombra ni se elimina** (constraint del consumidor programático — ver
  §Constraints del consumidor programático): el pipeline del consumidor programático **lee
  `provenance[].chaining_hop` directamente**, así que renombrarlo a `hop`
  sería un **break silencioso**. Se **mantiene `chaining_hop` con ese nombre**; `source_kind` se suma
  **al lado** (aditivo). La profundidad de expansión se sigue expresando con `chaining_hop`.
- **`equation_id` deja de sobrecargarse:** para un citante forrajeado, `equation_id=null` y
  `source_kind="chaining_forward"`, `chaining_hop=1` (hoy es `equation_id="chaining:forward"`,
  `chaining_hop=1`). Para una semilla, `equation_id="eq-…"` (FK a `equations`),
  `source_kind="seed_equation"`, `chaining_hop=null`.
- **Retrocompat de lectura (migración de corpus existentes) — se decide EN 0.15.0, no ahora.** Cuando
  D2 aterrice, al leer un corpus viejo donde `equation_id` empieza con `chaining:` se deberá **derivar**
  `source_kind` (y confirmar `chaining_hop`) de ese prefijo. **Si esa derivación se hace on-read (parser de compat) o con una
  migración de tabla escrita queda ABIERTO a 0.15.0** (el PO lo difirió junto con D2): en 0.14.0 no hay
  migración ni parser de compat porque `equation_id` no cambia todavía.
- **`corpus_hash` no cambia** (ADR 0013 D2 / 0017 R2): el hash **excluye `provenance`**, así que sumar
  `source_kind` al evento (en 0.15.0) **no alterará** `corpus_hash` ni la reproducibilidad.
  `compute_corpus_hash` (`backends/memory.py:59`) ya saltea la columna `provenance`.

> **Nota de fasing (resuelta por el PO, 2026-07-25).** #291 propone un **MVP incremental**: primero
> `equations` + FK (D1, resuelve el 80%), y `source_kind` (D2) como segundo paso. **El PO tomó el
> MVP:** **0.14.0 = D1 + D3 + D4**; **D2 → 0.15.0**. Este ADR fija el **diseño** de D2 (congelado, no se
> reabre) pero su implementación —y la migración de `chaining:*`— es 0.15.0.

### D3 — `equation_hash` en la metadata del schema Arrow (el contrato con el consumidor programático)

`to_arrow()` (o la ruta de export, ver §Bifurcaciones sobre **dónde** vive) puebla la **metadata del
schema Arrow** (`pa.schema(...).with_metadata({...})`, bytes→bytes) con:

| Clave | Valor |
|---|---|
| `equation_hash` | SHA-256 (hex, minúsculas) de la ecuación cruda normalizada (ver abajo). |
| `equation_hash_algo` | `"sha256"` (constante; explícito para versionar el algoritmo del digest). |
| `equation_expression` | la ecuación **cruda** (`raw_query`), para trazabilidad. |
| `equation_id` | la FK (`eq-…`), para cruzar con la tabla `equations` (D1). |

**Normalización canónica del hash — `strip()` puro (contrato de verificación del consumidor).** Se hashea la
ecuación **cruda** (`raw_query` = lo que el usuario escribió, `EquationSpec.query` / `--equation`,
**antes** de la traducción a filtros OpenAlex):

```
equation_hash = sha256( normalize(raw_query).encode("utf-8") ).hexdigest()
donde  normalize(expression) = expression.strip()
```

Es decir: se toma la ecuación cruda, se le aplica **`str.strip()`** (elimina espacios en blanco al
inicio y al final; **NO** colapsa espacios internos, **NO** cambia mayúsculas, **NO** normaliza comillas
ni Unicode NFC/NFKC), se **codifica en UTF-8** y se aplica **SHA-256**; el resultado es el **hexdigest en
minúsculas**. Esta definición es **exactamente la del contrato de verificación del consumidor**
(`sha256(expression.strip().encode("utf-8")).hexdigest()`) y la de #292 al pie de la letra, y **se documenta idéntica** en
`docs/API.md` como contrato público congelado.

> **`equation_hash` es contrato a FUTURO, NO un bloqueante de 0.14.0.** La verificación por hash **aún no
> está implementada del lado del consumidor** (su contrato de verificación está en estado **Propuesta**).
> bib2graph emite el hash bien (strip exacto) para dejar la ligadura ecuación↔corpus lista y verificable
> **cuando** el consumidor programático la active; su ausencia **no frena** el release (ver §Consecuencias).

**Corpus multi-ecuación / sin ecuación (resuelto por el PO, 2026-07-25 — se confirma la recomendación
del ADR):** un corpus puede tener 0, 1 o N ecuaciones (seed + reseed + chaining). **Regla congelada:
exactamente una ecuación → `equation_hash` presente; cero o múltiples → la metadata `equation_hash` (y
`equation_expression`/`equation_id`) se OMITE + se emite un `warning`.** Nunca se emite un hash inventado
para un corpus con 0 o >1 ecuaciones: fallar suave y honesto, no mentir un hash que el consumidor
programático no podría verificar.

### D4 — `b2g export --format arrow|bibtex`, respetando `--scope`

- **`export` gana dos formatos** al `--format` existente (`graphml`/`csv`): **`arrow`** y **`bibtex`**.
  **No es un verbo nuevo** (respeta la poda de 10 verbos, ADR 0037; `export`/`snapshot` = un verbo).
- **`--format arrow`** → escribe el corpus (`Corpus.to_arrow()`, scopeado) a **un archivo `.arrow`
  (Feather / Arrow IPC), NO parquet** (resolución del PO, 2026-07-25). La metadata de schema de D1/D3
  (objeto ecuación embebido + `equation_hash` + `equation_hash_algo`) **viaja dentro del archivo
  Feather**, que es **un archivo autoverificable** que el consumidor programático sube y valida. **Es un
  artefacto distinto de `snapshot create`** (que escribe **parquet + `manifest.json`** para
  reproducibilidad interna, ADR 0017): no se solapan. La distinción es intencional:
  - **`export --format arrow`** = **Feather autoverificable**, orientado al **consumidor externo**
    (programático) — un solo archivo con la ligadura ecuación↔corpus embebida y verificable por hash.
  - **`snapshot create`** = **parquet + manifest**, orientado a la **reproducibilidad interna** de
    bib2graph (sello del `corpus_hash`, rehidratable con `snapshot restore`, ADR 0030).
- **`--format bibtex`** → escribe un `.bib` **parseable** con las entradas del corpus scopeado.
  **Defaults congelados (resolución del PO, 2026-07-25):**
  - **(a) entry-type inferido**, con **`@article` como default** cuando no hay señal para inferir otro
    tipo.
  - **(b) citekey = el `id` interno del paper** (`doi:…`/`src:…`/`tt:…`, D1 de ADR 0013): estable y sin
    colisiones. El DOI va **como campo** (`doi = {…}`), no como citekey.
  - **(c) campos mínimos universales:** `title`, `author`, `year`, `doi`, `journal`/`venue`, `url`.
    **`keywords`/`abstract` quedan fuera del MVP.**
  - **(d) scope = el corpus scopeado por `--scope`, sin filtrar por "metadata suficiente":** las entradas
    incompletas se emiten con los campos que haya (no se descartan por faltarles autor/año/etc.).
- **`--scope`** — hoy `export` (redes) **no** tiene `--scope`; el que existe es `build --scope`
  (`[all|accepted|seeds]`, `Corpus.scoped`, API.md §2). Los formatos de **corpus** (`arrow`/`bibtex`)
  **sí** respetan `--scope` (DoD de #293) reusando `Corpus.scoped(scope)` (vocab CLI `seeds`→`seeds_only`).
  Los formatos de **redes** (`graphml`/`csv`) **ignoran** `--scope` (releen artefactos de build ya
  scopeados). Coexistencia de un flag que aplica a unos formatos y no a otros: **el ADR recomienda**
  documentarlo explícito y emitir `warning` si se pasa `--scope` con `graphml`/`csv`.
- **`exports_dir` / `--out-dir`:** los archivos van a `<workspace>/exports/` por defecto
  (`ws.exports_dir`), con `--out-dir` como override (igual que hoy). Envelope `--json` consistente:
  `{format, out_dir, files_written, workspace}` + eco de workspace (ADR 0045).

## Consecuencias

- (+) **Trazabilidad completa corpus → ecuación → pregunta.** La tabla `equations` (fuente de verdad)
  + FK deja recuperar *qué* búsqueda produjo cada paper (query, engine, límites), no solo *que hubo una*.
  Beneficia a cualquier harness, no solo al consumidor programático.
- (+) **Ligadura ecuación↔corpus verificable, no por confianza.** El `equation_hash` (`v1`) en la
  metadata del Feather deja que el consumidor programático rechace un Arrow que no salió de la ecuación
  confirmada (su contrato de verificación). El **archivo Feather es autoverificable** (la ligadura viaja
  dentro).
- (+) **`equation_id` dejará de estar sobrecargado (en 0.15.0).** `source_kind` (aditivo, junto a
  `chaining_hop`) separará "vino de una ecuación" de "vino de encadenar citas"; `chaining:*` dejará de
  ser una pseudo-ecuación. **En 0.14.0 esto es solo diseño** (D2 diferida); el corte 0.14.0 **no toca
  `provenance`**.
- (+) **Retrocompat total en 0.14.0.** El `equation_id` string sigue en `provenance` sin cambios
  (incluidos los `chaining:*`); D1 solo **agrega** la tabla `equations` y su FK. Nada rompe para
  consumidores actuales.
- (+) **Sin verbo nuevo ni cambio de envelope/exit/FSM.** `export` extiende `--format`; `export` no
  transiciona (ADR 0021/0037 intactos).
- (+) **`corpus_hash` intacto.** Ni D1 ni D3 tocan el contenido bibliográfico; D2 (0.15.0) sumará campos
  a `provenance`, que R2 excluye del hash. La identidad del corpus no cambia en ningún corte.
- (+) **`export --format arrow` (Feather) NO se solapa con `snapshot create` (parquet).** Dos artefactos
  con propósitos distintos: Feather autoverificable para el consumidor externo (programático) vs parquet +
  manifest para reproducibilidad interna. Evita ambigüedad "¿cuál uso?".
- (+) **`equation_hash` NO bloquea 0.14.0.** La verificación por hash **aún no está implementada del
  lado del consumidor** (su contrato de verificación está en **Propuesta**). Emitir el hash bien (strip
  exacto) es el **piso honesto** que cierra la coherencia ecuación↔corpus (el feedback del consumidor
  programático) **sin esperar nada más**: es barato y prioritario, pero su ausencia **no frena el
  release**. bib2graph deja la ligadura lista para cuando el consumidor programático active la
  verificación.
- (+) **D1 y D3 son ADITIVOS sobre el schema del Arrow → seguros para el consumidor programático.** El
  consumidor programático **ignora todo lo que no está en su `INGESTED_COLUMNS`** y toda metadata de
  schema que no consume. La tabla lateral `equations` (D1), la FK, y la metadata de ecuación +
  `equation_hash` (D3) **no tocan** las columnas ni los valores que su ingest lee: no rompen su carga.
  Ver §Constraints del consumidor programático.
- (−) **Cambio de contrato público** en `docs/API.md`: (a) `export` gana `--format arrow|bibtex` +
  interacción con `--scope` (§2); (b) se documenta el objeto `equations`, la metadata del Feather y la
  **normalización exacta (`strip()`) del `equation_hash`** como contrato congelado. **(El evento
  `provenance` con `source_kind` —aditivo, sin renombrar `chaining_hop`— se documentará cuando D2 aterrice
  en 0.15.0.)** **Este ADR es el ADR requerido** por el CLAUDE.md / DoD de #293. La edición concreta de
  `API.md` es trabajo del `coder` al implementar (mismo criterio que 0044/0045/0048), **guiada por este
  ADR**.
- (−) **`equation_hash` congelado:** una vez que el consumidor programático empiece a verificar, cambiar la normalización
  (`strip()`) rompería la verificación. Es deliberado; la definición se documenta bit a bit y
  `equation_hash_algo="sha256"` deja versionar el algoritmo para evoluciones controladas.
- (−) **Migración de corpus con `chaining:*` — diferida a 0.15.0 con D2.** En 0.14.0 no hay nada que
  migrar ni parser de compat que mantener. Cuando D2 aterrice se decidirá **on-read vs migración escrita**
  (on-read = reversible, no reescribe stores, mantiene parser vivo; escrita = más limpia, toca datos vivos,
  necesita idempotencia/versión de schema).
- (−) **Coordinar la API Python de #291 con el seam del worker del consumidor programático.** El worker
  del consumidor programático (diferido / config-gated, **no corre hoy** y **no importa bib2graph como
  paquete pinneado**) asume una firma **especulativa** `Corpus.forage(equation=expression)` +
  `to_arrow()`. **No condiciona el diseño de #291** en este ADR, pero la API Python que #291 fije debe
  **coordinarse con ese seam** (o el consumidor actualiza su adaptador). No rompe el consumidor
  programático que corre hoy.
- (−) **Superficie de `equations` en dos backends:** la tabla hermana hay que implementarla en
  `DuckDBBackend` (SQL) y `InMemoryBackend` (Python), como ya se hizo con `loop_state_log` (ADR 0013 D4).

## Constraints del consumidor programático (contrato de schema del Arrow) — DUROS

Un usuario programático que integra el Arrow de bib2graph reportó que su ingest depende de columnas,
tipos, valores y **límites de tamaño** que **NO pueden cambiar sin romper la carga**. Ese ingest (que
**corre hoy**, a diferencia de la verificación por hash) consume el **Arrow que produce bib2graph** —
varios de esos constraints rompen **en silencio** (sin error, con datos faltantes). Esto es un
**constraint duro del contrato del corpus**, no una recomendación. **D1 los respeta** (es aditivo:
tabla lateral + FK + metadata, no toca columnas/valores existentes). **D2, cuando aterrice en 0.15.0,
DEBE respetarlos** (por eso `chaining_hop` **no se renombra**, ver D2).

**Rompen EN SILENCIO si cambian (sin error; se caen datos):**

- **`source_id` y `references_id` deben seguir siendo ids OpenAlex del MISMO namespace (`W…`).** El
  consumidor programático arma el grafo de citas **joineando `references_id` de un paper contra
  `source_id` de otro**. Si cambian
  de esquema de id, **todas las citas desaparecen sin error** (se caen 3 de 4 redes de El Mirador + el
  ranking del muestreo). (Coherente con ADR 0036: el `id` canónico es DOI-ancla, pero `source_id`/
  `references_id` siguen siendo los ids del motor OpenAlex.)
- **`curation_status` con valores EXACTOS `candidate | accepted | rejected`.** El ingest del consumidor
  programático hace `.exclude(rejected)`. **Renombrar un estado = los papers rechazados se filtran
  adentro del mapa** (o peor, dejan de filtrarse). (Coherente con `_VALID_CURATION` en `schemas.py`.)
- **`is_seed` (booleano, no-null).** Clasifica seed vs chaining en el ingest del consumidor programático.
  Debe seguir emitiéndose **no-null** (ya es no-nullable en `CORPUS_SCHEMA`).
- **Las columnas de `INGESTED_COLUMNS`** (`id`, `doi`, `title`, `year`, `abstract`, `source`,
  `curation_status`, `is_seed`, `source_id`, `references_id`, `authors_*`, `keywords_*`,
  `institutions_*`, `references_doi`, `provenance`…): un **rename/typo** las vuelve **invisibles sin
  error** para el consumidor programático.

**Rompen DURO (Postgres rechaza la transacción entera) si exceden límite/tipo:**

| Campo | Límite / tipo |
|---|---|
| `id`, `source_id`, `references_id` (cada elem) | ≤ 500 chars |
| `curation_status` | ≤ 16 chars |
| `doi` | ≤ 255 chars |
| `source` | ≤ 255 chars |
| `authors_raw` (cada elem) | ≤ 500 chars |
| `institutions_raw` (cada elem) | ≤ 500 chars |
| `provenance[].source` | ≤ 255 chars |
| `year` | int **o** null |
| `provenance[].fetched_at` | datetime **parseable** |
| `provenance[].chaining_hop` | int **o** null |

**Seguro (dato tranquilizador):** **AGREGAR columnas o metadata nueva al Arrow es 100% seguro** — el
consumidor programático ignora todo lo que no está en `INGESTED_COLUMNS` y toda metadata de schema que no
consume. Por eso **D1** (tabla `equations` lateral + FK + metadata de ecuación en el schema) y **D3**
(`equation_hash` en metadata) son **aditivos** y no tocan el contrato del ingest. La regla de diseño para
este ADR y para D2/0.15.0: **agregar sí, renombrar/estrechar/re-tipar NO** sobre lo que el consumidor
programático lee.

## Alternativas descartadas

- **Dejar la ecuación solo como string en `provenance` (statu quo) y solo documentarla mejor.**
  **Rechazada:** es exactamente el límite de #291. Un string suelto no permite recuperar query/engine/
  límites; un consumidor sabe *que* hubo una ecuación, no *cuál*. Documentar mejor un string opaco no lo
  vuelve un objeto recuperable. Además no resuelve el overload `chaining:*`.
- **Estilo "extra-files" (la ecuación y su hash en archivos sueltos junto al Arrow, tipo
  `equation.json` + `equation.sha256`).** **Rechazada:** rompe la ligadura **dentro** del artefacto que
  el consumidor programático sube. El consumidor carga **un** Arrow y quiere verificar **ese** Arrow; un
  sidecar se puede perder, editar o desincronizar en el traspaso, y lo obliga a un contrato de "familia
  de archivos" en vez de "un archivo autoverificable". La metadata del schema Arrow viaja **con** los
  datos.
- **Sobrecargar más `equation_id` (p. ej. `chaining:backward:{id}`) en vez de un `source_kind` explícito.**
  **Rechazada:** perpetúa el problema de #291 (un campo con dos significados) y hace frágil el parseo
  downstream. Un enum explícito (`source_kind`, aditivo junto a `chaining_hop`) es autodescriptivo y no
  colisiona con las PK de `equations`.
- **Un `equation_hash` sobre la query *traducida* (`executed_query` OpenAlex) en vez de la cruda.**
  **Rechazada:** el consumidor programático confirma con el usuario la **ecuación cruda**, no los filtros OpenAlex
  traducidos (que además cambian si cambia el traductor, ADR 0007). Hashear la cruda es lo que #292
  especifica y lo estable de cara al usuario. (La traducida queda en `params_json.executed_query` para
  auditoría, no para el hash.)
- **Robustecer la normalización del hash (NFC + lower + colapsar espacios) en vez de `strip()` puro.**
  **Rechazada:** el contrato de verificación del consumidor especifica **exactamente**
  `sha256(expression.strip().encode("utf-8")).hexdigest()`. bib2graph **no** puede robustecer
  unilateralmente: cualquier normalización más agresiva que la del consumidor produciría hashes distintos
  y la verificación (cuando se active) fallaría. El hash debe replicar la spec del consumidor programático
  al pie de la letra; robustecer sería una **renegociación cross-repo** que hoy no está sobre la mesa.
  `strip()` es lo que el contrato de verificación del consumidor ya espera.
- **Escribir `--format arrow` como parquet** (consistente con `snapshot create`). **Rechazada por el PO
  (2026-07-25):** solaparía con `snapshot create` (parquet + manifest) y confundiría "¿cuál uso?".
  Feather/IPC deja la metadata de schema viajar natural y da un **archivo autoverificable** distinto del
  snapshot; los dos artefactos tienen propósitos separados (externo/consumidor programático vs interno/reproducibilidad).
- **Un verbo nuevo `b2g corpus-export` separado de `export`.** **Rechazada:** suma superficie CLI contra
  la poda a 10 verbos (ADR 0037/0038); `export` ya es el verbo de serialización. Se extiende su `--format`.

## Resolución del PO (2026-07-25)

El PO resolvió las seis bifurcaciones que este ADR había dejado abiertas. Se registran acá; el cuerpo
del ADR ya las folded.

1. **Formato de `--format arrow` = `.arrow` / Feather (IPC), NO parquet.** La metadata de schema viaja
   dentro del archivo Feather (autoverificable, orientado al consumidor programático). **No se solapa con `snapshot
   create`** (parquet + `manifest.json`, reproducibilidad interna): son dos artefactos con propósitos
   separados. (Ver D4 y §Consecuencias.)

2. **`source_kind`/`hop` (D2) se DIFIERE a 0.15.0.** El **corte 0.14.0 = D1 (tabla `equations` + FK) +
   D3 (`equation_hash`) + D4 (`export arrow|bibtex`)**. El **diseño** de D2 queda fijado y congelado en
   este ADR; su implementación es 0.15.0. (Ver nota de fasing en D2.)

3. **Migración de corpus con `chaining:*` — DIFERIDA junto con D2 a 0.15.0.** En 0.14.0 no hay que migrar
   nada ni mantener parser de compat (D1 es aditivo; `equation_id`/`provenance` no cambian). **On-read vs
   migración escrita se decide cuando D2 aterrice.** (Ver D2 y §Consecuencias.)

4. **Hash = `strip()` puro, NO robustecer.** `sha256(expression.strip().encode("utf-8")).hexdigest()`,
   UTF-8, hex minúsculas; nada de NFC/lower/collapse. Es **exactamente** la spec del contrato de
   verificación del consumidor. **La verificación NO está implementada aún del lado del consumidor** (su
   contrato de verificación está en Propuesta): el `equation_hash` es **contrato a futuro, no bloqueante
   de 0.14.0** — piso honesto que cierra la coherencia ecuación↔corpus (el feedback del consumidor
   programático) sin esperar nada más. Emitirlo bien es barato
   y prioritario; su ausencia no frena el release. (Ver D3 y §Consecuencias.)

5. **Política del `equation_hash` con 0 o >1 ecuaciones: se confirma la recomendación del ADR.**
   Exactamente 1 ecuación → `equation_hash` presente; 0 o N → metadata omitida + `warning` (no mentir un
   hash). (Ver D3.)

6. **Formato del `.bib` (defaults decididos, no abiertos):** (a) entry-type **inferido**, `@article`
   default cuando no hay señal; (b) citekey = el **`id` interno** del paper (estable, sin colisiones),
   con el DOI como **campo**; (c) campos mínimos universales: `title`, `author`, `year`, `doi`,
   `journal`/`venue`, `url` (`keywords`/`abstract` fuera del MVP); (d) scope = el corpus **scopeado por
   `--scope`**, sin filtrar por "metadata suficiente" (entradas incompletas se emiten con lo que haya).
   (Ver D4.)

## Constraints cross-repo pendientes (contexto, no bloquean 0.14.0)

- **`equation_hash`:** cuando el consumidor programático implemente la verificación (su contrato de
  verificación pasa de Propuesta a Aceptada), ambos lados deben producir el mismo `sha256(strip())`.
  bib2graph ya lo emite correcto; el trabajo restante es del lado del consumidor. No es de este release.
- **Seam del worker del consumidor programático:** la API Python que fije **#291** debe coordinarse con
  la firma especulativa `Corpus.forage(equation=…)` + `to_arrow()` que asume ese worker (diferido /
  config-gated, no corre hoy). No condiciona el diseño de este ADR; se resuelve al implementar #291 (o el
  consumidor actualiza su adaptador).
