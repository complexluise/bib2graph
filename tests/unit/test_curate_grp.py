"""Tests del grupo noun-verb ``b2g curate`` (sub-issue #155, superficie CLI 0.10.0).

Cubre:

Forma del envelope (todos los subcomandos):
  1. curate dump  → exit 0, schema="1", command="curate dump", ok=True, stdout puro.
  2. curate apply → exit 0, schema="1", command="curate apply", ok=True, stdout puro.
  3. curate accept → exit 0, schema="1", command="curate accept", ok=True, stdout puro.
  4. curate reject → exit 0, schema="1", command="curate reject", ok=True, stdout puro.
  5. curate filter → exit 0, schema="1", command="curate filter", ok=True, stdout puro.

Sin subcomando:
  6. b2g curate → help + exit 0.

Breaking changes:
  7. curate dump --all → "No such option" (opción eliminada).

FSM (#155, precedente D1 de #159):
  8. curate filter → transiciona a FILTERED.
  9. curate accept, reject, dump, apply → NO transicionan el FSM.

Round-trip:
  10. curate dump → editar CSV → curate apply → corpus refleja decisiones.
  11. curate apply con IDs huérfanos → not_found_count reportado.

Regresión #165 (verbos sueltos intactos):
  12. b2g accept --ids … → envelope command="accept", misma transición (ninguna).
  13. b2g reject --ids … → envelope command="reject", misma transición (ninguna).
  14. b2g filter --year-gte … → envelope command="filter", misma transición FILTERED.

Marcador: ``unit`` (DuckDB en tmp_path, sin red real).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest
from click.testing import CliRunner

from bib2graph.cli import b2g
from bib2graph.schemas import CORPUS_SCHEMA

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers compartidos
# ---------------------------------------------------------------------------


def _row(
    *,
    id: str,
    title: str = "Título de prueba",
    year: int = 2020,
    is_seed: bool = False,
    curation_status: str = "candidate",
    language: str = "en",
) -> dict[str, Any]:
    """Fila mínima con schema completo para tests."""
    return {
        "id": id,
        "source_id": None,
        "doi": None,
        "title": title,
        "year": year,
        "abstract": None,
        "source": None,
        "language": language,
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


def _init_workspace(tmp_path: Path, name: str = "test-ws") -> Any:
    """Crea y devuelve un Workspace inicializado en tmp_path."""
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / name
    return Workspace.init(ws_dir, name)


def _seed_store(ws: Any, rows: list[dict[str, Any]]) -> None:
    """Persiste filas en el store del workspace."""
    from bib2graph.corpus import Corpus
    from bib2graph.stores.duckdb import DuckDBStore

    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)
    store = DuckDBStore(ws.library_path)
    store.persist(corpus)
    store.close()


def _assert_one_json_line(stdout: str, *, schema: str = "1") -> dict[str, Any]:
    """Aserta exactamente una línea JSON con schema correcto; devuelve el dict."""
    lines = [ln for ln in stdout.splitlines() if ln.strip()]
    assert len(lines) == 1, (
        f"Se esperaba exactamente 1 línea en stdout, se obtuvieron {len(lines)}:\n"
        f"{stdout!r}"
    )
    data = json.loads(lines[0])
    assert data.get("schema") == schema
    return data


def _get_loop_state(ws: Any) -> Any:
    """Lee el loop_state del backend DuckDB del workspace."""
    from bib2graph.stores.duckdb import DuckDBStore

    store = DuckDBStore(ws.library_path)
    state = store.backend.loop_state()
    store.close()
    return state


# ---------------------------------------------------------------------------
# 1. curate dump → envelope correcto
# ---------------------------------------------------------------------------


def test_curate_dump_envelope_correcto(tmp_path: Path) -> None:
    """curate dump --json emite envelope schema='1', command='curate dump', ok=True."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="C1")])

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "curate", "dump", "--json"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    data = _assert_one_json_line(result.stdout)
    assert data["ok"] is True
    assert data["command"] == "curate dump"
    assert "csv_path" in data["data"]
    assert "papers_exported" in data["data"]


