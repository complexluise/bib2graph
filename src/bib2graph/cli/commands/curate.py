"""cli.commands.curate — Subcomando ``b2g curate``.

Curación en lote (#22 dump + #26 import): permite revisar y marcar papers
en una tabla externa (Excel/Calc) y reimportar las decisiones al corpus.

Flujo canónico:
    b2g curate --dump                   # exporta <workspace>/exports/curacion.csv
    b2g curate --dump --out mi.csv      # override de ruta de salida
    b2g curate --dump --all             # incluye también aceptados y rechazados
    b2g curate --from-csv mi.csv        # reimporta las decisiones del CSV

El CSV que ``--dump`` produce tiene exactamente las columnas que ``--from-csv``
lee, lo que garantiza el round-trip sin fricción.

Columnas:
    id           — identificador canónico del paper (readonly)
    openalex_id  — identificador OpenAlex (readonly)
    title        — título (readonly)
    year         — año de publicación (readonly)
    authors      — lista de autores separada por \" | \" (readonly)
    scent_score  — best-effort desde provenance del candidato; vacío si no hay
    cluster      — reservado para futura integración de redes; siempre vacío hoy
    decision     — editable: accepted | rejected | undecided
    note         — editable: texto libre, advisory (round-trip solo)

``note`` es advisory:
    ``ProvenanceEvent`` no tiene un campo genérico de anotación. Registrar la
    nota en ``decided_by`` (el único campo libre en provenance) contaminaría
    semántica. Por lo tanto la nota se preserva en el CSV (round-trip) pero
    NO se persiste en el corpus. El docstring lo declara explícitamente.

``scent_score`` best-effort:
    Si hay eventos de chaining en el provenance del paper, se lee el campo
    ``scent`` que el Forager puede haber guardado. Si no existe, queda vacío.
    No se falla por ausencia.

``cluster`` best-effort:
    Reservado para cuando los grafos de red estén disponibles. Siempre vacío
    en esta versión. No se falla por ausencia.

Idempotencia:
    Reimportar el mismo CSV produce el mismo estado. ``accept``/``reject`` del
    Corpus son idempotentes (``apply_curation`` en el backend verifica el id).

R2 (ADR 0017 enmendado):
    ``decided_at`` se inyecta en la frontera CLI (aquí), no en el núcleo.
    El hash del Corpus excluye timestamps de provenance.

CURACIÓN TRANSVERSAL (ADR 0016 enmendado, R3):
    ``curate`` es curación transversal: no transiciona el CycleState.
    Disponible en cualquier estado del lazo.
"""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import click

from bib2graph.cli._envelope import build_envelope, emit, emit_human
from bib2graph.cli._errors import DataError, UsageError, handle_errors
from bib2graph.cli._store import open_store, resolve_workspace
from bib2graph.constants import Col, CurationStatus

# ---------------------------------------------------------------------------
# Constantes del CSV de curación
# ---------------------------------------------------------------------------

CURATE_CSV_FILENAME = "curacion.csv"

# Columnas del CSV: orden estable y conocido por el humano y la reimportación.
CSV_COLUMNS = [
    "id",
    "openalex_id",
    "title",
    "year",
    "authors",
    "scent_score",
    "cluster",
    "decision",
    "note",
]

# Columnas requeridas para que ``--from-csv`` acepte el archivo.
CSV_REQUIRED_COLUMNS = {"id", "decision"}

# Valores válidos para la columna ``decision``.
VALID_DECISIONS = {
    CurationStatus.ACCEPTED,
    CurationStatus.REJECTED,
    "undecided",
}

# Mapa de curation_status → decision en el dump
_STATUS_TO_DECISION: dict[str, str] = {
    CurationStatus.CANDIDATE: "undecided",
    CurationStatus.ACCEPTED: "accepted",
    CurationStatus.REJECTED: "rejected",
}


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _authors_display(row: dict[str, Any]) -> str:
    """Extrae los autores de una fila del corpus y los une con ' | '.

    Usa ``authors_raw`` si disponible, ``authors_id`` como fallback.
    Devuelve cadena vacía si no hay datos.

    Args:
        row: Fila de la tabla Arrow convertida a dict.

    Returns:
        Cadena de autores separada por \" | \" o cadena vacía.
    """
    raw = row.get(Col.AUTHORS_RAW)
    if raw and isinstance(raw, list):
        return " | ".join(str(a) for a in raw if a)
    ids = row.get(Col.AUTHORS_ID)
    if ids and isinstance(ids, list):
        return " | ".join(str(a) for a in ids if a)
    return ""


