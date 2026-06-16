"""cli.commands.status — Subcomando ``b2g status``.

Expone el LoopState y los conteos por curation_status del corpus.
NO transiciona el LoopState.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from bib2graph.cli._envelope import build_envelope, emit, emit_human
from bib2graph.cli._errors import handle_errors
from bib2graph.cli._store import open_store

# Transiciones disponibles desde cada estado (permisivas; ADR 0016)
_TRANSITIONS: dict[str | None, list[str]] = {
    None: ["seed"],
    "SEEDED": ["seed", "chain", "filter", "build", "snapshot", "inspect", "validate"],
    "FORAGED": ["seed", "chain", "filter", "build", "snapshot", "inspect", "validate"],
    "FILTERED": ["seed", "chain", "filter", "build", "snapshot", "inspect", "validate"],
    "BUILT": [
        "seed",
        "chain",
        "filter",
        "build",
        "export",
        "snapshot",
        "inspect",
        "validate",
    ],
}


# ---------------------------------------------------------------------------
# Función núcleo (testeable, sin Click)
# ---------------------------------------------------------------------------


def run_status(store_path: str | Path) -> dict[str, Any]:
    """Lee el LoopState y los conteos del corpus del store.

    Consulta la última fila de ``loop_state_log`` y hace un GROUP BY sobre
    ``curation_status`` para obtener los conteos. No transiciona el LoopState.

    Args:
        store_path: Ruta al archivo ``.duckdb``.

    Returns:
        Dict con ``loop_state``, ``transitions_available``, ``counts_by_status``,
        ``total_papers``.

    Raises:
        StoreError: Si el store está bloqueado.
    """
    store = open_store(store_path)

    loop_state = store.backend.loop_state()
    state_str = loop_state.value if loop_state is not None else None

    # Conteos por curation_status via query SQL
    from bib2graph.constants import Col

    counts_table = store.backend.query(
        f"SELECT {Col.CURATION_STATUS.value}, COUNT(*) as cnt FROM corpus GROUP BY 1"
    )
    counts: dict[str, int] = {}
    if len(counts_table) > 0:
        for row in counts_table.to_pylist():
            status = str(row[Col.CURATION_STATUS])
            counts[status] = int(row["cnt"])

    total = sum(counts.values())

    transitions = _TRANSITIONS.get(state_str, ["seed"])

    return {
        "loop_state": state_str,
        "transitions_available": transitions,
        "counts_by_status": counts,
        "total_papers": total,
    }


# ---------------------------------------------------------------------------
# Comando Click
# ---------------------------------------------------------------------------


@click.command("status")
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    help="Salida JSON estructurada.",
)
@click.pass_context
@handle_errors("status")
def status_cmd(
    ctx: click.Context,
    json_output: bool,
) -> None:
    """Muestra el estado del lazo (LoopState) y conteos de curación.

    No transiciona el LoopState.
    """
    store_path = ctx.obj["store"]
    data = run_status(store_path)

    if json_output:
        envelope = build_envelope(
            command="status",
            ok=True,
            data=data,
            exit_code=0,
        )
        emit(envelope)
    else:
        state = data["loop_state"] or "INITIAL (sin estado)"
        emit_human(f"Estado del lazo: {state}")
        emit_human(f"Total papers: {data['total_papers']}")
        if data["counts_by_status"]:
            emit_human("Conteos por curation_status:")
            for status, cnt in sorted(data["counts_by_status"].items()):
                emit_human(f"  {status}: {cnt}")
        emit_human(
            f"Próximos pasos disponibles: {', '.join(data['transitions_available'])}"
        )
