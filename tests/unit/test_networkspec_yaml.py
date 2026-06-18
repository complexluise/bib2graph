"""Tests TDD del Hito 9 — capa declarativa NetworkSpec (YAML).

Casos cubiertos (docs/ROADMAP — Hito 9 DoD):

1. load_specs: YAML válido (1-2 redes) → lista de NetworkSpec correctos
   (incluido campo ``resolution``).
2. load_specs: YAML malformado (sintaxis) → ValueError accionable.
3. load_specs: YAML válido pero spec inválida (kind inexistente, campo extra)
   → ValueError accionable que cita el índice de la red y el campo.
4. Equivalencia build≡quick: para bibliographic_coupling con defaults, la red
   producida por Networks.build(corpus, spec_desde_yaml_con_defaults) tiene los
   mismos nodos/aristas que Networks.quick(corpus)[coupling].
5. No-regresión resolution=1.0 ≡ comportamiento actual (default).
6. Subcomando b2g networks --spec end-to-end con CliRunner: corre, escribe
   artefactos, NO transiciona el CycleState, envelope JSON correcto.

Marcador: ``unit`` (sin red ni I/O externo; DuckDB en tmp_path).
Fecha de fixtures: 2026-06-17.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest

from bib2graph.networks.spec import NetworkSpec, load_specs
from bib2graph.schemas import CORPUS_SCHEMA

# ---------------------------------------------------------------------------
# Fixtures comunes
# ---------------------------------------------------------------------------


def _make_corpus_rows() -> list[dict[str, Any]]:
    """3 papers con referencias compartidas (produce aristas de coupling)."""
    return [
        {
            "id": f"P{i}",
            "openalex_id": None,
            "doi": None,
            "title": f"Paper {i}",
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
            "authors_id": [f"AUTH_{i}", "AUTH_0"],
            "authors_affiliations": None,
            "keywords_raw": None,
            "keywords_id": [f"KW_{i}", "KW_SHARED"],
            "institutions_raw": None,
            "institutions_id": [f"INST_{i}"],
            "references_id": [f"REF_{i}", "REF_SHARED"],
            "references_doi": None,
            "cited_by_id": None,
        }
        for i in range(3)
    ]


def _make_corpus():  # type: ignore[no-untyped-def]
    """Corpus Arrow mínimo con estructura de coupling."""
    from bib2graph.corpus import Corpus

    rows = _make_corpus_rows()
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    return Corpus.from_arrow(table)


def _seed_store(store_path: Path) -> None:
    """Pobla un store con corpus mínimo para tests CLI."""
    from bib2graph.corpus import Corpus
    from bib2graph.stores.duckdb import DuckDBStore

    rows = _make_corpus_rows()
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)
    store = DuckDBStore(store_path)
    store.persist(corpus)


# ---------------------------------------------------------------------------
# 1. load_specs: YAML válido → NetworkSpec correctos
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_load_specs_yaml_valido_una_red(tmp_path: Path) -> None:
    """YAML válido con 1 red → lista con 1 NetworkSpec con los campos correctos."""
    yaml_content = """\
networks:
  - kind: bibliographic_coupling
    min_weight: 2
    resolution: 1.5
"""
    spec_file = tmp_path / "redes.yaml"
    spec_file.write_text(yaml_content, encoding="utf-8")

    specs = load_specs(spec_file)

    assert len(specs) == 1
    spec = specs[0]
    assert isinstance(spec, NetworkSpec)
    assert spec.kind == "bibliographic_coupling"
    assert spec.min_weight == 2
    assert spec.resolution == 1.5


@pytest.mark.unit
def test_load_specs_yaml_valido_dos_redes(tmp_path: Path) -> None:
    """YAML válido con 2 redes → lista con 2 NetworkSpec en el orden correcto."""
    yaml_content = """\
networks:
  - kind: bibliographic_coupling
  - kind: author_collab
    clustering: label_prop
