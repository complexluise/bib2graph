"""cli.commands.enrich — Subcomando ``b2g enrich`` (alias deprecado, #165).

Enriquece el corpus en dos pasadas usando OpenAlex:
- **Pasada 1 (Hito 8a):** resuelve ``references_id`` → ``references_doi``.
- **Pasada 2 (Hito 8b):** puebla ``cited_by_id`` de las semillas aceptadas
  con los IDs de sus citantes (segundo nivel de fetch, batcheado por OR).

Nota: ``enrich`` NO transiciona el ``CycleState`` del store —el enriquecimiento
es una operación ortogonal al FSM del lazo bibliométrico.  Si en el futuro
se decide transicionar (p. ej. a un estado ENRICHED), se agrega la llamada
a ``apply_transition`` aquí, sin tocar el FSM en el núcleo.

DEPRECADO (ADR 0038, #165): absorbido en ``b2g chain`` / ``b2g build``.
Se retira en 0.11.0.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from bib2graph.cli._deprecation import emit_deprecation
from bib2graph.cli._enrich import enrich_corpus
from bib2graph.cli._envelope import build_envelope, emit, emit_human
from bib2graph.cli._errors import handle_errors
from bib2graph.cli._options import json_mode, json_option
from bib2graph.cli._store import open_store, resolve_library_path

# ---------------------------------------------------------------------------
# Función núcleo (testeable, sin Click)
# ---------------------------------------------------------------------------


def run_enrich(
    store_path: str | Path,
    *,
    email: str | None = None,
    api_key: str | None = None,
    transport: Any = None,
    max_citing: int | None = None,
) -> dict[str, Any]:
    """Enriquece el corpus (refs→DOI y cited_by_id) y persiste el resultado.

    Ejecuta ``OpenAlexEnricher.enrich`` que hace dos pasadas:
    1. Resuelve ``references_id`` → ``references_doi`` (batcheando ≤100 IDs).
    2. Puebla ``cited_by_id`` de las semillas aceptadas (batcheando ≤50 IDs
       con ``cites:`` OR, re-atribuyendo citantes a los seeds que realmente citan).

    Si el corpus no tiene seeds aceptadas ni referencias, termina con 0 sin error.

    Args:
        store_path: Ruta al archivo ``.duckdb``.
        email: Email para el polite pool de OpenAlex.
        api_key: API key opcional de OpenAlex.
        transport: Transport inyectable para tests (``httpx.MockTransport``).
        max_citing: Tope de citantes a registrar en ``cited_by_id`` por paper.
            ``None`` = sin tope.

    Returns:
        Dict con:
          - ``refs_resolved``: IDs de referencia resueltos a DOI.
          - ``refs_total_unique``: Total de references_id únicos en el corpus.
          - ``citing_new``: Nuevos citantes añadidos a ``cited_by_id``.
          - ``citing_targets``: Seeds aceptadas procesadas en pasada 2.
          - ``total_papers``: Número total de papers en el corpus.

    Raises:
        httpx.HTTPError: Si falla la conexión a OpenAlex (capturado por
            ``@handle_errors`` como exit 4).
        StoreError: Si el store está bloqueado (exit 5).
    """
    from bib2graph.sources.openalex import OpenAlexSource

    store = open_store(store_path)
    try:
        corpus = store.load()
        source = OpenAlexSource(email=email, api_key=api_key, transport=transport)
        enriched, metrics = enrich_corpus(
            corpus, source, max_citing=max_citing, pass_name="both"
        )
        store.persist(enriched)
        total_papers = len(enriched)
    finally:
        store.close()

    return {
        "refs_resolved": metrics.get("refs_resolved", 0),
        "refs_total_unique": metrics.get("refs_total_unique", 0),
        "citing_new": metrics.get("citing_new", 0),
        "citing_targets": metrics.get("citing_targets", 0),
        "total_papers": total_papers,
    }


# ---------------------------------------------------------------------------
# Comando Click
# ---------------------------------------------------------------------------


@click.command("enrich")
@click.option(
    "--email",
    default=None,
    help="Email para el polite pool de OpenAlex.",
)
@click.option(
    "--api-key",
    default=None,
    help="API key de OpenAlex (opcional; mejora el rate limit).",
)
@click.option(
    "--max-citing",
    "max_citing",
    default=None,
    type=int,
    help=(
        "Tope de citantes a registrar en cited_by_id por paper. "
        "Default: sin tope (todos los citantes encontrados)."
    ),
)
@json_option
@click.pass_context
@handle_errors("enrich")
def enrich_cmd(
    ctx: click.Context,
    email: str | None,
    api_key: str | None,
    max_citing: int | None,
    json_output: bool,
) -> None:
    """Enriquece el corpus: references→DOI (8a) y cited_by_id (8b).

    Pasada 1: resuelve ``references_id`` → ``references_doi`` consultando OpenAlex.
    Pasada 2: puebla ``cited_by_id`` de las semillas aceptadas con los IDs
    de sus citantes (segundo nivel de fetch, batcheado por OR).

    Si no hay referencias ni semillas aceptadas, termina sin error.
    """
    dep_msg = emit_deprecation("b2g enrich", "b2g chain")
    store_path = resolve_library_path(ctx.obj)
    data = run_enrich(
        store_path,
        email=email,
        api_key=api_key,
        max_citing=max_citing,
    )

    if json_mode(json_output):
        envelope = build_envelope(
            command="enrich",
            ok=True,
            data=data,
            exit_code=0,
            warnings=[dep_msg],
        )
        emit(envelope)
    else:
        emit_human(f"Referencias únicas en corpus: {data['refs_total_unique']}")
        emit_human(f"Referencias resueltas a DOI:  {data['refs_resolved']}")
        emit_human(f"Seeds aceptadas procesadas:   {data['citing_targets']}")
        emit_human(f"Nuevos citantes en cited_by:  {data['citing_new']}")
        emit_human(f"Total de papers en corpus:    {data['total_papers']}")
