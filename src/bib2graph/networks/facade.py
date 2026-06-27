"""facade — Networks: API de alto nivel para construir redes bibliométricas.

Expone ``Networks.build`` (spec) y ``Networks.quick`` (baja fricción).
Ver API.md §10.

Ambos métodos son estáticos y puros: mismo corpus + mismo spec → mismo
``NetworkArtifact``. Sin I/O, sin red, sin estado global (AGENTS.md).

R2 (ADR 0017 enmendado): ``_louvain_seed_from_hash`` deriva un ``random_state``
determinista del ``corpus_hash`` de **contenido** (excluye provenance), de modo
que "mismo corpus + mismo spec → mismas comunidades" entre corridas.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import networkx as nx
import pyarrow as pa

from bib2graph.constants import Col, NetworkKind
from bib2graph.networks.analyzer import (
    assortativity,
    community_composition,
    detect_communities,
    network_metrics,
)
from bib2graph.networks.decorate import decorate
from bib2graph.networks.projectors import (
    AuthorCollaborationProjector,
    BibliographicCouplingProjector,
    CoCitationProjector,
    InstitutionCollaborationProjector,
    KeywordCoOccurrenceProjector,
    Projector,
)
from bib2graph.networks.spec import NetworkArtifact, NetworkSpec

if TYPE_CHECKING:
    from bib2graph.corpus import Corpus

    # nx.Graph es genérico solo en los stubs de types-networkx, no en runtime.
    _Graph = nx.Graph[Any, Any, Any]
else:
    _Graph = nx.Graph

logger = logging.getLogger(__name__)

# Tipos de red base en Networks.quick (sin co-citación; esta se añade condicionalmente)
# Derivado de NetworkKind — fuente única (R1, ADR 0023)
_QUICK_KINDS: list[str] = [
    NetworkKind.BIBLIOGRAPHIC_COUPLING,
    NetworkKind.AUTHOR_COLLAB,
    NetworkKind.INSTITUTION_COLLAB,
    NetworkKind.KEYWORD_COOCCURRENCE,
]


def _has_cited_by_data(corpus: Corpus) -> bool:
    """Devuelve ``True`` si algún paper del corpus tiene ``cited_by_id`` no vacío.

    Se usa para decidir si incluir la red de co-citación en ``Networks.quick``
    (Hito 8b): si la columna está vacía en todo el corpus, la co-citación
    produciría 0 nodos/aristas y se omite silenciosamente.

    Args:
        corpus: Corpus a inspeccionar.

    Returns:
        ``True`` si al menos un paper tiene ``cited_by_id`` con ≥1 elemento.
    """
    table = corpus.to_arrow()
    col = table.column("cited_by_id")
    return any(val for val in col.to_pylist())


def _louvain_seed_from_hash(corpus_hash: str) -> int:
    """Deriva un ``random_state`` determinista del ``corpus_hash`` de contenido.

    R2 (ADR 0017 enmendado): siembra Louvain con un entero derivado del
    content-hash (no del hash que incluía provenance).  Esto garantiza
    "mismo corpus + mismo spec → mismas comunidades" entre corridas.

    Algoritmo: toma los primeros 8 caracteres hex del hash (32 bits),
    los convierte a int y los acota a [0, 2^31 - 1] (rango positivo de
    numpy int32 que acepta ``python-louvain``).

    Args:
        corpus_hash: Hexdigest SHA-256 del contenido bibliográfico.

    Returns:
        Entero en [0, 2^31 - 1] derivado del hash.
    """
    return int(corpus_hash[:8], 16) % (2**31)


def _projector_for_kind(spec: NetworkSpec) -> Projector:
    """Devuelve la instancia del proyector correspondiente al ``spec.kind``.

    R5: compara con ``NetworkKind`` (fuente única, ADR 0023) en vez de
    string-literals.

    Args:
        spec: Especificación de la red.

    Returns:
        Instancia del proyector (cumple el protocolo ``Projector``).

    Raises:
        ValueError: Si el kind no es reconocido.
    """
    kind = spec.kind
    if kind == NetworkKind.BIBLIOGRAPHIC_COUPLING:
        return BibliographicCouplingProjector()
    elif kind == NetworkKind.AUTHOR_COLLAB:
        return AuthorCollaborationProjector()
    elif kind == NetworkKind.INSTITUTION_COLLAB:
        return InstitutionCollaborationProjector()
    elif kind == NetworkKind.KEYWORD_COOCCURRENCE:
        return KeywordCoOccurrenceProjector()
    elif kind == NetworkKind.COCITATION:
        return CoCitationProjector()
    else:
        raise ValueError(f"Kind de red no reconocido: '{kind}'")


def _apply_keyword_filter(table: pa.Table, terms: list[str]) -> pa.Table:
    """Filtra la tabla a filas cuyo ``keywords_raw`` matchee algún término.

    Semántica ANY + substring case-insensitive: un paper entra si CUALQUIER
    término del filtro matchea como substring (case-insensitive) contra
    CUALQUIERA de sus keywords en ``keywords_raw``.

    Implementación puramente Python/pyarrow: sin I/O, sin estado global,
    determinista (cumple la regla de pureza del núcleo, AGENTS.md).

    Args:
        table: Tabla Arrow canónica del Corpus.
        terms: Lista de términos a buscar (no vacía; el llamador garantiza esto).

    Returns:
        Tabla Arrow filtrada (puede estar vacía si ningún paper matchea).
    """
    terms_lower = [t.lower() for t in terms]
    keywords_col = table.column("keywords_raw").to_pylist()

    mask: list[bool] = []
    for kws in keywords_col:
        if not kws:  # None o lista vacía → no matchea
            mask.append(False)
            continue
        # ANY: un término matchea cualquier keyword del paper
        matched = any(
            term in kw.lower() for kw in kws if kw is not None for term in terms_lower
        )
        mask.append(matched)

    bool_array = pa.array(mask, type=pa.bool_())
    return table.filter(bool_array)


def _inject_scalar_attribute(
    g: _Graph,
    table: pa.Table,
    attribute: str,
) -> bool:
    """Inyecta un atributo escalar del corpus como atributo de nodo en el grafo.

    Útil para atributos como ``language`` o ``research_areas`` que no son
    inyectados por ``decorate`` pero sí existen en la tabla Arrow.

    Solo actúa en grafos cuyo nodo es un paper id (``Col.ID``): busca cada nodo
    del grafo en la columna ``id`` de la tabla y extrae el valor escalar.
    Para atributos de lista (p.ej. ``research_areas``), extrae el primer elemento.

    Args:
        g: Grafo NetworkX (modificado in-place).
        table: Tabla Arrow canónica del Corpus.
        attribute: Nombre del atributo/columna a inyectar.

    Returns:
        ``True`` si el atributo existía en la tabla y se inyectó en al menos
        un nodo; ``False`` si la columna no existe en la tabla.
    """
    from bib2graph.constants import Col

    if attribute not in table.schema.names:
        return False

    # Construir índice rápido: paper_id → valor del atributo
    ids = table.column(Col.ID).to_pylist()
    values = table.column(attribute).to_pylist()

    attr_index: dict[str, object] = {}
    for pid, val in zip(ids, values, strict=False):
        if pid is None:
            continue
        # Para atributos de lista, extraer el primero (p.ej. research_areas)
        if isinstance(val, list):
            val = val[0] if val else None
        attr_index[str(pid)] = val

    injected = False
    for node in g.nodes():
        key = str(node)
        if key in attr_index and attr_index[key] is not None:
            g.nodes[node][attribute] = attr_index[key]
            injected = True

    return injected


def _build_artifact(corpus: Corpus, spec: NetworkSpec) -> NetworkArtifact:
    """Construye un ``NetworkArtifact`` a partir de un corpus y una spec.

    Proyecta, calcula métricas y detecta comunidades (si spec.clustering está
    configurado).

    R2: Louvain se siembra con un ``random_state`` derivado del
    ``corpus_hash`` de contenido (excluyendo provenance) para reproducibilidad.

    Si ``spec.keyword_filter`` es una lista no vacía, la tabla Arrow del corpus
    se subsettea antes de proyectar: solo entran los papers cuyas
    ``keywords_raw`` matcheen (ANY, substring, case-insensitive) algún término
    del filtro. Proyección y decoración operan sobre el subcorpus, garantizando
    consistencia entre nodos, aristas y labels.

    Args:
        corpus: Corpus de origen.
        spec: Especificación de la red.

    Returns:
        ``NetworkArtifact`` con grafo, métricas, comunidades y spec.
    """
    projector = _projector_for_kind(spec)
    table = corpus.to_arrow()

    if spec.keyword_filter:
        table = _apply_keyword_filter(table, spec.keyword_filter)

    g: _Graph = projector.project(
        table,
        min_weight=spec.min_weight,
        scope=spec.scope,
    )

    metrics = network_metrics(g)

    communities: dict[Any, int] | None = None
    if spec.clustering is not None and g.number_of_nodes() > 0:
        # R5: el ``except Exception`` que enmascaraba fallos reales fue eliminado.
        # Solo se captura ``ImportError`` (dependencia faltante → fallar fuerte,
        # lección 7, AGENTS.md).  Cualquier otro error se propaga limpio.
        # ``ValueError`` (método desconocido) y errores de graph también se propagan.
        try:
            # R2: derivar random_state del content-hash para Louvain reproducible
            random_state: int | None = None
            if spec.clustering == "louvain":
                corpus_hash = corpus._backend.corpus_hash()
                random_state = _louvain_seed_from_hash(corpus_hash)
            communities = detect_communities(
                g,
                method=spec.clustering,
                random_state=random_state,
                resolution=spec.resolution,
            )
        except ImportError:
            raise  # dep faltante: fallar fuerte (lección 7, AGENTS.md)

    artifact = NetworkArtifact(
        graph=g,
        metrics=metrics,
        communities=communities,
        assortativity=None,
        layout=None,
        spec=spec,
    )

    # Decorar el grafo con labels legibles y atributos de nodo (issue #25).
    # Se hace aquí, en la frontera de construcción, para que todos los
    # exportadores (GraphML, CSV) y el CLI reciban artefactos ya decorados
    # sin necesitar conocer el corpus.
    decorate(artifact, table)

    # D3 — asortatividad/composición: solo cuando spec.assortativity_attribute
    # está configurado y el grafo tiene nodos.
    if spec.assortativity_attribute is not None and g.number_of_nodes() > 0:
        attr = spec.assortativity_attribute

        # Verificar si el atributo ya está en los nodos (p.ej. inyectado por
        # decorate para 'curation_status', 'is_seed', etc.). Si no, intentar
        # inyectarlo desde la tabla Arrow (p.ej. 'language', 'research_areas').
        attr_in_nodes = any(
            attr in g.nodes[n] for n in g.nodes() if g.nodes[n].get(attr) is not None
        )
        if not attr_in_nodes:
            attr_in_nodes = _inject_scalar_attribute(g, table, attr)

        if not attr_in_nodes:
            # El atributo no existe en el grafo ni en la tabla del corpus.
            # Warning accionable: no crashear (D3 — manejo de atributo inexistente).
            logger.warning(
                "assortativity_attribute='%s' no existe en los nodos del grafo "
                "ni como columna en el corpus. Verificá el nombre del atributo. "
                "Asortatividad no calculada para la red '%s'.",
                attr,
                spec.kind,
            )
        else:
            assort_result = assortativity(g, attribute=attr, by_degree=True)

            # Si hay comunidades, agregar composición por comunidad.
            if communities is not None:
                assort_result["community_composition"] = community_composition(
                    g, communities, attr
                )

            artifact.assortativity = assort_result

    return artifact


# ---------------------------------------------------------------------------
# Helpers de predicados para predict_build_preview (misma lógica que los
# proyectores — fuente única preview ↔ build, ADR 0037 §(e))
# ---------------------------------------------------------------------------


def _count_rows_with_col(
    rows: list[dict[str, object]],
    col: str,
    *,
    seeds_only: bool = False,
) -> int:
    """Cuenta filas donde la columna lista tiene al menos 1 elemento no-None.

    Usado SOLO para texto de reason ("N/M papers con col"), no para el
    predicado de vaciedad.  Ver ``_has_shared_item`` y
    ``_has_paper_with_multi_distinct`` para los predicados correctos.

    Args:
        rows: Filas del corpus como dicts (salida de ``table.to_pylist()``).
        col: Nombre de la columna de tipo lista.
        seeds_only: Si ``True``, solo cuenta filas donde ``is_seed == True``.

    Returns:
        Número de filas con al menos 1 elemento no-None en la columna dada.
    """
    count = 0
    for row in rows:
        if seeds_only and not row.get(Col.IS_SEED):
            continue
        val = row.get(col)
        if isinstance(val, list) and any(e is not None for e in val):
            count += 1
    return count


def _has_shared_item(
    rows: list[dict[str, object]],
    col: str,
    *,
    seeds_only: bool = False,
) -> bool:
    """True sii algún item en ``col`` aparece en ≥2 papers distintos.

    Espeja ``collect_item_to_papers`` + ``_build_shared_refs_graph``
    (projectors.py): una arista entre P1 y P2 existe sii comparten algún
    ítem.  El mínimo para ≥1 arista es que algún ítem sea compartido por ≥2
    papers distintos.

    Necesario y suficiente para grafos de tipo shared-refs: dos papers con
    referencias disjuntas producen 0 aristas, aunque cada uno tenga muchas
    referencias (caso trampa de la Nota 20).

    Args:
        rows: Filas del corpus como dicts (salida de ``table.to_pylist()``).
        col: Columna de tipo lista (``references_id``, ``cited_by_id``).
        seeds_only: Si ``True``, solo considera filas ``is_seed == True``
            (para co-citación con scope ``seeds_only``).

    Returns:
        ``True`` si algún ítem aparece en ≥2 papers distintos.
    """
    # item → conjunto de paper_ids que lo contienen (dedup por paper)
    item_papers: dict[str, set[str]] = {}
    for row in rows:
        if seeds_only and not row.get(Col.IS_SEED):
            continue
        val = row.get(col)
        if not isinstance(val, list):
            continue
        paper_id = str(row.get(Col.ID) or "")
        for item in val:
            if item is not None:
                key = str(item)
                if key not in item_papers:
                    item_papers[key] = set()
                item_papers[key].add(paper_id)
    return any(len(papers) >= 2 for papers in item_papers.values())


def _has_paper_with_multi_distinct(
    rows: list[dict[str, object]],
    col: str,
) -> bool:
    """True sii algún paper tiene ≥2 entidades DISTINTAS no-None en ``col``.

    Espeja exactamente ``_build_cooccurrence_graph`` (projectors.py): el
    criterio es ``sorted(set(str(e) for e in entities if e is not None))``,
    luego ``combinations(unique_entities, 2)`` → ≥1 par sii ≥2 distintas.

    Corrige el bug de la Nota 20 P1: ``[A1, A1]`` (autor duplicado) tiene
    2 elementos pero tras dedup solo 1 distinto → la red sale vacía aunque
    ``len(val) >= 2``.  Esta función usa ``set`` para el dedup, igual que el
    proyector.

    Args:
        rows: Filas del corpus como dicts (salida de ``table.to_pylist()``).
        col: Columna de tipo lista (``authors_id``, ``institutions_id``,
            ``keywords_id``).

    Returns:
        ``True`` si algún paper tiene ≥2 entidades distintas no-None.
    """
    for row in rows:
        val = row.get(col)
        if not isinstance(val, list):
            continue
        distinct = {str(e) for e in val if e is not None}
        if len(distinct) >= 2:
            return True
    return False


def predict_build_preview(corpus: Corpus) -> list[dict[str, object]]:
    """Predice vacío/no-vacío para cada red posible sin proyectarlas.

    Fuente única con ``Networks.quick``: reusa los mismos predicados de columna
    que los proyectores para decidir la inclusión de papers.  El conteo es
    barato (no proyecta ningún grafo).

    Incluye siempre las 5 redes posibles (incluida co-citación incluso si
    ``cited_by_id`` está vacío), para que el diagnóstico sea completo:
    el agente/humano ve qué falta para activar cada tipo de red ANTES del
    ``build`` (ADR 0037 §(e), cura de la trampa de la Nota 20).

    Args:
        corpus: Corpus a inspeccionar.

    Returns:
        Lista de dicts, uno por tipo de red, con:

        - ``kind``: tipo de red (string de ``NetworkKind``).
        - ``would_be_empty``: ``True`` si la red saldría vacía.
        - ``reason``: causa determinista si saldría vacía, ``None`` si no.
        - ``fix_command``: comando exacto para arreglarlo, ``None`` si no vacía.
    """
    table = corpus.to_arrow()
    rows: list[dict[str, object]] = table.to_pylist()
    total = len(rows)
    total_seeds = sum(1 for r in rows if r.get(Col.IS_SEED))

    preview: list[dict[str, object]] = []

    # --- bibliographic_coupling: references_id, scope=full ---
    # No-vacía sii algún references_id aparece en ≥2 papers distintos.
    # (dos papers con refs disjuntas producen 0 aristas → caso trampa Nota 20)
    n_refs_any = _count_rows_with_col(rows, Col.REFERENCES_ID)
    bc_empty = not _has_shared_item(rows, Col.REFERENCES_ID)
    if bc_empty:
        if n_refs_any == 0:
            bc_reason: str | None = f"0/{total} papers con {Col.REFERENCES_ID}"
        else:
            bc_reason = (
                f"{n_refs_any}/{total} papers con {Col.REFERENCES_ID} "
                f"pero ninguna referencia aparece en ≥2 papers"
            )
    else:
        bc_reason = None
    preview.append(
        {
            "kind": str(NetworkKind.BIBLIOGRAPHIC_COUPLING),
            "would_be_empty": bc_empty,
            "reason": bc_reason,
            # TODO(0037 1B): reapuntar fix_command al consolidar verbos
            "fix_command": "b2g seed --resolve" if bc_empty else None,
        }
    )

    # --- author_collab: authors_id, scope=full ---
    # No-vacía sii algún paper tiene ≥2 autores DISTINTOS no-None.
    # ([A1, A1] → tras dedup 1 único → 0 aristas, aunque len=2)
    n_authors_any = _count_rows_with_col(rows, Col.AUTHORS_ID)
    ac_empty = not _has_paper_with_multi_distinct(rows, Col.AUTHORS_ID)
    if ac_empty:
        if n_authors_any == 0:
            ac_reason: str | None = f"0/{total} papers con {Col.AUTHORS_ID}"
        else:
            ac_reason = (
                f"{n_authors_any}/{total} papers con {Col.AUTHORS_ID} "
                f"pero ninguno con ≥2 autores distintos"
            )
    else:
        ac_reason = None
    preview.append(
        {
            "kind": str(NetworkKind.AUTHOR_COLLAB),
            "would_be_empty": ac_empty,
            "reason": ac_reason,
            # TODO(0037 1B): reapuntar fix_command al consolidar verbos
            "fix_command": "b2g seed --resolve" if ac_empty else None,
        }
    )

    # --- institution_collab: institutions_id, scope=full ---
    # No-vacía sii algún paper tiene ≥2 instituciones DISTINTAS no-None.
    n_inst_any = _count_rows_with_col(rows, Col.INSTITUTIONS_ID)
    ic_empty = not _has_paper_with_multi_distinct(rows, Col.INSTITUTIONS_ID)
    if ic_empty:
        if n_inst_any == 0:
            ic_reason: str | None = f"0/{total} papers con {Col.INSTITUTIONS_ID}"
        else:
            ic_reason = (
                f"{n_inst_any}/{total} papers con {Col.INSTITUTIONS_ID} "
                f"pero ninguno con ≥2 instituciones distintas"
            )
    else:
        ic_reason = None
    preview.append(
        {
            "kind": str(NetworkKind.INSTITUTION_COLLAB),
            "would_be_empty": ic_empty,
            "reason": ic_reason,
            # TODO(0037 1B): reapuntar fix_command al consolidar verbos
            "fix_command": "b2g seed --resolve" if ic_empty else None,
        }
    )

    # --- keyword_cooccurrence: keywords_id, scope=full ---
    # No-vacía sii algún paper tiene ≥2 keywords DISTINTAS no-None.
    # Fix preferencial: si hay keywords_raw pero no keywords_id, thesaurus puede
    # generar keywords_id sin red; si no hay keywords_raw, se necesita seed --resolve.
    n_kw_any = _count_rows_with_col(rows, Col.KEYWORDS_ID)
    n_kw_raw = _count_rows_with_col(rows, Col.KEYWORDS_RAW)
    kw_empty = not _has_paper_with_multi_distinct(rows, Col.KEYWORDS_ID)
    if kw_empty:
        if n_kw_any == 0:
            kw_reason: str | None = f"0/{total} papers con {Col.KEYWORDS_ID}"
        else:
            kw_reason = (
                f"{n_kw_any}/{total} papers con {Col.KEYWORDS_ID} "
                f"pero ninguno con ≥2 keywords distintas"
            )
        # Si hay keywords_raw pero no keywords_id, el thesaurus puede generarlos
        # TODO(0037 1B): reapuntar fix_command al consolidar verbos
        kw_fix: str | None = (
            "b2g thesaurus" if n_kw_raw > 0 and n_kw_any == 0 else "b2g seed --resolve"
        )
    else:
        kw_reason = None
        kw_fix = None
    preview.append(
        {
            "kind": str(NetworkKind.KEYWORD_COOCCURRENCE),
            "would_be_empty": kw_empty,
            "reason": kw_reason,
            "fix_command": kw_fix,
        }
    )

    # --- cocitation: cited_by_id, scope=seeds_only ---
    # No-vacía sii algún cited_by_id aparece en ≥2 seeds distintas.
    # (dos seeds con citantes disjuntos producen 0 aristas)
    n_cited_any = _count_rows_with_col(rows, Col.CITED_BY_ID, seeds_only=True)
    coc_empty = not _has_shared_item(rows, Col.CITED_BY_ID, seeds_only=True)
    if coc_empty:
        if n_cited_any == 0:
            coc_reason: str | None = (
                f"{n_cited_any}/{total_seeds} seeds con {Col.CITED_BY_ID}"
            )
        else:
            coc_reason = (
                f"{n_cited_any}/{total_seeds} seeds con {Col.CITED_BY_ID} "
                f"pero ningún citante aparece en ≥2 seeds"
            )
    else:
        coc_reason = None
    preview.append(
        {
            "kind": str(NetworkKind.COCITATION),
            "would_be_empty": coc_empty,
            "reason": coc_reason,
            # TODO(0037 1B): reapuntar fix_command al consolidar verbos
            "fix_command": "b2g enrich" if coc_empty else None,
        }
    )

    return preview


class Networks:
    """API de alto nivel para construir redes bibliométricas desde un Corpus.

    Todos los métodos son estáticos y puros (mismo input → mismo output).
    """

    @staticmethod
    def build(corpus: Corpus, spec: NetworkSpec) -> NetworkArtifact:
        """Construye una red bibliométrica según la especificación dada.

        Args:
            corpus: Corpus de origen.
            spec: Especificación declarativa de la red.

        Returns:
            ``NetworkArtifact`` con grafo, métricas y comunidades.
        """
        return _build_artifact(corpus, spec)

    @staticmethod
    def quick(corpus: Corpus, *, min_weight: int = 1) -> list[NetworkArtifact]:
        """Construye las redes principales con configuración razonable.

        Arma specs para: acoplamiento bibliográfico (full), co-autoría,
        colaboración institucional y co-ocurrencia de keywords.

        **Co-citación (Hito 8b):** se incluye si el corpus tiene ``cited_by_id``
        poblado en al menos un paper (es decir, si pasó por el
        ``OpenAlexEnricher`` con la pasada 2).  Si ``cited_by_id`` está vacío
        en todo el corpus, la co-citación se omite sin error (avisa por log).

        Args:
            corpus: Corpus de origen.
            min_weight: Peso mínimo de arista (#159 — ``build --min-weight``).
                Default 1 = sin filtro (comportamiento anterior intacto).
                Si es > 1, las aristas con peso < N se filtran en todas las redes.

        Returns:
            Lista de 4 o 5 ``NetworkArtifact`` (coupling, co-autoría,
            institución, co-word y, condicionalmente, co-citación).
        """
        kinds = list(_QUICK_KINDS)

        if _has_cited_by_data(corpus):
            logger.info("Networks.quick: cited_by_id poblado — incluyendo co-citación.")
            kinds.append(NetworkKind.COCITATION)
        else:
            logger.info(
                "Networks.quick: cited_by_id vacío — co-citación omitida. "
                "Ejecutá 'b2g enrich' para poblar cited_by_id de las semillas "
                "aceptadas, o usá Networks.build(corpus, NetworkSpec(kind='cocitation')) "
                "para proyectar con los citantes disponibles."
            )

        specs = [NetworkSpec(kind=k, min_weight=min_weight) for k in kinds]
        return [_build_artifact(corpus, spec) for spec in specs]
