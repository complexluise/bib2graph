"""Tests del grupo noun-verb ``b2g read`` (sub-issue #156).

Cubre:
1. Servicios nuevos (unit puro, sin Click):
   - ``list_papers``: sin filtros, con --query (CI), --status, is_seed, year.
   - ``corpus_stats``: group_by status/year/is_seed; group_by inválido → DataError.
   - ``get_paper`` extendido: resuelve por id, doi, source_id; inexistente → DataError.

2. CLI ``read list --json``: envelope schema="1", exit 0, data.papers + count.
3. CLI ``read stats --json --group-by <X>``: forma del envelope.
4. CLI ``read show --id <X> --json``: ~14 campos; inexistente → DataError exit 2.
5. ``b2g read`` sin subcomando → ayuda (exit 0).
6. stdout puro: una sola línea JSON, sin ruido.

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
# Helpers compartidos
# ---------------------------------------------------------------------------


def _row(
    *,
    id: str,
    title: str = "Título de prueba",
    year: int | None = 2020,
    is_seed: bool = True,
    curation_status: str = "candidate",
    doi: str | None = None,
    source_id: str | None = None,
    references_id: list[str] | None = None,
    cited_by_id: list[str] | None = None,
) -> dict[str, Any]:
    """Fila mínima con schema completo para tests de read.

    Usa los nombres canónicos del CORPUS_SCHEMA (source_id, no openalex_id).
    """
    return {
        "id": id,
        "source_id": source_id,
        "doi": doi,
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
        "authors_raw": ["Autor A"],
        "authors_id": ["oa:author1"],
        "authors_affiliations": None,
        "keywords_raw": None,
        "keywords_id": None,
        "institutions_raw": None,
        "institutions_id": None,
        "references_id": references_id,
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


# ---------------------------------------------------------------------------
# 1. Servicios — list_papers
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_list_papers_sin_filtros_devuelve_todos(tmp_path: Path) -> None:
    """list_papers sin filtros devuelve todos los papers con campos mínimos."""
    from bib2graph.service.reads import list_papers

    ws = _init_workspace(tmp_path)
    rows = [
        _row(id="P1", title="Paper uno", year=2021),
        _row(id="P2", title="Paper dos", year=2022),
        _row(id="P3", title="Paper tres", year=2023),
    ]
    _seed_store(ws, rows)

    result = list_papers(ws)

    assert result["count"] == 3
    assert len(result["papers"]) == 3
    ids = {p["id"] for p in result["papers"]}
    assert ids == {"P1", "P2", "P3"}
    # Campos mínimos presentes
    for paper in result["papers"]:
        assert "id" in paper
        assert "title" in paper
        assert "year" in paper
        assert "curation_status" in paper
        assert "is_seed" in paper


@pytest.mark.unit
def test_list_papers_query_filtra_por_titulo_ci(tmp_path: Path) -> None:
    """list_papers --query filtra substring case-insensitive en el título."""
    from bib2graph.service.reads import list_papers

    ws = _init_workspace(tmp_path)
    rows = [
        _row(id="P1", title="Unequal Exchange in World Trade"),
        _row(id="P2", title="Capital Accumulation and Growth"),
        _row(id="P3", title="UNEQUAL DISTRIBUTION OF WEALTH"),
    ]
    _seed_store(ws, rows)

    result = list_papers(ws, query="unequal")

    assert result["count"] == 2
    ids = {p["id"] for p in result["papers"]}
    assert ids == {"P1", "P3"}


@pytest.mark.unit
def test_list_papers_status_filtra_por_curation_status(tmp_path: Path) -> None:
    """list_papers filtra por curation_status exacto."""
    from bib2graph.service.reads import list_papers

    ws = _init_workspace(tmp_path)
    rows = [
        _row(id="P1", curation_status="candidate"),
        _row(id="P2", curation_status="accepted"),
        _row(id="P3", curation_status="rejected"),
        _row(id="P4", curation_status="accepted"),
    ]
    _seed_store(ws, rows)

    result = list_papers(ws, status="accepted")

    assert result["count"] == 2
    ids = {p["id"] for p in result["papers"]}
    assert ids == {"P2", "P4"}


@pytest.mark.unit
def test_list_papers_seeds_filtra_is_seed_true(tmp_path: Path) -> None:
    """list_papers con is_seed=True devuelve solo semillas."""
    from bib2graph.service.reads import list_papers

    ws = _init_workspace(tmp_path)
    rows = [
        _row(id="P1", is_seed=True),
        _row(id="P2", is_seed=False),
        _row(id="P3", is_seed=True),
    ]
    _seed_store(ws, rows)

    result = list_papers(ws, is_seed=True)

    assert result["count"] == 2
    assert all(p["is_seed"] is True for p in result["papers"])


@pytest.mark.unit
def test_list_papers_candidates_filtra_is_seed_false(tmp_path: Path) -> None:
    """list_papers con is_seed=False devuelve solo no-semillas."""
    from bib2graph.service.reads import list_papers

    ws = _init_workspace(tmp_path)
    rows = [
        _row(id="P1", is_seed=True),
        _row(id="P2", is_seed=False),
        _row(id="P3", is_seed=False),
    ]
    _seed_store(ws, rows)

    result = list_papers(ws, is_seed=False)

    assert result["count"] == 2
    assert all(p["is_seed"] is False for p in result["papers"])


@pytest.mark.unit
def test_list_papers_year_filtra_por_anio(tmp_path: Path) -> None:
    """list_papers filtra por año exacto."""
    from bib2graph.service.reads import list_papers

    ws = _init_workspace(tmp_path)
    rows = [
        _row(id="P1", year=2019),
        _row(id="P2", year=2021),
        _row(id="P3", year=2021),
        _row(id="P4", year=2023),
    ]
    _seed_store(ws, rows)

    result = list_papers(ws, year=2021)

    assert result["count"] == 2
    ids = {p["id"] for p in result["papers"]}
    assert ids == {"P2", "P3"}


@pytest.mark.unit
def test_list_papers_filtros_combinados(tmp_path: Path) -> None:
    """list_papers combina filtros con AND lógico."""
    from bib2graph.service.reads import list_papers

    ws = _init_workspace(tmp_path)
    rows = [
        _row(id="P1", title="Unequal Exchange", year=2020, curation_status="accepted"),
        _row(id="P2", title="Unequal Trade", year=2021, curation_status="accepted"),
        _row(id="P3", title="Unequal Income", year=2020, curation_status="candidate"),
    ]
    _seed_store(ws, rows)

    result = list_papers(ws, query="unequal", status="accepted", year=2020)

    assert result["count"] == 1
    assert result["papers"][0]["id"] == "P1"


# ---------------------------------------------------------------------------
# 2. Servicios — corpus_stats
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_corpus_stats_group_by_status(tmp_path: Path) -> None:
    """corpus_stats agrupa por curation_status y devuelve conteos correctos."""
    from bib2graph.service.reads import corpus_stats

    ws = _init_workspace(tmp_path)
    rows = [
        _row(id="P1", curation_status="candidate"),
        _row(id="P2", curation_status="accepted"),
        _row(id="P3", curation_status="candidate"),
        _row(id="P4", curation_status="rejected"),
    ]
    _seed_store(ws, rows)

    result = corpus_stats(ws, group_by="status")

    assert result["group_by"] == "status"
    assert result["total"] == 4
    groups_map = {g["key"]: g["count"] for g in result["groups"]}
    assert groups_map["candidate"] == 2
    assert groups_map["accepted"] == 1
    assert groups_map["rejected"] == 1


@pytest.mark.unit
def test_corpus_stats_group_by_year(tmp_path: Path) -> None:
    """corpus_stats agrupa por año."""
    from bib2graph.service.reads import corpus_stats

    ws = _init_workspace(tmp_path)
    rows = [
        _row(id="P1", year=2020),
        _row(id="P2", year=2021),
        _row(id="P3", year=2020),
    ]
    _seed_store(ws, rows)

    result = corpus_stats(ws, group_by="year")

    assert result["group_by"] == "year"
    assert result["total"] == 3
    groups_map = {str(g["key"]): g["count"] for g in result["groups"]}
    assert groups_map["2020"] == 2
    assert groups_map["2021"] == 1


@pytest.mark.unit
def test_corpus_stats_group_by_is_seed(tmp_path: Path) -> None:
    """corpus_stats agrupa por is_seed."""
    from bib2graph.service.reads import corpus_stats

    ws = _init_workspace(tmp_path)
    rows = [
        _row(id="P1", is_seed=True),
        _row(id="P2", is_seed=False),
        _row(id="P3", is_seed=True),
    ]
    _seed_store(ws, rows)

    result = corpus_stats(ws, group_by="is_seed")

    assert result["group_by"] == "is_seed"
    assert result["total"] == 3
    # Cada grupo tiene key=True o key=False y count correspondiente
    assert len(result["groups"]) == 2


@pytest.mark.unit
def test_corpus_stats_group_by_invalido_lanza_dataerror(tmp_path: Path) -> None:
    """corpus_stats con group_by inválido lanza DataError."""
    from bib2graph.service.errors import DataError
    from bib2graph.service.reads import corpus_stats

    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    with pytest.raises(DataError, match="no válido"):
        corpus_stats(ws, group_by="autor")


@pytest.mark.unit
def test_corpus_stats_default_es_status(tmp_path: Path) -> None:
    """corpus_stats sin parámetro usa group_by='status' por defecto."""
    from bib2graph.service.reads import corpus_stats

    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1", curation_status="candidate")])

    result = corpus_stats(ws)

    assert result["group_by"] == "status"
    assert "groups" in result


# ---------------------------------------------------------------------------
# 3. Servicios — get_paper extendido (id | doi | source_id)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_paper_resuelve_por_id(tmp_path: Path) -> None:
    """get_paper resuelve por id interno (comportamiento original)."""
    from bib2graph.service.reads import get_paper

    ws = _init_workspace(tmp_path)
    rows = [_row(id="P1", title="Paper uno", doi="10.1/p1", source_id="W1234")]
    _seed_store(ws, rows)

    result = get_paper(ws, "P1")

    assert result["id"] == "P1"
    assert result["title"] == "Paper uno"


@pytest.mark.unit
def test_get_paper_resuelve_por_doi(tmp_path: Path) -> None:
    """get_paper resuelve por DOI cuando no hay match por id."""
    from bib2graph.service.reads import get_paper

    ws = _init_workspace(tmp_path)
    rows = [_row(id="W123", title="Paper con DOI", doi="10.1016/j.ecolecon.2019")]
    _seed_store(ws, rows)

    result = get_paper(ws, "10.1016/j.ecolecon.2019")

    assert result["id"] == "W123"
    assert result["doi"] == "10.1016/j.ecolecon.2019"


@pytest.mark.unit
def test_get_paper_resuelve_por_source_id(tmp_path: Path) -> None:
    """get_paper resuelve por source_id cuando no hay match por id ni doi."""
    from bib2graph.service.reads import get_paper

    ws = _init_workspace(tmp_path)
    rows = [_row(id="P1", title="Paper con source_id", source_id="W2741809807")]
    _seed_store(ws, rows)

    result = get_paper(ws, "W2741809807")

    assert result["id"] == "P1"
    assert result["source_id"] == "W2741809807"


@pytest.mark.unit
def test_get_paper_prioriza_id_sobre_doi(tmp_path: Path) -> None:
    """Cuando ident coincide con id de un paper y doi de otro, gana el id."""
    from bib2graph.service.reads import get_paper

    ws = _init_workspace(tmp_path)
    # P-DOI tiene id="VALOR" y P2 tiene doi="VALOR"
    rows = [
        _row(id="VALOR", title="Coincide por id", doi="10.1/otro"),
        _row(id="P2", title="Coincide por doi", doi="VALOR"),
    ]
    _seed_store(ws, rows)

    result = get_paper(ws, "VALOR")

    # id gana sobre doi
    assert result["id"] == "VALOR"
    assert result["title"] == "Coincide por id"


@pytest.mark.unit
def test_get_paper_mismo_paper_tres_ids(tmp_path: Path) -> None:
    """El mismo paper es encontrable por id, doi y source_id."""
    from bib2graph.service.reads import get_paper

    ws = _init_workspace(tmp_path)
    rows = [
        _row(
            id="W999",
            title="Paper multi-identificador",
            doi="10.1234/test",
            source_id="W999_openalex",
        )
    ]
    _seed_store(ws, rows)

    by_id = get_paper(ws, "W999")
    by_doi = get_paper(ws, "10.1234/test")
    by_source = get_paper(ws, "W999_openalex")

    assert by_id["id"] == by_doi["id"] == by_source["id"] == "W999"
    assert by_id["title"] == by_doi["title"] == by_source["title"]


@pytest.mark.unit
def test_get_paper_inexistente_lanza_dataerror(tmp_path: Path) -> None:
    """get_paper con ident que no existe lanza DataError."""
    from bib2graph.service.errors import DataError
    from bib2graph.service.reads import get_paper

    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    with pytest.raises(DataError, match="no encontrado"):
        get_paper(ws, "id-que-no-existe")


@pytest.mark.unit
def test_get_paper_devuelve_catorce_campos(tmp_path: Path) -> None:
    """get_paper devuelve los ~14 campos documentados."""
    from bib2graph.service.reads import get_paper

    ws = _init_workspace(tmp_path)
    rows = [
        _row(
            id="P1",
            title="Paper completo",
            year=2022,
            doi="10.1/p1",
            source_id="W001",
            is_seed=True,
            curation_status="accepted",
            references_id=["R1", "R2"],
        )
    ]
    _seed_store(ws, rows)

    result = get_paper(ws, "P1")

    expected_keys = {
        "id",
        "source_id",
        "doi",
        "title",
        "year",
        "abstract",
        "is_seed",
        "curation_status",
        "authors_raw",
        "authors_id",
        "keywords_id",
        "references_id",
        "cited_by_id",
        "provenance",
    }
    for key in expected_keys:
        assert key in result, f"Falta clave: {key}"


# Neutralidad de transporte de service.reads: consolidada en
# test_service.py::test_service_modulo_neutral_de_transporte (epic #184).


# ---------------------------------------------------------------------------
# 5. CLI — read list --json
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_cli_read_list_json_envelope_forma(tmp_path: Path) -> None:
    """read list --json devuelve envelope schema='1', ok=True, data.papers + count."""
    ws = _init_workspace(tmp_path)
    _seed_store(
        ws,
        [
            _row(id="P1", title="Alpha", curation_status="candidate"),
            _row(id="P2", title="Beta", curation_status="accepted"),
        ],
    )

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "read", "list", "--json"],
        catch_exceptions=False,
    )
    data = _assert_one_json_line(result.stdout)

    assert data["ok"] is True
    assert data["command"] == "read list"
    assert data["exit_code"] == 0
    assert "papers" in data["data"]
    assert "count" in data["data"]
    assert data["data"]["count"] == 2


@pytest.mark.unit
def test_cli_read_list_query_filtra(tmp_path: Path) -> None:
    """read list --query filtra por título en el CLI."""
    ws = _init_workspace(tmp_path)
    _seed_store(
        ws,
        [
            _row(id="P1", title="Ecología Política"),
            _row(id="P2", title="Economía Ambiental"),
        ],
    )

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "read", "list", "--query", "ecolog", "--json"],
        catch_exceptions=False,
    )
    data = _assert_one_json_line(result.stdout)

    assert data["data"]["count"] == 1
    assert data["data"]["papers"][0]["id"] == "P1"


@pytest.mark.unit
def test_cli_read_list_status_filtra(tmp_path: Path) -> None:
    """read list --status accepted filtra por curation_status."""
    ws = _init_workspace(tmp_path)
    _seed_store(
        ws,
        [
            _row(id="P1", curation_status="accepted"),
            _row(id="P2", curation_status="candidate"),
            _row(id="P3", curation_status="accepted"),
        ],
    )

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws.root),
            "read",
            "list",
            "--status",
            "accepted",
            "--json",
        ],
        catch_exceptions=False,
    )
    data = _assert_one_json_line(result.stdout)

    assert data["data"]["count"] == 2


@pytest.mark.unit
def test_cli_read_list_seeds_filtra(tmp_path: Path) -> None:
    """read list --seeds filtra a is_seed=True."""
    ws = _init_workspace(tmp_path)
    _seed_store(
        ws,
        [
            _row(id="P1", is_seed=True),
            _row(id="P2", is_seed=False),
        ],
    )

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "read", "list", "--seeds", "--json"],
        catch_exceptions=False,
    )
    data = _assert_one_json_line(result.stdout)

    assert data["data"]["count"] == 1
    assert data["data"]["papers"][0]["id"] == "P1"


@pytest.mark.unit
def test_cli_read_list_candidates_filtra(tmp_path: Path) -> None:
    """read list --candidates filtra a is_seed=False."""
    ws = _init_workspace(tmp_path)
    _seed_store(
        ws,
        [
            _row(id="P1", is_seed=True),
            _row(id="P2", is_seed=False),
            _row(id="P3", is_seed=False),
        ],
    )

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "read", "list", "--candidates", "--json"],
        catch_exceptions=False,
    )
    data = _assert_one_json_line(result.stdout)

    assert data["data"]["count"] == 2


@pytest.mark.unit
def test_cli_read_list_year_filtra(tmp_path: Path) -> None:
    """read list --year filtra por año exacto."""
    ws = _init_workspace(tmp_path)
    _seed_store(
        ws,
        [
            _row(id="P1", year=2020),
            _row(id="P2", year=2021),
        ],
    )

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "read", "list", "--year", "2021", "--json"],
        catch_exceptions=False,
    )
    data = _assert_one_json_line(result.stdout)

    assert data["data"]["count"] == 1
    assert data["data"]["papers"][0]["id"] == "P2"


@pytest.mark.unit
def test_cli_read_list_seeds_candidates_mutuamente_excluyentes(tmp_path: Path) -> None:
    """read list --seeds --candidates → UsageError (exit 1)."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws.root),
            "read",
            "list",
            "--seeds",
            "--candidates",
            "--json",
        ],
        catch_exceptions=False,
    )
    data = _assert_one_json_line(result.stdout)

    assert data["ok"] is False
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# 6. CLI — read stats --json
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_cli_read_stats_json_envelope_forma(tmp_path: Path) -> None:
    """read stats --json devuelve envelope con group_by, total y groups."""
    ws = _init_workspace(tmp_path)
    _seed_store(
        ws,
        [
            _row(id="P1", curation_status="candidate"),
            _row(id="P2", curation_status="accepted"),
        ],
    )

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "read", "stats", "--json"],
        catch_exceptions=False,
    )
    data = _assert_one_json_line(result.stdout)

    assert data["ok"] is True
    assert data["command"] == "read stats"
    payload = data["data"]
    assert "group_by" in payload
    assert "total" in payload
    assert "groups" in payload
    assert payload["total"] == 2


