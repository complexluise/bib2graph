"""schemas — schema Arrow canónico, validación de filas y modelos base.

Única fuente de verdad del schema de 23 columnas (API.md §1.1).
Ningún otro módulo define columnas; todos importan de aquí.

R1 (ADR 0023):
- ``ProvenanceEvent``: modelo Pydantic del evento de procedencia (fuente única).
- ``CORPUS_SCHEMA`` sigue siendo la definición Arrow autoritativa; ``PaperRow``
  se alinea campo a campo y hay una función ``assert_schema_parity()`` que falla
  si divergen.  El test de paridad (``test_schemas.py``) la invoca.
"""

from __future__ import annotations

import json

import pyarrow as pa
from pydantic import BaseModel, field_validator

from bib2graph.constants import Col, CurationStatus

SCHEMA_VERSION = "1"

# ---------------------------------------------------------------------------
# ProvenanceEvent — fuente única del evento de procedencia (R1, ADR 0023)
# ---------------------------------------------------------------------------


class ProvenanceEvent(BaseModel):
    """Evento de procedencia de un paper en el Corpus.

    Fuente única: reemplaza los dicts construidos a mano en ≥4 sitios.
    El parseo falla ruidoso ante JSON corrupto (no ``return []`` silencioso).

    Serialización determinista: los campos se exportan en el orden de
    declaración del modelo (Pydantic v2 mantiene el orden de los campos).

    Fields:
        action: Tipo de evento (``'fetched'``, ``'seeded'``, ``'accepted'``,
            ``'rejected'``, ``'fetched_by_id'``).
        equation_id: ID de la ecuación de búsqueda que originó el paper, o
            ``None`` si no aplica.
        chaining_hop: Profundidad del chaining (1 = primera expansión), o
            ``None`` si es semilla.
        source: Fuente del evento (``'openalex'``, ``'bibtex'``,
            ``'chaining:backward'``, etc.), o ``None``.
        fetched_at: Timestamp ISO8601 UTC del fetch, o ``None``.
        decided_by: Identificador de quien tomó la decisión, o ``None``.
        decided_at: Timestamp ISO8601 UTC de la decisión, o ``None``.
    """

    action: str
    equation_id: str | None = None
    chaining_hop: int | None = None
    source: str | None = None
    fetched_at: str | None = None
    decided_by: str | None = None
    decided_at: str | None = None

    model_config = {"frozen": True}  # serialización determinista

    def to_dict(self) -> dict[str, object]:
        """Serializa el evento a dict con orden de campos estable.

        Returns:
            Dict con los campos en el orden de declaración del modelo.
        """
        return self.model_dump()

    @classmethod
    def parse_list(cls, provenance_json: str | None) -> list[ProvenanceEvent]:
        """Parsea el JSON de provenance como lista de ``ProvenanceEvent``.

        Falla ruidoso ante JSON corrupto: lanza ``ValueError`` con un mensaje
        accionable.  No devuelve ``[]`` en silencio (cierra el bug de
        ``_parse_provenance`` en ``backends/memory.py``).

        Args:
            provenance_json: String JSON o ``None``.

        Returns:
            Lista de ``ProvenanceEvent`` (puede ser vacía si el JSON es
            ``None`` o lista vacía válida).

        Raises:
            ValueError: Si el JSON es corrupto o no es una lista de objetos.
        """
        if not provenance_json:
            return []
        try:
            raw = json.loads(provenance_json)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"JSON de provenance corrupto (no se puede parsear): {exc!r}. "
                f"Valor recibido: {provenance_json!r}"
            ) from exc
        if not isinstance(raw, list):
            raise ValueError(
                f"provenance debe ser una lista JSON, se recibió: {type(raw).__name__}. "
                f"Valor: {provenance_json!r}"
            )
        events: list[ProvenanceEvent] = []
        for i, item in enumerate(raw):
            if not isinstance(item, dict):
                raise ValueError(
                    f"provenance[{i}] debe ser un objeto JSON, "
                    f"se recibió: {type(item).__name__}. "
                    f"Valor: {item!r}"
                )
            try:
                events.append(cls(**item))
            except Exception as exc:
                raise ValueError(
                    f"provenance[{i}] no es un ProvenanceEvent válido: {exc!r}. "
                    f"Objeto: {item!r}"
                ) from exc
        return events

    @classmethod
    def dump_list(cls, events: list[ProvenanceEvent]) -> str:
        """Serializa una lista de eventos a JSON string determinista.

        Args:
            events: Lista de ``ProvenanceEvent``.

        Returns:
            String JSON con los eventos en orden.
        """
        return json.dumps([e.to_dict() for e in events], ensure_ascii=False)


# ---------------------------------------------------------------------------
# Schema Arrow canónico — 23 columnas según API.md §1.1
# ---------------------------------------------------------------------------

_LIST_STR = pa.list_(pa.string())