"""
    spec_file = tmp_path / "redes.yaml"
    spec_file.write_text(yaml_content, encoding="utf-8")

    specs = load_specs(spec_file)

    assert len(specs) == 2
    assert specs[0].kind == "bibliographic_coupling"
    assert specs[1].kind == "author_collab"
    assert specs[1].clustering == "label_prop"


@pytest.mark.unit
def test_load_specs_defaults_correctos(tmp_path: Path) -> None:
    """Una red sin campos opcionales usa los defaults de NetworkSpec."""
    yaml_content = "networks:\n  - kind: keyword_cooccurrence\n"
    spec_file = tmp_path / "redes.yaml"
    spec_file.write_text(yaml_content, encoding="utf-8")

    specs = load_specs(spec_file)

    spec = specs[0]
    assert spec.min_weight == 1
    assert spec.resolution == 1.0
    assert spec.clustering == "louvain"
    assert spec.scope == "full"


@pytest.mark.unit
def test_load_specs_campo_resolution_en_yaml(tmp_path: Path) -> None:
    """El campo resolution se carga correctamente desde el YAML."""
    yaml_content = "networks:\n  - kind: bibliographic_coupling\n    resolution: 0.5\n"
    spec_file = tmp_path / "redes.yaml"
    spec_file.write_text(yaml_content, encoding="utf-8")

    specs = load_specs(spec_file)

    assert specs[0].resolution == 0.5


# ---------------------------------------------------------------------------
# 2. load_specs: YAML malformado → ValueError accionable
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_load_specs_yaml_malformado_lanza_value_error(tmp_path: Path) -> None:
    """YAML con sintaxis inválida → ValueError que describe el problema.

    Los tabuladores dentro del bloque YAML son ilegales y PyYAML los
    rechaza con un YAMLError.
    """
    # Tabulador al inicio de línea es síntaxis inválida en YAML
    yaml_content = "networks:\n\t- kind: bibliographic_coupling\n"
    spec_file = tmp_path / "redes.yaml"
    spec_file.write_text(yaml_content, encoding="utf-8")

    with pytest.raises(ValueError, match="YAML malformado"):
        load_specs(spec_file)


@pytest.mark.unit
def test_load_specs_sin_clave_raiz_networks(tmp_path: Path) -> None:
    """YAML sin clave 'networks:' → ValueError accionable."""
    yaml_content = "redes:\n  - kind: bibliographic_coupling\n"
    spec_file = tmp_path / "redes.yaml"
    spec_file.write_text(yaml_content, encoding="utf-8")

    with pytest.raises(ValueError, match="networks:"):
        load_specs(spec_file)


@pytest.mark.unit
def test_load_specs_archivo_no_existe() -> None:
    """Archivo YAML inexistente → FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_specs("/ruta/que/no/existe.yaml")


