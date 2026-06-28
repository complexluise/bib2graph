"""Tests TDD — bloque ``maturity`` en build/snapshot/read top (#160).

Cubre:
1. ``compute_maturity`` (helper puro):
   a. ``curated=False`` cuando todo es candidate/seed.
   b. ``curated=True`` con ≥1 accepted.
   c. ``curated=True`` con ≥1 rejected.
   d. ``saturated`` siempre False.
   e. ``scope`` y ``empty_networks`` pasan literalmente.
   f. Key-set consistente (4 claves exactas).

2. ``build`` — ``maturity`` en data:
   a. Presente en el path normal (corpus no vacío).
   b. Presente en el early-return (corpus vacío tras scope).
   c. ``empty_networks`` de maturity = kinds del data["empty_networks"].
   d. ``schema="1"`` intacto.

3. ``snapshot`` — ``maturity`` en data:
   a. Presente, scope="all", empty_networks=[].
   b. ``schema="1"`` intacto.

4. ``read top`` — ``maturity`` en result:
   a. Presente con corpus bib-coupling (co-cit vacía → maturity.empty_networks=["cocitation"]).
   b. Presente con corpus co-citación (no vacía → maturity.empty_networks=[]).
   c. Forma consistente (4 claves).

5. Negativos — maturity AUSENTE en read list/stats/show.

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
    is_seed: bool = True,
    curation_status: str = "candidate",
    references_id: list[str] | None = None,
    cited_by_id: list[str] | None = None,
    keywords_id: list[str] | None = None,
) -> dict[str, Any]:
    """Fila mínima con schema canónico completo."""
    return {
        "id": id,
        "source_id": None,
        "doi": None,
        "title": f"Paper {id}",
        "year": 2020,
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
        "keywords_id": keywords_id,
        "institutions_raw": None,
        "institutions_id": None,
        "references_id": references_id,
        "references_doi": None,
        "cited_by_id": cited_by_id,
    }


def _make_corpus(*rows: dict[str, Any]):  # type: ignore[no-untyped-def]
    """Construye un Corpus en memoria desde filas dict."""
    from bib2graph.corpus import Corpus

    table = pa.Table.from_pylist(list(rows), schema=CORPUS_SCHEMA)
    return Corpus.from_arrow(table)


def _seed_store(store_path: Path, rows: list[dict[str, Any]]) -> None:
    """Persiste filas en un DuckDB temporal."""
    from bib2graph.corpus import Corpus
    from bib2graph.stores.duckdb import DuckDBStore

    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)
    store = DuckDBStore(store_path)
    store.persist(corpus)
    store.close()


def _init_workspace(tmp_path: Path, name: str = "test-ws") -> Any:
    """Crea y devuelve un Workspace inicializado en tmp_path."""
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / name
    return Workspace.init(ws_dir, name)


def _seed_workspace(ws: Any, rows: list[dict[str, Any]]) -> None:
    """Persiste filas en el store del workspace."""
    _seed_store(ws.library_path, rows)


def _rows_bib_coupling() -> list[dict[str, Any]]:
    """3 papers con referencias compartidas (coupling); sin cited_by_id → coc vacía."""
    return [
        _row("P1", references_id=["R1", "R2", "R3"]),
        _row("P2", references_id=["R1", "R3"]),
        _row("P3", references_id=["R2"]),
    ]


def _rows_cocitation() -> list[dict[str, Any]]:
    """3 papers con cited_by_id → co-citación no vacía."""
    return [
        _row("P1", is_seed=True, cited_by_id=["C1", "C2"]),
        _row("P2", is_seed=True, cited_by_id=["C1", "C3"]),
        _row("P3", is_seed=True, cited_by_id=["C4"]),
    ]


def _assert_maturity_shape(mat: dict[str, Any]) -> None:
    """Verifica que el bloque maturity tenga exactamente las 4 claves esperadas."""
    assert set(mat.keys()) == {
        "curated",
        "scope",
        "saturated",
        "empty_networks",
    }, f"Claves de maturity incorrectas: {set(mat.keys())}"
    assert isinstance(mat["curated"], bool), "curated debe ser bool"
    assert isinstance(mat["saturated"], bool), "saturated debe ser bool"
    assert isinstance(mat["empty_networks"], list), "empty_networks debe ser list"


# ---------------------------------------------------------------------------
# 1. compute_maturity — helper puro
# ---------------------------------------------------------------------------


class TestComputeMaturity:
    """Tests unitarios de la función pura compute_maturity."""

    def test_curated_false_todo_candidate(self) -> None:
        """corpus con solo candidates → curated=False."""
        from bib2graph.service.maturity import compute_maturity

        corpus = _make_corpus(
            _row("P1", curation_status="candidate"),
            _row("P2", curation_status="candidate"),
        )
        mat = compute_maturity(corpus, scope="all", empty_network_kinds=[])
        assert mat["curated"] is False

    def test_curated_false_solo_seeds_candidate(self) -> None:
        """corpus con seeds (is_seed=True) pero curation_status='candidate' → curated=False."""
        from bib2graph.service.maturity import compute_maturity

        corpus = _make_corpus(
            _row("P1", is_seed=True, curation_status="candidate"),
            _row("P2", is_seed=True, curation_status="candidate"),
        )
        mat = compute_maturity(corpus, scope="all", empty_network_kinds=[])
        assert mat["curated"] is False

    def test_curated_true_con_accepted(self) -> None:
        """corpus con ≥1 accepted → curated=True."""
        from bib2graph.service.maturity import compute_maturity

        corpus = _make_corpus(
            _row("P1", curation_status="candidate"),
            _row("P2", curation_status="accepted"),
        )
        mat = compute_maturity(corpus, scope="all", empty_network_kinds=[])
        assert mat["curated"] is True

    def test_curated_true_con_rejected(self) -> None:
        """corpus con ≥1 rejected → curated=True."""
        from bib2graph.service.maturity import compute_maturity

        corpus = _make_corpus(
            _row("P1", curation_status="candidate"),
            _row("P2", curation_status="rejected"),
        )
        mat = compute_maturity(corpus, scope="all", empty_network_kinds=[])
        assert mat["curated"] is True

    def test_curated_true_con_accepted_y_rejected(self) -> None:
        """corpus con accepted y rejected → curated=True."""
        from bib2graph.service.maturity import compute_maturity

        corpus = _make_corpus(
            _row("P1", curation_status="accepted"),
            _row("P2", curation_status="rejected"),
        )
        mat = compute_maturity(corpus, scope="all", empty_network_kinds=[])
        assert mat["curated"] is True

    def test_saturated_siempre_false(self) -> None:
        """saturated siempre es False, independientemente del corpus."""
        from bib2graph.service.maturity import compute_maturity

        corpus_curado = _make_corpus(_row("P1", curation_status="accepted"))
        corpus_puro = _make_corpus(_row("P2", curation_status="candidate"))

        mat_curado = compute_maturity(
            corpus_curado, scope="all", empty_network_kinds=[]
        )
        mat_puro = compute_maturity(corpus_puro, scope="all", empty_network_kinds=[])

        assert mat_curado["saturated"] is False
        assert mat_puro["saturated"] is False

    def test_scope_se_pasa_literalmente(self) -> None:
        """scope se propaga tal cual al bloque maturity."""
        from bib2graph.service.maturity import compute_maturity

        corpus = _make_corpus(_row("P1"))

        for token in ("all", "seeds", "accepted", None):
            mat = compute_maturity(corpus, scope=token, empty_network_kinds=[])
            assert mat["scope"] == token, (
                f"scope esperado {token!r}, got {mat['scope']!r}"
            )

    def test_empty_network_kinds_se_pasan_literalmente(self) -> None:
        """empty_network_kinds se propaga literalmente."""
        from bib2graph.service.maturity import compute_maturity

        corpus = _make_corpus(_row("P1"))

        mat_vacia = compute_maturity(corpus, scope="all", empty_network_kinds=[])
        assert mat_vacia["empty_networks"] == []

        mat_con_kinds = compute_maturity(
            corpus,
            scope="all",
            empty_network_kinds=["cocitation", "keyword_cooccurrence"],
        )
        assert mat_con_kinds["empty_networks"] == ["cocitation", "keyword_cooccurrence"]

    def test_keyset_consistente_4_claves(self) -> None:
        """El bloque maturity tiene exactamente 4 claves (nunca más, nunca menos)."""
        from bib2graph.service.maturity import compute_maturity

        corpus = _make_corpus(_row("P1", curation_status="accepted"))
        mat = compute_maturity(corpus, scope="all", empty_network_kinds=["cocitation"])
        _assert_maturity_shape(mat)


# ---------------------------------------------------------------------------
# 2. build — maturity en data
# ---------------------------------------------------------------------------


class TestBuildMaturity:
    """``run_build`` incluye ``maturity`` en el dict devuelto."""

    def test_maturity_presente_en_build_normal(self, tmp_path: Path) -> None:
        """run_build con corpus no vacío incluye data['maturity']."""
        from bib2graph.cli.commands.build import run_build

        store_path = tmp_path / "lib.duckdb"
        _seed_store(store_path, _rows_bib_coupling())

        data = run_build(store_path, out_dir=tmp_path / "nets")

        assert "maturity" in data, "data debe tener clave 'maturity'"
        _assert_maturity_shape(data["maturity"])

    # Semántica curated=False/True eliminada aquí (epic #184):
    # la invariante vive en TestComputeMaturity::test_curated_false_todo_candidate
    # y test_curated_true_con_accepted; este archivo solo verifica presencia y forma.

    def test_maturity_scope_coincide_con_data_scope(self, tmp_path: Path) -> None:
        """maturity.scope coincide con data['scope']."""
        from bib2graph.cli.commands.build import run_build

        store_path = tmp_path / "lib.duckdb"
        _seed_store(store_path, _rows_bib_coupling())

        data = run_build(
            store_path,
            out_dir=tmp_path / "nets",
            scope_cli_token="seeds",
            corpus_scope="seeds_only",
        )

        assert data["maturity"]["scope"] == data["scope"] == "seeds"

    def test_maturity_empty_networks_kinds_de_data_empty_networks(
        self, tmp_path: Path
    ) -> None:
        """maturity.empty_networks son solo los kinds (sin reason/fix_command duplicados)."""
        from bib2graph.cli.commands.build import run_build

        store_path = tmp_path / "lib.duckdb"
        # Sin keywords_id → keyword_cooccurrence vacía
        rows = [_row(f"P{i}", references_id=[f"R{i}", "RSHARED"]) for i in range(3)]
        _seed_store(store_path, rows)

        data = run_build(store_path, out_dir=tmp_path / "nets")

        empty_kinds_in_data = [en["kind"] for en in data["empty_networks"]]
        maturity_empty = data["maturity"]["empty_networks"]

        # Los kinds de maturity.empty_networks deben coincidir con data["empty_networks"]
        assert set(maturity_empty) == set(empty_kinds_in_data), (
            f"maturity.empty_networks {maturity_empty!r} != "
            f"data.empty_networks kinds {empty_kinds_in_data!r}"
        )

        # Maturity SOLO tiene los kinds (no reason ni fix_command)
        for item in maturity_empty:
            assert isinstance(item, str), (
                f"maturity.empty_networks debe contener strings, no dicts: {item!r}"
            )

    # Semántica saturated=False eliminada aquí (epic #184):
    # la invariante vive en TestComputeMaturity::test_saturated_siempre_false.

    def test_maturity_presente_en_early_return_corpus_vacio(
        self, tmp_path: Path
    ) -> None:
        """Early-return (scope deja 0 papers) también incluye maturity."""
        from bib2graph.cli.commands.build import run_build

        store_path = tmp_path / "lib.duckdb"
        # Solo seeds; scope=accepted → corpus_filtrado vacío si ningún accepted
        _seed_store(
            store_path,
            [_row("P1", is_seed=True, curation_status="candidate")],
        )

        run_build(
            store_path,
            out_dir=tmp_path / "nets",
            corpus_scope="accepted",
        )

        # Early-return: corpus_scope='accepted' deja 0 papers (P1 es seed pero candidate,
        # el scope 'accepted' incluye is_seed=True → P1 SÍ entra.
        # Probamos con corpus_scope='seeds_only' y corpus sin seeds:
        store_path2 = tmp_path / "lib2.duckdb"
        _seed_store(
            store_path2,
            [_row("C1", is_seed=False, curation_status="candidate")],
        )
        data2 = run_build(
            store_path2,
            out_dir=tmp_path / "nets2",
            corpus_scope="seeds_only",
        )

        assert "maturity" in data2, "Early-return debe incluir 'maturity'"
        _assert_maturity_shape(data2["maturity"])
        assert data2["maturity"]["saturated"] is False

    def test_build_schema_1_intacto_con_maturity(self, tmp_path: Path) -> None:
        """build --json: schema='1' intacto después de agregar maturity."""
        from bib2graph.workspace import Workspace

        ws_dir = tmp_path / "ws"
        ws = Workspace.init(ws_dir, "test")
        _seed_workspace(ws, _rows_bib_coupling())

        from bib2graph.cli import b2g

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            ["--workspace", str(ws_dir), "build", "--json"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, f"Error: {result.output}"
        envelope = json.loads(result.output)
        assert envelope["schema"] == "1"
        assert envelope["ok"] is True
        assert "maturity" in envelope["data"]

    def test_build_json_maturity_no_tiene_reason_fix_command(
        self, tmp_path: Path
    ) -> None:
        """maturity en --json NO duplica reason/fix_command de empty_networks."""
        from bib2graph.workspace import Workspace

        ws_dir = tmp_path / "ws"
        ws = Workspace.init(ws_dir, "test")
        # Sin keywords_id → keyword_cooccurrence vacía
        rows = [_row(f"P{i}", references_id=[f"R{i}", "RS"]) for i in range(3)]
        _seed_workspace(ws, rows)

        from bib2graph.cli import b2g

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            ["--workspace", str(ws_dir), "build", "--json"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        envelope = json.loads(result.output)
        mat = envelope["data"]["maturity"]

        # maturity.empty_networks son strings (kinds), no dicts
        for item in mat["empty_networks"]:
            assert isinstance(item, str), (
                f"maturity.empty_networks deben ser strings: {item!r}"
            )


# ---------------------------------------------------------------------------
# 3. snapshot — maturity en data
# ---------------------------------------------------------------------------


class TestSnapshotMaturity:
    """``run_snapshot`` incluye ``maturity`` en el dict devuelto."""

    def test_maturity_presente_en_snapshot(self, tmp_path: Path) -> None:
        """run_snapshot incluye data['maturity']."""
        from bib2graph.cli.commands.snapshot import run_snapshot

        store_path = tmp_path / "lib.duckdb"
        _seed_store(store_path, _rows_bib_coupling())

        snap_dir = tmp_path / "snapshots"
        data = run_snapshot(store_path, out_dir=snap_dir)

        assert "maturity" in data, "data debe tener clave 'maturity'"
        _assert_maturity_shape(data["maturity"])

    def test_snapshot_maturity_scope_all(self, tmp_path: Path) -> None:
        """snapshot: maturity.scope='all' (exporta completo)."""
        from bib2graph.cli.commands.snapshot import run_snapshot

        store_path = tmp_path / "lib.duckdb"
        _seed_store(store_path, _rows_bib_coupling())

        data = run_snapshot(store_path, out_dir=tmp_path / "snaps")

        assert data["maturity"]["scope"] == "all"

    def test_snapshot_maturity_empty_networks_vacia(self, tmp_path: Path) -> None:
        """snapshot: maturity.empty_networks=[] (snapshot no sabe de redes)."""
        from bib2graph.cli.commands.snapshot import run_snapshot

        store_path = tmp_path / "lib.duckdb"
        _seed_store(store_path, _rows_bib_coupling())

        data = run_snapshot(store_path, out_dir=tmp_path / "snaps")

        assert data["maturity"]["empty_networks"] == []

    # Semántica curated=False/True y saturated=False eliminada aquí (epic #184):
    # las invariantes viven en TestComputeMaturity; aquí solo se verifica wiring.

    def test_snapshot_schema_1_intacto(self, tmp_path: Path) -> None:
        """snapshot --json: schema='1' intacto después de agregar maturity."""
        from bib2graph.workspace import Workspace

        ws_dir = tmp_path / "ws"
        ws = Workspace.init(ws_dir, "test")
        _seed_workspace(ws, _rows_bib_coupling())

        from bib2graph.cli import b2g

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            ["--workspace", str(ws_dir), "snapshot", "create", "--json"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, f"Error: {result.output}"
        envelope = json.loads(result.output)
        assert envelope["schema"] == "1"
        assert envelope["ok"] is True
        assert "maturity" in envelope["data"]


# ---------------------------------------------------------------------------
# 4. read top — maturity en result
# ---------------------------------------------------------------------------


class TestReadTopMaturity:
    """``get_top`` incluye ``maturity`` en el result."""

    def test_maturity_presente_en_get_top(self, tmp_path: Path) -> None:
        """get_top incluye result['maturity']."""
        from bib2graph.service.reads import get_top

        ws = _init_workspace(tmp_path)
        _seed_workspace(ws, _rows_bib_coupling())

        result = get_top(ws, n=3, kind="bibliographic_coupling")

        assert "maturity" in result, "result debe tener clave 'maturity'"
        _assert_maturity_shape(result["maturity"])

    def test_read_top_maturity_scope_all(self, tmp_path: Path) -> None:
        """read top: maturity.scope='all'."""
        from bib2graph.service.reads import get_top

        ws = _init_workspace(tmp_path)
        _seed_workspace(ws, _rows_bib_coupling())

        result = get_top(ws, n=3, kind="bibliographic_coupling")

        assert result["maturity"]["scope"] == "all"

    def test_read_top_maturity_cocitacion_vacia_en_empty_networks(
        self, tmp_path: Path
    ) -> None:
        """read top con co-citación vacía → maturity.empty_networks=['cocitation']."""
        from bib2graph.service.reads import get_top

        ws = _init_workspace(tmp_path)
        _seed_workspace(ws, _rows_bib_coupling())  # sin cited_by_id → coc vacía

        result = get_top(ws, n=3, kind="bibliographic_coupling")

        assert result["maturity"]["empty_networks"] == ["cocitation"], (
            f"Expected ['cocitation'], got {result['maturity']['empty_networks']!r}"
        )

    def test_read_top_maturity_cocitacion_llena_empty_networks_vacia(
        self, tmp_path: Path
    ) -> None:
        """read top con co-citación no vacía → maturity.empty_networks=[]."""
        from bib2graph.service.reads import get_top

        ws = _init_workspace(tmp_path)
        _seed_workspace(ws, _rows_cocitation())

        result = get_top(ws, n=5, kind="cocitation")

        assert result["maturity"]["empty_networks"] == []

    # Semántica curated=False/True y saturated=False eliminada aquí (epic #184):
    # las invariantes viven en TestComputeMaturity; aquí solo se verifica wiring.

    def test_read_top_schema_1_intacto_con_maturity(self, tmp_path: Path) -> None:
        """read top --json: schema='1' intacto después de agregar maturity."""
        from bib2graph.workspace import Workspace

        ws_dir = tmp_path / "ws"
        ws = Workspace.init(ws_dir, "test")
        _seed_workspace(ws, _rows_bib_coupling())

        from bib2graph.cli import b2g

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            ["--workspace", str(ws_dir), "read", "top", "--json"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, f"Error: {result.output}"
        envelope = json.loads(result.output)
        assert envelope["schema"] == "1"
        assert envelope["ok"] is True
        assert "maturity" in envelope["data"]


# ---------------------------------------------------------------------------
# 5. Negativos — maturity AUSENTE en read list/stats/show
# ---------------------------------------------------------------------------


class TestMaturityAusenteEnOtrasLecturas:
    """maturity solo aparece en build/snapshot/read top, NO en list/stats/show."""

    def test_maturity_ausente_en_list_papers(self, tmp_path: Path) -> None:
        """list_papers NO incluye 'maturity' (es plomería, no presentación)."""
        from bib2graph.service.reads import list_papers

        ws = _init_workspace(tmp_path)
        _seed_workspace(ws, _rows_bib_coupling())

        result = list_papers(ws)

        assert "maturity" not in result, (
            "list_papers NO debe tener 'maturity'; es solo para build/snapshot/read top"
        )

    def test_maturity_ausente_en_corpus_stats(self, tmp_path: Path) -> None:
        """corpus_stats NO incluye 'maturity'."""
        from bib2graph.service.reads import corpus_stats

        ws = _init_workspace(tmp_path)
        _seed_workspace(ws, _rows_bib_coupling())

        result = corpus_stats(ws)

        assert "maturity" not in result, "corpus_stats NO debe tener 'maturity'"

    def test_maturity_ausente_en_get_paper(self, tmp_path: Path) -> None:
        """get_paper NO incluye 'maturity'."""
        from bib2graph.service.reads import get_paper

        ws = _init_workspace(tmp_path)
        _seed_workspace(ws, _rows_bib_coupling())

        result = get_paper(ws, "P1")

        assert "maturity" not in result, "get_paper NO debe tener 'maturity'"
