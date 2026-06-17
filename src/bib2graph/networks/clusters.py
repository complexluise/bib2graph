"""clusters — tabla de comunidades para redes de paper.

Función pura ``cluster_table`` que cruza nodos de una red bibliométrica
(bibliographic_coupling / cocitation) con el corpus para producir una fila
de resumen por comunidad: tamaño, conteos por estado de curación, rango de
años, top autores y top keywords.

Aplica SOLO a redes de paper (nodos = Col.ID canónico).
Para redes de autor/keyword/institución las comunidades agrupan entidades
distintas a papers; en V1 no tiene sentido la misma tabla — la función devuelve
``[]`` con un aviso en el docstring (no crash).

Lección B6 (Nota 09): cruzar por ``Col.ID`` (id canónico, ej. ``oa:abab…``),
NUNCA por ``Col.OPENALEX_ID`` (``W…``). Un nodo del grafo ES un ``Col.ID``.
"""

from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import TYPE_CHECKING, Any

import pyarrow as pa

from bib2graph.constants import Col, CurationStatus, NetworkKind

if TYPE_CHECKING:
    from bib2graph.networks.spec import NetworkArtifact

# Kinds cuyo nodo es un paper id (Col.ID) — misma fuente que _PAPER_KINDS en decorate.py
_PAPER_KINDS: frozenset[str] = frozenset(
    {NetworkKind.BIBLIOGRAPHIC_COUPLING, NetworkKind.COCITATION}
)

# Cuántos autores/keywords mostrar en top_authors / top_keywords
_TOP_N: int = 5


