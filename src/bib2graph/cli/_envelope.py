"""cli._envelope — Envelope JSON común y versionado (adaptador CLI).

Re-exporta ``build_envelope`` y ``ENVELOPE_SCHEMA_VERSION`` desde
``bib2graph.service.envelope`` (ADR 0028): el contrato vive en la capa de
servicios neutral; ``cli/`` conserva solo el I/O del adaptador
(``emit``/``emit_human``).

Los imports existentes del CLI y de los tests —
``from bib2graph.cli._envelope import build_envelope, ENVELOPE_SCHEMA_VERSION``
— resuelven a los **mismos objetos** que ``bib2graph.service.envelope``.

La estructura del envelope (ADR 0021):

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

# Re-exportar desde la capa de servicios neutral (ADR 0028).
# Los imports existentes de cli/ y tests resuelven a los mismos objetos.
from bib2graph.service.envelope import ENVELOPE_SCHEMA_VERSION, build_envelope

__all__ = [
    "ENVELOPE_SCHEMA_VERSION",
    "build_envelope",
    "emit",
    "emit_human",
]


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
