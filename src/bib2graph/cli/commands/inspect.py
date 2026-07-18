"""cli.commands.inspect — Subcomando ``b2g inspect`` (alias deprecado, #165).

Dump read-only del manifest y conteos. Con --id: datos de un paper.
NO transiciona el CycleState.

DEPRECADO (ADR 0038, #165): usar ``b2g read show`` (con ``--id``) o
``b2g status`` (sin ``--id``).  Se retira en 0.11.0.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click

from bib2graph.cli._deprecation import emit_deprecation
from bib2graph.cli._envelope import build_envelope, emit, emit_human
from bib2graph.cli._errors import DataError, handle_errors
from bib2graph.cli._options import json_mode, json_option
from bib2graph.cli._store import (
    open_store,
    resolve_workspace,
    workspace_echo,
    workspace_walkup_warning,
)
from bib2graph.constants import Col


def run_inspect(
    store_path: str | Path,
    *,
    paper_id: str | None = None,
) -> dict[str, Any]:
    """Inspecciona el manifest del corpus o un paper específico.

    Sin ``paper_id``: devuelve el manifest (equations/filters/chaining/
    openalex_version) y conteos.
    Con ``paper_id``: devuelve los datos + provenance de ese paper.

    Args:
        store_path: Ruta al archivo ``.duckdb``.
        paper_id: ID del paper a inspeccionar (opcional).

    Returns:
        Dict con los datos de inspección.

    Raises:
        DataError: Si el ``paper_id`` no existe en el corpus.
        StoreError: Si el store está bloqueado.
    """
    store = open_store(store_path)
    corpus = store.load()

    if paper_id is not None:
        table = corpus.to_arrow()
        rows = table.to_pylist()
        matching = [r for r in rows if str(r.get(Col.ID)) == paper_id]
        if not matching:
            raise DataError(
                f"Paper '{paper_id}' no encontrado en el corpus. "
                "Verificá el id con ``b2g status``."
            )
        row = matching[0]
        provenance_raw = row.get(Col.PROVENANCE)
        provenance: list[object] = []
        if provenance_raw:
            try:
                provenance = json.loads(str(provenance_raw))
            except (json.JSONDecodeError, TypeError):
                provenance = [str(provenance_raw)]

        return {
            "paper_id": paper_id,
            "title": row.get(Col.TITLE),
            "year": row.get(Col.YEAR),
            "curation_status": row.get(Col.CURATION_STATUS),
            "is_seed": row.get(Col.IS_SEED),
            "provenance": provenance,
        }

    manifest = corpus.manifest
    equations = [
        {
            "query": eq.query if hasattr(eq, "query") else str(eq),
        }
        for eq in manifest.equations
    ]
    filters = [
        {
            "name": f.name if hasattr(f, "name") else str(f),
            "count_before": getattr(f, "count_before", None),
            "count_after": getattr(f, "count_after", None),
        }
        for f in manifest.filters
    ]

    return {
        "manifest": {
            "schema_version": manifest.schema_version,
            "openalex_version": manifest.openalex_version,
            "equations": equations,
            "filters": filters,
            "chaining": manifest.chaining.model_dump() if manifest.chaining else None,
        },
        "total_papers": len(corpus),
        "loop_state": store.backend.loop_state().value
        if store.backend.loop_state()
        else None,
    }


@click.command("inspect")
@click.option(
    "--id",
    "paper_id",
    default=None,
    help="ID del paper a inspeccionar.",
)
@json_option
@click.pass_context
@handle_errors("inspect")
def inspect_cmd(
    ctx: click.Context,
    paper_id: str | None,
    json_output: bool,
) -> None:
    """Inspecciona el manifest o un paper específico (read-only).

    Sin --id: muestra el manifest y conteos.
    Con --id: muestra datos + provenance de ese paper.
    """
    new_cmd = "b2g read show" if paper_id else "b2g status"
    dep_msg = emit_deprecation("b2g inspect", new_cmd)
    ws = resolve_workspace(ctx.obj)
    data = run_inspect(ws.library_path, paper_id=paper_id)

    # ADR 0045 (#259): eco de workspace + warning accionable en walk-up.
    data["workspace"] = workspace_echo(ws)

    if json_mode(json_output):
        envelope = build_envelope(
            command="inspect",
            ok=True,
            data=data,
            exit_code=0,
            warnings=[dep_msg, *workspace_walkup_warning(ws)],
        )
        emit(envelope)
    else:
        if paper_id:
            emit_human(f"Paper: {data.get('paper_id')}")
            emit_human(f"Título: {data.get('title')}")
            emit_human(f"Año: {data.get('year')}")
            emit_human(f"Estado: {data.get('curation_status')}")
            emit_human(f"Es semilla: {data.get('is_seed')}")
        else:
            emit_human(f"Total papers: {data.get('total_papers')}")
            emit_human(f"CycleState: {data.get('loop_state')}")
            manifest = data.get("manifest", {})
            emit_human(f"OpenAlex version: {manifest.get('openalex_version')}")
            emit_human(f"Ecuaciones: {len(manifest.get('equations', []))}")
            emit_human(f"Filtros aplicados: {len(manifest.get('filters', []))}")
