"""Tests unitarios del Hito 8a — ``OpenAlexEnricher`` y el helper ``enrich_corpus``.

Todos los tests de red usan ``httpx.MockTransport`` (sin red real en CI).

Casos cubiertos:
1. Resolución refs→DOI: respuesta mockeada → ``references_doi`` poblado y
   alineado a ``references_id``.
2. Idempotencia: ``enrich(enrich(c))`` == ``enrich(c)`` (mismo resultado).
3. Batching: corpus con >100 references únicas dispara >1 request.
4. Refs no resueltas → None en esa posición (no pierde el paper, no desalinea).
5. Corpus sin references → 0 resueltas, sin error.
6. ``cli._enrich.enrich_corpus`` (pass_name="refs_doi") vía store: contrato del
   dict de métricas (claves estables). El verbo suelto ``b2g enrich`` (y su
   función núcleo ``cli.commands.enrich.run_enrich``, que delegaba en este
   mismo helper) fue retirado en 0.12.0 (#207, ADR 0038 P1); estos tests
   ejercen la misma ruta de I/O (abrir store, enriquecer, persistir) que
   ``run_enrich`` usaba internamente.
7. Red caída → propaga ``httpx.ConnectError`` (exit 4 vía ``@handle_errors``).
8. ``Enricher`` Protocol: ``OpenAlexEnricher`` satisface el protocolo.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pyarrow as pa
import pytest

from bib2graph.constants import Col
from bib2graph.corpus import Corpus
from bib2graph.schemas import CORPUS_SCHEMA

# ---------------------------------------------------------------------------
# Helpers de filas mínimas y corpus de test
# ---------------------------------------------------------------------------


def _make_row(
    *,
    id: str,
    openalex_id: str | None = None,
    references_id: list[str] | None = None,
) -> dict[str, Any]:
    """Fila mínima compatible con el schema canónico."""
    return {
        "id": id,
        "openalex_id": openalex_id,
        "doi": None,
        "title": f"Paper {id}",
        "year": 2020,
        "abstract": None,
        "source": None,
        "language": "en",
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
        "references_id": references_id,
        "references_doi": None,
        "cited_by_id": None,
    }


def _corpus_from_rows(rows: list[dict[str, Any]]) -> Corpus:
    """Construye un Corpus Arrow desde una lista de dicts."""
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    return Corpus.from_arrow(table)


# ---------------------------------------------------------------------------
# Helpers de mocks HTTP
# ---------------------------------------------------------------------------


def _make_dois_transport(
    id_doi_map: dict[str, str],
) -> httpx.MockTransport:
    """MockTransport que responde a consultas ``openalex_id:`` con los DOIs dados.

    Responde con una lista de objetos ``{id: url, doi: url}`` filtrando por
    los IDs presentes en el filtro OR de la request.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        # Extraer los IDs pedidos del parámetro filter
        url_str = str(request.url)
        results = []
        for short_id, doi in id_doi_map.items():
            if short_id in url_str:
                results.append(
                    {
                        "id": f"https://openalex.org/{short_id}",
                        "doi": f"https://doi.org/{doi}",
                    }
                )
        body = {
            "results": results,
            "meta": {"count": len(results), "next_cursor": None},
        }
        return httpx.Response(
            200,
            json=body,
            headers={"x-openalex-api-version": "2026-05-01"},
        )

    return httpx.MockTransport(handler)


