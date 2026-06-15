"""stores.base — Protocol ``Store``: persistencia de la biblioteca viva.

Define el contrato mínimo que cualquier implementación de store debe cumplir.
El núcleo depende solo de este Protocol, nunca de una implementación concreta.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from bib2graph.corpus import Corpus


@runtime_checkable
class Store(Protocol):
    """Contrato de persistencia de la biblioteca viva.

    Un ``Store`` sabe guardar y recuperar un ``Corpus`` entre sesiones.

    Implementaciones:
    - ``DuckDBStore`` (biblioteca viva en archivo ``.duckdb`` — Hito 3).
    - ``ZoteroStore`` (extra ``[zotero]`` — Hito 11, V1.1).
    - ``Neo4jStore`` (extra ``[neo4j]`` — Hito 11, post-V1.2).
    """

    def persist(self, corpus: Corpus) -> None:
        """Persiste el corpus en el store.

        Debe ser idempotente: persistir el mismo corpus dos veces no duplica
        filas (la llave natural es ``id``).

        Args:
            corpus: El ``Corpus`` a persistir.
        """
        ...

    def load(self) -> Corpus:
        """Carga el corpus acumulado desde el store.

        Returns:
            El ``Corpus`` acumulado en el store (puede estar vacío si es la
            primera carga).
        """
        ...
