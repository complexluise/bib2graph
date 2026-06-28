"""networks — proyectores, analizadores y Networks API del Hito 2.

Reexporta los símbolos públicos del paquete de redes:
  - Proyectores (5 implementaciones + constante MIN_WEIGHT_DEFAULT).
  - Analizadores (funciones puras + QualityThresholds).
  - ``NetworkArtifact`` y ``Networks`` (facade de alto nivel).
  - ``decorate`` / ``decorate_graph`` (capa de decoración de nodos, issue #25).
  - ``cluster_table`` (tabla de resumen de comunidades por cluster, issue #31).

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
from bib2graph.networks.clusters import cluster_table
from bib2graph.networks.decorate import decorate, decorate_graph
from bib2graph.networks.facade import Networks, predict_build_preview
from bib2graph.networks.projectors import (
    MIN_WEIGHT_DEFAULT,
    AuthorCollaborationProjector,
    BibliographicCouplingProjector,
    CoCitationProjector,
    InstitutionCollaborationProjector,
    KeywordCoOccurrenceProjector,
    collect_item_to_papers,
)
from bib2graph.networks.spec import NetworkArtifact, NetworkSpec, load_specs

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
    "cluster_table",
    "cocitation_quality_report",
    "collect_item_to_papers",
    "community_composition",
    "decorate",
    "decorate_graph",
    "detect_communities",
    "load_specs",
    "network_metrics",
    "predict_build_preview",
]
