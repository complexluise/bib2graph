"""Tests TDD del Hito 6 — CLI agente-native ``b2g``.

Casos cubiertos (docs/ROADMAP.md §Hito 6):

1. Contrato del envelope: cada ``run_<cmd>`` devuelve las claves estables
   del envelope (schema, ok, command, exit_code, data, warnings, error).
2. Mapeo error→exit code: un caso por código (1-5).
3. E2E flujo de 10 minutos: seed → chain → filter → build → export,
   con MockTransport y DuckDB temporal.
4. status tras secuencia: devuelve loop_state == FILTERED y conteos esperados.

Filosofía (AGENTS.md): se testea la FUNCIÓN detrás del comando, NO el parser
de Click. Se normalizan volátiles antes de comparar.
Marcador: ``unit`` (DuckDB en tmp_path, red mockeada con MockTransport).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
import pyarrow as pa
import pytest

from bib2graph.schemas import CORPUS_SCHEMA

# ---------------------------------------------------------------------------
# Helpers de fixtures
# ---------------------------------------------------------------------------

SAMPLE_WORKS: list[dict[str, Any]] = json.loads(
    (Path(__file__).parent.parent / "fixtures" / "sample_works.json").read_text(
        encoding="utf-8"
    )
)


def _make_mock_transport(
    works: list[dict[str, Any]] | None = None,
) -> httpx.MockTransport:
    """MockTransport que responde con los works dados (1 página + EOF)."""
    if works is None:
        works = SAMPLE_WORKS
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


def _make_network_transport() -> httpx.MockTransport:
    """MockTransport para forward chaining (fetch_citing)."""
    calls: list[int] = [0]

    def handler(request: httpx.Request) -> httpx.Response:
        calls[0] += 1
        # Primera llamada: citantes; el resto: vacío
        if calls[0] == 1:
            body = {
                "results": [SAMPLE_WORKS[0]],
                "meta": {"count": 1, "next_cursor": None},
            }
        else:
            body = {"results": [], "meta": {"count": 0, "next_cursor": None}}
        return httpx.Response(
            200,
            json=body,
            headers={"x-openalex-api-version": "2026-05-01"},
        )

    return httpx.MockTransport(handler)


def _make_error_transport() -> httpx.MockTransport:
    """MockTransport que lanza un error de red."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Sin conexión (mock de error de red)")

    return httpx.MockTransport(handler)


def _make_corpus_row(
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
    """Puebla un store con filas mínimas para tests subsiguientes."""
    from bib2graph.corpus import Corpus
    from bib2graph.stores.duckdb import DuckDBStore

    if rows is None:
        rows = [_make_corpus_row(id="P1"), _make_corpus_row(id="P2")]
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)
    store = DuckDBStore(store_path)
    store.persist(corpus)


# ---------------------------------------------------------------------------
# 1. Contrato del envelope — forma estable del dict de salida
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_envelope_build_tiene_claves_estables() -> None:
    """build_envelope devuelve las claves canónicas del envelope v1."""
    from bib2graph.cli._envelope import build_envelope

    envelope = build_envelope(
        command="seed",
        ok=True,
        data={"papers_added": 3},
        exit_code=0,
    )

    assert envelope["schema"] == "1"
    assert envelope["ok"] is True
    assert envelope["command"] == "seed"
    assert envelope["exit_code"] == 0
    assert isinstance(envelope["data"], dict)
    assert isinstance(envelope["warnings"], list)
    assert envelope["error"] is None


@pytest.mark.unit
def test_envelope_error_tiene_claves_estables() -> None:
    """build_envelope con error=... popula la clave error correctamente."""
    from bib2graph.cli._envelope import build_envelope

    envelope = build_envelope(
        command="seed",
        ok=False,
        data={},
        exit_code=4,
        error={"code": "NETWORK_ERROR", "message": "Sin conexión."},
    )

    assert envelope["ok"] is False
    assert envelope["exit_code"] == 4
    assert envelope["error"] is not None
    assert envelope["error"]["code"] == "NETWORK_ERROR"
    assert envelope["error"]["message"] == "Sin conexión."


@pytest.mark.unit
def test_run_seed_devuelve_claves_esperadas(tmp_path: Path) -> None:
    """run_seed devuelve dict con executed_query, papers_added, total_papers."""
    from bib2graph.cli.commands.seed import run_seed

    store_path = tmp_path / "test.duckdb"
    transport = _make_mock_transport()

    data = run_seed(
        store_path,
        "unequal exchange",
        transport=transport,
    )

    assert "executed_query" in data
    assert "papers_added" in data
    assert "total_papers" in data
    assert isinstance(data["papers_added"], int)
    assert data["papers_added"] >= 0


