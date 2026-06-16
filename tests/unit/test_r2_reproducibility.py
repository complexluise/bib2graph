"""Tests R2 — Reproducibilidad / identidad: content-hash vs procedencia + Louvain seeded.

Verifica los tres contratos del Hito R2 (ADR 0017 enmendado):

1. **Headline:** ``corpus_hash`` es ESTABLE ante timestamps de curación distintos.
   Aceptar los mismos papers "en dos instantes" → mismo hash.
2. **Louvain reproducible:** mismo corpus + spec → partición idéntica en dos corridas.
3. **Reloj inyectado:** el núcleo no llama ``datetime.now()``; el evento lleva el
   ``decided_at`` inyectado desde afuera.

Disciplina de tests del repo: solo lo que tiene lógica o riesgo de regresión.
Marcador: ``unit`` (sin red, sin I/O).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import networkx as nx
import pyarrow as pa
import pytest

from bib2graph.backends.memory import _apply_curation_to_rows, compute_corpus_hash
from bib2graph.corpus import Corpus
from bib2graph.filters.prisma import FilterCriterion, apply_filters
from bib2graph.networks.analyzer import detect_communities
from bib2graph.networks.facade import Networks, _louvain_seed_from_hash
from bib2graph.schemas import CORPUS_SCHEMA

# ---------------------------------------------------------------------------
# Helpers — datos sintéticos mínimos
# ---------------------------------------------------------------------------


def _make_row(
    *,
    id: str,
    title: str = "Paper de prueba",
    curation_status: str = "candidate",
    provenance: str | None = None,
) -> dict[str, object]:
    """Fila mínima con todos los campos del schema."""
    return {
        "id": id,
        "openalex_id": None,
        "doi": None,
        "title": title,
        "year": 2020,
        "abstract": None,
        "source": None,
        "language": None,
        "publisher": None,
        "research_areas": None,
        "is_seed": True,
        "curation_status": curation_status,
        "provenance": provenance,
        "authors_raw": None,
        "authors_id": None,
        "authors_affiliations": None,
        "keywords_raw": None,
        "keywords_id": None,
        "institutions_raw": None,
        "institutions_id": None,
        "references_id": None,
        "references_doi": None,
        "cited_by_id": None,
    }


def _make_table(rows: list[dict[str, object]]) -> pa.Table:
    return pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)


def _make_corpus(*ids: str) -> Corpus:
    """Corpus mínimo con los ids dados como papers candidatos."""
    rows = [_make_row(id=id_, title=f"Paper {id_}") for id_ in ids]
    return Corpus.from_arrow(_make_table(rows))


# ---------------------------------------------------------------------------
# 1. Headline: corpus_hash estable ante timestamps de curación distintos
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_corpus_hash_estable_ante_timestamps_distintos() -> None:
    """HEADLINE R2: aceptar los mismos papers en dos instantes → mismo corpus_hash.

    Antes de R2, el hash incluía provenance (con datetime.now()), así que
    dos llamadas a corpus.accept([id]) producían hashes distintos.
    Tras R2, el hash se computa SOLO sobre contenido bibliográfico (excluye
    provenance), de modo que el resultado es idéntico independientemente de
    cuándo se tomó la decisión.
    """
    corpus = _make_corpus("oa:aabbccdd11223344", "oa:bbccdd1122334455")
    paper_id = "oa:aabbccdd11223344"

    # "Instante 1": aceptar con timestamp fijo T1
    t1 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
    curado_t1 = corpus.accept([paper_id], by="human", decided_at=t1)

    # "Instante 2": aceptar con timestamp distinto T2 (1 hora después)
    t2 = t1 + timedelta(hours=1)
    curado_t2 = corpus.accept([paper_id], by="human", decided_at=t2)

    hash_t1 = curado_t1._backend.corpus_hash()
    hash_t2 = curado_t2._backend.corpus_hash()

    assert hash_t1 == hash_t2, (
        f"El corpus_hash difiere entre t1={t1} y t2={t2}: "
        f"{hash_t1!r} vs {hash_t2!r}. "
        "R2 requiere que el hash sea independiente de los timestamps de curación."
    )


@pytest.mark.unit
def test_corpus_hash_excluye_provenance_pero_incluye_curation_status() -> None:
    """El hash cambia si cambia curation_status (contenido), pero NO por provenance.

    Verifica que la exclusión de provenance no "ciega" el hash a cambios
    semánticos reales: dos papers con el mismo id pero distinto curation_status
    deben tener hashes distintos.
    """
    corpus = _make_corpus("oa:aabbccdd11223344")
    paper_id = "oa:aabbccdd11223344"

    t1 = datetime(2026, 1, 1, tzinfo=UTC)
    curado = corpus.accept([paper_id], decided_at=t1)

    hash_sin_curar = corpus._backend.corpus_hash()
    hash_curado = curado._backend.corpus_hash()

    # Distinto curation_status → distinto hash
    assert hash_sin_curar != hash_curado


@pytest.mark.unit
def test_corpus_hash_solo_contenido_bibliografico() -> None:
    """compute_corpus_hash excluye la columna provenance del hash.

    Dos tablas con el mismo contenido bibliográfico pero distinto provenance
    deben producir el mismo hash.  Verifica la implementación de bajo nivel.
    """
    row_sin_prov = _make_row(id="oa:test00000000", provenance=None)
    row_con_prov = _make_row(
        id="oa:test00000000",
        provenance=json.dumps(
            [
                {
                    "action": "accepted",
                    "equation_id": None,
                    "chaining_hop": None,
                    "source": None,
                    "fetched_at": None,
                    "decided_by": "human",
                    "decided_at": "2026-01-01T00:00:00+00:00",
                }
            ]
        ),
    )
    table_sin = _make_table([row_sin_prov])
    table_con = _make_table([row_con_prov])

    assert compute_corpus_hash(table_sin) == compute_corpus_hash(table_con), (
        "compute_corpus_hash debe ser idéntico para el mismo contenido "
        "independientemente del valor de la columna provenance."
    )


# ---------------------------------------------------------------------------
# 2. Reloj inyectado: el evento lleva el decided_at inyectado
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_decided_at_inyectado_aparece_en_evento() -> None:
    """El evento de curación lleva el decided_at inyectado, no un datetime.now().

    Verifica que cuando se pasa decided_at explícito a corpus.accept(),
    el evento en provenance refleja ese timestamp exacto.
    """
    corpus = _make_corpus("oa:aabbccdd11223344")
    paper_id = "oa:aabbccdd11223344"

    fixed_at = datetime(2026, 3, 15, 12, 30, 0, tzinfo=UTC)
    curado = corpus.accept([paper_id], by="agente", decided_at=fixed_at)

    row = curado.to_arrow().to_pylist()[0]
    events = json.loads(row["provenance"])
    assert len(events) == 1
    event = events[0]

    assert event["action"] == "accepted"
    assert event["decided_by"] == "agente"
    # El decided_at debe ser el timestamp inyectado, serializado como ISO8601
    assert fixed_at.isoformat() in event["decided_at"] or event["decided_at"].startswith(
        "2026-03-15T12:30:00"
    ), (
        f"decided_at esperado '2026-03-15T12:30:00+00:00', "
        f"se obtuvo '{event['decided_at']}'"
    )


@pytest.mark.unit
def test_decided_at_distintos_producen_timestamps_distintos_en_provenance() -> None:
    """Dos aceptaciones con decided_at distintos → eventos con timestamps distintos.

    Confirma que el timestamp inyectado se registra fielmente en el log
    de procedencia (la procedencia refleja el *cuándo* real).
    """
    corpus = _make_corpus("oa:aabbccdd11223344")
    paper_id = "oa:aabbccdd11223344"

    t1 = datetime(2026, 1, 1, tzinfo=UTC)
    t2 = datetime(2026, 6, 15, tzinfo=UTC)

    curado_t1 = corpus.accept([paper_id], decided_at=t1)
    curado_t2 = corpus.accept([paper_id], decided_at=t2)

    events_t1 = json.loads(curado_t1.to_arrow().to_pylist()[0]["provenance"])
    events_t2 = json.loads(curado_t2.to_arrow().to_pylist()[0]["provenance"])

    # Timestamps distintos en el log
    assert events_t1[0]["decided_at"] != events_t2[0]["decided_at"]
    # Pero hash idéntico (la identidad no depende del cuándo)
    assert curado_t1._backend.corpus_hash() == curado_t2._backend.corpus_hash()


@pytest.mark.unit
def test_nucleo_sin_decided_at_usa_fallback() -> None:
    """Sin decided_at inyectado, el backend usa datetime.now(UTC) como fallback.

    Verifica que el uso como librería (sin pasar decided_at) sigue funcionando:
    el evento de curación tiene un decided_at no-None.
    """
    corpus = _make_corpus("oa:aabbccdd11223344")
    paper_id = "oa:aabbccdd11223344"

    # Sin pasar decided_at (uso como librería)
    curado = corpus.accept([paper_id])
    row = curado.to_arrow().to_pylist()[0]
    events = json.loads(row["provenance"])
    assert events[0]["decided_at"] is not None


@pytest.mark.unit
def test_apply_curation_to_rows_con_decided_at_fijo() -> None:
    """_apply_curation_to_rows registra el decided_at inyectado en el evento.

    Test de bajo nivel: verifica el helper directamente con un timestamp fijo.
    """
    rows = [_make_row(id="oa:test11111111")]
    fixed_at = "2026-05-01T00:00:00+00:00"

    updated = _apply_curation_to_rows(
        rows, ["oa:test11111111"], "accepted", "test_user", fixed_at
    )

    events = json.loads(updated[0]["provenance"])
    assert events[0]["decided_at"] == fixed_at


# ---------------------------------------------------------------------------
# 2b. Reloj inyectado vía apply_filters (path de curación filter)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_apply_filters_decided_at_inyectado_aparece_en_evento() -> None:
    """apply_filters inyecta decided_at en cada evento de rechazo del filtrado.

    Verifica que cuando se pasa decided_at explícito a apply_filters(), el
    evento en provenance de los papers rechazados refleja ese timestamp exacto
    (no un datetime.now() del núcleo).  Cubre el gap R2 del path de curación
    vía ``b2g filter``.
    """
    corpus = _make_corpus("oa:aabbccdd11223344", "oa:bbccdd1122334455")

    # Dos papers con distintos años: el de 2015 será rechazado
    rows = [
        {**_make_row(id="oa:aabbccdd11223344"), "year": 2015},
        {**_make_row(id="oa:bbccdd1122334455"), "year": 2022},
    ]
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)

    fixed_at = datetime(2026, 4, 10, 9, 0, 0, tzinfo=UTC)
    criteria = [FilterCriterion(field="year", op="gte", value=2018)]

    final_corpus, steps = apply_filters(corpus, criteria, decided_at=fixed_at)

    assert len(steps) == 1
    assert steps[0].count_before == 2
    assert steps[0].count_after == 1  # solo el de 2022 pasa

    all_rows = final_corpus.to_arrow().to_pylist()
    rejected_row = next(r for r in all_rows if r["id"] == "oa:aabbccdd11223344")
    assert rejected_row["curation_status"] == "rejected"

    events = json.loads(rejected_row["provenance"])
    assert len(events) == 1
    event = events[0]
    assert event["action"] == "rejected"
    # El decided_at debe ser el timestamp inyectado, NO un datetime.now()
    assert event["decided_at"] is not None
    assert event["decided_at"].startswith("2026-04-10T09:00:00"), (
        f"decided_at esperado '2026-04-10T09:00:00+00:00', "
        f"se obtuvo '{event['decided_at']}'. "
        "R2 requiere que apply_filters inyecte el decided_at desde la frontera."
    )


@pytest.mark.unit
def test_apply_filters_sin_decided_at_usa_fallback() -> None:
    """Sin decided_at, apply_filters delega en el fallback del núcleo (datetime.now).

    Verifica la ergonomía de librería: llamar a apply_filters sin decided_at
    sigue funcionando; el evento de curación tiene un decided_at no-None
    (generado por el fallback del backend).
    """
    rows = [
        {**_make_row(id="oa:aabbccdd11223344"), "year": 2010},
    ]
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)

    criteria = [FilterCriterion(field="year", op="gte", value=2020)]
    final_corpus, _ = apply_filters(corpus, criteria)  # sin decided_at

    all_rows = final_corpus.to_arrow().to_pylist()
    rejected_row = all_rows[0]
    assert rejected_row["curation_status"] == "rejected"

    events = json.loads(rejected_row["provenance"])
    assert events[0]["decided_at"] is not None


# ---------------------------------------------------------------------------
# 3. Louvain reproducible: mismo corpus + spec → misma partición
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_louvain_reproducible_misma_particion_dos_corridas() -> None:
    """detect_communities(method='louvain', random_state=N) → misma partición.

    Verifica que el mismo random_state produce exactamente la misma partición
    de comunidades en dos llamadas consecutivas sobre el mismo grafo.
    """
    g = nx.karate_club_graph()  # grafo clásico para pruebas de comunidades
    seed = 42

    particion_1 = detect_communities(g, method="louvain", random_state=seed)
    particion_2 = detect_communities(g, method="louvain", random_state=seed)

    assert particion_1 == particion_2, (
        "Louvain con el mismo random_state debe producir la misma partición "
        "en dos corridas (R2: reproducibilidad garantizada)."
    )


@pytest.mark.unit
def test_louvain_seed_derivado_de_corpus_hash() -> None:
    """_louvain_seed_from_hash produce un entero en el rango correcto.

    Verifica que la función de derivación del seed es determinista y
    produce un valor en [0, 2^31 - 1] (rango aceptado por python-louvain).
    """
    corpus_hash = "a1b2c3d4e5f60789abcdef1234567890abcdef1234567890abcdef1234567890"
    seed = _louvain_seed_from_hash(corpus_hash)

    assert isinstance(seed, int)
    assert 0 <= seed < 2**31

    # Determinista: mismo hash → mismo seed
    assert _louvain_seed_from_hash(corpus_hash) == seed

    # Hashes distintos → seeds (probablemente) distintos (no hay colisión forzada)
    otro_hash = "ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00"
    assert _louvain_seed_from_hash(otro_hash) != seed


@pytest.mark.unit
def test_networks_build_louvain_reproducible() -> None:
    """Networks.build con spec.clustering='louvain' produce partición reproducible.

    Integra _louvain_seed_from_hash y detect_communities a través de facade.py:
    mismo corpus → mismo corpus_hash → mismo random_state → misma partición.
    """
    from bib2graph.networks.spec import NetworkSpec

    # Corpus con papers que comparten referencias (genera acoplamiento bibliográfico)
    rows = [
        {
            **_make_row(id=f"oa:paper{i:08d}", title=f"Paper {i}"),
            "references_id": ["oa:ref00000001", "oa:ref00000002"],
        }
        for i in range(1, 6)
    ]
    corpus = Corpus.from_arrow(_make_table(rows))

    spec = NetworkSpec(kind="bibliographic_coupling", clustering="louvain")

    artifact_1 = Networks.build(corpus, spec)
    artifact_2 = Networks.build(corpus, spec)

    assert artifact_1.communities == artifact_2.communities, (
        "Networks.build con el mismo corpus y spec debe producir las mismas "
        "comunidades en dos corridas (R2: Louvain seeded con corpus_hash)."
    )


@pytest.mark.unit
def test_louvain_seed_cambia_si_cambia_corpus() -> None:
    """Corpus distintos producen random_state distintos para Louvain.

    Verifica que la derivación del seed captura correctamente las diferencias
    de contenido entre corpus: dos corpus con contenido distinto producen
    seeds distintos (y por lo tanto, potencialmente particiones distintas).
    """
    corpus_a = _make_corpus("oa:paper00000001")
    corpus_b = _make_corpus("oa:paper00000002")

    hash_a = corpus_a._backend.corpus_hash()
    hash_b = corpus_b._backend.corpus_hash()

    seed_a = _louvain_seed_from_hash(hash_a)
    seed_b = _louvain_seed_from_hash(hash_b)

    # Corpus distintos → hashes distintos → seeds distintos
    assert hash_a != hash_b
    assert seed_a != seed_b
