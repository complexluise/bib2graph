"""cli.commands.seed — Subcomando ``b2g seed``.

Siembra el corpus desde una ecuación de búsqueda en OpenAlex, desde un
YAML declarativo, o desde un archivo BibTeX local.

Tres modos mutuamente excluyentes (exactamente uno requerido):
  --equation '<texto>'    siembra desde OpenAlex con la ecuación dada.
  --spec equation.yaml    siembra desde OpenAlex con los parámetros del YAML
                          (mismo resultado que ``--equation`` + flags).
  --from-bib archivo.bib  siembra desde un archivo BibTeX local (sin red).

R3 — reseed: si ya había un estado previo en el store (no es la primera
siembra), la acción se trata como ``reseed`` → loop-back a SEEDED con
ronda++ (ADR 0016 enmendado).  El corpus acumulado (lo curado) se conserva.

ADR 0030 — capa declarativa: ``--spec`` es equivalente a pasar ``--equation``
con los flags correspondientes; los campos del YAML mapean 1:1 a los argumentos
de ``run_seed``.

Para cargar un corpus curado desde un parquet sin red, usá ``b2g snapshot restore``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import click

from bib2graph.cli._envelope import build_envelope, emit, emit_human
from bib2graph.cli._errors import (
    DataError,
    DependencyError,
    NetworkError,
    UsageError,
    handle_errors,
)
from bib2graph.cli._ingest import normalize_and_dedup
from bib2graph.cli._options import json_mode, json_option
from bib2graph.cli._store import (
    open_store,
    resolve_workspace,
    workspace_echo,
    workspace_walkup_warning,
)

# Función núcleo: siembra desde OpenAlex (testeable, sin Click)


def run_seed(
    store_path: str | Path,
    equation: str,
    *,
    native: bool = False,
    email: str | None = None,
    transport: Any = None,
    max_results: int | None = None,
    exclude: list[str] | None = None,
    min_year: int | None = None,
    max_year: int | None = None,
) -> dict[str, Any]:
    """Siembra el corpus desde OpenAlex y persiste en el store.

    Lee el estado actual del store, siembra los papers de la ecuación,
    hace merge con el corpus existente, persiste y transiciona a SEEDED.

    Args:
        store_path: Ruta al archivo ``.duckdb``.
        equation: Ecuación de búsqueda (WoS-style o nativa si ``native=True``).
        native: Si es ``True``, pasa la ecuación cruda a OpenAlex sin traducir.
        email: Email para el polite pool de OpenAlex.
        transport: Transport inyectable para tests (``httpx.MockTransport``).
        max_results: Tope de resultados a traer de OpenAlex (#14).  ``None``
            usa el default del source (200).
        exclude: Términos a excluir del título/abstract vía ``AND NOT`` (#30).
            ``None`` o lista vacía = sin exclusiones.
        min_year: Año mínimo de publicación.  Genera
            ``from_publication_date:<min_year>-01-01`` en el filtro de OpenAlex.
        max_year: Año máximo de publicación.  Genera
            ``to_publication_date:<max_year>-12-31`` en el filtro de OpenAlex.

    Returns:
        Dict con ``executed_query``, ``translation_report``, ``papers_added``,
        ``total_papers``, ``round``, ``reseeded``.

    Raises:
        DataError: Si la ecuación está vacía.
        NetworkError: Si falla la conexión a OpenAlex.
        StoreError: Si el store está bloqueado.
    """
    from bib2graph.cycle import apply_transition
    from bib2graph.sources.openalex import OpenAlexSource

    if not equation or not equation.strip():
        raise DataError("La ecuación de búsqueda no puede estar vacía.")

    merged_backend_close = None
    store = open_store(store_path)
    try:
        existing = store.load()

        # R3 — reseed: si ya había un estado previo, es un re-sembrado.
        current_state = store.backend.loop_state()
        current_round = store.backend.loop_round()
        if current_state is not None:
            # Re-sembrado (la idea muta): reseed → SEEDED, ronda++
            new_state, new_round = apply_transition(
                current_state, "reseed", current_round
            )
        else:
            new_state, new_round = apply_transition(None, "seed", current_round)

        source_kwargs: dict[str, Any] = {"email": email, "transport": transport}
        if max_results is not None:
            source_kwargs["max_results"] = max_results

        try:
            source = OpenAlexSource(**source_kwargs)
            result = source.seed(
                equation,
                native=native,
                exclude=exclude,
                min_year=min_year,
                max_year=max_year,
            )
        except ImportError as exc:
            raise NetworkError(
                f"Error importando httpx: {exc}. Verificá la instalación del núcleo."
            ) from exc
        # httpx.HTTPError y subclases (ConnectError, TimeoutException,
        # RemoteProtocolError, TransportError, etc.) se dejan propagar: el
        # decorador @handle_errors las captura por tipo y emite exit 4.

        # Merge primero, dedup después sobre el corpus COMPLETO (fix bug cross-biblioteca).
        # El reloj se fija UNA vez por invocación (R2).
        ingest_at = datetime.now(UTC)
        merged = existing.merge(result.corpus)
        merged_deduped = normalize_and_dedup(merged, applied_at=ingest_at)
        papers_added = len(result.corpus)
        total_papers = len(merged_deduped)
        # Capturá close() del backend CLONADO (merged._backend, no merged_deduped)
        # normalize_and_dedup devuelve un corpus con InMemoryBackend;
        # el clone DuckDB está en merged._backend (fix #93).
        merged_backend_close = getattr(merged._backend, "close", None)
        store.persist_replace(merged_deduped)
        store.backend.set_loop_state(new_state, cycle_round=new_round)
    finally:
        # Ver run_seed_from_bib: cierra explícitamente las conexiones DuckDB
        # para evitar segfault en Linux ante llamadas consecutivas al mismo archivo.
        if merged_backend_close is not None:
            merged_backend_close()
        store.close()

    return {
        "executed_query": result.executed_query,
        "translation_report": result.translation_report,
        "papers_added": papers_added,
        "total_papers": total_papers,
        "round": new_round,
        "reseeded": current_state is not None,
    }


# Función núcleo: siembra desde BibTeX (testeable, sin Click)


def run_seed_from_bib(
    store_path: str | Path,
    bib_path: str | Path,
    *,
    resolve: bool = False,
    email: str | None = None,
    transport: Any = None,
) -> dict[str, Any]:
    """Siembra el corpus desde un archivo BibTeX y persiste en el store.

    Lee el archivo ``.bib`` con ``BibtexSource.load``, hace merge con el
    corpus existente, persiste y transiciona a SEEDED (o reseed si ya había
    un estado previo, igual que ``run_seed``).

    Sin red: no instancia ``OpenAlexSource`` ni hace requests.  Todos los
    papers cargados quedan con ``is_seed=True`` y
    ``curation_status='candidate'``.

    Si ``resolve=True``, encadena la resolución DOI→source_id después de
    la siembra (llama a ``service.resolve.resolve_dois``).  El ``email``
    se propaga al polite pool de OpenAlex en esa llamada (cierra GAP-2,
    ADR 0035 / issue #112).

    Mapea ``ImportError`` de ``bibtexparser`` a ``DependencyError`` (exit 3),
    igual que el patrón de ``[dedup]``.  El ``ImportError`` de la ruta OpenAlex
    (httpx) NO aplica acá.

    Args:
        store_path: Ruta al archivo ``.duckdb``.
        bib_path: Ruta al archivo ``.bib``.
        resolve: Si es ``True``, encadena la resolución DOI→source_id tras
            la siembra.  Default ``False``.
        email: Email para el polite pool de OpenAlex (solo relevante cuando
            ``resolve=True``).
        transport: Transport inyectable para tests (``httpx.MockTransport``);
            solo relevante cuando ``resolve=True``.

    Returns:
        Dict con ``papers_added``, ``total_papers``, ``round``, ``reseeded``.
        Si ``resolve=True``, suma ``resolve`` con las métricas de resolución.
        No incluye ``executed_query`` ni ``translation_report`` (no aplican
        a BibTeX).

    Raises:
        DependencyError: Si ``bibtexparser`` no está instalado (exit 3).
        DataError: Si el archivo ``.bib`` no existe o está mal formado.
        NetworkError: Si ``resolve=True`` y falla la conexión a OpenAlex.
        StoreError: Si el store está bloqueado.
    """
    from bib2graph.cycle import apply_transition
    from bib2graph.sources.bibtex import BibtexSource

    resolved_bib = Path(bib_path)
    if not resolved_bib.exists():
        raise DataError(
            f"El archivo BibTeX '{resolved_bib}' no existe. "
            "Verificá la ruta al archivo .bib."
        )

    merged_backend_close = None
    store = open_store(store_path)
    resolve_data: dict[str, Any] | None = None
    try:
        existing = store.load()

        # R3 — reseed: misma lógica que run_seed.
        current_state = store.backend.loop_state()
        current_round = store.backend.loop_round()
        if current_state is not None:
            new_state, new_round = apply_transition(
                current_state, "reseed", current_round
            )
        else:
            new_state, new_round = apply_transition(None, "seed", current_round)

        try:
            source = BibtexSource()
            corpus = source.load(str(resolved_bib))
        except ImportError as exc:
            raise DependencyError(
                f"bibtexparser no está instalado: {exc}. "
                "Instalá el extra: uv sync --extra bibtex "
                '(o pip install "bib2graph[bibtex]").'
            ) from exc
        except ValueError as exc:
            raise DataError(str(exc)) from exc

        # Merge primero, dedup después sobre el corpus COMPLETO (fix bug cross-biblioteca).
        # El reloj se fija UNA vez por invocación (R2).
        ingest_at = datetime.now(UTC)
        merged = existing.merge(corpus)
        merged_deduped = normalize_and_dedup(merged, applied_at=ingest_at)
        papers_added = len(corpus)
        total_papers = len(merged_deduped)
        # Capturá close() del backend CLONADO (merged._backend, no merged_deduped)
        # antes de persistir.  normalize_and_dedup devuelve un corpus con
        # InMemoryBackend; el clone DuckDB está en merged._backend (fix #93).
        merged_backend_close = getattr(merged._backend, "close", None)
        store.persist_replace(merged_deduped)
        store.backend.set_loop_state(new_state, cycle_round=new_round)

        # Encadenar resolución DOI→source_id DENTRO del mismo try, con el store
        # ya abierto.  Llamar a resolve_dois(store_path) tras store.close() reabre
        # el mismo .duckdb en el mismo proceso y corrompe las UDFs de DuckDB →
        # segfault (exit 139, #110, #93).  _resolve_dois_on_store opera sobre el
        # store abierto sin ciclo de vida propio.
        if resolve:
            from bib2graph.service.resolve import _resolve_dois_on_store

            resolve_data = _resolve_dois_on_store(
                store, email=email, transport=transport
            )
    finally:
        # Cierra explícitamente TODAS las conexiones DuckDB de esta
        # invocación.  En Linux DuckDB retiene el lock de archivo hasta
        # close() explícito; depender del GC entre llamadas consecutivas
        # sobre el mismo archivo causa segfault (exit 139).
        #
        # merged._backend es una conexión DuckDB CLONADA abierta por
        # Corpus.merge() → DuckDBBackend._clone(); debe cerrarse antes de
        # que la siguiente llamada abra el mismo archivo en disco.
        if merged_backend_close is not None:
            merged_backend_close()
        store.close()

    seed_result: dict[str, Any] = {
        "papers_added": papers_added,
        "total_papers": total_papers,
        "round": new_round,
        "reseeded": current_state is not None,
    }

    if resolve_data is not None:
        seed_result["resolve"] = resolve_data

    return seed_result


def preview_seed_query(
    equation: str,
    *,
    native: bool = False,
    exclude: list[str] | None = None,
    min_year: int | None = None,
    max_year: int | None = None,
) -> dict[str, Any]:
    """Traduce la ecuación a la query de OpenAlex SIN fetchear ni tocar el corpus.

    #287 fricción #2: la semántica AND de ``--equation`` era opaca hasta gastar
    la llamada (el eco ``Query ejecutada:`` llegaba después). Este preview
    (dry-run) devuelve la query ejecutada y el reporte de traducción para que un
    agente razone la ecuación antes de consumir cuota del rate limit.

    Función pura: solo traduce (``_translate``); no abre store ni hace red.

    Returns:
        Dict con ``preview=True``, ``executed_query`` y ``translation_report``.

    Raises:
        DataError: Si la ecuación está vacía.
    """
    from bib2graph.sources.openalex import _translate

    if not equation or not equation.strip():
        raise DataError("La ecuación de búsqueda no puede estar vacía.")

    executed_query, translation_report = _translate(
        equation,
        native=native,
        exclude=exclude,
        min_year=min_year,
        max_year=max_year,
    )
    return {
        "preview": True,
        "executed_query": executed_query,
        "translation_report": translation_report,
    }


# Comando Click


@click.command("seed")
@click.option(
    "--equation",
    "equation",
    default=None,
    help=(
        "Ecuación de búsqueda bibliográfica (modo OpenAlex directo). Los términos "
        "se combinan en AND dentro de title_and_abstract.search: agregar términos "
        "REDUCE los resultados. Usá --preview para ver la query sin gastar la "
        "llamada, o --exclude para AND NOT."
    ),
)
@click.option(
    "--spec",
    "spec_path",
    default=None,
    type=click.Path(),
    help=(
        "Ruta a un YAML con la ecuación de búsqueda declarativa "
        "(equation.yaml; mutuamente excluyente con --equation y --from-bib)."
    ),
)
@click.option(
    "--from-bib",
    "bib_path",
    default=None,
    type=click.Path(),
    help=(
        "Ruta a un archivo BibTeX (.bib) para sembrar sin red "
        "(mutuamente excluyente con --equation y --spec)."
    ),
)
@click.option(
    "--native",
    is_flag=True,
    default=False,
    help="Pasar la ecuación cruda a OpenAlex sin traducción (solo con --equation).",
)
@click.option(
    "--email",
    default=None,
    help="Email para el polite pool de OpenAlex (recomendado; solo con --equation/--spec).",
)
@click.option(
    "--max-results",
    "max_results",
    type=int,
    default=None,
    help="Tope de resultados a traer de OpenAlex, default: 200 (solo con --equation/--spec).",
)
@click.option(
    "--exclude",
    "exclude",
    multiple=True,
    help=(
        "Término a excluir del título/abstract (repetible; solo con --equation/--spec). "
        'Cada valor agrega AND NOT title_and_abstract.search:"…" al filtro.'
    ),
)
@click.option(
    "--min-year",
    "min_year",
    type=int,
    default=None,
    help=(
        "Año mínimo de publicación (solo con --equation/--spec). "
        "Genera from_publication_date:<min_year>-01-01 en el filtro de OpenAlex."
    ),
)
@click.option(
    "--max-year",
    "max_year",
    type=int,
    default=None,
    help=(
        "Año máximo de publicación (solo con --equation/--spec). "
        "Genera to_publication_date:<max_year>-12-31 en el filtro de OpenAlex."
    ),
)
@click.option(
    "--resolve",
    "do_resolve",
    is_flag=True,
    default=False,
    help=(
        "Tras cargar el .bib, resolver DOIs a source_id de OpenAlex "
        "(solo con --from-bib; resuelve automáticamente en la misma invocación)."
    ),
)
@click.option(
    "--preview",
    "preview",
    is_flag=True,
    default=False,
    help=(
        "Muestra la query que se ejecutaría en OpenAlex SIN fetchear ni tocar el "
        "corpus (dry-run; solo con --equation/--spec). Sirve para razonar la "
        "ecuación —los términos van en AND— antes de gastar la llamada."
    ),
)
@json_option
@click.pass_context
@handle_errors("seed")
def seed_cmd(
    ctx: click.Context,
    equation: str | None,
    spec_path: str | None,
    bib_path: str | None,
    native: bool,
    email: str | None,
    max_results: int | None,
    exclude: tuple[str, ...],
    min_year: int | None,
    max_year: int | None,
    do_resolve: bool,
    preview: bool,
    json_output: bool,
) -> None:
    """Siembra el corpus. Exactamente uno de los tres modos es requerido.

    \b
    Modos mutuamente excluyentes:
      --equation '<texto>'    siembra desde OpenAlex con la ecuación dada.
      --spec equation.yaml    siembra desde OpenAlex con parámetros del YAML.
      --from-bib archivo.bib  siembra desde un archivo BibTeX local (sin red).

    \b
    Para cargar un corpus curado desde un parquet sin red, usá b2g snapshot restore.

    \b
    Tras el seed, el estado del lazo transiciona a SEEDED.

    \b
    Ejemplos:
      b2g seed --equation "unequal exchange"
      b2g seed --spec equation.yaml
      b2g seed --from-bib semillas.bib
    """
    modes_given = sum(
        [equation is not None, spec_path is not None, bib_path is not None]
    )
    if modes_given == 0:
        raise UsageError(
            "Debés especificar un modo: --equation '<texto>', --spec <equation.yaml> "
            "o --from-bib <archivo.bib>."
        )
    if modes_given > 1:
        active = []
        if equation is not None:
            active.append("--equation")
        if spec_path is not None:
            active.append("--spec")
        if bib_path is not None:
            active.append("--from-bib")
        raise UsageError(
            f"Los modos {' y '.join(active)} son mutuamente excluyentes. "
            "Usá exactamente uno por invocación."
        )

    # --email se permite con --from-bib cuando se usa junto a --resolve (cierra GAP-2 / #112).
    if bib_path is not None:
        openalex_flags_usados: list[str] = []
        if native:
            openalex_flags_usados.append("--native")
        if max_results is not None:
            openalex_flags_usados.append("--max-results")
        if exclude:
            openalex_flags_usados.append("--exclude")
        if min_year is not None:
            openalex_flags_usados.append("--min-year")
        if max_year is not None:
            openalex_flags_usados.append("--max-year")
        if openalex_flags_usados:
            raise UsageError(
                f"Los flags {', '.join(openalex_flags_usados)} son exclusivos del modo "
                "OpenAlex (--equation/--spec) y no pueden usarse con --from-bib."
            )
        if email is not None and not do_resolve:
            raise UsageError(
                "--email con --from-bib requiere --resolve (el email se usa en la "
                "resolución DOI→source_id). "
                "Usá: b2g seed --from-bib <archivo> --resolve --email <tu@email.com>"
            )
    else:
        if do_resolve:
            raise UsageError(
                "--resolve solo es válido con --from-bib. "
                "Para un corpus existente, corré b2g seed --from-bib <archivo> --resolve "
                "de nuevo (idempotente: solo resuelve los DOIs pendientes)."
            )

    # #287 fricción #2: --preview traduce y muestra la query sin fetchear ni
    # tocar el corpus (dry-run). Corta antes de resolver workspace: es puro.
    if preview:
        if bib_path is not None:
            raise UsageError(
                "--preview no aplica a --from-bib (no hay query que traducir). "
                "Usalo con --equation o --spec."
            )
        if spec_path is not None:
            from bib2graph.sources.equation import load_equation_spec

            try:
                spec = load_equation_spec(spec_path)
            except (ValueError, FileNotFoundError) as exc:
                raise DataError(str(exc)) from exc
            data = preview_seed_query(
                spec.query,
                native=spec.native,
                exclude=spec.exclude if spec.exclude else None,
                min_year=spec.min_year,
                max_year=spec.max_year,
            )
        else:
            data = preview_seed_query(
                equation,  # type: ignore[arg-type]  # equation is not None here
                native=native,
                exclude=list(exclude) if exclude else None,
                min_year=min_year,
                max_year=max_year,
            )
        if json_mode(json_output):
            envelope = build_envelope(
                command="seed",
                ok=True,
                data=data,
                exit_code=0,
                warnings=list(data.get("translation_report", [])) or None,
            )
            emit(envelope)
        else:
            emit_human(f"[preview] Query que se ejecutaría: {data['executed_query']}")
            emit_human(
                "[preview] Los términos van en AND: agregar términos reduce los "
                "resultados. No se fetcheó nada ni se tocó el corpus."
            )
            if data.get("translation_report"):
                emit_human("Advertencias de traducción:")
                for w in data["translation_report"]:
                    emit_human(f"  - {w}")
        return

    ws = resolve_workspace(ctx.obj)
    store_path = ws.library_path
    ws_warnings = workspace_walkup_warning(ws)

    if bib_path is not None:
        data = run_seed_from_bib(store_path, bib_path, resolve=do_resolve, email=email)
        data["workspace"] = workspace_echo(ws)
        if json_mode(json_output):
            envelope = build_envelope(
                command="seed",
                ok=True,
                data=data,
                exit_code=0,
                warnings=ws_warnings or None,
            )
            emit(envelope)
        else:
            emit_human(f"Sembrados {data['papers_added']} papers nuevos desde BibTeX.")
            emit_human(f"Total en corpus: {data['total_papers']}")
            if do_resolve and "resolve" in data:
                r = data["resolve"]
                emit_human(
                    f"Resolución DOI→source_id: "
                    f"{r['resolved']} resueltos de {r['total_with_doi']} con DOI."
                )
        return

    if spec_path is not None:
        from bib2graph.sources.equation import load_equation_spec

        try:
            spec = load_equation_spec(spec_path)
        except (ValueError, FileNotFoundError) as exc:
            raise DataError(str(exc)) from exc

        data = run_seed(
            store_path,
            spec.query,
            native=spec.native,
            email=email,
            max_results=spec.max_results,
            exclude=spec.exclude if spec.exclude else None,
            min_year=spec.min_year,
            max_year=spec.max_year,
        )
        data["workspace"] = workspace_echo(ws)
        if json_mode(json_output):
            envelope = build_envelope(
                command="seed",
                ok=True,
                data=data,
                exit_code=0,
                warnings=list(data.get("translation_report", [])) + ws_warnings,
            )
            emit(envelope)
        else:
            emit_human(f"Sembrados {data['papers_added']} papers nuevos.")
            emit_human(f"Query ejecutada: {data['executed_query']}")
            if data.get("translation_report"):
                emit_human("Advertencias de traducción:")
                for w in data["translation_report"]:
                    emit_human(f"  - {w}")
            emit_human(f"Total en corpus: {data['total_papers']}")
        return

    data = run_seed(
        store_path,
        equation,  # type: ignore[arg-type]  # equation is not None here
        native=native,
        email=email,
        max_results=max_results,
        exclude=list(exclude) if exclude else None,
        min_year=min_year,
        max_year=max_year,
    )
    data["workspace"] = workspace_echo(ws)

    if json_mode(json_output):
        envelope = build_envelope(
            command="seed",
            ok=True,
            data=data,
            exit_code=0,
            warnings=list(data.get("translation_report", [])) + ws_warnings,
        )
        emit(envelope)
    else:
        emit_human(f"Sembrados {data['papers_added']} papers nuevos.")
        emit_human(f"Query ejecutada: {data['executed_query']}")
        if data.get("translation_report"):
            emit_human("Advertencias de traducción:")
            for w in data["translation_report"]:
                emit_human(f"  - {w}")
        emit_human(f"Total en corpus: {data['total_papers']}")
