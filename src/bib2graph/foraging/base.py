"""foraging.base — tipos de datos del forrajeo.

Define ``Direction``, ``GrowthPreview`` y ``RankedCandidates``.

``RankedCandidates`` necesita ``arbitrary_types_allowed`` porque ``Corpus``
no es un ``BaseModel`` de Pydantic.

Ver docs/API.md §5.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from bib2graph.corpus import Corpus

# Alias público para el tipo de dirección de chaining
Direction = Literal["backward", "forward", "both"]


class GrowthPreview(BaseModel):
    """Estimación de cuántos papers agregaría un chaining antes de traerlos.

    Permite al investigador controlar el crecimiento del corpus sin hacer
    fetch (ADR 0008: control de crecimiento).

    ``preview()`` opera **solo localmente**, sin red.  El crecimiento
    backward se estima exactamente desde ``references_id``.

    Para el crecimiento forward hay dos casos:

    - Si el corpus fue enriquecido (``b2g enrich``), los papers tienen
      ``cited_by_id`` poblado: se calcula el número de IDs únicos aún no
      presentes en el corpus — estimación local exacta.  En este caso
      ``forward_requires_fetch`` es ``False`` y ``forward_from_cited_by``
      es ``True``.
    - Si ``cited_by_id`` está vacío (corpus recién sembrado, sin enrich),
      el crecimiento forward no es estimable sin red.  En este caso
      ``forward_requires_fetch`` es ``True``, ``forward_from_cited_by``
      es ``False`` y ``by_direction["forward"]`` vale ``0``.

    Attributes:
        estimated_new: Estimación total de candidatos nuevos (solo lo que
            puede calcularse localmente; forward vale 0 cuando
            ``forward_requires_fetch`` es ``True``).
        by_direction: Desglose por dirección (``backward``/``forward``).
            La entrada ``"forward"`` vale ``0`` cuando el crecimiento forward
            no es estimable sin red.
        direction: Dirección pedida (``backward``/``forward``/``both``).
        forward_requires_fetch: ``True`` cuando el crecimiento forward no puede
            estimarse localmente (corpus sin ``cited_by_id`` poblado) y es
            necesario llamar a ``chain()`` para obtener el conteo real.
            ``False`` cuando la dirección es solo backward, o cuando
            ``cited_by_id`` está disponible (estimación local exacta).
        forward_from_cited_by: ``True`` cuando el crecimiento forward se estimó
            localmente desde ``cited_by_id`` (corpus enriquecido con
            ``b2g enrich``).  ``False`` en los demás casos.
        capped_by_max: ``True`` cuando el resultado está acotado por
            ``max_candidates``; ``False`` si no se aplicó límite o si el
            número de candidatos es menor al límite.
    """

    estimated_new: int
    by_direction: dict[str, int]
    direction: Direction
    forward_requires_fetch: bool = False
    forward_from_cited_by: bool = False
    capped_by_max: bool = False


class RankedCandidates(BaseModel):
    """Resultado del ``Forager.chain()``: candidatos rankeados por scent.

    El corpus contiene SOLO los candidatos nuevos materializados (forward:
    filas reales; backward: vacío — los IDs backward van a ``observed_refs``).
    El corpus NO se mergeó con el corpus semilla.
    El ranking es una lista estable ordenada por scent descendente, con
    desempate por id ascendente.

    Attributes:
        corpus: Corpus de candidatos materializados con
            ``curation_status='candidate'`` (solo forward; backward = vacío).
        ranking: Lista ``(id, information_scent)`` ordenada por scent desc.
            Incluye tanto candidatos forward (materializados) como backward
            (solo IDs observados, sin fila en corpus).
        observed_refs: IDs de OpenAlex observados en backward chaining pero
            NO materializados como filas del corpus (opción B — #54).  Son
            los candidatos backward que se persisten en la tabla auxiliar
            ``referenced_but_not_fetched`` por el comando CLI, no en el corpus.
            Vacío en chaining puramente forward.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    corpus: Corpus
    ranking: list[tuple[str, float]]
    observed_refs: list[str] = []
