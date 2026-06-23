"""Tests TDD del Ciclo A — ``b2g seed --from-bib`` + filtro de año real.

Casos cubiertos (encuadre del architect, issue #50):

1. run_seed_from_bib: siembra desde .bib, persiste, SEEDED, is_seed/curation_status.
2. run_seed_from_bib: campos faltantes en el .bib (parser defensivo) no rompen.
3. run_seed_from_bib: exit 3 si bibtexparser no está (DependencyError).
4. run_seed_from_bib: archivo .bib inexistente → DataError.
5. run_seed_from_bib: reseed si ya había estado previo.
6. Mutua exclusión de 3 modos (CLI):
   - 0 modos → UsageError
   - 2 modos (--equation + --from-bib) → UsageError
   - 3 modos → UsageError
   - --from-bib + flag OpenAlex (--exclude) → UsageError
   - --from-bib + --min-year → UsageError
   - --from-bib + --native → UsageError
7. Filtro de año: --min-year incluye from_publication_date en el filter enviado a OpenAlex.
8. Filtro de año: --max-year incluye to_publication_date en el filter.
9. Filtro de año: ambos juntos (--min-year + --max-year).
10. Filtro de año: sin año, el filter no incluye cláusulas de fecha.
11. Filtro de año vía --spec equation.yaml con min_year/max_year.
12. envelope --json de --from-bib: tiene papers_added/total_papers/round/reseeded;
    NO tiene executed_query ni translation_report.

Filosofía (AGENTS.md): se testea la FUNCIÓN detrás del comando, no el parser Click.
CliRunner solo donde hay integración de flag necesaria (mutua exclusión, envelopes).
Marcador: ``unit`` (DuckDB en tmp_path, sin red real; MockTransport para OA).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers y fixtures
# ---------------------------------------------------------------------------

SAMPLE_WORKS: list[dict[str, Any]] = json.loads(
    (Path(__file__).parent.parent / "fixtures" / "sample_works.json").read_text(
        encoding="utf-8"
    )
)


def _make_mock_transport(
    works: list[dict[str, Any]] | None = None,
) -> httpx.MockTransport:
    """MockTransport que responde con los works dados (1 página + EOF)."""
    if works is None:
        works = SAMPLE_WORKS
    calls: list[int] = [0]

    def handler(request: httpx.Request) -> httpx.Response:
        calls[0] += 1
        if calls[0] == 1:
            body = {
                "results": works,
                "meta": {"count": len(works), "next_cursor": None},
            }
        else:
            body = {"results": [], "meta": {"count": 0, "next_cursor": None}}
        return httpx.Response(
            200,
            json=body,
            headers={"x-openalex-api-version": "2026-06-17"},
        )

    return httpx.MockTransport(handler)


def _make_capturing_transport() -> tuple[httpx.MockTransport, list[str]]:
    """MockTransport que captura el parámetro 'filter' de las requests.

    Devuelve el transport y una lista donde se acumulan los valores del
    parámetro ``filter`` de cada request (para afirmar sobre el contenido).
    """
    captured_filters: list[str] = []
    calls: list[int] = [0]

    def handler(request: httpx.Request) -> httpx.Response:
        calls[0] += 1
        # Capturar el parámetro filter de la URL
        params = dict(request.url.params)
        filter_val = params.get("filter", "")
        captured_filters.append(filter_val)

        if calls[0] == 1:
            body = {
                "results": SAMPLE_WORKS,
                "meta": {"count": len(SAMPLE_WORKS), "next_cursor": None},
            }
        else:
            body = {"results": [], "meta": {"count": 0, "next_cursor": None}}
        return httpx.Response(
            200,
            json=body,
            headers={"x-openalex-api-version": "2026-06-17"},
        )

    return httpx.MockTransport(handler), captured_filters


# Archivo .bib mínimo con campos completos
BIB_COMPLETO = """\
@article{martinez2010,
  author    = {Martínez-Alier, Joan and Muradian, Roldan},
  title     = {Ecological Economics from the Ground Up},
  journal   = {Ecological Economics},
  year      = {2010},
  doi       = {10.1016/j.ecolecon.2010.02.003},
  abstract  = {This paper reviews ecological economics.},
  keywords  = {ecological economics; social metabolism},
  publisher = {Elsevier},
}

