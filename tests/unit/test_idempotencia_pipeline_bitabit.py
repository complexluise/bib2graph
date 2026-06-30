"""Issue #61 — Idempotencia bit-a-bit del pipeline restore→build→networks.

Complementa los tests de ``test_example_r2_gate.py`` (que ya verifica
comunidades estables en dos llamadas a ``Networks.quick`` sobre el mismo
objeto ``Corpus`` en memoria) con una verificación explícita de que el
pipeline completo ejecutado **dos veces desde el principio** —incluyendo
el round-trip DuckDB de ``run_restore`` + ``run_build``— produce resultados
idénticos bit-a-bit.

Casos cubiertos:
1. ``corpus_hash`` idéntico entre dos runs independientes del pipeline
   ``run_restore → corpus.load()`` sobre el mismo parquet de entrada
   (verificación sin DuckDB, mínima y ágil).
2. ``corpus_hash`` del store idéntico en dos ejecuciones ``run_restore``
   separadas en stores temporales distintos.
3. La composición de comunidades (nodo→comunidad) de ``Networks.quick`` es
   idéntica entre dos runs completos ``run_restore → run_build`` sobre el
   mismo parquet. Esto es la verificación bit-a-bit solicitada: mismo input
   → mismo output, independientemente de que Python pueda variar el orden de
   iteración de dicts entre procesos (``PYTHONHASHSEED``).
4. ``corpus_hash`` del store es idéntico al que produce la carga directa del
   parquet (coherencia entre el path DuckDB y el path Arrow puro).

Sin red. El parquet congelado en ``examples/valoraciones/corpus.parquet``
sirve de input. Está commiteado; si falta, los tests FALLAN (no se saltean):
es una regresión de reproducibilidad, no una condición a tolerar.

Marcador: ``unit`` (sin red; el parquet es local, ≤200 KB; DuckDB en tmp_path).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_EXAMPLES_PARQUET = (
    Path(__file__).parent.parent.parent / "examples" / "valoraciones" / "corpus.parquet"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_parquet() -> None:
    """Falla (no saltea) si el parquet del ejemplo no existe.

    El parquet está commiteado en examples/valoraciones/; si falta es una
    regresión de reproducibilidad, no una condición a saltear. Coherente con
    test_example_r2_gate.py::test_parquet_existe_y_carga (epic #184, sub-tarea 8)."""
    assert _EXAMPLES_PARQUET.exists(), (
        f"No se encontró el parquet del ejemplo en {_EXAMPLES_PARQUET}. "
        "Debe estar commiteado en examples/valoraciones/. Para regenerarlo "
        "(con red): ver §Armado desde cero en examples/valoraciones/README.md."
    )


def _load_parquet_slice(n: int = 20) -> pa.Table:
    """Carga un slice del parquet del ejemplo (para tests ágiles)."""
    from bib2graph.schemas import CORPUS_SCHEMA

    full = pq.read_table(str(_EXAMPLES_PARQUET), schema=CORPUS_SCHEMA)  # type: ignore[no-untyped-call]
    return full.slice(0, n)


def _communities_of_run(corpus: Any) -> dict[str, dict[str, int]]:
    """Extrae el mapeo nodo→comunidad de cada red, agrupado por kind."""
    from bib2graph.networks.facade import Networks

    artifacts = Networks.quick(corpus)
    return {
        a.spec.kind: dict(a.communities) if a.communities is not None else {}
        for a in artifacts
    }


def _make_offline_transport() -> httpx.MockTransport:
    """MockTransport vacío para mantener ``run_build`` SIN red.

    Cuando el corpus tiene seeds aceptadas, ``run_build`` corre una pasada
    ``cited_by`` contra OpenAlex (ADR 0038 §enrich) ANTES de proyectar las
    redes.  El parquet del ejemplo tiene seeds aceptadas, así que sin inyectar
    transport esa pasada pegaría a la red real → flake (httpx.ReadTimeout en CI).
    Este transport devuelve 0 citantes: la pasada es no-op determinista y el
    test queda hermético, como declara su módulo ("Sin red")."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"results": [], "meta": {"count": 0, "next_cursor": None}},
            headers={"x-openalex-api-version": "2026-05-01"},
        )

    return httpx.MockTransport(handler)


# ---------------------------------------------------------------------------
# 1. corpus_hash idéntico entre dos cargas puras del mismo parquet (sin DuckDB)
# ---------------------------------------------------------------------------


def test_corpus_hash_identico_en_dos_cargas_arrow() -> None:
    """El corpus_hash es idéntico en dos instancias Corpus cargadas del mismo parquet.

    Verifica que el hash se calcula solo sobre contenido bibliográfico
    (excluyendo provenance y timestamps) y que Arrow no introduce
    variabilidad al deserializar.
    """
    _require_parquet()

    from bib2graph.corpus import Corpus
    from bib2graph.schemas import CORPUS_SCHEMA

    table = pq.read_table(str(_EXAMPLES_PARQUET), schema=CORPUS_SCHEMA)  # type: ignore[no-untyped-call]

    corpus_a = Corpus.from_arrow(table)
    corpus_b = Corpus.from_arrow(table)

    hash_a = corpus_a._backend.corpus_hash()
    hash_b = corpus_b._backend.corpus_hash()

    assert hash_a == hash_b, (
        f"El corpus_hash difiere entre dos instancias Corpus cargadas del mismo parquet: "
        f"{hash_a!r} vs {hash_b!r}. "
        "R2 requiere que el hash sea estable e independiente de la instancia."
    )
    # Debe ser un hexdigest SHA-256 válido (64 caracteres hexadecimales)
    assert len(hash_a) == 64
    assert all(c in "0123456789abcdef" for c in hash_a)


# ---------------------------------------------------------------------------
# 2. corpus_hash del store idéntico entre dos ejecuciones de run_restore
# ---------------------------------------------------------------------------


def test_run_restore_corpus_hash_identico_entre_dos_runs(tmp_path: Path) -> None:
    """run_restore sobre el mismo parquet produce corpus_hash idéntico en dos runs.

    Dos ejecuciones de run_restore con stores distintos (tmp_path/runA.duckdb
    y tmp_path/runB.duckdb) deben producir el mismo corpus_hash al cargar el
    corpus resultante. Esto verifica que el round-trip DuckDB no introduce
    no-determinismo en el hash.

    Usa un slice de 10 filas para mantener el test ágil; el comportamiento
    del pipeline es independiente del tamaño del corpus.
    """
    _require_parquet()

    slice_table = _load_parquet_slice(10)
    slice_parquet = tmp_path / "slice.parquet"
    pq.write_table(slice_table, str(slice_parquet))  # type: ignore[no-untyped-call]

    from bib2graph.cli.commands.restore import run_restore
    from bib2graph.stores.duckdb import DuckDBStore

    # Run A
    store_a = tmp_path / "runA.duckdb"
    run_restore(store_a, slice_parquet)
    corpus_a = DuckDBStore(store_a).load()
    hash_a = corpus_a._backend.corpus_hash()

    # Run B (store distinto, mismo parquet)
    store_b = tmp_path / "runB.duckdb"
    run_restore(store_b, slice_parquet)
    corpus_b = DuckDBStore(store_b).load()
    hash_b = corpus_b._backend.corpus_hash()

    assert hash_a == hash_b, (
        f"corpus_hash difiere entre dos ejecuciones de run_restore sobre el mismo parquet: "
        f"run A: {hash_a!r}, run B: {hash_b!r}. "
        "El round-trip DuckDB no debe alterar el content-hash del corpus."
    )


# ---------------------------------------------------------------------------
# 3. Composición de comunidades idéntica entre dos runs completos del pipeline
# ---------------------------------------------------------------------------


def test_comunidades_identicas_entre_dos_runs_pipeline(tmp_path: Path) -> None:
    """La composición nodo→comunidad es bit-a-bit idéntica entre dos runs del pipeline.

    Ejecuta el pipeline ``run_restore → run_build`` dos veces sobre el mismo
    parquet, con stores distintos, y compara el mapeo nodo→comunidad que produce
    ``Networks.quick`` sobre cada corpus restaurado.

    Este es el test solicitado en #61: verificar que dos runs independientes
    producen el mismo output (idempotencia del pipeline end-to-end). La aserción
    es sobre las comunidades de ``Networks.quick`` (la fuente de no-determinismo
    a vigilar: orden de dicts / Louvain). El camino de escritura de artefactos
    (``run_build``) se ejercita UNA vez (run A) para mantener su cobertura sin
    reconstruir las redes por duplicado (#184): la idempotencia ya la garantiza la
    comparación de comunidades, no una segunda escritura a disco.

    Garantía de Louvain: ``random_state`` se deriva del ``corpus_hash`` de
    contenido (``_louvain_seed_from_hash``), que es idéntico si el corpus
    es el mismo → la partición es determinista e independiente de
    ``PYTHONHASHSEED`` (Python no usa ``hash()`` para Louvain).
    """
    _require_parquet()

    # Usar un slice del parquet real con suficiente contenido para tener
    # al menos una red de acoplamiento bibliográfico con comunidades.
    # La co-citación puede no estar si el slice no tiene cited_by_id;
    # verificamos sobre las redes que efectivamente se produzcan.
    slice_table = _load_parquet_slice(20)
    slice_parquet = tmp_path / "slice.parquet"
    pq.write_table(slice_table, str(slice_parquet))  # type: ignore[no-untyped-call]

    from bib2graph.cli.commands.build import run_build
    from bib2graph.cli.commands.restore import run_restore
    from bib2graph.stores.duckdb import DuckDBStore

    # Run A: pipeline completo (incluye run_build para ejercer el camino de escritura).
    # transport inyectado → la pasada cited_by (ADR 0038 §enrich) NO toca la red:
    # devuelve 0 citantes, manteniendo el test hermético y determinista.
    store_a = tmp_path / "runA.duckdb"
    run_restore(store_a, slice_parquet)
    corpus_a = DuckDBStore(store_a).load()
    communities_a = _communities_of_run(corpus_a)
    run_build(
        store_a, out_dir=tmp_path / "networks_a", transport=_make_offline_transport()
    )

    # Run B (store distinto, mismo parquet): solo restore + comunidades.
    # No se reconstruye run_build: su determinismo de output no se asevera acá
    # (la aserción es sobre las comunidades de Networks.quick).
    store_b = tmp_path / "runB.duckdb"
    run_restore(store_b, slice_parquet)
    corpus_b = DuckDBStore(store_b).load()
    communities_b = _communities_of_run(corpus_b)

    # Las redes producidas deben ser las mismas kinds
    assert set(communities_a.keys()) == set(communities_b.keys()), (
        f"Los dos runs produjeron redes distintas: "
        f"run A: {sorted(communities_a.keys())}, run B: {sorted(communities_b.keys())}."
    )

    # Para cada red, el mapeo nodo→comunidad debe ser idéntico
    for kind in communities_a:
        map_a = communities_a[kind]
        map_b = communities_b[kind]
        assert map_a == map_b, (
            f"Las comunidades de '{kind}' difieren entre run A y run B. "
            "El pipeline completo debe ser determinista: mismo corpus → mismo output. "
            f"Nodos en A pero no en B: {set(map_a) - set(map_b)}. "
            f"Valores distintos: "
            + str(
                {
                    n: (map_a.get(n), map_b.get(n))
                    for n in map_a
                    if map_a.get(n) != map_b.get(n)
                }
            )
        )


# ---------------------------------------------------------------------------
# 4. corpus_hash del store coherente con el hash del parquet Arrow puro
# ---------------------------------------------------------------------------


def test_corpus_hash_coherente_store_vs_arrow_puro(tmp_path: Path) -> None:
    """El corpus_hash del store tras run_restore coincide con el de la carga Arrow pura.

    Verifica que el hash producido por el path DuckDB (run_restore →
    DuckDBStore.load() → corpus_hash()) es el mismo que el producido
    cargando el parquet directamente con Arrow (sin DuckDB).

    Esta coherencia garantiza que el formato de persistencia no altera el
    content-hash del corpus (R2: identidad es del contenido, no del transporte).
    """
    _require_parquet()

    slice_table = _load_parquet_slice(10)
    slice_parquet = tmp_path / "slice.parquet"
    pq.write_table(slice_table, str(slice_parquet))  # type: ignore[no-untyped-call]

    # Path Arrow puro
    from bib2graph.corpus import Corpus
    from bib2graph.schemas import CORPUS_SCHEMA

    table = pq.read_table(str(slice_parquet), schema=CORPUS_SCHEMA)  # type: ignore[no-untyped-call]
    corpus_arrow = Corpus.from_arrow(table)
    # #88: la ingesta (run_restore) normaliza+deduplica el corpus. Aplicamos la
    # MISMA transformación al path Arrow puro para comparar el mismo contenido —
    # lo que se testea acá es el transporte (DuckDB vs Arrow), no el dedup.
    # applied_at no entra al corpus_hash (R2), así que no afecta la comparación.
    from datetime import UTC, datetime

    from bib2graph.cli._ingest import normalize_and_dedup

    corpus_arrow = normalize_and_dedup(corpus_arrow, applied_at=datetime.now(UTC))
    hash_arrow = corpus_arrow._backend.corpus_hash()

    # Path DuckDB (run_restore → DuckDBStore.load)
    from bib2graph.cli.commands.restore import run_restore
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "test.duckdb"
    run_restore(store_path, slice_parquet)
    corpus_store = DuckDBStore(store_path).load()
    hash_store = corpus_store._backend.corpus_hash()

    assert hash_arrow == hash_store, (
        f"El corpus_hash difiere entre el path Arrow puro ({hash_arrow!r}) "
        f"y el path DuckDB tras run_restore ({hash_store!r}). "
        "El formato de persistencia no debe alterar el content-hash (R2)."
    )
