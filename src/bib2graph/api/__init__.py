"""api — Costura FastAPI local (Hito G3, ADR 0028).

Import perezoso: FastAPI solo se importa dentro de ``create_app``; el núcleo
puede importarse sin fastapi instalado.  Usar:

    from bib2graph.api import create_app
    app = create_app(ws, token="...")

o, más habitual, dejar que ``cli/commands/gui.py`` lo invoque.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from bib2graph.workspace import Workspace


def create_app(
    ws: Workspace,
    *,
    token: str,
    cors_origins: list[str] | None = None,
) -> Any:
    """Fábrica de la app FastAPI (import perezoso de fastapi).

    Args:
        ws: Workspace resuelto — inyectado una sola vez (singleton por proceso).
        token: Token efímero generado por ``b2g gui``.
        cors_origins: Lista de orígenes CORS permitidos.  Por defecto:
            ``["http://localhost:5173", "http://127.0.0.1:5173"]``.

    Returns:
        Instancia de ``FastAPI`` configurada con routers, CORS y seguridad.
    """
    from bib2graph.api.app import create_app as _create_app

    return _create_app(ws, token=token, cors_origins=cors_origins)
