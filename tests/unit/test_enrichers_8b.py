"""Tests unitarios del Hito 8b — co-citación end-to-end.

Todos los tests de red usan ``httpx.MockTransport`` (sin red real en CI).

Casos cubiertos:
1. Co-citación end-to-end: 2 seeds aceptados + 1 citante compartido →
   ``cited_by_id`` poblado en ambos → ``CoCitationProjector`` / ``Networks.quick``
   produce ≥1 arista con peso correcto.
2. Re-atribución con batch OR: citantes que citan a distintos seeds → cada
   ``cited_by_id`` recibe solo los citantes correctos.
3. Idempotencia: re-enrich no duplica en ``cited_by_id``.
4. Tope ``max_citing_per_paper`` respetado.
5. Alcance: papers NO-seed o no-aceptados NO se enriquecen.
6. ``Networks.quick`` sin ``cited_by_id`` → 4 redes, sin fallo (regresión).
7. ``Networks.quick`` con ``cited_by_id`` → 5 redes, incluyendo co-citación.
8. No pierde papers; corpus sin seeds aceptados → 0 fetch, sin error.
9. ``fetch_citing_batch`` en lotes ≤50: 3 seeds → 1 sola request por lote.
10. Co-citación no afecta papers sin openalex_id.
11. Presupuesto por semilla (anti-starvation): semilla muy citada no roba cupo.
12. El tope acota el fetch: se deja de paginar cuando todas las semillas alcanzan tope.
13. Sin tope (None): pagina todo y atribuye correctamente.
"""

from __future__ import annotations

from typing import Any

import httpx
import pyarrow as pa
import pytest

from bib2graph.constants import CurationStatus
from bib2graph.corpus import Corpus
from bib2graph.networks.facade import Networks
from bib2graph.networks.projectors import CoCitationProjector
from bib2graph.schemas import CORPUS_SCHEMA

# ---------------------------------------------------------------------------
# Helpers de filas mínimas
# ---------------------------------------------------------------------------


def _make_row(
    *,
    id: str,
    source_id: str | None = None,
    is_seed: bool = True,
    curation_status: str = CurationStatus.ACCEPTED,
    references_id: list[str] | None = None,
    cited_by_id: list[str] | None = None,
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
        "authors_id": None,
        "authors_affiliations": None,
        "keywords_raw": None,
        "keywords_id": None,
        "institutions_raw": None,
        "institutions_id": None,
        "references_id": references_id,
        "references_doi": None,
        "cited_by_id": cited_by_id,
    }


def _corpus_from_rows(rows: list[dict[str, Any]]) -> Corpus:
    """Construye un Corpus Arrow desde una lista de dicts."""
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    return Corpus.from_arrow(table)


# ---------------------------------------------------------------------------
# Helpers de MockTransport para cited_by
# ---------------------------------------------------------------------------


def _citing_work(
    citer_oa_id: str,
    cites_ids: list[str],
) -> dict[str, Any]:
    """Construye un objeto Work de OpenAlex que representa un citante.

    El citante ``citer_oa_id`` tiene en su ``referenced_works`` los IDs
    ``cites_ids`` (los papers que él cita = los seeds en el corpus).
    """
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
    """MockTransport que responde a consultas ``cites:`` devolviendo works dados.

    Ignora el filtro exacto y devuelve siempre la lista completa (el Enricher
    se encarga de la re-atribución cruzando ``references_id`` del citante).
    También responde 200 vacío a las consultas ``openalex_id:`` (pasada DOI).
    """

    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        # Pasada 1 (references_doi): consultas openalex_id → sin DOIs (vacío)
        if "openalex_id" in url_str:
            body = {"results": [], "meta": {"count": 0, "next_cursor": None}}
        # Pasada 2 (cited_by): consultas cites: → devolver citantes
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


