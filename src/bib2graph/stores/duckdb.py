"""stores.duckdb — ``DuckDBStore``: fachada de costura sobre ``DuckDBBackend``.

Implementa el Protocol ``Store`` (``persist``/``load``) delegando toda la
I/O en ``DuckDBBackend``.  Es la costura por defecto para la biblioteca
viva (ADR 0009, 0015).

El ``DuckDBStore`` es una fachada delgada:
- ``persist`` hace un ``merge`` del corpus entrante en el backend persistido.
- ``load`` devuelve un ``Corpus`` respaldado por el ``DuckDBBackend`` del
  archivo (la bibliotheca viva acumulada).

Single-writer (ADR 0019): si el archivo está bloqueado por otro proceso,
``StoreLockedError`` se propaga; el CLI (Hito 6) lo mapea al exit code 5.
"""

from __future__ import annotations

from pathlib import Path

from bib2graph.backends.duckdb import DuckDBBackend, StoreLockedError
from bib2graph.corpus import Corpus
from bib2graph.cycle import CycleState
from bib2graph.schemas import CORPUS_SCHEMA

__all__ = ["CycleState", "DuckDBStore", "StoreLockedError"]


class DuckDBStore:
    """Fachada de persistencia sobre ``DuckDBBackend`` (ADR 0009, 0015).

    Implementa el Protocol ``Store``: ``persist`` / ``load``.

    Args:
        path: Ruta al archivo ``.duckdb`` de la biblioteca viva.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        # Abrir (o crear) el backend en disco; propaga StoreLockedError si bloqueado
        self._backend: DuckDBBackend = DuckDBBackend(path=self._path)

    # ------------------------------------------------------------------
    # Store Protocol
    # ------------------------------------------------------------------

    def persist(self, corpus: Corpus) -> None:
        """Persiste el corpus en la biblioteca viva (idempotente).

        Hace un merge del corpus entrante en el backend persistido.
        Idempotente: persistir el mismo corpus dos veces no duplica filas
        (el upsert por ``id`` garantiza la idempotencia, D1/D3).

        Args:
            corpus: El ``Corpus`` a persistir.
        """
        self._backend._upsert_table(corpus.to_arrow())

    def load(self) -> Corpus:
        """Carga el corpus acumulado desde la biblioteca viva.

        Devuelve un ``Corpus`` respaldado por el ``DuckDBBackend`` del
        archivo; las operaciones subsecuentes (``accept``, ``reject``,
        ``merge``) mutarán el archivo en disco.

        Returns:
            El ``Corpus`` acumulado en el store.
        """
        import pyarrow as pa

        table = self._backend.to_arrow()
        if len(table) == 0:
            table = pa.table(
                {f.name: pa.array([], type=f.type) for f in CORPUS_SCHEMA},
                schema=CORPUS_SCHEMA,
            )
        # Devolver un Corpus respaldado por el DuckDBBackend
        return Corpus.from_arrow(table, backend=self._backend)

    # ------------------------------------------------------------------
    # Acceso al backend subyacente (CycleState, query SQL)
    # ------------------------------------------------------------------

    @property
    def backend(self) -> DuckDBBackend:
        """Acceso directo al ``DuckDBBackend`` subyacente.

        Permite usar extensiones propias como ``loop_state()``,
        ``set_loop_state()`` y ``query(sql)``.

        Returns:
            El ``DuckDBBackend`` de esta biblioteca viva.
        """
        return self._backend
