"""service.export_network — Carga del NetworkArtifact desde disco (ADR 0052, #321).

``load_artifact_from_disk(ws, kind)`` reconstruye un ``NetworkArtifact`` a
partir de los artefactos que ``b2g build`` dejó en
``<workspace>/networks/<kind>/``:

  - ``network.graphml`` — el grafo (incluye el atributo ``community`` por nodo,
    inyectado por ``_write_artifacts`` cuando se detectaron comunidades).
  - ``metrics.json`` — métricas + spec (kind, clustering, resolution, scope,
    nodes, edges, density, num_components, avg_clustering, assortativity).

Función pura (sin I/O fuera de leer de disco): el caller decide qué hacer con
un ``None`` (modo degradado, ADR 0052 D4) o con un ``NetworkArtifact`` válido.

Vive en ``service/`` (capa neutral, ADR 0028) y es importable desde el CLI y
desde cualquier futuro adaptador de transporte (sin tocar el dominio).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import networkx as nx

from bib2graph.constants import PAPER_NETWORK_KINDS
from bib2graph.networks.spec import NetworkArtifact, NetworkSpec

if TYPE_CHECKING:
    from bib2graph.workspace import Workspace


def load_artifact_from_disk(
    ws: Workspace,
    kind: str,
) -> NetworkArtifact | None:
    """Carga el ``NetworkArtifact`` de ``kind`` desde el workspace.

    Busca ``<workspace>/networks/<kind>/network.graphml`` y reconstruye el
    grafo + comunidades + spec a partir del grafo (atributo ``community``) y
    de ``<kind>/metrics.json`` (espec + métricas + assortativity).

    Returns:
        ``NetworkArtifact`` reconstruido, o ``None`` si los artefactos no
        existen (modo degradado del ADR 0052 D4 — ``b2g build`` no se corrió
        para ese kind).

    Args:
        ws: Workspace activo.
        kind: NetworkKind string (``"bibliographic_coupling"``,
            ``"cocitation"``, ``"author_collab"``, etc.).

    Returns:
        ``NetworkArtifact`` si los artefactos están en disco, ``None`` si no.
    """
    kind_dir = ws.networks_dir / kind
    graphml_path = kind_dir / "network.graphml"
    metrics_path = kind_dir / "metrics.json"

    if not graphml_path.exists():
        return None

    g = nx.read_graphml(str(graphml_path))

    # Spec desde metrics.json (con defaults sensatos si falta algún campo)
    clustering: str | None = None
    resolution: float = 1.0
    scope: str = "full"
    nodes_count: int = g.number_of_nodes()
    edges_count: int = g.number_of_edges()

    if metrics_path.exists():
        try:
            raw = json.loads(metrics_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = {}
        clustering = raw.get("clustering")
        if (
            isinstance(clustering, str)
            and clustering
            in {
                "louvain",
                "label_prop",
                "greedy_modularity",
            }
        ) or clustering is None:
            pass
        else:
            clustering = None
        try:
            resolution = float(raw.get("resolution", 1.0))
        except (TypeError, ValueError):
            resolution = 1.0
        if isinstance(raw.get("scope"), str) and raw["scope"] in {"full", "seeds_only"}:
            scope = raw["scope"]
        if isinstance(raw.get("nodes"), int):
            nodes_count = raw["nodes"]
        if isinstance(raw.get("edges"), int):
            edges_count = raw["edges"]

    spec = NetworkSpec(
        kind=kind,
        clustering=clustering,
        resolution=resolution,
        scope=scope,
    )

    # Comunidades: atributo ``community`` en cada nodo (escrito por
    # ``_write_artifacts`` cuando hay detección).
    communities: dict[Any, int] | None = None
    for node, data in g.nodes(data=True):
        if "community" in data and data["community"] is not None:
            if communities is None:
                communities = {}
            try:
                communities[node] = int(data["community"])
            except (TypeError, ValueError):
                continue
    # Si ningún nodo tiene community, conservamos None (no inventamos {} vs {})
    # — ``arrow_with_network`` y el envelope lo reflejan con `null`/0.

    # Métricas mínimas coherentes con el grafo recargado (los valores
    # ``density``/``num_components``/``avg_clustering`` del metrics.json
    # original se conservan si están, pero el grafo es la fuente de verdad
    # para ``nodes``/``edges``).
    metrics: dict[str, object] = {
        "nodes": nodes_count,
        "edges": edges_count,
    }

    # Asortatividad del metrics.json (escrita por ``_write_artifacts`` si el
    # build la computó con ``assortativity_attribute``).
    assortativity: dict[str, object] | None = None
    if metrics_path.exists():
        try:
            raw = json.loads(metrics_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = {}
        if isinstance(raw.get("assortativity"), dict):
            assortativity = raw["assortativity"]

    return NetworkArtifact(
        graph=g,
        metrics=metrics,
        communities=communities,
        assortativity=assortativity,
        layout=None,
        spec=spec,
    )


def is_paper_kind(kind: str) -> bool:
    """``True`` si el kind es de paper (coupling/cocitation). Cobertura fina."""
    return kind in PAPER_NETWORK_KINDS
