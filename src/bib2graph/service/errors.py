"""service.errors — Jerarquía de errores B2GError (capa de servicios neutral).

Define la jerarquía de excepciones tipadas que comparten CLI y API (ADR 0028).
Esta capa es agnóstica de transporte: sin ``print``, ``sys.exit``, Click ni
FastAPI.

Mapeo de exit codes (ADR 0021):
  0: éxito
  1: uso (opción faltante/inválida)
  2: datos (schema inválido, ids inexistentes, filtro inválido)
  3: dependencia/capacidad faltante (ImportError)
  4: red (httpx.HTTPError / timeout)
  5: store/snapshot bloqueado o corrupto (StoreLockedError / OSError)

``code_for(exc)`` devuelve el exit code correspondiente a una excepción
sin efectos de I/O; lo usa la capa de servicio y los adaptadores (CLI/API)
para derivar exit codes / HTTP status sin duplicar la política.
"""

from __future__ import annotations

import httpx

# ---------------------------------------------------------------------------
# Jerarquía de excepciones tipadas
# ---------------------------------------------------------------------------


class B2GError(Exception):
    """Base de todos los errores accionables de bib2graph."""

    exit_code: int = 1
    code: str = "B2G_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UsageError(B2GError):
    """Error de uso: opción faltante o inválida (exit 1)."""

    exit_code = 1
    code = "USAGE_ERROR"


class DataError(B2GError):
    """Error de datos: schema inválido, ids inexistentes, filtro inválido (exit 2)."""

    exit_code = 2
    code = "DATA_ERROR"


class DependencyError(B2GError):
    """Dependencia o capacidad faltante: ImportError / AttributeError (exit 3)."""

    exit_code = 3
    code = "DEPENDENCY_ERROR"


class NetworkError(B2GError):
    """Error de red: httpx.HTTPError / timeout (exit 4)."""

    exit_code = 4
    code = "NETWORK_ERROR"


class StoreError(B2GError):
    """Store/snapshot bloqueado o corrupto (exit 5)."""

    exit_code = 5
    code = "STORE_ERROR"


# ---------------------------------------------------------------------------
# Helper neutral de mapeo error→código (sin I/O)
# ---------------------------------------------------------------------------


def code_for(exc: BaseException) -> int:
    """Devuelve el exit code correspondiente a una excepción.

    Política (ADR 0021):
    - ``B2GError`` y subclases → ``.exit_code`` propio.
    - ``OSError`` (incluye ``StoreLockedError``) → 5.
    - ``ImportError`` → 3.
    - ``httpx.HTTPError`` → 4 (httpx es dependencia del núcleo).

    No llama a ``sys.exit`` ni imprime nada; es una función pura de mapeo.

    Args:
        exc: La excepción capturada.

    Returns:
        Entero 0-5 del contrato (ADR 0021).
    """
    if isinstance(exc, B2GError):
        return exc.exit_code
    if isinstance(exc, OSError):
        return 5
    if isinstance(exc, ImportError):
        return 3
    if isinstance(exc, httpx.HTTPError):
        return 4
    # Excepción no mapeada: propagar sin asignar código (el llamador decide).
    raise TypeError(f"No hay mapeo de exit code para {type(exc).__name__!r}") from exc
