"""foraging.scent — cómputo del *information scent* (funciones puras).

El scent mide la frecuencia de enlace de un candidato con el corpus
existente, en ambas direcciones:

- **Backward**: el candidato aparece en ``references_id`` de los papers
  del corpus; su scent = nº de papers del corpus que lo listan como
  referencia.  Excluye los ids que ya son ``id``/``openalex_id`` del corpus
  (no son candidatos nuevos).

- **Forward**: el citante trae ``cited_by_id``; su scent = nº de papers del
  corpus a los que cita (cuántos papers del corpus cita el candidato).

Sin acoplamiento, sin centralidad, sin construcción de grafo (ADR 0008,
decisión a=A).  El ranking final es descendente por scent, con desempate
estable por id ascendente (determinista ante cualquier ``PYTHONHASHSEED``).

Ver docs/API.md §5.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from bib2graph.constants import Col


def compute_backward_scent(
    corpus_rows: list[dict[str, Any]],
) -> dict[str, float]:
    """Calcula el scent backward para cada candidato potencial.

    El candidato backward es un id que aparece en ``references_id`` de
    al menos un paper del corpus, pero que NO es el ``id`` ni el
    ``openalex_id`` de ningún paper ya en el corpus.

    Args:
        corpus_rows: Lista de filas del corpus como dicts (``to_pylist()``).

    Returns:
        Dict ``{candidate_id: scent}`` donde scent = nº de papers del
        corpus que listan al candidato en ``references_id``.
    """
    # ids ya presentes en el corpus (para excluir)
    corpus_ids: set[str] = set()
    for row in corpus_rows:
        id_val = row.get(Col.ID)
        openalex_id_val = row.get(Col.OPENALEX_ID)
        if id_val:
            corpus_ids.add(str(id_val))
        if openalex_id_val:
            corpus_ids.add(str(openalex_id_val))

    # Conteo: cuántos papers del corpus listan a cada ref
    ref_count: Counter[str] = Counter()
    for row in corpus_rows:
        refs = row.get(Col.REFERENCES_ID)
        if not refs or not isinstance(refs, list):
            continue
        # Usamos un set para no contar el mismo ref dos veces en el mismo paper
        seen_in_paper: set[str] = set()
        for ref in refs:
            if ref and isinstance(ref, str) and ref not in seen_in_paper:
                seen_in_paper.add(ref)
                ref_count[ref] += 1

    # Excluir los que ya están en el corpus
    return {
        ref_id: float(count)
        for ref_id, count in ref_count.items()
        if ref_id not in corpus_ids
    }


def compute_forward_scent(
    corpus_rows: list[dict[str, Any]],
    citing_rows: list[dict[str, Any]],
) -> dict[str, float]:
    """Calcula el scent forward para cada candidato citante.

    El scent de un citante = nº de papers del corpus a los que cita.
    ``citing_rows`` son los Works de OpenAlex traídos como citantes
    (tienen ``references_id`` con los ids que citan).

    Args:
        corpus_rows: Filas del corpus actual (para saber qué ids están).
        citing_rows: Filas de los citantes traídos vía fetch_citing.

    Returns:
        Dict ``{citing_id: scent}`` donde scent = nº de papers del corpus
        que el citante lista en sus referencias.
    """
    # ids y openalex_ids del corpus
    corpus_ids: set[str] = set()
    for row in corpus_rows:
        id_val = row.get(Col.ID)
        openalex_id_val = row.get(Col.OPENALEX_ID)
        if id_val:
            corpus_ids.add(str(id_val))
        if openalex_id_val:
            corpus_ids.add(str(openalex_id_val))

    # ids ya en el corpus (para excluir al candidato si ya está)
    citing_ids_already: set[str] = corpus_ids.copy()

    scent: defaultdict[str, float] = defaultdict(float)
    for row in citing_rows:
        citing_id = row.get(Col.ID)
        if not citing_id:
            continue
        citing_id_str = str(citing_id)
        if citing_id_str in citing_ids_already:
            continue  # ya en el corpus, no es candidato nuevo

        refs = row.get(Col.REFERENCES_ID)
        if not refs or not isinstance(refs, list):
            continue

        # Cuántas refs de este citante son papers del corpus
        overlap = sum(
            1 for ref in refs if ref and isinstance(ref, str) and ref in corpus_ids
        )
        if overlap > 0:
            scent[citing_id_str] += float(overlap)

    return dict(scent)


def rank_candidates(
    scent_map: dict[str, float],
    *,
    max_candidates: int | None = None,
) -> list[tuple[str, float]]:
    """Ordena candidatos por scent descendente, con desempate por id ascendente.

    El desempate por id garantiza estabilidad determinista independiente del
    orden de iteración de dicts y de ``PYTHONHASHSEED``.

    Args:
        scent_map: Dict ``{id: scent}`` de candidatos.
        max_candidates: Si no es ``None``, corta la lista al tope dado.

    Returns:
        Lista ``[(id, scent)]`` ordenada por scent desc, id asc.
    """
    ranked = sorted(scent_map.items(), key=lambda kv: (-kv[1], kv[0]))
    if max_candidates is not None:
        ranked = ranked[:max_candidates]
    return ranked
