"""projectors — Projector (Protocol) y las 5 implementaciones del Hito 2.

Funciones puras: ``pa.Table → nx.Graph``. Sin I/O, sin red, sin estado global.
Ver API.md §7 y las decisiones D1-D2.

Decisión D1 (peso): conteo crudo de ítems compartidos.
Decisión D2 (tipo de nodo):
  - co-autoría / instituciones / co-word → entidad como nodo.
  - acoplamiento / co-citación → paper (``id``) como nodo.
"""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from typing import TYPE_CHECKING, Any, Literal, Protocol

import networkx as nx
import pyarrow as pa

from bib2graph.constants import Col

if TYPE_CHECKING:
    # nx.Graph es genérico solo en los stubs de types-networkx, no en runtime.
    _Graph = nx.Graph[Any, Any, Any]
else:
    _Graph = nx.Graph

MIN_WEIGHT_DEFAULT: int = 1


class Projector(Protocol):
    """Protocolo de proyector: transforma una tabla Arrow en un grafo NetworkX.

    Args:
        table: Tabla Arrow con el schema canónico del Corpus.
        min_weight: Filtra aristas con ``weight < min_weight`` (D1). Default 1.
        scope: ``'full'`` opera sobre toda la tabla; ``'seeds_only'`` filtra a
            ``is_seed == True`` antes de proyectar.

    Returns:
        Grafo NetworkX no dirigido con atributo ``weight`` en cada arista.
    """

    def project(
        self,
        table: pa.Table,
        *,
        min_weight: int = MIN_WEIGHT_DEFAULT,
        scope: Literal["full", "seeds_only"] = "full",
    ) -> _Graph: ...


def _filter_scope(table: pa.Table, scope: Literal["full", "seeds_only"]) -> pa.Table:
    """Filtra la tabla según el scope solicitado.

    Args:
        table: Tabla Arrow canónica.
        scope: ``'full'`` = sin filtro; ``'seeds_only'`` = solo filas con
            ``is_seed == True``.

    Returns:
        Tabla (posiblemente filtrada).
    """
    if scope == "seeds_only":
        mask = table.column(Col.IS_SEED)
        return table.filter(mask)
    return table


def _build_cooccurrence_graph(
    rows: list[dict[str, object]],
    id_col: str,
    entity_col: str,
    *,
    min_weight: int,
) -> _Graph:
    """Construye un grafo de co-ocurrencia genérico.

    Para cada par de entidades que aparecen juntas en algún paper, el peso
    de la arista es el número de papers donde co-ocurren (D1).

    Args:
        rows: Lista de filas de la tabla como dicts.
        id_col: Columna con el id del paper (no se usa para nodos; solo para
            iterar).
        entity_col: Columna con la lista de entidades por paper.
        min_weight: Umbral mínimo de peso de arista.

    Returns:
        Grafo no dirigido con atributo ``weight``.
    """
    pair_count: dict[tuple[str, str], int] = defaultdict(int)

    for row in rows:
        entities = row.get(entity_col)
        if not entities or not isinstance(entities, list):
            continue
        # Ordenar para garantizar par canónico (determinismo, sin depender de sets)
        unique_entities = sorted(set(str(e) for e in entities if e is not None))
        for a, b in combinations(unique_entities, 2):
            pair_count[(a, b)] += 1

    g: _Graph = nx.Graph()
    for (a, b), weight in sorted(pair_count.items()):
        if weight >= min_weight:
            g.add_edge(a, b, weight=weight)

    return g


