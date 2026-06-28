"""Tests de ``b2g read top`` (sub-issue #157).

Cubre:
1. Servicio ``get_top`` — unit puro, sin Click:
   a. ``central`` ordenado por degree_centrality descendente, top N.
   b. ``cocitation`` ordenado por peso descendente con títulos resueltos.
   c. Kind default = ``bibliographic_coupling``.
   d. Kind inválido → DataError.
   e. n <= 0 → DataError.
   f. Co-citación vacía (sin cited_by_id) → exit 0 + bloque vacío +
      reason/fix_command (honest-empty, NO DataError).

2. CLI ``read top --json``:
   a. Envelope schema="1", command="read top", ok=True, exit_code=0.
   b. Forma de ``central`` y ``cocitation`` en data.
   c. ``--kind`` inválido → exit 2 (Click.Choice).
   d. stdout puro: exactamente una línea JSON (#151).

3. Invariante de neutralidad: ``get_top`` no viola la neutralidad de
   transporte de ``service.reads``.

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
    """Fila mínima con schema completo para tests de read top."""
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
# Corpus con bibliographic coupling (3 papers con referencias compartidas)
# ---------------------------------------------------------------------------
#
# P1: refs [R1, R2, R3]  → comparte con P2 (R1, R3) y P3 (R2)
# P2: refs [R1, R3]       → comparte con P1 (R1, R3)
# P3: refs [R2]            → comparte con P1 (R2)
#
# Red bibliographic_coupling:
#   P1-P2 weight=2, P1-P3 weight=1
#   grados: P1=2, P2=1, P3=1
#   degree_centrality (n=3): P1=2/2=1.0, P2=1/2=0.5, P3=1/2=0.5


def _bib_coupling_rows() -> list[dict[str, Any]]:
    return [
        _row(
            id="P1",
            title="Paper Uno — título completo largo",
            references_id=["R1", "R2", "R3"],
        ),
        _row(
            id="P2",
            title="Paper Dos",
            references_id=["R1", "R3"],
        ),
        _row(
            id="P3",
            title="Paper Tres",
            references_id=["R2"],
        ),
    ]


# ---------------------------------------------------------------------------
# Corpus con co-citación
# ---------------------------------------------------------------------------
#
# P1 (seed): cited_by=[C1, C2]
# P2 (seed): cited_by=[C1, C3]
# P3 (seed): cited_by=[C4]
#
# Red cocitation (seeds_only):
#   P1-P2 weight=1 (comparten C1)
#   P1 y P3 no comparten → sin arista
#   P2 y P3 no comparten → sin arista


def _cocitation_rows() -> list[dict[str, Any]]:
    return [
        _row(id="P1", title="Paper Uno Seed", is_seed=True, cited_by_id=["C1", "C2"]),
        _row(id="P2", title="Paper Dos Seed", is_seed=True, cited_by_id=["C1", "C3"]),
        _row(id="P3", title="Paper Tres Seed", is_seed=True, cited_by_id=["C4"]),
    ]


# ---------------------------------------------------------------------------
# 1. Servicio get_top — central ordenado por degree_centrality desc
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_top_central_ordenado_por_degree_desc(tmp_path: Path) -> None:
    """get_top devuelve central ordenado por degree_centrality descendente."""
    from bib2graph.service.reads import get_top

    ws = _init_workspace(tmp_path)
    _seed_store(ws, _bib_coupling_rows())

    result = get_top(ws, n=3, kind="bibliographic_coupling")

    central = result["central"]
    assert len(central) >= 1
    # P1 tiene degree_centrality más alta (conectado a P2 y P3)
    assert central[0]["id"] == "P1"
    assert central[0]["degree_centrality"] >= central[-1]["degree_centrality"]

    # Verificar que el orden es descendente
    dc_values = [node["degree_centrality"] for node in central]
    assert dc_values == sorted(dc_values, reverse=True)


@pytest.mark.unit
def test_get_top_central_top_n_limita(tmp_path: Path) -> None:
    """get_top con n=1 devuelve solo el nodo más central."""
    from bib2graph.service.reads import get_top

    ws = _init_workspace(tmp_path)
    _seed_store(ws, _bib_coupling_rows())

    result = get_top(ws, n=1, kind="bibliographic_coupling")

    assert len(result["central"]) == 1
    assert result["central"][0]["id"] == "P1"
    assert result["top"] == 1


@pytest.mark.unit
def test_get_top_central_tiene_titulo_completo(tmp_path: Path) -> None:
    """get_top resuelve el título completo del corpus (no el label truncado)."""
    from bib2graph.service.reads import get_top

    ws = _init_workspace(tmp_path)
    _seed_store(ws, _bib_coupling_rows())

    result = get_top(ws, n=3, kind="bibliographic_coupling")

    node_map = {n["id"]: n for n in result["central"]}
    # El título de P1 debe ser el completo del corpus
    assert node_map["P1"]["title"] == "Paper Uno — título completo largo"
    assert "id" in node_map["P1"]
    assert "degree_centrality" in node_map["P1"]


# ---------------------------------------------------------------------------
# 2. Servicio get_top — cocitación por peso desc con títulos resueltos
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_top_cocitacion_con_titulos_resueltos(tmp_path: Path) -> None:
    """get_top resuelve source_title y target_title desde el corpus."""
    from bib2graph.service.reads import get_top

    ws = _init_workspace(tmp_path)
    _seed_store(ws, _cocitation_rows())

    result = get_top(ws, n=5, kind="cocitation")

    # Corpus con cited_by_id → cocitation no debería estar vacío
    # P1 y P2 comparten C1 → 1 par en cocitation
    assert len(result["cocitation"]) >= 1

    pair = result["cocitation"][0]
    assert "source" in pair
    assert "source_title" in pair
    assert "target" in pair
    assert "target_title" in pair
    assert "weight" in pair

    # Los ids deben ser P1 o P2
    pair_ids = {pair["source"], pair["target"]}
    assert pair_ids == {"P1", "P2"}

    # Los títulos deben ser los del corpus
    titles = {pair["source_title"], pair["target_title"]}
    assert "Paper Uno Seed" in titles
    assert "Paper Dos Seed" in titles


@pytest.mark.unit
def test_get_top_cocitacion_por_peso_desc(tmp_path: Path) -> None:
    """get_top ordena los pares de co-citación por peso descendente."""
    from bib2graph.service.reads import get_top

    # Corpus con múltiples pares y pesos variados
    # P1 y P2 comparten C1 y C2 → weight=2
    # P1 y P3 comparten C3 → weight=1
    rows = [
        _row(id="P1", title="P1", is_seed=True, cited_by_id=["C1", "C2", "C3"]),
        _row(id="P2", title="P2", is_seed=True, cited_by_id=["C1", "C2"]),
        _row(id="P3", title="P3", is_seed=True, cited_by_id=["C3"]),
    ]
    ws = _init_workspace(tmp_path)
    _seed_store(ws, rows)

    result = get_top(ws, n=5, kind="cocitation")

    cocitation = result["cocitation"]
    assert len(cocitation) >= 2

    # Verificar orden descendente por peso
    weights = [p["weight"] for p in cocitation]
    assert weights == sorted(weights, reverse=True)

    # El par con mayor peso (P1-P2, weight=2) debe ser el primero
    first = cocitation[0]
    assert {first["source"], first["target"]} == {"P1", "P2"}
    assert first["weight"] == 2


# ---------------------------------------------------------------------------
# 3. Kind default = bibliographic_coupling
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_top_kind_default_es_bibliographic_coupling(tmp_path: Path) -> None:
    """get_top sin kind explícito usa bibliographic_coupling."""
    from bib2graph.service.reads import get_top

    ws = _init_workspace(tmp_path)
    _seed_store(ws, _bib_coupling_rows())

    result = get_top(ws)  # sin kind ni n → defaults

    assert result["kind"] == "bibliographic_coupling"
    assert result["top"] == 10


# ---------------------------------------------------------------------------
# 4. Kind inválido → DataError
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_top_kind_invalido_lanza_dataerror(tmp_path: Path) -> None:
    """get_top con kind no reconocido lanza DataError (defensa del servicio)."""
    from bib2graph.service.errors import DataError
    from bib2graph.service.reads import get_top

    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    with pytest.raises(DataError, match="no reconocido"):
        get_top(ws, kind="red_inventada")


# ---------------------------------------------------------------------------
# 5. n <= 0 → DataError
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_top_n_cero_lanza_dataerror(tmp_path: Path) -> None:
    """get_top con n=0 lanza DataError (n debe ser positivo)."""
    from bib2graph.service.errors import DataError
    from bib2graph.service.reads import get_top

    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    with pytest.raises(DataError, match="positivo"):
        get_top(ws, n=0)


@pytest.mark.unit
def test_get_top_n_negativo_lanza_dataerror(tmp_path: Path) -> None:
    """get_top con n negativo lanza DataError."""
    from bib2graph.service.errors import DataError
    from bib2graph.service.reads import get_top

    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    with pytest.raises(DataError, match="positivo"):
        get_top(ws, n=-5)


# ---------------------------------------------------------------------------
# 6. Co-citación vacía (sin cited_by_id) → honest-empty, NO DataError
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_top_cocitacion_vacia_es_honest_empty(tmp_path: Path) -> None:
    """get_top con corpus sin cited_by_id devuelve cocitation=[] + reason/fix_command.

    Este test verifica explícitamente que NO se lanza DataError cuando la red
    de co-citación está vacía (error común: devolver exit 2 en vez de exit 0).
    """
    from bib2graph.service.reads import get_top

    # Corpus solo con references_id (bib. coupling OK) pero sin cited_by_id
    ws = _init_workspace(tmp_path)
    _seed_store(ws, _bib_coupling_rows())  # filas sin cited_by_id

    # NO debe lanzar DataError ni ninguna excepción
    result = get_top(ws, n=5, kind="bibliographic_coupling")

    assert result["cocitation"] == []
    # Debe incluir reason y fix_command (honest-empty)
    assert "reason" in result, "Se esperaba 'reason' cuando co-citación está vacía"
    assert "fix_command" in result, (
        "Se esperaba 'fix_command' cuando co-citación está vacía"
    )
    assert result["fix_command"] is not None
    # El fix_command debe apuntar al enriquecimiento
    assert "enrich" in str(result["fix_command"]).lower()


@pytest.mark.unit
def test_get_top_cocitacion_vacia_kind_cocitation_honest_empty(
    tmp_path: Path,
) -> None:
    """get_top con kind=cocitation y corpus sin cited_by_id → honest-empty."""
    from bib2graph.service.reads import get_top

    ws = _init_workspace(tmp_path)
    # Corpus sin cited_by_id en ningún paper
    _seed_store(
        ws,
        [
            _row(id="P1", title="Paper 1", cited_by_id=None),
            _row(id="P2", title="Paper 2", cited_by_id=None),
        ],
    )

    result = get_top(ws, n=5, kind="cocitation")

    assert result["central"] == []  # cocitation sin datos → sin nodos
    assert result["cocitation"] == []
    assert "reason" in result
    assert "fix_command" in result


@pytest.mark.unit
def test_get_top_cocitacion_llena_no_tiene_reason(tmp_path: Path) -> None:
    """get_top con co-citación no vacía NO incluye reason ni fix_command."""
    from bib2graph.service.reads import get_top

    ws = _init_workspace(tmp_path)
    _seed_store(ws, _cocitation_rows())

    result = get_top(ws, n=5, kind="cocitation")

    # Con datos de co-citación, no debe haber reason
    assert "reason" not in result
    assert "fix_command" not in result


# ---------------------------------------------------------------------------
# 7. CLI read top --json — forma del envelope
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_cli_read_top_json_envelope_forma(tmp_path: Path) -> None:
    """read top --json devuelve envelope schema='1', ok=True, command='read top'."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, _bib_coupling_rows())

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "read", "top", "--json"],
        catch_exceptions=False,
    )
    data = _assert_one_json_line(result.stdout)

    assert data["ok"] is True
    assert data["command"] == "read top"
    assert data["exit_code"] == 0
    assert "central" in data["data"]
    assert "cocitation" in data["data"]
    assert "kind" in data["data"]
    assert "top" in data["data"]
    assert data["data"]["kind"] == "bibliographic_coupling"
    assert data["data"]["top"] == 10