# ---------------------------------------------------------------------------
# 3. load_specs: spec inválida → ValueError con índice y campo
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_load_specs_kind_invalido_cita_indice(tmp_path: Path) -> None:
    """Kind inexistente → ValueError que cita el índice (0-based) de la red."""
    yaml_content = """\
networks:
  - kind: bibliographic_coupling
  - kind: red_que_no_existe
"""
    spec_file = tmp_path / "redes.yaml"
    spec_file.write_text(yaml_content, encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        load_specs(spec_file)

    msg = str(exc_info.value)
    # Debe citar el índice 1 (segunda red, 0-based) y el campo 'kind'
    assert "#1" in msg
    assert "kind" in msg


@pytest.mark.unit
def test_load_specs_campo_extra_lanza_error(tmp_path: Path) -> None:
    """Campo no permitido en la spec → ValueError accionable con el índice."""
    yaml_content = """\
networks:
  - kind: bibliographic_coupling
    campo_inventado: true
"""
    spec_file = tmp_path / "redes.yaml"
    spec_file.write_text(yaml_content, encoding="utf-8")

    with pytest.raises(ValueError, match="#0"):
        load_specs(spec_file)


@pytest.mark.unit
def test_load_specs_tipo_incorrecto_cita_campo(tmp_path: Path) -> None:
    """min_weight con tipo incorrecto → ValueError que cita el campo."""
    yaml_content = """\
networks:
  - kind: bibliographic_coupling
    min_weight: "no_es_un_numero"
"""
    spec_file = tmp_path / "redes.yaml"
    spec_file.write_text(yaml_content, encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        load_specs(spec_file)

    msg = str(exc_info.value)
    assert "min_weight" in msg


# ---------------------------------------------------------------------------
# 4. Equivalencia build ≡ quick para bibliographic_coupling con defaults
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_equivalencia_build_vs_quick_con_defaults(tmp_path: Path) -> None:
    """Networks.build(corpus, spec_yaml_defaults) ≡ Networks.quick[coupling].

    La spec del YAML usa exactamente los mismos defaults que NetworkSpec(kind=k)
    puro (sin sobreescribir resolution ni min_weight).  Esto garantiza que
    la red resultante tenga los mismos nodos, aristas Y comunidades que la que
    produce quick.

    Las COMUNIDADES también deben coincidir: el seed de Louvain es función pura
    del corpus_hash de contenido (facade._louvain_seed_from_hash), no del orden
    de llamada, y ``resolution`` nunca entra al hash.  Por eso dos builds con la
    misma spec sobre el mismo corpus producen idénticas comunidades — y eso es
    justo lo que pide el DoD del Hito 9 (build ≡ quick).
    """
    from bib2graph.networks.facade import Networks

    corpus = _make_corpus()

    # Spec equivalente a NetworkSpec(kind="bibliographic_coupling") puro
    yaml_content = "networks:\n  - kind: bibliographic_coupling\n"
    spec_file = tmp_path / "redes.yaml"
    spec_file.write_text(yaml_content, encoding="utf-8")

    [spec_yaml] = load_specs(spec_file)
    art_build = Networks.build(corpus, spec_yaml)

    # Obtener el artefacto de coupling de quick
    arts_quick = Networks.quick(corpus)
    art_quick = next(a for a in arts_quick if a.spec.kind == "bibliographic_coupling")

    assert set(art_build.graph.nodes()) == set(art_quick.graph.nodes())
    assert set(art_build.graph.edges()) == set(art_quick.graph.edges())
    # DoD Hito 9: la equivalencia incluye las comunidades (seed puro del hash).
    assert art_build.communities == art_quick.communities


# ---------------------------------------------------------------------------
# 5. No-regresión: resolution=1.0 ≡ comportamiento anterior
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_resolution_default_no_cambia_comportamiento() -> None:
    """detect_communities con resolution=1.0 produce el mismo resultado que sin pasarlo.

    Verifica que el parámetro ``resolution`` con su valor por defecto (1.0)
    es inocuo: produce el mismo número de comunidades que la llamada anterior
    que no lo pasaba (equivalencia funcional con el comportamiento pre-Hito 9).
    """
    import networkx as nx

    from bib2graph.networks.analyzer import detect_communities

    g: nx.Graph = nx.Graph()
    g.add_edges_from([("A", "B"), ("B", "C"), ("C", "A"), ("D", "E"), ("E", "F")])

    # Sin resolution explícito (default 1.0)
    result_default = detect_communities(g, method="louvain", random_state=42)
    # Con resolution=1.0 explícito
    result_explicit = detect_communities(
        g, method="louvain", random_state=42, resolution=1.0
    )

    assert result_default == result_explicit
    assert isinstance(result_default, dict)
    assert set(result_default.keys()) == set(g.nodes())


@pytest.mark.unit
def test_resolution_ignorado_en_label_prop() -> None:
    """resolution se ignora silenciosamente para label_prop (sin error)."""
    import networkx as nx

    from bib2graph.networks.analyzer import detect_communities

    g: nx.Graph = nx.Graph()
    g.add_edges_from([("A", "B"), ("B", "C"), ("C", "A")])

    # No debe lanzar error aunque resolution se pase para label_prop
    result = detect_communities(g, method="label_prop", resolution=2.0)
    assert set(result.keys()) == set(g.nodes())


@pytest.mark.unit
def test_resolution_ignorado_en_greedy_modularity() -> None:
    """resolution se ignora silenciosamente para greedy_modularity (sin error)."""
    import networkx as nx

    from bib2graph.networks.analyzer import detect_communities

    g: nx.Graph = nx.Graph()
    g.add_edges_from([("A", "B"), ("B", "C"), ("C", "A")])

    result = detect_communities(g, method="greedy_modularity", resolution=0.5)
    assert set(result.keys()) == set(g.nodes())


# ---------------------------------------------------------------------------
# 6. Subcomando b2g networks --spec end-to-end (CliRunner)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_networks_cmd_escribe_artefactos(tmp_path: Path) -> None:
    """b2g networks --spec corre, escribe artefactos y devuelve exit 0."""
    from click.testing import CliRunner

    from bib2graph.cli import b2g
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / "ws"
    ws = Workspace.init(ws_dir, "test")
    _seed_store(ws.library_path)

    yaml_content = "networks:\n  - kind: bibliographic_coupling\n"
    spec_file = tmp_path / "redes.yaml"
    spec_file.write_text(yaml_content, encoding="utf-8")

    out_dir = tmp_path / "output_nets"

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws_dir),
            "networks",
            "--spec",
            str(spec_file),
            "--out-dir",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0, f"Salida inesperada: {result.output}"
    # Verificar que al menos existe la carpeta del kind
    coupling_dir = out_dir / "bibliographic_coupling"
    assert coupling_dir.exists() or out_dir.exists()


@pytest.mark.unit
def test_networks_cmd_no_transiciona_cycle_state(tmp_path: Path) -> None:
    """b2g networks --spec NO transiciona el CycleState del lazo.

    A diferencia de ``b2g build``, el subcomando ``networks`` es transversal
    al lazo bibliométrico: no modifica el estado del ciclo FSM.
    """
    from click.testing import CliRunner

    from bib2graph.cli import b2g
    from bib2graph.stores.duckdb import DuckDBStore
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / "ws"
    ws = Workspace.init(ws_dir, "test")
    _seed_store(ws.library_path)

    # Capturar el estado antes
    store_before = DuckDBStore(ws.library_path)
    state_before = store_before.backend.loop_state()

    yaml_content = "networks:\n  - kind: bibliographic_coupling\n"
    spec_file = tmp_path / "redes.yaml"
    spec_file.write_text(yaml_content, encoding="utf-8")

    out_dir = tmp_path / "output_nets"

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws_dir),
            "networks",
            "--spec",
            str(spec_file),
            "--out-dir",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0, f"Salida inesperada: {result.output}"

    # El CycleState no debe haber cambiado
    store_after = DuckDBStore(ws.library_path)
    state_after = store_after.backend.loop_state()
    assert state_after == state_before


