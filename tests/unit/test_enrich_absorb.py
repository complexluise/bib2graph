"""Tests TDD — absorción de ``enrich`` en ``chain``/``build`` (ADR 0038, #162).

Cubre las decisiones de implementación del sub-issue #162:

1. ``chain`` ejecuta la pasada refs→DOI automáticamente sobre el corpus
   mergeado+dedup, ANTES de ``persist_replace``.
2. ``build`` ejecuta la pasada cited_by automáticamente cuando hay seeds
   aceptadas, ANTES de proyectar las redes.
3. ``build`` es no-op (0 requests cited_by) cuando no hay seeds aceptadas;
   ``data["enrichment"]`` queda vacío ``{}``.
4. ``enrich`` suelto sigue funcionando idéntico (delega en el helper
   ``enrich_corpus`` de ``cli._enrich``).
5. ``data["enrichment"]`` es un bloque ADITIVO en chain y build:
   nunca rompe el envelope ``schema="1"``.
6. El helper ``enrich_corpus`` soporta ``pass_name`` inválido con ``ValueError``.
7. Co-citación: tras ``build`` con seeds aceptadas, ``Networks.quick``
   produce 5 redes (co-citación incluida).

Todos los tests son ``unit``: usan ``tmp_path`` + ``httpx.MockTransport``
(sin red real).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pyarrow as pa
import pytest

from bib2graph.constants import CurationStatus
from bib2graph.corpus import Corpus
from bib2graph.schemas import CORPUS_SCHEMA

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers compartidos
# ---------------------------------------------------------------------------


def _row(
    id: str,
    *,
    source_id: str | None = None,
    is_seed: bool = True,
    curation_status: str = CurationStatus.CANDIDATE,
    references_id: list[str] | None = None,
    cited_by_id: list[str] | None = None,
    authors_id: list[str] | None = None,
    institutions_id: list[str] | None = None,
    keywords_id: list[str] | None = None,
) -> dict[str, Any]:
    """Fila mínima compatible con el schema canónico."""
    return {
        "id": id,
        "source_id": source_id,
        "doi": None,
        "title": f"Paper {id}",
        "year": 2020,
        "abstract": None,
        "source": None,
        "language": "en",
        "publisher": None,
        "research_areas": None,
        "is_seed": is_seed,
        "curation_status": curation_status,
        "provenance": None,
        "authors_raw": None,
        "authors_id": authors_id or ["AUTH_A", "AUTH_B"],
        "authors_affiliations": None,
        "keywords_raw": None,
        "keywords_id": keywords_id or ["KW_1"],
        "institutions_raw": None,
        "institutions_id": institutions_id or ["INST_1"],
        "references_id": references_id,
        "references_doi": None,
        "cited_by_id": cited_by_id,
    }


def _corpus_from_rows(rows: list[dict[str, Any]]) -> Corpus:
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    return Corpus.from_arrow(table)


def _store_with_corpus(tmp_path: Path, rows: list[dict[str, Any]]) -> Path:
    """Crea un DuckDBStore temporal con el corpus dado y retorna su ruta."""
    from bib2graph.stores.duckdb import DuckDBStore

    db_path = tmp_path / "test.duckdb"
    corpus = _corpus_from_rows(rows)
    store = DuckDBStore(db_path)
    store.persist(corpus)
    store.close()
    return db_path


# ---------------------------------------------------------------------------
# Mocks HTTP para DOI resolution y cited_by
# ---------------------------------------------------------------------------


def _make_doi_transport(ref_id_to_doi: dict[str, str]) -> httpx.MockTransport:
    """Transport que responde a ``openalex_id:`` con los DOIs dados."""

    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        results = []
        if "openalex_id" in url_str:
            for short_id, doi in ref_id_to_doi.items():
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


def _make_cited_by_transport(
    citing_works: list[dict[str, Any]],
) -> httpx.MockTransport:
    """Transport que responde a ``cites:`` con los works dados."""

    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "cites" in url_str:
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


def _make_counting_transport(
    doi_map: dict[str, str] | None = None,
    citing_works: list[dict[str, Any]] | None = None,
) -> tuple[httpx.MockTransport, dict[str, list[int]]]:
    """Transport que cuenta llamadas por tipo y devuelve datos mockeados."""
    doi_map = doi_map or {}
    citing_works = citing_works or []
    counters: dict[str, list[int]] = {"doi": [0], "citing": [0], "other": [0]}

    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "openalex_id" in url_str:
            counters["doi"][0] += 1
            results = [
                {"id": f"https://openalex.org/{k}", "doi": f"https://doi.org/{v}"}
                for k, v in doi_map.items()
                if k in url_str
            ]
            body: dict[str, Any] = {
                "results": results,
                "meta": {"count": len(results), "next_cursor": None},
            }
        elif "cites" in url_str:
            counters["citing"][0] += 1
            body = {
                "results": citing_works,
                "meta": {"count": len(citing_works), "next_cursor": None},
            }
        else:
            counters["other"][0] += 1
            body = {"results": [], "meta": {"count": 0, "next_cursor": None}}
        return httpx.Response(
            200,
            json=body,
            headers={"x-openalex-api-version": "2026-05-01"},
        )

    return httpx.MockTransport(handler), counters


def _citing_work(citer_oa_id: str, cites_ids: list[str]) -> dict[str, Any]:
    """Work de OpenAlex que cita los seeds dados."""
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


# ---------------------------------------------------------------------------
# 1. chain ejecuta la pasada refs→DOI automáticamente
# ---------------------------------------------------------------------------


def test_chain_resuelve_references_doi(tmp_path: Path) -> None:
    """``run_chain`` aplica la pasada refs→DOI sobre el corpus mergeado+dedup."""
    from bib2graph.cli.commands.chain import run_chain
    from bib2graph.stores.duckdb import DuckDBStore

    # Corpus con una semilla que tiene references_id pero references_doi vacío
    rows = [_row("P1", references_id=["W1111"], is_seed=True)]
    db_path = _store_with_corpus(tmp_path, rows)

    # Mock: W1111 → DOI 10.1000/test
    transport, counters = _make_counting_transport(doi_map={"W1111": "10.1000/test"})
    run_chain(db_path, direction="backward", transport=transport)

    # Verificar que references_doi se pobló
    store = DuckDBStore(db_path)
    corpus = store.load()
    table = corpus.to_arrow()  # leer ANTES de cerrar la conexión DuckDB
    store.close()
    refs_doi = table.column("references_doi").to_pylist()[0]

    assert refs_doi is not None, "references_doi debe estar poblado"
    assert "10.1000/test" in refs_doi, f"DOI esperado no encontrado: {refs_doi}"
    # Se hizo al menos una request de DOI resolution
    assert counters["doi"][0] >= 1, "Debe haber llamadas de resolución DOI"


def test_chain_data_tiene_bloque_enrichment(tmp_path: Path) -> None:
    """``run_chain`` retorna ``data['enrichment']`` con métricas de refs→DOI."""
    from bib2graph.cli.commands.chain import run_chain

    rows = [_row("P1", references_id=["W1111"], is_seed=True)]
    db_path = _store_with_corpus(tmp_path, rows)

    transport = _make_doi_transport({"W1111": "10.1000/test"})
    data = run_chain(db_path, direction="backward", transport=transport)

    assert "enrichment" in data, "data debe tener clave 'enrichment'"
    enrichment = data["enrichment"]
    assert isinstance(enrichment, dict), "enrichment debe ser un dict"
    assert "refs_resolved" in enrichment, "enrichment debe tener 'refs_resolved'"
    assert "refs_total_unique" in enrichment, (
        "enrichment debe tener 'refs_total_unique'"
    )
    assert enrichment["refs_resolved"] == 1
    assert enrichment["refs_total_unique"] == 1


def test_chain_sin_referencias_enrichment_cero(tmp_path: Path) -> None:
    """``run_chain`` con corpus sin referencias retorna enrichment con 0."""
    from bib2graph.cli.commands.chain import run_chain

    rows = [_row("P1", references_id=None)]
    db_path = _store_with_corpus(tmp_path, rows)

    transport, counters = _make_counting_transport()
    data = run_chain(db_path, direction="backward", transport=transport)

    assert data["enrichment"].get("refs_resolved", 0) == 0
    assert counters["doi"][0] == 0, "Sin referencias no debe hacer requests DOI"


# ---------------------------------------------------------------------------
# 2. build ejecuta la pasada cited_by cuando hay seeds aceptadas
# ---------------------------------------------------------------------------


def test_build_dispara_cited_by_con_seeds_aceptadas(tmp_path: Path) -> None:
    """``run_build`` corre cited_by y popula co-citación cuando hay seeds aceptadas."""
    from bib2graph.cli.commands.build import run_build

    # 2 seeds aceptadas con source_id
    rows = [
        _row(
            "P1",
            source_id="W100",
            is_seed=True,
            curation_status=CurationStatus.ACCEPTED,
        ),
        _row(
            "P2",
            source_id="W200",
            is_seed=True,
            curation_status=CurationStatus.ACCEPTED,
        ),
    ]
    db_path = _store_with_corpus(tmp_path, rows)
    out_dir = tmp_path / "networks"

    # Mock: C1 cita a W100 y W200 → co-citación
    citing = [_citing_work("C1", ["W100", "W200"])]
    transport, counters = _make_counting_transport(citing_works=citing)

    data = run_build(db_path, out_dir=out_dir, transport=transport)

    # Se hicieron requests de cited_by
    assert counters["citing"][0] >= 1, "Debe haber requests cited_by"
    # El enrichment block está presente
    assert "enrichment" in data
    assert data["enrichment"].get("citing_new", 0) >= 1
    assert data["enrichment"].get("citing_targets", 0) == 2


def test_build_co_citacion_en_redes_tras_cited_by(tmp_path: Path) -> None:
    """Tras la pasada cited_by en build, Networks.quick produce co-citación."""
    from bib2graph.cli.commands.build import run_build

    rows = [
        _row(
            "P1",
            source_id="W100",
            is_seed=True,
            curation_status=CurationStatus.ACCEPTED,
        ),
        _row(
            "P2",
            source_id="W200",
            is_seed=True,
            curation_status=CurationStatus.ACCEPTED,
        ),
    ]
    db_path = _store_with_corpus(tmp_path, rows)
    out_dir = tmp_path / "networks"

    citing = [_citing_work("C1", ["W100", "W200"])]
    transport = _make_cited_by_transport(citing)

    data = run_build(db_path, out_dir=out_dir, transport=transport)

    kinds = {n["kind"] for n in data["networks"]}
    assert "cocitation" in kinds, (
        f"Co-citación debe estar en redes tras cited_by. Redes: {kinds}"
    )
    assert data["networks_built"] == 5, (
        f"Deben ser 5 redes con co-citación. Fueron: {data['networks_built']}"
    )


# ---------------------------------------------------------------------------
# 3. build es no-op (sin requests) cuando no hay seeds aceptadas
# ---------------------------------------------------------------------------


def test_build_noop_sin_seeds_aceptadas(tmp_path: Path) -> None:
    """``run_build`` no hace requests cited_by cuando no hay seeds aceptadas."""
    from bib2graph.cli.commands.build import run_build

    # Solo candidatos — sin seeds aceptadas
    rows = [
        _row("P1", is_seed=True, curation_status=CurationStatus.CANDIDATE),
        _row("P2", is_seed=True, curation_status=CurationStatus.CANDIDATE),
    ]
    db_path = _store_with_corpus(tmp_path, rows)
    out_dir = tmp_path / "networks"

    transport, counters = _make_counting_transport()
    data = run_build(db_path, out_dir=out_dir, transport=transport)

    # Sin seeds aceptadas → 0 requests de cited_by
    assert counters["citing"][0] == 0, (
        f"Sin seeds aceptadas no debe hacer requests cited_by; "
        f"hizo {counters['citing'][0]}"
    )
    # El enrichment block existe pero está vacío
    assert "enrichment" in data
    assert data["enrichment"] == {}, (
        f"Sin seeds aceptadas, enrichment debe ser vacío: {data['enrichment']}"
    )


def test_build_4_redes_sin_seeds_aceptadas(tmp_path: Path) -> None:
    """Sin seeds aceptadas build produce 4 redes (sin co-citación) y exit 0."""
    from bib2graph.cli.commands.build import run_build

    rows = [
        _row(
            f"P{i}",
            is_seed=True,
            curation_status=CurationStatus.CANDIDATE,
            authors_id=[f"AUTH_{i}", "AUTH_SHARED"],
            keywords_id=[f"KW_{i}", "KW_SHARED"],
            institutions_id=[f"INST_{i}"],
            references_id=[f"REF_{i}", "REF_SHARED"],
        )
        for i in range(3)
    ]
    db_path = _store_with_corpus(tmp_path, rows)
    out_dir = tmp_path / "networks"

    transport, counters = _make_counting_transport()
    data = run_build(db_path, out_dir=out_dir, transport=transport)

    assert counters["citing"][0] == 0
    kinds = {n["kind"] for n in data["networks"]}
    assert "cocitation" not in kinds, "Sin cited_by_id no debe haber co-citación"
    # 4 redes base (bibliographic_coupling, coauthorship, cooccurrence, keyword)
    assert len(data["networks"]) == 4 or data["networks_built"] == 4, (
        f"Sin co-citación deben ser 4 redes; fueron {data['networks_built']}"
    )


# ---------------------------------------------------------------------------
# 4. enrich suelto sigue funcionando idéntico
# ---------------------------------------------------------------------------


def test_enrich_suelto_sigue_funcionando(tmp_path: Path) -> None:
    """``run_enrich`` (alias) delega en el helper y produce el mismo resultado."""
    from bib2graph.cli.commands.enrich import run_enrich

    rows = [
        _row(
            "P1",
            source_id="W100",
            is_seed=True,
            curation_status=CurationStatus.ACCEPTED,
            references_id=["W999"],
        )
    ]
    db_path = _store_with_corpus(tmp_path, rows)

    citing = [_citing_work("C1", ["W100"])]
    transport, _ = _make_counting_transport(
        doi_map={"W999": "10.1000/ref"},
        citing_works=citing,
    )

    data = run_enrich(db_path, transport=transport)

    # Claves estables del contrato original
    assert "refs_resolved" in data
    assert "refs_total_unique" in data
    assert "citing_new" in data
    assert "citing_targets" in data
    assert "total_papers" in data
    assert isinstance(data["refs_resolved"], int)
    assert isinstance(data["total_papers"], int)


def test_enrich_suelto_claves_numericas(tmp_path: Path) -> None:
    """``run_enrich`` retorna exactamente las 5 claves requeridas (contrato original)."""
    from bib2graph.cli.commands.enrich import run_enrich
    from bib2graph.stores.duckdb import DuckDBStore

    rows = [_row("P1", references_id=["W111"])]
    db_path = tmp_path / "e.duckdb"
    store = DuckDBStore(db_path)
    store.persist(_corpus_from_rows(rows))
    store.close()

    transport = _make_doi_transport({"W111": "10.1000/xyz"})
    data = run_enrich(db_path, transport=transport)

    required = {
        "refs_resolved",
        "refs_total_unique",
        "citing_new",
        "citing_targets",
        "total_papers",
    }
    assert required.issubset(data.keys()), (
        f"Faltan claves en data: {required - set(data.keys())}"
    )
    assert data["total_papers"] == 1
    assert data["refs_resolved"] == 1
    assert data["refs_total_unique"] == 1
    assert data["citing_new"] == 0  # sin seeds aceptadas → 0
    assert data["citing_targets"] == 0


# ---------------------------------------------------------------------------
# 5. data["enrichment"] es aditivo y no rompe schema="1"
# ---------------------------------------------------------------------------


def test_chain_enrichment_no_rompe_schema(tmp_path: Path) -> None:
    """``data['enrichment']`` es un dict plano y no cambia el envelope schema."""
    from bib2graph.cli._envelope import build_envelope
    from bib2graph.cli.commands.chain import run_chain

    rows = [_row("P1", references_id=["W1111"])]
    db_path = _store_with_corpus(tmp_path, rows)

    transport = _make_doi_transport({"W1111": "10.1000/test"})
    data = run_chain(db_path, direction="backward", transport=transport)

    envelope = build_envelope(command="chain", ok=True, data=data, exit_code=0)
    assert envelope["schema"] == "1", f"schema debe ser '1', es '{envelope['schema']}'"
    assert isinstance(data["enrichment"], dict)


def test_build_enrichment_no_rompe_schema(tmp_path: Path) -> None:
    """``data['enrichment']`` en build es un dict plano; schema='1' intacto."""
    from bib2graph.cli._envelope import build_envelope
    from bib2graph.cli.commands.build import run_build

    rows = [_row("P1", is_seed=True, curation_status=CurationStatus.CANDIDATE)]
    db_path = _store_with_corpus(tmp_path, rows)
    out_dir = tmp_path / "networks"

    transport, _ = _make_counting_transport()
    data = run_build(db_path, out_dir=out_dir, transport=transport)

    envelope = build_envelope(command="build", ok=True, data=data, exit_code=0)
    assert envelope["schema"] == "1"
    assert "enrichment" in data
    assert isinstance(data["enrichment"], dict)


# ---------------------------------------------------------------------------
# 6. Helper enrich_corpus: pass_name inválido → ValueError
# ---------------------------------------------------------------------------


def test_enrich_corpus_pass_name_invalido() -> None:
    """``enrich_corpus`` con ``pass_name`` desconocido lanza ``ValueError``."""
    from bib2graph.cli._enrich import enrich_corpus
    from bib2graph.sources.openalex import OpenAlexSource

    corpus = _corpus_from_rows([_row("P1")])
    source = OpenAlexSource()

    with pytest.raises(ValueError, match="pass_name desconocido"):
        enrich_corpus(corpus, source, pass_name="invalid_pass")


# ---------------------------------------------------------------------------
# 7. Helper enrich_corpus: métricas correctas por pasada
# ---------------------------------------------------------------------------


def test_enrich_corpus_refs_doi_solo() -> None:
    """``enrich_corpus(pass_name='refs_doi')`` retorna métricas de refs→DOI."""
    from bib2graph.cli._enrich import enrich_corpus
    from bib2graph.sources.openalex import OpenAlexSource

    corpus = _corpus_from_rows([_row("P1", references_id=["W111"])])
    transport = _make_doi_transport({"W111": "10.1000/x"})
    source = OpenAlexSource(transport=transport)

    enriched, metrics = enrich_corpus(corpus, source, pass_name="refs_doi")

    assert "refs_resolved" in metrics
    assert "refs_total_unique" in metrics
    # cited_by keys no deben estar si no se ejecutó esa pasada
    assert "citing_new" not in metrics
    assert "citing_targets" not in metrics
    # Corpus gana el DOI
    refs_doi = enriched.to_arrow().column("references_doi").to_pylist()[0]
    assert refs_doi is not None
    assert "10.1000/x" in refs_doi


def test_enrich_corpus_cited_by_solo() -> None:
    """``enrich_corpus(pass_name='cited_by')`` retorna métricas de cited_by."""
    from bib2graph.cli._enrich import enrich_corpus
    from bib2graph.sources.openalex import OpenAlexSource

    corpus = _corpus_from_rows(
        [_row("P1", source_id="W100", curation_status=CurationStatus.ACCEPTED)]
    )
    citing = [_citing_work("C1", ["W100"])]
    transport = _make_cited_by_transport(citing)
    source = OpenAlexSource(transport=transport)

    enriched, metrics = enrich_corpus(corpus, source, pass_name="cited_by")

    assert "citing_new" in metrics
    assert "citing_targets" in metrics
    # refs_doi keys no deben estar si no se ejecutó esa pasada
    assert "refs_resolved" not in metrics
    # Corpus gana el citante
    cited_by = enriched.to_arrow().column("cited_by_id").to_pylist()[0]
    assert cited_by is not None
    assert "C1" in cited_by


def test_enrich_corpus_both_tiene_todas_las_claves() -> None:
    """``enrich_corpus(pass_name='both')`` retorna todas las métricas."""
    from bib2graph.cli._enrich import enrich_corpus
    from bib2graph.sources.openalex import OpenAlexSource

    corpus = _corpus_from_rows(
        [
            _row(
                "P1",
                source_id="W100",
                curation_status=CurationStatus.ACCEPTED,
                references_id=["W999"],
            )
        ]
    )
    citing = [_citing_work("C1", ["W100"])]
    transport, _ = _make_counting_transport(
        doi_map={"W999": "10.1000/ref"}, citing_works=citing
    )
    source = OpenAlexSource(transport=transport)

    _enriched, metrics = enrich_corpus(corpus, source, pass_name="both")

    assert "refs_resolved" in metrics
    assert "refs_total_unique" in metrics
    assert "citing_new" in metrics
    assert "citing_targets" in metrics


# ---------------------------------------------------------------------------
# 8. build: max_citing controla el tope de citantes por seed
# ---------------------------------------------------------------------------


def test_build_max_citing_limita_citantes(tmp_path: Path) -> None:
    """``run_build(max_citing=1)`` limita cited_by_id a 1 citante por seed."""
    from bib2graph.cli.commands.build import run_build
    from bib2graph.stores.duckdb import DuckDBStore

    rows = [
        _row(
            "P1",
            source_id="W100",
            is_seed=True,
            curation_status=CurationStatus.ACCEPTED,
        )
    ]
    db_path = _store_with_corpus(tmp_path, rows)
    out_dir = tmp_path / "networks"

    # 5 citantes de W100
    citing = [_citing_work(f"C{i}", ["W100"]) for i in range(1, 6)]
    transport = _make_cited_by_transport(citing)

    run_build(db_path, out_dir=out_dir, transport=transport, max_citing=1)

    # Verificar que cited_by_id tiene ≤ 1 elemento
    store = DuckDBStore(db_path)
    corpus = store.load()
    rows_out = corpus.to_arrow().to_pylist()  # leer ANTES de cerrar
    store.close()
    p1 = next(r for r in rows_out if r["id"] == "P1")
    cited = p1.get("cited_by_id") or []
    assert len(cited) <= 1, f"max_citing=1 debe limitar a ≤1 citante; hay {len(cited)}"
