"""Schema común de la sandbox de exploración.

Lo único que exporta este módulo es ``CORPUS_COLUMNS`` y ``new_row()``. Los
scripts de la sandbox lo importan para no divergir en nombres de columnas.

NO es el schema canónico de ``bib2graph`` (``docs/ARCHITECTURE.md`` §3) — es
una aproximación exploratoria que la sandbox usa para detectar qué necesita
el schema real. Los hallazgos se vuelcan en ``informe_ied.md``.

Convención de tipos: las listas (autores, keywords, refs) se serializan como
``";"``-separado en CSV y como ``list[str]`` en parquet. El round-trip CSV
<-> parquet se hace explícito en cada script.
"""
from __future__ import annotations

CORPUS_COLUMNS: list[str] = [
    "id",
    "doi",
    "title",
    "year",
    "abstract",
    "authors_raw",
    "authors_id",
    "authors_affiliations",
    "keywords_raw",
    "keywords_id",
    "references_doi",
    "source",
    "language",
    "is_seed",
]


def new_row() -> dict[str, object]:
    """Devuelve una fila vacía con todas las columnas en None/lista vacía."""
    return {c: (None if c not in _LIST_COLUMNS else []) for c in CORPUS_COLUMNS}


_LIST_COLUMNS = {"authors_raw", "authors_id", "authors_affiliations",
                 "keywords_raw", "keywords_id", "references_doi"}
