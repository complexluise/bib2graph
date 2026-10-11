"""cli.commands.export — Subcomando ``b2g export``.

Serializa artefactos al formato pedido. NO transiciona el CycleState.

Dos familias de formato (ADR 0050 D4, issue #293):
  - **Redes de build** (``graphml``/``csv``, ya existentes): releen
    ``<workspace>/networks/<kind>/network.graphml`` — ya vienen scopeados
    de ``b2g build --scope``; ``--scope`` de este comando se **ignora** para
    estos formatos (con un warning si se pasa explícito).
  - **Corpus** (``arrow``/``bibtex``, nuevos): serializan
    ``corpus.scoped(scope).to_arrow()`` — ``--scope`` de este comando SÍ
    aplica (vocab CLI ``seeds`` → ``seeds_only``, igual que ``build``).

ADR 0052 (#321) — red tipada en el Arrow:
  ``--network-type <kind>`` (default ``bibliographic_coupling``) controla qué
  red del ``b2g build`` se embebe como columnas struct anidadas en la tabla
  ``papers`` del ``.arrow`` (``community_id``, ``degree_weighted``,
  ``intra_community_pagerank``, ``network_edges``, ``network_communities``)
  + 4 claves de metadata del schema (network_type, network_type_algo,
  network_resolution, network_scope). Solo aplica a ``--format arrow``.

  Modo degradado (ADR 0052 D4): si no hay artefacto de build para el kind
  pedido, el export sale igual, las columnas de red están AUSENTES,
  ``network_type`` ausente en metadata, y se emite un warning en el envelope
  ``--json`` (``data.warnings`` → top-level ``warnings``).

  Kinds no-paper (author_collab / institution_collab / keyword_cooccurrence):
  warning en envelope + sin columnas de red (los nodos de esas redes no son
  papers; no se pueden anclar por paper en el Arrow).

  ``cocitation`` sin ``cited_by_id`` poblado en el corpus: error accionable
  (DataError, exit 2 — la red de co-citación no es construible sin
  citantes).

ADR 0029 — workspace:
  El directorio de salida es ``<workspace>/exports/`` por defecto.
  Si se pasa ``--out-dir`` explícito, se usa ese (override opcional).
  La fuente de artefactos de build es ``<workspace>/networks/`` por defecto.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Literal

import click

from bib2graph.cli._envelope import build_envelope, emit, emit_human
from bib2graph.cli._errors import DataError, handle_errors
from bib2graph.cli._options import json_mode, json_option
from bib2graph.cli._scope import map_scope as _map_scope
from bib2graph.cli._store import (
    open_store_readonly,
    resolve_workspace,
    workspace_echo,
    workspace_walkup_warning,
)
from bib2graph.constants import NetworkKind

#: Formatos que serializan artefactos de build (redes); ignoran ``--scope``.
_NETWORK_FORMATS = frozenset({"graphml", "csv"})
#: Formatos que serializan el corpus; respetan ``--scope`` (ADR 0050 D4).
_CORPUS_FORMATS = frozenset({"arrow", "bibtex"})

#: Kinds de NetworkKind no-papers: warning en envelope + sin columnas de red.
_NON_PAPER_KINDS: frozenset[str] = frozenset(
    {
        NetworkKind.AUTHOR_COLLAB,
        NetworkKind.INSTITUTION_COLLAB,
        NetworkKind.KEYWORD_COOCCURRENCE,
    }
)


def _export_networks(
    format: str,
    *,
    out_dir: str | Path,
    networks_dir: str | Path | None,
    store_path: str | Path,
) -> dict[str, Any]:
    """Relee artefactos de build (redes) y los serializa a GraphML o CSV.

    Args:
        format: ``"graphml"`` o ``"csv"``.
        out_dir: Directorio de salida para los archivos exportados.
        networks_dir: Directorio base de artefactos de build (default:
            ``<store_dir>/networks/``).
        store_path: Ruta al archivo ``.duckdb`` (para derivar el default de
            ``networks_dir`` si no se pasa explícito).

    Returns:
        Dict con ``format``, ``out_dir``, ``files_written`` y
        ``networks_exported``.

    Raises:
        DataError: Si no hay artefactos de build disponibles.
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


