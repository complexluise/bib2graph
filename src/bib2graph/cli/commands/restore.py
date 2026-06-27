"""cli.commands.restore — Subcomando ``b2g restore``.

Rehidrata el corpus desde un parquet curado (snapshot) sin tocar la red.
Semánticamente: ``restore`` es a ``snapshot`` lo que ``load`` es a ``dump``.
El parquet es corpus *curado*, no semilla.

Modo único requerido:
  --from-corpus <parquet>   carga el corpus desde un parquet con schema canónico.

Decisión de CycleState tras restore:
  El corpus restaurado viene de un snapshot curado — ya pasó el lazo completo
  (siembra → forrajeo → curación). Se fija el estado en ``FILTERED`` porque:
  - El corpus ya tiene decisiones de curación aplicadas (equivalente a haber
    pasado ``b2g filter``/``b2g curate``).
  - ``build`` y ``networks`` están disponibles desde ``FILTERED`` (FSM permisiva).
  - No se fuerza ``BUILT`` porque las redes no se construyeron aún en el store
    destino; sería mentirle al lazo.
  - ``SEEDED`` sería demasiado bajo: omite el hecho de que los datos ya fueron
    revisados y es semánticamente el estado de «acabo de sembrar desde la red».
  Resultado: ``build`` y ``networks`` corren sin re-forrajeo ni re-filtrado,
  respetando el estado real del corpus importado (ADR 0016 enmendado §1).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import click

from bib2graph.cli._envelope import build_envelope, emit, emit_human
from bib2graph.cli._errors import DataError, handle_errors
from bib2graph.cli._ingest import normalize_and_dedup
from bib2graph.cli._options import json_mode, json_option
from bib2graph.cli._store import open_store, resolve_library_path

# ---------------------------------------------------------------------------
# Función núcleo: rehidratación desde parquet (testeable, sin Click)
# ---------------------------------------------------------------------------


def run_restore(
    store_path: str | Path,
    corpus_path: str | Path,
) -> dict[str, Any]:
    """Carga un corpus curado desde un parquet y lo persiste en el store sin red.

    Lee el parquet con el schema canónico (``CORPUS_SCHEMA``), lo hidrata con
    ``Corpus.from_arrow``, hace merge con el corpus existente y persiste.
    Transiciona el ``CycleState`` a ``FILTERED`` (el corpus ya fue curado;
    ver docstring del módulo para la justificación).

    Preserva las columnas de curación del parquet
    (``decision`` / ``curation_status`` / ``is_seed``): el merge de ``Corpus``
    respeta el ``curation_status`` más reciente (D3 del merge).

    No instancia ``OpenAlexSource``, no hace requests. Es el camino offline
    para rehidratar un corpus curado exportado con ``b2g snapshot``.

    Args:
        store_path: Ruta al archivo ``.duckdb``.
        corpus_path: Ruta al archivo ``.parquet`` con el corpus curado.

    Returns:
        Dict con ``papers_loaded``, ``total_papers``, ``state``, ``round``.

    Raises:
        DataError: Si el parquet no existe o no tiene el schema canónico.
        StoreError: Si el store está bloqueado.
    """
    import pyarrow.parquet as pq

    from bib2graph.corpus import Corpus
    from bib2graph.cycle import CycleState, apply_transition
    from bib2graph.schemas import CORPUS_SCHEMA

    resolved = Path(corpus_path)
    if not resolved.exists():
        raise DataError(
            f"El parquet '{resolved}' no existe. Verificá la ruta al corpus curado."
        )

    try:
        table = pq.read_table(str(resolved), schema=CORPUS_SCHEMA)  # type: ignore[no-untyped-call]
    except Exception as exc:
        raise DataError(
            f"No se pudo leer el parquet '{resolved}': {exc}. "
            "Verificá que el archivo tenga el schema canónico de bib2graph."
        ) from exc

    try:
        incoming = Corpus.from_arrow(table)
    except Exception as exc:
        raise DataError(
            f"El parquet '{resolved}' no cumple el schema canónico: {exc}."
        ) from exc

    merged_backend_close = None
    store = open_store(store_path)
    try:
        existing = store.load()

        # Transición a FILTERED: el corpus restaurado ya pasó curación.
        # apply_transition es permisiva — acepta "filter" desde cualquier estado
        # actual del store (incluyendo None para un store vacío nuevo).
        current_state = store.backend.loop_state()
        # La ronda nunca debe ser < 1: loop_round() devuelve 0 para bases legacy
        # (round=NULL, pre-R3) y para stores vacíos. max(..., 1) la normaliza en
        # ambos branches para no persistir un estado con ronda 0 incoherente.
        current_round = max(store.backend.loop_round(), 1)
        # "filter" lleva a FILTERED; la ronda no cambia (no es reseed).
        # Para un store vacío (current_state=None), arrancamos desde SEEDED ficticio.
        if current_state is None:
            new_state, new_round = apply_transition(
                CycleState.SEEDED, "filter", current_round
            )
        else:
            new_state, new_round = apply_transition(
                current_state, "filter", current_round
            )

        # Merge primero, dedup después sobre el corpus COMPLETO (fix bug cross-biblioteca).
        # Orden: existing + incoming → merged completo → normalize_and_dedup → persist_replace.
        # El reloj se fija UNA vez por invocación (R2).
        ingest_at = datetime.now(UTC)
        merged = existing.merge(incoming)
        merged_deduped = normalize_and_dedup(merged, applied_at=ingest_at)
        papers_loaded = len(incoming)
        total_papers = len(merged_deduped)
        merged_backend_close = getattr(merged_deduped._backend, "close", None)
        store.persist_replace(merged_deduped)
        store.backend.set_loop_state(new_state, cycle_round=new_round)
    finally:
        # Ver run_seed_from_bib: cierra explícitamente las conexiones DuckDB
        # para evitar segfault en Linux ante llamadas consecutivas al mismo archivo.
        if merged_backend_close is not None:
            merged_backend_close()
        store.close()

    return {
        "papers_loaded": papers_loaded,
        "total_papers": total_papers,
        "state": str(new_state),
        "round": new_round,
    }


# ---------------------------------------------------------------------------
# Comando Click (no se testea directamente)
# ---------------------------------------------------------------------------


@click.command("restore")
@click.option(
    "--from-corpus",
    "corpus_path",
    required=True,
    type=click.Path(),
    help=(
        "Ruta al parquet con el corpus curado a importar sin red "
        "(producido por b2g snapshot)."
    ),
)
@json_option
@click.pass_context
@handle_errors("restore")
def restore_cmd(
    ctx: click.Context,
    corpus_path: str,
    json_output: bool,
) -> None:
    """Rehidrata el corpus desde un parquet curado sin tocar la red.

    \b
    Carga el parquet con el schema canónico de bib2graph, hace merge con
    el corpus existente y transiciona el lazo a FILTERED (el corpus ya
    fue curado; build y networks pueden correr a continuación).

    \b
    Preserva las columnas de curación del parquet (curation_status, is_seed).

    \b
    Ejemplos:
      b2g restore --from-corpus snapshots/corpus.parquet
      b2g restore --from-corpus corpus_curado.parquet --json
    """
    store_path = resolve_library_path(ctx.obj)
    data = run_restore(store_path, corpus_path)

    if json_mode(json_output):
        envelope = build_envelope(
            command="restore",
            ok=True,
            data=data,
            exit_code=0,
        )
        emit(envelope)
    else:
        emit_human(f"Corpus restaurado: {data['papers_loaded']} papers importados.")
        emit_human(f"Total en corpus: {data['total_papers']}")
        emit_human(f"Estado del lazo: {data['state']}")
