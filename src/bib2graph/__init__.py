"""bib2graph — librería para construir redes bibliométricas reproducibles.

Hito 1: núcleo de la tabla canónica ``Corpus``. Expone el wrapper de semántica
de valor (``Corpus``), sus metadatos sellados (``Manifest``, ``CorpusSnapshot``)
y la excepción de contrato (``SchemaError``). Ver ``docs/API.md`` §1.
"""

from __future__ import annotations

from bib2graph.corpus import Corpus, CorpusSnapshot, Manifest
from bib2graph.schemas import SchemaError

__all__ = [
    "Corpus",
    "CorpusSnapshot",
    "Manifest",
    "SchemaError",
]
