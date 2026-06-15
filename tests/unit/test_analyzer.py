"""Tests TDD del Hito 2 — analizadores.

Tests prescriptos por docs/ROADMAP.md §Hito 2:
- network_metrics + centrality sobre grafo de valor conocido.
- detect_communities: fallo explícito si falta python-louvain (monkeypatch).
- assortativity: atributo configurable + disclaimer cuando se pasa proxy.
- community_composition: %s conocidos.
- cocitation_quality_report: caso que pasa y uno que falla umbral.

Marcador: ``unit`` (sin red, sin I/O).
"""

from __future__ import annotations

import sys
from typing import Any
from unittest.mock import patch

import networkx as nx
import pyarrow as pa
import pytest

from bib2graph.networks.analyzer import (
    QualityThresholds,
    assortativity,
    centrality,
    cocitation_quality_report,
    community_composition,
    detect_communities,
    network_metrics,
)
from bib2graph.schemas import CORPUS_SCHEMA

# ---------------------------------------------------------------------------
# Grafos sintéticos de referencia
# ---------------------------------------------------------------------------


@pytest.fixture()
def star_graph() -> nx.Graph:
    """Grafo estrella K1,3: nodo 0 (centro) conectado a 1, 2, 3.

    Propiedades calculadas a mano:
      - nodos: 4, aristas: 3
      - densidad: 3 / (4*3/2) = 3/6 = 0.5
      - componentes: 1
      - clustering promedio: 0.0 (ningún par de hojas conectado)
      - degree_centrality: 0={3/3=1.0}, 1=2=3={1/3≈0.333}
      - betweenness: 0=1.0, 1=2=3=0.0
    """
    g = nx.Graph()
    g.add_edges_from([(0, 1), (0, 2), (0, 3)])
    return g


@pytest.fixture()
def triangle_graph() -> nx.Graph:
    """Grafo triángulo K3: nodos 0,1,2 todos conectados.

    Propiedades:
      - densidad: 1.0
      - componentes: 1
      - clustering promedio: 1.0
    """
    g = nx.Graph()
    g.add_edges_from([(0, 1), (1, 2), (0, 2)])
    return g


# ---------------------------------------------------------------------------
# 1. network_metrics
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_network_metrics_estrella(star_graph: nx.Graph) -> None:
    """network_metrics devuelve densidad, componentes y clustering del grafo estrella."""
    m = network_metrics(star_graph)

    assert m["density"] == pytest.approx(0.5)
    assert m["num_components"] == 1
    assert m["avg_clustering"] == pytest.approx(0.0)