def _export_corpus(
    format: str,
    *,
    out_dir: str | Path,
    store_path: str | Path,
    scope: str,
    networks_dir: str | Path,
    network_type: str,
) -> dict[str, Any]:
    """Serializa el corpus (scopeado) a Arrow (Feather) o BibTeX.

    Para ``format == "arrow"`` y ``network_type`` no vacío, intenta embeber
    la red tipada del ``b2g build`` en la tabla ``papers`` (ADR 0052 D1):

      - ``network_type`` en kinds no-paper (author_collab, etc.) → warning
        en ``corpus_warnings``, NO se embebe red.
      - ``network_type == "cocitation"`` con corpus sin ``cited_by_id``
        poblado → ``DataError`` accionable (la red no se puede construir).
      - Si existe ``<networks_dir>/<network_type>/network.graphml`` → se
        reconstruye el ``NetworkArtifact`` desde disco y se embebe vía
        ``arrow_with_network``. Si no existe → modo degradado (ADR 0052 D4)
        con warning.

    Args:
        format: ``"arrow"`` o ``"bibtex"``.
        out_dir: Directorio de salida para el archivo exportado.
        store_path: Ruta al archivo ``.duckdb``.
        scope: Vocab interno de scope (``all``/``accepted``/``seeds_only``).
        networks_dir: Directorio base de artefactos de build
            (``<workspace>/networks/``).
        network_type: ``NetworkKind`` a embeber (``"bibliographic_coupling"``
            por default; vacío = sin red).

    Returns:
        Dict con ``format``, ``out_dir``, ``files_written``, ``rows_exported``
        y ``warnings`` (lista, puede ser vacía). Para ``format == "arrow"``
        incluye el warning accionable de ``build_equation_metadata`` cuando el
        corpus tiene 0 o >1 ecuaciones registradas (ADR 0050 D3), y los
        warnings de red del ADR 0052 (modo degradado, kind no-paper, etc.).

    Raises:
        DataError: Si ``format`` no se reconoce o si ``network_type`` no
            aplica al corpus (``cocitation`` sin ``cited_by_id``).
        ImportError: Si falta ``bibtexparser`` (formato ``bibtex``, extra
            ``[bibtex]``).
    """
    from bib2graph.backends.memory import build_equation_metadata
    from bib2graph.exporters.arrow import ArrowExporter, arrow_with_network
    from bib2graph.exporters.bibtex import BibtexExporter
    from bib2graph.service.export_network import (
        is_paper_kind,
        load_artifact_from_disk,
    )
    from bib2graph.workspace import Workspace

    corpus_warnings: list[str] = []
    network_meta: dict[str, Any] = {
        "network_type": None,
        "network_nodes": 0,
        "network_edges": 0,
        "network_communities": 0,
        "network_modularity": None,
        "network_type_algo": None,
        "network_resolution": None,
    }

    store = open_store_readonly(store_path)
    try:
        corpus = store.load().scoped(scope)
        # Materializar la tabla ANTES de cerrar el store: para scope='all',
        # corpus.scoped() devuelve el mismo Corpus respaldado por el
        # DuckDBBackend vivo (lazy); to_arrow() debe correr con la conexión
        # todavía abierta.
        table = corpus.to_arrow()
        if format == "arrow":
            # to_arrow() ya puebla equation_hash en la metadata cuando aplica
            # (ADR 0050 D3), pero descarta el warning ahí a propósito (no es
            # ruidoso para llamadas internas). Este es el punto de consumo
            # real visible al usuario: propagamos el warning si corresponde.
            _metadata, warning = build_equation_metadata(store.backend.load_equations())
            if warning is not None:
                corpus_warnings.append(warning)

            # ADR 0052 — embeber la red tipada si network_type está presente.
            if network_type:
                if not is_paper_kind(network_type):
                    corpus_warnings.append(
                        f"network_type={network_type} not supported in Arrow "
                        "export; use --format graphml for this kind"
                    )
                elif network_type == NetworkKind.COCITATION and not _any_cited_by(
                    table
                ):
                    raise DataError(
                        "--network-type cocitation requires cited_by_id to be "
                        "populated in the corpus (run 'b2g enrich' to populate "
                        "it from the accepted seeds)."
                    )
                else:
                    # Necesitamos el Workspace para resolver el directorio de
                    # artefactos de build. ``networks_dir`` puede venir como
                    # Path absoluto o relativo; si no contiene un workspace.json
                    # en su raíz, ``Workspace.open`` va a fallar — el caller
                    # garantiza que ``networks_dir`` es ``<workspace>/networks``.
                    ws_root = Path(networks_dir).parent
                    try:
                        ws = Workspace.open(ws_root, source="flag")
                    except Exception:
                        ws = None

                    artifact = None
                    if ws is not None:
                        artifact = load_artifact_from_disk(ws, network_type)

                    if artifact is None:
                        # Modo degradado (ADR 0052 D4): sin b2b build para
                        # este kind. No es un error: el corpus se exporta,
                        # las columnas de red están AUSENTES, warning al
                        # usuario.
                        corpus_warnings.append(
                            "no network computed; run 'b2g build' first to "
                            "attach a typed network to the export"
                        )
                    else:
                        table = arrow_with_network(table, artifact)
                        # Poblar el bloque aditivo del envelope (ADR 0052 D5).
                        spec = artifact.spec
                        network_meta["network_type"] = str(spec.kind)
                        network_meta["network_nodes"] = artifact.graph.number_of_nodes()
                        network_meta["network_edges"] = artifact.graph.number_of_edges()
                        if artifact.communities is not None:
                            network_meta["network_communities"] = len(
                                {int(c) for c in artifact.communities.values()}
                            )
                        if spec.clustering is not None:
                            network_meta["network_type_algo"] = str(spec.clustering)
                        network_meta["network_resolution"] = float(spec.resolution)

                        # Modularidad global (nx.community.modularity sobre la
                        # partición del artifact si tiene comunidades).
                        if artifact.communities:
                            try:
                                import networkx as nx

                                comm_ids = sorted(
                                    {int(c) for c in artifact.communities.values()}
                                )
                                by_comm: dict[int, set[Any]] = {
                                    cid: set() for cid in comm_ids
                                }
                                for node, cid in artifact.communities.items():
                                    if artifact.graph.has_node(node):
                                        by_comm[int(cid)].add(node)
                                mod = nx.community.modularity(
                                    artifact.graph,
                                    [by_comm[cid] for cid in comm_ids],
                                )
                                network_meta["network_modularity"] = float(mod)
                            except Exception:
                                network_meta["network_modularity"] = None
    finally:
        store.close()

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    if format == "arrow":
        dest = out_path / "corpus.arrow"
        ArrowExporter().export(table, dest)
    elif format == "bibtex":
        dest = out_path / "corpus.bib"
        BibtexExporter().export(table, dest)
    else:
        raise DataError(f"Formato '{format}' no reconocido. Usá 'arrow' o 'bibtex'.")

    data: dict[str, Any] = {
        "format": format,
        "out_dir": str(out_path),
        "files_written": [str(dest)],
        "rows_exported": table.num_rows,
        "warnings": corpus_warnings,
    }
    # ADR 0052 D5: campos aditivos del envelope ``--json`` para ``--format
    # arrow``. ``network_type=None`` y los counts en 0 cuando el kind no se
    # embebe (modo degradado / kind no-paper / bibtex).
    if format == "arrow":
        data.update(network_meta)
    return data


