"""Tests — #270 / ADR 0048: ``chain forward`` puebla ``cited_by_id``.

Verifica el "camino único de co-citación" decidido en el ADR 0048: el
forrajeo hacia adelante (``chain --direction forward``), que ya trae los
citantes de las semillas para el chaining, completa además el campo
``cited_by_id`` de esas semillas — el insumo que consume el
``CoCitationProjector`` (ADR 0014, no se toca).

Cubre:
- Forager puro: ``chain(direction='forward')`` incluye en ``RankedCandidates
  .corpus`` una fila de actualización de la semilla con ``cited_by_id``
  poblado (unión, no reemplazo).
- Idempotencia: correr forward dos veces no duplica ``cited_by_id``.
- End-to-end del camino feliz: ``seed → chain forward → curate accept →
  build`` produce una red de co-citación NO vacía, sin necesidad de
  ``enrich`` (deprecado) ni de que build dependa de seeds aceptadas para
  poblar el insumo (el insumo ya llega poblado desde chain).

Marcador: ``integration`` (DuckDB local + httpx.MockTransport; sin red real).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pyarrow as pa
import pytest

from bib2graph.corpus import Corpus
from bib2graph.foraging.forager import Forager
from bib2graph.schemas import CORPUS_SCHEMA

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_row(
    id: str,
    *,
    source_id: str | None = None,
    is_seed: bool = True,
    cited_by_id: list[str] | None = None,
    curation_status: str = "candidate",
) -> dict[str, Any]:
    return {
        "id": id,
        "source_id": source_id,
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
        "references_id": None,
        "references_doi": None,
        "cited_by_id": cited_by_id,
    }


def _make_corpus(*rows: dict[str, Any]) -> Corpus:
    table = pa.Table.from_pylist(list(rows), schema=CORPUS_SCHEMA)
    return Corpus.from_arrow(table)


def _citing_work(
    citer_id: str,
    *,
    cites_ids: list[str],
    title: str = "Citing Paper",
    year: int = 2022,
) -> dict[str, Any]:
    """Work JSON de OpenAlex que cita ``cites_ids`` (IDs cortos, sin prefijo)."""
    return {
        "id": f"https://openalex.org/{citer_id}",
        "doi": None,
        "title": title,
        "display_name": title,
        "publication_year": year,
        "language": "en",
        "abstract_inverted_index": None,
        "authorships": [],
        "keywords": [],
        "referenced_works": [f"https://openalex.org/{cid}" for cid in cites_ids],
        "primary_location": None,
        "type": "article",
    }


def _make_forward_transport(
    citing_works: list[dict[str, Any]],
) -> httpx.MockTransport:
    """Transport que responde a ``cites:`` con los works dados y vacío al resto.

    Cubre también ``openalex_id:`` (refs→DOI, pasada automática de ``chain``)
    devolviendo vacío: no hay DOIs que resolver en estos tests.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        filter_val: str = params.get("filter", "")
        results: list[dict[str, Any]] = citing_works if "cites:" in filter_val else []
        return httpx.Response(
            200,
            json={
                "results": results,
                "meta": {"count": len(results), "next_cursor": None},
            },
            headers={"x-openalex-api-version": "2026-05-01"},
        )

    return httpx.MockTransport(handler)


# ---------------------------------------------------------------------------
# Forager puro: chain(forward) puebla cited_by_id
# ---------------------------------------------------------------------------


class TestForagerForwardPopulatesCitedById:
    """El Forager, en direction forward, incluye actualizaciones de semilla."""

    def test_chain_forward_incluye_cited_by_de_semilla(self) -> None:
        """RankedCandidates.corpus incluye la semilla con cited_by_id poblado."""
        from bib2graph.sources.openalex import OpenAlexSource

        rows = [_base_row("P1", source_id="W1", curation_status="accepted")]
        corpus = _make_corpus(*rows)

        transport = _make_forward_transport([_citing_work("W9999", cites_ids=["W1"])])
        source = OpenAlexSource(transport=transport)
        forager = Forager(source, depth=1)
        ranked = forager.chain(corpus, direction="forward")

        rows_out = ranked.corpus.to_arrow().to_pylist()
        seed_row = next((r for r in rows_out if r["id"] == "P1"), None)
        assert seed_row is not None, (
            "chain(forward) debe incluir una fila de actualización para la "
            "semilla P1 con cited_by_id poblado (ADR 0048, #270)"
        )
        assert seed_row["cited_by_id"] == ["W9999"], (
            f"cited_by_id de la semilla debe contener el citante; "
            f"got {seed_row['cited_by_id']!r}"
        )

    def test_cited_by_id_es_union_no_reemplazo(self) -> None:
        """Si la semilla ya tenía cited_by_id, el nuevo citante se une (D3)."""
        from bib2graph.sources.openalex import OpenAlexSource

        rows = [
            _base_row(
                "P1",
                source_id="W1",
                curation_status="accepted",
                cited_by_id=["W_OLD"],
            )
        ]
        corpus = _make_corpus(*rows)

        transport = _make_forward_transport([_citing_work("W9999", cites_ids=["W1"])])
        source = OpenAlexSource(transport=transport)
        forager = Forager(source, depth=1)
        ranked = forager.chain(corpus, direction="forward")

        rows_out = ranked.corpus.to_arrow().to_pylist()
        seed_row = next(r for r in rows_out if r["id"] == "P1")
        assert set(seed_row["cited_by_id"]) == {"W_OLD", "W9999"}, (
            "cited_by_id debe ser la unión del valor existente y el nuevo "
            f"citante; got {seed_row['cited_by_id']!r}"
        )


