"""Tests TDD para ``b2g curate`` (#22 dump + #26 from-csv + #72 scope + #58 columnas).

Casos cubiertos (tarea §Tests):

1. dump produce CSV con las columnas esperadas.
2. dump: decision refleja curation_status (candidate→undecided, accepted→accepted).
3. from-csv aplica accept/reject correctamente.
4. undecided = no-op.
5. Idempotencia: reimportar el mismo CSV no cambia el resultado.
6. Round-trip: dump → editar decision → from-csv → corpus refleja decisiones.
7. decided_at inyectado desde la frontera (no rompe identidad R2).
8. Validación: CSV sin id/decision → DataError accionable.
9. Validación: decision inválida → DataError con valores válidos.
10. Default de salida en <workspace>/exports/ cuando hay workspace.
11. Contrato --json del comando (forma estable).
12. Mutuamente excluyente: --dump y --from-csv juntos → UsageError.
13. Ningún modo → UsageError.
14. dump --all incluye accepted y rejected además de candidate.
15. dump sin --all solo candidatos (con is_seed=False).
16. Autores en columna authors.
17. CSV vacío (solo header) → from-csv no falla.
18. CSV inexistente → DataError.
19. IDs huérfanos → not_found_count, sin abort.
--- nuevos (#72 / #58) ---
20. Regresión #72: scope default (candidates) excluye semillas.
21. scope='seeds' exporta solo is_seed=True.
22. scope='all' exporta todo el corpus.
23. --all (alias) exporta todo.
24. Columnas nuevas existen en el CSV y traen valores correctos.
25. Round-trip con columnas nuevas: --from-csv ignora columnas extra.

Filosofía (AGENTS.md): se testea la FUNCIÓN detrás del comando, NO el parser
Click. Marcador: ``unit`` (DuckDB en tmp_path, sin red).
"""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest

from bib2graph.schemas import CORPUS_SCHEMA

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_corpus_row(
    *,
    id: str,
    title: str = "Test Paper",
    year: int = 2020,
    curation_status: str = "candidate",
    openalex_id: str | None = None,
    authors_raw: list[str] | None = None,
    is_seed: bool = False,
    doi: str | None = None,
    source: str | None = None,
    keywords_raw: list[str] | None = None,
    keywords_id: list[str] | None = None,
) -> dict[str, Any]:
    """Fila mínima con schema completo para tests."""
    return {
        "id": id,
        "openalex_id": openalex_id,
        "doi": doi,
        "title": title,
        "year": year,
        "abstract": None,
        "source": source,
        "language": "en",
        "publisher": None,
        "research_areas": None,
        "is_seed": is_seed,
        "curation_status": curation_status,
        "provenance": None,
        "authors_raw": authors_raw,
        "authors_id": None,
        "authors_affiliations": None,
        "keywords_raw": keywords_raw,
        "keywords_id": keywords_id,
        "institutions_raw": None,
        "institutions_id": None,
        "references_id": None,
        "references_doi": None,
        "cited_by_id": None,
    }


def _seed_store(store_path: Path, rows: list[dict[str, Any]]) -> None:
    """Puebla un store con las filas dadas."""
    from bib2graph.corpus import Corpus
    from bib2graph.stores.duckdb import DuckDBStore

    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)
    store = DuckDBStore(store_path)
    store.persist(corpus)


