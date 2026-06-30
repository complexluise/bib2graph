"""cli.commands.snapshot — Grupo noun-verb ``b2g snapshot`` (ADR 0038, #163).

Convierte ``snapshot`` de comando plano a **grupo noun-verb** con dos
subcomandos:

  ``snapshot create``  — exporta una foto sellada del corpus actual
                         (= comportamiento anterior del comando plano).
  ``snapshot restore`` — rehidrata el corpus desde un parquet curado sin red
                         (= lógica de ``b2g restore``, fuente única en service).

Molde: ``curate.py`` (#155) — grupo ``invoke_without_command=True`` + check
manual para exit 0 sin subcomando (Click 8.4 usa exit 2 con
``no_args_is_help=True`` en grupos).

BREAKING (ADR 0038):
  - ``b2g snapshot`` plano pasa a ``b2g snapshot create``.
  - ``b2g snapshot restore`` es el nuevo camino canónico para rehabilitar corpus.
  - ``b2g restore`` suelto queda intacto como shim; su retiro es #165.

Capa de servicios (ADR 0038):
  Toda la lógica vive en ``service.snapshot``; este módulo son shims delgados
  que inyectan el reloj en la frontera CLI (R2/ADR 0017) y emiten el envelope.

Backward compat con tests existentes:
  ``run_snapshot`` y ``run_restore`` se re-exportan desde ``service.snapshot``
  para que los tests que importan de ``bib2graph.cli.commands.snapshot`` sigan
  funcionando sin cambios.
  ``snapshot_cmd`` = ``snapshot_grp`` (alias para tests que usaban el nombre viejo).

Flujo canónico:
    b2g snapshot create                         # exporta corpus.parquet + manifest.json
    b2g snapshot create --out-dir mis_snaps/    # directorio alternativo
    b2g snapshot restore --from-corpus snap/corpus.parquet   # rehidrata
    b2g snapshot                                # imprime ayuda y sale con exit 0
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import click

from bib2graph.cli._envelope import build_envelope, emit, emit_human
from bib2graph.cli._errors import handle_errors
from bib2graph.cli._options import json_mode, json_option
from bib2graph.cli._store import resolve_workspace
from bib2graph.service.snapshot import run_restore, run_snapshot

__all__ = [
    "run_restore",
    "run_snapshot",
    "snapshot_cmd",
    "snapshot_grp",
]


# Grupo raíz


@click.group("snapshot", invoke_without_command=True)
@click.pass_context
def snapshot_grp(ctx: click.Context) -> None:
    """Gestión de snapshots del corpus: create y restore.

    Subcomandos: create, restore.

    Ejemplos:
        b2g snapshot create
        b2g snapshot create --out-dir mis_snaps/
        b2g snapshot restore --from-corpus snaps/corpus.parquet
    """
    ctx.ensure_object(dict)
    # Click 8.4: no_args_is_help=True en grupos termina con exit 2.
    # Usamos invoke_without_command=True + check manual para exit 0 correcto.
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# snapshot create


@snapshot_grp.command("create")
@click.option(
    "--out-dir",
    default=None,
    help=(
        "Directorio destino del snapshot "
        "(default: <workspace>/snapshots/ o <store_dir>/snapshots/)."
    ),
)
@json_option
@click.pass_context
@handle_errors("snapshot create")
def create_cmd(
    ctx: click.Context,
    out_dir: str | None,
    json_output: bool,
) -> None:
    """Exporta una foto sellada del corpus actual (parquet + manifest.json).

    No transiciona el CycleState.

    El directorio de salida por defecto es ``<workspace>/snapshots/``.
    Con ``--out-dir`` se puede especificar un directorio alternativo.
    """
    # ADR 0029: usar snapshots_dir del workspace si no se especifica --out-dir
    ws = resolve_workspace(ctx.obj)
    effective_out_dir: Path = Path(out_dir) if out_dir is not None else ws.snapshots_dir

    data = run_snapshot(ws.library_path, out_dir=effective_out_dir)

    if json_mode(json_output):
        envelope = build_envelope(
            command="snapshot create",
            ok=True,
            data=data,
            exit_code=0,
        )
        emit(envelope)
    else:
        emit_human(f"Snapshot exportado en: {data['snapshot_dir']}")
        emit_human(f"corpus_hash: {data['corpus_hash']}")
        emit_human(f"Total papers: {data['total_papers']}")


# snapshot restore


@snapshot_grp.command("restore")
@click.option(
    "--from-corpus",
    "corpus_path",
    required=True,
    type=click.Path(),
    help=(
        "Ruta al parquet con el corpus curado a importar sin red "
        "(producido por b2g snapshot create)."
    ),
)
@json_option
@click.pass_context
@handle_errors("snapshot restore")
def restore_sub_cmd(
    ctx: click.Context,
    corpus_path: str,
    json_output: bool,
) -> None:
    """Rehidrata el corpus desde un parquet curado sin tocar la red.

    \b
    Carga el parquet con el schema canónico de bib2graph, hace merge con
    el corpus existente y transiciona el lazo a FILTERED (el corpus ya
    fue curado; build y networks pueden correr a continuación).

    \b
    Preserva las columnas de curación del parquet (curation_status, is_seed).

    \b
    Ejemplos:
      b2g snapshot restore --from-corpus snapshots/corpus.parquet
      b2g snapshot restore --from-corpus corpus_curado.parquet --json
    """
    ws = resolve_workspace(ctx.obj)
    # R2/ADR 0017: el reloj se inyecta en la frontera CLI.
    decided_at = datetime.now(UTC)
    data = run_restore(ws.library_path, corpus_path, decided_at=decided_at)

    if json_mode(json_output):
        envelope = build_envelope(
            command="snapshot restore",
            ok=True,
            data=data,
            exit_code=0,
        )
        emit(envelope)
    else:
        emit_human(f"Corpus restaurado: {data['papers_loaded']} papers importados.")
        emit_human(f"Total en corpus: {data['total_papers']}")
        emit_human(f"Estado del lazo: {data['state']}")


# Alias snapshot_cmd → snapshot_grp (compat con registros y tests existentes)
snapshot_cmd = snapshot_grp
