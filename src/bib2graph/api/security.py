"""api.security — Token efímero para la API local (ADR 0028, Nota 12 C.3).

El token se genera en ``b2g gui`` con ``secrets.token_urlsafe(32)`` y se
inyecta en ``create_app``.  La verificación usa ``secrets.compare_digest``
para evitar timing attacks (aunque el servidor solo escucha en 127.0.0.1).

El token viaja en el header ``Authorization: Bearer <token>``.
"""

from __future__ import annotations

import secrets


def generate_token() -> str:
    """Genera un token efímero de 32 bytes (URL-safe base64).

    Returns:
        Token de 43 caracteres URL-safe.
    """
    return secrets.token_urlsafe(32)


def verify_token(provided: str, expected: str) -> bool:
    """Verifica el token con comparación de tiempo constante.

    Args:
        provided: Token enviado por el cliente (del header ``Authorization``).
        expected: Token canónico generado en el arranque.

    Returns:
        ``True`` si los tokens coinciden.
    """
    return secrets.compare_digest(provided, expected)