@pytest.mark.unit
def test_network_metrics_triangulo(triangle_graph: nx.Graph) -> None:
    """network_metrics devuelve densidad 1.0 y clustering 1.0 para el triángulo."""
    m = network_metrics(triangle_graph)

    assert m["density"] == pytest.approx(1.0)
    assert m["num_components"] == 1
    assert m["avg_clustering"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# 2. centrality
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_centrality_estrella(star_graph: nx.Graph) -> None:
    """centrality devuelve grado e intermediación exactos para la estrella."""
    c = centrality(star_graph)

    # El centro (nodo 0) tiene degree_centrality=1.0 y betweenness=1.0
    assert c["degree"][0] == pytest.approx(1.0)
    assert c["betweenness"][0] == pytest.approx(1.0)

    # Las hojas tienen degree=1/3 y betweenness=0
    for leaf in [1, 2, 3]:
        assert c["degree"][leaf] == pytest.approx(1 / 3)
        assert c["betweenness"][leaf] == pytest.approx(0.0)


@pytest.mark.unit
def test_centrality_triangulo(triangle_graph: nx.Graph) -> None:
    """En el triángulo todos los nodos tienen degree=1.0 y betweenness=0.0."""
    c = centrality(triangle_graph)

    for node in [0, 1, 2]:
        assert c["degree"][node] == pytest.approx(1.0)
        assert c["betweenness"][node] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 3. detect_communities — fallo explícito si falta python-louvain
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_detect_communities_louvain_ok(triangle_graph: nx.Graph) -> None:
    """detect_communities(method='louvain') funciona cuando python-louvain está instalado."""
    result = detect_communities(triangle_graph, method="louvain")
    assert isinstance(result, dict)
    # Todos los nodos tienen comunidad asignada
    for node in triangle_graph.nodes:
        assert node in result


@pytest.mark.unit
def test_detect_communities_louvain_falla_sin_paquete(
    triangle_graph: nx.Graph,
) -> None:
    """detect_communities(method='louvain') falla explícito si falta python-louvain.

    Se monkeypatchea el import de 'community' para simular ausencia del paquete.
    El mensaje de error debe mencionar 'python-louvain'.
    """
    # Guardamos el módulo real
    real_community = sys.modules.get("community")

    with (
        patch.dict(sys.modules, {"community": None}),
        pytest.raises(  # type: ignore[dict-item]
            ImportError, match="python-louvain"
        ),
    ):
        detect_communities(triangle_graph, method="louvain")

    # Restaurar si hace falta (patch.dict lo hace solo, pero por claridad)
    if real_community is not None:
        sys.modules["community"] = real_community


# ---------------------------------------------------------------------------
# 4. assortativity — atributo configurable + disclaimer de proxy
# ---------------------------------------------------------------------------


@pytest.fixture()
def two_clique_graph() -> nx.Graph:
    """Grafo de dos cliques separadas con atributo 'region'.

    Clique A: nodos 0,1 → region='Norte'
    Clique B: nodos 2,3 → region='Sur'
    Arista entre cliques: ninguna → asortatividad perfecta = 1.0
    """
    g = nx.Graph()
    g.add_edge(0, 1)
    g.add_edge(2, 3)
    nx.set_node_attributes(g, {0: "Norte", 1: "Norte", 2: "Sur", 3: "Sur"}, "region")
    return g


@pytest.mark.unit
def test_assortativity_por_atributo(two_clique_graph: nx.Graph) -> None:
    """assortativity(attribute='region') devuelve 1.0 para dos cliques puras."""
    result = assortativity(two_clique_graph, attribute="region", by_degree=False)

    assert "attribute_assortativity" in result
    assert result["attribute_assortativity"] == pytest.approx(1.0)


@pytest.mark.unit
def test_assortativity_sin_atributo_por_grado(star_graph: nx.Graph) -> None:
    """assortativity() por grado incluye 'degree_assortativity' en el resultado."""
    result = assortativity(star_graph, by_degree=True)

    assert "degree_assortativity" in result


@pytest.mark.unit
def test_assortativity_disclaimer_cuando_se_pasa_proxy(
    two_clique_graph: nx.Graph,
) -> None:
    """Cuando se pasa proxy=..., el resultado incluye un campo 'proxy_disclaimer'."""
    result = assortativity(
        two_clique_graph,
        attribute="region",
        by_degree=False,
        proxy="affiliation_per_paper",
    )

    assert "proxy_disclaimer" in result
    # El disclaimer debe mencionar el nombre del proxy
    assert "affiliation_per_paper" in result["proxy_disclaimer"]


@pytest.mark.unit
def test_assortativity_sin_proxy_no_incluye_disclaimer(
    two_clique_graph: nx.Graph,
) -> None:
    """Sin proxy=, NO hay campo 'proxy_disclaimer' en el resultado."""
    result = assortativity(two_clique_graph, attribute="region", by_degree=False)

    assert "proxy_disclaimer" not in result


# ---------------------------------------------------------------------------
# 5. community_composition — %s conocidos
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_community_composition_porcentajes_conocidos() -> None:
    """community_composition devuelve el % de cada categoría por comunidad.

    Grafo: 4 nodos. Comunidad 0: nodos 0(Norte),1(Norte). Comunidad 1: 2(Sur),3(Sur).
    Para la comunidad 0: Norte=100%, Sur=0%.
    Para la comunidad 1: Norte=0%, Sur=100%.
    """
    g = nx.Graph()
    g.add_nodes_from([0, 1, 2, 3])
    nx.set_node_attributes(g, {0: "Norte", 1: "Norte", 2: "Sur", 3: "Sur"}, "region")
    communities = {0: 0, 1: 0, 2: 1, 3: 1}

    result = community_composition(g, communities, attribute="region")

    # Comunidad 0: 100% Norte
    assert result[0]["Norte"] == pytest.approx(1.0)
    assert result[0]["Sur"] == pytest.approx(0.0)

    # Comunidad 1: 100% Sur
    assert result[1]["Norte"] == pytest.approx(0.0)
    assert result[1]["Sur"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# 6. cocitation_quality_report — caso que pasa y uno que falla umbral
# ---------------------------------------------------------------------------


def _make_corpus_table(rows: list[dict[str, object]]) -> pa.Table:
    return pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)


def _corpus_row(
    id: str,
    *,
    references_id: list[str] | None = None,
    doi: str | None = None,
    institutions_id: list[str] | None = None,
    authors_id: list[str] | None = None,
) -> dict[str, object]:
    return {
        "id": id,
        "openalex_id": None,
        "doi": doi,
        "title": f"Paper {id}",
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
        "authors_id": authors_id,
        "authors_affiliations": None,
        "keywords_raw": None,
        "keywords_id": None,
        "institutions_raw": None,
        "institutions_id": institutions_id,
        "references_id": references_id,
        "references_doi": None,
        "cited_by_id": None,
    }


def _make_corpus_that_passes() -> Any:
    """Corpus mínimo que pasa todos los umbrales por defecto."""
    from bib2graph.corpus import Corpus

    # min_volume=200: 200 papers
    # min_doi_refs_pct=0.90: 90% con DOI
    # min_countries=5: instituciones en 5 países
    # min_recurrent_authors=10: 10 autores recurrentes (≥2 papers)

    rows = []
    # 200 papers, 180 con DOI (90%), referencias llenas, autores e instituciones variados
    countries = ["I_AR", "I_BR", "I_MX", "I_CO", "I_CL"]
    # 12 autores recurrentes (aparecen en 2+ papers)
    recurrent_authors = [f"AUTH_{i}" for i in range(12)]

    for i in range(200):
        doi = f"10.1000/p{i:04d}" if i < 180 else None
        # Cada paper tiene una institución de un país distinto (round-robin)
        inst = countries[i % len(countries)]
        # Primeros 24 papers comparten autores recurrentes (2 papers cada uno)
        # para que los 12 autores aparezcan >= 2 veces
        authors = [recurrent_authors[i // 2]] if i < 24 else [f"UNIQUE_AUTH_{i}"]

        rows.append(
            _corpus_row(
                f"P{i:04d}",
                doi=doi,
                institutions_id=[inst],
                authors_id=authors,
                references_id=[f"R{i}"],
            )
        )

    table = _make_corpus_table(rows)
    return Corpus.from_arrow(table)


def _make_corpus_that_fails_volume() -> Any:
    """Corpus con < 200 papers: falla el umbral de volumen."""
    from bib2graph.corpus import Corpus

    rows = [
        _corpus_row(f"P{i}", doi=f"10.1/{i}", institutions_id=["I_AR"])
        for i in range(10)  # Solo 10 papers, min_volume=200
    ]
    table = _make_corpus_table(rows)
    return Corpus.from_arrow(table)


@pytest.mark.unit
def test_cocitation_quality_report_pasa_todos_umbrales() -> None:
    """cocitation_quality_report devuelve overall_pass=True cuando se cumplen umbrales."""

    corpus = _make_corpus_that_passes()
    # Grafo mínimo: no importa para el reporte de calidad del corpus
    g = nx.Graph()

    report = cocitation_quality_report(corpus, g)

    assert "overall_pass" in report
    assert report["overall_pass"] is True, f"Esperaba pass. Reporte: {report}"
    # Estructura del reporte
    for key in [
        "min_volume",
        "min_doi_refs_pct",
        "min_countries",
        "min_recurrent_authors",
    ]:
        assert key in report
        assert "valor" in report[key]
        assert "umbral" in report[key]
        assert "pasa" in report[key]


@pytest.mark.unit
def test_cocitation_quality_report_falla_volumen() -> None:
    """cocitation_quality_report devuelve overall_pass=False y min_volume.pasa=False."""
    corpus = _make_corpus_that_fails_volume()
    g = nx.Graph()
    thresholds = QualityThresholds(min_volume=200)

    report = cocitation_quality_report(corpus, g, thresholds=thresholds)

    assert report["overall_pass"] is False
    assert report["min_volume"]["pasa"] is False
    assert report["min_volume"]["valor"] < 200
    assert report["min_volume"]["umbral"] == 200


@pytest.mark.unit
def test_cocitation_quality_report_min_countries_tiene_proxy_disclaimer() -> None:
    """min_countries incluye campo 'proxy' que advierte que institutions_id es un proxy.

    Consistente con el patrón proxy_disclaimer de assortativity (principio D4).
    """
    corpus = _make_corpus_that_passes()
    g = nx.Graph()

    report = cocitation_quality_report(corpus, g)

    min_countries_entry = report["min_countries"]
    assert isinstance(min_countries_entry, dict)
    assert "proxy" in min_countries_entry
    # El disclaimer debe mencionar institutions_id
    assert "institutions_id" in min_countries_entry["proxy"]
