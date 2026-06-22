"""Tests TDD — ADR 0036 opción C: tabla lateral ``external_ids``.

Verifica que:
- La tabla ``external_ids`` existe en DuckDBBackend y en InMemoryBackend.
- Paridad de contrato observable entre ambos backends.
- Idempotencia: escribir ``(paper_id, engine, id)`` dos veces → una sola entrada.
- Reemplazo: escribir ``(paper_id, engine, id2)`` sobre un ``(paper_id, engine)``
  existente reemplaza el valor anterior (un ID por motor por paper).
- Multi-motor: ``(p1, 'openalex', 'W1')`` y ``(p1, 'semanticscholar', 'S1')``
  coexisten (N motores por paper).
- ``external_ids`` NO afecta ``corpus_hash`` (agregar entradas no cambia el hash).
- La tabla sobrevive al ``_clone()`` del DuckDBBackend.
- Migración liviana: una DB sin la tabla no falla al abrirla.

Marcadores:
- ``unit`` (InMemoryBackend, DuckDB en tmp_path — sin red real).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest

from bib2graph.backends.duckdb import DuckDBBackend
from bib2graph.backends.memory import InMemoryBackend
from bib2graph.schemas import CORPUS_SCHEMA

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _empty_table() -> pa.Table:
    """Tabla Arrow canónica vacía (para backends sin papers)."""
    return pa.table(
        {f.name: pa.array([], type=f.type) for f in CORPUS_SCHEMA},
        schema=CORPUS_SCHEMA,
    )


def _memory_backend() -> InMemoryBackend:
    return InMemoryBackend(_empty_table())


# ---------------------------------------------------------------------------
# InMemoryBackend — tabla external_ids
# ---------------------------------------------------------------------------


class TestInMemoryBackendExternalIds:
    """InMemoryBackend.add_external_id / external_ids_for / all_external_ids."""

    def test_initial_empty(self) -> None:
        """Backend nuevo no tiene IDs externos registrados."""
        backend = _memory_backend()
        assert backend.external_ids_for("P1") == {}
        assert backend.all_external_ids() == []

    def test_add_and_retrieve(self) -> None:
        """add_external_id registra el id y external_ids_for lo devuelve."""
        backend = _memory_backend()
        backend.add_external_id("P1", "openalex", "W123")

        result = backend.external_ids_for("P1")
        assert result == {"openalex": "W123"}

    def test_idempotente_mismo_valor(self) -> None:
        """Re-escribir el mismo (paper_id, engine, id) no crea duplicado."""
        backend = _memory_backend()
        backend.add_external_id("P1", "openalex", "W123")
        backend.add_external_id("P1", "openalex", "W123")

        result = backend.external_ids_for("P1")
        assert result == {"openalex": "W123"}
        assert len(backend.all_external_ids()) == 1

    def test_reemplaza_valor_distinto(self) -> None:
        """Re-escribir (paper_id, engine) con id distinto reemplaza el anterior."""
        backend = _memory_backend()
        backend.add_external_id("P1", "openalex", "W1")
        backend.add_external_id("P1", "openalex", "W2")

        result = backend.external_ids_for("P1")
        assert result == {"openalex": "W2"}
        # Solo una entrada por (paper_id, engine)
        assert len(backend.all_external_ids()) == 1

    def test_multi_motor(self) -> None:
        """Motores distintos para el mismo paper coexisten."""
        backend = _memory_backend()
        backend.add_external_id("P1", "openalex", "W1")
        backend.add_external_id("P1", "semanticscholar", "S1")

        result = backend.external_ids_for("P1")
        assert result == {"openalex": "W1", "semanticscholar": "S1"}
        assert len(backend.all_external_ids()) == 2

    def test_multi_paper(self) -> None:
        """Papers distintos no interfieren entre sí."""
        backend = _memory_backend()
        backend.add_external_id("P1", "openalex", "W1")
        backend.add_external_id("P2", "openalex", "W2")

        assert backend.external_ids_for("P1") == {"openalex": "W1"}
        assert backend.external_ids_for("P2") == {"openalex": "W2"}
        assert backend.external_ids_for("P3") == {}

    def test_corpus_hash_no_cambia(self) -> None:
        """corpus_hash no cambia al agregar external_ids."""
        backend = _memory_backend()
        hash_antes = backend.corpus_hash()

        backend.add_external_id("P1", "openalex", "W1")
        backend.add_external_id("P1", "semanticscholar", "S1")

        hash_despues = backend.corpus_hash()
        assert hash_antes == hash_despues, (
            "corpus_hash no debe cambiar al agregar external_ids"
        )

    def test_external_ids_sobreviven_a_add_paper(self) -> None:
        """external_ids se propagan a la nueva instancia tras add_paper."""
        backend = _memory_backend()
        backend.add_external_id("P1", "openalex", "W1")

        row: dict[str, Any] = {
            "id": "P2",
            "openalex_id": None,
            "doi": None,
            "title": "Paper 2",
            "year": 2021,
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
        backend2 = backend.add_paper(row)

        # El external_id de P1 sobrevive en la nueva instancia
        assert backend2.external_ids_for("P1") == {"openalex": "W1"}


# ---------------------------------------------------------------------------
# DuckDBBackend — tabla external_ids
# ---------------------------------------------------------------------------


class TestDuckDBBackendExternalIds:
    """DuckDBBackend: tabla external_ids (DDL, métodos, migración)."""

    def test_tabla_creada_en_setup(self, tmp_path: Path) -> None:
        """La tabla external_ids se crea en _setup."""
        db_path = tmp_path / "test.duckdb"
        backend = DuckDBBackend(path=db_path)
        # Debe poder hacer la query sin error
        result = backend.external_ids_for("P1")
        assert result == {}
        backend.close()

    def test_add_and_retrieve(self, tmp_path: Path) -> None:
        """add_external_id registra el id y external_ids_for lo devuelve."""
        db_path = tmp_path / "test.duckdb"
        backend = DuckDBBackend(path=db_path)

        backend.add_external_id("P1", "openalex", "W123")
        result = backend.external_ids_for("P1")
        assert result == {"openalex": "W123"}
        backend.close()

    def test_idempotente_mismo_valor(self, tmp_path: Path) -> None:
        """Re-escribir el mismo (paper_id, engine, id) no crea duplicado."""
        db_path = tmp_path / "test.duckdb"
        backend = DuckDBBackend(path=db_path)

        backend.add_external_id("P1", "openalex", "W123")
        backend.add_external_id("P1", "openalex", "W123")

        result = backend.external_ids_for("P1")
        assert result == {"openalex": "W123"}
        assert len(backend.all_external_ids()) == 1
        backend.close()

    def test_reemplaza_valor_distinto(self, tmp_path: Path) -> None:
        """Re-escribir (paper_id, engine) con id distinto reemplaza el anterior."""
        db_path = tmp_path / "test.duckdb"
        backend = DuckDBBackend(path=db_path)

        backend.add_external_id("P1", "openalex", "W1")
        backend.add_external_id("P1", "openalex", "W2")

        result = backend.external_ids_for("P1")
        assert result == {"openalex": "W2"}
        assert len(backend.all_external_ids()) == 1
        backend.close()

    def test_multi_motor(self, tmp_path: Path) -> None:
        """Motores distintos para el mismo paper coexisten."""
        db_path = tmp_path / "test.duckdb"
        backend = DuckDBBackend(path=db_path)

        backend.add_external_id("P1", "openalex", "W1")
        backend.add_external_id("P1", "semanticscholar", "S1")

        result = backend.external_ids_for("P1")
        assert result == {"openalex": "W1", "semanticscholar": "S1"}
        assert len(backend.all_external_ids()) == 2
        backend.close()

    def test_multi_paper(self, tmp_path: Path) -> None:
        """Papers distintos no interfieren entre sí."""
        db_path = tmp_path / "test.duckdb"
        backend = DuckDBBackend(path=db_path)

        backend.add_external_id("P1", "openalex", "W1")
        backend.add_external_id("P2", "openalex", "W2")

        assert backend.external_ids_for("P1") == {"openalex": "W1"}
        assert backend.external_ids_for("P2") == {"openalex": "W2"}
        assert backend.external_ids_for("P3") == {}
        backend.close()

    def test_corpus_hash_no_cambia(self, tmp_path: Path) -> None:
        """corpus_hash no cambia al agregar external_ids al DuckDBBackend."""
        db_path = tmp_path / "test.duckdb"
        backend = DuckDBBackend(path=db_path)
        hash_antes = backend.corpus_hash()

        backend.add_external_id("P1", "openalex", "W1")
        hash_despues = backend.corpus_hash()

        assert hash_antes == hash_despues, (
            "corpus_hash no debe cambiar al agregar external_ids"
        )
        backend.close()

    def test_snapshot_round_trip_memory(self, tmp_path: Path) -> None:
        """La tabla external_ids sobrevive al _clone en modo :memory:."""
        backend = DuckDBBackend()  # :memory:
        backend.add_external_id("P1", "openalex", "W1")
        backend.add_external_id("P1", "semanticscholar", "S1")

        cloned = backend._clone()
        assert cloned.external_ids_for("P1") == {
            "openalex": "W1",
            "semanticscholar": "S1",
        }

    def test_snapshot_round_trip_file(self, tmp_path: Path) -> None:
        """La tabla external_ids persiste en archivo y una nueva instancia la lee."""
        db_path = tmp_path / "test.duckdb"
        backend = DuckDBBackend(path=db_path)
        backend.add_external_id("P1", "openalex", "W1")
        backend.close()

        backend2 = DuckDBBackend(path=db_path)
        assert backend2.external_ids_for("P1") == {"openalex": "W1"}
        backend2.close()

    def test_migracion_liviana_db_sin_tabla(self, tmp_path: Path) -> None:
        """Una DB sin external_ids no falla al abrirla (CREATE TABLE IF NOT EXISTS).

        Simula una base pre-ADR 0036: creamos las tablas viejas manualmente
        sin external_ids, luego abrimos DuckDBBackend que debe crearla.
        """
        import duckdb

        db_path = tmp_path / "legacy.duckdb"
        con = duckdb.connect(str(db_path))
        con.execute(
            "CREATE TABLE IF NOT EXISTS corpus (id VARCHAR PRIMARY KEY, "
            "openalex_id VARCHAR, doi VARCHAR, title VARCHAR NOT NULL, "
            "year INTEGER, abstract VARCHAR, source VARCHAR, language VARCHAR, "
            "publisher VARCHAR, research_areas VARCHAR[], is_seed BOOLEAN NOT NULL, "
            "curation_status VARCHAR NOT NULL, provenance VARCHAR, "
            "authors_raw VARCHAR[], authors_id VARCHAR[], authors_affiliations VARCHAR[], "
            "keywords_raw VARCHAR[], keywords_id VARCHAR[], institutions_raw VARCHAR[], "
            "institutions_id VARCHAR[], references_id VARCHAR[], references_doi VARCHAR[], "
            "cited_by_id VARCHAR[], _seq BIGINT)"
        )
        con.execute(
            "CREATE TABLE IF NOT EXISTS loop_state_log "
            "(state VARCHAR NOT NULL, round INTEGER DEFAULT 0, "
            "recorded_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        con.execute(
            "CREATE TABLE IF NOT EXISTS referenced_but_not_fetched "
            "(ref_id VARCHAR NOT NULL, cycle_round INTEGER NOT NULL DEFAULT 0, "
            "observed_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        con.close()

        # Abrir con DuckDBBackend — no debe fallar
        backend = DuckDBBackend(path=db_path)
        assert backend.external_ids_for("P1") == {}
        backend.close()


# ---------------------------------------------------------------------------
# Paridad de contrato InMemoryBackend ↔ DuckDBBackend
# ---------------------------------------------------------------------------


class TestExternalIdsParidad:
    """Verifica que InMemoryBackend y DuckDBBackend exponen el mismo contrato observable."""

    def test_add_and_retrieve_paridad(self, tmp_path: Path) -> None:
        """add_external_id + external_ids_for dan el mismo resultado en ambos backends."""
        mem = _memory_backend()
        db = DuckDBBackend(path=tmp_path / "par.duckdb")

        for backend in (mem, db):
            backend.add_external_id("P1", "openalex", "W1")
            backend.add_external_id("P1", "semanticscholar", "S1")
            backend.add_external_id("P2", "doi", "10.1234/test")

        assert mem.external_ids_for("P1") == db.external_ids_for("P1")
        assert mem.external_ids_for("P2") == db.external_ids_for("P2")
        assert mem.external_ids_for("P99") == db.external_ids_for("P99")
        db.close()

    def test_idempotencia_paridad(self, tmp_path: Path) -> None:
        """Idempotencia (mismo valor) da el mismo resultado en ambos backends."""
        mem = _memory_backend()
        db = DuckDBBackend(path=tmp_path / "par.duckdb")

        for backend in (mem, db):
            backend.add_external_id("P1", "openalex", "W1")
            backend.add_external_id("P1", "openalex", "W1")  # duplicado

        assert mem.external_ids_for("P1") == db.external_ids_for("P1")
        assert len(mem.all_external_ids()) == len(db.all_external_ids()) == 1
        db.close()

    def test_reemplazo_paridad(self, tmp_path: Path) -> None:
        """Reemplazo de valor da el mismo resultado en ambos backends."""
        mem = _memory_backend()
        db = DuckDBBackend(path=tmp_path / "par.duckdb")

        for backend in (mem, db):
            backend.add_external_id("P1", "openalex", "W1")
            backend.add_external_id("P1", "openalex", "W2")  # reemplaza

        assert mem.external_ids_for("P1") == db.external_ids_for("P1")
        assert len(mem.all_external_ids()) == len(db.all_external_ids()) == 1
        db.close()

    def test_corpus_hash_no_cambia_paridad(self, tmp_path: Path) -> None:
        """corpus_hash no cambia tras add_external_id en ninguno de los dos backends."""
        mem = _memory_backend()
        db = DuckDBBackend(path=tmp_path / "par.duckdb")

        hash_mem_antes = mem.corpus_hash()
        hash_db_antes = db.corpus_hash()

        mem.add_external_id("P1", "openalex", "W1")
        db.add_external_id("P1", "openalex", "W1")

        assert mem.corpus_hash() == hash_mem_antes
        assert db.corpus_hash() == hash_db_antes
        db.close()
