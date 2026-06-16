"""preprocessors.dedup — deduplicación fuzzy determinista de autores y keywords.

Implementa ``deduplicate_authors`` y ``deduplicate_keywords``: funciones puras
que colapsan variantes ortográficas cercanas en un único canónico, operando
sobre ``authors_id`` y ``keywords_id`` respectivamente (NUNCA sobre ``_raw``).

Decisiones de diseño (ADR 0017 / Hito 7):
- Librería: ``rapidfuzz`` únicamente (extra ``[dedup]``).  Import perezoso
  dentro de cada función pública; importar este módulo nunca falla aunque el
  extra esté ausente.
- Scorer: ``rapidfuzz.fuzz.token_sort_ratio``.  Ordena los tokens antes de
  comparar, lo que maneja variantes de orden en nombres de autores
  (``"smith john"`` vs ``"john smith"``) y en frases multi-palabra de keywords.
  Devuelve 0-100; se compara contra ``threshold * 100``.
- Agrupamiento: componentes conexos sobre el grafo de similitud (si A~B y
  B~C, {A,B,C} forman un cluster).  Las variantes se iteran en orden
  lexicográfico (``sorted``) para determinismo byte a byte.
- Canónico del cluster: variante más frecuente (en cuántos papers aparece);
  desempate por id ascendente (lexicográfico).
- Orden dentro de las listas remapeadas: orden de primera aparición tras el
  remapeo (preserva el orden original de la lista por paper, colapsando
  duplicados).  Determinista porque Arrow entrega orden estable.
- Idempotencia garantizada: tras el colapso, ningún par de variantes
  restantes supera el threshold (el canónico se mapea a sí mismo).
- NO muta la entrada: semántica de valor, devuelve ``Corpus`` nuevo.
- Registra ``PreprocRef`` en el Manifest con librería, versión, threshold y
  número de clusters colapsados (auditoría/reproducibilidad, ADR 0017).

Ver docs/API.md §6, ADR 0017.
"""

from __future__ import annotations

import importlib.metadata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bib2graph.corpus import Corpus


def _rapidfuzz_version() -> str:
    """Devuelve la versión instalada de rapidfuzz, o 'unknown' si falla."""
    try:
        return importlib.metadata.version("rapidfuzz")
    except Exception:
        return "unknown"


def _build_clusters(
    variants: list[str],
    threshold: float,
) -> list[frozenset[str]]:
    """Agrupa variantes en componentes conexos por similitud ≥ threshold.

    Itera los pares de variantes en orden lexicográfico para garantizar
    determinismo.  La transitividad se resuelve con Union-Find (si A~B y B~C,
    {A,B,C} forman un cluster).

    Asume que ``rapidfuzz`` ya está importado (se llama solo desde funciones
    que ya verificaron el import).

    Args:
        variants: Lista de variantes distintas ordenadas lexicográficamente.
        threshold: Umbral de similitud en [0, 1].  Se compara contra
            ``token_sort_ratio / 100``.

    Returns:
        Lista de frozensets, cada uno representando un cluster de variantes.
    """
    import rapidfuzz.fuzz as _fuzz

    # Union-Find simple con path compression
    parent: dict[str, str] = {v: v for v in variants}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            # Raíz lexicográficamente menor gana (determinismo)
            if ra < rb:
                parent[rb] = ra
            else:
                parent[ra] = rb

    threshold_100 = threshold * 100
    for i, va in enumerate(variants):
        for vb in variants[i + 1 :]:
            score = float(_fuzz.token_sort_ratio(va, vb))
            if score >= threshold_100:
                union(va, vb)

    # Agrupar por raíz
    groups: dict[str, set[str]] = {}
    for v in variants:
        root = find(v)
        groups.setdefault(root, set()).add(v)

    return [frozenset(g) for g in groups.values()]


