"""service.curate — Orquestación de curación paper-a-paper (ADR 0028 Hito G3).

Capa de servicios neutral: sin ``print``, ``sys.exit``, Click ni FastAPI.
Las operaciones de curación toman ``store_path`` (no el workspace completo)
porque mutar el corpus solo necesita la ruta al archivo ``.duckdb``.

``decided_at`` es **inyectado por el llamador** (R2/ADR 0017): el servicio
nunca llama ``datetime.now()``.  La frontera (CLI o API) inyecta el reloj.

Operaciones:
  - ``accept_papers`` — marca ids como ``accepted``.
  - ``reject_papers`` — marca ids como ``rejected``.
  - ``curate_paper`` — wrapper de un solo paper (``decision`` = ``"accepted"``
    o ``"rejected"``; otra cosa → ``DataError``).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from bib2graph.service.errors import DataError, StoreError

# ---------------------------------------------------------------------------
# Helper interno — abrir store para escritura
# ---------------------------------------------------------------------------


def _open_writable(path: Path) -> Any:
    """Abre el store para escritura; falla accionable si está bloqueado.

    Gemelo de ``_open_readonly`` de ``service/reads.py``, pero sin la
    verificación de existencia (los comandos de escritura crean el archivo
    si no existe).

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


# ---------------------------------------------------------------------------
# accept_papers
# ---------------------------------------------------------------------------


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
            ``None`` → el núcleo usará el timestamp que ya tiene (pero el
            llamador DEBE inyectarlo en la frontera para determinismo).

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


# ---------------------------------------------------------------------------
# reject_papers
# ---------------------------------------------------------------------------


def reject_papers(
    store_path: str | Path,
    ids: list[str],
    *,
    by: str = "api",
    decided_at: datetime | None = None,
) -> dict[str, Any]:
    """Marca los papers dados como ``rejected`` y persiste.

    Verifica que todos los ids existan en el corpus antes de operar.

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


# ---------------------------------------------------------------------------
# curate_paper — wrapper de un solo paper
# ---------------------------------------------------------------------------

_VALID_DECISIONS = frozenset({"accepted", "rejected"})


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
        Dict con los campos del resultado de la operación correspondiente
        (``accepted_count``/``rejected_count`` + ``ids``).

    Raises:
        DataError: Si ``decision`` es inválida o el id no existe.
        StoreError: Si el store está bloqueado.
    """
    if decision not in _VALID_DECISIONS:
        valid = ", ".join(sorted(_VALID_DECISIONS))
        raise DataError(f"Decisión '{decision}' inválida. Valores válidos: {valid}.")

    if decision == "accepted":
        return accept_papers(store_path, [paper_id], by=by, decided_at=decided_at)
    return reject_papers(store_path, [paper_id], by=by, decided_at=decided_at)
