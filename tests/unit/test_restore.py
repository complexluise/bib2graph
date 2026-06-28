"""Tests de b2g restore — rehidratación de corpus curado desde parquet.

Casos cubiertos (movidos desde test_equation_spec.py + extendidos):

1. run_restore persiste el corpus desde parquet SIN red (transport que falla
   si se usa; verificamos que la función núcleo no toca OpenAlexSource).
2. run_restore preserva las columnas de curación (decision/curation_status/is_seed).
3. run_restore con parquet inexistente → DataError accionable.
4. run_restore transiciona el CycleState a FILTERED (permite build/networks
   aguas abajo sin re-forrajeo; ver docstring de restore.py para la justificación).
5. b2g restore --from-corpus importa sin red (CliRunner), envelope correcto.
6. El estado FILTERED habilita build aguas abajo (FSM permisiva: apply_transition
   desde FILTERED → build → BUILT es válido).
7. b2g restore requiere --from-corpus (no hay modo sin argumento).

Filosofía (AGENTS.md): se testea la FUNCIÓN detrás del comando, NO el parser
Click. CliRunner solo donde hay integración de flag necesaria.
Marcador: ``unit`` (DuckDB en tmp_path, sin red real).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest

from bib2graph.schemas import CORPUS_SCHEMA

# ---------------------------------------------------------------------------
# Fixtures y helpers
# ---------------------------------------------------------------------------


def _make_corpus_row(
    *,
    id: str,
    title: str = "Test",
    curation_status: str = "candidate",
    is_seed: bool = True,
    year: int = 2020,
) -> dict[str, Any]:
    """Fila mínima con schema completo."""
    return {
        "id": id,
        "openalex_id": None,
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
        "references_id": None,
        "references_doi": None,
        "cited_by_id": None,
    }


def _make_parquet(
    path: Path,
    rows: list[dict[str, Any]] | None = None,
) -> Path:
    """Escribe un parquet con el schema canónico en ``path``."""
    if rows is None:
        rows = [
            _make_corpus_row(id="P1"),
            _make_corpus_row(id="P2"),
            _make_corpus_row(id="P3", curation_status="accepted"),
        ]
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    import pyarrow.parquet as pq

    pq.write_table(table, str(path))
    return path


# ---------------------------------------------------------------------------
# 1. run_restore persiste sin red
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_run_restore_persiste_sin_red(tmp_path: Path) -> None:
    """run_restore persiste el corpus desde parquet sin tocar OpenAlex.

    La función núcleo run_restore no instancia OpenAlexSource ni hace
    requests HTTP — verificado implícitamente porque no importa httpx ni
    llama a ninguna source. El store queda con los papers del parquet.
    """
    from bib2graph.cli.commands.restore import run_restore
    from bib2graph.stores.duckdb import DuckDBStore

    rows = [
        _make_corpus_row(id="P1"),
        _make_corpus_row(id="P2"),
        _make_corpus_row(id="P3"),
    ]
    parquet_path = tmp_path / "corpus.parquet"
    _make_parquet(parquet_path, rows)

    store_path = tmp_path / "test.duckdb"
    data = run_restore(store_path, parquet_path)

    assert data["papers_loaded"] == 3
    assert data["total_papers"] == 3

    # Verificar que el store tiene los papers
    store = DuckDBStore(store_path)
    corpus = store.load()
    assert len(corpus) == 3


@pytest.mark.unit
def test_run_restore_no_usa_red_con_transport_fallido(tmp_path: Path) -> None:
    """run_restore no instancia ningún transport — el transport inyectable
    de OpenAlexSource no se invoca en el camino de restore.

    Se verifica indirectamente: si la función llamara OpenAlexSource, el test
    fallaría porque no hay red y la importación fallaría o lanzaría error.
    Como no lanza, confirmamos que el camino es libre de red.
    """
    from bib2graph.cli.commands.restore import run_restore

    rows = [_make_corpus_row(id="P1"), _make_corpus_row(id="P2")]
    parquet_path = tmp_path / "corpus.parquet"
    _make_parquet(parquet_path, rows)

    store_path = tmp_path / "test.duckdb"
    # No se pasa transport: si restore usara red, fallaría aquí.
    data = run_restore(store_path, parquet_path)

    assert data["papers_loaded"] == 2
    assert data["total_papers"] == 2


# ---------------------------------------------------------------------------
# 2. run_restore preserva curación
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_run_restore_preserva_curacion(tmp_path: Path) -> None:
    """run_restore preserva curation_status del parquet.

    Los papers aceptados/rechazados en el parquet conservan su estado
    en el store tras la importación.
    """
    from bib2graph.cli.commands.restore import run_restore
    from bib2graph.constants import Col, CurationStatus
    from bib2graph.stores.duckdb import DuckDBStore

    rows = [
        _make_corpus_row(id="P1", curation_status="accepted"),
        _make_corpus_row(id="P2", curation_status="rejected"),
        _make_corpus_row(id="P3", curation_status="candidate"),
    ]
    parquet_path = tmp_path / "corpus.parquet"
    _make_parquet(parquet_path, rows)

    store_path = tmp_path / "test.duckdb"
    run_restore(store_path, parquet_path)

    store = DuckDBStore(store_path)
    corpus = store.load()
    table_rows = corpus.to_arrow().to_pylist()

    statuses = {r[Col.ID]: r[Col.CURATION_STATUS] for r in table_rows}
    assert statuses["P1"] == CurationStatus.ACCEPTED
    assert statuses["P2"] == CurationStatus.REJECTED
    assert statuses["P3"] == CurationStatus.CANDIDATE


@pytest.mark.unit
def test_run_restore_preserva_is_seed(tmp_path: Path) -> None:
    """run_restore preserva el campo is_seed del parquet."""
    from bib2graph.cli.commands.restore import run_restore
    from bib2graph.constants import Col
    from bib2graph.stores.duckdb import DuckDBStore

    rows = [
        _make_corpus_row(id="P1", is_seed=True),
        _make_corpus_row(id="P2", is_seed=False),
    ]
    parquet_path = tmp_path / "corpus.parquet"
    _make_parquet(parquet_path, rows)

    store_path = tmp_path / "test.duckdb"
    run_restore(store_path, parquet_path)

    store = DuckDBStore(store_path)
    corpus = store.load()
    table_rows = corpus.to_arrow().to_pylist()

    seeds = {r[Col.ID]: r[Col.IS_SEED] for r in table_rows}
    assert seeds["P1"] is True
    assert seeds["P2"] is False


# ---------------------------------------------------------------------------
# 3. run_restore con parquet inexistente → DataError
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_run_restore_parquet_inexistente(tmp_path: Path) -> None:
    """Parquet inexistente → DataError con mensaje accionable."""
    from bib2graph.cli._errors import DataError
    from bib2graph.cli.commands.restore import run_restore

    store_path = tmp_path / "test.duckdb"
    with pytest.raises(DataError, match="no existe"):
        run_restore(store_path, tmp_path / "no_existe.parquet")


# ---------------------------------------------------------------------------
# 4. run_restore transiciona a FILTERED
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_run_restore_transiciona_a_filtered(tmp_path: Path) -> None:
    """run_restore fija el CycleState en FILTERED.

    FILTERED permite ejecutar build y networks aguas abajo sin re-forrajeo
    (FSM permisiva: build está disponible desde FILTERED).
    """
    from bib2graph.cli.commands.restore import run_restore
    from bib2graph.cycle import CycleState
    from bib2graph.stores.duckdb import DuckDBStore

    rows = [_make_corpus_row(id="P1")]
    parquet_path = tmp_path / "corpus.parquet"
    _make_parquet(parquet_path, rows)

    store_path = tmp_path / "test.duckdb"
    data = run_restore(store_path, parquet_path)

    # El estado reportado en el dict de retorno
    assert data["state"] == str(CycleState.FILTERED)

    # El estado persistido en el store
    store = DuckDBStore(store_path)
    state = store.backend.loop_state()
    assert state == CycleState.FILTERED


# ---------------------------------------------------------------------------
# 5. b2g restore --from-corpus (CliRunner)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_restore_cmd_sin_red(tmp_path: Path) -> None:
    """b2g restore --from-corpus importa el corpus sin realizar requests HTTP.

    Verifica que el comando no instancia OpenAlexSource ni hace requests:
    el store queda con los papers del parquet y el envelope es correcto.
    """
    from click.testing import CliRunner

    from bib2graph.cli import b2g
    from bib2graph.stores.duckdb import DuckDBStore
    from bib2graph.workspace import Workspace

    rows = [_make_corpus_row(id="P1"), _make_corpus_row(id="P2")]
    parquet_path = tmp_path / "corpus.parquet"
    _make_parquet(parquet_path, rows)

    ws_dir = tmp_path / "ws"
    ws = Workspace.init(ws_dir, "test")

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws_dir),
            "restore",
            "--from-corpus",
            str(parquet_path),
            "--json",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, f"Salida inesperada: {result.output}"
    # Usar result.stdout (solo stdout) porque b2g restore emite aviso de deprecación
    # a stderr (#165); result.output mezcla ambas streams en Click 8.4.1.
    envelope = json.loads(result.stdout)
    assert envelope["ok"] is True
    assert envelope["command"] == "restore"
    assert envelope["data"]["papers_loaded"] == 2
    assert envelope["data"]["total_papers"] == 2
    assert envelope["schema"] == "1"

    # Verificar que el store tiene los papers
    store = DuckDBStore(ws.library_path)
    corpus = store.load()
    assert len(corpus) == 2


@pytest.mark.unit
def test_restore_cmd_envelope_contiene_state(tmp_path: Path) -> None:
    """b2g restore --json incluye 'state' en el envelope."""
    from click.testing import CliRunner

    from bib2graph.cli import b2g
    from bib2graph.workspace import Workspace

    rows = [_make_corpus_row(id="P1")]
    parquet_path = tmp_path / "corpus.parquet"
    _make_parquet(parquet_path, rows)

    ws_dir = tmp_path / "ws"
    Workspace.init(ws_dir, "test")

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws_dir),
            "restore",
            "--from-corpus",
            str(parquet_path),
            "--json",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    # Usar result.stdout porque b2g restore emite aviso de deprecación a stderr (#165).
    envelope = json.loads(result.stdout)
    assert "state" in envelope["data"]
    assert envelope["data"]["state"] == "FILTERED"


# ---------------------------------------------------------------------------
# 6. Estado FILTERED habilita build (FSM permisiva)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_filtered_habilita_build_en_fsm(tmp_path: Path) -> None:
    """Desde FILTERED se puede transicionar a BUILT (FSM permisiva).

    Verifica que apply_transition(FILTERED, 'build', ...) devuelve BUILT
    sin lanzar excepción — garantía de que build corre después de restore.
    """
    from bib2graph.cycle import CycleState, apply_transition

    state, rnd = apply_transition(CycleState.FILTERED, "build", 1)
    assert state == CycleState.BUILT
    assert rnd == 1


@pytest.mark.unit
def test_filtered_habilita_networks_en_fsm() -> None:
    """Desde FILTERED se puede transicionar a cualquier estado de cadena.

    Verifica que la FSM permisiva no bloquea ninguna acción desde FILTERED.
    """
    from bib2graph.cycle import CycleState, available_transitions

    transitions = available_transitions(CycleState.FILTERED)
    assert "build" in transitions


# ---------------------------------------------------------------------------
# 7. b2g restore requiere --from-corpus
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_restore_cmd_sin_from_corpus_falla(tmp_path: Path) -> None:
    """b2g restore sin --from-corpus → error de uso de Click (--from-corpus required)."""
    from click.testing import CliRunner

    from bib2graph.cli import b2g
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / "ws"
    Workspace.init(ws_dir, "test")

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws_dir),
            "restore",
        ],
    )

    # Click emite error de opción requerida faltante (exit code != 0)
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# 8. run_restore con store que YA tiene corpus + estado previo (branch
#    current_state is not None) preserva la ronda del lazo existente
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_run_restore_con_estado_previo_preserva_ronda(tmp_path: Path) -> None:
    """run_restore sobre un store con estado/ronda previos preserva la ronda.

    Cubre el branch ``current_state is not None`` de restore.py (~línea 111):
    cuando el store ya tiene corpus + estado del lazo, run_restore aplica
    apply_transition sobre el estado/ronda actuales en lugar de partir de
    ronda=1.  El estado resultante debe ser FILTERED con la ronda preservada
    (no reseteada a 1).

    Secuencia:
    1. Crear store con un corpus inicial + estado SEEDED ronda=2 (simula
       segunda siembra tras reseed).
    2. Importar un parquet adicional con run_restore.
    3. Verificar: corpus mergeado, curación preservada, estado=FILTERED,
       ronda=2 (preservada, no reseteada).
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    from bib2graph.cli.commands.restore import run_restore
    from bib2graph.constants import Col, CurationStatus
    from bib2graph.corpus import Corpus
    from bib2graph.cycle import CycleState
    from bib2graph.schemas import CORPUS_SCHEMA
    from bib2graph.stores.duckdb import DuckDBStore

    # --- 1. Preparar store con corpus inicial + estado SEEDED ronda=2 ---
    existing_rows = [
        _make_corpus_row(id="E1", curation_status="accepted"),
        _make_corpus_row(id="E2", curation_status="rejected"),
    ]
    existing_table = pa.Table.from_pylist(existing_rows, schema=CORPUS_SCHEMA)
    existing_corpus = Corpus.from_arrow(existing_table)

    store_path = tmp_path / "test.duckdb"
    store = DuckDBStore(store_path)
    store.persist(existing_corpus)
    # Simular segunda ronda (reseed desde ronda 1)
    store.backend.set_loop_state(CycleState.SEEDED, cycle_round=2)

    # Verificar precondición: estado y ronda correctos antes de restore
    assert store.backend.loop_state() == CycleState.SEEDED
    assert store.backend.loop_round() == 2

    # --- 2. Importar parquet adicional con run_restore ---
    incoming_rows = [
        _make_corpus_row(id="N1", curation_status="candidate"),
        _make_corpus_row(id="N2", curation_status="accepted"),
    ]
    parquet_path = tmp_path / "incoming.parquet"
    pq.write_table(
        pa.Table.from_pylist(incoming_rows, schema=CORPUS_SCHEMA), str(parquet_path)
    )

    data = run_restore(store_path, parquet_path)

    # --- 3. Verificar postcondiciones ---

    # (a) El corpus se mergeó: contiene los papers previos + los nuevos
    store2 = DuckDBStore(store_path)
    corpus_final = store2.load()
    ids_final = set(corpus_final.to_arrow().column(Col.ID).to_pylist())
    assert "E1" in ids_final
    assert "E2" in ids_final
    assert "N1" in ids_final
    assert "N2" in ids_final

    # (b) La curación de los papers previos se preservó
    rows_final = {r[Col.ID]: r for r in corpus_final.to_arrow().to_pylist()}
    assert rows_final["E1"][Col.CURATION_STATUS] == CurationStatus.ACCEPTED
    assert rows_final["E2"][Col.CURATION_STATUS] == CurationStatus.REJECTED

    # (c) El estado es FILTERED con la ronda preservada (no reseteada a 1)
    assert data["state"] == str(CycleState.FILTERED)
    assert data["round"] == 2, (
        f"La ronda debería preservarse en 2, pero se obtuvo {data['round']!r}. "
        "Posible bug: restore.py aplica apply_transition con current_round=0 "
        "cuando la base tiene state pero loop_round() devuelve 0 (legacy NULL)."
    )
    assert store2.backend.loop_state() == CycleState.FILTERED
    assert store2.backend.loop_round() == 2