def test_curate_dump_stdout_puro(tmp_path: Path) -> None:
    """curate dump --json: stdout tiene exactamente 1 línea JSON (sin ruido)."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="C1")])

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "curate", "dump", "--json"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    lineas = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert len(lineas) == 1


# ---------------------------------------------------------------------------
# 2. curate apply → envelope correcto
# ---------------------------------------------------------------------------


def test_curate_apply_envelope_correcto(tmp_path: Path) -> None:
    """curate apply <csv> --json emite envelope correcto."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1"), _row(id="P2")])

    # Generar CSV con curate dump
    runner = CliRunner()
    runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "curate", "dump"],
        catch_exceptions=False,
    )
    csv_path = ws.exports_dir / "curacion.csv"
    assert csv_path.exists()

    # Aplicar decisiones
    result = runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "curate", "apply", str(csv_path), "--json"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    data = _assert_one_json_line(result.stdout)
    assert data["ok"] is True
    assert data["command"] == "curate apply"
    assert "accepted_count" in data["data"]
    assert "rejected_count" in data["data"]
    assert "skipped_count" in data["data"]
    assert "not_found_count" in data["data"]
    assert "total_rows" in data["data"]


# ---------------------------------------------------------------------------
# 3. curate accept → envelope correcto
# ---------------------------------------------------------------------------


def test_curate_accept_envelope_correcto(tmp_path: Path) -> None:
    """curate accept --ids P1 --json emite envelope correcto."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1"), _row(id="P2")])

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws.root),
            "curate",
            "accept",
            "--ids",
            "P1",
            "--json",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    data = _assert_one_json_line(result.stdout)
    assert data["ok"] is True
    assert data["command"] == "curate accept"
    assert data["data"]["accepted_count"] == 1


# ---------------------------------------------------------------------------
# 4. curate reject → envelope correcto
# ---------------------------------------------------------------------------


def test_curate_reject_envelope_correcto(tmp_path: Path) -> None:
    """curate reject --ids P1 --json emite envelope correcto."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1"), _row(id="P2")])

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws.root),
            "curate",
            "reject",
            "--ids",
            "P1",
            "--json",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    data = _assert_one_json_line(result.stdout)
    assert data["ok"] is True
    assert data["command"] == "curate reject"
    assert data["data"]["rejected_count"] == 1


# ---------------------------------------------------------------------------
# 5. curate filter → envelope correcto
# ---------------------------------------------------------------------------


def test_curate_filter_envelope_correcto(tmp_path: Path) -> None:
    """curate filter --year-gte 1900 --json emite envelope correcto."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1", year=2020), _row(id="P2", year=2021)])

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws.root),
            "curate",
            "filter",
            "--year-gte",
            "1900",
            "--json",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    data = _assert_one_json_line(result.stdout)
    assert data["ok"] is True
    assert data["command"] == "curate filter"
    assert "steps" in data["data"]
    assert "total_papers" in data["data"]


# ---------------------------------------------------------------------------
# 6. curate sin subcomando → help + exit 0
# ---------------------------------------------------------------------------


def test_curate_sin_subcomando_imprime_ayuda() -> None:
    """b2g curate sin subcomando imprime ayuda y sale con exit 0."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(b2g, ["curate"])
    assert result.exit_code == 0
    assert "dump" in result.output
    assert "apply" in result.output
    assert "accept" in result.output
    assert "reject" in result.output
    assert "filter" in result.output


# ---------------------------------------------------------------------------
# 7. curate dump --all → "No such option" (BREAKING #155)
# ---------------------------------------------------------------------------


def test_curate_dump_all_no_existe(tmp_path: Path) -> None:
    """curate dump --all fue eliminado (#155); Click debe reportar 'No such option'."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="C1")])

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "curate", "dump", "--all"],
    )
    # Click reporta "No such option" y sale con exit != 0
    assert result.exit_code != 0
    assert "no such option" in result.output.lower()


# ---------------------------------------------------------------------------
# 8. curate filter → transiciona a FILTERED (FSM)
# ---------------------------------------------------------------------------


def test_curate_filter_transiciona_a_filtered(tmp_path: Path) -> None:
    """curate filter transiciona el CycleState a FILTERED (el verbo define la transición)."""
    from bib2graph.cycle import CycleState

    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1", year=2020)])

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws.root),
            "curate",
            "filter",
            "--year-gte",
            "1900",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output

    estado_post = _get_loop_state(ws)
    assert estado_post == CycleState.FILTERED, (
        f"curate filter debe transicionar a FILTERED, pero quedó en {estado_post}"
    )


# ---------------------------------------------------------------------------
# 9. curate accept/reject/dump/apply → NO transicionan el FSM
# ---------------------------------------------------------------------------


def test_curate_accept_no_transiciona_fsm(tmp_path: Path) -> None:
    """curate accept NO transiciona el CycleState (curación transversal)."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    estado_previo = _get_loop_state(ws)

    runner = CliRunner()
    runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "curate", "accept", "--ids", "P1"],
        catch_exceptions=False,
    )

    estado_post = _get_loop_state(ws)
    assert estado_post == estado_previo, (
        f"curate accept no debe cambiar el CycleState: {estado_previo} → {estado_post}"
    )


