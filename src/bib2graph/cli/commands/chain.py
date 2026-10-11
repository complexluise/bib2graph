"""cli.commands.chain — Subcomando ``b2g chain``.

Expande el corpus con candidatos rankeados por information scent.
Transiciona el CycleState a FORAGED tras persistir con éxito.

**Guardarraíles anti-footgun (#309):** el forrajeo forward es multiplicativo
(cada semilla dispara sus propias llamadas HTTP) y su costo es invisible hasta
que ya se gastó — un ``chain`` sin acotar sobre cientos de semillas puede
agotar la cuota de OpenAlex (429 account-wide, recuperación de horas).  Este
módulo agrega, TODOS aditivos (no cambian el default sin acotar, ver
Discussion #310):

- ``--ids``/``--top``/``--scope``: acotan la **unidad escopada** — de qué
  papers-origen se forrajea (ver ``_resolve_origin_ids``).
- ``--preview``: dry-run que estima el fanout sin fetchear (ya existía,
  ahora también refleja el scoping).
- ``--budget``: tope de llamadas HTTP; al alcanzarlo, para y reporta parcial
  SIN reintentar (ver ``foraging.base.CallBudget``).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

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
from bib2graph.constants import Col

if TYPE_CHECKING:
    from bib2graph.corpus import Corpus

# Mapea el vocab de --scope (CLI) al vocab interno de corpus.scoped() —
# mismo patrón que build.py._map_scope (#309, reusa Corpus.scoped, ADR
# consistente con el resto del CLI: --scope usa 'seeds', scoped() 'seeds_only').
_SCOPE_TO_INTERNAL = {"all": "all", "accepted": "accepted", "seeds": "seeds_only"}


def _resolve_origin_ids(
    corpus: Corpus,
    *,
    ids: tuple[str, ...],
    top: int | None,
    scope: str | None,
) -> set[str] | None:
    """Resuelve la unidad escopada del forrajeo (#309) a un set de ids.

    Los tres flags (``--ids``, ``--top``, ``--scope``) son mutuamente
    excluyentes en este MVP: combinar dos criterios de acotamiento distintos
    (p. ej. "estos 3 IDs" + "los 10 más centrales") no tiene una semántica
    obvia sin más contexto de producto — se deja para una iteración futura si
    hay necesidad real (ver Discussion #310).

    Args:
        corpus: Corpus cargado del store.
        ids: IDs explícitos de ``--ids`` (tupla vacía = no se usó el flag).
        top: Valor de ``--top`` (``None`` = no se usó el flag).
        scope: Valor de ``--scope`` (``None`` = no se usó el flag).

    Returns:
        Set de ``id``/``source_id`` a los que acotar el chaining, o ``None``
        si no se pasó ningún flag de scoping — comportamiento ACTUAL sin
        cambios: todas las semillas (#309, DoD "no cambiar los defaults").

    Raises:
        UsageError: Si se combina más de un flag de scoping, si ``--ids``
            referencia IDs que no existen en el corpus, o si ``--top`` es
            <= 0.
    """
    flags_used = sum([bool(ids), top is not None, scope is not None])
    if flags_used > 1:
        raise UsageError(
            "--ids, --top y --scope son mutuamente excluyentes: elegí UN "
            "criterio para acotar la unidad escopada del forrajeo."
        )
    if flags_used == 0:
        return None

    if ids:
        corpus_ids: set[str] = set()
        rows = corpus.to_arrow().to_pylist()
        for row in rows:
            if row.get(Col.ID):
                corpus_ids.add(str(row[Col.ID]))
            if row.get(Col.SOURCE_ID):
                corpus_ids.add(str(row[Col.SOURCE_ID]))
        missing = [id_ for id_ in ids if id_ not in corpus_ids]
        if missing:
            raise UsageError(
                f"--ids referencia {len(missing)} id(s) que no están en el "
                f"corpus: {missing}. Verificá los IDs con 'b2g read' o quitalos."
            )
        return set(ids)

    if top is not None:
        if top <= 0:
            raise UsageError(f"--top debe ser un entero positivo (recibido {top}).")
        return _top_n_seed_ids(corpus, top)

    assert scope is not None  # flags_used == 1 y ni ids ni top: debe ser scope
    internal_scope = _SCOPE_TO_INTERNAL.get(scope)
    if internal_scope is None:
        raise UsageError(f"--scope '{scope}' no reconocido. Usá: all, accepted, seeds.")
    scoped_corpus = corpus.scoped(internal_scope)
    scoped_rows = scoped_corpus.to_arrow().to_pylist()
    result: set[str] = set()
    for row in scoped_rows:
        if row.get(Col.ID):
            result.add(str(row[Col.ID]))
        if row.get(Col.SOURCE_ID):
            result.add(str(row[Col.SOURCE_ID]))
    return result


def _top_n_seed_ids(corpus: Corpus, top: int) -> set[str]:
    """Resuelve ``--top N``: las N semillas más "centrales" del corpus.

    **Criterio (#309):** nº de referencias (``len(references_id)``) como
    proxy simple de centralidad — una semilla con más referencias listadas
    tiene más superficie de acoplamiento bibliográfico potencial (backward) y
    tiende a ser un hub más citado en su propio campo.  Es una **degradación
    documentada** del criterio ideal (centralidad de acople sobre el grafo
    construido por ``b2g build``): no requiere un build previo ni artefactos
    en disco, es puro y determinista.  Si se necesita la centralidad real del
    acoplamiento bibliográfico, correr ``b2g build`` y usar ``--scope``/
    ``--ids`` con los IDs más centrales del ``metrics.json`` resultante.

    Desempate: ``id`` ascendente (mismo criterio de estabilidad que
    ``foraging.scent.rank_candidates``).

    Args:
        corpus: Corpus cargado del store.
        top: Cuántas semillas devolver (ya validado > 0 por el llamador).

    Returns:
        Set de ``id`` (no ``source_id``: alcanza para acotar, ``_resolve_origin_ids``
        ya matchea contra ambos en el llamador de ``Forager``) de las ``top``
        semillas con más referencias.  Si hay menos de ``top`` semillas, se
        devuelven todas.
    """
    rows = corpus.to_arrow().to_pylist()
    seed_rows = [row for row in rows if row.get(Col.IS_SEED)]
    ranked = sorted(
        seed_rows,
        key=lambda row: (
            -len(row.get(Col.REFERENCES_ID) or []),
            str(row.get(Col.ID)),
        ),
    )
    return {str(row[Col.ID]) for row in ranked[:top] if row.get(Col.ID)}


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
    ids: tuple[str, ...] = (),
    top: int | None = None,
    scope: str | None = None,
    budget: int | None = None,
    _fsm_action: str | None = None,
) -> dict[str, Any]:
    """Expande el corpus con candidatos rankeados por information scent.

    Cuando ``preview=True``, estima el crecimiento potencial **sin fetchear**
    ni transicionar el estado del corpus.  La estimación backward es exacta
    (desde ``references_id``); la forward es exacta si el corpus tiene
    ``cited_by_id`` poblado (por un ``chain forward`` previo o la pasada
    cited_by de ``build``, ADR 0048), o indica que se requiere fetch si
    ``cited_by_id`` está vacío.

    **Unidad escopada (#309):** ``ids``/``top``/``scope`` acotan de qué
    papers-origen se forrajea (mutuamente excluyentes, ver
    ``_resolve_origin_ids``).  Si no se pasa ninguno, comportamiento ACTUAL
    sin cambios: todas las semillas.

    **Budget (#309):** ``budget`` topa las llamadas HTTP del forward
    chaining.  Al alcanzarlo, el forrajeo **para limpio (sin reintentar)** y
    el resultado queda marcado como parcial (``result["budget_stopped"]``).

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
        ids: IDs explícitos de papers-origen (``--ids``, repetible).  Tupla
            vacía (default) = no acota.
        top: Acota a las ``top`` semillas más "centrales" (``--top``, ver
            ``_top_n_seed_ids``).  ``None`` (default) = no acota.
        scope: Acota al subconjunto ``all``/``accepted``/``seeds`` del
            corpus (``--scope``, reusa ``Corpus.scoped``).  ``None``
            (default) = no acota.
        budget: Tope de llamadas HTTP a OpenAlex (``--budget``).  ``None``
            (default) = sin tope (comportamiento actual).

    Returns:
        Dict con ``candidates_found``, ``total_papers``, ``ranking_preview``,
        ``budget_used``, ``budget_stopped`` (modo normal); o con ``preview``,
        ``estimated_candidates``, ``by_direction``, ``capped_by_max``,
        ``forward_requires_fetch``, ``forward_from_cited_by``, ``origin_count``
        (modo preview).  ``candidates_found`` es el total de candidatos
        rankeados (backward observados + forward materializados, #269); NO
        cuenta solo lo materializado en el corpus, que en chaining puramente
        backward siempre da 0 (opción B, #54).

    Raises:
        UsageError: Si se combina más de un flag de scoping, o si
            ``--ids``/``--top`` son inválidos.
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
            ids=ids,
            top=top,
            scope=scope,
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
    from bib2graph.foraging import CallBudget, Forager
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

        # Unidad escopada (#309): resuelve --ids/--top/--scope contra el
        # corpus ANTES de tocar la red. None = comportamiento actual (todas
        # las semillas), sin cambios.
        origin_ids = _resolve_origin_ids(corpus, ids=ids, top=top, scope=scope)
        call_budget = CallBudget(budget) if budget is not None else None

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
                origin_ids=origin_ids,
                call_budget=call_budget,
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
        # #309: budget del forward chaining (llamadas HTTP a /works para
        # traer citantes).  NO incluye las llamadas de la pasada refs_doi
        # posterior (acotada, bajo impacto — fuera de alcance del budget).
        "budget_used": ranked.budget_used,
        "budget_stopped": ranked.budget_stopped,
    }


def _run_chain_preview(
    store_path: str | Path,
    *,
    direction: Literal["backward", "forward", "both"],
    depth: int,
    max_candidates: int | None,
    ids: tuple[str, ...] = (),
    top: int | None = None,
    scope: str | None = None,
) -> dict[str, Any]:
    """Implementación del modo preview (dry-run) de ``run_chain``.

    Estima el crecimiento potencial del corpus **sin hacer fetch ni transicionar
    estado**.  Abre el store, lee el corpus y llama a ``Forager.preview()``.

    Con ``--ids``/``--top``/``--scope`` (#309), la estimación de fanout se
    acota al subconjunto de papers-origen resuelto — el preview refleja
    fielmente lo que haría el ``chain`` real subsecuente sin ``--preview``.

    Args:
        store_path: Ruta al archivo ``.duckdb``.
        direction: Dirección pedida.
        depth: Profundidad (solo 1 implementado; >1 → DependencyError).
        max_candidates: Tope de candidatos.
        ids: IDs explícitos de papers-origen (``--ids``).
        top: Acota a las ``top`` semillas más "centrales" (``--top``).
        scope: Acota al scope ``all``/``accepted``/``seeds`` (``--scope``).

    Returns:
        Dict con las claves del envelope de preview (``preview=True``,
        ``estimated_candidates``, ``by_direction``, ``direction``,
        ``capped_by_max``, ``forward_requires_fetch``, ``forward_from_cited_by``,
        ``origin_count``: cuántos papers-origen participan del fanout estimado).
    """
    from bib2graph.foraging import Forager

    store = open_store(store_path)
    try:
        corpus = store.load()

        origin_ids = _resolve_origin_ids(corpus, ids=ids, top=top, scope=scope)
        rows = corpus.to_arrow().to_pylist()
        if origin_ids is not None:
            # Contar PAPERS (filas), no entradas del set (que incluye tanto
            # id como source_id por paper — contar el set duplicaría).
            origin_count = sum(
                1
                for row in rows
                if str(row.get(Col.ID)) in origin_ids
                or str(row.get(Col.SOURCE_ID)) in origin_ids
            )
        else:
            # Comportamiento actual sin scoping: origen = todas las semillas.
            origin_count = sum(1 for row in rows if row.get(Col.IS_SEED))

        try:
            forager = Forager(
                None,  # source no se usa en preview()
                depth=depth,
                max_candidates=max_candidates,
                origin_ids=origin_ids,
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
            "``cited_by_id`` poblado.  Ejecutá ``b2g build`` primero para obtener "
            "una estimación local (puebla cited_by_id de las semillas aceptadas), "
            "o ejecutá ``b2g chain`` sin ``--preview`` para traer los citantes "
            "directamente."
        )

    return {
        "preview": True,
        "direction": direction,
        "estimated_candidates": growth.estimated_new,
        "by_direction": growth.by_direction,
        "capped_by_max": growth.capped_by_max,
        "forward_requires_fetch": growth.forward_requires_fetch,
        "forward_from_cited_by": growth.forward_from_cited_by,
        # #309: cuántos papers-origen participan del fanout estimado (todas
        # las semillas si no se pasó --ids/--top/--scope).
        "origin_count": origin_count,
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
        "si el corpus tiene cited_by_id (poblado por un chain forward previo), "
        "si no, indica que se necesita fetch."
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
@click.option(
    "--ids",
    "ids",
    multiple=True,
    help=(
        "Forrajea SOLO desde estos papers-origen (repetible: --ids ID1 --ids ID2). "
        "Mutuamente excluyente con --top/--scope.  Sin este flag (default): "
        "todas las semillas (comportamiento actual, sin cambios)."
    ),
)
@click.option(
    "--top",
    "top",
    type=int,
    default=None,
    help=(
        "Forrajea desde las N semillas más 'centrales' (criterio: nº de "
        "referencias, ver docstring de _top_n_seed_ids). "
        "Mutuamente excluyente con --ids/--scope."
    ),
)
@click.option(
    "--scope",
    "scope",
    type=click.Choice(["all", "accepted", "seeds"]),
    default=None,
    help=(
        "Forrajea desde este subconjunto del corpus (reusa Corpus.scoped). "
        "Mutuamente excluyente con --ids/--top."
    ),
)
@click.option(
    "--budget",
    "budget",
    type=int,
    default=None,
    help=(
        "Tope de llamadas HTTP a OpenAlex para el forward chaining.  Al "
        "alcanzarlo, PARA y reporta el estado parcial (papers materializados, "
        "budget usado) — nunca reintenta.  Sin límite por defecto."
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
    ids: tuple[str, ...],
    top: int | None,
    scope: str | None,
    budget: int | None,
    json_output: bool,
) -> None:
    """Expande el corpus con candidatos rankeados por information scent.

    Con --preview (dry-run), solo muestra la estimación de crecimiento sin
    tocar la red ni el corpus.  Sin --preview, transiciona el estado a FORAGED.

    Guardarraíles anti-footgun (#309): --ids/--top/--scope acotan de qué
    papers-origen se forrajea (sin ninguno: todas las semillas, igual que
    siempre); --budget topa las llamadas HTTP y para limpio al agotarse.
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
        ids=ids,
        top=top,
        scope=scope,
        budget=budget,
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
        emit_human(f"[preview] Papers-origen: {data['origin_count']}")
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
        if data.get("budget_stopped"):
            emit_human(
                f"Aviso: se alcanzó --budget ({data['budget_used']} llamadas). "
                "El resultado es PARCIAL — corré 'b2g chain' de nuevo (o con "
                "--ids/--top/--scope más acotado) para completar el forrajeo."
            )
