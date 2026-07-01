"""cli.commands.init — Subcomando ``b2g init``.

Scaffolds un workspace nuevo (carpeta autocontenida) para una investigación.

Uso:
    b2g init <nombre>    # crea ./<nombre>/ como workspace
    b2g init .           # inicializa el cwd como workspace

El workspace creado contiene:
    workspace.json    — manifest mínimo (marcador)
    library.duckdb    — biblioteca viva inicializada
    networks/         — cache de redes (build), regenerable
    snapshots/        — snapshots sellados
    exports/          — exports regenerables

ADR 0029 §Decisión.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from bib2graph.cli._envelope import build_envelope, emit, emit_human
from bib2graph.cli._errors import UsageError, handle_errors
from bib2graph.cli._options import json_mode, json_option


def run_init(path: Path, name: str) -> dict[str, Any]:
    """Crea un workspace nuevo en ``path`` con el nombre ``name``.

    Si ``path`` ya contiene un ``workspace.json``, falla con error accionable.
    Si ``path`` no existe, la crea.

    Args:
        path: Directorio destino del workspace.
        name: Nombre legible de la investigación (va al manifest).

    Returns:
        Dict con ``workspace_dir``, ``library_path``, ``manifest``.

    Raises:
        UsageError: Si ya existe un workspace en ``path``.
    """
    from bib2graph.workspace import Workspace, WorkspaceExistsError

    try:
        ws = Workspace.init(path, name)
    except WorkspaceExistsError as exc:
        raise UsageError(str(exc)) from exc

    return {
        "workspace_dir": str(ws.root),
        "library_path": str(ws.library_path),
        "manifest": ws.manifest.model_dump() if ws.manifest else {},
    }


@click.command("init")
@click.argument("target", default=".")
@click.option(
    "--name",
    default=None,
    help=(
        "Nombre legible de la investigación (default: nombre del directorio destino)."
    ),
)
@json_option
@handle_errors("init")
def init_cmd(
    target: str,
    name: str | None,
    json_output: bool,
) -> None:
    """Inicializa una carpeta como workspace de investigación.

    TARGET puede ser un nombre de carpeta nueva (se crea en el cwd) o un
    directorio existente (incluido '.' para el directorio actual).

    Ejemplos:

      b2g init mi-estudio        # crea ./mi-estudio/ como workspace

      b2g init .                 # inicializa el cwd como workspace

      b2g init mi-estudio --name "Estudio de redes IED"
    """
    target_path = Path(target)

    if not target_path.is_absolute() and not target_path.exists() and target != ".":
        target_path = Path.cwd() / target_path

    resolved_name = name if name else target_path.resolve().name

    data = run_init(target_path, resolved_name)

    if json_mode(json_output):
        envelope = build_envelope(
            command="init",
            ok=True,
            data=data,
            exit_code=0,
        )
        emit(envelope)
    else:
        emit_human(f"Workspace creado en: {data['workspace_dir']}")
        emit_human(f"Biblioteca: {data['library_path']}")
        emit_human(f"Nombre: {data['manifest'].get('name', resolved_name)}")
