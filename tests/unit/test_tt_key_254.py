"""Corte 4 (#254, ADR 0053 D3): migración v2→v3 de ids ``tt:`` y compat de snapshot.

Los tests de ``_title_key``/``_compute_id`` (casos del DoD, valores dorados de
``doi:``/``src:``) viven en ``test_compute_id.py``.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from bib2graph.backends.duckdb import DuckDBBackend
from bib2graph.constants import Col, Provider
from bib2graph.corpus import (
    Corpus,
    CorpusSnapshot,
    _compute_id,
    read_corpus_parquet,
)
from bib2graph.schemas import CORPUS_SCHEMA
from bib2graph.stores.duckdb import DuckDBStore

pytestmark = pytest.mark.integration

OA = Provider.OPENALEX
S2 = Provider.S2

_EXAMPLE = (
    Path(__file__).parent.parent.parent / "examples" / "valoraciones" / "corpus.parquet"
)
# corpus_hash del ejemplo commiteado medido ANTES de D3 (0 ids tt:).
_EXAMPLE_HASH = "9141a8c6fa62e9527267a078a470b41ac6911370a8f892df655805488ae84844"


def _old_tt(title: str, year: int | None) -> str:
    """Id ``tt:`` con la clave vieja (``title.lower().strip()``)."""
    digest = hashlib.sha256(f"{title.lower().strip()}|{year}".encode()).hexdigest()
    return f"tt:{digest[:16]}"


def _row(
    id_: str,
    provider: str,
    title: str,
    year: int | None = 2020,
    *,
    seq: int,
    status: str = "candidate",
    provenance: str | None = None,
    keywords: list[str] | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {name: None for name in CORPUS_SCHEMA.names}
    row.update(
        {
            Col.ID: id_,
            Col.PROVIDER: provider,
            Col.TITLE: title,
            Col.YEAR: year,
            Col.IS_SEED: True,
            Col.CURATION_STATUS: status,
            Col.PROVENANCE: provenance,
            Col.KEYWORDS_RAW: keywords,
            "_seq": seq,
        }
    )
    return row


def _make_v2_store(
    path: Path,
    rows: list[dict[str, Any]],
    external: list[tuple[str, str, str]] = (),  # type: ignore[assignment]
) -> None:
    """Fabrica un store v2: schema vigente + filas crudas + ``schema_version = 2``."""
    DuckDBStore(path).close()
    con = duckdb.connect(str(path))
    try:
        schema = CORPUS_SCHEMA.append(pa.field("_seq", pa.int64()))
        table = pa.Table.from_pylist(rows, schema=schema)
        con.register("_rows", table)
        cols = ", ".join(schema.names)
        con.execute(f"INSERT INTO corpus ({cols}) SELECT {cols} FROM _rows")
        con.unregister("_rows")
        for paper_id, engine, id_ in external:
            con.execute(
                "INSERT INTO external_ids VALUES (?, ?, ?)", [paper_id, engine, id_]
            )
        con.execute("UPDATE store_meta SET value = '2' WHERE key = 'schema_version'")
    finally:
        con.close()


def _raw(path: Path, sql: str) -> list[tuple[Any, ...]]:
    con = duckdb.connect(str(path))
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def _decision(action: str, at: str) -> str:
    return json.dumps(
        [{"action": action, "decided_by": "t", "decided_at": at, "source": None}]
    )


CAFE_NEW = _compute_id(None, None, "Cafe", 2020)


# ---------------------------------------------------------------------------
# Migración v2 -> v3
# ---------------------------------------------------------------------------


def test_migracion_v2_a_v3_fusiona_cafe_y_remapea_external_ids(tmp_path: Path) -> None:
    path = tmp_path / "lib.duckdb"
    accent, plain = _old_tt("Café", 2020), _old_tt("Cafe", 2020)
    assert accent != plain
    # `Cafe` ya tenía la clave nueva (ascii en minúscula): conserva su id.
    assert plain == CAFE_NEW
    _make_v2_store(
        path,
        [
            _row(accent, "openalex", "Café", seq=5, keywords=["a"]),
            _row(plain, "openalex", "Cafe", seq=9, keywords=["b"]),
        ],
        external=[(accent, "openalex", "W1"), (plain, "doi", "10.1/x")],
    )

    store = DuckDBStore(path, provider=OA)
    try:
        table = store.load().to_arrow()
        assert table.column(Col.ID).to_pylist() == [CAFE_NEW]  # una fila fusionada
        assert sorted(table.column(Col.KEYWORDS_RAW).to_pylist()[0]) == ["a", "b"]
        assert store.backend.external_ids_for(CAFE_NEW) == {
            "openalex": "W1",
            "doi": "10.1/x",
        }
    finally:
        store.close()
    assert _raw(path, "SELECT value FROM store_meta WHERE key='schema_version'") == [
        ("3",)
    ]
    assert (
        _raw(
            path,
            "SELECT paper_id FROM external_ids WHERE paper_id <> ?".replace(
                "?", f"'{CAFE_NEW}'"
            ),
        )
        == []
    )
    # `_seq` de la fusionada = el menor (orden de primera aparición).
    assert _raw(path, "SELECT _seq FROM corpus") == [(5,)]


def test_migracion_titulos_solo_puntuacion_no_se_fusionan(tmp_path: Path) -> None:
    path = tmp_path / "lib.duckdb"
    titles = ["...", "???", "---", "—"]
    ids = [_old_tt(t, 2020) for t in titles]
    assert len(set(ids)) == 4
    _make_v2_store(
        path,
        [
            _row(i, "openalex", t, seq=n + 1)
            for n, (i, t) in enumerate(zip(ids, titles, strict=True))
        ],
    )
    DuckDBStore(path, provider=OA).close()
    # Sin fusión: mismos ids (clave previa a #254) y mismas 4 filas.
    assert sorted(r[0] for r in _raw(path, "SELECT id FROM corpus")) == sorted(ids)


def test_snapshot_pre_v3_titulos_solo_puntuacion_no_se_fusionan(tmp_path: Path) -> None:
    titles = ["...", "???"]
    ids = [_old_tt(t, 2020) for t in titles]
    rows = [
        _row(i, "openalex", t, seq=n + 1)
        for n, (i, t) in enumerate(zip(ids, titles, strict=True))
    ]
    _write_snapshot(tmp_path / "sp", rows, "2")
    table = CorpusSnapshot.load(tmp_path / "sp").corpus.to_arrow()
    assert table.column(Col.ID).to_pylist() == ids


def test_snapshot_sella_schema_version_en_metadata_y_es_preferente(
    tmp_path: Path,
) -> None:
    corpus = Corpus.from_arrow(
        pa.Table.from_pylist(
            [{**_row("doi:a", "openalex", "A", seq=1), "_seq": None}],
            schema=CORPUS_SCHEMA,
        )
    )
    corpus.snapshot(tmp_path / "snap")
    parquet = tmp_path / "snap" / "corpus.parquet"
    meta = pq.read_schema(str(parquet)).metadata  # type: ignore[no-untyped-call]
    assert meta[b"bib2graph.schema_version"] == b"3"
    # La metadata gana sobre un manifest que dice "2": no se recalcula.
    accent = _old_tt("Café", 2020)
    t = pa.Table.from_pylist(
        [_row(accent, "openalex", "Café", seq=1)], schema=CORPUS_SCHEMA
    ).replace_schema_metadata({b"bib2graph.schema_version": b"3"})
    pq.write_table(t, str(parquet))  # type: ignore[no-untyped-call]
    (tmp_path / "snap" / "manifest.json").write_text(
        json.dumps({"schema_version": "2"}), encoding="utf-8"
    )
    assert read_corpus_parquet(parquet).column(Col.ID).to_pylist() == [accent]


def test_manifest_sin_schema_version_es_version_desconocida(tmp_path: Path) -> None:
    accent = _old_tt("Café", 2020)
    d = tmp_path / "nov"
    d.mkdir()
    pq.write_table(  # type: ignore[no-untyped-call]
        pa.Table.from_pylist(
            [_row(accent, "openalex", "Café", seq=1)], schema=CORPUS_SCHEMA
        ),
        str(d / "corpus.parquet"),
    )
    (d / "manifest.json").write_text("{}", encoding="utf-8")
    # Desconocida = igual que sin manifest: no se recalcula (hay columna provider).
    assert read_corpus_parquet(d / "corpus.parquet").column(Col.ID).to_pylist() == [
        accent
    ]


def test_migracion_no_toca_doi_ni_src_y_segunda_apertura_es_noop(
    tmp_path: Path,
) -> None:
    path = tmp_path / "lib.duckdb"
    doi_id = _compute_id("10.1/x", None, "Café", 2020)
    src_id = _compute_id(None, "W123", "Café", 2020)
    assert doi_id == "doi:4d718a0a89634e64" and src_id == "src:b9932de3e4b0566b"
    _make_v2_store(
        path,
        [
            _row(doi_id, "openalex", "Café", seq=1),
            _row(src_id, "openalex", "Café", seq=2),
            _row(_old_tt("Café", 2020), "openalex", "Café", seq=3),
        ],
    )
    before = _raw(
        path,
        "SELECT * FROM corpus WHERE id LIKE 'doi:%' OR id LIKE 'src:%' ORDER BY id",
    )
    DuckDBStore(path, provider=OA).close()
    after = _raw(
        path,
        "SELECT * FROM corpus WHERE id LIKE 'doi:%' OR id LIKE 'src:%' ORDER BY id",
    )
    assert before == after and len(after) == 2
    ids = {r[0] for r in _raw(path, "SELECT id FROM corpus")}
    assert ids == {doi_id, src_id, _compute_id(None, None, "Café", 2020)}

    snapshot = _raw(path, "SELECT * FROM corpus ORDER BY id")
    DuckDBStore(path, provider=OA).close()  # one-shot: no vuelve a migrar
    assert _raw(path, "SELECT * FROM corpus ORDER BY id") == snapshot


def test_migracion_no_fusiona_entre_carriles_pero_sincroniza_curacion(
    tmp_path: Path,
) -> None:
    path = tmp_path / "lib.duckdb"
    accent, plain = _old_tt("Café", 2020), _old_tt("Cafe", 2020)
    _make_v2_store(
        path,
        [
            _row(
                accent,
                "openalex",
                "Café",
                seq=1,
                status="accepted",
                provenance=_decision("accepted", "2026-01-01T00:00:00+00:00"),
            ),
            _row(plain, "s2", "Cafe", seq=1),
        ],
    )
    DuckDBStore(path, provider=OA).close()
    rows = _raw(
        path, "SELECT id, provider, curation_status FROM corpus ORDER BY provider"
    )
    # Un registro por carril (no se fusionan carriles distintos), mismo id.
    assert rows == [
        (CAFE_NEW, "openalex", "accepted"),
        (CAFE_NEW, "s2", "accepted"),  # curación re-sincronizada (D2.2)
    ]


def test_migracion_cadena_v1_a_v3_en_una_apertura(tmp_path: Path) -> None:
    path = tmp_path / "v1.duckdb"
    con = duckdb.connect(str(path))
    con.execute(
        """CREATE TABLE corpus (
            id VARCHAR PRIMARY KEY, source_id VARCHAR, doi VARCHAR,
            title VARCHAR NOT NULL, year INTEGER, abstract VARCHAR, source VARCHAR,
            language VARCHAR, publisher VARCHAR, research_areas VARCHAR[],
            is_seed BOOLEAN NOT NULL, curation_status VARCHAR NOT NULL,
            provenance VARCHAR, authors_raw VARCHAR[], authors_id VARCHAR[],
            authors_affiliations VARCHAR[], keywords_raw VARCHAR[],
            keywords_id VARCHAR[], institutions_raw VARCHAR[],
            institutions_id VARCHAR[], references_id VARCHAR[],
            references_doi VARCHAR[], cited_by_id VARCHAR[], _seq BIGINT)"""
    )
    con.execute(
        "CREATE TABLE external_ids (paper_id VARCHAR NOT NULL, engine VARCHAR NOT NULL,"
        " id VARCHAR NOT NULL, PRIMARY KEY (paper_id, engine))"
    )
    old = _old_tt("Straße", 2020)
    con.execute(
        "INSERT INTO corpus (id, title, year, is_seed, curation_status, _seq) "
        "VALUES (?, 'Straße', 2020, TRUE, 'candidate', 1)",
        [old],
    )
    con.execute("INSERT INTO external_ids VALUES (?, 'openalex', 'W7')", [old])
    con.close()

    store = DuckDBStore(path, provider=S2, legacy_provider=S2)
    try:
        new = _compute_id(None, None, "STRASSE", 2020)
        assert store.load().to_arrow().column(Col.ID).to_pylist() == [new]
        assert store.backend.external_ids_for(new) == {"openalex": "W7"}
    finally:
        store.close()
    assert _raw(path, "SELECT provider FROM corpus") == [("s2",)]
    assert _raw(path, "SELECT value FROM store_meta") == [("3",)]


def test_migracion_v2_a_v3_es_transaccional(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "lib.duckdb"
    accent = _old_tt("Café", 2020)
    _make_v2_store(path, [_row(accent, "openalex", "Café", seq=1)])

    def boom(self: DuckDBBackend, ids: Any) -> None:
        raise RuntimeError("falla al final de la migración")

    with monkeypatch.context() as m:
        m.setattr(DuckDBBackend, "_sync_curation_across_lanes", boom)
        with pytest.raises(RuntimeError, match="al final"):
            DuckDBBackend(path=path)
    # ROLLBACK: sigue v2 con el id viejo y sin tablas temporales a medias.
    assert _raw(path, "SELECT id FROM corpus") == [(accent,)]
    assert _raw(path, "SELECT value FROM store_meta") == [("2",)]
    assert (
        _raw(
            path,
            "SELECT 1 FROM information_schema.tables WHERE table_name LIKE '%_v3'",
        )
        == []
    )
    # Reintentable.
    DuckDBStore(path, provider=OA).close()
    assert _raw(path, "SELECT value FROM store_meta") == [("3",)]


def test_migracion_10k_filas_con_10pct_tt_es_set_based(tmp_path: Path) -> None:
    """#336: 10k filas, ~10% ``tt:``; se mide y se acota con margen amplio."""
    path = tmp_path / "big.duckdb"
    rows: list[dict[str, Any]] = []
    for i in range(10_000):
        if i % 10 == 0:
            # pares con/sin tildes: ids viejos distintos, misma clave nueva
            n = i // 20
            title = f"Título número {n}" if i % 20 else f"Titulo numero {n}"
            rows.append(_row(_old_tt(title, 2020), "openalex", title, seq=i + 1))
        else:
            rows.append(_row(f"doi:{i:016x}", "openalex", f"Paper {i}", seq=i + 1))
    _make_v2_store(path, rows)

    t0 = time.perf_counter()
    store = DuckDBStore(path, provider=OA)
    elapsed = time.perf_counter() - t0
    try:
        assert len(store.load()) == 9_000 + 500  # 1000 tt -> 500 tras fusionar
    finally:
        store.close()
    print(f"\nmigración v2->v3 10k filas (1000 tt:): {elapsed:.2f}s")
    assert elapsed < 20


