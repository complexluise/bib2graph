"""Tests TDD — ``intra_community_pagerank`` (ADR 0052 D3, #321).

Cubre:
1. Grafo chico conocido (5 nodos, 2 comunidades) con PageRank esperado a mano.
2. Grafo sin comunidades (dict vacío) -> dict vacío.
3. Grafo con comunidades de un solo nodo -> PageRank = 1.0 (convención de nx.pagerank).
4. Grafo con comunidades que no matchean nodos del grafo -> esos nodos se ignoran.
5. Grafo vacío -> dict vacío.
6. Subgrafo inducido (no todos los nodos de la comunidad están en el grafo) ->
   el PageRank se computa sobre el subgrafo inducido.

Marcador: ``unit`` (núcleo puro, sin red ni I/O).
"""

from __future__ import annotations

import networkx as nx
import pytest

from bib2graph.networks.intra_community_pagerank import intra_community_pagerank

pytestmark = pytest.mark.unit


def _build_5node_2comm_graph() -> nx.Graph:
    """Grafo conocido: 5 nodos, 2 comunidades separadas.

    Comunidad 1: {A, B, C}, triangulo con pesos 2, 2, 1 (A-B=2, A-C=2, B-C=1).
    Comunidad 2: {D, E}, arista con peso 3 (D-E=3).

    Subgrafos inducidos:
      sg1 = nx.Graph con edges [(A,B,2),(A,C,2),(B,C,1)] -> nx.pagerank(sg1).
      sg2 = nx.Graph con edge [(D,E,3)] -> nx.pagerank(sg2).

    Calculado con nx.pagerank (ground truth):
      sg1 = {'A': 0.394, 'B': 0.303, 'C': 0.303}
      sg2 = {'D': 0.5, 'E': 0.5}

    El test assertea con tolerancia (no igualdad exacta) por robustez ante
    cambios menores en nx.pagerank entre versiones.
    """
    g: nx.Graph = nx.Graph()
    g.add_node("A")
    g.add_node("B")
    g.add_node("C")
    g.add_node("D")
    g.add_node("E")
    g.add_edge("A", "B", weight=2.0)
    g.add_edge("A", "C", weight=2.0)
    g.add_edge("B", "C", weight=1.0)
    g.add_edge("D", "E", weight=3.0)
    return g


def test_grafo_conocido_2_comunidades_page_rank_esperado() -> None:
    """Grafo de 5 nodos / 2 comunidades: PageRank intra-comunidad conocido."""
    g = _build_5node_2comm_graph()
    communities: dict[str, int] = {
        "A": 0,
        "B": 0,
        "C": 0,
        "D": 1,
        "E": 1,
    }

    result = intra_community_pagerank(g, communities)

    # Mismos nodos que en la entrada
    assert set(result.keys()) == {"A", "B", "C", "D", "E"}

    # Comunidad 0 (triangulo): A tiene mas PageRank por sus 2 aristas pesadas
    assert result["A"] > result["B"]
    assert result["A"] > result["C"]
    assert abs(result["B"] - result["C"]) < 1e-9  # simetricos en el triangulo

    # Comunidad 1 (arista simple): D y E simétricos -> PageRank 0.5 cada uno
    assert abs(result["D"] - 0.5) < 1e-6
    assert abs(result["E"] - 0.5) < 1e-6
    assert abs(result["D"] - result["E"]) < 1e-9

    # Tolerancia contra el ground truth (ground truth medido en la version de nx)
    expected_a = 0.39361741945785217
    assert abs(result["A"] - expected_a) < 1e-6


def test_sin_comunidades_devuelve_dict_vacio() -> None:
    """``communities={}`` -> ``{}`` (sin PageRank que computar)."""
    g = _build_5node_2comm_graph()
    result = intra_community_pagerank(g, {})
    assert result == {}


def test_grafo_vacio_con_comunidades_devuelve_dict_vacio() -> None:
    """Grafo sin nodos pero con comunidades declaradas -> ``{}``.

    Ningún nodo del grafo matchea, no hay subgrafo inducido que computar.
    """
    g: nx.Graph = nx.Graph()
    communities = {"A": 0, "B": 0}
    result = intra_community_pagerank(g, communities)
    assert result == {}


def test_comunidad_de_un_nodo_devuelve_page_rank_1() -> None:
    """Subgrafo de 1 nodo -> PageRank = 1. (convención de ``nx.pagerank``)."""
    g: nx.Graph = nx.Graph()
    g.add_node("Z")
    communities = {"Z": 0}
    result = intra_community_pagerank(g, communities)
    assert result == {"Z": 1.0}


