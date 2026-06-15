"""foraging — forrajeo/chaining rankeado por *information scent*.

Re-exporta las piezas públicas del paquete.  ``explain_candidate`` es
una capacidad gateada en el extra ``[llm]`` y NO se re-exporta desde
la raíz de bib2graph; se importa desde este sub-paquete explícitamente.

Ver docs/API.md §5 y ADR 0008.
"""

from __future__ import annotations

from bib2graph.foraging.base import Direction, GrowthPreview, RankedCandidates
from bib2graph.foraging.explain import explain_candidate
from bib2graph.foraging.forager import Forager

__all__ = [
    "Direction",
    "Forager",
    "GrowthPreview",
    "RankedCandidates",
    "explain_candidate",
]
