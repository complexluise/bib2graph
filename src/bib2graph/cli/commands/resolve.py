"""cli.commands.resolve — Subcomando ``b2g resolve`` (alias deprecado, #165).

Resuelve los DOIs del workspace actual a IDs de OpenAlex (``source_id``),
habilitando el enriquecimiento posterior con ``b2g enrich`` y el forrajeo
con ``b2g chain`` para papers ingresados desde BibTeX (GAP-1, ADR 0035).

Sin source_id (vacío tras ``seed --from-bib``), los comandos ``enrich`` y
``chain`` devuelven 0 resultados.  ``b2g resolve`` cierra ese gap.

Flags:
  --email       Email para el polite pool de OpenAlex (recomendado).
  --workspace   Workspace a resolver (resolución por ambiente si se omite).
  --json        Salida JSON estructurada (envelope versionado, ADR 0021).

NO transiciona el CycleState (operación ortogonal al lazo, igual que enrich).

DEPRECADO (ADR 0038, #165): usar ``b2g seed --resolve``.  Se retira en 0.11.0.
"""

from __future__ import annotations

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


def run_resolve(
    store_path: str | Path,
    *,
    email: str | None = None,
    transport: Any = None,
) -> dict[str, Any]:
    """Resuelve DOIs pendientes a source_id de OpenAlex y persiste.

    Delega en ``service.resolve.resolve_dois``: filtra papers con doi != NULL
    AND source_id IS NULL, consulta OpenAlex (batcheado) y persiste el
    resultado.  Idempotente.

    Args:
        store_path: Ruta al archivo ``.duckdb``.
        email: Email para el polite pool de OpenAlex.
        transport: Transport inyectable para tests (``httpx.MockTransport``).

    Returns:
        Dict con ``resolved``, ``total_with_doi``, ``already_resolved``,
        ``total_papers``.

    Raises:
        NetworkError: Si falla la conexión a OpenAlex (exit 4).
        StoreError: Si el store está bloqueado (exit 5).
    """
    from bib2graph.service.resolve import resolve_dois

    return resolve_dois(store_path, email=email, transport=transport)


@click.command("resolve")
@click.option(
    "--email",
    default=None,
    help="Email para el polite pool de OpenAlex (recomendado).",
)
@json_option
@click.pass_context
@handle_errors("resolve")
def resolve_cmd(
    ctx: click.Context,
    email: str | None,
    json_output: bool,
) -> None:
    """Resuelve DOIs del corpus a IDs de OpenAlex (source_id).

    Papers sembrados desde BibTeX tienen DOI pero no source_id: sin source_id,
    ``b2g enrich`` y ``b2g chain`` devuelven 0.  Este comando cierra el GAP-1
    (ADR 0035): consulta OpenAlex por cada DOI sin resolver y puebla source_id.

    Idempotente: papers que ya tienen source_id no se tocan.

    \b
    NO transiciona el CycleState (ortogonal al lazo, como enrich).

    \b
    Ejemplo:
      b2g seed --from-bib semillas.bib
      b2g resolve --email mi@email.com
      b2g enrich --email mi@email.com
    """
    dep_msg = emit_deprecation("b2g resolve", "b2g seed --resolve")
    ws = resolve_workspace(ctx.obj)
    data = run_resolve(ws.library_path, email=email)

    # ADR 0045 (#259): eco de workspace + warning accionable en walk-up.
    data["workspace"] = workspace_echo(ws)

    if json_mode(json_output):
        envelope = build_envelope(
            command="resolve",
            ok=True,
            data=data,
            exit_code=0,
            warnings=[dep_msg, *workspace_walkup_warning(ws)],
        )
        emit(envelope)
    else:
        emit_human(f"Papers con DOI en corpus:    {data['total_with_doi']}")
        emit_human(f"Ya tenían source_id:         {data['already_resolved']}")
        emit_human(f"Resueltos en esta corrida:   {data['resolved']}")
        emit_human(f"Total de papers en corpus:   {data['total_papers']}")
