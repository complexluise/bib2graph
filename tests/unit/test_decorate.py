"""Tests de la capa decorate — issue #25.

Verifica:
- ``decorate_graph`` inyecta ``label`` correcto por ``NetworkKind``.
- Atributos ``year``/``is_seed``/``curation_status``/``degree_centrality`` presentes
  en nodos de paper.
- Atributo ``community`` presente cuando se pasa ``communities``.
- Round-trip GraphML: exportar grafo decorado → releer → nodos tienen ``label``
  legible (no el id crudo).
- Los proyectores siguen puros (sin ``label``) — la decoración es aparte.
- Determinismo: mismo corpus → mismos atributos.

Marcador: ``unit`` (sin red, sin I/O).
"""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import pyarrow as pa
import pytest

from bib2graph.constants import NetworkKind
from bib2graph.corpus import Corpus
from bib2graph.networks.decorate import LABEL_MAX_CHARS, decorate, decorate_graph
from bib2graph.networks.facade import Networks
from bib2graph.networks.projectors import (
    AuthorCollaborationProjector,
    BibliographicCouplingProjector,
    KeywordCoOccurrenceProjector,
)
from bib2graph.networks.spec import NetworkSpec
from bib2graph.schemas import CORPUS_SCHEMA

# ---------------------------------------------------------------------------
# Fixture — corpus sintético con datos suficientes para todos los kinds
# ---------------------------------------------------------------------------


def _make_table() -> pa.Table:
    """Tabla Arrow sintética con 3 papers que comparten referencias, autores y keywords."""
    rows = [
        {
            "id": "P0",
            "openalex_id": None,
            "doi": None,
            "title": "Artículo cero",
            "year": 2020,
            "abstract": None,
            "source": None,
            "language": None,
            "publisher": None,
            "research_areas": None,
            "is_seed": True,
            "curation_status": "accepted",
            "provenance": None,
            "authors_raw": ["Autor Uno", "Autor Dos"],
            "authors_id": ["auth_1", "auth_2"],
            "authors_affiliations": None,
            "keywords_raw": None,
            "keywords_id": ["machine_learning", "redes"],
            "institutions_raw": ["Univ. A"],
            "institutions_id": ["inst_a"],
            "references_id": ["R_shared", "R_x"],
            "references_doi": None,
            "cited_by_id": None,
        },
        {
            "id": "P1",
            "openalex_id": None,
            "doi": None,
            "title": "Artículo uno",
            "year": 2021,
            "abstract": None,
            "source": None,
            "language": None,
            "publisher": None,
            "research_areas": None,
            "is_seed": True,
            "curation_status": "candidate",
            "provenance": None,
            "authors_raw": ["Autor Uno", "Autor Tres"],
            "authors_id": ["auth_1", "auth_3"],
            "authors_affiliations": None,
            "keywords_raw": None,
            "keywords_id": ["machine_learning", "grafos"],
            "institutions_raw": ["Univ. B"],
            "institutions_id": ["inst_b"],
            "references_id": ["R_shared", "R_y"],
            "references_doi": None,
            "cited_by_id": None,
        },
        {
            "id": "P2",
            "openalex_id": None,
            "doi": None,
            "title": "Artículo dos",
            "year": 2022,
            "abstract": None,
            "source": None,
            "language": None,
            "publisher": None,
            "research_areas": None,
            "is_seed": False,
            "curation_status": "rejected",
            "provenance": None,
            "authors_raw": ["Autor Dos", "Autor Tres"],
            "authors_id": ["auth_2", "auth_3"],
            "authors_affiliations": None,
            "keywords_raw": None,
            "keywords_id": ["redes", "grafos"],
            "institutions_raw": ["Univ. A", "Univ. B"],
            "institutions_id": ["inst_a", "inst_b"],
            "references_id": ["R_shared", "R_z"],
            "references_doi": None,
            "cited_by_id": None,
        },
    ]
    return pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)


def _make_corpus() -> Corpus:
    return Corpus.from_arrow(_make_table())


# ---------------------------------------------------------------------------
# label por kind — un caso por tipo
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_label_paper_titulo_anio() -> None:
    """Nodo paper → label = 'título (año)'."""
    table = _make_table()
    projector = BibliographicCouplingProjector()
    g = projector.project(table)
    # Los 3 papers comparten R_shared → hay aristas; P0-P1, P0-P2, P1-P2
    assert g.number_of_nodes() > 0, "el grafo de acoplamiento debe tener nodos"

    decorate_graph(g, table, NetworkKind.BIBLIOGRAPHIC_COUPLING)

    for node in g.nodes():
        label = g.nodes[node]["label"]
        # El label nunca debe ser el id crudo (ej. "P0")
        assert label != str(node), f"label crudo en nodo {node!r}: {label!r}"
        # Debe contener el año entre paréntesis
        assert "(" in label and ")" in label, f"label sin año: {label!r}"


