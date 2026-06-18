"""api.deps — Dependencias FastAPI (workspace singleton, token, write lock).

Provee tres dependencias inyectables:

  - ``get_workspace`` — devuelve el singleton ``Workspace`` inyectado al crear
    la app (no resuelve desde el entorno en cada request).
  - ``require_token`` — ``Depends`` que lanza ``HTTPException(401)`` si el
    token del header es inválido o está ausente.
  - ``acquire_write_lock`` — ``Depends`` que adquiere el ``WriteLock`` global
    serializado (una escritura a la vez, ADR 0028 §6 / ADR 0019).

Uso en ``app.py``:
    from bib2graph.api.deps import make_deps
    get_ws, check_token, write_lock = make_deps(ws, token)
"""

from __future__ import annotations

import threading
from collections.abc import Generator
from typing import Any


def make_deps(ws: Any, token: str) -> tuple[Any, Any, Any]:
    """Fábrica de las tres dependencias inyectables.

    Cierra sobre ``ws`` y ``token`` para que no sean globales mutables.

    Args:
        ws: ``Workspace`` resuelto — singleton por proceso.
        token: Token efímero generado en el arranque.

    Returns:
        Tupla ``(get_workspace_dep, require_token_dep, acquire_write_lock_dep)``
        listas para usarse con ``Depends(...)``.
    """
    from fastapi import Depends, HTTPException
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

    from bib2graph.api.security import verify_token

    _lock = threading.Lock()
    _bearer_scheme = HTTPBearer(auto_error=False)

    async def get_workspace_dep() -> Any:
        """Devuelve el workspace singleton inyectado al crear la app."""
        return ws

    async def require_token_dep(
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    ) -> None:
        """Verifica el Bearer token; lanza 401 si falta o es inválido."""
        if credentials is None or not verify_token(credentials.credentials, token):
            raise HTTPException(status_code=401, detail="Token inválido o ausente.")

    def acquire_write_lock_dep() -> Generator[None, None, None]:
        """Adquiere el lock global de escritura; libera al salir del scope."""
        with _lock:
            yield

    return get_workspace_dep, require_token_dep, acquire_write_lock_dep
