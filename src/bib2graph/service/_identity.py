"""service._identity — Resolución de un identificador de paper al id interno.

Un paper se identifica canónicamente por su ``id`` interno (hash DOI-first,
ADR 0036), pero el **DOI es el identificador que importa** para el usuario y el
``source_id`` del motor también es visible en ``read show``/``read list``. Este
helper resuelve cualquiera de las tres formas —``id`` interno, DOI crudo o
``source_id``— al ``id`` interno, para que los comandos acepten indistintamente
lo que el usuario tenga a mano. Misma prioridad que ``read show``:
``id > doi > source_id`` (ADR 0036).

Función pura sobre filas ya cargadas (``corpus.to_arrow().to_pylist()``): sin
I/O, sin reloj, sin Click. La usan ``service.reads.get_paper`` y
``service.curate.accept_papers``/``reject_papers``.
"""

from __future__ import annotations

from typing import Any

from bib2graph.constants import Col


def resolve_ident_to_row(
    rows: list[dict[str, Any]], ident: str
) -> dict[str, Any] | None:
    """Devuelve la fila cuyo id/doi/source_id coincide con ``ident``, o ``None``.

    Prioridad ``id > doi > source_id`` (ADR 0036): si ``ident`` matchea por
    ``id`` gana esa fila, aunque otro paper lo tenga como ``source_id``.
    """
    for row in rows:
        if str(row.get(Col.ID)) == ident:
            return row
    for row in rows:
        doi = row.get(Col.DOI)
        if doi is not None and str(doi) == ident:
            return row
    for row in rows:
        source_id = row.get(Col.SOURCE_ID)
        if source_id is not None and str(source_id) == ident:
            return row
    return None


def resolve_ident_to_id(rows: list[dict[str, Any]], ident: str) -> str | None:
    """Resuelve ``ident`` al ``id`` interno del paper, o ``None`` si no matchea."""
    row = resolve_ident_to_row(rows, ident)
    return str(row.get(Col.ID)) if row is not None else None


def resolve_idents(
    rows: list[dict[str, Any]], idents: list[str]
) -> tuple[list[str], list[str]]:
    """Resuelve una lista de idents a ids internos.

    Cada ident puede venir como ``id`` interno, DOI crudo o ``source_id``.

    Returns:
        ``(resolved_ids, unresolved)``. ``resolved_ids`` son los ids internos en
        el orden de entrada, deduplicados preservando el orden (dos idents que
        apuntan al mismo paper —p.ej. su DOI y su source_id— colapsan a un id).
        ``unresolved`` son los idents que no matchearon por ninguna de las tres
        vías, en orden de entrada.
    """
    resolved: list[str] = []
    seen: set[str] = set()
    unresolved: list[str] = []
    for ident in idents:
        internal = resolve_ident_to_id(rows, ident)
        if internal is None:
            unresolved.append(ident)
        elif internal not in seen:
            seen.add(internal)
            resolved.append(internal)
    return resolved, unresolved
