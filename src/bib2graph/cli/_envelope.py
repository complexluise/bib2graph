"""cli._envelope — Envelope JSON común y versionado.

Define la estructura del envelope JSON estable del CLI agente-native (ADR 0010):

    {
        "schema": "1",
        "ok": bool,
        "command": str,
        "exit_code": int,
        "data": {...},
        "warnings": [...],
        "error": null | {"code": str, "message": str}
    }

La versión de contrato es ``"1"`` hasta que se declare una ruptura.
"""

from __future__ import annotations

import json
import sys
from typing import Any

# Versión del contrato del envelope JSON.
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
    """Construye el envelope JSON estable del CLI.

    Args:
        command: Nombre del subcomando.
        ok: ``True`` si el comando terminó con éxito.
        data: Datos de resultado del comando (vacío ``{}`` en error).
        exit_code: Código de salida del proceso.
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


def emit(envelope: dict[str, Any]) -> None:
    """Imprime el envelope JSON en stdout y vacía el buffer.

    Args:
        envelope: El envelope ya construido con ``build_envelope``.
    """
    print(json.dumps(envelope, ensure_ascii=False, default=str))
    sys.stdout.flush()


def emit_human(text: str) -> None:
    """Imprime texto legible en stdout (modo humano).

    Args:
        text: Texto a imprimir.
    """
    print(text)
