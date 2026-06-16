"""cli.commands.validate — Subcomando ``b2g validate``.

Valida el schema del store y la consistencia del corpus.
Exit 0: válido. Exit 2: datos inválidos. Exit 5: store corrupto/bloqueado.
NO transiciona el LoopState.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from bib2graph.cli._envelope import build_envelope, emit, emit_human
from bib2graph.cli._errors import DataError, StoreError, handle_errors
from bib2graph.cli._store import open_store_readonly
from bib2graph.constants import Col, CurationStatus

# ---------------------------------------------------------------------------
# Función núcleo (testeable, sin Click)
# ---------------------------------------------------------------------------


def run_validate(store_path: str | Path) -> dict[str, Any]:
    """Valida el schema del store y la consistencia del corpus.

    Abre el store, exporta la tabla Arrow y valida con ``validate_table``.
    Verifica que todos los papers tengan ``id`` no nulo y ``title`` no nulo.

    Args:
        store_path: Ruta al archivo ``.duckdb``.

    Returns:
        Dict con ``valid``, ``total_papers``, ``issues`` (lista de problemas).

    Raises:
        DataError: Si el schema es inválido o hay inconsistencias.
        StoreError: Si el store está bloqueado o corrupto.
    """
    from bib2graph.schemas import SchemaError, validate_table

    # R5: open_store_readonly falla si el archivo no existe (no auto-crea).
    store = open_store_readonly(store_path)

    try:
        corpus = store.load()
        table = corpus.to_arrow()
    except SchemaError as exc:
        raise DataError(
            f"Schema inválido en el store: {exc}. "
            "El store puede estar corrupto o ser de una versión incompatible."
        ) from exc
    except Exception as exc:
        exc_class = type(exc).__name__
        if "Schema" in exc_class or "Arrow" in exc_class:
            raise DataError(f"Error de schema: {exc}") from exc
        raise StoreError(
            f"Error al leer el store: {exc}. El archivo puede estar corrupto."
        ) from exc

    # Validación con validate_table (lanza SchemaError si falla)
    try:
        validate_table(table)
    except SchemaError as exc:
        raise DataError(
            f"Schema del corpus inválido: {exc}. Verificá la integridad del store."
        ) from exc

    # Verificaciones de consistencia
    issues = []
    rows = table.to_pylist()

    null_ids = [i for i, r in enumerate(rows) if not r.get(Col.ID)]
    if null_ids:
        issues.append(f"{len(null_ids)} papers con id nulo (filas: {null_ids[:5]}...)")

    null_titles = [i for i, r in enumerate(rows) if not r.get(Col.TITLE)]
    if null_titles:
        issues.append(
            f"{len(null_titles)} papers sin título (filas: {null_titles[:5]}...)"
        )

    _valid_statuses = {
        CurationStatus.CANDIDATE,
        CurationStatus.ACCEPTED,
        CurationStatus.REJECTED,
    }
    invalid_status = [
        r.get(Col.ID) for r in rows if r.get(Col.CURATION_STATUS) not in _valid_statuses
    ]
    if invalid_status:
        issues.append(f"{len(invalid_status)} papers con curation_status inválido")

    if issues:
        raise DataError(
            "Inconsistencias detectadas en el corpus:\n"
            + "\n".join(f"  - {issue}" for issue in issues)
        )

    return {
        "valid": True,
        "total_papers": len(table),
        "issues": [],
    }


# ---------------------------------------------------------------------------
# Comando Click
# ---------------------------------------------------------------------------


@click.command("validate")
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    help="Salida JSON estructurada.",
)
@click.pass_context
@handle_errors("validate")
def validate_cmd(
    ctx: click.Context,
    json_output: bool,
) -> None:
    """Valida el schema y consistencia del store.

    Exit 0: válido. Exit 2: datos inválidos. Exit 5: store corrupto.
    """
    store_path = ctx.obj["store"]
    data = run_validate(store_path)

    if json_output:
        envelope = build_envelope(
            command="validate",
            ok=True,
            data=data,
            exit_code=0,
        )
        emit(envelope)
    else:
        emit_human(f"Store válido. Total papers: {data['total_papers']}")
