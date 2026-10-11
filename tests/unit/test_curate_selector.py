"""Tests de curación masiva declarativa (#308).

``curate accept``/``curate reject`` aceptan, además de ``--ids`` enumerados,
un SELECTOR declarativo: ``--query`` (substring de título, mismo criterio
que ``read list --query``) y/o metadata ``--year-gte/lte``, ``--language``,
``--type``, ``--min-citations`` (misma semántica que ``curate filter``).

Cubre:
  1. ``select_ids_by_predicate`` (núcleo del selector, service.curate).
  2. ``accept_papers``/``reject_papers`` con selector (service layer).
  3. ``curate accept``/``curate reject`` --year-gte/--query (CLI).
  4. Combinación ``--ids`` + selector → unión.
  5. ``--ids`` solo sigue funcionando (regresión, ya cubierto en
     test_curate_grp.py, pero se repite acá el caso límite sin selector).
  6. Envelope ``--json`` con conteos correctos.
  7. Sin ``--ids`` ni selector → error de uso (exit 1).

Marcador: ``unit`` (DuckDB en tmp_path, sin red real).
"""

from __future__ import annotations

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
# Helpers compartidos (mismo molde que test_curate_grp.py)
# ---------------------------------------------------------------------------


def _row(
    *,
    id: str,
    title: str = "Título de prueba",
    year: int = 2020,
    is_seed: bool = False,
    curation_status: str = "candidate",
    language: str = "en",
    cited_by_id: list[str] | None = None,
) -> dict[str, Any]:
    """Fila mínima con schema completo para tests, con año/status variados."""
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
        "cited_by_id": cited_by_id,
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


def _status_by_id(ws: Any) -> dict[str, str]:
    """Lee curation_status por id desde el store."""
    from bib2graph.stores.duckdb import DuckDBStore

    store = DuckDBStore(ws.library_path)
    corpus = store.load()
    by_id = {
        str(r["id"]): str(r["curation_status"]) for r in corpus.to_arrow().to_pylist()
    }
    store.close()
    return by_id


# Corpus de prueba con años/status/títulos variados (fixture compartida).
def _mixed_corpus_rows() -> list[dict[str, Any]]:
    return [
        _row(id="P2010", title="Old paper on unrelated topic", year=2010),
        _row(id="P2015", title="Erratum: correction notice", year=2015),
        _row(id="P2018", title="A study on unequal exchange", year=2018),
        _row(id="P2020", title="Recent advances in ecology", year=2020),
        _row(
            id="P2022ACC",
            title="Already accepted paper",
            year=2022,
            curation_status="accepted",
        ),
        _row(
            id="P2023REJ",
            title="Already rejected paper",
            year=2023,
            curation_status="rejected",
        ),
    ]


# ---------------------------------------------------------------------------
# 1. select_ids_by_predicate — núcleo del selector (service layer, sin CLI)
# ---------------------------------------------------------------------------


def test_select_ids_by_predicate_year_gte() -> None:
    """select_ids_by_predicate con year_gte devuelve solo los ids >= el año."""
    from bib2graph.service.curate import select_ids_by_predicate

    rows = _mixed_corpus_rows()
    matched = select_ids_by_predicate(rows, year_gte=2018)

    assert set(matched) == {"P2018", "P2020", "P2022ACC", "P2023REJ"}


def test_select_ids_by_predicate_query() -> None:
    """select_ids_by_predicate con query matchea substring case-insensitive en título."""
    from bib2graph.service.curate import select_ids_by_predicate

    rows = _mixed_corpus_rows()
    matched = select_ids_by_predicate(rows, query="ERRATUM")

    assert matched == ["P2015"]


def test_select_ids_by_predicate_query_y_year_and_logico() -> None:
    """query + year_gte se combinan con AND lógico."""
    from bib2graph.service.curate import select_ids_by_predicate

    rows = _mixed_corpus_rows()
    matched = select_ids_by_predicate(rows, query="paper", year_gte=2020)

    # "paper" está en "Old paper..." (2010, excluido por year), "Already accepted
    # paper" (2022) y "Already rejected paper" (2023).
    assert set(matched) == {"P2022ACC", "P2023REJ"}


def test_select_ids_by_predicate_sin_criterios_devuelve_vacio() -> None:
    """Sin ningún criterio, select_ids_by_predicate no selecciona nada implícito."""
    from bib2graph.service.curate import select_ids_by_predicate

    rows = _mixed_corpus_rows()
    matched = select_ids_by_predicate(rows)

    assert matched == []


def test_select_ids_by_predicate_min_citations() -> None:
    """select_ids_by_predicate con min_citations usa len(cited_by_id) (misma semántica que filter)."""
    from bib2graph.service.curate import select_ids_by_predicate

    rows = [
        _row(id="LOW", cited_by_id=["A"]),
        _row(id="HIGH", cited_by_id=["A", "B", "C"]),
    ]
    matched = select_ids_by_predicate(rows, min_citations=2)

    assert matched == ["HIGH"]