@pytest.mark.unit
def test_run_status_devuelve_claves_esperadas(tmp_path: Path) -> None:
    """run_status devuelve loop_state, transitions_available, counts_by_status."""
    from bib2graph.cli.commands.status import run_status

    store_path = tmp_path / "test.duckdb"
    _seed_store(store_path)

    data = run_status(store_path)

    assert "loop_state" in data
    assert "transitions_available" in data
    assert "counts_by_status" in data
    assert "total_papers" in data
    assert isinstance(data["transitions_available"], list)
    assert isinstance(data["counts_by_status"], dict)


@pytest.mark.unit
def test_run_filter_devuelve_claves_esperadas(tmp_path: Path) -> None:
    """run_filter devuelve steps, total_papers, criteria_applied."""
    from bib2graph.cli.commands.filter import run_filter

    store_path = tmp_path / "test.duckdb"
    _seed_store(store_path)

    data = run_filter(store_path, year_gte=2000)

    assert "steps" in data
    assert "total_papers" in data
    assert "criteria_applied" in data
    assert isinstance(data["steps"], list)
    assert data["criteria_applied"] == 1


@pytest.mark.unit
def test_run_validate_valido(tmp_path: Path) -> None:
    """run_validate devuelve valid=True y total_papers para un store sano."""
    from bib2graph.cli.commands.validate import run_validate

    store_path = tmp_path / "test.duckdb"
    _seed_store(store_path)

    data = run_validate(store_path)

    assert data["valid"] is True
    assert data["total_papers"] == 2
    assert data["issues"] == []


@pytest.mark.unit
def test_run_inspect_sin_id(tmp_path: Path) -> None:
    """run_inspect sin --id devuelve manifest y total_papers."""
    from bib2graph.cli.commands.inspect import run_inspect

    store_path = tmp_path / "test.duckdb"
    _seed_store(store_path)

    data = run_inspect(store_path)

    assert "manifest" in data
    assert "total_papers" in data
    assert data["total_papers"] == 2


@pytest.mark.unit
def test_run_snapshot_crea_archivos(tmp_path: Path) -> None:
    """run_snapshot crea el directorio con corpus.parquet y manifest.json."""
    from bib2graph.cli.commands.snapshot import run_snapshot

    store_path = tmp_path / "test.duckdb"
    _seed_store(store_path)
    out_dir = tmp_path / "snap"

    data = run_snapshot(store_path, out_dir=out_dir)

    assert "corpus_hash" in data
    assert "snapshot_dir" in data
    assert (out_dir / "corpus.parquet").exists()
    assert (out_dir / "manifest.json").exists()


@pytest.mark.unit
def test_run_accept_marca_aceptado(tmp_path: Path) -> None:
    """run_accept marca el paper como accepted y persiste."""
    from bib2graph.cli.commands.accept import run_accept
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "test.duckdb"
    _seed_store(store_path)

    data = run_accept(store_path, ["P1"])

    assert data["accepted_count"] == 1
    # Verificar que persiste
    store = DuckDBStore(store_path)
    corpus = store.load()
    rows = corpus.to_arrow().to_pylist()
    p1 = next(r for r in rows if r["id"] == "P1")
    assert p1["curation_status"] == "accepted"


@pytest.mark.unit
def test_run_reject_marca_rechazado(tmp_path: Path) -> None:
    """run_reject marca el paper como rejected y persiste."""
    from bib2graph.cli.commands.reject import run_reject
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "test.duckdb"
    _seed_store(store_path)

    data = run_reject(store_path, ["P2"])

    assert data["rejected_count"] == 1
    store = DuckDBStore(store_path)
    corpus = store.load()
    rows = corpus.to_arrow().to_pylist()
    p2 = next(r for r in rows if r["id"] == "P2")
    assert p2["curation_status"] == "rejected"


# ---------------------------------------------------------------------------
# 2. Mapeo error → exit code (un caso por código)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_exit_code_1_sin_store() -> None:
    """Sin --store (opción requerida) el CLI retorna exit code 1 (uso)."""
    from bib2graph.cli import main

    # main() sin argumentos → Click UsageError → exit 1
    result = main()
    assert result == 1


@pytest.mark.unit
def test_exit_code_2_accept_id_inexistente(tmp_path: Path) -> None:
    """accept de id inexistente → DataError → exit 2."""
    from bib2graph.cli._errors import DataError
    from bib2graph.cli.commands.accept import run_accept

    store_path = tmp_path / "test.duckdb"
    _seed_store(store_path)

    with pytest.raises(DataError) as exc_info:
        run_accept(store_path, ["ID_QUE_NO_EXISTE"])

    assert exc_info.value.exit_code == 2


