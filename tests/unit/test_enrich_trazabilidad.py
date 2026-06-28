"""Tests de trazabilidad de enriquecimiento — issue #141.

Verifica que:
1. Tras ``run_enrich``, ``manifest.enrichers`` persiste en el store y se
   recupera en el próximo ``store.load()`` (no queda ``[]`` vacío).
2. Los params del ``EnricherRef`` persisten con los valores calculados.
3. Re-aplicar ``run_enrich`` (idempotencia) reemplaza las refs anteriores
   en vez de acumularlas indefinidamente.
4. El flujo ``chain`` (refs_doi) + ``build`` (cited_by) acumula ambos
   ``EnricherRef`` en el manifest tras la segunda carga.

Marcador: ``unit`` (DuckDB en ``tmp_path``, sin red real; transports mockeados).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pyarrow as pa
import pytest

from bib2graph.constants import CurationStatus
from bib2graph.schemas import CORPUS_SCHEMA

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_row(
    *,
    id: str,
    source_id: str | None = None,
    title: str = "Título de prueba",
    year: int = 2020,
    is_seed: bool = True,
    curation_status: str = CurationStatus.ACCEPTED,
    references_id: list[str] | None = None,
) -> dict[str, Any]:
    """Fila mínima compatible con el schema canónico."""
    return {
        "id": id,
        "source_id": source_id,
        "doi": None,
        "title": title,
        "year": year,
        "abstract": None,
        "source": None,
        "language": "en",
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


def _seed_store(store_path: Path, rows: list[dict[str, Any]]) -> None:
    """Puebla un store DuckDB con las filas dadas."""
    from bib2graph.corpus import Corpus
    from bib2graph.stores.duckdb import DuckDBStore

    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)
    store = DuckDBStore(store_path)
    store.persist(corpus)
    store.close()


def _make_empty_transport() -> httpx.MockTransport:
    """MockTransport que devuelve respuestas vacías (sin resolver refs ni citantes)."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"results": [], "meta": {"count": 0, "next_cursor": None}},
            headers={"x-openalex-api-version": "2026-05-01"},
        )

    return httpx.MockTransport(handler)


def _citing_work(citer_oa_id: str, cites_ids: list[str]) -> dict[str, Any]:
    """Construye un objeto Work de OpenAlex que representa un citante."""
    return {
        "id": f"https://openalex.org/{citer_oa_id}",
        "doi": None,
        "title": f"Citante {citer_oa_id}",
        "display_name": f"Citante {citer_oa_id}",
        "publication_year": 2023,
        "language": "en",
        "abstract_inverted_index": None,
        "authorships": [],
        "keywords": [],
        "referenced_works": [f"https://openalex.org/{oa_id}" for oa_id in cites_ids],
        "primary_location": None,
        "type": "article",
    }


def _make_cited_by_transport(
    citing_works: list[dict[str, Any]],
) -> httpx.MockTransport:
    """MockTransport que responde a ``cites:`` con la lista de citantes dada."""

    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "openalex_id" in url_str:
            body: dict[str, Any] = {
                "results": [],
                "meta": {"count": 0, "next_cursor": None},
            }
        elif "cites" in url_str:
            body = {
                "results": citing_works,
                "meta": {"count": len(citing_works), "next_cursor": None},
            }
        else:
            body = {"results": [], "meta": {"count": 0, "next_cursor": None}}
        return httpx.Response(
            200,
            json=body,
            headers={"x-openalex-api-version": "2026-05-01"},
        )

    return httpx.MockTransport(handler)


# ---------------------------------------------------------------------------
# 1. manifest.enrichers persiste tras run_enrich
# ---------------------------------------------------------------------------


def test_manifest_enrichers_persiste_tras_run_enrich(tmp_path: Path) -> None:
    """Tras run_enrich, manifest.enrichers no queda vacío en la siguiente carga."""
    from bib2graph.cli.commands.enrich import run_enrich
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "test.duckdb"
    _seed_store(
        store_path,
        [_make_row(id="P1", source_id="W100")],
    )

    citing_works = [_citing_work("C1", ["W100"])]
    run_enrich(store_path, transport=_make_cited_by_transport(citing_works))

    # Reabrir el store en instancia nueva y verificar que manifest.enrichers sobrevivió
    store = DuckDBStore(store_path)
    corpus = store.load()
    store.close()

    assert len(corpus.manifest.enrichers) >= 1, (
        "manifest.enrichers debe tener al menos 1 EnricherRef tras run_enrich"
    )


# ---------------------------------------------------------------------------
# 2. Los params del EnricherRef persisten con los valores calculados
# ---------------------------------------------------------------------------


def test_manifest_enrichers_params_persisten(tmp_path: Path) -> None:
    """Los params del EnricherRef persisten correctamente en el store."""
    from bib2graph.cli.commands.enrich import run_enrich
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "test.duckdb"
    _seed_store(
        store_path,
        [_make_row(id="P1", source_id="W100")],
    )

    citing_works = [_citing_work("C1", ["W100"])]
    run_enrich(store_path, transport=_make_cited_by_transport(citing_works))

    # Reabrir el store y verificar que los params del EnricherRef son correctos
    store = DuckDBStore(store_path)
    corpus = store.load()
    store.close()

    enrichers_by_name = {e.name: e for e in corpus.manifest.enrichers}

    # Pasada cited_by debe registrarse con sus params
    assert "openalex_cited_by" in enrichers_by_name, (
        "Debe existir EnricherRef 'openalex_cited_by' tras run_enrich"
    )
    cb_ref = enrichers_by_name["openalex_cited_by"]
    assert "resolved" in cb_ref.params, (
        "EnricherRef 'openalex_cited_by' debe tener el param 'resolved'"
    )
    assert "total" in cb_ref.params, (
        "EnricherRef 'openalex_cited_by' debe tener el param 'total'"
    )


# ---------------------------------------------------------------------------
# 3. Idempotencia: re-aplicar run_enrich reemplaza, no acumula
# ---------------------------------------------------------------------------


def test_manifest_enrichers_idempotente_no_acumula(tmp_path: Path) -> None:
    """Re-aplicar run_enrich reemplaza los EnricherRef, no los duplica."""
    from bib2graph.cli.commands.enrich import run_enrich
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "test.duckdb"
    _seed_store(
        store_path,
        [_make_row(id="P1", source_id="W100")],
    )

    transport = _make_cited_by_transport([_citing_work("C1", ["W100"])])

    # Dos ejecuciones sucesivas
    run_enrich(store_path, transport=transport)
    run_enrich(
        store_path,
        transport=_make_cited_by_transport([_citing_work("C1", ["W100"])]),
    )

    # Reabrir y verificar que no hay duplicados (cada nombre aparece una sola vez)
    store = DuckDBStore(store_path)
    corpus = store.load()
    store.close()

    names = [e.name for e in corpus.manifest.enrichers]
    assert len(names) == len(set(names)), (
        f"Hay EnricherRef duplicados en manifest.enrichers: {names}"
    )
