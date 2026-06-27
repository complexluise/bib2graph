"""cli.commands.networks — Subcomando ``b2g networks``.

Carga una especificación declarativa de redes desde un archivo YAML y
construye cada red, escribiendo artefactos a disco.

A diferencia de ``b2g build`` (que usa ``Networks.quick`` y transiciona el
``CycleState`` del lazo bibliométrico), este subcomando es **ad-hoc**:
  - Acepta cualquier combinación de redes definidas en el YAML.
  - NO transiciona el ``CycleState`` ni sella ``.corpus_hash``
    (ejecución declarativa transversal al lazo — mismo criterio que
    ``b2g enrich`` y ``b2g curate``).

Los artefactos se escriben en ``<out_dir>/<kind>/``:
  - ``network.graphml``: el grafo en formato GraphML.
  - ``metrics.json``: métricas de red calculadas.
  - ``clusters.csv``: tabla de resumen de comunidades (solo redes de paper
    con comunidades detectadas, issue #31).

Envelope ``--json`` (schema="1"): lista de redes en el mismo formato que
``b2g build``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from bib2graph.cli._envelope import build_envelope, emit, emit_human
from bib2graph.cli._errors import DataError, DependencyError, handle_errors
from bib2graph.cli._options import json_mode, json_option
from bib2graph.cli._store import open_store, resolve_workspace
from bib2graph.cli.commands.build import _write_artifacts

# ---------------------------------------------------------------------------
# Función núcleo (testeable, sin Click)
# ---------------------------------------------------------------------------


def run_networks(
    store_path: str | Path,
    spec_path: str | Path,
    *,
    out_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Construye redes bibliométricas desde una especificación YAML.

    Carga ``spec_path`` con ``load_specs``, construye cada red con
    ``Networks.build`` y escribe artefactos con el helper ``_write_artifacts``
    (compartido con ``run_build``).

    NO transiciona el ``CycleState`` ni sella ``.corpus_hash``:
    esta operación es transversal al lazo bibliométrico (igual que ``enrich``
    y ``curate``).

    Args:
        store_path: Ruta al archivo ``.duckdb``.
        spec_path: Ruta al archivo YAML con la definición de redes.
        out_dir: Directorio base de salida. Default: ``<store_dir>/networks/``.

    Returns:
        Dict con ``networks_built``, ``artifacts_dir`` y lista de redes
        (mismo esquema que ``run_build``).

    Raises:
        DataError: Si el YAML está malformado o alguna spec es inválida.
        DependencyError: Si falta ``python-louvain``.
        StoreError: Si el store está bloqueado.
    """
    from bib2graph.networks.facade import Networks
    from bib2graph.networks.spec import load_specs

    store = open_store(store_path)
    corpus = store.load()

    store_path_obj = Path(store_path)
    if out_dir is None:
        artifacts_dir = store_path_obj.parent / "networks"
    else:
        artifacts_dir = Path(out_dir)

    try:
        specs = load_specs(spec_path)
    except (ValueError, FileNotFoundError) as exc:
        raise DataError(str(exc)) from exc

    try:
        artifacts = [Networks.build(corpus, spec) for spec in specs]
    except ImportError as exc:
        raise DependencyError(
            f"Dependencia faltante para detectar comunidades: {exc}. "
            "Instalá python-louvain: uv add python-louvain."
        ) from exc

    networks_info = _write_artifacts(artifacts, corpus, artifacts_dir)

    return {
        "networks_built": len(artifacts),
        "artifacts_dir": str(artifacts_dir),
        "networks": networks_info,
    }


# ---------------------------------------------------------------------------
# Comando Click
# ---------------------------------------------------------------------------


@click.command("networks")
@click.option(
    "--spec",
    "spec_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Ruta al archivo YAML con la especificación de redes.",
)
@click.option(
    "--out-dir",
    default=None,
    help=(
        "Directorio base de artefactos "
        "(default: <workspace>/networks/ o <store_dir>/networks/)."
    ),
)
@json_option
@click.pass_context
@handle_errors("networks")
def networks_cmd(
    ctx: click.Context,
    spec_path: str,
    out_dir: str | None,
    json_output: bool,
) -> None:
    """Construye redes bibliométricas desde una especificación YAML.

    Carga el YAML indicado con --spec, valida cada red contra NetworkSpec y
    escribe artefactos (GraphML + metrics.json + clusters.csv cuando aplica).

    No transiciona el estado del lazo bibliométrico.
    """
    ws = resolve_workspace(ctx.obj)
    effective_out_dir: str | Path | None = out_dir
    if effective_out_dir is None:
        effective_out_dir = ws.networks_dir

    data = run_networks(ws.library_path, spec_path, out_dir=effective_out_dir)

    if json_mode(json_output):
        envelope = build_envelope(
            command="networks",
            ok=True,
            data=data,
            exit_code=0,
        )
        emit(envelope)
    else:
        emit_human(f"Redes construidas: {data['networks_built']}")
        emit_human(f"Artefactos en: {data['artifacts_dir']}")
        for net in data["networks"]:
            emit_human(f"  {net['kind']}: {net['nodes']} nodos, {net['edges']} aristas")