@pytest.mark.unit
def test_cli_read_stats_group_by_year(tmp_path: Path) -> None:
    """read stats --group-by year agrupa por año."""
    ws = _init_workspace(tmp_path)
    _seed_store(
        ws,
        [
            _row(id="P1", year=2020),
            _row(id="P2", year=2021),
            _row(id="P3", year=2020),
        ],
    )

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "read", "stats", "--group-by", "year", "--json"],
        catch_exceptions=False,
    )
    data = _assert_one_json_line(result.stdout)

    payload = data["data"]
    assert payload["group_by"] == "year"
    assert payload["total"] == 3
    groups_map = {str(g["key"]): g["count"] for g in payload["groups"]}
    assert groups_map["2020"] == 2
    assert groups_map["2021"] == 1


@pytest.mark.unit
def test_cli_read_stats_group_by_is_seed(tmp_path: Path) -> None:
    """read stats --group-by is_seed agrupa por semilla."""
    ws = _init_workspace(tmp_path)
    _seed_store(
        ws,
        [
            _row(id="P1", is_seed=True),
            _row(id="P2", is_seed=False),
        ],
    )

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws.root),
            "read",
            "stats",
            "--group-by",
            "is_seed",
            "--json",
        ],
        catch_exceptions=False,
    )
    data = _assert_one_json_line(result.stdout)

    assert data["ok"] is True
    assert data["data"]["group_by"] == "is_seed"
    assert data["data"]["total"] == 2


