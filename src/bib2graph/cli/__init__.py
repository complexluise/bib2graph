"""cli — CLI agente-native ``b2g`` (Hito 6).

Arma el grupo Click principal, registra los 11 subcomandos y expone
``main()`` como entry point del paquete.

Entry point en ``pyproject.toml``:
    b2g = "bib2graph.cli:main"

Subcomandos:
    seed, chain, filter, build, export, snapshot,
    status, inspect, validate, accept, reject.

Cada subcomando lleva:
  - ``--json``: salida JSON estructurada (envelope versionado, §API.md).
  - Exit codes 0-5 (ADR 0010).
  - Sin estado entre invocaciones: el estado vive en ``--store``.
"""

from __future__ import annotations

import click

from bib2graph.cli.commands.accept import accept_cmd
from bib2graph.cli.commands.build import build_cmd
from bib2graph.cli.commands.chain import chain_cmd
from bib2graph.cli.commands.export import export_cmd
from bib2graph.cli.commands.filter import filter_cmd
from bib2graph.cli.commands.inspect import inspect_cmd
from bib2graph.cli.commands.reject import reject_cmd
from bib2graph.cli.commands.seed import seed_cmd
from bib2graph.cli.commands.snapshot import snapshot_cmd
from bib2graph.cli.commands.status import status_cmd
from bib2graph.cli.commands.validate import validate_cmd


@click.group()
@click.option(
    "--store",
    required=True,
    type=click.Path(),
    help="Ruta al archivo .duckdb de la biblioteca viva. Una investigación = un archivo.",
)
@click.pass_context
def b2g(ctx: click.Context, store: str) -> None:
    """b2g — bib2graph CLI agente-native.

    Transforma corpus bibliográficos en redes bibliométricas reproducibles.
    El estado de la investigación vive en --store (archivo .duckdb).

    Subcomandos: seed, chain, filter, build, export, snapshot,
    status, inspect, validate, accept, reject.

    Ejemplo:
        b2g --store mi_investigacion.duckdb seed --equation "unequal exchange"
        b2g --store mi_investigacion.duckdb status --json
    """
    ctx.ensure_object(dict)
    ctx.obj["store"] = store


# Registrar los 11 subcomandos
b2g.add_command(seed_cmd)
b2g.add_command(chain_cmd)
b2g.add_command(filter_cmd)
b2g.add_command(build_cmd)
b2g.add_command(export_cmd)
b2g.add_command(snapshot_cmd)
b2g.add_command(status_cmd)
b2g.add_command(inspect_cmd)
b2g.add_command(validate_cmd)
b2g.add_command(accept_cmd)
b2g.add_command(reject_cmd)


def main() -> int:
    """Entry point del CLI agente-native b2g.

    Invoca el grupo Click principal y devuelve el exit code.
    Los errores ya están manejados por el decorador ``@handle_errors``
    en cada subcomando.

    Returns:
        Exit code del proceso (0 éxito, 1-5 error según ADR 0010).
    """
    try:
        b2g(standalone_mode=False)
        return 0
    except click.exceptions.Exit as exc:
        return int(exc.exit_code)
    except click.exceptions.Abort:
        return 1
    except click.exceptions.UsageError as exc:
        click.echo(f"Error de uso: {exc.format_message()}", err=True)
        return 1
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 0
