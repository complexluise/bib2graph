"""Tests TDD para ``cluster_table`` y la integración con ``b2g build`` (#31).

Casos cubiertos:

1. ``cluster_table`` sobre corpus+grafo sintético con comunidades conocidas
   produce filas con size/seed_count/year_*/top_authors/top_keywords correctos.
2. Cruce por ``Col.ID`` (no ``openalex_id``) — test que fallaría si se usara
   la columna equivocada (lección B6, Nota 09).
3. Determinismo: mismo input → mismo output, mismo orden.
4. Redes que no son de paper (author_collab/keyword/institution) → devuelve [].
5. ``artifact.communities`` es None → devuelve [].
6. Nodo sin match en el corpus → no crash; ese nodo suma al size.
7. Cluster vacío de años → year_min/max/mean son None.
8. ``b2g build`` escribe clusters.csv para red de paper con comunidades.
9. ``b2g build`` no falla cuando la red no tiene comunidades.
10. ``cluster_table`` es importable desde ``bib2graph.networks``.

Marcador: ``unit`` (sin red, sin I/O).
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import networkx as nx
import pyarrow as pa
import pytest

from bib2graph.constants import NetworkKind
from bib2graph.networks.clusters import cluster_table
from bib2graph.networks.spec import NetworkArtifact, NetworkSpec
from bib2graph.schemas import CORPUS_SCHEMA

# ---------------------------------------------------------------------------
# Helpers de fixtures
# ---------------------------------------------------------------------------


def _make_row(
    *,
    id: str,
    openalex_id: str | None = None,
    year: int | None = None,
    is_seed: bool = False,
    curation_status: str = "candidate",
    authors_raw: list[str] | None = None,
    keywords_id: list[str] | None = None,
    references_id: list[str] | None = None,
) -> dict[str, Any]:
    """Fila mínima con schema completo para tests."""
    return {
        "id": id,
        "openalex_id": openalex_id,
        "doi": None,
        "title": f"Título de {id}",
        "year": year,
        "abstract": None,
        "source": None,
        "language": None,
        "publisher": None,
        "research_areas": None,
        "is_seed": is_seed,
        "curation_status": curation_status,
        "provenance": None,
        "authors_raw": authors_raw,
        "authors_id": None,
        "authors_affiliations": None,
        "keywords_raw": None,
        "keywords_id": keywords_id,
        "institutions_raw": None,
        "institutions_id": None,
        "references_id": references_id,
        "references_doi": None,
        "cited_by_id": None,
    }


def _make_artifact(
    *,
    kind: str,
    nodes: list[str],
    edges: list[tuple[str, str]],
    communities: dict[str, int] | None,
) -> NetworkArtifact:
    """Construye un NetworkArtifact sintético con grafo y comunidades dados."""
    g: nx.Graph = nx.Graph()
    g.add_nodes_from(nodes)
    g.add_edges_from(edges)
    spec = NetworkSpec(kind=kind, clustering=None)  # type: ignore[arg-type]
    return NetworkArtifact(
        graph=g,
        metrics={},
        communities=communities,
        assortativity=None,
        layout=None,
        spec=spec,
    )


# ---------------------------------------------------------------------------
# Corpus de referencia para los tests principales
#
# 4 papers:
#   P1: is_seed=True, accepted, year=2020, Autor A, Autor B, kw: ml, redes
#   P2: is_seed=True, accepted, year=2021, Autor B, Autor C, kw: ml
#   P3: is_seed=False, candidate, year=2022, Autor C, kw: redes, grafos
#   P4: is_seed=False, candidate, year=2019, Autor A, kw: grafos
#
# Comunidades:
#   Cluster 0: P1, P2   (seed_count=2, accepted=2, candidate=0, years=[2020,2021])
#   Cluster 1: P3, P4   (seed_count=0, candidate=2, years=[2022,2019])
# ---------------------------------------------------------------------------

_ROWS = [
    _make_row(
        id="P1",
        openalex_id="W111",
        year=2020,
        is_seed=True,
        curation_status="accepted",
        authors_raw=["Autor A", "Autor B"],
        keywords_id=["ml", "redes"],
        references_id=["R1", "R2"],
    ),
    _make_row(
        id="P2",
        openalex_id="W222",
        year=2021,
        is_seed=True,
        curation_status="accepted",
        authors_raw=["Autor B", "Autor C"],
        keywords_id=["ml"],
        references_id=["R1", "R3"],
    ),
    _make_row(
        id="P3",
        openalex_id="W333",
        year=2022,
        is_seed=False,
        curation_status="candidate",
        authors_raw=["Autor C"],
        keywords_id=["redes", "grafos"],
        references_id=["R2", "R3"],
    ),
    _make_row(
        id="P4",
        openalex_id="W444",
        year=2019,
        is_seed=False,
        curation_status="candidate",
        authors_raw=["Autor A"],
        keywords_id=["grafos"],
        references_id=["R4"],
    ),
]

_TABLE = pa.Table.from_pylist(_ROWS, schema=CORPUS_SCHEMA)

# Comunidades: cluster 0 → P1, P2; cluster 1 → P3, P4
_COMMUNITIES: dict[str, int] = {"P1": 0, "P2": 0, "P3": 1, "P4": 1}

_ARTIFACT = _make_artifact(
    kind=NetworkKind.BIBLIOGRAPHIC_COUPLING,
    nodes=["P1", "P2", "P3", "P4"],
    edges=[("P1", "P2"), ("P3", "P4")],
    communities=_COMMUNITIES,
)


# ---------------------------------------------------------------------------
# 1. Filas por cluster — valores calculados a mano
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_cluster_table_produce_dos_filas() -> None:
    """cluster_table devuelve una fila por comunidad (2 comunidades = 2 filas)."""
    rows = cluster_table(_TABLE, _ARTIFACT)
    assert len(rows) == 2


@pytest.mark.unit
def test_cluster_table_cluster_0_size() -> None:
    """Cluster 0 tiene size=2 (P1 + P2)."""
    rows = cluster_table(_TABLE, _ARTIFACT)
    c0 = next(r for r in rows if r["cluster"] == 0)
    assert c0["size"] == 2


@pytest.mark.unit
def test_cluster_table_cluster_0_seed_count() -> None:
    """Cluster 0: seed_count=2 (ambos son semillas)."""
    rows = cluster_table(_TABLE, _ARTIFACT)
    c0 = next(r for r in rows if r["cluster"] == 0)
    assert c0["seed_count"] == 2


@pytest.mark.unit
def test_cluster_table_cluster_0_accepted_count() -> None:
    """Cluster 0: accepted_count=2, candidate_count=0."""
    rows = cluster_table(_TABLE, _ARTIFACT)
    c0 = next(r for r in rows if r["cluster"] == 0)
    assert c0["accepted_count"] == 2
    assert c0["candidate_count"] == 0


@pytest.mark.unit
def test_cluster_table_cluster_0_years() -> None:
    """Cluster 0: year_min=2020, year_max=2021, year_mean=2020.5."""
    rows = cluster_table(_TABLE, _ARTIFACT)
    c0 = next(r for r in rows if r["cluster"] == 0)
    assert c0["year_min"] == 2020
    assert c0["year_max"] == 2021
    assert c0["year_mean"] == 2020.5


@pytest.mark.unit
def test_cluster_table_cluster_1_candidate_count() -> None:
    """Cluster 1: candidate_count=2, seed_count=0, accepted_count=0."""
    rows = cluster_table(_TABLE, _ARTIFACT)
    c1 = next(r for r in rows if r["cluster"] == 1)
    assert c1["candidate_count"] == 2
    assert c1["seed_count"] == 0
    assert c1["accepted_count"] == 0


@pytest.mark.unit
def test_cluster_table_cluster_1_years() -> None:
    """Cluster 1: year_min=2019, year_max=2022."""
    rows = cluster_table(_TABLE, _ARTIFACT)
    c1 = next(r for r in rows if r["cluster"] == 1)
    assert c1["year_min"] == 2019
    assert c1["year_max"] == 2022


@pytest.mark.unit
def test_cluster_table_top_authors_cluster_0() -> None:
    """Cluster 0: top_authors incluye 'Autor B' (aparece 2 veces) como primero."""
    rows = cluster_table(_TABLE, _ARTIFACT)
    c0 = next(r for r in rows if r["cluster"] == 0)
    # Autor B aparece en P1 y P2 → debe ser el más frecuente
    assert "Autor B" in c0["top_authors"]
    assert c0["top_authors"][0] == "Autor B"


@pytest.mark.unit
def test_cluster_table_top_keywords_cluster_0() -> None:
    """Cluster 0: top_keywords incluye 'ml' (aparece 2 veces) como primero."""
    rows = cluster_table(_TABLE, _ARTIFACT)
    c0 = next(r for r in rows if r["cluster"] == 0)
    assert "ml" in c0["top_keywords"]
    assert c0["top_keywords"][0] == "ml"


# ---------------------------------------------------------------------------
# 2. Cruce por Col.ID, no por openalex_id (lección B6)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_cruce_por_col_id_no_openalex_id() -> None:
    """El cruce usa Col.ID ('P1'…) no openalex_id ('W111'…).

    Si se cruzara por openalex_id, los nodos del grafo (P1,P2,P3,P4) nunca
    matchearían con 'W111','W222'… → size contaría 4 nodos pero
    seed_count/accepted/years/authors/keywords serían todos 0/[].

    Aquí verificamos que los datos de corpus SÍ lleguen al resultado,
    lo que confirma que el cruce es por Col.ID.
    """
    rows = cluster_table(_TABLE, _ARTIFACT)
    # Debe haber datos reales, no vacíos
    total_seeds = sum(r["seed_count"] for r in rows)
    total_accepted = sum(r["accepted_count"] for r in rows)
    # Con cruce por Col.ID: total_seeds=2, total_accepted=2
    # Con cruce por openalex_id: todo sería 0
    assert total_seeds == 2, (
        f"seed_count esperado=2, obtenido={total_seeds}. "
        "Posible error: cruce por openalex_id en lugar de Col.ID."
    )
    assert total_accepted == 2


# ---------------------------------------------------------------------------
# 3. Determinismo
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_cluster_table_determinismo() -> None:
    """Mismo input → mismo output en dos llamadas independientes."""
    rows1 = cluster_table(_TABLE, _ARTIFACT)
    rows2 = cluster_table(_TABLE, _ARTIFACT)
    assert rows1 == rows2


@pytest.mark.unit
def test_cluster_table_orden_por_cluster_id() -> None:
    """Las filas están ordenadas por cluster id (ascendente)."""
    rows = cluster_table(_TABLE, _ARTIFACT)
    cluster_ids = [r["cluster"] for r in rows]
    assert cluster_ids == sorted(cluster_ids)


@pytest.mark.unit
def test_top_authors_desempate_alfabetico() -> None:
    """Ante empate de frecuencia, top_authors ordena alfabéticamente (ADR 0017).

    Este test cubriría el caso donde dos autores tienen la misma frecuencia;
    el desempate debe ser determinista (alfabético) independientemente del
    orden de nodo o de PYTHONHASHSEED.
    """
    # P_X y P_Y tienen referencias compartidas → hay arista entre ellos.
    # Autor A aparece en P_X → count 1.
    # Autor B y Autor C aparecen en P_Y → count 1 cada uno.
    # Empate entre A, B y C: orden esperado alfabético (A, B, C).
    rows_empate = [
        _make_row(
            id="P_X",
            year=2020,
            is_seed=True,
            curation_status="accepted",
            authors_raw=["Autor A"],
            keywords_id=["kw_z", "kw_a"],
            references_id=["R_shared"],
        ),
        _make_row(
            id="P_Y",
            year=2021,
            is_seed=False,
            curation_status="candidate",
            authors_raw=["Autor B", "Autor C"],
            keywords_id=["kw_m", "kw_a"],
            references_id=["R_shared"],
        ),
    ]
    table_empate = pa.Table.from_pylist(rows_empate, schema=CORPUS_SCHEMA)
    art_empate = _make_artifact(
        kind=NetworkKind.BIBLIOGRAPHIC_COUPLING,
        nodes=["P_X", "P_Y"],
        edges=[("P_X", "P_Y")],
        communities={"P_X": 0, "P_Y": 0},
    )
    result = cluster_table(table_empate, art_empate)
    assert len(result) == 1
    c0 = result[0]

    # top_authors: A(1), B(1), C(1) → desempate alfabético → [A, B, C]
    assert c0["top_authors"] == ["Autor A", "Autor B", "Autor C"], (
        f"Desempate alfabético fallido: {c0['top_authors']!r}"
    )

    # top_keywords: kw_a aparece 2 veces (en ambos papers), kw_m y kw_z una vez.
    # kw_a primero (count 2), luego kw_m y kw_z empatados (count 1) → [kw_a, kw_m, kw_z]
    assert c0["top_keywords"][0] == "kw_a", (
        f"kw_a debería ser primera (count=2): {c0['top_keywords']!r}"
    )
    # Empate entre kw_m y kw_z → desempate alfabético → kw_m antes que kw_z
    assert c0["top_keywords"][1] == "kw_m", (
        f"Desempate alfabético en keywords fallido: {c0['top_keywords']!r}"
    )
    assert c0["top_keywords"][2] == "kw_z"


# ---------------------------------------------------------------------------
# 4. Redes que no son de paper → []
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_cluster_table_autor_devuelve_vacio() -> None:
    """Para author_collab cluster_table devuelve []."""
    art = _make_artifact(
        kind=NetworkKind.AUTHOR_COLLAB,
        nodes=["auth_1", "auth_2"],
        edges=[("auth_1", "auth_2")],
        communities={"auth_1": 0, "auth_2": 1},
    )
    assert cluster_table(_TABLE, art) == []


@pytest.mark.unit
def test_cluster_table_keyword_devuelve_vacio() -> None:
    """Para keyword_cooccurrence cluster_table devuelve []."""
    art = _make_artifact(
        kind=NetworkKind.KEYWORD_COOCCURRENCE,
        nodes=["ml", "redes"],
        edges=[("ml", "redes")],
        communities={"ml": 0, "redes": 0},
    )
    assert cluster_table(_TABLE, art) == []


@pytest.mark.unit
def test_cluster_table_institution_devuelve_vacio() -> None:
    """Para institution_collab cluster_table devuelve []."""
    art = _make_artifact(
        kind=NetworkKind.INSTITUTION_COLLAB,
        nodes=["inst_a", "inst_b"],
        edges=[("inst_a", "inst_b")],
        communities={"inst_a": 0, "inst_b": 0},
    )
    assert cluster_table(_TABLE, art) == []


# ---------------------------------------------------------------------------
# 5. Communities None → []
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_cluster_table_sin_communities_devuelve_vacio() -> None:
    """artifact.communities=None → cluster_table devuelve []."""
    art = _make_artifact(
        kind=NetworkKind.BIBLIOGRAPHIC_COUPLING,
        nodes=["P1", "P2"],
        edges=[("P1", "P2")],
        communities=None,
    )
    assert cluster_table(_TABLE, art) == []


# ---------------------------------------------------------------------------
# 6. Nodo sin match en corpus → no crash
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_nodo_sin_match_en_corpus_no_crash() -> None:
    """Un nodo 'NOID' sin match en el corpus no provoca crash.

    El nodo suma al size pero no aporta datos bibliográficos.
    """
    art = _make_artifact(
        kind=NetworkKind.BIBLIOGRAPHIC_COUPLING,
        nodes=["P1", "NOID"],
        edges=[("P1", "NOID")],
        communities={"P1": 0, "NOID": 0},
    )
    rows = cluster_table(_TABLE, art)
    assert len(rows) == 1
    c0 = rows[0]
    # size = 2 (P1 + NOID), pero seed_count solo de P1
    assert c0["size"] == 2
    assert c0["seed_count"] == 1  # solo P1 es semilla


# ---------------------------------------------------------------------------
# 7. Cluster sin años → year_min/max/mean None
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_cluster_sin_anios_year_none() -> None:
    """Si ningún nodo del cluster tiene año, year_min/max/mean son None."""
    rows_sin_year = [
        _make_row(
            id="SY1",
            year=None,
            is_seed=True,
            curation_status="candidate",
            references_id=["R_x"],
        ),
        _make_row(
            id="SY2",
            year=None,
            is_seed=False,
            curation_status="candidate",
            references_id=["R_x"],
        ),
    ]
    table_sin_year = pa.Table.from_pylist(rows_sin_year, schema=CORPUS_SCHEMA)
    art = _make_artifact(
        kind=NetworkKind.BIBLIOGRAPHIC_COUPLING,
        nodes=["SY1", "SY2"],
        edges=[("SY1", "SY2")],
        communities={"SY1": 0, "SY2": 0},
    )
    rows = cluster_table(table_sin_year, art)
    assert len(rows) == 1
    c0 = rows[0]
    assert c0["year_min"] is None
    assert c0["year_max"] is None
    assert c0["year_mean"] is None


# ---------------------------------------------------------------------------
# 8. Integración con b2g build: escribe clusters.csv para red de paper
# ---------------------------------------------------------------------------


def _seed_store(store_path: Path, rows: list[dict[str, Any]]) -> None:
    """Puebla un DuckDBStore temporal con las filas dadas."""
    from bib2graph.corpus import Corpus
    from bib2graph.stores.duckdb import DuckDBStore

    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)
    store = DuckDBStore(store_path)
    store.persist(corpus)


@pytest.mark.unit
def test_build_escribe_clusters_csv(tmp_path: Path) -> None:
    """run_build escribe clusters.csv en el directorio de la red de acoplamiento."""
    from bib2graph.cli.commands.build import run_build

    store_path = tmp_path / "lib.duckdb"
    # Corpus con referencias compartidas → grafo de coupling no vacío
    rows = [
        _make_row(
            id="oa:A1",
            year=2020,
            is_seed=True,
            curation_status="accepted",
            authors_raw=["Autor X"],
            keywords_id=["kw1"],
            references_id=["R1", "R2"],
        ),
        _make_row(
            id="oa:A2",
            year=2021,
            is_seed=True,
            curation_status="accepted",
            authors_raw=["Autor Y"],
            keywords_id=["kw1", "kw2"],
            references_id=["R1", "R3"],
        ),
        _make_row(
            id="oa:A3",
            year=2022,
            is_seed=False,
            curation_status="candidate",
            authors_raw=["Autor Z"],
            keywords_id=["kw2"],
            references_id=["R2", "R3"],
        ),
    ]
    _seed_store(store_path, rows)

    out_dir = tmp_path / "networks"
    run_build(store_path, out_dir=out_dir)

    clusters_csv = out_dir / "bibliographic_coupling" / "clusters.csv"
    assert clusters_csv.exists(), (
        "clusters.csv no fue creado para bibliographic_coupling"
    )

    with open(clusters_csv, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        csv_rows = list(reader)

    # Debe haber al menos 1 fila (puede haber múltiples clusters)
    assert len(csv_rows) >= 1

    # Las columnas esperadas deben existir
    expected_cols = {
        "cluster",
        "size",
        "seed_count",
        "candidate_count",
        "accepted_count",
        "year_min",
        "year_max",
        "year_mean",
        "top_authors",
        "top_keywords",
    }
    assert expected_cols.issubset(set(reader.fieldnames or []))


@pytest.mark.unit
def test_build_no_falla_sin_comunidades(tmp_path: Path) -> None:
    """run_build no falla cuando la red de coupling no produce aristas.

    Un corpus con 0 referencias compartidas → grafo vacío → comunidades vacías
    → cluster_table devuelve [] → no se escribe clusters.csv, pero tampoco falla.
    """
    from bib2graph.cli.commands.build import run_build

    store_path = tmp_path / "lib.duckdb"
    # Corpus sin referencias compartidas → grafo de coupling vacío (sin aristas)
    rows = [
        _make_row(
            id="oa:B1",
            year=2020,
            is_seed=True,
            curation_status="candidate",
            references_id=["R_solo_1"],
        ),
        _make_row(
            id="oa:B2",
            year=2021,
            is_seed=False,
            curation_status="candidate",
            references_id=["R_solo_2"],
        ),
    ]
    _seed_store(store_path, rows)

    out_dir = tmp_path / "networks"
    result = run_build(store_path, out_dir=out_dir)
    assert "networks" in result
    assert result["networks_built"] >= 1
    # clusters.csv puede o no existir, pero run_build no debe fallar
    coupling_dir = out_dir / "bibliographic_coupling"
    assert coupling_dir.exists()


# ---------------------------------------------------------------------------
# 9. cluster_table importable desde bib2graph.networks
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_cluster_table_importable_desde_networks() -> None:
    """cluster_table es importable desde el paquete bib2graph.networks."""
    from bib2graph.networks import cluster_table as ct

    assert callable(ct)
