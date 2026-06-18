"""service — Capa de servicios neutral de bib2graph (ADR 0028).

Agnóstica de transporte: sin ``print``, ``sys.exit``, Click ni FastAPI.
CLI y API son adaptadores delgados de esta capa.

Contrato público re-exportado:
  - ``build_envelope``, ``ENVELOPE_SCHEMA_VERSION`` — envelope JSON versionado.
  - ``B2GError``, ``UsageError``, ``DataError``, ``DependencyError``,
    ``NetworkError``, ``StoreError`` — jerarquía de errores tipados.
  - ``code_for`` — helper de mapeo error→exit code (sin I/O).
"""

from __future__ import annotations

from bib2graph.service.envelope import ENVELOPE_SCHEMA_VERSION, build_envelope
from bib2graph.service.errors import (
    B2GError,
    DataError,
    DependencyError,
    NetworkError,
    StoreError,
    UsageError,
    code_for,
)

__all__ = [
    "ENVELOPE_SCHEMA_VERSION",
    "B2GError",
    "DataError",
    "DependencyError",
    "NetworkError",
    "StoreError",
    "UsageError",
    "build_envelope",
    "code_for",
]
