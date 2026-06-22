"""Tests TDD del Hito R4 — scent bibliométrico vía proyectores.

Tests prescriptos (ROADMAP Hito R4):
- Ranking por scent-vía-proyectores: candidatos con acoplamiento/centralidad
  CONOCIDOS Y CALCULADOS A MANO salen en el ORDEN esperado.
- Determinismo: mismo corpus → mismo ranking (regresión).
- Que ``import`` de ``explain_candidate`` FALLE (la superficie ya no lo expone).

## Fórmulas documentadas (de foraging/scent.py)

Backward score(X) = |{Pi ∈ corpus : X ∈ Pi.references_id}|
  → usa collect_item_to_papers(corpus, Col.ID, Col.REFERENCES_ID)

Forward score(Y) — citación directa al corpus (fix forward-scent, Wohlin):
  corpus_ids = {Pi.id | Pi.source_id : Pi ∈ corpus}
  forward_score(Y) = |{ref ∈ Y.references_id : ref ∈ corpus_ids}|
  → cuántos corpus-papers cita Y directamente
  → robusto ante references_id ralas en el corpus (no degenera a 0)
  → CAMBIO vs. as-built R4: el viejo score medía acoplamiento bibliográfico
    (corpus-papers que comparten refs con Y), que degeneraba a 0 cuando
    el corpus tiene references_id vacías (estado común tras un seed).

Marcador: ``unit`` (sin red, sin I/O real).
"""

from __future__ import annotations

from typing import Any

import pytest

