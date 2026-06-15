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
    backward se estima exactamente desde ``references_id``.  El crecimiento
    forward no puede estimarse sin fetch, por lo que ``by_direction["forward"]``
    vale ``0`` cuando ``forward_requires_fetch`` es ``True``; el conteo real
    solo se conoce al llamar ``chain(direction="forward"/"both")``.

    Attributes:
        estimated_new: Estimación total de candidatos nuevos (solo lo que
            puede calcularse localmente; forward vale 0 cuando
            ``forward_requires_fetch`` es ``True``).
        by_direction: Desglose por dirección (``backward``/``forward``).
            La entrada ``"forward"`` vale ``0`` cuando el crecimiento forward
            no es estimable sin red.
        direction: Dirección pedida (``backward``/``forward``/``both``).
        forward_requires_fetch: ``True`` cuando se pidió forward o both —
            indica que el crecimiento forward es desconocido hasta llamar a
            ``chain()``.  ``False`` cuando la dirección es solo backward
            (estimación exacta local).
    """

    estimated_new: int
    by_direction: dict[str, int]
    direction: Direction
    forward_requires_fetch: bool = False


class RankedCandidates(BaseModel):
    """Resultado del ``Forager.chain()``: candidatos rankeados por scent.

    El corpus contiene SOLO los candidatos nuevos (no mergeado con el
    corpus semilla). El ranking es una lista estable ordenada por scent
    descendente, con desempate por id ascendente.

    Attributes:
        corpus: Corpus de candidatos con ``curation_status='candidate'``.
        ranking: Lista ``(id, information_scent)`` ordenada por scent desc.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    corpus: Corpus
    ranking: list[tuple[str, float]]
