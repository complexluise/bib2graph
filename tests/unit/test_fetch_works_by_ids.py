"""Tests unitarios para OpenAlexSource.fetch_works_by_ids.

Casos cubiertos (DoD #55):
(a) Todos los IDs existen → Corpus con esas filas, is_seed=False/CANDIDATE/action="fetched_by_id".
(b) IDs inexistentes → omitidos sin error (el filtro OR no los devuelve).
(c) Mezcla parcial → solo los existentes, sin error.
(d) Orden determinista: mismo input → mismo orden por id canónico.
(e) Lista vacía → Corpus vacío sin error.
(f) No-regresión: seed() sigue marcando is_seed=True tras el refactor de _work_to_row.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from bib2graph.constants import Col, CurationStatus
from bib2graph.schemas import ProvenanceEvent
from bib2graph.sources.openalex import OpenAlexSource

# ---------------------------------------------------------------------------
# Fixtures y helpers de mock
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
SAMPLE_WORKS_PATH = FIXTURES_DIR / "sample_works.json"


def _load_fixture_works() -> list[dict[str, Any]]:
    return json.loads(SAMPLE_WORKS_PATH.read_text(encoding="utf-8"))


def _make_batch_transport(works: list[dict[str, Any]]) -> httpx.MockTransport:
    """MockTransport para _fetch_batch_select: devuelve los works en una sola página."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = {
            "results": works,
            "meta": {"count": len(works), "next_cursor": None},
        }
        return httpx.Response(
            200,
            json=body,
            headers={"x-openalex-api-version": "2026-05-01"},
        )

    return httpx.MockTransport(handler)


