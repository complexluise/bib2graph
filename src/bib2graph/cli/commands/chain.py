"""cli.commands.chain — Subcomando ``b2g chain``.

Expande el corpus con candidatos rankeados por information scent.
Transiciona el CycleState a FORAGED tras persistir con éxito.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal

import click

from bib2graph.cli._enrich import enrich_corpus
from bib2graph.cli._envelope import build_envelope, emit, emit_human
from bib2graph.cli._errors import DataError, DependencyError, UsageError, handle_errors
from bib2graph.cli._ingest import normalize_and_dedup
from bib2graph.cli._options import json_mode, json_option
from bib2graph.cli._store import (
    open_store,
    resolve_workspace,
    workspace_echo,
    workspace_walkup_warning,
)


# Función núcleo (testeable, sin Click)
def run_chain(
    store_path: str | Path,
    *,
    direction: Literal["backward", "forward", "both"] = "both",
    depth: int = 1,
    max_candidates: int | None = None,
    max_citing_per_paper: int | None = 50,
    email: str | None = None,
    transport: Any = None,
    preview: bool = False,
    since: date | None = None,
    _fsm_action: str | None = None,
) -> dict[str, Any]:
    """Expande el corpus con candidatos rankeados por information scent.

    Cuando ``preview=True``, estima el crecimiento potencial **sin fetchear**
    ni transicionar el estado del corpus.  La estimación backward es exacta
    (desde ``references_id``); la forward es exacta si el corpus tiene
    ``cited_by_id`` poblado (pasó por ``b2g enrich`` o un ``chain forward``
    previo, ADR 0048), o indica que se requiere fetch si ``cited_by_id``
    está vacío.

    Args:
        store_path: Ruta al archivo ``.duckdb``.
        direction: Dirección del chaining (``backward``, ``forward``, ``both``).
        depth: Profundidad del chaining (solo 1 soportado; >1 → NotImplementedError).
        max_candidates: Tope de candidatos (None = sin límite).
        max_citing_per_paper: Presupuesto de citantes por semilla en forward
            chaining (default 50; None = sin tope).
        email: Email para el polite pool de OpenAlex.
        transport: Transport inyectable para tests.
        preview: Si ``True``, solo estima el crecimiento sin fetchear ni
            transicionar estado (dry-run).

    Returns:
        Dict con ``candidates_found``, ``total_papers``, ``ranking_preview``
        (modo normal); o con ``preview``, ``estimated_candidates``,
        ``by_direction``, ``capped_by_max``, ``forward_requires_fetch``,
        ``forward_from_cited_by`` (modo preview).  ``candidates_found`` es el
        total de candidatos rankeados (backward observados + forward
        materializados, #269); NO cuenta solo lo materializado en el corpus,
        que en chaining puramente backward siempre da 0 (opción B, #54).

    Raises:
        DependencyError: Si el source no soporta forward chaining.
        NetworkError: Si falla la conexión a OpenAlex.
        StoreError: Si el store está bloqueado.
    """
    if preview:
        return _run_chain_preview(
            store_path,
            direction=direction,
            depth=depth,
            max_candidates=max_candidates,
        )

    if since is not None and direction == "backward":
        raise UsageError(
            "--since no es compatible con --direction backward.  "
            "Usá --direction forward (o 'both', donde la ventana aplica solo al tramo forward)."
        )

    # Cuando since está activo con direction='both', la ventana aplica solo
    # al tramo forward — opción más simple y clara (ADR 0037 §c).
    effective_direction = direction
    if since is not None and direction == "both":
        effective_direction = "forward"

    from bib2graph.cycle import apply_transition
    from bib2graph.foraging import Forager
    from bib2graph.sources.openalex import OpenAlexSource

    # Selección de acción FSM: "monitor" si --since activo O si se fuerza
    # desde run_monitor (_fsm_action="monitor"); sino "chain" → FORAGED.
    fsm_action = (
        _fsm_action
        if _fsm_action is not None
        else ("monitor" if since is not None else "chain")
    )

    merged_backend_close = None
    store = open_store(store_path)
    try:
        corpus = store.load()

        # R3 — fuente única de verdad: el destino de la transición lo dicta cycle.py,
        # no un literal en el comando (ADR 0016 enmendado §1).
        current_state = store.backend.loop_state()
        current_round = store.backend.loop_round()

        # Guarda corpus vacío (portada de monitor, ADR 0037 §c).
        if fsm_action == "monitor":
            if current_state is None:
                raise DataError(
                    "No hay corpus ni estado previo en el store.  "
                    "Iniciá la investigación con 'b2g seed' antes de monitorear."
                )
            if len(corpus) == 0:
                raise DataError(
                    "El corpus está vacío.  "
                    "Usá 'b2g seed' para sembrar papers antes de monitorear."
                )

        new_state, new_round = apply_transition(
            current_state, fsm_action, current_round
        )

        source = OpenAlexSource(email=email, transport=transport)

        # Pre-check explícito: si la dirección requiere forward y el source no
        # tiene ``fetch_citing_batch`` (ni ``fetch_citing`` como fallback), fallamos
        # antes de entrar al Forager — así un ``AttributeError`` genuino que surja
        # dentro de chain/merge/_fetch_forward no queda disfrazado de "source no
        # soporta forward" (exit 3).
        if effective_direction in ("forward", "both") and not (
            hasattr(source, "fetch_citing_batch") or hasattr(source, "fetch_citing")
        ):
            raise DependencyError(
                f"El source {type(source).__name__!r} no soporta forward chaining: "
                "no tiene el método ``fetch_citing_batch`` ni ``fetch_citing``. "
                "Usá un source compatible (p. ej. OpenAlexSource) o cambiá "
                "--direction a 'backward'."
            )

        try:
            forager = Forager(
                source,
                depth=depth,
                max_candidates=max_candidates,
                max_citing_per_paper=max_citing_per_paper,
            )
            ranked = forager.chain(corpus, direction=effective_direction, since=since)
        except NotImplementedError as exc:
            raise DependencyError(
                f"Profundidad {depth} no soportada aún: {exc}. Usá depth=1 (por defecto)."
            ) from exc
        # httpx.HTTPError y subclases (ConnectError, TimeoutException,
        # RemoteProtocolError, TransportError, etc.) se dejan propagar: el
        # decorador @handle_errors las captura por tipo y emite exit 4.
        # AttributeError genuino se propaga limpio (no se disfraza de exit 3).

        # #269: candidates_found debe reflejar el TOTAL de candidatos encontrados
        # por el ranking (backward + forward), no solo las filas materializadas
        # en ranked.corpus. Backward NO materializa filas (opción B, #54): sus IDs
        # viven en ranked.observed_refs / ranked.ranking, así que len(ranked.corpus)
        # da 0 en chaining puramente backward aunque haya miles de candidatos
        # observados — contradiciendo lo que --preview lista. ranked.ranking es la
        # lista completa (recortada solo por --max-candidates, igual que el preview),
        # separada del render truncado a 10 de ranking_preview.
        candidates_found = len(ranked.ranking)
        ranking_preview = [
            {"id": id_, "scent": scent} for id_, scent in ranked.ranking[:10]
        ]
        # Calcular genuinamente nuevos vs corpus (reusado de monitor, ADR 0037 §c).
        existing_ids = set(corpus.to_arrow().column("id").to_pylist())
        new_candidates_count = sum(
            1
            for id_ in ranked.corpus.to_arrow().column("id").to_pylist()
            if id_ not in existing_ids
        )
        # Merge primero, dedup después sobre el corpus COMPLETO (fix cross-biblioteca, #88).
        # Los IDs backward (ranked.observed_refs) NO van al corpus — se persisten en la
        # tabla auxiliar ``referenced_but_not_fetched`` (#54, opción B).
        # El reloj se fija UNA vez por invocación (R2).
        ingest_at = datetime.now(UTC)
        merged = corpus.merge(ranked.corpus)
        merged_deduped = normalize_and_dedup(merged, applied_at=ingest_at)

        # Pasada refs→DOI: enriquecer el corpus mergeado+dedup con el mismo source
        # ya instanciado (forrajeo puro, ADR 0038 §enrich). Automático, sin flag.
        # El source reutiliza la misma conexión HTTP → sin overhead extra.
        merged_deduped, enrich_metrics = enrich_corpus(
            merged_deduped, source, pass_name="refs_doi"
        )

        total_papers = len(merged_deduped)
        merged_backend_close = getattr(merged_deduped._backend, "close", None)
        store.persist_replace(merged_deduped)
        # #141: persistir EnricherRef (refs_doi) para que manifest.enrichers sobreviva.
        store.backend.persist_enricher_refs(merged_deduped.manifest.enrichers)

        # #54: persistir IDs backward observados en la tabla auxiliar.
        if ranked.observed_refs:
            store.backend.add_referenced_refs(
                ranked.observed_refs, cycle_round=new_round
            )

        store.backend.set_loop_state(new_state, cycle_round=new_round)
    finally:
        # Ver run_seed_from_bib: cierra explícitamente las conexiones DuckDB
        # para evitar segfault en Linux ante llamadas consecutivas al mismo archivo.
        if merged_backend_close is not None:
            merged_backend_close()
        store.close()

    return {
        "candidates_found": candidates_found,
        "new_candidates": new_candidates_count,
        "total_papers": total_papers,
        "direction": effective_direction,
        "depth": depth,
        "ranking_preview": ranking_preview,
        "observed_refs_count": len(ranked.observed_refs),
        "loop_state": new_state.value,
        "round": new_round,
        "enrichment": enrich_metrics,
    }


def _run_chain_preview(
    store_path: str | Path,
    *,
    direction: Literal["backward", "forward", "both"],
    depth: int,
    max_candidates: int | None,
) -> dict[str, Any]:
    """Implementación del modo preview (dry-run) de ``run_chain``.

    Estima el crecimiento potencial del corpus **sin hacer fetch ni transicionar
    estado**.  Abre el store, lee el corpus y llama a ``Forager.preview()``.

    Args:
        store_path: Ruta al archivo ``.duckdb``.
        direction: Dirección pedida.
        depth: Profundidad (solo 1 implementado; >1 → DependencyError).
        max_candidates: Tope de candidatos.

    Returns:
        Dict con las claves del envelope de preview (``preview=True``,
        ``estimated_candidates``, ``by_direction``, ``direction``,
        ``capped_by_max``, ``forward_requires_fetch``, ``forward_from_cited_by``).
    """
    from bib2graph.foraging import Forager

    store = open_store(store_path)
    try:
        corpus = store.load()

        try:
            forager = Forager(
                None,  # source no se usa en preview()
                depth=depth,
                max_candidates=max_candidates,
            )
        except NotImplementedError as exc:
            raise DependencyError(
                f"Profundidad {depth} no soportada aún: {exc}. "
                "Usá depth=1 (por defecto)."
            ) from exc

        growth = forager.preview(corpus, direction=direction)
    finally:
        store.close()

    warnings: list[str] = []
    if growth.forward_requires_fetch:
        warnings.append(
            "El crecimiento forward no puede estimarse sin red: el corpus no tiene "
            "``cited_by_id`` poblado.  Ejecutá ``b2g enrich`` primero para obtener "
            "una estimación local, o ejecutá ``b2g chain`` sin ``--preview`` para "
            "traer los citantes directamente."
        )

    return {
        "preview": True,
        "direction": direction,
        "estimated_candidates": growth.estimated_new,
        "by_direction": growth.by_direction,
        "capped_by_max": growth.capped_by_max,
        "forward_requires_fetch": growth.forward_requires_fetch,
        "forward_from_cited_by": growth.forward_from_cited_by,
        "warnings": warnings,
    }


# Comando Click
@click.command("chain")
@click.option(
    "--direction",
    type=click.Choice(["backward", "forward", "both"]),
    default="both",
    show_default=True,
    help="Dirección del chaining.",
)
@click.option(
    "--depth",
    type=int,
    default=1,
    show_default=True,
    help="Profundidad del chaining (solo 1 soportado).",
)
@click.option(
    "--max-candidates",
    type=int,
    default=None,
    help="Tope de candidatos (sin límite por defecto).",
)
@click.option(
    "--max-citing",
    "max_citing_per_paper",
    type=int,
    default=50,
    show_default=True,
    help="Presupuesto de citantes por semilla en forward chaining.",
)
@click.option(
    "--email",
    default=None,
    help="Email para el polite pool de OpenAlex.",
)
@click.option(
    "--preview",
    "preview",
    is_flag=True,
    default=False,
    help=(
        "Estima el crecimiento potencial SIN fetchear ni modificar el corpus "
        "(dry-run).  Backward: exacto desde references_id.  Forward: exacto "
        "si el corpus tiene cited_by_id (requiere enrich previo), si no, "
        "indica que se necesita fetch."
    ),
)
@click.option(
    "--since",
    "since_str",
    default=None,
    help=(
        "Forrajeo incremental: solo trae citantes publicados desde esta fecha.  "
        "Acepta fecha ISO (YYYY-MM-DD) o atajo relativo (90d, 6m, 1y).  "
        "Fuerza direction=forward y transiciona a MONITORED (no a FORAGED).  "
        "Incompatible con --direction backward."
    ),
)
@json_option
@click.pass_context
@handle_errors("chain")
def chain_cmd(
    ctx: click.Context,
    direction: str,
    depth: int,
    max_candidates: int | None,
    max_citing_per_paper: int,
    email: str | None,
    preview: bool,
    since_str: str | None,
    json_output: bool,
) -> None:
    """Expande el corpus con candidatos rankeados por information scent.

    Con --preview (dry-run), solo muestra la estimación de crecimiento sin
    tocar la red ni el corpus.  Sin --preview, transiciona el estado a FORAGED.
    """
    from bib2graph.cli._options import parse_since

    ws = resolve_workspace(ctx.obj)
    store_path = ws.library_path

    # Parsear --since en la frontera (R2/ADR 0017): el reloj se fija aquí.
    since: date | None = None
    if since_str is not None:
        since = parse_since(since_str, now=datetime.now(UTC).date())

    data = run_chain(
        store_path,
        direction=direction,  # type: ignore[arg-type]
        depth=depth,
        max_candidates=max_candidates,
        max_citing_per_paper=max_citing_per_paper,
        email=email,
        preview=preview,
        since=since,
    )

    # ADR 0045 (#259): eco de workspace + warning accionable en walk-up.
    data["workspace"] = workspace_echo(ws)

    if json_mode(json_output):
        envelope = build_envelope(
            command="chain",
            ok=True,
            data=data,
            exit_code=0,
            warnings=list(data.get("warnings", [])) + workspace_walkup_warning(ws),
        )
        emit(envelope)
    elif preview:
        emit_human(f"[preview] Dirección: {data['direction']}")
        emit_human(f"[preview] Candidatos potenciales: {data['estimated_candidates']}")
        for dir_name, count in data["by_direction"].items():
            emit_human(f"  {dir_name}: {count}")
        if data["capped_by_max"]:
            emit_human(f"  (acotado por --max-candidates={max_candidates})")
        for warning in data.get("warnings", []):
            emit_human(f"Aviso: {warning}")
    else:
        emit_human(f"Candidatos encontrados: {data['candidates_found']}")
        emit_human(f"Total en corpus: {data['total_papers']}")
        if data["ranking_preview"]:
            emit_human("Top candidatos por scent:")
            for item in data["ranking_preview"][:5]:
                emit_human(f"  {item['id']}: {item['scent']:.3f}")
