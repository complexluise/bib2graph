"""Tests de ``equation_hash`` en la metadata de schema Arrow (ADR 0050 D3).

Cubre:
- ``build_equation_metadata`` (función pura, helper compartido por
  ``InMemoryBackend``/``DuckDBBackend``): 1 ecuación → metadata correcta
  (hash verificado a mano); 0 o >1 ecuaciones → metadata ausente + warning.
- ``to_arrow()`` de ambos backends: la metadata viaja en el schema de la
  tabla exportada.
- ``corpus_hash`` NO cambia por la presencia de la tabla lateral
  ``equations`` (R2, ADR 0013/0017: identidad = contenido, no procedencia;
  la tabla lateral no participa de la identidad del corpus).
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Any

import pyarrow as pa
import pytest

from bib2graph.backends import InMemoryBackend, TabularBackend
from bib2graph.backends.duckdb import DuckDBBackend
from bib2graph.backends.memory import build_equation_metadata
from bib2graph.schemas import CORPUS_SCHEMA

BackendFactory = Callable[[pa.Table], TabularBackend]


@pytest.fixture(
    params=[
        pytest.param(lambda t: InMemoryBackend(t), id="memory", marks=pytest.mark.unit),
        pytest.param(
            lambda t: DuckDBBackend(t), id="duckdb", marks=pytest.mark.integration
        ),
    ]
)
def backend_factory(request: pytest.FixtureRequest) -> BackendFactory:
    """Devuelve una factory ``pa.Table → TabularBackend`` según el parámetro."""
    factory: BackendFactory = request.param
    return factory


def _empty_table() -> pa.Table:
    return pa.table({col: [] for col in CORPUS_SCHEMA.names}, schema=CORPUS_SCHEMA)


# ---------------------------------------------------------------------------
# build_equation_metadata — función pura
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_build_equation_metadata_hash_correcto_una_ecuacion() -> None:
    """1 ecuación → metadata con equation_hash = sha256(raw_query.strip()) exacto."""
    raw_query = '"unequal ecological exchange" OR "ecologically unequal exchange"'
    expected_hash = hashlib.sha256(raw_query.strip().encode("utf-8")).hexdigest()

    metadata, warning = build_equation_metadata(
        [
            {
                "equation_id": "eq-20260719T220850",
                "engine": "openalex",
                "raw_query": raw_query,
                "params_json": "{}",
                "label": None,
                "created_at": "2026-07-19T22:08:50+00:00",
            }
        ]
    )

    assert warning is None
    assert metadata[b"equation_hash"] == expected_hash.encode("utf-8")
    assert metadata[b"equation_hash_algo"] == b"sha256"
    assert metadata[b"equation_expression"] == raw_query.encode("utf-8")
    assert metadata[b"equation_id"] == b"eq-20260719T220850"


@pytest.mark.unit
def test_build_equation_metadata_strip_puro_no_colapsa_espacios_internos() -> None:
    """Normalización EXACTA: solo ``strip()`` — espacios al borde se eliminan,
    los internos NO se colapsan (contrato bit a bit con el consumidor programático)."""
    raw_query = "   ecological   debt   "
    expected_hash = hashlib.sha256(b"ecological   debt").hexdigest()

    metadata, warning = build_equation_metadata(
        [
            {
                "equation_id": "eq-1",
                "engine": "openalex",
                "raw_query": raw_query,
                "params_json": "{}",
                "label": None,
                "created_at": None,
            }
        ]
    )

    assert warning is None
    assert metadata[b"equation_hash"] == expected_hash.encode("utf-8")
    # equation_expression conserva la ecuación CRUDA (sin strip), para trazabilidad.
    assert metadata[b"equation_expression"] == raw_query.encode("utf-8")


@pytest.mark.unit
def test_build_equation_metadata_cero_ecuaciones_omite_y_advierte() -> None:
    """0 ecuaciones → metadata vacía + warning (no se inventa un hash)."""
    metadata, warning = build_equation_metadata([])

    assert metadata == {}
    assert warning is not None
    assert "0 ecuaci" in warning


@pytest.mark.unit
def test_build_equation_metadata_multiples_ecuaciones_omite_y_advierte() -> None:
    """>1 ecuaciones → metadata vacía + warning (no se puede elegir una sola)."""
    equations = [
        {
            "equation_id": "eq-1",
            "engine": "openalex",
            "raw_query": "a",
            "params_json": "{}",
            "label": None,
            "created_at": None,
        },
        {
            "equation_id": "eq-2",
            "engine": "openalex",
            "raw_query": "b",
            "params_json": "{}",
            "label": None,
            "created_at": None,
        },
    ]

    metadata, warning = build_equation_metadata(equations)

    assert metadata == {}
    assert warning is not None
    assert "2 ecuaci" in warning


# ---------------------------------------------------------------------------
# to_arrow() — paridad entre backends
# ---------------------------------------------------------------------------


def test_to_arrow_una_ecuacion_metadata_presente(
    backend_factory: BackendFactory,
) -> None:
    """``to_arrow()`` de un corpus con 1 ecuación trae ``equation_hash`` correcto."""
    raw_query = "  unequal exchange  "
    expected_hash = hashlib.sha256(raw_query.strip().encode("utf-8")).hexdigest()

    backend = backend_factory(_empty_table())
    backend.persist_equation(
        "eq-20260719T220850",
        engine="openalex",
        raw_query=raw_query,
        params_json='{"max_results": 150}',
    )

    table = backend.to_arrow()
    metadata: dict[bytes, bytes] = table.schema.metadata or {}

    assert metadata.get(b"equation_hash") == expected_hash.encode("utf-8")
    assert metadata.get(b"equation_hash_algo") == b"sha256"
    assert metadata.get(b"equation_id") == b"eq-20260719T220850"


def test_to_arrow_cero_ecuaciones_metadata_ausente(
    backend_factory: BackendFactory,
) -> None:
    """``to_arrow()`` sin ecuaciones NO trae ``equation_hash`` en la metadata."""
    backend = backend_factory(_empty_table())

    table = backend.to_arrow()
    metadata: dict[bytes, bytes] = table.schema.metadata or {}

    assert b"equation_hash" not in metadata


def test_to_arrow_multiples_ecuaciones_metadata_ausente(
    backend_factory: BackendFactory,
) -> None:
    """``to_arrow()`` con >1 ecuaciones NO trae ``equation_hash`` (no mentir un hash)."""
    backend = backend_factory(_empty_table())
    backend.persist_equation("eq-1", engine="openalex", raw_query="a", params_json="{}")
    backend.persist_equation("eq-2", engine="openalex", raw_query="b", params_json="{}")

    table = backend.to_arrow()
    metadata: dict[bytes, bytes] = table.schema.metadata or {}

    assert b"equation_hash" not in metadata


def test_to_arrow_no_altera_columnas_del_schema_canonico(
    backend_factory: BackendFactory,
) -> None:
    """La metadata es ADITIVA: las columnas/tipos de CORPUS_SCHEMA no cambian
    (constraint duro del consumidor programático, ADR 0050 §Constraints — agregar sí, renombrar/
    estrechar/re-tipar NO)."""
    backend = backend_factory(_empty_table())
    backend.persist_equation("eq-1", engine="openalex", raw_query="a", params_json="{}")

    table = backend.to_arrow()

    assert table.schema.names == CORPUS_SCHEMA.names
    for expected_field, actual_field in zip(CORPUS_SCHEMA, table.schema, strict=True):
        assert actual_field.type.equals(expected_field.type)
        assert actual_field.nullable == expected_field.nullable


# ---------------------------------------------------------------------------
# corpus_hash — R2: la tabla lateral no participa de la identidad
# ---------------------------------------------------------------------------


def test_corpus_hash_no_cambia_con_tabla_equations(
    backend_factory: BackendFactory,
) -> None:
    """``corpus_hash`` es idéntico con y sin ecuaciones persistidas (R2, ADR 0017).

    La identidad del corpus es del contenido bibliográfico; la tabla lateral
    ``equations`` (como ``external_ids``/``referenced_but_not_fetched``) es
    procedencia/metadata operativa, no contenido.
    """
    row: dict[str, Any] = {
        "id": "oa:aaaabbbb11112222",
        "source_id": None,
        "doi": None,
        "title": "Título de prueba",
        "year": 2020,
        "abstract": None,
        "source": None,
        "language": None,
        "publisher": None,
        "research_areas": None,
        "is_seed": True,
        "curation_status": "candidate",
        "provenance": None,
        "authors_raw": None,
        "authors_id": None,
        "authors_affiliations": None,
        "keywords_raw": None,
        "keywords_id": None,
        "institutions_raw": None,
        "institutions_id": None,
        "references_id": None,
        "references_doi": None,
        "cited_by_id": None,
    }
    table = pa.Table.from_pylist([row], schema=CORPUS_SCHEMA)

    backend_a = backend_factory(table)
    hash_sin_ecuacion = backend_a.corpus_hash()

    backend_b = backend_factory(table)
    backend_b.persist_equation(
        "eq-1", engine="openalex", raw_query="ecolog*", params_json="{}"
    )
    hash_con_ecuacion = backend_b.corpus_hash()

    assert hash_sin_ecuacion == hash_con_ecuacion