def _make_counting_cited_by_transport(
    citing_works: list[dict[str, Any]],
) -> tuple[httpx.MockTransport, dict[str, list[int]]]:
    """MockTransport que cuenta requests por tipo (openalex_id y cites).

    Returns:
        Tupla ``(transport, counters)`` donde ``counters`` es un dict con
        claves ``"doi"`` y ``"citing"``, cada una con una lista de un entero.
    """
    counters: dict[str, list[int]] = {"doi": [0], "citing": [0]}

    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "openalex_id" in url_str:
            counters["doi"][0] += 1
            body = {"results": [], "meta": {"count": 0, "next_cursor": None}}
        elif "cites" in url_str:
            counters["citing"][0] += 1
            body = {
                "results": citing_works,
                "meta": {"count": len(citing_works), "next_cursor": None},
            }
        else:
            body = {"results": [], "meta": {"count": 0, "next_cursor": None}}
        return httpx.Response(200, json=body)

    return httpx.MockTransport(handler), counters


def _make_enricher(
    transport: httpx.BaseTransport,
    max_citing_per_paper: int | None = None,
) -> Any:
    """Construye un OpenAlexEnricher con transport inyectado."""
    from bib2graph.enrichers.openalex import OpenAlexEnricher
    from bib2graph.sources.openalex import OpenAlexSource

    source = OpenAlexSource(email="test@example.com", transport=transport)
    return OpenAlexEnricher(source, max_citing_per_paper=max_citing_per_paper)


# ---------------------------------------------------------------------------
# 1. Co-citación end-to-end
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_cocitacion_end_to_end_cited_by_poblado() -> None:
    """2 seeds aceptados + 1 citante compartido → cited_by_id poblado en ambos."""
    # Seeds: W100 y W200, ambas aceptadas
    corpus = _corpus_from_rows(
        [
            _make_row(id="P1", source_id="W100"),
            _make_row(id="P2", source_id="W200"),
        ]
    )
    # Citante C1 cita a W100 y W200
    citing_works = [_citing_work("C1", ["W100", "W200"])]
    transport = _make_cited_by_transport(citing_works)

    enricher = _make_enricher(transport)
    result = enricher.enrich(corpus)

    table = result.to_arrow()
    rows = table.to_pylist()
    cited_by_map = {row["source_id"]: row.get("cited_by_id") or [] for row in rows}

    assert "C1" in cited_by_map["W100"], "W100 debe tener C1 como citante"
    assert "C1" in cited_by_map["W200"], "W200 debe tener C1 como citante"


@pytest.mark.unit
def test_cocitacion_end_to_end_proyector_produce_arista() -> None:
    """Tras enrich, CoCitationProjector produce ≥1 arista con peso correcto."""
    corpus = _corpus_from_rows(
        [
            _make_row(id="P1", source_id="W100"),
            _make_row(id="P2", source_id="W200"),
        ]
    )
    # C1 cita ambos → 1 arista de co-citación peso 1
    citing_works = [_citing_work("C1", ["W100", "W200"])]
    transport = _make_cited_by_transport(citing_works)

    enricher = _make_enricher(transport)
    result = enricher.enrich(corpus)

    projector = CoCitationProjector()
    g = projector.project(result.to_arrow())

    assert g.number_of_edges() >= 1, "CoCitationProjector debe producir ≥1 arista"
    edges = list(g.edges(data=True))
    assert edges[0][2]["weight"] == 1, "Peso debe ser 1 (un citante compartido)"


@pytest.mark.unit
def test_cocitacion_end_to_end_networks_quick_incluye_red() -> None:
    """Networks.quick incluye co-citación cuando hay cited_by_id poblado."""
    corpus = _corpus_from_rows(
        [
            _make_row(id="P1", source_id="W100"),
            _make_row(id="P2", source_id="W200"),
        ]
    )
    citing_works = [_citing_work("C1", ["W100", "W200"])]
    transport = _make_cited_by_transport(citing_works)

    enricher = _make_enricher(transport)
    result = enricher.enrich(corpus)

    artifacts = Networks.quick(result)
    kinds = {a.spec.kind for a in artifacts}

    assert "cocitation" in kinds, "Networks.quick debe incluir co-citación"
    assert len(artifacts) == 5, "Debe haber 5 redes (4 base + co-citación)"


