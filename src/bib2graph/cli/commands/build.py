"""cli.commands.build — Subcomando ``b2g build``.

Computa las redes bibliométricas y escribe artefactos a disco.
Transiciona el CycleState a BUILT tras persistir con éxito.

Modos de operación (ADR 0038, #159):
  - **Sin ``--spec``** (one-shot): usa ``Networks.quick``.  Construye las 4-5
    redes principales.
  - **Con ``--spec``** (declarativo): carga un YAML con ``load_specs`` y
    construye cada red con ``Networks.build``.  Absorbe la capacidad de
    ``b2g networks``, pero con transición de FSM y sellado de hash (D1).

En AMBOS modos:
  - ``--scope`` pre-filtra el corpus (``all`` / ``accepted`` / ``seeds``).
  - ``--min-weight`` filtra aristas con peso < N (default 1 = sin filtro).
  - Se transiciona a BUILT y se sella ``networks/.corpus_hash``.
  - Se diagnostican redes vacías en build-time, reusando ``predict_build_preview``
    (fuente única con ``status``, ADR 0037 §(e)).

ADR 0029 — workspace:
  El directorio de artefactos es ``<workspace>/networks/`` por defecto.
  Si se pasa ``--out-dir`` explícito, se usa ese.

ADR 0029 — sellado por corpus_hash:
  Escribe ``networks/.corpus_hash`` con el hash del corpus **filtrado** que
  produjo las redes. Permite detectar staleness sin un build system completo.

Los artefactos se escriben en ``<networks_dir>/<kind>/``:
  - ``network.graphml``: el grafo en formato GraphML.
  - ``metrics.json``: métricas de red calculadas.
  - ``clusters.csv``: tabla de resumen de comunidades (solo redes de paper
    con comunidades detectadas, issue #31).
"""

from __future__ import annotations

import csv as _csv
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click

from bib2graph.cli._envelope import build_envelope, emit, emit_human
from bib2graph.cli._errors import DataError, DependencyError, handle_errors
from bib2graph.cli._options import json_mode, json_option
from bib2graph.cli._store import open_store, resolve_workspace

if TYPE_CHECKING:
    from bib2graph.corpus import Corpus
    from bib2graph.networks.spec import NetworkArtifact


# ---------------------------------------------------------------------------
# Helper: mapeo del vocabulario CLI de --scope al vocabulario interno de corpus.scoped()
# ---------------------------------------------------------------------------


def _map_scope(scope: str) -> str:
    """Mapea el vocab de ``--scope`` (CLI) al vocab interno de ``corpus.scoped()``.

    ``--scope`` usa ``seeds`` (forma corta), mientras que ``corpus.scoped()``
    espera ``seeds_only``.  Los demás valores son idénticos en ambos vocabs.

    Args:
        scope: Valor del flag ``--scope`` (``all`` | ``accepted`` | ``seeds``).

    Returns:
        Vocabulario interno: ``all`` | ``accepted`` | ``seeds_only``.
    """
    if scope == "seeds":
        return "seeds_only"
    return scope


# ---------------------------------------------------------------------------
# Helper compartido: carga de specs YAML + construcción de artefactos
# ---------------------------------------------------------------------------


