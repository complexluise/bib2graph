"""cli.commands.chain — Subcomando ``b2g chain``.

Expande el corpus con candidatos rankeados por information scent.
Transiciona el CycleState a FORAGED tras persistir con éxito.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import click

from bib2graph.cli._envelope import build_envelope, emit, emit_human
from bib2graph.cli._errors import DependencyError, handle_errors
from bib2graph.cli._store import open_store, resolve_library_path

# ---------------------------------------------------------------------------
# Función núcleo (testeable, sin Click)
# ---------------------------------------------------------------------------


def run_chain(
    store_path: str | Path,
    *,
    direction: Literal["backward", "forward", "both"] = "both",
    depth: int = 1,
    max_candidates: int | None = None,
    max_citing_per_paper: int | None = 50,
    email: str | None = None,
    transport: Any = None,
) -> dict[str, Any]:
    """Expande el corpus con candidatos rankeados por information scent.

    Args:
        store_path: Ruta al archivo ``.duckdb``.
        direction: Dirección del chaining (``backward``, ``forward``, ``both``).
        depth: Profundidad del chaining (solo 1 soportado; >1 → NotImplementedError).
        max_candidates: Tope de candidatos (None = sin límite).
        max_citing_per_paper: Presupuesto de citantes por semilla en forward
            chaining (default 50; None = sin tope).
        email: Email para el polite pool de OpenAlex.
        transport: Transport inyectable para tests.

    Returns:
        Dict con ``candidates_found``, ``total_papers``, ``ranking_preview``.

    Raises:
        DependencyError: Si el source no soporta forward chaining.
        NetworkError: Si falla la conexión a OpenAlex.
        StoreError: Si el store está bloqueado.
    """
    from bib2graph.cycle import apply_transition
    from bib2graph.foraging import Forager
    from bib2graph.sources.openalex import OpenAlexSource

    merged_backend_close = None
    store = open_store(store_path)
    try:
        corpus = store.load()

        # R3 — fuente única de verdad: el destino de la transición lo dicta cycle.py,
        # no un literal en el comando (ADR 0016 enmendado §1).
        current_state = store.backend.loop_state()
        current_round = store.backend.loop_round()
        new_state, new_round = apply_transition(current_state, "chain", current_round)

        source = OpenAlexSource(email=email, transport=transport)

        # Pre-check explícito: si la dirección requiere forward y el source no
        # tiene ``fetch_citing_batch`` (ni ``fetch_citing`` como fallback), fallamos
        # antes de entrar al Forager — así un ``AttributeError`` genuino que surja
        # dentro de chain/merge/_fetch_forward no queda disfrazado de "source no
        # soporta forward" (exit 3).
        if direction in ("forward", "both") and not (
            hasattr(source, "fetch_citing_batch") or hasattr(source, "fetch_citing")
        ):
            raise DependencyError(
                f"El source {type(source).__name__!r} no soporta forward chaining: "
                "no tiene el método ``fetch_citing_batch`` ni ``fetch_citing``. "
                "Usá un source compatible (p. ej. OpenAlexSource) o cambiá "
                "--direction a 'backward'."
            )

        try:
            forager = Forager(
                source,
                depth=depth,
                max_candidates=max_candidates,
                max_citing_per_paper=max_citing_per_paper,
            )
            ranked = forager.chain(corpus, direction=direction)
        except NotImplementedError as exc:
            raise DependencyError(
                f"Profundidad {depth} no soportada aún: {exc}. Usá depth=1 (por defecto)."
            ) from exc
        # httpx.HTTPError y subclases (ConnectError, TimeoutException,
        # RemoteProtocolError, TransportError, etc.) se dejan propagar: el
        # decorador @handle_errors las captura por tipo y emite exit 4.
        # AttributeError genuino se propaga limpio (no se disfraza de exit 3).

        # Merge de candidatos forward materializados en el corpus.
        # Los IDs backward (ranked.observed_refs) NO van al corpus — se persisten
        # en la tabla auxiliar ``referenced_but_not_fetched`` (#54, opción B).
        merged = corpus.merge(ranked.corpus)
        candidates_found = len(ranked.corpus)
        total_papers = len(merged)
        ranking_preview = [
            {"id": id_, "scent": scent} for id_, scent in ranked.ranking[:10]
        ]
        merged_backend_close = getattr(merged._backend, "close", None)
        store.persist(merged)

        # #54: persistir IDs backward observados en la tabla auxiliar.
        # El backend del store (DuckDBBackend) ya tiene add_referenced_refs;
        # el InMemoryBackend lo implementa también para tests.
        if ranked.observed_refs:
            store.backend.add_referenced_refs(
                ranked.observed_refs, cycle_round=new_round
            )

        store.backend.set_loop_state(new_state, cycle_round=new_round)
    finally:
        # Ver run_seed_from_bib: cierra explícitamente las conexiones DuckDB
        # para evitar segfault en Linux ante llamadas consecutivas al mismo archivo.
        if merged_backend_close is not None:
            merged_backend_close()
        store.close()

    return {
        "candidates_found": candidates_found,
        "total_papers": total_papers,
        "direction": direction,
        "depth": depth,
        "ranking_preview": ranking_preview,
        "observed_refs_count": len(ranked.observed_refs),
    }


# ---------------------------------------------------------------------------
# Comando Click
# ---------------------------------------------------------------------------


@click.command("chain")
@click.option(
    "--direction",
    type=click.Choice(["backward", "forward", "both"]),
    default="both",
    show_default=True,
    help="Dirección del chaining.",
)
@click.option(
    "--depth",
    type=int,
    default=1,
    show_default=True,
    help="Profundidad del chaining (solo 1 soportado).",
)
@click.option(
    "--max-candidates",
    type=int,
    default=None,
    help="Tope de candidatos (sin límite por defecto).",
)
@click.option(
    "--max-citing",
    "max_citing_per_paper",
    type=int,
    default=50,
    show_default=True,
    help="Presupuesto de citantes por semilla en forward chaining.",
)
@click.option(
    "--email",
    default=None,
    help="Email para el polite pool de OpenAlex.",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    help="Salida JSON estructurada.",
)
@click.pass_context
@handle_errors("chain")
def chain_cmd(
    ctx: click.Context,
    direction: str,
    depth: int,
    max_candidates: int | None,
    max_citing_per_paper: int,
    email: str | None,
    json_output: bool,
) -> None:
    """Expande el corpus con candidatos rankeados por information scent.

    Tras el chain, el estado del lazo transiciona a FORAGED.
    """
    store_path = resolve_library_path(ctx.obj)
    data = run_chain(
        store_path,
        direction=direction,  # type: ignore[arg-type]
        depth=depth,
        max_candidates=max_candidates,
        max_citing_per_paper=max_citing_per_paper,
        email=email,
    )

    if json_output:
        envelope = build_envelope(
            command="chain",
            ok=True,
            data=data,
            exit_code=0,
        )
        emit(envelope)
    else:
        emit_human(f"Candidatos encontrados: {data['candidates_found']}")
        emit_human(f"Total en corpus: {data['total_papers']}")
        if data["ranking_preview"]:
            emit_human("Top candidatos por scent:")
            for item in data["ranking_preview"][:5]:
                emit_human(f"  {item['id']}: {item['scent']:.3f}")
