"""cli.commands.build — Subcomando ``b2g build``.

Computa las redes bibliométricas con Networks.quick y escribe artefactos
a disco. Transiciona el LoopState a BUILT tras persistir con éxito.

Los artefactos se escriben en ``<store_dir>/networks/<kind>/``:
  - ``network.graphml``: el grafo en formato GraphML.
  - ``metrics.json``: métricas de red calculadas.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click

from bib2graph.cli._envelope import build_envelope, emit, emit_human
from bib2graph.cli._errors import DependencyError, handle_errors
from bib2graph.cli._store import open_store

# ---------------------------------------------------------------------------
# Función núcleo (testeable, sin Click)
# ---------------------------------------------------------------------------


def run_build(
    store_path: str | Path,
    *,
    out_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Computa redes bibliométricas y escribe artefactos a disco.

    Usa ``Networks.quick`` para las 4 redes principales (coupling, co-autoría,
    institución, co-word). Escribe GraphML + metrics.json por red.
    Transiciona a BUILT tras escribir con éxito.

    Args:
        store_path: Ruta al archivo ``.duckdb``.
        out_dir: Directorio base de salida. Default: ``<store_dir>/networks/``.

    Returns:
        Dict con ``networks_built``, ``artifacts_dir`` y lista de redes.

    Raises:
        DependencyError: Si falta ``python-louvain``.
        StoreError: Si el store está bloqueado.
    """
    from bib2graph.cycle import apply_transition
    from bib2graph.exporters.graphml import GraphMLExporter
    from bib2graph.networks.facade import Networks

    store = open_store(store_path)
    corpus = store.load()

    # R3 — fuente única de verdad: el destino de la transición lo dicta cycle.py,
    # no un literal en el comando (ADR 0016 enmendado §1).
    current_state = store.backend.loop_state()
    current_round = store.backend.loop_round()
    new_state, new_round = apply_transition(current_state, "build", current_round)

    store_path_obj = Path(store_path)
    if out_dir is None:
        artifacts_dir = store_path_obj.parent / "networks"
    else:
        artifacts_dir = Path(out_dir)

    try:
        artifacts = Networks.quick(corpus)
    except ImportError as exc:
        raise DependencyError(
            f"Dependencia faltante para detectar comunidades: {exc}. "
            "Instalá python-louvain: uv add python-louvain."
        ) from exc

    exporter = GraphMLExporter()
    networks_info = []

    for art in artifacts:
        kind = art.spec.kind
        kind_dir = artifacts_dir / kind
        kind_dir.mkdir(parents=True, exist_ok=True)

        # Exportar GraphML: fusionar métricas + comunidades como atributo de nodo.
        # art.communities es un dict {nodo: int} o None si no se calcularon.
        node_attrs: dict[str, object] = {**art.metrics}
        if art.communities:
            node_attrs["community"] = art.communities
        exporter.export(art.graph, node_attrs, kind_dir)

        # Escribir metrics.json
        metrics_path = kind_dir / "metrics.json"
        # Serializar métricas (pueden tener tipos no-JSON como nx.Graph)
        safe_metrics = {
            k: v
            for k, v in art.metrics.items()
            if isinstance(v, (int, float, str, bool, type(None)))
        }
        metrics_path.write_text(
            json.dumps(
                {
                    "kind": kind,
                    "nodes": art.graph.number_of_nodes(),
                    "edges": art.graph.number_of_edges(),
                    **safe_metrics,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        networks_info.append(
            {
                "kind": kind,
                "nodes": art.graph.number_of_nodes(),
                "edges": art.graph.number_of_edges(),
                "graphml": str(kind_dir / "network.graphml"),
                "metrics_json": str(metrics_path),
            }
        )

    store.backend.set_loop_state(new_state, cycle_round=new_round)

    return {
        "networks_built": len(artifacts),
        "artifacts_dir": str(artifacts_dir),
        "networks": networks_info,
    }


# ---------------------------------------------------------------------------
# Comando Click
# ---------------------------------------------------------------------------


@click.command("build")
@click.option(
    "--out-dir",
    default=None,
    help="Directorio base de artefactos (default: <store_dir>/networks/).",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    help="Salida JSON estructurada.",
)
@click.pass_context
@handle_errors("build")
def build_cmd(
    ctx: click.Context,
    out_dir: str | None,
    json_output: bool,
) -> None:
    """Computa las 4 redes con Networks.quick y escribe artefactos.

    Tras el build, el estado del lazo transiciona a BUILT.
    """
    store_path = ctx.obj["store"]
    data = run_build(store_path, out_dir=out_dir)

    if json_output:
        envelope = build_envelope(
            command="build",
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
