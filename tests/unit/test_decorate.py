"""Tests de la capa decorate — issue #25 y #209.

Verifica:
- ``decorate_graph`` inyecta ``label`` correcto por ``NetworkKind``.
- Atributos ``year``/``is_seed``/``curation_status``/``degree_centrality`` presentes
  en nodos de paper.
- Atributos ``doi``/``url`` presentes en nodos de paper cuando hay DOI (#209).
- Atributo ``community`` presente cuando se pasa ``communities``.
- Round-trip GraphML: exportar grafo decorado → releer → nodos tienen ``label``
  legible (no el id crudo).
- Round-trip CSV y GraphML incluyen ``doi``/``url`` cuando están presentes (#209).
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
from bib2graph.exporters.csv import CsvExporter
from bib2graph.exporters.graphml import GraphMLExporter
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


# ---------------------------------------------------------------------------
# doi / url en nodos de paper (#209)
# ---------------------------------------------------------------------------


def _make_table_con_doi() -> pa.Table:
    """Tabla Arrow con un paper con DOI y otro sin DOI.

    Ambos comparten ``R_shared`` para que el acoplamiento bibliográfico cree
    una arista entre ellos (los dos nodos quedan en el grafo).
    """
    rows = [
        {
            "id": "PDOI",
            "source_id": None,
            "doi": "10.1234/ejemplo.2024",
            "title": "Paper con DOI",
            "year": 2024,
            "abstract": None,
            "source": None,
            "language": None,
            "publisher": None,
            "research_areas": None,
            "is_seed": True,
            "curation_status": "accepted",
            "provenance": None,
            "authors_raw": None,
            "authors_id": None,
            "authors_affiliations": None,
            "keywords_raw": None,
            "keywords_id": None,
            "institutions_raw": None,
            "institutions_id": None,
            "references_id": ["R_shared", "R_a"],
            "references_doi": None,
            "cited_by_id": None,
        },
        {
            "id": "PNODOI",
            "source_id": None,
            "doi": None,
            "title": "Paper sin DOI",
            "year": 2023,
            "abstract": None,
            "source": None,
            "language": None,
            "publisher": None,
            "research_areas": None,
            "is_seed": True,
            "curation_status": "candidate",
            "provenance": None,
            "authors_raw": None,
            "authors_id": None,
            "authors_affiliations": None,
            "keywords_raw": None,
            "keywords_id": None,
            "institutions_raw": None,
            "institutions_id": None,
            "references_id": ["R_shared", "R_b"],
            "references_doi": None,
            "cited_by_id": None,
        },
    ]
    return pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)


@pytest.mark.unit
def test_doi_y_url_en_nodo_paper_con_doi() -> None:
    """Nodo de paper con DOI → atributos ``doi`` y ``url`` correctos (#209)."""
    table = _make_table_con_doi()
    projector = BibliographicCouplingProjector()
    g = projector.project(table)
    assert "PDOI" in g.nodes, "PDOI debe estar en el grafo"

    decorate_graph(g, table, NetworkKind.BIBLIOGRAPHIC_COUPLING)

    attrs = g.nodes["PDOI"]
    assert "doi" in attrs, "atributo doi ausente en nodo con DOI"
    assert attrs["doi"] == "10.1234/ejemplo.2024"
    assert "url" in attrs, "atributo url ausente en nodo con DOI"
    assert attrs["url"] == "https://doi.org/10.1234/ejemplo.2024"


@pytest.mark.unit
def test_sin_doi_no_tiene_url_basura() -> None:
    """Nodo de paper sin DOI NO debe tener atributos ``doi`` ni ``url`` (#209).

    Garantiza que no aparezca ``url = 'https://doi.org/None'`` ni un doi vacío.
    """
    table = _make_table_con_doi()
    projector = BibliographicCouplingProjector()
    g = projector.project(table)
    assert "PNODOI" in g.nodes, "PNODOI debe estar en el grafo"

    decorate_graph(g, table, NetworkKind.BIBLIOGRAPHIC_COUPLING)

    attrs = g.nodes["PNODOI"]
    assert "doi" not in attrs, f"doi no debería estar en nodo sin DOI: {attrs!r}"
    assert "url" not in attrs, f"url no debería estar en nodo sin DOI: {attrs!r}"


@pytest.mark.unit
def test_doi_no_se_inyecta_en_nodo_autor() -> None:
    """Los atributos doi/url NO se inyectan en nodos de red de autores.

    Solo aplican a paper-kinds (bibliographic_coupling, cocitation).
    """
    rows = [
        {
            "id": "PA1",
            "source_id": None,
            "doi": "10.9999/autor.2024",
            "title": "Autor compartido A",
            "year": 2024,
            "abstract": None,
            "source": None,
            "language": None,
            "publisher": None,
            "research_areas": None,
            "is_seed": True,
            "curation_status": "accepted",
            "provenance": None,
            "authors_raw": ["Juan Pérez"],
            "authors_id": ["auth_shared"],
            "authors_affiliations": None,
            "keywords_raw": None,
            "keywords_id": None,
            "institutions_raw": None,
            "institutions_id": None,
            "references_id": None,
            "references_doi": None,
            "cited_by_id": None,
        },
        {
            "id": "PA2",
            "source_id": None,
            "doi": "10.9999/autor.2025",
            "title": "Autor compartido B",
            "year": 2025,
            "abstract": None,
            "source": None,
            "language": None,
            "publisher": None,
            "research_areas": None,
            "is_seed": True,
            "curation_status": "accepted",
            "provenance": None,
            "authors_raw": ["Juan Pérez", "Ana García"],
            "authors_id": ["auth_shared", "auth_other"],
            "authors_affiliations": None,
            "keywords_raw": None,
            "keywords_id": None,
            "institutions_raw": None,
            "institutions_id": None,
            "references_id": None,
            "references_doi": None,
            "cited_by_id": None,
        },
    ]
    t = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    projector = AuthorCollaborationProjector()
    g = projector.project(t)
    assert g.number_of_nodes() > 0, "grafo de autores debe tener nodos"

    decorate_graph(g, t, NetworkKind.AUTHOR_COLLAB)

    for node in g.nodes():
        attrs = g.nodes[node]
        assert "doi" not in attrs, (
            f"doi no debe estar en nodo de autor {node!r}: {attrs!r}"
        )
        assert "url" not in attrs, (
            f"url no debe estar en nodo de autor {node!r}: {attrs!r}"
        )


@pytest.mark.unit
def test_export_csv_incluye_doi_url(tmp_path: Path) -> None:
    """El CSV de un grafo decorado con DOIs incluye columnas doi y url (#209).

    CsvExporter es genérico: vuelca todos los atributos de nodo presentes.
    Si decorate_graph inyecta doi/url, aparecen en nodos.csv.
    """
    table = _make_table_con_doi()
    projector = BibliographicCouplingProjector()
    g = projector.project(table)
    decorate_graph(g, table, NetworkKind.BIBLIOGRAPHIC_COUPLING)

    CsvExporter().export(g, {}, tmp_path)

    content = (tmp_path / "nodos.csv").read_text(encoding="utf-8-sig")
    header = content.splitlines()[0]
    assert "doi" in header, f"columna doi ausente en nodos.csv; header: {header!r}"
    assert "url" in header, f"columna url ausente en nodos.csv; header: {header!r}"

    # El nodo con DOI tiene el valor correcto
    assert "10.1234/ejemplo.2024" in content
    assert "https://doi.org/10.1234/ejemplo.2024" in content


@pytest.mark.unit
def test_export_graphml_incluye_doi_url(tmp_path: Path) -> None:
    """El GraphML de un grafo decorado con DOIs incluye atributos doi y url (#209).

    GraphMLExporter es genérico: escribe todos los atributos de nodo presentes.
    """
    table = _make_table_con_doi()
    projector = BibliographicCouplingProjector()
    g = projector.project(table)
    decorate_graph(g, table, NetworkKind.BIBLIOGRAPHIC_COUPLING)

    GraphMLExporter().export(g, {}, tmp_path)

    reloaded = nx.read_graphml(str(tmp_path / "network.graphml"))

    # El nodo con DOI tiene ambos atributos
    assert "doi" in reloaded.nodes["PDOI"], (
        f"doi ausente en PDOI tras round-trip GraphML: {dict(reloaded.nodes['PDOI'])!r}"
    )
    assert reloaded.nodes["PDOI"]["doi"] == "10.1234/ejemplo.2024"
    assert "url" in reloaded.nodes["PDOI"], (
        f"url ausente en PDOI tras round-trip GraphML: {dict(reloaded.nodes['PDOI'])!r}"
    )
    assert reloaded.nodes["PDOI"]["url"] == "https://doi.org/10.1234/ejemplo.2024"

    # El nodo sin DOI NO tiene url basura
    assert "doi" not in reloaded.nodes["PNODOI"], (
        "doi no debería aparecer en PNODOI tras round-trip GraphML"
    )
    assert "url" not in reloaded.nodes["PNODOI"], (
        "url no debería aparecer en PNODOI tras round-trip GraphML"
    )


# ---------------------------------------------------------------------------
# URL fallback a OpenAlex + campos adicionales en nodos.csv (#203)
# ---------------------------------------------------------------------------


def _make_table_url_fallback() -> pa.Table:
    """Tabla con: paper con DOI, paper sin DOI pero con source_id de OpenAlex,
    y paper sin DOI ni source_id (sin URL posible). Todos comparten refs para
    quedar conectados en el acoplamiento bibliográfico.
    """
    rows = [
        {
            "id": "PDOI",
            "source_id": "W111",
            "doi": "10.1234/con-doi",
            "title": "Paper con DOI",
            "year": 2024,
            "abstract": None,
            "source": "Revista de Ejemplo",
            "language": None,
            "publisher": None,
            "research_areas": None,
            "is_seed": True,
            "curation_status": "accepted",
            "provenance": None,
            "authors_raw": ["Ana Pérez", "José Muñoz"],
            "authors_id": ["a1", "a2"],
            "authors_affiliations": None,
            "keywords_raw": None,
            "keywords_id": ["bibliometría", "análisis de redes"],
            "institutions_raw": None,
            "institutions_id": None,
            "references_id": ["R_shared"],
            "references_doi": None,
            "cited_by_id": ["C1", "C2", "C3"],
        },
        {
            "id": "POA",
            "source_id": "W222",
            "doi": None,
            "title": "Paper sin DOI, con OpenAlex id",
            "year": 2023,
            "abstract": None,
            "source": None,
            "language": None,
            "publisher": None,
            "research_areas": None,
            "is_seed": True,
            "curation_status": "candidate",
            "provenance": None,
            "authors_raw": None,
            "authors_id": None,
            "authors_affiliations": None,
            "keywords_raw": None,
            "keywords_id": None,
            "institutions_raw": None,
            "institutions_id": None,
            "references_id": ["R_shared"],
            "references_doi": None,
            "cited_by_id": None,
        },
        {
            "id": "PNADA",
            "source_id": None,
            "doi": None,
            "title": "Paper sin DOI ni OpenAlex id",
            "year": 2022,
            "abstract": None,
            "source": None,
            "language": None,
            "publisher": None,
            "research_areas": None,
            "is_seed": False,
            "curation_status": "rejected",
            "provenance": None,
            "authors_raw": None,
            "authors_id": None,
            "authors_affiliations": None,
            "keywords_raw": None,
            "keywords_id": None,
            "institutions_raw": None,
            "institutions_id": None,
            "references_id": ["R_shared"],
            "references_doi": None,
            "cited_by_id": None,
        },
    ]
    return pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)


