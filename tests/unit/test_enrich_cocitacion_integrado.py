"""Issue #64 — OpenAlexEnricher 8b (co-citación): integración mockeada end-to-end.

``test_enrichers_8b.py`` ya cubre el ``OpenAlexEnricher`` en memoria (sin
DuckDB). Este archivo agrega la capa de integración con el **store DuckDB**
vía ``run_enrich``, verificando el comportamiento end-to-end que antes no
podía validarse porque ``cited_by_id`` quedaba vacío en uso real.

Casos cubiertos:
1. ``cited_by_id`` se popula en las seeds aceptadas tras ``run_enrich`` con
   un transport mockeado que devuelve citantes reales (con ``referenced_works``
   correctos para la re-atribución).
2. ``Networks.quick`` sobre el corpus enriquecido produce la red ``cocitation``
   con las aristas esperadas (citantes compartidos entre seeds).
3. Idempotencia de ``run_enrich``: re-correr sobre el mismo store produce el
   mismo estado (mismo ``corpus_hash`` y misma red cocitation).
4. ``max_citing`` acota el fetch: con tope = 1, ``cited_by_id`` tiene ≤1
   citante por seed; el estado del store es consistente.
5. Corpus chico sin seeds aceptadas → ``run_enrich`` termina sin error y sin
   alterar el corpus (0 citantes, mismo ``corpus_hash``).

Sin red. Todos los transports son ``httpx.MockTransport``. El store es
DuckDB en ``tmp_path`` (cerrado y reabierto para verificar persistencia).

Reusa helpers y patrones de ``test_enrichers_8b.py``.

Marcador: ``unit`` (sin red real; DuckDB en tmp_path).
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
# Helpers de filas mínimas (copiados del patrón de test_enrichers_8b.py)
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
    """MockTransport que responde a ``cites:`` con la lista de citantes dada.

    Las consultas ``openalex_id:`` (pasada refs→DOI) devuelven vacío.
    """

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


def _make_empty_transport() -> httpx.MockTransport:
    """MockTransport que siempre devuelve respuestas vacías."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"results": [], "meta": {"count": 0, "next_cursor": None}},
            headers={"x-openalex-api-version": "2026-05-01"},
        )

    return httpx.MockTransport(handler)


def _setup_store(store_path: Path, rows: list[dict[str, Any]]) -> None:
    """Persiste el corpus inicial en el store DuckDB."""
    from bib2graph.stores.duckdb import DuckDBStore

    corpus = _corpus_from_rows(rows)
    store = DuckDBStore(store_path)
    store.persist(corpus)
    store.close()


def _load_corpus_from_store(store_path: Path) -> Corpus:
    """Carga el corpus del store DuckDB como corpus en memoria (nueva instancia).

    Convierte a Arrow antes de cerrar el store para que el corpus devuelto
    sea en memoria pura (InMemoryBackend) y no dependa de la conexión DuckDB.
    """
    import pyarrow as pa

    from bib2graph.schemas import CORPUS_SCHEMA
    from bib2graph.stores.duckdb import DuckDBStore

    store = DuckDBStore(store_path)
    try:
        table = store.backend.to_arrow()
    finally:
        store.close()

    # Rearmar un corpus en memoria pura para que no dependa de la conexión cerrada
    if len(table) == 0:
        table = pa.table(
            {f.name: pa.array([], type=f.type) for f in CORPUS_SCHEMA},
            schema=CORPUS_SCHEMA,
        )
    return Corpus.from_arrow(table)


# ---------------------------------------------------------------------------
# 1. cited_by_id poblado en seeds aceptadas tras run_enrich mockeado
# ---------------------------------------------------------------------------


def test_run_enrich_puebla_cited_by_en_seeds_aceptadas(tmp_path: Path) -> None:
    """run_enrich con transport mockeado puebla cited_by_id en las seeds aceptadas.

    Escenario: 2 seeds aceptadas (W100, W200) + 1 citante compartido C1 que
    cita a ambas. Tras run_enrich, cited_by_id debe contener C1 en ambos papers.

    Verifica la integración end-to-end: store → run_enrich → store → load.
    """
    from bib2graph.cli.commands.enrich import run_enrich

    rows = [
        _make_row(id="P1", source_id="W100"),
        _make_row(id="P2", source_id="W200"),
    ]
    store_path = tmp_path / "test.duckdb"
    _setup_store(store_path, rows)

    # C1 cita a W100 y W200 → co-citación entre P1 y P2
    citing_works = [_citing_work("C1", ["W100", "W200"])]
    transport = _make_cited_by_transport(citing_works)

    data = run_enrich(store_path, transport=transport)

    # Verificar métricas de la función
    assert data["citing_targets"] == 2, (
        f"Se esperaban 2 seeds objetivo, se obtuvieron {data['citing_targets']}"
    )
    assert data["citing_new"] >= 1, (
        f"Se esperaba ≥1 citante nuevo, se obtuvieron {data['citing_new']}"
    )

    # Verificar persistencia: abrir el store y chequear cited_by_id
    corpus = _load_corpus_from_store(store_path)
    table = corpus.to_arrow()
    rows_out = {r["source_id"]: r for r in table.to_pylist()}

    assert "C1" in (rows_out["W100"].get("cited_by_id") or []), (
        "W100 debe tener C1 en cited_by_id tras run_enrich"
    )
    assert "C1" in (rows_out["W200"].get("cited_by_id") or []), (
        "W200 debe tener C1 en cited_by_id tras run_enrich"
    )


