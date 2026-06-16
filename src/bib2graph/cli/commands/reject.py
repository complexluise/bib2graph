"""cli.commands.reject — Subcomando ``b2g reject``.

Marca papers como rejected en el corpus.
NO transiciona el LoopState.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import click

from bib2graph.cli._envelope import build_envelope, emit, emit_human
from bib2graph.cli._errors import DataError, handle_errors
from bib2graph.cli._store import open_store

# ---------------------------------------------------------------------------
# Función núcleo (testeable, sin Click)
# ---------------------------------------------------------------------------


def run_reject(
    store_path: str | Path,
    ids: list[str],
    *,
    by: str = "cli",
) -> dict[str, Any]:
    """Marca los papers dados como rejected y persiste.

    Verifica que todos los ids existan en el corpus antes de operar.

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
    if not ids:
        raise DataError("Debés especificar al menos un ID con --ids.")

    store = open_store(store_path)
    corpus = store.load()

    # Verificar que todos los ids existen
    existing_ids = {str(r["id"]) for r in corpus.to_arrow().to_pylist()}
    missing = [id_ for id_ in ids if id_ not in existing_ids]
    if missing:
        raise DataError(
            f"IDs no encontrados en el corpus: {missing}. "
            "Verificá los ids con ``b2g inspect``."
        )

    # R2: el reloj se inyecta en la frontera (ADR 0017 enmendado); el núcleo
    # no llama datetime.now().
    now = datetime.now(UTC)
    updated = corpus.reject(ids, by=by, decided_at=now)
    store.persist(updated)

    return {
        "rejected_count": len(ids),
        "ids": ids,
    }


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
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    help="Salida JSON estructurada.",
)
@click.pass_context
@handle_errors("reject")
def reject_cmd(
    ctx: click.Context,
    ids: tuple[str, ...],
    by: str,
    json_output: bool,
) -> None:
    """Marca papers como rejected en el corpus.

    No transiciona el LoopState.
    """
    store_path = ctx.obj["store"]
    data = run_reject(store_path, list(ids), by=by)

    if json_output:
        envelope = build_envelope(
            command="reject",
            ok=True,
            data=data,
            exit_code=0,
        )
        emit(envelope)
    else:
        emit_human(f"Rechazados {data['rejected_count']} papers.")
