"""Tests TDD del Hito 2 — exportadores (GraphML, CSV).

Tests prescriptos por docs/ROADMAP.md §Hito 2:
- Round-trip GraphML: escribir → nx.read_graphml → mismas aristas/pesos.
- Smoke test CSV: que crea nodos.csv + aristas.csv.

Marcador: ``unit`` (I/O solo con tmp_path).
"""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import pytest

from bib2graph.exporters.csv import CsvExporter
from bib2graph.exporters.graphml import GraphMLExporter

# ---------------------------------------------------------------------------
# Grafo de prueba
# ---------------------------------------------------------------------------


@pytest.fixture()
def simple_graph() -> nx.Graph:
    """Grafo de 3 nodos con pesos y atributos de nodo."""
    g = nx.Graph()
    g.add_node("A", label="Paper A", community=0)
    g.add_node("B", label="Paper B", community=0)
    g.add_node("C", label="Paper C", community=1)
    g.add_edge("A", "B", weight=3)
    g.add_edge("B", "C", weight=1)
    return g


@pytest.fixture()
def results_dict() -> dict[str, object]:
    """Resultados de análisis mínimos para el exporter."""
    return {
        "degree": {"A": 0.5, "B": 1.0, "C": 0.5},
        "betweenness": {"A": 0.0, "B": 1.0, "C": 0.0},
    }


# ---------------------------------------------------------------------------
# 1. GraphMLExporter — round-trip
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_graphml_roundtrip_aristas_y_pesos(
    simple_graph: nx.Graph,
    results_dict: dict[str, object],
    tmp_path: Path,
) -> None:
    """GraphMLExporter escribe un archivo que, al releer, conserva aristas y pesos."""
    GraphMLExporter().export(simple_graph, results_dict, tmp_path)

    graphml_path = tmp_path / "network.graphml"
    assert graphml_path.exists()

    reloaded = nx.read_graphml(str(graphml_path))

    # Mismos nodos
    assert set(reloaded.nodes) == set(simple_graph.nodes)

    # Mismas aristas con pesos correctos (GraphML los serializa como string → float)
    for u, v, data in simple_graph.edges(data=True):
        assert reloaded.has_edge(u, v) or reloaded.has_edge(v, u)
        reloaded_edge = (
            reloaded.edges[u, v] if reloaded.has_edge(u, v) else reloaded.edges[v, u]
        )
        assert float(reloaded_edge["weight"]) == pytest.approx(data["weight"])


@pytest.mark.unit
def test_graphml_incluye_atributos_de_nodo(
    simple_graph: nx.Graph,
    results_dict: dict[str, object],
    tmp_path: Path,
) -> None:
    """Los atributos de nodo (y métricas de results) quedan en el GraphML."""
    GraphMLExporter().export(simple_graph, results_dict, tmp_path)

    reloaded = nx.read_graphml(str(tmp_path / "network.graphml"))

    # El nodo B tiene degree=1.0 en results_dict
    assert "degree" in reloaded.nodes["B"]
    assert float(reloaded.nodes["B"]["degree"]) == pytest.approx(1.0)


@pytest.mark.unit
def test_graphml_roundtrip_con_atributo_none(tmp_path: Path) -> None:
    """GraphMLExporter no rompe cuando un nodo tiene un atributo con valor None.

    Caso real: country=None para nodos sin afiliación. nx.write_graphml lanza
    NetworkXError si encuentra None. El exporter debe omitir la clave para ese
    nodo (más limpio para Gephi) en vez de fallar o convertir a ''.
    """
    g = nx.Graph()
    g.add_node("A", country="AR", label="Paper A")
    g.add_node("B", country=None, label="Paper B")  # country ausente
    g.add_node("C", country="BR", label="Paper C")
    g.add_edge("A", "B", weight=2)
    g.add_edge("B", "C", weight=1)

    # No debe lanzar excepción
    GraphMLExporter().export(g, {}, tmp_path)

    graphml_path = tmp_path / "network.graphml"
    assert graphml_path.exists()

    reloaded = nx.read_graphml(str(graphml_path))

    # Los nodos con country poblado conservan el atributo
    assert reloaded.nodes["A"].get("country") == "AR"
    assert reloaded.nodes["C"].get("country") == "BR"

    # El nodo con country=None no tiene la clave (omitida, no convertida a "")
    assert "country" not in reloaded.nodes["B"]


# ---------------------------------------------------------------------------
# 2. CsvExporter — smoke test
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_csv_crea_archivos_nodos_y_aristas(
    simple_graph: nx.Graph,
    results_dict: dict[str, object],
    tmp_path: Path,
) -> None:
    """CsvExporter crea nodos.csv y aristas.csv en el directorio de salida."""
    CsvExporter().export(simple_graph, results_dict, tmp_path)

    assert (tmp_path / "nodos.csv").exists()
    assert (tmp_path / "aristas.csv").exists()


@pytest.mark.unit
def test_csv_aristas_columnas_correctas(
    simple_graph: nx.Graph,
    results_dict: dict[str, object],
    tmp_path: Path,
) -> None:
    """aristas.csv tiene columnas source,target,weight (D5)."""
    CsvExporter().export(simple_graph, results_dict, tmp_path)

    content = (tmp_path / "aristas.csv").read_text(encoding="utf-8-sig")
    header = content.splitlines()[0]
    assert header == "source,target,weight"


@pytest.mark.unit
def test_csv_escribe_con_bom_utf8_para_excel(tmp_path: Path) -> None:
    """Los CSV se escriben en utf-8-sig (BOM) para Excel-Windows (#214).

    Sin BOM, Excel asume cp1252 y rompe las tildes (Valoración → ValoraciÃ³n).
    Regresión: el export debe empezar con el BOM UTF-8 y las tildes deben
    sobrevivir el round-trip.
    """
    g = nx.Graph()
    g.add_node("doi:abc", label="Valoración estética (Müller, 1987)")
    g.add_node("doi:def", label="Crítica de la razón")
    g.add_edge("doi:abc", "doi:def", weight=3)

    CsvExporter().export(g, {"grado": dict(g.degree())}, tmp_path)

    for name in ("nodos.csv", "aristas.csv"):
        raw = (tmp_path / name).read_bytes()
        assert raw.startswith(b"\xef\xbb\xbf"), f"{name} debe empezar con BOM UTF-8"

    # Las tildes sobreviven el round-trip leyendo utf-8-sig
    nodos = (tmp_path / "nodos.csv").read_text(encoding="utf-8-sig")
    assert "Valoración estética (Müller, 1987)" in nodos