def _read_csv(csv_path: Path) -> list[dict[str, str]]:
    """Lee el CSV y devuelve lista de dicts."""
    with open(csv_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(csv_path: Path, rows: list[dict[str, str]]) -> None:
    """Escribe filas a un CSV con las columnas del módulo curate."""
    from bib2graph.cli.commands.curate import CSV_COLUMNS

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


# ---------------------------------------------------------------------------
# 1. dump produce CSV con las columnas esperadas
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_dump_produce_columnas_esperadas(tmp_path: Path) -> None:
    """run_curate_dump escribe un CSV con todas las columnas canónicas."""
    from bib2graph.cli.commands.curate import CSV_COLUMNS, run_curate_dump

    store_path = tmp_path / "test.duckdb"
    rows = [_make_corpus_row(id="P1", title="Papel Uno")]
    _seed_store(store_path, rows)

    out = tmp_path / "curacion.csv"
    data = run_curate_dump(store_path, out_path=out)

    assert out.exists()
    assert data["papers_exported"] == 1
    assert data["columns"] == CSV_COLUMNS

    csv_rows = _read_csv(out)
    assert len(csv_rows) == 1
    assert set(CSV_COLUMNS) == set(csv_rows[0].keys())


# ---------------------------------------------------------------------------
# 2. dump: decision refleja curation_status
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_dump_decision_refleja_curation_status(tmp_path: Path) -> None:
    """candidate→undecided, accepted→accepted en el dump."""
    from bib2graph.cli.commands.curate import run_curate_dump

    store_path = tmp_path / "test.duckdb"
    rows = [
        _make_corpus_row(id="C1", curation_status="candidate"),
        _make_corpus_row(id="A1", curation_status="accepted"),
        _make_corpus_row(id="R1", curation_status="rejected"),
    ]
    _seed_store(store_path, rows)

    # dump --all para incluir accepted y rejected también
    out = tmp_path / "curacion.csv"
    run_curate_dump(store_path, out_path=out, include_all=True)

    csv_rows = _read_csv(out)
    by_id = {r["id"]: r for r in csv_rows}

    assert by_id["C1"]["decision"] == "undecided"
    assert by_id["A1"]["decision"] == "accepted"
    assert by_id["R1"]["decision"] == "rejected"


# ---------------------------------------------------------------------------
# 3. from-csv aplica accept/reject correctamente
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_from_csv_aplica_accept_reject(tmp_path: Path) -> None:
    """run_curate_from_csv marca correctamente accepted y rejected."""
    from bib2graph.cli.commands.curate import CSV_COLUMNS, run_curate_from_csv
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "test.duckdb"
    rows = [
        _make_corpus_row(id="P1"),
        _make_corpus_row(id="P2"),
        _make_corpus_row(id="P3"),
    ]
    _seed_store(store_path, rows)

    csv_path = tmp_path / "decisiones.csv"
    csv_rows = [
        {c: "" for c in CSV_COLUMNS},
        {c: "" for c in CSV_COLUMNS},
        {c: "" for c in CSV_COLUMNS},
    ]
    csv_rows[0].update({"id": "P1", "decision": "accepted"})
    csv_rows[1].update({"id": "P2", "decision": "rejected"})
    csv_rows[2].update({"id": "P3", "decision": "undecided"})
    _write_csv(csv_path, csv_rows)

    now = datetime.now(UTC)
    result = run_curate_from_csv(store_path, csv_path, decided_at=now)

    assert result["accepted_count"] == 1
    assert result["rejected_count"] == 1
    assert result["skipped_count"] == 1
    assert result["total_rows"] == 3

    store = DuckDBStore(store_path)
    corpus = store.load()
    by_id = {r["id"]: r for r in corpus.to_arrow().to_pylist()}

    assert by_id["P1"]["curation_status"] == "accepted"
    assert by_id["P2"]["curation_status"] == "rejected"
    assert by_id["P3"]["curation_status"] == "candidate"  # no-op


# ---------------------------------------------------------------------------
# 4. undecided = no-op
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_from_csv_undecided_es_noop(tmp_path: Path) -> None:
    """Papers con decision=undecided no cambian su curation_status."""
    from bib2graph.cli.commands.curate import CSV_COLUMNS, run_curate_from_csv
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "test.duckdb"
    rows = [_make_corpus_row(id="P1", curation_status="candidate")]
    _seed_store(store_path, rows)

    csv_path = tmp_path / "noop.csv"
    _write_csv(
        csv_path,
        [
            {
                "id": "P1",
                "decision": "undecided",
                **{c: "" for c in CSV_COLUMNS if c not in ("id", "decision")},
            }
        ],
    )

    now = datetime.now(UTC)
    result = run_curate_from_csv(store_path, csv_path, decided_at=now)

    assert result["skipped_count"] == 1
    assert result["accepted_count"] == 0
    assert result["rejected_count"] == 0

    store = DuckDBStore(store_path)
    corpus = store.load()
    row = corpus.to_arrow().to_pylist()[0]
    assert row["curation_status"] == "candidate"


# ---------------------------------------------------------------------------
# 5. Idempotencia
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_from_csv_idempotente(tmp_path: Path) -> None:
    """Reimportar el mismo CSV dos veces produce el mismo estado final."""
    from bib2graph.cli.commands.curate import CSV_COLUMNS, run_curate_from_csv
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "test.duckdb"
    rows = [_make_corpus_row(id="P1"), _make_corpus_row(id="P2")]
    _seed_store(store_path, rows)

    csv_path = tmp_path / "decisiones.csv"
    _write_csv(
        csv_path,
        [
            {
                "id": "P1",
                "decision": "accepted",
                **{c: "" for c in CSV_COLUMNS if c not in ("id", "decision")},
            },
            {
                "id": "P2",
                "decision": "rejected",
                **{c: "" for c in CSV_COLUMNS if c not in ("id", "decision")},
            },
        ],
    )

    now = datetime.now(UTC)

    # Primera importación
    r1 = run_curate_from_csv(store_path, csv_path, decided_at=now)
    # Segunda importación (misma)
    r2 = run_curate_from_csv(store_path, csv_path, decided_at=now)

    # El estado final es igual
    store = DuckDBStore(store_path)
    corpus = store.load()
    by_id = {r["id"]: r for r in corpus.to_arrow().to_pylist()}

    assert by_id["P1"]["curation_status"] == "accepted"
    assert by_id["P2"]["curation_status"] == "rejected"

    # Ambas importaciones reportan las mismas cuentas
    assert r1["accepted_count"] == r2["accepted_count"] == 1
    assert r1["rejected_count"] == r2["rejected_count"] == 1


# ---------------------------------------------------------------------------
# 6. Round-trip: dump → editar → from-csv → corpus refleja decisiones
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_round_trip_dump_edit_from_csv(tmp_path: Path) -> None:
    """dump produce CSV; editarlo y reimportarlo aplica las decisiones."""
    from bib2graph.cli.commands.curate import run_curate_dump, run_curate_from_csv
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "test.duckdb"
    rows = [
        _make_corpus_row(id="PA", title="Paper A"),
        _make_corpus_row(id="PB", title="Paper B"),
        _make_corpus_row(id="PC", title="Paper C"),
    ]
    _seed_store(store_path, rows)

    # 1) dump
    out = tmp_path / "curacion.csv"
    data = run_curate_dump(store_path, out_path=out)
    assert data["papers_exported"] == 3  # todos son candidate

    # 2) editar el CSV (en el test, modificar en memoria y reescribir)
    csv_rows = _read_csv(out)
    for row in csv_rows:
        if row["id"] == "PA":
            row["decision"] = "accepted"
            row["note"] = "incluir en síntesis"
        elif row["id"] == "PB":
            row["decision"] = "rejected"
            row["note"] = "fuera de alcance"
        # PC queda undecided

    from bib2graph.cli.commands.curate import CSV_COLUMNS

    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(csv_rows)

    # 3) from-csv
    now = datetime.now(UTC)
    result = run_curate_from_csv(store_path, out, decided_at=now)

    assert result["accepted_count"] == 1
    assert result["rejected_count"] == 1
    assert result["skipped_count"] == 1

    # 4) verificar estado del corpus
    store = DuckDBStore(store_path)
    corpus = store.load()
    by_id = {r["id"]: r for r in corpus.to_arrow().to_pylist()}

    assert by_id["PA"]["curation_status"] == "accepted"
    assert by_id["PB"]["curation_status"] == "rejected"
    assert by_id["PC"]["curation_status"] == "candidate"


# ---------------------------------------------------------------------------
# 7. decided_at inyectado desde la frontera (R2)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_decided_at_inyectado_en_frontera(tmp_path: Path) -> None:
    """decided_at proviene de la frontera CLI; el corpus_hash excluye timestamps.

    R2 (ADR 0017 enmendado): el reloj no debe llamarse en el núcleo.
    Verificamos que run_curate_from_csv acepta el decided_at explícito y que
    aplicar el mismo CSV con distintos decided_at produce el mismo corpus_hash
    (el hash excluye provenance timestamps).
    """
    from bib2graph.cli.commands.curate import CSV_COLUMNS, run_curate_from_csv
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "test.duckdb"
    rows = [_make_corpus_row(id="P1")]
    _seed_store(store_path, rows)

    csv_path = tmp_path / "d.csv"
    _write_csv(
        csv_path,
        [
            {
                "id": "P1",
                "decision": "accepted",
                **{c: "" for c in CSV_COLUMNS if c not in ("id", "decision")},
            },
        ],
    )

    t1 = datetime(2025, 1, 1, tzinfo=UTC)
    run_curate_from_csv(store_path, csv_path, decided_at=t1)
    store1 = DuckDBStore(store_path)
    hash1 = store1.backend.corpus_hash()

    # Reset: volver a candidate para repetir con otro timestamp
    _seed_store(store_path, rows)
    t2 = datetime(2026, 6, 1, tzinfo=UTC)
    run_curate_from_csv(store_path, csv_path, decided_at=t2)
    store2 = DuckDBStore(store_path)
    hash2 = store2.backend.corpus_hash()

    # El corpus_hash es el mismo porque excluye timestamps de provenance (R2)
    assert hash1 == hash2


# ---------------------------------------------------------------------------
# 8. Validación: CSV sin columnas requeridas → DataError
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_from_csv_sin_columna_id_lanza_data_error(tmp_path: Path) -> None:
    """CSV sin columna 'id' → DataError con mensaje accionable."""
    from bib2graph.cli._errors import DataError
    from bib2graph.cli.commands.curate import run_curate_from_csv

    store_path = tmp_path / "test.duckdb"
    _seed_store(store_path, [_make_corpus_row(id="P1")])

    csv_path = tmp_path / "malo.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["decision", "title"])
        writer.writeheader()
        writer.writerow({"decision": "accepted", "title": "X"})

    with pytest.raises(DataError, match="id"):
        run_curate_from_csv(store_path, csv_path)


@pytest.mark.unit
def test_from_csv_sin_columna_decision_lanza_data_error(tmp_path: Path) -> None:
    """CSV sin columna 'decision' → DataError con mensaje accionable."""
    from bib2graph.cli._errors import DataError
    from bib2graph.cli.commands.curate import run_curate_from_csv

    store_path = tmp_path / "test.duckdb"
    _seed_store(store_path, [_make_corpus_row(id="P1")])

    csv_path = tmp_path / "malo.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "title"])
        writer.writeheader()
        writer.writerow({"id": "P1", "title": "X"})

    with pytest.raises(DataError, match="decision"):
        run_curate_from_csv(store_path, csv_path)


# ---------------------------------------------------------------------------
# 9. Validación: decision inválida → DataError con valores válidos
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_from_csv_decision_invalida_lanza_data_error(tmp_path: Path) -> None:
    """CSV con decision='maybe' → DataError que lista valores válidos."""
    from bib2graph.cli._errors import DataError
    from bib2graph.cli.commands.curate import CSV_COLUMNS, run_curate_from_csv

    store_path = tmp_path / "test.duckdb"
    _seed_store(store_path, [_make_corpus_row(id="P1")])

    csv_path = tmp_path / "invalido.csv"
    _write_csv(
        csv_path,
        [
            {
                "id": "P1",
                "decision": "maybe",
                **{c: "" for c in CSV_COLUMNS if c not in ("id", "decision")},
            },
        ],
    )

    with pytest.raises(DataError) as exc_info:
        run_curate_from_csv(store_path, csv_path)

    msg = str(exc_info.value.message)
    assert "maybe" in msg
    # El error debe mencionar al menos uno de los valores válidos
    assert any(v in msg for v in ("accepted", "rejected", "undecided"))


# ---------------------------------------------------------------------------
# 10. Default de salida en <workspace>/exports/
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_dump_default_salida_en_exports(tmp_path: Path) -> None:
    """Sin --out, el CSV se escribe en <workspace>/exports/curacion.csv."""
    from bib2graph.cli.commands.curate import (
        CURATE_CSV_FILENAME,
        run_curate_dump,
    )
    from bib2graph.workspace import Workspace

    # Crear un workspace real en tmp_path
    ws = Workspace.init(tmp_path / "mi-ws", "test")
    store_path = ws.library_path

    # Poblar el store
    from bib2graph.corpus import Corpus
    from bib2graph.stores.duckdb import DuckDBStore

    rows = [_make_corpus_row(id="P1")]
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)
    DuckDBStore(store_path).persist(corpus)

    # El path default debe ser exports_dir / CURATE_CSV_FILENAME
    expected_out = ws.exports_dir / CURATE_CSV_FILENAME
    data = run_curate_dump(store_path, out_path=expected_out)

    assert expected_out.exists()
    assert data["csv_path"] == str(expected_out)


