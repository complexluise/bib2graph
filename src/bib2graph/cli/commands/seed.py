"""cli.commands.seed — Subcomando ``b2g seed``.

Siembra el corpus desde una ecuación de búsqueda en OpenAlex.
Transiciona el CycleState a SEEDED tras persistir con éxito.

R3 — reseed: si ya había un estado previo en el store (no es la primera
siembra), la acción se trata como ``reseed`` → loop-back a SEEDED con
ronda++ (ADR 0016 enmendado).  El corpus acumulado (lo curado) se conserva.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from bib2graph.cli._envelope import build_envelope, emit, emit_human
from bib2graph.cli._errors import DataError, NetworkError, handle_errors
from bib2graph.cli._store import open_store

# ---------------------------------------------------------------------------
# Función núcleo (testeable, sin Click)
# ---------------------------------------------------------------------------


def run_seed(
    store_path: str | Path,
    equation: str,
    *,
    native: bool = False,
    email: str | None = None,
    transport: Any = None,
) -> dict[str, Any]:
    """Siembra el corpus desde OpenAlex y persiste en el store.

    Lee el estado actual del store, siembra los papers de la ecuación,
    hace merge con el corpus existente, persiste y transiciona a SEEDED.

    Args:
        store_path: Ruta al archivo ``.duckdb``.
        equation: Ecuación de búsqueda (WoS-style o nativa si ``native=True``).
        native: Si es ``True``, pasa la ecuación cruda a OpenAlex sin traducir.
        email: Email para el polite pool de OpenAlex.
        transport: Transport inyectable para tests (``httpx.MockTransport``).

    Returns:
        Dict con ``executed_query``, ``translation_report``, ``papers_added``.

    Raises:
        DataError: Si la ecuación está vacía.
        NetworkError: Si falla la conexión a OpenAlex.
        StoreError: Si el store está bloqueado.
    """
    from bib2graph.cycle import apply_transition
    from bib2graph.sources.openalex import OpenAlexSource

    if not equation or not equation.strip():
        raise DataError("La ecuación de búsqueda no puede estar vacía.")

    store = open_store(store_path)
    existing = store.load()

    # R3 — reseed: si ya había un estado previo, es un re-sembrado.
    # apply_transition lleva la ronda al valor correcto.
    current_state = store.backend.loop_state()
    current_round = store.backend.loop_round()
    if current_state is not None:
        # Re-sembrado (la idea muta): reseed → SEEDED, ronda++
        new_state, new_round = apply_transition(current_state, "reseed", current_round)
    else:
        # Primera siembra
        new_state, new_round = apply_transition(None, "seed", current_round)

    try:
        source = OpenAlexSource(email=email, transport=transport)
        result = source.seed(equation, native=native)
    except ImportError as exc:
        raise NetworkError(
            f"Error importando httpx: {exc}. Verificá la instalación del núcleo."
        ) from exc
    # httpx.HTTPError y subclases (ConnectError, TimeoutException,
    # RemoteProtocolError, TransportError, etc.) se dejan propagar: el
    # decorador @handle_errors las captura por tipo y emite exit 4.

    # Merge con el corpus existente (acumula sobre lo curado)
    merged = existing.merge(result.corpus)
    store.persist(merged)
    store.backend.set_loop_state(new_state, cycle_round=new_round)

    papers_added = len(result.corpus)

    return {
        "executed_query": result.executed_query,
        "translation_report": result.translation_report,
        "papers_added": papers_added,
        "total_papers": len(merged),
        "round": new_round,
        "reseeded": current_state is not None,
    }


# ---------------------------------------------------------------------------
# Comando Click (no se testea directamente)
# ---------------------------------------------------------------------------


@click.command("seed")
@click.option("--equation", required=True, help="Ecuación de búsqueda bibliográfica.")
@click.option(
    "--native",
    is_flag=True,
    default=False,
    help="Pasar la ecuación cruda a OpenAlex sin traducción.",
)
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
@handle_errors("seed")
def seed_cmd(
    ctx: click.Context,
    equation: str,
    native: bool,
    email: str | None,
    json_output: bool,
) -> None:
    """Siembra el corpus desde una ecuación de búsqueda en OpenAlex.

    Tras el seed, el estado del lazo transiciona a SEEDED.
    """
    store_path = ctx.obj["store"]
    data = run_seed(store_path, equation, native=native, email=email)

    if json_output:
        envelope = build_envelope(
            command="seed",
            ok=True,
            data=data,
            exit_code=0,
            warnings=data.get("translation_report", []),
        )
        emit(envelope)
    else:
        emit_human(f"Sembrados {data['papers_added']} papers nuevos.")
        emit_human(f"Query ejecutada: {data['executed_query']}")
        if data.get("translation_report"):
            emit_human("Advertencias de traducción:")
            for w in data["translation_report"]:
                emit_human(f"  - {w}")
        emit_human(f"Total en corpus: {data['total_papers']}")
