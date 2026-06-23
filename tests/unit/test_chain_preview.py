"""Tests TDD — issue #89: preview del crecimiento del chaining (B2).

Verifica que ``b2g chain --preview`` (``run_chain(..., preview=True)``) estima
el crecimiento potencial del corpus **sin fetchear ni modificar estado**:

- Backward: exacto desde ``references_id`` (refs únicas no presentes en corpus,
  acotado por max-candidates).
- Forward: exacto desde ``cited_by_id`` si el corpus fue enriquecido (``b2g
  enrich``); mensaje accionable si ``cited_by_id`` está vacío.
- ``--preview`` nunca agrega papers ni transiciona el CycleState.

Los tests del núcleo puro (``Forager.preview``) prueban la estimación desde
``cited_by_id``; los tests de integración usan un store DuckDB temporal.

Marcador: ``unit`` (DuckDB en tmp_path, sin red real).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pyarrow as pa
import pytest

from bib2graph.corpus import Corpus
from bib2graph.foraging.base import GrowthPreview
from bib2graph.foraging.forager import Forager
from bib2graph.schemas import CORPUS_SCHEMA

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row(
    id: str,
    *,
    source_id: str | None = None,
    is_seed: bool = True,
    references_id: list[str] | None = None,
    cited_by_id: list[str] | None = None,
    curation_status: str = "candidate",
) -> dict[str, Any]:
    """Fila mínima con schema canónico completo."""
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


def _seed_store_with_rows(store_path: Path, rows: list[dict[str, Any]]) -> None:
    """Puebla un store DuckDB con las filas dadas."""
    from bib2graph.stores.duckdb import DuckDBStore

    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)
    store = DuckDBStore(store_path)
    store.persist(corpus)
    store.close()


# ---------------------------------------------------------------------------
# Tests del núcleo puro: Forager.preview() con cited_by_id
# ---------------------------------------------------------------------------


class TestForagerPreviewForwardDesdeCitedByID:
    """Forager.preview() estima forward localmente desde cited_by_id (post-enrich)."""

    def test_forward_estima_desde_cited_by_id(self) -> None:
        """Con cited_by_id poblado, forward preview estima sin red.

        P1 tiene cited_by_id=[CIT_A, CIT_B, CIT_C].
        Los 3 citantes no están en el corpus → forward = 3.
        """
        rows = [
            _row("P1", source_id="W1", cited_by_id=["CIT_A", "CIT_B", "CIT_C"]),
        ]
        corpus = _make_corpus(*rows)

        source = MagicMock()
        forager = Forager(source, depth=1)
        preview = forager.preview(corpus, direction="forward")

        assert isinstance(preview, GrowthPreview)
        assert preview.by_direction["forward"] == 3
        assert preview.estimated_new == 3
        assert preview.forward_from_cited_by is True
        assert preview.forward_requires_fetch is False

    def test_forward_excluye_ids_ya_en_corpus(self) -> None:
        """cited_by_id que ya están en el corpus no cuentan como candidatos nuevos.

        P1.cited_by_id = [P2, CIT_X].
        P2 ya está en el corpus → solo CIT_X es nuevo → forward = 1.
        """
        rows = [
            _row("P1", source_id="W1", cited_by_id=["P2", "CIT_X"]),
            _row("P2", source_id="W2"),
        ]
        corpus = _make_corpus(*rows)

        source = MagicMock()
        forager = Forager(source, depth=1)
        preview = forager.preview(corpus, direction="forward")

        assert preview.by_direction["forward"] == 1
        assert preview.forward_from_cited_by is True

    def test_forward_excluye_source_ids_ya_en_corpus(self) -> None:
        """cited_by_id que coinciden con source_id del corpus se excluyen."""
        rows = [
            # P1 tiene source_id=W1; su cited_by_id incluye W1 (ya en corpus)
            _row("P1", source_id="W1", cited_by_id=["W1", "CIT_Y"]),
        ]
        corpus = _make_corpus(*rows)

        source = MagicMock()
        forager = Forager(source, depth=1)
        preview = forager.preview(corpus, direction="forward")

        # W1 ya está (source_id de P1); solo CIT_Y es nuevo
        assert preview.by_direction["forward"] == 1

    def test_forward_sin_cited_by_id_requiere_fetch(self) -> None:
        """Sin cited_by_id, forward preview marca forward_requires_fetch=True."""
        rows = [
            _row("P1", source_id="W1", cited_by_id=None),
        ]
        corpus = _make_corpus(*rows)

        source = MagicMock()
        forager = Forager(source, depth=1)
        preview = forager.preview(corpus, direction="forward")

        assert preview.forward_requires_fetch is True
        assert preview.forward_from_cited_by is False
        assert preview.by_direction["forward"] == 0
        assert preview.estimated_new == 0

    def test_both_backward_y_forward_desde_datos_locales(self) -> None:
        """direction='both' combina backward (references_id) y forward (cited_by_id).

        P1: references_id=[REF_A, REF_B], cited_by_id=[CIT_X].
        backward = 2 (REF_A, REF_B), forward = 1 (CIT_X) → total = 3.
        """
        rows = [
            _row(
                "P1",
                source_id="W1",
                references_id=["REF_A", "REF_B"],
                cited_by_id=["CIT_X"],
            ),
        ]
        corpus = _make_corpus(*rows)

        source = MagicMock()
        forager = Forager(source, depth=1)
        preview = forager.preview(corpus, direction="both")

        assert preview.by_direction["backward"] == 2
        assert preview.by_direction["forward"] == 1
        assert preview.estimated_new == 3
        assert preview.forward_from_cited_by is True
        assert preview.forward_requires_fetch is False

    def test_max_candidates_acota_backward(self) -> None:
        """max_candidates acota el conteo backward en el preview."""
        rows = [
            _row("P1", references_id=["REF_A", "REF_B", "REF_C"]),
        ]
        corpus = _make_corpus(*rows)

        source = MagicMock()
        forager = Forager(source, depth=1, max_candidates=2)
        preview = forager.preview(corpus, direction="backward")

        assert preview.by_direction["backward"] == 2
        assert preview.capped_by_max is True

    def test_max_candidates_acota_forward_desde_cited_by_id(self) -> None:
        """max_candidates acota el conteo forward cuando viene de cited_by_id."""
        rows = [
            _row(
                "P1",
                source_id="W1",
                cited_by_id=["CIT_A", "CIT_B", "CIT_C", "CIT_D"],
            ),
        ]
        corpus = _make_corpus(*rows)

        source = MagicMock()
        forager = Forager(source, depth=1, max_candidates=2)
        preview = forager.preview(corpus, direction="forward")

        assert preview.by_direction["forward"] == 2
        assert preview.capped_by_max is True

    def test_max_candidates_no_acota_si_hay_menos_candidatos(self) -> None:
        """capped_by_max=False cuando hay menos candidatos que el límite."""
        rows = [
            _row("P1", source_id="W1", cited_by_id=["CIT_A"]),
        ]
        corpus = _make_corpus(*rows)

        source = MagicMock()
        forager = Forager(source, depth=1, max_candidates=10)
        preview = forager.preview(corpus, direction="forward")

        assert preview.by_direction["forward"] == 1
        assert preview.capped_by_max is False

    def test_preview_no_llama_al_source(self) -> None:
        """preview() no debe llamar a ningún método del source."""
        calls: list[str] = []

        class SpySource:
            def fetch_citing_batch(
                self, ids: list[str], *, max_per_paper: int | None = None
            ) -> dict[str, list[str]]:
                calls.append("fetch_citing_batch")
                raise AssertionError("preview() no debe llamar al source")

            def fetch_citing(self, oa_id: str) -> list[dict[str, Any]]:
                calls.append("fetch_citing")
                raise AssertionError("preview() no debe llamar al source")

        rows = [
            _row("P1", source_id="W1", cited_by_id=["CIT_X"], references_id=["REF_A"]),
        ]
        corpus = _make_corpus(*rows)
        forager = Forager(SpySource(), depth=1)  # type: ignore[arg-type]
        forager.preview(corpus, direction="both")

        assert calls == [], f"El source fue llamado: {calls}"

    def test_preview_no_muta_corpus(self) -> None:
        """preview() no modifica el corpus de entrada."""
        rows = [
            _row("P1", source_id="W1", cited_by_id=["CIT_X"], references_id=["REF_A"]),
        ]
        corpus = _make_corpus(*rows)
        n_original = len(corpus)

        source = MagicMock()
        forager = Forager(source, depth=1)
        forager.preview(corpus, direction="both")

        assert len(corpus) == n_original, "preview() no debe agregar filas al corpus"

    def test_unique_ids_de_multiples_papers(self) -> None:
        """IDs repetidos en cited_by_id de varios papers se cuentan una sola vez."""
        rows = [
            _row("P1", source_id="W1", cited_by_id=["CIT_A", "CIT_B"]),
            _row("P2", source_id="W2", cited_by_id=["CIT_B", "CIT_C"]),
        ]
        corpus = _make_corpus(*rows)

        source = MagicMock()
        forager = Forager(source, depth=1)
        preview = forager.preview(corpus, direction="forward")

        # CIT_B aparece en los dos; solo se cuenta una vez → total 3 únicos
        assert preview.by_direction["forward"] == 3
        assert preview.forward_from_cited_by is True


# ---------------------------------------------------------------------------
# Tests de run_chain con preview=True (integración con DuckDB)
# ---------------------------------------------------------------------------


class TestRunChainPreview:
    """``run_chain(..., preview=True)`` estimación sin fetch ni transición de estado."""

    def test_backward_preview_estima_correctamente(self, tmp_path: Path) -> None:
        """run_chain(preview=True, direction='backward') estima desde references_id.

        2 refs únicas no presentes en corpus → estimated_candidates=2.
        No agrega papers, no transiciona estado.
        """
        from bib2graph.cli.commands.chain import run_chain
        from bib2graph.stores.duckdb import DuckDBStore

        store_path = tmp_path / "lib.duckdb"
        _seed_store_with_rows(
            store_path,
            [
                _row("P1", references_id=["REF_A", "REF_B"]),
                _row("P2", references_id=["REF_A"]),
            ],
        )

        # Registrar estado inicial (puede ser None si se creó con persist raw)
        store = DuckDBStore(store_path)
        state_before = store.backend.loop_state()
        store.close()

        result = run_chain(
            store_path,
            direction="backward",
            preview=True,
        )

        assert result["preview"] is True
        assert result["estimated_candidates"] == 2
        assert result["by_direction"]["backward"] == 2
        assert result["forward_requires_fetch"] is False  # backward only

        # El estado no debe haber cambiado
        store = DuckDBStore(store_path)
        state_after = store.backend.loop_state()
        n_papers_after = len(store.load())
        store.close()

        assert state_after == state_before, (
            f"preview no debe cambiar el estado; antes={state_before!r}, "
            f"después={state_after!r}"
        )
        assert n_papers_after == 2, "preview no debe agregar papers"

    def test_forward_preview_desde_cited_by_id(self, tmp_path: Path) -> None:
        """run_chain(preview=True, direction='forward') usa cited_by_id local.

        P1.cited_by_id=[CIT_X] → estimated_candidates=1, sin red.
        """
        from bib2graph.cli.commands.chain import run_chain
        from bib2graph.stores.duckdb import DuckDBStore

        store_path = tmp_path / "lib.duckdb"
        _seed_store_with_rows(
            store_path,
            [_row("P1", source_id="W1", cited_by_id=["CIT_X"])],
        )

        # Estado inicial
        store = DuckDBStore(store_path)
        state_before = store.backend.loop_state()
        store.close()

        result = run_chain(
            store_path,
            direction="forward",
            preview=True,
        )

        assert result["preview"] is True
        assert result["forward_from_cited_by"] is True
        assert result["forward_requires_fetch"] is False
        assert result["by_direction"]["forward"] == 1
        assert result["estimated_candidates"] == 1

        # Estado inalterado
        store = DuckDBStore(store_path)
        state_after = store.backend.loop_state()
        store.close()
        assert state_after == state_before, (
            f"preview no debe cambiar el estado; antes={state_before!r}, "
            f"después={state_after!r}"
        )

    def test_forward_sin_cited_by_id_da_aviso_accionable(self, tmp_path: Path) -> None:
        """run_chain(preview=True, direction='forward') sin cited_by_id → aviso.

        Si el corpus no tiene cited_by_id (no pasó por enrich), el preview
        debe indicar que se requiere fetch e incluir un mensaje accionable.
        """
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        _seed_store_with_rows(
            store_path,
            [_row("P1", source_id="W1", cited_by_id=None)],
        )

        result = run_chain(
            store_path,
            direction="forward",
            preview=True,
        )

        assert result["preview"] is True
        assert result["forward_requires_fetch"] is True
        assert result["by_direction"]["forward"] == 0
        assert result["estimated_candidates"] == 0
        # Debe haber un aviso accionable
        warnings = result.get("warnings", [])
        assert len(warnings) >= 1
        # El aviso debe mencionar enrich o cited_by_id
        combined = " ".join(warnings).lower()
        assert "enrich" in combined or "cited_by_id" in combined

    def test_preview_no_transiciona_estado(self, tmp_path: Path) -> None:
        """preview nunca transiciona el CycleState aunque se llame varias veces."""
        from bib2graph.cli.commands.chain import run_chain
        from bib2graph.stores.duckdb import DuckDBStore

        store_path = tmp_path / "lib.duckdb"
        _seed_store_with_rows(
            store_path,
            [
                _row(
                    "P1",
                    references_id=["REF_A"],
                    cited_by_id=["CIT_X"],
                )
            ],
        )

        # Registrar estado inicial
        store = DuckDBStore(store_path)
        state_before = store.backend.loop_state()
        store.close()

        # Llamar preview varias veces
        for _ in range(3):
            run_chain(store_path, direction="both", preview=True)

        store = DuckDBStore(store_path)
        state_after = store.backend.loop_state()
        n_papers = len(store.load())
        store.close()

        assert state_after == state_before, (
            f"preview no debe cambiar el estado; antes={state_before!r}, "
            f"después={state_after!r}"
        )
        assert n_papers == 1, "preview no debe agregar papers al corpus"

    def test_preview_max_candidates_acota_estimado(self, tmp_path: Path) -> None:
        """max_candidates acota la estimación del preview.

        3 referencias nuevas, max_candidates=2 → estimated=2, capped_by_max=True.
        """
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        _seed_store_with_rows(
            store_path,
            [_row("P1", references_id=["REF_A", "REF_B", "REF_C"])],
        )

        result = run_chain(
            store_path,
            direction="backward",
            max_candidates=2,
            preview=True,
        )

        assert result["estimated_candidates"] == 2
        assert result["capped_by_max"] is True

    def test_envelope_preview_tiene_claves_estables(self, tmp_path: Path) -> None:
        """El dict de preview tiene todas las claves del contrato."""
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        _seed_store_with_rows(
            store_path,
            [_row("P1", references_id=["REF_A"])],
        )

        result = run_chain(store_path, direction="backward", preview=True)

        expected_keys = {
            "preview",
            "direction",
            "estimated_candidates",
            "by_direction",
            "capped_by_max",
            "forward_requires_fetch",
            "forward_from_cited_by",
            "warnings",
        }
        assert expected_keys.issubset(result.keys()), (
            f"Faltan claves en el resultado: {expected_keys - result.keys()}"
        )

    def test_both_con_references_y_cited_by(self, tmp_path: Path) -> None:
        """direction='both' combina backward (references_id) + forward (cited_by_id)."""
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        _seed_store_with_rows(
            store_path,
            [
                _row(
                    "P1",
                    source_id="W1",
                    references_id=["REF_A", "REF_B"],
                    cited_by_id=["CIT_X"],
                )
            ],
        )

        result = run_chain(store_path, direction="both", preview=True)

        assert result["preview"] is True
        assert result["by_direction"]["backward"] == 2
        assert result["by_direction"]["forward"] == 1
        assert result["estimated_candidates"] == 3
        assert result["forward_from_cited_by"] is True
        assert result["forward_requires_fetch"] is False
