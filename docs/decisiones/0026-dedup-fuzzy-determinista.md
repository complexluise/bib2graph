# 0026 — Deduplicación fuzzy determinista con `rapidfuzz` (splink diferido)

> **Supersedida en parte por [0031](0031-preprocesamiento-automatico-en-ingesta.md) (2026-06-18, #88):**
> el **algoritmo** de este ADR (token_sort_ratio + Union-Find + canónico más-frecuente, determinista)
> **sigue vigente**, pero su **invocación cambia**: el dedup deja de ser "función de librería sin
> subcomando CLI" y pasa a ejecutarse **automáticamente en la ingesta** (sobre el corpus completo
> mergeado, cross-biblioteca), y `rapidfuzz` deja el extra `[dedup]` para ir al **núcleo**. El cuerpo
> de abajo queda como historia inmutable del corte del Hito 7. Ver 0031.

- **Estado:** Aceptada · **AS-BUILT (2026-06-16)** (Hito 7) · **supersedida en parte por
  [0031](0031-preprocesamiento-automatico-en-ingesta.md)** (2026-06-18): invocación del dedup
  (automático en ingesta) y `rapidfuzz` al núcleo; el algoritmo sigue vigente
- **Fecha:** 2026-06-16
- **Decidido por:** IA (Claude Opus 4.8), validado por el Product Owner proxy
  (ver [`registro-ia.md`](registro-ia.md))
- **Relacionada con:** [0011](0011-thesaurus-multilingue.md) (thesaurus determinista; el dedup fuzzy
  es el complemento que su enmienda dejaba abierto **solo si es determinista**),
  [0017](0017-reproducibilidad-historia-snapshot.md) (reproducibilidad por historia auditable; el
  dedup registra un `PreprocRef`), [0022](0022-producto-sin-ia-generativa.md) (el producto no usa IA
  generativa: el dedup es **determinista por similitud de cadenas**, no semántico/LLM/embeddings),
  [0005](0005-dependencias-extras.md) (núcleo liviano + extras con import perezoso; el extra `[dedup]`
  pasa a `rapidfuzz`, ver su enmienda)

## Contexto

El Hito 7 ([ROADMAP/04](../ROADMAP/04-lo-que-viene.md)) materializa la deduplicación **fuzzy** de
`authors_id` y `keywords_id`: el complemento aproximado de la normalización conservadora del
`Preprocessor` (ADR 0011, Hito 5), que solo colapsa variantes triviales (lowercase, acentos,
espacios) y matchea keywords contra el thesaurus curado. Lo que queda son variantes **casi-iguales**
que ni la normalización ni el thesaurus capturan ("J. Smith" vs "John Smith"; "ecological exchange"
vs "ecologic exchange").

El `[dedup]` original (ADR 0005, v0) listaba `fuzzywuzzy` + `python-levenshtein`. `fuzzywuzzy` está
**abandonado** (sin releases, licencia GPL); su sucesor mantenido y permisivo (MIT) es `rapidfuzz`.
La enmienda de 2026-06-15 del ADR 0011 (raíz del retiro de IA, ADR 0022) ya dejó dicho que el único
fallback aceptado para ampliar cobertura es **fuzzy determinista** (`rapidfuzz`), **nunca**
semántico/LLM. Faltaba decidir el contrato y el algoritmo concretos, y descartar formalmente
`splink`.

## Decisión

El dedup fuzzy es **determinista** y vive en el extra **`[dedup]` = `rapidfuzz>=3,<4`** (import
perezoso). Se expone como **función de librería** (no subcomando CLI — decisión del PO), exportada
desde `bib2graph.preprocessors`:

```python
def deduplicate_authors(corpus: Corpus, *, threshold: float = 0.92) -> Corpus: ...
def deduplicate_keywords(corpus: Corpus, *, threshold: float = 0.90) -> Corpus: ...
```

- **`threshold` por-campo** (autores 0.92 / keywords 0.90; ambas reciben el parámetro): los nombres
  de autor toleran menos ruido que las keywords.
