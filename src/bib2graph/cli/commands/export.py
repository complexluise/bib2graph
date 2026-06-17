"""cli.commands.export — Subcomando ``b2g export``.

Serializa los artefactos de build al formato pedido.
NO transiciona el CycleState.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import click

from bib2graph.cli._envelope import build_envelope, emit, emit_human
from bib2graph.cli._errors import DataError, handle_errors
from bib2graph.cli._store import resolve_library_path

# ---------------------------------------------------------------------------
# Función núcleo (testeable, sin Click)
# ---------------------------------------------------------------------------


def run_export(
    store_path: str | Path,
    *,
    format: Literal["graphml", "csv"] = "graphml",
    out_dir: str | Path,
    networks_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Relee artefactos de build y los serializa al formato pedido.

    Lee los GraphML de ``<store_dir>/networks/<kind>/network.graphml``
    (o el directorio dado) y exporta al formato pedido.

    Args:
        store_path: Ruta al archivo ``.duckdb``.
        format: Formato de salida (``graphml`` o ``csv``).
        out_dir: Directorio de salida para los archivos exportados.
        networks_dir: Directorio base de artefactos de build (default:
            ``<store_dir>/networks/``).

    Returns:
        Dict con ``format``, ``files_written`` y lista de archivos.

    Raises:
        DataError: Si no hay artefactos de build disponibles.
        StoreError: Si el store está bloqueado.
    """
    import networkx as nx

    from bib2graph.exporters.csv import CsvExporter
    from bib2graph.exporters.graphml import GraphMLExporter

    store_path_obj = Path(store_path)
    if networks_dir is None:
        nets_dir = store_path_obj.parent / "networks"
    else:
        nets_dir = Path(networks_dir)

    if not nets_dir.exists():
        raise DataError(
            f"No hay artefactos de build en '{nets_dir}'. "
            "Ejecutá primero ``b2g build``."
        )

    # Buscar subdirectorios de redes
    kind_dirs = [d for d in nets_dir.iterdir() if d.is_dir()]
    if not kind_dirs:
        raise DataError(
            f"No se encontraron redes en '{nets_dir}'. Ejecutá primero ``b2g build``."
        )

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    files_written = []

    if format == "graphml":
        exporter_gml = GraphMLExporter()
        for kind_dir in sorted(kind_dirs, key=lambda d: d.name):
            graphml_src = kind_dir / "network.graphml"
            if not graphml_src.exists():
                continue
            g = nx.read_graphml(str(graphml_src))
            metrics_path = kind_dir / "metrics.json"
            metrics = {}
            if metrics_path.exists():
                metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            kind_out = out_path / kind_dir.name
            exporter_gml.export(g, metrics, kind_out)
            files_written.append(str(kind_out / "network.graphml"))

    elif format == "csv":
        exporter_csv = CsvExporter()
        for kind_dir in sorted(kind_dirs, key=lambda d: d.name):
            graphml_src = kind_dir / "network.graphml"
            if not graphml_src.exists():
                continue
            g = nx.read_graphml(str(graphml_src))
            metrics_path = kind_dir / "metrics.json"
            metrics = {}
            if metrics_path.exists():
                metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            kind_out = out_path / kind_dir.name
            exporter_csv.export(g, metrics, kind_out)
            files_written.append(str(kind_out / "nodos.csv"))
            files_written.append(str(kind_out / "aristas.csv"))
    else:
        raise DataError(f"Formato '{format}' no reconocido. Usá 'graphml' o 'csv'.")

    return {
        "format": format,
        "out_dir": str(out_path),
        "files_written": files_written,
        "networks_exported": len(kind_dirs),
    }


# ---------------------------------------------------------------------------
# Comando Click
# ---------------------------------------------------------------------------


@click.command("export")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["graphml", "csv"]),
    default="graphml",
    show_default=True,
    help="Formato de salida.",
)
@click.option(
    "--out-dir",
    required=True,
    help="Directorio de salida para los archivos exportados.",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    help="Salida JSON estructurada.",
)
@click.pass_context
@handle_errors("export")
def export_cmd(
    ctx: click.Context,
    fmt: str,
    out_dir: str,
    json_output: bool,
) -> None:
    """Serializa artefactos de build al formato pedido (GraphML o CSV).

    No transiciona el CycleState.
    """
    store_path = resolve_library_path(ctx.obj)
    data = run_export(
        store_path,
        format=fmt,  # type: ignore[arg-type]
        out_dir=out_dir,
    )

    if json_output:
        envelope = build_envelope(
            command="export",
            ok=True,
            data=data,
            exit_code=0,
        )
        emit(envelope)
    else:
        emit_human(f"Exportados {data['networks_exported']} redes en formato {fmt}")
        emit_human(f"Directorio: {data['out_dir']}")
        for f in data["files_written"]:
            emit_human(f"  {f}")
