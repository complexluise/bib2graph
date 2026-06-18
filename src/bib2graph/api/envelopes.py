"""api.envelopes — Handler de excepciones y mapeo código→HTTP (ADR 0028 §7).

Convierte ``B2GError`` / ``Exception`` en ``JSONResponse`` con el status HTTP
adecuado.  El body siempre es el envelope ``schema="1"`` íntegro construido
con ``service.build_envelope``; la SPA lee ``error.code`` para la lógica,
NO el status HTTP.

Mapeo código→HTTP (ADR 0028 §7):
  0 → 200   (éxito)
  1 → 400   (UsageError: parámetro faltante/inválido)
  2 → 422   (DataError: schema inválido / id inexistente)
  3 → 501   (DependencyError: dependencia faltante)
  4 → 502   (NetworkError: red no disponible)
  5 → 409   (StoreError: store bloqueado/corrupto — retry cross-process diferido)

Excepción no mapeada → 500 (error interno).
"""

from __future__ import annotations

from typing import Any

# Mapeo exit-code → HTTP status (ADR 0028 §7)
_CODE_TO_HTTP: dict[int, int] = {
    0: 200,
    1: 400,
    2: 422,
    3: 501,
    4: 502,
    5: 409,
}

# Excepción inesperada (bug interno): NO es un error de contrato 0-5. Usamos un
# código fuera del rango (70 = EX_SOFTWARE) que http_status_for mapea a 500 por
# defecto. La SPA lee error.code ("INTERNAL_ERROR") y el HTTP status, no este número.
_INTERNAL_ERROR_EXIT_CODE = 70


def http_status_for(code: int) -> int:
    """Devuelve el HTTP status correspondiente al exit-code del contrato.

    Args:
        code: Exit code 0-5 (ADR 0021).

    Returns:
        HTTP status code según el mapeo de ADR 0028 §7.
    """
    return _CODE_TO_HTTP.get(code, 500)


def make_error_response(
    command: str,
    exc: BaseException,
) -> Any:
    """Construye una ``JSONResponse`` a partir de una excepción.

    Reusa ``service.build_envelope`` y ``service.code_for`` para no reimplementar
    la política de errores.

    Args:
        command: Nombre del endpoint / operación (para el envelope).
        exc: La excepción capturada.

    Returns:
        ``fastapi.responses.JSONResponse`` con el envelope íntegro en el body
        y el status HTTP del mapeo.
    """
    from fastapi.responses import JSONResponse

    from bib2graph.service.envelope import build_envelope
    from bib2graph.service.errors import B2GError, code_for

    if isinstance(exc, B2GError):
        exit_code = exc.exit_code
        error_code = exc.code
        message = exc.message
    else:
        # Excepción no mapeada por code_for → 500
        try:
            exit_code = code_for(exc)
            error_code = type(exc).__name__.upper()
            message = str(exc)
        except TypeError:
            # Excepción no mapeada = bug interno → HTTP 500 (NO 409: no es un
            # conflicto de store; mentirle a la SPA sugeriría reintentar).
            exit_code = _INTERNAL_ERROR_EXIT_CODE
            error_code = "INTERNAL_ERROR"
            message = str(exc)

    status = http_status_for(exit_code)
    envelope = build_envelope(
        command=command,
        ok=False,
        data={},
        exit_code=exit_code,
        error={"code": error_code, "message": message},
    )
    return JSONResponse(status_code=status, content=envelope)


def exception_handler_factory(command: str) -> Any:
    """Fábrica del handler de excepciones para FastAPI.

    Devuelve un handler async compatible con
    ``app.add_exception_handler(Exception, handler)``.

    Args:
        command: Prefijo del endpoint usado en el envelope de error.

    Returns:
        Handler async para ``app.add_exception_handler``.
    """
    from starlette.requests import Request

    async def handler(request: Request, exc: Exception) -> Any:
        return make_error_response(command, exc)

    return handler


def build_ok_response(command: str, data: dict[str, Any]) -> Any:
    """Construye una ``JSONResponse`` de éxito con el envelope canónico.

    Args:
        command: Nombre del endpoint / operación.
        data: Payload del resultado (siempre dict).

    Returns:
        ``fastapi.responses.JSONResponse`` con status 200 y el envelope íntegro.
    """
    from fastapi.responses import JSONResponse

    from bib2graph.service.envelope import build_envelope

    envelope = build_envelope(
        command=command,
        ok=True,
        data=data,
        exit_code=0,
    )
    return JSONResponse(status_code=200, content=envelope)
