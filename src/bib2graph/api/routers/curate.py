"""api.routers.curate — POST /api/paper/{id}/curate (Hito G3, ADR 0028).

Endpoint de escritura: aplica una decisión de curación a un paper individual.
Requiere el WriteLock para serializar escrituras (ADR 0028 §6 / ADR 0019).

El reloj (``decided_at``) se inyecta aquí — frontera de la API — igual que
el CLI lo inyecta en su frontera (R2/ADR 0017).
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from bib2graph.api.envelopes import build_ok_response


class CurateRequest(BaseModel):
    """Body del endpoint de curación."""

    decision: str


def make_curate_router(
    get_workspace_dep: Any,
    require_token_dep: Any,
    acquire_write_lock_dep: Any,
) -> APIRouter:
    """Fábrica del router de curación con las dependencias inyectadas.

    Crea un ``APIRouter`` nuevo por invocación para evitar que múltiples
    llamadas (p. ej. en tests) acumulen handlers en el mismo router.

    Args:
        get_workspace_dep: Dependencia que devuelve el workspace singleton.
        require_token_dep: Dependencia de verificación de token.
        acquire_write_lock_dep: Dependencia del lock de escritura serializado.

    Returns:
        ``APIRouter`` con el endpoint POST montado.
    """
    router = APIRouter()

    @router.post("/api/paper/{paper_id}/curate")
    async def curate_paper_endpoint(
        paper_id: str,
        body: CurateRequest,
        ws: Any = Depends(get_workspace_dep),
        _token: None = Depends(require_token_dep),
        _lock: Generator[None, None, None] = Depends(acquire_write_lock_dep),
    ) -> Any:
        """Aplica ``decision`` (``accepted``/``rejected``) al paper indicado.

        Toma el WriteLock global: una escritura a la vez (ADR 0028 §6).
        Inyecta ``decided_at`` en la frontera API (R2/ADR 0017).
        """
        from bib2graph.service.curate import curate_paper

        # R2: el reloj se inyecta en la frontera (la API es una frontera igual
        # que el CLI); el servicio no llama datetime.now().
        now = datetime.now(UTC)
        data = curate_paper(
            ws.library_path,
            paper_id,
            decision=body.decision,
            by="gui",
            decided_at=now,
        )
        return build_ok_response("curate_paper", data)

    return router