def test_nodo_no_en_grafo_se_ignora() -> None:
    """Comunidades que incluyen nodos NO presentes en el grafo se ignoran.

    PageRank solo aplica a nodos del grafo; un id que aparece en
    ``communities`` pero no en ``graph.nodes`` no entra al resultado.
    """
    g: nx.Graph = nx.Graph()
    g.add_node("A")
    g.add_node("B")
    g.add_edge("A", "B", weight=1.0)
    communities = {"A": 0, "B": 0, "X": 0}  # X no existe
    result = intra_community_pagerank(g, communities)
    assert "X" not in result
    assert set(result.keys()) == {"A", "B"}
    assert abs(result["A"] - 0.5) < 1e-6
    assert abs(result["B"] - 0.5) < 1e-6


def test_subgrafo_inducido_usa_solo_nodos_del_grafo() -> None:
    """El subgrafo de cada comunidad es el inducido del grafo (no la lista).

    Documenta el contrato: si una comunidad declara un nodo no presente
    en el grafo, ``nx.subgraph`` lo descarta silenciosamente (los
    ``nodelist`` que no existen no aparecen en el subgrafo). El resultado
    sigue siendo correcto.
    """
    g: nx.Graph = nx.Graph()
    g.add_node("A")
    g.add_node("B")
    g.add_node("C")
    g.add_edge("A", "B", weight=2.0)
    g.add_edge("B", "C", weight=1.0)

    communities = {"A": 0, "B": 0, "C": 0, "X": 0}
    result = intra_community_pagerank(g, communities)
    assert "X" not in result
    # A, B, C están en la comunidad 0; los 3 forman un subgrafo inducido.
    assert set(result.keys()) == {"A", "B", "C"}
    # En este path lineal (A-B-C), B es el "puente" entre A y C — recibe flujo
    # de ambos. El PageRank favorece al puente, no al nodo con la arista más
    # pesada. La métrica es flujo entre nodos, no peso de aristas hacia un nodo.
    assert result["B"] > result["A"]
    assert result["B"] > result["C"]
    # A y C NO son simétricos (las aristas tienen pesos distintos: 2 vs 1).
    # La asimetría en PageRank refleja la asimetría del path.


def test_peso_default_es_weight() -> None:
    """El parámetro ``weight`` default es ``"weight"`` (atributo de arista)."""
    g: nx.Graph = nx.Graph()
    g.add_node("A")
    g.add_node("B")
    g.add_edge("A", "B", weight=5.0)
    communities = {"A": 0, "B": 0}
    result = intra_community_pagerank(g, communities)
    # Simétrico, ambos 0.5
    assert abs(result["A"] - 0.5) < 1e-6
    assert abs(result["B"] - 0.5) < 1e-6


def test_personalizar_atributo_de_peso() -> None:
    """Se puede usar un atributo de peso distinto a ``"weight"``."""
    g: nx.Graph = nx.Graph()
    g.add_node("A")
    g.add_node("B")
    g.add_edge("A", "B", similarity=10.0)
    communities = {"A": 0, "B": 0}
    result = intra_community_pagerank(g, communities, weight="similarity")
    assert abs(result["A"] - 0.5) < 1e-6


def test_dos_comunidades_disjuntas_independientes() -> None:
    """Comunidades disjuntas: cada subgrafo se procesa de forma independiente.

    Construye 2 comunidades separadas de 2 nodos cada una, con pesos
    distintos, y verifica que el PageRank de cada una es 0.5 (simetría).
    """
    g: nx.Graph = nx.Graph()
    g.add_node("A")
    g.add_node("B")
    g.add_node("C")
    g.add_node("D")
    g.add_edge("A", "B", weight=1.0)
    g.add_edge("C", "D", weight=100.0)
    communities = {"A": 0, "B": 0, "C": 1, "D": 1}

    result = intra_community_pagerank(g, communities)

    # Cada subgrafo (arista simple) tiene PageRank 0.5 para ambos nodos,
    # sin importar el peso (PageRank usa el peso pero sobre la topologia
    # simétrica de 2 nodos sigue dando 0.5/0.5).
    assert abs(result["A"] - 0.5) < 1e-6
    assert abs(result["B"] - 0.5) < 1e-6
    assert abs(result["C"] - 0.5) < 1e-6
    assert abs(result["D"] - 0.5) < 1e-6


def test_comunidades_con_isolate_no_crashea() -> None:
    """Comunidad con un nodo aislado en el grafo -> PageRank 1.0 (sin error).

    Un nodo aislado en el subgrafo inducido es un grafo de 1 nodo, y
    ``nx.pagerank`` devuelve ``{nodo: 1.0}`` por convención.
    """
    g: nx.Graph = nx.Graph()
    g.add_node("A")
    g.add_node("B")
    g.add_node("C")
    g.add_edge("A", "B", weight=1.0)
    # C queda aislado en la comunidad 1 (no tiene aristas)
    communities = {"A": 0, "B": 0, "C": 1}
    result = intra_community_pagerank(g, communities)
    assert result["A"] == pytest.approx(0.5, abs=1e-6)
    assert result["B"] == pytest.approx(0.5, abs=1e-6)
    assert result["C"] == pytest.approx(1.0, abs=1e-6)
