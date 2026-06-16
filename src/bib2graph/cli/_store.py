"""cli._store — Helper para abrir DuckDBStore y traducir StoreLockedError.

Centraliza la apertura del store y el manejo del error de bloqueo,
para que cada subcomando no tenga que repetir el try/except.

R5 — footgun de auto-creación:
  ``open_store_readonly`` verifica que el archivo exista antes de abrirlo.
  Los comandos de solo lectura (``status``, ``validate``) usan esta variante
  para no crear silenciosamente un store vacío ante un typo en ``--store``
  (Nota 06, catálogo de secundarios).  ``open_store`` (escritura) mantiene
  el comportamiento de crear el archivo si no existe.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bib2graph.cli._errors import StoreError


def open_store(path: str | Path) -> Any:
    """Abre (o crea) el DuckDBStore en ``path``.

    Captura ``StoreLockedError`` (subclase de ``OSError``) y lo re-lanza
    como ``StoreError`` (exit 5) para el decorador ``@handle_errors``.

    Uso: comandos de ESCRITURA (seed, chain, filter, build, accept, reject,
    snapshot, export).  Los comandos de SOLO LECTURA deben usar
    ``open_store_readonly`` para no auto-crear el store ante un typo.

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


def open_store_readonly(path: str | Path) -> Any:
    """Abre el DuckDBStore en ``path`` para SOLO LECTURA.

    R5: a diferencia de ``open_store``, falla con un error accionable si el
    archivo NO existe, en vez de crearlo vacío.  Esto evita el footgun
    verificado en Nota 06 donde ``b2g status --store typo.duckdb`` creaba
    silenciosamente un archivo vacío.

    Args:
        path: Ruta al archivo ``.duckdb``.

    Returns:
        ``DuckDBStore`` abierto y listo para leer.

    Raises:
        StoreError: Si el archivo no existe, está bloqueado o no se puede abrir.
    """
    from bib2graph.backends.duckdb import StoreLockedError
    from bib2graph.stores.duckdb import DuckDBStore

    resolved = Path(path)
    if not resolved.exists():
        raise StoreError(
            f"El store '{path}' no existe. "
            "Verificá la ruta o iniciá la investigación con 'b2g seed'."
        )

    try:
        return DuckDBStore(resolved)
    except StoreLockedError as exc:
        raise StoreError(str(exc)) from exc
    except OSError as exc:
        raise StoreError(
            f"No se puede abrir el store '{path}': {exc}. "
            "Verificá que el archivo no esté bloqueado por otro proceso."
        ) from exc
