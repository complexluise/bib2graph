"""networks — proyectores, analizadores y Networks API del Hito 2.

Reexporta los símbolos públicos del paquete de redes:
  - Proyectores (5 implementaciones + constante MIN_WEIGHT_DEFAULT).
  - Analizadores (funciones puras + QualityThresholds).
  - ``NetworkArtifact`` y ``Networks`` (facade de alto nivel).

Ver API.md §7-10.
"""

from __future__ import annotations

from bib2graph.networks.analyzer import (
    QualityThresholds,
    assortativity,
    centrality,
    cocitation_quality_report,
    community_composition,
    detect_communities,
    network_metrics,
)
from bib2graph.networks.facade import Networks
from bib2graph.networks.projectors import (
    MIN_WEIGHT_DEFAULT,
    AuthorCollaborationProjector,
    BibliographicCouplingProjector,
    CoCitationProjector,
    InstitutionCollaborationProjector,
    KeywordCoOccurrenceProjector,
    collect_item_to_papers,
)
from bib2graph.networks.spec import NetworkArtifact, NetworkSpec

__all__ = [
    "MIN_WEIGHT_DEFAULT",
    "AuthorCollaborationProjector",
    "BibliographicCouplingProjector",
    "CoCitationProjector",
    "InstitutionCollaborationProjector",
    "KeywordCoOccurrenceProjector",
    "NetworkArtifact",
    "NetworkSpec",
    "Networks",
    "QualityThresholds",
    "assortativity",
    "centrality",
    "cocitation_quality_report",
    "collect_item_to_papers",
    "community_composition",
    "detect_communities",
    "network_metrics",
]
