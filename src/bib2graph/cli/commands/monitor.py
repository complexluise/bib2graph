"""cli.commands.monitor — Subcomando ``b2g monitor``.

Re-chequea OpenAlex por nuevos citantes del corpus (forward chaining),
mergea los candidatos nuevos a la biblioteca viva y transiciona el
CycleState a MONITORED (paso 8 del ciclo, Ellis).

Requiere que el corpus tenga al menos una semilla con ``openalex_id``
conocido (de lo contrario el forward chaining no encuentra nada).  Si no
hay corpus ni estado previo, falla con un error accionable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from bib2graph.cli._envelope import build_envelope, emit, emit_human
from bib2graph.cli._errors import DataError, handle_errors
from bib2graph.cli._store import open_store, resolve_library_path

# ---------------------------------------------------------------------------
# Función núcleo (testeable, sin Click)
# ---------------------------------------------------------------------------


def run_monitor(
    store_path: str | Path,
    *,
    email: str | None = None,
    transport: Any = None,
) -> dict[str, Any]:
    """Re-chequea OpenAlex por nuevos citantes del corpus y transiciona a MONITORED.

    Usa forward chaining (``Forager`` con ``direction="forward"``, que usa
    ``fetch_citing_batch`` del source, batcheado y con cap por semilla) para
    encontrar nuevos papers que citan al corpus.
    Mergea los candidatos nuevos a la biblioteca viva y transiciona el estado a
    MONITORED vía ``apply_transition(current_state, "monitor", current_round)``.

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
    from bib2graph.cycle import apply_transition
    from bib2graph.foraging import Forager
    from bib2graph.sources.openalex import OpenAlexSource

    store = open_store(store_path)
    current_state = store.backend.loop_state()
    current_round = store.backend.loop_round()

    # Error accionable: monitor requiere un corpus previo sembrado.
    if current_state is None:
        raise DataError(
            "No hay corpus ni estado previo en el store. "
            "Iniciá la investigación con 'b2g seed' antes de monitorear."
        )

    corpus = store.load()
    if len(corpus) == 0:
        raise DataError(
            "El corpus está vacío. "
            "Usá 'b2g seed' para sembrar papers antes de monitorear."
        )

    new_state, new_round = apply_transition(current_state, "monitor", current_round)

    source = OpenAlexSource(email=email, transport=transport)

    # Forward chaining: nuevos citantes del corpus.
    forager = Forager(source, depth=1)
    ranked = forager.chain(corpus, direction="forward")

    # Calcular cuántos son genuinamente nuevos (no estaban en el corpus).
    existing_ids = set(corpus.to_arrow().column("id").to_pylist())
    new_candidate_ids = [
        id_
        for id_ in ranked.corpus.to_arrow().column("id").to_pylist()
        if id_ not in existing_ids
    ]
    new_candidates_count = len(new_candidate_ids)

    # Merge de candidatos nuevos y persistencia.
    merged = corpus.merge(ranked.corpus)
    store.persist(merged)
    store.backend.set_loop_state(new_state, cycle_round=new_round)

    return {
        "new_candidates": new_candidates_count,
        "total_papers": len(merged),
        "loop_state": new_state.value,
        "round": new_round,
    }


# ---------------------------------------------------------------------------
# Comando Click
# ---------------------------------------------------------------------------


@click.command("monitor")
@click.option(
    "--email",
    default=None,
    help="Email para el polite pool de OpenAlex (recomendado).",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    help="Salida JSON estructurada.",
)
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
    store_path = resolve_library_path(ctx.obj)
    data = run_monitor(store_path, email=email)

    if json_output:
        envelope = build_envelope(
            command="monitor",
            ok=True,
            data=data,
            exit_code=0,
        )
        emit(envelope)
    else:
        emit_human(f"Nuevos citantes encontrados: {data['new_candidates']}")
        emit_human(f"Total en corpus: {data['total_papers']}")
        emit_human(f"Estado: {data['loop_state']}")
        emit_human(f"Ronda: {data['round']}")
