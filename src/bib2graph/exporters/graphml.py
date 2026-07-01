"""graphml — exportador de redes al formato GraphML (Gephi / VOSviewer / Cytoscape).

Implementa ``GraphMLExporter`` según API.md §9 y la decisión D5.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import networkx as nx

if TYPE_CHECKING:
    # nx.Graph es genérico solo en los stubs de types-networkx, no en runtime.
    _Graph = nx.Graph[Any, Any, Any]
else:
    _Graph = nx.Graph


class GraphMLExporter:
    """Exporta un grafo NetworkX a GraphML con atributos de nodo y métricas.

    Según la decisión D5, los atributos de nodo ya presentes en el grafo y las
    métricas del dict ``results`` se escriben como node attributes antes de
    llamar a ``nx.write_graphml``. Gephi los lee como columnas.
    """

    def export(
        self,
        g: _Graph,
        results: dict[str, object],
        out_dir: str | Path,
    ) -> None:
        """Exporta el grafo a ``<out_dir>/network.graphml``.

        Fusiona los valores del dict ``results`` como atributos de nodo. Si
        ``results`` contiene un dict anidado (p. ej. ``{"degree": {nodo: val}}``),
        cada valor se asigna al nodo correspondiente.

        Args:
            g: Grafo NetworkX a exportar.
            results: Dict de métricas/análisis. Los valores pueden ser dicts
                ``{nodo: valor}`` (p. ej. salida de ``centrality``).
            out_dir: Directorio de salida. Se crea si no existe.
        """
        out_path = Path(out_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        # Copiar el grafo para no mutar el original
        export_g: _Graph = g.copy()

        for metric_name, metric_value in results.items():
            if isinstance(metric_value, dict):
                for node, val in metric_value.items():
                    if export_g.has_node(node):
                        export_g.nodes[node][metric_name] = val

        # nx.write_graphml lanza NetworkXError si algún atributo de nodo o
        # arista es None (Gephi tampoco los admite). Omitimos las claves None
        # en vez de convertirlas a "" para no contaminar tipos en Gephi.
        for _, data in export_g.nodes(data=True):
            none_keys = [k for k, v in data.items() if v is None]
            for k in none_keys:
                del data[k]

        for _, _, data in export_g.edges(data=True):
            none_keys = [k for k, v in data.items() if v is None]
            for k in none_keys:
                del data[k]

        nx.write_graphml(export_g, str(out_path / "network.graphml"))