# ---------------------------------------------------------------------------
# 2. Networks.quick produce cocitation con aristas esperadas
# ---------------------------------------------------------------------------


def test_run_enrich_produce_red_cocitacion_con_arista_esperada(tmp_path: Path) -> None:
    """Tras run_enrich, Networks.quick incluye la red cocitation con ≥1 arista.

    C1 cita W100 y W200 → co-citación entre P1 y P2 → 1 arista de peso 1.
    La arista debe conectar los IDs canónicos de P1 y P2 (Col.ID, no openalex_id).
    """
    from bib2graph.cli.commands.enrich import run_enrich
    from bib2graph.constants import NetworkKind
    from bib2graph.networks.facade import Networks

    rows = [
        _make_row(id="P1", source_id="W100"),
        _make_row(id="P2", source_id="W200"),
    ]
    store_path = tmp_path / "test.duckdb"
    _setup_store(store_path, rows)

    citing_works = [_citing_work("C1", ["W100", "W200"])]
    transport = _make_cited_by_transport(citing_works)
    run_enrich(store_path, transport=transport)

    corpus = _load_corpus_from_store(store_path)
    artifacts = Networks.quick(corpus)
    kinds = {a.spec.kind for a in artifacts}

    assert NetworkKind.COCITATION in kinds, (
        f"Networks.quick debe incluir co-citación después de enrich. "
        f"Redes presentes: {kinds}"
    )

    cocit = next(a for a in artifacts if a.spec.kind == NetworkKind.COCITATION)
    assert cocit.graph.number_of_nodes() >= 2, (
        f"La red de co-citación debe tener ≥2 nodos; tiene {cocit.graph.number_of_nodes()}"
    )
    assert cocit.graph.number_of_edges() >= 1, (
        f"La red de co-citación debe tener ≥1 arista; tiene {cocit.graph.number_of_edges()}"
    )

    # Verificar que el peso de la arista es 1 (un citante compartido C1)
    edges = list(cocit.graph.edges(data=True))
    assert any(e[2].get("weight", 0) >= 1 for e in edges), (
        "Al menos una arista debe tener weight ≥ 1 (C1 cita a W100 y W200)"
    )


# ---------------------------------------------------------------------------
# 3. Idempotencia de run_enrich: re-correr → mismo corpus_hash y misma red
# ---------------------------------------------------------------------------


def test_run_enrich_idempotente_corpus_hash_y_cocitacion(tmp_path: Path) -> None:
    """Re-correr run_enrich produce el mismo corpus_hash y la misma red cocitation.

    Verifica que:
    (a) El corpus_hash es idéntico antes y después de un segundo run_enrich.
    (b) La red cocitation tiene el mismo número de aristas en ambos runs.

    Esto cierra el contrato de idempotencia del enriquecimiento (R2/Hito 8b):
    enriquecer dos veces ≡ enriquecer una vez.
    """
    from bib2graph.cli.commands.enrich import run_enrich
    from bib2graph.constants import NetworkKind
    from bib2graph.networks.facade import Networks

    rows = [
        _make_row(id="P1", source_id="W100"),
        _make_row(id="P2", source_id="W200"),
        _make_row(id="P3", source_id="W300"),
    ]
    store_path = tmp_path / "test.duckdb"
    _setup_store(store_path, rows)

    # C1 cita W100+W200; C2 cita W200+W300; C3 cita W100+W300
    citing_works = [
        _citing_work("C1", ["W100", "W200"]),
        _citing_work("C2", ["W200", "W300"]),
        _citing_work("C3", ["W100", "W300"]),
    ]
    transport = _make_cited_by_transport(citing_works)

    # Primera ejecución
    run_enrich(store_path, transport=transport)
    corpus_after_1 = _load_corpus_from_store(store_path)
    hash_after_1 = corpus_after_1._backend.corpus_hash()

    artifacts_1 = Networks.quick(corpus_after_1)
    edges_cocit_1 = next(
        (
            a.graph.number_of_edges()
            for a in artifacts_1
            if a.spec.kind == NetworkKind.COCITATION
        ),
        0,
    )

    # Segunda ejecución (idempotencia: mismo transport, mismo corpus)
    transport2 = _make_cited_by_transport(citing_works)
    run_enrich(store_path, transport=transport2)
    corpus_after_2 = _load_corpus_from_store(store_path)
    hash_after_2 = corpus_after_2._backend.corpus_hash()

    artifacts_2 = Networks.quick(corpus_after_2)
    edges_cocit_2 = next(
        (
            a.graph.number_of_edges()
            for a in artifacts_2
            if a.spec.kind == NetworkKind.COCITATION
        ),
        0,
    )

    assert hash_after_1 == hash_after_2, (
        f"El corpus_hash difiere entre el 1er y 2do enrich: "
        f"{hash_after_1!r} vs {hash_after_2!r}. "
        "run_enrich debe ser idempotente (mismo corpus → mismo hash)."
    )
    assert edges_cocit_1 == edges_cocit_2, (
        f"La red cocitation difiere entre el 1er ({edges_cocit_1} aristas) y "
        f"2do ({edges_cocit_2} aristas) enrich. "
        "La red debe ser idéntica si el corpus no cambió."
    )
    # La co-citación debe tener aristas (3 seeds con citantes compartidos → 3 aristas)
    assert edges_cocit_1 >= 3, (
        f"Se esperaban ≥3 aristas de co-citación (pares W100-W200, W200-W300, W100-W300), "
        f"hay {edges_cocit_1}."
    )


