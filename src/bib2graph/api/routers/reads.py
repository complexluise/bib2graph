"""api.routers.reads — 6 GET endpoints de lectura (Hito G3, ADR 0028).

Cada endpoint llama a ``service.reads.*``, envuelve el resultado con
``build_ok_response`` y deja que el handler global de excepciones convierta
los ``B2GError`` en respuestas de error.

Endpoints:
  GET /api/workspace
  GET /api/rounds
  GET /api/paper/{id}
  GET /api/paper/{id}/scent
  GET /api/network/{kind}
  GET /api/compare?a=&b=

``data`` siempre es un dict: las lecturas que devuelven lista se envuelven
en un dict con clave semántica (``rounds``, ``nodes``, etc.) para respetar
la firma de ``build_envelope(data: dict)``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from bib2graph.api.envelopes import build_ok_response


def make_reads_router(
    get_workspace_dep: Any,
    require_token_dep: Any,
) -> APIRouter:
    """Fábrica del router de lecturas con las dependencias inyectadas.

    Crea un ``APIRouter`` nuevo por invocación para evitar que múltiples
    llamadas (p. ej. en tests) acumulen handlers en el mismo router.

    Args:
        get_workspace_dep: Dependencia que devuelve el workspace singleton.
        require_token_dep: Dependencia de verificación de token.

    Returns:
        ``APIRouter`` con los 6 endpoints de lectura montados.
    """
    router = APIRouter()

    @router.get("/api/workspace")
    async def get_workspace_endpoint(
        ws: Any = Depends(get_workspace_dep),
        _token: None = Depends(require_token_dep),
    ) -> Any:
        """Estado del workspace activo."""
        from bib2graph.service.reads import get_workspace

        data = get_workspace(ws)
        return build_ok_response("get_workspace", data)

    @router.get("/api/rounds")
    async def list_rounds_endpoint(
        ws: Any = Depends(get_workspace_dep),
        _token: None = Depends(require_token_dep),
    ) -> Any:
        """Lista de snapshots + entrada viva."""
        from bib2graph.service.reads import list_rounds

        rounds = list_rounds(ws)
        return build_ok_response("list_rounds", {"rounds": rounds})

    @router.get("/api/paper/{paper_id}")
    async def get_paper_endpoint(
        paper_id: str,
        ws: Any = Depends(get_workspace_dep),
        _token: None = Depends(require_token_dep),
    ) -> Any:
        """Fila completa del corpus para un paper."""
        from bib2graph.service.reads import get_paper

        data = get_paper(ws, paper_id)
        return build_ok_response("get_paper", data)

    @router.get("/api/paper/{paper_id}/scent")
    async def get_scent_endpoint(
        paper_id: str,
        ws: Any = Depends(get_workspace_dep),
        _token: None = Depends(require_token_dep),
    ) -> Any:
        """Score de acoplamiento + vecinos de un paper."""
        from bib2graph.service.reads import get_scent

        data = get_scent(ws, paper_id)
        return build_ok_response("get_scent", data)

    @router.get("/api/network/{kind}")
    async def get_network_endpoint(
        kind: str,
        ws: Any = Depends(get_workspace_dep),
        _token: None = Depends(require_token_dep),
    ) -> Any:
        """Red de la ronda viva para el kind dado."""
        from bib2graph.service.reads import get_network

        data = get_network(ws, kind)
        return build_ok_response("get_network", data)

    @router.get("/api/compare")
    async def compare_rounds_endpoint(
        a: str,
        b: str,
        ws: Any = Depends(get_workspace_dep),
        _token: None = Depends(require_token_dep),
    ) -> Any:
        """Diff entre dos snapshots (added/removed paper_ids + metricas)."""
        from bib2graph.service.reads import compare_rounds

        data = compare_rounds(ws, a, b)
        return build_ok_response("compare_rounds", data)

    return router