# ---------------------------------------------------------------------------
# 7. CLI — read show --json
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_cli_read_show_por_id_json(tmp_path: Path) -> None:
    """read show --id <id> devuelve ~14 campos en el envelope."""
    ws = _init_workspace(tmp_path)
    _seed_store(
        ws,
        [
            _row(
                id="P1",
                title="Paper de prueba",
                year=2023,
                doi="10.1/p1",
                source_id="W001",
                is_seed=True,
                curation_status="accepted",
                references_id=["R1"],
            )
        ],
    )

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "read", "show", "--id", "P1", "--json"],
        catch_exceptions=False,
    )
    data = _assert_one_json_line(result.stdout)

    assert data["ok"] is True
    assert data["command"] == "read show"
    assert data["exit_code"] == 0
    payload = data["data"]
    assert payload["id"] == "P1"
    assert payload["title"] == "Paper de prueba"
    assert payload["year"] == 2023
    assert payload["doi"] == "10.1/p1"
    assert payload["source_id"] == "W001"
    assert payload["is_seed"] is True
    assert payload["curation_status"] == "accepted"
    # provenance es lista
    assert isinstance(payload["provenance"], list)


@pytest.mark.unit
def test_cli_read_show_por_doi_json(tmp_path: Path) -> None:
    """read show --id <doi> resuelve por DOI."""
    ws = _init_workspace(tmp_path)
    _seed_store(
        ws,
        [_row(id="W999", title="Paper DOI", doi="10.9999/test")],
    )

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws.root),
            "read",
            "show",
            "--id",
            "10.9999/test",
            "--json",
        ],
        catch_exceptions=False,
    )
    data = _assert_one_json_line(result.stdout)

    assert data["ok"] is True
    assert data["data"]["id"] == "W999"