@article{hornborg2009,
  author    = {Hornborg, Alf},
  title     = {Zero-Sum World: Challenges in Conceptualizing Environmental Load Displacement},
  journal   = {International Journal of Comparative Sociology},
  year      = {2009},
  doi       = {10.1177/0020715209105141},
  keywords  = {ecologically unequal exchange; world-system},
}
"""

# Archivo .bib con campos faltantes variados (ejercita parser defensivo)
BIB_CON_FALTANTES = """\
@article{completo,
  author    = {Autor, Uno},
  title     = {Paper Con Todos Los Campos},
  journal   = {Test Journal},
  year      = {2020},
  doi       = {10.1234/completo},
  abstract  = {Resumen completo.},
  keywords  = {keyword1; keyword2},
}

@article{sin_abstract,
  author    = {Autor, Dos},
  title     = {Paper Sin Abstract},
  journal   = {Test Journal},
  year      = {2021},
  doi       = {10.1234/sinabstract},
}

@article{sin_keywords,
  author    = {Autor, Tres},
  title     = {Paper Sin Keywords},
  journal   = {Test Journal},
  year      = {2022},
  abstract  = {Tiene abstract pero no tiene keywords.},
}

@article{sin_doi,
  author    = {Autor, Cuatro},
  title     = {Paper Sin DOI},
  journal   = {Test Journal},
  year      = {2019},
  abstract  = {Sin DOI pero con abstract.},
}

@article{sin_autores,
  title     = {Paper Sin Autores},
  journal   = {Test Journal},
  year      = {2018},
  abstract  = {Entrada sin campo author.},
}

@article{sin_anio,
  author    = {Autor, Seis},
  title     = {Paper Sin Anio},
  journal   = {Test Journal},
  abstract  = {Sin campo year.},
}
"""

# .bib sin título (debe omitirse, no romper)
BIB_SIN_TITULO = """\
@article{sin_titulo,
  author = {Autor, Siete},
  year   = {2020},
  journal = {Journal X},
}
"""


def _make_bib_file(tmp_path: Path, content: str, name: str = "test.bib") -> Path:
    """Escribe un archivo .bib en tmp_path y devuelve la ruta."""
    bib_file = tmp_path / name
    bib_file.write_text(content, encoding="utf-8")
    return bib_file


# ---------------------------------------------------------------------------
# 1. run_seed_from_bib: siembra básica, estado SEEDED, is_seed/curation_status
# ---------------------------------------------------------------------------


def test_run_seed_from_bib_siembra_y_transiciona_a_seeded(tmp_path: Path) -> None:
    """run_seed_from_bib persiste papers y transiciona el store a SEEDED."""
    from bib2graph.cli.commands.seed import run_seed_from_bib
    from bib2graph.cycle import CycleState
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "test.duckdb"
    bib_file = _make_bib_file(tmp_path, BIB_COMPLETO)

    data = run_seed_from_bib(store_path, bib_file)

    assert data["papers_added"] == 2
    assert data["total_papers"] == 2
    assert data["round"] == 1
    assert data["reseeded"] is False

    # Verificar que el store tiene el estado SEEDED
    store = DuckDBStore(store_path)
    assert store.backend.loop_state() == CycleState.SEEDED

    # Verificar is_seed y curation_status en todos los papers
    corpus = store.load()
    rows = corpus.to_arrow().to_pylist()
    assert len(rows) == 2
    for row in rows:
        assert row["is_seed"] is True
        assert row["curation_status"] == "candidate"


def test_run_seed_from_bib_devuelve_claves_esperadas(tmp_path: Path) -> None:
    """run_seed_from_bib devuelve exactamente papers_added/total_papers/round/reseeded."""
    from bib2graph.cli.commands.seed import run_seed_from_bib

    store_path = tmp_path / "test.duckdb"
    bib_file = _make_bib_file(tmp_path, BIB_COMPLETO)

    data = run_seed_from_bib(store_path, bib_file)

    assert set(data.keys()) == {"papers_added", "total_papers", "round", "reseeded"}
    # No deben estar las claves de OpenAlex
    assert "executed_query" not in data
    assert "translation_report" not in data


# ---------------------------------------------------------------------------
# 2. run_seed_from_bib: campos faltantes (parser defensivo)
# ---------------------------------------------------------------------------


def test_run_seed_from_bib_campos_faltantes_no_rompen(tmp_path: Path) -> None:
    """Campos opcionales ausentes en el .bib no generan errores."""
    from bib2graph.cli.commands.seed import run_seed_from_bib

    store_path = tmp_path / "test.duckdb"
    bib_file = _make_bib_file(tmp_path, BIB_CON_FALTANTES)

    # No debe lanzar excepciones
    data = run_seed_from_bib(store_path, bib_file)

    # 6 entradas en el .bib, todas con título → 6 papers
    assert data["papers_added"] == 6
    assert data["total_papers"] == 6


def test_run_seed_from_bib_entry_sin_titulo_se_omite(tmp_path: Path) -> None:
    """Entradas sin título se omiten silenciosamente (no rompen el corpus)."""
    from bib2graph.cli.commands.seed import run_seed_from_bib

    store_path = tmp_path / "test.duckdb"
    bib_file = _make_bib_file(tmp_path, BIB_SIN_TITULO)

    # Contrato R5: avisar (UserWarning), no fallar en silencio.
    with pytest.warns(UserWarning):
        data = run_seed_from_bib(store_path, bib_file)

    # La entrada sin título debe omitirse → 0 papers
    assert data["papers_added"] == 0
    assert data["total_papers"] == 0


def test_run_seed_from_bib_campos_opcionales_son_none(tmp_path: Path) -> None:
    """Campos opcionales ausentes quedan None en el corpus (sin KeyError)."""
    from bib2graph.cli.commands.seed import run_seed_from_bib
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "test.duckdb"
    # Solo una entrada con los campos mínimos (título + journal + año)
    bib_minimo = """\
