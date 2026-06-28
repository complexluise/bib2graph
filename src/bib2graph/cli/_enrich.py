"""cli._enrich — Helper de enriquecimiento en memoria (sin I/O de store).

Centraliza la lógica de enriquecimiento para que ``chain``, ``build`` y
``enrich`` compartan UNA sola implementación (fuente única, sin duplicar).

El helper opera sobre un ``Corpus`` ya en memoria, dentro de la transacción
existente de quien lo llama. NO abre ni cierra el store: eso es
responsabilidad del llamante.

Pasadas soportadas:
  - ``"refs_doi"``: resuelve ``references_id`` → ``references_doi`` (Hito 8a).
    Corre en ``chain`` (forrajeo puro), automática.
  - ``"cited_by"``: puebla ``cited_by_id`` de las semillas aceptadas (Hito 8b).
    Corre en ``build``, automática si hay seeds aceptadas; si no, no-op graceful.
  - ``"both"``: ambas pasadas (se usa en ``enrich`` standalone).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from bib2graph.corpus import Corpus
    from bib2graph.sources.openalex import OpenAlexSource


def enrich_corpus(
    corpus: Corpus,
    source: OpenAlexSource,
    *,
    max_citing: int | None = None,
    pass_name: str = "both",
) -> tuple[Corpus, dict[str, Any]]:
    """Enriquece el corpus en memoria con una o ambas pasadas de OpenAlex.

    Construye un ``OpenAlexEnricher`` con el ``source`` dado y ejecuta la(s)
    pasada(s) indicadas.  Extrae las métricas del Manifest del corpus resultado
    y las devuelve junto al corpus enriquecido.

    No abre store ni hace I/O de persistencia — eso es responsabilidad
    del llamante (chain/build/enrich).

    Args:
        corpus: Corpus en memoria sobre el que operar.
        source: ``OpenAlexSource`` ya instanciado y configurado.
            El mismo source que el comando ya creó para chaining o build.
        max_citing: Tope de citantes por semilla para la pasada ``cited_by``.
            ``None`` = sin tope.  Ignorado en ``refs_doi``.
        pass_name: Pasada(s) a ejecutar.
            ``"refs_doi"`` = solo Pasada 1 (resuelve DOIs de referencias).
            ``"cited_by"`` = solo Pasada 2 (puebla citantes de seeds aceptadas).
            ``"both"`` = ambas en orden (Pasada 1 → Pasada 2).  Default.

    Returns:
        Tupla ``(corpus_enriquecido, metricas)`` donde ``metricas`` es un
        dict con un subconjunto de:
          - ``refs_resolved`` (int): referencias resueltas a DOI.
          - ``refs_total_unique`` (int): total de references_id únicos.
          - ``citing_new`` (int): nuevos citantes añadidos a cited_by_id.
          - ``citing_targets`` (int): seeds aceptadas procesadas en pasada 2.
        Solo aparecen las claves de las pasadas que se ejecutaron.

    Raises:
        httpx.HTTPError: Si falla la conexión a OpenAlex (propagado).
        ValueError: Si ``pass_name`` no es ``"refs_doi"``, ``"cited_by"``
            ni ``"both"``.
    """
    from bib2graph.enrichers.openalex import OpenAlexEnricher

    if pass_name not in ("refs_doi", "cited_by", "both"):
        raise ValueError(
            f"pass_name desconocido: {pass_name!r}. "
            "Usá 'refs_doi', 'cited_by' o 'both'."
        )

    enricher = OpenAlexEnricher(source, max_citing_per_paper=max_citing)

    if pass_name == "refs_doi":
        enriched = enricher.enrich_references_doi(corpus)
    elif pass_name == "cited_by":
        enriched = enricher.enrich_cited_by(corpus)
    else:  # "both"
        enriched = enricher.enrich(corpus)

    metrics = _extract_metrics(enriched)
    return enriched, metrics


def _extract_metrics(corpus: Corpus) -> dict[str, Any]:
    """Extrae métricas de enriquecimiento del Manifest del corpus.

    Recorre ``corpus.manifest.enrichers`` buscando las entradas de las
    pasadas 1 (``openalex_references_doi``) y 2 (``openalex_cited_by``).
    Devuelve un dict con solo las claves presentes.

    Args:
        corpus: Corpus enriquecido (con el Manifest actualizado por el Enricher).

    Returns:
        Dict con claves ``refs_resolved``, ``refs_total_unique``, ``citing_new``
        y/o ``citing_targets`` según las pasadas ejecutadas.
    """
    enricher_refs = corpus.manifest.enrichers
    metrics: dict[str, Any] = {}

    doi_entry = next(
        (e for e in enricher_refs if e.name == "openalex_references_doi"), None
    )
    if doi_entry is not None:
        metrics["refs_resolved"] = int(doi_entry.params.get("resolved", 0))
        metrics["refs_total_unique"] = int(doi_entry.params.get("total_unique_refs", 0))

    cb_entry = next((e for e in enricher_refs if e.name == "openalex_cited_by"), None)
    if cb_entry is not None:
        metrics["citing_new"] = int(cb_entry.params.get("resolved", 0))
        metrics["citing_targets"] = int(cb_entry.params.get("total", 0))

    return metrics
