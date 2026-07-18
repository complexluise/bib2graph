"""Tests del retiro de los alias deprecados y el entry-point ``bib2graph`` (#207, ADR 0038).

La ventana de deprecación (ADR 0038 P1, nominalmente cerrada en 0.11.0) se
ejecutó en 0.12.0 (#207): los 9 verbos planos deprecados, el entry-point
legado ``bib2graph`` y el flag ``build --corpus-scope`` fueron retirados sin
alias.  Este módulo verifica que invocarlos ahora produce el error estándar
de Click ("No such command"/"No such option"), no una delegación con aviso.

Verbos retirados verificados (#207):
  accept, reject, filter, inspect, monitor, networks, enrich, restore, resolve.

Sus formas canónicas — cubiertas por los tests del verbo/grupo correspondiente,
no aquí:
  - ``b2g accept``    → ``b2g curate accept``    (test_curate_grp.py)
  - ``b2g reject``    → ``b2g curate reject``    (test_curate_grp.py)
  - ``b2g filter``    → ``b2g curate filter``    (test_curate_grp.py)
  - ``b2g inspect``   → ``b2g read show`` / ``b2g status`` (test_cli.py)
  - ``b2g monitor``   → ``b2g chain --since``    (test_chain_since.py)
  - ``b2g networks``  → ``b2g build --spec``     (test_build_absorber_networks.py)
  - ``b2g enrich``    → ``b2g chain`` / ``b2g build`` (test_enrich_absorb.py)
  - ``b2g restore``   → ``b2g snapshot restore`` (test_snapshot_grp.py)
  - ``b2g resolve``   → ``b2g seed --resolve``   (test_parity_resolve_paths.py)

Entry-point legado ``bib2graph`` (``main_bib2graph_alias``): retirado sin
reemplazo; ``bib2graph.cli`` ya no expone esa función.

Flag ``build --corpus-scope``: retirado sin alias; usar ``build --scope``.

Marcador: ``unit`` (CliRunner, sin red ni DuckDB persistente).
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from bib2graph.cli import b2g

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Los 9 verbos planos retirados: "No such command" (exit 2, error estándar Click)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "verbo",
    [
        "accept",
        "reject",
        "filter",
        "inspect",
        "monitor",
        "networks",
        "enrich",
        "restore",
        "resolve",
    ],
)
def test_verbo_retirado_da_error_estandar_de_click(verbo: str) -> None:
    """Invocar un verbo plano retirado da el error estándar de Click.

    Sin catch_exceptions=False: Click intercepta el UsageError de "No such
    command" internamente y termina con exit_code=2 (comportamiento nativo,
    no un shim de bib2graph).
    """
    runner = CliRunner()
    result = runner.invoke(b2g, [verbo])
    assert result.exit_code == 2, (
        f"'b2g {verbo}' debería fallar con el exit code estándar de Click "
        f"(comando desconocido), obtuvo {result.exit_code}. output={result.output!r}"
    )
    assert "no such command" in result.output.lower(), (
        f"Esperaba 'No such command' en la salida de 'b2g {verbo}'; "
        f"output={result.output!r}"
    )


@pytest.mark.parametrize(
    "verbo",
    [
        "accept",
        "reject",
        "filter",
        "inspect",
        "monitor",
        "networks",
        "enrich",
        "restore",
        "resolve",
    ],
)
def test_verbo_retirado_no_aparece_en_help(verbo: str) -> None:
    """Ninguno de los 9 verbos retirados aparece listado en ``b2g --help``."""
    runner = CliRunner()
    result = runner.invoke(b2g, ["--help"])
    assert result.exit_code == 0
    # Verificación por token de línea de comando (Click alinea a 2 espacios);
    # evita falsos positivos por substring (p. ej. "filter" dentro de otra palabra).
    listed = {
        line.strip().split()[0]
        for line in result.output.splitlines()
        if line.startswith("  ") and line.strip()
    }
    assert verbo not in listed, f"'{verbo}' no debería listarse en 'b2g --help'"


def test_help_lista_exactamente_la_superficie_final_de_12_comandos() -> None:
    """``b2g --help`` lista EXACTAMENTE los 12 registros de la superficie final.

    10 verbos del ciclo (init, seed, chain, build, export, status, validate +
    grupos curate, read, snapshot) + skill + schema (meta) = 12. Ninguno de
    los 9 verbos retirados (#207, ADR 0038 P1) aparece.
    """
    runner = CliRunner()
    result = runner.invoke(b2g, ["--help"])
    assert result.exit_code == 0

    # Click agrupa los subcomandos bajo el encabezado "Commands:"; parseamos
    # solo esa sección para no capturar líneas de "Options:" ni del docstring.
    lines = result.output.splitlines()
    commands_idx = next(i for i, ln in enumerate(lines) if ln.strip() == "Commands:")
    listed = {
        line.strip().split()[0]
        for line in lines[commands_idx + 1 :]
        if line.startswith("  ") and line.strip()
    }

    esperados = {
        "init",
        "seed",
        "chain",
        "build",
        "export",
        "status",
        "validate",
        "curate",
        "read",
        "snapshot",
        "skill",
        "schema",
    }
    assert listed == esperados, (
        f"Superficie de 'b2g --help' no coincide con los 12 registros esperados.\n"
        f"Faltan: {esperados - listed}\n"
        f"Sobran: {listed - esperados}"
    )


# ---------------------------------------------------------------------------
# build --corpus-scope retirado: "No such option"
# ---------------------------------------------------------------------------


def test_build_corpus_scope_retirado_da_error_estandar_de_click(
    tmp_path: object,
) -> None:
    """``build --corpus-scope`` retirado: Click devuelve 'No such option'."""
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / "ws"  # type: ignore[operator]
    Workspace.init(ws_dir, "test")

    runner = CliRunner()
    result = runner.invoke(
        b2g, ["--workspace", str(ws_dir), "build", "--corpus-scope", "all"]
    )
    assert result.exit_code == 2
    assert "no such option" in result.output.lower()


# ---------------------------------------------------------------------------
# Entry-point legado 'bib2graph' retirado: la función ya no existe
# ---------------------------------------------------------------------------


def test_main_bib2graph_alias_ya_no_existe() -> None:
    """``bib2graph.cli`` ya no expone ``main_bib2graph_alias`` (retirado #207)."""
    import bib2graph.cli as cli_module

    assert not hasattr(cli_module, "main_bib2graph_alias"), (
        "main_bib2graph_alias debería haber sido retirado junto con el "
        "entry-point legado 'bib2graph' (#207, ADR 0038 P1)."
    )


def test_deprecation_module_ya_no_existe() -> None:
    """``bib2graph.cli._deprecation`` fue retirado: ya no queda alias vivo que lo use."""
    with pytest.raises(ModuleNotFoundError):
        import importlib

        importlib.import_module("bib2graph.cli._deprecation")
