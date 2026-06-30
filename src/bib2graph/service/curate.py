"""service.curate — Orquestación de curación (ADR 0028 Hito G3 + #155).

Capa de servicios neutral: sin ``print``, ``sys.exit``, Click ni FastAPI.

``decided_at`` es **inyectado por el llamador** (R2/ADR 0017): el servicio
nunca llama ``datetime.now()``.  La frontera (CLI o API) inyecta el reloj.

Operaciones de curación paper-a-paper (G3 original):
  - ``accept_papers`` — marca ids como ``accepted``.
  - ``reject_papers`` — marca ids como ``rejected``.
  - ``curate_paper`` — wrapper de un solo paper.

Operaciones en lote (subidas desde cli/ en #155):
  - ``run_curate_dump`` — exporta corpus a CSV para revisión offline.
  - ``run_curate_from_csv`` — reimporta decisiones desde CSV.

Operación de filtrado PRISMA (subida desde cli/ en #155):
  - ``filter_corpus`` — aplica filtros PRISMA y transiciona a FILTERED.

El CLI (`cli/commands/curate.py` grupo noun-verb, `cli/commands/filter.py`)
son shims delgados que inyectan el reloj e invocan estas funciones.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any

from bib2graph.constants import Col, CurationStatus
from bib2graph.service.errors import DataError, StoreError

# Constantes CSV — fuente canónica (exportadas desde cli/ para compat)

CURATE_CSV_FILENAME = "curacion.csv"

CSV_COLUMNS = [
    "id",
    "source_id",
    "title",
    "year",
    "authors",
    "venue",
    "doi",
    "keywords",
    "cited_by_count",
    "references_count",
    "is_seed",
    "openalex_url",
    "scent_score",
    "cluster",
    "decision",
    "note",
]

CSV_REQUIRED_COLUMNS: frozenset[str] = frozenset({"id", "decision"})

VALID_DECISIONS: frozenset[str] = frozenset(
    {CurationStatus.ACCEPTED, CurationStatus.REJECTED, "undecided"}
)

_STATUS_TO_DECISION: dict[str, str] = {
    CurationStatus.CANDIDATE: "undecided",
    CurationStatus.ACCEPTED: "accepted",
    CurationStatus.REJECTED: "rejected",
}

VALID_SCOPES: frozenset[str] = frozenset({"candidates", "seeds", "all"})


def _open_writable(path: Path) -> Any:
    """Abre el store para escritura; falla accionable si está bloqueado.

    Args:
        path: Ruta al archivo ``.duckdb``.

    Returns:
        ``DuckDBStore`` abierto y listo para leer/escribir.

    Raises:
        StoreError: Si el store está bloqueado o no se puede abrir.
    """
    from bib2graph.backends.duckdb import StoreLockedError
    from bib2graph.stores.duckdb import DuckDBStore

    try:
        return DuckDBStore(path)
    except StoreLockedError as exc:
        raise StoreError(str(exc)) from exc
    except OSError as exc:
        raise StoreError(
            f"No se puede abrir el store '{path}': {exc}. "
            "Verificá que el archivo no esté bloqueado por otro proceso."
        ) from exc


# Helpers internos — transformación de filas para el CSV


def _authors_display(row: dict[str, Any]) -> str:
    """Extrae los autores de una fila del corpus y los une con ' | '."""
    raw = row.get(Col.AUTHORS_RAW)
    if raw and isinstance(raw, list):
        return " | ".join(str(a) for a in raw if a)
    ids = row.get(Col.AUTHORS_ID)
    if ids and isinstance(ids, list):
        return " | ".join(str(a) for a in ids if a)
    return ""


def _keywords_display(row: dict[str, Any]) -> str:
    """Extrae las keywords de una fila del corpus y las une con ' | '."""
    ids = row.get(Col.KEYWORDS_ID)
    if ids and isinstance(ids, list):
        return " | ".join(str(k) for k in ids if k)
    raw = row.get(Col.KEYWORDS_RAW)
    if raw and isinstance(raw, list):
        return " | ".join(str(k) for k in raw if k)
    return ""


def _openalex_url(row: dict[str, Any]) -> str:
    """Deriva la URL de OpenAlex a partir del source_id (solo IDs W…)."""
    src_id = row.get(Col.SOURCE_ID)
    if src_id:
        src_str = str(src_id)
        if src_str.startswith("W") and src_str[1:].isdigit():
            return f"https://openalex.org/{src_str}"
    return ""


def _scent_score_display(row: dict[str, Any]) -> str:
    """Extrae el scent_score del provenance si está disponible (best-effort)."""
    import json as _json

    provenance_raw = row.get(Col.PROVENANCE)
    if not provenance_raw:
        return ""
    try:
        events = _json.loads(str(provenance_raw))
        if not isinstance(events, list):
            return ""
        for event in events:
            if isinstance(event, dict):
                val = event.get("scent")
                if val is not None:
                    return str(val)
    except (_json.JSONDecodeError, TypeError):
        pass
    return ""


def _row_to_csv_dict(row: dict[str, Any]) -> dict[str, str]:
    """Convierte una fila del corpus al dict para el CSV de curación."""
    status = str(row.get(Col.CURATION_STATUS, CurationStatus.CANDIDATE))
    decision = _STATUS_TO_DECISION.get(status, "undecided")
    is_seed_val = row.get(Col.IS_SEED)
    is_seed_str = str(is_seed_val) if is_seed_val is not None else ""

    return {
        "id": str(row.get(Col.ID) or ""),
        "source_id": str(row.get(Col.SOURCE_ID) or ""),
        "title": str(row.get(Col.TITLE) or ""),
        "year": str(row.get(Col.YEAR) or ""),
        "authors": _authors_display(row),
        "venue": str(row.get(Col.SOURCE) or ""),
        "doi": str(row.get(Col.DOI) or ""),
        "keywords": _keywords_display(row),
        "cited_by_count": "",  # no en el schema canónico
        "references_count": "",  # no en el schema canónico
        "is_seed": is_seed_str,
        "openalex_url": _openalex_url(row),
        "scent_score": _scent_score_display(row),
        "cluster": "",  # reservado para integración con redes
        "decision": decision,
        "note": "",
    }


def _filter_table_by_scope(table: Any, scope: str) -> Any:
    """Filtra una tabla Arrow según el scope de dump.

    Scope 'candidates': curation_status == 'candidate' AND is_seed == False.
    Scope 'seeds':      is_seed == True.
    Scope 'all':        sin filtro.

    Args:
        table: Tabla Arrow del corpus.
        scope: Uno de 'candidates', 'seeds', 'all'.

    Returns:
        Tabla Arrow filtrada.
    """
    import pyarrow.compute as pc

    if scope == "all":
        return table
    elif scope == "seeds":
        mask = table.column(Col.IS_SEED)
        return table.filter(mask)
    else:
        status_col = table.column(Col.CURATION_STATUS)
        is_candidate = pc.equal(status_col, CurationStatus.CANDIDATE)  # type: ignore[attr-defined]
        is_seed_col = table.column(Col.IS_SEED)
        not_seed = pc.invert(is_seed_col)  # type: ignore[attr-defined]
        mask = pc.and_(is_candidate, not_seed)  # type: ignore[attr-defined]
        return table.filter(mask)


def run_curate_dump(
    store_path: str | Path,
    *,
    out_path: Path,
    scope: str = "candidates",
    include_all: bool = False,
) -> dict[str, Any]:
    """Exporta el corpus a un CSV para revisión offline.

    Por defecto exporta solo los candidatos forrajeados (``scope='candidates'``).
    Con ``scope='seeds'`` exporta las semillas; con ``scope='all'`` exporta todo.

    ``include_all`` es un alias de ``scope='all'`` mantenido por compatibilidad
    con tests existentes.  Si ``True``, fuerza ``scope='all'``.

    Args:
        store_path: Ruta al archivo ``.duckdb``.
        out_path: Ruta completa del archivo CSV de salida.
        scope: 'candidates' (default), 'seeds' o 'all'.
        include_all: Alias de scope='all'. Si True, fuerza scope='all'.

    Returns:
        Dict con ``csv_path``, ``papers_exported``, ``columns``.

    Raises:
        DataError: Si el corpus está vacío o no hay papers en el scope dado.
        StoreError: Si el store está bloqueado.
    """
    effective_scope = "all" if include_all else scope

    path = Path(store_path)
    store = _open_writable(path)
    try:
        corpus = store.load()
        all_table = corpus.to_arrow()
        table = _filter_table_by_scope(all_table, effective_scope)
        rows = table.to_pylist()
    finally:
        store.close()

    if not rows and effective_scope != "all":
        scope_label = (
            "candidatos forrajeados" if effective_scope == "candidates" else "semillas"
        )
        raise DataError(
            f"No hay {scope_label} para exportar. "
            "Usá --scope all para exportar todo el corpus, o ejecutá "
            "``b2g chain`` para agregar candidatos."
        )

    out_path = Path(out_path)
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


def run_curate_from_csv(
    store_path: str | Path,
    csv_path: str | Path,
    *,
    by: str = "cli",
    decided_at: datetime | None = None,
) -> dict[str, Any]:
    """Reimporta decisiones de curación desde un CSV al corpus.

    Lee el CSV producido por ``run_curate_dump`` y aplica las decisiones en
    lote.  Solo requiere columnas ``id`` y ``decision``; columnas extra se
    ignoran (garantiza round-trip).

    Mapeo:
      - ``accepted``  → ``Corpus.accept``
      - ``rejected``  → ``Corpus.reject``
      - ``undecided`` → no-op

    Idempotente: reimportar el mismo CSV produce el mismo estado final.

    R2: ``decided_at`` se inyecta desde la frontera; el servicio no llama
    ``datetime.now()``.

    Args:
        store_path: Ruta al archivo ``.duckdb``.
        csv_path: Ruta al archivo CSV con las decisiones.
        by: Identificador de quien decide (default: ``"cli"``).
        decided_at: Timestamp inyectado por el llamador (R2/ADR 0017).

    Returns:
        Dict con ``accepted_count``, ``rejected_count``, ``skipped_count``,
        ``not_found_count``, ``total_rows``.

    Raises:
        DataError: Si el CSV no existe, faltan columnas o hay decisiones inválidas.
        StoreError: Si el store está bloqueado.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise DataError(
            f"El archivo CSV '{csv_path}' no existe. "
            "Generalo primero con ``b2g curate dump``."
        )

    rows: list[dict[str, str]] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = set(reader.fieldnames or [])

        missing = CSV_REQUIRED_COLUMNS - fieldnames
        if missing:
            raise DataError(
                f"El CSV '{csv_path}' no tiene las columnas requeridas: "
                f"{sorted(missing)}. "
                "Asegurate de exportar con ``b2g curate dump`` y no borrar "
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

    to_accept = [r["id"] for r in rows if r["decision"].strip().lower() == "accepted"]
    to_reject = [r["id"] for r in rows if r["decision"].strip().lower() == "rejected"]
    skipped = len(rows) - len(to_accept) - len(to_reject)

    curated_backend_close = None
    path = Path(store_path)
    store = _open_writable(path)
    try:
        corpus = store.load()

        existing_ids: set[str] = {
            str(r.get(Col.ID, "")) for r in corpus.to_arrow().to_pylist()
        }
        to_accept_found = [id_ for id_ in to_accept if id_ in existing_ids]
        to_reject_found = [id_ for id_ in to_reject if id_ in existing_ids]
        not_found = [id_ for id_ in (to_accept + to_reject) if id_ not in existing_ids]

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


def filter_corpus(
    store_path: str | Path,
    *,
    year_gte: int | None = None,
    year_lte: int | None = None,
    language: list[str] | None = None,
    type_in: list[str] | None = None,
    min_citations: int | None = None,
    decided_at: datetime | None = None,
) -> dict[str, Any]:
    """Aplica filtros PRISMA al corpus marcando rejected los excluidos.

    Los filtros se aplican en orden; cada uno ve el resultado del anterior.
    El CycleState transiciona a FILTERED tras persistir con éxito.

    R3 — fuente única de verdad: el destino de la transición lo dicta
    ``cycle.py``, no un literal en este módulo (ADR 0016 enmendado §1).
    R2 (ADR 0017 enmendado): ``decided_at`` es **inyectado por el llamador**;
    este servicio nunca llama ``datetime.now()``.  El CLI inyecta el reloj
    en la frontera CLI→servicio (``curate filter`` y ``run_filter`` suelto).

    Args:
        store_path: Ruta al archivo ``.duckdb``.
        year_gte: Filtrar años >= este valor.
        year_lte: Filtrar años <= este valor.
        language: Lista de códigos ISO 639-1 a incluir.
        type_in: Lista de áreas de investigación a incluir.
        min_citations: Mínimo de citantes (``len(cited_by_id) >= min_citations``).
        decided_at: Timestamp inyectado por el llamador (R2/ADR 0017).
            ``None`` → el núcleo (``apply_filters``) usará su propio timestamp,
            pero el llamador DEBE inyectarlo en la frontera para determinismo.

    Returns:
        Dict con ``steps`` (conteos PRISMA por paso) y ``total_papers``.

    Raises:
        DataError: Si ningún criterio es válido.
        StoreError: Si el store está bloqueado.
    """
    from bib2graph.cycle import apply_transition
    from bib2graph.filters.prisma import FilterCriterion, apply_filters

    criteria: list[FilterCriterion] = []

    if year_gte is not None:
        criteria.append(FilterCriterion(field="year", op="gte", value=year_gte))
    if year_lte is not None:
        criteria.append(FilterCriterion(field="year", op="lte", value=year_lte))
    if language:
        criteria.append(FilterCriterion(field="language", op="in", value=language))
    if type_in:
        criteria.append(FilterCriterion(field="type", op="in", value=type_in))
    if min_citations is not None:
        criteria.append(
            FilterCriterion(field="min_citations", op="gte", value=min_citations)
        )

    if not criteria:
        raise DataError(
            "Debés especificar al menos un criterio de filtro: "
            "--year-gte, --year-lte, --language, --type, o --min-citations."
        )

    path = Path(store_path)
    filtered_backend_close = None
    store = _open_writable(path)
    try:
        corpus = store.load()

        current_state = store.backend.loop_state()
        current_round = store.backend.loop_round()
        new_state, new_round = apply_transition(current_state, "filter", current_round)

        filtered_corpus, steps = apply_filters(corpus, criteria, decided_at=decided_at)
        total_papers = len(filtered_corpus)
        filtered_backend_close = getattr(filtered_corpus._backend, "close", None)
        store.persist(filtered_corpus)
        store.backend.persist_filter_steps(steps)
        store.backend.set_loop_state(new_state, cycle_round=new_round)
    finally:
        if filtered_backend_close is not None:
            filtered_backend_close()
        store.close()

    steps_data = [
        {
            "name": s.name,
            "criteria": s.criteria,
            "count_before": s.count_before,
            "count_after": s.count_after,
            "excluded": s.count_before - s.count_after,
        }
        for s in steps
    ]

    return {
        "steps": steps_data,
        "total_papers": total_papers,
        "criteria_applied": len(criteria),
    }


def accept_papers(
    store_path: str | Path,
    ids: list[str],
    *,
    by: str = "api",
    decided_at: datetime | None = None,
) -> dict[str, Any]:
    """Marca los papers dados como ``accepted`` y persiste.

    Verifica que todos los ids existan en el corpus antes de operar.

    Args:
        store_path: Ruta al archivo ``.duckdb``.
        ids: Lista de ids a aceptar.
        by: Identificador de quien decide (default: ``"api"``).
        decided_at: Timestamp inyectado por el llamador (R2/ADR 0017).

    Returns:
        Dict con ``accepted_count``, ``ids``.

    Raises:
        DataError: Si la lista está vacía o algún id no existe.
        StoreError: Si el store está bloqueado.
    """
    if not ids:
        raise DataError("Debés especificar al menos un ID.")

    path = Path(store_path)
    updated_backend_close = None
    store = _open_writable(path)
    try:
        corpus = store.load()

        existing_ids = {str(r["id"]) for r in corpus.to_arrow().to_pylist()}
        missing = [id_ for id_ in ids if id_ not in existing_ids]
        if missing:
            raise DataError(
                f"IDs no encontrados en el corpus: {missing}. "
                "Verificá los ids con 'b2g inspect'."
            )

        updated = corpus.accept(ids, by=by, decided_at=decided_at)
        updated_backend_close = getattr(updated._backend, "close", None)
        store.persist(updated)
    finally:
        if updated_backend_close is not None:
            updated_backend_close()
        store.close()

    return {
        "accepted_count": len(ids),
        "ids": ids,
    }


def reject_papers(
    store_path: str | Path,
    ids: list[str],
    *,
    by: str = "api",
    decided_at: datetime | None = None,
) -> dict[str, Any]:
    """Marca los papers dados como ``rejected`` y persiste.

    Args:
        store_path: Ruta al archivo ``.duckdb``.
        ids: Lista de ids a rechazar.
        by: Identificador de quien decide (default: ``"api"``).
        decided_at: Timestamp inyectado por el llamador (R2/ADR 0017).

    Returns:
        Dict con ``rejected_count``, ``ids``.

    Raises:
        DataError: Si la lista está vacía o algún id no existe.
        StoreError: Si el store está bloqueado.
    """
    if not ids:
        raise DataError("Debés especificar al menos un ID.")

    path = Path(store_path)
    updated_backend_close = None
    store = _open_writable(path)
    try:
        corpus = store.load()

        existing_ids = {str(r["id"]) for r in corpus.to_arrow().to_pylist()}
        missing = [id_ for id_ in ids if id_ not in existing_ids]
        if missing:
            raise DataError(
                f"IDs no encontrados en el corpus: {missing}. "
                "Verificá los ids con 'b2g inspect'."
            )

        updated = corpus.reject(ids, by=by, decided_at=decided_at)
        updated_backend_close = getattr(updated._backend, "close", None)
        store.persist(updated)
    finally:
        if updated_backend_close is not None:
            updated_backend_close()
        store.close()

    return {
        "rejected_count": len(ids),
        "ids": ids,
    }


_VALID_DECISIONS_STRICT = frozenset({"accepted", "rejected"})


def curate_paper(
    store_path: str | Path,
    paper_id: str,
    *,
    decision: str,
    by: str = "api",
    decided_at: datetime | None = None,
) -> dict[str, Any]:
    """Aplica una decisión de curación a un paper individual.

    Wrapper de ``accept_papers``/``reject_papers`` para el endpoint de la API
    que opera paper-a-paper.

    Args:
        store_path: Ruta al archivo ``.duckdb``.
        paper_id: Id del paper a curar.
        decision: ``"accepted"`` o ``"rejected"`` (otra cosa → ``DataError``).
        by: Identificador de quien decide (default: ``"api"``).
        decided_at: Timestamp inyectado por el llamador (R2/ADR 0017).

    Returns:
        Dict con los campos del resultado (``accepted_count``/``rejected_count`` + ``ids``).

    Raises:
        DataError: Si ``decision`` es inválida o el id no existe.
        StoreError: Si el store está bloqueado.
    """
    if decision not in _VALID_DECISIONS_STRICT:
        valid = ", ".join(sorted(_VALID_DECISIONS_STRICT))
        raise DataError(f"Decisión '{decision}' inválida. Valores válidos: {valid}.")

    if decision == "accepted":
        return accept_papers(store_path, [paper_id], by=by, decided_at=decided_at)
    return reject_papers(store_path, [paper_id], by=by, decided_at=decided_at)