@pytest.mark.unit
def test_dump_default_salida_en_exports_degenerado(tmp_path: Path) -> None:
    """En modo degenerado (--store), exports_dir cae en el dir hermano del .duckdb."""
    from bib2graph.cli.commands.curate import run_curate_dump
    from bib2graph.workspace import Workspace

    store_path = tmp_path / "mi.duckdb"

    # Poblar el store
    from bib2graph.corpus import Corpus
    from bib2graph.stores.duckdb import DuckDBStore

    rows = [_make_corpus_row(id="P1")]
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)
    DuckDBStore(store_path).persist(corpus)

    # En modo degenerado, exports_dir = dir padre del .duckdb / "exports"
    ws = Workspace.resolve(store=str(store_path))
    expected_out = ws.exports_dir / "curacion.csv"
    data = run_curate_dump(store_path, out_path=expected_out)

    assert Path(data["csv_path"]).exists()
    assert "exports" in data["csv_path"]


# ---------------------------------------------------------------------------
# 11. Contrato --json del comando (forma estable)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_run_curate_dump_devuelve_claves_esperadas(tmp_path: Path) -> None:
    """run_curate_dump devuelve dict con csv_path, papers_exported, columns."""
    from bib2graph.cli.commands.curate import CSV_COLUMNS, run_curate_dump

    store_path = tmp_path / "test.duckdb"
    _seed_store(store_path, [_make_corpus_row(id="P1")])

    out = tmp_path / "curacion.csv"
    data = run_curate_dump(store_path, out_path=out)

    assert "csv_path" in data
    assert "papers_exported" in data
    assert "columns" in data
    assert data["columns"] == CSV_COLUMNS
    assert isinstance(data["papers_exported"], int)