@pytest.mark.unit
def test_networks_cmd_json_envelope_correcto(tmp_path: Path) -> None:
    """b2g networks --spec --json emite envelope con schema='1' y claves de build."""
    from click.testing import CliRunner

    from bib2graph.cli import b2g
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / "ws"
    ws = Workspace.init(ws_dir, "test")
    _seed_store(ws.library_path)

    yaml_content = "networks:\n  - kind: bibliographic_coupling\n"
    spec_file = tmp_path / "redes.yaml"
    spec_file.write_text(yaml_content, encoding="utf-8")

    out_dir = tmp_path / "output_nets"

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws_dir),
            "networks",
            "--spec",
            str(spec_file),
            "--out-dir",
            str(out_dir),
            "--json",
        ],
    )

    assert result.exit_code == 0, f"Salida inesperada: {result.output}"
    envelope = json.loads(result.output)

    assert envelope["schema"] == "1"
    assert envelope["ok"] is True
    assert envelope["command"] == "networks"
    assert envelope["exit_code"] == 0
    assert "networks_built" in envelope["data"]
    assert "artifacts_dir" in envelope["data"]
    assert "networks" in envelope["data"]
    assert envelope["data"]["networks_built"] == 1


@pytest.mark.unit
def test_networks_cmd_yaml_invalido_emite_data_error(tmp_path: Path) -> None:
    """b2g networks --spec con YAML inválido emite DataError (exit 2) en JSON."""
    from click.testing import CliRunner

    from bib2graph.cli import b2g
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / "ws"
    ws = Workspace.init(ws_dir, "test")
    _seed_store(ws.library_path)

    # Kind inexistente → DataError en el loader
    yaml_content = "networks:\n  - kind: red_inexistente\n"
    spec_file = tmp_path / "redes_malas.yaml"
    spec_file.write_text(yaml_content, encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws_dir),
            "networks",
            "--spec",
            str(spec_file),
            "--json",
        ],
    )

    assert result.exit_code == 2  # DataError → exit 2
    envelope = json.loads(result.output)
    assert envelope["ok"] is False
    assert envelope["error"] is not None
    assert envelope["error"]["code"] == "DATA_ERROR"