def _scent_score_display(row: dict[str, Any]) -> str:
    """Extrae el scent_score del provenance si está disponible.

    El Forager puede haber guardado un campo ``scent`` en provenance.
    Esta función lo busca en el JSON de provenance. Si no existe, devuelve
    cadena vacía (best-effort, no falla).

    Args:
        row: Fila de la tabla Arrow convertida a dict.

    Returns:
        Valor de scent como string, o cadena vacía.
    """
    import json

    provenance_raw = row.get(Col.PROVENANCE)
    if not provenance_raw:
        return ""
    try:
        events = json.loads(str(provenance_raw))
        if not isinstance(events, list):
            return ""
        # Buscar el campo 'scent' en cualquier evento
        for event in events:
            if isinstance(event, dict):
                val = event.get("scent")
                if val is not None:
                    return str(val)
    except (json.JSONDecodeError, TypeError):
        pass
    return ""


def _row_to_csv_dict(row: dict[str, Any]) -> dict[str, str]:
    """Convierte una fila del corpus al dict para el CSV de curación.

    Args:
        row: Fila de la tabla Arrow convertida a dict.

    Returns:
        Dict con las columnas del CSV de curación, todas como strings.
    """
    status = str(row.get(Col.CURATION_STATUS, CurationStatus.CANDIDATE))
    decision = _STATUS_TO_DECISION.get(status, "undecided")

    return {
        "id": str(row.get(Col.ID) or ""),
        "openalex_id": str(row.get(Col.OPENALEX_ID) or ""),
        "title": str(row.get(Col.TITLE) or ""),
        "year": str(row.get(Col.YEAR) or ""),
        "authors": _authors_display(row),
        "scent_score": _scent_score_display(row),
        "cluster": "",  # reservado para integración con redes
        "decision": decision,
        "note": "",
    }


# ---------------------------------------------------------------------------
# Función núcleo: dump
# ---------------------------------------------------------------------------