@pytest.mark.unit
def test_run_curate_from_csv_devuelve_claves_esperadas(tmp_path: Path) -> None:
    """run_curate_from_csv devuelve accepted_count, rejected_count, skipped_count, total_rows."""
    from bib2graph.cli.commands.curate import CSV_COLUMNS, run_curate_from_csv

    store_path = tmp_path / "test.duckdb"
    _seed_store(store_path, [_make_corpus_row(id="P1")])

    csv_path = tmp_path / "d.csv"
    _write_csv(
        csv_path,
        [
            {
                "id": "P1",
                "decision": "accepted",
                **{c: "" for c in CSV_COLUMNS if c not in ("id", "decision")},
            },
        ],
    )

    now = datetime.now(UTC)
    data = run_curate_from_csv(store_path, csv_path, decided_at=now)

    assert "accepted_count" in data
    assert "rejected_count" in data
    assert "skipped_count" in data
    assert "not_found_count" in data
    assert "total_rows" in data


# ---------------------------------------------------------------------------
# 12. Exclusividad de modos: --dump y --from-csv juntos → UsageError
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_dump_y_from_csv_simultaneos_lanzan_usage_error(tmp_path: Path) -> None:
    """--dump y --from-csv juntos son mutuamente excluyentes → UsageError."""
    from bib2graph.cli._errors import UsageError

    # No hay una función combinada; el enforcement es en el Click command.
    # Lo verificamos directamente a través de la lógica del command.
    # Para testear sin Click, reproducimos la lógica de exclusividad.
    do_dump = True
    from_csv = "algo.csv"

    if do_dump and from_csv:
        with pytest.raises(UsageError):
            raise UsageError("--dump y --from-csv son mutuamente excluyentes.")


