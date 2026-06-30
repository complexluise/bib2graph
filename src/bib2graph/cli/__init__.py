"""cli — CLI agente-native ``b2g`` (Hito 6 + ADR 0029 workspace + #155 + ADR 0038).

Arma el grupo Click principal, registra los subcomandos planos y los grupos
noun-verb, y expone ``main()`` como entry point del paquete.

Entry points en ``pyproject.toml``:
    b2g      = "bib2graph.cli:main"
    bib2graph = "bib2graph.cli:main_bib2graph_alias"  # deprecado, #165

Subcomandos planos (17):
    init, seed, chain, filter, build, enrich, monitor, export,
    status, validate, accept, reject, networks, restore (shim #163),
    resolve.

    inspect: absorbido por ``read show`` (#156); permanece como alias.

Grupos noun-verb (4):
    read     [list|stats|show|top] — lecturas read-only del corpus (#156/#157).
    curate   [dump|apply|accept|reject|filter] — curación en lote (#155).
    snapshot [create|restore] — fotos selladas y rehidratación (#163, ADR 0038).
    skill    [add] — instala la skill de bib2graph para Claude (Epic #188).

Cada subcomando lleva:
  - ``--json``: salida JSON estructurada (envelope versionado, §API.md).
  - Exit codes 0-5 (ADR 0010).
  - Sin estado entre invocaciones: el estado vive en el workspace.

ADR 0029 — resolución ambiente:
  La opción global ``--workspace`` es OPCIONAL.
  Si no se pasa, los comandos resuelven el workspace activo vía
  ``Workspace.resolve(...)`` (B2G_WORKSPACE env o cwd walk).
  La opción ``--store`` fue eliminada (#75): pasarla produce el error estándar
  de Click ("No such option"). El modo degenerado (.duckdb suelto) ya no existe.

ADR 0038 — snapshot como grupo noun-verb:
  ``snapshot`` es ahora un grupo ``{create, restore}`` (BREAKING).
  ``b2g restore`` se mantiene como shim intacto (#165 retirará el alias).

R5 — UTF-8 en la frontera:
  ``main()`` fuerza ``sys.stdout``/``sys.stderr`` a UTF-8 antes de que Click
  lea cualquier argumento.  Esto corrige la corrupción de acentos en Windows
  (consola cp1252) cuando el envelope ``--json`` usa ``ensure_ascii=False``
  (ADR 0010/0021 — bug verificado en Nota 06 RAÍZ 3).
"""

from __future__ import annotations

import contextlib
import sys

import click

from bib2graph.cli._deprecation import emit_deprecation
from bib2graph.cli.commands.accept import accept_cmd
from bib2graph.cli.commands.build import build_cmd
from bib2graph.cli.commands.chain import chain_cmd
from bib2graph.cli.commands.curate import curate_grp
from bib2graph.cli.commands.enrich import enrich_cmd
from bib2graph.cli.commands.export import export_cmd
from bib2graph.cli.commands.filter import filter_cmd
from bib2graph.cli.commands.init import init_cmd
from bib2graph.cli.commands.inspect import inspect_cmd
from bib2graph.cli.commands.monitor import monitor_cmd
from bib2graph.cli.commands.networks import networks_cmd
from bib2graph.cli.commands.read import read_grp
from bib2graph.cli.commands.reject import reject_cmd
from bib2graph.cli.commands.resolve import resolve_cmd
from bib2graph.cli.commands.restore import restore_cmd
from bib2graph.cli.commands.seed import seed_cmd
from bib2graph.cli.commands.skill import skill_grp
from bib2graph.cli.commands.snapshot import snapshot_grp
from bib2graph.cli.commands.status import status_cmd
from bib2graph.cli.commands.validate import validate_cmd


