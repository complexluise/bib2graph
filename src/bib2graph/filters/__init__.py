"""filters — filtros PRISMA deterministas (funciones puras).

Exporta ``FilterCriterion``, ``apply_filter`` y ``apply_filters``.

Los filtros MARCAN ``curation_status='rejected'`` pero NO borran filas.
El conteo PRISMA (before/after) sale de los papers que no son ``rejected``.

Ver docs/API.md §convenciones (CLI ``filter``), corpus §1.1.
"""

from __future__ import annotations

from bib2graph.filters.prisma import FilterCriterion, apply_filter, apply_filters

__all__ = ["FilterCriterion", "apply_filter", "apply_filters"]
