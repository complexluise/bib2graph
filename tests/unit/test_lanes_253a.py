"""Corte 3a (#253, ADR 0053 D2): carriles por proveedor en el store.

Cubre la parte *store* del DoD del Corte 3: esquema (`provider` + PK compuesta),
backend atado a un carril (`corpus_lane`), migración v1→v2, curación por `id`
sincronizada entre carriles, `corpus_hash` por carril y el guardarraíl de SQL
crudo (R2).  Sin red; DuckDB en `tmp_path`.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from bib2graph.backends import InMemoryBackend, ProviderMismatchError
from bib2graph.backends.duckdb import DuckDBBackend
from bib2graph.backends.memory import compute_corpus_hash
from bib2graph.constants import Col, Provider
from bib2graph.corpus import Corpus, CorpusSnapshot, EnricherRef, read_corpus_parquet
from bib2graph.schemas import CORPUS_SCHEMA
from bib2graph.stores.duckdb import DuckDBStore

pytestmark = pytest.mark.integration

OA = Provider.OPENALEX
S2 = Provider.S2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row(
    id_: str,
    provider: str = "openalex",
    *,
    title: str | None = None,
    status: str = "candidate",
    provenance: str | None = None,
    is_seed: bool = True,
    **extra: Any,
) -> dict[str, Any]:
    row: dict[str, Any] = {name: None for name in CORPUS_SCHEMA.names}
    row.update(
        {
            Col.ID: id_,
            Col.PROVIDER: provider,
            Col.TITLE: title if title is not None else f"{provider} {id_}",
            Col.YEAR: 2020,
            Col.IS_SEED: is_seed,
            Col.CURATION_STATUS: status,
            Col.PROVENANCE: provenance,
        }
    )
    row.update(extra)
    return row


def _table(rows: list[dict[str, Any]]) -> pa.Table:
    return pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)


def _decision(action: str, at: str) -> str:
    return json.dumps(
        [{"action": action, "decided_by": "t", "decided_at": at, "source": None}]
    )


def _lane_store(path: Path, provider: Provider) -> DuckDBStore:
    return DuckDBStore(path, provider=provider)


def _hash(path: Path, provider: Provider) -> str:
    store = _lane_store(path, provider)
    try:
        return compute_corpus_hash(store.load().to_arrow())
    finally:
        store.close()


def _statuses(path: Path) -> list[tuple[str, str, str]]:
    """(id, provider, curation_status) de TODOS los carriles (lectura cruda)."""
    con = duckdb.connect(str(path))
    try:
        return sorted(
            con.execute("SELECT id, provider, curation_status FROM corpus").fetchall()
        )
    finally:
        con.close()


def _assert_one_state_per_id(path: Path) -> None:
    con = duckdb.connect(str(path))
    try:
        bad = con.execute(
            "SELECT id FROM corpus GROUP BY id HAVING COUNT(DISTINCT curation_status) > 1"
        ).fetchall()
    finally:
        con.close()
    assert bad == []


def _two_lanes(path: Path, ids: list[str]) -> None:
    """Siembra los mismos ids en los carriles openalex y s2."""
    oa = _lane_store(path, OA)
    oa.persist(Corpus.from_arrow(_table([_row(i, "openalex") for i in ids])))
    oa.close()
    s2 = _lane_store(path, S2)
    s2.persist(Corpus.from_arrow(_table([_row(i, "s2") for i in ids])))
    s2.close()


# ---------------------------------------------------------------------------
# Esquema y coexistencia
# ---------------------------------------------------------------------------


def test_schema_trae_provider_no_nullable_despues_de_id() -> None:
    names = CORPUS_SCHEMA.names
    assert names[:2] == ["id", "provider"]
    assert CORPUS_SCHEMA.field("provider").nullable is False


def test_mismo_doi_dos_carriles_coexisten(tmp_path: Path) -> None:
    path = tmp_path / "lib.duckdb"
    doi_id = "doi:aaaa1111bbbb2222"
    oa = _lane_store(path, OA)
    oa.persist(Corpus.from_arrow(_table([_row(doi_id, "openalex", title="Título OA")])))
    oa.close()
    s2 = _lane_store(path, S2)
    s2.persist(Corpus.from_arrow(_table([_row(doi_id, "s2", title="Título S2")])))
    s2.close()

    assert [(i, p) for i, p, _ in _statuses(path)] == [
        (doi_id, "openalex"),
        (doi_id, "s2"),
    ]
    for provider, title in ((OA, "Título OA"), (S2, "Título S2")):
        store = _lane_store(path, provider)
        try:
            table = store.load().to_arrow()
            assert table.column(Col.TITLE).to_pylist() == [title]  # ninguno pisado
        finally:
            store.close()


def test_load_y_len_solo_ven_su_carril(tmp_path: Path) -> None:
    path = tmp_path / "lib.duckdb"
    oa = _lane_store(path, OA)
    oa.persist(Corpus.from_arrow(_table([_row("a"), _row("b")])))
    oa.close()
    s2 = _lane_store(path, S2)
    s2.persist(Corpus.from_arrow(_table([_row("c", "s2")])))
    try:
        corpus = s2.load()
        assert len(corpus) == 1
        assert corpus.to_arrow().column(Col.ID).to_pylist() == ["c"]
        assert corpus.provider == "s2"
        assert len(corpus.seeds()) == 1 and len(corpus.candidates()) == 1
    finally:
        s2.close()


def test_corpus_hash_distingue_carriles() -> None:
    a = Corpus.from_arrow(_table([_row("x", "openalex", title="T")]))
    b = Corpus.from_arrow(_table([_row("x", "s2", title="T")]))
    assert compute_corpus_hash(a.to_arrow()) != compute_corpus_hash(b.to_arrow())


def test_hash_por_carril_estable_entre_aperturas(tmp_path: Path) -> None:
    path = tmp_path / "lib.duckdb"
    _two_lanes(path, ["a", "b"])
    assert _hash(path, OA) == _hash(path, OA)
    assert _hash(path, OA) != _hash(path, S2)


# ---------------------------------------------------------------------------
# No interferencia (R2)
# ---------------------------------------------------------------------------


def test_ingesta_en_carril_no_toca_otro(tmp_path: Path) -> None:
    path = tmp_path / "lib.duckdb"
    oa = _lane_store(path, OA)
    oa.persist(Corpus.from_arrow(_table([_row("a"), _row("b")])))
    oa.close()
    before = _hash(path, OA)

    s2 = _lane_store(path, S2)
    try:
        s2.persist_replace(
            Corpus.from_arrow(_table([_row("a", "s2"), _row("z", "s2")]))
        )
        s2.persist(Corpus.from_arrow(_table([_row("y", "s2")])))  # upsert
        s2.persist_replace(
            Corpus.from_arrow(_table([_row("a", "s2")]))
        )  # reescribe el carril
        s2.backend.persist_filter_steps([])
        s2.backend.add_referenced_refs(["r1"], cycle_round=1)
    finally:
        s2.close()

    assert _hash(path, OA) == before
    oa2 = _lane_store(path, OA)
    try:
        assert len(oa2.load()) == 2
    finally:
        oa2.close()


def test_overwrite_corpus_solo_borra_su_carril(tmp_path: Path) -> None:
    path = tmp_path / "lib.duckdb"
    _two_lanes(path, ["a", "b", "c"])
    s2 = _lane_store(path, S2)
    try:
        s2.persist_replace(Corpus.from_arrow(_table([_row("a", "s2")])))
    finally:
        s2.close()
    rows = _statuses(path)
    assert [r for r in rows if r[1] == "openalex"] == [
        ("a", "openalex", "candidate"),
        ("b", "openalex", "candidate"),
        ("c", "openalex", "candidate"),
    ]
    assert [r[0] for r in rows if r[1] == "s2"] == ["a"]


def test_seq_es_por_carril(tmp_path: Path) -> None:
    path = tmp_path / "lib.duckdb"
    oa = _lane_store(path, OA)
    oa.persist(Corpus.from_arrow(_table([_row("a"), _row("b"), _row("c")])))
    oa.close()
    s2 = _lane_store(path, S2)
    s2.persist(Corpus.from_arrow(_table([_row("z", "s2"), _row("y", "s2")])))
    try:
        # El orden de primera aparición se mide dentro del carril.
        assert s2.load().to_arrow().column(Col.ID).to_pylist() == ["z", "y"]
    finally:
        s2.close()
    con = duckdb.connect(str(path))
    try:
        seqs = dict(
            con.execute(
                "SELECT id, _seq FROM corpus WHERE provider IN ('s2')"
            ).fetchall()
        )
    finally:
        con.close()
    assert seqs == {"z": 1, "y": 2}  # empieza en 1, no continúa los del otro carril


# ---------------------------------------------------------------------------
# ProviderMismatchError
# ---------------------------------------------------------------------------


def test_merge_corpus_proveedores_distintos_falla() -> None:
    a = Corpus.from_arrow(_table([_row("a", "openalex")]))
    b = Corpus.from_arrow(_table([_row("b", "s2")]))
    with pytest.raises(ProviderMismatchError):
        a.merge(b)


def test_merge_corpus_vacio_con_cualquier_carril_ok() -> None:
    empty = Corpus.from_arrow(_table([]))
    s2 = Corpus.from_arrow(_table([_row("b", "s2")]))
    merged = empty.merge(s2)
    assert merged.provider == "s2" and empty.provider is None


def test_corpus_provider_mixto_falla() -> None:
    mixed = Corpus.from_arrow(_table([_row("a", "openalex"), _row("b", "s2")]))
    with pytest.raises(ProviderMismatchError):
        _ = mixed.provider


def test_escritura_fila_de_otro_carril_falla(tmp_path: Path) -> None:
    path = tmp_path / "lib.duckdb"
    store = _lane_store(path, S2)
    try:
        store.persist(Corpus.from_arrow(_table([_row("a", "s2")])))
        foreign = Corpus.from_arrow(_table([_row("b", "openalex")]))
        with pytest.raises(ProviderMismatchError):
            store.persist(foreign)
        with pytest.raises(ProviderMismatchError):
            store.backend.merge(foreign.to_arrow())
        with pytest.raises(ProviderMismatchError):
            store.backend.add_paper(_row("b", "openalex"))
        # overwrite con filas ajenas: falla ANTES de borrar el carril.
        with pytest.raises(ProviderMismatchError):
            store.persist_replace(foreign)
        assert len(store.load()) == 1
    finally:
        store.close()


def test_escritura_sin_provider_falla(tmp_path: Path) -> None:
    backend = DuckDBBackend(path=tmp_path / "lib.duckdb", provider=OA)
    try:
        table = _table([_row("a")])
        no_provider = table.set_column(
            1, CORPUS_SCHEMA.field("provider"), pa.array([None], type=pa.string())
        )
        with pytest.raises(ProviderMismatchError):
            backend._upsert_table(no_provider)
    finally:
        backend.close()


def test_provider_desconocido_falla_claro(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="openalex"):
        DuckDBBackend(path=tmp_path / "x.duckdb", provider="scopus")


def test_inmemory_backend_merge_mismatch() -> None:
    mem = InMemoryBackend(_table([_row("a", "openalex")]))
    with pytest.raises(ProviderMismatchError):
        mem.merge(_table([_row("b", "s2")]))
    with pytest.raises(ProviderMismatchError):
        mem.add_paper(_row("c", "s2"))


def test_add_paper_hereda_el_carril_del_corpus() -> None:
    corpus = Corpus.from_arrow(_table([_row("a", "s2")]))
    row = _row("b", "s2")
    row.pop(Col.PROVIDER)
    added = corpus.add_paper({k: v for k, v in row.items() if v is not None})
    assert added.provider == "s2"


# ---------------------------------------------------------------------------
# Sources sellan su token
# ---------------------------------------------------------------------------


def test_sources_sellan_provider() -> None:
    from bib2graph.sources.bibtex import _entry_to_row
    from bib2graph.sources.openalex import _work_to_row
    from bib2graph.sources.semanticscholar import _paper_to_row

    oa = _work_to_row(
        {"id": "https://openalex.org/W1", "title": "t"},
        equation_id="e",
        fetched_at="2026-01-01T00:00:00+00:00",
    )
    s2 = _paper_to_row(
        {"paperId": "p", "title": "t"},
        equation_id="e",
        fetched_at="2026-01-01T00:00:00+00:00",
    )
    assert oa[Col.PROVIDER] == "openalex"
    assert s2[Col.PROVIDER] == "s2"
    bib = _entry_to_row(
        {"title": "t"}, fetched_at="2026-01-01T00:00:00+00:00", provider=Provider.S2
    )
    assert bib[Col.PROVIDER] == "s2"


def test_bibtex_source_recibe_provider(tmp_path: Path) -> None:
    pytest.importorskip("bibtexparser")
    from bib2graph.sources.bibtex import BibtexSource

    bib = tmp_path / "x.bib"
    bib.write_text("@article{k, title={Un titulo}, year={2020}}", encoding="utf-8")
    assert BibtexSource(provider=Provider.S2).load(str(bib)).provider == "s2"
    assert BibtexSource().load(str(bib)).provider == "openalex"


# ---------------------------------------------------------------------------
# Migración v1 → v2
# ---------------------------------------------------------------------------

# DDL REAL de v1 (HEAD antes de #253): PK solo por id, sin `provider` ni
# `store_meta`; las hermanas sin columna `provider`.
_V1_DDL = [
    """
    CREATE TABLE corpus (
        id                   VARCHAR NOT NULL PRIMARY KEY,
        source_id            VARCHAR,
        doi                  VARCHAR,
        title                VARCHAR NOT NULL,
        year                 INTEGER,
        abstract             VARCHAR,
        source               VARCHAR,
        language             VARCHAR,
        publisher            VARCHAR,
        research_areas       VARCHAR[],
        is_seed              BOOLEAN NOT NULL,
        curation_status      VARCHAR NOT NULL,
        provenance           VARCHAR,
        authors_raw          VARCHAR[],
        authors_id           VARCHAR[],
        authors_affiliations VARCHAR[],
        keywords_raw         VARCHAR[],
        keywords_id          VARCHAR[],
        institutions_raw     VARCHAR[],
        institutions_id      VARCHAR[],
        references_id        VARCHAR[],
        references_doi       VARCHAR[],
        cited_by_id          VARCHAR[],
        _seq                 BIGINT
    )
    """,
    """CREATE TABLE loop_state_log (
        state VARCHAR NOT NULL, round INTEGER DEFAULT 0,
        recorded_at TIMESTAMPTZ NOT NULL DEFAULT now())""",
    """CREATE TABLE referenced_but_not_fetched (
        ref_id VARCHAR NOT NULL, cycle_round INTEGER NOT NULL DEFAULT 0,
        observed_at TIMESTAMPTZ NOT NULL DEFAULT now())""",
    """CREATE TABLE external_ids (
        paper_id VARCHAR NOT NULL, engine VARCHAR NOT NULL, id VARCHAR NOT NULL,
        PRIMARY KEY (paper_id, engine))""",
    """CREATE TABLE filter_log (
        name VARCHAR NOT NULL, criteria VARCHAR NOT NULL,
        count_before INTEGER NOT NULL, count_after INTEGER NOT NULL,
        recorded_at TIMESTAMPTZ NOT NULL DEFAULT now())""",
    """CREATE TABLE enricher_log (
        name VARCHAR NOT NULL, params_json VARCHAR NOT NULL DEFAULT '{}',
        recorded_at TIMESTAMPTZ NOT NULL DEFAULT now())""",
    """CREATE TABLE equations (
        equation_id VARCHAR NOT NULL PRIMARY KEY, engine VARCHAR NOT NULL,
        raw_query VARCHAR NOT NULL, params_json VARCHAR NOT NULL DEFAULT '{}',
        label VARCHAR, created_at VARCHAR NOT NULL, _seq BIGINT)""",
]


def _make_v1_store(path: Path) -> None:
    """Construye un `.duckdb` v1 fiel: 3 papers con `_seq` no contiguo + hermanas."""
    con = duckdb.connect(str(path))
    for ddl in _V1_DDL:
        con.execute(ddl)
    # `_seq` intencionalmente no contiguo y fuera del orden alfabético de id.
    for id_, title, seq, status in (
        ("doi:ccc", "C", 10, "accepted"),
        ("doi:aaa", "A", 20, "candidate"),
        ("doi:bbb", "B", 30, "rejected"),
    ):
        con.execute(
            "INSERT INTO corpus (id, title, is_seed, curation_status, _seq, "
            "keywords_raw) VALUES (?, ?, TRUE, ?, ?, ['k1','k2'])",
            [id_, title, status, seq],
        )
    con.execute("INSERT INTO loop_state_log (state, round) VALUES ('SEEDED', 1)")
    con.execute(
        "INSERT INTO referenced_but_not_fetched (ref_id, cycle_round) VALUES ('W9', 1)"
    )
    con.execute("INSERT INTO filter_log VALUES ('year', 'year>=2000', 3, 2, now())")
    con.execute("INSERT INTO enricher_log (name, params_json) VALUES ('oa', '{}')")
    con.execute("INSERT INTO external_ids VALUES ('doi:ccc', 'openalex', 'W1')")
    con.execute(
        "INSERT INTO equations VALUES ('eq-1', 'openalex', 'q', '{}', NULL, 't', 1)"
    )
    con.close()


def _meta(path: Path) -> dict[str, str]:
    con = duckdb.connect(str(path))
    try:
        return dict(con.execute("SELECT key, value FROM store_meta").fetchall())
    finally:
        con.close()


def test_migracion_v1_a_v2(tmp_path: Path) -> None:
    path = tmp_path / "v1.duckdb"
    _make_v1_store(path)

    store = DuckDBStore(path)  # default: legacy = openalex
    try:
        table = store.load().to_arrow()
        # Orden por `_seq` preservado (no alfabético).
        assert table.column(Col.ID).to_pylist() == ["doi:ccc", "doi:aaa", "doi:bbb"]
        assert set(table.column(Col.PROVIDER).to_pylist()) == {"openalex"}
        assert table.column(Col.CURATION_STATUS).to_pylist() == [
            "accepted",
            "candidate",
            "rejected",
        ]
        assert table.column(Col.KEYWORDS_RAW).to_pylist()[0] == ["k1", "k2"]
        # Hermanas conservadas y etiquetadas con el carril legacy.
        assert store.backend.referenced_refs() == ["W9"]
        assert [s["name"] for s in store.backend.load_filter_steps()] == ["year"]
        assert [r["name"] for r in store.backend.load_enricher_refs()] == ["oa"]
        assert store.backend.external_ids_for("doi:ccc") == {"openalex": "W1"}
        assert [e["equation_id"] for e in store.backend.load_equations()] == ["eq-1"]
        assert store.backend.loop_state() is not None
    finally:
        store.close()
    assert _meta(path) == {"schema_version": "2"}


def test_migracion_segunda_apertura_no_op(tmp_path: Path) -> None:
    path = tmp_path / "v1.duckdb"
    _make_v1_store(path)
    DuckDBStore(path, provider=OA, legacy_provider=OA).close()
    before = _statuses(path)

    # Reabrir con OTRO legacy_provider no vuelve a migrar ni re-etiqueta.
    store = DuckDBStore(path, provider=S2, legacy_provider=S2)
    try:
        assert len(store.load()) == 0  # el carril s2 está vacío
    finally:
        store.close()
    assert _statuses(path) == before
    assert {p for _, p, _ in before} == {"openalex"}
    assert _meta(path) == {"schema_version": "2"}


def test_migracion_usa_source_del_workspace(tmp_path: Path) -> None:
    path = tmp_path / "v1.duckdb"
    _make_v1_store(path)
    store = DuckDBStore(path, provider=S2, legacy_provider=S2)
    try:
        corpus = store.load()
        assert len(corpus) == 3 and corpus.provider == "s2"
        assert store.backend.referenced_refs() == ["W9"]  # hermanas → s2 también
    finally:
        store.close()
    assert {p for _, p, _ in _statuses(path)} == {"s2"}


def test_workspace_init_adopta_duckdb_legacy_con_su_source(tmp_path: Path) -> None:
    """`b2g init .` sobre un `.duckdb` v1 lo migra con `workspace.json.source`."""
    from bib2graph.workspace import Workspace

    root = tmp_path / "ws"
    root.mkdir()
    _make_v1_store(root / "library.duckdb")
    Workspace.init(root, "legacy", source=S2)
    assert {p for _, p, _ in _statuses(root / "library.duckdb")} == {"s2"}


def test_migracion_es_transaccional(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "v1.duckdb"
    _make_v1_store(path)

    def boom(self: DuckDBBackend, table: str, column: str) -> bool:
        raise RuntimeError("falla a mitad de la migración")

    with monkeypatch.context() as m:
        m.setattr(DuckDBBackend, "_column_exists", boom)
        with pytest.raises(RuntimeError, match="a mitad"):
            DuckDBBackend(path=path)

    # ROLLBACK: el store sigue siendo v1 íntegro (sin store_meta, sin `provider`).
    con = duckdb.connect(str(path))
    try:
        cols = {r[0] for r in con.execute("DESCRIBE corpus").fetchall()}
        assert "provider" not in cols
        assert con.execute("SELECT COUNT(*) FROM corpus").fetchone() == (3,)
        assert con.execute("SELECT COUNT(*) FROM store_meta").fetchone() == (0,)
        assert not con.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name='corpus_v2'"
        ).fetchall()
    finally:
        con.close()
    # Reintentable: sin el fallo, migra.
    store = DuckDBStore(path)
    try:
        assert len(store.load()) == 3
    finally:
        store.close()


def test_store_de_version_futura_falla_claro(tmp_path: Path) -> None:
    from bib2graph.backends.duckdb import StoreSchemaError

    path = tmp_path / "lib.duckdb"
    DuckDBStore(path).close()
    con = duckdb.connect(str(path))
    con.execute("UPDATE store_meta SET value = '99' WHERE key = 'schema_version'")
    con.close()
    with pytest.raises(StoreSchemaError, match="99"):
        DuckDBStore(path)


def test_store_nuevo_nace_v2(tmp_path: Path) -> None:
    path = tmp_path / "new.duckdb"
    DuckDBStore(path).close()
    assert _meta(path) == {"schema_version": "2"}


# ---------------------------------------------------------------------------
# Curación por id (D2.2)
# ---------------------------------------------------------------------------


def test_curacion_por_id_propaga_entre_carriles(tmp_path: Path) -> None:
    path = tmp_path / "lib.duckdb"
    _two_lanes(path, ["a", "b"])

    oa = _lane_store(path, OA)
    oa.load().accept(["a"], decided_at=_dt("2026-01-01T00:00:00+00:00"))
    oa.close()
    assert dict((i, s) for i, p, s in _statuses(path) if p == "s2")["a"] == "accepted"
    _assert_one_state_per_id(path)

    # Rechazar después en B → ambos rechazados.
    s2 = _lane_store(path, S2)
    s2.load().reject(["a"], decided_at=_dt("2026-02-01T00:00:00+00:00"))
    s2.close()
    assert [s for i, _, s in _statuses(path) if i == "a"] == ["rejected", "rejected"]
    _assert_one_state_per_id(path)

    # Y la decisión humana MÁS RECIENTE gana también en el otro sentido.
    oa = _lane_store(path, OA)
    oa.load().accept(["a"], decided_at=_dt("2026-03-01T00:00:00+00:00"))
    oa.close()
    assert [s for i, _, s in _statuses(path) if i == "a"] == ["accepted", "accepted"]
    _assert_one_state_per_id(path)


def test_evento_de_curacion_queda_solo_en_el_carril_que_decidio(tmp_path: Path) -> None:
    path = tmp_path / "lib.duckdb"
    _two_lanes(path, ["a"])
    oa = _lane_store(path, OA)
    oa.load().accept(["a"], decided_at=_dt("2026-01-01T00:00:00+00:00"))
    oa.close()
    con = duckdb.connect(str(path))
    try:
        prov = dict(con.execute("SELECT provider, provenance FROM corpus").fetchall())
    finally:
        con.close()
    assert "accepted" in (prov["openalex"] or "")
    assert not prov["s2"]  # la fila hermana recibe el estado, no el evento


def test_invariante_curacion_un_estado_por_id_tras_cada_operacion(
    tmp_path: Path,
) -> None:
    path = tmp_path / "lib.duckdb"
    _two_lanes(path, ["a", "b", "c"])
    _assert_one_state_per_id(path)

    oa = _lane_store(path, OA)
    corpus = oa.load()
    oa.persist(corpus.accept(["a"], decided_at=_dt("2026-01-01T00:00:00+00:00")))
    _assert_one_state_per_id(path)
    oa.persist_replace(oa.load())
    _assert_one_state_per_id(path)
    oa.backend.add_paper(_row("d", "openalex"))
    _assert_one_state_per_id(path)
    oa.close()

    s2 = _lane_store(path, S2)
    s2.load().reject(["b"], decided_at=_dt("2026-01-02T00:00:00+00:00"))
    _assert_one_state_per_id(path)
    s2.persist(Corpus.from_arrow(_table([_row("a", "s2", status="rejected")])))
    _assert_one_state_per_id(path)
    s2.close()


def test_carril_nuevo_hereda_curacion(tmp_path: Path) -> None:
    path = tmp_path / "lib.duckdb"
    oa = _lane_store(path, OA)
    oa.persist(
        Corpus.from_arrow(
            _table(
                [
                    _row(
                        "a",
                        "openalex",
                        status="accepted",
                        provenance=_decision("accepted", "2026-01-01T00:00:00+00:00"),
                    ),
                    _row("b", "openalex", status="rejected"),
                ]
            )
        )
    )
    oa.close()
    # El paper llega por s2 como candidate: entra con la curación del paper.
    s2 = _lane_store(path, S2)
    s2.persist(Corpus.from_arrow(_table([_row("a", "s2"), _row("b", "s2")])))
    try:
        got = dict(
            zip(
                s2.load().to_arrow().column(Col.ID).to_pylist(),
                s2.load().to_arrow().column(Col.CURATION_STATUS).to_pylist(),
                strict=True,
            )
        )
    finally:
        s2.close()
    assert got == {"a": "accepted", "b": "rejected"}
    _assert_one_state_per_id(path)


def test_overwrite_hereda_curacion(tmp_path: Path) -> None:
    path = tmp_path / "lib.duckdb"
    oa = _lane_store(path, OA)
    oa.persist(Corpus.from_arrow(_table([_row("a", status="accepted")])))
    oa.close()
    s2 = _lane_store(path, S2)
    s2.persist_replace(Corpus.from_arrow(_table([_row("a", "s2")])))
    s2.close()
    assert [s for _, _, s in _statuses(path)] == ["accepted", "accepted"]


def test_filter_respeta_aceptado_de_otro_carril(tmp_path: Path) -> None:
    """ADR 0044: `curate filter` sobre s2 no rechaza lo aceptado en openalex."""
    from bib2graph.service.curate import filter_corpus

    path = tmp_path / "lib.duckdb"
    oa = _lane_store(path, OA)
    oa.persist(
        Corpus.from_arrow(_table([_row("keep", year=1990), _row("drop", year=1990)]))
    )
    oa.load().accept(["keep"], decided_at=_dt("2026-01-01T00:00:00+00:00"))
    oa.close()
    s2 = _lane_store(path, S2)
    s2.persist(
        Corpus.from_arrow(
            _table([_row("keep", "s2", year=1990), _row("drop", "s2", year=1990)])
        )
    )
    s2.close()

    filter_corpus(
        path, provider=S2, year_gte=2000, decided_at=_dt("2026-02-01T00:00:00+00:00")
    )

    s2_status = {i: s for i, p, s in _statuses(path) if p == "s2"}
    assert s2_status == {"keep": "accepted", "drop": "rejected"}
    _assert_one_state_per_id(path)


def test_sync_es_set_based_y_rapido(tmp_path: Path) -> None:
    path = tmp_path / "lib.duckdb"
    n = 20_000
    ids = [f"p{i}" for i in range(n)]
    oa = _lane_store(path, OA)
    oa.persist(Corpus.from_arrow(_table([_row(i, status="accepted") for i in ids])))
    oa.close()
    s2 = _lane_store(path, S2)
    t0 = time.perf_counter()
    s2.persist(Corpus.from_arrow(_table([_row(i, "s2") for i in ids])))
    elapsed = time.perf_counter() - t0
    s2.close()
    assert elapsed < 15, f"sync de {n} ids tardó {elapsed:.1f}s (¿loop Python?)"
    assert {s for _, p, s in _statuses(path) if p == "s2"} == {"accepted"}


def test_un_solo_carril_no_paga_el_sync(tmp_path: Path) -> None:
    backend = DuckDBBackend(path=tmp_path / "lib.duckdb", provider=OA)
    try:
        calls: list[str] = []
        real = backend._con.execute

        class Spy:
            def __init__(self, con: Any) -> None:
                self._con = con

            def __getattr__(self, name: str) -> Any:
                return getattr(self._con, name)

            def execute(self, sql: str, *a: Any, **k: Any) -> Any:
                calls.append(sql)
                return real(sql, *a, **k)

        backend._con = Spy(backend._con)  # type: ignore[assignment]
        backend._upsert_table(_table([_row("a")]))
        assert not any("_latest_human_decided_at_udf" in c for c in calls)
    finally:
        backend.close()


# ---------------------------------------------------------------------------
# Dedup intra-carril
# ---------------------------------------------------------------------------


def test_dedup_intra_carril(tmp_path: Path) -> None:
    from bib2graph.preprocessors.pipeline import normalize_and_dedup

    path = tmp_path / "lib.duckdb"
    oa = _lane_store(path, OA)
    oa.persist(
        Corpus.from_arrow(
            _table(
                [
                    _row(
                        "a",
                        "openalex",
                        authors_raw=["Smith, J."],
                        authors_id=["Smith, J."],
                    )
                ]
            )
        )
    )
    oa.close()
    before = _hash(path, OA)

    s2 = _lane_store(path, S2)
    try:
        s2.persist(
            Corpus.from_arrow(
                _table(
                    [
                        _row(
                            "a",
                            "s2",
                            authors_raw=["Smith, J.", "J. Smith"],
                            authors_id=["Smith, J.", "J. Smith"],
                        )
                    ]
                )
            )
        )
        deduped = normalize_and_dedup(
            s2.load(), applied_at=_dt("2026-01-01T00:00:00+00:00")
        )
        s2.persist_replace(deduped)
    finally:
        s2.close()

    assert _hash(path, OA) == before  # el canónico de autores no cruza carriles
    assert deduped.provider == "s2"


# ---------------------------------------------------------------------------
# Hermanas por carril y equations
# ---------------------------------------------------------------------------


def test_hermanas_son_por_carril(tmp_path: Path) -> None:
    path = tmp_path / "lib.duckdb"
    oa = _lane_store(path, OA)
    oa.backend.add_referenced_refs(["W1", "W2"], cycle_round=1)
    oa.backend.persist_filter_steps(
        [
            type(
                "S",
                (),
                {"name": "n", "criteria": "c", "count_before": 5, "count_after": 3},
            )()
        ]
    )
    oa.backend.persist_enricher_refs([EnricherRef(name="e1")])
    oa.close()
    s2 = _lane_store(path, S2)
    try:
        assert s2.backend.referenced_refs() == []
        assert s2.backend.referenced_refs_count() == 0
        assert s2.backend.load_filter_steps() == []
        assert s2.backend.load_enricher_refs() == []
        # `replace=True` en s2 no borra lo de openalex.
        s2.backend.persist_filter_steps([])
        s2.backend.persist_enricher_refs([])
        s2.backend.add_referenced_refs(["W1"], cycle_round=1)  # mismo id, otro carril
        assert s2.backend.referenced_refs() == ["W1"]
    finally:
        s2.close()
    oa2 = _lane_store(path, OA)
    try:
        assert oa2.backend.referenced_refs() == ["W1", "W2"]
        assert len(oa2.backend.load_filter_steps()) == 1
        assert len(oa2.backend.load_enricher_refs()) == 1
    finally:
        oa2.close()


def test_equation_hash_por_carril(tmp_path: Path) -> None:
    path = tmp_path / "lib.duckdb"
    oa = _lane_store(path, OA)
    oa.persist(Corpus.from_arrow(_table([_row("a")])))
    oa.backend.persist_equation(
        "eq-oa", engine="openalex", raw_query="alpha", params_json="{}"
    )
    oa.close()
    s2 = _lane_store(path, S2)
    s2.persist(Corpus.from_arrow(_table([_row("a", "s2")])))
    s2.backend.persist_equation(
        "eq-s2", engine="s2", raw_query="beta", params_json="{}"
    )
    s2.close()

    for provider, eq_id, query in ((OA, "eq-oa", "alpha"), (S2, "eq-s2", "beta")):
        store = _lane_store(path, provider)
        try:
            corpus = store.load()
            assert [e.equation_id for e in corpus.manifest.equations] == [eq_id]
            meta = corpus.to_arrow().schema.metadata
            assert meta[b"equation_id"] == eq_id.encode()
            assert meta[b"equation_expression"] == query.encode()
        finally:
            store.close()


def test_external_ids_huerfanos_por_carril(tmp_path: Path) -> None:
    path = tmp_path / "lib.duckdb"
    oa = _lane_store(path, OA)
    corpus = Corpus.from_arrow(_table([_row("x", source_id="W1")]))
    oa.persist(corpus)
    oa.register_external_ids(corpus)
    oa.close()
    s2c = Corpus.from_arrow(_table([_row("x", "s2", source_id="s2x")]))
    s2 = _lane_store(path, S2)
    s2.persist(s2c)
    s2.register_external_ids(s2c)
    s2.close()

    # El carril openalex reemplaza `x` por `y` (p. ej. dedup): se limpia SOLO su huérfano.
    oa = _lane_store(path, OA)
    new = Corpus.from_arrow(_table([_row("y", source_id="W1")]))
    oa.persist_replace(new)
    oa.register_external_ids(new)
    try:
        assert sorted(oa.backend.all_external_ids()) == sorted(
            [("y", "openalex", "W1"), ("x", "s2", "s2x")]
        )
    finally:
        oa.close()


# ---------------------------------------------------------------------------
# Compat de snapshot v1
# ---------------------------------------------------------------------------


def _v1_parquet(path: Path, rows: list[dict[str, Any]]) -> None:
    table = _table(rows).drop_columns([Col.PROVIDER])
    pq.write_table(table, str(path))  # type: ignore[no-untyped-call]


def test_snapshot_v1_compat_lee_como_openalex(tmp_path: Path) -> None:
    snap_dir = tmp_path / "snap"
    snap_dir.mkdir()
    _v1_parquet(snap_dir / "corpus.parquet", [_row("a"), _row("b")])
    (snap_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "1",
                "corpus_hash": "x",
                "lib_version": "0",
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    corpus = CorpusSnapshot.load(snap_dir).corpus
    assert corpus.provider == "openalex" and len(corpus) == 2
    assert read_corpus_parquet(snap_dir / "corpus.parquet").schema.equals(CORPUS_SCHEMA)


def test_snapshot_v1_compat_restore_en_openalex(tmp_path: Path) -> None:
    from bib2graph.service.snapshot import run_restore

    parquet = tmp_path / "corpus.parquet"
    _v1_parquet(parquet, [_row("a"), _row("b")])
    store_path = tmp_path / "lib.duckdb"
    data = run_restore(store_path, parquet)
    assert data["total_papers"] == 2
    assert {p for _, p, _ in _statuses(store_path)} == {"openalex"}


def test_restore_de_carril_ajeno_falla_accionable(tmp_path: Path) -> None:
    from bib2graph.service.errors import DataError
    from bib2graph.service.snapshot import run_restore

    parquet = tmp_path / "corpus.parquet"
    pq.write_table(_table([_row("a", "s2")]), str(parquet))  # type: ignore[no-untyped-call]
    with pytest.raises(DataError, match="carril"):
        run_restore(tmp_path / "lib.duckdb", parquet, provider=OA)


def test_snapshot_nuevo_es_schema_v2(tmp_path: Path) -> None:
    corpus = Corpus.from_arrow(_table([_row("a", "s2")]))
    snap = corpus.snapshot(tmp_path / "snap")
    assert snap.manifest.schema_version == "2"
    assert snap.corpus.provider == "s2"
    assert (
        Col.PROVIDER
        in pq.read_table(str(tmp_path / "snap" / "corpus.parquet")).column_names
    )  # type: ignore[no-untyped-call]


# ---------------------------------------------------------------------------
# Contrato Arrow aditivo y guardarraíl de SQL crudo (R2)
# ---------------------------------------------------------------------------


def test_columna_provider_es_aditiva_en_el_arrow() -> None:
    corpus = Corpus.from_arrow(_table([_row("a")]))
    table = corpus.to_arrow()
    assert table.schema.field("provider").type == pa.string()
    # Las columnas congeladas por tests/unit/test_arrow_schema_contract.py siguen.
    for name in ("id", "source_id", "references_id", "curation_status"):
        assert name in table.column_names


_RAW_CORPUS_SQL = re.compile(
    r"\b(FROM|JOIN|INTO|UPDATE)\s+corpus\b(?!_)", re.IGNORECASE
)


def test_no_sql_crudo_sobre_corpus_fuera_de_backends() -> None:
    """R2: un `FROM corpus` crudo fuera de `backends/` leería/borraría TODOS los carriles.

    Todo SQL de lectura del corpus fuera del backend debe ir contra `corpus_lane`.
    """
    src = Path(__file__).resolve().parents[2] / "src" / "bib2graph"
    offenders: list[str] = []
    for py in src.rglob("*.py"):
        if "backends" in py.relative_to(src).parts:
            continue
        for lineno, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            if _RAW_CORPUS_SQL.search(line):
                offenders.append(f"{py.relative_to(src)}:{lineno}: {line.strip()}")
    assert offenders == [], (
        "SQL crudo sobre `corpus` fuera de backends/:\n" + "\n".join(offenders)
    )


def test_query_del_backend_lee_corpus_lane(tmp_path: Path) -> None:
    path = tmp_path / "lib.duckdb"
    _two_lanes(path, ["a", "b"])
    s2 = _lane_store(path, S2)
    try:
        counts = s2.backend.query("SELECT COUNT(*) AS n FROM corpus_lane")
        assert counts.column("n").to_pylist() == [2]
        only = s2.backend.query("SELECT DISTINCT provider FROM corpus_lane")
        assert only.column("provider").to_pylist() == ["s2"]
    finally:
        s2.close()


def test_clone_memory_conserva_carril_y_todos_los_datos() -> None:
    backend = DuckDBBackend(_table([_row("a", "s2")]), provider=S2)
    try:
        backend.add_referenced_refs(["W1"], cycle_round=1)
        clone = backend._clone()
        try:
            assert clone.provider == S2
            assert clone.referenced_refs() == ["W1"]
            assert clone.to_arrow().column(Col.ID).to_pylist() == ["a"]
        finally:
            clone.close()
    finally:
        backend.close()


def _dt(iso: str) -> Any:
    from datetime import datetime

    return datetime.fromisoformat(iso)
