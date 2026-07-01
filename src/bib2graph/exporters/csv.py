"""csv — exportador de redes a CSV (nodos + aristas).

Implementa ``CsvExporter`` según API.md §9 y la decisión D5.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import TYPE_CHECKING, Any

import networkx as nx

if TYPE_CHECKING:
    # nx.Graph es genérico solo en los stubs de types-networkx, no en runtime.
    _Graph = nx.Graph[Any, Any, Any]
else:
    _Graph = nx.Graph


class CsvExporter:
    """Exporta un grafo NetworkX a dos archivos CSV.

    Según la decisión D5:
      - ``aristas.csv``: columnas ``source,target,weight``.
      - ``nodos.csv``: ``id,label`` + atributos de nodo presentes + métricas
        de ``results`` (dict anidado ``{métrica: {nodo: valor}}``) unidas
        por id.
    """

    def export(
        self,
        g: _Graph,
        results: dict[str, object],
        out_dir: str | Path,
    ) -> None:
        """Exporta el grafo a ``nodos.csv`` y ``aristas.csv`` en ``out_dir``.

        Args:
            g: Grafo NetworkX a exportar.
            results: Dict de métricas. Los valores deben ser dicts
                ``{nodo: valor}`` para fusionarse a ``nodos.csv``.
            out_dir: Directorio de salida. Se crea si no existe.
        """
        out_path = Path(out_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        self._write_aristas(g, out_path)
        self._write_nodos(g, results, out_path)

    def _write_aristas(self, g: _Graph, out_path: Path) -> None:
        """Escribe aristas.csv con columnas source,target,weight (D5)."""
        # utf-8-sig (BOM) para que Excel-Windows autodetecte UTF-8 y no rompa tildes (#214)
        with open(out_path / "aristas.csv", "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["source", "target", "weight"])
            # Orden determinista: aristas ordenadas por (source, target)
            for u, v, data in sorted(
                g.edges(data=True), key=lambda e: (str(e[0]), str(e[1]))
            ):
                weight = data.get("weight", 1)
                writer.writerow([u, v, weight])

    def _write_nodos(
        self,
        g: _Graph,
        results: dict[str, object],
        out_path: Path,
    ) -> None:
        """Escribe nodos.csv con id, label, atributos de nodo y métricas (D5)."""
        node_attr_keys: set[str] = set()
        for _, attrs in g.nodes(data=True):
            node_attr_keys.update(attrs.keys())

        metric_keys: list[str] = []
        metric_dicts: dict[str, dict[Any, Any]] = {}
        for k, v in results.items():
            if isinstance(v, dict):
                metric_keys.append(k)
                metric_dicts[k] = v

        attr_cols = sorted(node_attr_keys - {"label"})  # 'label' la manejamos aparte
        metric_cols = sorted(metric_keys)
        header = ["id", "label", *attr_cols, *metric_cols]

        # utf-8-sig (BOM) para que Excel-Windows autodetecte UTF-8 y no rompa tildes (#214)
        with open(out_path / "nodos.csv", "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            # Orden determinista: nodos ordenados por id como string
            for node in sorted(g.nodes, key=str):
                attrs = g.nodes[node]
                label = attrs.get("label", str(node))
                row: list[Any] = [node, label]
                for col in attr_cols:
                    row.append(attrs.get(col, ""))
                for col in metric_cols:
                    metric_val = metric_dicts[col].get(node, "")
                    row.append(metric_val)
                writer.writerow(row)
