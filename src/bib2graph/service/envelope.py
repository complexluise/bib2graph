"""service.envelope — Envelope JSON común y versionado (capa de servicios neutral).

Define la estructura del envelope JSON estable del contrato agente-native
(ADR 0021/0028):

    {
        "schema": "1",
        "ok": bool,
        "command": str,
        "exit_code": int,
        "data": {...},
        "warnings": [...],
        "error": null | {"code": str, "message": str}
    }

Esta capa es agnóstica de transporte: sin ``print``, ``sys.exit``, Click ni
FastAPI. El I/O (``emit``/``emit_human``) vive en ``cli/_envelope.py``.

La versión de contrato es ``"1"`` hasta que se declare una ruptura.
"""

from __future__ import annotations

from typing import Any

ENVELOPE_SCHEMA_VERSION = "1"


def build_envelope(
    *,
    command: str,
    ok: bool,
    data: dict[str, Any],
    exit_code: int,
    warnings: list[str] | None = None,
    error: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Construye el envelope JSON estable del contrato.

    Args:
        command: Nombre del subcomando u operación.
        ok: ``True`` si la operación terminó con éxito.
        data: Datos de resultado (vacío ``{}`` en error).
        exit_code: Código de resultado (0-5, ADR 0021).
        warnings: Lista de advertencias opcionales.
        error: Dict ``{"code": str, "message": str}`` o ``None``.

    Returns:
        Dict con la estructura canónica del envelope.
    """
    return {
        "schema": ENVELOPE_SCHEMA_VERSION,
        "ok": ok,
        "command": command,
        "exit_code": exit_code,
        "data": data,
        "warnings": warnings or [],
        "error": error,
    }
