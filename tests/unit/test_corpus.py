"""Tests TDD del Hito 1 — núcleo de la tabla canónica ``Corpus``.

Exactamente los tests prescritos en docs/ROADMAP.md §Hito 1 "Tests TDD — los
justos", con datos sintéticos chicos y resultados verificables a mano.

Marcador: ``unit`` (sin red, sin I/O salvo ``tmp_path``).
"""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pytest

from bib2graph.corpus import Corpus, CorpusSnapshot, _compute_corpus_hash
from bib2graph.schemas import CORPUS_SCHEMA, SCHEMA_VERSION, SchemaError

# ---------------------------------------------------------------------------
# Fixtures — datos sintéticos mínimos
# ---------------------------------------------------------------------------

_LIST_STR = pa.list_(pa.string())


def _make_minimal_row(
    *,
    id: str = "doi:aabbccdd11223344",
    source_id: str | None = "W12345",
    doi: str | None = "10.1000/xyz123",
    title: str = "Intercambio ecológico desigual",
    year: int | None = 2020,
    abstract: str | None = None,
    source: str | None = None,
    language: str | None = "es",
    publisher: str | None = None,
    research_areas: list[str] | None = None,
    is_seed: bool = True,
    curation_status: str = "candidate",
    provenance: str | None = None,
    authors_raw: list[str] | None = None,
    authors_id: list[str] | None = None,
    authors_affiliations: list[str] | None = None,
    keywords_raw: list[str] | None = None,
    keywords_id: list[str] | None = None,
    institutions_raw: list[str] | None = None,
    institutions_id: list[str] | None = None,
    references_id: list[str] | None = None,
    references_doi: list[str] | None = None,
    cited_by_id: list[str] | None = None,
) -> dict[str, object]:
    """Construye un dict de fila mínima con todos los campos del schema."""
    return {
        "id": id,
        "source_id": source_id,
        "doi": doi,
        "title": title,
        "year": year,
        "abstract": abstract,
        "source": source,
        "language": language,
        "publisher": publisher,
        "research_areas": research_areas,
        "is_seed": is_seed,
        "curation_status": curation_status,
        "provenance": provenance,
        "authors_raw": authors_raw,
        "authors_id": authors_id,
        "authors_affiliations": authors_affiliations,
        "keywords_raw": keywords_raw,
        "keywords_id": keywords_id,
        "institutions_raw": institutions_raw,
        "institutions_id": institutions_id,
        "references_id": references_id,
        "references_doi": references_doi,
        "cited_by_id": cited_by_id,
    }


def _make_table(rows: list[dict[str, object]]) -> pa.Table:
    """Construye una tabla Arrow con el schema canónico desde una lista de dicts."""
    return pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)


@pytest.fixture()
def corpus_un_paper() -> Corpus:
    """Corpus con un único paper válido."""
    row = _make_minimal_row()
    table = _make_table([row])
    return Corpus.from_arrow(table)


@pytest.fixture()
def corpus_dos_papers() -> Corpus:
    """Corpus con dos papers distintos."""
    rows = [
        _make_minimal_row(
            id="doi:aabbccdd11223344",
            source_id="W12345",
            doi="10.1000/xyz123",
            title="Intercambio ecológico desigual",
            year=2020,
            keywords_raw=["ecology", "exchange"],
        ),
        _make_minimal_row(
            id="doi:bbccdd1122334455",
            source_id="W67890",
            doi="10.2000/abc456",
            title="Metabolismo social",
            year=2021,
            keywords_raw=["metabolism", "society"],
        ),
    ]
    table = _make_table(rows)
    return Corpus.from_arrow(table)


# ---------------------------------------------------------------------------
# 1. from_arrow — camino feliz y fallas ruidosas
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_from_arrow_camino_feliz(corpus_un_paper: Corpus) -> None:
    """from_arrow construye el Corpus correctamente con una tabla válida."""
    assert len(corpus_un_paper) == 1
    assert corpus_un_paper.manifest.schema_version == SCHEMA_VERSION


@pytest.mark.unit
def test_from_arrow_falla_columna_faltante() -> None:
    """from_arrow levanta SchemaError cuando falta una columna obligatoria."""
    # Tabla sin la columna 'id'
    table = pa.table(
        {
            "title": pa.array(["Titulo"], type=pa.string()),
            "is_seed": pa.array([True], type=pa.bool_()),
            "curation_status": pa.array(["candidate"], type=pa.string()),
        }
    )
    with pytest.raises(SchemaError, match="Columna requerida ausente"):
        Corpus.from_arrow(table)