def _make_error_transport() -> httpx.MockTransport:
    """MockTransport que simula error de red."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Sin conexión (mock)")

    return httpx.MockTransport(handler)


def _make_counting_transport(
    id_doi_map: dict[str, str],
) -> tuple[httpx.MockTransport, list[int]]:
    """MockTransport que cuenta cuántas requests recibe.

    Returns:
        Tupla ``(transport, call_counter)`` donde ``call_counter[0]`` se
        incrementa en cada request recibida.
    """
    calls: list[int] = [0]

    def handler(request: httpx.Request) -> httpx.Response:
        calls[0] += 1
        url_str = str(request.url)
        results = []
        for short_id, doi in id_doi_map.items():
            if short_id in url_str:
                results.append(
                    {
                        "id": f"https://openalex.org/{short_id}",
                        "doi": f"https://doi.org/{doi}",
                    }
                )
        body = {
            "results": results,
            "meta": {"count": len(results), "next_cursor": None},
        }
        return httpx.Response(200, json=body)

    return httpx.MockTransport(handler), calls


# ---------------------------------------------------------------------------
# Importaciones diferidas (para que el módulo importe limpio sin duckdb en scope)
# ---------------------------------------------------------------------------


def _make_enricher(transport: httpx.BaseTransport) -> Any:
    from bib2graph.enrichers.openalex import OpenAlexEnricher
    from bib2graph.sources.openalex import OpenAlexSource

    source = OpenAlexSource(email="test@example.com", transport=transport)
    return OpenAlexEnricher(source)


def _run_enrich_via_store(
    store_path: Path, *, transport: httpx.BaseTransport
) -> dict[str, Any]:
    """Replica el camino de I/O que usaba el ex-``run_enrich`` (retirado #207).

    Abre el store, enriquece en memoria con ``cli._enrich.enrich_corpus``
    (pass_name="both", misma fuente única que ``chain``/``build`` usan) y
    persiste — el mismo camino que ``cli.commands.enrich.run_enrich`` recorría
    antes de su retiro en 0.12.0 (ADR 0038 P1).
    """
    from bib2graph.cli._enrich import enrich_corpus
    from bib2graph.sources.openalex import OpenAlexSource
    from bib2graph.stores.duckdb import DuckDBStore

    store = DuckDBStore(store_path)
    try:
        corpus = store.load()
        source = OpenAlexSource(transport=transport)
        enriched, metrics = enrich_corpus(corpus, source, pass_name="both")
        store.persist(enriched)
        store.backend.persist_enricher_refs(enriched.manifest.enrichers)
        total_papers = len(enriched)
    finally:
        store.close()

    return {
        "refs_resolved": metrics.get("refs_resolved", 0),
        "refs_total_unique": metrics.get("refs_total_unique", 0),
        "citing_new": metrics.get("citing_new", 0),
        "citing_targets": metrics.get("citing_targets", 0),
        "total_papers": total_papers,
    }


# ---------------------------------------------------------------------------
# 1. Resolución refs→DOI: references_doi poblado y alineado
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_enrich_resuelve_references_doi() -> None:
    """``enrich`` rellena ``references_doi`` alineado a ``references_id``."""
    doi_map = {"W1111111": "10.1000/paper1", "W2222222": "10.1000/paper2"}
    corpus = _corpus_from_rows(
        [
            _make_row(
                id="P1",
                openalex_id="W9999999",
                references_id=["W1111111", "W2222222"],
            )
        ]
    )

    enricher = _make_enricher(_make_dois_transport(doi_map))
    result = enricher.enrich(corpus)

    table = result.to_arrow()
    refs_doi = table.column(Col.REFERENCES_DOI).to_pylist()[0]

    assert refs_doi is not None
    assert len(refs_doi) == 2
    assert refs_doi[0] == "10.1000/paper1"
    assert refs_doi[1] == "10.1000/paper2"


@pytest.mark.unit
def test_enrich_alineacion_con_references_id() -> None:
    """El orden de ``references_doi`` coincide exactamente con ``references_id``."""
    # DOI del primer ID pero NO del segundo
    doi_map = {"W1111111": "10.1000/paper1"}
    corpus = _corpus_from_rows(
        [
            _make_row(
                id="P1",
                references_id=["W1111111", "W2222222"],
            )
        ]
    )

    enricher = _make_enricher(_make_dois_transport(doi_map))
    result = enricher.enrich(corpus)

    table = result.to_arrow()
    refs_doi = table.column(Col.REFERENCES_DOI).to_pylist()[0]

    assert refs_doi is not None
    assert refs_doi[0] == "10.1000/paper1"  # resuelto
    assert refs_doi[1] is None  # no resuelto → None


# ---------------------------------------------------------------------------
# 2. Idempotencia: enrich(enrich(c)) == enrich(c)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_enrich_idempotente() -> None:
    """``enrich(enrich(c))`` produce el mismo corpus que ``enrich(c)``."""
    doi_map = {"W1111111": "10.1000/paper1", "W2222222": "10.1000/paper2"}
    corpus = _corpus_from_rows(
        [
            _make_row(
                id="P1",
                references_id=["W1111111", "W2222222"],
            )
        ]
    )

    enricher = _make_enricher(_make_dois_transport(doi_map))
    once = enricher.enrich(corpus)
    twice = enricher.enrich(once)

    # Contenido idéntico (mismos DOIs, sin duplicar)
    once_table = once.to_arrow()
    twice_table = twice.to_arrow()
    once_doi = once_table.column(Col.REFERENCES_DOI).to_pylist()[0]
    twice_doi = twice_table.column(Col.REFERENCES_DOI).to_pylist()[0]

    assert once_doi == twice_doi


@pytest.mark.unit
def test_enrich_idempotente_enricher_ref_no_duplica() -> None:
    """El EnricherRef en el Manifest no se duplica al enriquecer dos veces."""
    doi_map = {"W1111111": "10.1000/paper1"}
    corpus = _corpus_from_rows([_make_row(id="P1", references_id=["W1111111"])])

    enricher = _make_enricher(_make_dois_transport(doi_map))
    once = enricher.enrich(corpus)
    twice = enricher.enrich(once)

    enricher_refs = twice.manifest.enrichers
    names = [e.name for e in enricher_refs]
    # Solo debe haber UNA entrada "openalex_references_doi"
    assert names.count("openalex_references_doi") == 1


# ---------------------------------------------------------------------------
# 3. Batching: >100 references únicas → >1 request
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_enrich_batching_mas_de_100_referencias() -> None:
    """Un corpus con >100 references únicas dispara más de 1 request HTTP."""
    # Crear 150 IDs únicos
    n = 150
    ref_ids = [f"W{i:07d}" for i in range(1, n + 1)]
    doi_map = {rid: f"10.1000/{rid.lower()}" for rid in ref_ids}

    corpus = _corpus_from_rows([_make_row(id="P1", references_id=ref_ids)])

    transport, call_counter = _make_counting_transport(doi_map)
    enricher = _make_enricher(transport)
    enricher.enrich(corpus)

    # Con batch_size=100 y 150 IDs únicos → 2 requests mínimo
    assert call_counter[0] >= 2


@pytest.mark.unit
def test_enrich_batching_exactamente_100_referencias() -> None:
    """100 referencias exactas → 1 sola request (límite justo del batch)."""
    n = 100
    ref_ids = [f"W{i:07d}" for i in range(1, n + 1)]
    doi_map = {rid: f"10.1000/{rid.lower()}" for rid in ref_ids}

    corpus = _corpus_from_rows([_make_row(id="P1", references_id=ref_ids)])

    transport, call_counter = _make_counting_transport(doi_map)
    enricher = _make_enricher(transport)
    enricher.enrich(corpus)

    assert call_counter[0] == 1


# ---------------------------------------------------------------------------
# 4. Refs no resueltas → None (no pierde el paper ni desalinea)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_enrich_ref_no_resuelta_es_none() -> None:
    """Una referencia sin DOI en OpenAlex → None en esa posición."""
    # doi_map NO contiene W9999999 → no se resuelve
    doi_map = {"W1111111": "10.1000/paper1"}
    corpus = _corpus_from_rows(
        [
            _make_row(
                id="P1",
                references_id=["W1111111", "W9999999"],
            )
        ]
    )

    enricher = _make_enricher(_make_dois_transport(doi_map))
    result = enricher.enrich(corpus)

    table = result.to_arrow()
    refs_doi = table.column(Col.REFERENCES_DOI).to_pylist()[0]

    assert refs_doi is not None
    assert refs_doi[0] == "10.1000/paper1"
    assert refs_doi[1] is None


@pytest.mark.unit
def test_enrich_no_pierde_papers() -> None:
    """El corpus enriquecido tiene al menos tantos papers como el original."""
    doi_map = {"W1111111": "10.1000/paper1"}
    rows = [
        _make_row(id="P1", references_id=["W1111111"]),
        _make_row(id="P2", references_id=None),
        _make_row(id="P3", references_id=["W9999999"]),
    ]
    corpus = _corpus_from_rows(rows)

    enricher = _make_enricher(_make_dois_transport(doi_map))
    result = enricher.enrich(corpus)

    assert len(result) == len(corpus)


# ---------------------------------------------------------------------------
# 5. Corpus sin references → 0 resueltas, sin error
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_enrich_corpus_sin_references_no_falla() -> None:
    """Corpus sin references_id → devuelve corpus sin error y 0 resueltas."""
    corpus = _corpus_from_rows(
        [
            _make_row(id="P1", references_id=None),
            _make_row(id="P2", references_id=None),
        ]
    )

    # El transport nunca debería llamarse
    transport, call_counter = _make_counting_transport({})
    enricher = _make_enricher(transport)
    result = enricher.enrich(corpus)

    # No se hicieron requests a la red
    assert call_counter[0] == 0
    # El EnricherRef registra 0/0
    enricher_refs = result.manifest.enrichers
    ref_entry = next(
        (e for e in enricher_refs if e.name == "openalex_references_doi"), None
    )
    assert ref_entry is not None
    assert ref_entry.params["resolved"] == "0"
    assert ref_entry.params["total_unique_refs"] == "0"


# ---------------------------------------------------------------------------
# 6. enrich_corpus vía store: contrato del dict de salida (claves estables)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_run_enrich_devuelve_claves_esperadas(tmp_path: Path) -> None:
    """El camino de I/O de enrich devuelve dict con ``refs_resolved``,
    ``refs_total_unique``, ``total_papers``."""
    from bib2graph.stores.duckdb import DuckDBStore

    doi_map = {"W1111111": "10.1000/paper1"}
    rows = [_make_row(id="P1", references_id=["W1111111"])]
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)
    store = DuckDBStore(tmp_path / "test.duckdb")
    store.persist(corpus)

    transport = _make_dois_transport(doi_map)
    data = _run_enrich_via_store(tmp_path / "test.duckdb", transport=transport)

    assert "refs_resolved" in data
    assert "refs_total_unique" in data
    assert "total_papers" in data
    assert isinstance(data["refs_resolved"], int)
    assert isinstance(data["refs_total_unique"], int)
    assert isinstance(data["total_papers"], int)
    assert data["total_papers"] == 1


@pytest.mark.unit
def test_run_enrich_corpus_sin_references(tmp_path: Path) -> None:
    """Corpus sin referencias → el camino de I/O de enrich devuelve 0 resueltas, sin error."""
    from bib2graph.stores.duckdb import DuckDBStore

    rows = [_make_row(id="P1", references_id=None)]
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)
    store = DuckDBStore(tmp_path / "test.duckdb")
    store.persist(corpus)

    transport, call_counter = _make_counting_transport({})
    data = _run_enrich_via_store(tmp_path / "test.duckdb", transport=transport)

    assert data["refs_resolved"] == 0
    assert data["refs_total_unique"] == 0
    assert call_counter[0] == 0  # sin requests a la red


# ---------------------------------------------------------------------------
# 7. Red caída → propaga httpx.ConnectError (exit 4 vía @handle_errors)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_run_enrich_red_caida_propaga_error(tmp_path: Path) -> None:
    """El camino de I/O de enrich con red caída propaga ``httpx.ConnectError`` (exit 4)."""
    from bib2graph.stores.duckdb import DuckDBStore

    rows = [_make_row(id="P1", references_id=["W1111111"])]
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)
    store = DuckDBStore(tmp_path / "test.duckdb")
    store.persist(corpus)

    with pytest.raises(httpx.ConnectError):
        _run_enrich_via_store(
            tmp_path / "test.duckdb", transport=_make_error_transport()
        )


# ---------------------------------------------------------------------------
# 8. Enricher Protocol: OpenAlexEnricher satisface el protocolo
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_openalex_enricher_cumple_protocolo() -> None:
    """``OpenAlexEnricher`` satisface el ``Enricher`` Protocol."""
    from bib2graph.enrichers.base import Enricher
    from bib2graph.enrichers.openalex import OpenAlexEnricher
    from bib2graph.sources.openalex import OpenAlexSource

    source = OpenAlexSource(email="test@example.com")
    enricher = OpenAlexEnricher(source)

    assert isinstance(enricher, Enricher)


# ---------------------------------------------------------------------------
# 9. Múltiples papers con referencias solapadas
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_enrich_multiples_papers_referencias_solapadas() -> None:
    """Corpus con varios papers que comparten referencias → todos resueltos."""
    doi_map = {
        "W1111111": "10.1000/paper1",
        "W2222222": "10.1000/paper2",
    }
    rows = [
        _make_row(id="P1", references_id=["W1111111", "W2222222"]),
        _make_row(id="P2", references_id=["W2222222"]),
        _make_row(id="P3", references_id=None),
    ]
    corpus = _corpus_from_rows(rows)

    enricher = _make_enricher(_make_dois_transport(doi_map))
    result = enricher.enrich(corpus)

    table = result.to_arrow()
    refs_doi = table.column(Col.REFERENCES_DOI).to_pylist()

    # P1: ambos resueltos
    assert refs_doi[0] == ["10.1000/paper1", "10.1000/paper2"]
    # P2: uno resuelto
    assert refs_doi[1] == ["10.1000/paper2"]
    # P3: sin references → None
    assert refs_doi[2] is None