def test_curate_reject_no_transiciona_fsm(tmp_path: Path) -> None:
    """curate reject NO transiciona el CycleState (curación transversal)."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    estado_previo = _get_loop_state(ws)

    runner = CliRunner()
    runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "curate", "reject", "--ids", "P1"],
        catch_exceptions=False,
    )

    estado_post = _get_loop_state(ws)
    assert estado_post == estado_previo, (
        f"curate reject no debe cambiar el CycleState: {estado_previo} → {estado_post}"
    )


def test_curate_dump_no_transiciona_fsm(tmp_path: Path) -> None:
    """curate dump NO transiciona el CycleState (curación transversal)."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="C1")])

    estado_previo = _get_loop_state(ws)

    runner = CliRunner()
    runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "curate", "dump"],
        catch_exceptions=False,
    )

    estado_post = _get_loop_state(ws)
    assert estado_post == estado_previo, (
        f"curate dump no debe cambiar el CycleState: {estado_previo} → {estado_post}"
    )


def test_curate_apply_no_transiciona_fsm(tmp_path: Path) -> None:
    """curate apply NO transiciona el CycleState (curación transversal)."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="C1")])

    estado_previo = _get_loop_state(ws)

    # Generar CSV de decisiones
    runner = CliRunner()
    runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "curate", "dump"],
        catch_exceptions=False,
    )
    csv_path = ws.exports_dir / "curacion.csv"

    runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "curate", "apply", str(csv_path)],
        catch_exceptions=False,
    )

    estado_post = _get_loop_state(ws)
    assert estado_post == estado_previo, (
        f"curate apply no debe cambiar el CycleState: {estado_previo} → {estado_post}"
    )


# ---------------------------------------------------------------------------
# 10. Round-trip: dump → editar CSV → apply
# ---------------------------------------------------------------------------


def test_round_trip_dump_apply(tmp_path: Path) -> None:
    """curate dump → editar decision → curate apply → corpus refleja decisiones."""
    from bib2graph.stores.duckdb import DuckDBStore

    ws = _init_workspace(tmp_path)
    _seed_store(
        ws,
        [
            _row(id="PA", title="Paper A"),
            _row(id="PB", title="Paper B"),
            _row(id="PC", title="Paper C"),
        ],
    )

    runner = CliRunner()

    # 1) dump
    result_dump = runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "curate", "dump", "--json"],
        catch_exceptions=False,
    )
    assert result_dump.exit_code == 0
    data_dump = json.loads(result_dump.stdout.strip())
    csv_path = Path(data_dump["data"]["csv_path"])
    assert csv_path.exists()

    # 2) Editar el CSV: PA → accepted, PB → rejected
    from bib2graph.service.curate import CSV_COLUMNS

    rows: list[dict[str, str]] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        if row["id"] == "PA":
            row["decision"] = "accepted"
        elif row["id"] == "PB":
            row["decision"] = "rejected"
        # PC queda undecided

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    # 3) apply
    result_apply = runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "curate", "apply", str(csv_path), "--json"],
        catch_exceptions=False,
    )
    assert result_apply.exit_code == 0, result_apply.output
    data_apply = json.loads(result_apply.stdout.strip())
    assert data_apply["data"]["accepted_count"] == 1
    assert data_apply["data"]["rejected_count"] == 1
    assert data_apply["data"]["skipped_count"] == 1
    assert data_apply["data"]["not_found_count"] == 0

    # 4) Verificar estado del corpus (to_arrow antes de close — DuckDB requiere conexión activa)
    store = DuckDBStore(ws.library_path)
    corpus = store.load()
    by_id = {r["id"]: r for r in corpus.to_arrow().to_pylist()}
    store.close()

    assert by_id["PA"]["curation_status"] == "accepted"
    assert by_id["PB"]["curation_status"] == "rejected"
    assert by_id["PC"]["curation_status"] == "candidate"


# ---------------------------------------------------------------------------
# 11. curate apply con IDs huérfanos → not_found_count reportado
# ---------------------------------------------------------------------------


def test_curate_apply_ids_huerfanos_reportados(tmp_path: Path) -> None:
    """curate apply con IDs que no existen en el corpus → not_found_count > 0, sin abort."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    # Crear CSV con un ID huérfano
    csv_path = tmp_path / "decisiones.csv"
    from bib2graph.service.curate import CSV_COLUMNS

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerow(
            {**{c: "" for c in CSV_COLUMNS}, "id": "P1", "decision": "accepted"}
        )
        writer.writerow(
            {**{c: "" for c in CSV_COLUMNS}, "id": "P_FANTASMA", "decision": "accepted"}
        )

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "curate", "apply", str(csv_path), "--json"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout.strip())
    assert data["data"]["accepted_count"] == 1
    assert data["data"]["not_found_count"] == 1


