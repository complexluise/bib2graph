"""cli._ingest — Re-exportación de la pipeline de ingesta automática.

La implementación canónica vive en ``preprocessors.pipeline`` (issue #175).
Este módulo la re-exporta para que los imports existentes del CLI y de los
tests — ``from bib2graph.cli._ingest import normalize_and_dedup`` — sigan
funcionando sin cambios.

Orden determinista de la pipeline:
  1. ``Preprocessor().normalize``  — canonicaliza ``authors_id`` y ``language``.
  2. ``deduplicate_authors(threshold=THRESHOLD_AUTHORS)``  — colapsa variantes.
  3. ``deduplicate_keywords(threshold=THRESHOLD_KEYWORDS)`` — colapsa variantes.

El dedup opera sobre el corpus COMPLETO (existing + incoming ya mergeados),
garantizando deduplicación cross-biblioteca (no solo intra-lote).

Reloj en la frontera (R2): ``applied_at`` se inyecta desde la función
llamante (``run_seed``, ``run_restore``, etc.) con un único
``datetime.now(UTC)`` por invocación — mismo patrón que ``decided_at``
en curación.  Ver ``preprocessor.py``.
"""

from __future__ import annotations

# Re-exportar desde el módulo neutral para backward compat con imports existentes.
from bib2graph.preprocessors.pipeline import normalize_and_dedup

__all__ = ["normalize_and_dedup"]
