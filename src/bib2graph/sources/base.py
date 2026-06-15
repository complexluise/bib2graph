"""base — Protocol ``Source`` y modelo ``SeedResult``.

Define los contratos públicos de siembra:
- ``Source``: Protocol ``@runtime_checkable`` con ``seed()`` / ``load()``.
- ``SeedResult``: resultado de ``seed()`` con el corpus, la query ejecutada y
  el reporte de traducción.

Ver ``docs/API.md`` §2 y ADR 0018 (mínimo universal vs enriquecimiento opcional).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from bib2graph.corpus import Corpus


class SeedResult(BaseModel):
    """Resultado de ``Source.seed()``.

    Agrupa el corpus sembrado, la query exacta ejecutada (consciencia de
    traducción, ADR 0007) y el reporte de mapeo (qué mapeó limpio, qué se
    aproximó, qué se descartó).

    ``corpus`` se valida en runtime (``arbitrary_types_allowed`` porque ``Corpus``
    no es un ``BaseModel``). No hay circularidad: ``corpus.py`` no importa
    ``sources``.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    corpus: Corpus
    executed_query: str
    translation_report: list[str]


@runtime_checkable
class Source(Protocol):
    """Convierte una entrada externa en un ``Corpus``.

    El acceso a campos es DEFENSIVO (sin ``KeyError``).  Debe entregar al
    menos el MÍNIMO UNIVERSAL (``id``, ``title``, ``year``, ``authors_raw``,
    ``keywords_raw``); el enriquecimiento (refs/citantes/afiliaciones/
    instituciones) es OPCIONAL (ADR 0018).
    """

    def seed(self, query: str) -> SeedResult:
        """Siembra desde una ecuación de búsqueda.

        Args:
            query: Ecuación de búsqueda (WoS-style o nativa OpenAlex).

        Returns:
            ``SeedResult`` con el corpus, la query ejecutada y el reporte
            de traducción.
        """
        ...

    def load(self, path: str) -> Corpus:
        """Siembra desde un archivo (export/pearls).

        Args:
            path: Ruta al archivo de entrada.

        Returns:
            ``Corpus`` con ``is_seed=True`` en todas las filas.
        """
        ...
