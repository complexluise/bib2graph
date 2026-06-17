"""cli.commands.accept — Subcomando ``b2g accept``.

Marca papers como accepted en el corpus.

CURACIÓN TRANSVERSAL (ADR 0016 enmendado, R3): ``accept`` y ``reject`` están
disponibles en CUALQUIER estado del lazo y NO transicionan el CycleState.
Son lo único irreductiblemente humano (Nota 05 §4, pasos 0/4/7).  El mapa del
lazo (``b2g status``) los muestra siempre en ``curation_available``, separado
de ``transitions_available``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import click

from bib2graph.cli._envelope import build_envelope, emit, emit_human
from bib2graph.cli._errors import DataError, handle_errors
from bib2graph.cli._store import open_store, resolve_library_path

# ---------------------------------------------------------------------------
# Función núcleo (testeable, sin Click)
# ---------------------------------------------------------------------------


def run_accept(
    store_path: str | Path,
    ids: list[str],
    *,
    by: str = "cli",
) -> dict[str, Any]:
    """Marca los papers dados como accepted y persiste.

    Verifica que todos los ids existan en el corpus antes de operar.

    Args:
        store_path: Ruta al archivo ``.duckdb``.
        ids: Lista de ids a aceptar.
        by: Identificador de quien decide (default: ``"cli"``).

    Returns:
        Dict con ``accepted_count``, ``ids``.

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
    updated = corpus.accept(ids, by=by, decided_at=now)
    store.persist(updated)

    return {
        "accepted_count": len(ids),
        "ids": ids,
    }


# ---------------------------------------------------------------------------
# Comando Click
# ---------------------------------------------------------------------------


@click.command("accept")
@click.option(
    "--ids",
    required=True,
    multiple=True,
    help="IDs de papers a aceptar (repetible: --ids ID1 --ids ID2).",
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
@handle_errors("accept")
def accept_cmd(
    ctx: click.Context,
    ids: tuple[str, ...],
    by: str,
    json_output: bool,
) -> None:
    """Marca papers como accepted en el corpus.

    Curación TRANSVERSAL: no transiciona el CycleState.  Disponible en
    cualquier estado del lazo (Nota 05 §4, ADR 0016 enmendado R3).
    """
    store_path = resolve_library_path(ctx.obj)
    data = run_accept(store_path, list(ids), by=by)

    if json_output:
        envelope = build_envelope(
            command="accept",
            ok=True,
            data=data,
            exit_code=0,
        )
        emit(envelope)
    else:
        emit_human(f"Aceptados {data['accepted_count']} papers.")
