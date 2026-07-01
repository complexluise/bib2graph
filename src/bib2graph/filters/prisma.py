"""filters.prisma — ``apply_filter`` / ``apply_filters`` (funciones puras).

Los filtros MARCAN ``rejected`` pero NO borran filas (decisión c-bis=marcar).
``apply_filter`` calcula ``count_before`` (papers no-rejected antes), determina
los ids que no pasan, llama ``corpus.reject(...)`` con provenance y devuelve
``(corpus_nuevo, FilterStep)``.
``apply_filters`` encadena y sella ``Manifest.filters`` al final.

Criterios soportados:

- ``year`` + ``gte``/``lte``: año >= / <= valor.
- ``type`` + ``in``/``not_in``: ``research_areas`` contiene / no contiene el valor.
- ``language`` + ``eq``/``in``/``not_in``: idioma igual / en lista / no en lista.
- ``min_citations`` + ``gte``: ``len(cited_by_id)`` >= valor.

R5: campo o operador desconocido → ``ValueError`` accionable (antes era no-op silencioso).

ADR 0043: la inclusión manual gana — el filtro nunca rechaza un paper
``accepted``, solo actúa sobre ``candidate`` (y demás no-``accepted``,
no-``rejected``).

Ver docs/API.md §convenciones (CLI ``filter``).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from bib2graph.constants import Col, CurationStatus
from bib2graph.corpus import Corpus, FilterStep

_FIELD_OPS: dict[str, set[str]] = {
    "year": {"gte", "lte"},
    "type": {"in", "not_in"},
    "language": {"eq", "in", "not_in"},
    "min_citations": {"gte"},
}


class FilterCriterion(BaseModel):
    """Criterio de filtro PRISMA.

    Attributes:
        field: Campo del Corpus a filtrar.
        op: Operador de comparación.
        value: Valor de referencia (int para year/min_citations; str o
            ``list[str]`` para type/language).
    """

    field: Literal["year", "type", "language", "min_citations"]
    op: Literal["gte", "lte", "in", "not_in", "eq"]
    value: int | str | list[str]


def _passes(row: dict[str, object], criterion: FilterCriterion) -> bool:
    """Devuelve ``True`` si el paper pasa el criterio (no debe ser rechazado).

    Args:
        row: Fila del corpus como dict.
        criterion: Criterio a evaluar.

    Returns:
        ``True`` si el paper cumple el criterio (NO se rechaza).
    """
    field = criterion.field
    op = criterion.op
    value = criterion.value

    if field == "year":
        year_raw = row.get(Col.YEAR)
        if year_raw is None:
            return False
        y = int(str(year_raw))
        int_value = int(str(value))
        if op == "gte":
            return y >= int_value
        if op == "lte":
            return y <= int_value
        raise ValueError(
            f"Operador '{op}' no soportado para el campo 'year'. "
            f"Operadores válidos: {_FIELD_OPS['year']}."
        )

    if field == "type":
        areas = row.get(Col.RESEARCH_AREAS)
        area_list: list[str] = (
            [str(a) for a in areas] if isinstance(areas, list) else []
        )
        vals: list[str] = (
            [str(value)] if isinstance(value, (str, int)) else [str(v) for v in value]
        )
        if op == "in":
            return any(v in area_list for v in vals)
        if op == "not_in":
            return not any(v in area_list for v in vals)
        raise ValueError(
            f"Operador '{op}' no soportado para el campo 'type'. "
            f"Operadores válidos: {_FIELD_OPS['type']}."
        )

    if field == "language":
        lang = row.get(Col.LANGUAGE)
        lang_str = str(lang).lower() if lang is not None else ""
        vals_lang: list[str] = (
            [str(value).lower()]
            if isinstance(value, (str, int))
            else [str(v).lower() for v in value]
        )
        if op == "eq":
            return lang_str == vals_lang[0]
        if op == "in":
            return lang_str in vals_lang
        if op == "not_in":
            return lang_str not in vals_lang
        raise ValueError(
            f"Operador '{op}' no soportado para el campo 'language'. "
            f"Operadores válidos: {_FIELD_OPS['language']}."
        )

    if field == "min_citations":
        cited = row.get(Col.CITED_BY_ID)
        n = len(cited) if isinstance(cited, list) else 0
        min_val = int(str(value))
        if op == "gte":
            return n >= min_val
        raise ValueError(
            f"Operador '{op}' no soportado para el campo 'min_citations'. "
            f"Operadores válidos: {_FIELD_OPS.get(field, set())}."
        )

    raise ValueError(
        f"Campo de filtro desconocido: '{field}'. "
        f"Campos soportados: {list(_FIELD_OPS.keys())}."
    )


def _count_not_rejected(corpus: Corpus) -> int:
    """Cuenta los papers que NO están rechazados (candidate + accepted).

    Args:
        corpus: Corpus a contar.

    Returns:
        Número de papers no rechazados.
    """
    rows = corpus.to_arrow().to_pylist()
    return sum(1 for r in rows if r.get(Col.CURATION_STATUS) != CurationStatus.REJECTED)


def apply_filter(
    corpus: Corpus,
    criterion: FilterCriterion,
    *,
    decided_at: datetime | None = None,
) -> tuple[Corpus, FilterStep]:
    """Aplica un criterio de filtro, marcando rejected los papers que no pasan.

    ``count_before`` = papers no-rejected antes del filtro.
    ``count_after`` = papers no-rejected después del filtro.

    Los papers rechazados siguen en la tabla con ``curation_status='rejected'``
    (NUNCA se borran; flujo PRISMA).

    ADR 0043: la inclusión manual gana sobre el criterio automático — el
    filtro NUNCA mueve un paper ``accepted`` a ``rejected``. El filtro actúa
    solo sobre papers no-aceptados (``candidate`` y demás no-``accepted``),
    igual que ya omite a los ya-``rejected``.

    R2 (ADR 0017 enmendado): ``decided_at`` se inyecta desde la frontera
    (CLI) para que el núcleo no llame al reloj.  Si es ``None``, el backend
    usa ``datetime.now(UTC)`` como conveniencia para uso como librería.

    Args:
        corpus: Corpus a filtrar (no muta).
        criterion: Criterio a aplicar.
        decided_at: Instante de la decisión.  Si es ``None``, el backend
            usa ``datetime.now(UTC)`` como fallback (ergonomía de librería).

    Returns:
        Tupla ``(corpus_nuevo, FilterStep)`` con los conteos PRISMA.
    """
    count_before = _count_not_rejected(corpus)

    rows = corpus.to_arrow().to_pylist()
    ids_to_reject = [
        str(row[Col.ID])
        for row in rows
        if row.get(Col.CURATION_STATUS)
        not in (CurationStatus.REJECTED, CurationStatus.ACCEPTED)
        and not _passes(row, criterion)
    ]

    label = f"filter:{criterion.field}:{criterion.op}:{criterion.value}"
    new_corpus = (
        corpus.reject(
            ids_to_reject,
            by="prisma_filter",
            source=label,
            decided_at=decided_at,
        )
        if ids_to_reject
        else corpus
    )

    count_after = _count_not_rejected(new_corpus)

    step = FilterStep(
        name=f"filter:{criterion.field}",
        criteria=label,
        count_before=count_before,
        count_after=count_after,
    )
    return new_corpus, step


def apply_filters(
    corpus: Corpus,
    criteria: list[FilterCriterion],
    *,
    decided_at: datetime | None = None,
) -> tuple[Corpus, list[FilterStep]]:
    """Encadena varios criterios de filtro y sella ``Manifest.filters``.

    Los filtros se aplican en orden; cada uno ve los conteos PRISMA del
    resultado del anterior.  Al final, ``Manifest.filters`` se actualiza
    con todos los pasos.

    R2 (ADR 0017 enmendado): ``decided_at`` se inyecta desde la frontera
    (CLI) para que el núcleo no llame al reloj.  Si es ``None``, el backend
    usa ``datetime.now(UTC)`` como conveniencia para uso como librería.

    Args:
        corpus: Corpus inicial (no muta).
        criteria: Lista de criterios a aplicar en orden.
        decided_at: Instante de la decisión compartido por todos los pasos.
            Si es ``None``, el backend usa ``datetime.now(UTC)`` como fallback.

    Returns:
        Tupla ``(corpus_final, [FilterStep, ...])`` con todos los pasos.
    """
    steps: list[FilterStep] = []
    current = corpus

    for criterion in criteria:
        current, step = apply_filter(current, criterion, decided_at=decided_at)
        steps.append(step)

    new_manifest = current.manifest.model_copy(update={"filters": steps})
    final_corpus = current.with_manifest(new_manifest)
    return final_corpus, steps
