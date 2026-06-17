"""Tests TDD del Ciclo 9a — capa declarativa de ecuación.

Casos cubiertos (ADR 0030 §Tests):

1. load_equation_spec: YAML válido (raíz ``equation:``) carga los campos.
2. load_equation_spec: YAML malformado → ValueError accionable.
3. load_equation_spec: spec inválida (campo extra, falta ``query``) → ValueError
   citando archivo + campo.
4. seed --spec ≡ seed --equation+flags: mismo ``executed_query`` / resultado.
5. Mutua exclusión: 0 modos → UsageError; 2 modos (--equation + --spec) → UsageError.

Nota: los tests de ``b2g restore --from-corpus`` viven en
``tests/unit/test_restore.py`` (separación semántica: restore ≠ seed).

Filosofía (AGENTS.md): se testea la FUNCIÓN detrás del comando, NO el parser
Click. CliRunner solo donde hay integración de flag necesaria.
Marcador: ``unit`` (DuckDB en tmp_path, sin red real).
Fecha de fixtures: 2026-06-17.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

# ---------------------------------------------------------------------------
# Fixtures y helpers comunes
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


# ---------------------------------------------------------------------------
# 1. load_equation_spec: YAML válido carga los campos
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_load_equation_spec_yaml_valido_campos_completos(tmp_path: Path) -> None:
    """YAML válido con todos los campos → EquationSpec con los valores correctos."""
    from bib2graph.sources.equation import EquationSpec, load_equation_spec

    yaml_content = """\
equation:
  query: '"unequal ecological exchange" OR "ecologically unequal exchange"'
  exclude:
    - "stock exchange"
    - "commodity exchange"
  max_results: 150
  native: false
  min_year: 1990
  max_year: 2024
"""
    spec_file = tmp_path / "equation.yaml"
    spec_file.write_text(yaml_content, encoding="utf-8")

    spec = load_equation_spec(spec_file)

    assert isinstance(spec, EquationSpec)
    assert (
        spec.query == '"unequal ecological exchange" OR "ecologically unequal exchange"'
    )
    assert spec.exclude == ["stock exchange", "commodity exchange"]
    assert spec.max_results == 150
    assert spec.native is False
    assert spec.min_year == 1990
    assert spec.max_year == 2024


@pytest.mark.unit
def test_load_equation_spec_yaml_solo_query(tmp_path: Path) -> None:
    """YAML con solo ``query`` → EquationSpec con defaults correctos."""
    from bib2graph.sources.equation import load_equation_spec

    yaml_content = """\
equation:
  query: '"unequal exchange"'
"""
    spec_file = tmp_path / "equation.yaml"
    spec_file.write_text(yaml_content, encoding="utf-8")

    spec = load_equation_spec(spec_file)

    assert spec.query == '"unequal exchange"'
    assert spec.exclude == []
    assert spec.max_results is None
    assert spec.native is False
    assert spec.min_year is None
    assert spec.max_year is None


@pytest.mark.unit
def test_load_equation_spec_native_true(tmp_path: Path) -> None:
    """YAML con ``native: true`` → spec con native=True."""
    from bib2graph.sources.equation import load_equation_spec

    yaml_content = "equation:\n  query: 'title.search:ecologia'\n  native: true\n"
    spec_file = tmp_path / "equation.yaml"
    spec_file.write_text(yaml_content, encoding="utf-8")

    spec = load_equation_spec(spec_file)

    assert spec.native is True


@pytest.mark.unit
def test_load_equation_spec_archivo_no_existe() -> None:
    """Archivo YAML inexistente → FileNotFoundError."""
    from bib2graph.sources.equation import load_equation_spec

    with pytest.raises(FileNotFoundError):
        load_equation_spec("/ruta/que/no/existe.yaml")


# ---------------------------------------------------------------------------
# 2. load_equation_spec: YAML malformado → ValueError accionable
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_load_equation_spec_yaml_malformado(tmp_path: Path) -> None:
    """YAML con sintaxis inválida → ValueError que describe el problema."""
    from bib2graph.sources.equation import load_equation_spec

    # Tabulador al inicio de línea es sintaxis inválida en YAML
    yaml_content = "equation:\n\t- query: algo\n"
    spec_file = tmp_path / "equation.yaml"
    spec_file.write_text(yaml_content, encoding="utf-8")

    with pytest.raises(ValueError, match="YAML malformado"):
        load_equation_spec(spec_file)


@pytest.mark.unit
def test_load_equation_spec_sin_clave_raiz_equation(tmp_path: Path) -> None:
    """YAML sin clave ``equation:`` → ValueError accionable."""
    from bib2graph.sources.equation import load_equation_spec

    yaml_content = "query: 'algo'\n"
    spec_file = tmp_path / "equation.yaml"
    spec_file.write_text(yaml_content, encoding="utf-8")

    with pytest.raises(ValueError, match="equation:"):
        load_equation_spec(spec_file)


@pytest.mark.unit
def test_load_equation_spec_clave_raiz_equivocada(tmp_path: Path) -> None:
    """YAML con clave raíz ``equations:`` (plural) → ValueError accionable."""
    from bib2graph.sources.equation import load_equation_spec

    yaml_content = "equations:\n  query: 'algo'\n"
    spec_file = tmp_path / "equation.yaml"
    spec_file.write_text(yaml_content, encoding="utf-8")

    with pytest.raises(ValueError, match="equation:"):
        load_equation_spec(spec_file)


# ---------------------------------------------------------------------------
# 3. load_equation_spec: spec inválida → ValueError citando archivo + campo
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_load_equation_spec_campo_extra_lanza_error(tmp_path: Path) -> None:
    """Campo no permitido en la spec → ValueError que cita el campo extra."""
    from bib2graph.sources.equation import load_equation_spec

    yaml_content = """\
