"""foraging.scent — cómputo del *information scent* bibliométrico (funciones puras).

El scent mide el acoplamiento bibliométrico de un candidato con el corpus
curado, usando los **proyectores** como base (`networks/projectors.py`).
El forrajeo (costura) depende del núcleo de proyección; el núcleo NUNCA
depende de la costura (ADR 0020, enmienda 2026-06-15; ADR 0022).

## Fórmula del score (determinista, sin LLM)

### Backward — candidato X referenciado por papers del corpus

    backward_score(X) = |{Pi ∈ corpus : X ∈ Pi.references_id}|

*Interpretación bibliométrica*: cuántos papers del corpus apuntan a X.
Equivale a la "columna" de X en la matriz de acoplamiento: si muchos
papers del corpus citan X, es que X es un antecedente compartido del campo
(acoplamiento hacia atrás).  Se computa mediante
``collect_item_to_papers(corpus, Col.ID, Col.REFERENCES_ID)[X]``.

### Forward — candidato Y que cita papers del corpus

    corpus_ids = {Pi.id | Pi.source_id : Pi ∈ corpus}
    forward_score(Y) = |{ref ∈ Y.references_id : ref ∈ corpus_ids}|

*Interpretación bibliométrica*: cuántos corpus-papers cita Y directamente
(fuerza de citación directa al corpus, Wohlin).  Es robusto y siempre > 0
para cualquier citante real traído por ``fetch_citing``, sin depender de que
los corpus-papers tengan ``references_id`` poblado (a diferencia del
acoplamiento bibliográfico puro, que degenera a 0 cuando ``references_id``
es rala — estado común tras un seed sin enriquecimiento).

No requiere el índice inverso ``collect_item_to_papers``; se resuelve con
intersección directa ``Y.references_id ∩ corpus_ids``.

### Score combinado (dirección "both")

Cuando se usan ambas direcciones, los scores se suman por candidato; un
candidato backward puede aparecer también como forward si es a su vez
citante.

### Desempate estable

Ranking descendente por score, desempate ascendente por ``id`` (garantía
de determinismo independiente de ``PYTHONHASHSEED`` o del orden de
iteración de dicts).

### Sesgo reconocido (ADR 0020, enmienda 2026-06-15)

El scent *prioriza*; no garantiza exhaustividad.  La exhaustividad la
sostienen los filtros PRISMA y el conteo de exclusiones, no el scent.
El efecto Mateo está presente: un candidato marginal pero relevante puede
quedar abajo si el corpus existente aún no lo cita.

Ver docs/API.md §5 y ADR 0020/0022.
"""

from __future__ import annotations

from typing import Any

from bib2graph.constants import Col
from bib2graph.networks.projectors import collect_item_to_papers


def compute_backward_scent(
    corpus_rows: list[dict[str, Any]],
) -> dict[str, float]:
    """Calcula el scent backward para cada candidato potencial.

    Un candidato backward es un id que aparece en ``references_id`` de al
    menos un paper del corpus, pero que NO es el ``id`` ni el
    ``source_id`` de ningún paper ya en el corpus.

    Score = ``|{Pi ∈ corpus : X ∈ Pi.references_id}|``
    (acoplamiento hacia atrás: cuántos corpus-papers apuntan al candidato).

    Computa el score mediante el primitivo
    ``collect_item_to_papers(corpus, Col.ID, Col.REFERENCES_ID)``, que
    construye el índice ``{ref_id → [corpus_paper_ids_que_lo_citan]}``.

    La exclusión de candidatos duplicados usa tanto Col.ID como Col.SOURCE_ID
    porque los IDs de motor (W… de OpenAlex) aparecen en references_id y deben
    cruzar contra el source_id W… del corpus para no re-proponer papers ya presentes.

    Args:
        corpus_rows: Lista de filas del corpus como dicts (``to_pylist()``).

    Returns:
        Dict ``{candidate_id: score}`` donde score = nº de corpus-papers
        que listan al candidato en ``references_id``.
    """
    # Se incluye tanto Col.ID como Col.SOURCE_ID: las references_id de OpenAlex
    # son IDs de motor (W…) y deben cruzar contra el source_id W… del corpus.
    corpus_ids: set[str] = set()
    for row in corpus_rows:
        id_val = row.get(Col.ID)
        source_id_val = row.get(Col.SOURCE_ID)
        if id_val:
            corpus_ids.add(str(id_val))
        if source_id_val:
            corpus_ids.add(str(source_id_val))

    # Usamos Col.ID como id_col para registrar qué corpus-paper hace la cita.
    ref_to_papers = collect_item_to_papers(corpus_rows, Col.ID, Col.REFERENCES_ID)

    # Score = número de corpus-papers distintos que citan el candidato
    return {
        ref_id: float(len(set(papers)))
        for ref_id, papers in ref_to_papers.items()
        if ref_id not in corpus_ids
    }