# ---------------------------------------------------------------------------
# 2. Re-atribución con batch OR
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_reatribucion_citantes_distintos_seeds() -> None:
    """Citantes que citan a distintos seeds → cited_by_id correcto por seed."""
    corpus = _corpus_from_rows(
        [
            _make_row(id="P1", source_id="W100"),
            _make_row(id="P2", source_id="W200"),
        ]
    )
    # C1 cita solo W100; C2 cita solo W200; C3 cita ambos
    citing_works = [
        _citing_work("C1", ["W100"]),
        _citing_work("C2", ["W200"]),
        _citing_work("C3", ["W100", "W200"]),
    ]
    transport = _make_cited_by_transport(citing_works)

    enricher = _make_enricher(transport)
    result = enricher.enrich(corpus)

    table = result.to_arrow()
    rows = table.to_pylist()
    cited_by_map = {row["source_id"]: set(row.get("cited_by_id") or []) for row in rows}

    # W100 debe tener C1 y C3 (no C2)
    assert cited_by_map["W100"] == {"C1", "C3"}, (
        f"W100 debe tener {{C1, C3}}, tiene {cited_by_map['W100']}"
    )
    # W200 debe tener C2 y C3 (no C1)
    assert cited_by_map["W200"] == {"C2", "C3"}, (
        f"W200 debe tener {{C2, C3}}, tiene {cited_by_map['W200']}"
    )


@pytest.mark.unit
def test_reatribucion_citante_sin_referencias_no_se_asigna() -> None:
    """Un citante sin references_id no contamina ningún cited_by_id."""
    corpus = _corpus_from_rows([_make_row(id="P1", source_id="W100")])
    # C_empty no tiene referenced_works → no cita a nadie
    citing_works = [_citing_work("C_empty", [])]
    transport = _make_cited_by_transport(citing_works)

    enricher = _make_enricher(transport)
    result = enricher.enrich(corpus)

    table = result.to_arrow()
    rows_data = table.to_pylist()
    cited_by = rows_data[0].get("cited_by_id") or []
    assert cited_by == [] or "C_empty" not in cited_by


# ---------------------------------------------------------------------------
# 3. Idempotencia
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_enrich_cited_by_idempotente() -> None:
    """Re-enrich no duplica en cited_by_id."""
    corpus = _corpus_from_rows([_make_row(id="P1", source_id="W100")])
    citing_works = [_citing_work("C1", ["W100"])]
    transport = _make_cited_by_transport(citing_works)

    enricher = _make_enricher(transport)
    once = enricher.enrich(corpus)
    twice = enricher.enrich(once)

    table = twice.to_arrow()
    rows_data = table.to_pylist()
    cited_by = rows_data[0].get("cited_by_id") or []

    # No duplicados
    assert len(cited_by) == len(set(cited_by)), "cited_by_id no debe tener duplicados"
    assert "C1" in cited_by


@pytest.mark.unit
def test_enrich_cited_by_enricher_ref_no_duplica() -> None:
    """El EnricherRef 'openalex_cited_by' no se duplica al re-enriquecer."""
    corpus = _corpus_from_rows([_make_row(id="P1", source_id="W100")])
    citing_works = [_citing_work("C1", ["W100"])]
    transport = _make_cited_by_transport(citing_works)

    enricher = _make_enricher(transport)
    once = enricher.enrich(corpus)
    twice = enricher.enrich(once)

    names = [e.name for e in twice.manifest.enrichers]
    assert names.count("openalex_cited_by") == 1


# ---------------------------------------------------------------------------
# 4. Tope max_citing_per_paper
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_tope_max_citing_per_paper() -> None:
    """max_citing_per_paper=2 trunca cited_by_id a 2 citantes por paper."""
    corpus = _corpus_from_rows([_make_row(id="P1", source_id="W100")])
    # 5 citantes que citan a W100
    citing_works = [_citing_work(f"C{i}", ["W100"]) for i in range(1, 6)]
    transport = _make_cited_by_transport(citing_works)

    enricher = _make_enricher(transport, max_citing_per_paper=2)
    result = enricher.enrich(corpus)

    table = result.to_arrow()
    rows_data = table.to_pylist()
    cited_by = rows_data[0].get("cited_by_id") or []
    assert len(cited_by) <= 2, f"Debe haber ≤2 citantes, hay {len(cited_by)}"


