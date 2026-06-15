"""schemas — schema Arrow canónico y validación de filas del Corpus.

Única fuente de verdad del schema de 22 columnas (API.md §1.1).
Ningún otro módulo define columnas; todos importan de aquí.
"""

from __future__ import annotations

import pyarrow as pa
from pydantic import BaseModel, field_validator

SCHEMA_VERSION = "1"

# ---------------------------------------------------------------------------
# Schema Arrow canónico — 22 columnas según API.md §1.1
# ---------------------------------------------------------------------------

_LIST_STR = pa.list_(pa.string())

CORPUS_SCHEMA: pa.Schema = pa.schema(
    [
        # Identificadores
        pa.field("id", pa.string(), nullable=False),
        pa.field("openalex_id", pa.string(), nullable=True),
        pa.field("doi", pa.string(), nullable=True),
        # Metadatos bibliográficos
        pa.field("title", pa.string(), nullable=False),
        pa.field("year", pa.int32(), nullable=True),
        pa.field("abstract", pa.string(), nullable=True),
        pa.field("source", pa.string(), nullable=True),
        pa.field("language", pa.string(), nullable=True),
        pa.field("publisher", pa.string(), nullable=True),
        pa.field("research_areas", _LIST_STR, nullable=True),
        # Curación y procedencia
        pa.field("is_seed", pa.bool_(), nullable=False),
        pa.field("curation_status", pa.string(), nullable=False),
        pa.field("provenance", pa.string(), nullable=True),
        # Autores
        pa.field("authors_raw", _LIST_STR, nullable=True),
        pa.field("authors_id", _LIST_STR, nullable=True),
        pa.field("authors_affiliations", _LIST_STR, nullable=True),
        # Keywords
        pa.field("keywords_raw", _LIST_STR, nullable=True),
        pa.field("keywords_id", _LIST_STR, nullable=True),
        # Instituciones
        pa.field("institutions_raw", _LIST_STR, nullable=True),
        pa.field("institutions_id", _LIST_STR, nullable=True),
        # Referencias y citantes
        pa.field("references_id", _LIST_STR, nullable=True),
        pa.field("references_doi", _LIST_STR, nullable=True),
        pa.field("cited_by_id", _LIST_STR, nullable=True),
    ]
)

# Columnas obligatoriamente no-nulas (nullable=False en el schema)
_NON_NULLABLE_COLS = {"id", "title", "is_seed", "curation_status"}


# ---------------------------------------------------------------------------
# Excepción de contrato
# ---------------------------------------------------------------------------


class SchemaError(Exception):
    """Violación del schema canónico Arrow del Corpus.

    Se lanza con el nombre de la columna y la descripción del problema para
    que el mensaje sea accionable (lección 7 de v0: fallar fuerte y ruidoso).
    """


# ---------------------------------------------------------------------------
# Validación de tabla Arrow
# ---------------------------------------------------------------------------


def validate_table(table: pa.Table) -> None:
    """Valida que ``table`` cumpla el schema canónico del Corpus.

    Comprueba columnas presentes, tipos Arrow y ausencia de nulos en las
    columnas obligatorias. Falla ruidoso nombrando la columna problemática.

    Args:
        table: Tabla Arrow a validar.

    Raises:
        SchemaError: Si falta alguna columna, el tipo no coincide o hay nulos
            en columnas no-nullable.
    """
    expected_fields = {f.name: f for f in CORPUS_SCHEMA}
    actual_fields = {f.name: f for f in table.schema}

    # 1. Columnas presentes
    missing = set(expected_fields) - set(actual_fields)
    if missing:
        # Ordenar para mensajes deterministas
        col = sorted(missing)[0]
        raise SchemaError(
            f"Columna requerida ausente: '{col}'. "
            f"El schema canónico exige {sorted(missing)}."
        )

    # 2. Tipos Arrow
    for name, expected_field in expected_fields.items():
        actual_field = actual_fields[name]
        if not actual_field.type.equals(expected_field.type):
            raise SchemaError(
                f"Tipo incorrecto en columna '{name}': "
                f"se esperaba {expected_field.type!s}, "
                f"se recibió {actual_field.type!s}."
            )

    # 3. No-nulos en columnas obligatorias
    for col in _NON_NULLABLE_COLS:
        if col in actual_fields:
            chunk = table.column(col)
            null_count = chunk.null_count
            if null_count > 0:
                raise SchemaError(
                    f"Columna '{col}' no permite nulos pero tiene "
                    f"{null_count} valor(es) nulo(s)."
                )


# ---------------------------------------------------------------------------
# Modelo Pydantic v2 para validación de fila individual (add_paper)
# ---------------------------------------------------------------------------

_VALID_CURATION = {"candidate", "accepted", "rejected"}


class PaperRow(BaseModel):
    """Validación de una fila antes de insertarla en el Corpus vía ``add_paper``.

    Los campos opcionales tienen ``None`` como default; los obligatorios no.
    Coincide con el schema Arrow canónico (CORPUS_SCHEMA).
    """

    # Obligatorios (no-nullable en Arrow)
    id: str
    title: str
    is_seed: bool
    curation_status: str

    # Opcionales
    openalex_id: str | None = None
    doi: str | None = None
    year: int | None = None
    abstract: str | None = None
    source: str | None = None
    language: str | None = None
    publisher: str | None = None
    research_areas: list[str] | None = None
    provenance: str | None = None
    authors_raw: list[str] | None = None
    authors_id: list[str] | None = None
    authors_affiliations: list[str] | None = None
    keywords_raw: list[str] | None = None
    keywords_id: list[str] | None = None
    institutions_raw: list[str] | None = None
    institutions_id: list[str] | None = None
    references_id: list[str] | None = None
    references_doi: list[str] | None = None
    cited_by_id: list[str] | None = None

    @field_validator("curation_status")
    @classmethod
    def _curation_valida(cls, v: str) -> str:
        if v not in _VALID_CURATION:
            raise ValueError(
                f"curation_status debe ser uno de {_VALID_CURATION}, se recibió '{v}'."
            )
        return v