@article{minimo,
  title   = {Paper Minimo},
  journal = {Journal X},
  year    = {2020},
}
"""
    bib_file = _make_bib_file(tmp_path, bib_minimo)

    run_seed_from_bib(store_path, bib_file)

    corpus = DuckDBStore(store_path).load()
    rows = corpus.to_arrow().to_pylist()
    assert len(rows) == 1
    row = rows[0]

    # Campos opcionales deben ser None (no KeyError, no dato inventado)
    assert row["doi"] is None
    assert row["abstract"] is None
    assert row["keywords_raw"] is None
    assert row["authors_raw"] is None


# ---------------------------------------------------------------------------
# 3. exit 3 si bibtexparser no está (DependencyError)
# ---------------------------------------------------------------------------


def test_run_seed_from_bib_sin_bibtexparser_lanza_dependency_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sin bibtexparser, run_seed_from_bib lanza DependencyError (exit 3)."""
    from bib2graph.cli._errors import DependencyError
    from bib2graph.cli.commands.seed import run_seed_from_bib

    store_path = tmp_path / "test.duckdb"
    bib_file = _make_bib_file(tmp_path, BIB_COMPLETO)

    # Simular ausencia de bibtexparser
    monkeypatch.setitem(sys.modules, "bibtexparser", None)  # type: ignore[call-overload]
    monkeypatch.setitem(sys.modules, "bibtexparser.bparser", None)  # type: ignore[call-overload]
    monkeypatch.setitem(sys.modules, "bibtexparser.customization", None)  # type: ignore[call-overload]

    with pytest.raises(DependencyError) as exc_info:
        run_seed_from_bib(store_path, bib_file)

    assert exc_info.value.exit_code == 3
    assert "bibtexparser" in exc_info.value.message.lower()
    assert "bibtex" in exc_info.value.message.lower()


def test_seed_from_bib_cli_sin_bibtexparser_emite_exit_3(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """b2g seed --from-bib sin bibtexparser → exit 3 en el CLI."""
    from click.testing import CliRunner

    from bib2graph.cli import b2g
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / "ws"
    Workspace.init(ws_dir, "test")
    bib_file = _make_bib_file(tmp_path, BIB_COMPLETO)

    monkeypatch.setitem(sys.modules, "bibtexparser", None)  # type: ignore[call-overload]
    monkeypatch.setitem(sys.modules, "bibtexparser.bparser", None)  # type: ignore[call-overload]
    monkeypatch.setitem(sys.modules, "bibtexparser.customization", None)  # type: ignore[call-overload]

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws_dir),
            "seed",
            "--from-bib",
            str(bib_file),
            "--json",
        ],
    )

    assert result.exit_code == 3, f"Se esperaba exit 3, salida: {result.output}"
    envelope = json.loads(result.output)
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "DEPENDENCY_ERROR"


