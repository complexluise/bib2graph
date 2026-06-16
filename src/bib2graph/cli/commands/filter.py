"""cli.commands.filter — Subcomando ``b2g filter``.

Aplica filtros PRISMA deterministas al corpus: marca rejected (no borra).
Transiciona el LoopState a FILTERED tras persistir con éxito.
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


def run_filter(
    store_path: str | Path,
    *,
    year_gte: int | None = None,
    year_lte: int | None = None,
    language: list[str] | None = None,
    type_in: list[str] | None = None,
    min_citations: int | None = None,
) -> dict[str, Any]:
    """Aplica filtros PRISMA al corpus marcando rejected los excluidos.

    Los filtros se aplican en orden; cada uno ve el resultado del anterior.
    El LoopState transiciona a FILTERED tras persistir con éxito.

    Args:
        store_path: Ruta al archivo ``.duckdb``.
        year_gte: Filtrar años >= este valor.
        year_lte: Filtrar años <= este valor.
        language: Lista de códigos ISO 639-1 a incluir (ej. ``["en", "es"]``).
        type_in: Lista de áreas de investigación a incluir.
        min_citations: Mínimo de citantes (``len(cited_by_id) >= min_citations``).

    Returns:
        Dict con ``steps`` (conteos PRISMA por paso) y ``total_papers``.

    Raises:
        DataError: Si ningún criterio es válido.
        StoreError: Si el store está bloqueado.
    """
    from bib2graph.cycle import apply_transition
    from bib2graph.filters.prisma import FilterCriterion, apply_filters

    criteria: list[FilterCriterion] = []

    if year_gte is not None:
        criteria.append(FilterCriterion(field="year", op="gte", value=year_gte))
    if year_lte is not None:
        criteria.append(FilterCriterion(field="year", op="lte", value=year_lte))
    if language:
        criteria.append(FilterCriterion(field="language", op="in", value=language))
    if type_in:
        criteria.append(FilterCriterion(field="type", op="in", value=type_in))
    if min_citations is not None:
        criteria.append(
            FilterCriterion(field="min_citations", op="gte", value=min_citations)
        )

    if not criteria:
        raise DataError(
            "Debés especificar al menos un criterio de filtro: "
            "--year-gte, --year-lte, --language, --type, o --min-citations."
        )

    store = open_store(store_path)
    corpus = store.load()

    # R3 — fuente única de verdad: el destino de la transición lo dicta cycle.py,
    # no un literal en el comando (ADR 0016 enmendado §1).
    current_state = store.backend.loop_state()
    current_round = store.backend.loop_round()
    new_state, new_round = apply_transition(current_state, "filter", current_round)

    # R2: el reloj se inyecta en la frontera (ADR 0017 enmendado); el núcleo
    # no llama datetime.now(). Un único timestamp para todos los pasos de
    # filtrado de esta invocación.
    now = datetime.now(UTC)
    filtered_corpus, steps = apply_filters(corpus, criteria, decided_at=now)
    store.persist(filtered_corpus)
    store.backend.set_loop_state(new_state, cycle_round=new_round)

    steps_data = [
        {
            "name": s.name,
            "criteria": s.criteria,
            "count_before": s.count_before,
            "count_after": s.count_after,
            "excluded": s.count_before - s.count_after,
        }
        for s in steps
    ]

    return {
        "steps": steps_data,
        "total_papers": len(filtered_corpus),
        "criteria_applied": len(criteria),
    }


# ---------------------------------------------------------------------------
# Comando Click
# ---------------------------------------------------------------------------


@click.command("filter")
@click.option("--year-gte", type=int, default=None, help="Incluir años >= este valor.")
@click.option("--year-lte", type=int, default=None, help="Incluir años <= este valor.")
@click.option(
    "--language",
    multiple=True,
    help="Códigos ISO 639-1 a incluir (repetible: --language en --language es).",
)
@click.option(
    "--type",
    "type_in",
    multiple=True,
    help="Áreas de investigación a incluir (repetible).",
)
@click.option(
    "--min-citations",
    type=int,
    default=None,
    help="Mínimo de citantes en cited_by_id.",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    help="Salida JSON estructurada.",
)
@click.pass_context
@handle_errors("filter")
def filter_cmd(
    ctx: click.Context,
    year_gte: int | None,
    year_lte: int | None,
    language: tuple[str, ...],
    type_in: tuple[str, ...],
    min_citations: int | None,
    json_output: bool,
) -> None:
    """Aplica filtros PRISMA al corpus (marca rejected, no borra).

    Tras el filtro, el estado del lazo transiciona a FILTERED.
    """
    store_path = ctx.obj["store"]
    data = run_filter(
        store_path,
        year_gte=year_gte,
        year_lte=year_lte,
        language=list(language) if language else None,
        type_in=list(type_in) if type_in else None,
        min_citations=min_citations,
    )

    if json_output:
        envelope = build_envelope(
            command="filter",
            ok=True,
            data=data,
            exit_code=0,
        )
        emit(envelope)
    else:
        emit_human(f"Filtros aplicados: {data['criteria_applied']}")
        for step in data["steps"]:
            emit_human(
                f"  {step['name']}: {step['count_before']} → {step['count_after']} "
                f"(-{step['excluded']})"
            )
        emit_human(f"Total en corpus: {data['total_papers']}")
