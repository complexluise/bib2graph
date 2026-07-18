"""cli.commands.monitor — Subcomando ``b2g monitor`` (alias deprecado, #165).

Re-chequea OpenAlex por nuevos citantes del corpus (forward chaining),
mergea los candidatos nuevos a la biblioteca viva y transiciona el
CycleState a MONITORED (paso 8 del ciclo, Ellis).

Requiere que el corpus tenga al menos una semilla con ``source_id``
conocido (de lo contrario el forward chaining no encuentra nada).  Si no
hay corpus ni estado previo, falla con un error accionable.

**Implementación:** ``run_monitor`` es ahora un delegador fino sobre
``run_chain`` (con ``_fsm_action="monitor"``), garantizando fuente única
de la lógica de forrajeo (ADR 0037 §c).  La retirada formal de este
subcomando es el issue #165.

DEPRECADO (ADR 0038, #165): usar ``b2g chain --since``.  Se retira en 0.11.0.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from bib2graph.cli._deprecation import emit_deprecation
from bib2graph.cli._envelope import build_envelope, emit, emit_human
from bib2graph.cli._errors import handle_errors
from bib2graph.cli._options import json_mode, json_option
from bib2graph.cli._store import (
    resolve_workspace,
    workspace_echo,
    workspace_walkup_warning,
)


def run_monitor(
    store_path: str | Path,
    *,
    email: str | None = None,
    transport: Any = None,
) -> dict[str, Any]:
    """Re-chequea OpenAlex por nuevos citantes del corpus y transiciona a MONITORED.

    Delega en ``run_chain`` con ``direction="forward"`` y
    ``_fsm_action="monitor"`` para mantener fuente única de la lógica de
    forrajeo (ADR 0037 §c).

    Args:
        store_path: Ruta al archivo ``.duckdb``.
        email: Email para el polite pool de OpenAlex.
        transport: Transport inyectable para tests (``httpx.MockTransport``).

    Returns:
        Dict con ``new_candidates``, ``total_papers``, ``loop_state``, ``round``.

    Raises:
        DataError: Si no hay corpus previo (store vacío sin estado).
        NetworkError: Si falla la conexión a OpenAlex.
        StoreError: Si el store está bloqueado.
    """
    from bib2graph.cli.commands.chain import run_chain

    result = run_chain(
        store_path,
        direction="forward",
        email=email,
        transport=transport,
        _fsm_action="monitor",
    )
    return {
        "new_candidates": result["new_candidates"],
        "total_papers": result["total_papers"],
        "loop_state": result["loop_state"],
        "round": result["round"],
    }


@click.command("monitor")
@click.option(
    "--email",
    default=None,
    help="Email para el polite pool de OpenAlex (recomendado).",
)
@json_option
@click.pass_context
@handle_errors("monitor")
def monitor_cmd(
    ctx: click.Context,
    email: str | None,
    json_output: bool,
) -> None:
    """Re-chequea OpenAlex por nuevos citantes del corpus.

    Usa forward chaining para detectar papers que citan al corpus actual
    (citantes nuevos desde la última vez que se monitoreó).  Mergea los
    candidatos nuevos a la biblioteca viva y transiciona el estado a MONITORED.

    Requiere un corpus previo (ejecutar 'b2g seed' primero).
    Requiere --email para el polite pool de OpenAlex.
    """
    dep_msg = emit_deprecation("b2g monitor", "b2g chain --since")
    ws = resolve_workspace(ctx.obj)
    data = run_monitor(ws.library_path, email=email)

    # ADR 0045 (#259): eco de workspace + warning accionable en walk-up.
    data["workspace"] = workspace_echo(ws)

    if json_mode(json_output):
        envelope = build_envelope(
            command="monitor",
            ok=True,
            data=data,
            exit_code=0,
            warnings=[dep_msg, *workspace_walkup_warning(ws)],
        )
        emit(envelope)
    else:
        emit_human(f"Nuevos citantes encontrados: {data['new_candidates']}")
        emit_human(f"Total en corpus: {data['total_papers']}")
        emit_human(f"Estado: {data['loop_state']}")
        emit_human(f"Ronda: {data['round']}")