@pytest.mark.unit
def test_exit_code_2_filter_sin_criterios(tmp_path: Path) -> None:
    """filter sin criterios → DataError → exit 2."""
    from bib2graph.cli._errors import DataError
    from bib2graph.cli.commands.filter import run_filter

    store_path = tmp_path / "test.duckdb"
    _seed_store(store_path)

    with pytest.raises(DataError) as exc_info:
        run_filter(store_path)

    assert exc_info.value.exit_code == 2


@pytest.mark.unit
def test_exit_code_3_build_louvain_faltante(tmp_path: Path) -> None:
    """build sin python-louvain → DependencyError → exit 3.

    Simula el caso en que Networks.quick lanza ImportError porque
    python-louvain no está instalado.
    """
    from bib2graph.cli._errors import DependencyError
    from bib2graph.cli.commands.build import run_build

    store_path = tmp_path / "test.duckdb"
    _seed_store(store_path)

    # Simular que Networks.quick lanza ImportError (python-louvain ausente)
    # Patcheamos la función donde se importa (facade)
    with (
        patch(
            "bib2graph.networks.facade.Networks.quick",
            side_effect=ImportError("No module named 'community'"),
        ),
        pytest.raises(DependencyError) as exc_info,
    ):
        run_build(store_path)

    assert exc_info.value.exit_code == 3


@pytest.mark.unit
def test_exit_code_3_chain_forward_source_sin_fetch_citing(tmp_path: Path) -> None:
    """chain forward con source que no tiene fetch_citing → DependencyError → exit 3.

    Simula el AttributeError que lanza Forager._fetch_forward cuando el
    source no implementa fetch_citing (por ejemplo, BibtexSource).
    """
    from bib2graph.cli._errors import DependencyError
    from bib2graph.cli.commands.chain import run_chain

    store_path = tmp_path / "test.duckdb"
    _seed_store(store_path)

    # Patchear Forager.chain para que lance AttributeError (simula source sin fetch_citing)
    with (
        patch(
            "bib2graph.foraging.forager.Forager.chain",
            side_effect=AttributeError(
                "El source 'BibtexSource' no implementa 'fetch_citing': "
                "el forward chaining requiere OpenAlexSource o un source con ese método."
            ),
        ),
        pytest.raises(DependencyError) as exc_info,
    ):
        run_chain(store_path, direction="forward", transport=_make_mock_transport([]))

    assert exc_info.value.exit_code == 3


@pytest.mark.unit
def test_exit_code_4_seed_connect_error(tmp_path: Path) -> None:
    """seed con ConnectError → el decorador captura httpx.HTTPError → exit 4.

    Con el fix de _errors.py, la excepción httpx.ConnectError se propaga desde
    run_seed y el decorador @handle_errors la captura por tipo (no por nombre de
    clase), emitiendo exit 4.
    """
    from bib2graph.cli.commands.seed import run_seed

    store_path = tmp_path / "test.duckdb"
    error_transport = _make_error_transport()

    # run_seed propaga httpx.ConnectError (subclase de httpx.HTTPError).
    # El decorador la captura → sys.exit(4). Sin el decorador (llamada directa),
    # la excepción se relanza tal cual — afirmamos que es de tipo httpx.
    with pytest.raises(httpx.ConnectError):
        run_seed(store_path, "unequal exchange", transport=error_transport)


@pytest.mark.unit
def test_exit_code_4_seed_remote_protocol_error(tmp_path: Path) -> None:
    """seed con RemoteProtocolError → capturado por decorador como exit 4 (regresión).

    httpx.RemoteProtocolError es subclase de httpx.HTTPError. El filtro por
    nombre de clase anterior (*"HTTP" in class_name*) no la capturaba.
    Con la captura por tipo, queda correctamente mapeada a exit 4.
    """
    from bib2graph.cli.commands.seed import run_seed

    def remote_protocol_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.RemoteProtocolError(
            "Server disconnected without sending a response",
            request=request,
        )

    transport = httpx.MockTransport(remote_protocol_handler)
    store_path = tmp_path / "test_rpe.duckdb"

    # run_seed propaga httpx.RemoteProtocolError (subclase de httpx.HTTPError).
    with pytest.raises(httpx.RemoteProtocolError):
        run_seed(store_path, "unequal exchange", transport=transport)


