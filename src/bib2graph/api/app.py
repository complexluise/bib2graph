"""api.app — Fábrica de la aplicación FastAPI (Hito G3, ADR 0028).

``create_app`` monta los routers, CORS, el handler global de excepciones y el
token de seguridad.  Es el único lugar del paquete ``api/`` que importa
``fastapi`` directamente — y solo se llama cuando la GUI está instalada.

El núcleo (``corpus``, ``service``, etc.) nunca importa este módulo.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from bib2graph.workspace import Workspace

_DEFAULT_CORS = ["http://localhost:5173", "http://127.0.0.1:5173"]


def create_app(
    ws: Workspace,
    *,
    token: str,
    cors_origins: list[str] | None = None,
) -> Any:
    """Construye y configura la aplicación FastAPI.

    Args:
        ws: Workspace resuelto — singleton por proceso.
        token: Token efímero generado en el arranque (``b2g gui``).
        cors_origins: Orígenes CORS permitidos.  Default:
            ``["http://localhost:5173", "http://127.0.0.1:5173"]``.

    Returns:
        Instancia de ``FastAPI`` lista para ``uvicorn.run``.
    """
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from starlette.requests import Request

    from bib2graph.api.deps import make_deps
    from bib2graph.api.routers.curate import make_curate_router
    from bib2graph.api.routers.reads import make_reads_router

    app = FastAPI(
        title="bib2graph API",
        description="API local de bib2graph — Hito G3 (ADR 0028).",
    )

    # CORS: permite la SPA en desarrollo (Vite dev-server)
    origins = cors_origins if cors_origins is not None else _DEFAULT_CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Dependencias — fábrica para evitar globales mutables
    get_ws_dep, require_token_dep, write_lock_dep = make_deps(ws, token)

    # Routers
    reads_router = make_reads_router(get_ws_dep, require_token_dep)
    curate_router = make_curate_router(get_ws_dep, require_token_dep, write_lock_dep)

    app.include_router(reads_router)
    app.include_router(curate_router)

    # Handler global de excepciones: B2GError + Exception → JSONResponse con envelope
    from bib2graph.api.envelopes import make_error_response
    from bib2graph.service.errors import B2GError

    @app.exception_handler(B2GError)
    async def b2g_error_handler(request: Request, exc: B2GError) -> Any:
        """Convierte ``B2GError`` en JSONResponse con el envelope canónico."""
        path = request.url.path.lstrip("/").replace("/", "_")
        return make_error_response(path, exc)

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception) -> Any:
        """Convierte cualquier excepción no capturada en JSONResponse 500."""
        path = request.url.path.lstrip("/").replace("/", "_")
        return make_error_response(path, exc)

    return app
