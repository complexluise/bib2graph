"""service.reads — Funciones de lectura de la capa de servicios (ADR 0028).

Capa de servicios neutral: sin ``print``, ``sys.exit``, Click ni FastAPI.
Cada función recibe el ``store_path`` o el ``Workspace`` ya resuelto (la
resolución de workspace se hace en el adaptador CLI), abre el store en
modo lectura, y devuelve un ``dict`` serializable o lanza un ``B2GError``
tipado.

Lecturas del Hito G2 (6 originales):
  - ``get_workspace`` — estado del workspace activo (nombre, loop_state, ronda,
    conteos, staleness de cache de redes).
  - ``list_rounds`` — snapshots sellados en ``<workspace>/snapshots/`` más una
    entrada sintética ``id="live"`` para el corpus vivo.
  - ``get_paper`` — fila completa del corpus resolviendo por id, doi o source_id
    (ADR 0036; antes solo por id). Prioridad: id > doi > source_id.
  - ``get_scent`` — score de acoplamiento + vecinos compartidos de un paper
    ya en el corpus.
  - ``get_network`` — red de la ronda viva (desde cache ``networks/`` o recomputo).
  - ``compare_rounds`` — diff entre dos snapshots (added/removed paper_ids +
    métricas básicas).

Lecturas del grupo ``read`` (sub-issues #156, #157):
  - ``list_papers`` — lista papers con filtros opcionales: query (título
    substring CI), status, is_seed, year. Payload mínimo para listados.
  - ``corpus_stats`` — estadísticas agregadas del corpus, agrupadas por
    ``status``, ``year`` o ``is_seed``.
  - ``get_top`` — nodos más centrales de la red ``kind`` + pares de co-citación
    con título resuelto (#157).

Decisiones de producto (Bifurcaciones B-G2-1/B-G2-2/B-G2-3):
  - Ronda = snapshot sellado (Opción A). ``list_rounds``/``compare_rounds``
    se anclan a los snapshots de ``<workspace>/snapshots/``.
  - ``get_scent`` expone el score de acoplamiento real (referencias compartidas
    + resoluciones de referencias e citantes en el corpus), NO 4 paneles cosméticos.
  - ``get_network`` sirve la red viva. ``kind`` inválido o sin red → ``DataError``.
  - ``get_top``: red vacía → honest-empty (exit 0 + bloques vacíos + reason/fix_command);
    NO ``DataError``.  ``n <= 0`` o ``kind`` inválido → ``DataError``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from bib2graph.constants import Col, NetworkKind
from bib2graph.service.errors import DataError, StoreError

if TYPE_CHECKING:
    from bib2graph.workspace import Workspace


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _open_readonly(path: Path) -> Any:
    """Abre el store en modo lectura; falla accionable si no existe.

    Args:
        path: Ruta al archivo ``.duckdb``.

    Returns:
        ``DuckDBStore`` abierto y listo para leer.

    Raises:
        StoreError: Si el archivo no existe o no se puede abrir.
    """
    from bib2graph.backends.duckdb import StoreLockedError
    from bib2graph.stores.duckdb import DuckDBStore

    if not path.exists():
        raise StoreError(
            f"El store '{path}' no existe. "
            "Verificá la ruta o iniciá la investigación con 'b2g seed'."
        )
    try:
        return DuckDBStore(path)
    except StoreLockedError as exc:
        raise StoreError(str(exc)) from exc
    except OSError as exc:
        raise StoreError(
            f"No se puede abrir el store '{path}': {exc}. "
            "Verificá que el archivo no esté bloqueado por otro proceso."
        ) from exc


# ---------------------------------------------------------------------------
# 1. get_workspace
# ---------------------------------------------------------------------------


def get_workspace(ws: Workspace) -> dict[str, Any]:
    """Lee el estado actual del workspace: nombre, loop_state, ronda y conteos.

    Reutiliza la misma lógica de lectura de ``run_status`` migrada a la capa
    de servicios. El command CLI ``b2g status`` puede delegarle la lectura y
    mantener solo el I/O (emit/handle_errors).

    Args:
        ws: Workspace resuelto (ADR 0029).

    Returns:
        Dict con: ``name``, ``root``, ``created_at``, ``bib2graph_version``,
        ``source``, ``loop_state``, ``round``, ``total_papers``,
        ``counts_by_status``, ``transitions_available``,
        ``curation_available``, ``networks_cache_stale``.

    Raises:
        StoreError: Si el store no existe o está bloqueado.
    """
    from bib2graph.backends.memory import compute_corpus_hash
    from bib2graph.constants import Col
    from bib2graph.cycle import CURATION_ACTIONS, available_transitions

    store = _open_readonly(ws.library_path)

    loop_state = store.backend.loop_state()
    state_str = loop_state.value if loop_state is not None else None
    current_round = store.backend.loop_round()

    counts_table = store.backend.query(
        f"SELECT {Col.CURATION_STATUS.value}, COUNT(*) as cnt FROM corpus GROUP BY 1"
    )
    counts: dict[str, int] = {}
    if len(counts_table) > 0:
        for row in counts_table.to_pylist():
            status = str(row[Col.CURATION_STATUS])
            counts[status] = int(row["cnt"])

    total = sum(counts.values())

    # Staleness de la cache de redes
    corpus = store.load()
    live_hash = compute_corpus_hash(corpus.to_arrow())
    networks_cache_stale = ws.is_networks_cache_stale(live_hash)

    transitions = available_transitions(loop_state)
    curation = list(CURATION_ACTIONS)

    manifest = ws.manifest
    return {
        "name": manifest.name if manifest else None,
        "root": str(ws.root),
        "created_at": manifest.created_at if manifest else None,
        "bib2graph_version": manifest.bib2graph_version if manifest else None,
        "source": ws.source,
        "loop_state": state_str,
        "round": current_round,
        "total_papers": total,
        "counts_by_status": counts,
        "transitions_available": transitions,
        "curation_available": curation,
        "networks_cache_stale": networks_cache_stale,
    }


# ---------------------------------------------------------------------------
# 2. list_rounds
# ---------------------------------------------------------------------------


def list_rounds(ws: Workspace) -> list[dict[str, Any]]:
    """Lista los snapshots sellados del workspace más la entrada "live".

    Escanea ``<workspace>/snapshots/`` y lee el ``manifest.json`` de cada
    subdirectorio. Agrega una entrada sintética ``id="live"`` con el estado
    actual del corpus.

    Args:
        ws: Workspace resuelto.

    Returns:
        Lista de dicts; cada snapshot tiene:
        ``{id, corpus_hash, created_at, total_papers, schema_version}``.
        La entrada viva tiene:
        ``{id="live", round, loop_state, total_papers}``.

    Raises:
        StoreError: Si el store no existe o está bloqueado.
    """
    # Snapshots sellados (helper read-only del Workspace; ronda = snapshot, B-G2-1)
    rounds: list[dict[str, Any]] = ws.list_snapshots()

    # Entrada sintética para el corpus vivo
    store = _open_readonly(ws.library_path)
    loop_state = store.backend.loop_state()
    current_round = store.backend.loop_round()

    corpus = store.load()
    rounds.append(
        {
            "id": "live",
            "round": current_round,
            "loop_state": loop_state.value if loop_state is not None else None,
            "total_papers": len(corpus),
        }
    )

    return rounds


# ---------------------------------------------------------------------------
# 3. get_paper
# ---------------------------------------------------------------------------


def get_paper(ws: Workspace, ident: str) -> dict[str, Any]:
    """Devuelve la fila completa del corpus para un paper.

    Resuelve ``ident`` contra tres columnas en orden de prioridad:
    ``Col.ID`` (exacto) → ``Col.DOI`` (exacto) → ``Col.SOURCE_ID`` (exacto).
    Si varios matchean, gana el que coincide por ``id``.
    Coherente con ADR 0036 (identidad source-agnóstica, DOI ancla).

    Incluye todos los campos del ``CORPUS_SCHEMA``: id, source_id, doi,
    title, year, abstract, is_seed, curation_status, authors_raw,
    authors_id, keywords_id, references_id, cited_by_id, provenance.

    Args:
        ws: Workspace resuelto.
        ident: Valor a buscar; se prueba contra id, doi y source_id en ese
            orden.

    Returns:
        Dict con todos los campos de la fila del corpus.

    Raises:
        DataError: Si ``ident`` no coincide con ningún paper.
        StoreError: Si el store no existe o está bloqueado.
    """
    store = _open_readonly(ws.library_path)
    corpus = store.load()
    table = corpus.to_arrow()

    rows = table.to_pylist()

    # Prioridad: id > doi > source_id (ADR 0036)
    matching_by_id = [r for r in rows if str(r.get(Col.ID)) == ident]
    if matching_by_id:
        matching = matching_by_id
    else:
        matching_by_doi = [
            r
            for r in rows
            if r.get(Col.DOI) is not None and str(r.get(Col.DOI)) == ident
        ]
        if matching_by_doi:
            matching = matching_by_doi
        else:
            matching = [
                r
                for r in rows
                if r.get(Col.SOURCE_ID) is not None
                and str(r.get(Col.SOURCE_ID)) == ident
            ]

    if not matching:
        raise DataError(
            f"Paper '{ident}' no encontrado en el corpus. "
            "Verificá el id con 'b2g read list' o 'b2g status'."
        )

    row = matching[0]

    # Parsear provenance
    provenance_raw = row.get(Col.PROVENANCE)
    provenance: list[Any] = []
    if provenance_raw:
        try:
            provenance = json.loads(str(provenance_raw))
        except (json.JSONDecodeError, TypeError):
            provenance = [str(provenance_raw)]

    return {
        "id": row.get(Col.ID),
        "source_id": row.get(Col.SOURCE_ID),
        "doi": row.get(Col.DOI),
        "title": row.get(Col.TITLE),
        "year": row.get(Col.YEAR),
        "abstract": row.get(Col.ABSTRACT),
        "is_seed": row.get(Col.IS_SEED),
        "curation_status": row.get(Col.CURATION_STATUS),
        "authors_raw": row.get(Col.AUTHORS_RAW),
        "authors_id": row.get(Col.AUTHORS_ID),
        "keywords_id": row.get(Col.KEYWORDS_ID),
        "references_id": row.get(Col.REFERENCES_ID),
        "cited_by_id": row.get(Col.CITED_BY_ID),
        "provenance": provenance,
    }


# ---------------------------------------------------------------------------
# 4. get_scent
# ---------------------------------------------------------------------------


def get_scent(ws: Workspace, paper_id: str) -> dict[str, Any]:
    """Devuelve el score de acoplamiento real de un paper con el corpus.

    El scent se calcula usando el índice de acoplamiento bibliográfico:
    cuántos otros papers del corpus comparten referencias con el paper dado
    (``coupling``), más las resoluciones de sus ``references_id`` y
    ``cited_by_id`` contra los ids presentes en el corpus.

    No usa los 4 paneles cosméticos del mock. Expone los vecinos
    reales: ``coupling`` (papers del corpus con referencias compartidas),
    ``references`` (references_id del paper resueltas al corpus),
    ``cited_by`` (cited_by_id del paper resueltos al corpus).

    Args:
        ws: Workspace resuelto.
        paper_id: Valor de ``Col.ID`` del paper.

    Returns:
        Dict con: ``paper_id``, ``score`` (int, nº de referencias compartidas
        con otros papers del corpus), ``coupling`` (list[{paper_id, title,
        weight}]), ``references`` (list[{paper_id, title}]),
        ``cited_by`` (list[{paper_id, title}]).

    Raises:
        DataError: Si el ``paper_id`` no existe en el corpus.
        StoreError: Si el store no existe o está bloqueado.
    """
    from bib2graph.networks.projectors import collect_item_to_papers

    store = _open_readonly(ws.library_path)
    corpus = store.load()
    table = corpus.to_arrow()
    rows = table.to_pylist()

    # Verificar que el paper exista
    matching = [r for r in rows if str(r.get(Col.ID)) == paper_id]
    if not matching:
        raise DataError(
            f"Paper '{paper_id}' no encontrado en el corpus. "
            "Verificá el id con 'b2g inspect'."
        )

    paper_row = matching[0]

    # Índice inverso: referencia → [papers del corpus que la citan]
    ref_to_papers = collect_item_to_papers(rows, Col.ID, Col.REFERENCES_ID)

    # Índice título por id para resolución legible
    id_to_title: dict[str, str | None] = {
        str(r.get(Col.ID)): str(r.get(Col.TITLE)) if r.get(Col.TITLE) else None
        for r in rows
        if r.get(Col.ID)
    }

    # Coupling: papers del corpus que comparten al menos una referencia con paper_id.
    # Construimos un mapa {paper_id_vecino → peso (refs compartidas)}.
    paper_refs: list[str] = list(paper_row.get(Col.REFERENCES_ID) or [])
    coupling_weights: dict[str, int] = {}
    for ref in paper_refs:
        if ref is None:
            continue
        for citing_paper in ref_to_papers.get(str(ref), []):
            if str(citing_paper) != paper_id:
                coupling_weights[str(citing_paper)] = (
                    coupling_weights.get(str(citing_paper), 0) + 1
                )

    coupling = [
        {
            "paper_id": pid,
            "title": id_to_title.get(pid),
            "weight": w,
        }
        for pid, w in sorted(coupling_weights.items(), key=lambda kv: (-kv[1], kv[0]))
    ]

    # Score = nº de corpus-papers con los que comparte al menos 1 referencia
    score = len(coupling_weights)

    # References resueltas: references_id del paper que están en el corpus
    corpus_ids: set[str] = set(id_to_title.keys())
    references = [
        {"paper_id": ref_id, "title": id_to_title.get(ref_id)}
        for ref_id in paper_refs
        if ref_id is not None and str(ref_id) in corpus_ids
    ]

    # Cited_by resueltos: cited_by_id del paper que están en el corpus
    paper_cited_by: list[str] = list(paper_row.get(Col.CITED_BY_ID) or [])
    cited_by = [
        {"paper_id": cid, "title": id_to_title.get(cid)}
        for cid in paper_cited_by
        if cid is not None and str(cid) in corpus_ids
    ]

    return {
        "paper_id": paper_id,
        "score": score,
        "coupling": coupling,
        "references": references,
        "cited_by": cited_by,
    }


# ---------------------------------------------------------------------------
# 5. get_network
# ---------------------------------------------------------------------------

_VALID_KINDS: frozenset[str] = frozenset(
    {
        NetworkKind.BIBLIOGRAPHIC_COUPLING,
        NetworkKind.COCITATION,
        NetworkKind.AUTHOR_COLLAB,
        NetworkKind.INSTITUTION_COLLAB,
        NetworkKind.KEYWORD_COOCCURRENCE,
    }
)


def get_network(ws: Workspace, kind: str) -> dict[str, Any]:
    """Devuelve la red de la ronda viva para el kind dado.

    Recomputa con ``Networks.build`` + ``decorate`` (función pura: mismo corpus
    → misma red, Louvain seeded por ``corpus_hash``, R2).  No lee la cache de
    ``<workspace>/networks/<kind>/`` todavía (optimización diferida a G3).

    ``kind`` debe ser uno de los ``NetworkKind`` del núcleo:
    ``bibliographic_coupling``, ``cocitation``, ``author_collab``,
    ``institution_collab``, ``keyword_cooccurrence``.

    Args:
        ws: Workspace resuelto.
        kind: Tipo de red (``NetworkKind`` como string).

    Returns:
        Dict con:
        ``nodes`` (list[{id, label, degree_centrality, ?community, ?year,
        ?is_seed, ?curation_status}]),
        ``edges`` (list[{source, target, weight}]),
        ``metrics`` ({n_nodes, n_edges, density, num_components,
        avg_clustering, n_communities}).

    Raises:
        DataError: Si ``kind`` es inválido o no hay red para la ronda viva.
        StoreError: Si el store no existe o está bloqueado.
    """
    from bib2graph.networks.analyzer import network_metrics
    from bib2graph.networks.facade import Networks
    from bib2graph.networks.spec import NetworkSpec

    if kind not in _VALID_KINDS:
        valid = ", ".join(sorted(_VALID_KINDS))
        raise DataError(
            f"NetworkKind '{kind}' no reconocido. Valores válidos: {valid}."
        )

    store = _open_readonly(ws.library_path)
    corpus = store.load()

    try:
        nk = NetworkKind(kind)
        spec = NetworkSpec(kind=nk)
        artifact = Networks.build(corpus, spec)
    except Exception as exc:
        raise DataError(
            f"No se pudo construir la red '{kind}': {exc}. "
            "Verificá que el corpus tenga datos suficientes para esta proyección."
        ) from exc

    graph = artifact.graph

    # Nodos con atributos
    nodes = []
    for node in graph.nodes():
        attrs = graph.nodes[node]
        node_dict: dict[str, Any] = {
            "id": str(node),
            "label": attrs.get("label", str(node)),
            "degree_centrality": attrs.get("degree_centrality", 0.0),
        }
        # Atributos opcionales de paper (solo para redes de paper)
        for optional_attr in ("community", "year", "is_seed", "curation_status"):
            if optional_attr in attrs:
                node_dict[optional_attr] = attrs[optional_attr]
        nodes.append(node_dict)

    # Aristas
    edges = [
        {"source": str(u), "target": str(v), "weight": data.get("weight", 1)}
        for u, v, data in graph.edges(data=True)
    ]

    # Métricas
    base_metrics = network_metrics(graph)

    # Número de comunidades distintas
    n_communities: int = 0
    if artifact.communities:
        n_communities = len(set(artifact.communities.values()))

    metrics: dict[str, Any] = {
        "n_nodes": graph.number_of_nodes(),
        "n_edges": graph.number_of_edges(),
        "density": base_metrics.get("density", 0.0),
        "num_components": base_metrics.get("num_components", 0),
        "avg_clustering": base_metrics.get("avg_clustering", 0.0),
        "n_communities": n_communities,
    }

    return {
        "nodes": nodes,
        "edges": edges,
        "metrics": metrics,
    }


# ---------------------------------------------------------------------------
# 6. compare_rounds
# ---------------------------------------------------------------------------


def compare_rounds(ws: Workspace, round_a: str, round_b: str) -> dict[str, Any]:
    """Compara dos snapshots sellados y devuelve el diff de papers y métricas.

    Carga los parquets de los snapshots ``round_a`` y ``round_b`` en modo
    read-only y diferea por ``Col.ID``. Para la entrada especial ``"live"``
    usa el corpus vivo del store.

    Args:
        ws: Workspace resuelto.
        round_a: ID del primer snapshot (nombre del directorio en ``snapshots/``
            o ``"live"`` para el corpus vivo).
        round_b: ID del segundo snapshot.

    Returns:
        Dict con: ``round_a``, ``round_b``, ``added_paper_ids`` (ids en b no en
        a), ``removed_paper_ids`` (ids en a no en b), ``mutated_hubs`` (lista
        vacía, diferido), ``metrics_change`` ([{metric, before, after}]).

    Raises:
        DataError: Si alguno de los snapshots no existe o no tiene parquet.
        StoreError: Si el store no existe o está bloqueado.
    """
    import pyarrow.parquet as pq

    from bib2graph.schemas import CORPUS_SCHEMA

    def _load_ids_and_metrics(
        snapshot_id: str,
    ) -> tuple[set[str], int]:
        """Carga los ids y total_papers de un snapshot o del corpus vivo."""
        if snapshot_id == "live":
            store = _open_readonly(ws.library_path)
            corpus = store.load()
            table = corpus.to_arrow()
            ids = {str(row.get(Col.ID)) for row in table.to_pylist() if row.get(Col.ID)}
            return ids, len(ids)

        snap_dir = ws.snapshots_dir / snapshot_id
        parquet_path = snap_dir / "corpus.parquet"

        if not snap_dir.exists():
            raise DataError(
                f"Snapshot '{snapshot_id}' no encontrado en '{ws.snapshots_dir}'. "
                "Verificá los snapshots disponibles con 'list_rounds'."
            )
        if not parquet_path.exists():
            raise DataError(
                f"Snapshot '{snapshot_id}' no tiene corpus.parquet. "
                "El snapshot puede estar incompleto."
            )

        try:
            table = pq.read_table(  # type: ignore[no-untyped-call]
                parquet_path, schema=CORPUS_SCHEMA
            )
        except Exception as exc:
            raise DataError(
                f"No se pudo leer el parquet del snapshot '{snapshot_id}': {exc}."
            ) from exc

        ids = {str(row.get(Col.ID)) for row in table.to_pylist() if row.get(Col.ID)}
        return ids, len(ids)

    ids_a, total_a = _load_ids_and_metrics(round_a)
    ids_b, total_b = _load_ids_and_metrics(round_b)

    added = sorted(ids_b - ids_a)
    removed = sorted(ids_a - ids_b)

    metrics_change: list[dict[str, Any]] = [
        {
            "metric": "n_papers",
            "before": total_a,
            "after": total_b,
        }
    ]

    # Métricas de redes por kind si ambos snapshots tienen metrics.json
    # (solo para snapshots reales, no para "live")
    def _read_network_metrics(snapshot_id: str, kind: str) -> dict[str, Any] | None:
        # DIFERIDO (B-G2-3): hoy los snapshots NO materializan redes por kind
        # (corpus.snapshot() solo escribe corpus.parquet + manifest.json), así
        # que este path nunca existe todavía y el diff de métricas-por-red queda
        # inactivo (devuelve None). Se activará si/cuando se construyan redes por
        # snapshot. El diff de papers (added/removed) NO depende de esto.
        if snapshot_id == "live":
            return None
        metrics_path = (
            ws.snapshots_dir / snapshot_id / "networks" / kind / "metrics.json"
        )
        if not metrics_path.exists():
            return None
        try:
            loaded: dict[str, Any] = json.loads(
                metrics_path.read_text(encoding="utf-8")
            )
            return loaded
        except (json.JSONDecodeError, OSError):
            return None

    if round_a != "live" and round_b != "live":
        for nk in sorted(_VALID_KINDS):
            m_a = _read_network_metrics(round_a, nk)
            m_b = _read_network_metrics(round_b, nk)
            if m_a is None or m_b is None:
                continue
            for metric_key in ("n_communities", "density"):
                before = m_a.get(metric_key)
                after = m_b.get(metric_key)
                if before is not None and after is not None:
                    metrics_change.append(
                        {
                            "metric": f"{metric_key}:{nk}",
                            "before": before,
                            "after": after,
                        }
                    )

    return {
        "round_a": round_a,
        "round_b": round_b,
        "added_paper_ids": added,
        "removed_paper_ids": removed,
        "mutated_hubs": [],  # diferido: requiere redes construidas por snapshot
        "metrics_change": metrics_change,
    }


# ---------------------------------------------------------------------------
# 7. list_papers  (sub-issue #156 — grupo read)
# ---------------------------------------------------------------------------


def list_papers(
    ws: Workspace,
    *,
    query: str | None = None,
    status: str | None = None,
    is_seed: bool | None = None,
    year: int | None = None,
) -> dict[str, Any]:
    """Lista papers del corpus con filtros opcionales.

    Devuelve un payload mínimo por paper (id, title, year, curation_status,
    is_seed) más el conteo total.  Diseñado para listar en el CLI/SPA sin
    cargar campos pesados (abstract, referencias, autores).

    Filtros combinables (todos opcionales, se aplican con AND lógico):
    - ``query``: substring case-insensitive sobre el título.
    - ``status``: valor exacto de ``curation_status``
      (``"candidate"``, ``"accepted"``, ``"rejected"``).
    - ``is_seed``: ``True`` → solo semillas; ``False`` → solo no-semillas.
    - ``year``: año exacto de publicación.

    Args:
        ws: Workspace resuelto.
        query: Texto a buscar en el título (substring, case-insensitive).
        status: Valor exacto de ``curation_status``.
        is_seed: Filtro por campo is_seed.
        year: Año exacto de publicación.

    Returns:
        Dict con ``papers`` (lista de dicts mínimos) y ``count`` (int).

    Raises:
        StoreError: Si el store no existe o está bloqueado.
    """
    store = _open_readonly(ws.library_path)
    corpus = store.load()
    table = corpus.to_arrow()
    rows = table.to_pylist()

    result: list[dict[str, Any]] = []
    for row in rows:
        # Filtro por query: substring CI sobre el título
        if query is not None:
            title_val = str(row.get(Col.TITLE) or "")
            if query.lower() not in title_val.lower():
                continue

        # Filtro por status (curation_status exacto)
        if status is not None and str(row.get(Col.CURATION_STATUS)) != status:
            continue

        # Filtro por is_seed
        if is_seed is not None and bool(row.get(Col.IS_SEED)) != is_seed:
            continue

        # Filtro por año exacto
        if year is not None:
            row_year = row.get(Col.YEAR)
            if row_year is None or int(row_year) != year:
                continue

        result.append(
            {
                "id": row.get(Col.ID),
                "title": row.get(Col.TITLE),
                "year": row.get(Col.YEAR),
                "curation_status": row.get(Col.CURATION_STATUS),
                "is_seed": row.get(Col.IS_SEED),
            }
        )

    return {"papers": result, "count": len(result)}


# ---------------------------------------------------------------------------
# 8. corpus_stats  (sub-issue #156 — grupo read)
# ---------------------------------------------------------------------------

_VALID_GROUP_BY: frozenset[str] = frozenset({"status", "year", "is_seed"})

# Mapeo de alias CLI → nombre de columna SQL
_GROUP_BY_COL: dict[str, str] = {
    "status": Col.CURATION_STATUS.value,
    "year": Col.YEAR.value,
    "is_seed": Col.IS_SEED.value,
}


def corpus_stats(
    ws: Workspace,
    *,
    group_by: str = "status",
) -> dict[str, Any]:
    """Estadísticas del corpus agrupadas por ``status``, ``year`` o ``is_seed``.

    Para ``group_by="status"`` reutiliza la consulta GROUP BY de
    ``get_workspace`` (``counts_by_status``); para ``year`` e ``is_seed``
    aplica la misma estrategia sobre la columna correspondiente.

    Args:
        ws: Workspace resuelto.
        group_by: Dimensión de agrupación.  Valores válidos:
            ``"status"`` (default), ``"year"``, ``"is_seed"``.

    Returns:
        Dict con:
        - ``group_by``: dimensión usada.
        - ``total``: total de papers en el corpus.
        - ``groups``: lista de ``{key, count}`` ordenada por clave.

    Raises:
        DataError: Si ``group_by`` no es un valor válido.
        StoreError: Si el store no existe o está bloqueado.
    """
    if group_by not in _VALID_GROUP_BY:
        valid = ", ".join(sorted(_VALID_GROUP_BY))
        raise DataError(f"group_by '{group_by}' no válido. Valores admitidos: {valid}.")

    store = _open_readonly(ws.library_path)
    col = _GROUP_BY_COL[group_by]

    counts_table = store.backend.query(
        f"SELECT {col}, COUNT(*) AS cnt FROM corpus GROUP BY 1 ORDER BY 1"
    )

    groups: list[dict[str, Any]] = []
    total = 0
    if len(counts_table) > 0:
        for row in counts_table.to_pylist():
            key = row.get(col)
            cnt = int(row["cnt"])
            groups.append({"key": key, "count": cnt})
            total += cnt

    return {
        "group_by": group_by,
        "total": total,
        "groups": groups,
    }


# ---------------------------------------------------------------------------
# 9. get_top  (sub-issue #157 — read top)
# ---------------------------------------------------------------------------


def get_top(
    ws: Workspace,
    *,
    n: int = 10,
    kind: str = "bibliographic_coupling",
) -> dict[str, Any]:
    """Devuelve los nodos más centrales de la red ``kind`` y los pares de co-citación.

    El bloque "central" se extrae de la red del ``kind`` solicitado, ordenando
    los nodos por ``degree_centrality`` descendente y tomando los primeros ``n``.
    El bloque "cocitation" es **siempre** la red ``cocitation`` (top N pares
    por peso descendente), independientemente del ``kind`` elegido.

    La función es idempotente y no requiere ``build`` previo: recomputa las
    redes en tiempo de lectura (mismo camino que ``get_network``).

    Para redes de paper (``bibliographic_coupling``, ``cocitation``), los ids
    de nodo son ids del corpus y se resuelven al título completo.  Para otras
    redes (``author_collab``, ``institution_collab``, ``keyword_cooccurrence``),
    los ids son ids de entidad y se usa el ``label`` decorado como título.

    Red vacía → honest-empty (exit 0 + bloque vacío + ``reason``/``fix_command``),
    NO ``DataError``.

    Args:
        ws: Workspace resuelto.
        n: Número de nodos/pares a devolver (default 10). Debe ser > 0.
        kind: Tipo de red para el bloque central. Uno de los 5 ``NetworkKind``
            (default ``bibliographic_coupling``).

    Returns:
        Dict con:

        - ``kind``: tipo de red usado para el bloque central.
        - ``top``: ``n`` pedido.
        - ``central``: lista de hasta ``n`` nodos ``{id, title,
          degree_centrality, ?community}`` ordenados por
          ``degree_centrality`` descendente.
        - ``cocitation``: lista de hasta ``n`` pares ``{source,
          source_title, target, target_title, weight}`` ordenados
          por ``weight`` descendente.
        - ``reason`` / ``fix_command``: presentes solo cuando
          ``cocitation`` está vacío (honest-empty; NOT un error).

    Raises:
        DataError: Si ``kind`` no es un ``NetworkKind`` válido, si
            ``n <= 0``, o si la construcción de alguna red falla
            (error genuino, no vaciedad).
        StoreError: Si el store no existe o está bloqueado.
    """
    if kind not in _VALID_KINDS:
        valid = ", ".join(sorted(_VALID_KINDS))
        raise DataError(
            f"NetworkKind '{kind}' no reconocido. Valores válidos: {valid}."
        )
    if n <= 0:
        raise DataError(f"top N debe ser un entero positivo; se recibió {n}.")

    # Cargar corpus una vez para el índice id→título y para predict_build_preview
    store = _open_readonly(ws.library_path)
    corpus = store.load()
    table = corpus.to_arrow()
    id_to_title: dict[str, str | None] = {
        str(r.get(Col.ID)): (str(r.get(Col.TITLE)) if r.get(Col.TITLE) else None)
        for r in table.to_pylist()
        if r.get(Col.ID)
    }

    # -------------------------------------------------------------------
    # Bloque "central": top N nodos por degree_centrality en --kind
    # -------------------------------------------------------------------
    central_net = get_network(ws, kind)
    sorted_nodes = sorted(
        central_net["nodes"],
        key=lambda node: node["degree_centrality"],
        reverse=True,
    )[:n]

    central: list[dict[str, Any]] = []
    for node in sorted_nodes:
        node_id = node["id"]
        # Redes de paper → id es un Col.ID → resolvible al título del corpus.
        # Otras redes → id es un id de entidad → usar label decorado.
        title = id_to_title.get(node_id) or node.get("label")
        entry: dict[str, Any] = {
            "id": node_id,
            "title": title,
            "degree_centrality": node["degree_centrality"],
        }
        if "community" in node:
            entry["community"] = node["community"]
        central.append(entry)

    # -------------------------------------------------------------------
    # Bloque "cocitation": top N pares por peso (SIEMPRE red cocitation)
    # -------------------------------------------------------------------
    coc_net = (
        central_net
        if kind == NetworkKind.COCITATION
        else get_network(ws, NetworkKind.COCITATION)
    )

    sorted_edges = sorted(
        coc_net["edges"],
        key=lambda e: e["weight"],
        reverse=True,
    )[:n]

    cocitation: list[dict[str, Any]] = []
    for edge in sorted_edges:
        src_id = str(edge["source"])
        tgt_id = str(edge["target"])
        cocitation.append(
            {
                "source": src_id,
                "source_title": id_to_title.get(src_id),
                "target": tgt_id,
                "target_title": id_to_title.get(tgt_id),
                "weight": edge["weight"],
            }
        )

    result: dict[str, Any] = {
        "kind": kind,
        "top": n,
        "central": central,
        "cocitation": cocitation,
    }

    # Honest-empty: si co-citación vacía, agregar reason/fix_command.
    # Igual que "build" con red vacía → exit 0, NO DataError.
    if not coc_net["edges"]:
        from bib2graph.networks.facade import predict_build_preview

        preview = predict_build_preview(corpus)
        coc_entry = next(
            (p for p in preview if p["kind"] == str(NetworkKind.COCITATION)),
            None,
        )
        if coc_entry is not None:
            result["reason"] = coc_entry["reason"]
            result["fix_command"] = coc_entry["fix_command"]

    return result
