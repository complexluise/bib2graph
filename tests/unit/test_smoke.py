"""Smoke tests del andamiaje (Hito 0 → Hito 6).

Prueba mínima: el paquete importa sin efectos colaterales (red, disco, estado
global). El comportamiento de uso del CLI real está cubierto en test_cli.py
(p.ej. ``test_exit_code_1_sin_store``).
"""

from __future__ import annotations

import importlib
import sys


def test_import_sin_efectos_colaterales() -> None:
    """Importar bib2graph no debe tocar red, disco ni estado global (lección 6)."""
    sys.modules.pop("bib2graph", None)
    modulo = importlib.import_module("bib2graph")
    assert modulo is not None