@pytest.mark.unit
def test_cli_read_top_json_top_n_flag(tmp_path: Path) -> None:
    """read top --top 2 --json respeta el valor de --top."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, _bib_coupling_rows())

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "read", "top", "--top", "2", "--json"],
        catch_exceptions=False,
    )
    data = _assert_one_json_line(result.stdout)

    assert data["ok"] is True
    assert data["data"]["top"] == 2
    assert len(data["data"]["central"]) <= 2


@pytest.mark.unit
def test_cli_read_top_json_n_shorthand(tmp_path: Path) -> None:
    """read top -n 1 --json funciona como alias de --top."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, _bib_coupling_rows())

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "read", "top", "-n", "1", "--json"],
        catch_exceptions=False,
    )
    data = _assert_one_json_line(result.stdout)

    assert data["ok"] is True
    assert data["data"]["top"] == 1
    assert len(data["data"]["central"]) <= 1


@pytest.mark.unit
def test_cli_read_top_json_kind_cocitation(tmp_path: Path) -> None:
    """read top --kind cocitation --json usa la red de co-citación para central."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, _cocitation_rows())

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws.root),
            "read",
            "top",
            "--kind",
            "cocitation",
            "--json",
        ],
        catch_exceptions=False,
    )
    data = _assert_one_json_line(result.stdout)

    assert data["ok"] is True
    assert data["data"]["kind"] == "cocitation"


# ---------------------------------------------------------------------------
# 8. CLI read top con co-citación vacía → exit 0 + bloque vacío (NOT exit 2)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_cli_read_top_cocitacion_vacia_exit0(tmp_path: Path) -> None:
    """read top con corpus sin cited_by_id → exit 0 + cocitation vacía.

    Verifica el invariante honest-empty desde el CLI: co-citación vacía
    NO debe producir exit 2 (DataError).
    """
    ws = _init_workspace(tmp_path)
    _seed_store(ws, _bib_coupling_rows())  # sin cited_by_id

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "read", "top", "--json"],
        catch_exceptions=False,
    )
    data = _assert_one_json_line(result.stdout)

    # Exit 0, ok=True — NO DataError
    assert result.exit_code == 0, (
        f"Se esperaba exit 0 (honest-empty), se obtuvo {result.exit_code}.\n"
        f"stdout: {result.stdout!r}"
    )
    assert data["ok"] is True
    assert data["exit_code"] == 0
    assert data["data"]["cocitation"] == []
    # reason y fix_command deben estar en data
    assert "reason" in data["data"]
    assert "fix_command" in data["data"]


# ---------------------------------------------------------------------------
# 9. CLI --kind inválido → exit 2 (Click.Choice intercepta antes del handler)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_cli_read_top_kind_invalido_exit_nonzero(tmp_path: Path) -> None:
    """read top --kind inválido → Click.Choice → exit no-cero."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws.root),
            "read",
            "top",
            "--kind",
            "red_inventada",
            "--json",
        ],
    )
    # Click.Choice intercepta antes de que el handler lo vea → exit no-cero
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# 10. stdout puro — exactamente una línea JSON (#151)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_cli_read_top_stdout_una_linea_json(tmp_path: Path) -> None:
    """read top --json: stdout es exactamente una línea no-vacía."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, _bib_coupling_rows())

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "read", "top", "--json"],
        catch_exceptions=False,
    )
    lineas = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert len(lineas) == 1, (
        f"Se esperaba exactamente 1 línea en stdout, se obtuvieron {len(lineas)}:\n"
        f"{result.stdout!r}"
    )


@pytest.mark.unit
def test_cli_read_top_stdout_una_linea_json_cocitacion_vacia(
    tmp_path: Path,
) -> None:
    """read top --json con co-citación vacía: sigue siendo 1 línea JSON."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, _bib_coupling_rows())

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "read", "top", "--json"],
        catch_exceptions=False,
    )
    lineas = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert len(lineas) == 1


# Neutralidad de transporte de service.reads (incl. get_top): consolidada en
# test_service.py::test_service_modulo_neutral_de_transporte (epic #184).
