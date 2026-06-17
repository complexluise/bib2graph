"""cli._store — Helper para resolver el workspace y abrir DuckDBStore.

Centraliza la apertura del store y el manejo del error de bloqueo,
para que cada subcomando no tenga que repetir el try/except.

ADR 0029 — resolución workspace:
  ``resolve_library_path`` lee ``ctx.obj["workspace"]`` y ``ctx.obj["store"]``
  y delega en ``Workspace.resolve(...)`` con las env actuales y el cwd.
  El resultado es siempre una ``Path`` al archivo ``.duckdb``.

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

from bib2graph.cli._errors import StoreError, UsageError


def resolve_library_path(ctx_obj: dict[str, Any]) -> Path:
    """Resuelve la ruta al archivo .duckdb desde el contexto Click (ADR 0029).

    Lee ``workspace`` y ``store`` del dict de contexto Click y delega en
    ``Workspace.resolve(...)`` para aplicar la precedencia (ADR 0029):
      1. ``--workspace`` explícito (forma canónica),
      2. ``--store`` explícito (modo degenerado, retrocompat; mutuamente excluyente con ``--workspace``),
      3. variable de entorno ``B2G_WORKSPACE``,
      4. caminar hacia arriba desde cwd buscando ``workspace.json``.

    Args:
        ctx_obj: El dict ``ctx.obj`` del grupo Click (contiene ``workspace``
            y ``store`` con los valores de las opciones globales).

    Returns:
        Ruta al archivo ``.duckdb`` de la biblioteca viva.

    Raises:
        UsageError: Si no se puede resolver ningún workspace (exit 1).
    """
    from bib2graph.workspace import Workspace, WorkspaceNotFoundError

    workspace: str | None = ctx_obj.get("workspace")
    store: str | None = ctx_obj.get("store")

    try:
        ws = Workspace.resolve(workspace=workspace, store=store)
    except WorkspaceNotFoundError as exc:
        raise UsageError(str(exc)) from exc

    return ws.library_path


def resolve_workspace(ctx_obj: dict[str, Any]) -> Any:
    """Resuelve el Workspace completo desde el contexto Click (ADR 0029).

    Variante de ``resolve_library_path`` que devuelve el ``Workspace`` completo
    (útil cuando el comando necesita más que solo la ruta al store, p.ej.
    ``networks_dir`` para ``build`` o el manifest para ``status``).

    Args:
        ctx_obj: El dict ``ctx.obj`` del grupo Click.

    Returns:
        El ``Workspace`` resuelto.

    Raises:
        UsageError: Si no se puede resolver ningún workspace (exit 1).
    """
    from bib2graph.workspace import Workspace, WorkspaceNotFoundError

    workspace: str | None = ctx_obj.get("workspace")
    store: str | None = ctx_obj.get("store")

    try:
        return Workspace.resolve(workspace=workspace, store=store)
    except WorkspaceNotFoundError as exc:
        raise UsageError(str(exc)) from exc


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
