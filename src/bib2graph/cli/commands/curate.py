"""cli.commands.curate — Grupo noun-verb ``b2g curate`` (#155, superficie CLI 0.10.0).

Convierte ``curate`` de comando plano con flags en un **grupo noun-verb** con
cinco subcomandos:

  ``curate dump``    — exporta papers a CSV para revisión offline.
  ``curate apply``   — reimporta decisiones desde el CSV editado.
  ``curate accept``  — acepta papers por id (transversal, sin FSM).
  ``curate reject``  — rechaza papers por id (transversal, sin FSM).
  ``curate filter``  — aplica filtros PRISMA y transiciona a FILTERED.

Molde: ``read.py`` (#156/#157) — grupo noun-verb con ``invoke_without_command=True``
y check manual para exit 0 sin subcomando (Click 8.4 usa exit 2 con
``no_args_is_help=True`` en grupos).

BREAKING (#155):
  - ``curate --dump`` y ``curate --from-csv`` eliminados (sin alias).
  - ``curate --all`` eliminado; usar ``curate dump --scope all``.

TRANSVERSAL (ADR 0016 enmendado, R3):
  ``dump``, ``apply``, ``accept`` y ``reject`` son transversales: no transicionan
  el CycleState.  ``filter`` SÍ transiciona a FILTERED (el verbo define la
  transición, precedente D1 de #159).

Capa de servicios (#155):
  Toda la lógica vive en ``service.curate``; este módulo son shims delgados
  que inyectan el reloj (frontera CLI, R2/ADR 0017) y emiten el envelope.

Backward compat con tests existentes:
  ``CSV_COLUMNS``, ``CURATE_CSV_FILENAME``, ``CSV_REQUIRED_COLUMNS``,
  ``VALID_DECISIONS``, ``VALID_SCOPES``, ``run_curate_dump``,
  ``run_curate_from_csv`` se re-exportan desde ``service.curate`` para que los
  tests que importan de ``bib2graph.cli.commands.curate`` sigan funcionando.

Flujo canónico:
    b2g curate dump                          # exporta candidatos a curacion.csv
    b2g curate dump --scope all              # exporta todo el corpus
    b2g curate dump --out mi.csv             # override de ruta
    b2g curate apply curacion.csv            # aplica decisiones
    b2g curate apply curacion.csv --by maria # con identificador de curador
    b2g curate accept --ids W1 --ids W2      # acepta por id
    b2g curate reject --ids W3               # rechaza por id
    b2g curate filter --year-gte 2018        # filtra y transiciona a FILTERED
"""

from __future__ import annotations

from datetime import UTC, datetime

import click

from bib2graph.cli._envelope import build_envelope, emit, emit_human
from bib2graph.cli._errors import handle_errors
from bib2graph.cli._options import json_mode, json_option
from bib2graph.cli._store import resolve_library_path, resolve_workspace
from bib2graph.service.curate import (
    CSV_COLUMNS,
    CSV_REQUIRED_COLUMNS,
    CURATE_CSV_FILENAME,
    VALID_DECISIONS,
    VALID_SCOPES,
    run_curate_dump,
    run_curate_from_csv,
)

__all__ = [
    "CSV_COLUMNS",
    "CSV_REQUIRED_COLUMNS",
    "CURATE_CSV_FILENAME",
    "VALID_DECISIONS",
    "VALID_SCOPES",
    "curate_grp",
    "run_curate_dump",
    "run_curate_from_csv",
]


# Grupo raíz
@click.group("curate", invoke_without_command=True)
@click.pass_context
def curate_grp(ctx: click.Context) -> None:
    """Curación del corpus: dump, apply, accept, reject, filter.

    Subcomandos: dump, apply, accept, reject, filter.

    Ejemplos:
        b2g curate dump
        b2g curate dump --scope all
        b2g curate apply curacion.csv
        b2g curate accept --ids W1 --ids W2
        b2g curate reject --ids W3
        b2g curate filter --year-gte 2018 --year-lte 2024
    """
    ctx.ensure_object(dict)
    # Click 8.4: no_args_is_help=True en grupos termina con exit 2.
    # Usamos invoke_without_command=True + check manual para exit 0 correcto.
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# curate dump
@curate_grp.command("dump")
@click.option(
    "--out",
    "out_override",
    default=None,
    type=click.Path(),
    help=(
        "Ruta de salida del CSV. Override del default <workspace>/exports/curacion.csv."
    ),
)
@click.option(
    "--scope",
    default="candidates",
    type=click.Choice(["candidates", "seeds", "all"]),
    show_default=True,
    help=(
        "Qué papers exportar. "
        "'candidates' (default) = forrajeados a revisar (is_seed=False, status=candidate). "
        "'seeds' = semillas originales. "
        "'all' = todo el corpus."
    ),
)
@json_option
@click.pass_context
@handle_errors("curate dump")
def dump_cmd(
    ctx: click.Context,
    out_override: str | None,
    scope: str,
    json_output: bool,
) -> None:
    """Exporta papers a CSV para revisión offline.

    Por defecto exporta solo los candidatos forrajeados (is_seed=False,
    status=candidate).  Editá las columnas ``decision`` y ``note`` en
    Excel/Calc y luego reimportá con ``b2g curate apply``.

    Curación TRANSVERSAL: no transiciona el CycleState.
    """
    from pathlib import Path

    ws = resolve_workspace(ctx.obj)
    store_path = ws.library_path

    if out_override is not None:
        out_path = Path(out_override)
    else:
        out_path = ws.exports_dir / CURATE_CSV_FILENAME

    data = run_curate_dump(store_path, out_path=out_path, scope=scope)

    if json_mode(json_output):
        envelope = build_envelope(
            command="curate dump",
            ok=True,
            data=data,
            exit_code=0,
        )
        emit(envelope)
    else:
        emit_human(f"Exportados {data['papers_exported']} papers a: {data['csv_path']}")


