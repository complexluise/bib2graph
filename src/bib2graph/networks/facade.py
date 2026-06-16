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

from bib2graph.constants import NetworkKind
from bib2graph.networks.analyzer import detect_communities, network_metrics
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

# Tipos de red disponibles en Networks.quick (D3: sin co-citación)
# Derivado de NetworkKind — fuente única (R1, ADR 0023)
_QUICK_KINDS: list[str] = [
    NetworkKind.BIBLIOGRAPHIC_COUPLING,
    NetworkKind.AUTHOR_COLLAB,
    NetworkKind.INSTITUTION_COLLAB,
    NetworkKind.KEYWORD_COOCCURRENCE,
]


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

    Args:
        spec: Especificación de la red.

    Returns:
        Instancia del proyector (cumple el protocolo ``Projector``).

    Raises:
        ValueError: Si el kind no es reconocido.
    """
    kind = spec.kind
    if kind == "bibliographic_coupling":
        return BibliographicCouplingProjector()
    elif kind == "author_collab":
        return AuthorCollaborationProjector()
    elif kind == "institution_collab":
        return InstitutionCollaborationProjector()
    elif kind == "keyword_cooccurrence":
        return KeywordCoOccurrenceProjector()
    elif kind == "cocitation":
        return CoCitationProjector()
    else:
        raise ValueError(f"Kind de red no reconocido: '{kind}'")


def _build_artifact(corpus: Corpus, spec: NetworkSpec) -> NetworkArtifact:
    """Construye un ``NetworkArtifact`` a partir de un corpus y una spec.

    Proyecta, calcula métricas y detecta comunidades (si spec.clustering está
    configurado).

    R2: Louvain se siembra con un ``random_state`` derivado del
    ``corpus_hash`` de contenido (excluyendo provenance) para reproducibilidad.

    Args:
        corpus: Corpus de origen.
        spec: Especificación de la red.

    Returns:
        ``NetworkArtifact`` con grafo, métricas, comunidades y spec.
    """
    projector = _projector_for_kind(spec)
    table = corpus.to_arrow()

    g: _Graph = projector.project(
        table,
        min_weight=spec.min_weight,
        scope=spec.scope,
    )

    metrics = network_metrics(g)

    communities: dict[Any, int] | None = None
    if spec.clustering is not None and g.number_of_nodes() > 0:
        try:
            # R2: derivar random_state del content-hash para Louvain reproducible
            random_state: int | None = None
            if spec.clustering == "louvain":
                corpus_hash = corpus._backend.corpus_hash()
                random_state = _louvain_seed_from_hash(corpus_hash)
            communities = detect_communities(
                g, method=spec.clustering, random_state=random_state
            )
        except ImportError:
            raise  # dep faltante: fallar fuerte (lección 7, AGENTS.md)
        except Exception as exc:
            logger.warning(
                "No se pudo detectar comunidades con método '%s': %s",
                spec.clustering,
                exc,
            )
            communities = None

    return NetworkArtifact(
        graph=g,
        metrics=metrics,
        communities=communities,
        assortativity=None,
        layout=None,
        spec=spec,
    )


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
    def quick(corpus: Corpus) -> list[NetworkArtifact]:
        """Construye las 4 redes principales con configuración razonable.

        Arma specs para: acoplamiento bibliográfico (full), co-autoría,
        colaboración institucional y co-ocurrencia de keywords.

        La co-citación se OMITE intencionalmente en ``quick`` porque requiere
        el segundo nivel de fetch del ``OpenAlexEnricher`` (Hito 8). El
        ``CoCitationProjector`` sí está implementado y disponible vía
        ``Networks.build(corpus, NetworkSpec(kind='cocitation'))``.

        Args:
            corpus: Corpus de origen.

        Returns:
            Lista de 4 ``NetworkArtifact`` (coupling, co-autoría, institución,
            co-word).
        """
        logger.info(
            "Networks.quick: construyendo 4 redes (coupling, co-autoría, "
            "institución, co-word). La co-citación se omite en quick porque "
            "requiere el 2º nivel de fetch del OpenAlexEnricher (Hito 8). "
            "Usa Networks.build(corpus, NetworkSpec(kind='cocitation')) para "
            "proyectar co-citación con los citantes disponibles en el corpus."
        )

        specs = [NetworkSpec(kind=k) for k in _QUICK_KINDS]
        return [_build_artifact(corpus, spec) for spec in specs]