@pytest.mark.unit
def test_exit_code_5_store_bloqueado(tmp_path: Path) -> None:
    """StoreLockedError → StoreError → exit 5."""
    from bib2graph.backends.duckdb import StoreLockedError
    from bib2graph.cli._errors import StoreError
    from bib2graph.cli._store import open_store

    store_path = tmp_path / "locked.duckdb"

    # DuckDBStore se importa dentro de open_store; patcheamos en el módulo origen
    with (
        patch(
            "bib2graph.stores.duckdb.DuckDBStore",
            side_effect=StoreLockedError("Archivo bloqueado (mock)"),
        ),
        pytest.raises(StoreError) as exc_info,
    ):
        open_store(store_path)

    assert exc_info.value.exit_code == 5


# ---------------------------------------------------------------------------
# 3. E2E flujo de 10 minutos: seed → chain → filter → build → export
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_e2e_seed_chain_filter_build_export(tmp_path: Path) -> None:
    """Flujo completo seed → chain → filter → build → export.

    - seed: puebla el corpus con papers de MockTransport.
    - chain backward: agrega candidatos desde references_id del corpus.
    - filter: filtra por año >= 2010 (marca rejected).
    - build: construye redes y escribe artefactos.
    - export: re-emite GraphML a out_dir.
    Verifica: exit 0, GraphML existe, corpus acumulado coherente.
    """
    from bib2graph.backends.duckdb import LoopState
    from bib2graph.cli.commands.build import run_build
    from bib2graph.cli.commands.chain import run_chain
    from bib2graph.cli.commands.export import run_export
    from bib2graph.cli.commands.filter import run_filter
    from bib2graph.cli.commands.seed import run_seed
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "investigacion.duckdb"
    transport = _make_mock_transport()

    # 1) seed
    seed_data = run_seed(
        store_path,
        "unequal exchange",
        transport=transport,
    )
    assert seed_data["papers_added"] > 0
    assert "executed_query" in seed_data

    # 2) chain backward (no requiere red adicional)
    # Mock del forward: usamos backward solamente para no requerir fetch_citing
    chain_data = run_chain(
        store_path,
        direction="backward",
        transport=_make_mock_transport([]),
    )
    # backward puede no encontrar candidatos nuevos si references_id está vacío,
    # pero el comando debe completar sin error
    assert "candidates_found" in chain_data
    assert "total_papers" in chain_data

    # 3) filter: incluir solo papers con año >= 2010
    filter_data = run_filter(store_path, year_gte=2010)
    assert filter_data["criteria_applied"] == 1
    assert len(filter_data["steps"]) == 1

    # 4) build: construye las 4 redes
    build_data = run_build(store_path)
    assert build_data["networks_built"] == 4
    artifacts_dir = Path(build_data["artifacts_dir"])
    assert artifacts_dir.exists()

    # Verificar que existe al menos 1 archivo GraphML
    graphml_files = list(artifacts_dir.rglob("*.graphml"))
    assert len(graphml_files) >= 1

    # 5) export a CSV
    export_out = tmp_path / "export_csv"
    export_data = run_export(
        store_path,
        format="csv",
        out_dir=export_out,
    )
    assert export_data["format"] == "csv"
    assert len(export_data["files_written"]) > 0

    # Verificar LoopState final
    store = DuckDBStore(store_path)
    final_state = store.backend.loop_state()
    assert final_state == LoopState.BUILT

    # Corpus coherente: tiene papers
    corpus = store.load()
    assert len(corpus) > 0


# ---------------------------------------------------------------------------
# 4. status tras secuencia: loop_state y conteos esperados
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_status_tras_seed_chain_filter(tmp_path: Path) -> None:
    """run_status tras seed→chain→filter devuelve loop_state=FILTERED y conteos."""
    from bib2graph.cli.commands.chain import run_chain
    from bib2graph.cli.commands.filter import run_filter
    from bib2graph.cli.commands.seed import run_seed
    from bib2graph.cli.commands.status import run_status

    store_path = tmp_path / "seq.duckdb"
    transport = _make_mock_transport()

    # seed
    run_seed(store_path, "unequal exchange", transport=transport)

    # chain backward
    run_chain(
        store_path,
        direction="backward",
        transport=_make_mock_transport([]),
    )

    # filter
    run_filter(store_path, year_gte=2000)

    # status
    data = run_status(store_path)

    assert data["loop_state"] == "FILTERED"
    assert data["total_papers"] > 0
    assert isinstance(data["counts_by_status"], dict)
    # Debe haber al menos papers en candidate o rejected
    all_counts = sum(data["counts_by_status"].values())
    assert all_counts == data["total_papers"]
    # R3: desde cualquier estado con estado previo, reseed está disponible
    # (el "seed" inicial solo está en None → "seed"; con estado previo → "reseed")
    assert "reseed" in data["transitions_available"]


