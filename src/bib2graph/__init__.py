"""bib2graph — librería para construir redes bibliométricas reproducibles.

Hito 1: núcleo de la tabla canónica ``Corpus``.
Hito 1.5: costura ``TabularBackend`` + ``InMemoryBackend``.
Hito 2: proyectores, analizadores, exportadores y ``Networks``.
Hito 3: ``DuckDBBackend`` / ``DuckDBStore`` (biblioteca viva, carga perezosa).
Hito 4: ``OpenAlexSource``, ``BibtexSource``, ``Source``, ``SeedResult``
        (costura de siembra directa — httpx es núcleo, sin carga perezosa).

Símbolos públicos exportados:
  - Hito 1/1.5: ``Corpus``, ``Manifest``, ``CorpusSnapshot``, ``SchemaError``,
    ``TabularBackend``, ``InMemoryBackend``.
  - Hito 2: proyectores (5), ``Networks``, ``NetworkArtifact``,
    ``GraphMLExporter``, ``CsvExporter``, ``network_metrics``, ``centrality``,
    ``detect_communities``, ``assortativity``, ``community_composition``,
    ``cocitation_quality_report``, ``QualityThresholds``.
  - Hito 3: ``DuckDBBackend``, ``DuckDBStore`` (carga perezosa — PEP 562).
  - Hito 4: ``OpenAlexSource``, ``BibtexSource``, ``Source``, ``SeedResult``
    (import directo; httpx es núcleo, sin efectos de import).

``DuckDBBackend`` y ``DuckDBStore`` se exponen vía ``__getattr__`` perezoso
(PEP 562) para que ``import bib2graph`` NO importe ``duckdb`` y el smoke test
del Hito 0 siga verde (``'duckdb' not in sys.modules`` tras el import).
``OpenAlexSource`` y ``BibtexSource`` se importan directamente (httpx es
núcleo — no hay efectos de import que deban diferirse).

Ver ``docs/API.md`` §1-2, §4, §7-10.
"""

from __future__ import annotations

from bib2graph.backends import InMemoryBackend, TabularBackend
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
from bib2graph.sources import BibtexSource, OpenAlexSource, SeedResult, Source

__all__ = [
    "AuthorCollaborationProjector",
    "BibliographicCouplingProjector",
    "BibtexSource",
    "CoCitationProjector",
    "Corpus",
    "CorpusSnapshot",
    "CsvExporter",
    "DuckDBBackend",
    "DuckDBStore",
    "GraphMLExporter",
    "InMemoryBackend",
    "InstitutionCollaborationProjector",
    "KeywordCoOccurrenceProjector",
    "Manifest",
    "NetworkArtifact",
    "Networks",
    "OpenAlexSource",
    "QualityThresholds",
    "SchemaError",
    "SeedResult",
    "Source",
    "TabularBackend",
    "assortativity",
    "centrality",
    "cocitation_quality_report",
    "community_composition",
    "detect_communities",
    "network_metrics",
]

# ---------------------------------------------------------------------------
# Carga perezosa de símbolos que importan duckdb (PEP 562)
#
# ``import bib2graph`` NO arrastra duckdb.  Solo ``bib2graph.DuckDBBackend``
# o ``bib2graph.DuckDBStore`` lo cargan bajo demanda.
# ---------------------------------------------------------------------------

_LAZY = {
    "DuckDBBackend": ("bib2graph.backends.duckdb", "DuckDBBackend"),
    "DuckDBStore": ("bib2graph.stores.duckdb", "DuckDBStore"),
}


def __getattr__(name: str) -> object:
    if name in _LAZY:
        module_name, attr = _LAZY[name]
        import importlib

        mod = importlib.import_module(module_name)
        return getattr(mod, attr)
    raise AttributeError(f"module 'bib2graph' has no attribute {name!r}")
