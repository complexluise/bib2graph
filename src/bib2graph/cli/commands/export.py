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

#: Formatos que serializan artefactos de build (redes); ignoran ``--scope``.
_NETWORK_FORMATS = frozenset({"graphml", "csv"})
#: Formatos que serializan el corpus; respetan ``--scope`` (ADR 0050 D4).
_CORPUS_FORMATS = frozenset({"arrow", "bibtex"})


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
) -> dict[str, Any]:
    """Serializa el corpus (scopeado) a Arrow (Feather) o BibTeX.

    Args:
        format: ``"arrow"`` o ``"bibtex"``.
        out_dir: Directorio de salida para el archivo exportado.
        store_path: Ruta al archivo ``.duckdb``.
        scope: Vocab interno de scope (``all``/``accepted``/``seeds_only``).

    Returns:
        Dict con ``format``, ``out_dir``, ``files_written``, ``rows_exported``
        y ``warnings`` (lista, puede ser vacía). Para ``format == "arrow"``
        incluye el warning accionable de ``build_equation_metadata`` cuando el
        corpus tiene 0 o >1 ecuaciones registradas (ADR 0050 D3): el
        ``equation_hash`` se omite en ese caso y el usuario debe saberlo, en
        vez de descubrirlo en silencio al inspeccionar el ``.arrow``.

    Raises:
        ImportError: Si falta ``bibtexparser`` (formato ``bibtex``, extra
            ``[bibtex]``).
    """
    from bib2graph.backends.memory import build_equation_metadata
    from bib2graph.exporters.arrow import ArrowExporter
    from bib2graph.exporters.bibtex import BibtexExporter

    corpus_warnings: list[str] = []

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

    return {
        "format": format,
        "out_dir": str(out_path),
        "files_written": [str(dest)],
        "rows_exported": table.num_rows,
        "warnings": corpus_warnings,
    }


def run_export(
    store_path: str | Path,
    *,
    format: Literal["graphml", "csv", "arrow", "bibtex"] = "graphml",
    out_dir: str | Path,
    networks_dir: str | Path | None = None,
    scope: str = "all",
    scope_explicit: bool = False,
) -> dict[str, Any]:
    """Serializa artefactos al formato pedido.

    Para ``graphml``/``csv`` relee los artefactos de build de
    ``<store_dir>/networks/<kind>/network.graphml`` (``scope`` se ignora:
    esos artefactos ya vienen scopeados de ``b2g build --scope``).

    Para ``arrow``/``bibtex`` (ADR 0050 D4) serializa
    ``corpus.scoped(scope).to_arrow()`` del store vivo — ``scope`` sí aplica.

    Args:
        store_path: Ruta al archivo ``.duckdb``.
        format: Formato de salida (``graphml``, ``csv``, ``arrow`` o
            ``bibtex``).
        out_dir: Directorio de salida para los archivos exportados.
        networks_dir: Directorio base de artefactos de build (solo
            ``graphml``/``csv``; default: ``<store_dir>/networks/``).
        scope: Vocab interno de scope (``all``/``accepted``/``seeds_only``).
            Solo aplica a ``arrow``/``bibtex`` (ADR 0050 D4).
        scope_explicit: ``True`` si el caller pasó ``--scope`` explícito en
            la CLI. Se usa para emitir el warning de scope-ignorado cuando
            ``format`` es de red y el usuario igual pasó ``--scope``.

    Returns:
        Dict con ``format``, ``out_dir``, ``files_written`` y, según la
        familia de formato, ``networks_exported`` (redes) o ``rows_exported``
        (corpus). Incluye ``warnings`` (lista, puede ser vacía).

    Raises:
        DataError: Si no hay artefactos de build disponibles (redes) o el
            formato no se reconoce.
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
        data = _export_corpus(
            format,
            out_dir=out_dir,
            store_path=store_path,
            scope=scope,
        )
    else:
        raise DataError(
            f"Formato '{format}' no reconocido. Usá 'graphml', 'csv', 'arrow' o 'bibtex'."
        )

    # Fusionar (no pisar): _export_corpus ya puede traer sus propios warnings
    # (p. ej. equation_hash omitido, ADR 0050 D3) en data["warnings"].
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
    out_dir: str | None,
    json_output: bool,
) -> None:
    """Serializa artefactos al formato pedido.

    No transiciona el CycleState.

    - 'graphml'/'csv': re-emiten las redes de build (ya scopeadas por
      ``b2g build --scope``).
    - 'arrow'/'bibtex' (ADR 0050 D4): serializan el CORPUS del store vivo,
      scopeado por ``--scope`` de este comando.

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
    )

    # ADR 0045 (#259): eco de workspace + warning accionable en walk-up.
    data["workspace"] = workspace_echo(ws)

    if json_mode(json_output):
        all_warnings: list[str] = list(data.get("warnings") or [])
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
        for w in data.get("warnings", []):
            print(f"ADVERTENCIA: {w}", file=sys.stderr)
        if "networks_exported" in data:
            emit_human(f"Exportados {data['networks_exported']} redes en formato {fmt}")
        else:
            emit_human(f"Exportadas {data['rows_exported']} filas en formato {fmt}")
        emit_human(f"Directorio: {data['out_dir']}")
        for f in data["files_written"]:
            emit_human(f"  {f}")
