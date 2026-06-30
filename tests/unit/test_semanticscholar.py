"""Tests unitarios de ``SemanticScholarSource`` (ADR 0042).

Todos los tests de red usan ``httpx.MockTransport`` (sin red real en CI),
salvo el marcado ``@pytest.mark.network`` (excluido del gate por defecto).

Casos cubiertos (instrucción del epic):
1. ``seed`` con key (mock 200): mapeo S2→PaperRow, executed_query,
   translation_report honesto, provenance.source="semanticscholar".
2. ``seed`` sin key (mock 429 sostenido): NetworkError accionable (D2),
   sin loop infinito.
3. ``_paper_to_row``: dedup cross-motor vía DOI (mismo id que OpenAlex);
   sin DOI → id cae a source_id; campos faltantes defensivos.
4. ``fetch_works_by_ids``: paginación >500 IDs; consulta por DOI:10.….
5. ``fetch_citing_batch``/``_with_works``: atribución, max_per_paper, []
   para input vacío.
6. Paridad de contrato: isinstance(SemanticScholarSource(...), Source).
7. Un test @network opcional.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx
import pytest

from bib2graph.constants import Col, CurationStatus
from bib2graph.corpus import _rows_with_ids
from bib2graph.schemas import ProvenanceEvent
from bib2graph.service.errors import NetworkError
from bib2graph.sources.base import Source
from bib2graph.sources.openalex import _work_to_row
from bib2graph.sources.semanticscholar import SemanticScholarSource, _paper_to_row

# ---------------------------------------------------------------------------
# Fixtures de datos S2 (JSON crudo, shape de la Academic Graph API)
# ---------------------------------------------------------------------------

PAPER_CON_DOI: dict[str, Any] = {
    "paperId": "649def34f8be52c8b66281af98ae884c09aef38",
    "title": "Construction of the Literature Graph in Semantic Scholar",
    "abstract": "We describe a deployed scalable system for organizing...",
    "year": 2018,
    "externalIds": {"DOI": "10.18653/V1/N18-3011", "MAG": "12345"},
    "authors": [
        {"authorId": "1741101", "name": "Waleed Ammar"},
        {"authorId": "1741102", "name": "Dirk Groeneveld"},
    ],
    "fieldsOfStudy": ["Computer Science"],
    "s2FieldsOfStudy": [{"category": "Computer Science", "source": "external"}],
    "referenceCount": 2,
    "citationCount": 10,
}

PAPER_SIN_DOI: dict[str, Any] = {
    "paperId": "abc123sindoinone",
    "title": "A paper without DOI",
    "abstract": None,
    "year": 2020,
    "externalIds": {},
    "authors": [],
    "fieldsOfStudy": None,
    "s2FieldsOfStudy": [],
    "referenceCount": 0,
    "citationCount": 0,
}

PAPER_CAMPOS_MINIMOS: dict[str, Any] = {
    "paperId": "minimo000",
    "title": "Title only",
}


# ---------------------------------------------------------------------------
# Helpers de mock HTTP
# ---------------------------------------------------------------------------


def _make_search_handler(papers: list[dict[str, Any]]) -> httpx.MockTransport:
    """MockTransport para /paper/search: una página con todos, luego vacía."""
    calls: list[int] = [0]

    def handler(request: httpx.Request) -> httpx.Response:
        calls[0] += 1
        if calls[0] == 1:
            body = {"total": len(papers), "offset": 0, "data": papers}
        else:
            body = {"total": len(papers), "offset": len(papers), "data": []}
        return httpx.Response(200, json=body)

    return httpx.MockTransport(handler)


def _make_429_handler() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="Too Many Requests")

    return httpx.MockTransport(handler)


# ---------------------------------------------------------------------------
# 1. seed con MockTransport (mapeo, executed_query, translation_report)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_seed_con_mock_transport_mapea_corpus() -> None:
    """``seed()`` con MockTransport puebla el corpus con los papers fixture."""
    papers = [PAPER_CON_DOI, PAPER_SIN_DOI]
    transport = _make_search_handler(papers)
    source = SemanticScholarSource(api_key="test-key", transport=transport)

    result = source.seed("unequal exchange ecological debt")

    assert len(result.corpus) == len(papers)


@pytest.mark.unit
def test_seed_executed_query_es_la_query_nativa() -> None:
    """``executed_query`` == query (sin traducción, D3 ADR 0042)."""
    transport = _make_search_handler([PAPER_CON_DOI])
    source = SemanticScholarSource(api_key="test-key", transport=transport)

    query = "complex systems thinking"
    result = source.seed(query)

    assert result.executed_query == query


@pytest.mark.unit
def test_seed_translation_report_honesto() -> None:
    """``translation_report`` declara explícitamente que no hubo traducción."""
    transport = _make_search_handler([PAPER_CON_DOI])
    source = SemanticScholarSource(api_key="test-key", transport=transport)

    result = source.seed("ecological exchange")

    assert len(result.translation_report) == 1
    report_line = result.translation_report[0]
    assert "S2" in report_line
    assert "sin traducción" in report_line or "sin traducción WoS" in report_line


@pytest.mark.unit
def test_seed_provenance_source_semanticscholar() -> None:
    """Todas las filas sembradas tienen provenance.source == 'semanticscholar'."""
    transport = _make_search_handler([PAPER_CON_DOI, PAPER_SIN_DOI])
    source = SemanticScholarSource(api_key="test-key", transport=transport)

    result = source.seed("ecological exchange")
    table = result.corpus.to_arrow()
    provenance_col = table.column(Col.PROVENANCE).to_pylist()

    for prov_json in provenance_col:
        events = ProvenanceEvent.parse_list(prov_json)
        assert len(events) >= 1
        assert events[0].source == "semanticscholar"


@pytest.mark.unit
def test_seed_is_seed_true_y_curation_candidate() -> None:
    """``seed()`` marca is_seed=True y curation_status=candidate."""
    transport = _make_search_handler([PAPER_CON_DOI])
    source = SemanticScholarSource(api_key="test-key", transport=transport)

    result = source.seed("ecological exchange")
    table = result.corpus.to_arrow()

    assert all(table.column(Col.IS_SEED).to_pylist())
    assert all(
        s == CurationStatus.CANDIDATE
        for s in table.column(Col.CURATION_STATUS).to_pylist()
    )


@pytest.mark.unit
def test_seed_authors_raw_mapeados() -> None:
    """``authors[].name`` → ``authors_raw``."""
    transport = _make_search_handler([PAPER_CON_DOI])
    source = SemanticScholarSource(api_key="test-key", transport=transport)

    result = source.seed("ecological exchange")
    table = result.corpus.to_arrow()
    authors_raw = table.column(Col.AUTHORS_RAW).to_pylist()[0]

    assert authors_raw is not None
    assert "Waleed Ammar" in authors_raw
    assert "Dirk Groeneveld" in authors_raw


@pytest.mark.unit
def test_seed_research_areas_desde_fields_of_study() -> None:
    """``fieldsOfStudy`` → ``research_areas``."""
    transport = _make_search_handler([PAPER_CON_DOI])
    source = SemanticScholarSource(api_key="test-key", transport=transport)

    result = source.seed("ecological exchange")
    table = result.corpus.to_arrow()
    research_areas = table.column(Col.RESEARCH_AREAS).to_pylist()[0]

    assert research_areas is not None
    assert "Computer Science" in research_areas


@pytest.mark.unit
def test_seed_keywords_raw_vacio_declarado() -> None:
    """``keywords_raw`` queda vacío (S2 no expone keywords ricas, ADR 0018-B)."""
    transport = _make_search_handler([PAPER_CON_DOI])
    source = SemanticScholarSource(api_key="test-key", transport=transport)

    result = source.seed("ecological exchange")
    table = result.corpus.to_arrow()
    keywords_raw = table.column(Col.KEYWORDS_RAW).to_pylist()

    assert all(k is None for k in keywords_raw)


@pytest.mark.unit
def test_seed_manifest_equations_query() -> None:
    """``manifest.equations[0].query == executed_query``."""
    transport = _make_search_handler([PAPER_CON_DOI])
    source = SemanticScholarSource(api_key="test-key", transport=transport)

    query = "complex systems"
    result = source.seed(query)

    assert len(result.corpus.manifest.equations) == 1
    assert result.corpus.manifest.equations[0].query == result.executed_query


# ---------------------------------------------------------------------------
# 2. seed sin key (429 sostenido) → NetworkError accionable
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_seed_429_levanta_network_error_accionable() -> None:
    """Un 429 sostenido en /paper/search lanza NetworkError, no HTTPStatusError.

    Sella D2 (ADR 0042): el mensaje nombra la API key como remedio (no el
    "polite pool" de OpenAlex). No debe loopear infinitamente: seed() no
    reintenta (single-shot), por lo que un único 429 ya dispara el error.
    """
    transport = _make_429_handler()
    source = SemanticScholarSource(transport=transport)  # sin api_key

    with pytest.raises(NetworkError) as exc_info:
        source.seed("ecological exchange")

    msg = str(exc_info.value)
    assert "429" in msg
    assert "api key" in msg.lower() or "api_key" in msg.lower()
    assert "S2_API_KEY" in msg
    assert "ADR 0042" in msg


@pytest.mark.unit
def test_seed_429_no_es_httpstatuserror_pelado() -> None:
    """El error levantado es NetworkError, no httpx.HTTPStatusError directo."""
    transport = _make_429_handler()
    source = SemanticScholarSource(transport=transport)

    try:
        source.seed("ecological exchange")
        pytest.fail("Se esperaba una excepción")
    except NetworkError:
        pass
    except httpx.HTTPStatusError:
        pytest.fail("seed() no debe propagar httpx.HTTPStatusError pelado")


# ---------------------------------------------------------------------------
# 3. _paper_to_row: dedup cross-motor vía DOI, fallback sin DOI, defensivo
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_paper_to_row_con_doi_ancla_id_cross_motor() -> None:
    """Un paper S2 con DOI obtiene el mismo id canónico que un work OpenAlex
    con el mismo DOI (dedup cross-motor gratis, ADR 0036/0042)."""
    fetched_at = "2026-06-30T00:00:00+00:00"

    s2_row = _paper_to_row(PAPER_CON_DOI, equation_id="eq-1", fetched_at=fetched_at)
    openalex_work = {
        "id": "https://openalex.org/W123",
        "doi": "https://doi.org/10.18653/v1/N18-3011",
        "title": "Construction of the Literature Graph (OpenAlex version)",
        "publication_year": 2018,
    }
    oa_row = _work_to_row(openalex_work, equation_id="eq-2", fetched_at=fetched_at)

    [s2_with_id] = _rows_with_ids([s2_row])
    [oa_with_id] = _rows_with_ids([oa_row])

    assert s2_with_id[Col.ID] == oa_with_id[Col.ID]
    assert str(s2_with_id[Col.ID]).startswith("doi:")


@pytest.mark.unit
def test_paper_to_row_sin_doi_cae_a_source_id() -> None:
    """Sin DOI, el id canónico cae al source_id (paperId)."""
    fetched_at = "2026-06-30T00:00:00+00:00"
    row = _paper_to_row(PAPER_SIN_DOI, equation_id="eq-1", fetched_at=fetched_at)

    assert row[Col.DOI] is None
    assert row[Col.SOURCE_ID] == PAPER_SIN_DOI["paperId"]

    [with_id] = _rows_with_ids([row])
    assert str(with_id[Col.ID]).startswith("src:")


@pytest.mark.unit
def test_paper_to_row_campos_faltantes_sin_keyerror() -> None:
    """Paper con solo title/paperId → sin KeyError, campos faltantes en None."""
    fetched_at = "2026-06-30T00:00:00+00:00"

    row = _paper_to_row(PAPER_CAMPOS_MINIMOS, equation_id="eq-1", fetched_at=fetched_at)

    assert row[Col.TITLE] == "Title only"
    assert row[Col.SOURCE_ID] == "minimo000"
    assert row[Col.DOI] is None
    assert row[Col.YEAR] is None
    assert row[Col.ABSTRACT] is None
    assert row[Col.AUTHORS_RAW] is None
    assert row[Col.RESEARCH_AREAS] is None
    assert row[Col.REFERENCES_ID] is None
    assert row[Col.REFERENCES_DOI] is None
    assert row[Col.CITED_BY_ID] == []


@pytest.mark.unit
def test_paper_to_row_provenance_source_tag() -> None:
    """El evento de provenance usa source_tag (default 'semanticscholar')."""
    fetched_at = "2026-06-30T00:00:00+00:00"
    row = _paper_to_row(PAPER_CON_DOI, equation_id="eq-1", fetched_at=fetched_at)

    events = ProvenanceEvent.parse_list(row[Col.PROVENANCE])
    assert events[0].source == "semanticscholar"


@pytest.mark.unit
def test_paper_to_row_referencias_con_doi() -> None:
    """``references[].{paperId, externalIds.DOI}`` → references_id/references_doi."""
    paper = dict(PAPER_CON_DOI)
    paper["references"] = [
        {"paperId": "ref1", "externalIds": {"DOI": "10.1/ref1"}},
        {"paperId": "ref2", "externalIds": {}},
        {"paperId": None, "externalIds": {"DOI": "10.1/ref3"}},
    ]
    fetched_at = "2026-06-30T00:00:00+00:00"
    row = _paper_to_row(paper, equation_id="eq-1", fetched_at=fetched_at)

    assert row[Col.REFERENCES_ID] == ["ref1", "ref2"]
    assert row[Col.REFERENCES_DOI] == ["10.1/ref1", "10.1/ref3"]


# ---------------------------------------------------------------------------
# 4. fetch_works_by_ids: paginación >500, consulta por DOI:
# ---------------------------------------------------------------------------


def _make_batch_handler(
    response_for_call: list[list[dict[str, Any] | None]],
) -> tuple[httpx.MockTransport, list[dict[str, Any]]]:
    """MockTransport para /paper/batch; registra cada request para inspección."""
    calls: list[int] = [0]
    requests_seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        body = _json.loads(request.content)
        requests_seen.append(body)
        idx = calls[0]
        calls[0] += 1
        data = response_for_call[idx] if idx < len(response_for_call) else []
        return httpx.Response(200, json=data)

    return httpx.MockTransport(handler), requests_seen


@pytest.mark.unit
def test_fetch_works_by_ids_paginacion_mas_de_500() -> None:
    """Más de 500 IDs → 2 lotes (POST /paper/batch paginado por ≤500)."""
    ids = [f"paper{i}" for i in range(501)]
    transport, requests_seen = _make_batch_handler([[], []])
    source = SemanticScholarSource(transport=transport)

    source.fetch_works_by_ids(ids)

    assert len(requests_seen) == 2
    assert len(requests_seen[0]["ids"]) == 500
    assert len(requests_seen[1]["ids"]) == 1


@pytest.mark.unit
def test_fetch_works_by_ids_consulta_por_doi_prefijo() -> None:
    """IDs con prefijo DOI: se pasan tal cual al body del batch (sin transformar)."""
    transport, requests_seen = _make_batch_handler([[PAPER_CON_DOI]])
    source = SemanticScholarSource(transport=transport)

    corpus = source.fetch_works_by_ids(["DOI:10.18653/V1/N18-3011"])

    assert requests_seen[0]["ids"] == ["DOI:10.18653/V1/N18-3011"]
    assert len(corpus) == 1


@pytest.mark.unit
def test_fetch_works_by_ids_is_seed_false_y_action_fetched_by_id() -> None:
    """Papers traídos por ID: is_seed=False, provenance action='fetched_by_id'."""
    transport, _ = _make_batch_handler([[PAPER_CON_DOI]])
    source = SemanticScholarSource(transport=transport)

    corpus = source.fetch_works_by_ids(["649def34f8be52c8b66281af98ae884c09aef38"])
    table = corpus.to_arrow()

    assert all(v is False for v in table.column(Col.IS_SEED).to_pylist())
    for prov_json in table.column(Col.PROVENANCE).to_pylist():
        events = ProvenanceEvent.parse_list(prov_json)
        assert events[0].action == "fetched_by_id"


@pytest.mark.unit
def test_fetch_works_by_ids_ids_inexistentes_se_omiten() -> None:
    """S2 devuelve null posicional para IDs no encontrados → se omiten sin error."""
    transport, _ = _make_batch_handler([[PAPER_CON_DOI, None, None]])
    source = SemanticScholarSource(transport=transport)

    corpus = source.fetch_works_by_ids(["p1", "p2", "p3"])

    assert len(corpus) == 1


@pytest.mark.unit
def test_fetch_works_by_ids_lista_vacia_sin_request() -> None:
    """Lista vacía → Corpus vacío sin request HTTP (sin transport, fallaría si llamara)."""
    source = SemanticScholarSource()

    corpus = source.fetch_works_by_ids([])

    assert len(corpus) == 0


# ---------------------------------------------------------------------------
# 5. fetch_citing_batch / fetch_citing_batch_with_works
# ---------------------------------------------------------------------------


def _citing_paper(paper_id: str, year: int = 2021) -> dict[str, Any]:
    return {
        "paperId": paper_id,
        "title": f"Citing paper {paper_id}",
        "year": year,
        "authors": [],
        "externalIds": {},
        "abstract": None,
        "fieldsOfStudy": None,
        "s2FieldsOfStudy": [],
        "referenceCount": 0,
        "citationCount": 0,
    }


def _make_citations_handler(
    by_paper_id: dict[str, list[dict[str, Any]]],
) -> httpx.MockTransport:
    """MockTransport para /paper/{id}/citations: una página por paper, sin 'next'."""

    def handler(request: httpx.Request) -> httpx.Response:
        # path: /graph/v1/paper/{id}/citations
        parts = request.url.path.split("/")
        paper_id = parts[parts.index("paper") + 1]
        citers = by_paper_id.get(paper_id, [])
        body = {
            "offset": 0,
            "data": [{"citingPaper": c} for c in citers],
        }
        return httpx.Response(200, json=body)

    return httpx.MockTransport(handler)


@pytest.mark.unit
def test_fetch_citing_batch_atribucion_basica() -> None:
    """``fetch_citing_batch`` devuelve {seed_id: [citer_id, ...]}."""
    by_paper = {
        "seed1": [_citing_paper("c1"), _citing_paper("c2")],
        "seed2": [_citing_paper("c3")],
    }
    transport = _make_citations_handler(by_paper)
    source = SemanticScholarSource(transport=transport)

    result = source.fetch_citing_batch(["seed1", "seed2"])

    assert result["seed1"] == ["c1", "c2"]
    assert result["seed2"] == ["c3"]


@pytest.mark.unit
def test_fetch_citing_batch_max_per_paper_respetado() -> None:
    """``max_per_paper`` acota el número de citantes por semilla."""
    by_paper = {
        "seed1": [_citing_paper(f"c{i}") for i in range(5)],
    }
    transport = _make_citations_handler(by_paper)
    source = SemanticScholarSource(transport=transport)

    result = source.fetch_citing_batch(["seed1"], max_per_paper=2)

    assert len(result["seed1"]) == 2


@pytest.mark.unit
def test_fetch_citing_batch_lista_vacia() -> None:
    """``fetch_citing_batch([])`` → {} sin request HTTP."""
    source = SemanticScholarSource()

    assert source.fetch_citing_batch([]) == {}


@pytest.mark.unit
def test_fetch_citing_batch_with_works_devuelve_tupla() -> None:
    """``fetch_citing_batch_with_works`` devuelve (attribution, works_map)."""
    by_paper = {"seed1": [_citing_paper("c1")]}
    transport = _make_citations_handler(by_paper)
    source = SemanticScholarSource(transport=transport)

    attribution, works_map = source.fetch_citing_batch_with_works(["seed1"])

    assert attribution == {"seed1": ["c1"]}
    assert "c1" in works_map
    assert works_map["c1"]["paperId"] == "c1"


@pytest.mark.unit
def test_fetch_citing_batch_with_works_lista_vacia() -> None:
    """``fetch_citing_batch_with_works([])`` → ({}, {}) sin request HTTP."""
    source = SemanticScholarSource()

    attribution, works_map = source.fetch_citing_batch_with_works([])

    assert attribution == {}
    assert works_map == {}


@pytest.mark.unit
def test_fetch_citing_batch_since_filtra_por_anio() -> None:
    """``since`` descarta citantes con año < since.year (aproximación, ver docstring)."""
    by_paper = {
        "seed1": [_citing_paper("old", year=2015), _citing_paper("new", year=2023)],
    }
    transport = _make_citations_handler(by_paper)
    source = SemanticScholarSource(transport=transport)

    result = source.fetch_citing_batch(["seed1"], since=date(2020, 1, 1))

    assert result["seed1"] == ["new"]


# ---------------------------------------------------------------------------
# 6. Paridad de contrato: Source Protocol
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_semantic_scholar_source_cumple_protocol_source() -> None:
    """``SemanticScholarSource`` satisface el Protocol ``Source`` (runtime_checkable)."""
    source = SemanticScholarSource()
    assert isinstance(source, Source)


# ---------------------------------------------------------------------------
# Credenciales (sin red)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_api_key_desde_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    """``api_key`` se resuelve desde ``S2_API_KEY`` si no hay argumento."""
    monkeypatch.setenv("S2_API_KEY", "env-key")
    source = SemanticScholarSource()
    assert source._api_key == "env-key"


@pytest.mark.unit
def test_api_key_argumento_gana_sobre_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    """Argumento explícito gana sobre la variable de entorno."""
    monkeypatch.setenv("S2_API_KEY", "env-key")
    source = SemanticScholarSource(api_key="explicit-key")
    assert source._api_key == "explicit-key"


@pytest.mark.unit
def test_client_usa_header_x_api_key_no_bearer() -> None:
    """El cliente usa el header ``x-api-key`` (no ``Authorization: Bearer``)."""
    source = SemanticScholarSource(api_key="my-key")
    client = source._client()
    try:
        assert client.headers.get("x-api-key") == "my-key"
        assert "authorization" not in {k.lower() for k in client.headers}
    finally:
        client.close()


# ---------------------------------------------------------------------------
# load(): declarado, no implementado (decisión del PO)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_load_levanta_not_implemented_error() -> None:
    """``load()`` levanta NotImplementedError con mensaje claro."""
    source = SemanticScholarSource()

    with pytest.raises(NotImplementedError, match="seed"):
        source.load("algun/path.json")


# ---------------------------------------------------------------------------
# max_results
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_max_results_default_es_200() -> None:
    source = SemanticScholarSource()
    assert source._max_results == 200


@pytest.mark.unit
def test_max_results_propagado() -> None:
    source = SemanticScholarSource(max_results=30)
    assert source._max_results == 30


@pytest.mark.unit
def test_seed_max_results_corta_resultados() -> None:
    """``seed()`` con ``max_results=1`` devuelve a lo sumo 1 paper."""
    papers = [PAPER_CON_DOI, PAPER_SIN_DOI]
    transport = _make_search_handler(papers)
    source = SemanticScholarSource(max_results=1, transport=transport)

    result = source.seed("ecological exchange")

    assert len(result.corpus) == 1


# ---------------------------------------------------------------------------
# 7. Test de red real (excluido del gate por defecto)
# ---------------------------------------------------------------------------


@pytest.mark.network
def test_seed_red_real() -> None:
    """Siembra real contra la API de S2 (sin key: bajo volumen, puede dar 429).

    Lección #30: validar contra la API real, no solo mocks. Si S2 devuelve 429
    por falta de key, el test documenta el comportamiento esperado (D2).
    """
    source = SemanticScholarSource()

    try:
        result = source.seed("complex systems thinking")
    except NetworkError as exc:
        assert "API key" in str(exc) or "api key" in str(exc).lower()
        return

    assert result.executed_query == "complex systems thinking"