def _any_cited_by(table: Any) -> bool:
    """True sii al menos un paper del corpus tiene ``cited_by_id`` no vacío.

    Helper para validar ``network_type=cocitation`` (ADR 0052 D2): la red
    de co-citación requiere que el corpus tenga citantes poblados. Sin
    esto, la red saldría con 0 aristas y el usuario debe saberlo.

    Args:
        table: Tabla Arrow del Corpus.

    Returns:
        ``True`` si al menos un row tiene ``cited_by_id`` con ≥1 elemento.
    """
    from bib2graph.constants import Col

    if Col.CITED_BY_ID not in table.schema.names:
        return False
    for val in table.column(Col.CITED_BY_ID).to_pylist():
        if isinstance(val, list) and any(e is not None for e in val):
            return True
    return False


def run_export(
    store_path: str | Path,
    *,
    format: Literal["graphml", "csv", "arrow", "bibtex"] = "graphml",
    out_dir: str | Path,
    networks_dir: str | Path | None = None,
    scope: str = "all",
    scope_explicit: bool = False,
    network_type: str = "bibliographic_coupling",
) -> dict[str, Any]:
    """Serializa artefactos al formato pedido.

    Para ``graphml``/``csv`` relee los artefactos de build de
    ``<store_dir>/networks/<kind>/network.graphml`` (``scope`` se ignora:
    esos artefactos ya vienen scopeados de ``b2g build --scope``).

    Para ``arrow``/``bibtex`` (ADR 0050 D4) serializa
    ``corpus.scoped(scope).to_arrow()`` del store vivo — ``scope`` sí aplica.

    Para ``--format arrow``, ``network_type`` controla la red tipada del
    ADR 0052 (D1/D2/D4/D5): default ``bibliographic_coupling``. Solo aplica
    a ``arrow``; para ``bibtex`` la red no se embebe (los kinds no-paper
    no tienen dónde anclarse).

    Args:
        store_path: Ruta al archivo ``.duckdb``.
        format: Formato de salida (``graphml``, ``csv``, ``arrow`` o
            ``bibtex``).
        out_dir: Directorio de salida para los archivos exportados.
        networks_dir: Directorio base de artefactos de build (solo
            ``graphml``/``csv``/``arrow`` con red; default:
            ``<store_dir>/networks/``).
        scope: Vocab interno de scope (``all``/``accepted``/``seeds_only``).
            Solo aplica a ``arrow``/``bibtex`` (ADR 0050 D4).
        scope_explicit: ``True`` si el caller pasó ``--scope`` explícito en
            la CLI. Se usa para emitir el warning de scope-ignorado cuando
            ``format`` es de red y el usuario igual pasó ``--scope``.
        network_type: ``NetworkKind`` a embeber en el Arrow. Default
            ``"bibliographic_coupling"`` (la más robusta en one-shot, D2).
            Solo aplica a ``--format arrow``.

    Returns:
        Dict con ``format``, ``out_dir``, ``files_written`` y, según la
        familia de formato, ``networks_exported`` (redes) o ``rows_exported``
        (corpus). Incluye ``warnings`` (lista, puede ser vacía) y, para
        ``--format arrow``, los 7 campos aditivos del envelope
        (``network_type``, ``network_nodes``, ``network_edges``,
        ``network_communities``, ``network_modularity``, ``network_type_algo``,
        ``network_resolution``).

    Raises:
        DataError: Si no hay artefactos de build disponibles (redes), el
            formato no se reconoce, o ``network_type=cocitation`` sin
            ``cited_by_id`` poblado.
        StoreError: Si el store está bloqueado.
        ImportError: Si falta ``bibtexparser`` (formato ``bibtex``).
    """
    warnings: list[str] = []

    if format in _NETWORK_FORMATS:
        if scope_explicit:
            warnings.append(
                f"--scope se ignora con --format {format}: las redes de build ya "
                "vienen scopeadas por 'b2g build --scope'. --scope solo aplica a "
                "--format arrow|bibtex (ADR 0050 D4)."
            )
        data = _export_networks(
            format,
            out_dir=out_dir,
            networks_dir=networks_dir,
            store_path=store_path,
        )
    elif format in _CORPUS_FORMATS:
        if networks_dir is None:
            effective_networks_dir: Path = Path(store_path).parent / "networks"
        else:
            effective_networks_dir = Path(networks_dir)
        data = _export_corpus(
            format,
            out_dir=out_dir,
            store_path=store_path,
            scope=scope,
            networks_dir=effective_networks_dir,
            network_type=network_type,
        )
    else:
        raise DataError(
            f"Formato '{format}' no reconocido. Usá 'graphml', 'csv', 'arrow' o 'bibtex'."
        )

    # Fusionar (no pisar): _export_corpus ya puede traer sus propios warnings
    # (p. ej. equation_hash omitido, ADR 0050 D3) en data["warnings"]. Este
    # dict es el contrato de ``run_export`` (usado directo en tests, sin
    # pasar por el envelope) — mantiene ``data["warnings"]`` como fuente única
    # de verdad para callers no-CLI. QA 0.14.0 (hallazgo #3): es el caller CLI
    # (``export_cmd``) quien debe evitar duplicarlas al construir el envelope
    # (ver ahí: se extraen de ``data`` en vez de copiarse a un canal aparte).
    data["warnings"] = warnings + list(data.get("warnings") or [])
    return data


