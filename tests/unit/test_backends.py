"""Suite de contrato de ``TabularBackend`` — Hitos 1.5 y 3.

Tests parametrizados por backend que verifican los invariantes D1/D2/D3
(ADR 0013) como **contrato del backend** (ADR 0015).

Marcadores:
- ``unit``: parámetro ``memory`` (``InMemoryBackend``, sin red, sin I/O).
- ``integration``: parámetro ``duckdb`` (``DuckDBBackend``, I/O en memoria).

El gate ``uv run pytest -m unit`` ejecuta solo los tests con
``InMemoryBackend``; el gate ``uv run pytest -m integration`` ejecuta los
tests con ``DuckDBBackend``.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pyarrow as pa
import pytest

from bib2graph.backends import InMemoryBackend, TabularBackend
from bib2graph.backends.duckdb import DuckDBBackend
from bib2graph.schemas import CORPUS_SCHEMA

# ---------------------------------------------------------------------------
# Helpers — datos sintéticos
# ---------------------------------------------------------------------------

_LIST_STR = pa.list_(pa.string())


def _make_row(
    *,
    id: str,
    title: str = "Título de prueba",
    openalex_id: str | None = None,
    doi: str | None = None,
    year: int | None = 2020,
    is_seed: bool = True,
    curation_status: str = "candidate",
    provenance: str | None = None,
    keywords_raw: list[str] | None = None,
) -> dict[str, object]:
    """Fila mínima con todos los campos del schema canónico."""
    return {
        "id": id,
        "openalex_id": openalex_id,
        "doi": doi,
        "title": title,
        "year": year,
        "abstract": None,
        "source": None,
        "language": None,
        "publisher": None,
        "research_areas": None,
        "is_seed": is_seed,
        "curation_status": curation_status,
        "provenance": provenance,
        "authors_raw": None,
        "authors_id": None,
        "authors_affiliations": None,
        "keywords_raw": keywords_raw,
        "keywords_id": None,
        "institutions_raw": None,
        "institutions_id": None,
        "references_id": None,
        "references_doi": None,
        "cited_by_id": None,
    }


def _make_table(rows: list[dict[str, object]]) -> pa.Table:
    return pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)


# ---------------------------------------------------------------------------
# Fixture parametrizado por backend
#
# El marcador de cada test lo dicta el parámetro del fixture:
#   - memory → pytest.mark.unit   (sin I/O)
#   - duckdb → pytest.mark.integration  (I/O DuckDB)
# ---------------------------------------------------------------------------

BackendFactory = Callable[[pa.Table], TabularBackend]


@pytest.fixture(
    params=[
        pytest.param(
            lambda t: InMemoryBackend(t),
            id="memory",
            marks=pytest.mark.unit,
        ),
        pytest.param(
            lambda t: DuckDBBackend(t),
            id="duckdb",
            marks=pytest.mark.integration,
        ),
    ]
)
def backend_factory(request: pytest.FixtureRequest) -> BackendFactory:
    """Devuelve una factory ``pa.Table → TabularBackend`` según el parámetro."""
    factory: BackendFactory = request.param
    return factory


# ---------------------------------------------------------------------------
# Suite de contrato — D3: idempotencia de merge
# ---------------------------------------------------------------------------


def test_merge_idempotente(backend_factory: BackendFactory) -> None:
    """merge(self_table) es idempotente: mismos ids, mismo conteo (D3)."""
    rows = [
        _make_row(id="oa:aaaabbbb11112222", title="Paper A"),
        _make_row(id="oa:bbbbcccc22223333", title="Paper B"),
    ]
    table = _make_table(rows)
    backend = backend_factory(table)

    merged = backend.merge(backend.to_arrow())

    ids_orig = set(backend.to_arrow().column("id").to_pylist())
    ids_merged = set(merged.to_arrow().column("id").to_pylist())
    assert ids_orig == ids_merged
    assert len(merged) == len(backend)


def test_merge_idempotente_igualdad_contenido(backend_factory: BackendFactory) -> None:
    """merge(self_table) == self: igualdad de contenido completa (D3, D2)."""
    rows = [
        _make_row(id="oa:aaaabbbb11112222", title="Paper A", keywords_raw=None),
        _make_row(
            id="oa:bbbbcccc22223333",
            title="Paper B",
            keywords_raw=["alpha", "beta"],
        ),
    ]
    table = _make_table(rows)
    backend = backend_factory(table)

    merged = backend.merge(backend.to_arrow())

    assert backend.corpus_hash() == merged.corpus_hash()


# ---------------------------------------------------------------------------
# Suite de contrato — D3: dedup por id
# ---------------------------------------------------------------------------


def test_merge_dedup_por_id(backend_factory: BackendFactory) -> None:
    """merge deduplica: dos tablas con el mismo id producen una fila, no dos."""
    shared_id = "doi:cafecafecafecafe"
    row_a = _make_row(id=shared_id, title="Paper dup A", doi="10.1/dup")
    row_b = _make_row(id=shared_id, title="Paper dup B", doi="10.1/dup")

    table_a = _make_table([row_a])
    table_b = _make_table([row_b])

    backend = backend_factory(table_a)
    merged = backend.merge(table_b)

    assert len(merged) == 1


def test_merge_union_listas(backend_factory: BackendFactory) -> None:
    """merge hace unión de sets en columnas list[string] (D3)."""
    shared_id = "oa:deadbeefdeadbeef"
    row_a = _make_row(id=shared_id, keywords_raw=["alpha", "beta"])
    row_b = _make_row(id=shared_id, keywords_raw=["beta", "gamma"])

    backend = backend_factory(_make_table([row_a]))
    merged = backend.merge(_make_table([row_b]))

    result_row = merged.to_arrow().to_pylist()[0]
    assert sorted(result_row["keywords_raw"]) == ["alpha", "beta", "gamma"]


# ---------------------------------------------------------------------------
# Suite de contrato — D3: orden por primera aparición
# ---------------------------------------------------------------------------


def test_merge_orden_primera_aparicion(backend_factory: BackendFactory) -> None:
    """Las filas de self van primero; las nuevas de other van al final (D3)."""
    id_a = "oa:aaaabbbb11112222"
    id_b = "oa:bbbbcccc22223333"
    id_c = "oa:ccccdddd33334444"

    table_self = _make_table(
        [
            _make_row(id=id_a, title="Paper A"),
            _make_row(id=id_b, title="Paper B"),
        ]
    )
    table_other = _make_table(
        [
            _make_row(id=id_c, title="Paper C"),  # nueva
            _make_row(id=id_a, title="Paper A"),  # duplicada
        ]
    )

    backend = backend_factory(table_self)
    merged = backend.merge(table_other)

    ids = merged.to_arrow().column("id").to_pylist()
    # A y B del self van primero; C (nueva de other) al final
    assert ids[0] == id_a
    assert ids[1] == id_b
    assert ids[2] == id_c


# ---------------------------------------------------------------------------
# Suite de contrato — D2: corpus_hash estable y order-independent
# ---------------------------------------------------------------------------


def test_corpus_hash_estable(backend_factory: BackendFactory) -> None:
    """El mismo contenido produce el mismo corpus_hash en dos llamadas (D2)."""
    rows = [_make_row(id="oa:aaaabbbb11112222", title="Paper A")]
    backend = backend_factory(_make_table(rows))

    h1 = backend.corpus_hash()
    h2 = backend.corpus_hash()
    assert h1 == h2


def test_corpus_hash_order_independent(backend_factory: BackendFactory) -> None:
    """Mismo contenido en distinto orden de filas → mismo corpus_hash (D2)."""
    row_a = _make_row(id="oa:aaaabbbb11112222", title="Paper A")
    row_b = _make_row(id="oa:bbbbcccc22223333", title="Paper B")

    backend_ab = backend_factory(_make_table([row_a, row_b]))
    backend_ba = backend_factory(_make_table([row_b, row_a]))

    assert backend_ab.corpus_hash() == backend_ba.corpus_hash()


def test_corpus_hash_cambia_si_cambia_contenido(
    backend_factory: BackendFactory,
) -> None:
    """El corpus_hash cambia cuando cambia el contenido (no es constante)."""
    rows_a = [_make_row(id="oa:aaaabbbb11112222", title="Paper A")]
    rows_b = [_make_row(id="oa:bbbbcccc22223333", title="Paper B")]

    backend_a = backend_factory(_make_table(rows_a))
    backend_b = backend_factory(_make_table(rows_b))

    assert backend_a.corpus_hash() != backend_b.corpus_hash()


# ---------------------------------------------------------------------------
# Suite de contrato — D4: accept/reject agregan evento de provenance
# ---------------------------------------------------------------------------


def test_apply_curation_accepted_agrega_evento(backend_factory: BackendFactory) -> None:
    """apply_curation(action='accepted') agrega evento con action y decided_by (D4)."""
    paper_id = "oa:aaaabbbb11112222"
    backend = backend_factory(_make_table([_make_row(id=paper_id)]))

    curado = backend.apply_curation([paper_id], action="accepted", by="revisor")

    row = curado.to_arrow().to_pylist()[0]
    assert row["curation_status"] == "accepted"
    events: list[dict[str, Any]] = json.loads(row["provenance"])
    assert len(events) == 1
    assert events[0]["action"] == "accepted"
    assert events[0]["decided_by"] == "revisor"
    assert events[0]["decided_at"] is not None


def test_apply_curation_rejected_agrega_evento(backend_factory: BackendFactory) -> None:
    """apply_curation(action='rejected') agrega evento con action y decided_by (D4)."""
    paper_id = "oa:aaaabbbb11112222"
    backend = backend_factory(_make_table([_make_row(id=paper_id)]))

    curado = backend.apply_curation([paper_id], action="rejected", by="agente")

    row = curado.to_arrow().to_pylist()[0]
    assert row["curation_status"] == "rejected"
    events: list[dict[str, Any]] = json.loads(row["provenance"])
    assert events[0]["action"] == "rejected"


def test_apply_curation_no_muta_original(backend_factory: BackendFactory) -> None:
    """La instancia original no muta tras apply_curation (semántica de valor)."""
    paper_id = "oa:aaaabbbb11112222"
    backend = backend_factory(_make_table([_make_row(id=paper_id)]))
    original_status = backend.to_arrow().to_pylist()[0]["curation_status"]

    _ = backend.apply_curation([paper_id], action="accepted", by="revisor")

    assert backend.to_arrow().to_pylist()[0]["curation_status"] == original_status


def test_apply_curation_provenance_append_only(backend_factory: BackendFactory) -> None:
    """Dos curaciones consecutivas acumulan dos eventos (log append-only, D4)."""
    paper_id = "oa:aaaabbbb11112222"
    backend = backend_factory(_make_table([_make_row(id=paper_id)]))

    b1 = backend.apply_curation([paper_id], action="accepted", by="revisor_a")
    b2 = b1.apply_curation([paper_id], action="rejected", by="revisor_b")

    events: list[dict[str, Any]] = json.loads(
        b2.to_arrow().to_pylist()[0]["provenance"]
    )
    assert len(events) == 2
    assert events[0]["action"] == "accepted"
    assert events[1]["action"] == "rejected"


# ---------------------------------------------------------------------------
# Suite de contrato — add_paper
# ---------------------------------------------------------------------------


def test_add_paper_aumenta_conteo(backend_factory: BackendFactory) -> None:
    """add_paper agrega una fila y el backend nuevo tiene len + 1."""
    backend = backend_factory(_make_table([_make_row(id="oa:aaaabbbb11112222")]))

    nuevo = backend.add_paper(_make_row(id="oa:bbbbcccc22223333", title="Nuevo"))

    assert len(nuevo) == len(backend) + 1


def test_add_paper_no_muta_original(backend_factory: BackendFactory) -> None:
    """add_paper no muta la instancia original (semántica de valor)."""
    backend = backend_factory(_make_table([_make_row(id="oa:aaaabbbb11112222")]))
    original_len = len(backend)

    _ = backend.add_paper(_make_row(id="oa:bbbbcccc22223333", title="Nuevo"))

    assert len(backend) == original_len


# ---------------------------------------------------------------------------
# Suite de contrato — filter_view
# ---------------------------------------------------------------------------


def test_filter_view_seeds(backend_factory: BackendFactory) -> None:
    """filter_view('seeds') devuelve solo las filas con is_seed=True."""
    rows = [
        _make_row(id="oa:aaaabbbb11112222", is_seed=True),
        _make_row(id="oa:bbbbcccc22223333", is_seed=False),
    ]
    backend = backend_factory(_make_table(rows))

    seeds = backend.filter_view("seeds")

    assert len(seeds) == 1
    assert seeds.to_pylist()[0]["id"] == "oa:aaaabbbb11112222"


def test_filter_view_candidates(backend_factory: BackendFactory) -> None:
    """filter_view('candidates') devuelve solo los papers con curation_status='candidate'."""
    rows = [
        _make_row(id="oa:aaaabbbb11112222", curation_status="candidate"),
        _make_row(id="oa:bbbbcccc22223333", curation_status="accepted"),
    ]
    backend = backend_factory(_make_table(rows))

    candidates = backend.filter_view("candidates")

    assert len(candidates) == 1
    assert candidates.to_pylist()[0]["id"] == "oa:aaaabbbb11112222"


def test_filter_view_accepted(backend_factory: BackendFactory) -> None:
    """filter_view('accepted') devuelve solo los papers con curation_status='accepted'."""
    rows = [
        _make_row(id="oa:aaaabbbb11112222", curation_status="candidate"),
        _make_row(id="oa:bbbbcccc22223333", curation_status="accepted"),
    ]
    backend = backend_factory(_make_table(rows))

    accepted = backend.filter_view("accepted")

    assert len(accepted) == 1
    assert accepted.to_pylist()[0]["id"] == "oa:bbbbcccc22223333"


# ---------------------------------------------------------------------------
# Regresión Task C — merge parametrizado (sin interpolación de ids crudos)
# ---------------------------------------------------------------------------


def test_merge_solapado_preserva_hash_y_orden(backend_factory: BackendFactory) -> None:
    """merge de dos corpus solapados produce el mismo corpus_hash/orden que InMemoryBackend.

    Regresión: verifica que el rewrite de merge (sin interpolación de ids crudos
    en SQL, ADR 0015/C) mantiene el comportamiento D3 exacto.  El InMemoryBackend
    es la referencia de verdad; DuckDBBackend debe producir el mismo hash.
    """
    id_a = "oa:aaaabbbb11112222"
    id_b = "oa:bbbbcccc22223333"
    id_c = "oa:ccccdddd33334444"

    table_self = _make_table(
        [
            _make_row(id=id_a, title="Paper A"),
            _make_row(id=id_b, title="Paper B"),
        ]
    )
    table_other = _make_table(
        [
            _make_row(id=id_c, title="Paper C"),  # nueva
            _make_row(id=id_a, title="Paper A bis"),  # solapada (merge D3)
        ]
    )

    backend = backend_factory(table_self)
    merged = backend.merge(table_other)

    # Orden: A, B (del self), C (nueva de other)
    ids = merged.to_arrow().column("id").to_pylist()
    assert ids == [id_a, id_b, id_c]
    # Contenido completo: 3 papers
    assert len(merged) == 3
    # corpus_hash debe coincidir con el de InMemoryBackend (referencia D2/D3)
    from bib2graph.backends import InMemoryBackend

    ref_backend = InMemoryBackend(table_self).merge(table_other)
    assert merged.corpus_hash() == ref_backend.corpus_hash()