@pytest.mark.unit
def test_cli_read_show_por_source_id_json(tmp_path: Path) -> None:
    """read show --id <source_id> resuelve por source_id."""
    ws = _init_workspace(tmp_path)
    _seed_store(
        ws,
        [_row(id="P1", title="Paper source_id", source_id="W2741809807")],
    )

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws.root),
            "read",
            "show",
            "--id",
            "W2741809807",
            "--json",
        ],
        catch_exceptions=False,
    )
    data = _assert_one_json_line(result.stdout)

    assert data["ok"] is True
    assert data["data"]["id"] == "P1"


@pytest.mark.unit
def test_cli_read_show_inexistente_dataerror_exit2(tmp_path: Path) -> None:
    """read show --id INEXISTENTE → DataError, ok=False, exit_code=2."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws.root),
            "read",
            "show",
            "--id",
            "INEXISTENTE",
            "--json",
        ],
        catch_exceptions=False,
    )
    data = _assert_one_json_line(result.stdout)

    assert data["ok"] is False
    assert data["exit_code"] == 2
    assert result.exit_code == 2


# ---------------------------------------------------------------------------
# 8. read sin subcomando → imprime ayuda (exit 0)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_cli_read_sin_subcomando_imprime_ayuda() -> None:
    """b2g read sin subcomando → no_args_is_help=True → exit 0 con ayuda."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(b2g, ["read"])
    # no_args_is_help=True hace exit con código 0 y escribe la ayuda
    assert result.exit_code == 0
    assert "list" in result.output
    assert "stats" in result.output
    assert "show" in result.output


