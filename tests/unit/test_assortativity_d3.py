"""Tests D3 — asortatividad/composición cableada en NetworkArtifact.

Historia D3 (#90): ``NetworkSpec.assortativity_attribute`` cablea la llamada a
``analyzer.assortativity`` y ``analyzer.community_composition`` dentro de
``_build_artifact`` (facade.py), exponiendo el resultado en
``NetworkArtifact.assortativity`` y en el ``metrics.json`` / envelope de red.

Casos cubiertos:
1. Atributo categórico en la tabla del corpus (``language``) + comunidades →
   ``attribute_assortativity`` y ``community_composition`` poblados.
2. ``assortativity_attribute=None`` → ``artifact.assortativity is None``
   (comportamiento anterior intacto).
3. Atributo inexistente → warning accionable (no crash), ``assortativity`` sigue None.
4. Atributo de nodo ya inyectado por ``decorate`` (``curation_status``) →
   asortatividad calculada sin pasar por ``_inject_scalar_attribute``.
5. ``_write_artifacts`` incluye asortatividad en ``metrics.json`` y en el
   entry del envelope.

Marcador: ``unit`` (sin red, sin I/O).
"""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import Any

import networkx as nx
import pyarrow as pa
import pytest

from bib2graph.corpus import Corpus
from bib2graph.networks.facade import Networks, _inject_scalar_attribute
from bib2graph.networks.spec import NetworkSpec
from bib2graph.schemas import CORPUS_SCHEMA

# ---------------------------------------------------------------------------
# Helpers de fixtures
# ---------------------------------------------------------------------------


def _row(
    pid: str,
    *,
    language: str | None = None,
    curation_status: str = "candidate",
    references_id: list[str] | None = None,
) -> dict[str, Any]:
    """Crea una fila de corpus mínima para los tests."""
    return {
        "id": pid,
        "openalex_id": None,
        "doi": None,
        "title": f"Paper {pid}",
        "year": 2020,
        "abstract": None,
        "source": None,
        "language": language,
        "publisher": None,
        "research_areas": None,
        "is_seed": True,
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
        "cited_by_id": None,
    }


def _make_corpus_con_language() -> Corpus:
    """Corpus de 4 papers: 2 en inglés (comparten una referencia) y 2 en español.

    Construye una red de acoplamiento bibliográfico donde los pares del mismo
    idioma comparten referencias. Esto garantiza asortatividad alta por ``language``.

      P0 (en) refs: [R0, R_SHARED_EN]
      P1 (en) refs: [R1, R_SHARED_EN]
      P2 (es) refs: [R2, R_SHARED_ES]
      P3 (es) refs: [R3, R_SHARED_ES]
    """
    rows = [
        _row("P0", language="en", references_id=["R0", "R_SHARED_EN"]),
        _row("P1", language="en", references_id=["R1", "R_SHARED_EN"]),
        _row("P2", language="es", references_id=["R2", "R_SHARED_ES"]),
        _row("P3", language="es", references_id=["R3", "R_SHARED_ES"]),
    ]
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    return Corpus.from_arrow(table)


def _make_corpus_sin_language() -> Corpus:
    """Corpus de 3 papers sin atributo de lenguaje (todos None)."""
    rows = [
        _row("P0", references_id=["R0", "R_SHARED"]),
        _row("P1", references_id=["R1", "R_SHARED"]),
        _row("P2", references_id=["R2"]),
    ]
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    return Corpus.from_arrow(table)


def _make_corpus_con_curation_status() -> Corpus:
    """Corpus de 4 papers con curation_status variado para usar como atributo.

    ``curation_status`` es inyectado por ``decorate`` para paper networks,
    por lo que NO requiere ``_inject_scalar_attribute``.
    """
    rows = [
        _row("P0", curation_status="accepted", references_id=["R0", "R_SHARED_ACC"]),
        _row("P1", curation_status="accepted", references_id=["R1", "R_SHARED_ACC"]),
        _row("P2", curation_status="candidate", references_id=["R2", "R_SHARED_CAND"]),
        _row("P3", curation_status="candidate", references_id=["R3", "R_SHARED_CAND"]),
    ]
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    return Corpus.from_arrow(table)


