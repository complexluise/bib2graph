"""cli.commands.reject — Subcomando ``b2g reject``.

Marca papers como rejected en el corpus.

CURACIÓN TRANSVERSAL (ADR 0016 enmendado, R3): ``accept`` y ``reject`` están
disponibles en CUALQUIER estado del lazo y NO transicionan el CycleState.
Son lo único irreductiblemente humano (Nota 05 §4, pasos 0/4/7).  El mapa del
lazo (``b2g status``) los muestra siempre en ``curation_available``, separado
de ``transitions_available``.

Shim delgado (ADR 0028 G3): la orquestación vive en ``service.curate``; este
módulo inyecta el reloj (frontera CLI, R2/ADR 0017) y delega.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import click

from bib2graph.cli._envelope import build_envelope, emit, emit_human
from bib2graph.cli._errors import handle_errors
from bib2graph.cli._options import json_mode, json_option
from bib2graph.cli._store import resolve_library_path

# ---------------------------------------------------------------------------
# Función núcleo (testeable, sin Click) — shim que inyecta now y delega
# ---------------------------------------------------------------------------


def run_reject(
    store_path: str | Path,
    ids: list[str],
    *,
    by: str = "cli",
) -> dict[str, Any]:
    """Shim CLI: inyecta ``decided_at`` en la frontera y delega en ``service.curate``.

    Firma idéntica a la versión anterior para que ``test_cli.py`` no cambie.

    Args:
        store_path: Ruta al archivo ``.duckdb``.
        ids: Lista de ids a rechazar.
        by: Identificador de quien decide (default: ``"cli"``).

    Returns:
        Dict con ``rejected_count``, ``ids``.

    Raises:
        DataError: Si algún id no existe en el corpus.
        StoreError: Si el store está bloqueado.
    """
    from bib2graph.service.curate import reject_papers

    # R2: el reloj se inyecta en la frontera CLI (ADR 0017 enmendado).
    now = datetime.now(UTC)
    return reject_papers(store_path, ids, by=by, decided_at=now)


# ---------------------------------------------------------------------------
# Comando Click
# ---------------------------------------------------------------------------


@click.command("reject")
@click.option(
    "--ids",
    required=True,
    multiple=True,
    help="IDs de papers a rechazar (repetible: --ids ID1 --ids ID2).",
)
@click.option(
    "--by",
    default="cli",
    show_default=True,
    help="Identificador de quien decide.",
)
@json_option
@click.pass_context
@handle_errors("reject")
def reject_cmd(
    ctx: click.Context,
    ids: tuple[str, ...],
    by: str,
    json_output: bool,
) -> None:
    """Marca papers como rejected en el corpus.

    Curación TRANSVERSAL: no transiciona el CycleState.  Disponible en
    cualquier estado del lazo (Nota 05 §4, ADR 0016 enmendado R3).
    """
    store_path = resolve_library_path(ctx.obj)
    data = run_reject(store_path, list(ids), by=by)

    if json_mode(json_output):
        envelope = build_envelope(
            command="reject",
            ok=True,
            data=data,
            exit_code=0,
        )
        emit(envelope)
    else:
        emit_human(f"Rechazados {data['rejected_count']} papers.")