@pytest.mark.unit
def test_label_autor_nombre() -> None:
    """Nodo autor → label = nombre display (authors_raw correlativo)."""
    table = _make_table()
    projector = AuthorCollaborationProjector()
    g = projector.project(table)
    assert g.number_of_nodes() > 0

    decorate_graph(g, table, NetworkKind.AUTHOR_COLLAB)

    # auth_1 aparece en P0 y P1; authors_raw[0] = "Autor Uno"
    assert "auth_1" in g.nodes
    label = g.nodes["auth_1"]["label"]
    assert label == "Autor Uno", f"label inesperado: {label!r}"


@pytest.mark.unit
def test_label_keyword_es_la_keyword() -> None:
    """Nodo keyword → label = la keyword misma (keywords_id ya es legible)."""
    table = _make_table()
    projector = KeywordCoOccurrenceProjector()
    g = projector.project(table)
    assert g.number_of_nodes() > 0

    decorate_graph(g, table, NetworkKind.KEYWORD_COOCCURRENCE)

    for node in g.nodes():
        label = g.nodes[node]["label"]
        # Para keywords el label debe ser idéntico al nodo (es la keyword)
        assert label == str(node), (
            f"label de keyword no coincide: {label!r} vs {node!r}"
        )


# ---------------------------------------------------------------------------
# Atributos extra en nodos de paper
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_atributos_extra_en_nodos_paper() -> None:
    """Nodos de red de paper tienen year, is_seed, curation_status, degree_centrality."""
    table = _make_table()
    projector = BibliographicCouplingProjector()
    g = projector.project(table)

    decorate_graph(g, table, NetworkKind.BIBLIOGRAPHIC_COUPLING)

    for node in g.nodes():
        attrs = g.nodes[node]
        assert "year" in attrs, f"year falta en nodo {node!r}"
        assert isinstance(attrs["year"], int)
        assert "is_seed" in attrs, f"is_seed falta en nodo {node!r}"
        assert isinstance(attrs["is_seed"], bool)
        assert "curation_status" in attrs, f"curation_status falta en nodo {node!r}"
        assert "degree_centrality" in attrs, f"degree_centrality falta en nodo {node!r}"
        assert isinstance(attrs["degree_centrality"], float)


@pytest.mark.unit
def test_atributo_community_presente() -> None:
    """El atributo community se inyecta cuando se pasa communities."""
    table = _make_table()
    projector = BibliographicCouplingProjector()
    g = projector.project(table)

    # Comunidades sintéticas
    communities = {node: idx % 2 for idx, node in enumerate(g.nodes())}
    decorate_graph(
        g, table, NetworkKind.BIBLIOGRAPHIC_COUPLING, communities=communities
    )

    for node in g.nodes():
        assert "community" in g.nodes[node], f"community falta en nodo {node!r}"
        assert isinstance(g.nodes[node]["community"], int)


@pytest.mark.unit
def test_sin_community_sin_atributo() -> None:
    """Sin communities=None, el atributo community no aparece en los nodos."""
    table = _make_table()
    projector = BibliographicCouplingProjector()
    g = projector.project(table)

    decorate_graph(g, table, NetworkKind.BIBLIOGRAPHIC_COUPLING, communities=None)

    for node in g.nodes():
        assert "community" not in g.nodes[node], f"community inesperado en {node!r}"


# ---------------------------------------------------------------------------
# Round-trip GraphML
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_round_trip_graphml_label_legible(tmp_path: Path) -> None:
    """Exportar grafo decorado → releer GraphML → nodos tienen label legible."""
    table = _make_table()
    projector = BibliographicCouplingProjector()
    g = projector.project(table)
    decorate_graph(g, table, NetworkKind.BIBLIOGRAPHIC_COUPLING)

    # Exportar
    out_file = tmp_path / "network.graphml"
    nx.write_graphml(g, str(out_file))

    # Releer
    g2 = nx.read_graphml(str(out_file))

    for _node_id, data in g2.nodes(data=True):
        label = data.get("label", "")
        # El label no debe ser el id crudo; debe contener año
        assert "(" in label, f"label sin año tras round-trip: {label!r}"
        assert ")" in label


# ---------------------------------------------------------------------------
# Proyectores siguen puros (sin label)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_proyectores_son_puros_sin_label() -> None:
    """BibliographicCouplingProjector.project() NO setea label en los nodos.

    La decoración es responsabilidad exclusiva de decorate_graph, no del
    proyector (separación de capas, issue #25).
    """
    table = _make_table()
    projector = BibliographicCouplingProjector()
    g = projector.project(table)

    for node in g.nodes():
        assert "label" not in g.nodes[node], (
            f"Proyector no debe setear label; lo encontró en nodo {node!r}"
        )


@pytest.mark.unit
def test_proyector_autor_puro_sin_label() -> None:
    """AuthorCollaborationProjector.project() NO setea label en los nodos."""
    table = _make_table()
    projector = AuthorCollaborationProjector()
    g = projector.project(table)

    for node in g.nodes():
        assert "label" not in g.nodes[node], (
            f"Proyector no debe setear label; lo encontró en nodo {node!r}"
        )


