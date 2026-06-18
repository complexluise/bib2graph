"""cli.commands.snapshot — Subcomando ``b2g snapshot``.

Exporta una foto sellada del corpus actual (parquet + manifest.json).
NO transiciona el CycleState.

ADR 0029 — workspace:
  El directorio de salida es ``<workspace>/snapshots/`` por defecto.
  Si se pasa ``--out-dir`` explícito, se usa ese (override opcional).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from bib2graph.cli._envelope import build_envelope, emit, emit_human
from bib2graph.cli._errors import handle_errors
from bib2graph.cli._store import open_store, resolve_workspace

# ---------------------------------------------------------------------------
# Función núcleo (testeable, sin Click)
# ---------------------------------------------------------------------------


def run_snapshot(
    store_path: str | Path,
    *,
    out_dir: str | Path,
) -> dict[str, Any]:
    """Exporta una foto sellada del corpus actual.

    Carga el corpus del store y exporta un snapshot sellado (parquet +
    manifest.json) al directorio indicado. No transiciona el CycleState.

    Args:
        store_path: Ruta al archivo ``.duckdb``.
        out_dir: Directorio destino del snapshot.

    Returns:
        Dict con ``snapshot_dir``, ``corpus_hash``, ``total_papers``.

    Raises:
        StoreError: Si el store está bloqueado.
    """
    store = open_store(store_path)
    corpus = store.load()

    snap = corpus.snapshot(Path(out_dir))

    return {
        "snapshot_dir": str(snap.path),
        "corpus_hash": snap.manifest.corpus_hash,
        "total_papers": len(corpus),
        "schema_version": snap.manifest.schema_version,
    }


# ---------------------------------------------------------------------------
# Comando Click
# ---------------------------------------------------------------------------


@click.command("snapshot")
@click.option(
    "--out-dir",
    default=None,
    help=(
        "Directorio destino del snapshot "
        "(default: <workspace>/snapshots/ o <store_dir>/snapshots/)."
    ),
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    help="Salida JSON estructurada.",
)
@click.pass_context
@handle_errors("snapshot")
def snapshot_cmd(
    ctx: click.Context,
    out_dir: str | None,
    json_output: bool,
) -> None:
    """Exporta una foto sellada del corpus actual (parquet + manifest.json).

    No transiciona el CycleState.

    El directorio de salida por defecto es ``<workspace>/snapshots/``.
    Con ``--out-dir`` se puede especificar un directorio alternativo.
    """
    # ADR 0029: usar snapshots_dir del workspace si no se especifica --out-dir
    ws = resolve_workspace(ctx.obj)
    effective_out_dir: Path = Path(out_dir) if out_dir is not None else ws.snapshots_dir

    data = run_snapshot(ws.library_path, out_dir=effective_out_dir)

    if json_output:
        envelope = build_envelope(
            command="snapshot",
            ok=True,
            data=data,
            exit_code=0,
        )
        emit(envelope)
    else:
        emit_human(f"Snapshot exportado en: {data['snapshot_dir']}")
        emit_human(f"corpus_hash: {data['corpus_hash']}")
        emit_human(f"Total papers: {data['total_papers']}")