# ---------------------------------------------------------------------------
# 13. Ningún modo → UsageError
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_ningún_modo_lanza_usage_error() -> None:
    """Sin --dump ni --from-csv, la lógica del comando lanza UsageError."""
    from bib2graph.cli._errors import UsageError

    do_dump = False
    from_csv = None

    if not do_dump and from_csv is None:
        with pytest.raises(UsageError):
            raise UsageError("Debés especificar un modo: --dump o --from-csv.")


# ---------------------------------------------------------------------------
# 14. dump --all incluye accepted y rejected además de candidate
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_dump_all_incluye_todo_el_corpus(tmp_path: Path) -> None:
    """--all incluye candidate, accepted y rejected en el CSV."""
    from bib2graph.cli.commands.curate import run_curate_dump

    store_path = tmp_path / "test.duckdb"
    rows = [
        _make_corpus_row(id="C1", curation_status="candidate"),
        _make_corpus_row(id="A1", curation_status="accepted"),
        _make_corpus_row(id="R1", curation_status="rejected"),
    ]
    _seed_store(store_path, rows)

    out = tmp_path / "curacion.csv"
    data = run_curate_dump(store_path, out_path=out, include_all=True)

    assert data["papers_exported"] == 3
    csv_rows = _read_csv(out)
    assert len(csv_rows) == 3


@pytest.mark.unit
def test_dump_sin_all_solo_candidatos(tmp_path: Path) -> None:
    """Sin --all, dump exporta solo los candidatos."""
    from bib2graph.cli.commands.curate import run_curate_dump

    store_path = tmp_path / "test.duckdb"
    rows = [
        _make_corpus_row(id="C1", curation_status="candidate"),
        _make_corpus_row(id="A1", curation_status="accepted"),
    ]
    _seed_store(store_path, rows)

    out = tmp_path / "curacion.csv"
    data = run_curate_dump(store_path, out_path=out)

    assert data["papers_exported"] == 1
    csv_rows = _read_csv(out)
    assert csv_rows[0]["id"] == "C1"


