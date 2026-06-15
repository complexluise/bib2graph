"""CLI de bib2graph (Hito 0: placeholder).

La implementación real llega en el Hito 6 (ver ``docs/ROADMAP.md``). Mientras
tanto, este entry point existe para que ``b2g --help`` falle con un mensaje
útil en vez de un ``ModuleNotFoundError`` confuso.
"""

from __future__ import annotations

import sys


def main() -> int:
    """Placeholder honesto del CLI.

    Devuelve exit code 1 (error de uso) según el contrato de exit codes de
    ``docs/ARCHITECTURE.md`` §6.3 (Hito 6).
    """
    print(
        "bib2graph: el CLI no está implementado todavía. "
        "Estamos en Hito 0 (andamiaje). Ver docs/ROADMAP.md.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
