"""cli.commands.seed — Subcomando ``b2g seed``.

Siembra el corpus desde una ecuación de búsqueda en OpenAlex o desde un
YAML declarativo.

Dos modos mutuamente excluyentes (exactamente uno requerido):
  --equation '<texto>'    siembra desde OpenAlex con la ecuación dada.
  --spec equation.yaml    siembra desde OpenAlex con los parámetros del YAML
                          (mismo resultado que ``--equation`` + flags).

R3 — reseed: si ya había un estado previo en el store (no es la primera
siembra), la acción se trata como ``reseed`` → loop-back a SEEDED con
ronda++ (ADR 0016 enmendado).  El corpus acumulado (lo curado) se conserva.

ADR 0030 — capa declarativa: ``--spec`` es equivalente a pasar ``--equation``
con los flags correspondientes; los campos del YAML mapean 1:1 a los argumentos
de ``run_seed``.

Para cargar un corpus curado desde un parquet sin red, usá ``b2g restore``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from bib2graph.cli._envelope import build_envelope, emit, emit_human
from bib2graph.cli._errors import DataError, NetworkError, UsageError, handle_errors
from bib2graph.cli._store import open_store, resolve_library_path

# ---------------------------------------------------------------------------
# Función núcleo: siembra desde OpenAlex (testeable, sin Click)
# ---------------------------------------------------------------------------


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
        min_year: Año mínimo de publicación (filtro opcional).
        max_year: Año máximo de publicación (filtro opcional).

    Returns:
        Dict con ``executed_query``, ``translation_report``, ``papers_added``.

    Raises:
        DataError: Si la ecuación está vacía.
        NetworkError: Si falla la conexión a OpenAlex.
        StoreError: Si el store está bloqueado.
    """
    from bib2graph.cycle import apply_transition
    from bib2graph.sources.openalex import OpenAlexSource

    if not equation or not equation.strip():
        raise DataError("La ecuación de búsqueda no puede estar vacía.")

    store = open_store(store_path)
    existing = store.load()

    # R3 — reseed: si ya había un estado previo, es un re-sembrado.
    # apply_transition lleva la ronda al valor correcto.
    current_state = store.backend.loop_state()
    current_round = store.backend.loop_round()
    if current_state is not None:
        # Re-sembrado (la idea muta): reseed → SEEDED, ronda++
        new_state, new_round = apply_transition(current_state, "reseed", current_round)
    else:
        # Primera siembra
        new_state, new_round = apply_transition(None, "seed", current_round)

    # Construir kwargs opcionales para OpenAlexSource
    source_kwargs: dict[str, Any] = {"email": email, "transport": transport}
    if max_results is not None:
        source_kwargs["max_results"] = max_results

    try:
        source = OpenAlexSource(**source_kwargs)
        # min_year / max_year: reservados en EquationSpec (ADR 0030) pero aún no
        # propagados a OpenAlexSource.seed (que no los acepta todavía). Se
        # aceptan en la firma de run_seed para compatibilidad futura sin romper
        # el contrato público.
        result = source.seed(
            equation,
            native=native,
            exclude=exclude,
        )
    except ImportError as exc:
        raise NetworkError(
            f"Error importando httpx: {exc}. Verificá la instalación del núcleo."
        ) from exc
    # httpx.HTTPError y subclases (ConnectError, TimeoutException,
    # RemoteProtocolError, TransportError, etc.) se dejan propagar: el
    # decorador @handle_errors las captura por tipo y emite exit 4.

    # Merge con el corpus existente (acumula sobre lo curado)
    merged = existing.merge(result.corpus)
    store.persist(merged)
    store.backend.set_loop_state(new_state, cycle_round=new_round)

    papers_added = len(result.corpus)

    return {
        "executed_query": result.executed_query,
        "translation_report": result.translation_report,
        "papers_added": papers_added,
        "total_papers": len(merged),
        "round": new_round,
        "reseeded": current_state is not None,
    }


# ---------------------------------------------------------------------------
# Comando Click (no se testea directamente)
# ---------------------------------------------------------------------------


@click.command("seed")
@click.option(
    "--equation",
    "equation",
    default=None,
    help="Ecuación de búsqueda bibliográfica (modo OpenAlex directo).",
)
@click.option(
    "--spec",
    "spec_path",
    default=None,
    type=click.Path(),
    help=(
        "Ruta a un YAML con la ecuación de búsqueda declarativa "
        "(equation.yaml; mutuamente excluyente con --equation)."
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
    help="Email para el polite pool de OpenAlex (recomendado).",
)
@click.option(
    "--max-results",
    "max_results",
    type=int,
    default=None,
    help="Tope de resultados a traer de OpenAlex, default: 200 (solo con --equation).",
)
@click.option(
    "--exclude",
    "exclude",
    multiple=True,
    help=(
        "Término a excluir del título/abstract (repetible; solo con --equation). "
        'Cada valor agrega AND NOT title_and_abstract.search:"…" al filtro.'
    ),
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    help="Salida JSON estructurada.",
)
@click.pass_context
@handle_errors("seed")
def seed_cmd(
    ctx: click.Context,
    equation: str | None,
    spec_path: str | None,
    native: bool,
    email: str | None,
    max_results: int | None,
    exclude: tuple[str, ...],
    json_output: bool,
) -> None:
    """Siembra el corpus. Exactamente uno de los dos modos es requerido.

    \b
    Modos mutuamente excluyentes:
      --equation '<texto>'    siembra desde OpenAlex con la ecuación dada.
      --spec equation.yaml    siembra desde OpenAlex con parámetros del YAML.

    \b
    Para cargar un corpus curado desde un parquet sin red, usá b2g restore.

    \b
    Tras el seed, el estado del lazo transiciona a SEEDED.

    \b
    Ejemplos:
      b2g seed --equation "unequal exchange"
      b2g seed --spec equation.yaml
    """
    # --- Validar exclusividad de modos ---
    modes_given = sum([equation is not None, spec_path is not None])
    if modes_given == 0:
        raise UsageError(
            "Debés especificar un modo: --equation '<texto>' o --spec <equation.yaml>."
        )
    if modes_given > 1:
        active = []
        if equation is not None:
            active.append("--equation")
        if spec_path is not None:
            active.append("--spec")
        raise UsageError(
            f"Los modos {' y '.join(active)} son mutuamente excluyentes. "
            "Usá exactamente uno por invocación."
        )

    store_path = resolve_library_path(ctx.obj)

    # --- Modo --spec (YAML declarativo) ---
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
        if json_output:
            envelope = build_envelope(
                command="seed",
                ok=True,
                data=data,
                exit_code=0,
                warnings=data.get("translation_report", []),
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

    # --- Modo --equation (directo, comportamiento original) ---
    data = run_seed(
        store_path,
        equation,  # type: ignore[arg-type]  # equation is not None here
        native=native,
        email=email,
        max_results=max_results,
        exclude=list(exclude) if exclude else None,
    )

    if json_output:
        envelope = build_envelope(
            command="seed",
            ok=True,
            data=data,
            exit_code=0,
            warnings=data.get("translation_report", []),
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