def collect_item_to_papers(
    rows: list[dict[str, object]],
    id_col: str,
    list_col: str,
) -> dict[str, list[str]]:
    """Construye el índice inverso ``{item → [paper_ids que lo contienen]}``.

    Primitivo compartido por los proyectores y por el cómputo del *information
    scent* bibliométrico (``foraging.scent``).  Separa la fase de indexación de
    la fase de construcción del grafo para que el forrajeo pueda reusar la
    lógica sin construir un ``nx.Graph`` completo.

    Args:
        rows: Filas de la tabla como dicts.
        id_col: Columna con el id del paper.
        list_col: Columna con la lista de ítems (referencias, citantes, etc.).

    Returns:
        Dict ``{item_str: [paper_id_str, ...]}`` sin deduplicar (los papers se
        pueden repetir si el mismo paper aparece varias veces en ``rows``).
    """
    item_to_papers: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        paper_id = str(row.get(id_col) or "")
        items = row.get(list_col)
        if not items or not isinstance(items, list):
            continue
        for item in items:
            if item is not None:
                item_to_papers[str(item)].append(paper_id)
    return dict(item_to_papers)


def _build_shared_refs_graph(
    rows: list[dict[str, object]],
    id_col: str,
    list_col: str,
    *,
    min_weight: int,
) -> _Graph:
    """Construye un grafo de acoplamiento por referencias compartidas.

    Nodo = paper (``id``). Peso = nº de ítems de lista compartidos (D1, D2).

    Algoritmo eficiente: para cada ítem de lista, registra todos los papers
    que lo contienen; luego cuenta pares.

    Args:
        rows: Filas de la tabla.
        id_col: Columna con el id del paper.
        list_col: Columna con la lista de ítems (refs, citantes).
        min_weight: Umbral mínimo de peso de arista.

    Returns:
        Grafo no dirigido con atributo ``weight``.
    """
    item_to_papers = collect_item_to_papers(rows, id_col, list_col)

    pair_count: dict[tuple[str, str], int] = defaultdict(int)
    for papers in item_to_papers.values():
        sorted_papers = sorted(set(papers))
        for a, b in combinations(sorted_papers, 2):
            pair_count[(a, b)] += 1

    g: _Graph = nx.Graph()
    for (a, b), weight in sorted(pair_count.items()):
        if weight >= min_weight:
            g.add_edge(a, b, weight=weight)

    return g


class BibliographicCouplingProjector:
    """Acoplamiento bibliográfico: dos papers están acoplados si comparten referencias.

    Nodo = paper (``id``). Peso = nº de referencias compartidas (D1, D2).
    Scope por defecto: ``'full'`` (corpus completo; ciudadano de primera, crítica #2).
    No requiere Enricher: las refs ya vienen en ``references_id`` (OpenAlex).
    """

    def project(
        self,
        table: pa.Table,
        *,
        min_weight: int = MIN_WEIGHT_DEFAULT,
        scope: Literal["full", "seeds_only"] = "full",
    ) -> _Graph:
        """Proyecta el acoplamiento bibliográfico sobre la tabla.

        Args:
            table: Tabla Arrow canónica del Corpus.
            min_weight: Umbral mínimo de peso (default 1 = sin filtro).
            scope: Alcance de la proyección.

        Returns:
            Grafo de acoplamiento con ``weight`` en cada arista.
        """
        filtered = _filter_scope(table, scope)
        rows = filtered.to_pylist()
        return _build_shared_refs_graph(
            rows, Col.ID, Col.REFERENCES_ID, min_weight=min_weight
        )


class AuthorCollaborationProjector:
    """Co-autoría: dos autores están conectados si co-firman un paper.

    Nodo = autor (``authors_id``). Peso = nº de papers co-firmados (D1, D2).
    Scope por defecto: ``'full'``.
    """

    def project(
        self,
        table: pa.Table,
        *,
        min_weight: int = MIN_WEIGHT_DEFAULT,
        scope: Literal["full", "seeds_only"] = "full",
    ) -> _Graph:
        """Proyecta la red de co-autoría sobre la tabla.

        Args:
            table: Tabla Arrow canónica del Corpus.
            min_weight: Umbral mínimo de peso (default 1 = sin filtro).
            scope: Alcance de la proyección.

        Returns:
            Grafo de co-autoría con ``weight`` en cada arista.
        """
        filtered = _filter_scope(table, scope)
        rows = filtered.to_pylist()
        return _build_cooccurrence_graph(
            rows, Col.ID, Col.AUTHORS_ID, min_weight=min_weight
        )


