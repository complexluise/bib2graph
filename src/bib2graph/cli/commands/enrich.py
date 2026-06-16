"""cli.commands.enrich — Subcomando ``b2g enrich``.

Enriquece el corpus resolviendo ``references_id`` → ``references_doi``
usando OpenAlex.  Persiste el corpus enriquecido en el store.

Hito 8a: solo la resolución references→DOI.
Hito 8b (futuro): poblar ``cited_by_id`` (segundo nivel de fetch).

Nota: ``enrich`` NO transiciona el ``CycleState`` del store —el enriquecimiento
es una operación ortogonal al FSM del lazo bibliométrico.  Si en el futuro
se decide transicionar (p. ej. a un estado ENRICHED), se agrega la llamada
a ``apply_transition`` aquí, sin tocar el FSM en el núcleo.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from bib2graph.cli._envelope import build_envelope, emit, emit_human
from bib2graph.cli._errors import handle_errors
from bib2graph.cli._store import open_store

# ---------------------------------------------------------------------------
# Función núcleo (testeable, sin Click)
# ---------------------------------------------------------------------------


def run_enrich(
    store_path: str | Path,
    *,
    email: str | None = None,
    api_key: str | None = None,
    transport: Any = None,
) -> dict[str, Any]:
    """Enriquece el corpus resolviendo ``references_id`` → ``references_doi``.

    Carga el corpus del store, aplica ``OpenAlexEnricher`` y persiste el
    resultado.  Si el corpus no tiene ``references_id`` en ningún paper,
    termina con 0 resueltas sin error.

    Args:
        store_path: Ruta al archivo ``.duckdb``.
        email: Email para el polite pool de OpenAlex.
        api_key: API key opcional de OpenAlex.
        transport: Transport inyectable para tests (``httpx.MockTransport``).

    Returns:
        Dict con:
          - ``refs_resolved``: IDs de referencia resueltos a DOI.
          - ``refs_total_unique``: Total de references_id únicos en el corpus.
          - ``total_papers``: Número total de papers en el corpus.

    Raises:
        httpx.HTTPError: Si falla la conexión a OpenAlex (capturado por
            ``@handle_errors`` como exit 4).
        StoreError: Si el store está bloqueado (exit 5).
    """
    from bib2graph.enrichers.openalex import OpenAlexEnricher
    from bib2graph.sources.openalex import OpenAlexSource

    store = open_store(store_path)
    corpus = store.load()

    source = OpenAlexSource(email=email, api_key=api_key, transport=transport)
    enricher = OpenAlexEnricher(source)
    enriched = enricher.enrich(corpus)

    store.persist(enriched)

    # Extraer métricas del EnricherRef registrado
    enricher_refs = enriched.manifest.enrichers
    ref_entry = next(
        (e for e in enricher_refs if e.name == "openalex_references_doi"), None
    )
    refs_resolved = int(ref_entry.params.get("resolved", 0)) if ref_entry else 0
    refs_total = int(ref_entry.params.get("total_unique_refs", 0)) if ref_entry else 0

    return {
        "refs_resolved": refs_resolved,
        "refs_total_unique": refs_total,
        "total_papers": len(enriched),
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
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    help="Salida JSON estructurada.",
)
@click.pass_context
@handle_errors("enrich")
def enrich_cmd(
    ctx: click.Context,
    email: str | None,
    api_key: str | None,
    json_output: bool,
) -> None:
    """Enriquece el corpus resolviendo references_id → references_doi (Hito 8a).

    Consulta OpenAlex para obtener los DOIs de las referencias citadas por cada
    paper del corpus y rellena la columna ``references_doi``.

    Si no hay referencias en el corpus, termina con 0 resueltas sin error.
    """
    store_path = ctx.obj["store"]
    data = run_enrich(
        store_path,
        email=email,
        api_key=api_key,
    )

    if json_output:
        envelope = build_envelope(
            command="enrich",
            ok=True,
            data=data,
            exit_code=0,
        )
        emit(envelope)
    else:
        emit_human(f"Referencias únicas en corpus: {data['refs_total_unique']}")
        emit_human(f"Referencias resueltas a DOI:  {data['refs_resolved']}")
        emit_human(f"Total de papers en corpus:    {data['total_papers']}")