# ---------------------------------------------------------------------------
# 2. accept_papers/reject_papers con selector (service layer)
# ---------------------------------------------------------------------------


def test_accept_papers_con_selector_year_gte(tmp_path: Path) -> None:
    """accept_papers con year_gte marca accepted solo los papers >= el año."""
    from bib2graph.service.curate import accept_papers

    ws = _init_workspace(tmp_path)
    _seed_store(ws, _mixed_corpus_rows())

    data = accept_papers(ws.library_path, [], year_gte=2018)

    assert data["accepted_count"] == 4  # P2018, P2020, P2022ACC (ya accepted), P2023REJ
    statuses = _status_by_id(ws)
    assert statuses["P2010"] == "candidate"
    assert statuses["P2015"] == "candidate"
    assert statuses["P2018"] == "accepted"
    assert statuses["P2020"] == "accepted"
    assert statuses["P2022ACC"] == "accepted"
    assert (
        statuses["P2023REJ"] == "accepted"
    )  # accept por selector SÍ puede revertir reject


def test_reject_papers_con_selector_query(tmp_path: Path) -> None:
    """reject_papers con query marca rejected los papers que matchean el título."""
    from bib2graph.service.curate import reject_papers

    ws = _init_workspace(tmp_path)
    _seed_store(ws, _mixed_corpus_rows())

    data = reject_papers(ws.library_path, [], query="erratum")

    assert data["rejected_count"] == 1
    statuses = _status_by_id(ws)
    assert statuses["P2015"] == "rejected"
    assert statuses["P2010"] == "candidate"


def test_accept_papers_combina_ids_y_selector_union(tmp_path: Path) -> None:
    """accept_papers con --ids + selector afecta la UNIÓN (no intersección)."""
    from bib2graph.service.curate import accept_papers

    ws = _init_workspace(tmp_path)
    _seed_store(ws, _mixed_corpus_rows())

    # --ids P2010 (no matchea selector) + selector year_gte=2020 (P2020, P2022ACC, P2023REJ)
    data = accept_papers(ws.library_path, ["P2010"], year_gte=2020)

    statuses = _status_by_id(ws)
    assert statuses["P2010"] == "accepted"  # vino de --ids
    assert statuses["P2020"] == "accepted"  # vino del selector
    assert statuses["P2022ACC"] == "accepted"
    assert statuses["P2023REJ"] == "accepted"
    assert statuses["P2015"] == "candidate"  # no matchea ninguno de los dos
    assert data["accepted_count"] == 4
    assert data["selector_matched_count"] == 3


def test_accept_papers_solo_ids_sin_selector_comportamiento_previo(
    tmp_path: Path,
) -> None:
    """accept_papers sin ningún criterio de selector se comporta como antes (solo --ids)."""
    from bib2graph.service.curate import accept_papers

    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1"), _row(id="P2")])

    data = accept_papers(ws.library_path, ["P1"])

    assert data["accepted_count"] == 1
    assert data["selector_matched_count"] == 0
    statuses = _status_by_id(ws)
    assert statuses["P1"] == "accepted"
    assert statuses["P2"] == "candidate"


def test_accept_papers_sin_ids_ni_selector_lanza_data_error(tmp_path: Path) -> None:
    """accept_papers sin --ids ni selector lanza DataError (exit 1 vía UsageError en CLI)."""
    from bib2graph.service.curate import accept_papers
    from bib2graph.service.errors import DataError

    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    with pytest.raises(DataError):
        accept_papers(ws.library_path, [])


def test_reject_papers_sin_ids_ni_selector_lanza_data_error(tmp_path: Path) -> None:
    """reject_papers sin --ids ni selector lanza DataError."""
    from bib2graph.service.curate import reject_papers
    from bib2graph.service.errors import DataError

    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    with pytest.raises(DataError):
        reject_papers(ws.library_path, [])


# ---------------------------------------------------------------------------
# 3. curate accept/reject --year-gte / --query (CLI, exit 0)
# ---------------------------------------------------------------------------


def test_cli_curate_accept_year_gte(tmp_path: Path) -> None:
    """b2g curate accept --year-gte 2015 marca accepted solo los >= 2015."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, _mixed_corpus_rows())

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "curate", "accept", "--year-gte", "2015"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output

    statuses = _status_by_id(ws)
    assert statuses["P2010"] == "candidate"
    assert statuses["P2015"] == "accepted"
    assert statuses["P2018"] == "accepted"
    assert statuses["P2020"] == "accepted"


def test_cli_curate_reject_query(tmp_path: Path) -> None:
    """b2g curate reject --query "erratum" rechaza los que matchean el título."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, _mixed_corpus_rows())

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "curate", "reject", "--query", "erratum"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output

    statuses = _status_by_id(ws)
    assert statuses["P2015"] == "rejected"
    assert statuses["P2010"] == "candidate"


