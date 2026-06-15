"""Tests TDD del Hito 2 — Networks.build / Networks.quick / NetworkArtifact.

Tests prescriptos por docs/ROADMAP.md §Hito 2:
- Networks.quick devuelve los 4 artefactos esperados con sus spec.kind.
  (No se re-verifican métricas ya cubiertas en test_analyzer.py.)

Marcador: ``unit`` (sin red, sin I/O).
"""

from __future__ import annotations

import sys
from unittest.mock import patch

import pyarrow as pa
import pytest

from bib2graph.corpus import Corpus
from bib2graph.networks.facade import Networks
from bib2graph.networks.spec import NetworkArtifact, NetworkSpec
from bib2graph.schemas import CORPUS_SCHEMA

# ---------------------------------------------------------------------------
# Fixture — corpus sintético mínimo para Networks.quick
# ---------------------------------------------------------------------------


def _make_corpus_minimo() -> Corpus:
    """Corpus de 3 papers con autores, instituciones, keywords y referencias."""
    rows = [
        {
            "id": f"P{i}",
            "openalex_id": None,
            "doi": None,
            "title": f"Paper {i}",
            "year": 2020,
            "abstract": None,
            "source": None,
            "language": None,
            "publisher": None,
            "research_areas": None,
            "is_seed": True,
            "curation_status": "candidate",
            "provenance": None,
            "authors_raw": None,
            "authors_id": [f"AUTH_{i}", "AUTH_0"],  # AUTH_0 aparece en todos
            "authors_affiliations": None,
            "keywords_raw": None,
            "keywords_id": [f"KW_{i}", "KW_SHARED"],  # KW_SHARED en todos
            "institutions_raw": None,
            "institutions_id": [f"INST_{i}"],
            "references_id": [f"REF_{i}", "REF_SHARED"],  # REF_SHARED en todos
            "references_doi": None,
            "cited_by_id": None,
        }
        for i in range(3)
    ]
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    return Corpus.from_arrow(table)


# ---------------------------------------------------------------------------
# Networks.quick
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_networks_quick_devuelve_4_artefactos() -> None:
    """Networks.quick devuelve exactamente 4 NetworkArtifact (D3: sin co-citación)."""
    corpus = _make_corpus_minimo()
    artifacts = Networks.quick(corpus)

    assert len(artifacts) == 4


@pytest.mark.unit
def test_networks_quick_spec_kinds() -> None:
    """Los 4 artefactos tienen los spec.kind esperados (coupling, author, inst, keyword)."""
    corpus = _make_corpus_minimo()
    artifacts = Networks.quick(corpus)

    kinds = {a.spec.kind for a in artifacts}
    expected = {
        "bibliographic_coupling",
        "author_collab",
        "institution_collab",
        "keyword_cooccurrence",
    }
    assert kinds == expected


@pytest.mark.unit
def test_networks_quick_todos_son_network_artifact() -> None:
    """Cada elemento devuelto por quick es una instancia de NetworkArtifact."""
    corpus = _make_corpus_minimo()
    artifacts = Networks.quick(corpus)

    for art in artifacts:
        assert isinstance(art, NetworkArtifact)


@pytest.mark.unit
def test_networks_quick_artefactos_tienen_graph_y_metrics() -> None:
    """Cada NetworkArtifact tiene .graph y .metrics no nulos."""
    corpus = _make_corpus_minimo()
    artifacts = Networks.quick(corpus)

    for art in artifacts:
        assert art.graph is not None
        assert art.metrics is not None
        assert isinstance(art.metrics, dict)


# ---------------------------------------------------------------------------
# Networks.build
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_networks_build_con_spec_coupling() -> None:
    """Networks.build(corpus, spec) construye un NetworkArtifact para coupling."""
    corpus = _make_corpus_minimo()
    spec = NetworkSpec(kind="bibliographic_coupling")

    artifact = Networks.build(corpus, spec)

    assert isinstance(artifact, NetworkArtifact)
    assert artifact.spec.kind == "bibliographic_coupling"
    assert artifact.graph is not None


@pytest.mark.unit
def test_networks_build_spec_en_artifact() -> None:
    """El spec pasado a build aparece en el NetworkArtifact resultante."""
    corpus = _make_corpus_minimo()
    spec = NetworkSpec(kind="author_collab", min_weight=1)

    artifact = Networks.build(corpus, spec)

    assert artifact.spec is spec


# ---------------------------------------------------------------------------
# Networks.build — ImportError propaga fuerte cuando falta python-louvain
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_networks_build_louvain_propaga_import_error() -> None:
    """Networks.build con clustering='louvain' propaga ImportError si falta python-louvain.

    Verifica la lección 7 de AGENTS.md: dep faltante = fallo duro, no silencioso.
    Se monkeypatchea 'community' para simular ausencia del paquete.
    """
    corpus = _make_corpus_minimo()
    spec = NetworkSpec(kind="author_collab", clustering="louvain")

    with (
        patch.dict(sys.modules, {"community": None}),  # type: ignore[dict-item]
        pytest.raises(ImportError, match="python-louvain"),
    ):
        Networks.build(corpus, spec)