def _canonical_of_cluster(
    cluster: frozenset[str],
    freq: dict[str, int],
) -> str:
    """Elige el canónico del cluster: más frecuente, desempate lexicográfico.

    Clave: ``(-frecuencia, variante)`` → ``min`` devuelve la más frecuente
    y, ante empate, la lexicográficamente menor (id ascendente).

    Args:
        cluster: Conjunto de variantes del cluster.
        freq: Frecuencia de cada variante en el corpus (nº de papers).

    Returns:
        Variante canónica del cluster.
    """
    return min(cluster, key=lambda v: (-freq.get(v, 0), v))


def _compute_freq(rows: list[dict[str, object]], col: str) -> dict[str, int]:
    """Cuenta en cuántos papers aparece cada variante de la columna ``col``.

    Args:
        rows: Filas del corpus como lista de dicts.
        col: Nombre de la columna de tipo ``list[str] | None``.

    Returns:
        Dict ``{variante: frecuencia}`` (frecuencia = nº de papers distintos).
    """
    freq: dict[str, int] = {}
    for row in rows:
        variants = row.get(col)
        if not isinstance(variants, list):
            continue
        seen_in_row: set[str] = set()
        for v in variants:
            if isinstance(v, str) and v not in seen_in_row:
                freq[v] = freq.get(v, 0) + 1
                seen_in_row.add(v)
    return freq


def _remap_rows(
    rows: list[dict[str, object]],
    col: str,
    remap: dict[str, str],
) -> list[dict[str, object]]:
    """Aplica el mapa de variante→canónico a la columna ``col`` de cada fila.

    Orden dentro de la lista resultante: orden de primera aparición tras el
    remapeo (los duplicados que surgen por el colapso se eliminan).

    Args:
        rows: Filas del corpus como lista de dicts.
        col: Nombre de la columna a remapear.
        remap: Dict ``{variante: canónico}``.

    Returns:
        Nueva lista de filas con la columna remapeada.
    """
    result: list[dict[str, object]] = []
    for row in rows:
        variants = row.get(col)
        if not isinstance(variants, list):
            result.append(dict(row))
            continue
        new_vals: list[str] = []
        seen: set[str] = set()
        for v in variants:
            if not isinstance(v, str):
                continue
            canonical = remap.get(v, v)
            if canonical not in seen:
                seen.add(canonical)
                new_vals.append(canonical)
        new_row = dict(row)
        new_row[col] = new_vals if new_vals else None
        result.append(new_row)
    return result


def _deduplicate_col(
    corpus: Corpus,
    *,
    col: str,
    threshold: float,
    preproc_name: str,
) -> tuple[Corpus, int]:
    """Núcleo de deduplicación fuzzy sobre una columna de lista de strings.

    Común a autores y keywords.  Devuelve el Corpus nuevo y el nº de clusters
    colapsados (clusters con más de una variante).

    Args:
        corpus: Corpus de entrada (no muta).
        col: Nombre de la columna (``authors_id`` o ``keywords_id``).
        threshold: Umbral de similitud en [0, 1].
        preproc_name: Nombre del preprocesador para registrar en el Manifest.

    Returns:
        Tupla ``(Corpus nuevo, nº de clusters colapsados)``.

    Raises:
        ImportError: Si ``rapidfuzz`` no está instalado.
    """
    # Import perezoso de rapidfuzz — falla ruidoso si falta el extra
    try:
        import rapidfuzz.fuzz as _  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "rapidfuzz no está instalado. Instalá el extra: uv sync --extra dedup"
        ) from exc

    import pyarrow as pa

    from bib2graph.corpus import Corpus as _Corpus
    from bib2graph.corpus import PreprocRef
    from bib2graph.schemas import CORPUS_SCHEMA

    rows = corpus.to_arrow().to_pylist()

    # 1. Frecuencia de cada variante en el corpus
    freq = _compute_freq(rows, col)
    if not freq:
        # Sin variantes: corpus sin cambios
        return corpus, 0

    # 2. Variantes ordenadas (determinismo)
    variants_sorted = sorted(freq.keys())

    # 3. Clusters por componentes conexos
    clusters = _build_clusters(variants_sorted, threshold)

    # 4. Mapa variante → canónico + conteo de clusters no triviales
    n_collapsed = 0
    remap: dict[str, str] = {}
    for cluster in clusters:
        canonical = _canonical_of_cluster(cluster, freq)
        if len(cluster) > 1:
            n_collapsed += 1
        for v in cluster:
            remap[v] = canonical

    # 5. Remapeo de filas
    remapped_rows = _remap_rows(rows, col, remap)

    # 6. Construir Corpus nuevo
    new_table = pa.Table.from_pylist(remapped_rows, schema=CORPUS_SCHEMA)
    new_corpus = _Corpus.from_arrow(new_table)

    # 7. Registrar PreprocRef en el Manifest
    rf_version = _rapidfuzz_version()
    preproc_ref = PreprocRef(
        name=preproc_name,
        params={
            "library": "rapidfuzz",
            "rapidfuzz_version": rf_version,
            "scorer": "token_sort_ratio",
            "threshold": str(threshold),
            "n_clusters_collapsed": str(n_collapsed),
        },
    )
    new_manifest = corpus.manifest.model_copy(
        update={"preprocessors": [*corpus.manifest.preprocessors, preproc_ref]}
    )
    return new_corpus.with_manifest(new_manifest), n_collapsed


