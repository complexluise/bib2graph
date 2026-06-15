"""analyzer — funciones puras de análisis de redes bibliométricas.

Implementa las funciones prescritas por API.md §8:
  - ``network_metrics``: densidad, componentes, clustering.
  - ``centrality``: grado e intermediación por nodo.
  - ``detect_communities``: Louvain / label_prop / greedy_modularity.
  - ``assortativity``: por atributo categórico y/o grado, con disclaimer de proxy.
  - ``community_composition``: % de cada categoría por comunidad.
  - ``cocitation_quality_report``: informe de calidad con umbrales configurables.
  - ``QualityThresholds``: umbrales configurables (D6).

Todas son funciones puras: sin I/O, sin red, sin estado global.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import networkx as nx
from pydantic import BaseModel

if TYPE_CHECKING:
    from bib2graph.corpus import Corpus

    # nx.Graph es genérico solo en los stubs de types-networkx, no en runtime.
    _Graph = nx.Graph[Any, Any, Any]
else:
    _Graph = nx.Graph


# ---------------------------------------------------------------------------
# QualityThresholds (D6)
# ---------------------------------------------------------------------------


class QualityThresholds(BaseModel):
    """Umbrales configurables para el informe de calidad de co-citación.

    Los defaults sensatos son los de metodología §4. Se pueden sobreescribir
    para adaptar a otros campos de investigación (crítica #5).

    Attributes:
        min_volume: Número mínimo de papers en el corpus.
        min_doi_refs_pct: Fracción mínima de papers con DOI.
        min_countries: Número mínimo de países distintos (vía institutions_id).
        min_recurrent_authors: Nº mínimo de autores que aparecen en ≥2 papers.
    """

    min_volume: int = 200
    min_doi_refs_pct: float = 0.90
    min_countries: int = 5
    min_recurrent_authors: int = 10


# ---------------------------------------------------------------------------
# network_metrics
# ---------------------------------------------------------------------------


def network_metrics(g: _Graph) -> dict[str, object]:
    """Densidad, nº de componentes y clustering promedio del grafo.

    Args:
        g: Grafo NetworkX (no dirigido).

    Returns:
        Dict con claves ``'density'``, ``'num_components'``, ``'avg_clustering'``.
    """
    avg_clust = nx.average_clustering(g) if g.number_of_nodes() > 0 else 0.0
    return {
        "density": nx.density(g),
        "num_components": nx.number_connected_components(g),
        "avg_clustering": avg_clust,
    }


# ---------------------------------------------------------------------------
# centrality
# ---------------------------------------------------------------------------


def centrality(g: _Graph) -> dict[str, dict[Any, float]]:
    """Centralidad de grado e intermediación por nodo.

    Args:
        g: Grafo NetworkX (no dirigido).

    Returns:
        Dict con claves ``'degree'`` y ``'betweenness'``, cada una mapeando
        nodo → valor de centralidad.
    """
    return {
        "degree": nx.degree_centrality(g),
        "betweenness": nx.betweenness_centrality(g),
    }


# ---------------------------------------------------------------------------
# detect_communities
# ---------------------------------------------------------------------------


def detect_communities(g: _Graph, method: str = "louvain") -> dict[Any, int]:
    """Detecta comunidades en el grafo con el método indicado.

    Args:
        g: Grafo NetworkX (no dirigido).
        method: Algoritmo de detección. Uno de ``'louvain'``,
            ``'label_prop'``, ``'greedy_modularity'``.

    Returns:
        Dict nodo → id de comunidad (int).

    Raises:
        ImportError: Si se solicita ``'louvain'`` y ``python-louvain`` no está
            instalado. Falla explícito con el nombre del paquete a instalar
            (lección 7 de v0; AGENTS.md §manejo de errores).
        ValueError: Si ``method`` no es reconocido.
    """
    if method == "louvain":
        try:
            import community as community_louvain  # type: ignore[import-untyped]
        except (ImportError, TypeError):
            raise ImportError(
                "detect_communities(method='louvain') requiere el paquete "
                "'python-louvain'. Instalalo con: uv add python-louvain"
            ) from None
        partition: dict[Any, int] = community_louvain.best_partition(g)
        return partition

    elif method == "label_prop":
        communities_iter: list[Any] = list(
            nx.community.label_propagation_communities(g)
        )
        return {
            node: idx
            for idx, community_set in enumerate(sorted(communities_iter, key=sorted))
            for node in community_set
        }

    elif method == "greedy_modularity":
        gm_communities: Any = nx.community.greedy_modularity_communities(g)
        return {
            node: idx
            for idx, community_set in enumerate(gm_communities)
            for node in community_set
        }

    else:
        raise ValueError(
            f"Método de comunidades no reconocido: '{method}'. "
            "Use 'louvain', 'label_prop' o 'greedy_modularity'."
        )


# ---------------------------------------------------------------------------
# assortativity
# ---------------------------------------------------------------------------


def assortativity(
    g: _Graph,
    *,
    attribute: str | None = None,
    by_degree: bool = True,
    proxy: str | None = None,
) -> dict[str, object]:
    """Asortatividad por atributo categórico configurable y/o por grado.

    El atributo y sus categorías son config del usuario (no se hardcodea
    ningún campo como 'region'; crítica #5 del sandbox IED).

    Cuando se pasa ``proxy``, el resultado incluye ``'proxy_disclaimer'``
    advirtiendo que el atributo es un proxy, no el campo real (D4).

    Args:
        g: Grafo NetworkX (no dirigido).
        attribute: Nombre del atributo de nodo para asortatividad categórica.
            Si es None, no se calcula la asortatividad por atributo.
        by_degree: Si True, calcula asortatividad por grado.
        proxy: Si se pasa un string, indica que ``attribute`` es un proxy del
            campo real (p. ej. ``'affiliation_per_paper'``). Se añade un
            disclaimer al resultado.

    Returns:
        Dict con ``'attribute_assortativity'`` (si ``attribute`` fue dado),
        ``'degree_assortativity'`` (si ``by_degree=True``), y
        ``'proxy_disclaimer'`` (si ``proxy`` fue dado).
    """
    result: dict[str, object] = {}

    if attribute is not None:
        r = nx.attribute_assortativity_coefficient(g, attribute)
        result["attribute_assortativity"] = float(r)

    if by_degree:
        r_deg = nx.degree_assortativity_coefficient(g)
        result["degree_assortativity"] = float(r_deg)

    if proxy is not None:
        result["proxy_disclaimer"] = (
            f"El atributo '{attribute}' es un proxy derivado de '{proxy}'. "
            "No es el campo real de afiliación; interpretarlo con cautela."
        )

    return result


# ---------------------------------------------------------------------------
# community_composition
# ---------------------------------------------------------------------------


def community_composition(
    g: _Graph,
    communities: dict[Any, int],
    attribute: str,
) -> dict[int, dict[str, float]]:
    """Composición porcentual de cada comunidad por atributo categórico.

    Args:
        g: Grafo NetworkX con atributos de nodo.
        communities: Dict nodo → id de comunidad (salida de ``detect_communities``).
        attribute: Nombre del atributo de nodo a usar.

    Returns:
        Dict comunidad → Dict categoría → fracción (0.0 a 1.0). La suma de
        fracciones por comunidad es 1.0 si todos los nodos tienen el atributo.
    """
    # Agrupar nodos por comunidad → lista de valores del atributo
    community_values: dict[int, list[str]] = {}
    for node, comm_id in communities.items():
        val = g.nodes[node].get(attribute)
        if val is None:
            continue
        if comm_id not in community_values:
            community_values[comm_id] = []
        community_values[comm_id].append(str(val))

    # Recoger todas las categorías presentes
    all_categories: set[str] = set()
    for vals in community_values.values():
        all_categories.update(vals)
    sorted_categories = sorted(all_categories)  # orden determinista

    result: dict[int, dict[str, float]] = {}
    for comm_id in sorted(community_values):  # orden determinista
        vals = community_values[comm_id]
        total = len(vals)
        composition: dict[str, float] = {}
        for cat in sorted_categories:
            composition[cat] = vals.count(cat) / total if total > 0 else 0.0
        result[comm_id] = composition

    return result


# ---------------------------------------------------------------------------
# cocitation_quality_report
# ---------------------------------------------------------------------------


def cocitation_quality_report(
    corpus: Corpus,
    g: _Graph,
    *,
    thresholds: QualityThresholds | None = None,
) -> dict[str, object]:
    """Informe de calidad de la red de co-citación según metodología §4.

    Evalúa 4 criterios configurables y devuelve un dict estructurado (D6):
    ``{criterio: {valor, umbral, pasa}}`` + ``"overall_pass": bool``.
    Sin score ponderado.

    Args:
        corpus: Corpus a evaluar.
        g: Grafo de co-citación (actualmente no se usa en los criterios; se
            pasa por contrato para extensibilidad futura).
        thresholds: Umbrales configurables. Si None, usa ``QualityThresholds()``
            con los defaults de metodología §4.

    Returns:
        Dict con claves por criterio y ``"overall_pass": bool``.
    """
    if thresholds is None:
        thresholds = QualityThresholds()

    table = corpus.to_arrow()
    rows = table.to_pylist()
    total = len(rows)

    # Criterio 1: volumen documental
    vol_pasa = total >= thresholds.min_volume

    # Criterio 2: fracción con DOI
    con_doi = sum(1 for r in rows if r.get("doi"))
    doi_pct = con_doi / total if total > 0 else 0.0
    doi_pasa = doi_pct >= thresholds.min_doi_refs_pct

    # Criterio 3: diversidad geográfica (countries vía institutions_id)
    # Se usa el prefijo de cada id de institución como proxy de país
    # (ej. "ROR:AR..." → AR). En la práctica, institutions_id son ROR ids.
    # Para el report usamos el conjunto de valores únicos en institutions_id
    # que sean distintos entre sí (la diversidad real requiere un lookup externo;
    # aquí contamos cuántos ids distintos hay, bajo el supuesto de que cada inst
    # pertenece a un país diferente — el caller puede refinar asignando un
    # atributo de country a los nodos antes de llamar a esta función).
    #
    # Decisión de implementación: contamos cuántos valores de institutions_id
    # únicos hay en el corpus. Sin metadata extra no podemos mapear a países.
    # El contrato (D6) dice "diversidad geográfica" con umbral min_countries.
    # Implementamos como: nº de institutions_id únicos presentes ≥ min_countries.
    # Para tests, el caller puede usar institution ids con prefijo de país.
    unique_insts: set[str] = set()
    for r in rows:
        insts = r.get("institutions_id")
        if isinstance(insts, list):
            for inst in insts:
                if inst is not None:
                    unique_insts.add(str(inst))
    geo_pasa = len(unique_insts) >= thresholds.min_countries

    # Criterio 4: autores recurrentes (aparecen en ≥2 papers)
    author_count: dict[str, int] = {}
    for r in rows:
        authors = r.get("authors_id")
        if isinstance(authors, list):
            for a in authors:
                if a is not None:
                    author_count[str(a)] = author_count.get(str(a), 0) + 1
    recurrent = sum(1 for c in author_count.values() if c >= 2)
    recurrent_pasa = recurrent >= thresholds.min_recurrent_authors

    report: dict[str, object] = {
        "min_volume": {
            "valor": total,
            "umbral": thresholds.min_volume,
            "pasa": vol_pasa,
        },
        "min_doi_refs_pct": {
            "valor": round(doi_pct, 4),
            "umbral": thresholds.min_doi_refs_pct,
            "pasa": doi_pasa,
        },
        "min_countries": {
            "valor": len(unique_insts),
            "umbral": thresholds.min_countries,
            "pasa": geo_pasa,
            "proxy": (
                "institutions_id como proxy de países "
                "(sin lookup ROR→país; refinar en Hito 8)"
            ),
        },
        "min_recurrent_authors": {
            "valor": recurrent,
            "umbral": thresholds.min_recurrent_authors,
            "pasa": recurrent_pasa,
        },
        "overall_pass": vol_pasa and doi_pasa and geo_pasa and recurrent_pasa,
    }

    return report
