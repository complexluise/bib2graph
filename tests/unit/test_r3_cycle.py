"""Tests R3 — FSM cíclico de dominio (``cycle.py``) + reseed/ronda + curación transversal.

Casos cubiertos (ROADMAP Hito R3):

1. ``CycleState`` puro: secuencia de transiciones válidas y reseed (loop-back,
   ronda++) sin DuckDB.
2. Acumulación entre rondas: re-sembrar tras BUILT no pierde lo aceptado.
3. Contrato ``--json`` de ``status``: incluye ``curation_available``/``round``/
   transiciones; no driftea; ``schema="1"``.
4. ``reseed`` a través del backend DuckDB: ronda persiste.

Filosofía del repo: solo lo que tiene lógica o riesgo de regresión.  No se
testea el plumbing de Click; se testea ``run_status``.

Marcador: ``unit`` (DuckDB en tmp_path, puro de dominio).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest

from bib2graph.cycle import (
    CURATION_ACTIONS,
    CycleState,
    apply_transition,
    available_transitions,
)
from bib2graph.schemas import CORPUS_SCHEMA

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_row(
    *, id: str, title: str = "Test", curation_status: str = "candidate"
) -> dict[str, Any]:
    """Fila mínima con schema completo."""
    return {
        "id": id,
        "openalex_id": None,
        "doi": None,
        "title": title,
        "year": 2020,
        "abstract": None,
        "source": None,
        "language": "en",
        "publisher": None,
        "research_areas": None,
        "is_seed": True,
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
        "cited_by_id": None,
    }


def _seed_store(store_path: Path, rows: list[dict[str, Any]] | None = None) -> None:
    """Puebla un store con filas mínimas."""
    from bib2graph.corpus import Corpus
    from bib2graph.stores.duckdb import DuckDBStore

    if rows is None:
        rows = [_make_row(id="P1"), _make_row(id="P2")]
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)
    store = DuckDBStore(store_path)
    store.persist(corpus)


# ---------------------------------------------------------------------------
# 1. cycle.py puro: secuencia de transiciones válidas + reseed
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_primera_siembra_da_seeded_ronda_1() -> None:
    """La primera siembra desde None da SEEDED con ronda 1."""
    state, round_ = apply_transition(None, "seed", 0)
    assert state is CycleState.SEEDED
    assert round_ == 1


@pytest.mark.unit
def test_secuencia_chain_filter_build_monotona() -> None:
    """chain→filter→build sigue la cadena principal, ronda sin cambio."""
    state, round_ = apply_transition(None, "seed", 0)
    assert state is CycleState.SEEDED
    assert round_ == 1

    state, round_ = apply_transition(state, "chain", round_)
    assert state is CycleState.FORAGED
    assert round_ == 1

    state, round_ = apply_transition(state, "filter", round_)
    assert state is CycleState.FILTERED
    assert round_ == 1

    state, round_ = apply_transition(state, "build", round_)
    assert state is CycleState.BUILT
    assert round_ == 1


@pytest.mark.unit
def test_monitor_lleva_a_monitored() -> None:
    """monitor transiciona a MONITORED (estado existe en el modelo)."""
    state, round_ = apply_transition(CycleState.BUILT, "monitor", 1)
    assert state is CycleState.MONITORED
    assert round_ == 1


@pytest.mark.unit
def test_reseed_desde_built_loopback_ronda_mas_uno() -> None:
    """reseed desde BUILT → SEEDED, ronda++ (primera clase)."""
    state, round_ = apply_transition(CycleState.BUILT, "reseed", 1)
    assert state is CycleState.SEEDED
    assert round_ == 2


@pytest.mark.unit
def test_reseed_desde_monitored_loopback_ronda_mas_uno() -> None:
    """reseed desde MONITORED → SEEDED, ronda++ (loop-back cíclico completo)."""
    state, round_ = apply_transition(CycleState.MONITORED, "reseed", 2)
    assert state is CycleState.SEEDED
    assert round_ == 3


@pytest.mark.unit
def test_reseed_desde_seeded_loopback_ronda_mas_uno() -> None:
    """reseed desde SEEDED también incrementa la ronda (disponible desde cualquier estado)."""
    state, round_ = apply_transition(CycleState.SEEDED, "reseed", 1)
    assert state is CycleState.SEEDED
    assert round_ == 2


@pytest.mark.unit
def test_accion_desconocida_lanza_value_error() -> None:
    """Una acción no reconocida lanza ValueError con mensaje útil."""
    with pytest.raises(ValueError, match="no reconocida"):
        apply_transition(CycleState.SEEDED, "inexistente", 1)


@pytest.mark.unit
def test_transiciones_disponibles_none_solo_seed() -> None:
    """Sin estado previo, solo 'seed' está disponible."""
    transitions = available_transitions(None)
    assert transitions == ["seed"]


@pytest.mark.unit
def test_transiciones_disponibles_built_incluye_reseed_y_export() -> None:
    """Desde BUILT, reseed y export están disponibles."""
    transitions = available_transitions(CycleState.BUILT)
    assert "reseed" in transitions
    assert "export" in transitions


@pytest.mark.unit
def test_transiciones_disponibles_seeded_incluye_reseed() -> None:
    """Desde SEEDED, reseed está disponible (salto siempre-disponible)."""
    transitions = available_transitions(CycleState.SEEDED)
    assert "reseed" in transitions


@pytest.mark.unit
def test_curation_actions_contiene_accept_y_reject() -> None:
    """CURATION_ACTIONS exporta ['accept', 'reject'] como constante de dominio."""
    assert "accept" in CURATION_ACTIONS
    assert "reject" in CURATION_ACTIONS


# ---------------------------------------------------------------------------
# 2. Acumulación entre rondas: re-sembrar tras BUILT no pierde lo aceptado
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_acumulacion_entre_rondas_no_pierde_aceptados(tmp_path: Path) -> None:
    """Re-sembrar tras BUILT no pierde los papers aceptados (acumulación entre rondas).

    Simula dos rondas:
    - Ronda 1: sembrar + aceptar P1 + build.
    - Ronda 2: re-sembrar (reseed) agrega P3 al corpus; P1 sigue accepted.
    """
    from bib2graph.corpus import Corpus
    from bib2graph.cycle import CycleState, apply_transition
    from bib2graph.stores.duckdb import DuckDBStore

    db_path = tmp_path / "lib.duckdb"

    # --- Ronda 1 ---
    rows_r1 = [_make_row(id="P1"), _make_row(id="P2")]
    table_r1 = pa.Table.from_pylist(rows_r1, schema=CORPUS_SCHEMA)
    corpus_r1 = Corpus.from_arrow(table_r1)

    store = DuckDBStore(db_path)
    store.persist(corpus_r1)
    store.backend.set_loop_state(CycleState.SEEDED, cycle_round=1)

    # Aceptar P1
    corpus_loaded = store.load()
    corpus_accepted = corpus_loaded.accept(["P1"], by="revisor")
    store.persist(corpus_accepted)

    # Build (ronda 1, round=1)
    store.backend.set_loop_state(CycleState.BUILT, cycle_round=1)
    assert store.backend.loop_round() == 1

    # --- Ronda 2: reseed ---
    current_state = store.backend.loop_state()
    current_round = store.backend.loop_round()
    new_state, new_round = apply_transition(current_state, "reseed", current_round)
    assert new_state is CycleState.SEEDED
    assert new_round == 2

    # Sembrar paper nuevo (P3); merge acumula sobre P1/P2 ya existentes
    rows_r2 = [_make_row(id="P3")]
    table_r2 = pa.Table.from_pylist(rows_r2, schema=CORPUS_SCHEMA)
    corpus_r2 = Corpus.from_arrow(table_r2)

    corpus_existing = store.load()
    merged = corpus_existing.merge(corpus_r2)
    store.persist(merged)
    store.backend.set_loop_state(new_state, cycle_round=new_round)

    # --- Verificar acumulación ---
    final_corpus = store.load()
    ids = set(final_corpus.to_arrow().column("id").to_pylist())
    assert "P1" in ids
    assert "P2" in ids
    assert "P3" in ids

    # P1 sigue accepted
    rows = {r["id"]: r for r in final_corpus.to_arrow().to_pylist()}
    assert rows["P1"]["curation_status"] == "accepted"

    # Ronda es 2
    assert store.backend.loop_round() == 2
    assert store.backend.loop_state() is CycleState.SEEDED


# ---------------------------------------------------------------------------
# 3. Contrato --json de status: curation_available / round / schema="1"
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_run_status_incluye_curation_available_y_round(tmp_path: Path) -> None:
    """run_status devuelve curation_available y round (R3: mapa honesto del lazo)."""
    from bib2graph.cli.commands.status import run_status

    store_path = tmp_path / "test.duckdb"
    _seed_store(store_path)

    data = run_status(store_path)

    # Campos básicos
    assert "loop_state" in data
    assert "transitions_available" in data
    assert "counts_by_status" in data
    assert "total_papers" in data

    # Campos nuevos R3 (aditivos, schema="1")
    assert "curation_available" in data
    assert "round" in data

    # curation_available siempre lista accept y reject
    assert "accept" in data["curation_available"]
    assert "reject" in data["curation_available"]

    # round es entero
    assert isinstance(data["round"], int)


@pytest.mark.unit
def test_run_status_sin_estado_curation_available_present(tmp_path: Path) -> None:
    """run_status en store sin estado devuelve curation_available presente (siempre)."""
    from bib2graph.cli.commands.status import run_status
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "empty.duckdb"
    DuckDBStore(store_path)  # inicializa tablas

    data = run_status(store_path)

    assert data["loop_state"] is None
    assert data["round"] == 0
    assert "accept" in data["curation_available"]
    assert "reject" in data["curation_available"]
    # Sin estado: solo seed en transitions_available
    assert data["transitions_available"] == ["seed"]


@pytest.mark.unit
def test_status_json_schema_es_1_y_campos_no_driftan(tmp_path: Path) -> None:
    """El envelope --json de status mantiene schema='1' con los campos aditivos de R3."""
    from bib2graph.cli._envelope import build_envelope
    from bib2graph.cli.commands.status import run_status

    store_path = tmp_path / "test.duckdb"
    _seed_store(store_path)

    data = run_status(store_path)
    envelope = build_envelope(
        command="status",
        ok=True,
        data=data,
        exit_code=0,
    )

    # schema no se bumpea (decisión del PO 2026-06-16: aditivos)
    assert envelope["schema"] == "1"
    assert envelope["ok"] is True
    assert envelope["command"] == "status"
    assert envelope["exit_code"] == 0

    # Campos de data presentes
    d = envelope["data"]
    assert "loop_state" in d
    assert "transitions_available" in d
    assert "curation_available" in d  # nuevo R3
    assert "round" in d  # nuevo R3
    assert "counts_by_status" in d
    assert "total_papers" in d

    # JSON-serializable
    serialized = json.dumps(envelope)
    parsed = json.loads(serialized)
    assert parsed["data"]["round"] == d["round"]


@pytest.mark.unit
def test_transitions_no_incluyen_accept_reject(tmp_path: Path) -> None:
    """transitions_available NO incluye accept/reject (están en curation_available).

    Antes de R3, este era el bug: accept/reject no aparecían en ningún lado.
    Tras R3, el contrato es: transitions_available = acciones de ciclo,
    curation_available = ["accept", "reject"] siempre.
    """
    from bib2graph.cli.commands.status import run_status

    store_path = tmp_path / "test.duckdb"
    _seed_store(store_path)

    data = run_status(store_path)

    assert "accept" not in data["transitions_available"]
    assert "reject" not in data["transitions_available"]
    assert "accept" in data["curation_available"]
    assert "reject" in data["curation_available"]


# ---------------------------------------------------------------------------
# 4. reseed a través del backend DuckDB: ronda persiste
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_loop_round_persiste_tras_reseed(tmp_path: Path) -> None:
    """loop_round() persiste el número de ronda correctamente tras reseed."""
    from bib2graph.cycle import CycleState
    from bib2graph.stores.duckdb import DuckDBStore

    db_path = tmp_path / "lib.duckdb"
    store = DuckDBStore(db_path)

    # Sin estado: ronda 0
    assert store.backend.loop_round() == 0

    # Ronda 1
    store.backend.set_loop_state(CycleState.SEEDED, cycle_round=1)
    assert store.backend.loop_round() == 1

    store.backend.set_loop_state(CycleState.BUILT, cycle_round=1)
    assert store.backend.loop_round() == 1

    # Reseed: ronda 2
    store.backend.set_loop_state(CycleState.SEEDED, cycle_round=2)
    assert store.backend.loop_round() == 2
    assert store.backend.loop_state() is CycleState.SEEDED


@pytest.mark.unit
def test_loop_round_sobrevive_al_reload(tmp_path: Path) -> None:
    """loop_round() persiste en disco y sobrevive al reload (nueva instancia)."""
    from bib2graph.cycle import CycleState
    from bib2graph.stores.duckdb import DuckDBStore

    db_path = tmp_path / "lib.duckdb"

    store1 = DuckDBStore(db_path)
    store1.backend.set_loop_state(CycleState.SEEDED, cycle_round=1)
    store1.backend.set_loop_state(CycleState.BUILT, cycle_round=1)
    store1.backend.set_loop_state(CycleState.SEEDED, cycle_round=2)

    # Nueva instancia
    store2 = DuckDBStore(db_path)
    assert store2.backend.loop_round() == 2
    assert store2.backend.loop_state() is CycleState.SEEDED


@pytest.mark.unit
def test_run_status_ronda_aumenta_tras_reseed_via_seed(tmp_path: Path) -> None:
    """run_status refleja ronda=2 tras un reseed vía run_seed (integración liviana).

    Verifica que la ronda se incremente correctamente cuando run_seed detecta
    un estado previo y aplica reseed en vez de primera siembra.
    """
    import httpx

    from bib2graph.cli.commands.seed import run_seed
    from bib2graph.cli.commands.status import run_status

    store_path = tmp_path / "test.duckdb"

    works: list[dict[str, Any]] = [
        {
            "id": "https://openalex.org/W001",
            "title": "Paper de prueba R3",
            "publication_year": 2020,
            "doi": None,
            "primary_location": None,
            "language": "en",
            "type": "article",
            "abstract_inverted_index": None,
            "authorships": [],
            "concepts": [],
            "keywords": [],
            "topics": [],
            "referenced_works": [],
            "cited_by_api_url": "",
            "cited_by_count": 0,
            "best_oa_location": None,
        }
    ]

    call_count: list[int] = [0]

    def handler(request: httpx.Request) -> httpx.Response:
        call_count[0] += 1
        if call_count[0] == 1:
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

    transport = httpx.MockTransport(handler)

    # Primera siembra
    result1 = run_seed(store_path, "ecology", transport=transport)
    assert result1["round"] == 1
    assert result1["reseeded"] is False

    # Segunda siembra (reseed)
    call_count[0] = 0  # reset el contador del mock
    transport2 = httpx.MockTransport(handler)
    result2 = run_seed(store_path, "ecology reseed", transport=transport2)
    assert result2["round"] == 2
    assert result2["reseeded"] is True

    # status refleja ronda=2
    data = run_status(store_path)
    assert data["round"] == 2
    assert data["loop_state"] == "SEEDED"