@pytest.mark.unit
def test_url_doi_first_sobre_source_id() -> None:
    """Con DOI y source_id ambos presentes, url usa el DOI (#203)."""
    table = _make_table_url_fallback()
    projector = BibliographicCouplingProjector()
    g = projector.project(table)
    decorate_graph(g, table, NetworkKind.BIBLIOGRAPHIC_COUPLING)

    assert g.nodes["PDOI"]["url"] == "https://doi.org/10.1234/con-doi"


@pytest.mark.unit
def test_url_fallback_openalex_sin_doi() -> None:
    """Sin DOI pero con source_id de OpenAlex, url cae al link de OpenAlex (#203)."""
    table = _make_table_url_fallback()
    projector = BibliographicCouplingProjector()
    g = projector.project(table)
    decorate_graph(g, table, NetworkKind.BIBLIOGRAPHIC_COUPLING)

    assert "doi" not in g.nodes["POA"], "no debe inventar un doi ausente"
    assert g.nodes["POA"]["url"] == "https://openalex.org/W222"


@pytest.mark.unit
def test_sin_doi_ni_source_id_no_hay_url() -> None:
    """Sin DOI ni source_id, el nodo no recibe url (no se inventa nada, #203)."""
    table = _make_table_url_fallback()
    projector = BibliographicCouplingProjector()
    g = projector.project(table)
    decorate_graph(g, table, NetworkKind.BIBLIOGRAPHIC_COUPLING)

    assert "url" not in g.nodes["PNADA"]
    assert "doi" not in g.nodes["PNADA"]


