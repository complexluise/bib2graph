"""Tests TDD — remanentes del modelo workspace (ADR 0029).

Cierra los ítems "fuera de este corte" del AS-BUILT 2026-06-16:

  Parte A — Redirigir snapshot/export al workspace:
    - snapshot sin --out-dir escribe en <workspace>/snapshots/
    - export sin --out-dir escribe en <workspace>/exports/
    - --out-dir explícito sigue funcionando (override gana)
    - (eliminado en #75: el modo degenerado --store ya no existe)

  Parte B — Staleness de la cache de redes:
    - is_networks_cache_stale con hash distinto → True
    - is_networks_cache_stale con hash coincidente → False
    - is_networks_cache_stale sin .corpus_hash → False
    - read_networks_corpus_hash sin archivo → None
    - read_networks_corpus_hash con archivo → string del hash
    - status con cache stale → aviso en envelope["warnings"]
    - status con cache fresca → sin aviso
    - data["networks_cache_stale"] reflejado correctamente

Filosofía (AGENTS.md): se testean funciones núcleo y el comportamiento del
comando via CliRunner donde corresponde. Marcador: ``unit``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest

from bib2graph.schemas import CORPUS_SCHEMA

# ---------------------------------------------------------------------------
# Helpers compartidos
# ---------------------------------------------------------------------------


def _make_corpus_row(
    *, id: str, title: str = "Test", curation_status: str = "candidate"
) -> dict[str, Any]:
    """Fila mínima con schema completo."""
    return {
        "id": id,
        "openalex_id": None,
        "doi": None,
        "title": title,
        "year": 2020,
        "abstract": None,
        "source": None,
        "language": "en",
        "publisher": None,
        "research_areas": None,
        "is_seed": True,
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
# Parte A — snapshot sin --out-dir usa <workspace>/snapshots/
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_snapshot_sin_outdir_usa_workspace_snapshots_dir(tmp_path: Path) -> None:
    """run_snapshot con out_dir = ws.snapshots_dir escribe en <workspace>/snapshots/."""
    from bib2graph.cli.commands.snapshot import run_snapshot
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / "proyecto"
    ws = Workspace.init(ws_dir, "proyecto")
    _seed_store(ws.library_path)

    data = run_snapshot(ws.library_path, out_dir=ws.snapshots_dir)

    assert Path(data["snapshot_dir"]).is_relative_to(ws.snapshots_dir)
    assert (ws.snapshots_dir / "corpus.parquet").exists() or any(
        ws.snapshots_dir.iterdir()
    )
    assert "corpus_hash" in data
    assert "total_papers" in data


@pytest.mark.unit
def test_snapshot_cmd_sin_outdir_resuelve_snapshots_dir(tmp_path: Path) -> None:
    """snapshot_cmd sin --out-dir usa ws.snapshots_dir (integración Click)."""
    from click.testing import CliRunner

    from bib2graph.cli.commands.snapshot import snapshot_cmd
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / "proyecto"
    ws = Workspace.init(ws_dir, "proyecto")
    _seed_store(ws.library_path)

    runner = CliRunner()
    result = runner.invoke(
        snapshot_cmd,
        ["create", "--json"],
        obj={"workspace": str(ws_dir)},
    )

    assert result.exit_code == 0, result.output
    import json

    envelope = json.loads(result.output)
    assert envelope["ok"] is True
    snap_dir = Path(envelope["data"]["snapshot_dir"])
    # El snapshot debe quedar dentro de <workspace>/snapshots/
    assert snap_dir.is_relative_to(ws.snapshots_dir)


@pytest.mark.unit
def test_snapshot_cmd_con_outdir_explicito_usa_ese(tmp_path: Path) -> None:
    """snapshot_cmd con --out-dir explícito usa ese directorio (override gana)."""
    from click.testing import CliRunner

    from bib2graph.cli.commands.snapshot import snapshot_cmd
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / "proyecto"
    ws = Workspace.init(ws_dir, "proyecto")
    _seed_store(ws.library_path)

    custom_out = tmp_path / "mi_snapshot"
    runner = CliRunner()
    result = runner.invoke(
        snapshot_cmd,
        ["create", "--out-dir", str(custom_out), "--json"],
        obj={"workspace": str(ws_dir)},
    )

    assert result.exit_code == 0, result.output
    import json

    envelope = json.loads(result.output)
    assert envelope["ok"] is True
    snap_dir = Path(envelope["data"]["snapshot_dir"])
    # El snapshot debe estar dentro del directorio explícito, NO en snapshots/
    assert snap_dir.is_relative_to(custom_out)
    assert not snap_dir.is_relative_to(ws.snapshots_dir)


# ---------------------------------------------------------------------------
# Parte A — export sin --out-dir usa <workspace>/exports/
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_export_cmd_sin_outdir_resuelve_exports_dir(tmp_path: Path) -> None:
    """export_cmd sin --out-dir usa ws.exports_dir (integración Click)."""
    from click.testing import CliRunner

    from bib2graph.cli.commands.build import run_build
    from bib2graph.cli.commands.export import export_cmd
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / "proyecto"
    ws = Workspace.init(ws_dir, "proyecto")
    _seed_store(ws.library_path)

    # Primero construir las redes (export las necesita)
    run_build(ws.library_path, out_dir=ws.networks_dir)

    runner = CliRunner()
    result = runner.invoke(
        export_cmd,
        ["--json"],
        obj={"workspace": str(ws_dir)},
    )

    assert result.exit_code == 0, result.output
    import json

    envelope = json.loads(result.output)
    assert envelope["ok"] is True
    out_dir = Path(envelope["data"]["out_dir"])
    # El export debe quedar dentro de <workspace>/exports/
    assert out_dir == ws.exports_dir


@pytest.mark.unit
def test_export_cmd_con_outdir_explicito_usa_ese(tmp_path: Path) -> None:
    """export_cmd con --out-dir explícito usa ese directorio (override gana)."""
    from click.testing import CliRunner

    from bib2graph.cli.commands.build import run_build
    from bib2graph.cli.commands.export import export_cmd
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / "proyecto"
    ws = Workspace.init(ws_dir, "proyecto")
    _seed_store(ws.library_path)

    run_build(ws.library_path, out_dir=ws.networks_dir)

    custom_out = tmp_path / "mi_export"
    runner = CliRunner()
    result = runner.invoke(
        export_cmd,
        ["--out-dir", str(custom_out), "--json"],
        obj={"workspace": str(ws_dir)},
    )

    assert result.exit_code == 0, result.output
    import json

    envelope = json.loads(result.output)
    assert envelope["ok"] is True
    out_dir = Path(envelope["data"]["out_dir"])
    assert out_dir == custom_out
    assert out_dir != ws.exports_dir


# ---------------------------------------------------------------------------
# Parte B — helpers de staleness en Workspace
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_read_networks_corpus_hash_sin_archivo_devuelve_none(tmp_path: Path) -> None:
    """read_networks_corpus_hash devuelve None si no hay .corpus_hash."""
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / "ws"
    ws = Workspace.init(ws_dir, "test")

    assert ws.read_networks_corpus_hash() is None


@pytest.mark.unit
def test_read_networks_corpus_hash_con_archivo_devuelve_hash(tmp_path: Path) -> None:
    """read_networks_corpus_hash devuelve el hash sellado."""
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / "ws"
    ws = Workspace.init(ws_dir, "test")

    hash_file = ws.networks_dir / ".corpus_hash"
    hash_file.write_text("abc123", encoding="utf-8")

    assert ws.read_networks_corpus_hash() == "abc123"


@pytest.mark.unit
def test_is_networks_cache_stale_sin_corpus_hash_es_false(tmp_path: Path) -> None:
    """is_networks_cache_stale es False si no hay .corpus_hash (no hay cache)."""
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / "ws"
    ws = Workspace.init(ws_dir, "test")

    assert ws.is_networks_cache_stale("cualquier_hash") is False


@pytest.mark.unit
def test_is_networks_cache_stale_hash_coincidente_es_false(tmp_path: Path) -> None:
    """is_networks_cache_stale es False cuando el hash sellado coincide."""
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / "ws"
    ws = Workspace.init(ws_dir, "test")

    hash_file = ws.networks_dir / ".corpus_hash"
    hash_file.write_text("hash_estable_42", encoding="utf-8")

    assert ws.is_networks_cache_stale("hash_estable_42") is False


@pytest.mark.unit
def test_is_networks_cache_stale_hash_distinto_es_true(tmp_path: Path) -> None:
    """is_networks_cache_stale es True cuando el hash sellado difiere del vivo."""
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / "ws"
    ws = Workspace.init(ws_dir, "test")

    hash_file = ws.networks_dir / ".corpus_hash"
    hash_file.write_text("hash_viejo", encoding="utf-8")

    assert ws.is_networks_cache_stale("hash_nuevo") is True


@pytest.mark.unit
def test_staleness_tras_build_y_sin_cambios_es_false(tmp_path: Path) -> None:
    """Tras un build con el corpus actual, is_networks_cache_stale es False."""
    from bib2graph.backends.memory import compute_corpus_hash
    from bib2graph.cli.commands.build import run_build
    from bib2graph.stores.duckdb import DuckDBStore
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / "ws"
    ws = Workspace.init(ws_dir, "test")
    _seed_store(ws.library_path)

    run_build(ws.library_path, out_dir=ws.networks_dir)

    store = DuckDBStore(ws.library_path)
    corpus = store.load()
    live_hash = compute_corpus_hash(corpus.to_arrow())

    assert ws.is_networks_cache_stale(live_hash) is False


@pytest.mark.unit
def test_staleness_tras_build_y_nuevo_paper_es_true(tmp_path: Path) -> None:
    """Tras un build y agregar un paper, is_networks_cache_stale es True."""
    from bib2graph.backends.memory import compute_corpus_hash
    from bib2graph.cli.commands.build import run_build
    from bib2graph.corpus import Corpus
    from bib2graph.stores.duckdb import DuckDBStore
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / "ws"
    ws = Workspace.init(ws_dir, "test")
    _seed_store(ws.library_path)

    run_build(ws.library_path, out_dir=ws.networks_dir)

    # Agregar un paper nuevo al corpus (cambia el hash vivo)
    new_row = _make_corpus_row(id="P_NUEVO", title="Nuevo paper")
    new_table = pa.Table.from_pylist([new_row], schema=CORPUS_SCHEMA)
    new_corpus = Corpus.from_arrow(new_table)
    store = DuckDBStore(ws.library_path)
    existing_corpus = store.load()
    merged = existing_corpus.merge(new_corpus)
    store.persist(merged)

    store2 = DuckDBStore(ws.library_path)
    updated_corpus = store2.load()
    live_hash = compute_corpus_hash(updated_corpus.to_arrow())

    assert ws.is_networks_cache_stale(live_hash) is True


# ---------------------------------------------------------------------------
# Parte B — status reporta staleness en el envelope
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_status_sin_cache_no_avisa_staleness(tmp_path: Path) -> None:
    """status sin cache de redes: data['networks_cache_stale'] es False."""
    from click.testing import CliRunner

    from bib2graph.cli.commands.status import status_cmd
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / "proyecto"
    ws = Workspace.init(ws_dir, "proyecto")
    _seed_store(ws.library_path)

    runner = CliRunner()
    result = runner.invoke(
        status_cmd,
        ["--json"],
        obj={"workspace": str(ws_dir)},
    )

    assert result.exit_code == 0, result.output
    import json

    envelope = json.loads(result.output)
    assert envelope["ok"] is True
    assert envelope["data"]["networks_cache_stale"] is False
    assert envelope["warnings"] == []


@pytest.mark.unit
def test_status_cache_fresca_no_avisa(tmp_path: Path) -> None:
    """status con cache fresca (hash coincide): sin aviso y stale=False."""
    from click.testing import CliRunner

    from bib2graph.cli.commands.build import run_build
    from bib2graph.cli.commands.status import status_cmd
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / "proyecto"
    ws = Workspace.init(ws_dir, "proyecto")
    _seed_store(ws.library_path)

    # Build → sella el hash
    run_build(ws.library_path, out_dir=ws.networks_dir)

    runner = CliRunner()
    result = runner.invoke(
        status_cmd,
        ["--json"],
        obj={"workspace": str(ws_dir)},
    )

    assert result.exit_code == 0, result.output
    import json

    envelope = json.loads(result.output)
    assert envelope["ok"] is True
    assert envelope["data"]["networks_cache_stale"] is False
    assert envelope["warnings"] == []


@pytest.mark.unit
def test_status_cache_stale_emite_aviso(tmp_path: Path) -> None:
    """status con cache obsoleta: warnings tiene un mensaje con 'b2g build'."""
    from bib2graph.cli.commands.build import run_build
    from bib2graph.cli.commands.status import status_cmd
    from bib2graph.workspace import Workspace

    # Sellar un hash "viejo" artificialmente
    ws_dir = tmp_path / "proyecto"
    ws = Workspace.init(ws_dir, "proyecto")
    _seed_store(ws.library_path)
    run_build(ws.library_path, out_dir=ws.networks_dir)

    # Sobrescribir .corpus_hash con un hash falso para simular staleness
    hash_file = ws.networks_dir / ".corpus_hash"
    hash_file.write_text("hash_falso_del_pasado", encoding="utf-8")

    import json

    from click.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(
        status_cmd,
        ["--json"],
        obj={"workspace": str(ws_dir)},
    )

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["ok"] is True
    assert envelope["data"]["networks_cache_stale"] is True
    assert len(envelope["warnings"]) == 1
    assert "b2g build" in envelope["warnings"][0]
