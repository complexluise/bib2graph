"""Tests del Hito G2 — 6 lecturas de ``bib2graph.service`` (ADR 0028).

Cobertura priorizada (docs/ROADMAP/05-gui.md §Hito G2):

1. ``compare_rounds`` sobre dos snapshots conocidos (1 paper extra) →
   ``added_paper_ids``/``removed_paper_ids`` calculados a mano + ``n_papers``
   correcto.  Es el test de mayor valor (diferenciador del ADR 0027).
2. ``get_network(kind)`` sobre corpus conocido → nº nodos/aristas + presencia
   de ``label``/``community`` en nodos de paper (bibliographic_coupling).
3. ``get_paper`` happy-path + ``DataError`` con id inexistente.
4. Smokes de forma para ``get_workspace``, ``list_rounds``, ``get_scent``.

Filosofía (AGENTS.md): se testea lógica real sobre datos sintéticos; no se
re-testean passthroughs triviales ni lo que ya cubre ``test_cli.py``.
Marcador: ``unit`` (DuckDB en tmp_path, sin red real).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest

from bib2graph.schemas import CORPUS_SCHEMA

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers compartidos
# ---------------------------------------------------------------------------


def _row(
    *,
    id: str,
    title: str = "Título de prueba",
    year: int = 2020,
    is_seed: bool = True,
    curation_status: str = "candidate",
    doi: str | None = None,
    references_id: list[str] | None = None,
    cited_by_id: list[str] | None = None,
) -> dict[str, Any]:
    """Fila mínima con schema completo para tests."""
    return {
        "id": id,
        "openalex_id": None,
        "doi": doi,
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
        "authors_raw": ["Autor A"],
        "authors_id": ["oa:author1"],
        "authors_affiliations": None,
        "keywords_raw": ["keyword1"],
        "keywords_id": ["kw1"],
        "institutions_raw": None,
        "institutions_id": None,
        "references_id": references_id,
        "references_doi": None,
        "cited_by_id": cited_by_id,
    }


def _init_workspace(tmp_path: Path, name: str = "test-ws") -> Any:
    """Crea y devuelve un Workspace inicializado en tmp_path."""
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / name
    return Workspace.init(ws_dir, name)


def _seed_store(ws: Any, rows: list[dict[str, Any]]) -> None:
    """Persiste filas en el store del workspace."""
    from bib2graph.corpus import Corpus
    from bib2graph.stores.duckdb import DuckDBStore

    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)
    store = DuckDBStore(ws.library_path)
    store.persist(corpus)


def _write_snapshot(ws: Any, name: str, rows: list[dict[str, Any]]) -> Path:
    """Escribe un snapshot mínimo (corpus.parquet + manifest.json) en snapshots/."""
    import pyarrow.parquet as pq

    from bib2graph.corpus import Corpus

    snap_dir = ws.snapshots_dir / name
    snap_dir.mkdir(parents=True, exist_ok=True)

    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    pq.write_table(table, snap_dir / "corpus.parquet")  # type: ignore[no-untyped-call]

    corpus = Corpus.from_arrow(table)
    manifest = corpus.manifest.model_copy(
        update={
            "corpus_hash": corpus._backend.corpus_hash(),
            "schema_version": "1",
        }
    )
    (snap_dir / "manifest.json").write_text(
        manifest.model_dump_json(indent=2), encoding="utf-8"
    )
    return snap_dir


# ---------------------------------------------------------------------------
# 1. compare_rounds — el diferenciador
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_compare_rounds_added_removed_calculados_a_mano(tmp_path: Path) -> None:
    """compare_rounds detecta paper extra en b y calcula n_papers correctamente.

    Corpus A: P1, P2 (2 papers).
    Corpus B: P1, P2, P3 (3 papers — P3 es el agregado).

    Calculado a mano:
      - added_paper_ids = ["P3"]
      - removed_paper_ids = []
      - metrics_change[n_papers] = {before: 2, after: 3}
    """
    from bib2graph.service.reads import compare_rounds

    ws = _init_workspace(tmp_path)

    rows_a = [
        _row(id="P1", title="Paper 1"),
        _row(id="P2", title="Paper 2"),
    ]
    rows_b = [
        _row(id="P1", title="Paper 1"),
        _row(id="P2", title="Paper 2"),
        _row(id="P3", title="Paper 3"),
    ]

    _write_snapshot(ws, "snap-a", rows_a)
    _write_snapshot(ws, "snap-b", rows_b)

    result = compare_rounds(ws, "snap-a", "snap-b")

    assert result["round_a"] == "snap-a"
    assert result["round_b"] == "snap-b"
    assert result["added_paper_ids"] == ["P3"]
    assert result["removed_paper_ids"] == []

    n_papers_change = next(
        m for m in result["metrics_change"] if m["metric"] == "n_papers"
    )
    assert n_papers_change["before"] == 2
    assert n_papers_change["after"] == 3

    assert isinstance(result["mutated_hubs"], list)


@pytest.mark.unit
def test_compare_rounds_removed_paper(tmp_path: Path) -> None:
    """compare_rounds detecta paper removido de a a b."""
    from bib2graph.service.reads import compare_rounds

    ws = _init_workspace(tmp_path)

    rows_a = [_row(id="P1"), _row(id="P2"), _row(id="P4")]
    rows_b = [_row(id="P1"), _row(id="P2")]

    _write_snapshot(ws, "snap-a", rows_a)
    _write_snapshot(ws, "snap-b", rows_b)

    result = compare_rounds(ws, "snap-a", "snap-b")

    assert result["added_paper_ids"] == []
    assert result["removed_paper_ids"] == ["P4"]

    n_papers_change = next(
        m for m in result["metrics_change"] if m["metric"] == "n_papers"
    )
    assert n_papers_change["before"] == 3
    assert n_papers_change["after"] == 2


@pytest.mark.unit
def test_compare_rounds_snapshot_inexistente_lanza_dataerror(
    tmp_path: Path,
) -> None:
    """compare_rounds con snapshot inexistente lanza DataError accionable."""
    from bib2graph.service.errors import DataError
    from bib2graph.service.reads import compare_rounds

    ws = _init_workspace(tmp_path)
    rows = [_row(id="P1")]
    _write_snapshot(ws, "snap-real", rows)
    _seed_store(ws, rows)

    with pytest.raises(DataError, match="snap-inexistente"):
        compare_rounds(ws, "snap-real", "snap-inexistente")


@pytest.mark.unit
def test_compare_rounds_live_vs_snapshot(tmp_path: Path) -> None:
    """compare_rounds admite 'live' como uno de los extremos del diff."""
    from bib2graph.service.reads import compare_rounds

    ws = _init_workspace(tmp_path)

    rows_snap = [_row(id="P1"), _row(id="P2")]
    rows_live = [_row(id="P1"), _row(id="P2"), _row(id="P5")]

    _write_snapshot(ws, "snap-a", rows_snap)
    _seed_store(ws, rows_live)

    result = compare_rounds(ws, "snap-a", "live")

    assert "P5" in result["added_paper_ids"]
    assert result["removed_paper_ids"] == []

    n_papers_change = next(
        m for m in result["metrics_change"] if m["metric"] == "n_papers"
    )
    assert n_papers_change["before"] == 2
    assert n_papers_change["after"] == 3


# ---------------------------------------------------------------------------
# 2. get_network — red de la ronda viva
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_network_bibliographic_coupling_estructura(tmp_path: Path) -> None:
    """get_network devuelve nodos/aristas/métricas con la forma esperada.

    Corpus de 3 papers: P1 y P2 comparten la referencia 'R1'; P3 no tiene
    referencias.  La red de acoplamiento bibliográfico debe tener exactamente
    2 nodos (P1, P2) y 1 arista con weight=1.
    """
    from bib2graph.constants import NetworkKind
    from bib2graph.service.reads import get_network

    ws = _init_workspace(tmp_path)

    rows = [
        _row(id="P1", title="Paper 1 largo para label", references_id=["R1", "R2"]),
        _row(id="P2", title="Paper 2", references_id=["R1", "R3"]),
        _row(id="P3", title="Paper 3 sin refs", references_id=None),
    ]
    _seed_store(ws, rows)

    result = get_network(ws, NetworkKind.BIBLIOGRAPHIC_COUPLING)

    assert "nodes" in result
    assert "edges" in result
    assert "metrics" in result

    node_ids = {n["id"] for n in result["nodes"]}
    assert "P1" in node_ids
    assert "P2" in node_ids
    assert "P3" not in node_ids  # P3 no tiene refs compartidas → no aparece

    # Exactamente 1 arista P1-P2
    assert len(result["edges"]) == 1
    edge = result["edges"][0]
    assert {edge["source"], edge["target"]} == {"P1", "P2"}
    assert edge["weight"] == 1

    # Cada nodo tiene label y degree_centrality
    for node in result["nodes"]:
        assert "label" in node
        assert "degree_centrality" in node
        assert isinstance(node["degree_centrality"], float)


@pytest.mark.unit
def test_get_network_paper_nodes_tienen_atributos_extra(tmp_path: Path) -> None:
    """Los nodos de redes de paper tienen year/is_seed/curation_status inyectados."""
    from bib2graph.constants import NetworkKind
    from bib2graph.service.reads import get_network

    ws = _init_workspace(tmp_path)

    rows = [
        _row(
            id="P1",
            title="Primer paper",
            year=2021,
            is_seed=True,
            curation_status="accepted",
            references_id=["R1"],
        ),
        _row(
            id="P2",
            title="Segundo paper",
            year=2022,
            is_seed=False,
            curation_status="candidate",
            references_id=["R1"],
        ),
    ]
    _seed_store(ws, rows)

    result = get_network(ws, NetworkKind.BIBLIOGRAPHIC_COUPLING)

    node_map = {n["id"]: n for n in result["nodes"]}
    assert "P1" in node_map
    assert "P2" in node_map

    n1 = node_map["P1"]
    assert n1.get("year") == 2021
    assert n1.get("is_seed") is True
    assert n1.get("curation_status") == "accepted"


@pytest.mark.unit
def test_get_network_kind_invalido_lanza_dataerror(tmp_path: Path) -> None:
    """get_network con kind desconocido lanza DataError accionable."""
    from bib2graph.service.errors import DataError
    from bib2graph.service.reads import get_network

    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    with pytest.raises(DataError, match="no reconocido"):
        get_network(ws, "red_inventada")


@pytest.mark.unit
def test_get_network_metricas_forma(tmp_path: Path) -> None:
    """get_network devuelve todas las claves de métricas esperadas."""
    from bib2graph.constants import NetworkKind
    from bib2graph.service.reads import get_network

    ws = _init_workspace(tmp_path)
    rows = [
        _row(id="P1", references_id=["R1"]),
        _row(id="P2", references_id=["R1"]),
    ]
    _seed_store(ws, rows)

    result = get_network(ws, NetworkKind.BIBLIOGRAPHIC_COUPLING)

    metrics = result["metrics"]
    for key in (
        "n_nodes",
        "n_edges",
        "density",
        "num_components",
        "avg_clustering",
        "n_communities",
    ):
        assert key in metrics, f"Falta clave de métrica: {key}"


# ---------------------------------------------------------------------------
# 3. get_paper — happy-path y DataError
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_paper_happy_path_devuelve_fila_completa(tmp_path: Path) -> None:
    """get_paper devuelve todos los campos de la fila del corpus."""
    from bib2graph.service.reads import get_paper

    ws = _init_workspace(tmp_path)
    rows = [
        _row(
            id="P1",
            title="Paper de prueba",
            year=2023,
            is_seed=True,
            curation_status="accepted",
            references_id=["R1", "R2"],
        )
    ]
    _seed_store(ws, rows)

    result = get_paper(ws, "P1")

    assert result["id"] == "P1"
    assert result["title"] == "Paper de prueba"
    assert result["year"] == 2023
    assert result["is_seed"] is True
    assert result["curation_status"] == "accepted"
    assert result["references_id"] == ["R1", "R2"]
    # authors_raw viene del helper _row
    assert result["authors_raw"] == ["Autor A"]
    # provenance es lista (vacía o con eventos)
    assert isinstance(result["provenance"], list)


@pytest.mark.unit
def test_get_paper_id_inexistente_lanza_dataerror(tmp_path: Path) -> None:
    """get_paper con id inexistente lanza DataError accionable."""
    from bib2graph.service.errors import DataError
    from bib2graph.service.reads import get_paper

    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    with pytest.raises(DataError, match="no encontrado"):
        get_paper(ws, "id-que-no-existe")


# ---------------------------------------------------------------------------
# 4. Smokes de forma — get_workspace / list_rounds / get_scent
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_workspace_forma(tmp_path: Path) -> None:
    """get_workspace devuelve las claves documentadas (smoke de forma)."""
    from bib2graph.service.reads import get_workspace

    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1"), _row(id="P2")])

    result = get_workspace(ws)

    expected_keys = {
        "name",
        "root",
        "created_at",
        "bib2graph_version",
        "source",
        "loop_state",
        "round",
        "total_papers",
        "counts_by_status",
        "networks_cache_stale",
    }
    for key in expected_keys:
        assert key in result, f"Falta clave: {key}"

    assert result["name"] == "test-ws"
    assert result["total_papers"] == 2
    assert isinstance(result["counts_by_status"], dict)
    assert isinstance(result["networks_cache_stale"], bool)


@pytest.mark.unit
def test_list_rounds_incluye_entrada_live(tmp_path: Path) -> None:
    """list_rounds incluye siempre la entrada id='live' del corpus vivo."""
    from bib2graph.service.reads import list_rounds

    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    rounds = list_rounds(ws)

    live_entries = [r for r in rounds if r["id"] == "live"]
    assert len(live_entries) == 1
    live = live_entries[0]
    assert "round" in live
    assert "loop_state" in live
    assert "total_papers" in live


@pytest.mark.unit
def test_list_rounds_incluye_snapshots_en_orden(tmp_path: Path) -> None:
    """list_rounds lista los snapshots existentes antes de la entrada 'live'."""
    from bib2graph.service.reads import list_rounds

    ws = _init_workspace(tmp_path)
    rows = [_row(id="P1")]
    _write_snapshot(ws, "2024-01-01", rows)
    _write_snapshot(ws, "2024-06-15", rows)
    _seed_store(ws, rows)

    rounds = list_rounds(ws)

    snap_ids = [r["id"] for r in rounds if r["id"] != "live"]
    assert "2024-01-01" in snap_ids
    assert "2024-06-15" in snap_ids
    # Deben estar ordenados lexicográficamente
    assert snap_ids == sorted(snap_ids)


@pytest.mark.unit
def test_get_scent_forma(tmp_path: Path) -> None:
    """get_scent devuelve las claves documentadas (smoke de forma)."""
    from bib2graph.service.reads import get_scent

    ws = _init_workspace(tmp_path)
    rows = [
        _row(id="P1", references_id=["R1", "R2"]),
        _row(id="P2", references_id=["R1", "R3"]),
        _row(id="P3", references_id=["R4"]),
    ]
    _seed_store(ws, rows)

    result = get_scent(ws, "P1")

    assert result["paper_id"] == "P1"
    assert "score" in result
    assert "coupling" in result
    assert "references" in result
    assert "cited_by" in result

    assert isinstance(result["score"], int)
    assert isinstance(result["coupling"], list)


@pytest.mark.unit
def test_get_scent_coupling_detecta_vecinos_compartidos(tmp_path: Path) -> None:
    """get_scent detecta que P2 comparte la referencia R1 con P1 → coupling."""
    from bib2graph.service.reads import get_scent

    ws = _init_workspace(tmp_path)
    rows = [
        _row(id="P1", references_id=["R1", "R2"]),
        _row(id="P2", references_id=["R1", "R3"]),
    ]
    _seed_store(ws, rows)

    result = get_scent(ws, "P1")

    # P1 y P2 comparten R1 → P2 debe aparecer en coupling de P1
    coupling_ids = [c["paper_id"] for c in result["coupling"]]
    assert "P2" in coupling_ids
    # score = 1 (un paper con referencias compartidas)
    assert result["score"] == 1


@pytest.mark.unit
def test_get_scent_paper_inexistente_lanza_dataerror(tmp_path: Path) -> None:
    """get_scent con id inexistente lanza DataError."""
    from bib2graph.service.errors import DataError
    from bib2graph.service.reads import get_scent

    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    with pytest.raises(DataError, match="no encontrado"):
        get_scent(ws, "no-existe")


# Neutralidad de transporte de service.reads: consolidada en
# test_service.py::test_service_modulo_neutral_de_transporte (epic #184).


# ---------------------------------------------------------------------------
# 5. resolve_doi / resolve_url  (issue #212 — opción 1)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_resolve_doi_con_doi(tmp_path: Path) -> None:
    """resolve_doi devuelve el DOI desnudo cuando el paper existe y tiene DOI."""
    from bib2graph.service.reads import resolve_doi

    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1", doi="10.1234/test.001")])

    result = resolve_doi(ws, "P1")

    assert result == "10.1234/test.001"


@pytest.mark.unit
def test_resolve_doi_sin_doi(tmp_path: Path) -> None:
    """resolve_doi devuelve None cuando el paper existe pero no tiene DOI."""
    from bib2graph.service.reads import resolve_doi

    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1", doi=None)])

    result = resolve_doi(ws, "P1")

    assert result is None


@pytest.mark.unit
def test_resolve_doi_doi_vacio_es_none(tmp_path: Path) -> None:
    """resolve_doi trata un DOI cadena vacía ('') como ausente → None.

    Coherente con networks/decorate.py (que solo emite doi/url cuando el
    DOI es truthy) y con resolve_url. Sella el contrato 'None en los 3
    casos' del issue #212.
    """
    from bib2graph.service.reads import resolve_doi, resolve_url

    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1", doi="")])

    assert resolve_doi(ws, "P1") is None
    assert resolve_url(ws, "P1") is None


@pytest.mark.unit
def test_resolve_doi_id_inexistente(tmp_path: Path) -> None:
    """resolve_doi devuelve None cuando el id no existe en el corpus (no lanza)."""
    from bib2graph.service.reads import resolve_doi

    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    result = resolve_doi(ws, "id-que-no-existe")

    assert result is None


@pytest.mark.unit
def test_resolve_url_con_doi(tmp_path: Path) -> None:
    """resolve_url devuelve la URL bien formada cuando hay DOI."""
    from bib2graph.service.reads import resolve_url

    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1", doi="10.1234/test.001")])

    result = resolve_url(ws, "P1")

    assert result == "https://doi.org/10.1234/test.001"


@pytest.mark.unit
def test_resolve_url_sin_doi(tmp_path: Path) -> None:
    """resolve_url devuelve None cuando el paper existe pero no tiene DOI."""
    from bib2graph.service.reads import resolve_url

    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1", doi=None)])

    result = resolve_url(ws, "P1")

    assert result is None


@pytest.mark.unit
def test_resolve_url_id_inexistente(tmp_path: Path) -> None:
    """resolve_url devuelve None cuando el id no existe en el corpus (no lanza)."""
    from bib2graph.service.reads import resolve_url

    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    result = resolve_url(ws, "id-que-no-existe")

    assert result is None


@pytest.mark.unit
def test_resolve_url_criterio_consistente_con_decorate(tmp_path: Path) -> None:
    """resolve_url usa el mismo criterio doi→url que networks/decorate.py.

    Ambos consumen doi_to_url de constants.py como fuente única.
    Este test fija el contrato: mismo DOI → misma URL.
    """
    from bib2graph.constants import doi_to_url
    from bib2graph.service.reads import resolve_url

    doi = "10.9999/consistencia"
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1", doi=doi)])

    # resolve_url debe coincidir con la derivación de doi_to_url directa
    assert resolve_url(ws, "P1") == doi_to_url(doi)


@pytest.mark.unit
def test_resolve_doi_y_url_expuestos_en_service(tmp_path: Path) -> None:
    """resolve_doi y resolve_url son importables desde bib2graph.service."""
    import bib2graph.service as svc

    assert hasattr(svc, "resolve_doi")
    assert hasattr(svc, "resolve_url")
    assert callable(svc.resolve_doi)
    assert callable(svc.resolve_url)
