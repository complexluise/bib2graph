"""cli.commands.build — Subcomando ``b2g build``.

Computa las redes bibliométricas con Networks.quick y escribe artefactos
a disco. Transiciona el CycleState a BUILT tras persistir con éxito.

ADR 0029 — workspace:
  El directorio de artefactos es ``<workspace>/networks/`` por defecto.
  Si se pasa ``--out-dir`` explícito, se usa ese.

ADR 0029 — sellado por corpus_hash:
  Escribe ``networks/.corpus_hash`` con el hash del corpus que produjo
  las redes. Permite detectar staleness sin un build system completo.

Los artefactos se escriben en ``<networks_dir>/<kind>/``:
  - ``network.graphml``: el grafo en formato GraphML.
  - ``metrics.json``: métricas de red calculadas.
  - ``clusters.csv``: tabla de resumen de comunidades (solo redes de paper
    con comunidades detectadas, issue #31).
"""

from __future__ import annotations

import csv as _csv
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click

from bib2graph.cli._envelope import build_envelope, emit, emit_human
from bib2graph.cli._errors import DependencyError, handle_errors
from bib2graph.cli._store import open_store, resolve_workspace

if TYPE_CHECKING:
    from bib2graph.corpus import Corpus
    from bib2graph.networks.spec import NetworkArtifact


# ---------------------------------------------------------------------------
# Helper compartido: escritura de artefactos por red
# ---------------------------------------------------------------------------


def _write_artifacts(
    artifacts: list[NetworkArtifact],
    corpus: Corpus,
    artifacts_dir: Path,
) -> list[dict[str, Any]]:
    """Escribe GraphML + metrics.json + clusters.csv por cada ``NetworkArtifact``.

    Helper reutilizable por ``run_build`` y ``run_networks``.  Contiene SOLO la
    lógica de export de artefactos: NO transiciona ``CycleState`` ni sella
    ``.corpus_hash`` (esas responsabilidades quedan en quien llame a esta función).

    Args:
        artifacts: Lista de artefactos a exportar.
        corpus: Corpus origen (se necesita para ``cluster_table``).
        artifacts_dir: Directorio base donde se crean las subcarpetas ``<kind>/``.

    Returns:
        Lista de dicts con ``kind``, ``nodes``, ``edges``, ``graphml``,
        ``metrics_json`` y (si aplica) ``clusters_csv``.
    """
    from bib2graph.exporters.graphml import GraphMLExporter
    from bib2graph.networks.clusters import cluster_table

    exporter = GraphMLExporter()
    networks_info: list[dict[str, Any]] = []

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

        # Escribir clusters.csv para redes de paper con comunidades (issue #31).
        # cluster_table devuelve [] si el kind no es de paper o no hay comunidades.
        clusters_path: str | None = None
        clusters = cluster_table(corpus.to_arrow(), art)
        if clusters:
            clusters_path = str(kind_dir / "clusters.csv")
            with open(clusters_path, "w", newline="", encoding="utf-8") as _f:
                _writer = _csv.DictWriter(
                    _f,
                    fieldnames=[
                        "cluster",
                        "size",
                        "seed_count",
                        "candidate_count",
                        "accepted_count",
                        "year_min",
                        "year_max",
                        "year_mean",
                        "top_authors",
                        "top_keywords",
                    ],
                )
                _writer.writeheader()
                for _row in clusters:
                    # Serializar listas como cadena separada por "|"
                    _writer.writerow(
                        {
                            **_row,
                            "top_authors": "|".join(_row["top_authors"]),
                            "top_keywords": "|".join(_row["top_keywords"]),
                        }
                    )

        net_entry: dict[str, Any] = {
            "kind": kind,
            "nodes": art.graph.number_of_nodes(),
            "edges": art.graph.number_of_edges(),
            "graphml": str(kind_dir / "network.graphml"),
            "metrics_json": str(metrics_path),
        }
        if clusters_path is not None:
            net_entry["clusters_csv"] = clusters_path
        networks_info.append(net_entry)

    return networks_info


# ---------------------------------------------------------------------------
# Función núcleo (testeable, sin Click)
# ---------------------------------------------------------------------------


