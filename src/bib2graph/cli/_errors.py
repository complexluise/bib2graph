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
from bib2graph.cli._options import json_mode as _resolve_json_mode
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


# Importación perezosa del envelope para evitar importación circular
def _emit_error_envelope(
    command: str,
    exit_code: int,
    error_code: str,
    message: str,
    json_mode: bool,
    *,
    subcode: str | None = None,
) -> None:
    """Emite el envelope de error si está en modo JSON; en modo humano, imprime texto.

    Args:
        subcode: Subcódigo opcional del error (ADR 0045 #258), poblado solo
            para ``NETWORK_ERROR``/exit 4 (``RATE_LIMITED``/``UPSTREAM_TIMEOUT``).
            ``None`` para todo lo demás — no se agrega al dict de error para
            no ensuciar el envelope con una clave ``null`` en casos no-red.
    """
    if json_mode:
        from bib2graph.cli._envelope import build_envelope, emit

        error: dict[str, str | None] = {"code": error_code, "message": message}
        if subcode is not None:
            error["subcode"] = subcode

        envelope = build_envelope(
            command=command,
            ok=False,
            data={},
            exit_code=exit_code,
            error=error,
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

    ADR 0045 (#258) — grieta 3a: si la excepción capturada es ``NetworkError``
    con ``.subcode`` seteado (``RATE_LIMITED``/``UPSTREAM_TIMEOUT``), se
    propaga a ``error.subcode`` en el envelope. Para ``httpx.HTTPStatusError``
    no traducido explícitamente por el source, se deriva el subcode del
    ``response.status_code`` cuando está disponible (429/504); para
    ``httpx.TimeoutException`` (sin respuesta), se asume ``UPSTREAM_TIMEOUT``.
    En cualquier otro caso, ``subcode`` queda ``None`` (aditivo, no rompe).

    Args:
        command: Nombre del subcomando (para el envelope).

    Returns:
        Decorador que envuelve la función Click.
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            _local_flag = bool(kwargs.get("json_output", False))
            json_mode: bool = _resolve_json_mode(_local_flag)

            try:
                return func(*args, **kwargs)
            except B2GError as exc:
                subcode = getattr(exc, "subcode", None)
                _emit_error_envelope(
                    command,
                    exc.exit_code,
                    exc.code,
                    exc.message,
                    json_mode,
                    subcode=subcode,
                )
                sys.exit(exc.exit_code)
            except OSError as exc:
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
                msg = (
                    f"Error de red ({type(exc).__name__}): {exc}. "
                    "Verificá tu conexión a internet y reintentá."
                )
                _emit_error_envelope(
                    command,
                    4,
                    "NETWORK_ERROR",
                    msg,
                    json_mode,
                    subcode=_subcode_for_http_error(exc),
                )
                sys.exit(4)

        return wrapper  # type: ignore[return-value]

    return decorator


def _subcode_for_http_error(exc: httpx.HTTPError) -> str | None:
    """Deriva ``error.subcode`` (ADR 0045 #258) de una ``httpx.HTTPError`` cruda.

    Cubre el caso de un ``httpx.HTTPStatusError``/``httpx.TimeoutException``
    que llega a ``handle_errors`` sin haber sido traducido explícitamente a
    ``NetworkError`` por el source (p. ej. un source de terceros, o un 5xx
    no cubierto por el retry de OpenAlex). No inventa información: si no hay
    ``response`` con status HTTP tipado y no es un timeout, devuelve ``None``.

    Args:
        exc: La excepción ``httpx.HTTPError`` capturada.

    Returns:
        ``RATE_LIMITED``/``UPSTREAM_TIMEOUT`` cuando se puede derivar,
        ``None`` en cualquier otro caso.
    """
    from bib2graph.service.errors import subcode_for_status

    response = getattr(exc, "response", None)
    if response is not None:
        status_code = getattr(response, "status_code", None)
        if status_code is not None:
            return subcode_for_status(int(status_code))
    if isinstance(exc, httpx.TimeoutException):
        return "UPSTREAM_TIMEOUT"
    return None