@pytest.mark.unit
def test_tope_none_no_trunca() -> None:
    """max_citing_per_paper=None no trunca (devuelve todos los citantes)."""
    corpus = _corpus_from_rows([_make_row(id="P1", source_id="W100")])
    # 10 citantes
    citing_works = [_citing_work(f"C{i}", ["W100"]) for i in range(1, 11)]
    transport = _make_cited_by_transport(citing_works)

    enricher = _make_enricher(transport, max_citing_per_paper=None)
    result = enricher.enrich(corpus)

    table = result.to_arrow()
    rows_data = table.to_pylist()
    cited_by = rows_data[0].get("cited_by_id") or []
    assert len(cited_by) == 10


# ---------------------------------------------------------------------------
# 5. Alcance: NO-seed y no-aceptados no se enriquecen
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_no_seed_no_se_enriquece() -> None:
    """Papers con is_seed=False no se incluyen como objetivo de cited_by_id."""
    corpus = _corpus_from_rows(
        [
            _make_row(id="P1", source_id="W100"),  # seed + accepted
            _make_row(
                id="P2",
                source_id="W200",
                is_seed=False,
                curation_status=CurationStatus.ACCEPTED,
            ),  # NO seed
        ]
    )
    citing_works = [_citing_work("C1", ["W100", "W200"])]
    transport = _make_cited_by_transport(citing_works)

    enricher = _make_enricher(transport)
    result = enricher.enrich(corpus)

    table = result.to_arrow()
    rows_data = table.to_pylist()
    cited_by_map = {
        row["source_id"]: set(row.get("cited_by_id") or []) for row in rows_data
    }

    # W100 (seed aceptada) debe tener C1
    assert "C1" in cited_by_map["W100"]
    # W200 (NO seed) no debe tener C1 en cited_by_id (no fue objetivo del fetch)
    assert "C1" not in cited_by_map.get("W200", set())


@pytest.mark.unit
def test_candidato_no_se_enriquece() -> None:
    """Papers con curation_status=candidate no se incluyen como objetivo."""
    corpus = _corpus_from_rows(
        [
            _make_row(id="P1", source_id="W100"),  # seed + accepted
            _make_row(
                id="P2",
                source_id="W200",
                curation_status=CurationStatus.CANDIDATE,
            ),  # candidato
        ]
    )
    citing_works = [_citing_work("C1", ["W100", "W200"])]
    transport = _make_cited_by_transport(citing_works)

    enricher = _make_enricher(transport)
    result = enricher.enrich(corpus)

    table = result.to_arrow()
    rows_data = table.to_pylist()
    cited_by_map = {
        row["source_id"]: set(row.get("cited_by_id") or []) for row in rows_data
    }

    # W100 (aceptada) sí
    assert "C1" in cited_by_map["W100"]
    # W200 (candidata) no recibe citantes vía el enrich (no fue objetivo)
    assert "C1" not in cited_by_map.get("W200", set())


# ---------------------------------------------------------------------------
# 6. Networks.quick sin cited_by_id → 4 redes, sin fallo (regresión)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_networks_quick_sin_cited_by_omite_cocitacion_sin_fallar() -> None:
    """Networks.quick con cited_by_id vacío → 4 redes, sin error."""
    rows = [
        {
            "id": f"P{i}",
            "source_id": None,
            "doi": None,
            "title": f"Paper {i}",
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
            "authors_id": [f"AUTH_{i}", "AUTH_0"],
            "authors_affiliations": None,
            "keywords_raw": None,
            "keywords_id": [f"KW_{i}", "KW_SHARED"],
            "institutions_raw": None,
            "institutions_id": [f"INST_{i}"],
            "references_id": [f"REF_{i}", "REF_SHARED"],
            "references_doi": None,
            "cited_by_id": None,  # sin citantes
        }
        for i in range(3)
    ]
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)

    # No debe lanzar excepción
    artifacts = Networks.quick(corpus)

    assert len(artifacts) == 4, "Sin cited_by_id debe haber exactamente 4 redes"
    kinds = {a.spec.kind for a in artifacts}
    assert "cocitation" not in kinds