from bib2graph.foraging.scent import (
    compute_backward_scent,
    compute_forward_scent,
    rank_candidates,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row(
    id: str,
    *,
    source_id: str | None = None,
    references_id: list[str] | None = None,
    is_seed: bool = True,
) -> dict[str, Any]:
    return {
        "id": id,
        "source_id": source_id,
        "doi": None,
        "title": f"Paper {id}",
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


# ---------------------------------------------------------------------------
# 1. Ranking backward por acoplamiento (calculado a mano)
# ---------------------------------------------------------------------------


class TestBackwardScentStructural:
    """Backward score vía collect_item_to_papers — calculado a mano.

    Corpus sintético:
      P1 cita [A, B, C]
      P2 cita [A, B]
      P3 cita [A]

    Índice item_to_papers (references_id):
      A → [P1, P2, P3]  → score = 3
      B → [P1, P2]      → score = 2
      C → [P1]          → score = 1

    Candidatos: A, B, C (ninguno es id de corpus-paper)
    Orden esperado: A (3.0) > B (2.0) > C (1.0)
    """

    def test_orden_conocido_calculado_a_mano(self) -> None:
        rows = [
            _row("P1", references_id=["A", "B", "C"]),
            _row("P2", references_id=["A", "B"]),
            _row("P3", references_id=["A"]),
        ]
        scent = compute_backward_scent(rows)
        ranked = rank_candidates(scent)

        assert ranked[0] == ("A", 3.0), "A debe tener score 3 (citado por P1,P2,P3)"
        assert ranked[1] == ("B", 2.0), "B debe tener score 2 (citado por P1,P2)"
        assert ranked[2] == ("C", 1.0), "C debe tener score 1 (citado solo por P1)"

    def test_candidato_con_mismo_id_corpus_excluido(self) -> None:
        """Un candidato que coincide con el id de un corpus-paper no rankea."""
        rows = [
            _row("P1", source_id="W1", references_id=["P2", "EXT_A"]),
            _row("P2", source_id="W2", references_id=["EXT_A"]),
        ]
        scent = compute_backward_scent(rows)
        assert "P2" not in scent, "P2 es corpus-paper, no debe ser candidato"
        assert "W2" not in scent, "W2 es source_id de P2, no debe ser candidato"
        assert scent.get("EXT_A") == 2.0

    def test_score_unico_por_paper_aunque_ref_repetida(self) -> None:
        """Un paper con la misma ref duplicada cuenta como 1, no 2."""
        rows = [
            _row("P1", references_id=["A", "A"]),  # A duplicada en la misma fila
        ]
        scent = compute_backward_scent(rows)
        # A aparece en 1 paper (P1), aunque el paper la liste dos veces.
        # collect_item_to_papers no deduplica dentro del mismo paper,
        # pero el score usa set(papers) → P1 se cuenta una vez.
        assert scent["A"] == 1.0


# ---------------------------------------------------------------------------
# 2. Ranking forward por citación directa (calculado a mano)
# ---------------------------------------------------------------------------


class TestForwardScentStructural:
    """Forward score vía citación directa al corpus — calculado a mano.

    La fórmula es:
        corpus_ids = {Pi.id | Pi.source_id : Pi ∈ corpus}
        forward_score(Y) = |{ref ∈ Y.references_id : ref ∈ corpus_ids}|

    CAMBIO vs. as-built R4: el viejo score era acoplamiento bibliográfico
    (cuántos corpus-papers comparten referencias con Y). El nuevo score
    es citación directa (cuántos corpus-papers cita Y explícitamente en
    su lista de referencias). Es robusto ante corpus con references_id ralas.

    Corpus sintético:
      P1 (id="P1", source_id="W1")
      P2 (id="P2", source_id="W2")

    corpus_ids = {"P1", "W1", "P2", "W2"}

    Candidatos (citing_rows):
      Y1 cita [P1, W2]  → 2 corpus-ids en refs → score = 2
      Y2 cita [P1]      → 1 corpus-id en refs  → score = 1
      Y3 cita [W2]      → 1 corpus-id en refs  → score = 1
      Y4 cita [EXT]     → ningún corpus-id     → excluido (score = 0)
    """

    def test_orden_conocido_calculado_a_mano(self) -> None:
        corpus = [
            _row("P1", source_id="W1"),
            _row("P2", source_id="W2"),
        ]
        citing = [
            _row("Y1", references_id=["P1", "W2"], is_seed=False),
            _row("Y2", references_id=["P1"], is_seed=False),
            _row("Y3", references_id=["W2"], is_seed=False),
            _row("Y4", references_id=["EXT"], is_seed=False),
        ]

        scent = compute_forward_scent(corpus, citing)

        assert scent.get("Y1") == 2.0, (
            "Y1 cita P1 y W2 (ambos en corpus_ids) → score = 2"
        )
        assert scent.get("Y2") == 1.0, "Y2 cita P1 (en corpus_ids) → score = 1"
        assert scent.get("Y3") == 1.0, "Y3 cita W2 (source_id de P2) → score = 1"
        assert "Y4" not in scent, "Y4 no cita ningún corpus-paper → excluido"

        ranked = rank_candidates(scent)
        assert ranked[0][0] == "Y1", "Y1 debe liderar el ranking (score 2)"

    def test_desempate_estable_por_id_ascendente(self) -> None:
        """Y2 e Y3 tienen score 1; Y2 < Y3 alfabéticamente → Y2 primero."""
        corpus = [
            _row("P1", source_id="W1"),
            _row("P2", source_id="W2"),
        ]
        citing = [
            _row("Y3", references_id=["P1"], is_seed=False),
            _row("Y2", references_id=["P2"], is_seed=False),
        ]
        scent = compute_forward_scent(corpus, citing)
        ranked = rank_candidates(scent)
        # Ambos tienen score 1.0; desempate por id ascendente
        assert ranked[0][0] == "Y2"
        assert ranked[1][0] == "Y3"

    def test_candidato_en_corpus_excluido(self) -> None:
        """Un candidato forward que ya está en el corpus no aparece."""
        corpus = [
            _row("P1", source_id="W1", references_id=["BG1"]),
        ]
        citing = [
            _row("P1", references_id=["W1"], is_seed=False),  # mismo id que corpus
        ]
        scent = compute_forward_scent(corpus, citing)
        assert "P1" not in scent

    def test_citante_sin_match_en_corpus_excluido(self) -> None:
        """Si Y no cita ningún corpus-paper, queda excluido (score = 0)."""
        corpus = [_row("P1", source_id="W1")]
        citing = [_row("Y1", references_id=["BG1"], is_seed=False)]
        scent = compute_forward_scent(corpus, citing)
        assert scent == {}

    def test_corpus_con_references_id_ralas_no_degrada_score(self) -> None:
        """Fix del forward-scent: corpus con references_id=None no degrada a 0.

        AS-BUILT (acoplamiento): si corpus tiene references_id=None, el índice
        ref_to_corpus_papers queda vacío → score=0 para todo citante → pérdida.

        CON FIX (citación directa): Y cita a corpus-papers por su id/source_id;
        references_id del corpus no importa → score > 0 para citantes reales.

        Escenario del steering:
          - Corpus con references_id ralas (None)
          - Citante Y que cita a 2 corpus-papers directamente
          - As-built: score(Y) = 0 (se perdía)
          - Con fix: score(Y) = 2
        """
        corpus = [
            _row("C1", source_id="OA1", references_id=None),
            _row("C2", source_id="OA2", references_id=None),
        ]
        citing = [
            _row(
                "Y",
                references_id=["OA1", "OA2"],  # cita a C1 y C2 por source_id
                is_seed=False,
            ),
        ]
        scent = compute_forward_scent(corpus, citing)
        assert scent.get("Y") == 2.0, (
            "Y cita 2 corpus-papers directamente → score=2 "
            "(as-built habría dado 0 porque references_id del corpus es None)"
        )


# ---------------------------------------------------------------------------
# 3. Determinismo — mismo corpus → mismo ranking
# ---------------------------------------------------------------------------


class TestDeterminismo:
    """Regresión: el ranking debe ser idéntico en dos llamadas con el mismo corpus."""

    def test_backward_determinista(self) -> None:
        rows = [
            _row("P1", references_id=["A", "B", "C"]),
            _row("P2", references_id=["A", "D"]),
            _row("P3", references_id=["B"]),
        ]
        scent1 = compute_backward_scent(rows)
        scent2 = compute_backward_scent(rows)
        ranked1 = rank_candidates(scent1)
        ranked2 = rank_candidates(scent2)
        assert ranked1 == ranked2

    def test_forward_determinista(self) -> None:
        # corpus_ids = {"P1", "W1", "P2"}
        corpus = [
            _row("P1", source_id="W1"),
            _row("P2"),
        ]
        citing = [
            # Y1 cita P1 (corpus-id) → score = 1
            _row("Y1", references_id=["P1"], is_seed=False),
            # Y2 cita W1 (source_id de P1) y P2 → score = 2
            _row("Y2", references_id=["W1", "P2"], is_seed=False),
        ]
        scent1 = compute_forward_scent(corpus, citing)
        scent2 = compute_forward_scent(corpus, citing)
        ranked1 = rank_candidates(scent1)
        ranked2 = rank_candidates(scent2)
        assert ranked1 == ranked2


# ---------------------------------------------------------------------------
# 4. explain_candidate ya no existe (R4, ADR 0022)
# ---------------------------------------------------------------------------


class TestExplainCandidateEliminado:
    """Verifica que explain_candidate fue eliminado de la superficie pública."""

    def test_foraging_no_expone_explain_candidate(self) -> None:
        """bib2graph.foraging no debe tener explain_candidate (R4)."""
        import importlib

        mod = importlib.import_module("bib2graph.foraging")
        assert not hasattr(mod, "explain_candidate"), (
            "explain_candidate fue eliminado en R4 — no debe estar en bib2graph.foraging"
        )

    def test_modulo_foraging_explain_no_existe(self) -> None:
        """El archivo foraging/explain.py fue borrado en R4."""
        import importlib

        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("bib2graph.foraging.explain")

    def test_llm_extra_no_en_pyproject(self) -> None:
        """El extra [llm] fue eliminado de pyproject.toml (R4, ADR 0022).

        Verifica que importlib.metadata no lo lista como extra del paquete.
        """
        import importlib.metadata

        try:
            dist = importlib.metadata.distribution("bib2graph")
            extras = dist.metadata.get_all("Provides-Extra") or []
            assert "llm" not in extras, (
                "El extra [llm] fue eliminado en R4 — no debe estar en los extras"
            )
        except importlib.metadata.PackageNotFoundError:
            # En entorno de editable install sin metadata, saltamos este check
            pytest.skip("bib2graph no encontrado como paquete instalado con metadata")


# ---------------------------------------------------------------------------
# 5. collect_item_to_papers reusado (sin duplicar lógica del proyector)
# ---------------------------------------------------------------------------


class TestCollectItemToPapers:
    """Verifica que el primitivo del proyector funciona correctamente."""

    def test_indice_correcto(self) -> None:
        """collect_item_to_papers construye {item: [papers]} correctamente."""
        from bib2graph.constants import Col
        from bib2graph.networks.projectors import collect_item_to_papers

        rows: list[dict[str, object]] = [
            {"id": "P1", "references_id": ["A", "B"]},
            {"id": "P2", "references_id": ["A", "C"]},
            {"id": "P3", "references_id": None},
        ]
        idx = collect_item_to_papers(rows, Col.ID, Col.REFERENCES_ID)

        assert set(idx["A"]) == {"P1", "P2"}
        assert idx["B"] == ["P1"]
        assert idx["C"] == ["P2"]
        assert "D" not in idx

    def test_filas_sin_lista_ignoradas(self) -> None:
        """Filas con campo de lista nulo o vacío no producen entradas."""
        from bib2graph.constants import Col
        from bib2graph.networks.projectors import collect_item_to_papers

        rows: list[dict[str, object]] = [
            {"id": "P1", "references_id": None},
            {"id": "P2", "references_id": []},
        ]
        idx = collect_item_to_papers(rows, Col.ID, Col.REFERENCES_ID)
        assert idx == {}
