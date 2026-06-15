"""cli._errors — Jerarquía de errores B2GError y decorador de captura.

Define la jerarquía de excepciones tipadas del CLI y el decorador
``@handle_errors`` que captura excepciones conocidas, emite el envelope
JSON de error y llama a ``sys.exit(code)``.

Mapeo de exit codes (ADR 0010):
  0: éxito
  1: uso (opción faltante/inválida)
  2: datos (schema inválido, ids inexistentes, filtro inválido)
  3: dependencia/capacidad faltante (ImportError, AttributeError)
  4: red (httpx.HTTPError / timeout)
  5: store/snapshot bloqueado o corrupto (StoreLockedError / OSError)
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

import httpx

F = TypeVar("F", bound=Callable[..., Any])


# ---------------------------------------------------------------------------
# Jerarquía de excepciones tipadas
# ---------------------------------------------------------------------------


class B2GError(Exception):
    """Base de todos los errores accionables del CLI bib2graph."""

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
# Decorador de captura
# ---------------------------------------------------------------------------


# Importación perezosa del envelope para evitar importación circular
def _emit_error_envelope(
    command: str,
    exit_code: int,
    error_code: str,
    message: str,
    json_mode: bool,
) -> None:
    """Emite el envelope de error si está en modo JSON; en modo humano, imprime texto."""
    if json_mode:
        from bib2graph.cli._envelope import build_envelope, emit

        envelope = build_envelope(
            command=command,
            ok=False,
            data={},
            exit_code=exit_code,
            error={"code": error_code, "message": message},
        )
        emit(envelope)
    else:
        print(f"Error: {message}", file=sys.stderr)


def handle_errors(command: str) -> Callable[[F], F]:
    """Decorador que captura excepciones conocidas y las convierte en exit codes.

    Captura (en orden de precedencia):
    - ``B2GError`` y subclases → exit code propio
    - ``StoreLockedError`` (OSError) → exit 5
    - ``ImportError`` / ``AttributeError`` accionables → exit 3
    - ``httpx.HTTPError`` / ``httpx.TimeoutException`` → exit 4

    Args:
        command: Nombre del subcomando (para el envelope).

    Returns:
        Decorador que envuelve la función Click.
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Determinar modo JSON desde kwargs o ctx
            json_mode: bool = kwargs.get("json_output", False) or kwargs.get(
                "json", False
            )

            try:
                return func(*args, **kwargs)
            except B2GError as exc:
                _emit_error_envelope(
                    command, exc.exit_code, exc.code, exc.message, json_mode
                )
                sys.exit(exc.exit_code)
            except OSError as exc:
                # StoreLockedError es subclase de OSError
                from bib2graph.backends.duckdb import StoreLockedError

                if isinstance(exc, StoreLockedError):
                    _emit_error_envelope(command, 5, "STORE_ERROR", str(exc), json_mode)
                    sys.exit(5)
                _emit_error_envelope(command, 5, "STORE_ERROR", str(exc), json_mode)
                sys.exit(5)
            except ImportError as exc:
                msg = (
                    f"Dependencia faltante: {exc}. "
                    "Instalá el extra requerido (ver pyproject.toml [project.optional-dependencies])."
                )
                _emit_error_envelope(command, 3, "DEPENDENCY_ERROR", msg, json_mode)
                sys.exit(3)
            except AttributeError as exc:
                msg = (
                    f"Capacidad no disponible en este source: {exc}. "
                    "Verificá que el source soporte la operación pedida."
                )
                _emit_error_envelope(command, 3, "DEPENDENCY_ERROR", msg, json_mode)
                sys.exit(3)
            except httpx.HTTPError as exc:
                # Captura por tipo: HTTPStatusError, ConnectError, TimeoutException,
                # RemoteProtocolError, TransportError y toda la jerarquía httpx.
                msg = (
                    f"Error de red ({type(exc).__name__}): {exc}. "
                    "Verificá tu conexión a internet y reintentá."
                )
                _emit_error_envelope(command, 4, "NETWORK_ERROR", msg, json_mode)
                sys.exit(4)

        return wrapper  # type: ignore[return-value]

    return decorator