# ---------------------------------------------------------------------------
# 4. run_seed_from_bib: archivo .bib inexistente → DataError
# ---------------------------------------------------------------------------


def test_run_seed_from_bib_archivo_inexistente_lanza_data_error(
    tmp_path: Path,
) -> None:
    """run_seed_from_bib con ruta inexistente → DataError (exit 2)."""
    from bib2graph.cli._errors import DataError
    from bib2graph.cli.commands.seed import run_seed_from_bib

    store_path = tmp_path / "test.duckdb"

    with pytest.raises(DataError) as exc_info:
        run_seed_from_bib(store_path, tmp_path / "no_existe.bib")

    assert exc_info.value.exit_code == 2


# ---------------------------------------------------------------------------
# 5. run_seed_from_bib: reseed si ya había estado previo
# ---------------------------------------------------------------------------


def test_run_seed_from_bib_reseed_incrementa_ronda(tmp_path: Path) -> None:
    """Segunda siembra con --from-bib es un reseed: ronda++ y reseeded=True."""
    from bib2graph.cli.commands.seed import run_seed_from_bib
    from bib2graph.cycle import CycleState
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "test.duckdb"
    bib_file = _make_bib_file(tmp_path, BIB_COMPLETO)

    # Primera siembra
    data1 = run_seed_from_bib(store_path, bib_file)
    assert data1["round"] == 1
    assert data1["reseeded"] is False

    # Segunda siembra (reseed)
    bib_file2 = _make_bib_file(tmp_path, BIB_CON_FALTANTES, name="test2.bib")
    data2 = run_seed_from_bib(store_path, bib_file2)

    assert data2["reseeded"] is True
    assert data2["round"] == 2

    store = DuckDBStore(store_path)
    assert store.backend.loop_state() == CycleState.SEEDED


# ---------------------------------------------------------------------------
# 6. Mutua exclusión de 3 modos (CliRunner)
# ---------------------------------------------------------------------------


def test_seed_sin_modo_usage_error(tmp_path: Path) -> None:
    """b2g seed sin ningún modo → UsageError (exit 1)."""
    from click.testing import CliRunner

    from bib2graph.cli import b2g
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / "ws"
    Workspace.init(ws_dir, "test")

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        ["--workspace", str(ws_dir), "seed", "--json"],
    )

    assert result.exit_code == 1
    envelope = json.loads(result.output)
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "USAGE_ERROR"


def test_seed_equation_y_from_bib_usage_error(tmp_path: Path) -> None:
    """--equation y --from-bib juntos → UsageError (exit 1)."""
    from click.testing import CliRunner

    from bib2graph.cli import b2g
    from bib2graph.workspace import Workspace

    bib_file = _make_bib_file(tmp_path, BIB_COMPLETO)
    ws_dir = tmp_path / "ws"
    Workspace.init(ws_dir, "test")
    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws_dir),
            "seed",
            "--equation",
            "unequal exchange",
            "--from-bib",
            str(bib_file),
            "--json",
        ],
    )

    assert result.exit_code == 1
    envelope = json.loads(result.output)
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "USAGE_ERROR"
    assert (
        "--from-bib" in envelope["error"]["message"]
        or "--equation" in envelope["error"]["message"]
    )


def test_seed_spec_y_from_bib_usage_error(tmp_path: Path) -> None:
    """--spec y --from-bib juntos → UsageError (exit 1)."""
    from click.testing import CliRunner

    from bib2graph.cli import b2g
    from bib2graph.workspace import Workspace

    spec_file = tmp_path / "eq.yaml"
    spec_file.write_text("equation:\n  query: 'algo'\n", encoding="utf-8")
    bib_file = _make_bib_file(tmp_path, BIB_COMPLETO)
    ws_dir = tmp_path / "ws"
    Workspace.init(ws_dir, "test")

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws_dir),
            "seed",
            "--spec",
            str(spec_file),
            "--from-bib",
            str(bib_file),
            "--json",
        ],
    )

    assert result.exit_code == 1
    envelope = json.loads(result.output)
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "USAGE_ERROR"