equation:
  query: '"unequal exchange"'
  campo_inventado: true
"""
    spec_file = tmp_path / "equation.yaml"
    spec_file.write_text(yaml_content, encoding="utf-8")

    with pytest.raises(ValueError, match="campo_inventado"):
        load_equation_spec(spec_file)


@pytest.mark.unit
def test_load_equation_spec_sin_query_lanza_error(tmp_path: Path) -> None:
    """Spec sin campo ``query`` (requerido) → ValueError accionable."""
    from bib2graph.sources.equation import load_equation_spec

    yaml_content = "equation:\n  max_results: 100\n"
    spec_file = tmp_path / "equation.yaml"
    spec_file.write_text(yaml_content, encoding="utf-8")

    with pytest.raises(ValueError, match="query"):
        load_equation_spec(spec_file)


@pytest.mark.unit
def test_load_equation_spec_tipo_incorrecto_lanza_error(tmp_path: Path) -> None:
    """max_results con tipo incorrecto (string) → ValueError citando el campo."""
    from bib2graph.sources.equation import load_equation_spec

    yaml_content = """\
equation:
  query: '"unequal exchange"'
  max_results: "no_es_numero"
"""
    spec_file = tmp_path / "equation.yaml"
    spec_file.write_text(yaml_content, encoding="utf-8")

    with pytest.raises(ValueError, match="max_results"):
        load_equation_spec(spec_file)


@pytest.mark.unit
def test_load_equation_spec_cita_archivo_en_error(tmp_path: Path) -> None:
    """El ValueError por campo extra cita el nombre del archivo."""
    from bib2graph.sources.equation import load_equation_spec

    spec_file = tmp_path / "mi_ecuacion.yaml"
    spec_file.write_text(
        "equation:\n  query: 'algo'\n  campo_raro: 1\n", encoding="utf-8"
    )

    with pytest.raises(ValueError) as exc_info:
        load_equation_spec(spec_file)

    assert "mi_ecuacion.yaml" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 4. seed --spec ≡ seed --equation+flags: mismo executed_query
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_seed_spec_equivalente_a_equation_directo(tmp_path: Path) -> None:
    """seed con --spec produce el mismo executed_query que --equation con mismos flags.

    El YAML declara query + exclude, que se mapean 1:1 a los args de run_seed.
    La equivalencia se verifica comparando executed_query: ambas rutas generan
    la misma query OpenAlex (mismo passthrough + mismas cláusulas AND NOT).
    """
    from bib2graph.cli.commands.seed import run_seed
    from bib2graph.sources.equation import load_equation_spec

    # Preparar YAML con query + exclude
    query = '"unequal exchange"'
    excludes = ["stock exchange"]
    yaml_content = f"""\
equation:
  query: '{query}'
  exclude:
    - "{excludes[0]}"
  max_results: 5