@click.command("export")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["graphml", "csv", "arrow", "bibtex"]),
    default="graphml",
    show_default=True,
    help=(
        "Formato de salida. 'graphml'/'csv' serializan redes de build; "
        "'arrow'/'bibtex' serializan el CORPUS (ADR 0050 D4)."
    ),
)
@click.option(
    "--scope",
    "scope",
    type=click.Choice(["all", "accepted", "seeds"]),
    default=None,
    help=(
        "Filtra el corpus antes de exportar. Solo aplica a --format arrow|bibtex "
        "(ADR 0050 D4); se IGNORA con --format graphml|csv (esas redes ya vienen "
        "scopeadas por 'b2g build --scope'). 'all' = corpus completo (default); "
        "'accepted' = semillas + aceptados; 'seeds' = solo semillas."
    ),
)
@click.option(
    "--network-type",
    "network_type",
    type=click.Choice(
        [
            NetworkKind.BIBLIOGRAPHIC_COUPLING.value,
            NetworkKind.COCITATION.value,
            NetworkKind.AUTHOR_COLLAB.value,
            NetworkKind.INSTITUTION_COLLAB.value,
            NetworkKind.KEYWORD_COOCCURRENCE.value,
        ],
        case_sensitive=False,
    ),
    default=NetworkKind.BIBLIOGRAPHIC_COUPLING.value,
    show_default=True,
    help=(
        "Red del b2g build a embeber en el Arrow (ADR 0052 D2). Solo aplica a "
        "--format arrow: agrega columnas de red (community_id, degree_weighted, "
        "intra_community_pagerank, network_edges, network_communities) + "
        "metadata del schema. Kinds no-paper (author_collab, institution_collab, "
        "keyword_cooccurrence) salen sin red + warning. cocitation requiere "
        "cited_by_id poblado (sino: error accionable). Si no hay b2g build "
        "previo, modo degradado (sin columnas de red) + warning."
    ),
)
@click.option(
    "--out-dir",
    default=None,
    help=(
        "Directorio de salida para los archivos exportados "
        "(default: <workspace>/exports/ o <store_dir>/exports/)."
    ),
)
@json_option
@click.pass_context
@handle_errors("export")
def export_cmd(
    ctx: click.Context,
    fmt: str,
    scope: str | None,
    network_type: str,
    out_dir: str | None,
    json_output: bool,
) -> None:
    """Serializa artefactos al formato pedido.

    No transiciona el CycleState.

    - 'graphml'/'csv': re-emiten las redes de build (ya scopeadas por
      ``b2g build --scope``).
    - 'arrow'/'bibtex' (ADR 0050 D4): serializan el CORPUS del store vivo,
      scopeado por ``--scope`` de este comando. ``--format arrow`` admite
      ``--network-type`` para embeber la red tipada del último ``b2g build``
      (ADR 0052).

    El directorio de salida por defecto es ``<workspace>/exports/``.
    Con ``--out-dir`` se puede especificar un directorio alternativo.
    """
    # ADR 0029: resolver workspace para obtener dirs canónicos
    ws = resolve_workspace(ctx.obj)
    effective_out_dir: Path = Path(out_dir) if out_dir is not None else ws.exports_dir

    scope_explicit = scope is not None
    internal_scope = _map_scope(scope) if scope is not None else "all"

    data = run_export(
        ws.library_path,
        format=fmt,  # type: ignore[arg-type]
        out_dir=effective_out_dir,
        networks_dir=ws.networks_dir,
        scope=internal_scope,
        scope_explicit=scope_explicit,
        network_type=network_type,
    )

    # ADR 0045 (#259): eco de workspace + warning accionable en walk-up.
    data["workspace"] = workspace_echo(ws)

    # QA 0.14.0 (hallazgo #3): el envelope tiene UN solo canal canónico de
    # warnings — el ``warnings`` top-level (ADR 0021 §C). Antes ``data``
    # (con su propia clave ``warnings``, p. ej. el aviso de equation_hash
    # omitido, ADR 0050 D3) se pasaba completo como ``data=data`` Y además
    # se copiaban las mismas warnings al top-level, duplicando el texto en
    # ``data.warnings`` y en ``warnings``. Se extraen (``pop``, no ``get``)
    # de ``data`` para que sobrevivan en un solo lugar.
    data_warnings: list[str] = list(data.pop("warnings", None) or [])

    if json_mode(json_output):
        all_warnings: list[str] = list(data_warnings)
        all_warnings.extend(workspace_walkup_warning(ws))
        envelope = build_envelope(
            command="export",
            ok=True,
            data=data,
            exit_code=0,
            warnings=all_warnings or None,
        )
        emit(envelope)
    else:
        for w in data_warnings:
            print(f"ADVERTENCIA: {w}", file=sys.stderr)
        if "networks_exported" in data:
            emit_human(f"Exportados {data['networks_exported']} redes en formato {fmt}")
        else:
            emit_human(f"Exportadas {data['rows_exported']} filas en formato {fmt}")
        emit_human(f"Directorio: {data['out_dir']}")
        for f in data["files_written"]:
            emit_human(f"  {f}")