# curate apply
@curate_grp.command("apply")
@click.argument("csv_file", type=click.Path())
@click.option(
    "--by",
    default="cli",
    show_default=True,
    help="Identificador de quien decide (curador).",
)
@json_option
@click.pass_context
@handle_errors("curate apply")
def apply_cmd(
    ctx: click.Context,
    csv_file: str,
    by: str,
    json_output: bool,
) -> None:
    """Reimporta decisiones de curación desde CSV al corpus.

    CSV_FILE es el archivo CSV editado producido por ``b2g curate dump``.
    Solo las columnas ``id`` y ``decision`` son requeridas; el resto se ignora
    (garantiza round-trip dump→apply aunque el CSV tenga columnas extra).

    Decisiones aceptadas: accepted, rejected, undecided (no-op).

    Idempotente: reimportar el mismo CSV produce el mismo estado final.

    Curación TRANSVERSAL: no transiciona el CycleState.
    """
    ws = resolve_workspace(ctx.obj)
    store_path = ws.library_path

    # R2: el reloj se inyecta en la frontera CLI (ADR 0017 enmendado).
    now = datetime.now(UTC)
    data = run_curate_from_csv(store_path, csv_file, by=by, decided_at=now)

    if json_mode(json_output):
        envelope = build_envelope(
            command="curate apply",
            ok=True,
            data=data,
            exit_code=0,
        )
        emit(envelope)
    else:
        emit_human(
            f"Importados: {data['accepted_count']} aceptados, "
            f"{data['rejected_count']} rechazados, "
            f"{data['skipped_count']} sin cambio (undecided)."
        )
        if data["not_found_count"] > 0:
            emit_human(
                f"Advertencia: {data['not_found_count']} IDs del CSV no se "
                "encontraron en el corpus (posibles typos). "
                "Verificá con ``b2g inspect``."
            )


# curate accept
@curate_grp.command("accept")
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
@json_option
@click.pass_context
@handle_errors("curate accept")
def curate_accept_cmd(
    ctx: click.Context,
    ids: tuple[str, ...],
    by: str,
    json_output: bool,
) -> None:
    """Marca papers como accepted en el corpus.

    Curación TRANSVERSAL: no transiciona el CycleState.  Disponible en
    cualquier estado del lazo (Nota 05 §4, ADR 0016 enmendado R3).
    """
    from bib2graph.service.curate import accept_papers

    store_path = resolve_library_path(ctx.obj)
    now = datetime.now(UTC)
    data = accept_papers(store_path, list(ids), by=by, decided_at=now)

    if json_mode(json_output):
        envelope = build_envelope(
            command="curate accept",
            ok=True,
            data=data,
            exit_code=0,
        )
        emit(envelope)
    else:
        emit_human(f"Aceptados {data['accepted_count']} papers.")


# curate reject
@curate_grp.command("reject")
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
@json_option
@click.pass_context
@handle_errors("curate reject")
def curate_reject_cmd(
    ctx: click.Context,
    ids: tuple[str, ...],
    by: str,
    json_output: bool,
) -> None:
    """Marca papers como rejected en el corpus.

    Curación TRANSVERSAL: no transiciona el CycleState.  Disponible en
    cualquier estado del lazo (Nota 05 §4, ADR 0016 enmendado R3).
    """
    from bib2graph.service.curate import reject_papers

    store_path = resolve_library_path(ctx.obj)
    now = datetime.now(UTC)
    data = reject_papers(store_path, list(ids), by=by, decided_at=now)

    if json_mode(json_output):
        envelope = build_envelope(
            command="curate reject",
            ok=True,
            data=data,
            exit_code=0,
        )
        emit(envelope)
    else:
        emit_human(f"Rechazados {data['rejected_count']} papers.")


# curate filter
@curate_grp.command("filter")
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
@handle_errors("curate filter")
def curate_filter_cmd(
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

    Este es el único subcomando de ``curate`` que transiciona el CycleState
    (el verbo define la transición — precedente D1 de #159).
    """
    from bib2graph.service.curate import filter_corpus

    store_path = resolve_library_path(ctx.obj)
    # R2: el reloj se inyecta en la frontera CLI (ADR 0017 enmendado).
    now = datetime.now(UTC)
    data = filter_corpus(
        store_path,
        year_gte=year_gte,
        year_lte=year_lte,
        language=list(language) if language else None,
        type_in=list(type_in) if type_in else None,
        min_citations=min_citations,
        decided_at=now,
    )

    if json_mode(json_output):
        envelope = build_envelope(
            command="curate filter",
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


# Alias curate_cmd → curate_grp (compat con registros existentes)
curate_cmd = curate_grp
