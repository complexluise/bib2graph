"""Tests TDD del issue #113 — keyword_filter en NetworkSpec.

Casos cubiertos:

(a) corpus con keywords mixtas → keyword_filter produce sub-red solo con
    los papers que matchean.
(b) keyword_filter=None (default) → comportamiento idéntico al actual
    (sin filtrar).
(c) filtro sin matches → grafo vacío (0 nodos), sin error.
(d) case-insensitivity y substring: term "complex" matchea "Complexity".

Marcador: ``unit`` (sin red ni I/O externo).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest

from bib2graph.corpus import Corpus
from bib2graph.networks.facade import Networks, _apply_keyword_filter
from bib2graph.networks.spec import NetworkSpec, load_specs
from bib2graph.schemas import CORPUS_SCHEMA

# ---------------------------------------------------------------------------
# Helpers de fixture
# ---------------------------------------------------------------------------


def _paper(
    pid: str,
    keywords_raw: list[str] | None,
    references_id: list[str] | None = None,
) -> dict[str, Any]:
    """Construye una fila de paper mínima para los tests de keyword_filter."""
    return {
        "id": pid,
        "openalex_id": None,
        "doi": None,
        "title": f"Paper {pid}",
        "year": 2020,
        "abstract": None,
        "source": None,
        "language": None,
        "publisher": None,
        "research_areas": None,
        "is_seed": True,
        "curation_status": "candidate",
        "provenance": None,
        "authors_raw": None,
        "authors_id": [f"AUTH_{pid}"],
        "authors_affiliations": None,
        "keywords_raw": keywords_raw,
        "keywords_id": None,
        "institutions_raw": None,
        "institutions_id": None,
        "references_id": references_id,
        "references_doi": None,
        "cited_by_id": None,
    }


def _make_corpus_con_keywords() -> Corpus:
    """Corpus con 4 papers de distintas temáticas para los tests de filtro.

    - P1: keywords de complejidad ("Complexity", "Systems thinking")
    - P2: keywords de ecología ("Ecological economics", "Biodiversity")
    - P3: keywords mixtas ("Complexity", "Ecology")
    - P4: sin keywords relevantes ("Mathematics", "Algebra")

    P1 y P3 comparten REF_SHARED (para que haya aristas de coupling entre ellos).
    P2 y P3 comparten REF_ECO.
    """
    rows = [
        _paper(
            "P1",
            keywords_raw=["Complexity", "Systems thinking"],
            references_id=["REF_SHARED", "REF_A"],
        ),
        _paper(
            "P2",
            keywords_raw=["Ecological economics", "Biodiversity"],
            references_id=["REF_ECO", "REF_B"],
        ),
        _paper(
            "P3",
            keywords_raw=["Complexity", "Ecology"],
            references_id=["REF_SHARED", "REF_ECO"],
        ),
        _paper(
            "P4",
            keywords_raw=["Mathematics", "Algebra"],
            references_id=["REF_C"],
        ),
    ]
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    return Corpus.from_arrow(table)


# ---------------------------------------------------------------------------
# Tests de _apply_keyword_filter (función pura interna)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_apply_keyword_filter_retorna_solo_papers_con_match() -> None:
    """_apply_keyword_filter retiene solo filas con keywords que matchean."""
    corpus = _make_corpus_con_keywords()
    table = corpus.to_arrow()

    filtrada = _apply_keyword_filter(table, ["complex"])

    ids = filtrada.column("id").to_pylist()
    # P1 ("Complexity") y P3 ("Complexity") deben matchear; P2 y P4, no.
    assert set(ids) == {"P1", "P3"}


@pytest.mark.unit
def test_apply_keyword_filter_case_insensitive() -> None:
    """El filtro es case-insensitive: 'complex' matchea 'Complexity'."""
    corpus = _make_corpus_con_keywords()
    table = corpus.to_arrow()

    # Término en mayúsculas: debe igualmente matchear "Complexity"
    filtrada_upper = _apply_keyword_filter(table, ["COMPLEX"])
    filtrada_lower = _apply_keyword_filter(table, ["complex"])

    assert (
        filtrada_upper.column("id").to_pylist()
        == filtrada_lower.column("id").to_pylist()
    )


@pytest.mark.unit
def test_apply_keyword_filter_substring() -> None:
    """El filtro es por substring: 'ecolog' matchea 'Ecological economics' y 'Ecology'."""
    corpus = _make_corpus_con_keywords()
    table = corpus.to_arrow()

    filtrada = _apply_keyword_filter(table, ["ecolog"])

    ids = set(filtrada.column("id").to_pylist())
    # P2 ("Ecological economics"), P3 ("Ecology")
    assert ids == {"P2", "P3"}


@pytest.mark.unit
def test_apply_keyword_filter_any_semantics() -> None:
    """ANY: un paper entra si CUALQUIER término del filtro matchea alguna keyword."""
    corpus = _make_corpus_con_keywords()
    table = corpus.to_arrow()

    # "complex" matchea P1 y P3; "biodiversity" matchea P2
    filtrada = _apply_keyword_filter(table, ["complex", "biodiversity"])

    ids = set(filtrada.column("id").to_pylist())
    assert ids == {"P1", "P2", "P3"}


@pytest.mark.unit
def test_apply_keyword_filter_sin_matches_devuelve_tabla_vacia() -> None:
    """Sin matches → tabla vacía (0 filas), sin error."""
    corpus = _make_corpus_con_keywords()
    table = corpus.to_arrow()

    filtrada = _apply_keyword_filter(table, ["termino_que_no_existe_xyz"])

    assert filtrada.num_rows == 0


@pytest.mark.unit
def test_apply_keyword_filter_paper_sin_keywords_no_matchea() -> None:
    """Un paper con keywords_raw=None no matchea ningún filtro."""
    rows = [
        _paper("P_sin_kw", keywords_raw=None, references_id=["REF_X"]),
        _paper("P_con_kw", keywords_raw=["Complexity"], references_id=["REF_X"]),
    ]
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)

    filtrada = _apply_keyword_filter(table, ["complex"])

    ids = filtrada.column("id").to_pylist()
    assert ids == ["P_con_kw"]


# ---------------------------------------------------------------------------
# (a) Networks.build con keyword_filter produce sub-red con papers que matchean
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_keyword_filter_produce_sub_red_con_papers_matching() -> None:
    """(a) keyword_filter=['complex'] limita la red a P1 y P3 (acoplamiento).

    P1 y P3 comparten REF_SHARED, así que la red de coupling debe tener
    exactamente esa arista. P2 y P4 quedan fuera.
    """
    corpus = _make_corpus_con_keywords()
    spec = NetworkSpec(
        kind="bibliographic_coupling",
        keyword_filter=["complex"],
        clustering=None,
    )

    artifact = Networks.build(corpus, spec)

    nodes = set(artifact.graph.nodes())
    # Solo P1 y P3 pasan el filtro; la arista P1-P3 (REF_SHARED) debe existir.
    assert nodes == {"P1", "P3"}
    assert artifact.graph.has_edge("P1", "P3")


@pytest.mark.unit
def test_keyword_filter_excluye_papers_sin_match() -> None:
    """(a) Papers sin keyword matching no aparecen en el grafo resultante."""
    corpus = _make_corpus_con_keywords()
    spec = NetworkSpec(
        kind="bibliographic_coupling",
        keyword_filter=["complex"],
        clustering=None,
    )

    artifact = Networks.build(corpus, spec)

    nodes = set(artifact.graph.nodes())
    assert "P2" not in nodes
    assert "P4" not in nodes


# ---------------------------------------------------------------------------
# (b) keyword_filter=None → comportamiento idéntico al actual (sin filtrar)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_keyword_filter_none_no_filtra() -> None:
    """(b) keyword_filter=None (default) → mismo resultado que sin keyword_filter."""
    corpus = _make_corpus_con_keywords()

    spec_con_none = NetworkSpec(
        kind="bibliographic_coupling",
        keyword_filter=None,
        clustering=None,
    )
    spec_sin_campo = NetworkSpec(
        kind="bibliographic_coupling",
        clustering=None,
    )

    art_con_none = Networks.build(corpus, spec_con_none)
    art_sin_campo = Networks.build(corpus, spec_sin_campo)

    assert set(art_con_none.graph.nodes()) == set(art_sin_campo.graph.nodes())
    assert set(art_con_none.graph.edges()) == set(art_sin_campo.graph.edges())


@pytest.mark.unit
def test_keyword_filter_lista_vacia_no_filtra() -> None:
    """Lista vacía keyword_filter=[] → sin filtro (mismo resultado que None)."""
    corpus = _make_corpus_con_keywords()

    spec_vacia = NetworkSpec(
        kind="bibliographic_coupling",
        keyword_filter=[],
        clustering=None,
    )
    spec_none = NetworkSpec(
        kind="bibliographic_coupling",
        keyword_filter=None,
        clustering=None,
    )

    art_vacia = Networks.build(corpus, spec_vacia)
    art_none = Networks.build(corpus, spec_none)

    assert set(art_vacia.graph.nodes()) == set(art_none.graph.nodes())
    assert set(art_vacia.graph.edges()) == set(art_none.graph.edges())


# ---------------------------------------------------------------------------
# (c) filtro sin matches → grafo vacío (0 nodos), sin error
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_keyword_filter_sin_matches_grafo_vacio() -> None:
    """(c) Ningún paper matchea → grafo con 0 nodos, sin error."""
    corpus = _make_corpus_con_keywords()
    spec = NetworkSpec(
        kind="bibliographic_coupling",
        keyword_filter=["termino_que_no_existe_xyz"],
        clustering=None,
    )

    artifact = Networks.build(corpus, spec)

    assert artifact.graph.number_of_nodes() == 0
    assert artifact.graph.number_of_edges() == 0


@pytest.mark.unit
def test_keyword_filter_sin_matches_no_lanza_error() -> None:
    """(c) El filtro que no matchea nada no debe lanzar excepción."""
    corpus = _make_corpus_con_keywords()
    spec = NetworkSpec(
        kind="keyword_cooccurrence",
        keyword_filter=["zzz_nada_zzz"],
        clustering=None,
    )

    # No debe lanzar ninguna excepción
    artifact = Networks.build(corpus, spec)
    assert artifact is not None


# ---------------------------------------------------------------------------
# (d) case-insensitivity y substring en Networks.build
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_keyword_filter_case_insensitive_en_build() -> None:
    """(d) 'complex' (minúscula) matchea keyword 'Complexity' (capitalizada)."""
    corpus = _make_corpus_con_keywords()

    spec_lower = NetworkSpec(
        kind="bibliographic_coupling",
        keyword_filter=["complex"],
        clustering=None,
    )
    spec_upper = NetworkSpec(
        kind="bibliographic_coupling",
        keyword_filter=["COMPLEX"],
        clustering=None,
    )

    art_lower = Networks.build(corpus, spec_lower)
    art_upper = Networks.build(corpus, spec_upper)

    assert set(art_lower.graph.nodes()) == set(art_upper.graph.nodes())


@pytest.mark.unit
def test_keyword_filter_substring_en_build() -> None:
    """(d) Término parcial 'ecolog' matchea 'Ecological economics' y 'Ecology'."""
    corpus = _make_corpus_con_keywords()
    spec = NetworkSpec(
        kind="bibliographic_coupling",
        keyword_filter=["ecolog"],
        clustering=None,
    )

    artifact = Networks.build(corpus, spec)

    nodes = set(artifact.graph.nodes())
    # P2 ("Ecological economics") y P3 ("Ecology") deben estar
    assert "P2" in nodes
    assert "P3" in nodes
    # P1 y P4 no tienen keywords con 'ecolog'
    assert "P1" not in nodes
    assert "P4" not in nodes


# ---------------------------------------------------------------------------
# NetworkSpec — validación del campo keyword_filter
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_networkspec_keyword_filter_default_es_none() -> None:
    """El campo keyword_filter tiene None como valor por defecto."""
    spec = NetworkSpec(kind="bibliographic_coupling")
    assert spec.keyword_filter is None


@pytest.mark.unit
def test_networkspec_keyword_filter_acepta_lista_de_strings() -> None:
    """keyword_filter acepta una lista de strings correctamente."""
    spec = NetworkSpec(
        kind="bibliographic_coupling", keyword_filter=["complex", "ecolog"]
    )
    assert spec.keyword_filter == ["complex", "ecolog"]


@pytest.mark.unit
def test_networkspec_keyword_filter_en_yaml(tmp_path: Path) -> None:
    """El campo keyword_filter se carga correctamente desde YAML."""
    yaml_content = """\
networks:
  - kind: bibliographic_coupling
    keyword_filter:
      - complex
      - ecolog
"""
    spec_file = tmp_path / "redes.yaml"
    spec_file.write_text(yaml_content, encoding="utf-8")

    specs = load_specs(spec_file)

    assert len(specs) == 1
    assert specs[0].keyword_filter == ["complex", "ecolog"]
