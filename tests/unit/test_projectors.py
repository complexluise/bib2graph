"""Tests TDD del Hito 2 — proyectores (Projector + 5 implementaciones).

Tests prescriptos por docs/ROADMAP.md §Hito 2 "Tests TDD — los justos":
- Un grafo sintético por proyector con resultado calculado a mano (5).
- En coupling: paper con is_seed=False participa (scope full).
- En co-citación: default scope="seeds_only".
- En co-autoría: verificar filtro min_weight.

Marcador: ``unit`` (sin red, sin I/O).
"""

from __future__ import annotations

import pyarrow as pa
import pytest

from bib2graph.networks.projectors import (
    MIN_WEIGHT_DEFAULT,
    AuthorCollaborationProjector,
    BibliographicCouplingProjector,
    CoCitationProjector,
    InstitutionCollaborationProjector,
    KeywordCoOccurrenceProjector,
)
from bib2graph.schemas import CORPUS_SCHEMA

# ---------------------------------------------------------------------------
# Helpers para construir tablas Arrow sintéticas mínimas
# ---------------------------------------------------------------------------


def _make_table(rows: list[dict[str, object]]) -> pa.Table:
    """Construye tabla Arrow con el schema canónico desde lista de dicts."""
    return pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)


def _base_row(
    id: str,
    title: str,
    *,
    is_seed: bool = True,
    references_id: list[str] | None = None,
    cited_by_id: list[str] | None = None,
    authors_id: list[str] | None = None,
    institutions_id: list[str] | None = None,
    keywords_id: list[str] | None = None,
) -> dict[str, object]:
    """Fila mínima para tests de proyectores."""
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
        "curation_status": "candidate",
        "provenance": None,
        "authors_raw": None,
        "authors_id": authors_id,
        "authors_affiliations": None,
        "keywords_raw": None,
        "keywords_id": keywords_id,
        "institutions_raw": None,
        "institutions_id": institutions_id,
        "references_id": references_id,
        "references_doi": None,
        "cited_by_id": cited_by_id,
    }


# ---------------------------------------------------------------------------
# Constante
# ---------------------------------------------------------------------------


def test_min_weight_default_valor() -> None:
    """MIN_WEIGHT_DEFAULT es 1 (sin filtro)."""
    assert MIN_WEIGHT_DEFAULT == 1


# ---------------------------------------------------------------------------
# 1. BibliographicCouplingProjector
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_coupling_grafo_sintetico() -> None:
    """Acoplamiento bibliográfico: peso = refs compartidas calculado a mano.

    Escenario:
      P1 cita [R1, R2, R3]
      P2 cita [R1, R2]
      P3 cita [R3]

    Resultado esperado:
      P1—P2: 2 refs compartidas (R1, R2)
      P1—P3: 1 ref compartida (R3)
      P2—P3: 0 refs compartidas → sin arista
    """
    rows = [
        _base_row("P1", "Paper 1", references_id=["R1", "R2", "R3"]),
        _base_row("P2", "Paper 2", references_id=["R1", "R2"]),
        _base_row("P3", "Paper 3", references_id=["R3"]),
    ]
    table = _make_table(rows)
    g = BibliographicCouplingProjector().project(table)

    assert g.number_of_nodes() == 3
    assert g.has_edge("P1", "P2")
    assert g["P1"]["P2"]["weight"] == 2
    assert g.has_edge("P1", "P3")
    assert g["P1"]["P3"]["weight"] == 1
    assert not g.has_edge("P2", "P3")


@pytest.mark.unit
def test_coupling_incluye_non_seed_en_scope_full() -> None:
    """scope='full' incluye papers con is_seed=False en el acoplamiento.

    P1 (seed) y P2 (no-seed) comparten ref R1.
    Ambos deben aparecer como nodos y tener arista.
    """
    rows = [
        _base_row("P1", "Seed paper", is_seed=True, references_id=["R1", "R2"]),
        _base_row("P2", "Non-seed paper", is_seed=False, references_id=["R1", "R3"]),
    ]
    table = _make_table(rows)
    g = BibliographicCouplingProjector().project(table, scope="full")

    assert g.has_node("P1")
    assert g.has_node("P2")
    assert g.has_edge("P1", "P2")
    assert g["P1"]["P2"]["weight"] == 1


# ---------------------------------------------------------------------------
# 2. AuthorCollaborationProjector — también verifica filtro min_weight
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_author_collab_grafo_sintetico() -> None:
    """Co-autoría: peso = nº de papers co-firmados, calculado a mano.

    Escenario:
      Paper A: autores [A1, A2]
      Paper B: autores [A1, A2, A3]
      Paper C: autores [A2, A3]

    Resultado esperado:
      A1—A2: 2 papers (A y B)
      A1—A3: 1 paper (B)
      A2—A3: 2 papers (B y C)
    """
    rows = [
        _base_row("PA", "Paper A", authors_id=["A1", "A2"]),
        _base_row("PB", "Paper B", authors_id=["A1", "A2", "A3"]),
        _base_row("PC", "Paper C", authors_id=["A2", "A3"]),
    ]
    table = _make_table(rows)
    g = AuthorCollaborationProjector().project(table)

    assert g.has_edge("A1", "A2")
    assert g["A1"]["A2"]["weight"] == 2
    assert g.has_edge("A1", "A3")
    assert g["A1"]["A3"]["weight"] == 1
    assert g.has_edge("A2", "A3")
    assert g["A2"]["A3"]["weight"] == 2