@pytest.mark.unit
def test_from_arrow_falla_tipo_incorrecto() -> None:
    """from_arrow levanta SchemaError cuando el tipo Arrow no coincide."""
    row = _make_minimal_row()
    # Construir tabla con 'year' como string en vez de int32
    data: dict[str, pa.Array] = {}
    for field in CORPUS_SCHEMA:
        if field.name == "year":
            data[field.name] = pa.array(["2020"], type=pa.string())
        elif field.name in {
            "id",
            "title",
            "curation_status",
            "source_id",
            "doi",
            "abstract",
            "source",
            "language",
            "publisher",
            "provenance",
        }:
            data[field.name] = pa.array([row[field.name]], type=pa.string())
        elif field.name == "is_seed":
            data[field.name] = pa.array([row[field.name]], type=pa.bool_())
        else:
            data[field.name] = pa.array([row[field.name]], type=pa.list_(pa.string()))

    # Construir sin el schema para que el tipo de 'year' sea string
    wrong_schema = pa.schema(
        [
            f if f.name != "year" else pa.field("year", pa.string(), nullable=True)
            for f in CORPUS_SCHEMA
        ]
    )
    table = pa.table(data, schema=wrong_schema)
    with pytest.raises(SchemaError, match="Tipo incorrecto en columna 'year'"):
        Corpus.from_arrow(table)


# ---------------------------------------------------------------------------
# 2. merge — idempotencia y dedup con duplicados mixtos
# ---------------------------------------------------------------------------


@pytest.fixture()
def corpus_con_nulos() -> Corpus:
    """Corpus con filas que tienen columnas de lista y provenance nulos."""
    rows = [
        _make_minimal_row(
            id="doi:aabbccdd11223344",
            source_id="W12345",
            doi="10.1000/xyz123",
            title="Intercambio ecológico desigual",
            year=2020,
            # keywords_raw=None por defecto, provenance=None por defecto
            keywords_raw=None,
            authors_raw=None,
            provenance=None,
        ),
        _make_minimal_row(
            id="doi:bbccdd1122334455",
            source_id="W67890",
            doi="10.2000/abc456",
            title="Metabolismo social",
            year=2021,
            keywords_raw=["metabolism", "society"],
            provenance=None,
        ),
    ]
    table = _make_table(rows)
    return Corpus.from_arrow(table)


@pytest.mark.unit
def test_merge_idempotente(corpus_dos_papers: Corpus) -> None:
    """c.merge(c) produce un Corpus con los mismos ids que c."""
    c = corpus_dos_papers
    merged = c.merge(c)
    ids_orig = set(c.table.column("id").to_pylist())
    ids_merged = set(merged.table.column("id").to_pylist())
    assert ids_orig == ids_merged
    assert len(merged) == len(c)


@pytest.mark.unit
def test_merge_idempotente_value_equality(corpus_con_nulos: Corpus) -> None:
    """c.merge(c) == c: igualdad estructural completa (no solo ids/conteo).

    Verifica el DoD del ROADMAP (§Hito 1): c.merge(c) produce exactamente el
    mismo contenido que c, incluyendo filas con columnas de lista nulas y
    provenance nulo. Captura el bug donde _merge_list_field(None,None) devolvía
    [] y la rama provenance devolvía "[]" en vez de None.
    """
    c = corpus_con_nulos
    merged = c.merge(c)
    # Igualdad de value object (Corpus.__eq__ compara tabla Arrow)
    assert merged == c


@pytest.mark.unit
def test_merge_idempotente_corpus_hash_estable(corpus_con_nulos: Corpus) -> None:
    """corpus_hash es estable tras c.merge(c): mismo contenido → mismo hash (D2).

    Verifica que el hash del contenido de la tabla no cambia cuando se hace
    un merge idempotente, incluso con filas que tienen columnas nulas.
    """
    c = corpus_con_nulos
    merged = c.merge(c)
    hash_original = _compute_corpus_hash(c.table)
    hash_merged = _compute_corpus_hash(merged.table)
    assert hash_original == hash_merged


@pytest.mark.unit
def test_merge_dedup_duplicados_mixtos() -> None:
    """merge deduplica cuando el mismo paper llega por source_id y por doi.

    Escenario: paper A identificado por source_id W99999 en corpus_a,
    y el mismo paper con doi '10.9999/dup' en corpus_b. D1' garantiza que
    ambos generan el mismo ``id`` cuando se usa doi primero (ADR 0036).
    En este test forzamos el mismo ``id`` en ambos para simular dedup real.
    """
    # Mismo id, distintos valores en keywords_raw
    shared_id = "src:deadbeef12345678"
    row_a = _make_minimal_row(
        id=shared_id,
        source_id="W99999",
        doi=None,
        title="Paper duplicado",
        year=2019,
        keywords_raw=["ecology"],
    )
    row_b = _make_minimal_row(
        id=shared_id,
        source_id="W99999",
        doi="10.9999/dup",
        title="Paper duplicado",
        year=2019,
        keywords_raw=["exchange"],
    )
    c_a = Corpus.from_arrow(_make_table([row_a]))
    c_b = Corpus.from_arrow(_make_table([row_b]))

    merged = c_a.merge(c_b)
    assert len(merged) == 1

    result_row = merged.table.to_pylist()[0]
    # doi del otro gana (D3: escalar no-nulo de 'other')
    assert result_row["doi"] == "10.9999/dup"