def test_cli_curate_accept_combina_ids_y_year_lte(tmp_path: Path) -> None:
    """b2g curate accept --ids + --year-lte combina ids explícitos y selector."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, _mixed_corpus_rows())

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws.root),
            "curate",
            "accept",
            "--ids",
            "P2020",
            "--year-lte",
            "2010",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output

    statuses = _status_by_id(ws)
    assert statuses["P2010"] == "accepted"  # selector year_lte=2010
    assert statuses["P2020"] == "accepted"  # --ids explícito


def test_cli_curate_accept_min_citations_y_type_y_language(tmp_path: Path) -> None:
    """b2g curate accept combina --min-citations, --language y --type (repetibles)."""
    ws = _init_workspace(tmp_path)
    rows = [
        _row(id="EN_HIGH", language="en", cited_by_id=["A", "B", "C"]),
        _row(id="EN_LOW", language="en", cited_by_id=["A"]),
        _row(id="ES_HIGH", language="es", cited_by_id=["A", "B", "C"]),
    ]
    _seed_store(ws, rows)

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws.root),
            "curate",
            "accept",
            "--language",
            "en",
            "--min-citations",
            "2",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output

    statuses = _status_by_id(ws)
    assert statuses["EN_HIGH"] == "accepted"
    assert statuses["EN_LOW"] == "candidate"
    assert statuses["ES_HIGH"] == "candidate"


# ---------------------------------------------------------------------------
# 4. Sin --ids ni selector → error de uso (exit != 0)
# ---------------------------------------------------------------------------


def test_cli_curate_accept_sin_ids_ni_selector_falla(tmp_path: Path) -> None:
    """b2g curate accept sin --ids ni selector falla con exit != 0."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "curate", "accept"],
    )
    assert result.exit_code != 0


def test_cli_curate_reject_sin_ids_ni_selector_falla(tmp_path: Path) -> None:
    """b2g curate reject sin --ids ni selector falla con exit != 0."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "curate", "reject"],
    )
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# 5. --ids solo sigue funcionando (regresión explícita del selector nuevo)
# ---------------------------------------------------------------------------


def test_cli_curate_accept_solo_ids_sigue_funcionando(tmp_path: Path) -> None:
    """b2g curate accept --ids (sin ningún flag de selector) sigue funcionando igual."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1"), _row(id="P2")])

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "curate", "accept", "--ids", "P1", "--json"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout.strip())
    assert data["data"]["accepted_count"] == 1
    assert data["data"]["selector_matched_count"] == 0

    statuses = _status_by_id(ws)
    assert statuses["P1"] == "accepted"
    assert statuses["P2"] == "candidate"


# ---------------------------------------------------------------------------
# 6. Envelope --json con conteos correctos
# ---------------------------------------------------------------------------


def test_cli_curate_accept_json_envelope_conteos(tmp_path: Path) -> None:
    """curate accept --year-gte --json reporta accepted_count y selector_matched_count."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, _mixed_corpus_rows())

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws.root),
            "curate",
            "accept",
            "--year-gte",
            "2020",
            "--json",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["ok"] is True
    assert data["command"] == "curate accept"
    assert data["data"]["accepted_count"] == 3  # P2020, P2022ACC, P2023REJ
    assert data["data"]["selector_matched_count"] == 3
    assert sorted(data["data"]["ids"]) == ["P2020", "P2022ACC", "P2023REJ"]


def test_cli_curate_reject_json_envelope_conteos(tmp_path: Path) -> None:
    """curate reject --query --json reporta rejected_count correcto."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, _mixed_corpus_rows())

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws.root),
            "curate",
            "reject",
            "--query",
            "unequal exchange",
            "--json",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout.strip())
    assert data["data"]["rejected_count"] == 1
    assert data["data"]["ids"] == ["P2018"]


# ---------------------------------------------------------------------------
# 7. curate accept/reject por selector NO transiciona el CycleState
# ---------------------------------------------------------------------------


def test_cli_curate_accept_selector_no_transiciona_fsm(tmp_path: Path) -> None:
    """curate accept por selector es transversal: no transiciona el CycleState."""
    from bib2graph.stores.duckdb import DuckDBStore

    ws = _init_workspace(tmp_path)
    _seed_store(ws, _mixed_corpus_rows())

    store = DuckDBStore(ws.library_path)
    estado_previo = store.backend.loop_state()
    store.close()

    runner = CliRunner()
    runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "curate", "accept", "--year-gte", "2018"],
        catch_exceptions=False,
    )

    store = DuckDBStore(ws.library_path)
    estado_post = store.backend.loop_state()
    store.close()

    assert estado_post == estado_previo