- Operan sobre la columna **`_id`** (`authors_id` / `keywords_id`), **nunca** sobre `_raw` (el crudo
  es historia inmutable). Corren **después** de `normalize` y `apply_thesaurus`
  (normalize → thesaurus → dedup): el fuzzy refina lo que lo determinístico no colapsó.
- **`rapidfuzz`, no `splink`.** `rapidfuzz` es liviano, MIT, sin descarga de modelos y **determinista**
  (mismo input → mismo score). `splink` es **probabilístico** (EM / Fellegi-Sunter), introduce
  **no-determinismo** (estimación de parámetros) y arrastra dependencias pesadas (Spark/DuckDB ML);
  queda **diferido a post-V1** en un ADR aparte, si aparece un caso de record-linkage entre fuentes
  que lo justifique. El dedup de V1 no es record-linkage probabilístico: es colapso de variantes de
  cadena con un umbral fijo.

### Algoritmo determinista (AS-BUILT)

1. **Scorer:** `rapidfuzz.fuzz.token_sort_ratio` (0–100), comparado contra `threshold * 100`.
2. **Clustering:** los pares con score ≥ umbral forman aristas; los clusters son las **componentes
   conexas** vía **Union-Find** (raíz lexicográfica, iteración en orden → determinista, insensible a
   `PYTHONHASHSEED`).
3. **Canónico del cluster:** la variante **más frecuente** (en nº de papers distintos), con
   **desempate por `id` ascendente** (`min(key=(-freq, v))`).
4. **Remapeo:** solo la columna `_id`; preserva el **orden de primera aparición** de cada lista;
   **nunca toca `_raw`**.

Esto garantiza **determinismo** (mismo corpus + threshold + versión de `rapidfuzz` → mismo
resultado; verificado cross-`PYTHONHASHSEED`) e **idempotencia** (converge en una pasada). El import
del extra es **perezoso**: sin `[dedup]`, un `ImportError` accionable apunta a `uv sync --extra dedup`.

### Reproducibilidad (ADR 0017)

Cada función registra un `PreprocRef` en el `Manifest` con
`{library, rapidfuzz_version, scorer, threshold, n_clusters_collapsed}` — la versión de `rapidfuzz`
forma parte de la procedencia, porque el resultado es reproducible **a igual versión del scorer**.

### Campos en V1

**Autores + keywords.** Las **instituciones quedan diferidas**: `institutions_id` no está
normalizada determinísticamente hoy (no hay un `normalize` de instituciones que el fuzzy pueda
refinar sin riesgo); se difiere a un hito posterior.

## Consecuencias

- (+) **Redes de autor y keyword limpias de duplicados aproximados** sin abandonar el determinismo
  ni la reproducibilidad (ADR 0017/0022): el dedup es estructura, no IA.
- (+) **Núcleo liviano intacto:** `rapidfuzz` solo se instala con `[dedup]`; el import perezoso evita
  acoplar el núcleo (ADR 0005).
- (+) **`_raw` preservado** → el colapso es auditable y reversible re-derivando desde el crudo.
- (−) **Cobertura por umbral, no exhaustiva:** un threshold conservador deja pasar variantes muy
  divergentes; subirlo arriesga falsos positivos. El `threshold` por-campo es la perilla.
- (−) **`splink` (record-linkage probabilístico) queda fuera de V1:** si más adelante hace falta
  enlazar identidades entre fuentes heterogéneas, requiere un ADR nuevo (y aceptar el no-determinismo
  o seedearlo explícitamente).

> **AS-BUILT (2026-06-16):** `deduplicate_authors`/`deduplicate_keywords` en
> `src/bib2graph/preprocessors/dedup.py`, exportadas desde `bib2graph.preprocessors`, extra
> `[dedup] = rapidfuzz>=3,<4`. Algoritmo `token_sort_ratio` + Union-Find + canónico
> más-frecuente/desempate-id. **388 tests verdes** (mypy/ruff limpios; núcleo sin importar `rapidfuzz`).
