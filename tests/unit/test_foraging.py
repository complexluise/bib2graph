"""Tests TDD del Hito 5 — Forager, scent, explain_candidate.

Tests prescriptos:
- Backward scent: ranking con orden conocido.
- Preview no muta el corpus + estima correctamente.
- max_candidates corta el ranking.
- Candidatos marcados (is_seed=False, candidate, provenance chaining_hop=1).
- Forward chaining con httpx MockTransport.
- explain_candidate sin [llm] falla con ImportError accionable.
- depth=2 lanza NotImplementedError.

Marcador: ``unit`` (sin red, sin I/O real).
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import httpx
import pyarrow as pa
import pytest

from bib2graph.corpus import Corpus
from bib2graph.foraging.base import GrowthPreview, RankedCandidates
from bib2graph.foraging.explain import explain_candidate
from bib2graph.foraging.forager import Forager
from bib2graph.foraging.scent import (
    compute_backward_scent,
    compute_forward_scent,
    rank_candidates,
)
from bib2graph.schemas import CORPUS_SCHEMA
from bib2graph.sources.openalex import OpenAlexSource

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.unit


def _base_row(
    id: str,
    *,
    openalex_id: str | None = None,
    is_seed: bool = True,
    references_id: list[str] | None = None,
    cited_by_id: list[str] | None = None,
    curation_status: str = "candidate",
) -> dict[str, Any]:
    return {
        "id": id,
        "openalex_id": openalex_id,
        "doi": None,
        "title": f"Paper {id}",
        "year": 2020,
        "abstract": None,
        "source": None,
        "language": None,
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


def _make_corpus(*rows: dict[str, Any]) -> Corpus:
    table = pa.Table.from_pylist(list(rows), schema=CORPUS_SCHEMA)
    return Corpus.from_arrow(table)


# ---------------------------------------------------------------------------
# Tests de scent puro (funciones puras)
# ---------------------------------------------------------------------------


class TestComputeBackwardScent:
    """Backward scent: frecuencia con que un ref aparece en el corpus."""

    def test_ranking_orden_conocido(self) -> None:
        """REF_A aparece en 3 papers, REF_B en 2, REF_C en 1.

        El orden esperado es REF_A > REF_B > REF_C.
        """
        rows = [
            _base_row("P1", references_id=["REF_A", "REF_B", "REF_C"]),
            _base_row("P2", references_id=["REF_A", "REF_B"]),
            _base_row("P3", references_id=["REF_A"]),
        ]
        scent = compute_backward_scent(rows)
        ranked = rank_candidates(scent)

        assert ranked[0] == ("REF_A", 3.0)
        assert ranked[1] == ("REF_B", 2.0)
        assert ranked[2] == ("REF_C", 1.0)

    def test_excluye_ids_del_corpus(self) -> None:
        """Los ids que ya son papers del corpus no son candidatos."""
        rows = [
            _base_row("P1", openalex_id="W1", references_id=["P2", "REF_X"]),
            _base_row("P2", openalex_id="W2", references_id=["REF_X"]),
        ]
        scent = compute_backward_scent(rows)
        # P2 está en el corpus (como id), no debe aparecer como candidato
        assert "P2" not in scent
        # W2 es openalex_id de P2, tampoco debe aparecer
        assert "W2" not in scent
        # REF_X sí es candidato nuevo
        assert "REF_X" in scent
        assert scent["REF_X"] == 2.0

    def test_corpus_vacio(self) -> None:
        scent = compute_backward_scent([])
        assert scent == {}

    def test_sin_referencias(self) -> None:
        rows = [_base_row("P1", references_id=None)]
        scent = compute_backward_scent(rows)
        assert scent == {}

    def test_desempate_estable_por_id(self) -> None:
        """Dos candidatos con el mismo scent se ordenan por id ascendente."""
        rows = [
            _base_row("P1", references_id=["REF_B", "REF_A"]),
        ]
        scent = compute_backward_scent(rows)
        ranked = rank_candidates(scent)
        # Ambos tienen scent=1.0; el primero alfabéticamente debe ir primero
        ids = [r[0] for r in ranked]
        assert ids == sorted(ids)


class TestComputeForwardScent:
    """Forward scent: cuántos papers del corpus cita el candidato."""

    def test_scent_basico(self) -> None:
        corpus_rows = [
            _base_row("P1", openalex_id="W1"),
            _base_row("P2", openalex_id="W2"),
        ]
        citing_rows = [
            # Este citante cita W1 y W2 del corpus
            _base_row(
                "CITER_A",
                openalex_id="WCITER_A",
                references_id=["W1", "W2"],
                is_seed=False,
            ),
            # Este citante solo cita W1
            _base_row(
                "CITER_B",
                openalex_id="WCITER_B",
                references_id=["W1"],
                is_seed=False,
            ),
        ]
        # El scent de CITER_A debe ser 2.0 (cita 2 papers del corpus)
        # El scent de CITER_B debe ser 1.0
        scent = compute_forward_scent(corpus_rows, citing_rows)
        assert scent.get("CITER_A", 0.0) == 2.0
        assert scent.get("CITER_B", 0.0) == 1.0


# ---------------------------------------------------------------------------
# Tests del Forager
# ---------------------------------------------------------------------------


class TestForagerBackward:
    """Forager backward: solo trabaja localmente (sin red)."""

    def test_preview_no_muta_corpus(self) -> None:
        """preview() no debe cambiar el corpus de entrada."""
        rows = [_base_row("P1", references_id=["REF_A"])]
        corpus = _make_corpus(*rows)
        original_len = len(corpus)

        source = MagicMock()
        forager = Forager(source, depth=1)
        forager.preview(corpus, direction="backward")

        assert len(corpus) == original_len

    def test_preview_estima(self) -> None:
        """preview() devuelve GrowthPreview con estimated_new correcto."""
        rows = [
            _base_row("P1", references_id=["REF_A", "REF_B"]),
            _base_row("P2", references_id=["REF_A"]),
        ]
        corpus = _make_corpus(*rows)

        source = MagicMock()
        forager = Forager(source, depth=1)
        preview = forager.preview(corpus, direction="backward")

        assert isinstance(preview, GrowthPreview)
        assert preview.estimated_new == 2  # REF_A y REF_B
        assert preview.by_direction["backward"] == 2

    def test_max_candidates_corta_ranking(self) -> None:
        """max_candidates limita el número de candidatos en el ranking."""
        rows = [
            _base_row("P1", references_id=["REF_A", "REF_B", "REF_C"]),
        ]
        corpus = _make_corpus(*rows)

        source = MagicMock()
        forager = Forager(source, depth=1, max_candidates=2)
        ranked = forager.chain(corpus, direction="backward")

        assert isinstance(ranked, RankedCandidates)
        assert len(ranked.ranking) == 2

    def test_candidatos_marcados_correctamente(self) -> None:
        """Los candidatos tienen is_seed=False, candidate, provenance hop=1."""
        rows = [_base_row("P1", references_id=["REF_A"])]
        corpus = _make_corpus(*rows)

        source = MagicMock()
        forager = Forager(source, depth=1)
        ranked = forager.chain(corpus, direction="backward")

        cand_table = ranked.corpus.to_arrow().to_pylist()
        assert len(cand_table) == 1
        cand = cand_table[0]

        assert cand["is_seed"] is False
        assert cand["curation_status"] == "candidate"

        provenance = json.loads(cand["provenance"])
        assert isinstance(provenance, list)
        assert len(provenance) >= 1
        event = provenance[0]
        assert event["chaining_hop"] == 1
        assert "backward" in event["source"]

    def test_chain_no_muta_corpus_entrada(self) -> None:
        """chain() no muta el corpus de entrada."""
        rows = [_base_row("P1", references_id=["REF_A"])]
        corpus = _make_corpus(*rows)
        original_len = len(corpus)

        source = MagicMock()
        forager = Forager(source, depth=1)
        forager.chain(corpus, direction="backward")

        assert len(corpus) == original_len


class TestForagerPreviewNoRed:
    """preview() debe ser completamente local — CERO llamadas a fetch_citing."""

    def _make_counting_source(self) -> tuple[Any, list[str]]:
        """Source falso que registra cada llamada a fetch_citing."""
        calls: list[str] = []

        class CountingSource:
            def fetch_citing(self, oa_id: str) -> list[dict[str, Any]]:
                calls.append(oa_id)
                raise AssertionError(
                    f"fetch_citing fue llamado con '{oa_id}' desde preview() — "
                    "preview() debe ser local y no tocar la red"
                )

        return CountingSource(), calls

    def test_preview_both_cero_fetch_citing(self) -> None:
        """preview(direction='both') no debe llamar a fetch_citing."""
        rows = [_base_row("P1", openalex_id="W1", references_id=["REF_A"])]
        corpus = _make_corpus(*rows)
        source, calls = self._make_counting_source()

        forager = Forager(source, depth=1)  # type: ignore[arg-type]
        preview = forager.preview(corpus, direction="both")

        assert calls == [], f"fetch_citing fue llamado {len(calls)} veces"
        assert isinstance(preview, GrowthPreview)

    def test_preview_forward_cero_fetch_citing(self) -> None:
        """preview(direction='forward') no debe llamar a fetch_citing."""
        rows = [_base_row("P1", openalex_id="W1", references_id=None)]
        corpus = _make_corpus(*rows)
        source, calls = self._make_counting_source()

        forager = Forager(source, depth=1)  # type: ignore[arg-type]
        preview = forager.preview(corpus, direction="forward")

        assert calls == [], f"fetch_citing fue llamado {len(calls)} veces"
        assert isinstance(preview, GrowthPreview)

    def test_preview_forward_marca_forward_requires_fetch(self) -> None:
        """preview(forward) marca forward_requires_fetch=True y forward=0."""
        rows = [_base_row("P1", openalex_id="W1", references_id=["REF_A"])]
        corpus = _make_corpus(*rows)
        source, _ = self._make_counting_source()

        forager = Forager(source, depth=1)  # type: ignore[arg-type]
        preview = forager.preview(corpus, direction="forward")

        assert preview.forward_requires_fetch is True
        assert preview.by_direction["forward"] == 0
        assert preview.estimated_new == 0  # solo forward pedido, no estimable

    def test_preview_both_marca_forward_requires_fetch(self) -> None:
        """preview(both) marca forward_requires_fetch=True y forward=0."""
        rows = [_base_row("P1", openalex_id="W1", references_id=["REF_A", "REF_B"])]
        corpus = _make_corpus(*rows)
        source, _ = self._make_counting_source()

        forager = Forager(source, depth=1)  # type: ignore[arg-type]
        preview = forager.preview(corpus, direction="both")

        assert preview.forward_requires_fetch is True
        assert preview.by_direction["forward"] == 0
        # estimated_new cuenta solo backward (2 refs) + forward (0, no estimable)
        assert preview.estimated_new == 2
        assert preview.by_direction["backward"] == 2

    def test_preview_backward_no_marca_forward_requires_fetch(self) -> None:
        """preview(backward) tiene forward_requires_fetch=False (estimación exacta)."""
        rows = [_base_row("P1", references_id=["REF_A"])]
        corpus = _make_corpus(*rows)
        source, calls = self._make_counting_source()

        forager = Forager(source, depth=1)  # type: ignore[arg-type]
        preview = forager.preview(corpus, direction="backward")

        assert calls == []
        assert preview.forward_requires_fetch is False
        assert preview.estimated_new == 1
        assert preview.by_direction["backward"] == 1


class TestForagerForward:
    """Forager forward: usa MockTransport para simular fetch_citing."""

    def _make_mock_transport(
        self, citing_works: list[dict[str, Any]]
    ) -> httpx.MockTransport:
        """Crea un MockTransport que devuelve citing_works al primer GET /works."""

        def handler(request: httpx.Request) -> httpx.Response:
            payload = {
                "results": citing_works,
                "meta": {"next_cursor": None},
            }
            return httpx.Response(200, json=payload)

        return httpx.MockTransport(handler)

    def test_forward_chaining_con_mock_transport(self) -> None:
        """Forward chaining: candidatos traídos por fetch_citing con scent correcto."""
        # Corpus con 1 paper que tiene openalex_id
        rows = [_base_row("P1", openalex_id="W1", references_id=None)]
        corpus = _make_corpus(*rows)

        # Citante que cita W1 (su reference_id incluye W1)
        citing_work = {
            "id": "https://openalex.org/W9999",
            "title": "Citing Paper",
            "publication_year": 2022,
            "language": "en",
            "doi": None,
            "abstract_inverted_index": None,
            "authorships": [],
            "keywords": [],
            "referenced_works": ["https://openalex.org/W1"],
            "primary_location": None,
            "type": "article",
        }
        transport = self._make_mock_transport([citing_work])
        source = OpenAlexSource(transport=transport)

        forager = Forager(source, depth=1)
        ranked = forager.chain(corpus, direction="forward")

        assert isinstance(ranked, RankedCandidates)
        # Debe haber al menos 1 candidato
        assert len(ranked.ranking) >= 1
        # El candidato forward tiene is_seed=False
        cand_rows = ranked.corpus.to_arrow().to_pylist()
        assert all(not r["is_seed"] for r in cand_rows)

    def test_chain_forward_si_fetchea(self) -> None:
        """chain(forward) SÍ llama a fetch_citing — el fetch es correcto en chain."""
        fetch_calls: list[str] = []

        class TrackingSource:
            def fetch_citing(self, oa_id: str) -> list[dict[str, Any]]:
                fetch_calls.append(oa_id)
                return []  # Sin candidatos; basta verificar que se llamó

        rows = [_base_row("P1", openalex_id="W1", references_id=None)]
        corpus = _make_corpus(*rows)
        source = TrackingSource()

        forager = Forager(source, depth=1)  # type: ignore[arg-type]
        forager.chain(corpus, direction="forward")

        assert "W1" in fetch_calls, "chain(forward) debe llamar fetch_citing"

    def test_forward_sin_fetch_citing_falla_claro(self) -> None:
        """Si el source no tiene fetch_citing, falla con AttributeError claro."""

        class SimpleFakeSource:
            def seed(self, query: str) -> None:
                return None

            def load(self, path: str) -> None:
                return None

        rows = [_base_row("P1", openalex_id="W1")]
        corpus = _make_corpus(*rows)
        forager = Forager(SimpleFakeSource(), depth=1)  # type: ignore[arg-type]

        with pytest.raises(AttributeError, match="fetch_citing"):
            forager.chain(corpus, direction="forward")


class TestForagerDepth:
    def test_depth_mayor_a_1_lanza_not_implemented(self) -> None:
        """depth > 1 lanza NotImplementedError claro."""
        source = MagicMock()
        with pytest.raises(NotImplementedError, match="profundidad"):
            Forager(source, depth=2)


class TestExplainCandidate:
    def test_sin_llm_falla_con_import_error_accionable(self) -> None:
        """explain_candidate sin [llm] lanza ImportError con instrucciones."""
        rows = [_base_row("P1")]
        corpus = _make_corpus(*rows)

        with pytest.raises(ImportError, match="uv sync --extra llm"):
            explain_candidate(corpus, "P1")