@pytest.mark.unit
def test_author_collab_min_weight_filtra_aristas() -> None:
    """min_weight=2 elimina aristas con peso < 2.

    Con el escenario anterior: A1—A3 tiene peso 1 → se elimina.
    """
    rows = [
        _base_row("PA", "Paper A", authors_id=["A1", "A2"]),
        _base_row("PB", "Paper B", authors_id=["A1", "A2", "A3"]),
        _base_row("PC", "Paper C", authors_id=["A2", "A3"]),
    ]
    table = _make_table(rows)
    g = AuthorCollaborationProjector().project(table, min_weight=2)

    assert g.has_edge("A1", "A2")
    assert g.has_edge("A2", "A3")
    assert not g.has_edge("A1", "A3")  # peso 1 < 2


# ---------------------------------------------------------------------------
# 3. InstitutionCollaborationProjector
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_institution_collab_grafo_sintetico() -> None:
    """Co-autoría institucional: peso = nº de papers con co-aparición.

    Escenario:
      Paper A: instituciones [I1, I2]
      Paper B: instituciones [I1, I3]
      Paper C: instituciones [I2, I3]

    Resultado esperado:
      I1—I2: 1 (Paper A)
      I1—I3: 1 (Paper B)
      I2—I3: 1 (Paper C)
    """
    rows = [
        _base_row("PA", "Paper A", institutions_id=["I1", "I2"]),
        _base_row("PB", "Paper B", institutions_id=["I1", "I3"]),
        _base_row("PC", "Paper C", institutions_id=["I2", "I3"]),
    ]
    table = _make_table(rows)
    g = InstitutionCollaborationProjector().project(table)

    assert g.has_edge("I1", "I2")
    assert g["I1"]["I2"]["weight"] == 1
    assert g.has_edge("I1", "I3")
    assert g["I1"]["I3"]["weight"] == 1
    assert g.has_edge("I2", "I3")
    assert g["I2"]["I3"]["weight"] == 1


# ---------------------------------------------------------------------------
# 4. KeywordCoOccurrenceProjector
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_keyword_cooccurrence_grafo_sintetico() -> None:
    """Co-ocurrencia de keywords: peso = nº de papers donde co-ocurren.

    Escenario:
      Paper A: keywords [K1, K2, K3]
      Paper B: keywords [K1, K2]
      Paper C: keywords [K2, K3]

    Resultado esperado:
      K1—K2: 2 (A y B)
      K1—K3: 1 (A)
      K2—K3: 2 (A y C)
    """
    rows = [
        _base_row("PA", "Paper A", keywords_id=["K1", "K2", "K3"]),
        _base_row("PB", "Paper B", keywords_id=["K1", "K2"]),
        _base_row("PC", "Paper C", keywords_id=["K2", "K3"]),
    ]
    table = _make_table(rows)
    g = KeywordCoOccurrenceProjector().project(table)

    assert g.has_edge("K1", "K2")
    assert g["K1"]["K2"]["weight"] == 2
    assert g.has_edge("K1", "K3")
    assert g["K1"]["K3"]["weight"] == 1
    assert g.has_edge("K2", "K3")
    assert g["K2"]["K3"]["weight"] == 2


# ---------------------------------------------------------------------------
# 5. CoCitationProjector
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_cocitation_default_scope_seeds_only() -> None:
    """CoCitationProjector usa scope='seeds_only' por defecto.

    Escenario: P1 (seed) y P2 (non-seed) ambos citados por C1, C2.
    Con scope='seeds_only' solo P1 entra; sin par posible, grafo vacío.
    Verificamos: P2 NO aparece como nodo (no-seed excluido) y no hay aristas
    (la co-citación requiere al menos 2 seeds).

    Con scope='full': ambos entran, hay arista P1-P2 con peso 2.
    """
    rows = [
        _base_row("P1", "Seed 1", is_seed=True, cited_by_id=["C1", "C2"]),
        _base_row("P2", "Non-seed", is_seed=False, cited_by_id=["C1", "C2"]),
    ]
    table = _make_table(rows)

    # Default scope = seeds_only: P2 no entra, grafo sin aristas
    g_seeds = CoCitationProjector().project(table)
    assert "P2" not in g_seeds.nodes
    assert g_seeds.number_of_edges() == 0

    # scope=full: ambos entran, arista P1-P2 con peso 2
    g_full = CoCitationProjector().project(table, scope="full")
    assert g_full.has_edge("P1", "P2")
    assert g_full["P1"]["P2"]["weight"] == 2


@pytest.mark.unit
def test_cocitation_grafo_sintetico_peso_correcto() -> None:
    """Co-citación: peso = nº de papers que citan a ambos.

    Escenario: papers P1, P2, P3 todos seeds.
    P1 citado por [C1, C2, C3]
    P2 citado por [C1, C2]
    P3 citado por [C3, C4]

    Resultado esperado (co-citación):
      P1—P2: 2 (C1 y C2 citan a ambos)
      P1—P3: 1 (C3 cita a ambos)
      P2—P3: 0 → sin arista
    """
    rows = [
        _base_row("P1", "Paper 1", is_seed=True, cited_by_id=["C1", "C2", "C3"]),
        _base_row("P2", "Paper 2", is_seed=True, cited_by_id=["C1", "C2"]),
        _base_row("P3", "Paper 3", is_seed=True, cited_by_id=["C3", "C4"]),
    ]
    table = _make_table(rows)
    g = CoCitationProjector().project(table, scope="seeds_only")

    assert g.has_edge("P1", "P2")
    assert g["P1"]["P2"]["weight"] == 2
    assert g.has_edge("P1", "P3")
    assert g["P1"]["P3"]["weight"] == 1
    assert not g.has_edge("P2", "P3")