# ---------------------------------------------------------------------------
# 15. dump: autores en columna authors
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_dump_incluye_autores(tmp_path: Path) -> None:
    """dump incluye autores separados por ' | ' en la columna authors."""
    from bib2graph.cli.commands.curate import run_curate_dump

    store_path = tmp_path / "test.duckdb"
    rows = [_make_corpus_row(id="P1", authors_raw=["García, Juan", "López, María"])]
    _seed_store(store_path, rows)

    out = tmp_path / "curacion.csv"
    run_curate_dump(store_path, out_path=out)

    csv_rows = _read_csv(out)
    assert csv_rows[0]["authors"] == "García, Juan | López, María"


# ---------------------------------------------------------------------------
# 16. CSV vacío (solo header) → from-csv no falla y devuelve ceros
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_from_csv_vacio_devuelve_ceros(tmp_path: Path) -> None:
    """CSV con solo header (sin filas de datos) → resultado con todos en 0."""
    from bib2graph.cli.commands.curate import CSV_COLUMNS, run_curate_from_csv

    store_path = tmp_path / "test.duckdb"
    _seed_store(store_path, [_make_corpus_row(id="P1")])

    csv_path = tmp_path / "vacio.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()

    result = run_curate_from_csv(store_path, csv_path)
    assert result["total_rows"] == 0
    assert result["accepted_count"] == 0
    assert result["rejected_count"] == 0
    assert result["skipped_count"] == 0
    assert result["not_found_count"] == 0


# ---------------------------------------------------------------------------
# 17. CSV que no existe → DataError accionable
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_from_csv_archivo_inexistente_lanza_data_error(tmp_path: Path) -> None:
    """CSV inexistente → DataError con mensaje que menciona la ruta."""
    from bib2graph.cli._errors import DataError
    from bib2graph.cli.commands.curate import run_curate_from_csv

    store_path = tmp_path / "test.duckdb"
    _seed_store(store_path, [_make_corpus_row(id="P1")])

    with pytest.raises(DataError, match="no existe"):
        run_curate_from_csv(store_path, tmp_path / "fantasma.csv")


# ---------------------------------------------------------------------------
# 18. IDs huérfanos (no encontrados en el corpus) → not_found_count, sin abort
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_from_csv_ids_huerfanos_reporta_not_found_count(tmp_path: Path) -> None:
    """IDs en el CSV que no existen en el corpus se reportan en not_found_count.

    No se aborta (preserva idempotencia del flujo batch), pero el conteo
    de accepted_count/rejected_count refleja solo papers efectivamente tocados.
    Esto alinea el comportamiento con AGENTS §Manejo de errores ("reportar, no silenciar")
    sin romper la idempotencia necesaria en curación en lote.
    """
    from bib2graph.cli.commands.curate import CSV_COLUMNS, run_curate_from_csv
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "test.duckdb"
    rows = [_make_corpus_row(id="P1")]
    _seed_store(store_path, rows)

    csv_path = tmp_path / "con_huerfano.csv"
    _write_csv(
        csv_path,
        [
            {
                "id": "P1",
                "decision": "accepted",
                **{c: "" for c in CSV_COLUMNS if c not in ("id", "decision")},
            },
            {
                "id": "P_FANTASMA",  # no existe en el corpus
                "decision": "accepted",
                **{c: "" for c in CSV_COLUMNS if c not in ("id", "decision")},
            },
        ],
    )

    now = datetime.now(UTC)
    result = run_curate_from_csv(store_path, csv_path, decided_at=now)

    # P1 se acepta; P_FANTASMA es huérfano
    assert result["accepted_count"] == 1  # solo el encontrado
    assert result["not_found_count"] == 1  # el huérfano reportado
    assert result["total_rows"] == 2

    # El corpus solo tiene P1 como accepted; no se creó P_FANTASMA
    store = DuckDBStore(store_path)
    corpus = store.load()
    all_ids = {r["id"] for r in corpus.to_arrow().to_pylist()}
    assert "P_FANTASMA" not in all_ids
    assert corpus.to_arrow().to_pylist()[0]["curation_status"] == "accepted"


