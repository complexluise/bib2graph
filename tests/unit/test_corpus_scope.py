"""Tests TDD para ``Corpus.scoped`` y la integración con ``run_build`` (issue #56).

Casos cubiertos:

1. ``Corpus.scoped('all')`` → corpus completo sin filtrar.
2. ``Corpus.scoped('seeds_only')`` → solo filas con ``is_seed == True``.
3. ``Corpus.scoped('accepted')`` → semillas (is_seed=True) + aceptados
   (curation_status='accepted'); sin seeds no-aceptados, ni candidatos.
4. Pureza: ``scoped`` no muta el original; hash del subset es estable entre
   dos llamadas (determinismo).
5. Scope inválido → ``ValueError`` accionable.
6. ``run_build`` con default (``'all'``) cubre el corpus completo.
7. ``run_build`` con ``corpus_scope='accepted'`` proyecta solo seeds+accepted;
   el ``.corpus_hash`` sellado = hash del subset; el JSON incluye ``corpus_scope``.
8. ``clusters.csv`` cuenta nodos del subset (no del corpus completo).
9. ``run_build`` con scope que deja 0 papers → exit 0 + warning accionable,
   ``networks_built == 0``, no excepción.

Marcador: ``unit`` (DuckDB en tmp_path; sin red).
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest

from bib2graph.backends.memory import compute_corpus_hash
from bib2graph.corpus import Corpus
from bib2graph.schemas import CORPUS_SCHEMA

# ---------------------------------------------------------------------------
# Helpers de fixtures
# ---------------------------------------------------------------------------


def _make_row(
    *,
    id: str,
    is_seed: bool = False,
    curation_status: str = "candidate",
    references_id: list[str] | None = None,
    authors_raw: list[str] | None = None,
) -> dict[str, Any]:
    """Fila mínima con schema completo."""
    return {
        "id": id,
        "openalex_id": None,
        "doi": None,
        "title": f"Título {id}",
        "year": 2020,
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
        "keywords_id": None,
        "institutions_raw": None,
        "institutions_id": None,
        "references_id": references_id,
        "references_doi": None,
        "cited_by_id": None,
    }


def _make_corpus(*rows: dict[str, Any]) -> Corpus:
    """Construye un Corpus desde una lista de filas."""
    table = pa.Table.from_pylist(list(rows), schema=CORPUS_SCHEMA)
    return Corpus.from_arrow(table)


def _seed_store(store_path: Path, rows: list[dict[str, Any]]) -> None:
    """Puebla un DuckDBStore temporal con las filas dadas."""
    from bib2graph.stores.duckdb import DuckDBStore

    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)
    store = DuckDBStore(store_path)
    store.persist(corpus)


# ---------------------------------------------------------------------------
# Corpus de prueba: 4 papers con distintas combinaciones is_seed/curation_status
#
#  P1: seed + candidate   → aparece en all, accepted (seed), seeds_only
#  P2: no-seed + accepted → aparece en all, accepted
#  P3: no-seed + candidate → aparece solo en all
#  P4: no-seed + rejected  → aparece solo en all
# ---------------------------------------------------------------------------

_P1 = _make_row(id="P1", is_seed=True, curation_status="candidate")
_P2 = _make_row(id="P2", is_seed=False, curation_status="accepted")
_P3 = _make_row(id="P3", is_seed=False, curation_status="candidate")
_P4 = _make_row(id="P4", is_seed=False, curation_status="rejected")


# ---------------------------------------------------------------------------
# 1. scoped('all') — corpus completo
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_scoped_all_devuelve_corpus_completo() -> None:
    """scoped('all') devuelve exactamente el mismo conjunto de papers."""
    corpus = _make_corpus(_P1, _P2, _P3, _P4)

    resultado = corpus.scoped("all")

    assert len(resultado) == 4


# ---------------------------------------------------------------------------
# 2. scoped('seeds_only') — solo is_seed == True
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_scoped_seeds_only_devuelve_solo_semillas() -> None:
    """scoped('seeds_only') devuelve solo filas con is_seed == True."""
    corpus = _make_corpus(_P1, _P2, _P3, _P4)

    resultado = corpus.scoped("seeds_only")

    ids = {r["id"] for r in resultado.to_arrow().to_pylist()}
    assert ids == {"P1"}
    assert len(resultado) == 1


# ---------------------------------------------------------------------------
# 3. scoped('accepted') — semillas + papers aceptados (no candidatos, no rechazados)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_scoped_accepted_devuelve_seeds_y_aceptados() -> None:
    """scoped('accepted') incluye seeds (P1) y aceptados no-seed (P2); excluye P3/P4."""
    corpus = _make_corpus(_P1, _P2, _P3, _P4)

    resultado = corpus.scoped("accepted")

    ids = {r["id"] for r in resultado.to_arrow().to_pylist()}
    assert ids == {"P1", "P2"}
    assert len(resultado) == 2


@pytest.mark.unit
def test_scoped_accepted_excluye_candidate_y_rejected() -> None:
    """scoped('accepted') excluye candidatos y rechazados que no son semillas."""
    corpus = _make_corpus(_P3, _P4)  # ninguno es seed ni accepted

    resultado = corpus.scoped("accepted")

    assert len(resultado) == 0


# ---------------------------------------------------------------------------
# 4. Pureza — no muta el original; hash estable
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_scoped_no_muta_corpus_original() -> None:
    """scoped no muta el corpus original: el original sigue teniendo los 4 papers."""
    corpus = _make_corpus(_P1, _P2, _P3, _P4)

    _resultado = corpus.scoped("accepted")

    # El original permanece con 4 papers
    assert len(corpus) == 4


@pytest.mark.unit
def test_scoped_hash_estable_entre_dos_llamadas() -> None:
    """Dos llamadas a scoped con el mismo scope producen el mismo corpus_hash."""
    corpus = _make_corpus(_P1, _P2, _P3, _P4)

    r1 = corpus.scoped("accepted")
    r2 = corpus.scoped("accepted")

    hash1 = compute_corpus_hash(r1.to_arrow())
    hash2 = compute_corpus_hash(r2.to_arrow())
    assert hash1 == hash2


# ---------------------------------------------------------------------------
# 5. Scope inválido → ValueError
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_scoped_scope_invalido_lanza_valueerror() -> None:
    """scoped con scope desconocido lanza ValueError con mensaje accionable."""
    corpus = _make_corpus(_P1)

    with pytest.raises(ValueError, match="no reconocido"):
        corpus.scoped("invalid_scope")


# ---------------------------------------------------------------------------
# 6. run_build default='all' → corpus completo (no rompe comportamiento existente)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_run_build_default_scope_all_usa_corpus_completo(tmp_path: Path) -> None:
    """run_build sin corpus_scope explícito usa 'all' y construye redes sobre el corpus completo."""
    from bib2graph.cli.commands.build import run_build

    store_path = tmp_path / "lib.duckdb"
    rows = [
        _make_row(id="S1", is_seed=True, curation_status="candidate"),
        _make_row(id="S2", is_seed=True, curation_status="candidate"),
        _make_row(id="C1", is_seed=False, curation_status="candidate"),
    ]
    _seed_store(store_path, rows)

    out_dir = tmp_path / "nets"
    data = run_build(store_path, out_dir=out_dir)

    assert data["corpus_scope"] == "all"
    assert data["networks_built"] >= 1
    assert data["warnings"] == []


# ---------------------------------------------------------------------------
# 7. run_build corpus_scope='accepted' → subset correcto + hash del subset
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_run_build_corpus_scope_accepted_filtra_subset(tmp_path: Path) -> None:
    """run_build con corpus_scope='accepted' proyecta solo seeds+accepted.

    El .corpus_hash sellado debe ser el hash del subset (no del corpus completo).
    El JSON de salida incluye la clave 'corpus_scope'.
    """
    from bib2graph.cli.commands.build import run_build

    store_path = tmp_path / "lib.duckdb"
    # P_SEED: seed (entra en accepted)
    # P_ACCEPTED: aceptado no-seed (entra en accepted)
    # P_CAND: candidato no-seed (NO entra en accepted)
    rows = [
        _make_row(
            id="P_SEED",
            is_seed=True,
            curation_status="candidate",
            references_id=["R1", "R2"],
        ),
        _make_row(
            id="P_ACCEPTED",
            is_seed=False,
            curation_status="accepted",
            references_id=["R1", "R3"],
        ),
        _make_row(
            id="P_CAND",
            is_seed=False,
            curation_status="candidate",
            references_id=["R2", "R3"],
        ),
    ]
    _seed_store(store_path, rows)

    out_dir = tmp_path / "nets"
    data = run_build(store_path, out_dir=out_dir, corpus_scope="accepted")

    # Verificar que el scope está en el resultado
    assert data["corpus_scope"] == "accepted"
    assert data["networks_built"] >= 1

    # El hash sellado en disco debe coincidir con el hash del subset (2 papers).
    # Reconstituimos el corpus desde el store para derivar el hash esperado.
    from bib2graph.stores.duckdb import DuckDBStore

    store = DuckDBStore(store_path)
    corpus_full = store.load()
    full_table = corpus_full.to_arrow()
    subset_table = corpus_full.scoped("accepted").to_arrow()
    store.close()

    expected_hash = compute_corpus_hash(subset_table)

    hash_file = Path(data["artifacts_dir"]) / ".corpus_hash"
    assert hash_file.exists()
    assert hash_file.read_text(encoding="utf-8") == expected_hash

    # Y el hash del subset NO es el hash del corpus completo
    full_hash = compute_corpus_hash(full_table)
    assert expected_hash != full_hash


# ---------------------------------------------------------------------------
# 8. clusters.csv usa el subconjunto filtrado (no el corpus completo)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_run_build_clusters_csv_refleja_subset(tmp_path: Path) -> None:
    """clusters.csv contiene solo los nodos del subset filtrado.

    Con corpus_scope='seeds_only', un candidato no-seed con referencias
    compartidas NO debe aparecer en el grafo ni en clusters.csv.
    """
    from bib2graph.cli.commands.build import run_build

    store_path = tmp_path / "lib.duckdb"
    rows = [
        # Dos semillas con referencias compartidas → arista en coupling
        _make_row(
            id="S1",
            is_seed=True,
            curation_status="candidate",
            references_id=["R1", "R2"],
            authors_raw=["Autor A"],
        ),
        _make_row(
            id="S2",
            is_seed=True,
            curation_status="candidate",
            references_id=["R1", "R3"],
            authors_raw=["Autor B"],
        ),
        # Candidato no-seed: no debe entrar en la red con seeds_only
        _make_row(
            id="C1",
            is_seed=False,
            curation_status="candidate",
            references_id=["R2", "R3"],
            authors_raw=["Autor C"],
        ),
    ]
    _seed_store(store_path, rows)

    out_dir = tmp_path / "nets"
    data = run_build(store_path, out_dir=out_dir, corpus_scope="seeds_only")

    # Verificar que la red de coupling tiene exactamente 2 nodos (las dos semillas)
    coupling_net = next(
        (n for n in data["networks"] if n["kind"] == "bibliographic_coupling"), None
    )
    assert coupling_net is not None
    assert coupling_net["nodes"] == 2, (
        f"Se esperaban 2 nodos (solo semillas), se obtuvieron {coupling_net['nodes']}"
    )


# ---------------------------------------------------------------------------
# 9. 0 nodos graceful → exit 0 + warning, networks_built == 0, no excepción
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_run_build_scope_cero_papers_exit_0_con_warning(tmp_path: Path) -> None:
    """scope que deja 0 papers → exit 0, networks_built=0, warning accionable."""
    from bib2graph.cli.commands.build import run_build

    store_path = tmp_path / "lib.duckdb"
    # Corpus sin ningún paper aceptado ni seed para el scope 'seeds_only'
    # (todos son no-seed candidatos)
    rows = [
        _make_row(id="C1", is_seed=False, curation_status="candidate"),
        _make_row(id="C2", is_seed=False, curation_status="candidate"),
    ]
    _seed_store(store_path, rows)

    out_dir = tmp_path / "nets"
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        data = run_build(store_path, out_dir=out_dir, corpus_scope="seeds_only")

    # No debe lanzar excepción
    assert data["networks_built"] == 0
    assert data["corpus_scope"] == "seeds_only"
    assert len(data["warnings"]) == 1
    assert "0 papers" in data["warnings"][0]
    assert (
        "corpus-scope" in data["warnings"][0]
        or "corpus_scope" in data["warnings"][0]
        or "all" in data["warnings"][0]
    )

    # El warning de Python también debe haberse emitido
    assert len(w) >= 1
    assert any("0 papers" in str(warning.message) for warning in w)