def deduplicate_authors(
    corpus: Corpus,
    *,
    threshold: float = 0.92,
) -> Corpus:
    """Deduplica variantes de ``authors_id`` usando similitud fuzzy.

    Colapsa variantes ortográficas de autores que superan el ``threshold``
    de similitud (``token_sort_ratio`` de rapidfuzz).  El canónico es la
    variante más frecuente en el corpus; ante empate, la lexicográficamente
    menor.

    Solo opera sobre ``authors_id`` (campo ``_id``); ``authors_raw`` no se
    modifica (fuente reversible).

    Idempotente: una segunda pasada no cambia el resultado.

    Import perezoso de ``rapidfuzz``; si el extra ``[dedup]`` no está
    instalado, lanza ``ImportError`` con instrucción de instalación.

    Args:
        corpus: Corpus de entrada (no muta).
        threshold: Umbral de similitud en [0, 1].  Default 0.92 (más alto
            que keywords para minimizar colapso de homónimos).

    Returns:
        Nuevo Corpus con ``authors_id`` deduplicado y ``PreprocRef``
        registrado en el Manifest.

    Raises:
        ImportError: Si ``rapidfuzz`` no está instalado
            (``uv sync --extra dedup``).
    """
    from bib2graph.constants import Col

    result, _ = _deduplicate_col(
        corpus,
        col=Col.AUTHORS_ID,
        threshold=threshold,
        preproc_name="deduplicate_authors",
    )
    return result


def deduplicate_keywords(
    corpus: Corpus,
    *,
    threshold: float = 0.90,
) -> Corpus:
    """Deduplica variantes de ``keywords_id`` usando similitud fuzzy.

    Colapsa variantes ortográficas de keywords que superan el ``threshold``
    de similitud (``token_sort_ratio`` de rapidfuzz).  El canónico es la
    variante más frecuente en el corpus; ante empate, la lexicográficamente
    menor.

    Solo opera sobre ``keywords_id`` (campo ``_id``); ``keywords_raw`` no se
    modifica (fuente reversible).

    Idealmente se llama después del thesaurus (Hito 5), pero no depende de él.
    Idempotente: una segunda pasada no cambia el resultado.

    Import perezoso de ``rapidfuzz``; si el extra ``[dedup]`` no está
    instalado, lanza ``ImportError`` con instrucción de instalación.

    Args:
        corpus: Corpus de entrada (no muta).
        threshold: Umbral de similitud en [0, 1].  Default 0.90.

    Returns:
        Nuevo Corpus con ``keywords_id`` deduplicado y ``PreprocRef``
        registrado en el Manifest.

    Raises:
        ImportError: Si ``rapidfuzz`` no está instalado
            (``uv sync --extra dedup``).
    """
    from bib2graph.constants import Col

    result, _ = _deduplicate_col(
        corpus,
        col=Col.KEYWORDS_ID,
        threshold=threshold,
        preproc_name="deduplicate_keywords",
    )
    return result