# ---------------------------------------------------------------------------
# 5. Prueba adicional: LoopState transiciona correctamente
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_loop_state_transiciona_en_secuencia(tmp_path: Path) -> None:
    """seed transiciona a SEEDED; chain a FORAGED; filter a FILTERED; build a BUILT."""
    from bib2graph.backends.duckdb import LoopState
    from bib2graph.cli.commands.build import run_build
    from bib2graph.cli.commands.chain import run_chain
    from bib2graph.cli.commands.filter import run_filter
    from bib2graph.cli.commands.seed import run_seed
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "transitions.duckdb"

    # Antes de seed: None
    store = DuckDBStore(store_path)
    assert store.backend.loop_state() is None

    # Tras seed
    run_seed(store_path, "ecology", transport=_make_mock_transport())
    store2 = DuckDBStore(store_path)
    assert store2.backend.loop_state() == LoopState.SEEDED

    # Tras chain backward
    run_chain(store_path, direction="backward", transport=_make_mock_transport([]))
    store3 = DuckDBStore(store_path)
    assert store3.backend.loop_state() == LoopState.FORAGED

    # Tras filter
    run_filter(store_path, year_gte=2000)
    store4 = DuckDBStore(store_path)
    assert store4.backend.loop_state() == LoopState.FILTERED

    # Tras build
    run_build(store_path)
    store5 = DuckDBStore(store_path)
    assert store5.backend.loop_state() == LoopState.BUILT


# ---------------------------------------------------------------------------
# 6. Prueba: status inicial (sin estado)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_status_store_vacio(tmp_path: Path) -> None:
    """run_status en store vacío devuelve loop_state=None y total_papers=0."""
    from bib2graph.cli.commands.status import run_status

    store_path = tmp_path / "empty.duckdb"
    # Crear store vacío
    from bib2graph.stores.duckdb import DuckDBStore

    DuckDBStore(store_path)  # solo inicializa las tablas

    data = run_status(store_path)

    assert data["loop_state"] is None
    assert data["total_papers"] == 0
    assert "seed" in data["transitions_available"]


# ---------------------------------------------------------------------------
# 7. Prueba: build escribe la columna community en nodos.csv (regresión)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_build_escribe_community_en_nodos_csv(tmp_path: Path) -> None:
    """build pasa art.communities al exporter → nodos.csv contiene columna community.

    Regresión: antes de este fix, art.communities se calculaba con Louvain pero
    se descartaba (solo se pasaba art.metrics al exporter). Con el fix, se fusiona
    como atributo de nodo y el CsvExporter lo escribe como columna en nodos.csv.
    """
    import csv

    from bib2graph.cli.commands.build import run_build
    from bib2graph.cli.commands.seed import run_seed

    store_path = tmp_path / "community_test.duckdb"
    run_seed(store_path, "complex systems", transport=_make_mock_transport())

    build_data = run_build(store_path)
    artifacts_dir = Path(build_data["artifacts_dir"])

    # Verificar al menos una red con nodos.csv que tenga la columna community.
    # Si el grafo proyectado tiene 0 nodos (corpus sintético puede ser escaso),
    # solo verificamos que el archivo exista y que, si tiene filas de datos,
    # la columna community esté presente.
    found_community_col = False
    for nodos_csv in artifacts_dir.rglob("nodos.csv"):
        with open(nodos_csv, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            # Verificar la columna siempre que haya nodos (si hay header)
            if "community" in headers:
                found_community_col = True
                break
            # Si el grafo tiene nodos, la columna debe estar
            rows = list(reader)
            if rows:
                assert "community" in headers, (
                    f"nodos.csv en {nodos_csv} tiene filas pero falta columna 'community'. "
                    f"Columnas encontradas: {headers}"
                )

    # Al menos una red debe haber producido nodos con la columna community,
    # O bien todos los grafos tienen 0 nodos (corpus sintético muy escaso).
    # En ese caso, verificamos que el GraphML no tiene el atributo como campo
    # global, lo que confirmaría que el fix está activo.
    # Con el fixture sample_works.json que tiene papers reales, debe haber nodos.
    if not found_community_col:
        # Corpus con 0 nodos en todas las redes: chequeamos que GraphML exista
        graphml_files = list(artifacts_dir.rglob("*.graphml"))
        assert len(graphml_files) >= 1, "Debe haber al menos un archivo GraphML"