# ---------------------------------------------------------------------------
# 9. stdout puro — una sola línea JSON
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_cli_read_list_stdout_una_linea_json(tmp_path: Path) -> None:
    """read list --json: stdout es exactamente una línea no-vacía."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "read", "list", "--json"],
        catch_exceptions=False,
    )
    lineas = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert len(lineas) == 1


@pytest.mark.unit
def test_cli_read_show_stdout_una_linea_json(tmp_path: Path) -> None:
    """read show --json (error o éxito): stdout es exactamente una línea."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "read", "show", "--id", "P1", "--json"],
        catch_exceptions=False,
    )
    lineas = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert len(lineas) == 1


@pytest.mark.unit
def test_cli_read_stats_stdout_una_linea_json(tmp_path: Path) -> None:
    """read stats --json: stdout es exactamente una línea."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1", curation_status="candidate")])

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "read", "stats", "--json"],
        catch_exceptions=False,
    )
    lineas = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert len(lineas) == 1


# ---------------------------------------------------------------------------
# 10. read sin workspace → UsageError → envelope de error (exit 1)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_cli_read_list_sin_workspace_exit1_json() -> None:
    """read list --json sin workspace → UsageError → envelope error, exit 1."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(b2g, ["read", "list", "--json"], catch_exceptions=False)
    data = _assert_one_json_line(result.stdout)
    assert data["ok"] is False
    assert result.exit_code == 1
