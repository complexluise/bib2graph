"""preprocessors — normalización, thesaurus multilingüe y dedup fuzzy.

Exporta ``Preprocessor`` y las funciones puras de normalización, thesaurus
y deduplicación fuzzy, más la pipeline de ingesta automática.

Las funciones de dedup (``deduplicate_authors``, ``deduplicate_keywords``)
requieren el extra ``[dedup]`` (``uv sync --extra dedup``).  El import del
módulo no falla si el extra está ausente; solo falla al llamar las funciones.

Ver docs/API.md §6, ADR 0011, ADR 0017.
"""

from __future__ import annotations

from bib2graph.preprocessors.dedup import deduplicate_authors, deduplicate_keywords
from bib2graph.preprocessors.pipeline import (
    THRESHOLD_AUTHORS,
    THRESHOLD_KEYWORDS,
    normalize_and_dedup,
)
from bib2graph.preprocessors.preprocessor import Preprocessor

__all__ = [
    "THRESHOLD_AUTHORS",
    "THRESHOLD_KEYWORDS",
    "Preprocessor",
    "deduplicate_authors",
    "deduplicate_keywords",
    "normalize_and_dedup",
]
