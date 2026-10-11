"""arrow — exportador del corpus a un archivo Arrow IPC (Feather).

Implementa ``ArrowExporter`` según ADR 0050 D4 y ``arrow_with_network`` según
ADR 0052 D1/D3/D4. Serializa la tabla que ``Corpus.to_arrow()`` produce
(schema + metadata ya poblados por la proyección) a un único archivo
``.arrow`` (Arrow IPC / Feather), autoverificable para consumidores externos
(un consumidor programático).

Es un artefacto DISTINTO de ``snapshot create`` (parquet + manifest.json,
reproducibilidad interna, ADR 0017/0030): este exportador NO toca el schema
ni agrega/computa metadata por sí mismo — solo serializa la tabla tal como
``to_arrow()`` la entrega. ``pyarrow.feather.write_feather`` preserva la
metadata del schema (incluido cualquier ``equation_hash``/objeto ecuación que
la otra pieza del contrato, #291/#292, haya poblado) sin intervención de este
módulo.

ADR 0052 (#321) — red tipada en el Arrow:
``arrow_with_network(table, artifact)`` toma la tabla canónica del corpus y le
adhiere, cuando hay ``NetworkArtifact`` disponible, **5 columnas nuevas**
(``community_id``, ``degree_weighted``, ``intra_community_pagerank``,
``network_edges``, ``network_communities``) y **4 claves de metadata**
(``network_type``, ``network_type_algo``, ``network_resolution``,
``network_scope``). Si ``artifact is None``, la tabla queda intacta
(columnas de red **ausentes**, ``network_type`` ausente) — modo degradado
del ADR 0052 D4. La función es pura: no toca I/O, no toca ``corpus_hash``,
no muta la tabla de entrada.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pyarrow as pa

from bib2graph.constants import PAPER_NETWORK_KINDS

if TYPE_CHECKING:
    from bib2graph.networks.spec import NetworkArtifact


# Schemas Arrow de las columnas struct anidadas (ADR 0052 D1).
_EDGE_STRUCT = pa.struct(
    [
        pa.field("neighbor_id", pa.string(), nullable=False),
        pa.field("weight", pa.int64(), nullable=False),
    ]
)
_LIST_EDGES = pa.list_(_EDGE_STRUCT)

_COMMUNITY_STRUCT = pa.struct(
    [
        pa.field("community_id", pa.int64(), nullable=False),
        pa.field("size", pa.int64(), nullable=False),
        pa.field("modularity", pa.float64(), nullable=False),
    ]
)
_LIST_COMMUNITIES = pa.list_(_COMMUNITY_STRUCT)


# Kinds cuyo nodo es un paper id (``Col.ID``). Las redes no-papers
# Kinds de paper: reusar la fuente única de ``constants`` (ADR 0023). Kinds
# no-paper (author_collab / institution_collab / keyword_cooccurrence) no se
# pueden anclar por paper en el Arrow; la elección de kind la hace el CLI
# (allí se decide si se avisa con warning o se cae).


class ArrowExporter:
    """Exporta una tabla Arrow del corpus a un archivo Feather (Arrow IPC).

    No modifica el schema ni la tabla: solo la serializa. La metadata del
    schema (si la tabla la trae) viaja intacta dentro del archivo.
    """

    def export(self, table: pa.Table, out_path: str | Path) -> Path:
        """Escribe ``table`` a ``out_path`` en formato Feather (Arrow IPC).

        Args:
            table: Tabla Arrow a serializar (típicamente
                ``corpus.scoped(scope).to_arrow()``).
            out_path: Ruta del archivo de salida (p. ej.
                ``<exports_dir>/corpus.arrow``). El directorio padre se
                crea si no existe.

        Returns:
            La ``Path`` del archivo escrito.
        """
        from pyarrow import feather

        resolved = Path(out_path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        feather.write_feather(table, str(resolved))  # type: ignore[no-untyped-call]
        return resolved


def _degree_weighted(graph: Any) -> dict[Any, int]:
    """Suma de los pesos de las aristas por nodo.

    Función auxiliar interna. Para un grafo ``nx.Graph`` con atributo
    ``weight`` en cada arista, devuelve ``{nodo: int}`` con la suma de los
    pesos de las aristas adyacentes. Aislados quedan en 0.

    Args:
        graph: Grafo NetworkX.

    Returns:
        Dict ``nodo → int`` con el ``degree_weighted`` de cada nodo.
    """
    result: dict[Any, int] = {}
    for node in graph.nodes():
        total = 0
        for neighbor in graph.neighbors(node):
            data = graph.edges[node, neighbor]
            w = data.get("weight", 1) if isinstance(data, dict) else 1
            try:
                total += int(w)
            except (TypeError, ValueError):
                total += 1
        result[node] = total
    return result


def _global_partition_table(
    communities: dict[Any, int],
    graph: Any,
) -> list[dict[str, Any]]:
    """Construye la lista ``[struct community_id, size, modularity]``.

    Una entrada por comunidad presente en ``communities`` (partición global
    de la red). Es **idéntica para todos los papers** del Arrow exportado
    (ADR 0052 D1): una sola vez por paper, es la partición completa.

    Args:
        communities: Dict ``nodo → community_id`` (salida de
            ``detect_communities``).
        graph: Grafo de la red; se usa para calcular la modularidad de
            Newman de la partición (``nx.community.modularity``).

    Returns:
        Lista de dicts ``{"community_id": int, "size": int, "modularity": float}``
        ordenada por ``community_id`` ascendente. ``modularity`` es la
        modularidad de Newman de TODA la partición (no por comunidad); se
        replica en cada fila por consistencia de tipo Arrow.
    """
    import networkx as nx

    if not communities:
        return []

    # Reconstruir la lista de sets por comunidad que exige nx.community.modularity
    comm_ids = sorted({int(c) for c in communities.values()})
    by_comm: dict[int, set[Any]] = {cid: set() for cid in comm_ids}
    for node, comm_id in communities.items():
        if graph.has_node(node):
            by_comm[int(comm_id)].add(node)

    comm_sets: list[set[Any]] = [by_comm[cid] for cid in comm_ids]

    # Modularidad global de Newman (misma para todas las filas; la reportamos
    # en cada struct de la lista — semántica: "modularidad de la partición a la
    # que esta comunidad pertenece").
    modularity = nx.community.modularity(graph, comm_sets)

    return [
        {
            "community_id": int(cid),
            "size": len(by_comm[cid]),
            "modularity": float(modularity),
        }
        for cid in comm_ids
    ]


def arrow_with_network(
    table: pa.Table,
    artifact: NetworkArtifact | None,
) -> pa.Table:
    """Devuelve la tabla del corpus con la red tipada embebida (ADR 0052 D1).

    Si ``artifact`` es ``None``, devuelve la tabla intacta (modo degradado,
    ADR 0052 D4): las columnas de red están ausentes y ``network_type``
    ausente en metadata. Esto permite que un export sin ``b2g build`` previo
    siga produciendo un Arrow válido, sin mentir sobre la presencia de red.

    Si ``artifact`` está presente, exige que su kind sea de paper
    (``bibliographic_coupling`` o ``cocitation``); para kinds no-papers la
    función lanza ``ValueError`` (la decisión de warning vs error es del CLI,
    no del exportador).

    Función pura: no toca I/O, no muta ``table``, no afecta ``corpus_hash``
    (las columnas de red se adhieren a la tabla DESPUÉS de calcular el hash
    sobre la tabla original).

    Args:
        table: Tabla Arrow canónica del corpus (la que produce
            ``corpus.to_arrow()``).
        artifact: ``NetworkArtifact`` con la red computada por ``b2g build``
            para la red solicitada. ``None`` = modo degradado.

    Returns:
        Nueva ``pa.Table`` con las 5 columnas de red añadidas (``community_id``,
        ``degree_weighted``, ``intra_community_pagerank``, ``network_edges``,
        ``network_communities``) y la metadata del schema extendida con las
        4 claves ``network_type``/``network_type_algo``/``network_resolution``/
        ``network_scope`` si ``artifact`` está. Si ``artifact`` es ``None``,
        devuelve ``table`` sin cambios (mismas columnas, misma metadata).
    """
    if artifact is None:
        return table

    if artifact.spec.kind not in PAPER_NETWORK_KINDS:
        raise ValueError(
            f"arrow_with_network solo aplica a kinds de paper "
            f"({sorted(PAPER_NETWORK_KINDS)}); recibido '{artifact.spec.kind}'. "
            f"Para kinds no-papers, usar --format graphml o no embeber red."
        )

    graph = artifact.graph
    communities = artifact.communities or {}

    # Importación perezosa: la función es núcleo puro; la única dependencia
    # de runtime fuera del stdlib + pyarrow es networkx (ya declarada).
    from bib2graph.networks.intra_community_pagerank import intra_community_pagerank

    pr_per_node = intra_community_pagerank(graph, communities)
    degree_per_node = _degree_weighted(graph)

    global_partition = _global_partition_table(communities, graph)

    # Construir las 5 columnas alineadas con ``table.num_rows`` por posición
    # del paper id (los papers sin match en el grafo reciben valores neutros:
    # community_id -1, degree_weighted 0, pagerank 0.0, edges [], partición
    # global igual para todos).
    ids = table.column("id").to_pylist() if "id" in table.schema.names else None
    n = table.num_rows

    community_col: list[int] = []
    degree_col: list[int] = []
    pagerank_col: list[float] = []
    edges_col: list[list[dict[str, Any]]] = []
    comm_struct_col: list[list[dict[str, Any]]] = []

    for i in range(n):
        pid = ids[i] if ids is not None else None

        if pid is not None and graph.has_node(pid):
            community_col.append(int(communities.get(pid, -1)))
            degree_col.append(int(degree_per_node.get(pid, 0)))
            pagerank_col.append(float(pr_per_node.get(pid, 0.0)))
            edges: list[dict[str, Any]] = []
            for neighbor in graph.neighbors(pid):
                data = graph.edges[pid, neighbor]
                w = data.get("weight", 1) if isinstance(data, dict) else 1
                try:
                    w_int = int(w)
                except (TypeError, ValueError):
                    w_int = 1
                edges.append({"neighbor_id": str(neighbor), "weight": w_int})
            edges_col.append(edges)
        else:
            # Paper no presente en el grafo (aislado o sin aristas): valores
            # neutros. La partición global se replica igual para que todos
            # los papers tengan la misma información de comunidades.
            community_col.append(-1)
            degree_col.append(0)
            pagerank_col.append(0.0)
            edges_col.append([])

        comm_struct_col.append(list(global_partition))

    # Adjuntar las 5 columnas. Construimos un schema target con ``nullable=False``
    # explícito en las 3 columnas planas (ADR 0052 D1) y ``cast`` al final
    # para fijar el flag de nulabilidad — ``pa.array(values, type=...)`` produce
    # columnas nullable por default, y ``cast`` a un tipo simple no toca el
    # flag; hace falta cast a nivel de schema.
    table_with_net = (
        table.append_column("community_id", pa.array(community_col, type=pa.int64()))
        .append_column("degree_weighted", pa.array(degree_col, type=pa.int64()))
        .append_column(
            "intra_community_pagerank",
            pa.array(pagerank_col, type=pa.float64()),
        )
        .append_column("network_edges", pa.array(edges_col, type=_LIST_EDGES))
        .append_column(
            "network_communities",
            pa.array(comm_struct_col, type=_LIST_COMMUNITIES),
        )
    )

    # Cast del schema completo para fijar ``nullable=False`` en las 5 columnas
    # de red (ADR 0052 D1) — los structs anidados ya están bien con
    # ``nullable=False`` por construcción de ``pa.struct([...])``, pero
    # ``pa.array(values, type=...)`` produce columnas plana con ``nullable=True``
    # por default y eso no se corrige con ``cast`` a un tipo simple; hace
    # falta cast a nivel de schema.
    target_schema = table_with_net.schema.with_metadata(
        table_with_net.schema.metadata or {}
    )
    new_fields: list[pa.Field] = []
    for field in target_schema:
        if field.name in {
            "community_id",
            "degree_weighted",
            "intra_community_pagerank",
            "network_edges",
            "network_communities",
        }:
            new_fields.append(field.with_nullable(False))
        else:
            new_fields.append(field)
    target_schema = pa.schema(new_fields, metadata=target_schema.metadata)
    table_with_net = table_with_net.cast(target_schema)

    # Metadata del schema (ADR 0052 D1) — aditiva sobre la metadata que la
    # tabla ya traiga (p. ej. ``equation_hash`` de ADR 0050 D3).
    existing_metadata = dict(table_with_net.schema.metadata or {})
    existing_metadata[b"network_type"] = str(artifact.spec.kind).encode("utf-8")
    if artifact.spec.clustering is not None:
        existing_metadata[b"network_type_algo"] = str(artifact.spec.clustering).encode(
            "utf-8"
        )
    existing_metadata[b"network_resolution"] = str(artifact.spec.resolution).encode(
        "utf-8"
    )
    existing_metadata[b"network_scope"] = str(artifact.spec.scope).encode("utf-8")

    new_schema = table_with_net.schema.with_metadata(existing_metadata)
    return table_with_net.cast(new_schema)