def _make_seed_transport(works: list[dict[str, Any]]) -> httpx.MockTransport:
    """MockTransport para seed() (paginación con cursor): una página y fin."""
    calls: list[int] = [0]

    def handler(request: httpx.Request) -> httpx.Response:
        calls[0] += 1
        if calls[0] == 1:
            body = {
                "results": works,
                "meta": {"count": len(works), "next_cursor": None},
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
# (a) Todos los IDs existen → corpus correcto
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_fetch_works_by_ids_todos_existen_devuelve_corpus() -> None:
    """IDs todos existentes → Corpus con esa cantidad de filas."""
    works = _load_fixture_works()
    transport = _make_batch_transport(works)
    source = OpenAlexSource(transport=transport)

    ids = ["W2741809807", "W1234567890", "W9999999999"]
    corpus = source.fetch_works_by_ids(ids)

    assert len(corpus) == len(works)


@pytest.mark.unit
def test_fetch_works_by_ids_is_seed_false() -> None:
    """Los papers traídos por ID tienen is_seed=False."""
    works = _load_fixture_works()
    transport = _make_batch_transport(works)
    source = OpenAlexSource(transport=transport)

    corpus = source.fetch_works_by_ids(["W2741809807"])
    table = corpus.to_arrow()
    is_seed_col = table.column(Col.IS_SEED).to_pylist()

    assert all(v is False for v in is_seed_col)


@pytest.mark.unit
def test_fetch_works_by_ids_curation_status_candidate() -> None:
    """Los papers traídos por ID tienen curation_status=CANDIDATE."""
    works = _load_fixture_works()
    transport = _make_batch_transport(works)
    source = OpenAlexSource(transport=transport)

    corpus = source.fetch_works_by_ids(["W2741809807"])
    table = corpus.to_arrow()
    status_col = table.column(Col.CURATION_STATUS).to_pylist()

    assert all(s == CurationStatus.CANDIDATE for s in status_col)


@pytest.mark.unit
def test_fetch_works_by_ids_provenance_action_fetched_by_id() -> None:
    """El primer evento de provenance tiene action='fetched_by_id'."""
    works = _load_fixture_works()
    transport = _make_batch_transport(works)
    source = OpenAlexSource(transport=transport)

    corpus = source.fetch_works_by_ids(["W2741809807"])
    table = corpus.to_arrow()
    provenance_col = table.column(Col.PROVENANCE).to_pylist()

    for prov_json in provenance_col:
        events = ProvenanceEvent.parse_list(prov_json)
        assert len(events) >= 1
        assert events[0].action == "fetched_by_id"


# ---------------------------------------------------------------------------
# (b) IDs inexistentes → omitidos sin error
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_fetch_works_by_ids_inexistentes_devuelve_corpus_vacio() -> None:
    """IDs que no existen en OpenAlex → corpus vacío, sin error."""
    transport = _make_batch_transport([])  # API devuelve 0 resultados
    source = OpenAlexSource(transport=transport)

    corpus = source.fetch_works_by_ids(["W0000000001", "W0000000002"])

    assert len(corpus) == 0


@pytest.mark.unit
def test_fetch_works_by_ids_inexistentes_no_lanza_excepcion() -> None:
    """IDs inexistentes no lanzan excepción."""
    transport = _make_batch_transport([])
    source = OpenAlexSource(transport=transport)

    # No debe lanzar ninguna excepción
    corpus = source.fetch_works_by_ids(["W9999999998"])
    assert corpus is not None


# ---------------------------------------------------------------------------
# (c) Mezcla parcial → solo los existentes
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_fetch_works_by_ids_mezcla_parcial() -> None:
    """Con IDs mixtos (algunos existen, otros no), el corpus contiene solo los existentes."""
    works = _load_fixture_works()[:1]  # solo el primero "existe"
    transport = _make_batch_transport(works)
    source = OpenAlexSource(transport=transport)

    # Pasamos 3 IDs pero el mock devuelve solo 1 (simula que los otros no existen)
    corpus = source.fetch_works_by_ids(["W2741809807", "W0000000001", "W0000000002"])

    assert len(corpus) == 1


# ---------------------------------------------------------------------------
# (d) Orden determinista
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_fetch_works_by_ids_orden_determinista() -> None:
    """Dos llamadas con el mismo input producen filas en el mismo orden por id canónico."""
    works = _load_fixture_works()

    # Primera llamada
    transport1 = _make_batch_transport(works)
    source1 = OpenAlexSource(transport=transport1)
    corpus1 = source1.fetch_works_by_ids(["W2741809807", "W1234567890", "W9999999999"])

    # Segunda llamada
    transport2 = _make_batch_transport(works)
    source2 = OpenAlexSource(transport=transport2)
    corpus2 = source2.fetch_works_by_ids(["W2741809807", "W1234567890", "W9999999999"])

    ids1 = corpus1.to_arrow().column(Col.ID).to_pylist()
    ids2 = corpus2.to_arrow().column(Col.ID).to_pylist()

    assert ids1 == ids2


@pytest.mark.unit
def test_fetch_works_by_ids_orden_es_por_id_canonico() -> None:
    """Las filas están ordenadas por id canónico (ascendente)."""
    works = _load_fixture_works()
    transport = _make_batch_transport(works)
    source = OpenAlexSource(transport=transport)

    corpus = source.fetch_works_by_ids(["W2741809807", "W1234567890", "W9999999999"])
    ids = corpus.to_arrow().column(Col.ID).to_pylist()

    assert ids == sorted(ids)


# ---------------------------------------------------------------------------
# (e) Lista vacía → Corpus vacío sin error
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_fetch_works_by_ids_lista_vacia() -> None:
    """Lista vacía de IDs → Corpus vacío sin error (sin request HTTP)."""
    # No hay transport: si se hiciera un request, lanzaría error
    source = OpenAlexSource()

    corpus = source.fetch_works_by_ids([])

    assert len(corpus) == 0


# ---------------------------------------------------------------------------
# (f) No-regresión: seed() sigue marcando is_seed=True tras el refactor
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_seed_sigue_marcando_is_seed_true_tras_refactor() -> None:
    """Regresión: tras el refactor de _work_to_row, seed() sigue usando is_seed=True."""
    works = _load_fixture_works()
    transport = _make_seed_transport(works)
    source = OpenAlexSource(transport=transport)

    result = source.seed("ecological exchange")
    table = result.corpus.to_arrow()
    is_seed_col = table.column(Col.IS_SEED).to_pylist()

    assert all(v is True for v in is_seed_col), (
        "Regresión: seed() ya no marca is_seed=True. "
        "El refactor de _work_to_row rompió el comportamiento de seed()."
    )


@pytest.mark.unit
def test_seed_provenance_action_es_fetched_tras_refactor() -> None:
    """Regresión: tras el refactor, seed() sigue usando action='fetched' en provenance."""
    works = _load_fixture_works()
    transport = _make_seed_transport(works)
    source = OpenAlexSource(transport=transport)

    result = source.seed("ecological exchange")
    table = result.corpus.to_arrow()
    provenance_col = table.column(Col.PROVENANCE).to_pylist()

    for prov_json in provenance_col:
        events = ProvenanceEvent.parse_list(prov_json)
        assert len(events) >= 1
        assert events[0].action == "fetched", (
            "Regresión: seed() ya no usa action='fetched'. "
            f"Se obtuvo action='{events[0].action}'."
        )


# ---------------------------------------------------------------------------
# Test de red real (excluido del gate por defecto)
# ---------------------------------------------------------------------------


@pytest.mark.network
def test_fetch_works_by_ids_red_real() -> None:
    """Trae 2-3 IDs reales de OpenAlex y verifica que vuelven con metadata.

    Lección #30: validar contra la API real, no solo mocks.
    IDs elegidos: works conocidos y estables de OpenAlex.
    """
    source = OpenAlexSource(email="trama.complejidad@gmail.com")

    # IDs públicos y estables en OpenAlex
    ids = [
        "W2741809807",  # "Biophysical Trade Balance of Ecuador"
        "W2890038990",  # otro work real
    ]
    corpus = source.fetch_works_by_ids(ids)

    assert len(corpus) >= 1, (
        f"Se esperaba al menos 1 work, se obtuvieron {len(corpus)}. "
        "Posible cambio en los IDs de OpenAlex o error de red."
    )

    table = corpus.to_arrow()

    # Verificar is_seed=False en todos
    is_seed_col = table.column(Col.IS_SEED).to_pylist()
    assert all(v is False for v in is_seed_col)

    # Verificar curation_status=CANDIDATE en todos
    status_col = table.column(Col.CURATION_STATUS).to_pylist()
    assert all(s == CurationStatus.CANDIDATE for s in status_col)

    # Verificar que tienen títulos (metadata presente)
    title_col = table.column(Col.TITLE).to_pylist()
    assert all(t for t in title_col), "Algún work no tiene título."

    # Verificar provenance action="fetched_by_id"
    provenance_col = table.column(Col.PROVENANCE).to_pylist()
    for prov_json in provenance_col:
        events = ProvenanceEvent.parse_list(prov_json)
        assert len(events) >= 1
        assert events[0].action == "fetched_by_id"