# ---------------------------------------------------------------------------
# Test 1: atributo de corpus inyectado + comunidades → asortatividad poblada
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_assortativity_attribute_popula_artifact() -> None:
    """Con assortativity_attribute='language', NetworkArtifact.assortativity se puebla.

    La red de acoplamiento bibliográfico tiene dos pares que comparten referencias
    por idioma: alta asortatividad esperada (> 0).
    """
    corpus = _make_corpus_con_language()
    spec = NetworkSpec(
        kind="bibliographic_coupling",
        clustering="louvain",
        assortativity_attribute="language",
    )
    artifact = Networks.build(corpus, spec)

    assert artifact.assortativity is not None, (
        "assortativity debería poblarse cuando assortativity_attribute está seteado"
    )
    assert "attribute_assortativity" in artifact.assortativity
    val = artifact.assortativity["attribute_assortativity"]
    assert isinstance(val, float)
    # Con pares del mismo idioma bien separados, la asortatividad debería ser > 0
    assert isinstance(artifact.assortativity["degree_assortativity"], float)


@pytest.mark.unit
def test_assortativity_attribute_incluye_community_composition_cuando_hay_comunidades() -> (
    None
):
    """Cuando hay comunidades, assortativity incluye 'community_composition'."""
    corpus = _make_corpus_con_language()
    spec = NetworkSpec(
        kind="bibliographic_coupling",
        clustering="louvain",
        assortativity_attribute="language",
    )
    artifact = Networks.build(corpus, spec)

    assert artifact.assortativity is not None
    # community_composition debe estar presente porque spec.clustering='louvain'
    assert "community_composition" in artifact.assortativity
    comp = artifact.assortativity["community_composition"]
    assert isinstance(comp, dict)
    # Cada comunidad tiene un dict de categorías → fracciones
    for comm_id, cat_fracs in comp.items():
        assert isinstance(comm_id, int)
        assert isinstance(cat_fracs, dict)
        for cat, frac in cat_fracs.items():
            assert isinstance(cat, str)
            assert 0.0 <= float(frac) <= 1.0


# ---------------------------------------------------------------------------
# Test 2: assortativity_attribute=None → artifact.assortativity is None
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_assortativity_attribute_none_deja_assortativity_en_none() -> None:
    """assortativity_attribute=None → NetworkArtifact.assortativity es None.

    Comportamiento anterior intacto (regresión).
    """
    corpus = _make_corpus_con_language()
    spec = NetworkSpec(kind="bibliographic_coupling")  # assortativity_attribute=None

    artifact = Networks.build(corpus, spec)

    assert artifact.assortativity is None