def cluster_table(
    table: pa.Table,
    artifact: NetworkArtifact,
) -> list[dict[str, Any]]:
    """Construye una tabla de resumen de comunidades para redes de paper.

    Para cada comunidad detectada en ``artifact.communities`` agrega una fila con:
      - ``cluster``: id de comunidad (int).
      - ``size``: número de nodos en la comunidad.
      - ``seed_count``: nodos con ``is_seed=True``.
      - ``candidate_count``: nodos con ``curation_status='candidate'``.
      - ``accepted_count``: nodos con ``curation_status='accepted'``.
      - ``year_min``, ``year_max``, ``year_mean``: rango y media de año.
        ``year_mean`` es ``None`` si ningún nodo tiene año.
      - ``top_authors``: lista con hasta 5 autores más frecuentes (authors_raw).
      - ``top_keywords``: lista con hasta 5 keywords más frecuentes (keywords_id).

    El cruce nodo→fila se hace por ``Col.ID`` (id canónico), NO por
    ``Col.OPENALEX_ID``. Esta es la lección crítica de la Nota 09 B6:
    el nodo del grafo ES un ``Col.ID``; usar ``openalex_id`` daría 0 cruces.

    Comportamiento en casos límite:
      - ``artifact.communities`` es ``None`` → devuelve ``[]``.
      - ``artifact.spec.kind`` no es de paper → devuelve ``[]`` (no crash).
      - Nodo sin match en el corpus → ese nodo no aporta datos de año/autores/
        keywords pero SÍ suma al ``size``.
      - Cluster con 0 años → ``year_min=None``, ``year_max=None``, ``year_mean=None``.

    El orden de filas es determinista: clusters ordenados por ``cluster`` id.

    Args:
        table: Tabla Arrow canónica del Corpus (fuente de metadatos).
        artifact: ``NetworkArtifact`` con ``graph``, ``communities`` y ``spec``.

    Returns:
        Lista de dicts ordenada por ``cluster``. Vacía si no aplica.
    """
    # Sólo aplica a redes de paper
    if artifact.spec.kind not in _PAPER_KINDS:
        return []

    # Sin comunidades → sin tabla
    if artifact.communities is None:
        return []

    communities: dict[Any, int] = artifact.communities

    # --- Construir índice Col.ID → metadatos ---
    # Lección B6: index por Col.ID, no por Col.OPENALEX_ID
    paper_index = _build_paper_index(table)

    # --- Agrupar nodos por comunidad ---
    by_cluster: dict[int, list[Any]] = {}
    for node, comm_id in communities.items():
        cid = int(comm_id)
        if cid not in by_cluster:
            by_cluster[cid] = []
        by_cluster[cid].append(node)

    # --- Construir fila de resumen por cluster ---
    rows: list[dict[str, Any]] = []
    for comm_id in sorted(by_cluster):
        nodes = by_cluster[comm_id]
        size = len(nodes)

        seed_count = 0
        candidate_count = 0
        accepted_count = 0
        years: list[int] = []
        author_counter: Counter[str] = Counter()
        keyword_counter: Counter[str] = Counter()

        for node in nodes:
            key = str(node)
            info = paper_index.get(key)
            if info is None:
                # Nodo sin match en el corpus: suma al size, no aporta datos
                continue

            if info.get("is_seed"):
                seed_count += 1
            status = info.get("curation_status")
            if status == CurationStatus.CANDIDATE:
                candidate_count += 1
            elif status == CurationStatus.ACCEPTED:
                accepted_count += 1

            year = info.get("year")
            if isinstance(year, int):
                years.append(year)

            for author in info.get("authors_raw") or []:
                if author:
                    author_counter[str(author)] += 1

            for kw in info.get("keywords_id") or []:
                if kw:
                    keyword_counter[str(kw)] += 1

        year_min: int | None = min(years) if years else None
        year_max: int | None = max(years) if years else None
        year_mean: float | None = round(mean(years), 1) if years else None

        # Desempate explícito: orden primario por frecuencia descendente,
        # secundario alfabético ascendente. Garantiza reproducibilidad
        # independiente del método de clustering (louvain/label_prop/greedy)
        # y de PYTHONHASHSEED (ADR 0017, DoD de reproducibilidad).
        top_authors = [
            a
            for a, _ in sorted(author_counter.items(), key=lambda x: (-x[1], x[0]))[
                :_TOP_N
            ]
        ]
        top_keywords = [
            k
            for k, _ in sorted(keyword_counter.items(), key=lambda x: (-x[1], x[0]))[
                :_TOP_N
            ]
        ]

        rows.append(
            {
                "cluster": comm_id,
                "size": size,
                "seed_count": seed_count,
                "candidate_count": candidate_count,
                "accepted_count": accepted_count,
                "year_min": year_min,
                "year_max": year_max,
                "year_mean": year_mean,
                "top_authors": top_authors,
                "top_keywords": top_keywords,
            }
        )

    return rows


def _build_paper_index(table: pa.Table) -> dict[str, dict[str, Any]]:
    """Construye índice ``{Col.ID → metadatos}`` para cruce con nodos del grafo.

    Incluye: year, is_seed, curation_status, authors_raw, keywords_id.

    Args:
        table: Tabla Arrow canónica del Corpus.

    Returns:
        Dict keyed por ``str(Col.ID)``; excluye filas con id ``None``.
    """
    ids = table.column(Col.ID).to_pylist()
    years = table.column(Col.YEAR).to_pylist()
    is_seeds = table.column(Col.IS_SEED).to_pylist()
    statuses = table.column(Col.CURATION_STATUS).to_pylist()
    authors_raw_col = table.column(Col.AUTHORS_RAW).to_pylist()
    keywords_id_col = table.column(Col.KEYWORDS_ID).to_pylist()

    index: dict[str, dict[str, Any]] = {}
    for pid, year, is_seed, status, authors_raw, keywords_id in zip(
        ids,
        years,
        is_seeds,
        statuses,
        authors_raw_col,
        keywords_id_col,
        strict=False,
    ):
        if pid is None:
            continue
        key = str(pid)
        index[key] = {
            "year": int(year) if year is not None else None,
            "is_seed": bool(is_seed) if is_seed is not None else False,
            "curation_status": str(status) if status is not None else None,
            "authors_raw": authors_raw if isinstance(authors_raw, list) else [],
            "keywords_id": keywords_id if isinstance(keywords_id, list) else [],
        }
    return index
