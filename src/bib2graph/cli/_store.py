"""cli._store — Helper para abrir DuckDBStore y traducir StoreLockedError.

Centraliza la apertura del store y el manejo del error de bloqueo,
para que cada subcomando no tenga que repetir el try/except.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bib2graph.cli._errors import StoreError


def open_store(path: str | Path) -> Any:
    """Abre (o crea) el DuckDBStore en ``path``.

    Captura ``StoreLockedError`` (subclase de ``OSError``) y lo re-lanza
    como ``StoreError`` (exit 5) para el decorador ``@handle_errors``.

    Args:
        path: Ruta al archivo ``.duckdb``.

    Returns:
        ``DuckDBStore`` abierto y listo para usar.

    Raises:
        StoreError: Si el archivo está bloqueado o no se puede abrir.
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
