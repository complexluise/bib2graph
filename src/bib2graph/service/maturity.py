"""service.maturity — Bloque ``maturity`` para el ``--json`` de build/snapshot/read top.

Función pura sin I/O que calcula el bloque de madurez declarativo (ADR 0037 §f,
sub-issue #160). La honestidad por construcción requiere declarar explícitamente
el estado de curación, saturación y vaciedad de redes, **sin afirmar más de lo
que se sabe**.

Contrato del bloque::

    {
        "curated": false,          # bool
        "scope": "all",            # str | None
        "saturated": false,        # bool — SIEMPRE False en one-shot (PO)
        "empty_networks": []       # list[str] — solo los kinds vacíos
    }

``saturated`` es siempre ``False`` en el camino one-shot: el PO decidió no
sobre-afirmar; la condición de saturación de referencias requeriría comparar
el conteo de referencias nuevas entre dos rondas consecutivas de ``enrich``
(gancho futuro: ``referenced_refs_count()`` en el Enricher de OpenAlex).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from bib2graph.corpus import Corpus


def compute_maturity(
    corpus: Corpus,
    *,
    scope: str | None,
    empty_network_kinds: list[str],
) -> dict[str, Any]:
    """Calcula el bloque ``maturity`` para el ``--json`` de build/snapshot/read top.

    Función pura: no produce I/O ni efectos de lado.  Recibe el corpus ya
    cargado (sin abrir stores), el token de scope y los kinds de redes vacías
    determinados por quien llama.

    ``curated`` es ``True`` si el corpus contiene ≥1 paper con
    ``curation_status`` ∈ {``accepted``, ``rejected``}.  Refleja si hay
    decisiones de curación aplicadas, independientemente del scope o del FSM.

    ``saturated`` es siempre ``False`` (decisión PO: never over-claim en one-shot).
    Gancho futuro: comparar ``referenced_refs_count()`` entre rondas de ``enrich``
    para detectar convergencia de referencias.

    Args:
        corpus: Corpus ya cargado.  Se usa para derivar ``curated`` a partir
            de los conteos de ``curation_status``.
        scope: Token de scope tal como lo expone ``data["scope"]``.  En build
            se reutiliza ``data["scope"]``; en snapshot y read top es ``"all"``.
            Puede ser ``None`` si no aplica.
        empty_network_kinds: Lista de tokens ``kind`` de redes que resultaron
            vacías.  En build se extraen de ``data["empty_networks"]`` (lista
            de dicts ``{kind, reason, fix_command}``).  En read top es
            ``["cocitation"]`` si la red está vacía; en snapshot es ``[]``.
            Solo se incluyen los ``kind``, no los ``reason``/``fix_command``
            (esos siguen viviendo en ``data["empty_networks"]`` de build).

    Returns:
        Dict con exactamente 4 claves:
        - ``"curated"``: bool.
        - ``"scope"``: str | None.
        - ``"saturated"``: bool (siempre False).
        - ``"empty_networks"``: list[str] (solo kinds).
    """
    import pyarrow.compute as pc

    from bib2graph.constants import Col, CurationStatus

    table = corpus.to_arrow()

    # Derivar curated: ≥1 paper con curation_status ∈ {accepted, rejected}
    curation_col = table.column(Col.CURATION_STATUS)
    accepted_mask = pc.equal(curation_col, CurationStatus.ACCEPTED)  # type: ignore[attr-defined]
    rejected_mask = pc.equal(curation_col, CurationStatus.REJECTED)  # type: ignore[attr-defined]
    curated_mask = pc.or_(accepted_mask, rejected_mask)  # type: ignore[attr-defined]
    curated = bool(pc.any(curated_mask).as_py())  # type: ignore[attr-defined]

    return {
        "curated": curated,
        "scope": scope,
        # saturated: SIEMPRE False en one-shot — PO decidió no sobre-afirmar.
        # Gancho futuro: referenced_refs_count() entre rondas de enrich.
        "saturated": False,
        "empty_networks": list(empty_network_kinds),
    }
