"""cli._errors — Jerarquía de errores B2GError y decorador de captura.

Re-exporta la jerarquía de errores desde ``bib2graph.service.errors`` (ADR
0028): la jerarquía y el mapeo error→código viven en la capa de servicios
neutral; ``cli/`` conserva solo el I/O del adaptador (``handle_errors`` y
``_emit_error_envelope``).

Los imports existentes del CLI y de los tests —
``from bib2graph.cli._errors import B2GError, DataError, ...`` — resuelven
a los **mismos objetos** que ``bib2graph.service.errors``.

Mapeo de exit codes (ADR 0021):
  0: éxito
  1: uso (opción faltante/inválida)
  2: datos (schema inválido, ids inexistentes, filtro inválido)
  3: dependencia/capacidad faltante (ImportError)
  4: red (httpx.HTTPError / timeout)
  5: store/snapshot bloqueado o corrupto (StoreLockedError / OSError)

R5 — footguns cerrados:
  - Rama muerta de OSError eliminada: el ``if isinstance(exc, StoreLockedError)``
    y el ``else`` producían el mismo exit code 5 (Nota 06, catálogo de secundarios).
    Ahora se captura OSError directamente, sin bifurcación innecesaria.
  - ``AttributeError`` ya NO se captura aquí como dependencia faltante
    (``exit 3``).  Un ``AttributeError`` genuino (bug en el código) no debe
    disfrazarse de "Capacidad no disponible" — eso escondía bugs reales.
    Los ``AttributeError`` controlados se convierten en ``DependencyError``
    mediante un **pre-check explícito en el borde CLI** (p. ej. ``chain.py``
    verifica ``hasattr(source, 'fetch_citing')`` antes de llamar al Forager).
    Un ``AttributeError`` inesperado ahora se propaga limpio (falla accionable).
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

import httpx

# Re-exportar la jerarquía desde la capa de servicios neutral (ADR 0028).
# Los imports existentes de cli/ y tests resuelven a los mismos objetos.
from bib2graph.service.errors import (
    B2GError,
    DataError,
    DependencyError,
    NetworkError,
    StoreError,
    UsageError,
)

__all__ = [
    "B2GError",
    "DataError",
    "DependencyError",
    "NetworkError",
    "StoreError",
    "UsageError",
    "handle_errors",
]

F = TypeVar("F", bound=Callable[..., Any])


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
    - ``OSError`` (incluye ``StoreLockedError``) → exit 5
    - ``ImportError`` → exit 3
    - ``httpx.HTTPError`` / ``httpx.TimeoutException`` → exit 4

    R5: ``AttributeError`` ya NO se captura aquí.  Un bug real no debe
    disfrazarse de "dependencia faltante"; los ``AttributeError`` controlados
    (p. ej. source sin ``fetch_citing``) se convierten en ``DependencyError``
    mediante un pre-check explícito en el comando CLI que los detecta (p. ej.
    ``chain.py`` verifica ``hasattr`` antes de llamar al Forager).
    Un ``AttributeError`` inesperado se propaga limpio para que sea visible y accionable.

    R5: la rama muerta del ``if isinstance(exc, StoreLockedError)`` / ``else``
    se eliminó: ambas ramas hacían exactamente lo mismo (exit 5).

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
                # Captura OSError y su subclase StoreLockedError (exit 5).
                # R5: rama muerta eliminada — el if/else previo hacía lo mismo.
                _emit_error_envelope(command, 5, "STORE_ERROR", str(exc), json_mode)
                sys.exit(5)
            except ImportError as exc:
                msg = (
                    f"Dependencia faltante: {exc}. "
                    "Instalá el extra requerido (ver pyproject.toml [project.optional-dependencies])."
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