def test_seed_from_bib_con_exclude_usage_error(tmp_path: Path) -> None:
    """--from-bib + --exclude → UsageError (exit 1): flags OpenAlex incompatibles."""
    from click.testing import CliRunner

    from bib2graph.cli import b2g
    from bib2graph.workspace import Workspace

    bib_file = _make_bib_file(tmp_path, BIB_COMPLETO)
    ws_dir = tmp_path / "ws"
    Workspace.init(ws_dir, "test")
    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws_dir),
            "seed",
            "--from-bib",
            str(bib_file),
            "--exclude",
            "stock exchange",
            "--json",
        ],
    )

    assert result.exit_code == 1
    envelope = json.loads(result.output)
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "USAGE_ERROR"
    assert "--exclude" in envelope["error"]["message"]


def test_seed_from_bib_con_min_year_usage_error(tmp_path: Path) -> None:
    """--from-bib + --min-year → UsageError (exit 1)."""
    from click.testing import CliRunner

    from bib2graph.cli import b2g
    from bib2graph.workspace import Workspace

    bib_file = _make_bib_file(tmp_path, BIB_COMPLETO)
    ws_dir = tmp_path / "ws"
    Workspace.init(ws_dir, "test")
    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws_dir),
            "seed",
            "--from-bib",
            str(bib_file),
            "--min-year",
            "2010",
            "--json",
        ],
    )

    assert result.exit_code == 1
    envelope = json.loads(result.output)
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "USAGE_ERROR"
    assert "--min-year" in envelope["error"]["message"]


def test_seed_from_bib_con_native_usage_error(tmp_path: Path) -> None:
    """--from-bib + --native → UsageError (exit 1)."""
    from click.testing import CliRunner

    from bib2graph.cli import b2g
    from bib2graph.workspace import Workspace

    bib_file = _make_bib_file(tmp_path, BIB_COMPLETO)
    ws_dir = tmp_path / "ws"
    Workspace.init(ws_dir, "test")
    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws_dir),
            "seed",
            "--from-bib",
            str(bib_file),
            "--native",
            "--json",
        ],
    )

    assert result.exit_code == 1
    envelope = json.loads(result.output)
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "USAGE_ERROR"
    assert "--native" in envelope["error"]["message"]


# ---------------------------------------------------------------------------
# 7-10. Filtro de año: el filter enviado a OpenAlex incluye cláusulas de fecha
# ---------------------------------------------------------------------------


def test_filtro_min_year_incluye_from_publication_date(tmp_path: Path) -> None:
    """Con --min-year, el filter enviado a OpenAlex incluye from_publication_date."""
    from bib2graph.cli.commands.seed import run_seed

    store_path = tmp_path / "test.duckdb"
    transport, captured = _make_capturing_transport()

    run_seed(store_path, "ecology", transport=transport, min_year=2010)

    assert captured, "No se capturó ningún filter"
    filter_enviado = captured[0]
    assert "from_publication_date:2010-01-01" in filter_enviado


def test_filtro_max_year_incluye_to_publication_date(tmp_path: Path) -> None:
    """Con --max-year, el filter enviado a OpenAlex incluye to_publication_date."""
    from bib2graph.cli.commands.seed import run_seed

    store_path = tmp_path / "test.duckdb"
    transport, captured = _make_capturing_transport()

    run_seed(store_path, "ecology", transport=transport, max_year=2020)

    assert captured
    filter_enviado = captured[0]
    assert "to_publication_date:2020-12-31" in filter_enviado


def test_filtro_ambos_anios(tmp_path: Path) -> None:
    """Con min_year y max_year juntos, el filter incluye ambas cláusulas de fecha."""
    from bib2graph.cli.commands.seed import run_seed

    store_path = tmp_path / "test.duckdb"
    transport, captured = _make_capturing_transport()

    run_seed(store_path, "ecology", transport=transport, min_year=2005, max_year=2022)

    assert captured
    filter_enviado = captured[0]
    assert "from_publication_date:2005-01-01" in filter_enviado
    assert "to_publication_date:2022-12-31" in filter_enviado


