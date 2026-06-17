"""Tests TDD del Hito 5 + R4 — Forager y scent bibliométrico.

Tests prescriptos:
- Backward scent: ranking con orden conocido (score = acoplamiento hacia atrás).
- Forward scent: ranking por citación directa al corpus (fix forward-scent).
- Preview no muta el corpus + estima correctamente.
- max_candidates corta el ranking.
- Candidatos marcados (is_seed=False, candidate, provenance chaining_hop=1).
- Forward chaining con httpx MockTransport.
- depth=2 lanza NotImplementedError.

**R4 — cambio de scent (ADR 0020 enmienda + ADR 0022):**
``explain_candidate`` y el extra ``[llm]`` fueron ELIMINADOS del producto.
Los tests de ``explain_candidate`` / ``[llm]`` se RETIRAN (la capacidad ya
no existe).  Los tests de scent que asertaban la fórmula de frecuencia de
enlace se AJUSTAN a la nueva fórmula estructural:

- Backward: score = |{Pi ∈ corpus : X ∈ Pi.references_id}| — numéricamente
  igual al viejo conteo, pero computable vía ``collect_item_to_papers``.
- Forward (fix forward-scent, Wohlin):
    corpus_ids = {Pi.id | Pi.openalex_id : Pi ∈ corpus}
    forward_score(Y) = |{ref ∈ Y.references_id : ref ∈ corpus_ids}|
  (citación directa al corpus: cuántos corpus-papers cita Y explícitamente).
  CAMBIO RESPECTO DEL AS-BUILT R4: el viejo score era acoplamiento bibliográfico
  (corpus-papers que comparten refs con Y), que degeneraba a 0 cuando el corpus
  tiene references_id ralas (estado común tras un seed).

Marcador: ``unit`` (sin red, sin I/O real).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import httpx
import pyarrow as pa
import pytest

from bib2graph.corpus import Corpus
from bib2graph.foraging.base import GrowthPreview, RankedCandidates
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
    """Backward scent: acoplamiento hacia atrás.

    score(X) = |{Pi ∈ corpus : X ∈ Pi.references_id}|

    La fórmula numérica es la misma que el viejo conteo de frecuencia de enlace,
    pero ahora se computa usando el primitivo ``collect_item_to_papers`` del
    proyector (no reimplementando el Counter).
    """

    def test_ranking_orden_conocido(self) -> None:
        """REF_A aparece en 3 papers, REF_B en 2, REF_C en 1.

        Score = cuántos corpus-papers listan al candidato en references_id.
        El orden esperado es REF_A (3.0) > REF_B (2.0) > REF_C (1.0).
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
    """Forward scent: citación directa al corpus (fix forward-scent, Wohlin).

    score(Y) = |{ref ∈ Y.references_id : ref ∈ corpus_ids}|
    donde corpus_ids = {Pi.id | Pi.openalex_id : Pi ∈ corpus}

    CAMBIO RESPECTO DEL AS-BUILT R4 (ADR 0020 enmienda, fix forward-scent):
    El viejo score era acoplamiento bibliográfico:
      |{Pi ∈ corpus : Pi.references_id ∩ Y.references_id ≠ ∅}|
    que degeneraba a 0 cuando el corpus tiene references_id ralas.
    El nuevo score es citación directa al corpus: cuántos corpus-papers
    aparecen en Y.references_id (usando id u openalex_id del corpus).
    """

    def test_citacion_directa_basica(self) -> None:
        """Corpus sin references_id: la citación directa funciona igual.

        corpus_ids = {"P1", "P2"} (ids de los papers, sin openalex_id)

        Citantes:
          CITER_A cita [P1, P2, OTHER] → 2 corpus-ids en refs → score = 2
          CITER_B cita [P1]            → 1 corpus-id en refs  → score = 1
          CITER_C cita [EXTERNAL]      → ningún corpus-id     → excluido
        """
        corpus_rows = [
            _base_row("P1", references_id=None),
            _base_row("P2", references_id=None),
        ]
        citing_rows = [
            _base_row(
                "CITER_A",
                references_id=["P1", "P2", "OTHER"],
                is_seed=False,
            ),
            _base_row(
                "CITER_B",
                references_id=["P1"],
                is_seed=False,
            ),
            _base_row(
                "CITER_C",
                references_id=["EXTERNAL"],
                is_seed=False,
            ),
        ]
        scent = compute_forward_scent(corpus_rows, citing_rows)

        # CITER_A cita P1 y P2 directamente → score = 2
        assert scent.get("CITER_A") == 2.0
        # CITER_B cita solo P1 → score = 1
        assert scent.get("CITER_B") == 1.0
        # CITER_C no cita ningún corpus-paper → excluido
        assert "CITER_C" not in scent

    def test_openalex_id_match(self) -> None:
        """El score usa openalex_id del corpus además de id."""
        corpus_rows = [
            _base_row("P1", openalex_id="W_OA1", references_id=None),
        ]
        citing_rows = [
            # Cita al corpus-paper por su openalex_id
            _base_row("CITER_X", references_id=["W_OA1"], is_seed=False),
        ]
        scent = compute_forward_scent(corpus_rows, citing_rows)
        assert scent.get("CITER_X") == 1.0

    def test_orden_de_ranking_forward(self) -> None:
        """Candidato que cita más corpus-papers sale primero."""
        corpus_rows = [
            _base_row("P1", openalex_id="W1", references_id=None),
            _base_row("P2", openalex_id="W2", references_id=None),
        ]
        # CITER_X cita W1 y P2 (= dos corpus-papers) → score = 2
        citing_rows_x = [
            _base_row("CITER_X", references_id=["W1", "P2"], is_seed=False),
        ]
        # CITER_Y cita solo W1 (= un corpus-paper) → score = 1
        citing_rows_y = [
            _base_row("CITER_Y", references_id=["W1"], is_seed=False),
        ]
        all_citing = citing_rows_x + citing_rows_y
        scent = compute_forward_scent(corpus_rows, all_citing)

        ranked = rank_candidates(scent)
        assert ranked[0][0] == "CITER_X"
        assert ranked[0][1] == 2.0
        assert ranked[1][0] == "CITER_Y"
        assert ranked[1][1] == 1.0


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

    def test_candidatos_backward_en_observed_refs(self) -> None:
        """Backward chaining: IDs observados van a observed_refs, NO al corpus (#54).

        Opción B: los candidatos backward no se materializan como filas-fantasma.
        El ranking sigue presente; los IDs salen por observed_refs para persistirse
        en referenced_but_not_fetched.
        """
        rows = [_base_row("P1", references_id=["REF_A"])]
        corpus = _make_corpus(*rows)

        source = MagicMock()
        forager = Forager(source, depth=1)
        ranked = forager.chain(corpus, direction="backward")

        # El corpus NO tiene filas-fantasma backward
        cand_table = ranked.corpus.to_arrow().to_pylist()
        assert len(cand_table) == 0, (
            "Backward chaining no debe materializar filas en corpus (#54)"
        )
        # Los IDs backward van a observed_refs
        assert "REF_A" in ranked.observed_refs
        # El ranking sigue presente (la señal de scent es útil)
        assert len(ranked.ranking) == 1
        assert ranked.ranking[0][0] == "REF_A"

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
    """Forager forward: usa MockTransport para simular fetch_citing_batch.

    El forward chaining ahora opera solo sobre semillas aceptadas y usa
    ``fetch_citing_batch`` (batcheo OR ≤50, presupuesto por semilla) en lugar
    del loop N+1 de ``fetch_citing``.
    """

    def _make_batch_transport(
        self, citing_works: list[dict[str, Any]]
    ) -> httpx.MockTransport:
        """MockTransport que responde a consultas ``cites:`` con los works dados.

        Devuelve los works para cualquier request con ``cites`` en el filtro.
        Responde vacío a otras consultas (p. ej. ``openalex_id:``).
        """

        def handler(request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            if "cites" in url_str:
                payload = {
                    "results": citing_works,
                    "meta": {"next_cursor": None},
                }
            else:
                payload = {"results": [], "meta": {"next_cursor": None}}
            return httpx.Response(200, json=payload)

        return httpx.MockTransport(handler)

    def test_forward_chaining_con_mock_transport(self) -> None:
        """Forward chaining: candidatos traídos por fetch_citing_batch con citación directa.

        Fix forward-scent: el score es citación directa al corpus, no acoplamiento.
        El forward chaining ahora opera solo sobre semillas aceptadas
        (``is_seed=True AND curation_status=accepted``).

        El corpus tiene P1 (openalex_id="W1", aceptada) sin references_id.
        El citante (W9999) cita "W1" directamente → score = 1 → entra al ranking.
        """
        # Corpus con 1 semilla aceptada, sin references_id (estado común tras un seed)
        rows = [
            _base_row(
                "P1",
                openalex_id="W1",
                references_id=None,
                curation_status="accepted",  # requerido para forward chaining
            )
        ]
        corpus = _make_corpus(*rows)

        # Citante que cita a W1 (la semilla aceptada) directamente.
        # referenced_works → _oa_id_short → "W1" → atribuido a W1 por fetch_citing_batch
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
        transport = self._make_batch_transport([citing_work])
        source = OpenAlexSource(transport=transport)

        forager = Forager(source, depth=1)
        ranked = forager.chain(corpus, direction="forward")

        assert isinstance(ranked, RankedCandidates)
        # Debe haber exactamente 1 candidato (cita W1 directamente)
        assert len(ranked.ranking) >= 1
        # El score del candidato refleja citación directa (1 corpus-paper citado)
        assert ranked.ranking[0][1] == 1.0
        # El candidato forward tiene is_seed=False
        cand_rows = ranked.corpus.to_arrow().to_pylist()
        assert all(not r["is_seed"] for r in cand_rows)

    def test_chain_forward_usa_fetch_citing_batch(self) -> None:
        """chain(forward) usa fetch_citing_batch — NO el loop N+1 de fetch_citing."""
        batch_calls: list[list[str]] = []

        class TrackingSource:
            def fetch_citing_batch(
                self, ids: list[str], *, max_per_paper: int | None = None
            ) -> dict[str, list[str]]:
                batch_calls.append(list(ids))
                # W1 fue citado por W9999
                return {"W1": ["W9999"]}

        rows = [
            _base_row(
                "P1",
                openalex_id="W1",
                references_id=None,
                curation_status="accepted",
            )
        ]
        corpus = _make_corpus(*rows)
        source = TrackingSource()

        forager = Forager(source, depth=1)  # type: ignore[arg-type]
        ranked = forager.chain(corpus, direction="forward")

        # fetch_citing_batch fue llamado (no fetch_citing uno-por-uno)
        assert len(batch_calls) == 1, (
            f"chain(forward) debe llamar fetch_citing_batch 1 vez, "
            f"llamó {len(batch_calls)} veces"
        )
        assert "W1" in batch_calls[0], (
            "El lote debe incluir el openalex_id de la semilla aceptada"
        )
        # El candidato W9999 está en el ranking
        assert len(ranked.ranking) == 1
        assert ranked.ranking[0][0] == "W9999"

    def test_forward_no_N_mas_1_con_multiples_semillas(self) -> None:
        """Con N semillas aceptadas, forward chaining hace 1 batch (no N requests).

        3 semillas → 1 sola llamada a fetch_citing_batch con los 3 IDs juntos
        (batcheo OR ≤50), NO 3 llamadas individuales.
        """
        batch_calls: list[list[str]] = []

        class TrackingSource:
            def fetch_citing_batch(
                self, ids: list[str], *, max_per_paper: int | None = None
            ) -> dict[str, list[str]]:
                batch_calls.append(list(ids))
                return {}  # sin candidatos; basta verificar el conteo

        rows = [
            _base_row(f"P{i}", openalex_id=f"W{i}", curation_status="accepted")
            for i in range(1, 4)
        ]
        corpus = _make_corpus(*rows)
        source = TrackingSource()

        forager = Forager(source, depth=1)  # type: ignore[arg-type]
        forager.chain(corpus, direction="forward")

        # 3 semillas ≤ 50 → exactamente 1 llamada batch con los 3 IDs
        assert len(batch_calls) == 1, (
            f"3 semillas deben batchear en 1 llamada; se hicieron {len(batch_calls)}"
        )
        assert set(batch_calls[0]) == {"W1", "W2", "W3"}, (
            f"El lote debe contener los 3 openalex_ids; contiene {batch_calls[0]}"
        )

    def test_forward_alcance_solo_seeds(self) -> None:
        """Solo semillas (``is_seed=True``) entran al forward chaining.

        Papers con ``is_seed=False`` (candidatos de chaining previo) no se
        incluyen en el lote, sin importar su ``curation_status``.  El
        ``curation_status`` de la semilla no filtra: el chaining corre antes
        de la curación (ciclo SEEDED → FORAGED → curación).
        """
        batch_calls: list[list[str]] = []

        class TrackingSource:
            def fetch_citing_batch(
                self, ids: list[str], *, max_per_paper: int | None = None
            ) -> dict[str, list[str]]:
                batch_calls.append(list(ids))
                return {}

        rows = [
            _base_row(
                "P1",
                openalex_id="W1",
                curation_status="candidate",  # semilla candidate: sí entra
                is_seed=True,
            ),
            _base_row(
                "P2",
                openalex_id="W2",
                curation_status="accepted",
                is_seed=False,  # no-semilla: no entra aunque esté aceptada
            ),
            _base_row(
                "P3",
                openalex_id="W3",
                curation_status="candidate",
                is_seed=True,  # semilla candidate: sí entra
            ),
        ]
        corpus = _make_corpus(*rows)
        source = TrackingSource()

        forager = Forager(source, depth=1)  # type: ignore[arg-type]
        forager.chain(corpus, direction="forward")

        # Solo W1 y W3 (seeds) deben estar en el lote; W2 (is_seed=False) no
        assert len(batch_calls) == 1
        assert set(batch_calls[0]) == {"W1", "W3"}, (
            f"Solo las seeds deben estar en el lote; hay {batch_calls[0]}"
        )

    def test_forward_corpus_recien_sembrado_produce_candidatos(self) -> None:
        """Un corpus recién sembrado (semillas candidate) SÍ produce candidatos.

        Verifica el camino feliz: ``b2g seed`` + ``b2g chain``.  Las semillas
        nacen con ``curation_status='candidate'``; el forward chaining debe
        funcionar igualmente para traer candidatos.
        """
        batch_calls: list[list[str]] = []

        class TrackingSource:
            def fetch_citing_batch(
                self, ids: list[str], *, max_per_paper: int | None = None
            ) -> dict[str, list[str]]:
                batch_calls.append(list(ids))
                # W9 cita a W1 (la semilla)
                return {"W1": ["W9"]}

        rows = [
            _base_row(
                "P1", openalex_id="W1", curation_status="candidate", is_seed=True
            ),
        ]
        corpus = _make_corpus(*rows)
        source = TrackingSource()

        forager = Forager(source, depth=1)  # type: ignore[arg-type]
        ranked = forager.chain(corpus, direction="forward")

        # El forward chaining debe haberse ejecutado
        assert len(batch_calls) == 1, "Debe hacer 1 llamada batch para la semilla"
        # Debe haber producido al menos 1 candidato (W9 → cita W1)
        assert len(ranked.ranking) == 1
        assert ranked.ranking[0][0] == "W9"

    def test_forward_sin_seeds_cero_requests(self) -> None:
        """Sin semillas (``is_seed=True``), forward chaining no hace ningún request."""
        batch_calls: list[list[str]] = []

        class TrackingSource:
            def fetch_citing_batch(
                self, ids: list[str], *, max_per_paper: int | None = None
            ) -> dict[str, list[str]]:
                batch_calls.append(list(ids))
                return {}

        rows = [
            # is_seed=False (candidato de chaining previo): no hay semillas
            _base_row(
                "P1", openalex_id="W1", curation_status="accepted", is_seed=False
            ),
        ]
        corpus = _make_corpus(*rows)
        source = TrackingSource()

        forager = Forager(source, depth=1)  # type: ignore[arg-type]
        ranked = forager.chain(corpus, direction="forward")

        assert batch_calls == [], "Sin semillas no debe hacer requests"
        assert len(ranked.ranking) == 0

    def test_cap_por_semilla_respetado(self) -> None:
        """max_citing_per_paper se pasa a fetch_citing_batch para acotar el fetch."""
        received_max: list[int | None] = []

        class TrackingSource:
            def fetch_citing_batch(
                self, ids: list[str], *, max_per_paper: int | None = None
            ) -> dict[str, list[str]]:
                received_max.append(max_per_paper)
                # Devolver más citantes de los permitidos para verificar el cap
                return {"W1": [f"C{i}" for i in range(100)]}

        rows = [_base_row("P1", openalex_id="W1", curation_status="accepted")]
        corpus = _make_corpus(*rows)
        source = TrackingSource()

        forager = Forager(source, depth=1, max_citing_per_paper=5)  # type: ignore[arg-type]
        forager.chain(corpus, direction="forward")

        # El cap se pasa correctamente a fetch_citing_batch
        assert received_max == [5], (
            f"max_per_paper=5 debe pasarse a fetch_citing_batch; recibido {received_max}"
        )

    def test_forward_sin_fetch_citing_batch_falla_claro(self) -> None:
        """Si el source no tiene fetch_citing_batch ni fetch_citing, falla claro."""

        class SimpleFakeSource:
            def seed(self, query: str) -> None:
                return None

            def load(self, path: str) -> None:
                return None

        rows = [_base_row("P1", openalex_id="W1", curation_status="accepted")]
        corpus = _make_corpus(*rows)
        forager = Forager(SimpleFakeSource(), depth=1)  # type: ignore[arg-type]

        with pytest.raises(AttributeError, match="fetch_citing"):
            forager.chain(corpus, direction="forward")

    def test_idempotencia_forward_chaining(self) -> None:
        """Mismo corpus → mismo resultado (determinismo/idempotencia)."""
        batch_call_count = [0]

        class TrackingSource:
            def fetch_citing_batch(
                self, ids: list[str], *, max_per_paper: int | None = None
            ) -> dict[str, list[str]]:
                batch_call_count[0] += 1
                return {"W1": ["W9999"]}

        rows = [_base_row("P1", openalex_id="W1", curation_status="accepted")]
        corpus = _make_corpus(*rows)
        source = TrackingSource()

        forager = Forager(source, depth=1)  # type: ignore[arg-type]
        ranked1 = forager.chain(corpus, direction="forward")
        ranked2 = forager.chain(corpus, direction="forward")

        # Mismo resultado ambas veces
        assert ranked1.ranking == ranked2.ranking, (
            "chain() debe ser determinista: mismo corpus → mismo ranking"
        )


class TestForagerDepth:
    def test_depth_mayor_a_1_lanza_not_implemented(self) -> None:
        """depth > 1 lanza NotImplementedError claro."""
        source = MagicMock()
        with pytest.raises(NotImplementedError, match="profundidad"):
            Forager(source, depth=2)


# ---------------------------------------------------------------------------
# R4 — Tests de retiro de explain_candidate (ADR 0022)
# ---------------------------------------------------------------------------


class TestExplainCandidateRetirado:
    """explain_candidate ya no existe en la superficie pública (R4, ADR 0022)."""

    def test_import_explain_candidate_desde_foraging_falla(self) -> None:
        """explain_candidate ya no está en bib2graph.foraging (R4, ADR 0022)."""
        import importlib

        foraging_mod = importlib.import_module("bib2graph.foraging")
        assert not hasattr(foraging_mod, "explain_candidate"), (
            "explain_candidate fue eliminado en R4 (ADR 0022): "
            "no debe existir en bib2graph.foraging"
        )

    def test_modulo_explain_no_existe(self) -> None:
        """El módulo foraging.explain fue borrado en R4."""
        import importlib

        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("bib2graph.foraging.explain")