@pytest.mark.unit
def test_merge_union_listas() -> None:
    """merge hace unión de sets en columnas list[string] (D3)."""
    shared_id = "doi:cafecafecafecafe"
    row_a = _make_minimal_row(
        id=shared_id,
        source_id=None,
        doi="10.1111/union",
        title="Union test",
        year=2022,
        keywords_raw=["alpha", "beta"],
    )
    row_b = _make_minimal_row(
        id=shared_id,
        source_id=None,
        doi="10.1111/union",
        title="Union test",
        year=2022,
        keywords_raw=["beta", "gamma"],
    )
    c_a = Corpus.from_arrow(_make_table([row_a]))
    c_b = Corpus.from_arrow(_make_table([row_b]))

    merged = c_a.merge(c_b)
    result_row = merged.table.to_pylist()[0]
    keywords = sorted(result_row["keywords_raw"])
    assert keywords == ["alpha", "beta", "gamma"]


@pytest.mark.unit
def test_merge_preserva_provenance_append_only() -> None:
    """merge con provenances distintos une eventos sin duplicar (append-only).

    Verifica que el fix del bug de idempotencia NO rompió el comportamiento
    de merge cuando SÍ hay eventos de provenance: los eventos de ambos corpus
    se unen sin duplicación.
    """
    shared_id = "doi:feedfeedfeedfeed"
    evento_a = json.dumps(
        [
            {
                "action": "accepted",
                "equation_id": None,
                "chaining_hop": None,
                "source": "search_a",
                "fetched_at": "2024-01-01T00:00:00+00:00",
                "decided_by": "human",
                "decided_at": "2024-01-02T00:00:00+00:00",
            }
        ]
    )
    evento_b = json.dumps(
        [
            {
                "action": "rejected",
                "equation_id": None,
                "chaining_hop": None,
                "source": "search_b",
                "fetched_at": "2024-01-03T00:00:00+00:00",
                "decided_by": "human",
                "decided_at": "2024-01-04T00:00:00+00:00",
            }
        ]
    )
    row_a = _make_minimal_row(
        id=shared_id,
        title="Merge prov test",
        year=2023,
        curation_status="accepted",
        provenance=evento_a,
    )
    row_b = _make_minimal_row(
        id=shared_id,
        title="Merge prov test",
        year=2023,
        curation_status="rejected",
        provenance=evento_b,
    )
    c_a = Corpus.from_arrow(_make_table([row_a]))
    c_b = Corpus.from_arrow(_make_table([row_b]))

    merged = c_a.merge(c_b)
    result_row = merged.table.to_pylist()[0]
    events = json.loads(result_row["provenance"])
    # Ambos eventos presentes, sin duplicados
    assert len(events) == 2
    actions = {e["action"] for e in events}
    assert actions == {"accepted", "rejected"}


# ---------------------------------------------------------------------------
# 3. accept / reject — semántica de valor y log de provenance
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_accept_cambia_estado_y_agrega_evento(corpus_un_paper: Corpus) -> None:
    """accept devuelve Corpus nuevo con curation_status='accepted' y evento en provenance."""
    paper_id = corpus_un_paper.table.column("id").to_pylist()[0]
    curado = corpus_un_paper.accept([paper_id], by="luis")

    row = curado.table.to_pylist()[0]
    assert row["curation_status"] == "accepted"
    events = json.loads(row["provenance"])
    assert len(events) == 1
    assert events[0]["action"] == "accepted"
    assert events[0]["decided_by"] == "luis"
    assert events[0]["decided_at"] is not None


@pytest.mark.unit
def test_reject_cambia_estado_y_agrega_evento(corpus_un_paper: Corpus) -> None:
    """reject devuelve Corpus nuevo con curation_status='rejected' y evento en provenance."""
    paper_id = corpus_un_paper.table.column("id").to_pylist()[0]
    curado = corpus_un_paper.reject([paper_id], by="revisor")

    row = curado.table.to_pylist()[0]
    assert row["curation_status"] == "rejected"
    events = json.loads(row["provenance"])
    assert events[0]["action"] == "rejected"
    assert events[0]["decided_by"] == "revisor"


