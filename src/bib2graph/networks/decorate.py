"""decorate — inyección de label legible y atributos en los nodos de un grafo.

Capa frontera entre proyectores puros y exportadores. Los proyectores producen
``nx.Graph`` con ids crudos como nodos; ``decorate`` transforma esos ids en
labels legibles (título, nombre de autor, keyword) y agrega atributos de
curación/comunidad/centralidad.

Reglas de diseño:
- No muta el corpus ni la tabla Arrow.
- Muta el grafo IN-PLACE (la copia ya la hace el llamador o el exporter).
- Determinista: mismo corpus + mismo artifact → mismos atributos.
- No importa duckdb (núcleo puro).

Mapeo de label por ``NetworkKind``:
  - ``bibliographic_coupling`` / ``cocitation``: nodo = paper id (Col.ID).
    Label = ``"título (año)"`` (hasta LABEL_MAX_CHARS caracteres + "...").
    Atributos extra: ``year``, ``is_seed``, ``curation_status``.
  - ``author_collab``: nodo = authors_id. Label = nombre de author_raw
    correlativo si es posible, si no el propio id.
  - ``institution_collab``: nodo = institutions_id. Label = nombre de
    institutions_raw correlativo si es posible.
  - ``keyword_cooccurrence``: nodo = keywords_id. La keyword normalizada ya
    es legible; se usa directamente como label.

Atributos universales (todos los kinds):
  - ``label``: string legible (ver mapeo arriba).
  - ``degree_centrality``: float calculado con ``nx.degree_centrality``.

Atributos adicionales de paper (coupling/cocitation):
  - ``year``: int o ausente si None.
  - ``is_seed``: bool.
  - ``curation_status``: string.

Atributo de comunidad (si se provee ``communities``):
  - ``community``: int.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import networkx as nx
import pyarrow as pa

from bib2graph.constants import Col, NetworkKind

if TYPE_CHECKING:
    from bib2graph.networks.spec import NetworkArtifact

    # nx.Graph es genérico solo en los stubs de types-networkx, no en runtime.
    _Graph = nx.Graph[Any, Any, Any]
else:
    _Graph = nx.Graph

LABEL_MAX_CHARS: int = 60

_PAPER_KINDS: frozenset[str] = frozenset(
    {NetworkKind.BIBLIOGRAPHIC_COUPLING, NetworkKind.COCITATION}
)


def _build_paper_index(table: pa.Table) -> dict[str, dict[str, object]]:
    """Construye un índice ``{paper_id → {label, year, is_seed, curation_status}}``.

    El label de paper es ``"título (año)"`` truncado a ``LABEL_MAX_CHARS`` chars.

    Args:
        table: Tabla Arrow canónica del Corpus.

    Returns:
        Dict con una entrada por fila; solo incluye papers con id no-None.
    """
    ids = table.column(Col.ID).to_pylist()
    titles = table.column(Col.TITLE).to_pylist()
    years = table.column(Col.YEAR).to_pylist()
    is_seeds = table.column(Col.IS_SEED).to_pylist()
    statuses = table.column(Col.CURATION_STATUS).to_pylist()

    index: dict[str, dict[str, object]] = {}
    for pid, title, year, is_seed, status in zip(
        ids, titles, years, is_seeds, statuses, strict=False
    ):
        if pid is None:
            continue
        key = str(pid)
        if title:
            label = str(title)
            if year is not None:
                label = f"{label} ({year})"
            if len(label) > LABEL_MAX_CHARS:
                label = label[:LABEL_MAX_CHARS] + "..."
        else:
            label = key

        index[key] = {
            "label": label,
            "year": int(year) if year is not None else None,
            "is_seed": bool(is_seed) if is_seed is not None else False,
            "curation_status": str(status) if status is not None else None,
        }
    return index


def _build_author_index(table: pa.Table) -> dict[str, str]:
    """Construye un índice ``{authors_id → nombre display (authors_raw)}``.

    Alinea ``authors_id[i]`` con ``authors_raw[i]`` de cada fila. Si el índice
    ``i`` está fuera de rango en ``authors_raw``, se usa el propio id como label.

    Args:
        table: Tabla Arrow canónica del Corpus.

    Returns:
        Dict ``{author_id_str: display_name_str}``.
    """
    ids_col = table.column(Col.AUTHORS_ID).to_pylist()
    raw_col = table.column(Col.AUTHORS_RAW).to_pylist()

    index: dict[str, str] = {}
    for ids, raws in zip(ids_col, raw_col, strict=False):
        if not ids or not isinstance(ids, list):
            continue
        raw_list = raws if isinstance(raws, list) else []
        for i, author_id in enumerate(ids):
            if author_id is None:
                continue
            key = str(author_id)
            if key not in index:
                name = raw_list[i] if i < len(raw_list) and raw_list[i] else key
                index[key] = str(name)
    return index


def _build_institution_index(table: pa.Table) -> dict[str, str]:
    """Construye un índice ``{institutions_id → nombre display (institutions_raw)}``.

    Alinea ``institutions_id[i]`` con ``institutions_raw[i]`` de cada fila.

    Args:
        table: Tabla Arrow canónica del Corpus.

    Returns:
        Dict ``{institution_id_str: display_name_str}``.
    """
    ids_col = table.column(Col.INSTITUTIONS_ID).to_pylist()
    raw_col = table.column(Col.INSTITUTIONS_RAW).to_pylist()

    index: dict[str, str] = {}
    for ids, raws in zip(ids_col, raw_col, strict=False):
        if not ids or not isinstance(ids, list):
            continue
        raw_list = raws if isinstance(raws, list) else []
        for i, inst_id in enumerate(ids):
            if inst_id is None:
                continue
            key = str(inst_id)
            if key not in index:
                name = raw_list[i] if i < len(raw_list) and raw_list[i] else key
                index[key] = str(name)
    return index


# API pública


def decorate_graph(
    graph: _Graph,
    table: pa.Table,
    kind: str,
    *,
    communities: dict[Any, int] | None = None,
) -> None:
    """Inyecta atributos legibles en los nodos del grafo IN-PLACE.

    No copia el grafo; el llamador debe copiar antes si necesita preservar
    el original (``graph.copy()``).

    Atributos inyectados siempre:
      - ``label``: string legible según el kind (ver docstring del módulo).
      - ``degree_centrality``: float.

    Atributos adicionales para redes de paper (coupling/cocitation):
      - ``year``: int o ausente si None en el corpus.
      - ``is_seed``: bool.
      - ``curation_status``: string.

    Atributo de comunidad (si se provee ``communities``):
      - ``community``: int.

    Args:
        graph: Grafo NetworkX a decorar (modificado in-place).
        table: Tabla Arrow del Corpus (fuente de metadatos).
        kind: ``NetworkKind`` de la red (determina el mapeo de label).
        communities: Dict opcional ``{nodo: int}`` de la detección de
            comunidades. Si es None, no se escribe el atributo ``community``.
    """
    if graph.number_of_nodes() == 0:
        return

    # Centralidad de grado (una sola llamada, determinista)
    deg_centrality: dict[Any, float] = nx.degree_centrality(graph)

    if kind in _PAPER_KINDS:
        paper_index = _build_paper_index(table)
        for node in graph.nodes():
            key = str(node)
            info = paper_index.get(key, {})
            graph.nodes[node]["label"] = str(info.get("label", key))
            graph.nodes[node]["degree_centrality"] = deg_centrality.get(node, 0.0)
            year = info.get("year")
            if isinstance(year, int):
                graph.nodes[node]["year"] = year
            is_seed = info.get("is_seed")
            if isinstance(is_seed, bool):
                graph.nodes[node]["is_seed"] = is_seed
            curation = info.get("curation_status")
            if curation is not None:
                graph.nodes[node]["curation_status"] = str(curation)

    elif kind == NetworkKind.AUTHOR_COLLAB:
        author_index = _build_author_index(table)
        for node in graph.nodes():
            key = str(node)
            graph.nodes[node]["label"] = author_index.get(key, key)
            graph.nodes[node]["degree_centrality"] = deg_centrality.get(node, 0.0)

    elif kind == NetworkKind.INSTITUTION_COLLAB:
        inst_index = _build_institution_index(table)
        for node in graph.nodes():
            key = str(node)
            graph.nodes[node]["label"] = inst_index.get(key, key)
            graph.nodes[node]["degree_centrality"] = deg_centrality.get(node, 0.0)

    elif kind == NetworkKind.KEYWORD_COOCCURRENCE:
        # La keyword normalizada ya es legible; se usa directamente como label.
        for node in graph.nodes():
            graph.nodes[node]["label"] = str(node)
            graph.nodes[node]["degree_centrality"] = deg_centrality.get(node, 0.0)

    else:
        # Kind desconocido: fallback al id crudo (no fallar; es extensible)
        for node in graph.nodes():
            graph.nodes[node]["label"] = str(node)
            graph.nodes[node]["degree_centrality"] = deg_centrality.get(node, 0.0)

    if communities is not None:
        for node, comm_id in communities.items():
            if graph.has_node(node):
                graph.nodes[node]["community"] = int(comm_id)


def decorate(artifact: NetworkArtifact, table: pa.Table) -> None:
    """Decora el grafo del artefacto IN-PLACE con labels y atributos de nodo.

    Atajo sobre ``decorate_graph`` que extrae kind y communities del
    ``NetworkArtifact`` directamente.  Es el punto de integración en
    ``facade.py``.

    Args:
        artifact: ``NetworkArtifact`` cuyo ``graph`` se decorará in-place.
        table: Tabla Arrow del Corpus (fuente de metadatos).
    """
    decorate_graph(
        artifact.graph,
        table,
        artifact.spec.kind,
        communities=artifact.communities,
    )