# ---------------------------------------------------------------------------
# 12. Regresión #165: b2g accept suelto sigue funcionando
# ---------------------------------------------------------------------------


def test_accept_suelto_envelope_intacto(tmp_path: Path) -> None:
    """b2g accept (suelto) sigue emitiendo envelope con command='accept'."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "accept", "--ids", "P1", "--json"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    data = _assert_one_json_line(result.stdout)
    assert data["ok"] is True
    assert data["command"] == "accept"
    assert data["data"]["accepted_count"] == 1


def test_accept_suelto_no_transiciona_fsm(tmp_path: Path) -> None:
    """b2g accept suelto NO transiciona el CycleState (curación transversal)."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    estado_previo = _get_loop_state(ws)

    runner = CliRunner()
    runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "accept", "--ids", "P1"],
        catch_exceptions=False,
    )

    estado_post = _get_loop_state(ws)
    assert estado_post == estado_previo


# ---------------------------------------------------------------------------
# 13. Regresión #165: b2g reject suelto sigue funcionando
# ---------------------------------------------------------------------------


def test_reject_suelto_envelope_intacto(tmp_path: Path) -> None:
    """b2g reject (suelto) sigue emitiendo envelope con command='reject'."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "reject", "--ids", "P1", "--json"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    data = _assert_one_json_line(result.stdout)
    assert data["ok"] is True
    assert data["command"] == "reject"
    assert data["data"]["rejected_count"] == 1


def test_reject_suelto_no_transiciona_fsm(tmp_path: Path) -> None:
    """b2g reject suelto NO transiciona el CycleState (curación transversal)."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    estado_previo = _get_loop_state(ws)

    runner = CliRunner()
    runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "reject", "--ids", "P1"],
        catch_exceptions=False,
    )

    estado_post = _get_loop_state(ws)
    assert estado_post == estado_previo


# ---------------------------------------------------------------------------
# 14. Regresión #165: b2g filter suelto sigue funcionando y transiciona a FILTERED
# ---------------------------------------------------------------------------


