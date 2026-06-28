"""cli._deprecation — Helper de avisos de deprecación (ADR 0038, #165).

Centraliza la emisión de avisos de deprecación para verbos sueltos y
ejecutables legados.  El aviso va SIEMPRE a stderr (tanto en modo humano
como en modo ``--json``) para no contaminar stdout (#151).

En modo ``--json`` el mensaje también se propaga al top-level ``warnings[]``
del envelope vía ``build_envelope(..., warnings=[msg])``.

Formato canónico::

    AVISO: 'b2g networks' está deprecado y se eliminará en 0.11.0; usá 'b2g build --spec'.

Retiro planificado: 0.11.0 (ADR 0038 P1).
"""

from __future__ import annotations

import sys


def emit_deprecation(
    old: str,
    new: str,
    *,
    removed_in: str = "0.11.0",
) -> str:
    """Emite un aviso de deprecación a stderr y devuelve el mensaje.

    El mensaje se imprime **siempre a stderr** (nunca a stdout), lo que
    garantiza que el stdout en modo ``--json`` permanezca limpio (#151).
    El retorno permite al llamador enhebrarlo en el ``warnings[]`` del
    envelope JSON (top-level, no ``data.deprecation``).

    Args:
        old: Forma deprecada (p.ej. ``'b2g networks'``).
        new: Forma canónica sugerida (p.ej. ``'b2g build --spec'``).
        removed_in: Versión en la que se eliminará (default ``"0.11.0"``).

    Returns:
        El mensaje de aviso emitido, listo para enhebrarlo en el envelope.

    Example::

        msg = emit_deprecation("b2g networks", "b2g build --spec")
        envelope = build_envelope(..., warnings=[msg])
    """
    msg = f"AVISO: '{old}' está deprecado y se eliminará en {removed_in}; usá '{new}'."
    print(msg, file=sys.stderr)
    return msg