# ---------------------------------------------------------------------------
# 7. Networks.quick con cited_by_id → 5 redes
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_networks_quick_con_cited_by_incluye_cocitacion() -> None:
    """Networks.quick con cited_by_id poblado → 5 redes, incluyendo cocitation."""
    rows = [
        {
            "id": "P1",
            "source_id": "W100",
            "doi": None,
            "title": "Paper 1",
            "year": 2020,
            "abstract": None,
            "source": None,
            "language": None,
            "publisher": None,
            "research_areas": None,
            "is_seed": True,
            "curation_status": "accepted",
            "provenance": None,
            "authors_raw": None,
            "authors_id": ["AUTH_1"],
            "authors_affiliations": None,
            "keywords_raw": None,
            "keywords_id": ["KW_1"],
            "institutions_raw": None,
            "institutions_id": ["INST_1"],
            "references_id": None,
            "references_doi": None,
            "cited_by_id": ["C1"],  # ya tiene citante
        },
        {
            "id": "P2",
            "source_id": "W200",
            "doi": None,
            "title": "Paper 2",
            "year": 2020,
            "abstract": None,
            "source": None,
            "language": None,
            "publisher": None,
            "research_areas": None,
            "is_seed": True,
            "curation_status": "accepted",
            "provenance": None,
            "authors_raw": None,
            "authors_id": ["AUTH_2"],
            "authors_affiliations": None,
            "keywords_raw": None,
            "keywords_id": ["KW_2"],
            "institutions_raw": None,
            "institutions_id": ["INST_2"],
            "references_id": None,
            "references_doi": None,
            "cited_by_id": ["C1"],  # mismo citante → co-cita P1 y P2
        },
    ]
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)

    artifacts = Networks.quick(corpus)
    kinds = {a.spec.kind for a in artifacts}

    assert "cocitation" in kinds
    assert len(artifacts) == 5


# ---------------------------------------------------------------------------
# 8. No pierde papers; corpus sin seeds aceptados → 0 fetch, sin error
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_corpus_sin_seeds_aceptados_0_fetch() -> None:
    """Corpus sin seeds aceptados → 0 requests a cited_by, sin error."""
    corpus = _corpus_from_rows(
        [
            _make_row(
                id="P1",
                source_id="W100",
                curation_status=CurationStatus.CANDIDATE,
            ),
            _make_row(
                id="P2",
                source_id="W200",
                is_seed=False,
                curation_status=CurationStatus.ACCEPTED,
            ),
        ]
    )

    transport, counters = _make_counting_cited_by_transport([])
    enricher = _make_enricher(transport)
    result = enricher.enrich(corpus)

    # No se hicieron requests de cited_by (ninguna seed aceptada)
    assert counters["citing"][0] == 0, (
        "Sin seeds aceptadas no debe hacer requests citing"
    )
    # No pierde papers
    assert len(result) == len(corpus)


@pytest.mark.unit
def test_enrich_no_pierde_papers_con_semillas() -> None:
    """El corpus enriquecido tiene exactamente los mismos papers que el original."""
    corpus = _corpus_from_rows(
        [
            _make_row(id="P1", source_id="W100"),
            _make_row(
                id="P2",
                source_id="W200",
                curation_status=CurationStatus.CANDIDATE,
            ),
            _make_row(id="P3", source_id=None),
        ]
    )
    citing_works = [_citing_work("C1", ["W100"])]
    transport = _make_cited_by_transport(citing_works)

    enricher = _make_enricher(transport)
    result = enricher.enrich(corpus)

    assert len(result) == len(corpus), "No debe perder ni agregar papers"


# ---------------------------------------------------------------------------
# 9. fetch_citing_batch en lotes ≤50
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_fetch_citing_batch_loteo_50_ids() -> None:
    """Con 60 seeds aceptadas, fetch_citing_batch hace ≥2 requests (lotes ≤50)."""
    n = 60
    rows = [_make_row(id=f"P{i}", source_id=f"W{i:06d}") for i in range(1, n + 1)]
    corpus = _corpus_from_rows(rows)

    transport, counters = _make_counting_cited_by_transport([])
    enricher = _make_enricher(transport)
    enricher.enrich(corpus)

    # Con 60 seeds y lotes ≤50 → ≥2 requests de cites
    assert counters["citing"][0] >= 2, (
        f"Con {n} seeds debe hacer ≥2 requests (lotes ≤50), "
        f"hizo {counters['citing'][0]}"
    )


