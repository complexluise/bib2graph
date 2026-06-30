"""service.store — Helper neutral para abrir DuckDBStore.

Sin Click, sin print, sin sys.exit.  Capa de servicios neutral (ADR 0028).

Callers:
  - ``service.snapshot`` (run_snapshot / run_restore)
  - ``cli._store`` (re-exporta ``open_store`` para que los comandos CLI
    y los tests que importan desde allí sigan funcionando)

Este módulo es la fuente canónica de ``open_store`` (issue #175): evita la
duplicación que existía entre ``cli/_store.py`` y ``service/snapshot.py``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bib2graph.service.errors import StoreError


def open_store(path: str | Path) -> Any:
    """Abre (o crea) el DuckDBStore en ``path`` para escritura/lectura.

    Captura ``StoreLockedError`` (subclase de ``OSError``) y lo re-lanza
    como ``StoreError`` (exit 5).

    Uso: operaciones de ESCRITURA (seed, chain, filter, build, accept, reject,
    snapshot, restore) o lectura desde ``service/``.  Los comandos CLI de
    SOLO LECTURA deben usar ``cli._store.open_store_readonly`` para no
    auto-crear el store ante un typo.

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
