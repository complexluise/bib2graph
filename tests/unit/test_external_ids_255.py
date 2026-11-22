"""Tests del Corte 2 (#255, cierra #120) del ADR 0053: ``external_ids`` por engine.

``DuckDBStore.register_external_ids`` registra ``(id, engine, source_id)`` tras
cada persistencia de ingesta (seed, resolve, chain, build, restore).  Sin red
(``httpx.MockTransport``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pyarrow as pa
import pytest

from bib2graph.backends.memory import compute_corpus_hash
from bib2graph.constants import Col, Provider
from bib2graph.corpus import Corpus
from bib2graph.schemas import CORPUS_SCHEMA

pytestmark = pytest.mark.unit

SAMPLE_WORKS: list[dict[str, Any]] = json.loads(
    (Path(__file__).parent.parent / "fixtures" / "sample_works.json").read_text(
        encoding="utf-8"
    )
)

S2_SEED: dict[str, Any] = {
    "paperId": "s2seedaaa111",
    "title": "Seed paper S2",
    "year": 2019,
    "abstract": "abs",
    "externalIds": {"DOI": "10.1000/seed1"},
    "authors": [{"authorId": "1", "name": "Ana Autora"}],
    "fieldsOfStudy": ["Economics"],
    "referenceCount": 0,
    "citationCount": 1,
}


S2_CITER: dict[str, Any] = {
    "paperId": "s2citerbbb222",
    "title": "Citing paper",
    "year": 2022,
    "abstract": "citer abs",
    "externalIds": {"DOI": "10.1000/citer1"},
    "authors": [{"authorId": "2", "name": "Beto Citante"}],
    "fieldsOfStudy": ["Economics"],
    "references": [
        {"paperId": "s2seedaaa111", "externalIds": {"DOI": "10.1000/seed1"}}
    ],
}


def _oa_transport() -> httpx.MockTransport:
    calls = [0]

    def handler(request: httpx.Request) -> httpx.Response:
        calls[0] += 1
        results = SAMPLE_WORKS if calls[0] == 1 else []
        return httpx.Response(
            200,
            json={
                "results": results,
                "meta": {"count": len(results), "next_cursor": None},
            },
            headers={"x-openalex-api-version": "2026-06-17"},
        )

    return httpx.MockTransport(handler)


def _s2_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/paper/search"):
            data = [S2_SEED] if request.url.params.get("offset", "0") == "0" else []
            return httpx.Response(200, json={"total": 1, "offset": 0, "data": data})
        if request.url.path.endswith("/citations"):
            if request.url.params.get("offset", "0") != "0":
                return httpx.Response(200, json={"offset": 1, "data": []})
            return httpx.Response(
                200,
                json={"offset": 0, "next": None, "data": [{"citingPaper": S2_CITER}]},
            )
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def _external_ids(store_path: Path) -> list[tuple[str, str, str]]:
    from bib2graph.stores.duckdb import DuckDBStore

    store = DuckDBStore(store_path)
    try:
        return sorted(store.backend.all_external_ids())
    finally:
        store.close()


def _rows(
    store_path: Path, provider: Provider = Provider.OPENALEX
) -> list[dict[str, Any]]:
    from bib2graph.stores.duckdb import DuckDBStore

    store = DuckDBStore(store_path, provider=provider)
    try:
        return store.load().to_arrow().to_pylist()
    finally:
        store.close()


def _row(id_: str, source_id: str | None, doi: str | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {name: None for name in CORPUS_SCHEMA.names}
    row.update(
        {
            Col.ID: id_,
            Col.SOURCE_ID: source_id,
            Col.DOI: doi,
            Col.TITLE: f"Paper {id_}",
            Col.YEAR: 2020,
            Col.PROVIDER: "openalex",
            Col.IS_SEED: True,
            Col.CURATION_STATUS: "candidate",
        }
    )
    for col in (
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
    ):
        row[col] = []
    return row


def _corpus(rows: list[dict[str, Any]]) -> Corpus:
    return Corpus.from_arrow(pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA))


class TestSeedRegistra:
    def test_seed_openalex_registra_external_ids(self, tmp_path: Path) -> None:
        from bib2graph.cli.commands.seed import run_seed

        store_path = tmp_path / "lib.duckdb"
        run_seed(store_path, "unequal exchange", transport=_oa_transport())

        expected = sorted(
            (r[Col.ID], "openalex", r[Col.SOURCE_ID])
            for r in _rows(store_path)
            if r[Col.SOURCE_ID] is not None
        )
        assert expected  # el fixture trae source_id
        assert _external_ids(store_path) == expected

    def test_seed_s2_registra_external_ids(self, tmp_path: Path) -> None:
        from bib2graph.cli.commands.seed import run_seed

        store_path = tmp_path / "lib.duckdb"
        run_seed(
            store_path,
            "unequal exchange",
            provider=Provider.S2,
            transport=_s2_transport(),
        )

        rows = _rows(store_path, Provider.S2)
        assert [r[Col.SOURCE_ID] for r in rows] == ["s2seedaaa111"]
        # Token Provider ("s2"), no "semanticscholar" (D1.6).
        assert _external_ids(store_path) == [(rows[0][Col.ID], "s2", "s2seedaaa111")]

    def test_external_ids_idempotente(self, tmp_path: Path) -> None:
        from bib2graph.cli.commands.seed import run_seed

        store_path = tmp_path / "lib.duckdb"
        run_seed(store_path, "unequal exchange", transport=_oa_transport())
        first = _external_ids(store_path)
        run_seed(store_path, "unequal exchange", transport=_oa_transport())
        assert _external_ids(store_path) == first


class TestRegisterExternalIds:
    def test_fila_sin_source_id_no_registra(self, tmp_path: Path) -> None:
        from bib2graph.stores.duckdb import DuckDBStore

        store = DuckDBStore(tmp_path / "lib.duckdb")
        try:
            corpus = _corpus([_row("a", None), _row("b", "W2")])
            store.persist_replace(corpus)
            n = store.register_external_ids(corpus, Provider.OPENALEX)
            assert n == 1
            assert store.backend.all_external_ids() == [("b", "openalex", "W2")]
        finally:
            store.close()

    def test_external_ids_no_altera_corpus_hash(self, tmp_path: Path) -> None:
        from bib2graph.stores.duckdb import DuckDBStore

        store = DuckDBStore(tmp_path / "lib.duckdb")
        try:
            corpus = _corpus([_row("a", "W1"), _row("b", "W2")])
            store.persist_replace(corpus)
            before = compute_corpus_hash(store.load().to_arrow())
            store.register_external_ids(store.load(), Provider.OPENALEX)
            assert store.backend.all_external_ids()
            assert compute_corpus_hash(store.load().to_arrow()) == before
        finally:
            store.close()

    def test_engine_distinto_coexiste_por_paper(self, tmp_path: Path) -> None:
        from bib2graph.stores.duckdb import DuckDBStore

        path = tmp_path / "lib.duckdb"
        oa = DuckDBStore(path, provider=Provider.OPENALEX)
        try:
            oa.persist_replace(_corpus([_row("a", "W1")]))
            oa.register_external_ids(_corpus([_row("a", "W1")]))
        finally:
            oa.close()
        # ADR 0053 D2: el engine es el carril; el mismo id en el carril s2 registra
        # su propio source_id sin pisar el de openalex.
        s2_row = _row("a", "s2x")
        s2_row[Col.PROVIDER] = "s2"
        s2 = DuckDBStore(path, provider=Provider.S2)
        try:
            s2.persist_replace(_corpus([s2_row]))
            s2.register_external_ids(_corpus([s2_row]))
            assert s2.backend.external_ids_for("a") == {
                "openalex": "W1",
                "s2": "s2x",
            }
        finally:
            s2.close()

    def test_engine_ajeno_al_carril_falla(self, tmp_path: Path) -> None:
        from bib2graph.backends.base import ProviderMismatchError
        from bib2graph.stores.duckdb import DuckDBStore

        store = DuckDBStore(tmp_path / "lib.duckdb", provider=Provider.OPENALEX)
        try:
            store.persist_replace(_corpus([_row("a", "W1")]))
            with pytest.raises(ProviderMismatchError):
                store.register_external_ids(_corpus([_row("a", "W1")]), Provider.S2)
        finally:
            store.close()


class TestOtrosCaminos:
    def test_from_bib_sin_resolve_no_registra(self, tmp_path: Path) -> None:
        from bib2graph.cli.commands.seed import run_seed_from_bib

        bib = tmp_path / "x.bib"
        bib.write_text(
            "@article{k1, title={T}, author={A, B}, year={2020}, doi={10.1/x}}\n",
            encoding="utf-8",
        )
        store_path = tmp_path / "lib.duckdb"
        run_seed_from_bib(store_path, bib)
        assert all(r[Col.SOURCE_ID] is None for r in _rows(store_path))
        assert _external_ids(store_path) == []

    def test_resolve_registra_openalex(self, tmp_path: Path) -> None:
        from bib2graph.service.resolve import resolve_dois
        from bib2graph.stores.duckdb import DuckDBStore

        store_path = tmp_path / "lib.duckdb"
        store = DuckDBStore(store_path)
        store.persist_replace(_corpus([_row("a", None, doi="10.1234/abc")]))
        store.close()

        works = [
            {"id": "https://openalex.org/W999", "doi": "https://doi.org/10.1234/abc"}
        ]

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"results": works, "meta": {"count": 1, "next_cursor": None}},
            )

        resolve_dois(store_path, transport=httpx.MockTransport(handler))
        assert _external_ids(store_path) == [("a", "openalex", "W999")]

    def test_restore_registra_con_el_proveedor(self, tmp_path: Path) -> None:
        import pyarrow.parquet as pq

        from bib2graph.service.snapshot import run_restore

        parquet = tmp_path / "corpus.parquet"
        s2_row = _row("a", "s2abc")
        s2_row[Col.PROVIDER] = "s2"
        pq.write_table(  # type: ignore[no-untyped-call]
            pa.Table.from_pylist([s2_row], schema=CORPUS_SCHEMA), parquet
        )
        store_path = tmp_path / "lib.duckdb"
        run_restore(store_path, parquet, provider=Provider.S2)
        rows = _rows(store_path, Provider.S2)
        assert _external_ids(store_path) == [(rows[0][Col.ID], "s2", "s2abc")]


class TestChainBuildRegistran:
    def _seed_s2_store(self, store_path: Path, *, accepted: bool) -> None:
        from bib2graph.constants import CurationStatus
        from bib2graph.corpus import _rows_with_ids
        from bib2graph.sources.semanticscholar import _paper_to_row
        from bib2graph.stores.duckdb import DuckDBStore

        row = _paper_to_row(
            S2_SEED, equation_id="eq", fetched_at="2026-01-01T00:00:00+00:00"
        )
        if accepted:
            row[Col.CURATION_STATUS] = CurationStatus.ACCEPTED
        store = DuckDBStore(store_path, provider=Provider.S2)
        store.persist(_corpus(_rows_with_ids([row])))
        store.close()

    def test_chain_registra_citantes_s2(self, tmp_path: Path) -> None:
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        self._seed_s2_store(store_path, accepted=False)
        run_chain(
            store_path,
            direction="both",
            provider=Provider.S2,
            transport=_s2_transport(),
        )
        by_sid = {sid: eid for _, eid, sid in _external_ids(store_path)}
        assert {"s2citerbbb222"} <= set(by_sid)
        assert {e for _, e, _ in _external_ids(store_path)} == {"s2"}

    def test_build_cited_by_registra_s2(self, tmp_path: Path) -> None:
        from bib2graph.cli.commands.build import run_build

        store_path = tmp_path / "lib.duckdb"
        self._seed_s2_store(store_path, accepted=True)
        run_build(
            store_path,
            out_dir=tmp_path / "nets",
            provider=Provider.S2,
            transport=_s2_transport(),
        )
        # La pasada cited_by no materializa filas de citantes (solo cited_by_id):
        # se registra la semilla persistida por build (el store partía sin registro).
        assert [(e, sid) for _, e, sid in _external_ids(store_path)] == [
            ("s2", "s2seedaaa111")
        ]


class TestBulk:
    def test_diez_mil_filas_es_una_sentencia_rapida(self, tmp_path: Path) -> None:
        import time

        from bib2graph.stores.duckdb import DuckDBStore

        store = DuckDBStore(tmp_path / "lib.duckdb")
        try:
            corpus = _corpus([_row(f"p{i}", f"W{i}") for i in range(10_000)])
            store.persist_replace(corpus)
            t0 = time.perf_counter()
            n = store.register_external_ids(corpus, Provider.OPENALEX)
            elapsed = time.perf_counter() - t0
            assert n == 10_000
            assert len(store.backend.all_external_ids()) == 10_000
            # Antes (un execute/autocommit por fila): ~65 s.
            assert elapsed < 5, f"register_external_ids tardó {elapsed:.1f}s"
        finally:
            store.close()

    def test_limpia_huerfanos(self, tmp_path: Path) -> None:
        from bib2graph.stores.duckdb import DuckDBStore

        store = DuckDBStore(tmp_path / "lib.duckdb")
        try:
            old = _corpus([_row("a", "W1"), _row("b", "W2")])
            store.persist_replace(old)
            store.register_external_ids(old, Provider.OPENALEX)
            # "a" desaparece del corpus (p. ej. reemplazado por dedup).
            new = _corpus([_row("b", "W2")])
            store.persist_replace(new)
            store.register_external_ids(new, Provider.OPENALEX)
            assert store.backend.all_external_ids() == [("b", "openalex", "W2")]
        finally:
            store.close()

    def test_resolve_dois_solo_registra_filas_resueltas(self, tmp_path: Path) -> None:
        from bib2graph.service.resolve import resolve_dois
        from bib2graph.stores.duckdb import DuckDBStore

        store_path = tmp_path / "lib.duckdb"
        store = DuckDBStore(store_path)
        store.persist_replace(
            _corpus(
                [_row("a", None, doi="10.1234/abc"), _row("s2row", "s2zzz", doi=None)]
            )
        )
        store.close()
        works = [
            {"id": "https://openalex.org/W999", "doi": "https://doi.org/10.1234/abc"}
        ]

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"results": works, "meta": {"count": 1, "next_cursor": None}},
            )

        resolve_dois(store_path, transport=httpx.MockTransport(handler))
        # La fila preexistente (otro proveedor) NO se asume de OpenAlex.
        assert _external_ids(store_path) == [("a", "openalex", "W999")]