def compute_forward_scent(
    corpus_rows: list[dict[str, Any]],
    citing_rows: list[dict[str, Any]],
) -> dict[str, float]:
    """Calcula el scent forward para cada candidato citante.

    Un candidato forward es un paper (en ``citing_rows``) que cita papers
    del corpus pero que aún NO es ``id``/``source_id`` de ningún corpus-paper.

    ## Fórmula (citación directa al corpus — Wohlin)

        corpus_ids = {Pi.id | Pi.source_id : Pi ∈ corpus}
        forward_score(Y) = |{ref ∈ Y.references_id : ref ∈ corpus_ids}|

    *Interpretación*: cuántos corpus-papers cita Y directamente.  Este score
    es robusto y siempre > 0 para cualquier citante real traído por
    ``fetch_citing`` (que, por definición, cita al menos un corpus-paper),
    sin requerir que los corpus-papers tengan ``references_id`` poblado.
    La medida de acoplamiento bibliográfico puro degenera a 0 cuando
    ``references_id`` es rala (estado habitual tras un seed sin enriquecimiento);
    la citación directa NO tiene ese problema.

    Solo se emite una entrada en el resultado cuando ``forward_score(Y) > 0``
    (i.e., Y cita al menos un corpus-paper directamente).  Todos los citantes
    reales traídos por ``fetch_citing`` satisfacen esta condición por
    construcción.

    Args:
        corpus_rows: Filas del corpus actual (para construir ``corpus_ids``
            y excluir candidatos ya presentes).
        citing_rows: Filas de los citantes traídos vía ``fetch_citing``.
            Deben tener ``references_id`` para que el score sea computable.

    Returns:
        Dict ``{citing_id: score}`` donde score = nº de corpus-papers
        citados directamente por el candidato Y.
    """
    # Sirven para (a) excluir candidatos ya presentes y
    # (b) intersectar con Y.references_id para el score de citación directa.
    # Se incluye tanto Col.ID como Col.SOURCE_ID: las references_id de OpenAlex
    # son IDs de motor (W…) y deben cruzar contra el source_id W… del corpus.
    corpus_ids: set[str] = set()
    for row in corpus_rows:
        id_val = row.get(Col.ID)
        source_id_val = row.get(Col.SOURCE_ID)
        if id_val:
            corpus_ids.add(str(id_val))
        if source_id_val:
            corpus_ids.add(str(source_id_val))

    scent: dict[str, float] = {}
    for row in citing_rows:
        citing_id = row.get(Col.ID)
        if not citing_id:
            continue
        citing_id_str = str(citing_id)
        if citing_id_str in corpus_ids:
            continue

        refs = row.get(Col.REFERENCES_ID)
        if not refs or not isinstance(refs, list):
            continue

        direct = sum(
            1 for ref in refs if ref and isinstance(ref, str) and str(ref) in corpus_ids
        )

        if direct > 0:
            scent[citing_id_str] = float(direct)

    return scent


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
