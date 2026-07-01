"""cli.commands.status — Subcomando ``b2g status``.

Expone el CycleState y los conteos por curation_status del corpus.
NO transiciona el CycleState.

R3: el mapa honesto del lazo (ADR 0016 enmendado).  Muestra:
- estado actual (CycleState),
- transiciones disponibles desde ese estado,
- ``curation_available``: accept/reject son acciones SIEMPRE-DISPONIBLES
  (curación transversal, NO transicionan el lazo),
- contador de ronda,
- conteos por curation_status.

ADR 0029 (aditivo): el envelope incluye ``workspace`` con el workspace
resuelto (root, source) para que el agente sepa de dónde salió la biblioteca.
Mantiene ``schema="1"`` (campos nuevos son aditivos, no rompen agentes).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import click

from bib2graph.cli._envelope import build_envelope, emit, emit_human
from bib2graph.cli._errors import handle_errors
from bib2graph.cli._options import json_mode, json_option
from bib2graph.cli._store import open_store_readonly, resolve_workspace
from bib2graph.cycle import CURATION_ACTIONS, available_transitions, next_best_action
from bib2graph.networks.facade import predict_build_preview

# Función núcleo (testeable, sin Click)


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

    ADR 0037 §(e) — campos aditivos (schema="1" intacto):
    - ``next_best_action``: único próximo comando recomendado (derivado del FSM).
    - ``readiness``: si el próximo paso va a dar fruto (preparación, no solo
      alcanzabilidad FSM).
    - ``build_preview``: por cada red proyectable, predice vacío/no-vacío ANTES
      de correr build (diagnóstico de red-vacía en status-time).

    Args:
        store_path: Ruta al archivo ``.duckdb``.

    Returns:
        Dict con ``loop_state``, ``transitions_available``, ``curation_available``,
        ``round``, ``counts_by_status``, ``total_papers``, ``next_best_action``,
        ``readiness``, ``build_preview``.

    Raises:
        StoreError: Si el store está bloqueado.
    """
    # R5: open_store_readonly falla si el archivo no existe (no auto-crea).
    store = open_store_readonly(store_path)

    loop_state = store.backend.loop_state()
    state_str = loop_state.value if loop_state is not None else None
    current_round = store.backend.loop_round()

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
    curation = list(CURATION_ACTIONS)

    # #54: conteo de IDs backward observados pero no materializados.
    # El campo es aditivo (schema="1" intacto; campos nuevos no rompen agentes).
    referenced_not_fetched = store.backend.referenced_refs_count()

    # ADR 0037 §(e) — campos aditivos: next_best_action, readiness, build_preview.
    # Cargar el corpus para los conteos de columnas (predicados compartidos con
    # los proyectores → fuente única preview ↔ build).
    corpus = store.load()

    # next_best_action: derivado puramente del FSM (cycle.py).
    action = next_best_action(loop_state)

    build_prev = predict_build_preview(corpus)

    # readiness: si el próximo paso va a DAR FRUTO (no solo si está permitido).
    # Caso crítico "build": ready si al menos 1 red no sería vacía.
    # Caso "chain": ready si al menos 1 seed tiene source_id (necesario para
    #   el forrajeo en OpenAlex).  BibTeX sin --resolve → source_id=None en
    #   todos los seeds → chaining produce 0 papers nuevos (Nota 20, ADR 0037).
    if action == "build":
        all_empty = all(bool(item["would_be_empty"]) for item in build_prev)
        if all_empty:
            readiness: dict[str, Any] = {
                "ready": False,
                "reason": (
                    "Todas las redes proyectables saldrían vacías. "
                    "Revisá build_preview.fix_command para cada red."
                ),
            }
        else:
            readiness = {"ready": True, "reason": None}
    elif action == "chain":
        from bib2graph.constants import Col

        table_for_chain = corpus.to_arrow()
        rows_for_chain = table_for_chain.to_pylist()
        total_seeds_count = sum(1 for r in rows_for_chain if r.get(Col.IS_SEED))
        n_seeds_with_source = sum(
            1
            for r in rows_for_chain
            if r.get(Col.IS_SEED) and r.get(Col.SOURCE_ID) is not None
        )
        if total_seeds_count > 0 and n_seeds_with_source == 0:
            readiness = {
                "ready": False,
                "reason": (
                    f"0/{total_seeds_count} seeds tienen source_id: "
                    "ejecutá 'b2g seed --resolve' para obtener IDs de OpenAlex "
                    "necesarios para el forrajeo."
                ),
            }
        else:
            readiness = {"ready": True, "reason": None}
    else:
        readiness = {"ready": True, "reason": None}

    return {
        "loop_state": state_str,
        "transitions_available": transitions,
        "curation_available": curation,
        "round": current_round,
        "counts_by_status": counts,
        "total_papers": total,
        "referenced_not_fetched": referenced_not_fetched,
        "next_best_action": action,
        "readiness": readiness,
        "build_preview": build_prev,
    }


# Comando Click


@click.command("status")
@json_option
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
    - ADR 0029: workspace resuelto (root y fuente de resolución).
    """
    # ADR 0029: resolver workspace para obtener library_path + info de origen
    ws = resolve_workspace(ctx.obj)
    store_path = ws.library_path

    data = run_status(store_path)

    data["workspace"] = {
        "root": str(ws.root) if ws.root is not None else None,
        "source": ws.source,
    }

    # ADR 0029 — aviso de staleness de la cache de redes.
    # Si networks/.corpus_hash existe y no coincide con el corpus vivo,
    # se emite un aviso accionable (no se regenera automáticamente).
    # R5: open_store_readonly para consistencia (no auto-crea ante typo;
    # mapea StoreLockedError → exit 5 vía el decorador @handle_errors).
    warnings: list[str] = []
    from bib2graph.backends.memory import compute_corpus_hash

    _store = open_store_readonly(store_path)
    _corpus = _store.load()
    live_hash = compute_corpus_hash(_corpus.to_arrow())
    stale = ws.is_networks_cache_stale(live_hash)

    if stale:
        warnings.append(
            "La cache de redes (networks/) está desactualizada: el corpus cambió "
            "desde el último build. Ejecutá 'b2g build' para regenerarla."
        )

    data["networks_cache_stale"] = stale

    if json_mode(json_output):
        envelope = build_envelope(
            command="status",
            ok=True,
            data=data,
            exit_code=0,
            warnings=warnings,
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
        emit_human(
            f"Workspace: {data['workspace']['root']} (resuelto vía {data['workspace']['source']})"
        )
        ref_count = data.get("referenced_not_fetched", 0)
        if ref_count > 0:
            emit_human(f"Referenciados sin materializar: {ref_count}")
        emit_human(f"Próximo mejor paso: b2g {data['next_best_action']}")
        readiness = data["readiness"]
        ready_str = (
            "listo" if readiness["ready"] else f"NO listo — {readiness['reason']}"
        )
        emit_human(f"Preparación: {ready_str}")
        build_preview = data.get("build_preview", [])
        if build_preview:
            emit_human("Preview de redes (si corrieras build ahora):")
            for entry in build_preview:
                status_icon = "vacía" if entry["would_be_empty"] else "ok"
                line = f"  [{status_icon}] {entry['kind']}"
                if entry["would_be_empty"] and entry["reason"]:
                    line += f" — {entry['reason']} → {entry['fix_command']}"
                emit_human(line)
        for w in warnings:
            print(f"AVISO: {w}", file=sys.stderr)
