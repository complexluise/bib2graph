"""preprocessors.pipeline — Punto de entrada único de la pipeline de preprocesamiento automático.

Orquesta normalize + dedup_authors + dedup_keywords sobre el corpus completo
ya mergeado.  Módulo neutral: sin I/O, sin Click, sin red.

Callers:
  - ``cli._ingest`` (ingesta: seed / chain / seed_from_bib)
  - ``service.snapshot`` (restore)

Ambas rutas importan ``normalize_and_dedup`` y los umbrales **desde aquí**,
garantizando que no pueden diverger (issue #175, ADR 0031).

Fuente única:
  ``THRESHOLD_AUTHORS`` y ``THRESHOLD_KEYWORDS`` son la fuente canónica.  No
  dupliques estos valores en ningún otro módulo; importalos desde acá.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bib2graph.corpus import Corpus

#: Umbral de similitud para deduplicar variantes de autores.
#: ``rapidfuzz.fuzz.token_sort_ratio`` >= ``THRESHOLD_AUTHORS * 100`` → colapso.
THRESHOLD_AUTHORS: float = 0.92

#: Umbral de similitud para deduplicar variantes de keywords.
#: ``rapidfuzz.fuzz.token_sort_ratio`` >= ``THRESHOLD_KEYWORDS * 100`` → colapso.
THRESHOLD_KEYWORDS: float = 0.90


def normalize_and_dedup(
    corpus: Corpus,
    *,
    applied_at: datetime | None = None,
) -> Corpus:
    """Aplica normalize + dedup_authors + dedup_keywords al corpus.

    Punto de entrada único para la ingesta automática.  Se llama DESPUÉS de
    ``Corpus.merge`` (corpus ya completo = existing + incoming), garantizando
    deduplicación cross-biblioteca: el dedup ve toda la biblioteca acumulada,
    no solo el lote entrante.

    Idempotente en contenido: re-correr sobre el mismo corpus produce el
    mismo resultado (las tres operaciones son idempotentes).

    El thesaurus NO se aplica aquí; es un paso explícito del usuario
    (``b2g build --thesaurus``).

    Args:
        corpus: Corpus de entrada (no muta; semántica de valor).
            Debe ser el corpus COMPLETO ya mergeado (existing + incoming).
        applied_at: Timestamp de la operación para el ``PreprocRef``.  La
            frontera CLI inyecta un único ``datetime.now(UTC)`` por
            invocación (R2).  Si ``None``, se usa ``datetime.now(UTC)``
            (para uso como librería independiente).

    Returns:
        Nuevo Corpus normalizado y deduplicado.
    """
    from bib2graph.preprocessors.dedup import deduplicate_authors, deduplicate_keywords
    from bib2graph.preprocessors.preprocessor import Preprocessor

    ts = applied_at if applied_at is not None else datetime.now(UTC)
    preprocessor = Preprocessor()

    result = preprocessor.normalize(corpus, applied_at=ts)
    result = deduplicate_authors(result, threshold=THRESHOLD_AUTHORS)
    result = deduplicate_keywords(result, threshold=THRESHOLD_KEYWORDS)

    return result