# ---------------------------------------------------------------------------
# run_chain: idempotencia end-to-end sobre el store
# ---------------------------------------------------------------------------


class TestRunChainForwardCitedByIdempotente:
    """run_chain(forward) persiste cited_by_id; correr dos veces no duplica."""

    def _seed_store(self, store_path: Path) -> None:
        from bib2graph.cycle import CycleState
        from bib2graph.stores.duckdb import DuckDBStore

        row = _base_row("P1", source_id="W1", curation_status="accepted")
        table = pa.Table.from_pylist([row], schema=CORPUS_SCHEMA)
        corpus = Corpus.from_arrow(table)
        store = DuckDBStore(store_path)
        store.persist(corpus)
        store.backend.set_loop_state(CycleState.SEEDED, cycle_round=1)
        store.close()

    def test_run_chain_forward_puebla_cited_by_id(self, tmp_path: Path) -> None:
        from bib2graph.cli.commands.chain import run_chain
        from bib2graph.stores.duckdb import DuckDBStore

        store_path = tmp_path / "lib.duckdb"
        self._seed_store(store_path)

        transport = _make_forward_transport([_citing_work("W9999", cites_ids=["W1"])])
        run_chain(store_path, direction="forward", transport=transport)

        store = DuckDBStore(store_path)
        rows = store.load().to_arrow().to_pylist()
        store.close()

        seed_row = next(r for r in rows if r["id"] == "P1")
        assert seed_row["cited_by_id"] == ["W9999"], (
            "Tras run_chain(forward), la semilla debe tener cited_by_id "
            f"poblado; got {seed_row['cited_by_id']!r}"
        )

    def test_run_chain_forward_idempotente(self, tmp_path: Path) -> None:
        """Correr chain forward dos veces no duplica cited_by_id."""
        from bib2graph.cli.commands.chain import run_chain
        from bib2graph.stores.duckdb import DuckDBStore

        store_path = tmp_path / "lib.duckdb"
        self._seed_store(store_path)

        transport = _make_forward_transport([_citing_work("W9999", cites_ids=["W1"])])
        run_chain(store_path, direction="forward", transport=transport)
        run_chain(store_path, direction="forward", transport=transport)

        store = DuckDBStore(store_path)
        rows = store.load().to_arrow().to_pylist()
        store.close()

        seed_row = next(r for r in rows if r["id"] == "P1")
        assert seed_row["cited_by_id"] == ["W9999"], (
            "Repetir chain(forward) no debe duplicar cited_by_id; "
            f"got {seed_row['cited_by_id']!r}"
        )


# ---------------------------------------------------------------------------
# End-to-end: seed -> chain forward -> curate accept -> build (co-citación)
# ---------------------------------------------------------------------------


class TestEndToEndCocitationCierraElLazo:
    """El camino natural del lazo produce una red de co-citación no vacía."""

    def test_build_produce_cocitacion_tras_chain_forward(self, tmp_path: Path) -> None:
        """seed -> chain forward -> curate accept -> build: co-citación > 0.

        Dos semillas (P1=W1, P2=W2) comparten un citante (W9999) que las cita
        a ambas.  Tras ``chain --direction forward``, ambas quedan con
        ``cited_by_id=["W9999"]``: comparten un citante, luego están
        co-citadas.  ``build`` debe reflejarlo con ``edges > 0`` en la red
        ``cocitation``, SIN pasar por ``enrich`` (deprecado, ADR 0048).
        """
        from bib2graph.cli.commands.build import run_build
        from bib2graph.cli.commands.chain import run_chain
        from bib2graph.cycle import CycleState
        from bib2graph.stores.duckdb import DuckDBStore

        store_path = tmp_path / "lib.duckdb"

        rows = [
            _base_row("P1", source_id="W1", curation_status="accepted"),
            _base_row("P2", source_id="W2", curation_status="accepted"),
        ]
        table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
        corpus = Corpus.from_arrow(table)
        store = DuckDBStore(store_path)
        store.persist(corpus)
        store.backend.set_loop_state(CycleState.SEEDED, cycle_round=1)
        store.close()

        # Un citante que cita ambas semillas: co-citación entre P1 y P2.
        transport = _make_forward_transport(
            [_citing_work("W9999", cites_ids=["W1", "W2"])]
        )
        chain_result = run_chain(store_path, direction="forward", transport=transport)
        assert chain_result["candidates_found"] > 0

        # curate accept: ambas semillas ya vienen 'accepted' en este fixture
        # (no hace falta un paso CLI adicional; refleja que build no necesita
        # depender de la pasada 8b para tener el insumo — ya llegó de chain).
        # build sigue corriendo su propia pasada 8b heredada (ADR 0025/0038,
        # solapamiento transitorio documentado en ADR 0048); se le inyecta el
        # mismo transport mockeado (idempotente: no debería aportar citantes
        # nuevos, el insumo ya está poblado desde chain forward).
        build_result = run_build(store_path, corpus_scope="all", transport=transport)

        cocitation_entries = [
            n for n in build_result["networks"] if n["kind"] == "cocitation"
        ]
        assert cocitation_entries, "build debe producir una red 'cocitation'"
        assert cocitation_entries[0]["edges"] > 0, (
            "La red de co-citación debe tener aristas: P1 y P2 comparten el "
            f"citante W9999 tras chain forward; got {cocitation_entries[0]}"
        )