@pytest.mark.unit
def test_accept_no_muta_original(corpus_un_paper: Corpus) -> None:
    """El Corpus original no muta tras accept (semántica de valor)."""
    paper_id = corpus_un_paper.table.column("id").to_pylist()[0]
    original_status = corpus_un_paper.table.to_pylist()[0]["curation_status"]

    _ = corpus_un_paper.accept([paper_id])

    # Original sigue igual
    assert corpus_un_paper.table.to_pylist()[0]["curation_status"] == original_status


@pytest.mark.unit
def test_provenance_es_append_only(corpus_un_paper: Corpus) -> None:
    """Cada curación agrega un evento; los previos se conservan."""
    paper_id = corpus_un_paper.table.column("id").to_pylist()[0]
    c1 = corpus_un_paper.accept([paper_id], by="revisor_a")
    c2 = c1.reject([paper_id], by="revisor_b")

    events = json.loads(c2.table.to_pylist()[0]["provenance"])
    assert len(events) == 2
    assert events[0]["action"] == "accepted"
    assert events[1]["action"] == "rejected"


# ---------------------------------------------------------------------------
# 4. snapshot → reload con corpus_hash estable
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_snapshot_reload_corpus_hash_estable(
    corpus_dos_papers: Corpus, tmp_path: Path
) -> None:
    """Dos sellamientos del mismo contenido producen el mismo corpus_hash."""
    snap1 = corpus_dos_papers.snapshot(tmp_path / "snap1")
    snap2 = corpus_dos_papers.snapshot(tmp_path / "snap2")

    assert snap1.manifest.corpus_hash == snap2.manifest.corpus_hash


@pytest.mark.unit
def test_snapshot_reload_reconstruye_corpus(
    corpus_dos_papers: Corpus, tmp_path: Path
) -> None:
    """CorpusSnapshot.corpus reconstruye el mismo contenido que el original."""
    snap_path = tmp_path / "snap"
    snap = corpus_dos_papers.snapshot(snap_path)

    reloaded = snap.corpus
    ids_orig = set(corpus_dos_papers.table.column("id").to_pylist())
    ids_reload = set(reloaded.table.column("id").to_pylist())
    assert ids_orig == ids_reload


@pytest.mark.unit
def test_snapshot_hash_cambia_si_cambia_contenido(
    corpus_dos_papers: Corpus, tmp_path: Path
) -> None:
    """El corpus_hash es distinto si cambia el contenido."""
    snap1 = corpus_dos_papers.snapshot(tmp_path / "snap1")
    # Aceptar un paper cambia el contenido
    paper_id = corpus_dos_papers.table.column("id").to_pylist()[0]
    corpus_modificado = corpus_dos_papers.accept([paper_id])
    snap2 = corpus_modificado.snapshot(tmp_path / "snap2")

    assert snap1.manifest.corpus_hash != snap2.manifest.corpus_hash


@pytest.mark.unit
def test_corpus_snapshot_load(corpus_un_paper: Corpus, tmp_path: Path) -> None:
    """CorpusSnapshot.load recarga el snapshot desde disco correctamente."""
    snap_path = tmp_path / "snap_load"
    snap = corpus_un_paper.snapshot(snap_path)
    hash_original = snap.manifest.corpus_hash

    reloaded_snap = CorpusSnapshot.load(snap_path)
    assert reloaded_snap.manifest.corpus_hash == hash_original
    assert reloaded_snap.manifest.schema_version == SCHEMA_VERSION


@pytest.mark.unit
def test_snapshot_schema_version_en_manifest(
    corpus_un_paper: Corpus, tmp_path: Path
) -> None:
    """El snapshot incluye schema_version en el manifest (D6)."""
    snap = corpus_un_paper.snapshot(tmp_path / "snap_sv")
    assert snap.manifest.schema_version == SCHEMA_VERSION


@pytest.mark.unit
def test_snapshot_roundtrip_disco_preserva_nulos(
    corpus_con_nulos: Corpus, tmp_path: Path
) -> None:
    """Round-trip a disco con columnas de lista y provenance nulos: parquet debe
    preservar None (no convertirlo en []) para que el corpus_hash siga estable.

    Guarda de regresión: blinda el caso de nulos contra futuros cambios de versión
    de pyarrow (riesgo señalado al implementar merge/snapshot).
    """
    snap_path = tmp_path / "snap_nulos"
    hash_original = _compute_corpus_hash(corpus_con_nulos.table)

    corpus_con_nulos.snapshot(snap_path)
    reloaded = CorpusSnapshot.load(snap_path)

    assert reloaded.manifest.corpus_hash == hash_original
    assert _compute_corpus_hash(reloaded.corpus.table) == hash_original
    assert reloaded.corpus == corpus_con_nulos
