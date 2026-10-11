"""exporters — exportadores de redes y de corpus (Hito 2 + ADR 0050 D4).

Expone ``GraphMLExporter`` (para Gephi/VOSviewer/Cytoscape) y
``CsvExporter`` (para pandas) para redes de build (API.md §9, decisión D5).

Expone ``ArrowExporter`` (Feather/Arrow IPC) y ``BibtexExporter`` (``.bib``)
para el CORPUS scopeado (ADR 0050 D4, issue #293).
"""

from __future__ import annotations

from bib2graph.exporters.arrow import ArrowExporter
from bib2graph.exporters.bibtex import BibtexExporter
from bib2graph.exporters.csv import CsvExporter
from bib2graph.exporters.graphml import GraphMLExporter

__all__ = [
    "ArrowExporter",
    "BibtexExporter",
    "CsvExporter",
    "GraphMLExporter",
]