def _build_from_spec_file(
    corpus: Corpus,
    spec_path: str | Path,
) -> list[NetworkArtifact]:
    """Carga specs YAML y construye artefactos con ``Networks.build``.

    Helper compartido entre ``run_build --spec`` y ``run_networks``.
    Centraliza la carga YAML + proyección para que ambos comandos no diverjan
    (frontera con #165: cuando ``networks`` se retire, no habrá reconciliación).

    Args:
        corpus: Corpus ya filtrado (scope aplicado por quien llama).
        spec_path: Ruta al archivo YAML con la definición de redes.

    Returns:
        Lista de ``NetworkArtifact`` en el orden del YAML.

    Raises:
        DataError: Si el YAML está malformado o alguna spec es inválida.
        DependencyError: Si falta ``python-louvain`` al detectar comunidades.
    """
    from bib2graph.networks.facade import Networks
    from bib2graph.networks.spec import load_specs

    try:
        specs = load_specs(spec_path)
    except (ValueError, FileNotFoundError) as exc:
        raise DataError(str(exc)) from exc

    try:
        return [Networks.build(corpus, spec) for spec in specs]
    except ImportError as exc:
        raise DependencyError(
            f"Dependencia faltante para detectar comunidades: {exc}. "
            "Instalá python-louvain: uv add python-louvain."
        ) from exc


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

        # D3 — incluir asortatividad en metrics.json cuando está disponible.
        # community_composition es un dict anidado; se incluye dentro de
        # assortativity para no alterar el schema de primer nivel.
        metrics_payload: dict[str, object] = {
            "kind": kind,
            "nodes": art.graph.number_of_nodes(),
            "edges": art.graph.number_of_edges(),
            **safe_metrics,
        }
        if art.assortativity is not None:
            metrics_payload["assortativity"] = art.assortativity

        metrics_path.write_text(
            json.dumps(metrics_payload, ensure_ascii=False),
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
        if art.assortativity is not None:
            net_entry["assortativity"] = art.assortativity
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
    spec_path: str | Path | None = None,
    min_weight: int = 1,
    scope_cli_token: str | None = None,
) -> dict[str, Any]:
    """Computa redes bibliométricas y escribe artefactos a disco.

    Modos de operación (#159 — absorción de ``networks``):
    - **Sin ``spec_path``**: usa ``Networks.quick(corpus, min_weight=min_weight)``
      para las 4-5 redes principales.
    - **Con ``spec_path``**: carga YAML con ``load_specs`` y construye cada red
      con ``Networks.build``.

    En AMBOS modos:
    - ``corpus_scope`` pre-filtra el corpus antes de construir redes.
    - Se transiciona a BUILT y se sella ``networks/.corpus_hash`` con el hash
      del corpus **filtrado** (D1 — ADR 0038).
    - Se diagnostican redes vacías usando ``predict_build_preview`` como fuente
      única (ADR 0037 §(e) — no-divergencia con ``status``).

    Para redes de paper con comunidades detectadas escribe también clusters.csv
    (tabla de resumen de comunidades, issue #31).

    Args:
        store_path: Ruta al archivo ``.duckdb``.
        out_dir: Directorio base de salida. Default: ``<store_dir>/networks/``.
        corpus_scope: Filtro de curación aplicado antes de construir las redes.
            ``'all'`` (default) = corpus completo; ``'accepted'`` = semillas +
            aceptados; ``'seeds_only'`` = solo semillas.
        spec_path: Ruta al YAML de specs (opcional). Si se omite, usa quick.
        min_weight: Peso mínimo de arista. Default 1 = sin filtro.
            Solo aplica al modo quick (sin spec); en modo spec, ``NetworkSpec``
            del YAML lleva su propio ``min_weight``.
        scope_cli_token: Token CLI tal como lo tipió el usuario
            (``'seeds'``/``'accepted'``/``'all'``). Si se pasa, ``data["scope"]``
            expone este token en lugar del vocab interno. Permite que #160
            (maturity) y la CLI sean consistentes. Si se omite (llamadas directas
            sin CLI), ``data["scope"]`` queda igual a ``corpus_scope``.

    Returns:
        Dict con ``networks_built``, ``artifacts_dir``, ``corpus_hash``,
        ``corpus_scope`` (vocab interno), ``scope`` (token CLI o vocab interno),
        lista de redes, ``warnings`` y ``empty_networks``.

    Raises:
        DataError: Si ``spec_path`` está malformado (modo spec).
        DependencyError: Si falta ``python-louvain``.
        StoreError: Si el store está bloqueado.
    """
    import warnings as _warnings

    from bib2graph.cycle import apply_transition
    from bib2graph.networks.facade import Networks, predict_build_preview

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
                "corré `b2g curate` para aceptar papers o usá `--scope=all`."
            )
            _warnings.warn(msg, stacklevel=2)
            build_warnings.append(msg)
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            (artifacts_dir / ".corpus_hash").write_text("", encoding="utf-8")
            store.backend.set_loop_state(new_state, cycle_round=new_round)
            # scope_display para early-return (corpus vacío): mismo cálculo que el path normal.
            _scope_display_empty = (
                scope_cli_token if scope_cli_token is not None else corpus_scope
            )
            # Maturity en early-return: curated desde corpus_full (el filtrado está vacío).
            from bib2graph.service.maturity import compute_maturity as _compute_maturity

            _maturity_empty = _compute_maturity(
                corpus_full,
                scope=_scope_display_empty,
                empty_network_kinds=[],
            )
            return {
                "networks_built": 0,
                "artifacts_dir": str(artifacts_dir),
                "corpus_hash": "",
                "corpus_scope": corpus_scope,
                "scope": _scope_display_empty,
                "networks": [],
                "warnings": build_warnings,
                "empty_networks": [],
                "maturity": _maturity_empty,
            }

        # Diagnóstico pre-build (ADR 0037 §(e), fuente única con status-time).
        # Indexado por kind para lookup O(1) en el loop post-build.
        preview_by_kind = {str(e["kind"]): e for e in predict_build_preview(corpus)}

        # Construir artefactos según el modo.
        if spec_path is not None:
            # Modo declarativo: YAML → specs → Networks.build por red.
            # _build_from_spec_file levanta DataError / DependencyError.
            artifacts = _build_from_spec_file(corpus, spec_path)
        else:
            # Modo quick: Networks.quick con min_weight propagado a cada spec.
            try:
                artifacts = Networks.quick(corpus, min_weight=min_weight)
            except ImportError as exc:
                raise DependencyError(
                    f"Dependencia faltante para detectar comunidades: {exc}. "
                    "Instalá python-louvain: uv add python-louvain."
                ) from exc

        networks_info = _write_artifacts(artifacts, corpus, artifacts_dir)

        # Diagnóstico de redes vacías en build-time.
        # Reusa los reason/fix_command del preview (fuente única — ADR 0037 §(e)).
        # Si el preview predijo no-vacía pero salió vacía, sospechamos min_weight.
        empty_networks: list[dict[str, object]] = []
        for art in artifacts:
            kind_str = str(art.spec.kind)
            is_empty = (
                art.graph.number_of_nodes() == 0 or art.graph.number_of_edges() == 0
            )
            if not is_empty:
                continue

            preview_entry = preview_by_kind.get(kind_str)
            if preview_entry and preview_entry["would_be_empty"]:
                # Preview ya predijo vacía — usar su reason/fix_command (no-divergencia).
                reason: str = (
                    str(preview_entry["reason"])
                    if preview_entry["reason"]
                    else "Red vacía"
                )
                fix_cmd: str | None = (
                    str(preview_entry["fix_command"])
                    if preview_entry["fix_command"]
                    else None
                )
            elif spec_path is None and min_weight > 1:
                # Modo quick: el --min-weight del CLI filtró todas las aristas.
                reason = f"0 aristas con peso ≥ {min_weight}; bajá --min-weight"
                fix_cmd = f"b2g build --min-weight {min_weight - 1}"
            elif spec_path is not None and art.spec.min_weight > 1:
                # Modo spec: el min_weight del propio YAML filtró todas las aristas.
                # El --min-weight de la CLI NO se usa en modo spec → no sugerir bajarlo.
                reason = (
                    f"0 aristas con peso ≥ {art.spec.min_weight} "
                    f"(min_weight del spec '{kind_str}'); ajustá el spec"
                )
                fix_cmd = None
            else:
                # Caso inesperado: red vacía sin causa clara identificable.
                reason = "Red vacía (sin datos suficientes)"
                fix_cmd = None

            empty_networks.append(
                {"kind": kind_str, "reason": reason, "fix_command": fix_cmd}
            )
            # Los diagnósticos de red vacía van solo en data["empty_networks"].
            # data["warnings"] queda reservado para avisos de corpus-scope
            # (p. ej. "0 papers"); esto mantiene la compat con tests pre-0.10.0
            # que verifican data["warnings"] == [] cuando el corpus no está vacío.

        # ADR 0029 — sellar con corpus_hash del corpus FILTRADO (no del vivo completo).
        # D1: en AMBOS modos (quick y spec) transicionar + sellar (ADR 0038).
        from bib2graph.backends.memory import compute_corpus_hash

        corpus_hash = compute_corpus_hash(corpus.to_arrow())
        hash_file = artifacts_dir / ".corpus_hash"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        hash_file.write_text(corpus_hash, encoding="utf-8")

        store.backend.set_loop_state(new_state, cycle_round=new_round)

        # FIX 2 — gancho para #160 (maturity): "scope" expone el token CLI tal como
        # lo tipió el usuario ("seeds"/"accepted"/"all"), NO el vocab interno
        # ("seeds_only"). Esto hace que la superficie de agents-first sea consistente.
        # Cuando se llama sin CLI (tests unitarios directos), scope_cli_token=None
        # y se usa corpus_scope como fallback (preserva compat pre-0.10.0).
        scope_display = scope_cli_token if scope_cli_token is not None else corpus_scope

        # Maturity (#160): computar DENTRO del try para acceder a corpus_full
        # antes del store.close() en finally.  Extrae los kinds de empty_networks
        # (lista de dicts {kind, reason, fix_command}) sin duplicar reason/fix_command.
        from bib2graph.service.maturity import compute_maturity as _compute_maturity

        empty_network_kinds = [str(en["kind"]) for en in empty_networks]
        maturity = _compute_maturity(
            corpus_full,
            scope=scope_display,
            empty_network_kinds=empty_network_kinds,
        )
    finally:
        store.close()

    return {
        "networks_built": len(artifacts),
        "artifacts_dir": str(artifacts_dir),
        "corpus_hash": corpus_hash,
        "corpus_scope": corpus_scope,
        "scope": scope_display,
        "networks": networks_info,
        "warnings": build_warnings,
        "empty_networks": empty_networks,
        "maturity": maturity,
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
    "--scope",
    "scope",
    type=click.Choice(["all", "accepted", "seeds"]),
    default="all",
    show_default=True,
    help=(
        "Filtra el corpus antes de construir las redes. "
        "'all' = corpus completo (default); "
        "'accepted' = semillas (is_seed=True) + papers aceptados; "
        "'seeds' = solo semillas (is_seed=True). "
        "Si el scope deja 0 papers, termina con exit 0 y un warning accionable."
    ),
)
@click.option(
    "--corpus-scope",
    "corpus_scope_deprecated",
    type=click.Choice(["all", "accepted", "seeds_only"]),
    default=None,
    hidden=True,
    help=(
        "DEPRECATED (cierra en 0.11.0): usar --scope. "
        "Acepta los valores antiguos all|accepted|seeds_only."
    ),
)
@click.option(
    "--spec",
    "spec_path",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help=(
        "Ruta al YAML con la especificación de redes. "
        "Si se pasa, usa Networks.build por spec en lugar de Networks.quick. "
        "Sigue transicionando a BUILT y sellando corpus_hash (D1)."
    ),
)
@click.option(
    "--min-weight",
    "min_weight",
    type=int,
    default=1,
    show_default=True,
    help=(
        "Peso mínimo de arista (default 1 = sin filtro). "
        "Aristas con peso < N se descartan. "
        "Solo aplica al modo quick (sin --spec); en modo spec el YAML lleva su propio min_weight."
    ),
)
@json_option
@click.pass_context
@handle_errors("build")
def build_cmd(
    ctx: click.Context,
    out_dir: str | None,
    scope: str,
    corpus_scope_deprecated: str | None,
    spec_path: str | None,
    min_weight: int,
    json_output: bool,
) -> None:
    """Computa redes bibliométricas y escribe artefactos.

    Sin ``--spec``: usa Networks.quick (4-5 redes principales).
    Con ``--spec``: carga el YAML y construye cada red con Networks.build.

    En ambos modos transiciona a BUILT y sella networks/.corpus_hash.
    """
    # ADR 0029: usar networks_dir del workspace si no se especifica --out-dir
    ws = resolve_workspace(ctx.obj)
    effective_out_dir: str | Path | None = out_dir
    if effective_out_dir is None:
        effective_out_dir = ws.networks_dir

    # Resolver scope: --corpus-scope deprecado tiene prioridad con aviso.
    if corpus_scope_deprecated is not None:
        print(
            "AVISO: --corpus-scope está deprecado y se eliminará en 0.11.0; "
            "usá --scope en su lugar.",
            file=sys.stderr,
        )
        # El vocab deprecado (all|accepted|seeds_only) ya es el vocab interno.
        # Preservamos el mismo token para scope_cli_token (compat pre-0.10.0).
        internal_scope = corpus_scope_deprecated
        cli_token: str = corpus_scope_deprecated
    else:
        # El vocab nuevo (all|accepted|seeds) necesita mapeo para seeds→seeds_only.
        internal_scope = _map_scope(scope)
        # scope es el token tal como lo tipió el usuario ("seeds"/"accepted"/"all").
        cli_token = scope

    # FIX 1a — footgun: --min-weight se ignora en modo spec.
    # Avisar explícitamente para no perder la intención del usuario en silencio.
    if spec_path is not None and min_weight > 1:
        print(
            "--min-weight se ignora con --spec; cada red usa el min_weight de su YAML.",
            file=sys.stderr,
        )

    data = run_build(
        ws.library_path,
        out_dir=effective_out_dir,
        corpus_scope=internal_scope,
        spec_path=spec_path,
        min_weight=min_weight,
        scope_cli_token=cli_token,
    )

    if json_mode(json_output):
        envelope = build_envelope(
            command="build",
            ok=True,
            data=data,
            exit_code=0,
            warnings=data.get("warnings"),
        )
        emit(envelope)
    else:
        # Warnings van a stderr en modo humano (ADR 0021 §C; patrón de status.py).
        for w in data.get("warnings", []):
            print(f"ADVERTENCIA: {w}", file=sys.stderr)
        # Diagnósticos de redes vacías también a stderr (no son warnings de corpus).
        for en in data.get("empty_networks", []):
            fix = f" Sugerencia: {en['fix_command']}" if en.get("fix_command") else ""
            print(
                f"ADVERTENCIA: Red '{en['kind']}' vacía — {en['reason']}.{fix}",
                file=sys.stderr,
            )
        emit_human(f"Redes construidas: {data['networks_built']}")
        emit_human(f"Artefactos en: {data['artifacts_dir']}")
        emit_human(f"corpus_hash: {data['corpus_hash']}")
        for net in data["networks"]:
            emit_human(f"  {net['kind']}: {net['nodes']} nodos, {net['edges']} aristas")