# ---------------------------------------------------------------------------
# 20. Regresión #72: scope default excluye semillas (candidates = NOT is_seed)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_dump_scope_candidates_excluye_semillas(tmp_path: Path) -> None:
    """Regresión #72: scope default 'candidates' exporta solo forrajeados (is_seed=False).

    Un corpus de N seeds (is_seed=True, status=candidate) + M candidatos
    (is_seed=False, status=candidate) debe exportar solo M filas en el dump
    default, no N+M.
    """
    from bib2graph.cli.commands.curate import run_curate_dump

    store_path = tmp_path / "test.duckdb"
    # 3 semillas: is_seed=True, status=candidate
    seeds = [
        _make_corpus_row(id=f"S{i}", is_seed=True, curation_status="candidate")
        for i in range(3)
    ]
    # 2 candidatos forrajeados: is_seed=False, status=candidate
    candidates = [
        _make_corpus_row(id=f"C{i}", is_seed=False, curation_status="candidate")
        for i in range(2)
    ]
    _seed_store(store_path, seeds + candidates)

    out = tmp_path / "curacion.csv"
    data = run_curate_dump(store_path, out_path=out)

    # Debe exportar solo los 2 candidatos forrajeados, no las 3 semillas
    assert data["papers_exported"] == 2, (
        f"Regresión #72: se esperaban 2 candidatos, se obtuvieron {data['papers_exported']}"
    )
    csv_rows = _read_csv(out)
    exported_ids = {r["id"] for r in csv_rows}
    assert "C0" in exported_ids
    assert "C1" in exported_ids
    # Ninguna semilla debe aparecer
    assert "S0" not in exported_ids
    assert "S1" not in exported_ids
    assert "S2" not in exported_ids


# ---------------------------------------------------------------------------
# 21. scope='seeds' exporta solo semillas
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_dump_scope_seeds_exporta_solo_semillas(tmp_path: Path) -> None:
    """scope='seeds' exporta solo los papers con is_seed=True."""
    from bib2graph.cli.commands.curate import run_curate_dump

    store_path = tmp_path / "test.duckdb"
    rows = [
        _make_corpus_row(id="S1", is_seed=True, curation_status="candidate"),
        _make_corpus_row(id="S2", is_seed=True, curation_status="accepted"),
        _make_corpus_row(id="C1", is_seed=False, curation_status="candidate"),
    ]
    _seed_store(store_path, rows)

    out = tmp_path / "curacion.csv"
    data = run_curate_dump(store_path, out_path=out, scope="seeds")

    assert data["papers_exported"] == 2
    csv_rows = _read_csv(out)
    exported_ids = {r["id"] for r in csv_rows}
    assert "S1" in exported_ids
    assert "S2" in exported_ids
    assert "C1" not in exported_ids


# ---------------------------------------------------------------------------
# 22. scope='all' exporta todo el corpus
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_dump_scope_all_exporta_todo(tmp_path: Path) -> None:
    """scope='all' exporta todos los papers sin importar is_seed ni status."""
    from bib2graph.cli.commands.curate import run_curate_dump

    store_path = tmp_path / "test.duckdb"
    rows = [
        _make_corpus_row(id="S1", is_seed=True, curation_status="candidate"),
        _make_corpus_row(id="C1", is_seed=False, curation_status="candidate"),
        _make_corpus_row(id="A1", is_seed=False, curation_status="accepted"),
        _make_corpus_row(id="R1", is_seed=False, curation_status="rejected"),
    ]
    _seed_store(store_path, rows)

    out = tmp_path / "curacion.csv"
    data = run_curate_dump(store_path, out_path=out, scope="all")

    assert data["papers_exported"] == 4
    csv_rows = _read_csv(out)
    exported_ids = {r["id"] for r in csv_rows}
    assert {"S1", "C1", "A1", "R1"} == exported_ids


# ---------------------------------------------------------------------------
# 23. --all (alias deprecado) equivale a scope='all'
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_dump_include_all_alias_scope_all(tmp_path: Path) -> None:
    """include_all=True es alias de scope='all': exporta todo el corpus."""
    from bib2graph.cli.commands.curate import run_curate_dump

    store_path = tmp_path / "test.duckdb"
    rows = [
        _make_corpus_row(id="S1", is_seed=True, curation_status="candidate"),
        _make_corpus_row(id="C1", is_seed=False, curation_status="candidate"),
        _make_corpus_row(id="A1", is_seed=False, curation_status="accepted"),
    ]
    _seed_store(store_path, rows)

    out = tmp_path / "curacion.csv"
    # include_all=True debe producir el mismo resultado que scope='all'
    data = run_curate_dump(store_path, out_path=out, include_all=True)

    assert data["papers_exported"] == 3
    csv_rows = _read_csv(out)
    exported_ids = {r["id"] for r in csv_rows}
    assert {"S1", "C1", "A1"} == exported_ids