# ---------------------------------------------------------------------------
# Compat de snapshot y ejemplo commiteado
# ---------------------------------------------------------------------------


def _write_snapshot(
    snap_dir: Path, rows: list[dict[str, Any]], schema_version: str
) -> None:
    snap_dir.mkdir()
    for r in rows:
        r.pop("_seq", None)
    pq.write_table(  # type: ignore[no-untyped-call]
        pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA),
        str(snap_dir / "corpus.parquet"),
    )
    (snap_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": schema_version,
                "corpus_hash": "x",
                "lib_version": "0",
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )


def test_snapshot_pre_v3_recalcula_tt_al_cargar(tmp_path: Path) -> None:
    accent, plain = _old_tt("Café", 2020), _old_tt("Cafe", 2020)
    rows = [
        _row(accent, "openalex", "Café", seq=1),
        _row(plain, "openalex", "Cafe", seq=2),
        _row("doi:aaaa", "openalex", "Otro", seq=3),
    ]
    _write_snapshot(tmp_path / "s2", [dict(r) for r in rows], "2")
    ids = CorpusSnapshot.load(tmp_path / "s2").corpus.to_arrow().column(Col.ID)
    assert ids.to_pylist() == [CAFE_NEW, "doi:aaaa"]  # fusionó Café/Cafe
    # restore sobre un store ya migrado no duplica el paper.
    assert read_corpus_parquet(tmp_path / "s2" / "corpus.parquet").num_rows == 2


def test_snapshot_v3_no_recalcula(tmp_path: Path) -> None:
    accent = _old_tt("Café", 2020)  # id "viejo" pero declarado v3: se respeta
    _write_snapshot(tmp_path / "s3", [_row(accent, "openalex", "Café", seq=1)], "3")
    table = CorpusSnapshot.load(tmp_path / "s3").corpus.to_arrow()
    assert table.column(Col.ID).to_pylist() == [accent]


def test_ejemplo_valoraciones_hash_no_cambia() -> None:
    """El ejemplo commiteado tiene 0 ids ``tt:``: D3 no altera su hash."""
    raw = pq.read_table(str(_EXAMPLE))  # type: ignore[no-untyped-call]
    assert not [i for i in raw.column("id").to_pylist() if i.startswith("tt:")]
    table = read_corpus_parquet(_EXAMPLE)
    assert Corpus.from_arrow(table)._backend.corpus_hash() == _EXAMPLE_HASH
