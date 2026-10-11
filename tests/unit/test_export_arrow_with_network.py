"""Tests TDD — red tipada embebida en el Arrow del corpus (ADR 0052 D1/D3/D4, #321).

Cubre:
1. ``arrow_with_network`` con NetworkArtifact -> schema con las 5 columnas
   nuevas + 4 claves de metadata (network_type, network_type_algo,
   network_resolution, network_scope).
2. ``arrow_with_network`` con artifact=None -> tabla intacta (modo degradado).
3. Round-trip Arrow: serializar y releer preserva columnas y metadata.
4. Constraint del consumidor programático: las columnas PRE-EXISTENTES no
   cambian de nombre/tipo/nullability (ADR 0050 §Constraints).
5. corpus_hash intacto: tabla con/sin red tiene el mismo content-hash.
7. La función valida que el kind del artifact sea paper (coupling/cocitation);
   para kinds no-papers emite ``ValueError`` (la responsabilidad de elegir
   kind vs warning la tiene el CLI).

Marcador: ``unit`` (sin red, sin I/O).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import networkx as nx
import pyarrow as pa
import pytest

from bib2graph.backends.memory import compute_corpus_hash
from bib2graph.constants import Col, NetworkKind
from bib2graph.exporters.arrow import ArrowExporter, arrow_with_network
from bib2graph.networks.spec import NetworkArtifact, NetworkSpec
from bib2graph.schemas import CORPUS_SCHEMA

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row(
    id: str,
    *,
    title: str = "Paper",
    is_seed: bool = True,
    curation_status: str = "candidate",
    doi: str | None = None,
    year: int | None = 2020,
) -> dict[str, Any]:
    return {
        "id": id,
        "source_id": None,
        "doi": doi,
        "title": title,
        "year": year,
        "abstract": None,
        "source": None,
        "language": None,
        "publisher": None,
        "research_areas": None,
        "is_seed": is_seed,
        "curation_status": curation_status,
        "provenance": None,
        "authors_raw": None,
        "authors_id": None,
        "authors_affiliations": None,
        "keywords_raw": None,
        "keywords_id": None,
        "institutions_raw": None,
        "institutions_id": None,
        "references_id": None,
        "references_doi": None,
        "cited_by_id": None,
    }


def _3_row_corpus() -> pa.Table:
    rows = [
        _row("doi:p1", title="Paper A", doi="10.1/p1"),
        _row("doi:p2", title="Paper B", doi="10.1/p2"),
        _row("doi:p3", title="Paper C", doi="10.1/p3"),
    ]
    return pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)


def _build_artifact(
    *,
    nodes: list[str],
    edges: list[tuple[str, str, int]],
    communities: dict[str, int],
    algo: str = "louvain",
    resolution: float = 1.0,
    scope: str = "full",
) -> NetworkArtifact:
    """Construye un NetworkArtifact sintético para tests."""
    g: nx.Graph = nx.Graph()
    g.add_nodes_from(nodes)
    for a, b, w in edges:
        g.add_edge(a, b, weight=w)
    spec = NetworkSpec(
        kind=NetworkKind.BIBLIOGRAPHIC_COUPLING,  # type: ignore[arg-type]
        clustering=algo,  # type: ignore[arg-type]
        resolution=resolution,
        scope=scope,  # type: ignore[arg-type]
    )
    return NetworkArtifact(
        graph=g,
        metrics={"density": 0.0, "num_components": 1, "avg_clustering": 0.0},
        communities=communities,
        assortativity=None,
        layout=None,
        spec=spec,
    )


# ---------------------------------------------------------------------------
# 1. arrow_with_network con artifact (modo con red)
# ---------------------------------------------------------------------------


class TestArrowWithNetworkAddsColumns:
    def test_schema_extendido_tiene_5_columnas_nuevas(self) -> None:
        """Con NetworkArtifact -> schema con las 5 columnas de red.

        Las 5 columnas (ADR 0052 D1):
          community_id (int64), degree_weighted (int64),
          intra_community_pagerank (float64),
          network_edges (list<struct<neighbor_id: string, weight: int64>>),
          network_communities (list<struct<community_id: int64, size: int64, modularity: float64>>).
        """
        table = _3_row_corpus()
        artifact = _build_artifact(
            nodes=["doi:p1", "doi:p2", "doi:p3"],
            edges=[("doi:p1", "doi:p2", 3), ("doi:p2", "doi:p3", 1)],
            communities={"doi:p1": 0, "doi:p2": 0, "doi:p3": 1},
        )

        result = arrow_with_network(table, artifact)

        new_cols = {
            "community_id",
            "degree_weighted",
            "intra_community_pagerank",
            "network_edges",
            "network_communities",
        }
        assert new_cols.issubset(set(result.schema.names))

        # Tipos
        assert result.schema.field("community_id").type.equals(pa.int64())
        assert result.schema.field("community_id").nullable is False
        assert result.schema.field("degree_weighted").type.equals(pa.int64())
        assert result.schema.field("degree_weighted").nullable is False
        assert result.schema.field("intra_community_pagerank").type.equals(pa.float64())
        assert result.schema.field("intra_community_pagerank").nullable is False

        # Struct anidado de aristas
        edge_field = result.schema.field("network_edges")
        assert pa.types.is_list(edge_field.type)
        edge_struct = edge_field.type.value_type
        assert pa.types.is_struct(edge_struct)
        assert edge_struct.equals(
            pa.struct(
                [
                    pa.field("neighbor_id", pa.string(), nullable=False),
                    pa.field("weight", pa.int64(), nullable=False),
                ]
            )
        )
        assert edge_field.nullable is False

        # Struct anidado de comunidades
        comm_field = result.schema.field("network_communities")
        assert pa.types.is_list(comm_field.type)
        comm_struct = comm_field.type.value_type
        assert pa.types.is_struct(comm_struct)
        assert comm_struct.equals(
            pa.struct(
                [
                    pa.field("community_id", pa.int64(), nullable=False),
                    pa.field("size", pa.int64(), nullable=False),
                    pa.field("modularity", pa.float64(), nullable=False),
                ]
            )
        )
        assert comm_field.nullable is False

    def test_metadata_de_red_poblada_con_kind_algo_resolution_scope(self) -> None:
        """Metadata del schema Arrow incluye las 4 claves network_*. (ADR 0052 D1)."""
        table = _3_row_corpus()
        artifact = _build_artifact(
            nodes=["doi:p1", "doi:p2"],
            edges=[("doi:p1", "doi:p2", 1)],
            communities={"doi:p1": 0, "doi:p2": 0},
            algo="label_prop",
            resolution=1.5,
            scope="seeds_only",
        )

        result = arrow_with_network(table, artifact)

        metadata = result.schema.metadata or {}
        assert metadata[b"network_type"] == b"bibliographic_coupling"
        assert metadata[b"network_type_algo"] == b"label_prop"
        assert metadata[b"network_resolution"] == b"1.5"
        assert metadata[b"network_scope"] == b"seeds_only"

    def test_numero_de_filas_se_conserva(self) -> None:
        """La tabla resultante tiene la misma cantidad de filas que la original."""
        table = _3_row_corpus()
        artifact = _build_artifact(
            nodes=["doi:p1", "doi:p2"],
            edges=[("doi:p1", "doi:p2", 1)],
            communities={"doi:p1": 0, "doi:p2": 0},
        )
        result = arrow_with_network(table, artifact)
        assert result.num_rows == 3

    def test_poblacion_de_community_id(self) -> None:
        """Cada paper recibe el community_id correcto del dict de comunidades."""
        table = _3_row_corpus()
        artifact = _build_artifact(
            nodes=["doi:p1", "doi:p2", "doi:p3"],
            edges=[("doi:p1", "doi:p2", 1)],
            communities={"doi:p1": 0, "doi:p2": 0, "doi:p3": 7},
        )
        result = arrow_with_network(table, artifact)
        comm_col = result.column("community_id").to_pylist()
        ids = result.column(Col.ID).to_pylist()
        comm_by_id = dict(zip(ids, comm_col, strict=False))
        assert comm_by_id["doi:p1"] == 0
        assert comm_by_id["doi:p2"] == 0
        assert comm_by_id["doi:p3"] == 7

    def test_poblacion_de_degree_weighted(self) -> None:
        """degree_weighted = suma de pesos de las aristas del paper."""
        table = _3_row_corpus()
        artifact = _build_artifact(
            nodes=["doi:p1", "doi:p2", "doi:p3"],
            edges=[
                ("doi:p1", "doi:p2", 3),
                ("doi:p1", "doi:p3", 5),
                ("doi:p2", "doi:p3", 2),
            ],
            communities={"doi:p1": 0, "doi:p2": 0, "doi:p3": 0},
        )
        result = arrow_with_network(table, artifact)
        dw_col = result.column("degree_weighted").to_pylist()
        ids = result.column(Col.ID).to_pylist()
        dw_by_id = dict(zip(ids, dw_col, strict=False))
        assert dw_by_id["doi:p1"] == 8  # 3 + 5
        assert dw_by_id["doi:p2"] == 5  # 3 + 2
        assert dw_by_id["doi:p3"] == 7  # 5 + 2

    def test_poblacion_de_network_edges_salientes(self) -> None:
        """network_edges = aristas SALIENTES del paper con su peso."""
        table = _3_row_corpus()
        artifact = _build_artifact(
            nodes=["doi:p1", "doi:p2", "doi:p3"],
            edges=[
                ("doi:p1", "doi:p2", 3),
                ("doi:p1", "doi:p3", 5),
            ],
            communities={"doi:p1": 0, "doi:p2": 0, "doi:p3": 0},
        )
        result = arrow_with_network(table, artifact)
        edges_col = result.column("network_edges").to_pylist()
        ids = result.column(Col.ID).to_pylist()
        edges_by_id = dict(zip(ids, edges_col, strict=False))

        # p1 ve a p2 (peso 3) y a p3 (peso 5)
        p1_edges = edges_by_id["doi:p1"]
        assert {(e["neighbor_id"], e["weight"]) for e in p1_edges} == {
            ("doi:p2", 3),
            ("doi:p3", 5),
        }

        # p2 ve solo a p1 (grafo no dirigido, pero "salientes" = aristas)
        p2_edges = edges_by_id["doi:p2"]
        assert {(e["neighbor_id"], e["weight"]) for e in p2_edges} == {("doi:p1", 3)}

        # p3 ve a p1 (peso 5)
        p3_edges = edges_by_id["doi:p3"]
        assert {(e["neighbor_id"], e["weight"]) for e in p3_edges} == {("doi:p1", 5)}

    def test_nodo_aislado_tiene_network_edges_vacio(self) -> None:
        """Un nodo sin aristas tiene ``network_edges=[]`` (no null)."""
        table = _3_row_corpus()
        artifact = _build_artifact(
            nodes=["doi:p1", "doi:p2", "doi:p3"],
            edges=[("doi:p1", "doi:p2", 1)],  # p3 aislado
            communities={"doi:p1": 0, "doi:p2": 0, "doi:p3": 1},
        )
        result = arrow_with_network(table, artifact)
        edges_col = result.column("network_edges").to_pylist()
        ids = result.column(Col.ID).to_pylist()
        edges_by_id = dict(zip(ids, edges_col, strict=False))
        assert edges_by_id["doi:p3"] == []

    def test_network_communities_identico_para_todos_los_papers(self) -> None:
        """``network_communities`` es la partición GLOBAL, idéntica en cada fila.

        Una sola vez por paper: la lista es la misma para todas las filas
        (es la partición completa de la red, no la partición por paper).
        """
        table = _3_row_corpus()
        artifact = _build_artifact(
            nodes=["doi:p1", "doi:p2", "doi:p3"],
            edges=[("doi:p1", "doi:p2", 1)],
            communities={"doi:p1": 0, "doi:p2": 0, "doi:p3": 1},
        )
        result = arrow_with_network(table, artifact)
        nc_col = result.column("network_communities").to_pylist()
        # Todos los papers traen la MISMA lista
        assert nc_col[0] == nc_col[1]
        assert nc_col[1] == nc_col[2]
        # 2 comunidades: ids 0 y 1
        comm_ids = sorted([c["community_id"] for c in nc_col[0]])
        assert comm_ids == [0, 1]

    def test_network_communities_incluye_size_y_modularity(self) -> None:
        """Cada entrada de ``network_communities`` trae ``size`` y ``modularity``."""
        table = _3_row_corpus()
        artifact = _build_artifact(
            nodes=["doi:p1", "doi:p2", "doi:p3"],
            edges=[("doi:p1", "doi:p2", 1)],
            communities={"doi:p1": 0, "doi:p2": 0, "doi:p3": 1},
        )
        result = arrow_with_network(table, artifact)
        nc_col = result.column("network_communities").to_pylist()
        # La primera fila tiene 2 entradas de la lista
        assert len(nc_col[0]) == 2
        for entry in nc_col[0]:
            assert "community_id" in entry
            assert "size" in entry
            assert "modularity" in entry
            assert isinstance(entry["community_id"], int)
            assert isinstance(entry["size"], int)
            assert isinstance(entry["modularity"], float)

    def test_intra_community_pagerank_calculado(self) -> None:
        """``intra_community_pagerank`` se computa por subgrafo de comunidad."""
        table = _3_row_corpus()
        artifact = _build_artifact(
            nodes=["doi:p1", "doi:p2", "doi:p3"],
            edges=[("doi:p1", "doi:p2", 2), ("doi:p2", "doi:p3", 1)],
            communities={"doi:p1": 0, "doi:p2": 0, "doi:p3": 0},
        )
        result = arrow_with_network(table, artifact)
        pr_col = result.column("intra_community_pagerank").to_pylist()
        # Todos en la misma comunidad: los 3 forman el subgrafo
        for v in pr_col:
            assert isinstance(v, float)
            assert v > 0.0
            # PageRank suma a 1.0 sobre el subgrafo de la comunidad
            assert abs(sum(pr_col) - 1.0) < 1e-6


# ---------------------------------------------------------------------------
# 2. Modo degradado (artifact=None)
# ---------------------------------------------------------------------------


class TestArrowWithNetworkDegraded:
    def test_sin_artifact_tabla_intacta(self) -> None:
        """``artifact=None`` -> tabla sin columnas de red (modo degradado, D4)."""
        table = _3_row_corpus()
        original_names = set(CORPUS_SCHEMA.names)
        result = arrow_with_network(table, None)

        new_cols = {
            "community_id",
            "degree_weighted",
            "intra_community_pagerank",
            "network_edges",
            "network_communities",
        }
        # Las columnas de red están AUSENTES (no null/no vacías)
        assert not new_cols.intersection(set(result.schema.names))
        # El resto de columnas sigue presente
        assert set(result.schema.names) == original_names

    def test_sin_artifact_metadata_no_traer_network_type(self) -> None:
        """``artifact=None`` -> metadata del Arrow NO trae ``network_type`` (D4)."""
        table = _3_row_corpus()
        result = arrow_with_network(table, None)
        metadata = result.schema.metadata or {}
        assert b"network_type" not in metadata
        assert b"network_type_algo" not in metadata
        assert b"network_resolution" not in metadata
        assert b"network_scope" not in metadata


# ---------------------------------------------------------------------------
# 3. Round-trip Arrow: serializar y releer preserva la red
# ---------------------------------------------------------------------------


class TestArrowRoundTripWithNetwork:
    def test_roundtrip_preserva_columnas_y_metadata(self, tmp_path: Path) -> None:
        """Serializar con ``ArrowExporter`` y releer preserva columnas + metadata."""
        table = _3_row_corpus()
        artifact = _build_artifact(
            nodes=["doi:p1", "doi:p2", "doi:p3"],
            edges=[("doi:p1", "doi:p2", 3), ("doi:p2", "doi:p3", 1)],
            communities={"doi:p1": 0, "doi:p2": 0, "doi:p3": 1},
            algo="louvain",
            resolution=1.0,
        )
        with_table = arrow_with_network(table, artifact)

        out = tmp_path / "with_net.arrow"
        ArrowExporter().export(with_table, out)

        import pyarrow.feather as feather

        reread = feather.read_table(str(out))
        # Mismas columnas
        assert set(reread.schema.names) == set(with_table.schema.names)
        # Metadata preservada
        assert reread.schema.metadata == with_table.schema.metadata
        # Las columnas de red se pueden leer
        assert "community_id" in reread.schema.names
        assert "network_edges" in reread.schema.names
        comm_col = reread.column("community_id").to_pylist()
        assert set(comm_col) == {0, 1}

    def test_roundtrip_sin_red_preserva_esquema_minimo(self, tmp_path: Path) -> None:
        """Modo degradado: round-trip con tabla sin red -> schema mínimo del corpus."""
        table = _3_row_corpus()
        degraded = arrow_with_network(table, None)
        out = tmp_path / "no_net.arrow"
        ArrowExporter().export(degraded, out)

        import pyarrow.feather as feather

        reread = feather.read_table(str(out))
        assert set(reread.schema.names) == set(CORPUS_SCHEMA.names)
        assert b"network_type" not in (reread.schema.metadata or {})


# ---------------------------------------------------------------------------
# 4. Constraint del consumidor programático (ADR 0050 §Constraints)
# ---------------------------------------------------------------------------


class TestConsumerProgrammaticConstraints:
    """Las columnas PRE-EXISTENTES del Arrow NO cambian de nombre/tipo cuando
    se agrega la red tipada. El consumidor programático (#296) sigue
    funcionando sobre el Arrow exportado."""

    def test_columnas_pre_existentes_intactas_en_nombre_y_tipo(self) -> None:
        """Las 23 columnas de CORPUS_SCHEMA se conservan con nombre y tipo exactos."""
        table = _3_row_corpus()
        artifact = _build_artifact(
            nodes=["doi:p1", "doi:p2", "doi:p3"],
            edges=[("doi:p1", "doi:p2", 1)],
            communities={"doi:p1": 0, "doi:p2": 0, "doi:p3": 1},
        )
        result = arrow_with_network(table, artifact)

        for field in CORPUS_SCHEMA:
            assert field.name in result.schema.names, (
                f"Columna pre-existente '{field.name}' desapareció al agregar "
                f"la red tipada (rompe el constraint del consumidor programático)."
            )
            actual = result.schema.field(field.name)
            assert actual.type.equals(field.type), (
                f"Tipo de '{field.name}' cambió: se esperaba {field.type!s}, "
                f"se encontró {actual.type!s}."
            )

    def test_ingest_de_consumidor_que_ignora_columnas_nuevas_funciona(self) -> None:
        """Un consumidor que ignora las columnas nuevas puede leer el Arrow.

        Simula el ingest de un consumidor programático que solo lee las
        columnas pre-existentes (las del golden schema, ADR 0050). El
        Arrow con red tipada debe ser legible.
        """
        table = _3_row_corpus()
        artifact = _build_artifact(
            nodes=["doi:p1", "doi:p2", "doi:p3"],
            edges=[("doi:p1", "doi:p2", 1)],
            communities={"doi:p1": 0, "doi:p2": 0, "doi:p3": 1},
        )
        with_table = arrow_with_network(table, artifact)

        # El consumidor lee SOLO las columnas que conoce (golden, ADR 0050).
        golden_cols = [
            Col.ID,
            Col.DOI,
            Col.SOURCE_ID,
            Col.REFERENCES_ID,
            Col.REFERENCES_DOI,
            Col.TITLE,
            Col.YEAR,
            Col.ABSTRACT,
            Col.SOURCE,
            Col.CURATION_STATUS,
            Col.IS_SEED,
            Col.PROVENANCE,
            Col.AUTHORS_RAW,
            Col.AUTHORS_ID,
            Col.AUTHORS_AFFILIATIONS,
            Col.KEYWORDS_RAW,
            Col.KEYWORDS_ID,
            Col.INSTITUTIONS_RAW,
            Col.INSTITUTIONS_ID,
        ]
        # Seleccionar solo las columnas conocidas del consumidor.
        ingest_table = with_table.select(golden_cols)
        # 3 filas, todas las columnas golden presentes
        assert ingest_table.num_rows == 3
        for c in golden_cols:
            assert c in ingest_table.schema.names


# ---------------------------------------------------------------------------
# 5. corpus_hash intacto (ADR 0013 D2 / 0017 R2)
# ---------------------------------------------------------------------------


class TestCorpusHashIntacto:
    """Las columnas de red se proyectan DESPUÉS de calcular el content-hash.

    El ``corpus_hash`` del corpus vivo (lo que sella ``b2g snapshot`` y lo que
    usa ``b2g build`` para detectar staleness) NO cambia con/sin red: se
    computa sobre la tabla ``papers`` original. ``arrow_with_network`` opera
    sobre una ``pa.Table`` ya materializada y produce una tabla NUEVA con las
    columnas de red — nunca muta la entrada, así que el hash del corpus (que
    se saca del corpus, no de la tabla enriquecida) queda intacto.

    Estos tests verifican que la tabla ORIGINAL no se muta y que el hash del
    corpus — computado sobre la tabla original — es estable.
    """

    def test_tabla_original_no_se_muta(self) -> None:
        """``arrow_with_network`` no modifica la tabla de entrada (es pura)."""
        table = _3_row_corpus()
        original_names = list(table.schema.names)
        original_metadata = dict(table.schema.metadata or {})

        artifact = _build_artifact(
            nodes=["doi:p1", "doi:p2", "doi:p3"],
            edges=[("doi:p1", "doi:p2", 3), ("doi:p2", "doi:p3", 1)],
            communities={"doi:p1": 0, "doi:p2": 0, "doi:p3": 1},
        )

        _ = arrow_with_network(table, artifact)

        # La tabla original tiene exactamente las mismas columnas y metadata
        assert list(table.schema.names) == original_names
        assert dict(table.schema.metadata or {}) == original_metadata
        # Y los valores de las celdas tampoco cambian
        assert table.column("id").to_pylist() == ["doi:p1", "doi:p2", "doi:p3"]

    def test_corpus_hash_del_corpus_vivo_no_cambia(self) -> None:
        """El ``corpus_hash`` del Corpus (no de la tabla enriquecida) es estable.

        El contrato del ADR 0052 R2: el corpus se materializa vía
        ``Corpus.to_arrow()`` y ``compute_corpus_hash`` opera sobre la
        tabla ORIGINAL (la que produce el Corpus). ``arrow_with_network``
        produce una tabla NUEVA con columnas de red — esta tabla NO entra al
        cómputo del hash del corpus. Lo que se preserva: el corpus vivo
        (en el backend del ``Corpus``) tiene el MISMO ``corpus_hash`` antes
        y después de invocar ``arrow_with_network`` sobre una COPIA de su
        tabla.
        """
        from bib2graph.corpus import Corpus

        table = _3_row_corpus()
        corpus = Corpus.from_arrow(table)

        # Hash del corpus vivo (de la tabla original).
        hash_before = corpus._backend.corpus_hash()

        # Construir la tabla con-red A PARTIR de una copia de la tabla original
        # (simula lo que hace el CLI: lee to_arrow(), enriquece con la red).
        artifact = _build_artifact(
            nodes=["doi:p1", "doi:p2", "doi:p3"],
            edges=[("doi:p1", "doi:p2", 3), ("doi:p2", "doi:p3", 1)],
            communities={"doi:p1": 0, "doi:p2": 0, "doi:p3": 1},
        )
        _ = arrow_with_network(table, artifact)

        # Hash del corpus vivo sigue siendo el mismo: el corpus no fue mutado.
        hash_after = corpus._backend.corpus_hash()
        assert hash_before == hash_after

    def test_compute_corpus_hash_de_tabla_original_es_el_hash_del_corpus(self) -> None:
        """Documenta la equivalencia: ``compute_corpus_hash(to_arrow())`` ==
        ``backend.corpus_hash()``. La tabla enriquecida tiene un hash distinto
        (tiene columnas de red extras), pero ese hash NO es el del corpus vivo.
        """
        from bib2graph.corpus import Corpus

        table = _3_row_corpus()
        corpus = Corpus.from_arrow(table)
        live = corpus.to_arrow()

        # La tabla original y la que produce el Corpus son estructuralmente
        # idénticas (mismas columnas, misma metadata) -> mismo hash.
        assert compute_corpus_hash(live) == corpus._backend.corpus_hash()

    def test_compute_corpus_hash_igual_con_y_sin_red(self) -> None:
        """Regresión (Nota 05 de Atalaya, B2): el mismo corpus exportado con y
        sin red tiene el mismo ``corpus_hash`` — ``compute_corpus_hash`` excluye
        las columnas de red (ADR 0052 §Constraints / DoD).
        """
        table = _3_row_corpus()
        artifact = _build_artifact(
            nodes=["doi:p1", "doi:p2", "doi:p3"],
            edges=[("doi:p1", "doi:p2", 3), ("doi:p2", "doi:p3", 1)],
            communities={"doi:p1": 0, "doi:p2": 0, "doi:p3": 1},
        )
        with_net = arrow_with_network(table, artifact)

        assert len(with_net.schema.names) > len(table.schema.names)
        assert compute_corpus_hash(with_net) == compute_corpus_hash(table)


# ---------------------------------------------------------------------------
# 6. Validación de kind no-paper (la elección de kind la hace el CLI)
# ---------------------------------------------------------------------------


class TestNonPaperKindsRejected:
    def test_kind_no_paper_emite_value_error(self) -> None:
        """``arrow_with_network`` rechaza kinds no-papers (author_collab, etc.).

        La función exige artifact con kind de paper (coupling/cocitation) y
        lanza ``ValueError`` accionable. La responsabilidad de avisar con
        warning vs error es del CLI, no del exportador.
        """
        table = _3_row_corpus()
        g: nx.Graph = nx.Graph()
        g.add_nodes_from(["A", "B"])
        g.add_edge("A", "B", weight=1)
        spec = NetworkSpec(
            kind=NetworkKind.AUTHOR_COLLAB,  # type: ignore[arg-type]
            clustering=None,
        )
        artifact = NetworkArtifact(
            graph=g,
            metrics={},
            communities={"A": 0, "B": 0},
            assortativity=None,
            layout=None,
            spec=spec,
        )

        with pytest.raises(ValueError, match="paper"):
            arrow_with_network(table, artifact)