def test_filter_suelto_envelope_intacto(tmp_path: Path) -> None:
    """b2g filter (suelto) sigue emitiendo envelope con command='filter'."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1", year=2020)])

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws.root),
            "filter",
            "--year-gte",
            "1900",
            "--json",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    data = _assert_one_json_line(result.stdout)
    assert data["ok"] is True
    assert data["command"] == "filter"


def test_filter_suelto_transiciona_a_filtered(tmp_path: Path) -> None:
    """b2g filter suelto transiciona a FILTERED (mismo comportamiento que curate filter)."""
    from bib2graph.cycle import CycleState

    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1", year=2020)])

    runner = CliRunner()
    runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws.root),
            "filter",
            "--year-gte",
            "1900",
        ],
        catch_exceptions=False,
    )

    estado_post = _get_loop_state(ws)
    assert estado_post == CycleState.FILTERED


# ---------------------------------------------------------------------------
# 15. curate accept --ids múltiples en una invocación
# ---------------------------------------------------------------------------


def test_curate_accept_ids_multiples(tmp_path: Path) -> None:
    """curate accept acepta múltiples IDs con --ids repetido."""
    from bib2graph.stores.duckdb import DuckDBStore

    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1"), _row(id="P2"), _row(id="P3")])

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws.root),
            "curate",
            "accept",
            "--ids",
            "P1",
            "--ids",
            "P2",
            "--json",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout.strip())
    assert data["data"]["accepted_count"] == 2

    store = DuckDBStore(ws.library_path)
    corpus = store.load()
    by_id = {r["id"]: r for r in corpus.to_arrow().to_pylist()}
    store.close()
    assert by_id["P1"]["curation_status"] == "accepted"
    assert by_id["P2"]["curation_status"] == "accepted"
    assert by_id["P3"]["curation_status"] == "candidate"


# ---------------------------------------------------------------------------
# 16. curate dump --scope seeds exporta solo semillas
# ---------------------------------------------------------------------------


def test_curate_dump_scope_seeds(tmp_path: Path) -> None:
    """curate dump --scope seeds exporta solo papers con is_seed=True."""
    ws = _init_workspace(tmp_path)
    _seed_store(
        ws,
        [
            _row(id="S1", is_seed=True),
            _row(id="S2", is_seed=True),
            _row(id="C1", is_seed=False),
        ],
    )

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws.root),
            "curate",
            "dump",
            "--scope",
            "seeds",
            "--json",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout.strip())
    assert data["data"]["papers_exported"] == 2


# ---------------------------------------------------------------------------
# 17. Neutralidad de reloj (R2 / ADR 0017 enmendado): filter_corpus recibe
#     decided_at inyectado y lo pasa a apply_filters
# ---------------------------------------------------------------------------


def test_filter_corpus_pasa_decided_at_a_apply_filters(tmp_path: Path) -> None:
    """filter_corpus pasa el decided_at inyectado a apply_filters (R2/ADR 0017).

    Verifica que el servicio no genera su propio timestamp: lo recibe del llamador
    y lo propaga sin modificarlo al núcleo.
    """
    from datetime import UTC, datetime
    from unittest.mock import patch

    from bib2graph.service.curate import filter_corpus

    store_path = tmp_path / "test.duckdb"

    # Seed mínimo
    import pyarrow as pa

    from bib2graph.corpus import Corpus
    from bib2graph.schemas import CORPUS_SCHEMA
    from bib2graph.stores.duckdb import DuckDBStore

    row = _row(id="P1", year=2020)
    table = pa.Table.from_pylist([row], schema=CORPUS_SCHEMA)
    corpus_obj = Corpus.from_arrow(table)
    store = DuckDBStore(store_path)
    store.persist(corpus_obj)
    store.close()

    sentinel = datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC)

    captured: dict[str, Any] = {}

    original_apply_filters = __import__(
        "bib2graph.filters.prisma", fromlist=["apply_filters"]
    ).apply_filters

    def _spy_apply_filters(corpus, criteria, *, decided_at=None):  # type: ignore[no-untyped-def]
        captured["decided_at"] = decided_at
        return original_apply_filters(corpus, criteria, decided_at=decided_at)

    with patch(
        "bib2graph.filters.prisma.apply_filters", side_effect=_spy_apply_filters
    ):
        filter_corpus(store_path, year_gte=2000, decided_at=sentinel)

    assert captured.get("decided_at") == sentinel, (
        f"filter_corpus no propagó el decided_at inyectado: {captured.get('decided_at')!r}"
    )


def test_service_curate_no_llama_datetime_now() -> None:
    """service/curate.py no contiene llamadas directas a datetime.now() (R2/ADR 0017).

    El reloj es responsabilidad del llamador (frontera CLI), no del servicio.
    Detección por AST sobre el source real del módulo.
    """
    import ast
    import importlib
    import pathlib

    mod = importlib.import_module("bib2graph.service.curate")
    source_file = mod.__file__
    assert source_file is not None
    tree = ast.parse(pathlib.Path(source_file).read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # Detecta patrones: datetime.now(...), _datetime.now(...), UTC.now(...)
        if isinstance(func, ast.Attribute) and func.attr == "now":
            obj = func.value
            obj_name = (
                obj.id
                if isinstance(obj, ast.Name)
                else obj.attr
                if isinstance(obj, ast.Attribute)
                else None
            )
            if obj_name in {"datetime", "_datetime", "UTC"}:
                raise AssertionError(
                    f"service/curate.py llama a {obj_name}.now() en línea "
                    f"{node.lineno} — viola R2/ADR 0017: el reloj debe inyectarse "
                    "desde la frontera CLI, no generarse en el servicio."
                )
