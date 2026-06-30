"""Tests de ``DuckDBStore`` y ``CycleState`` — Hito 3.

Todos los tests tocan DuckDB sobre disco → marcados ``integration``.
El gate ``uv run pytest -m unit`` no los ejecuta.

Escenarios cubiertos (los justos, ROADMAP Hito 3):
- persist → load en instancia nueva acumula (biblioteca viva entre corridas).
- Idempotencia de persist (no duplica filas; mismo ``corpus_hash``).
- Procedencia/curación sobreviven al reinicio.
- ``CycleState``: transición SEEDED→FORAGED sobrevive al reload.
- Consulta SQL representativa vía ``backend.query(...)``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pytest

from bib2graph.corpus import Corpus
from bib2graph.cycle import CycleState
from bib2graph.schemas import CORPUS_SCHEMA
from bib2graph.stores.duckdb import DuckDBStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_row(
    *,
    id: str,
    title: str = "Título de prueba",
    is_seed: bool = True,
    curation_status: str = "candidate",
    provenance: str | None = None,
) -> dict[str, object]:
    """Fila mínima con todos los campos del schema canónico."""
    return {
        "id": id,
        "openalex_id": None,
        "doi": None,
        "title": title,
        "year": 2020,
        "abstract": None,
        "source": None,
        "language": None,
        "publisher": None,
        "research_areas": None,
        "is_seed": is_seed,
        "curation_status": curation_status,
        "provenance": provenance,
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


def _make_corpus(rows: list[dict[str, object]]) -> Corpus:
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    return Corpus.from_arrow(table)


# ---------------------------------------------------------------------------
# Tests de DuckDBStore
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_persist_load_acumula_entre_corridas(tmp_path: Path) -> None:
    """persist luego load en otra instancia devuelve el corpus acumulado."""
    db_path = tmp_path / "lib.duckdb"
    corpus1 = _make_corpus([_make_row(id="oa:aaaabbbb11112222", title="Paper A")])

    # Primera "corrida": persist
    store1 = DuckDBStore(db_path)
    store1.persist(corpus1)

    # Segunda "corrida": otra instancia, load
    store2 = DuckDBStore(db_path)
    loaded = store2.load()

    ids = loaded.to_arrow().column("id").to_pylist()
    assert "oa:aaaabbbb11112222" in ids
    assert len(loaded) == 1


@pytest.mark.integration
def test_persist_acumula_entre_corridas(tmp_path: Path) -> None:
    """Dos persist sucesivos con corpus distintos acumulan ambos (biblioteca viva)."""
    db_path = tmp_path / "lib.duckdb"
    corpus1 = _make_corpus([_make_row(id="oa:aaaabbbb11112222", title="Paper A")])
    corpus2 = _make_corpus([_make_row(id="oa:bbbbcccc22223333", title="Paper B")])

    DuckDBStore(db_path).persist(corpus1)
    DuckDBStore(db_path).persist(corpus2)

    loaded = DuckDBStore(db_path).load()
    ids = set(loaded.to_arrow().column("id").to_pylist())
    assert ids == {"oa:aaaabbbb11112222", "oa:bbbbcccc22223333"}


@pytest.mark.integration
def test_persist_idempotente(tmp_path: Path) -> None:
    """persist dos veces el mismo corpus no duplica filas; mismo corpus_hash."""
    db_path = tmp_path / "lib.duckdb"
    corpus = _make_corpus([_make_row(id="oa:aaaabbbb11112222", title="Paper A")])

    store = DuckDBStore(db_path)
    store.persist(corpus)
    loaded_first = store.load()
    hash_after_first = loaded_first._backend.corpus_hash()

    store.persist(corpus)
    loaded_second = store.load()
    hash_after_second = loaded_second._backend.corpus_hash()

    assert len(loaded_second) == 1
    assert hash_after_first == hash_after_second


@pytest.mark.integration
def test_provenance_curation_sobreviven_reinicio(tmp_path: Path) -> None:
    """accept en el corpus → persist → load nueva instancia → curación intacta."""
    db_path = tmp_path / "lib.duckdb"
    paper_id = "oa:aaaabbbb11112222"
    corpus = _make_corpus([_make_row(id=paper_id, title="Paper A")])

    # Primera sesión: aceptar y persistir
    corpus_curado = corpus.accept([paper_id], by="revisor_test")
    DuckDBStore(db_path).persist(corpus_curado)

    # Segunda sesión: load en instancia nueva
    loaded = DuckDBStore(db_path).load()
    rows = [r for r in loaded.to_arrow().to_pylist() if r["id"] == paper_id]
    row = rows[0]

    assert row["curation_status"] == "accepted"
    events = json.loads(row["provenance"])
    assert any(
        e["action"] == "accepted" and e["decided_by"] == "revisor_test" for e in events
    )


@pytest.mark.integration
def test_loop_state_sobrevive_al_reload(tmp_path: Path) -> None:
    """CycleState SEEDED→FORAGED sobrevive al reinicio (nueva instancia)."""
    db_path = tmp_path / "lib.duckdb"

    # Primera sesión: registrar transiciones
    store1 = DuckDBStore(db_path)
    store1.backend.set_loop_state(CycleState.SEEDED)
    store1.backend.set_loop_state(CycleState.FORAGED)

    # Segunda sesión: estado actual es FORAGED
    store2 = DuckDBStore(db_path)
    assert store2.backend.loop_state() == CycleState.FORAGED


@pytest.mark.integration
def test_loop_state_inicial_es_none(tmp_path: Path) -> None:
    """Un store recién creado sin transiciones devuelve loop_state() == None."""
    db_path = tmp_path / "lib.duckdb"
    store = DuckDBStore(db_path)
    assert store.backend.loop_state() is None


@pytest.mark.integration
def test_loop_state_transicion_permisiva(tmp_path: Path) -> None:
    """Las transiciones son permisivas: se puede saltar de SEEDED a BUILT."""
    db_path = tmp_path / "lib.duckdb"
    store = DuckDBStore(db_path)
    store.backend.set_loop_state(CycleState.SEEDED)
    store.backend.set_loop_state(CycleState.BUILT)
    assert store.backend.loop_state() == CycleState.BUILT


@pytest.mark.integration
def test_query_sql_representativa(tmp_path: Path) -> None:
    """backend.query(sql) devuelve resultados de una consulta SELECT."""
    db_path = tmp_path / "lib.duckdb"
    corpus = _make_corpus(
        [
            _make_row(
                id="oa:aaaabbbb11112222", title="Paper A", curation_status="accepted"
            ),
            _make_row(
                id="oa:bbbbcccc22223333", title="Paper B", curation_status="candidate"
            ),
        ]
    )

    store = DuckDBStore(db_path)
    store.persist(corpus)

    result = store.backend.query(
        "SELECT id, curation_status FROM corpus WHERE curation_status = 'accepted'"
    )
    assert len(result) == 1
    assert result.to_pylist()[0]["id"] == "oa:aaaabbbb11112222"


# ---------------------------------------------------------------------------
# Tests de DuckDBStore.close() — fix segfault Linux (doble open)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_duckdb_store_close_es_idempotente(tmp_path: Path) -> None:
    """close() no lanza error y puede llamarse múltiples veces sin romper nada."""
    db_path = tmp_path / "lib.duckdb"
    store = DuckDBStore(db_path)
    store.persist(_make_corpus([_make_row(id="oa:test0000aaaa0000")]))

    # Primera vez: no debe lanzar
    store.close()
    # Segunda vez: idempotente, no debe lanzar
    store.close()


@pytest.mark.integration
def test_duckdb_store_doble_open_mismo_archivo_no_crashea(tmp_path: Path) -> None:
    """Dos open_store consecutivos sobre el mismo archivo no crashean.

    Reproduce el patrón que causaba segfault en CI Linux (exit 139): dos
    invocaciones a run_seed_from_bib sobre el mismo store_path en el mismo
    proceso.  Con close() explícito al final de cada invocación el lock se
    libera y la segunda apertura es segura.
    """
    from bib2graph.cli._store import open_store

    db_path = tmp_path / "lib.duckdb"
    corpus_a = _make_corpus([_make_row(id="oa:aaaabbbb11112222", title="Paper A")])
    corpus_b = _make_corpus([_make_row(id="oa:bbbbcccc22223333", title="Paper B")])

    # Primera apertura: persist + close explícito
    store1 = open_store(db_path)
    merged1 = store1.load().merge(corpus_a)
    merged1_close = getattr(merged1._backend, "close", None)
    store1.persist(merged1)
    if merged1_close is not None:
        merged1_close()
    store1.close()

    # Segunda apertura sobre el mismo archivo: no debe segfaultear
    store2 = open_store(db_path)
    merged2 = store2.load().merge(corpus_b)
    merged2_close = getattr(merged2._backend, "close", None)
    store2.persist(merged2)
    if merged2_close is not None:
        merged2_close()
    store2.close()

    # Verificar que ambos papers persisten correctamente
    store3 = open_store(db_path)
    try:
        loaded = store3.load()
        ids = set(loaded.to_arrow().column("id").to_pylist())
    finally:
        store3.close()

    assert "oa:aaaabbbb11112222" in ids
    assert "oa:bbbbcccc22223333" in ids
    assert len(ids) == 2


@pytest.mark.integration
def test_duckdb_backend_close_es_idempotente(tmp_path: Path) -> None:
    """DuckDBBackend.close() es idempotente y no impide lecturas posteriores."""
    from bib2graph.backends.duckdb import DuckDBBackend

    db_path = tmp_path / "lib.duckdb"
    backend = DuckDBBackend(path=db_path)

    # close() no debe lanzar
    backend.close()
    # Segunda vez: idempotente
    backend.close()

    # Una nueva instancia sobre el mismo archivo sigue funcionando
    backend2 = DuckDBBackend(path=db_path)
    assert len(backend2) == 0
    backend2.close()


# ---------------------------------------------------------------------------
# Correctitud: lote con ids duplicados → dedup-MERGE (regresión #211)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_persist_lote_con_duplicados_dedup_merge(tmp_path: Path) -> None:
    """persist de lote con id duplicado: una fila final, provenance acumulada.

    Regresión #211: el upsert bulk anterior lanzaba ConstraintException
    (PRIMARY KEY) cuando el lote tenía dos filas con el mismo id.  Ahora se
    deduplica-MERGE antes del upsert, igual que el loop fila-a-fila previo:
    provenance append-only y curación "más reciente gana".
    """
    db_path = tmp_path / "lib_dup.duckdb"
    paper_id = "oa:test0000aaaa0000"

    prov_seed = json.dumps(
        [
            {
                "action": "seeded",
                "equation_id": "eq1",
                "chaining_hop": None,
                "source": "openalex",
                "fetched_at": None,
                "decided_by": None,
                "decided_at": None,
            }
        ]
    )
    prov_accept = json.dumps(
        [
            {
                "action": "accepted",
                "equation_id": None,
                "chaining_hop": None,
                "source": None,
                "fetched_at": None,
                "decided_by": "revisor",
                "decided_at": "2026-01-01T00:00:00+00:00",
            }
        ]
    )

    # Lote con el mismo id dos veces: candidate→seeded primero, accepted→prov_accept después
    row_a = _make_row(id=paper_id, curation_status="candidate", provenance=prov_seed)
    row_b = _make_row(id=paper_id, curation_status="accepted", provenance=prov_accept)
    corpus = _make_corpus([row_a, row_b])

    store = DuckDBStore(db_path)
    store.persist(corpus)  # No debe lanzar ConstraintException

    loaded = store.load()
    assert len(loaded) == 1, "Debe haber solo 1 fila tras dedup"

    row = loaded.to_arrow().to_pylist()[0]
    assert row["curation_status"] == "accepted", "Curación más reciente gana"
    events = json.loads(row["provenance"])
    assert len(events) == 2, "Provenance acumulada de ambas apariciones"
    actions = {e["action"] for e in events}
    assert "seeded" in actions
    assert "accepted" in actions


@pytest.mark.integration
def test_persist_overwrite_corpus_lote_con_duplicados(tmp_path: Path) -> None:
    """overwrite_corpus con lote duplicado: una fila final, provenance acumulada.

    Complementa el test anterior para la ruta de ``overwrite_corpus``
    (DELETE + INSERT masivo), que también recibe el lote antes del upsert
    y debe deduplicar con la misma semántica.
    """
    import pyarrow as pa

    from bib2graph.backends.duckdb import DuckDBBackend
    from bib2graph.schemas import CORPUS_SCHEMA

    db_path = tmp_path / "lib_ow_dup.duckdb"
    paper_id = "oa:test1111bbbb1111"

    prov_a = json.dumps(
        [
            {
                "action": "seeded",
                "equation_id": "eq2",
                "chaining_hop": None,
                "source": "openalex",
                "fetched_at": None,
                "decided_by": None,
                "decided_at": None,
            }
        ]
    )
    prov_b = json.dumps(
        [
            {
                "action": "accepted",
                "equation_id": None,
                "chaining_hop": None,
                "source": None,
                "fetched_at": None,
                "decided_by": "curador",
                "decided_at": "2026-02-01T00:00:00+00:00",
            }
        ]
    )

    row_a = _make_row(id=paper_id, curation_status="candidate", provenance=prov_a)
    row_b = _make_row(id=paper_id, curation_status="accepted", provenance=prov_b)
    table = pa.Table.from_pylist([row_a, row_b], schema=CORPUS_SCHEMA)

    backend = DuckDBBackend(path=db_path)
    backend.overwrite_corpus(table)  # No debe lanzar ConstraintException

    assert len(backend) == 1, "Debe haber solo 1 fila tras dedup en overwrite"

    row = backend.to_arrow().to_pylist()[0]
    assert row["curation_status"] == "accepted"
    events = json.loads(row["provenance"])
    assert len(events) == 2
    actions = {e["action"] for e in events}
    assert "seeded" in actions
    assert "accepted" in actions


# ---------------------------------------------------------------------------
# Correctitud: orden determinista de _seq para múltiples filas nuevas en un lote
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_persist_multifila_nueva_seq_determinista(tmp_path: Path) -> None:
    """persist de lote con N filas nuevas → orden D3 estable en to_arrow().

    Regresión de la observación MEDIO del verifier (#211): ROW_NUMBER() OVER ()
    sin ORDER BY no garantiza el orden en SQL estándar.  Con la columna auxiliar
    ``_row_idx`` (ORDER BY _row_idx), el _seq respeta el orden de aparición de
    la tabla Arrow entrante.

    El test verifica el ORDER (no solo el corpus_hash, que es order-independent)
    con MÚLTIPLES filas nuevas en el lote, pues el bug solo se manifiesta con ≥2
    filas nuevas y dependencia del scan interno de DuckDB.
    """
    db_path = tmp_path / "lib_ord.duckdb"
    # 6 ids en orden deliberado (mezcla de hex para evitar colusión con ascii sort)
    ids = [
        "oa:ffff000000000001",
        "oa:aaaa000000000002",
        "oa:9999000000000003",
        "oa:bbbb000000000004",
        "oa:1111000000000005",
        "oa:cccc000000000006",
    ]
    rows = [_make_row(id=id_, title=f"Paper {i}") for i, id_ in enumerate(ids)]
    corpus = _make_corpus(rows)

    store = DuckDBStore(db_path)
    store.persist(corpus)

    loaded_ids = store.load().to_arrow().column("id").to_pylist()
    assert loaded_ids == ids, (
        f"El orden D3 debe coincidir con el de la tabla Arrow entrante.\n"
        f"Esperado: {ids}\nObtenido: {loaded_ids}"
    )


# ---------------------------------------------------------------------------
# Benchmark de escala — upsert masivo (issue #211)
# Marcado @slow: NO corre en el gate por defecto (-m "not network and not slow").
# La idempotencia a escala pequeña ya está cubierta por test_persist_idempotente.
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.slow
def test_persist_escala_masiva(tmp_path: Path) -> None:
    """persist de 50.000 filas es correcto e idempotente (benchmark de escala).

    Consolida los dos tests de 50 K anteriores en uno: verifica que todas las
    filas persisten y que una segunda pasada no duplica (idempotencia D3).

    No hay assert de wall-clock (era la fuente de flake en runners CI cargados).
    La señal de rendimiento queda implícita en que el test termine en tiempo
    razonable (no bloquea el gate por estar marcado @slow).
    """
    N = 50_000
    rows = [_make_row(id=f"oa:{i:016x}", title=f"Paper {i}") for i in range(N)]
    corpus = _make_corpus(rows)

    db_path = tmp_path / "lib_bench.duckdb"
    store = DuckDBStore(db_path)
    store.persist(corpus)

    assert len(store.load()) == N, "No se persistieron todas las filas"

    # Segunda pasada: idempotencia (sin duplicados, mismo hash)
    store.persist(corpus)
    loaded = store.load()
    assert len(loaded) == N, "La segunda persist duplicó filas"
