"""bib2graph — librería para construir redes bibliométricas reproducibles.

Hito 1: núcleo de la tabla canónica ``Corpus``.
Hito 2: proyectores, analizadores, exportadores y ``Networks``.

Símbolos públicos exportados:
  - Hito 1: ``Corpus``, ``Manifest``, ``CorpusSnapshot``, ``SchemaError``.
  - Hito 2: proyectores (5), ``Networks``, ``NetworkArtifact``,
    ``GraphMLExporter``, ``CsvExporter``, ``network_metrics``, ``centrality``,
    ``detect_communities``, ``assortativity``, ``community_composition``,
    ``cocitation_quality_report``, ``QualityThresholds``.

Ver ``docs/API.md`` §1, §7-10.
"""

from __future__ import annotations

from bib2graph.corpus import Corpus, CorpusSnapshot, Manifest
from bib2graph.exporters import CsvExporter, GraphMLExporter
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
    AuthorCollaborationProjector,
    BibliographicCouplingProjector,
    CoCitationProjector,
    InstitutionCollaborationProjector,
    KeywordCoOccurrenceProjector,
)
from bib2graph.networks.spec import NetworkArtifact
from bib2graph.schemas import SchemaError

__all__ = [
    "AuthorCollaborationProjector",
    "BibliographicCouplingProjector",
    "CoCitationProjector",
    "Corpus",
    "CorpusSnapshot",
    "CsvExporter",
    "GraphMLExporter",
    "InstitutionCollaborationProjector",
    "KeywordCoOccurrenceProjector",
    "Manifest",
    "NetworkArtifact",
    "Networks",
    "QualityThresholds",
    "SchemaError",
    "assortativity",
    "centrality",
    "cocitation_quality_report",
    "community_composition",
    "detect_communities",
    "network_metrics",
]