def test_filtro_sin_anio_no_incluye_cláusulas_de_fecha(tmp_path: Path) -> None:
    """Sin min_year ni max_year, el filter NO incluye cláusulas from/to_publication_date."""
    from bib2graph.cli.commands.seed import run_seed

    store_path = tmp_path / "test.duckdb"
    transport, captured = _make_capturing_transport()

    run_seed(store_path, "ecology", transport=transport)

    assert captured
    filter_enviado = captured[0]
    assert "publication_date" not in filter_enviado


def test_filtro_anio_reportado_en_translation_report(tmp_path: Path) -> None:
    """El translation_report menciona el filtro de año cuando se aplica."""
    from bib2graph.cli.commands.seed import run_seed

    store_path = tmp_path / "test.duckdb"
    transport = _make_mock_transport()

    data = run_seed(store_path, "ecology", transport=transport, min_year=2000)

    # Debe haber al menos un reporte que mencione el año
    report_str = " ".join(data.get("translation_report", []))
    assert "2000" in report_str or "publication_date" in report_str


# ---------------------------------------------------------------------------
# 11. Filtro de año vía --spec equation.yaml con min_year/max_year
# ---------------------------------------------------------------------------


def test_filtro_anio_via_spec_yaml(tmp_path: Path) -> None:
    """min_year/max_year del YAML se propagan al filter de OpenAlex."""
    from bib2graph.cli.commands.seed import run_seed
    from bib2graph.sources.equation import load_equation_spec

    yaml_content = """\
equation:
  query: '"ecology"'
  min_year: 1995
  max_year: 2019
"""
    spec_file = tmp_path / "equation.yaml"
    spec_file.write_text(yaml_content, encoding="utf-8")

    spec = load_equation_spec(spec_file)
    assert spec.min_year == 1995
    assert spec.max_year == 2019

    store_path = tmp_path / "test.duckdb"
    transport, captured = _make_capturing_transport()

    run_seed(
        store_path,
        spec.query,
        transport=transport,
        min_year=spec.min_year,
        max_year=spec.max_year,
    )

    assert captured
    filter_enviado = captured[0]
    assert "from_publication_date:1995-01-01" in filter_enviado
    assert "to_publication_date:2019-12-31" in filter_enviado


# ---------------------------------------------------------------------------
# 12. envelope --json de --from-bib
# ---------------------------------------------------------------------------


def test_seed_from_bib_json_envelope_claves_correctas(tmp_path: Path) -> None:
    """b2g seed --from-bib --json produce envelope con claves BibTeX (sin OA)."""
    from click.testing import CliRunner

    from bib2graph.cli import b2g
    from bib2graph.workspace import Workspace

    bib_file = _make_bib_file(tmp_path, BIB_COMPLETO)
    ws_dir = tmp_path / "ws"
    Workspace.init(ws_dir, "test")

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws_dir),
            "seed",
            "--from-bib",
            str(bib_file),
            "--json",
        ],
    )

    assert result.exit_code == 0, f"Se esperaba exit 0, salida: {result.output}"
    envelope = json.loads(result.output)
    assert envelope["ok"] is True
    data = envelope["data"]

    # Claves BibTeX
    assert "papers_added" in data
    assert "total_papers" in data
    assert "round" in data
    assert "reseeded" in data

    # Claves de OpenAlex NO deben estar
    assert "executed_query" not in data
    assert "translation_report" not in data

    assert data["papers_added"] == 2
    assert data["total_papers"] == 2


# ---------------------------------------------------------------------------
# 13. Prueba de integración ligera: sample.bib del ejemplo
# ---------------------------------------------------------------------------


def test_sample_bib_ejemplo_carga_correctamente(tmp_path: Path) -> None:
    """El sample.bib de examples/bibtex/ carga sin errores."""
    from bib2graph.cli.commands.seed import run_seed_from_bib

    sample_bib = (
        Path(__file__).parent.parent.parent / "examples" / "bibtex" / "sample.bib"
    )
    if not sample_bib.exists():
        pytest.skip("examples/bibtex/sample.bib no encontrado")

    store_path = tmp_path / "demo.duckdb"
    data = run_seed_from_bib(store_path, sample_bib)

    # El .bib tiene 10 entradas, todas con título → 10 papers
    assert data["papers_added"] == 10
    assert data["total_papers"] == 10
    assert data["round"] == 1
    assert data["reseeded"] is False
