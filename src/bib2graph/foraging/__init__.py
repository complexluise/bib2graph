"""foraging — forrajeo/chaining rankeado por *information scent* bibliométrico.

Re-exporta las piezas públicas del paquete.

El *information scent* usa los proyectores del núcleo de redes (acoplamiento
bibliográfico / co-citación) — sin LLM, sin embeddings (ADR 0022).
``explain_candidate`` y el extra ``[llm]`` fueron **eliminados** (R4, ADR 0022):
el "porqué" de un candidato lo da la estructura visible, no un modelo generativo.

Ver docs/API.md §5 y ADR 0020/0022.
"""

from __future__ import annotations

from bib2graph.foraging.base import Direction, GrowthPreview, RankedCandidates
from bib2graph.foraging.forager import Forager

__all__ = [
    "Direction",
    "Forager",
    "GrowthPreview",
    "RankedCandidates",
]
