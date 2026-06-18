"""cli._ingest — Helper de ingesta automática: normalize + dedup.

Aplica la pipeline de preprocesamiento automático al corpus completo en el
momento de la ingesta (seed / seed_from_bib / restore / chain), sobre el
corpus YA MERGEADO con el existente.  El thesaurus queda como paso explícito
(``b2g thesaurus``).

Orden determinista:
  1. ``Preprocessor().normalize``  — canonicaliza ``authors_id`` y ``language``.
  2. ``deduplicate_authors(threshold=0.92)``  — colapsa variantes de autores.
  3. ``deduplicate_keywords(threshold=0.90)`` — colapsa variantes de keywords.

El dedup opera sobre el corpus COMPLETO (existing + incoming ya mergeados),
garantizando deduplicación cross-biblioteca (no solo intra-lote).

Reloj en la frontera (R2): ``applied_at`` se inyecta desde la función
llamante (``run_seed``, ``run_restore``, etc.) con un único
``datetime.now(UTC)`` por invocación — mismo patrón que ``decided_at``
en curación.  Ver ``preprocessor.py``.
"""

from __future__ import annotations

from datetime import UTC, datetime

from bib2graph.corpus import Corpus
from bib2graph.preprocessors.dedup import deduplicate_authors, deduplicate_keywords
from bib2graph.preprocessors.preprocessor import Preprocessor

# Umbrales fijos del auto-preproc (ADR 0031).
_THRESHOLD_AUTHORS: float = 0.92
_THRESHOLD_KEYWORDS: float = 0.90


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
    (``b2g thesaurus``).

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
    ts = applied_at if applied_at is not None else datetime.now(UTC)
    preprocessor = Preprocessor()

    result = preprocessor.normalize(corpus, applied_at=ts)
    result = deduplicate_authors(result, threshold=_THRESHOLD_AUTHORS)
    result = deduplicate_keywords(result, threshold=_THRESHOLD_KEYWORDS)

    return result