# ---------------------------------------------------------------------------
# Test 3: atributo inexistente → warning accionable, sin crash
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_assortativity_attribute_inexistente_no_crashea(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Atributo desconocido en assortativity_attribute → warning + assortativity=None.

    No debe levantar excepción; emite un log.warning con el nombre del atributo.
    """
    corpus = _make_corpus_con_language()
    spec = NetworkSpec(
        kind="bibliographic_coupling",
        assortativity_attribute="campo_inexistente",
    )

    with caplog.at_level(logging.WARNING, logger="bib2graph.networks.facade"):
        artifact = Networks.build(corpus, spec)

    # No debe crashear
    assert artifact.assortativity is None
    # Debe haber un warning accionable mencionando el atributo
    assert any("campo_inexistente" in record.message for record in caplog.records), (
        f"Se esperaba warning con nombre del atributo. Records: {caplog.records}"
    )


# ---------------------------------------------------------------------------
# Test 4: atributo ya en nodos por decorate (curation_status) → sin _inject
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_assortativity_usa_atributo_ya_en_nodos_por_decorate() -> None:
    """'curation_status' está en los nodos tras decorate → asortatividad calculada.

    Verifica que el flujo funciona cuando el atributo categórico ya fue inyectado
    por ``decorate`` (no necesita ``_inject_scalar_attribute``).
    """
    corpus = _make_corpus_con_curation_status()
    spec = NetworkSpec(
        kind="bibliographic_coupling",
        clustering=None,  # sin comunidades para simplicidad
        assortativity_attribute="curation_status",
    )
    artifact = Networks.build(corpus, spec)

    assert artifact.assortativity is not None
    assert "attribute_assortativity" in artifact.assortativity
    # Sin clustering=None, no hay community_composition
    assert "community_composition" not in artifact.assortativity


# ---------------------------------------------------------------------------
# Test 5: _inject_scalar_attribute — unit test de la función pura
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_inject_scalar_attribute_inyecta_language_en_nodos() -> None:
    """_inject_scalar_attribute inyecta 'language' desde la tabla Arrow a los nodos."""
    rows = [
        _row("P0", language="en"),
        _row("P1", language="es"),
        _row("P2", language="en"),
    ]
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)

    g: nx.Graph = nx.Graph()
    g.add_nodes_from(["P0", "P1", "P2"])

    result = _inject_scalar_attribute(g, table, "language")

    assert result is True
    assert g.nodes["P0"]["language"] == "en"
    assert g.nodes["P1"]["language"] == "es"
    assert g.nodes["P2"]["language"] == "en"


@pytest.mark.unit
def test_inject_scalar_attribute_retorna_false_si_columna_no_existe() -> None:
    """_inject_scalar_attribute retorna False si la columna no existe en la tabla."""
    rows = [_row("P0")]
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)

    g: nx.Graph = nx.Graph()
    g.add_node("P0")

    result = _inject_scalar_attribute(g, table, "columna_que_no_existe")

    assert result is False
    assert "columna_que_no_existe" not in g.nodes["P0"]


@pytest.mark.unit
def test_inject_scalar_attribute_ignora_nodos_con_valor_none() -> None:
    """_inject_scalar_attribute no inyecta el atributo en nodos con valor None."""
    rows = [
        _row("P0", language=None),
        _row("P1", language="en"),
    ]
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)

    g: nx.Graph = nx.Graph()
    g.add_nodes_from(["P0", "P1"])

    result = _inject_scalar_attribute(g, table, "language")

    # Retorna True porque al menos P1 se inyectó
    assert result is True
    assert "language" not in g.nodes["P0"]
    assert g.nodes["P1"]["language"] == "en"


# ---------------------------------------------------------------------------
# Test 6: _write_artifacts expone assortativity en metrics.json y net_entry
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_write_artifacts_incluye_assortativity_en_metrics_json() -> None:
    """_write_artifacts escribe 'assortativity' en metrics.json cuando está poblado.

    Verifica la exposición en el artefacto de disco (D3: "que aparezca en metrics.json").
    """
    from bib2graph.cli.commands.build import _write_artifacts

    corpus = _make_corpus_con_language()
    spec = NetworkSpec(
        kind="bibliographic_coupling",
        clustering="louvain",
        assortativity_attribute="language",
    )
    artifact = Networks.build(corpus, spec)
    assert artifact.assortativity is not None  # precondición

    with tempfile.TemporaryDirectory() as tmp:
        artifacts_dir = Path(tmp)
        entries = _write_artifacts([artifact], corpus, artifacts_dir)

        assert len(entries) == 1
        entry = entries[0]

        # El net_entry del envelope debe incluir 'assortativity'
        assert "assortativity" in entry
        assert "attribute_assortativity" in entry["assortativity"]

        # El metrics.json en disco también debe tenerlo
        metrics = json.loads(Path(entry["metrics_json"]).read_text(encoding="utf-8"))
        assert "assortativity" in metrics
        assert "attribute_assortativity" in metrics["assortativity"]


@pytest.mark.unit
def test_write_artifacts_sin_assortativity_no_incluye_clave() -> None:
    """_write_artifacts NO incluye 'assortativity' cuando artifact.assortativity es None.

    Regresión: el comportamiento anterior sin assortativity_attribute no se rompe.
    """
    from bib2graph.cli.commands.build import _write_artifacts

    corpus = _make_corpus_con_language()
    spec = NetworkSpec(kind="bibliographic_coupling")  # sin assortativity_attribute
    artifact = Networks.build(corpus, spec)
    assert artifact.assortativity is None  # precondición

    with tempfile.TemporaryDirectory() as tmp:
        artifacts_dir = Path(tmp)
        entries = _write_artifacts([artifact], corpus, artifacts_dir)

        entry = entries[0]
        assert "assortativity" not in entry

        metrics = json.loads(Path(entry["metrics_json"]).read_text(encoding="utf-8"))
        assert "assortativity" not in metrics


# ---------------------------------------------------------------------------
# Test 7: sin comunidades → community_composition ausente de assortativity
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_assortativity_sin_clustering_no_incluye_community_composition() -> None:
    """Con clustering=None, 'community_composition' no aparece en assortativity."""
    corpus = _make_corpus_con_language()
    spec = NetworkSpec(
        kind="bibliographic_coupling",
        clustering=None,
        assortativity_attribute="language",
    )
    artifact = Networks.build(corpus, spec)

    assert artifact.assortativity is not None
    assert "community_composition" not in artifact.assortativity
    assert "attribute_assortativity" in artifact.assortativity
