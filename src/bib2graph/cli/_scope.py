"""cli._scope — Helper compartido de mapeo de vocab ``--scope``.

Extraído de ``cli.commands.build`` y ``cli.commands.export`` (ambos tenían
una copia literal del mismo mapeo) para evitar divergencia (DRY, hallazgo de
revisión arquitectónica 0.14.0).
"""

from __future__ import annotations


def map_scope(scope: str) -> str:
    """Mapea el vocab de ``--scope`` (CLI) al vocab interno de ``corpus.scoped()``.

    ``--scope`` usa ``seeds`` (forma corta), mientras que ``corpus.scoped()``
    espera ``seeds_only``.  Los demás valores son idénticos en ambos vocabs.

    Args:
        scope: Valor del flag ``--scope`` (``all`` | ``accepted`` | ``seeds``).

    Returns:
        Vocabulario interno: ``all`` | ``accepted`` | ``seeds_only``.
    """
    if scope == "seeds":
        return "seeds_only"
    return scope
