"""Tests de ``DuckDBStore`` y ``LoopState`` — Hito 3.

Todos los tests tocan DuckDB sobre disco → marcados ``integration``.
El gate ``uv run pytest -m unit`` no los ejecuta.

Escenarios cubiertos (los justos, ROADMAP Hito 3):
- persist → load en instancia nueva acumula (biblioteca viva entre corridas).
- Idempotencia de persist (no duplica filas; mismo ``corpus_hash``).
- Procedencia/curación sobreviven al reinicio.
- ``LoopState``: transición SEEDED→FORAGED sobrevive al reload.
- Consulta SQL representativa vía ``backend.query(...)``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pytest

from bib2graph.backends.duckdb import LoopState
from bib2graph.corpus import Corpus
from bib2graph.schemas import CORPUS_SCHEMA
from bib2graph.stores.duckdb import DuckDBStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_row(
    *,
    id: str,
    title: str = "Título de prueba",
    is_seed: bool = True,
    curation_status: str = "candidate",
    provenance: str | None = None,
) -> dict[str, object]:
    """Fila mínima con todos los campos del schema canónico."""
    return {
        "id": id,
        "openalex_id": None,
        "doi": None,
        "title": title,
        "year": 2020,
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
        "keywords_raw": None,
        "keywords_id": None,
        "institutions_raw": None,
        "institutions_id": None,
        "references_id": None,
        "references_doi": None,
        "cited_by_id": None,
    }


def _make_corpus(rows: list[dict[str, object]]) -> Corpus:
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    return Corpus.from_arrow(table)


# ---------------------------------------------------------------------------
# Tests de DuckDBStore
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_persist_load_acumula_entre_corridas(tmp_path: Path) -> None:
    """persist luego load en otra instancia devuelve el corpus acumulado."""
    db_path = tmp_path / "lib.duckdb"
    corpus1 = _make_corpus([_make_row(id="oa:aaaabbbb11112222", title="Paper A")])

    # Primera "corrida": persist
    store1 = DuckDBStore(db_path)
    store1.persist(corpus1)

    # Segunda "corrida": otra instancia, load
    store2 = DuckDBStore(db_path)
    loaded = store2.load()

    ids = loaded.to_arrow().column("id").to_pylist()
    assert "oa:aaaabbbb11112222" in ids
    assert len(loaded) == 1


@pytest.mark.integration
def test_persist_acumula_entre_corridas(tmp_path: Path) -> None:
    """Dos persist sucesivos con corpus distintos acumulan ambos (biblioteca viva)."""
    db_path = tmp_path / "lib.duckdb"
    corpus1 = _make_corpus([_make_row(id="oa:aaaabbbb11112222", title="Paper A")])
    corpus2 = _make_corpus([_make_row(id="oa:bbbbcccc22223333", title="Paper B")])

    DuckDBStore(db_path).persist(corpus1)
    DuckDBStore(db_path).persist(corpus2)

    loaded = DuckDBStore(db_path).load()
    ids = set(loaded.to_arrow().column("id").to_pylist())
    assert ids == {"oa:aaaabbbb11112222", "oa:bbbbcccc22223333"}


@pytest.mark.integration
def test_persist_idempotente(tmp_path: Path) -> None:
    """persist dos veces el mismo corpus no duplica filas; mismo corpus_hash."""
    db_path = tmp_path / "lib.duckdb"
    corpus = _make_corpus([_make_row(id="oa:aaaabbbb11112222", title="Paper A")])

    store = DuckDBStore(db_path)
    store.persist(corpus)
    loaded_first = store.load()
    hash_after_first = loaded_first._backend.corpus_hash()

    store.persist(corpus)
    loaded_second = store.load()
    hash_after_second = loaded_second._backend.corpus_hash()

    assert len(loaded_second) == 1
    assert hash_after_first == hash_after_second


@pytest.mark.integration
def test_provenance_curation_sobreviven_reinicio(tmp_path: Path) -> None:
    """accept en el corpus → persist → load nueva instancia → curación intacta."""
    db_path = tmp_path / "lib.duckdb"
    paper_id = "oa:aaaabbbb11112222"
    corpus = _make_corpus([_make_row(id=paper_id, title="Paper A")])

    # Primera sesión: aceptar y persistir
    corpus_curado = corpus.accept([paper_id], by="revisor_test")
    DuckDBStore(db_path).persist(corpus_curado)

    # Segunda sesión: load en instancia nueva
    loaded = DuckDBStore(db_path).load()
    rows = [r for r in loaded.to_arrow().to_pylist() if r["id"] == paper_id]
    row = rows[0]

    assert row["curation_status"] == "accepted"
    events = json.loads(row["provenance"])
    assert any(
        e["action"] == "accepted" and e["decided_by"] == "revisor_test" for e in events
    )


@pytest.mark.integration
def test_loop_state_sobrevive_al_reload(tmp_path: Path) -> None:
    """LoopState SEEDED→FORAGED sobrevive al reinicio (nueva instancia)."""
    db_path = tmp_path / "lib.duckdb"

    # Primera sesión: registrar transiciones
    store1 = DuckDBStore(db_path)
    store1.backend.set_loop_state(LoopState.SEEDED)
    store1.backend.set_loop_state(LoopState.FORAGED)

    # Segunda sesión: estado actual es FORAGED
    store2 = DuckDBStore(db_path)
    assert store2.backend.loop_state() == LoopState.FORAGED


@pytest.mark.integration
def test_loop_state_inicial_es_none(tmp_path: Path) -> None:
    """Un store recién creado sin transiciones devuelve loop_state() == None."""
    db_path = tmp_path / "lib.duckdb"
    store = DuckDBStore(db_path)
    assert store.backend.loop_state() is None


@pytest.mark.integration
def test_loop_state_transicion_permisiva(tmp_path: Path) -> None:
    """Las transiciones son permisivas: se puede saltar de SEEDED a BUILT."""
    db_path = tmp_path / "lib.duckdb"
    store = DuckDBStore(db_path)
    store.backend.set_loop_state(LoopState.SEEDED)
    store.backend.set_loop_state(LoopState.BUILT)
    assert store.backend.loop_state() == LoopState.BUILT


@pytest.mark.integration
def test_query_sql_representativa(tmp_path: Path) -> None:
    """backend.query(sql) devuelve resultados de una consulta SELECT."""
    db_path = tmp_path / "lib.duckdb"
    corpus = _make_corpus(
        [
            _make_row(
                id="oa:aaaabbbb11112222", title="Paper A", curation_status="accepted"
            ),
            _make_row(
                id="oa:bbbbcccc22223333", title="Paper B", curation_status="candidate"
            ),
        ]
    )

    store = DuckDBStore(db_path)
    store.persist(corpus)

    result = store.backend.query(
        "SELECT id, curation_status FROM corpus WHERE curation_status = 'accepted'"
    )
    assert len(result) == 1
    assert result.to_pylist()[0]["id"] == "oa:aaaabbbb11112222"
