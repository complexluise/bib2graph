"""cli._click_error_handler — Intercepta errores de Click y los emite como envelope.

Cierra el gap del contrato ``schema="1"`` que detectó #283 (auditoría AX
capstone e2e 0.12.0): los errores de parseo de Click (``NoSuchCommand``,
``NoSuchOption``, ``BadParameter``, y toda subclase de
``click.exceptions.UsageError``) escapaban al cuerpo del comando y por lo
tanto no pasaban por el decorador ``@handle_errors`` — salían como
**texto plano a stderr** (``Error de uso: …``) en lugar del envelope
canónico. Un agente que siempre parsea JSON en stdout rompía: recibía texto
no-JSON y no podía rutear el error por el mismo canal.

Enmienda al ADR 0021 (2026-10-11): estos errores se re-canalizan al envelope
**en modo JSON**. En modo humano el comportamiento pre-existente (texto a
stderr + exit 2) queda intacto para no romper el flujo interactivo.

Función pura, sin I/O global ni estado; el I/O se hace con ``print``/
``sys.stderr`` explícitos vía los helpers de ``cli/_envelope`` (no rompe el
contrato de la capa de servicio neutral — es la **única** función del CLI
que cruza la frontera de transporte porque tiene que decidir el canal de
salida; ADR 0028).
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any

import click

# Mensaje de ``NoSuchCommand`` tiene la forma ``No such command '<name>'.``
# (con o sin punto final, según la versión de Click); extraemos el nombre
# intentado con un regex tolerante. Para otras subclases de ``UsageError``
# (``NoSuchOption``, ``BadParameter``, ``MissingArgument``) el verb está en
# ``exc.ctx.command.name``.
_NO_SUCH_COMMAND_RE = re.compile(r"No such command '([^']+)'")


def extract_command_from_usage_error(exc: click.exceptions.UsageError) -> str:
    """Extrae **best-effort** el nombre del subcomando intentado del ``UsageError``.

    Args:
        exc: La excepción ``click.exceptions.UsageError`` capturada.

    Returns:
        El nombre del verb intentado (``"monitor"``, ``"build"``, …) o
        ``""`` si no se puede determinar. Esto es **best-effort**: para
        ``NoSuchCommand`` parseamos el ``message``; para el resto usamos
        ``exc.ctx.command.name``.
    """
    msg = exc.message or ""
    m = _NO_SUCH_COMMAND_RE.search(msg)
    if m is not None:
        return m.group(1)
    ctx = exc.ctx
    if ctx is not None:
        command = getattr(ctx, "command", None)
        if command is not None:
            name = getattr(command, "name", None)
            if isinstance(name, str) and name:
                return name
    return ""


def emit_click_usage_error_envelope(
    exc: click.exceptions.UsageError,
    *,
    command: str,
    json_mode: bool,
) -> int:
    """Emite un ``click.exceptions.UsageError`` como envelope o como texto humano.

    Args:
        exc: La excepción ``UsageError`` capturada en ``main()``.
        command: Nombre best-effort del subcomando intentado (de
            ``extract_command_from_usage_error``).
        json_mode: Si ``True``, emite el envelope ``schema="1"`` a stdout;
            si ``False``, emite el texto humano a stderr (comportamiento
            pre-existente, intacto).

    Returns:
        El ``exit_code`` a devolver (``2``, parse error de Click — coherente
        con la tabla de exit codes del ADR 0021 §D para ``UsageError``).
    """
    exit_code = 2  # Click emite exit 2 para errores de parseo; lo respetamos.

    if json_mode:
        envelope: dict[str, Any] = {
            "schema": "1",
            "ok": False,
            "command": command,
            "exit_code": exit_code,
            "data": {},
            "warnings": [],
            "error": {"code": "USAGE_ERROR", "message": exc.message or ""},
        }
        print(json.dumps(envelope, ensure_ascii=False, default=str))
        sys.stdout.flush()
    else:
        print(
            f"Error de uso: {exc.format_message()}",
            file=sys.stderr,
        )

    return exit_code
