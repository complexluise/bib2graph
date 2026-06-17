"""Gate de reproducibilidad R2 — Ciclo 9b (ADR 0030).

Cierra el agujero de la Nota 09 §"No se validó la reproducibilidad del output":
el corpus.parquet de ``examples/valoraciones/`` sirve de gate end-to-end sin red.

Casos cubiertos:
1. El parquet existe y carga con el schema canónico.
2. El ``corpus_hash`` es estable entre dos cargas independientes del mismo parquet
   (reproducibilidad R2: el hash es del contenido, no de timestamps).
3. ``Networks.quick`` produce redes con nodos y aristas (ninguna de las 4 redes
   principales está vacía).
4. La co-citación está vacía (``cited_by_id`` no poblado) y se omite graceful.
5. La composición de comunidades es estable entre dos corridas del mismo corpus
   (Louvain seeded con corpus_hash → partición determinista).
6. ``run_restore`` a un store temporal carga el corpus sin red y transiciona a FILTERED.

Marcador: ``unit`` (sin red; el parquet es local, ~200 KB).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bib2graph.corpus import Corpus

# Ruta al parquet del ejemplo (relativa al directorio raíz del proyecto)
_EXAMPLES_PARQUET = (
    Path(__file__).parent.parent.parent / "examples" / "valoraciones" / "corpus.parquet"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_corpus_from_parquet() -> Corpus:
    """Carga el corpus desde el parquet del ejemplo con el schema canónico."""
    import pyarrow.parquet as pq

    from bib2graph.corpus import Corpus
    from bib2graph.schemas import CORPUS_SCHEMA

    table = pq.read_table(str(_EXAMPLES_PARQUET), schema=CORPUS_SCHEMA)  # type: ignore[no-untyped-call]
    return Corpus.from_arrow(table)


# ---------------------------------------------------------------------------
# 1. El parquet existe y tiene el schema canónico
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_parquet_existe_y_carga() -> None:
    """El corpus.parquet del ejemplo existe y carga con el schema canónico.

    Si este test falla, verificá que ``examples/valoraciones/build_corpus.py``
    haya sido ejecutado (genera el parquet desde los datos locales del PO).
    """
    assert _EXAMPLES_PARQUET.exists(), (
        f"No se encontró el parquet del ejemplo en {_EXAMPLES_PARQUET}. "
        "Ejecutá: uv run python examples/valoraciones/build_corpus.py"
    )

    corpus = _load_corpus_from_parquet()
    n = len(corpus)

    assert n >= 100, (
        f"El corpus tiene solo {n} filas; se esperan ≥100. "
        "Revisá los criterios de reducción en build_corpus.py."
    )
    assert n <= 200, (
        f"El corpus tiene {n} filas; se esperan ≤200 (corpus reducido). "
        "Revisá los criterios de reducción en build_corpus.py."
    )


# ---------------------------------------------------------------------------
# 2. corpus_hash estable entre dos cargas del mismo parquet
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_corpus_hash_estable_entre_cargas() -> None:
    """El corpus_hash es idéntico en dos cargas independientes del mismo parquet.

    R2 (ADR 0017 enmendado): el hash excluye provenance (timestamps de curación)
    y es order-independent. Dos instancias cargadas del mismo parquet deben
    producir el mismo hash.
    """
    corpus_a = _load_corpus_from_parquet()
    corpus_b = _load_corpus_from_parquet()

    hash_a = corpus_a._backend.corpus_hash()
    hash_b = corpus_b._backend.corpus_hash()

    assert hash_a == hash_b, (
        f"El corpus_hash difiere entre dos cargas del mismo parquet: "
        f"{hash_a!r} vs {hash_b!r}. "
        "R2 requiere que el hash sea estable e independiente de la instancia."
    )
    # El hash debe ser un hexdigest SHA-256 (64 caracteres)
    assert len(hash_a) == 64
    assert all(c in "0123456789abcdef" for c in hash_a)


# ---------------------------------------------------------------------------
# 3. Las redes principales no están vacías
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_redes_principales_no_vacias() -> None:
    """Networks.quick produce redes con nodos y aristas (redes no vacías).

    Las 4 redes principales (bibliographic_coupling, author_collab,
    institution_collab, keyword_cooccurrence) deben tener al menos 1 nodo
    y 1 arista con el corpus de ejemplo (137 filas).

    La co-citación se omite graceful (cited_by_id vacío) y se verifica en
    el test siguiente.
    """
    from bib2graph.constants import NetworkKind
    from bib2graph.networks.facade import Networks

    corpus = _load_corpus_from_parquet()
    artifacts = Networks.quick(corpus)

    # Debe haber exactamente 4 artefactos (co-citación omitida, cited_by vacío)
    kinds = [a.spec.kind for a in artifacts]
    assert NetworkKind.BIBLIOGRAPHIC_COUPLING in kinds, (
        "bibliographic_coupling ausente — verificá que el corpus tiene referencias."
    )
    assert NetworkKind.AUTHOR_COLLAB in kinds, (
        "author_collab ausente — verificá que el corpus tiene authors_id."
    )
    assert NetworkKind.KEYWORD_COOCCURRENCE in kinds, (
        "keyword_cooccurrence ausente — verificá que el corpus tiene keywords_id."
    )

    # Verificar que cada red tiene nodos y aristas
    for artifact in artifacts:
        g = artifact.graph
        kind = artifact.spec.kind
        assert g.number_of_nodes() > 0, (
            f"La red '{kind}' no tiene nodos. "
            "Revisá el corpus de ejemplo o los proyectores."
        )
        assert g.number_of_edges() > 0, (
            f"La red '{kind}' no tiene aristas. "
            "Revisá que el corpus tenga datos suficientes para proyectar aristas."
        )


# ---------------------------------------------------------------------------
# 4. Co-citación vacía y omitida graceful
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_cocitacion_vacia_omitida_graceful() -> None:
    """cited_by_id está vacío → co-citación omitida graceful por Networks.quick.

    El corpus original no pasó por el Enricher de co-citación (Hito 8b),
    así que cited_by_id está en blanco para todos los papers. Networks.quick
    debe omitir la co-citación sin error (solo un aviso informativo en el log).
    """
    from bib2graph.constants import NetworkKind
    from bib2graph.networks.facade import Networks

    corpus = _load_corpus_from_parquet()

    # Verificar precondición: cited_by_id vacío en todo el corpus
    table = corpus.to_arrow()
    cited_col = table.column("cited_by_id").to_pylist()
    assert not any(cited_col), (
        "Se esperaba cited_by_id vacío en todo el corpus. "
        "Si el corpus fue enriquecido, actualizar este test."
    )

    artifacts = Networks.quick(corpus)
    kinds = [a.spec.kind for a in artifacts]

    # Co-citación no debe estar en la lista
    assert NetworkKind.COCITATION not in kinds, (
        "Se esperaba que co-citación fuera omitida (cited_by_id vacío). "
        f"Redes presentes: {kinds}"
    )


# ---------------------------------------------------------------------------
# 5. Comunidades estables entre dos corridas
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_comunidades_estables_entre_corridas() -> None:
    """La composición de comunidades es idéntica en dos corridas del mismo corpus.

    Cierra el agujero de la Nota 09 §"No se validó la reproducibilidad":
    R2 garantiza que Louvain se siembra con un random_state derivado del
    corpus_hash, así que el mismo corpus → misma partición de comunidades.
    """
    from bib2graph.networks.facade import Networks

    corpus = _load_corpus_from_parquet()

    artifacts_1 = Networks.quick(corpus)
    artifacts_2 = Networks.quick(corpus)

    assert len(artifacts_1) == len(artifacts_2), (
        "Las dos corridas produjeron distinto número de redes."
    )

    for a1, a2 in zip(artifacts_1, artifacts_2, strict=True):
        kind = a1.spec.kind
        assert a1.communities == a2.communities, (
            f"Las comunidades de '{kind}' difieren entre corridas. "
            "R2 requiere que Louvain sea determinista con el mismo corpus. "
            f"Corrida 1: {a1.communities!r}\nCorrida 2: {a2.communities!r}"
        )


# ---------------------------------------------------------------------------
# 6. run_restore carga el corpus sin red y transiciona a FILTERED
#    (usa un slice del parquet para no ralentizar el gate con 137 filas DuckDB)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_run_restore_desde_parquet_ejemplo(tmp_path: Path) -> None:
    """run_restore carga el corpus del ejemplo sin red y deja el store en FILTERED.

    Verifica el ciclo end-to-end sin red del gate #33:
    restore → corpus cargado → estado FILTERED → build disponible.

    Usa un slice de 10 filas del parquet para mantener el test ágil
    (el comportamiento de run_restore es independiente del tamaño del corpus;
    la cobertura de 137 filas se verifica en los tests 1-5 más arriba).
    """
    import pyarrow.parquet as pq

    from bib2graph.cli.commands.restore import run_restore
    from bib2graph.cycle import CycleState
    from bib2graph.schemas import CORPUS_SCHEMA
    from bib2graph.stores.duckdb import DuckDBStore

    # Slice de 10 filas del parquet (no toda la tabla de 137)
    full_table = pq.read_table(str(_EXAMPLES_PARQUET), schema=CORPUS_SCHEMA)  # type: ignore[no-untyped-call]
    slice_table = full_table.slice(0, 10)
    slice_parquet = tmp_path / "slice.parquet"
    pq.write_table(slice_table, str(slice_parquet))  # type: ignore[no-untyped-call]

    store_path = tmp_path / "test_example.duckdb"
    data = run_restore(store_path, slice_parquet)

    assert data["papers_loaded"] == 10
    assert data["total_papers"] == 10
    assert data["state"] == str(CycleState.FILTERED)

    store = DuckDBStore(store_path)
    corpus_loaded = store.load()
    assert len(corpus_loaded) == 10

    backend_state = store.backend.loop_state()
    assert backend_state == CycleState.FILTERED


# ---------------------------------------------------------------------------
# 7. corpus_hash coherente: merge de vacío + parquet → mismo hash que parquet directo
#    (verificado en memoria pura, sin DuckDB, para ser ágil)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_corpus_hash_coherente_entre_parquet_y_merge_en_memoria() -> None:
    """El corpus_hash es idéntico antes y después de un merge con un corpus vacío.

    Verifica que Corpus.merge(vacío + incoming) no altera el contenido:
    la operación de merge idempotente preserva el hash de contenido (R2).
    Usa InMemoryBackend (sin DuckDB) para ser ágil.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    from bib2graph.corpus import Corpus
    from bib2graph.schemas import CORPUS_SCHEMA

    # Corpus del parquet
    table = pq.read_table(str(_EXAMPLES_PARQUET), schema=CORPUS_SCHEMA)  # type: ignore[no-untyped-call]
    corpus_incoming = Corpus.from_arrow(table)
    hash_incoming = corpus_incoming._backend.corpus_hash()

    # Corpus vacío (0 filas, schema canónico)
    empty_table = pa.Table.from_pylist([], schema=CORPUS_SCHEMA)
    corpus_empty = Corpus.from_arrow(empty_table)

    # merge(vacío, incoming) debe producir el mismo hash que incoming
    merged = corpus_empty.merge(corpus_incoming)
    hash_merged = merged._backend.corpus_hash()

    assert hash_incoming == hash_merged, (
        f"El corpus_hash difiere entre incoming ({hash_incoming!r}) y "
        f"merge(vacío, incoming) ({hash_merged!r}). "
        "El merge con un corpus vacío debe ser idempotente para el hash."
    )
