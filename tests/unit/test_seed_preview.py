"""Tests TDD para ``b2g seed --preview`` (#287 fricción #2).

La semántica AND de ``--equation`` era opaca hasta gastar la llamada: un agente
solo veía la query ejecutada DESPUÉS de consumir cuota del rate limit, así que
tanteaba (~4 llamadas de ensayo-error en la sesión de #287). ``--preview`` es un
dry-run que traduce la ecuación y muestra la query **sin fetchear ni tocar el
corpus**, para razonar la ecuación de antemano.

Marcador: ``unit`` (sin red; el preview no abre store ni cliente HTTP).
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from bib2graph.cli import b2g
from bib2graph.cli.commands.seed import preview_seed_query

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helper puro
# ---------------------------------------------------------------------------


def test_preview_combina_terminos_en_and() -> None:
    """preview_seed_query traduce a title_and_abstract.search con los términos."""
    data = preview_seed_query("solid pods personal data")

    assert data["preview"] is True
    assert "title_and_abstract.search:" in data["executed_query"]
    # Los términos aparecen en la query (combinados en AND dentro del search)
    for term in ("solid", "pods", "personal", "data"):
        assert term in data["executed_query"]


def test_preview_exclude_genera_and_not() -> None:
    """--exclude se refleja como AND NOT en la query previsualizada."""
    data = preview_seed_query("open science", exclude=["machine learning"])
    assert 'AND NOT "machine learning"' in data["executed_query"]


def test_preview_anios_van_fuera_del_search() -> None:
    """min_year/max_year se reflejan como predicados de fecha."""
    data = preview_seed_query("open science", min_year=2020, max_year=2024)
    assert "from_publication_date:2020-01-01" in data["executed_query"]
    assert "to_publication_date:2024-12-31" in data["executed_query"]


def test_preview_ecuacion_vacia_falla() -> None:
    """Una ecuación vacía → DataError (no una query trivial)."""
    from bib2graph.service.errors import DataError

    with pytest.raises(DataError):
        preview_seed_query("   ")


# ---------------------------------------------------------------------------
# CLI: seed --preview no fetchea ni toca el corpus
# ---------------------------------------------------------------------------


def test_cli_preview_json_sin_workspace() -> None:
    """seed --equation ... --preview --json emite envelope ok sin workspace ni red.

    El preview corta antes de resolver workspace: funciona en un filesystem
    vacío (un agente puede razonar la ecuación en cualquier lado).
    """
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            b2g,
            ["seed", "--equation", "solid pods personal data", "--preview", "--json"],
            catch_exceptions=False,
        )
    assert result.exit_code == 0, result.output
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert len(lines) == 1
    envelope = json.loads(lines[0])
    assert envelope["ok"] is True
    assert envelope["data"]["preview"] is True
    assert "title_and_abstract.search:" in envelope["data"]["executed_query"]


def test_cli_preview_humano_muestra_query_y_and() -> None:
    """En modo humano, --preview imprime [preview] con la query y la nota de AND."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            b2g,
            ["seed", "--equation", "a b c", "--preview"],
            catch_exceptions=False,
        )
    assert result.exit_code == 0, result.output
    assert "[preview]" in result.stdout
    assert "title_and_abstract.search:" in result.stdout
    assert "AND" in result.stdout  # explica la semántica


def test_cli_preview_con_from_bib_es_usage_error() -> None:
    """--preview con --from-bib no tiene query que traducir → UsageError."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            b2g,
            ["seed", "--from-bib", "x.bib", "--preview", "--json"],
            catch_exceptions=False,
        )
    # Exit code 1 = UsageError (ADR 0021); envelope de error
    assert result.exit_code == 1, result.output
    envelope = json.loads(next(ln for ln in result.stdout.splitlines() if ln.strip()))
    assert envelope["ok"] is False