@pytest.mark.unit
def test_fetch_citing_batch_50_ids_exactos() -> None:
    """Con 50 seeds exactas, fetch_citing_batch hace 1 sola request."""
    n = 50
    rows = [_make_row(id=f"P{i}", source_id=f"W{i:06d}") for i in range(1, n + 1)]
    corpus = _corpus_from_rows(rows)

    transport, counters = _make_counting_cited_by_transport([])
    enricher = _make_enricher(transport)
    enricher.enrich(corpus)

    assert counters["citing"][0] == 1, (
        f"Con {n} seeds exactas debe hacer 1 request, hizo {counters['citing'][0]}"
    )


# ---------------------------------------------------------------------------
# 10. Papers sin openalex_id no se usan como objetivo
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_papers_sin_openalex_id_no_son_objetivo() -> None:
    """Seeds aceptadas sin openalex_id no disparan fetch_citing."""
    # Todas sin openalex_id → no hay targets válidos
    corpus = _corpus_from_rows(
        [
            _make_row(id="P1", source_id=None),
            _make_row(id="P2", source_id=None),
        ]
    )

    transport, counters = _make_counting_cited_by_transport([])
    enricher = _make_enricher(transport)
    result = enricher.enrich(corpus)

    assert counters["citing"][0] == 0
    assert len(result) == 2  # no pierde papers


# ---------------------------------------------------------------------------
# 11. run_enrich expone claves citing_new y citing_targets
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_run_enrich_8b_claves_en_salida(tmp_path: Any) -> None:
    """``run_enrich`` devuelve las nuevas claves citing_new y citing_targets."""
    from bib2graph.cli.commands.enrich import run_enrich
    from bib2graph.stores.duckdb import DuckDBStore

    rows = [_make_row(id="P1", source_id="W100")]
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)
    store = DuckDBStore(tmp_path / "test.duckdb")
    store.persist(corpus)

    citing_works = [_citing_work("C1", ["W100"])]
    transport = _make_cited_by_transport(citing_works)

    data = run_enrich(tmp_path / "test.duckdb", transport=transport)

    assert "citing_new" in data, "Debe incluir clave citing_new"
    assert "citing_targets" in data, "Debe incluir clave citing_targets"
    assert isinstance(data["citing_new"], int)
    assert isinstance(data["citing_targets"], int)
    assert data["citing_targets"] == 1  # 1 seed aceptada
    assert data["citing_new"] == 1  # 1 nuevo citante


# ---------------------------------------------------------------------------
# 12. EnricherRef openalex_cited_by en Manifest
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_enricher_ref_cited_by_en_manifest() -> None:
    """Tras enrich, el Manifest tiene EnricherRef 'openalex_cited_by'."""
    corpus = _corpus_from_rows([_make_row(id="P1", source_id="W100")])
    citing_works = [_citing_work("C1", ["W100"])]
    transport = _make_cited_by_transport(citing_works)

    enricher = _make_enricher(transport)
    result = enricher.enrich(corpus)

    names = [e.name for e in result.manifest.enrichers]
    assert "openalex_cited_by" in names
    assert "openalex_references_doi" in names


# ---------------------------------------------------------------------------
# Helpers para tests de presupuesto por semilla (multi-página con cursor)
# ---------------------------------------------------------------------------


