"""Tests TDD — Fase 1A del hito 0.10.0: campos aditivos en ``b2g status --json``.

Cubre los tres nuevos campos del contrato ADR 0037 §(e):

1. ``next_best_action`` — único próximo comando recomendado (derivado del FSM).
2. ``readiness`` — si el próximo paso va a dar fruto (preparación, no alcanzabilidad).
3. ``build_preview`` — por cada red, predice vacío/no-vacío ANTES de correr build.

Caso canónico (Nota 20): corpus sembrado desde BibTeX sin ``--resolve`` →
las redes de citación/colaboración salen vacías; la red de keywords sale no-vacía
si hay ``keywords_id`` poblados (p. ej. tras ``thesaurus``).

Los campos son ADITIVOS: ``schema="1"`` se preserva, los campos viejos no cambian.

Marcador: ``unit`` (DuckDB en tmp_path, sin red real).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest

from bib2graph.constants import NetworkKind
from bib2graph.corpus import Corpus
from bib2graph.cycle import CycleState, next_best_action
from bib2graph.networks.facade import predict_build_preview
from bib2graph.schemas import CORPUS_SCHEMA

pytestmark = pytest.mark.unit

# Comandos de arreglo (fix_command) esperados, en un solo lugar: si cambia el copy
# user-facing se edita acá y no en ~10 asserts dispersos (epic #184, sub-tarea 8).
# Espejan los literales de networks/facade.py (_predict/_empty_network_entry).
FIX_RESOLVE = "b2g seed --resolve"
FIX_ENRICH = "b2g build"
FIX_THESAURUS = "b2g build --thesaurus <archivo>"

# ---------------------------------------------------------------------------
# Helpers de fixture
# ---------------------------------------------------------------------------


def _row(
    id: str,
    *,
    is_seed: bool = True,
    source_id: str | None = None,
    curation_status: str = "candidate",
    references_id: list[str] | None = None,
    cited_by_id: list[str] | None = None,
    authors_id: list[str] | None = None,
    institutions_id: list[str] | None = None,
    keywords_id: list[str] | None = None,
    keywords_raw: list[str] | None = None,
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
        "authors_id": authors_id,
        "authors_affiliations": None,
        "keywords_raw": keywords_raw,
        "keywords_id": keywords_id,
        "institutions_raw": None,
        "institutions_id": institutions_id,
        "references_id": references_id,
        "references_doi": None,
        "cited_by_id": cited_by_id,
    }


def _make_corpus(*rows: dict[str, Any]) -> Corpus:
    """Construye un Corpus en memoria desde filas dict."""
    table = pa.Table.from_pylist(list(rows), schema=CORPUS_SCHEMA)
    return Corpus.from_arrow(table)


def _seed_store(store_path: Path, rows: list[dict[str, Any]]) -> None:
    """Persiste un conjunto de filas en un DuckDB temporal."""
    from bib2graph.stores.duckdb import DuckDBStore

    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)
    store = DuckDBStore(store_path)
    store.persist(corpus)
    store.close()


def _seed_store_with_state(
    store_path: Path,
    rows: list[dict[str, Any]],
    state: CycleState,
) -> None:
    """Persiste filas y fija el estado del lazo."""
    from bib2graph.stores.duckdb import DuckDBStore

    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)
    store = DuckDBStore(store_path)
    store.persist(corpus)
    store.backend.set_loop_state(state, cycle_round=1)
    store.close()


# ---------------------------------------------------------------------------
# Pruebas unitarias puras: next_best_action (sin store)
# ---------------------------------------------------------------------------


class TestNextBestAction:
    """Verifica el mapa determinista FSM → comando recomendado."""

    def test_sin_estado_recomienda_seed(self) -> None:
        assert next_best_action(None) == "seed"

    def test_seeded_recomienda_chain(self) -> None:
        assert next_best_action(CycleState.SEEDED) == "chain"

    def test_foraged_recomienda_build(self) -> None:
        assert next_best_action(CycleState.FORAGED) == "build"

    def test_filtered_recomienda_build(self) -> None:
        assert next_best_action(CycleState.FILTERED) == "build"

    def test_built_recomienda_read(self) -> None:
        assert next_best_action(CycleState.BUILT) == "read"

    def test_monitored_recomienda_chain(self) -> None:
        assert next_best_action(CycleState.MONITORED) == "chain"


# ---------------------------------------------------------------------------
# Pruebas unitarias puras: predict_build_preview (sin store, Corpus en memoria)
# ---------------------------------------------------------------------------


class TestPredictBuildPreview:
    """Verifica predict_build_preview como función pura sobre Corpus."""

    def test_devuelve_cinco_redes(self) -> None:
        """El preview incluye siempre las 5 redes posibles."""
        corpus = _make_corpus(_row("P1"))
        preview = predict_build_preview(corpus)
        assert len(preview) == 5

    def test_cada_entrada_tiene_campos_requeridos(self) -> None:
        """Cada entrada tiene kind, would_be_empty, reason, fix_command."""
        corpus = _make_corpus(_row("P1"))
        preview = predict_build_preview(corpus)
        for entry in preview:
            assert "kind" in entry
            assert "would_be_empty" in entry
            assert "reason" in entry
            assert "fix_command" in entry

    def test_corpus_sin_datos_id_todo_vacio(self) -> None:
        """Sin ningún _id populado, todas las redes saldrían vacías."""
        corpus = _make_corpus(
            _row("P1"),
            _row("P2"),
        )
        preview = predict_build_preview(corpus)
        assert all(entry["would_be_empty"] for entry in preview), (
            "Con corpus sin _id cols, todas las redes deben ser vacías"
        )

    def test_reason_no_nula_cuando_vacia(self) -> None:
        """Si would_be_empty=True, reason no puede ser None."""
        corpus = _make_corpus(_row("P1"))
        preview = predict_build_preview(corpus)
        for entry in preview:
            if entry["would_be_empty"]:
                assert entry["reason"] is not None, (
                    f"{entry['kind']}: would_be_empty=True pero reason=None"
                )
                assert entry["fix_command"] is not None, (
                    f"{entry['kind']}: would_be_empty=True pero fix_command=None"
                )

    def test_reason_nula_cuando_no_vacia(self) -> None:
        """Si would_be_empty=False, reason y fix_command deben ser None."""
        # Corpus con keywords_id con >= 2 elementos por paper → keyword_cooccurrence no vacía
        corpus = _make_corpus(
            _row("P1", keywords_id=["k1", "k2"]),
            _row("P2", keywords_id=["k1", "k3"]),
        )
        preview = predict_build_preview(corpus)
        kw_entry = next(
            e for e in preview if e["kind"] == NetworkKind.KEYWORD_COOCCURRENCE
        )
        assert kw_entry["would_be_empty"] is False
        assert kw_entry["reason"] is None
        assert kw_entry["fix_command"] is None

    # --- Caso canónico: BibTeX sin --resolve ---

    def test_canonical_bibtex_sin_resolve_redes_vacias(self) -> None:
        """Corpus BibTeX sin --resolve: references_id y cited_by_id vacíos → vacías.

        Este es el caso de la Nota 20: el agente ve el vacío ANTES de build.
        """
        # Simula 15 papers de BibTeX sin --resolve:
        # todos los _id cols están vacíos, solo keywords_raw está poblado.
        rows = [
            _row(f"P{i}", keywords_raw=["ecology", "diversity"]) for i in range(1, 16)
        ]
        corpus = _make_corpus(*rows)
        preview = predict_build_preview(corpus)

        # Indexar por kind para verificar cada una
        by_kind = {str(e["kind"]): e for e in preview}

        # bibliographic_coupling vacía: sin references_id
        bc = by_kind[NetworkKind.BIBLIOGRAPHIC_COUPLING]
        assert bc["would_be_empty"] is True
        assert "references_id" in str(bc["reason"])
        assert bc["fix_command"] == FIX_RESOLVE

        # cocitation vacía: sin cited_by_id
        coc = by_kind[NetworkKind.COCITATION]
        assert coc["would_be_empty"] is True
        assert "cited_by_id" in str(coc["reason"])
        assert coc["fix_command"] == FIX_ENRICH

        # author_collab vacía: sin authors_id
        ac = by_kind[NetworkKind.AUTHOR_COLLAB]
        assert ac["would_be_empty"] is True
        assert "authors_id" in str(ac["reason"])
        assert ac["fix_command"] == FIX_RESOLVE

        # institution_collab vacía: sin institutions_id
        ic = by_kind[NetworkKind.INSTITUTION_COLLAB]
        assert ic["would_be_empty"] is True
        assert "institutions_id" in str(ic["reason"])
        assert ic["fix_command"] == FIX_RESOLVE

        # keyword_cooccurrence vacía: keywords_raw tiene datos pero keywords_id no
        # Fix debe ser build --thesaurus (puede generarlos sin red)
        kw = by_kind[NetworkKind.KEYWORD_COOCCURRENCE]
        assert kw["would_be_empty"] is True
        assert kw["fix_command"] == FIX_THESAURUS

    def test_keywords_id_poblado_produce_red_no_vacia(self) -> None:
        """Con keywords_id >= 2 por paper, keyword_cooccurrence sale no-vacía.

        Simula el estado AFTER thesaurus o AFTER seed --resolve donde
        keywords_id está disponible.
        """
        corpus = _make_corpus(
            _row("P1", keywords_id=["ecology", "complexity"]),
            _row("P2", keywords_id=["ecology", "networks"]),
        )
        preview = predict_build_preview(corpus)
        by_kind = {str(e["kind"]): e for e in preview}

        kw = by_kind[NetworkKind.KEYWORD_COOCCURRENCE]
        assert kw["would_be_empty"] is False
        assert kw["reason"] is None
        assert kw["fix_command"] is None

    def test_references_id_dos_o_mas_papers_no_vacia(self) -> None:
        """Con >= 2 papers con references_id, bibliographic_coupling no sale vacía."""
        corpus = _make_corpus(
            _row("P1", references_id=["R1", "R2"]),
            _row("P2", references_id=["R1", "R3"]),
        )
        preview = predict_build_preview(corpus)
        by_kind = {str(e["kind"]): e for e in preview}

        bc = by_kind[NetworkKind.BIBLIOGRAPHIC_COUPLING]
        assert bc["would_be_empty"] is False

    def test_un_paper_con_references_no_alcanza(self) -> None:
        """Solo 1 paper con referencias → bibliographic_coupling vacía (no hay par)."""
        corpus = _make_corpus(
            _row("P1", references_id=["R1", "R2"]),
        )
        preview = predict_build_preview(corpus)
        by_kind = {str(e["kind"]): e for e in preview}

        bc = by_kind[NetworkKind.BIBLIOGRAPHIC_COUPLING]
        assert bc["would_be_empty"] is True

    def test_cocitation_necesita_dos_seeds_con_cited_by(self) -> None:
        """Co-citación: necesita >= 2 seeds con cited_by_id."""
        # Solo 1 seed con cited_by_id → vacía
        corpus = _make_corpus(
            _row("P1", is_seed=True, cited_by_id=["C1", "C2"]),
        )
        preview = predict_build_preview(corpus)
        by_kind = {str(e["kind"]): e for e in preview}
        assert by_kind[NetworkKind.COCITATION]["would_be_empty"] is True

        # 2 seeds con cited_by_id → no vacía
        corpus2 = _make_corpus(
            _row("P1", is_seed=True, cited_by_id=["C1", "C2"]),
            _row("P2", is_seed=True, cited_by_id=["C1", "C3"]),
        )
        preview2 = predict_build_preview(corpus2)
        by_kind2 = {str(e["kind"]): e for e in preview2}
        assert by_kind2[NetworkKind.COCITATION]["would_be_empty"] is False

    def test_author_collab_necesita_un_paper_con_dos_autores(self) -> None:
        """author_collab: vacía si ningún paper tiene >= 2 authors_id."""
        # 0 papers con >= 2 autores → vacía
        corpus = _make_corpus(
            _row("P1", authors_id=["A1"]),
        )
        preview = predict_build_preview(corpus)
        by_kind = {str(e["kind"]): e for e in preview}
        assert by_kind[NetworkKind.AUTHOR_COLLAB]["would_be_empty"] is True

        # 1 paper con 2 autores → no vacía
        corpus2 = _make_corpus(
            _row("P1", authors_id=["A1", "A2"]),
        )
        preview2 = predict_build_preview(corpus2)
        by_kind2 = {str(e["kind"]): e for e in preview2}
        assert by_kind2[NetworkKind.AUTHOR_COLLAB]["would_be_empty"] is False

    def test_fix_thesaurus_cuando_hay_keywords_raw_sin_id(self) -> None:
        """Si keywords_raw existe pero keywords_id no, fix_command='b2g thesaurus'."""
        corpus = _make_corpus(
            _row("P1", keywords_raw=["ecology", "diversity"]),
        )
        preview = predict_build_preview(corpus)
        by_kind = {str(e["kind"]): e for e in preview}
        kw = by_kind[NetworkKind.KEYWORD_COOCCURRENCE]
        assert kw["would_be_empty"] is True
        assert kw["fix_command"] == FIX_THESAURUS

    def test_fix_seed_resolve_cuando_no_hay_keywords_raw(self) -> None:
        """Sin keywords_raw, fix_command para keyword_cooccurrence='b2g seed --resolve'."""
        corpus = _make_corpus(_row("P1"))
        preview = predict_build_preview(corpus)
        by_kind = {str(e["kind"]): e for e in preview}
        kw = by_kind[NetworkKind.KEYWORD_COOCCURRENCE]
        assert kw["would_be_empty"] is True
        assert kw["fix_command"] == FIX_RESOLVE

    def test_kinds_son_strings_de_networkkind(self) -> None:
        """El campo kind de cada entrada es un string válido de NetworkKind."""
        valid_kinds = {str(k) for k in NetworkKind}
        corpus = _make_corpus(_row("P1"))
        preview = predict_build_preview(corpus)
        for entry in preview:
            assert str(entry["kind"]) in valid_kinds, (
                f"kind={entry['kind']!r} no es un NetworkKind válido"
            )


# ---------------------------------------------------------------------------
# Pruebas de integración: run_status con DuckDB temporal
# ---------------------------------------------------------------------------


class TestRunStatusCamposAditivos:
    """Verifica que run_status incluye los tres campos aditivos."""

    def test_run_status_tiene_tres_campos_aditivos(self, tmp_path: Path) -> None:
        """run_status devuelve next_best_action, readiness y build_preview."""
        from bib2graph.cli.commands.status import run_status

        store_path = tmp_path / "test.duckdb"
        _seed_store(store_path, [_row("P1"), _row("P2")])

        data = run_status(store_path)

        assert "next_best_action" in data, "Falta next_best_action"
        assert "readiness" in data, "Falta readiness"
        assert "build_preview" in data, "Falta build_preview"

    def test_campos_viejos_siguen_presentes(self, tmp_path: Path) -> None:
        """Los campos existentes no desaparecen (contrato aditivo)."""
        from bib2graph.cli.commands.status import run_status

        store_path = tmp_path / "test.duckdb"
        _seed_store(store_path, [_row("P1")])

        data = run_status(store_path)

        # Campos pre-existentes
        assert "loop_state" in data
        assert "transitions_available" in data
        assert "curation_available" in data
        assert "round" in data
        assert "counts_by_status" in data
        assert "total_papers" in data
        assert "referenced_not_fetched" in data

    # Semántica del FSM (None→seed, FORAGED→build, BUILT→read) eliminada aquí (epic #184):
    # las invariantes viven en TestNextBestAction; este smoke verifica que run_status
    # expone el campo con el valor correcto para un estado representativo.
    def test_next_best_action_seeded_es_chain(self, tmp_path: Path) -> None:
        """Tras seed (SEEDED), next_best_action='chain'."""
        from bib2graph.cli.commands.status import run_status

        store_path = tmp_path / "seeded.duckdb"
        _seed_store_with_state(store_path, [_row("P1")], CycleState.SEEDED)

        data = run_status(store_path)

        assert data["next_best_action"] == "chain"

    def test_build_preview_tiene_cinco_entradas(self, tmp_path: Path) -> None:
        """build_preview incluye siempre las 5 redes posibles."""
        from bib2graph.cli.commands.status import run_status

        store_path = tmp_path / "test.duckdb"
        _seed_store(store_path, [_row("P1")])

        data = run_status(store_path)

        assert len(data["build_preview"]) == 5

    def test_readiness_tiene_campos_ready_y_reason(self, tmp_path: Path) -> None:
        """readiness es un objeto con 'ready' (bool) y 'reason' (str | None)."""
        from bib2graph.cli.commands.status import run_status

        store_path = tmp_path / "test.duckdb"
        _seed_store(store_path, [_row("P1")])

        data = run_status(store_path)

        readiness = data["readiness"]
        assert "ready" in readiness
        assert "reason" in readiness
        assert isinstance(readiness["ready"], bool)

    def test_readiness_false_cuando_build_y_todas_vacias(self, tmp_path: Path) -> None:
        """Si next_action='build' y todas las redes están vacías, readiness.ready=False.

        Este es el corazón del ADR 0037 §(e): el diagnóstico de red-vacía en
        status-time, no post-hoc.
        """
        from bib2graph.cli.commands.status import run_status

        store_path = tmp_path / "foraged_empty.duckdb"
        # Corpus foraged pero sin ningún _id col poblado
        rows = [_row(f"P{i}") for i in range(1, 10)]
        _seed_store_with_state(store_path, rows, CycleState.FORAGED)

        data = run_status(store_path)

        assert data["next_best_action"] == "build"
        readiness = data["readiness"]
        assert readiness["ready"] is False
        assert readiness["reason"] is not None

    def test_readiness_true_cuando_build_con_keywords(self, tmp_path: Path) -> None:
        """Si next_action='build' y al menos 1 red no sería vacía, readiness.ready=True."""
        from bib2graph.cli.commands.status import run_status

        store_path = tmp_path / "foraged_kw.duckdb"
        rows = [
            _row("P1", keywords_id=["k1", "k2"]),
            _row("P2", keywords_id=["k1", "k3"]),
        ]
        _seed_store_with_state(store_path, rows, CycleState.FORAGED)

        data = run_status(store_path)

        assert data["next_best_action"] == "build"
        assert data["readiness"]["ready"] is True

    def test_readiness_true_para_built(self, tmp_path: Path) -> None:
        """Para BUILT (next=read), readiness.ready=True independientemente del corpus."""
        from bib2graph.cli.commands.status import run_status

        store_path = tmp_path / "built.duckdb"
        # BibTeX sin --resolve: source_id=None. Aun así, read es siempre productivo.
        rows = [_row("P1")]
        _seed_store_with_state(store_path, rows, CycleState.BUILT)

        data = run_status(store_path)

        assert data["readiness"]["ready"] is True, (
            "readiness.ready debe ser True para BUILT (next=read)"
        )

    def test_readiness_true_para_chain_con_source_id(self, tmp_path: Path) -> None:
        """Para SEEDED con source_id populado, chain es productivo → ready=True."""
        from bib2graph.cli.commands.status import run_status

        store_path = tmp_path / "seeded_with_source.duckdb"
        rows = [_row("P1", source_id="W123456")]
        _seed_store_with_state(store_path, rows, CycleState.SEEDED)

        data = run_status(store_path)

        assert data["next_best_action"] == "chain"
        assert data["readiness"]["ready"] is True


# ---------------------------------------------------------------------------
# Caso canónico completo (Nota 20): BibTeX sin --resolve → diagnóstico en status-time
# ---------------------------------------------------------------------------


class TestCasoCanonicoNota20:
    """El caso de trampa que motivó el ADR 0037 §(e).

    Un agente que siembra desde BibTeX sin --resolve NO debe llegar a
    construir redes vacías sin advertencia. ``status`` debe mostrar el
    diagnóstico ANTES de que corra build.
    """

    def test_bibtex_sin_resolve_diagnostico_completo(self, tmp_path: Path) -> None:
        """Corpus BibTeX (solo keywords_raw, sin _id cols) → diagnóstico correcto.

        Verifica:
        - redes de citación/colaboración → would_be_empty=True con fix
        - keyword_cooccurrence → would_be_empty=True, fix='b2g thesaurus'
        - readiness.ready=False (build sería inútil)
        - next_best_action='build' (FSM en FORAGED)
        """
        from bib2graph.cli.commands.status import run_status

        store_path = tmp_path / "bibtex_no_resolve.duckdb"
        rows = [
            _row(f"P{i}", keywords_raw=["ecology", "diversity", "networks"])
            for i in range(1, 16)
        ]
        _seed_store_with_state(store_path, rows, CycleState.FORAGED)

        data = run_status(store_path)

        # next_best_action = "build" (FSM en FORAGED)
        assert data["next_best_action"] == "build"

        # readiness = False (todas las redes vacías)
        assert data["readiness"]["ready"] is False

        # build_preview indexado por kind
        by_kind = {str(e["kind"]): e for e in data["build_preview"]}

        # Redes de citación vacías
        assert by_kind[NetworkKind.BIBLIOGRAPHIC_COUPLING]["would_be_empty"] is True
        assert by_kind[NetworkKind.COCITATION]["would_be_empty"] is True

        # Fix para citación/colaboración = seed --resolve
        assert by_kind[NetworkKind.BIBLIOGRAPHIC_COUPLING]["fix_command"] == FIX_RESOLVE
        assert by_kind[NetworkKind.COCITATION]["fix_command"] == FIX_ENRICH

        # Keyword fix = build --thesaurus (hay keywords_raw pero no keywords_id)
        kw = by_kind[NetworkKind.KEYWORD_COOCCURRENCE]
        assert kw["would_be_empty"] is True
        assert kw["fix_command"] == FIX_THESAURUS

    def test_bibtex_con_thesaurus_keyword_no_vacia(self, tmp_path: Path) -> None:
        """Tras thesaurus, keywords_id se puebla → keyword_cooccurrence no-vacía.

        Simula el estado AFTER 'b2g thesaurus': keywords_id tiene datos
        pero references_id / cited_by_id siguen vacíos.
        """
        from bib2graph.cli.commands.status import run_status

        store_path = tmp_path / "bibtex_con_thesaurus.duckdb"
        rows = [
            _row(
                f"P{i}",
                keywords_raw=["ecology", "diversity"],
                keywords_id=["ecology", "diversity"],  # thesaurus aplicado
            )
            for i in range(1, 6)
        ]
        _seed_store_with_state(store_path, rows, CycleState.FORAGED)

        data = run_status(store_path)

        by_kind = {str(e["kind"]): e for e in data["build_preview"]}

        # Keyword ya no vacía
        kw = by_kind[NetworkKind.KEYWORD_COOCCURRENCE]
        assert kw["would_be_empty"] is False

        # readiness.ready=True (al menos 1 red no vacía)
        assert data["readiness"]["ready"] is True

        # Las demás siguen vacías (aún sin --resolve)
        assert by_kind[NetworkKind.BIBLIOGRAPHIC_COUPLING]["would_be_empty"] is True
        assert by_kind[NetworkKind.COCITATION]["would_be_empty"] is True


# ---------------------------------------------------------------------------
# P2 Tests: readiness para acción "chain" (ADR 0037 §(e))
# ---------------------------------------------------------------------------


class TestChainReadiness:
    """Verifica readiness.ready para next_best_action='chain'.

    El forrajeo en OpenAlex arranca del source_id.  BibTeX sin --resolve
    no tiene source_id → chaining produce 0 papers nuevos → not ready.
    """

    def test_chain_sin_source_id_no_listo(self, tmp_path: Path) -> None:
        """SEEDED con corpus BibTeX (sin source_id) → chain not ready."""
        from bib2graph.cli.commands.status import run_status

        store_path = tmp_path / "bibtex_seeded.duckdb"
        rows = [_row(f"P{i}") for i in range(1, 6)]  # todos con source_id=None
        _seed_store_with_state(store_path, rows, CycleState.SEEDED)

        data = run_status(store_path)

        assert data["next_best_action"] == "chain"
        readiness = data["readiness"]
        assert readiness["ready"] is False
        assert readiness["reason"] is not None
        # El reason debe mencionar source_id y la acción correctiva
        assert "source_id" in str(readiness["reason"])
        assert "seed --resolve" in str(readiness["reason"])

    def test_chain_con_source_id_listo(self, tmp_path: Path) -> None:
        """SEEDED con al menos 1 seed con source_id → chain ready."""
        from bib2graph.cli.commands.status import run_status

        store_path = tmp_path / "openalex_seeded.duckdb"
        rows = [
            _row("P1", source_id="W1000001"),
            _row("P2", source_id="W1000002"),
        ]
        _seed_store_with_state(store_path, rows, CycleState.SEEDED)

        data = run_status(store_path)

        assert data["next_best_action"] == "chain"
        assert data["readiness"]["ready"] is True
        assert data["readiness"]["reason"] is None

    def test_chain_mixto_al_menos_uno_con_source_listo(self, tmp_path: Path) -> None:
        """Corpus mixto (algunos con source_id, otros sin) → chain ready."""
        from bib2graph.cli.commands.status import run_status

        store_path = tmp_path / "mixed_seeded.duckdb"
        rows = [
            _row("P1", source_id="W1000001"),
            _row("P2"),  # sin source_id (BibTeX)
            _row("P3"),  # sin source_id (BibTeX)
        ]
        _seed_store_with_state(store_path, rows, CycleState.SEEDED)

        data = run_status(store_path)

        assert data["next_best_action"] == "chain"
        assert data["readiness"]["ready"] is True

    def test_monitored_sin_source_id_no_listo(self, tmp_path: Path) -> None:
        """MONITORED (también lleva a chain) sin source_id → not ready."""
        from bib2graph.cli.commands.status import run_status

        store_path = tmp_path / "monitored_bibtex.duckdb"
        rows = [_row("P1")]  # source_id=None
        _seed_store_with_state(store_path, rows, CycleState.MONITORED)

        data = run_status(store_path)

        assert data["next_best_action"] == "chain"
        assert data["readiness"]["ready"] is False


# ---------------------------------------------------------------------------
# P1-test: no-divergencia entre predict_build_preview y build real (ADR 0037)
# ---------------------------------------------------------------------------


class TestNoDivergenciaPreviewVsBuild:
    """P1-test: predict_build_preview debe coincidir con el build real.

    Para cada corpus representativo, construye las redes reales con ``Networks``
    y afirma que ``would_be_empty == (graph.number_of_edges() == 0)`` para cada
    tipo de red.

    Cubre específicamente los casos que exponían el bug original:
    - refs disjuntas (OLD: predict=False, build=empty)
    - autores duplicados (OLD: predict=False, build=empty)
    - citantes disjuntos en co-citación (OLD: predict=False, build=empty)
    """

    def _assert_all_kinds_agree(self, corpus: Corpus) -> None:
        """Verifica que preview.would_be_empty == build real para las 5 redes."""
        from bib2graph.networks.facade import Networks, predict_build_preview
        from bib2graph.networks.spec import NetworkSpec

        preview = predict_build_preview(corpus)
        by_kind = {str(e["kind"]): e for e in preview}

        for kind in NetworkKind:
            spec = NetworkSpec(kind=str(kind))
            artifact = Networks.build(corpus, spec)
            real_empty = artifact.graph.number_of_edges() == 0
            pred_empty = bool(by_kind[str(kind)]["would_be_empty"])
            assert pred_empty == real_empty, (
                f"kind={kind}: preview.would_be_empty={pred_empty!r} "
                f"pero el build real tiene {artifact.graph.number_of_edges()} aristas"
            )

    def test_corpus_sin_datos(self) -> None:
        """Corpus sin ningún _id → todas las redes vacías."""
        corpus = _make_corpus(_row("P1"), _row("P2"))
        self._assert_all_kinds_agree(corpus)

    def test_coupling_refs_disjuntas_bug_p1(self) -> None:
        """CASO TRAMPA P1: refs disjuntas → coupling vacía aunque ≥2 papers tienen refs."""
        # Bug original: n_refs=2 → OLD predicaba would_be_empty=False, build daba 0 aristas.
        corpus = _make_corpus(
            _row("P1", references_id=["R1", "R2"]),
            _row("P2", references_id=["R3", "R4"]),  # disjuntas con P1
        )
        self._assert_all_kinds_agree(corpus)

    def test_coupling_refs_compartidas(self) -> None:
        """Refs compartidas → coupling no-vacía."""
        corpus = _make_corpus(
            _row("P1", references_id=["R1", "R2"]),
            _row("P2", references_id=["R1", "R3"]),  # R1 compartida
        )
        self._assert_all_kinds_agree(corpus)

    def test_autor_duplicado_bug_p1(self) -> None:
        """CASO TRAMPA P1: [A1, A1] → tras dedup 1 único → author_collab vacía.

        Bug original: _count_rows_with_multi_col contaba 1 paper con len(val)>=2
        → predicaba would_be_empty=False, pero build daba 0 aristas.
        """
        corpus = _make_corpus(
            _row("P1", authors_id=["A1", "A1"]),
        )
        self._assert_all_kinds_agree(corpus)

    def test_autores_distintos(self) -> None:
        """[A1, A2] → 2 distintos → author_collab no-vacía."""
        corpus = _make_corpus(
            _row("P1", authors_id=["A1", "A2"]),
        )
        self._assert_all_kinds_agree(corpus)

    def test_institucion_duplicada_bug_p1(self) -> None:
        """CASO TRAMPA P1: [I1, I1] → institution_collab vacía."""
        corpus = _make_corpus(
            _row("P1", institutions_id=["I1", "I1"]),
        )
        self._assert_all_kinds_agree(corpus)

    def test_instituciones_distintas(self) -> None:
        """[I1, I2] → institution_collab no-vacía."""
        corpus = _make_corpus(
            _row("P1", institutions_id=["I1", "I2"]),
        )
        self._assert_all_kinds_agree(corpus)

    def test_keyword_duplicada_bug_p1(self) -> None:
        """CASO TRAMPA P1: [k1, k1] → keyword_cooccurrence vacía."""
        corpus = _make_corpus(
            _row("P1", keywords_id=["k1", "k1"]),
        )
        self._assert_all_kinds_agree(corpus)

    def test_keywords_distintas(self) -> None:
        """[k1, k2] → keyword_cooccurrence no-vacía."""
        corpus = _make_corpus(
            _row("P1", keywords_id=["k1", "k2"]),
        )
        self._assert_all_kinds_agree(corpus)

    def test_cocitation_citantes_disjuntos_bug_p1(self) -> None:
        """CASO TRAMPA P1: citantes disjuntos → cocitation vacía.

        Bug original: n_cited=2 seeds → OLD predicaba would_be_empty=False,
        pero build daba 0 aristas porque ningún citante es compartido.
        """
        corpus = _make_corpus(
            _row("P1", is_seed=True, cited_by_id=["C1"]),
            _row("P2", is_seed=True, cited_by_id=["C2"]),  # C1≠C2: disjuntos
        )
        self._assert_all_kinds_agree(corpus)

    def test_cocitation_citante_compartido(self) -> None:
        """Citante compartido → cocitation no-vacía."""
        corpus = _make_corpus(
            _row("P1", is_seed=True, cited_by_id=["C1", "C2"]),
            _row("P2", is_seed=True, cited_by_id=["C1", "C3"]),  # C1 compartido
        )
        self._assert_all_kinds_agree(corpus)

    def test_corpus_con_none_en_lista(self) -> None:
        """Listas con None como elementos → filtradas correctamente."""
        corpus = _make_corpus(
            _row("P1", authors_id=["A1", None]),  # solo A1 válido → no multi-distinct
            _row("P2", authors_id=[None, None]),  # 0 válidos
        )
        self._assert_all_kinds_agree(corpus)


# ---------------------------------------------------------------------------
# Tests de contrato: schema="1" y compatibilidad con agentes existentes
# ---------------------------------------------------------------------------


class TestContratoEnvelope:
    """Garantiza que los campos aditivos no rompen el envelope schema='1'."""

    def test_envelope_schema_sigue_siendo_uno(self, tmp_path: Path) -> None:
        """El envelope JSON tiene schema='1' con los campos nuevos."""
        from bib2graph.cli._envelope import build_envelope

        data = {
            "loop_state": "FORAGED",
            "transitions_available": ["build"],
            "curation_available": ["accept", "reject"],
            "round": 1,
            "counts_by_status": {"candidate": 5},
            "total_papers": 5,
            "referenced_not_fetched": 0,
            # Campos aditivos ADR 0037
            "next_best_action": "build",
            "readiness": {"ready": True, "reason": None},
            "build_preview": [
                {
                    "kind": "keyword_cooccurrence",
                    "would_be_empty": False,
                    "reason": None,
                    "fix_command": None,
                }
            ],
            "workspace": {"root": "/tmp/ws", "source": "explicit"},
            "networks_cache_stale": False,
        }

        envelope = build_envelope(
            command="status",
            ok=True,
            data=data,
            exit_code=0,
        )

        # Schema invariante
        assert envelope["schema"] == "1"
        assert envelope["ok"] is True
        assert envelope["command"] == "status"
        assert envelope["exit_code"] == 0

        # Campos viejos siguen en data
        assert envelope["data"]["loop_state"] == "FORAGED"
        assert envelope["data"]["total_papers"] == 5

        # Campos nuevos en data
        assert envelope["data"]["next_best_action"] == "build"
        assert envelope["data"]["readiness"]["ready"] is True
        assert len(envelope["data"]["build_preview"]) == 1
