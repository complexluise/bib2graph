"""stores — costuras de persistencia de la biblioteca viva.

Re-exporta el Protocol ``Store`` y las implementaciones disponibles.

``DuckDBStore`` es la costura por defecto (biblioteca viva, ADR 0009).
Costuras futuras (``ZoteroStore``, ``Neo4jStore``) se agregan cuando
existan (lección 5 de v0: no publicar lo que no existe).
"""

from __future__ import annotations

from bib2graph.stores.base import Store
from bib2graph.stores.duckdb import DuckDBStore

__all__ = [
    "DuckDBStore",
    "Store",
]