def run_curate_dump(
    store_path: str | Path,
    *,
    out_path: Path,
    include_all: bool = False,
) -> dict[str, Any]:
    """Exporta el corpus a un CSV para revisión offline.

    Por defecto exporta solo los candidatos (``curation_status == 'candidate'``).
    Con ``include_all=True`` exporta todos los papers del corpus.

    Columnas del CSV: id, openalex_id, title, year, authors, scent_score,
    cluster, decision, note. La columna ``decision`` refleja el
    ``curation_status`` actual (candidate → undecided). Las columnas
    ``decision`` y ``note`` son las editables por el humano.

    ``scent_score`` y ``cluster`` son best-effort: se incluyen si están
    disponibles en el provenance; si no, quedan vacíos.

    Args:
        store_path: Ruta al archivo ``.duckdb``.
        out_path: Ruta completa del archivo CSV de salida.
        include_all: Si True, incluye todos los papers; si False (default),
            solo los candidatos.

    Returns:
        Dict con ``csv_path``, ``papers_exported``, ``columns``.

    Raises:
        DataError: Si el corpus está vacío o no hay papers candidatos y
            ``include_all`` es False.
        StoreError: Si el store está bloqueado.
    """
    store = open_store(store_path)
    corpus = store.load()

    table = corpus.to_arrow() if include_all else corpus.candidates()

    rows = table.to_pylist()

    if not rows and not include_all:
        raise DataError(
            "No hay papers candidatos para exportar. "
            "Usá --all para exportar todo el corpus, o ejecutá "
            "``b2g chain`` para agregar candidatos."
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(_row_to_csv_dict(row))

    return {
        "csv_path": str(out_path),
        "papers_exported": len(rows),
        "columns": CSV_COLUMNS,
    }


# ---------------------------------------------------------------------------
# Función núcleo: from-csv
# ---------------------------------------------------------------------------


def run_curate_from_csv(
    store_path: str | Path,
    csv_path: str | Path,
    *,
    by: str = "cli",
    decided_at: datetime | None = None,
) -> dict[str, Any]:
    """Reimporta decisiones de curación desde un CSV al corpus.

    Lee el CSV producido por ``--dump`` (u otro CSV con columnas ``id`` y
    ``decision``), aplica las decisiones en lote e persiste.

    Mapeo de ``decision``:
      - ``accepted``  → ``Corpus.accept``
      - ``rejected``  → ``Corpus.reject``
      - ``undecided`` → no-op (el paper conserva su estado actual)

    Idempotente: reimportar el mismo CSV produce el mismo estado final.

    ``note``: advisory — no se persiste en el corpus (``ProvenanceEvent``
    no tiene campo de anotación genérico). La nota solo hace round-trip en
    el CSV; se ignora silenciosamente al importar.

    R2 (ADR 0017 enmendado): ``decided_at`` se inyecta desde la frontera CLI
    (la función que llama); el núcleo no llama al reloj.

    Args:
        store_path: Ruta al archivo ``.duckdb``.
        csv_path: Ruta al archivo CSV con las decisiones.
        by: Identificador de quien decide (default: ``"cli"``).
        decided_at: Timestamp de la decisión inyectado desde la frontera.
            Si es ``None``, el backend usa ``datetime.now(UTC)`` como fallback.

    Returns:
        Dict con ``accepted_count``, ``rejected_count``, ``skipped_count``,
        ``not_found_count``, ``total_rows``.

        ``accepted_count`` y ``rejected_count`` reflejan papers **efectivamente
        encontrados y marcados** en el corpus, no filas del CSV.
        ``not_found_count`` cuenta IDs del CSV que no existían en el corpus
        (huérfanos — se reportan sin abortar para preservar la idempotencia
        del flujo batch).

    Raises:
        DataError: Si el CSV no existe, le faltan columnas requeridas
            (``id``, ``decision``), o contiene valores de ``decision`` inválidos.
        StoreError: Si el store está bloqueado.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise DataError(
            f"El archivo CSV '{csv_path}' no existe. "
            "Generalo primero con ``b2g curate --dump``."
        )

    # Leer y validar el CSV
    rows: list[dict[str, str]] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = set(reader.fieldnames or [])

        missing = CSV_REQUIRED_COLUMNS - fieldnames
        if missing:
            raise DataError(
                f"El CSV '{csv_path}' no tiene las columnas requeridas: "
                f"{sorted(missing)}. "
                "Asegurate de exportar con ``b2g curate --dump`` y no borrar "
                "las columnas obligatorias (id, decision)."
            )

        for i, row in enumerate(reader, start=2):  # línea 1 = header
            decision = row.get("decision", "").strip().lower()
            if decision not in VALID_DECISIONS:
                raise DataError(
                    f"Línea {i}: valor de 'decision' inválido: '{row.get('decision')}'. "
                    f"Valores válidos: {sorted(VALID_DECISIONS)}."
                )
            rows.append(row)

    if not rows:
        return {
            "accepted_count": 0,
            "rejected_count": 0,
            "skipped_count": 0,
            "not_found_count": 0,
            "total_rows": 0,
        }

    # Agrupar por decisión
    to_accept = [r["id"] for r in rows if r["decision"].strip().lower() == "accepted"]
    to_reject = [r["id"] for r in rows if r["decision"].strip().lower() == "rejected"]
    # undecided → no-op
    skipped = len(rows) - len(to_accept) - len(to_reject)

    curated_backend_close = None
    store = open_store(store_path)
    try:
        corpus = store.load()

        # Detectar IDs huérfanos (no existen en el corpus).
        # No se aborta: el flujo batch debe ser idempotente aunque el corpus haya
        # cambiado entre el dump y el from-csv.  Se reporta ``not_found_count``
        # para que el humano/agente detecte typos en el CSV.
        existing_ids: set[str] = {
            str(r.get(Col.ID, "")) for r in corpus.to_arrow().to_pylist()
        }
        to_accept_found = [id_ for id_ in to_accept if id_ in existing_ids]
        to_reject_found = [id_ for id_ in to_reject if id_ in existing_ids]
        not_found = [id_ for id_ in (to_accept + to_reject) if id_ not in existing_ids]

        # R2: decided_at ya viene inyectado desde la frontera CLI
        if to_accept_found:
            corpus = corpus.accept(to_accept_found, by=by, decided_at=decided_at)
        if to_reject_found:
            corpus = corpus.reject(to_reject_found, by=by, decided_at=decided_at)

        curated_backend_close = getattr(corpus._backend, "close", None)
        store.persist(corpus)
    finally:
        if curated_backend_close is not None:
            curated_backend_close()
        store.close()

    return {
        "accepted_count": len(to_accept_found),
        "rejected_count": len(to_reject_found),
        "skipped_count": skipped,
        "not_found_count": len(not_found),
        "total_rows": len(rows),
    }


# ---------------------------------------------------------------------------
# Comando Click
# ---------------------------------------------------------------------------


@click.command("curate")
@click.option(
    "--dump",
    "do_dump",
    is_flag=True,
    default=False,
    help=(
        "Exporta los candidatos a un CSV para revisión offline. "
        "Salida default: <workspace>/exports/curacion.csv."
    ),
)
@click.option(
    "--from-csv",
    "from_csv",
    default=None,
    type=click.Path(),
    help="Reimporta decisiones de curación desde el CSV dado.",
)
@click.option(
    "--out",
    "out_override",
    default=None,
    type=click.Path(),
    help=(
        "Ruta de salida del CSV (solo con --dump). "
        "Override del default <workspace>/exports/curacion.csv."
    ),
)
@click.option(
    "--all",
    "include_all",
    is_flag=True,
    default=False,
    help=("Con --dump: incluye todos los papers del corpus, no solo los candidatos."),
)
@click.option(
    "--by",
    default="cli",
    show_default=True,
    help="Identificador de quien decide (solo con --from-csv).",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    help="Salida JSON estructurada.",
)
@click.pass_context
@handle_errors("curate")
def curate_cmd(
    ctx: click.Context,
    do_dump: bool,
    from_csv: str | None,
    out_override: str | None,
    include_all: bool,
    by: str,
    json_output: bool,
) -> None:
    """Curación en lote: exporta papers a CSV y reimporta decisiones.

    Dos modos mutuamente excluyentes (exactamente uno requerido):

    \b
      --dump          exporta candidatos a CSV para revisión offline.
      --from-csv CSV  reimporta decisiones desde el CSV dado.

    Flujo típico:

    \b
      b2g curate --dump                  # genera curacion.csv
      # (editar curacion.csv en Excel: columnas decision y note)
      b2g curate --from-csv curacion.csv  # aplica decisiones

    Curación TRANSVERSAL: no transiciona el CycleState.
    Disponible en cualquier estado del lazo (ADR 0016 enmendado R3).
    """
    # --- Validar exclusividad de modos ---
    if do_dump and from_csv:
        raise UsageError(
            "--dump y --from-csv son mutuamente excluyentes. "
            "Usá uno u otro por invocación."
        )
    if not do_dump and from_csv is None:
        raise UsageError("Debés especificar un modo: --dump o --from-csv <archivo>.")

    ws = resolve_workspace(ctx.obj)
    store_path = ws.library_path

    # --- Modo dump ---
    if do_dump:
        if out_override is not None:
            out_path = Path(out_override)
        else:
            out_path = ws.exports_dir / CURATE_CSV_FILENAME

        data = run_curate_dump(store_path, out_path=out_path, include_all=include_all)

        if json_output:
            envelope = build_envelope(
                command="curate",
                ok=True,
                data=data,
                exit_code=0,
            )
            emit(envelope)
        else:
            emit_human(
                f"Exportados {data['papers_exported']} papers a: {data['csv_path']}"
            )
        return

    # --- Modo from-csv ---
    # R2: el reloj se inyecta en la frontera (ADR 0017 enmendado)
    now = datetime.now(UTC)
    data = run_curate_from_csv(
        store_path,
        from_csv,  # type: ignore[arg-type]
        by=by,
        decided_at=now,
    )

    if json_output:
        envelope = build_envelope(
            command="curate",
            ok=True,
            data=data,
            exit_code=0,
        )
        emit(envelope)
    else:
        emit_human(
            f"Importados: {data['accepted_count']} aceptados, "
            f"{data['rejected_count']} rechazados, "
            f"{data['skipped_count']} sin cambio (undecided)."
        )
        if data["not_found_count"] > 0:
            emit_human(
                f"Advertencia: {data['not_found_count']} IDs del CSV no se "
                "encontraron en el corpus (posibles typos). "
                "Verificá con ``b2g inspect``."
            )
