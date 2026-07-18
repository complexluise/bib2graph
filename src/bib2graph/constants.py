"""constants — fuente única de vocabulario para bib2graph.

Capa base del grafo de dependencias: ``constants`` → núcleo puro → costuras → CLI.
Ningún módulo por debajo define estas constantes; todo el código las importa de aquí.

Un typo de columna falla en import/type-check (mypy), no en runtime tardío.
Cierra CONSTANTS de la Nota 06 (ADR 0023).
"""

from __future__ import annotations

from enum import StrEnum


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
    SOURCE_ID = "source_id"
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


class CurationStatus(StrEnum):
    """Valores canónicos del campo ``curation_status``.

    Única fuente de verdad; elimina los literales ``"candidate"``,
    ``"accepted"``, ``"rejected"`` dispersos en 11 archivos.
    """

    CANDIDATE = "candidate"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


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


def doi_to_url(doi: str | None) -> str | None:
    """Deriva la URL canónica ``https://doi.org/<doi>`` a partir de un DOI.

    Criterio compartido por ``networks/decorate.py`` y ``service/reads.py``
    para evitar drift en la regla de derivación.

    Args:
        doi: String del DOI (sin prefijo URL), o ``None``.

    Returns:
        ``"https://doi.org/<doi>"`` si ``doi`` es un string no vacío;
        ``None`` en cualquier otro caso (None, vacío).
    """
    if isinstance(doi, str) and doi:
        return f"https://doi.org/{doi}"
    return None


def openalex_id_to_url(source_id: str | None) -> str | None:
    """Deriva la URL de OpenAlex ``https://openalex.org/<source_id>`` desde un id corto.

    ``source_id`` (``Col.SOURCE_ID``) es el id corto de OpenAlex (p. ej. ``W12345``)
    cuando el paper proviene de ``OpenAlexSource`` — las demás fuentes (p. ej.
    ``BibtexSource``) siempre lo dejan en ``None``, así que un ``source_id`` truthy
    es seguro de interpretar como id de OpenAlex.

    Args:
        source_id: Id corto de OpenAlex, o ``None``.

    Returns:
        ``"https://openalex.org/<source_id>"`` si ``source_id`` es un string no
        vacío; ``None`` en cualquier otro caso.
    """
    if isinstance(source_id, str) and source_id:
        return f"https://openalex.org/{source_id}"
    return None


def resolve_paper_url(doi: str | None, source_id: str | None) -> str | None:
    """URL canónica del paper: DOI primero, OpenAlex como fallback (#203).

    Precedencia: ``https://doi.org/<doi>`` si hay DOI; si no, y solo si hay
    ``source_id`` (OpenAlex), ``https://openalex.org/<source_id>``. ``None``
    si no hay ninguno de los dos — nunca inventa una URL.

    Reusa ``doi_to_url``/``openalex_id_to_url`` (fuente única de cada regla de
    derivación) para no duplicar el criterio de "string no vacío".

    Args:
        doi: DOI del paper (sin prefijo URL), o ``None``.
        source_id: Id corto de OpenAlex, o ``None``.

    Returns:
        La URL canónica, o ``None`` si no hay DOI ni ``source_id``.
    """
    return doi_to_url(doi) or openalex_id_to_url(source_id)


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
