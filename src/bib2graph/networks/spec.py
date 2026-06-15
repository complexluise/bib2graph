"""spec — NetworkSpec (hook mínimo) y NetworkArtifact.

Contiene los tipos de datos centrales del módulo de redes:
  - ``NetworkSpec``: configuración declarativa de una red (hook para Hito 9).
  - ``NetworkArtifact``: resultado de proyectar + analizar un corpus.

Ver API.md §10.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

import networkx as nx
from pydantic import BaseModel

if TYPE_CHECKING:
    # nx.Graph es genérico solo en los stubs de types-networkx, no en runtime.
    _Graph = nx.Graph[Any, Any, Any]
else:
    _Graph = nx.Graph


class NetworkSpec(BaseModel):
    """Configuración declarativa de una red bibliométrica.

    Hito 2: se usa como hook mínimo en ``Networks.build``/``Networks.quick``.
    La carga desde YAML y la validación avanzada se implementan en el Hito 9.

    Args:
        kind: Tipo de red a proyectar.
        min_weight: Peso mínimo de arista (D1). Default 1 = sin filtro.
        min_year: Filtro de año mínimo (futuro).
        max_year: Filtro de año máximo (futuro).
        scope: Alcance de la proyección.
        clustering: Método de detección de comunidades.
        assortativity_attribute: Atributo categórico para asortatividad.
        layout: Algoritmo de layout para visualización (futuro).
    """

    kind: Literal[
        "bibliographic_coupling",
        "cocitation",
        "author_collab",
        "institution_collab",
        "keyword_cooccurrence",
    ]
    min_weight: int = 1
    min_year: int | None = None
    max_year: int | None = None
    scope: Literal["full", "seeds_only"] = "full"
    clustering: Literal["louvain", "label_prop", "greedy_modularity"] | None = "louvain"
    assortativity_attribute: str | None = None
    layout: Literal["spring", "kamada_kawai", "circular"] | None = None


@dataclass
class NetworkArtifact:
    """Resultado de proyectar y analizar un corpus con una ``NetworkSpec``.

    Agrupa el grafo, las métricas, las comunidades, la asortatividad, el layout
    y la especificación que lo originó.

    Attributes:
        graph: Grafo NetworkX proyectado.
        metrics: Salida de ``network_metrics`` (densidad, componentes, clustering).
        communities: Salida de ``detect_communities`` o None si no se calculó.
        assortativity: Salida de ``assortativity`` o None si no se calculó.
        layout: Dict nodo→coordenadas o None si no se calculó.
        spec: Especificación que generó este artefacto.
    """

    graph: _Graph
    metrics: dict[str, object]
    communities: dict[Any, int] | None
    assortativity: dict[str, object] | None
    layout: dict[Any, Any] | None
    spec: NetworkSpec
