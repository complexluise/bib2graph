"""intra_community_pagerank — PageRank restringido al subgrafo de cada comunidad.

ADR 0052 D3 (#321): ``intra_community_pagerank`` es la métrica central de la
"red tipada" que ``b2g export --format arrow`` embebe en la tabla del corpus
junto con las comunidades y el ``degree_weighted``. La idea: en lugar de
exportar un PageRank global (dominado por papers muy conectados al resto del
corpus), se computa el PageRank de cada nodo **restringido al subgrafo de su
comunidad**. Así, comunidades de tamaños distintos producen PageRanks
**comparables** — el insumo natural para "elegir el paper representativo de
cada comunidad" (caso de uso del consumidor programático, #316).

Diseño:
  - Función pura (sin I/O, sin red, sin estado global). Vive en ``networks/``
    siguiendo el patrón de ``analyzer.py`` (mismas reglas de pureza).
  - Para cada comunidad del dict ``communities``, construye el subgrafo
    inducido con ``nx.subgraph(subgraph)`` y le aplica ``nx.pagerank`` con
    el atributo de peso (default ``"weight"``).
  - Subgrafos disjuntos: la suma de PageRanks en distintos subgrafos es
    independiente, sin necesidad de renormalizar.
  - Subgrafo de 1 nodo aislado: ``nx.pagerank`` devuelve ``{nodo: 1.0}`` por
    convención (mismo valor que cualquier nodo en un grafo de 1 nodo). No se
    trata como error.
  - Sin comunidades (``{}``): devuelve ``{}``. Sin nodos en el grafo:
    devuelve ``{}``. Nodos en ``communities`` que no existen en el grafo: se
    ignoran (``nx.subgraph`` los descarta silenciosamente del subgrafo).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import networkx as nx

if TYPE_CHECKING:
    # nx.Graph es genérico solo en los stubs de types-networkx, no en runtime.
    _Graph = nx.Graph[Any, Any, Any]
else:
    _Graph = nx.Graph


def intra_community_pagerank(
    graph: _Graph,
    communities: dict[Any, int],
    *,
    weight: str = "weight",
) -> dict[Any, float]:
    """PageRank por nodo restringido al subgrafo de su comunidad.

    Itera las comunidades del dict ``communities`` (mapa ``nodo → community_id``),
    agrupa los nodos por ``community_id``, construye el subgrafo inducido de
    cada comunidad con ``nx.subgraph`` y aplica ``nx.pagerank`` con el atributo
    de peso ``weight`` (``"weight"`` por default).

    Costo: O(|V| + |E|) en total (PageRank por subgrafo es independiente y los
    subgrafos son disjuntos). Coherente con la nota "barato" del ADR 0052 D3.

    Args:
        graph: Grafo NetworkX (no dirigido) del ``NetworkArtifact``.
        communities: Dict ``nodo → community_id``. Un ``community_id`` es un
            entero (salida de ``detect_communities``). Los nodos que aparecen
            en este dict pero no en ``graph`` se ignoran.
        weight: Nombre del atributo de arista que se pasa a ``nx.pagerank``
            como ``weight=``. Default ``"weight"`` (coincide con el atributo
            que escriben los proyectores del núcleo).

    Returns:
        Dict ``nodo → float`` con el PageRank intra-comunidad de cada nodo
        presente en ``graph`` Y en ``communities``. Vacío (``{}``) si no hay
        comunidades declaradas o si el grafo está vacío.

    Casos límite (cubiertos por ``tests/unit/test_intra_community_pagerank.py``):
      - ``communities={}`` -> ``{}``.
      - Grafo sin nodos -> ``{}``.
      - Nodo en ``communities`` pero no en el grafo -> se ignora.
      - Comunidad con un único nodo -> PageRank = ``1.0`` (convención de
        ``nx.pagerank`` para grafos de 1 nodo).
      - Comunidad con un nodo aislado en el subgrafo -> ``1.0`` (el nodo no
        tiene aristas en el subgrafo inducido; nx.pagerank lo trata como
        grafo de 1 nodo).
    """
    if not communities or graph.number_of_nodes() == 0:
        return {}

    # Agrupar nodos por community_id, intersecando con los nodos del grafo.
    by_community: dict[int, list[Any]] = {}
    for node, comm_id in communities.items():
        if not graph.has_node(node):
            continue
        by_community.setdefault(int(comm_id), []).append(node)

    result: dict[Any, float] = {}
    for nodes in by_community.values():
        if not nodes:
            continue
        sub_pr = nx.pagerank(graph.subgraph(nodes), weight=weight)
        result.update(sub_pr)

    return result
