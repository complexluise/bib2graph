"""backends — costuras de almacenamiento tabular para el ``Corpus``.

Re-exporta el Protocol y las implementaciones disponibles en el núcleo.
``DuckDBBackend`` se agrega en el Hito 3 (no importar aquí hasta que exista).
"""

from __future__ import annotations

from bib2graph.backends.base import TabularBackend
from bib2graph.backends.memory import InMemoryBackend

__all__ = [
    "InMemoryBackend",
    "TabularBackend",
]
