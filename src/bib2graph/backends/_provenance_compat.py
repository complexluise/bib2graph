"""Compatibilidad on-read para corpus pre-D2 con ``chaining:*`` en provenance.

ADR 0050 D2 (#320): ``ProvenanceEvent.source_kind`` desambigua el origen de
un paper ("semilla de ecuación" vs "citante forrajeado") y elimina el
overload de ``equation_id`` con prefijos ``chaining:forward:…`` /
``chaining:backward:…`` que se usaban antes.

Migración híbrida (resolución del PO, 2026-10-11): **on-read** primero —un
parser de compat en el camino de lectura que deriva ``source_kind`` del
prefijo ``chaining:`` y pone ``equation_id=None``. La migración escrita a los
stores queda **diferida a 0.16.0+** si surge demanda.

Este módulo es una **función pura** (``migrate_provenance_event``) sin
efectos secundarios: no toca IO, red ni estado global. ``backends/memory``
la invoca desde ``_parse_provenance`` para que cualquier lectura del corpus
(corpus loaded en memoria, persistido en DuckDB, hidratado de snapshot,
rehidratado por ``restore``) pase por la migración transparente sin tener
que dispersarla por el resto del código.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bib2graph.schemas import ProvenanceEvent

# Prefijos que la migración on-read sabe traducir. Cualquier otro prefijo
# ``chaining:<algo>`` no se inventa (defensivo: preserva el evento tal cual).
_FORWARD_KIND = "chaining_forward"
_BACKWARD_KIND = "chaining_backward"
_SOURCE_KIND_FOR_PREFIX: dict[str, str] = {
    "chaining:forward": _FORWARD_KIND,
    "chaining:backward": _BACKWARD_KIND,
}


def migrate_provenance_event(
    event: ProvenanceEvent | dict[str, object],
) -> dict[str, object]:
    """Deriva ``source_kind`` de un evento pre-D2 con ``chaining:*`` en ``equation_id``.

    Reglas (orden de evaluación):

    1. Si el evento **ya** trae ``source_kind`` válido (``"seed_equation"`` /
       ``"chaining_forward"`` / ``"chaining_backward"``) → no se toca
       (idempotencia: doble migración o post-D2 que pasa por acá).
    2. Si ``equation_id`` empieza con un prefijo conocido
       (``chaining:forward`` o ``chaining:backward``), sea solo el prefijo o
       con un ID pegado (``chaining:forward:W12345``) → ``source_kind`` se
       deriva del prefijo y ``equation_id`` pasa a ``None``.
    3. Cualquier otro caso (``eq-…``, ``load``, ``fetched_by_id``,
       ``chaining:<otro>``, ``None``, evento de curación con ``action``
       ``accepted``/``rejected``) → se preserva el evento tal cual (incluido
       ``source_kind=None``). El parser no inventa ``source_kind`` para
       prefijos desconocidos: esa decisión queda para una migración escrita
       si surge.

    Es **función pura** (sin IO, sin red, sin estado global) — vive en
    ``backends/`` para que el parser on-read esté cerca del código de carga,
    pero no toca archivos DuckDB.

    Args:
        event: ``ProvenanceEvent`` o dict con los campos del evento.

    Returns:
        Nuevo dict con el evento migrado (no muta la entrada). Si el evento
        ya está en formato post-D2, devuelve un dict con los mismos campos.
    """
    if hasattr(event, "model_dump"):
        data: dict[str, object] = dict(event.model_dump())
    else:
        data = dict(event)

    # Idempotencia: si ya tiene source_kind válido, no se toca.
    if data.get("source_kind") in (
        "seed_equation",
        "chaining_forward",
        "chaining_backward",
    ):
        return data

    equation_id = data.get("equation_id")
    if not isinstance(equation_id, str):
        return data

    # Recorremos los prefijos conocidos. Si matchea, derivamos source_kind.
    # Solo matcheamos el prefijo exacto (`chaining:forward`) o con un `:` pegado
    # (`chaining:forward:foo`); nunca prefijos extendidos tipo
    # `chaining:forwardish` — esos no son chaining_forward y se preservan tal cual.
    for prefix, kind in _SOURCE_KIND_FOR_PREFIX.items():
        if equation_id == prefix or equation_id.startswith(prefix + ":"):
            data["source_kind"] = kind
            data["equation_id"] = None
            return data

    # Cualquier otro caso (incluido `chaining:<otro>` defensivo, seeds
    # `eq-…`, `load`, `fetched_by_id`, curación) se preserva tal cual.
    return data
