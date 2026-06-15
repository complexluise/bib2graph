"""Smoke tests del Hito 0 (andamiaje).

Los justos: que el paquete importe sin efectos colaterales y que el entry point
del CLI exista y devuelva el exit code del placeholder. El núcleo real se testea
desde el Hito 1 (ver ``docs/ROADMAP.md``).
"""

from __future__ import annotations

import importlib
import sys


def test_import_sin_efectos_colaterales() -> None:
    """Importar bib2graph no debe tocar red, disco ni estado global (lección 6)."""
    sys.modules.pop("bib2graph", None)
    modulo = importlib.import_module("bib2graph")
    assert modulo is not None


def test_cli_placeholder_devuelve_exit_1() -> None:
    """El placeholder del CLI sale con 1 (error de uso) hasta el Hito 6."""
    from bib2graph.cli import main

    assert main() == 1
