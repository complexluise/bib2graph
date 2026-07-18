"""cli._store — Helper para resolver el workspace y abrir DuckDBStore.

Centraliza la apertura del store y el manejo del error de bloqueo,
para que cada subcomando no tenga que repetir el try/except.

ADR 0029 — resolución workspace:
  ``resolve_library_path`` lee ``ctx.obj["workspace"]`` y delega en
  ``Workspace.resolve(...)`` con las env actuales y el cwd.
  El resultado es siempre una ``Path`` al archivo ``.duckdb``.

R5 — footgun de auto-creación:
  ``open_store_readonly`` verifica que el archivo exista antes de abrirlo.
  Los comandos de solo lectura (``status``, ``validate``) usan esta variante
  para no crear silenciosamente un store vacío ante un typo en la ruta
  (Nota 06, catálogo de secundarios).  ``open_store`` (escritura) mantiene
  el comportamiento de crear el archivo si no existe.

Fuente única (issue #175):
  ``open_store`` se re-exporta desde ``service.store`` para que la capa de
  servicios y el CLI usen la misma implementación sin violar el layering
  (ADR 0028).

ADR 0045 (#259) — grieta 3b, eco de workspace + warning en walk-up:
  ``workspace_echo``/``workspace_walkup_warning`` generalizan el patrón que
  ``status_cmd`` ya implementaba a mano (``data["workspace"] = {...}``).
  Todo comando que resuelve un ``Workspace`` (vía ``resolve_workspace``)
  debería usar estos dos helpers para poblar ``data["workspace"]`` y agregar
  el warning accionable cuando la resolución fue implícita (``source=="cwd"``).
  Los comandos meta que corren SIN workspace (``skill``, ``schema``) no los
  usan.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bib2graph.cli._errors import StoreError, UsageError

# Re-exportar open_store desde la capa neutral (service.store) para:
# 1. Mantener backward compat con todos los imports de ``cli._store.open_store``.
# 2. Garantizar fuente única con ``service.snapshot`` (issue #175).
from bib2graph.service.store import open_store as open_store

#: Warning accionable emitido cuando el workspace se resolvió por walk-up
#: implícito del cwd (``Workspace.source == "cwd"``). Mismo texto en todos
#: los comandos para que un agente pueda matchear el mensaje (ADR 0045 #259).
WORKSPACE_WALKUP_WARNING = (
    "workspace resuelto por walk-up del cwd; usá --workspace o B2G_WORKSPACE "
    "para fijarlo explícitamente"
)


def resolve_library_path(ctx_obj: dict[str, Any]) -> Path:
    """Resuelve la ruta al archivo .duckdb desde el contexto Click (ADR 0029).

    Lee ``workspace`` del dict de contexto Click y delega en
    ``Workspace.resolve(...)`` para aplicar la precedencia (ADR 0029):
      1. ``--workspace`` explícito (forma canónica),
      2. variable de entorno ``B2G_WORKSPACE``,
      3. caminar hacia arriba desde cwd buscando ``workspace.json``.

    Args:
        ctx_obj: El dict ``ctx.obj`` del grupo Click (contiene ``workspace``
            con el valor de la opción global).

    Returns:
        Ruta al archivo ``.duckdb`` de la biblioteca viva.

    Raises:
        UsageError: Si no se puede resolver ningún workspace (exit 1).
    """
    from bib2graph.workspace import Workspace, WorkspaceNotFoundError

    workspace: str | None = ctx_obj.get("workspace")

    try:
        ws = Workspace.resolve(workspace=workspace)
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

    try:
        return Workspace.resolve(workspace=workspace)
    except WorkspaceNotFoundError as exc:
        raise UsageError(str(exc)) from exc


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


def workspace_echo(ws: Any) -> dict[str, str | None]:
    """Arma el bloque ``data["workspace"]`` a partir de un ``Workspace`` resuelto.

    Generaliza el patrón que ``status_cmd`` ya implementaba a mano
    (``cli/commands/status.py``, ADR 0029) para que todo comando del ciclo
    que resuelve workspace lo ecoe de la misma forma (ADR 0045 #259).
    Es puramente aditivo: no cambia la precedencia de resolución
    (``workspace.py`` intacto), solo la hace legible por el mismo canal.

    Args:
        ws: El ``Workspace`` devuelto por ``resolve_workspace``.

    Returns:
        Dict ``{"root": str | None, "source": str}`` listo para asignar a
        ``data["workspace"]``.
    """
    return {
        "root": str(ws.root) if ws.root is not None else None,
        "source": ws.source,
    }


def workspace_walkup_warning(ws: Any) -> list[str]:
    """Devuelve el warning accionable si el workspace se resolvió por walk-up.

    ADR 0045 (#259): cuando ``ws.source == "cwd"`` (resolución implícita
    caminando hacia arriba desde el cwd, sin ``--workspace``/``B2G_WORKSPACE``
    explícitos), un agente que cambió de directorio puede estar operando en
    silencio sobre otra investigación. Este helper centraliza el mensaje para
    que todos los comandos lo emitan igual.

    Args:
        ws: El ``Workspace`` devuelto por ``resolve_workspace``.

    Returns:
        Lista con el warning si ``ws.source == "cwd"``; lista vacía si no.
    """
    if ws.source == "cwd":
        return [WORKSPACE_WALKUP_WARNING]
    return []