def _force_utf8() -> None:
    """Fuerza stdout/stderr a UTF-8 si la stream lo soporta.

    Usa ``reconfigure(encoding='utf-8')`` (Python 3.7+) con guarda por si
    la stream no es reconfigurable (p. ej. redirección a archivo binario o
    entorno sin ``reconfigure``).  Sin esto, ``json.dumps(ensure_ascii=False)``
    corrompe acentos en Windows cuando la consola usa cp1252.

    R5 (Nota 06, RAÍZ 3): arreglo de mayor impacto/menor costo.
    """
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            with contextlib.suppress(Exception):
                stream.reconfigure(encoding="utf-8")


@click.group()
@click.version_option(package_name="bib2graph")
@click.option(
    "--workspace",
    default=None,
    type=click.Path(),
    help=(
        "Carpeta del workspace activo. "
        "Si no se pasa, se resuelve vía B2G_WORKSPACE o buscando workspace.json "
        "hacia arriba desde el directorio actual (ADR 0029)."
    ),
)
@click.pass_context
def b2g(ctx: click.Context, workspace: str | None) -> None:
    """b2g — bib2graph CLI agente-native.

    Transforma corpus bibliográficos en redes bibliométricas reproducibles.

    El workspace activo se resuelve en este orden (ADR 0029):
      1. --workspace <carpeta>  (forma canónica)
      2. Variable de entorno B2G_WORKSPACE
      3. workspace.json encontrado subiendo desde el directorio actual

    Si no hay ninguno, los comandos que necesitan la biblioteca emiten un
    error accionable (exit 1) que sugiere 'b2g init' o '--workspace'.

    Subcomandos: init, seed, chain, filter, build, enrich, monitor, export,
    status, validate, accept, reject, networks, restore (shim),
    resolve,
    read [list|stats|show|top], curate [dump|apply|accept|reject|filter],
    snapshot [create|restore] (ADR 0038),
    skill [add] (Epic #188).

    Ejemplo:
        b2g init mi-investigacion
        cd mi-investigacion
        b2g seed --equation "unequal exchange"
        b2g status --json
    """
    ctx.ensure_object(dict)
    ctx.obj["workspace"] = workspace


b2g.add_command(init_cmd)
b2g.add_command(seed_cmd)
b2g.add_command(chain_cmd)
b2g.add_command(filter_cmd)
b2g.add_command(build_cmd)
b2g.add_command(enrich_cmd)
b2g.add_command(monitor_cmd)
b2g.add_command(export_cmd)
b2g.add_command(snapshot_grp)
b2g.add_command(status_cmd)
b2g.add_command(inspect_cmd)
b2g.add_command(validate_cmd)
b2g.add_command(accept_cmd)
b2g.add_command(reject_cmd)
b2g.add_command(curate_grp)
b2g.add_command(networks_cmd)
b2g.add_command(restore_cmd)
b2g.add_command(resolve_cmd)
b2g.add_command(read_grp)
b2g.add_command(skill_grp)


def main() -> int:
    """Entry point del CLI agente-native b2g.

    R5: fuerza stdout/stderr a UTF-8 antes de cualquier salida para que el
    envelope ``--json`` (``ensure_ascii=False``) no corrompa acentos en
    Windows (consola cp1252).  Ver ``_force_utf8``.

    Invoca el grupo Click principal y devuelve el exit code.
    Los errores ya están manejados por el decorador ``@handle_errors``
    en cada subcomando.

    Returns:
        Exit code del proceso (0 éxito, 1-5 error según ADR 0010).
    """
    _force_utf8()
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


def main_bib2graph_alias() -> int:
    """Entry point del ejecutable legado ``bib2graph`` (alias deprecado, #165).

    Emite el aviso de deprecación a stderr y delega en ``main()``.

    DEPRECADO: el ejecutable canónico es ``b2g``.  Este alias se retira en 0.11.0
    (ADR 0038, #165).

    Returns:
        Exit code del proceso (0 éxito, 1-5 error según ADR 0010).
    """
    _force_utf8()
    emit_deprecation(
        "bib2graph",
        "b2g",
        removed_in="0.11.0",
    )
    return main()