def _make_paginated_cited_by_transport(
    pages: list[list[dict[str, Any]]],
) -> tuple[httpx.MockTransport, dict[str, list[int]]]:
    """MockTransport multi-página que simula paginación por cursor para cites:.

    ``pages[0]`` es la primera página, ``pages[1]`` la segunda, etc.
    Cada request que llega con un cursor distinto de ``"*"`` avanza al
    siguiente índice de páginas.  El cursor devuelto es ``"cursor_N"``
    donde N es el índice de la siguiente página, o ``None`` si no hay más.

    Returns:
        Tupla ``(transport, counters)`` donde ``counters["citing"]`` acumula
        el número de requests con ``cites`` en la URL (= número de páginas
        fetcheadas).
    """
    counters: dict[str, list[int]] = {"doi": [0], "citing": [0]}

    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "openalex_id" in url_str:
            counters["doi"][0] += 1
            body: dict[str, Any] = {
                "results": [],
                "meta": {"count": 0, "next_cursor": None},
            }
            return httpx.Response(200, json=body)

        if "cites" not in url_str:
            return httpx.Response(
                200, json={"results": [], "meta": {"count": 0, "next_cursor": None}}
            )

        counters["citing"][0] += 1

        # Determinar qué página devolver según el cursor de la request
        params = dict(request.url.params)
        cursor_val = params.get("cursor", "*")
        if cursor_val == "*":
            page_idx = 0
        elif cursor_val.startswith("cursor_"):
            page_idx = int(cursor_val.split("_")[1])
        else:
            page_idx = 0

        if page_idx >= len(pages):
            # Sin más páginas
            return httpx.Response(
                200,
                json={"results": [], "meta": {"count": 0, "next_cursor": None}},
            )

        works = pages[page_idx]
        next_idx = page_idx + 1
        next_cursor = f"cursor_{next_idx}" if next_idx < len(pages) else None

        body = {
            "results": works,
            "meta": {"count": len(works), "next_cursor": next_cursor},
        }
        return httpx.Response(
            200,
            json=body,
            headers={"x-openalex-api-version": "2026-05-01"},
        )

    return httpx.MockTransport(handler), counters


# ---------------------------------------------------------------------------
# 11. Presupuesto por semilla SIN starvation
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_presupuesto_por_semilla_sin_starvation() -> None:
    """Semilla con muchos citantes no consume el presupuesto de la otra.

    Escenario:
    - W100: muy citada → tiene citantes C1..C10 en páginas 1 y 2
    - W200: poco citada → solo tiene citante C11
    - max_citing_per_paper=3

    W100 debe tener ≤3 citantes.  W200 debe tener su citante C11 aunque
    W100 ya había consumido capacidad en páginas anteriores.
    """
    # Página 1: C1..C5 citan W100; C11 cita W200
    page1 = [_citing_work(f"C{i}", ["W100"]) for i in range(1, 6)] + [
        _citing_work("C11", ["W200"])
    ]
    # Página 2: C6..C10 citan W100 (solo W100 sigue sin tope en page1 parcialmente)
    page2 = [_citing_work(f"C{i}", ["W100"]) for i in range(6, 11)]

    transport, _counters = _make_paginated_cited_by_transport([page1, page2])

    corpus = _corpus_from_rows(
        [
            _make_row(id="P1", source_id="W100"),
            _make_row(id="P2", source_id="W200"),
        ]
    )
    enricher = _make_enricher(transport, max_citing_per_paper=3)
    result = enricher.enrich(corpus)

    table = result.to_arrow()
    rows = table.to_pylist()
    cited_by_map = {row["source_id"]: set(row.get("cited_by_id") or []) for row in rows}

    # W100 no debe superar el tope
    assert len(cited_by_map["W100"]) <= 3, (
        f"W100 no debe superar max=3, tiene {len(cited_by_map['W100'])}"
    )
    # W200 debe tener su citante C11 (no starved)
    assert "C11" in cited_by_map["W200"], (
        "W200 debe tener C11 aunque W100 tenga muchos citantes"
    )


# ---------------------------------------------------------------------------
# 12. El tope acota el fetch: se deja de paginar cuando todas las semillas
#     del lote están satisfechas
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_tope_detiene_paginacion_cuando_todas_satisfechas() -> None:
    """Con max_citing_per_paper=1, se detiene antes de la página 2 si ya satisfecho.

    Escenario:
    - 1 semilla W100, max_citing_per_paper=1
    - Página 1: C1 cita W100 (→ W100 satisfecha tras página 1)
    - Página 2: C2 cita W100 (nunca debe fetchearse)

    Se espera que el número de páginas fetcheadas sea 1 (no 2).
    """
    page1 = [_citing_work("C1", ["W100"])]
    page2 = [_citing_work("C2", ["W100"])]

    transport, counters = _make_paginated_cited_by_transport([page1, page2])

    corpus = _corpus_from_rows([_make_row(id="P1", source_id="W100")])
    enricher = _make_enricher(transport, max_citing_per_paper=1)
    result = enricher.enrich(corpus)

    # Solo debe haberse hecho 1 request de cites (página 1; página 2 no debe fetchearse)
    assert counters["citing"][0] == 1, (
        f"Con max=1 y 1 semilla satisfecha en página 1, "
        f"no debe fetchear página 2; hizo {counters['citing'][0]} requests"
    )

    table = result.to_arrow()
    rows = table.to_pylist()
    cited_by = rows[0].get("cited_by_id") or []
    assert len(cited_by) == 1
    assert "C1" in cited_by