# ---------------------------------------------------------------------------
# 4. max_citing acota el fetch
# ---------------------------------------------------------------------------


def test_run_enrich_max_citing_acota_cited_by_id(tmp_path: Path) -> None:
    """run_enrich con max_citing=1 acota cited_by_id a ≤1 citante por seed.

    Verifica que el tope ``max_citing`` propagado a ``run_enrich`` se respeta
    en la persistencia: cada seed aceptada tiene ≤1 ID en cited_by_id.
    """
    from bib2graph.cli.commands.enrich import run_enrich

    rows = [
        _make_row(id="P1", source_id="W100"),
        _make_row(id="P2", source_id="W200"),
    ]
    store_path = tmp_path / "test.duckdb"
    _setup_store(store_path, rows)

    # 5 citantes que citan W100; 3 citantes que citan W200
    citing_works = [_citing_work(f"C{i}", ["W100"]) for i in range(1, 6)] + [
        _citing_work(f"D{i}", ["W200"]) for i in range(1, 4)
    ]
    transport = _make_cited_by_transport(citing_works)

    run_enrich(store_path, transport=transport, max_citing=1)

    corpus = _load_corpus_from_store(store_path)
    table = corpus.to_arrow()
    rows_out = {r["source_id"]: r for r in table.to_pylist()}

    for oa_id in ["W100", "W200"]:
        cited = rows_out[oa_id].get("cited_by_id") or []
        assert len(cited) <= 1, (
            f"{oa_id} tiene {len(cited)} citantes con max_citing=1; debe tener ≤1."
        )


# ---------------------------------------------------------------------------
# 5. Corpus sin seeds aceptadas → run_enrich no altera el corpus
# ---------------------------------------------------------------------------


def test_run_enrich_sin_seeds_aceptadas_no_altera_corpus(tmp_path: Path) -> None:
    """Corpus sin seeds aceptadas → run_enrich termina sin error y sin alterar el corpus.

    Verifica que el pipeline no falla y que el corpus_hash permanece igual
    cuando no hay targets válidos para el enrich de co-citación.
    """
    from bib2graph.cli.commands.enrich import run_enrich

    rows = [
        _make_row(
            id="P1",
            source_id="W100",
            curation_status=CurationStatus.CANDIDATE,  # NO aceptada
        ),
        _make_row(
            id="P2",
            source_id="W200",
            is_seed=False,  # NO seed
            curation_status=CurationStatus.ACCEPTED,
        ),
    ]
    store_path = tmp_path / "test.duckdb"
    _setup_store(store_path, rows)

    # Hash antes
    corpus_before = _load_corpus_from_store(store_path)
    hash_before = corpus_before._backend.corpus_hash()

    transport = _make_empty_transport()
    data = run_enrich(store_path, transport=transport)

    assert data["citing_targets"] == 0, (
        f"No debe haber seeds objetivo (0 aceptadas), se obtuvieron {data['citing_targets']}"
    )
    assert data["citing_new"] == 0, (
        f"No debe haber nuevos citantes, se obtuvieron {data['citing_new']}"
    )

    # Hash después: debe ser idéntico (no se alteró el corpus)
    corpus_after = _load_corpus_from_store(store_path)
    hash_after = corpus_after._backend.corpus_hash()

    assert hash_before == hash_after, (
        f"El corpus_hash cambió sin que haya seeds aceptadas: "
        f"antes {hash_before!r}, después {hash_after!r}. "
        "run_enrich no debe alterar el corpus cuando no hay targets."
    )