def run_build(
    store_path: str | Path,
    *,
    out_dir: str | Path | None = None,
    corpus_scope: str = "all",
) -> dict[str, Any]:
    """Computa redes bibliométricas y escribe artefactos a disco.

    Usa ``Networks.quick`` para las 4 redes principales (coupling, co-autoría,
    institución, co-word). Escribe GraphML + metrics.json por red.
    Para redes de paper con comunidades detectadas escribe también clusters.csv
    (tabla de resumen de comunidades, issue #31).
    Sella ``networks/.corpus_hash`` con el hash del corpus **filtrado** que las
    produjo (no del corpus vivo completo).
    Transiciona a BUILT tras escribir con éxito.

    Args:
        store_path: Ruta al archivo ``.duckdb``.
        out_dir: Directorio base de salida. Default: ``<store_dir>/networks/``.
        corpus_scope: Filtro de curación aplicado antes de construir las redes.
            ``'all'`` (default) = corpus completo; ``'accepted'`` = semillas +
            aceptados; ``'seeds_only'`` = solo semillas.

    Returns:
        Dict con ``networks_built``, ``artifacts_dir``, ``corpus_hash``,
        ``corpus_scope`` y lista de redes.

    Raises:
        DependencyError: Si falta ``python-louvain``.
        StoreError: Si el store está bloqueado.
    """
    import warnings as _warnings

    from bib2graph.cycle import apply_transition
    from bib2graph.networks.facade import Networks

    store = open_store(store_path)
    try:
        corpus_full = store.load()

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

        # Filtrar el corpus según el scope ANTES de construir redes (#56).
        # El corpus filtrado también es el que se pasa a _write_artifacts para que
        # clusters.csv cuadre con los nodos del grafo (sin drift).
        corpus = corpus_full.scoped(corpus_scope)

        # Caso de 0 nodos: no es error, pero sí merece un warning accionable.
        build_warnings: list[str] = []
        if len(corpus) == 0:
            msg = (
                f"scope='{corpus_scope}' dejó 0 papers; "
                "corré `b2g curate` para aceptar papers o usá `--corpus-scope=all`."
            )
            _warnings.warn(msg, stacklevel=2)
            build_warnings.append(msg)
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            (artifacts_dir / ".corpus_hash").write_text("", encoding="utf-8")
            store.backend.set_loop_state(new_state, cycle_round=new_round)
            return {
                "networks_built": 0,
                "artifacts_dir": str(artifacts_dir),
                "corpus_hash": "",
                "corpus_scope": corpus_scope,
                "networks": [],
                "warnings": build_warnings,
            }

        try:
            artifacts = Networks.quick(corpus)
        except ImportError as exc:
            raise DependencyError(
                f"Dependencia faltante para detectar comunidades: {exc}. "
                "Instalá python-louvain: uv add python-louvain."
            ) from exc

        networks_info = _write_artifacts(artifacts, corpus, artifacts_dir)

        # ADR 0029 — sellar con corpus_hash del corpus FILTRADO (no del vivo completo).
        # Esto garantiza que el hash refleja exactamente lo que produjo las redes.
        from bib2graph.backends.memory import compute_corpus_hash

        corpus_hash = compute_corpus_hash(corpus.to_arrow())
        hash_file = artifacts_dir / ".corpus_hash"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        hash_file.write_text(corpus_hash, encoding="utf-8")

        store.backend.set_loop_state(new_state, cycle_round=new_round)
    finally:
        store.close()

    return {
        "networks_built": len(artifacts),
        "artifacts_dir": str(artifacts_dir),
        "corpus_hash": corpus_hash,
        "corpus_scope": corpus_scope,
        "networks": networks_info,
        "warnings": build_warnings,
    }


# ---------------------------------------------------------------------------
# Comando Click
# ---------------------------------------------------------------------------


@click.command("build")
@click.option(
    "--out-dir",
    default=None,
    help=(
        "Directorio base de artefactos "
        "(default: <workspace>/networks/ o <store_dir>/networks/)."
    ),
)
@click.option(
    "--corpus-scope",
    "corpus_scope",
    type=click.Choice(["all", "accepted", "seeds_only"]),
    default="all",
    show_default=True,
    help=(
        "Filtra el corpus antes de construir las redes. "
        "'all' = corpus completo (default, sin cambio de comportamiento); "
        "'accepted' = semillas (is_seed=True) + papers aceptados por curación; "
        "'seeds_only' = solo semillas (is_seed=True). "
        "Si el scope deja 0 papers, termina con exit 0 y un warning accionable."
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
@handle_errors("build")
def build_cmd(
    ctx: click.Context,
    out_dir: str | None,
    corpus_scope: str,
    json_output: bool,
) -> None:
    """Computa las 4 redes con Networks.quick y escribe artefactos.

    Tras el build, el estado del lazo transiciona a BUILT.
    El directorio networks/ queda sellado con .corpus_hash del corpus filtrado.
    """
    # ADR 0029: usar networks_dir del workspace si no se especifica --out-dir
    ws = resolve_workspace(ctx.obj)
    effective_out_dir: str | Path | None = out_dir
    if effective_out_dir is None:
        effective_out_dir = ws.networks_dir

    data = run_build(
        ws.library_path, out_dir=effective_out_dir, corpus_scope=corpus_scope
    )

    if json_output:
        envelope = build_envelope(
            command="build",
            ok=True,
            data=data,
            exit_code=0,
            warnings=data.get("warnings"),
        )
        emit(envelope)
    else:
        for w in data.get("warnings", []):
            emit_human(f"ADVERTENCIA: {w}")
        emit_human(f"Redes construidas: {data['networks_built']}")
        emit_human(f"Artefactos en: {data['artifacts_dir']}")
        emit_human(f"corpus_hash: {data['corpus_hash']}")
        for net in data["networks"]:
            emit_human(f"  {net['kind']}: {net['nodes']} nodos, {net['edges']} aristas")