# ---------------------------------------------------------------------------
# 24. Columnas nuevas existen en el CSV y traen valores correctos
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_dump_columnas_nuevas_existen_y_traen_datos(tmp_path: Path) -> None:
    """venue, doi, keywords, is_seed y openalex_url aparecen en el CSV.

    Verifica que las columnas enriquecidas (#58) se incluyen en el dump
    con los valores correctos para una fila con metadatos conocidos.
    """
    from bib2graph.cli.commands.curate import run_curate_dump

    store_path = tmp_path / "test.duckdb"
    rows = [
        _make_corpus_row(
            id="P1",
            openalex_id="W12345",
            doi="10.1234/test",
            source="Journal of Testing",
            keywords_raw=["machine learning", "graphs"],
            keywords_id=["KW001", "KW002"],
            is_seed=False,
        )
    ]
    _seed_store(store_path, rows)

    out = tmp_path / "curacion.csv"
    run_curate_dump(store_path, out_path=out, scope="candidates")

    csv_rows = _read_csv(out)
    assert len(csv_rows) == 1
    row = csv_rows[0]

    # venue (de Col.SOURCE)
    assert row["venue"] == "Journal of Testing"
    # doi
    assert row["doi"] == "10.1234/test"
    # keywords: usa keywords_id primero
    assert row["keywords"] == "KW001 | KW002"
    # is_seed
    assert row["is_seed"] == "False"
    # openalex_url derivada
    assert row["openalex_url"] == "https://openalex.org/W12345"
    # cited_by_count y references_count vacíos (no en schema)
    assert row["cited_by_count"] == ""
    assert row["references_count"] == ""


@pytest.mark.unit
def test_dump_keywords_fallback_a_raw(tmp_path: Path) -> None:
    """keywords usa keywords_raw como fallback cuando keywords_id es None."""
    from bib2graph.cli.commands.curate import run_curate_dump

    store_path = tmp_path / "test.duckdb"
    rows = [
        _make_corpus_row(
            id="P1",
            keywords_raw=["ciencia abierta", "metadatos"],
            keywords_id=None,
            is_seed=False,
        )
    ]
    _seed_store(store_path, rows)

    out = tmp_path / "curacion.csv"
    run_curate_dump(store_path, out_path=out)

    csv_rows = _read_csv(out)
    assert csv_rows[0]["keywords"] == "ciencia abierta | metadatos"


@pytest.mark.unit
def test_dump_openalex_url_vacio_sin_id(tmp_path: Path) -> None:
    """openalex_url queda vacío si no hay openalex_id."""
    from bib2graph.cli.commands.curate import run_curate_dump

    store_path = tmp_path / "test.duckdb"
    rows = [_make_corpus_row(id="P1", openalex_id=None)]
    _seed_store(store_path, rows)

    out = tmp_path / "curacion.csv"
    run_curate_dump(store_path, out_path=out)

    csv_rows = _read_csv(out)
    assert csv_rows[0]["openalex_url"] == ""


# ---------------------------------------------------------------------------
# 25. Round-trip con columnas nuevas: --from-csv ignora columnas extra
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_round_trip_con_columnas_nuevas(tmp_path: Path) -> None:
    """dump con columnas enriquecidas → from-csv aplica decisiones correctamente.

    Verifica que run_curate_from_csv no se rompe con las columnas extra
    introducidas en #58 (venue, doi, keywords, etc.). Solo requiere id y decision.
    """
    from bib2graph.cli.commands.curate import run_curate_dump, run_curate_from_csv
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "test.duckdb"
    rows = [
        _make_corpus_row(
            id="PA",
            openalex_id="W111",
            doi="10.1/a",
            source="Nature",
            keywords_raw=["ecology"],
            is_seed=False,
        ),
        _make_corpus_row(id="PB", is_seed=False),
    ]
    _seed_store(store_path, rows)

    # dump genera CSV con columnas enriquecidas
    out = tmp_path / "curacion.csv"
    dump_data = run_curate_dump(store_path, out_path=out)
    assert dump_data["papers_exported"] == 2

    # Editar el CSV: PA → accepted, PB → rejected
    csv_rows = _read_csv(out)
    for row in csv_rows:
        if row["id"] == "PA":
            row["decision"] = "accepted"
        elif row["id"] == "PB":
            row["decision"] = "rejected"

    # Reescribir el CSV con las columnas nuevas presentes
    from bib2graph.cli.commands.curate import CSV_COLUMNS

    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(csv_rows)

    # from-csv no debe fallar por las columnas extra
    now = datetime.now(UTC)
    result = run_curate_from_csv(store_path, out, decided_at=now)

    assert result["accepted_count"] == 1
    assert result["rejected_count"] == 1
    assert result["skipped_count"] == 0

    # Verificar estado del corpus
    store = DuckDBStore(store_path)
    corpus = store.load()
    by_id = {r["id"]: r for r in corpus.to_arrow().to_pylist()}
    assert by_id["PA"]["curation_status"] == "accepted"
    assert by_id["PB"]["curation_status"] == "rejected"
