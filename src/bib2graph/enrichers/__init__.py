"""enrichers — Enriquecedores de corpus bibliométrico.

Expone los enrichers del núcleo: ``OpenAlexEnricher`` (resolución
``references_id`` → ``references_doi``).  Los enrichers de extras
(p. ej. S2) se importan de forma perezosa desde sus extras.

Hito 8a: resolución references→DOI via OpenAlex.
Hito 8b (futuro): poblado de ``cited_by_id`` (segundo nivel de fetch).
"""

from __future__ import annotations

from bib2graph.enrichers.base import Enricher
from bib2graph.enrichers.openalex import OpenAlexEnricher

__all__ = ["Enricher", "OpenAlexEnricher"]