"""
    spec_file = tmp_path / "equation.yaml"
    spec_file.write_text(yaml_content, encoding="utf-8")

    # Modo --equation directo
    store_eq = tmp_path / "eq.duckdb"
    transport_eq = _make_mock_transport()
    data_eq = run_seed(
        store_eq,
        query,
        transport=transport_eq,
        exclude=excludes,
        max_results=5,
    )

    # Modo --spec: cargar spec y llamar run_seed con sus campos
    store_spec = tmp_path / "spec.duckdb"
    transport_spec = _make_mock_transport()
    spec = load_equation_spec(spec_file)
    data_spec = run_seed(
        store_spec,
        spec.query,
        transport=transport_spec,
        exclude=spec.exclude if spec.exclude else None,
        max_results=spec.max_results,
        native=spec.native,
    )

    # El executed_query debe ser idéntico
    assert data_eq["executed_query"] == data_spec["executed_query"]


# ---------------------------------------------------------------------------
# 5. Mutua exclusión: 0 modos → error; 2 modos → error accionable
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_seed_sin_modo_lanza_usage_error(tmp_path: Path) -> None:
    """b2g seed sin ningún modo → UsageError accionable (exit 1)."""
    from click.testing import CliRunner

    from bib2graph.cli import b2g

    store_path = tmp_path / "test.duckdb"

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--store",
            str(store_path),
            "seed",
            "--json",
        ],
    )

    assert result.exit_code == 1, f"Se esperaba exit 1, salida: {result.output}"
    envelope = json.loads(result.output)
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "USAGE_ERROR"


@pytest.mark.unit
def test_seed_equation_y_spec_a_la_vez_lanza_usage_error(tmp_path: Path) -> None:
    """--equation y --spec juntos → UsageError accionable (exit 1)."""
    from click.testing import CliRunner

    from bib2graph.cli import b2g

    spec_file = tmp_path / "equation.yaml"
    spec_file.write_text("equation:\n  query: 'algo'\n", encoding="utf-8")
    store_path = tmp_path / "test.duckdb"

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--store",
            str(store_path),
            "seed",
            "--equation",
            "unequal exchange",
            "--spec",
            str(spec_file),
            "--json",
        ],
    )

    assert result.exit_code == 1, f"Se esperaba exit 1, salida: {result.output}"
    envelope = json.loads(result.output)
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "USAGE_ERROR"
    assert (
        "--equation" in envelope["error"]["message"]
        or "--spec" in envelope["error"]["message"]
    )


# ---------------------------------------------------------------------------
# Tests adicionales: retrocompatibilidad de --equation (no regresión)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_run_seed_retrocompat_equation_directo(tmp_path: Path) -> None:
    """run_seed con ecuación directa sigue funcionando (no-regresión).

    Verifica que el refactor de seed.py no rompió la firma existente de
    run_seed (llamada con equation positional + transport mock).
    """
    from bib2graph.cli.commands.seed import run_seed

    store_path = tmp_path / "test.duckdb"
    transport = _make_mock_transport()

    data = run_seed(
        store_path,
        "unequal exchange",
        transport=transport,
    )

    assert "executed_query" in data
    assert "papers_added" in data
    assert "total_papers" in data
    assert isinstance(data["papers_added"], int)
    assert data["papers_added"] >= 0


@pytest.mark.unit
def test_run_seed_con_exclude_y_max_results(tmp_path: Path) -> None:
    """run_seed con exclude y max_results propaga los parámetros correctamente."""
    from bib2graph.cli.commands.seed import run_seed
    from bib2graph.sources.openalex import _translate

    # Verificar que la query con exclude tiene el AND NOT esperado
    query = '"unequal exchange"'
    exclude = ["stock exchange"]
    executed, _ = _translate(query, exclude=exclude)

    store_path = tmp_path / "test.duckdb"
    transport = _make_mock_transport()

    data = run_seed(
        store_path,
        query,
        transport=transport,
        exclude=exclude,
        max_results=10,
    )

    assert data["executed_query"] == executed
    assert "AND NOT" in data["executed_query"]


# ---------------------------------------------------------------------------
# Tests de seed --spec a través del CLI (CliRunner + YAML válido/inválido)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_seed_spec_yaml_invalido_emite_data_error(tmp_path: Path) -> None:
    """b2g seed --spec con YAML inválido (campo extra) → DataError (exit 2)."""
    from click.testing import CliRunner

    from bib2graph.cli import b2g

    bad_yaml = "equation:\n  query: 'algo'\n  campo_extra: true\n"
    spec_file = tmp_path / "bad.yaml"
    spec_file.write_text(bad_yaml, encoding="utf-8")

    store_path = tmp_path / "test.duckdb"

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--store",
            str(store_path),
            "seed",
            "--spec",
            str(spec_file),
            "--json",
        ],
    )

    assert result.exit_code == 2, f"Se esperaba exit 2, salida: {result.output}"
    envelope = json.loads(result.output)
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "DATA_ERROR"


@pytest.mark.unit
def test_seed_spec_yaml_sin_query_emite_data_error(tmp_path: Path) -> None:
    """b2g seed --spec con YAML sin campo 'query' → DataError (exit 2)."""
    from click.testing import CliRunner

    from bib2graph.cli import b2g

    bad_yaml = "equation:\n  max_results: 100\n"
    spec_file = tmp_path / "bad.yaml"
    spec_file.write_text(bad_yaml, encoding="utf-8")

    store_path = tmp_path / "test.duckdb"

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--store",
            str(store_path),
            "seed",
            "--spec",
            str(spec_file),
            "--json",
        ],
    )

    assert result.exit_code == 2, f"Se esperaba exit 2, salida: {result.output}"
    envelope = json.loads(result.output)
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "DATA_ERROR"
