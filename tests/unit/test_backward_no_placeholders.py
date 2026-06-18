"""Tests TDD — #54 opción B: backward chaining sin placeholders en corpus.

Verifica que:
- ``chain(backward)`` produce CERO filas en ``RankedCandidates.corpus``
  (sin filas-fantasma ``[candidate:...]``).
- Los IDs observados están en ``RankedCandidates.observed_refs``.
- El ranking backward sobrevive en ``RankedCandidates.ranking``.
- Tras el comando ``chain`` backward, la tabla ``referenced_but_not_fetched``
  tiene los IDs con ``cycle_round``; el corpus NO creció con fantasmas.
- ``b2g status`` reporta el campo ``referenced_not_fetched``.
- La tabla sobrevive al snapshot (round-trip en DuckDBBackend).
- Migración liviana: una DB sin la tabla no falla al abrirla.
- No-regresión forward: el forward sigue materializando works reales al corpus.
- ``corpus_hash`` tras backward chaining NO incluye los observados (estable
  respecto a solo-seeds).

Marcador: ``unit`` (DuckDB en tmp_path / InMemoryBackend, sin red real).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest

from bib2graph.backends.duckdb import DuckDBBackend
from bib2graph.backends.memory import InMemoryBackend
from bib2graph.corpus import Corpus
from bib2graph.foraging.forager import Forager
from bib2graph.schemas import CORPUS_SCHEMA

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_row(
    id: str,
    *,
    openalex_id: str | None = None,
    is_seed: bool = True,
    references_id: list[str] | None = None,
    curation_status: str = "candidate",
) -> dict[str, Any]:
    return {
        "id": id,
        "openalex_id": openalex_id,
        "doi": None,
        "title": f"Paper {id}",
        "year": 2020,
        "abstract": None,
        "source": None,
        "language": None,
        "publisher": None,
        "research_areas": None,
        "is_seed": is_seed,
        "curation_status": curation_status,
        "provenance": None,
        "authors_raw": None,
        "authors_id": None,
        "authors_affiliations": None,
        "keywords_raw": None,
        "keywords_id": None,
        "institutions_raw": None,
        "institutions_id": None,
        "references_id": references_id,
        "references_doi": None,
        "cited_by_id": None,
    }


def _make_corpus(*rows: dict[str, Any]) -> Corpus:
    table = pa.Table.from_pylist(list(rows), schema=CORPUS_SCHEMA)
    return Corpus.from_arrow(table)


def _make_noop_source() -> Any:
    """Source mínimo que no tiene fetch_citing_batch (solo backward posible)."""

    class NoopSource:
        pass

    return NoopSource()


# ---------------------------------------------------------------------------
# Forager puro (sin persistencia)
# ---------------------------------------------------------------------------


class TestBackwardNoCandidateRows:
    """chain(backward) no produce filas-fantasma en corpus."""

    def test_corpus_backward_vacio(self) -> None:
        """Backward chaining: corpus del resultado vacío (sin filas-fantasma)."""
        corpus = _make_corpus(_base_row("P1", references_id=["REF_A", "REF_B"]))

        forager = Forager(_make_noop_source(), depth=1)
        ranked = forager.chain(corpus, direction="backward")

        rows = ranked.corpus.to_arrow().to_pylist()
        assert len(rows) == 0, (
            f"El corpus backward debe estar vacío (#54), tiene {len(rows)} filas"
        )

    def test_sin_titulo_placeholder_en_corpus(self) -> None:
        """Nunca hay títulos '[candidate:...]' en el corpus tras backward chaining."""
        corpus = _make_corpus(
            _base_row("P1", references_id=["REF_A"]),
            _base_row("P2", references_id=["REF_A", "REF_B"]),
        )

        forager = Forager(_make_noop_source(), depth=1)
        ranked = forager.chain(corpus, direction="backward")

        for row in ranked.corpus.to_arrow().to_pylist():
            title = row.get("title") or ""
            assert "[candidate:" not in title, (
                f"Título placeholder encontrado en corpus: {title!r}"
            )

    def test_observed_refs_contiene_ids_backward(self) -> None:
        """Los IDs backward van a observed_refs, no al corpus."""
        corpus = _make_corpus(
            _base_row("P1", references_id=["REF_A", "REF_B"]),
            _base_row("P2", references_id=["REF_A"]),
        )

        forager = Forager(_make_noop_source(), depth=1)
        ranked = forager.chain(corpus, direction="backward")

        assert set(ranked.observed_refs) == {"REF_A", "REF_B"}

    def test_ranking_backward_presente(self) -> None:
        """El ranking backward SOBREVIVE aunque el corpus esté vacío."""
        corpus = _make_corpus(
            _base_row("P1", references_id=["REF_A", "REF_B"]),
            _base_row("P2", references_id=["REF_A"]),
        )

        forager = Forager(_make_noop_source(), depth=1)
        ranked = forager.chain(corpus, direction="backward")

        # Ranking: REF_A (score=2) > REF_B (score=1)
        assert len(ranked.ranking) == 2
        assert ranked.ranking[0] == ("REF_A", 2.0)
        assert ranked.ranking[1] == ("REF_B", 1.0)

    def test_observed_refs_respeta_max_candidates(self) -> None:
        """max_candidates acota también los observed_refs (solo los del ranking)."""
        corpus = _make_corpus(
            _base_row("P1", references_id=["REF_A", "REF_B", "REF_C"]),
        )

        forager = Forager(_make_noop_source(), depth=1, max_candidates=2)
        ranked = forager.chain(corpus, direction="backward")

        # Con max_candidates=2, solo los 2 primeros del ranking están en observed_refs
        assert len(ranked.observed_refs) == 2
        assert len(ranked.ranking) == 2

    def test_corpus_hash_estable_sin_observed(self) -> None:
        """corpus_hash solo de seeds NO cambia tras backward chaining.

        Los observed_refs no están en el corpus → el hash no los incluye.
        """
        seeds = _make_corpus(_base_row("P1", references_id=["REF_A"]))

        hash_antes = seeds.to_arrow().schema  # verificar que el schema no cambia
        hash_semillas = seeds._backend.corpus_hash()

        forager = Forager(_make_noop_source(), depth=1)
        ranked = forager.chain(seeds, direction="backward")

        # Simular merge con el corpus del resultado (vacío para backward)
        merged = seeds.merge(ranked.corpus)
        hash_despues = merged._backend.corpus_hash()

        # El hash no cambió porque ranked.corpus está vacío
        assert hash_semillas == hash_despues, (
            "corpus_hash cambió tras backward chaining: los observed_refs "
            "no deben contaminar el hash del corpus"
        )
        _ = hash_antes  # usado solo para tipo


# ---------------------------------------------------------------------------
# InMemoryBackend — tabla auxiliar
# ---------------------------------------------------------------------------


class TestInMemoryBackendReferencedRefs:
    """InMemoryBackend.add_referenced_refs / referenced_refs_count / referenced_refs."""

    def test_add_retorna_nuevos(self) -> None:
        """add_referenced_refs devuelve el número de IDs realmente nuevos."""
        table = pa.table(
            {f.name: pa.array([], type=f.type) for f in CORPUS_SCHEMA},
            schema=CORPUS_SCHEMA,
        )
        backend = InMemoryBackend(table)

        n = backend.add_referenced_refs(["W1", "W2", "W3"], cycle_round=1)
        assert n == 3

    def test_add_idempotente(self) -> None:
        """Re-agregar los mismos IDs no los duplica."""
        table = pa.table(
            {f.name: pa.array([], type=f.type) for f in CORPUS_SCHEMA},
            schema=CORPUS_SCHEMA,
        )
        backend = InMemoryBackend(table)

        backend.add_referenced_refs(["W1", "W2"], cycle_round=1)
        n2 = backend.add_referenced_refs(["W1", "W3"], cycle_round=1)

        # Solo W3 es nuevo
        assert n2 == 1
        assert backend.referenced_refs_count() == 3
        assert set(backend.referenced_refs()) == {"W1", "W2", "W3"}

    def test_count_inicial_cero(self) -> None:
        """Backend nuevo tiene 0 referenced_refs."""
        table = pa.table(
            {f.name: pa.array([], type=f.type) for f in CORPUS_SCHEMA},
            schema=CORPUS_SCHEMA,
        )
        backend = InMemoryBackend(table)
        assert backend.referenced_refs_count() == 0

    def test_referenced_refs_lista(self) -> None:
        """referenced_refs devuelve lista en orden de inserción."""
        table = pa.table(
            {f.name: pa.array([], type=f.type) for f in CORPUS_SCHEMA},
            schema=CORPUS_SCHEMA,
        )
        backend = InMemoryBackend(table)
        backend.add_referenced_refs(["W1", "W2"], cycle_round=1)
        backend.add_referenced_refs(["W3"], cycle_round=2)

        refs = backend.referenced_refs()
        assert refs == ["W1", "W2", "W3"]

    def test_corpus_hash_no_incluye_referenced_refs(self) -> None:
        """corpus_hash no cambia cuando se agregan referenced_refs."""
        table = pa.table(
            {f.name: pa.array([], type=f.type) for f in CORPUS_SCHEMA},
            schema=CORPUS_SCHEMA,
        )
        backend = InMemoryBackend(table)
        hash_antes = backend.corpus_hash()

        backend.add_referenced_refs(["W1", "W2"], cycle_round=1)
        hash_despues = backend.corpus_hash()

        assert hash_antes == hash_despues, (
            "corpus_hash no debe cambiar al agregar referenced_refs"
        )


# ---------------------------------------------------------------------------
# DuckDBBackend — tabla auxiliar
# ---------------------------------------------------------------------------


class TestDuckDBBackendReferencedRefs:
    """DuckDBBackend: tabla referenced_but_not_fetched (DDL, métodos, migración)."""

    def test_tabla_creada_en_setup(self, tmp_path: Path) -> None:
        """La tabla referenced_but_not_fetched se crea en _setup."""
        db_path = tmp_path / "test.duckdb"
        backend = DuckDBBackend(path=db_path)
        # Debe poder hacer la query sin error
        count = backend.referenced_refs_count()
        assert count == 0
        backend.close()

    def test_add_referenced_refs(self, tmp_path: Path) -> None:
        """add_referenced_refs inserta IDs con cycle_round."""
        db_path = tmp_path / "test.duckdb"
        backend = DuckDBBackend(path=db_path)

        n = backend.add_referenced_refs(["W1", "W2"], cycle_round=1)
        assert n == 2
        assert backend.referenced_refs_count() == 2
        refs = backend.referenced_refs()
        assert set(refs) == {"W1", "W2"}
        backend.close()

    def test_add_idempotente(self, tmp_path: Path) -> None:
        """Re-agregar los mismos IDs no los duplica."""
        db_path = tmp_path / "test.duckdb"
        backend = DuckDBBackend(path=db_path)

        backend.add_referenced_refs(["W1", "W2"], cycle_round=1)
        n2 = backend.add_referenced_refs(["W1", "W3"], cycle_round=2)

        assert n2 == 1  # solo W3 es nuevo
        assert backend.referenced_refs_count() == 3
        backend.close()

    def test_snapshot_round_trip(self, tmp_path: Path) -> None:
        """La tabla referenced_but_not_fetched sobrevive al _clone (snapshot)."""
        db_path = tmp_path / "test.duckdb"
        backend = DuckDBBackend(path=db_path)
        backend.add_referenced_refs(["W1", "W2", "W3"], cycle_round=1)

        # _clone simula el comportamiento de snapshot para :memory:
        # Para un archivo en disco, una nueva instancia comparte los datos
        backend2 = DuckDBBackend(path=db_path)
        assert backend2.referenced_refs_count() == 3
        assert set(backend2.referenced_refs()) == {"W1", "W2", "W3"}
        backend.close()
        backend2.close()

    def test_migracion_liviana_db_sin_tabla(self, tmp_path: Path) -> None:
        """Una DB sin referenced_but_not_fetched no falla al abrirla.

        Simula una base pre-#54: creamos la tabla corpus y loop_state_log
        manualmente sin referenced_but_not_fetched, luego abrimos DuckDBBackend
        que debe crearla vía el DDL CREATE TABLE IF NOT EXISTS.
        """
        import duckdb

        db_path = tmp_path / "legacy.duckdb"
        # Crear una DB con solo las tablas viejas (sin referenced_but_not_fetched)
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
        con.close()

        # Abrir con DuckDBBackend — no debe fallar
        backend = DuckDBBackend(path=db_path)
        # La tabla nueva debe existir y estar vacía
        assert backend.referenced_refs_count() == 0
        backend.close()

    def test_corpus_hash_no_cambia(self, tmp_path: Path) -> None:
        """corpus_hash no cambia al agregar referenced_refs al DuckDBBackend."""
        db_path = tmp_path / "test.duckdb"
        backend = DuckDBBackend(path=db_path)
        hash_vacio = backend.corpus_hash()

        backend.add_referenced_refs(["W99"], cycle_round=1)
        hash_despues = backend.corpus_hash()

        assert hash_vacio == hash_despues
        backend.close()


# ---------------------------------------------------------------------------
# Comando chain — integración con store
# ---------------------------------------------------------------------------


class TestRunChainBackwardNoPersistePlaceholders:
    """run_chain backward: no persiste filas-fantasma; persiste en tabla auxiliar."""

    def _seed_store(self, store_path: Path, refs: list[str]) -> None:
        """Crea un store con una semilla que tiene las referencias dadas."""
        from bib2graph.corpus import Corpus
        from bib2graph.stores.duckdb import DuckDBStore

        row = _base_row("P1", references_id=refs)
        table = pa.Table.from_pylist([row], schema=CORPUS_SCHEMA)
        corpus = Corpus.from_arrow(table)
        store = DuckDBStore(store_path)
        store.persist(corpus)
        from bib2graph.cycle import CycleState

        store.backend.set_loop_state(CycleState.SEEDED, cycle_round=1)
        store.close()

    def test_corpus_no_crece_con_backward(self, tmp_path: Path) -> None:
        """Tras chain backward, el corpus NO tiene filas-fantasma."""
        from bib2graph.cli.commands.chain import run_chain
        from bib2graph.stores.duckdb import DuckDBStore

        store_path = tmp_path / "lib.duckdb"
        self._seed_store(store_path, ["REF_A", "REF_B"])

        store_before = DuckDBStore(store_path)
        n_before = len(store_before.load())
        store_before.close()

        run_chain(store_path, direction="backward")

        store_after = DuckDBStore(store_path)
        corpus_after = store_after.load()
        n_after = len(corpus_after)

        # El corpus no creció (no hay filas-fantasma backward)
        assert n_after == n_before, (
            f"El corpus creció de {n_before} a {n_after} tras backward chaining: "
            "las filas-fantasma backward no deben estar en el corpus (#54)"
        )
        store_after.close()

    def test_sin_titulo_placeholder_tras_chain_backward(self, tmp_path: Path) -> None:
        """Tras chain backward, no hay títulos '[candidate:...]' en el corpus."""
        from bib2graph.cli.commands.chain import run_chain
        from bib2graph.stores.duckdb import DuckDBStore

        store_path = tmp_path / "lib.duckdb"
        self._seed_store(store_path, ["REF_A"])

        run_chain(store_path, direction="backward")

        store = DuckDBStore(store_path)
        rows = store.load().to_arrow().to_pylist()
        store.close()

        for row in rows:
            title = row.get("title") or ""
            assert "[candidate:" not in title, (
                f"Título placeholder en corpus: {title!r}"
            )

    def test_referenced_but_not_fetched_tiene_ids(self, tmp_path: Path) -> None:
        """Tras chain backward, referenced_but_not_fetched tiene los IDs."""
        from bib2graph.backends.duckdb import DuckDBBackend
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        self._seed_store(store_path, ["REF_A", "REF_B"])

        run_chain(store_path, direction="backward")

        backend = DuckDBBackend(path=store_path)
        refs = set(backend.referenced_refs())
        assert "REF_A" in refs
        assert "REF_B" in refs
        backend.close()

    def test_observed_refs_count_en_resultado(self, tmp_path: Path) -> None:
        """run_chain devuelve observed_refs_count > 0 en backward."""
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        self._seed_store(store_path, ["REF_A", "REF_B"])

        result = run_chain(store_path, direction="backward")

        assert "observed_refs_count" in result
        assert result["observed_refs_count"] == 2

    def test_chain_idempotente_referenced(self, tmp_path: Path) -> None:
        """Correr chain backward dos veces no duplica los IDs en la tabla auxiliar."""
        from bib2graph.backends.duckdb import DuckDBBackend
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        self._seed_store(store_path, ["REF_A", "REF_B"])

        run_chain(store_path, direction="backward")
        run_chain(store_path, direction="backward")

        backend = DuckDBBackend(path=store_path)
        count = backend.referenced_refs_count()
        # No debe haber duplicados — sigue siendo 2
        assert count == 2, (
            f"Esperado 2 IDs únicos, encontrado {count} (posibles duplicados)"
        )
        backend.close()


# ---------------------------------------------------------------------------
# b2g status — campo referenced_not_fetched
# ---------------------------------------------------------------------------


class TestStatusReferencedNotFetched:
    """run_status devuelve el campo referenced_not_fetched."""

    def test_status_campo_referenced_not_fetched(self, tmp_path: Path) -> None:
        """run_status incluye referenced_not_fetched (cuenta de IDs observados)."""
        from bib2graph.cli.commands.chain import run_chain
        from bib2graph.cli.commands.status import run_status
        from bib2graph.corpus import Corpus
        from bib2graph.cycle import CycleState
        from bib2graph.stores.duckdb import DuckDBStore

        store_path = tmp_path / "lib.duckdb"
        row = _base_row("P1", references_id=["REF_A", "REF_B"])
        table = pa.Table.from_pylist([row], schema=CORPUS_SCHEMA)
        corpus = Corpus.from_arrow(table)
        store = DuckDBStore(store_path)
        store.persist(corpus)
        store.backend.set_loop_state(CycleState.SEEDED, cycle_round=1)
        store.close()

        run_chain(store_path, direction="backward")

        data = run_status(store_path)

        assert "referenced_not_fetched" in data, (
            "run_status debe incluir el campo 'referenced_not_fetched'"
        )
        assert data["referenced_not_fetched"] == 2

    def test_status_campo_cero_sin_backward(self, tmp_path: Path) -> None:
        """run_status devuelve referenced_not_fetched=0 sin backward chaining."""
        from bib2graph.cli.commands.status import run_status
        from bib2graph.corpus import Corpus
        from bib2graph.stores.duckdb import DuckDBStore

        store_path = tmp_path / "lib.duckdb"
        row = _base_row("P1")
        table = pa.Table.from_pylist([row], schema=CORPUS_SCHEMA)
        corpus = Corpus.from_arrow(table)
        store = DuckDBStore(store_path)
        store.persist(corpus)
        store.close()

        data = run_status(store_path)
        assert data.get("referenced_not_fetched", 0) == 0


# ---------------------------------------------------------------------------
# No-regresión forward
# ---------------------------------------------------------------------------


class TestForwardNoRegression:
    """chain(forward) sigue materializando works reales al corpus."""

    def test_forward_materializa_en_corpus(self) -> None:
        """Forward chaining: los candidatos SÍ van al corpus (no cambia)."""

        class TrackingSource:
            def fetch_citing_batch(
                self, ids: list[str], *, max_per_paper: int | None = None
            ) -> dict[str, list[str]]:
                return {"W1": ["W9999"]}

        rows = [_base_row("P1", openalex_id="W1", curation_status="candidate")]
        corpus = _make_corpus(*rows)
        forager = Forager(TrackingSource(), depth=1)  # type: ignore[arg-type]
        ranked = forager.chain(corpus, direction="forward")

        # Forward: el corpus tiene el candidato
        cand_rows = ranked.corpus.to_arrow().to_pylist()
        assert len(cand_rows) == 1, (
            f"Forward chaining debe materializar 1 candidato, hay {len(cand_rows)}"
        )
        # observed_refs está vacío (solo backward genera observed_refs)
        assert ranked.observed_refs == []

    def test_forward_corpus_hash_crece(self) -> None:
        """Tras forward chaining, el corpus crece y el hash cambia."""

        class TrackingSource:
            def fetch_citing_batch(
                self, ids: list[str], *, max_per_paper: int | None = None
            ) -> dict[str, list[str]]:
                return {"W1": ["W9999"]}

        rows = [_base_row("P1", openalex_id="W1")]
        corpus = _make_corpus(*rows)
        hash_antes = corpus._backend.corpus_hash()

        forager = Forager(TrackingSource(), depth=1)  # type: ignore[arg-type]
        ranked = forager.chain(corpus, direction="forward")
        merged = corpus.merge(ranked.corpus)

        hash_despues = merged._backend.corpus_hash()
        assert hash_antes != hash_despues, (
            "El corpus_hash debe cambiar tras forward chaining (se agregó un candidato)"
        )
