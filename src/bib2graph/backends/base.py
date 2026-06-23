"""backends.base — Protocol ``TabularBackend``.

Define la costura entre ``Corpus`` y sus implementaciones de almacenamiento.
El núcleo depende **solo de este Protocol**, nunca de una implementación
concreta (ADR 0002, 0015).

Semántica de las operaciones
-----------------------------
Las mutaciones (``add_paper``, ``merge``, ``apply_curation``) son
**semántica de valor**: cada operación devuelve una **nueva instancia**
del backend con el estado resultante; la instancia original no muta.
Esto mantiene la semántica inmutable del ``Corpus`` del Hito 1 y hace
los tests deterministas.

La igualdad (``__eq__``) y el ``__len__`` operan sobre el contenido
Arrow exportado, no sobre detalles internos del backend.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

import pyarrow as pa

if TYPE_CHECKING:
    pass


@runtime_checkable
class TabularBackend(Protocol):
    """Contrato de almacenamiento tabular para el ``Corpus``.

    Cualquier implementación que satisfaga este Protocol puede respaldar un
    ``Corpus``.  Las reglas de identidad/hash/merge del ADR 0013 (D1/D2/D3)
    son **contrato de este Protocol**: cada implementación debe cumplirlas.

    Implementaciones actuales:
    - ``InMemoryBackend`` (núcleo puro, sin I/O — Hito 1.5).
    - ``DuckDBBackend`` (biblioteca viva persistida — Hito 3).

    Invariantes que toda implementación debe garantizar
    ---------------------------------------------------
    D1  ``id`` estable y determinista (``_compute_id`` de ``schemas``).
    D2  ``corpus_hash`` order-independent: mismas filas en distinto orden →
        mismo hash.
    D3  ``merge`` idempotente: orden por primera aparición, dedup por ``id``,
        resolución de ``curation_status`` por decisión humana más reciente.
    """

    def to_arrow(self) -> pa.Table:
        """Exporta el contenido completo como tabla Arrow canónica.

        Es el puente estable hacia los proyectores y analizadores puros.

        Returns:
            Tabla Arrow con el schema canónico del Corpus.
        """
        ...

    def add_paper(self, row: dict[str, object]) -> TabularBackend:
        """Agrega una fila ya validada y devuelve un backend nuevo.

        El ``id`` debe estar calculado antes de llamar este método; la
        validación ``PaperRow`` corre en ``Corpus.add_paper``.

        Args:
            row: Diccionario con todos los campos del schema canónico.

        Returns:
            Nueva instancia del backend con el paper agregado.
        """
        ...

    def merge(self, other_table: pa.Table) -> TabularBackend:
        """Fusiona ``other_table`` en este backend (D3).

        Devuelve un backend nuevo con el resultado de la fusión.  El orden
        de filas resultante es determinista: primero las filas de ``self``
        en su orden original, luego las filas nuevas de ``other_table``.

        Args:
            other_table: Tabla Arrow a fusionar.

        Returns:
            Nueva instancia del backend con las filas fusionadas.
        """
        ...

    def apply_curation(
        self,
        ids: list[str],
        *,
        action: str,
        by: str,
        decided_at: str | None = None,
        source: str | None = None,
    ) -> TabularBackend:
        """Aplica accept/reject a los papers indicados y devuelve backend nuevo.

        Agrega un evento al log ``provenance`` con ``action``, ``decided_by``,
        ``source`` y ``decided_at`` (ISO8601 UTC).  La instancia original no muta.

        R2 (ADR 0017 enmendado): ``decided_at`` se inyecta desde la frontera
        (CLI) para que el núcleo no llame al reloj.  Si es ``None``, la
        implementación usa ``datetime.now(UTC)`` como fallback (ergonomía
        para uso como librería sin frontera CLI).

        Args:
            ids: Lista de ``id`` a actualizar.
            action: ``'accepted'`` o ``'rejected'``.
            by: Identificador de quien toma la decisión.
            decided_at: Timestamp ISO8601 UTC de la decisión.  Si es ``None``,
                la implementación usa ``datetime.now(UTC)`` como fallback.
            source: Origen del evento (p. ej. criterio de filtro PRISMA).
                Si es ``None``, el campo ``source`` del evento queda vacío.

        Returns:
            Nueva instancia del backend con la curación aplicada.
        """
        ...

    def filter_view(self, view: Literal["seeds", "candidates", "accepted"]) -> pa.Table:
        """Devuelve una tabla Arrow filtrada por la vista pedida.

        Args:
            view: ``'seeds'`` (``is_seed == True``), ``'candidates'``
                (``curation_status == 'candidate'``), o ``'accepted'``
                (``curation_status == 'accepted'``).

        Returns:
            Tabla Arrow filtrada.
        """
        ...

    def corpus_hash(self) -> str:
        """Computa el hash order-independent del contenido (D2).

        Returns:
            Hexdigest SHA-256 del contenido de la tabla.
        """
        ...

    def __len__(self) -> int:
        """Número de papers en el backend."""
        ...

    def __eq__(self, other: object) -> bool:
        """Igualdad canónica por ``corpus_hash`` (D2)."""
        ...

    def add_referenced_refs(self, ref_ids: list[str], *, cycle_round: int) -> int:
        """Appendea IDs backward observados a ``referenced_but_not_fetched`` (#54).

        Solo inserta los IDs que aún no están en la tabla (idempotente).

        Args:
            ref_ids: IDs de OpenAlex observados en backward chaining.
            cycle_round: Número de ronda del ciclo en curso.

        Returns:
            Número de IDs nuevos insertados.
        """
        ...

    def referenced_refs_count(self) -> int:
        """Número de IDs en ``referenced_but_not_fetched``.

        Returns:
            Conteo total de filas en la tabla auxiliar.
        """
        ...

    def referenced_refs(self) -> list[str]:
        """Lista de IDs en ``referenced_but_not_fetched``, en orden de inserción.

        Returns:
            Lista de ``ref_id``.
        """
        ...

    def add_external_id(self, paper_id: str, engine: str, id: str) -> None:
        """Registra un ID externo para un paper dado un motor (ADR 0036 opción C).

        Idempotente: si ya existe una entrada ``(paper_id, engine)``, el valor
        se reemplaza (un ID por motor por paper).

        Args:
            paper_id: ID interno del paper en el corpus.
            engine: Nombre del motor / fuente del ID (p. ej. ``'openalex'``,
                ``'semanticscholar'``, ``'doi'``).
            id: El ID externo correspondiente a ese motor.
        """
        ...

    def external_ids_for(self, paper_id: str) -> dict[str, str]:
        """Devuelve todos los IDs externos registrados para un paper.

        Args:
            paper_id: ID interno del paper en el corpus.

        Returns:
            Diccionario ``{engine: id}`` con todos los IDs registrados para
            ese paper.  Vacío si el paper no tiene IDs externos registrados.
        """
        ...

    def all_external_ids(self) -> list[tuple[str, str, str]]:
        """Devuelve todas las entradas de la tabla ``external_ids``.

        Returns:
            Lista de tuplas ``(paper_id, engine, id)`` en orden no definido.
        """
        ...
