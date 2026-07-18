"""cli.commands.filter — Subcomando ``b2g filter`` (alias deprecado, #165).

Aplica filtros PRISMA deterministas al corpus: marca rejected (no borra).
Transiciona el CycleState a FILTERED tras persistir con éxito.

Shim delgado (#155): la orquestación vive en ``service.curate.filter_corpus``;
este módulo es un shim que delega.  ``curate filter`` comparte la misma fuente
de lógica para garantizar comportamiento idéntico.

``run_filter`` se mantiene aquí como función importable para tests existentes;
internamente llama a ``service.curate.filter_corpus``.

DEPRECADO (ADR 0038, #165): usar ``b2g curate filter``.  Se retira en 0.11.0.
"""

from __future__ import annotations

from datetime import UTC, datetime
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


def run_filter(
    store_path: str | Path,
    *,
    year_gte: int | None = None,
    year_lte: int | None = None,
    language: list[str] | None = None,
    type_in: list[str] | None = None,
    min_citations: int | None = None,
    decided_at: datetime | None = None,
) -> dict[str, Any]:
    """Shim CLI: delega en ``service.curate.filter_corpus``.

    Mantiene la firma original de ``run_filter`` para que los tests existentes
    no cambien.  Toda la lógica vive en ``service.curate.filter_corpus``.

    R2 (ADR 0017 enmendado): ``decided_at`` es inyectado por el llamador.
    ``filter_cmd`` pasa ``datetime.now(UTC)``; los tests pueden pasar un
    timestamp fijo para determinismo.

    Args:
        store_path: Ruta al archivo ``.duckdb``.
        year_gte: Filtrar años >= este valor.
        year_lte: Filtrar años <= este valor.
        language: Lista de códigos ISO 639-1 a incluir.
        type_in: Lista de áreas de investigación a incluir.
        min_citations: Mínimo de citantes en cited_by_id.
        decided_at: Timestamp inyectado por el llamador (R2/ADR 0017).

    Returns:
        Dict con ``steps`` (conteos PRISMA por paso) y ``total_papers``.

    Raises:
        DataError: Si ningún criterio es válido.
        StoreError: Si el store está bloqueado.
    """
    from bib2graph.service.curate import filter_corpus

    return filter_corpus(
        store_path,
        year_gte=year_gte,
        year_lte=year_lte,
        language=language,
        type_in=type_in,
        min_citations=min_citations,
        decided_at=decided_at,
    )


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
@json_option
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
    dep_msg = emit_deprecation("b2g filter", "b2g curate filter")
    ws = resolve_workspace(ctx.obj)
    # R2: el reloj se inyecta en la frontera CLI (ADR 0017 enmendado).
    now = datetime.now(UTC)
    data = run_filter(
        ws.library_path,
        year_gte=year_gte,
        year_lte=year_lte,
        language=list(language) if language else None,
        type_in=list(type_in) if type_in else None,
        min_citations=min_citations,
        decided_at=now,
    )

    # ADR 0045 (#259): eco de workspace + warning accionable en walk-up.
    data["workspace"] = workspace_echo(ws)

    if json_mode(json_output):
        envelope = build_envelope(
            command="filter",
            ok=True,
            data=data,
            exit_code=0,
            warnings=[dep_msg, *workspace_walkup_warning(ws)],
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
