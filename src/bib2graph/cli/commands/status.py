"""cli.commands.status — Subcomando ``b2g status``.

Expone el CycleState y los conteos por curation_status del corpus.
NO transiciona el CycleState.

R3: el mapa honesto del lazo (ADR 0016 enmendado).  Muestra:
- estado actual (CycleState / LoopState),
- transiciones disponibles desde ese estado,
- ``curation_available``: accept/reject son acciones SIEMPRE-DISPONIBLES
  (curación transversal, NO transicionan el lazo),
- contador de ronda,
- conteos por curation_status.

El envelope ``--json`` incluye ``curation_available`` y ``round`` como campos
ADITIVOS que mantienen ``schema="1"`` (decisión del PO 2026-06-16: campos
nuevos no rompen a los agentes, no se bumpea).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from bib2graph.cli._envelope import build_envelope, emit, emit_human
from bib2graph.cli._errors import handle_errors
from bib2graph.cli._store import open_store
from bib2graph.cycle import CURATION_ACTIONS, available_transitions

# ---------------------------------------------------------------------------
# Función núcleo (testeable, sin Click)
# ---------------------------------------------------------------------------


def run_status(store_path: str | Path) -> dict[str, Any]:
    """Lee el CycleState, la ronda y los conteos del corpus del store.

    Consulta la última fila de ``loop_state_log`` y hace un GROUP BY sobre
    ``curation_status`` para obtener los conteos.  No transiciona el CycleState.

    R3 — mapa honesto del lazo:
    - ``transitions_available``: acciones de ciclo disponibles desde el estado
      actual (incluye ``reseed`` cuando hay estado previo).
    - ``curation_available``: ``["accept", "reject"]`` SIEMPRE, porque la
      curación es transversal y no transiciona el lazo.  Antes de R3, este
      campo no existía y ``transitions_available`` nunca los listaba (bug).
    - ``round``: contador de ronda (0 = sin estado; 1 = primera ronda; 2+ = re-sembrados).

    Args:
        store_path: Ruta al archivo ``.duckdb``.

    Returns:
        Dict con ``loop_state``, ``transitions_available``, ``curation_available``,
        ``round``, ``counts_by_status``, ``total_papers``.

    Raises:
        StoreError: Si el store está bloqueado.
    """
    store = open_store(store_path)

    loop_state = store.backend.loop_state()
    state_str = loop_state.value if loop_state is not None else None
    current_round = store.backend.loop_round()

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

    # Transiciones disponibles desde el dominio (cicle.py); incluye reseed
    # cuando hay estado previo.
    transitions = available_transitions(loop_state)

    # Curación transversal: siempre disponible, nunca transiciona el lazo.
    # Antes de R3, ``transitions_available`` nunca listaba accept/reject → bug cerrado.
    curation = list(CURATION_ACTIONS)

    return {
        "loop_state": state_str,
        "transitions_available": transitions,
        "curation_available": curation,
        "round": current_round,
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
    """Muestra el estado del lazo (CycleState) y conteos de curación.

    No transiciona el CycleState.

    El mapa del lazo incluye:
    - Estado actual y transiciones disponibles (incluyendo reseed).
    - accept/reject como acciones siempre-disponibles (curación transversal).
    - Contador de ronda.
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
        round_str = f" (ronda {data['round']})" if data["round"] > 0 else ""
        emit_human(f"Estado del lazo: {state}{round_str}")
        emit_human(f"Total papers: {data['total_papers']}")
        if data["counts_by_status"]:
            emit_human("Conteos por curation_status:")
            for status, cnt in sorted(data["counts_by_status"].items()):
                emit_human(f"  {status}: {cnt}")
        emit_human(
            f"Próximos pasos disponibles: {', '.join(data['transitions_available'])}"
        )
        emit_human(
            f"Curación (siempre disponible): {', '.join(data['curation_available'])}"
        )
