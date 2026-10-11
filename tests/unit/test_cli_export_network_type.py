"""Tests TDD — ``b2g export --format arrow --network-type <kind>`` (ADR 0052, #321).

Cubre:
1. Default ``--network-type bibliographic_coupling`` con build previo -> red
   embebida en el Arrow (5 columnas + metadata).
2. Override ``--network-type cocitation`` con ``cited_by_id`` poblado -> red
   embebida (variante del caso 1).
3. Override ``--network-type cocitation`` SIN ``cited_by_id`` poblado ->
   DataError accionable (exit 2).
4. Sin ``b2g build`` previo (sin graphml en disco) -> modo degradado (D4):
   las columnas de red están AUSENTES, ``network_type`` ausente en metadata,
   warning en el envelope.
5. Kinds no-paper (``author_collab``, etc.) -> warning en envelope + sin
   columnas de red.
6. Envelope ``--json`` con los 7 campos aditivos de D5.
7. ``--format bibtex`` ignora ``--network-type`` (no se embebe red).
8. ``corpus_hash`` intacto: con/sin red, el corpus vivo tiene el mismo hash.

Marcador: ``unit`` (DuckDB en tmp_path, sin red real).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest
from click.testing import CliRunner

from bib2graph.schemas import CORPUS_SCHEMA

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers compartidos
# ---------------------------------------------------------------------------


def _row(
    id: str,
    *,
    title: str = "Paper",
    is_seed: bool = True,
    curation_status: str = "candidate",
    doi: str | None = None,
    year: int | None = 2020,
    references_id: list[str] | None = None,
    cited_by_id: list[str] | None = None,
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
        "references_id": references_id,
        "references_doi": None,
        "cited_by_id": cited_by_id,
    }


def _seed_store(store_path: Path, rows: list[dict[str, Any]]) -> None:
    from bib2graph.corpus import Corpus
    from bib2graph.stores.duckdb import DuckDBStore

    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)
    store = DuckDBStore(store_path)
    store.persist(corpus)
    store.close()


def _init_workspace(tmp_path: Path, name: str = "ws") -> Any:
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / name
    return Workspace.init(ws_dir, name)


def _rows_with_shared_refs() -> list[dict[str, Any]]:
    """3 papers con refs compartidas -> acoplamiento no vacío."""
    return [
        _row(
            "doi:p1",
            title="Seed A",
            is_seed=True,
            curation_status="accepted",
            doi="10.1/p1",
            references_id=["R1", "R2"],
        ),
        _row(
            "doi:p2",
            title="Seed B",
            is_seed=True,
            curation_status="accepted",
            doi="10.1/p2",
            references_id=["R1", "R3"],
        ),
        _row(
            "doi:p3",
            title="Seed C",
            is_seed=True,
            curation_status="accepted",
            doi="10.1/p3",
            references_id=["R2", "R4"],
        ),
    ]


def _rows_with_cited_by() -> list[dict[str, Any]]:
    """3 papers con citantes compartidos -> co-citación no vacía."""
    return [
        _row(
            "doi:p1",
            title="Cited A",
            is_seed=True,
            curation_status="accepted",
            cited_by_id=["W999", "W888"],
        ),
        _row(
            "doi:p2",
            title="Cited B",
            is_seed=True,
            curation_status="accepted",
            cited_by_id=["W999", "W777"],
        ),
        _row(
            "doi:p3",
            title="Cited C",
            is_seed=True,
            curation_status="accepted",
            cited_by_id=["W888"],
        ),
    ]


def _run_export(
    ws: Any,
    *,
    fmt: str = "arrow",
    network_type: str | None = None,
    extra_args: list[str] | None = None,
) -> Any:
    from bib2graph.cli import b2g

    args = ["--workspace", str(ws.root), "export", "--format", fmt]
    if network_type is not None:
        args.extend(["--network-type", network_type])
    if extra_args:
        args.extend(extra_args)
    args.append("--json")

    runner = CliRunner()
    return runner.invoke(b2g, args, catch_exceptions=False)


def _read_arrow(arrow_path: str | Path) -> pa.Table:
    import pyarrow.feather as feather

    return feather.read_table(str(arrow_path))


# ---------------------------------------------------------------------------
# 1. Default --network-type bibliographic_coupling con build
# ---------------------------------------------------------------------------


class TestDefaultNetworkTypeBibliographicCoupling:
    def test_default_embebe_red_acoplamiento(self, tmp_path: Path) -> None:
        """Sin --network-type explícito -> default bibliographic_coupling, red embebida."""
        from bib2graph.cli.commands.build import run_build

        ws = _init_workspace(tmp_path)
        _seed_store(ws.library_path, _rows_with_shared_refs())
        run_build(ws.library_path, out_dir=ws.networks_dir)

        result = _run_export(ws)  # sin network_type -> default
        assert result.exit_code == 0, f"Error: {result.output}"
        envelope = json.loads(result.output)
        assert envelope["ok"] is True

        data = envelope["data"]
        arrow_path = Path(data["files_written"][0])
        reread = _read_arrow(arrow_path)

        # 5 columnas de red presentes
        new_cols = {
            "community_id",
            "degree_weighted",
            "intra_community_pagerank",
            "network_edges",
            "network_communities",
        }
        assert new_cols.issubset(set(reread.schema.names))

        # Metadata del schema
        metadata = reread.schema.metadata or {}
        assert metadata.get(b"network_type") == b"bibliographic_coupling"
        assert metadata.get(b"network_type_algo") == b"louvain"
        assert b"network_resolution" in metadata
        assert metadata.get(b"network_scope") == b"full"

        # Envelope: 7 campos aditivos de D5
        assert data["network_type"] == "bibliographic_coupling"
        assert data["network_nodes"] == 3
        assert data["network_edges"] > 0
        assert data["network_communities"] >= 1
        assert data["network_type_algo"] == "louvain"
        assert data["network_resolution"] == 1.0
        assert data["network_modularity"] is not None

    def test_explicit_bibliographic_coupling_embebe_red(self, tmp_path: Path) -> None:
        """``--network-type bibliographic_coupling`` explícito: igual al default."""
        from bib2graph.cli.commands.build import run_build

        ws = _init_workspace(tmp_path)
        _seed_store(ws.library_path, _rows_with_shared_refs())
        run_build(ws.library_path, out_dir=ws.networks_dir)

        result = _run_export(ws, network_type="bibliographic_coupling")
        assert result.exit_code == 0
        data = json.loads(result.output)["data"]
        assert data["network_type"] == "bibliographic_coupling"


# ---------------------------------------------------------------------------
# 2. Override --network-type cocitation con cited_by_id poblado
# ---------------------------------------------------------------------------


class TestNetworkTypeCocitation:
    def test_cocitation_con_cited_by_embebe_red(self, tmp_path: Path) -> None:
        """``--network-type cocitation`` con citantes poblados -> red embebida."""
        from bib2graph.cli.commands.build import run_build

        ws = _init_workspace(tmp_path)
        _seed_store(ws.library_path, _rows_with_cited_by())
        run_build(ws.library_path, out_dir=ws.networks_dir)

        result = _run_export(ws, network_type="cocitation")
        assert result.exit_code == 0, f"Error: {result.output}"
        data = json.loads(result.output)["data"]
        assert data["network_type"] == "cocitation"

        arrow_path = Path(data["files_written"][0])
        reread = _read_arrow(arrow_path)
        metadata = reread.schema.metadata or {}
        assert metadata.get(b"network_type") == b"cocitation"

    def test_cocitation_sin_cited_by_error_acionable(self, tmp_path: Path) -> None:
        """``--network-type cocitation`` sin citantes -> DataError (exit 2)."""
        from bib2graph.cli.commands.build import run_build

        ws = _init_workspace(tmp_path)
        # Papers SIN cited_by_id
        _seed_store(ws.library_path, _rows_with_shared_refs())
        run_build(ws.library_path, out_dir=ws.networks_dir)

        result = _run_export(ws, network_type="cocitation")
        assert result.exit_code == 2, f"Esperaba exit 2, obtuve {result.exit_code}"
        envelope = json.loads(result.output)
        assert envelope["ok"] is False
        assert envelope["error"]["code"] == "DATA_ERROR"
        assert "cocitation" in envelope["error"]["message"].lower()
        assert "cited_by_id" in envelope["error"]["message"].lower()


# ---------------------------------------------------------------------------
# 3. Modo degradado (sin b2g build previo)
# ---------------------------------------------------------------------------


class TestDegradedModeNoBuild:
    def test_sin_build_modo_degradado_con_warning(self, tmp_path: Path) -> None:
        """Sin ``b2g build`` previo -> Arrow sin columnas de red + warning."""
        ws = _init_workspace(tmp_path)
        _seed_store(ws.library_path, _rows_with_shared_refs())

        result = _run_export(ws, network_type="bibliographic_coupling")
        assert result.exit_code == 0, f"Error: {result.output}"
        envelope = json.loads(result.output)
        assert envelope["ok"] is True

        # Warning presente
        warnings_list = envelope.get("warnings") or []
        assert any(
            "no network computed" in w or "b2g build" in w for w in warnings_list
        )

        # data.network_* = 0/null (modo degradado)
        data = envelope["data"]
        assert data["network_type"] is None
        assert data["network_nodes"] == 0
        assert data["network_edges"] == 0
        assert data["network_communities"] == 0
        assert data["network_modularity"] is None

        # Arrow sin columnas de red (D4: ausentes, no null/no vacías)
        arrow_path = Path(data["files_written"][0])
        reread = _read_arrow(arrow_path)
        new_cols = {
            "community_id",
            "degree_weighted",
            "intra_community_pagerank",
            "network_edges",
            "network_communities",
        }
        assert not new_cols.intersection(set(reread.schema.names))
        # Sin metadata de network_type
        metadata = reread.schema.metadata or {}
        assert b"network_type" not in metadata


# ---------------------------------------------------------------------------
# 4. Kinds no-paper (warning + sin red)
# ---------------------------------------------------------------------------


class TestNonPaperKinds:
    def test_author_collab_warning_sin_red(self, tmp_path: Path) -> None:
        """``--network-type author_collab`` -> warning + sin columnas de red."""
        from bib2graph.cli.commands.build import run_build

        ws = _init_workspace(tmp_path)
        _seed_store(ws.library_path, _rows_with_shared_refs())
        run_build(ws.library_path, out_dir=ws.networks_dir)

        result = _run_export(ws, network_type="author_collab")
        assert result.exit_code == 0
        envelope = json.loads(result.output)
        assert envelope["ok"] is True

        # Warning presente
        warnings_list = envelope.get("warnings") or []
        assert any(
            "author_collab" in w and "not supported" in w.lower() for w in warnings_list
        )

        data = envelope["data"]
        # network_type=null en el envelope (no se embebe)
        assert data["network_type"] is None

        # Arrow sin columnas de red
        arrow_path = Path(data["files_written"][0])
        reread = _read_arrow(arrow_path)
        assert "community_id" not in reread.schema.names

    def test_keyword_cooccurrence_warning_sin_red(self, tmp_path: Path) -> None:
        """``--network-type keyword_cooccurrence`` -> warning + sin red."""
        from bib2graph.cli.commands.build import run_build

        ws = _init_workspace(tmp_path)
        _seed_store(ws.library_path, _rows_with_shared_refs())
        run_build(ws.library_path, out_dir=ws.networks_dir)

        result = _run_export(ws, network_type="keyword_cooccurrence")
        assert result.exit_code == 0
        envelope = json.loads(result.output)
        warnings_list = envelope.get("warnings") or []
        assert any("keyword_cooccurrence" in w for w in warnings_list)


# ---------------------------------------------------------------------------
# 5. bibtex no se ve afectado por --network-type
# ---------------------------------------------------------------------------


class TestBibtexIgnoraNetworkType:
    def test_bibtex_con_network_type_no_falla(self, tmp_path: Path) -> None:
        """``--format bibtex --network-type <kind>`` no rompe: la red no aplica."""
        pytest.importorskip("bibtexparser")
        from bib2graph.cli.commands.build import run_build

        ws = _init_workspace(tmp_path)
        _seed_store(ws.library_path, _rows_with_shared_refs())
        run_build(ws.library_path, out_dir=ws.networks_dir)

        result = _run_export(ws, fmt="bibtex", network_type="bibliographic_coupling")
        assert result.exit_code == 0, f"Error: {result.output}"
        envelope = json.loads(result.output)
        assert envelope["ok"] is True
        # Sin campos de network_* (bibtex no los emite)
        data = envelope["data"]
        assert "network_type" not in data or data.get("network_type") is None


# ---------------------------------------------------------------------------
# 6. Envelope --json: 7 campos aditivos del ADR 0052 D5
# ---------------------------------------------------------------------------


class TestEnvelopeD5:
    def test_envelope_todos_los_campos_d5_con_red(self, tmp_path: Path) -> None:
        """Los 7 campos de D5 están presentes y con valores no triviales."""
        from bib2graph.cli.commands.build import run_build

        ws = _init_workspace(tmp_path)
        _seed_store(ws.library_path, _rows_with_shared_refs())
        run_build(ws.library_path, out_dir=ws.networks_dir)

        result = _run_export(ws, network_type="bibliographic_coupling")
        assert result.exit_code == 0
        data = json.loads(result.output)["data"]

        # 7 campos de D5
        assert "network_type" in data
        assert "network_nodes" in data
        assert "network_edges" in data
        assert "network_communities" in data
        assert "network_modularity" in data
        assert "network_type_algo" in data
        assert "network_resolution" in data

    def test_envelope_campos_d5_en_modo_degradado(self, tmp_path: Path) -> None:
        """Modo degradado: los 7 campos están con valores neutros (no faltan)."""
        ws = _init_workspace(tmp_path)
        _seed_store(ws.library_path, _rows_with_shared_refs())

        result = _run_export(ws, network_type="bibliographic_coupling")
        assert result.exit_code == 0
        data = json.loads(result.output)["data"]

        assert data["network_type"] is None
        assert data["network_nodes"] == 0
        assert data["network_edges"] == 0
        assert data["network_communities"] == 0
        assert data["network_modularity"] is None
        assert data["network_type_algo"] is None
        assert data["network_resolution"] is None

    def test_envelope_schema_no_cambia(self, tmp_path: Path) -> None:
        """``schema="1"`` intacto (no rompe el contrato del envelope)."""
        from bib2graph.cli.commands.build import run_build

        ws = _init_workspace(tmp_path)
        _seed_store(ws.library_path, _rows_with_shared_refs())
        run_build(ws.library_path, out_dir=ws.networks_dir)

        result = _run_export(ws, network_type="bibliographic_coupling")
        envelope = json.loads(result.output)
        assert envelope["schema"] == "1"
        # Las 7 claves son aditivos sobre ``data``, no sobre ``schema``
        assert "network_type" not in envelope  # top-level: NO


# ---------------------------------------------------------------------------
# 7. corpus_hash intacto con/sin red
# ---------------------------------------------------------------------------


class TestCorpusHashIntactoCLI:
    def test_corpus_hash_mismo_con_y_sin_network_type(self, tmp_path: Path) -> None:
        """El corpus vivo tiene el MISMO ``corpus_hash`` con/sin ``--network-type``.

        ``b2g export`` no muta el corpus vivo; embeber la red es una proyección
        sobre una copia de la tabla del corpus, no un cambio al backend.
        """
        from bib2graph.cli.commands.build import run_build
        from bib2graph.stores.duckdb import DuckDBStore

        ws = _init_workspace(tmp_path)
        _seed_store(ws.library_path, _rows_with_shared_refs())
        run_build(ws.library_path, out_dir=ws.networks_dir)

        # Hash del corpus antes del export
        store = DuckDBStore(ws.library_path)
        corpus_before = store.load()
        hash_before = corpus_before._backend.corpus_hash()
        store.close()

        # Export CON red
        result = _run_export(ws, network_type="bibliographic_coupling")
        assert result.exit_code == 0

        # Hash del corpus después del export
        store = DuckDBStore(ws.library_path)
        corpus_after = store.load()
        hash_after = corpus_after._backend.corpus_hash()
        store.close()

        assert hash_before == hash_after
