"""Tests TDD para ``b2g snapshot`` como grupo noun-verb (ADR 0038, #163).

Casos cubiertos:

1.  ``snapshot create`` crea snapshot (= comportamiento del ex plano).
2.  ``snapshot create`` envelope correcto: ``command == "snapshot create"``.
3.  ``snapshot restore`` mergea+dedup y transiciona a FILTERED.
4.  ``snapshot restore`` envelope correcto: ``command == "snapshot restore"``.
5.  ``snapshot`` sin subcomando → help + exit 0 (NO envelope de error).
6.  ``restore`` suelto (shim) sigue funcionando idéntico (delega al servicio).
7.  ``restore`` suelto: ``command == "restore"`` (compat backward).
8.  Reloj inyectado: ``run_restore`` en service acepta ``decided_at`` param.
9.  ``run_snapshot`` importable desde ``cli.commands.snapshot`` (backward compat).
10. ``run_restore`` importable desde ``cli.commands.restore`` (backward compat).
11. Stdout puro (#151): en modo JSON, stdout == exactamente 1 línea.

Filosofía (AGENTS.md): se testea la FUNCIÓN detrás del comando cuando es
posible; CliRunner solo donde hay integración necesaria.
Marcador: ``unit`` (DuckDB en tmp_path, sin red real).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest

from bib2graph.schemas import CORPUS_SCHEMA

# ---------------------------------------------------------------------------
# Helpers comunes
# ---------------------------------------------------------------------------


def _make_corpus_row(
    *,
    id: str,
    title: str = "Test",
    curation_status: str = "candidate",
    is_seed: bool = True,
    year: int = 2020,
) -> dict[str, Any]:
    """Fila mínima con schema completo."""
    return {
        "id": id,
        "openalex_id": None,
        "doi": None,
        "title": title,
        "year": year,
        "abstract": None,
        "source": None,
        "language": "en",
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


def _make_parquet(path: Path, rows: list[dict[str, Any]] | None = None) -> Path:
    """Escribe un parquet con el schema canónico en ``path``."""
    import pyarrow.parquet as pq

    if rows is None:
        rows = [
            _make_corpus_row(id="P1"),
            _make_corpus_row(id="P2"),
            _make_corpus_row(id="P3", curation_status="accepted"),
        ]
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    pq.write_table(table, str(path))
    return path


def _seed_store(store_path: Path, rows: list[dict[str, Any]] | None = None) -> None:
    """Puebla un store con filas mínimas."""
    from bib2graph.corpus import Corpus
    from bib2graph.stores.duckdb import DuckDBStore

    if rows is None:
        rows = [_make_corpus_row(id="P1"), _make_corpus_row(id="P2")]
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)
    store = DuckDBStore(store_path)
    store.persist(corpus)


# ---------------------------------------------------------------------------
# 1. snapshot create crea snapshot
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_snapshot_create_crea_archivos(tmp_path: Path) -> None:
    """``b2g snapshot create`` (vía run_snapshot) crea parquet + manifest.json."""
    from bib2graph.service.snapshot import run_snapshot

    store_path = tmp_path / "test.duckdb"
    _seed_store(store_path)
    out_dir = tmp_path / "snap"

    data = run_snapshot(store_path, out_dir=out_dir)

    assert "snapshot_dir" in data
    assert "corpus_hash" in data
    assert "total_papers" in data
    assert (out_dir / "corpus.parquet").exists()
    assert (out_dir / "manifest.json").exists()
    assert data["total_papers"] == 2


# ---------------------------------------------------------------------------
# 2. snapshot create envelope: command == "snapshot create"
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_snapshot_create_envelope_command(tmp_path: Path) -> None:
    """``b2g snapshot create --json`` emite envelope con ``command=="snapshot create"``."""
    from click.testing import CliRunner

    from bib2graph.cli import b2g
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / "ws"
    ws = Workspace.init(ws_dir, "test")
    _seed_store(ws.library_path)

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        ["--workspace", str(ws_dir), "snapshot", "create", "--json"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, f"Salida inesperada:\n{result.output}"
    lines = [ln for ln in result.output.splitlines() if ln.strip()]
    assert len(lines) == 1, f"stdout debe ser 1 línea, fue: {result.output!r}"
    envelope = json.loads(lines[0])
    assert envelope["schema"] == "1"
    assert envelope["ok"] is True
    assert envelope["command"] == "snapshot create"
    assert "snapshot_dir" in envelope["data"]


# ---------------------------------------------------------------------------
# 3. snapshot restore mergea+dedup y transiciona a FILTERED
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_snapshot_restore_transiciona_a_filtered(tmp_path: Path) -> None:
    """``snapshot restore`` (service) transiciona a FILTERED y mergea corpus."""
    from bib2graph.cycle import CycleState
    from bib2graph.service.snapshot import run_restore
    from bib2graph.stores.duckdb import DuckDBStore

    parquet_path = _make_parquet(tmp_path / "corpus.parquet")
    store_path = tmp_path / "test.duckdb"

    data = run_restore(store_path, parquet_path)

    assert data["state"] == str(CycleState.FILTERED)
    assert data["papers_loaded"] == 3

    store = DuckDBStore(store_path)
    assert store.backend.loop_state() == CycleState.FILTERED


# ---------------------------------------------------------------------------
# 4. snapshot restore envelope: command == "snapshot restore"
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_snapshot_restore_envelope_command(tmp_path: Path) -> None:
    """``b2g snapshot restore --json`` emite envelope con ``command=="snapshot restore"``."""
    from click.testing import CliRunner

    from bib2graph.cli import b2g
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / "ws"
    Workspace.init(ws_dir, "test")
    parquet_path = _make_parquet(tmp_path / "corpus.parquet")

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws_dir),
            "snapshot",
            "restore",
            "--from-corpus",
            str(parquet_path),
            "--json",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, f"Salida inesperada:\n{result.output}"
    lines = [ln for ln in result.output.splitlines() if ln.strip()]
    assert len(lines) == 1, f"stdout debe ser 1 línea, fue: {result.output!r}"
    envelope = json.loads(lines[0])
    assert envelope["schema"] == "1"
    assert envelope["ok"] is True
    assert envelope["command"] == "snapshot restore"
    assert envelope["data"]["state"] == "FILTERED"


# ---------------------------------------------------------------------------
# 5. snapshot sin subcomando → help + exit 0 (NO envelope de error)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_snapshot_sin_subcomando_exit_0(tmp_path: Path) -> None:
    """``b2g snapshot`` sin subcomando imprime ayuda y sale con exit 0."""
    from click.testing import CliRunner

    from bib2graph.cli import b2g

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(b2g, ["snapshot"], catch_exceptions=False)

    # exit 0 (no error, solo ayuda)
    assert result.exit_code == 0, f"Se esperaba exit 0, fue {result.exit_code}"
    # La salida contiene texto de ayuda
    assert "snapshot" in result.output.lower()
    # NO debe ser una línea JSON de error
    assert not result.output.strip().startswith("{")


@pytest.mark.unit
def test_snapshot_sin_subcomando_stdout_no_envelope(tmp_path: Path) -> None:
    """``b2g snapshot`` sin subcomando muestra ayuda y no emite envelope JSON.

    ``--json`` es una opción post-verbo de los subcomandos (create/restore),
    no del grupo snapshot en sí.  El grupo invocado sin subcomando muestra
    ayuda y sale con exit 0 — no emite ningún envelope JSON de error.
    """
    from click.testing import CliRunner

    from bib2graph.cli import b2g

    runner = CliRunner()
    with runner.isolated_filesystem():
        # Sin subcomando, sin --json: ayuda + exit 0
        result = runner.invoke(b2g, ["snapshot"], catch_exceptions=False)

    assert result.exit_code == 0
    # La salida contiene texto de ayuda (subcomandos disponibles)
    assert "create" in result.output or "restore" in result.output
    # NO debe ser un envelope JSON de error
    assert not result.output.strip().startswith("{")


# ---------------------------------------------------------------------------
# 6 & 7. restore suelto (shim): sigue funcionando, command == "restore"
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_restore_shim_funciona(tmp_path: Path) -> None:
    """``b2g restore --from-corpus`` (shim) importa el corpus y transiciona a FILTERED."""
    from click.testing import CliRunner

    from bib2graph.cli import b2g
    from bib2graph.cycle import CycleState
    from bib2graph.stores.duckdb import DuckDBStore
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / "ws"
    ws = Workspace.init(ws_dir, "test")
    parquet_path = _make_parquet(tmp_path / "corpus.parquet")

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws_dir),
            "restore",
            "--from-corpus",
            str(parquet_path),
            "--json",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, f"Salida inesperada:\n{result.output}"
    # Usar result.stdout porque b2g restore (shim deprecado, #165) emite aviso
    # a stderr; result.output mezcla ambas streams en Click 8.4.1.
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert len(lines) == 1
    envelope = json.loads(lines[0])
    assert envelope["ok"] is True
    assert envelope["command"] == "restore"  # backward compat — NO "snapshot restore"
    assert envelope["data"]["state"] == "FILTERED"

    store = DuckDBStore(ws.library_path)
    assert store.backend.loop_state() == CycleState.FILTERED


# ---------------------------------------------------------------------------
# 8. Reloj inyectado: run_restore acepta decided_at
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_run_restore_acepta_decided_at(tmp_path: Path) -> None:
    """``service.snapshot.run_restore`` acepta ``decided_at`` inyectado (R2/ADR 0017).

    El servicio no llama ``datetime.now()`` directamente; el CLI lo inyecta.
    """
    from bib2graph.service.snapshot import run_restore

    parquet_path = _make_parquet(tmp_path / "corpus.parquet")
    store_path = tmp_path / "test.duckdb"

    # Inyectar un timestamp explícito (simulación de la frontera CLI).
    fixed_ts = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
    data = run_restore(store_path, parquet_path, decided_at=fixed_ts)

    # La función no debe lanzar y el resultado debe ser correcto.
    assert data["state"] == "FILTERED"
    assert data["papers_loaded"] == 3


# ---------------------------------------------------------------------------
# 9 & 10. Backward compat: importar run_snapshot / run_restore desde CLI modules
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_run_snapshot_importable_desde_cli_snapshot(tmp_path: Path) -> None:
    """``from bib2graph.cli.commands.snapshot import run_snapshot`` sigue funcionando."""
    from bib2graph.cli.commands.snapshot import run_snapshot

    store_path = tmp_path / "test.duckdb"
    _seed_store(store_path)
    out_dir = tmp_path / "snap"

    data = run_snapshot(store_path, out_dir=out_dir)
    assert "snapshot_dir" in data
    assert (out_dir / "corpus.parquet").exists()


@pytest.mark.unit
def test_run_restore_importable_desde_cli_restore(tmp_path: Path) -> None:
    """``from bib2graph.cli.commands.restore import run_restore`` sigue funcionando."""
    from bib2graph.cli.commands.restore import run_restore
    from bib2graph.cycle import CycleState

    parquet_path = _make_parquet(tmp_path / "corpus.parquet")
    store_path = tmp_path / "test.duckdb"

    data = run_restore(store_path, parquet_path)
    assert data["state"] == str(CycleState.FILTERED)


@pytest.mark.unit
def test_run_restore_importable_desde_service_snapshot(tmp_path: Path) -> None:
    """``from bib2graph.service.snapshot import run_restore`` funciona directamente."""
    from bib2graph.cycle import CycleState
    from bib2graph.service.snapshot import run_restore

    parquet_path = _make_parquet(tmp_path / "corpus.parquet")
    store_path = tmp_path / "test.duckdb"

    data = run_restore(store_path, parquet_path)
    assert data["state"] == str(CycleState.FILTERED)


# ---------------------------------------------------------------------------
# 11. Stdout puro: en modo JSON stdout == exactamente 1 línea
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_snapshot_create_stdout_puro_una_linea(tmp_path: Path) -> None:
    """``b2g snapshot create --json`` escribe exactamente 1 línea en stdout (#151)."""
    from click.testing import CliRunner

    from bib2graph.cli import b2g
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / "ws"
    ws = Workspace.init(ws_dir, "test")
    _seed_store(ws.library_path)

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        ["--workspace", str(ws_dir), "snapshot", "create", "--json"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    lines = [ln for ln in result.output.splitlines() if ln.strip()]
    assert len(lines) == 1, (
        f"stdout debe tener exactamente 1 línea, tuvo {len(lines)}:\n{result.output!r}"
    )


@pytest.mark.unit
def test_snapshot_restore_stdout_puro_una_linea(tmp_path: Path) -> None:
    """``b2g snapshot restore --json`` escribe exactamente 1 línea en stdout (#151)."""
    from click.testing import CliRunner

    from bib2graph.cli import b2g
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / "ws"
    Workspace.init(ws_dir, "test")
    parquet_path = _make_parquet(tmp_path / "corpus.parquet")

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws_dir),
            "snapshot",
            "restore",
            "--from-corpus",
            str(parquet_path),
            "--json",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    lines = [ln for ln in result.output.splitlines() if ln.strip()]
    assert len(lines) == 1, (
        f"stdout debe tener exactamente 1 línea, tuvo {len(lines)}:\n{result.output!r}"
    )


# ---------------------------------------------------------------------------
# FSM invariant: snapshot create NO transiciona, snapshot restore -> FILTERED
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_snapshot_create_no_transiciona_fsm(tmp_path: Path) -> None:
    """``snapshot create`` (run_snapshot) NO transiciona el CycleState.

    El corpus puede estar en cualquier estado; snapshot create no lo cambia.
    """
    from bib2graph.corpus import Corpus
    from bib2graph.cycle import CycleState
    from bib2graph.schemas import CORPUS_SCHEMA
    from bib2graph.service.snapshot import run_snapshot
    from bib2graph.stores.duckdb import DuckDBStore

    rows = [_make_corpus_row(id="P1")]
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)
    store_path = tmp_path / "test.duckdb"
    store = DuckDBStore(store_path)
    store.persist(corpus)
    store.backend.set_loop_state(CycleState.SEEDED, cycle_round=1)

    # Snapshot create: no debe cambiar el estado
    run_snapshot(store_path, out_dir=tmp_path / "snap")

    store2 = DuckDBStore(store_path)
    assert store2.backend.loop_state() == CycleState.SEEDED  # sin cambio


@pytest.mark.unit
def test_snapshot_restore_transiciona_a_filtered_desde_seeded(tmp_path: Path) -> None:
    """``snapshot restore`` transiciona desde SEEDED a FILTERED."""
    from bib2graph.cycle import CycleState
    from bib2graph.service.snapshot import run_restore
    from bib2graph.stores.duckdb import DuckDBStore

    parquet_path = _make_parquet(tmp_path / "corpus.parquet")
    store_path = tmp_path / "test.duckdb"

    data = run_restore(store_path, parquet_path)

    assert data["state"] == str(CycleState.FILTERED)
    store = DuckDBStore(store_path)
    assert store.backend.loop_state() == CycleState.FILTERED
