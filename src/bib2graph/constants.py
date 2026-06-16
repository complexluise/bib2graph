"""constants — fuente única de vocabulario para bib2graph.

Capa base del grafo de dependencias: ``constants`` → núcleo puro → costuras → CLI.
Ningún módulo por debajo define estas constantes; todo el código las importa de aquí.

Un typo de columna falla en import/type-check (mypy), no en runtime tardío.
Cierra CONSTANTS de la Nota 06 (ADR 0023).
"""

from __future__ import annotations

from enum import StrEnum

# ---------------------------------------------------------------------------
# Col — nombres canónicos de columna del Corpus (23 columnas según CORPUS_SCHEMA)
# ---------------------------------------------------------------------------


class Col(StrEnum):
    """Nombres canónicos de columna del schema Arrow del Corpus.

    Coincide exactamente con ``CORPUS_SCHEMA`` en ``schemas.py``.
    Usar ``Col.X`` (no ``"x"`` literal) garantiza que un typo falla en
    import/type-check (mypy strict), no en runtime.

    Ejemplo::

        table.column(Col.REFERENCES_ID)
        row[Col.CURATION_STATUS]
        f"SELECT * FROM corpus WHERE {Col.CURATION_STATUS} = 'accepted'"
        # (para SQL, usar Col.X.value)
    """

    # Identificadores
    ID = "id"
    OPENALEX_ID = "openalex_id"
    DOI = "doi"

    # Metadatos bibliográficos
    TITLE = "title"
    YEAR = "year"
    ABSTRACT = "abstract"
    SOURCE = "source"
    LANGUAGE = "language"
    PUBLISHER = "publisher"
    RESEARCH_AREAS = "research_areas"

    # Curación y procedencia
    IS_SEED = "is_seed"
    CURATION_STATUS = "curation_status"
    PROVENANCE = "provenance"

    # Autores
    AUTHORS_RAW = "authors_raw"
    AUTHORS_ID = "authors_id"
    AUTHORS_AFFILIATIONS = "authors_affiliations"

    # Keywords
    KEYWORDS_RAW = "keywords_raw"
    KEYWORDS_ID = "keywords_id"

    # Instituciones
    INSTITUTIONS_RAW = "institutions_raw"
    INSTITUTIONS_ID = "institutions_id"

    # Referencias y citantes
    REFERENCES_ID = "references_id"
    REFERENCES_DOI = "references_doi"
    CITED_BY_ID = "cited_by_id"


# ---------------------------------------------------------------------------
# CurationStatus — valores canónicos de curation_status
# ---------------------------------------------------------------------------


class CurationStatus(StrEnum):
    """Valores canónicos del campo ``curation_status``.

    Única fuente de verdad; elimina los literales ``"candidate"``,
    ``"accepted"``, ``"rejected"`` dispersos en 11 archivos.
    """

    CANDIDATE = "candidate"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


# ---------------------------------------------------------------------------
# NetworkKind — tipos de red bibliométrica
# ---------------------------------------------------------------------------


class NetworkKind(StrEnum):
    """Tipos de red bibliométrica disponibles.

    Fuente única para ``NetworkSpec.kind`` (``Literal``) y ``_QUICK_KINDS``
    en ``networks/facade.py``.  Los 5 kinds del Hito 2.
    """

    BIBLIOGRAPHIC_COUPLING = "bibliographic_coupling"
    COCITATION = "cocitation"
    AUTHOR_COLLAB = "author_collab"
    INSTITUTION_COLLAB = "institution_collab"
    KEYWORD_COOCCURRENCE = "keyword_cooccurrence"


# ---------------------------------------------------------------------------
# LIST_COLUMNS — columnas de tipo list[string] (centraliza _LIST_COLS y _LIST_COL_NAMES)
# ---------------------------------------------------------------------------

LIST_COLUMNS: frozenset[str] = frozenset(
    {
        Col.RESEARCH_AREAS,
        Col.AUTHORS_RAW,
        Col.AUTHORS_ID,
        Col.AUTHORS_AFFILIATIONS,
        Col.KEYWORDS_RAW,
        Col.KEYWORDS_ID,
        Col.INSTITUTIONS_RAW,
        Col.INSTITUTIONS_ID,
        Col.REFERENCES_ID,
        Col.REFERENCES_DOI,
        Col.CITED_BY_ID,
    }
)