@pytest.mark.unit
def test_proyector_keyword_puro_sin_label() -> None:
    """KeywordCoOccurrenceProjector.project() NO setea label en los nodos."""
    table = _make_table()
    projector = KeywordCoOccurrenceProjector()
    g = projector.project(table)

    for node in g.nodes():
        assert "label" not in g.nodes[node], (
            f"Proyector no debe setear label; lo encontró en nodo {node!r}"
        )


# ---------------------------------------------------------------------------
# Determinismo
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_decorate_es_determinista() -> None:
    """Mismo corpus → mismos atributos de nodo (dos llamadas independientes)."""
    table = _make_table()

    projector = BibliographicCouplingProjector()

    g1 = projector.project(table)
    decorate_graph(g1, table, NetworkKind.BIBLIOGRAPHIC_COUPLING)

    g2 = projector.project(table)
    decorate_graph(g2, table, NetworkKind.BIBLIOGRAPHIC_COUPLING)

    for node in g1.nodes():
        assert g1.nodes[node] == g2.nodes[node], (
            f"Atributos no deterministas en nodo {node!r}: "
            f"{g1.nodes[node]!r} vs {g2.nodes[node]!r}"
        )


# ---------------------------------------------------------------------------
# Integración: Networks.quick produce artefactos decorados
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_networks_quick_artefactos_decorados() -> None:
    """Networks.quick devuelve artefactos con label en todos los nodos."""
    corpus = _make_corpus()
    artifacts = Networks.quick(corpus)

    for art in artifacts:
        for node in art.graph.nodes():
            assert "label" in art.graph.nodes[node], (
                f"Nodo {node!r} sin label en red {art.spec.kind!r}"
            )


@pytest.mark.unit
def test_networks_build_artefacto_decorado() -> None:
    """Networks.build produce un artefacto con label en todos los nodos."""
    corpus = _make_corpus()
    spec = NetworkSpec(kind=NetworkKind.AUTHOR_COLLAB, clustering=None)
    art = Networks.build(corpus, spec)

    for node in art.graph.nodes():
        assert "label" in art.graph.nodes[node], (
            f"Nodo {node!r} sin label tras Networks.build"
        )


# ---------------------------------------------------------------------------
# decorate (función de alto nivel sobre NetworkArtifact)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_decorate_sobre_artifact() -> None:
    """decorate(artifact, table) decora el grafo del artifact correctamente."""
    from bib2graph.networks.spec import NetworkArtifact, NetworkSpec

    table = _make_table()
    projector = BibliographicCouplingProjector()
    g = projector.project(table)

    spec = NetworkSpec(kind=NetworkKind.BIBLIOGRAPHIC_COUPLING, clustering=None)
    artifact = NetworkArtifact(
        graph=g,
        metrics={},
        communities=None,
        assortativity=None,
        layout=None,
        spec=spec,
    )

    decorate(artifact, table)

    for node in artifact.graph.nodes():
        assert "label" in artifact.graph.nodes[node]


# ---------------------------------------------------------------------------
# Truncado de título largo
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_label_paper_truncado_si_titulo_largo() -> None:
    """Labels de paper con título largo se truncan a LABEL_MAX_CHARS + '...'."""
    titulo_largo = "A" * (LABEL_MAX_CHARS + 20)
    rows = [
        {
            "id": "PL",
            "openalex_id": None,
            "doi": None,
            "title": titulo_largo,
            "year": 2023,
            "abstract": None,
            "source": None,
            "language": None,
            "publisher": None,
            "research_areas": None,
            "is_seed": True,
            "curation_status": "accepted",
            "provenance": None,
            "authors_raw": None,
            "authors_id": ["auth_x"],
            "authors_affiliations": None,
            "keywords_raw": None,
            "keywords_id": None,
            "institutions_raw": None,
            "institutions_id": None,
            "references_id": ["R_only"],
            "references_doi": None,
            "cited_by_id": None,
        },
        {
            "id": "PL2",
            "openalex_id": None,
            "doi": None,
            "title": "Otro",
            "year": 2023,
            "abstract": None,
            "source": None,
            "language": None,
            "publisher": None,
            "research_areas": None,
            "is_seed": True,
            "curation_status": "accepted",
            "provenance": None,
            "authors_raw": None,
            "authors_id": ["auth_y"],
            "authors_affiliations": None,
            "keywords_raw": None,
            "keywords_id": None,
            "institutions_raw": None,
            "institutions_id": None,
            "references_id": ["R_only"],
            "references_doi": None,
            "cited_by_id": None,
        },
    ]
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    projector = BibliographicCouplingProjector()
    g = projector.project(table)
    assert "PL" in g.nodes

    decorate_graph(g, table, NetworkKind.BIBLIOGRAPHIC_COUPLING)

    label = g.nodes["PL"]["label"]
    assert label.endswith("..."), f"label largo no truncado: {label!r}"
    # El label truncado tiene exactamente LABEL_MAX_CHARS chars + "..."
    assert len(label) == LABEL_MAX_CHARS + 3