class InstitutionCollaborationProjector:
    """Co-autoría institucional: dos instituciones están conectadas si co-aparecen en un paper.

    Nodo = institución (``institutions_id``). Peso = nº de papers con co-aparición (D1, D2).
    Scope por defecto: ``'full'``.
    """

    def project(
        self,
        table: pa.Table,
        *,
        min_weight: int = MIN_WEIGHT_DEFAULT,
        scope: Literal["full", "seeds_only"] = "full",
    ) -> _Graph:
        """Proyecta la red de colaboración institucional sobre la tabla.

        Args:
            table: Tabla Arrow canónica del Corpus.
            min_weight: Umbral mínimo de peso (default 1 = sin filtro).
            scope: Alcance de la proyección.

        Returns:
            Grafo de colaboración institucional con ``weight`` en cada arista.
        """
        filtered = _filter_scope(table, scope)
        rows = filtered.to_pylist()
        return _build_cooccurrence_graph(
            rows, Col.ID, Col.INSTITUTIONS_ID, min_weight=min_weight
        )


class KeywordCoOccurrenceProjector:
    """Co-ocurrencia de keywords: dos keywords co-ocurren si aparecen en el mismo paper.

    Nodo = keyword (``keywords_id``). Peso = nº de papers donde co-ocurren (D1, D2).
    Scope por defecto: ``'full'``.
    """

    def project(
        self,
        table: pa.Table,
        *,
        min_weight: int = MIN_WEIGHT_DEFAULT,
        scope: Literal["full", "seeds_only"] = "full",
    ) -> _Graph:
        """Proyecta la red de co-ocurrencia de keywords sobre la tabla.

        Args:
            table: Tabla Arrow canónica del Corpus.
            min_weight: Umbral mínimo de peso (default 1 = sin filtro).
            scope: Alcance de la proyección.

        Returns:
            Grafo de co-ocurrencia de keywords con ``weight`` en cada arista.
        """
        filtered = _filter_scope(table, scope)
        rows = filtered.to_pylist()
        return _build_cooccurrence_graph(
            rows, Col.ID, Col.KEYWORDS_ID, min_weight=min_weight
        )


class CoCitationProjector:
    """Co-citación: dos papers son co-citados si un tercero los cita a ambos.

    Nodo = paper (``id``). Peso = nº de papers que citan a ambos (D1, D2).
    Scope por defecto: ``'seeds_only'`` (la más cara; requiere 2º nivel de fetch).

    Nota: la co-citación COMPLETA requiere el ``OpenAlexEnricher`` (Hito 8) para
    traer el 2º nivel de citantes. En Hito 2 se proyecta desde ``cited_by_id``
    de los papers disponibles en el corpus. El resultado es válido para el subset
    de citantes ya presentes en la tabla.
    """

    def project(
        self,
        table: pa.Table,
        *,
        min_weight: int = MIN_WEIGHT_DEFAULT,
        scope: Literal["full", "seeds_only"] = "seeds_only",
    ) -> _Graph:
        """Proyecta la red de co-citación desde ``cited_by_id``.

        Dos papers P1 y P2 están co-citados si comparten al menos un citante
        en ``cited_by_id``. El peso es el nº de citantes compartidos (D1).

        Para la co-citación completa, el corpus debe haber pasado por el
        ``OpenAlexEnricher`` (Hito 8). Sin enriquecimiento, solo se usan
        los citantes ya presentes en la tabla.

        Args:
            table: Tabla Arrow canónica del Corpus.
            min_weight: Umbral mínimo de peso (default 1 = sin filtro).
            scope: Alcance de la proyección. Default ``'seeds_only'``.

        Returns:
            Grafo de co-citación con ``weight`` en cada arista.
        """
        filtered = _filter_scope(table, scope)
        rows = filtered.to_pylist()
        return _build_shared_refs_graph(
            rows, Col.ID, Col.CITED_BY_ID, min_weight=min_weight
        )