@pytest.mark.unit
def test_tope_detiene_paginacion_dos_semillas_ambas_satisfechas() -> None:
    """Con 2 semillas y max=2, se detiene cuando AMBAS alcanzan el tope.

    - W100 y W200, max=2 cada una
    - Página 1: C1 y C2 citan W100; C3 y C4 citan W200 → ambas satisfechas
    - Página 2: más citantes → nunca deben fetchearse
    """
    page1 = [
        _citing_work("C1", ["W100"]),
        _citing_work("C2", ["W100"]),
        _citing_work("C3", ["W200"]),
        _citing_work("C4", ["W200"]),
    ]
    page2 = [
        _citing_work("C5", ["W100"]),
        _citing_work("C6", ["W200"]),
    ]

    transport, counters = _make_paginated_cited_by_transport([page1, page2])

    corpus = _corpus_from_rows(
        [
            _make_row(id="P1", source_id="W100"),
            _make_row(id="P2", source_id="W200"),
        ]
    )
    enricher = _make_enricher(transport, max_citing_per_paper=2)
    result = enricher.enrich(corpus)

    # Ambas satisfechas en página 1 → solo 1 request
    assert counters["citing"][0] == 1, (
        f"Ambas semillas satisfechas en página 1; "
        f"no debe fetchear página 2; hizo {counters['citing'][0]} requests"
    )

    table = result.to_arrow()
    rows = table.to_pylist()
    cited_by_map = {row["source_id"]: set(row.get("cited_by_id") or []) for row in rows}
    assert len(cited_by_map["W100"]) == 2
    assert len(cited_by_map["W200"]) == 2


# ---------------------------------------------------------------------------
# 13. Sin tope (None): pagina todo y atribuye correctamente
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_sin_tope_pagina_todo_y_atribuye() -> None:
    """max_citing_per_paper=None pagina todas las páginas y atribuye correctamente.

    - W100 y W200, sin tope
    - Página 1: C1 cita W100, C2 cita W200
    - Página 2: C3 cita W100 y W200, C4 cita W100
    - Deben fetchearse las 2 páginas y atribuirse correctamente.
    """
    page1 = [
        _citing_work("C1", ["W100"]),
        _citing_work("C2", ["W200"]),
    ]
    page2 = [
        _citing_work("C3", ["W100", "W200"]),
        _citing_work("C4", ["W100"]),
    ]

    transport, counters = _make_paginated_cited_by_transport([page1, page2])

    corpus = _corpus_from_rows(
        [
            _make_row(id="P1", source_id="W100"),
            _make_row(id="P2", source_id="W200"),
        ]
    )
    enricher = _make_enricher(transport, max_citing_per_paper=None)
    result = enricher.enrich(corpus)

    # Sin tope → debe fetchear ambas páginas
    assert counters["citing"][0] == 2, (
        f"Sin tope debe fetchear las 2 páginas; hizo {counters['citing'][0]}"
    )

    table = result.to_arrow()
    rows = table.to_pylist()
    cited_by_map = {row["source_id"]: set(row.get("cited_by_id") or []) for row in rows}

    # W100: C1, C3, C4
    assert cited_by_map["W100"] == {"C1", "C3", "C4"}, (
        f"W100 debe tener {{C1, C3, C4}}, tiene {cited_by_map['W100']}"
    )
    # W200: C2, C3
    assert cited_by_map["W200"] == {"C2", "C3"}, (
        f"W200 debe tener {{C2, C3}}, tiene {cited_by_map['W200']}"
    )