@pytest.mark.unit
def test_campos_adicionales_venue_authors_keywords_cited_by_count() -> None:
    """Nodos de paper traen venue/authors/keywords/cited_by_count cuando hay datos (#203)."""
    table = _make_table_url_fallback()
    projector = BibliographicCouplingProjector()
    g = projector.project(table)
    decorate_graph(g, table, NetworkKind.BIBLIOGRAPHIC_COUPLING)

    attrs = g.nodes["PDOI"]
    assert attrs["venue"] == "Revista de Ejemplo"
    assert attrs["authors"] == "Ana Pérez|José Muñoz"
    assert attrs["keywords"] == "bibliometría|análisis de redes"
    assert attrs["cited_by_count"] == 3

    # El nodo sin ninguno de esos datos no trae claves basura (criterio "vacío = ausente")
    attrs_vacio = g.nodes["POA"]
    assert "venue" not in attrs_vacio
    assert "authors" not in attrs_vacio
    assert "keywords" not in attrs_vacio
    assert "cited_by_count" not in attrs_vacio


@pytest.mark.unit
def test_export_csv_incluye_url_fallback_y_campos_nuevos(tmp_path: Path) -> None:
    """nodos.csv trae url (DOI-first/OpenAlex-fallback) + venue/authors/keywords/
    cited_by_count, con tildes intactas vía BOM UTF-8 (#203)."""
    table = _make_table_url_fallback()
    projector = BibliographicCouplingProjector()
    g = projector.project(table)
    decorate_graph(g, table, NetworkKind.BIBLIOGRAPHIC_COUPLING)

    CsvExporter().export(g, {}, tmp_path)

    raw = (tmp_path / "nodos.csv").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf"), "nodos.csv debe empezar con BOM UTF-8"

    content = (tmp_path / "nodos.csv").read_text(encoding="utf-8-sig")
    header = content.splitlines()[0]
    for col in ("url", "venue", "authors", "keywords", "cited_by_count"):
        assert col in header, (
            f"columna {col!r} ausente en nodos.csv; header: {header!r}"
        )

    # DOI-first
    assert "https://doi.org/10.1234/con-doi" in content
    # Fallback a OpenAlex para el paper sin DOI
    assert "https://openalex.org/W222" in content
    # Tildes sobreviven el round-trip (autores/keywords con acentos)
    assert "Ana Pérez|José Muñoz" in content
    assert "bibliometría|análisis de redes" in content
