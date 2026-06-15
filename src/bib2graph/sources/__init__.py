"""sources — costuras de siembra del ``Corpus``.

Re-exporta el Protocol ``Source``, el modelo ``SeedResult``, y las
implementaciones disponibles en v0.1:

- ``OpenAlexSource``: backbone de datos (ADR 0007). Siembra desde la API de
  OpenAlex con traducción PASSTHROUGH y reporte de límites.
- ``BibtexSource``: fuente secundaria. Siembra desde un archivo ``.bib``
  (requiere el extra ``[bibtex]``).

Ver ``docs/API.md`` §2, ADR 0007/0012/0017/0018.
"""

from __future__ import annotations

from bib2graph.sources.base import SeedResult, Source
from bib2graph.sources.bibtex import BibtexSource
from bib2graph.sources.openalex import OpenAlexSource

__all__ = [
    "BibtexSource",
    "OpenAlexSource",
    "SeedResult",
    "Source",
]