CORPUS_SCHEMA: pa.Schema = pa.schema(
    [
        # Identificadores
        pa.field(Col.ID, pa.string(), nullable=False),
        pa.field(Col.SOURCE_ID, pa.string(), nullable=True),
        pa.field(Col.DOI, pa.string(), nullable=True),
        # Metadatos bibliográficos
        pa.field(Col.TITLE, pa.string(), nullable=False),
        pa.field(Col.YEAR, pa.int32(), nullable=True),
        pa.field(Col.ABSTRACT, pa.string(), nullable=True),
        pa.field(Col.SOURCE, pa.string(), nullable=True),
        pa.field(Col.LANGUAGE, pa.string(), nullable=True),
        pa.field(Col.PUBLISHER, pa.string(), nullable=True),
        pa.field(Col.RESEARCH_AREAS, _LIST_STR, nullable=True),
        # Curación y procedencia
        pa.field(Col.IS_SEED, pa.bool_(), nullable=False),
        pa.field(Col.CURATION_STATUS, pa.string(), nullable=False),
        pa.field(Col.PROVENANCE, pa.string(), nullable=True),
        # Autores
        pa.field(Col.AUTHORS_RAW, _LIST_STR, nullable=True),
        pa.field(Col.AUTHORS_ID, _LIST_STR, nullable=True),
        pa.field(Col.AUTHORS_AFFILIATIONS, _LIST_STR, nullable=True),
        # Keywords
        pa.field(Col.KEYWORDS_RAW, _LIST_STR, nullable=True),
        pa.field(Col.KEYWORDS_ID, _LIST_STR, nullable=True),
        # Instituciones
        pa.field(Col.INSTITUTIONS_RAW, _LIST_STR, nullable=True),
        pa.field(Col.INSTITUTIONS_ID, _LIST_STR, nullable=True),
        # Referencias y citantes
        pa.field(Col.REFERENCES_ID, _LIST_STR, nullable=True),
        pa.field(Col.REFERENCES_DOI, _LIST_STR, nullable=True),
        pa.field(Col.CITED_BY_ID, _LIST_STR, nullable=True),
    ]
)

# Columnas obligatoriamente no-nulas (nullable=False en el schema)
_NON_NULLABLE_COLS: frozenset[str] = frozenset(
    {Col.ID, Col.TITLE, Col.IS_SEED, Col.CURATION_STATUS}
)


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
    for col_name in _NON_NULLABLE_COLS:
        if col_name in actual_fields:
            chunk = table.column(col_name)
            null_count = chunk.null_count
            if null_count > 0:
                raise SchemaError(
                    f"Columna '{col_name}' no permite nulos pero tiene "
                    f"{null_count} valor(es) nulo(s)."
                )


# ---------------------------------------------------------------------------
# Modelo Pydantic v2 para validación de fila individual (add_paper)
# ---------------------------------------------------------------------------

_VALID_CURATION: frozenset[str] = frozenset(
    {CurationStatus.CANDIDATE, CurationStatus.ACCEPTED, CurationStatus.REJECTED}
)


class PaperRow(BaseModel):
    """Validación de una fila antes de insertarla en el Corpus vía ``add_paper``.

    Los campos opcionales tienen ``None`` como default; los obligatorios no.
    Coincide con el schema Arrow canónico (CORPUS_SCHEMA).

    El orden de los campos debe mantenerse en sincronía con ``CORPUS_SCHEMA``
    (verificado por ``assert_schema_parity()`` y el test de paridad en
    ``tests/unit/test_schemas.py``).
    """

    # Obligatorios (no-nullable en Arrow) — mismo orden que CORPUS_SCHEMA
    id: str
    source_id: str | None = None
    doi: str | None = None
    title: str
    year: int | None = None
    abstract: str | None = None
    source: str | None = None
    language: str | None = None
    publisher: str | None = None
    research_areas: list[str] | None = None
    is_seed: bool
    curation_status: str
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

    @field_validator(Col.CURATION_STATUS)
    @classmethod
    def _curation_valida(cls, v: str) -> str:
        if v not in _VALID_CURATION:
            raise ValueError(
                f"curation_status debe ser uno de {set(_VALID_CURATION)}, "
                f"se recibió '{v}'."
            )
        return v


# ---------------------------------------------------------------------------
# Paridad PaperRow ⇄ CORPUS_SCHEMA (verificada por test; R1 ADR 0023)
# ---------------------------------------------------------------------------


def assert_schema_parity() -> None:
    """Verifica que ``PaperRow`` y ``CORPUS_SCHEMA`` tengan los mismos campos.

    Falla ruidoso si los campos divergen (uno tiene un campo que el otro no).
    Llamada desde el test de paridad en ``tests/unit/test_schemas.py``.

    Raises:
        AssertionError: Si los nombres de campo de ``PaperRow`` no coinciden
            exactamente con los de ``CORPUS_SCHEMA``.
    """
    schema_fields = [f.name for f in CORPUS_SCHEMA]
    model_fields = list(PaperRow.model_fields.keys())

    schema_set = set(schema_fields)
    model_set = set(model_fields)

    only_in_schema = schema_set - model_set
    only_in_model = model_set - schema_set

    errors: list[str] = []
    if only_in_schema:
        errors.append(
            f"Campos en CORPUS_SCHEMA pero NO en PaperRow: {sorted(only_in_schema)}"
        )
    if only_in_model:
        errors.append(
            f"Campos en PaperRow pero NO en CORPUS_SCHEMA: {sorted(only_in_model)}"
        )
    if errors:
        raise AssertionError("PaperRow y CORPUS_SCHEMA divergen:\n" + "\n".join(errors))
