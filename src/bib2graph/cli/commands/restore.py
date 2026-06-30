"""cli.commands.restore — Shim ``b2g restore`` (ADR 0038, #163, alias deprecado #165).

El subcomando ``restore`` suelto se mantiene intacto como shim para
compatibilidad con scripts y flujos existentes.  Su retiro está planificado
en el sub-issue #165.

DEPRECADO (ADR 0038, #165): usar ``b2g snapshot restore``.  Se retira en 0.11.0.

La lógica vive en ``service.snapshot.run_restore`` (fuente única).  Este
módulo es un adaptador delgado que:
  - Inyecta el reloj en la frontera CLI (``decided_at``, R2/ADR 0017).
  - Emite el envelope JSON con ``command="restore"`` (compatibilidad).
  - Re-exporta ``run_restore`` para tests que importan desde este módulo.

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

import click

from bib2graph.cli._deprecation import emit_deprecation
from bib2graph.cli._envelope import build_envelope, emit, emit_human
from bib2graph.cli._errors import handle_errors
from bib2graph.cli._options import json_mode, json_option
from bib2graph.cli._store import resolve_library_path

# Re-exportado para backward compat con tests que importan desde este módulo.
from bib2graph.service.snapshot import run_restore

__all__ = ["restore_cmd", "run_restore"]


@click.command("restore")
@click.option(
    "--from-corpus",
    "corpus_path",
    required=True,
    type=click.Path(),
    help=(
        "Ruta al parquet con el corpus curado a importar sin red "
        "(producido por b2g snapshot create)."
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

    \b
    Alternativa canónica (ADR 0038): b2g snapshot restore --from-corpus ...
    """
    dep_msg = emit_deprecation("b2g restore", "b2g snapshot restore")
    store_path = resolve_library_path(ctx.obj)
    # R2/ADR 0017: el reloj se inyecta en la frontera CLI.
    decided_at = datetime.now(UTC)
    data = run_restore(store_path, corpus_path, decided_at=decided_at)

    if json_mode(json_output):
        envelope = build_envelope(
            command="restore",
            ok=True,
            data=data,
            exit_code=0,
            warnings=[dep_msg],
        )
        emit(envelope)
    else:
        emit_human(f"Corpus restaurado: {data['papers_loaded']} papers importados.")
        emit_human(f"Total en corpus: {data['total_papers']}")
        emit_human(f"Estado del lazo: {data['state']}")
