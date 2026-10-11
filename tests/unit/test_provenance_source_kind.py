"""Tests source_kind en ProvenanceEvent (D2, ADR 0050).

Cubre:
- Validación del campo ``source_kind`` (Literal de 4 valores; ``None``).
- Población correcta en los lugares que escriben ``provenance`` (seed,
  fetch_citing, fetch_works_by_ids, OpenAlexSource.load, BibtexSource,
  forager _work_to_row forward, forager fallback, _apply_curation_to_rows).
- ``equation_id`` ya nunca contiene el prefijo ``chaining:`` (los seeds usan
  ``eq-…``, el chaining usa ``None``); ``chaining_hop`` se sigue emitiendo
  no-null para citantes forrajeados (constraint del consumidor programático).
- Migración on-read de corpus viejos con ``chaining:*``: dado un dict/JSON con
  ``equation_id="chaining:forward:…"``, ``migrate_provenance_event`` deriva
  ``source_kind="chaining_forward"`` y pone ``equation_id=None``.
- Idempotencia de la migración sobre un evento ya migrado.
- ``corpus_hash`` intacto ante la presencia/ausencia de ``source_kind`` (R2,
  ADR 0017: el hash excluye ``provenance``, así que es trivialmente estable).

Disciplina de tests del repo: solo donde hay lógica o riesgo de regresión.
Marcador: ``unit`` (sin red ni I/O).
"""

from __future__ import annotations

import json

import pyarrow as pa
import pytest
from pydantic import ValidationError

from bib2graph.backends._provenance_compat import migrate_provenance_event
from bib2graph.backends.memory import (
    _apply_curation_to_rows,
    compute_corpus_hash,
)
from bib2graph.constants import Col, CurationStatus
from bib2graph.corpus import Corpus
from bib2graph.schemas import CORPUS_SCHEMA, ProvenanceEvent

# ---------------------------------------------------------------------------
# 1. Validación del campo source_kind en el modelo
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_source_kind_default_none() -> None:
    """``source_kind`` default ``None`` para retrocompat con corpus viejos."""
    event = ProvenanceEvent(
        action="fetched",
        equation_id="eq-20260101T000000",
        chaining_hop=None,
        source="openalex",
        fetched_at="2026-01-01T00:00:00+00:00",
        decided_by=None,
        decided_at=None,
    )
    assert event.source_kind is None


@pytest.mark.unit
@pytest.mark.parametrize(
    "value",
    ["seed_equation", "chaining_forward", "chaining_backward"],
)
def test_source_kind_acepta_valores_del_enum(value: str) -> None:
    """Cada uno de los 3 valores válidos del Literal se acepta sin error."""
    event = ProvenanceEvent(
        action="fetched",
        equation_id=None,
        chaining_hop=1 if "chaining" in value else None,
        source="openalex",
        fetched_at="2026-01-01T00:00:00+00:00",
        decided_by=None,
        decided_at=None,
        source_kind=value,
    )
    assert event.source_kind == value


@pytest.mark.unit
def test_source_kind_rechaza_valor_fuera_del_enum() -> None:
    """Cualquier valor fuera del Literal falla ruidoso (Pydantic ValidationError)."""
    with pytest.raises(ValidationError, match="source_kind"):
        ProvenanceEvent(
            action="fetched",
            equation_id=None,
            chaining_hop=None,
            source="openalex",
            fetched_at="2026-01-01T00:00:00+00:00",
            decided_by=None,
            decided_at=None,
            source_kind="seed_inventado",
        )


@pytest.mark.unit
def test_source_kind_none_explicito_es_valido() -> None:
    """``None`` explícito también es válido (corpus viejos)."""
    event = ProvenanceEvent(
        action="loaded",
        equation_id="load",
        chaining_hop=None,
        source="openalex",
        fetched_at="2026-01-01T00:00:00+00:00",
        decided_by=None,
        decided_at=None,
        source_kind=None,
    )
    assert event.source_kind is None


# ---------------------------------------------------------------------------
# 2. Lugares que pueblan provenance — equation_id ya no contiene "chaining:"
# ---------------------------------------------------------------------------


def _make_minimal_work_dict(
    *, openalex_id: str = "W123", doi: str | None = "10.1234/example"
) -> dict[str, object]:
    """OpenAlex work mínimo válido para _work_to_row."""
    return {
        "id": f"https://openalex.org/{openalex_id}",
        "doi": f"https://doi.org/{doi}" if doi else None,
        "title": "Paper ejemplo",
        "publication_year": 2024,
        "language": "en",
        "abstract_inverted_index": {"hello": [0]},
        "authorships": [],
        "keywords": [],
        "referenced_works": [],
        "primary_location": {"source": {"display_name": "Journal X"}},
        "type": "article",
    }


@pytest.mark.unit
def test_work_to_row_seed_source_kind_seed_equation() -> None:
    """seed → source_kind='seed_equation', equation_id=eq-… (FK pura)."""
    from bib2graph.sources.openalex import _work_to_row

    row = _work_to_row(
        _make_minimal_work_dict(),
        equation_id="eq-20260101T000000",
        fetched_at="2026-01-01T00:00:00+00:00",
        source_kind="seed_equation",
    )
    events = json.loads(row[Col.PROVENANCE])
    assert len(events) == 1
    assert events[0]["source_kind"] == "seed_equation"
    assert events[0]["equation_id"] == "eq-20260101T000000"
    assert events[0]["chaining_hop"] is None
    # equation_id nunca lleva prefijo chaining:
    assert not str(events[0]["equation_id"]).startswith("chaining:")


@pytest.mark.unit
def test_work_to_row_chaining_forward_no_equation_id_y_chaining_hop_1() -> None:
    """fetch_citing / forager → source_kind='chaining_forward', equation_id=None, chaining_hop=1.

    Constraint duro (ADR 0050 §Constraints del consumidor programático):
    ``chaining_hop`` debe seguir emitiéndose no-null para citantes forrajeados.
    """
    from bib2graph.sources.openalex import _work_to_row

    row = _work_to_row(
        _make_minimal_work_dict(),
        equation_id=None,
        fetched_at="2026-01-01T00:00:00+00:00",
        is_seed=False,
        action="fetched",
        chaining_hop=1,
        source_tag="chaining:forward",
        source_kind="chaining_forward",
    )
    events = json.loads(row[Col.PROVENANCE])
    assert len(events) == 1
    assert events[0]["source_kind"] == "chaining_forward"
    assert events[0]["equation_id"] is None
    assert events[0]["chaining_hop"] == 1
    # El source_tag del evento sigue siendo "chaining:forward" (ADR 0020
    # lo mantiene adrede; source_kind NO lo duplica).
    assert events[0]["source"] == "chaining:forward"


@pytest.mark.unit
def test_work_to_row_load_no_source_kind() -> None:
    """load (archivo JSON) → source_kind=None; no es ni seed ni chain."""
    from bib2graph.sources.openalex import _work_to_row

    row = _work_to_row(
        _make_minimal_work_dict(),
        equation_id="load",
        fetched_at="2026-01-01T00:00:00+00:00",
    )
    events = json.loads(row[Col.PROVENANCE])
    assert len(events) == 1
    # Default = None (sin tocar) — cierre del overload de chaining:*
    assert events[0]["source_kind"] is None
    assert events[0]["equation_id"] == "load"


@pytest.mark.unit
def test_apply_curation_to_rows_evento_no_lleva_source_kind() -> None:
    """_apply_curation_to_rows añade evento de curación con source_kind=None.

    La curación (accept/reject) NO es ni seed ni chain; source_kind queda None.
    """
    rows = [
        {
            "id": "oa:test00000000",
            "openalex_id": None,
            "doi": None,
            "title": "Paper x",
            "year": 2020,
            "abstract": None,
            "source": None,
            "language": None,
            "publisher": None,
            "research_areas": None,
            "is_seed": True,
            "curation_status": CurationStatus.CANDIDATE.value,
            "provenance": None,
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
    ]
    updated = _apply_curation_to_rows(
        rows,
        ["oa:test00000000"],
        "accepted",
        "human",
        "2026-06-15T10:00:00+00:00",
    )
    events = json.loads(updated[0][Col.PROVENANCE])
    assert len(events) == 1
    assert events[0]["action"] == "accepted"
    assert events[0]["source_kind"] is None


@pytest.mark.unit
def test_bibtex_load_no_source_kind() -> None:
    """BibtexSource.load → source_kind=None (no es seed ni chain)."""
    from bib2graph.sources.bibtex import _entry_to_row

    row = _entry_to_row(
        {"title": "Paper", "author": "Doe, J.", "year": "2024"},
        fetched_at="2026-01-01T00:00:00+00:00",
    )
    events = json.loads(row[Col.PROVENANCE])
    assert len(events) == 1
    assert events[0]["source_kind"] is None
    assert events[0]["equation_id"] is None


# ---------------------------------------------------------------------------
# 3. Migración on-read — derive chaining:* → source_kind
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_migrate_provenance_event_chaining_forward() -> None:
    """Evento pre-D2 con chaining:forward → source_kind derivado, equation_id=None."""
    pre_d2 = {
        "action": "fetched",
        "equation_id": "chaining:forward:W12345",
        "chaining_hop": 1,
        "source": "chaining:forward",
        "fetched_at": "2026-01-01T00:00:00+00:00",
        "decided_by": None,
        "decided_at": None,
    }
    migrated = migrate_provenance_event(pre_d2)

    assert migrated["source_kind"] == "chaining_forward"
    assert migrated["equation_id"] is None
    assert migrated["chaining_hop"] == 1
    # El resto del evento se preserva bit a bit.
    assert migrated["action"] == "fetched"
    assert migrated["source"] == "chaining:forward"


@pytest.mark.unit
def test_migrate_provenance_event_chaining_backward() -> None:
    """Evento pre-D2 con chaining:backward → source_kind='chaining_backward', equation_id=None."""
    pre_d2 = {
        "action": "fetched",
        "equation_id": "chaining:backward:W12345",
        "chaining_hop": 1,
        "source": "chaining:backward",
        "fetched_at": "2026-01-01T00:00:00+00:00",
        "decided_by": None,
        "decided_at": None,
    }
    migrated = migrate_provenance_event(pre_d2)

    assert migrated["source_kind"] == "chaining_backward"
    assert migrated["equation_id"] is None


@pytest.mark.unit
def test_migrate_provenance_event_chaining_forward_only_prefix() -> None:
    """Sin ID después del prefijo → migra igual (forger forward batch)."""
    pre_d2 = {
        "action": "fetched",
        "equation_id": "chaining:forward",
        "chaining_hop": 1,
        "source": "chaining:forward",
        "fetched_at": "2026-01-01T00:00:00+00:00",
        "decided_by": None,
        "decided_at": None,
    }
    migrated = migrate_provenance_event(pre_d2)
    assert migrated["source_kind"] == "chaining_forward"
    assert migrated["equation_id"] is None


@pytest.mark.unit
def test_migrate_provenance_event_seed_equation_no_tocado() -> None:
    """Evento pre-D2 con equation_id=eq-… no se toca (FK pura, no carga)."""
    pre_d2 = {
        "action": "fetched",
        "equation_id": "eq-20260101T000000",
        "chaining_hop": None,
        "source": "openalex",
        "fetched_at": "2026-01-01T00:00:00+00:00",
        "decided_by": None,
        "decided_at": None,
    }
    migrated = migrate_provenance_event(pre_d2)
    # El parser no añade source_kind cuando el evento NO es chaining: se
    # devuelve tal cual.  Los consumidores que necesiten el campo deben
    # usar ``.get("source_kind")`` y tolerar ausencia (el default del modelo
    # es None).
    assert "source_kind" not in migrated or migrated["source_kind"] is None
    assert migrated["equation_id"] == "eq-20260101T000000"


@pytest.mark.unit
def test_migrate_provenance_event_load_no_tocado() -> None:
    """Evento pre-D2 con equation_id='load' o 'fetched_by_id' → no se toca."""
    for eq_id in ("load", "fetched_by_id"):
        pre_d2 = {
            "action": "fetched",
            "equation_id": eq_id,
            "chaining_hop": None,
            "source": "openalex",
            "fetched_at": "2026-01-01T00:00:00+00:00",
            "decided_by": None,
            "decided_at": None,
        }
        migrated = migrate_provenance_event(pre_d2)
        assert "source_kind" not in migrated or migrated["source_kind"] is None
        assert migrated["equation_id"] == eq_id


@pytest.mark.unit
def test_migrate_provenance_event_curation_no_tocado() -> None:
    """Evento de curación (action=accepted/rejected) → no se toca.

    La curación no es ni seed ni chain; si en el futuro alguien quiere
    sumar source_kind, será un campo separado, pero la migración on-read
    no debe inferirlo del equation_id.
    """
    pre_d2 = {
        "action": "accepted",
        "equation_id": None,
        "chaining_hop": None,
        "source": None,
        "fetched_at": None,
        "decided_by": "human",
        "decided_at": "2026-01-01T00:00:00+00:00",
    }
    migrated = migrate_provenance_event(pre_d2)
    assert "source_kind" not in migrated or migrated["source_kind"] is None
    assert migrated["equation_id"] is None


@pytest.mark.unit
def test_migrate_provenance_event_idempotente() -> None:
    """Aplicar la migración dos veces produce el mismo resultado.

    Un evento ya migrado (source_kind presente) NO se vuelve a derivar.
    """
    pre_d2 = {
        "action": "fetched",
        "equation_id": "chaining:forward:W12345",
        "chaining_hop": 1,
        "source": "chaining:forward",
        "fetched_at": "2026-01-01T00:00:00+00:00",
        "decided_by": None,
        "decided_at": None,
    }
    once = migrate_provenance_event(pre_d2)
    twice = migrate_provenance_event(once)

    assert once == twice
    # Y conservar el contenido del evento original (no fabricar campos).
    assert twice["source_kind"] == "chaining_forward"
    assert twice["equation_id"] is None


@pytest.mark.unit
def test_migrate_provenance_event_preserva_source_kind_preexistente() -> None:
    """Si el evento ya trae source_kind válido, no se sobrescribe.

    Protección contra doble migración accidental sobre corpus post-D2.
    """
    post_d2 = {
        "action": "fetched",
        "equation_id": "eq-20260101T000000",
        "chaining_hop": None,
        "source": "openalex",
        "fetched_at": "2026-01-01T00:00:00+00:00",
        "decided_by": None,
        "decided_at": None,
        "source_kind": "seed_equation",
    }
    migrated = migrate_provenance_event(post_d2)
    assert migrated == post_d2


@pytest.mark.unit
def test_migrate_provenance_event_acepta_provenanceevent_model() -> None:
    """El parser acepta también una instancia de ProvenanceEvent (no solo dict)."""
    pre_d2 = ProvenanceEvent(
        action="fetched",
        equation_id="chaining:forward:W12345",
        chaining_hop=1,
        source="chaining:forward",
        fetched_at="2026-01-01T00:00:00+00:00",
        decided_by=None,
        decided_at=None,
    )
    migrated = migrate_provenance_event(pre_d2)
    assert migrated["source_kind"] == "chaining_forward"
    assert migrated["equation_id"] is None


@pytest.mark.unit
def test_migrate_provenance_event_chaining_desconocido_pasa_transparent() -> None:
    """``chaining:<otro>`` sin 'forward'/'backward' conocido: defensivo, pasa tal cual.

    Cubre el caso de un prefijo ``chaining:`` que no sea ni forward ni backward
    (futuro): el parser es conservador y deja pasar el evento sin inventar
    un source_kind.  El campo source_kind queda ausente y equation_id se conserva
    hasta que se decida como migrarlo.
    """
    pre_d2 = {
        "action": "fetched",
        "equation_id": "chaining:lateral:foo",
        "chaining_hop": None,
        "source": "chaining:lateral",
        "fetched_at": "2026-01-01T00:00:00+00:00",
        "decided_by": None,
        "decided_at": None,
    }
    migrated = migrate_provenance_event(pre_d2)
    # Defensivo: no se inventa source_kind, se preserva el equation_id
    # completo (una decisión de futuro decide cómo migrarlo).
    assert "source_kind" not in migrated or migrated["source_kind"] is None
    assert migrated["equation_id"] == "chaining:lateral:foo"


# ---------------------------------------------------------------------------
# 4. corpus_hash estable con corpus pre-D2 vs post-D2
# ---------------------------------------------------------------------------


def _make_hash_row(
    *,
    id_: str,
    provenance: str | None,
    curation_status: str = CurationStatus.CANDIDATE.value,
) -> dict[str, object]:
    return {
        "id": id_,
        "openalex_id": None,
        "doi": None,
        "title": f"Paper {id_}",
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


@pytest.mark.unit
def test_corpus_hash_estable_con_o_sin_source_kind() -> None:
    """compute_corpus_hash excluye provenance (R2, ADR 0017).

    Por construcción, sumar ``source_kind`` al evento de provenance no
    altera el hash — el hash ya ignora la columna entera.  Este test es
    un guarda explícito contra cualquier refactor accidental que incluya
    provenance en el hash.
    """
    row_pre_d2 = _make_hash_row(
        id_="oa:test00000001",
        provenance=json.dumps(
            [
                {
                    "action": "fetched",
                    "equation_id": "chaining:forward:W12345",
                    "chaining_hop": 1,
                    "source": "chaining:forward",
                    "fetched_at": "2026-01-01T00:00:00+00:00",
                    "decided_by": None,
                    "decided_at": None,
                }
            ]
        ),
    )
    row_post_d2 = _make_hash_row(
        id_="oa:test00000001",
        provenance=json.dumps(
            [
                {
                    "action": "fetched",
                    "equation_id": None,
                    "chaining_hop": 1,
                    "source": "chaining:forward",
                    "fetched_at": "2026-06-15T00:00:00+00:00",
                    "decided_by": None,
                    "decided_at": None,
                    "source_kind": "chaining_forward",
                }
            ]
        ),
    )
    table_pre = pa.Table.from_pylist([row_pre_d2], schema=CORPUS_SCHEMA)
    table_post = pa.Table.from_pylist([row_post_d2], schema=CORPUS_SCHEMA)

    assert compute_corpus_hash(table_pre) == compute_corpus_hash(table_post), (
        "R2 garantiza que corpus_hash no depende de provenance: agregar "
        "source_kind no debe alterar la identidad del corpus."
    )


@pytest.mark.unit
def test_corpus_hash_post_d2_idempotente_con_migracion() -> None:
    """Corpus pre-D2 migrado on-read (source_kind derivado) → mismo hash que post-D2.

    Cierra el contrato: la migración on-read no introduce contenido
    bibliográfico nuevo (solo cambia provenance, fuera del hash).
    """
    from bib2graph.backends.memory import _parse_provenance

    pre_provenance = json.dumps(
        [
            {
                "action": "fetched",
                "equation_id": "chaining:forward:W12345",
                "chaining_hop": 1,
                "source": "chaining:forward",
                "fetched_at": "2026-01-01T00:00:00+00:00",
                "decided_by": None,
                "decided_at": None,
            }
        ]
    )
    post_provenance = json.dumps(
        [
            {
                "action": "fetched",
                "equation_id": None,
                "chaining_hop": 1,
                "source": "chaining:forward",
                "fetched_at": "2026-01-01T00:00:00+00:00",
                "decided_by": None,
                "decided_at": None,
                "source_kind": "chaining_forward",
            }
        ]
    )

    # La migración on-read produce el mismo JSON (en provenance) que post-D2,
    # salvo el campo source_kind — pero como provenance queda fuera del hash,
    # ambos corpus tienen el MISMO hash.
    row_pre = _make_hash_row(id_="oa:test00000002", provenance=pre_provenance)
    row_post = _make_hash_row(id_="oa:test00000002", provenance=post_provenance)

    table_pre = pa.Table.from_pylist([row_pre], schema=CORPUS_SCHEMA)
    table_post = pa.Table.from_pylist([row_post], schema=CORPUS_SCHEMA)

    assert compute_corpus_hash(table_pre) == compute_corpus_hash(table_post)

    # Sanity: la migración produce un evento que parsea limpio.
    migrated_events = _parse_provenance(pre_provenance)
    assert len(migrated_events) == 1
    assert migrated_events[0]["source_kind"] == "chaining_forward"
    assert migrated_events[0]["equation_id"] is None


# ---------------------------------------------------------------------------
# 5. Caminos de _work_to_row / forager cubriendo source_kind explícito
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_work_to_row_acepta_cualquier_source_kind_del_enum() -> None:
    """_work_to_row no restringe source_kind; acepta los 3 valores del Literal.

    Para que el contrato del Literal viva solo en ProvenanceEvent (fuente
    única) y _work_to_row sea trivial al forwardear el valor.
    """
    from bib2graph.sources.openalex import _work_to_row

    for value in ("seed_equation", "chaining_forward", "chaining_backward"):
        row = _work_to_row(
            _make_minimal_work_dict(),
            equation_id=None,
            fetched_at="2026-01-01T00:00:00+00:00",
            is_seed=False,
            action="fetched",
            chaining_hop=1 if value != "seed_equation" else None,
            source_tag="chaining:forward",
            source_kind=value,
        )
        events = json.loads(row[Col.PROVENANCE])
        assert events[0]["source_kind"] == value


@pytest.mark.unit
def test_corpus_round_trip_preserva_source_kind() -> None:
    """Corpus.from_arrow + to_arrow preserva source_kind en la provenance.

    Verifica que el campo aditivo no se pierde en el round-trip por la tabla
    Arrow (la provenance es un JSON string; los bytes se preservan tal cual).
    """
    from bib2graph.corpus import _rows_with_ids
    from bib2graph.sources.openalex import _work_to_row

    row = _work_to_row(
        _make_minimal_work_dict(),
        equation_id=None,
        fetched_at="2026-01-01T00:00:00+00:00",
        is_seed=False,
        action="fetched",
        chaining_hop=1,
        source_tag="chaining:forward",
        source_kind="chaining_forward",
    )
    rows_with_ids = _rows_with_ids([row])
    table = pa.Table.from_pylist(rows_with_ids, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)
    rows_out = corpus.to_arrow().to_pylist()
    assert len(rows_out) == 1
    events = json.loads(rows_out[0][Col.PROVENANCE])
    assert events[0]["source_kind"] == "chaining_forward"


# ---------------------------------------------------------------------------
# 6. Migración on-read end-to-end via apply_curation (InMemoryBackend)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_apply_curation_migra_chaining_forward_en_provenance() -> None:
    """Persistir pre-D2 con ``chaining:forward:*`` + aplicar curación → migrado in-place.

    Una fila con provenance pre-D2 (``equation_id="chaining:forward:W12345"``)
    se muta por ``apply_curation``: el ``_parse_provenance`` que invoca el
    path de curación ahora pasa por ``migrate_provenance_event`` y produce
    un JSON post-D2 (``equation_id=None``, ``source_kind="chaining_forward"``).
    La curación appendea su propio evento encima.

    Es el test end-to-end clave de la migración: prueba que el camino de
    mutación (que es donde hoy existe el ÚNICO punto que materializa
    provenance en objetos) SIEMPRE entrega eventos post-D2 al consumidor.
    """
    paper_id = "oa:pre_d2_chaining_001"
    provenance_pre_d2 = json.dumps(
        [
            {
                "action": "fetched",
                "equation_id": "chaining:forward:W12345",
                "chaining_hop": 1,
                "source": "chaining:forward",
                "fetched_at": "2026-01-01T00:00:00+00:00",
                "decided_by": None,
                "decided_at": None,
            }
        ]
    )
    base_row: dict[str, object] = {
        "id": paper_id,
        "openalex_id": "W12345",
        "doi": None,
        "title": "Paper pre-D2",
        "year": 2020,
        "abstract": None,
        "source": None,
        "language": None,
        "publisher": None,
        "research_areas": None,
        "is_seed": False,
        "curation_status": CurationStatus.CANDIDATE.value,
        "provenance": provenance_pre_d2,
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
    backend = Corpus.from_arrow(_make_table_proxy([base_row]))._backend

    # Aplicar curación → reescribe provenance via _apply_curation_to_rows,
    # que pasa por _parse_provenance → parse_provenance_migrated →
    # migrate_provenance_event.
    curado = backend.apply_curation(
        [paper_id],
        action="accepted",
        by="revisor",
        decided_at="2026-06-15T10:00:00+00:00",
    )
    events = json.loads(curado.to_arrow().to_pylist()[0][Col.PROVENANCE])
    assert len(events) == 2
    # Primer evento (pre-D2 fetched, migrado por el parser):
    assert events[0]["action"] == "fetched"
    assert events[0]["source_kind"] == "chaining_forward"
    assert events[0]["equation_id"] is None
    assert events[0]["chaining_hop"] == 1
    # Segundo evento (curación, no es chaining):
    assert events[1]["action"] == "accepted"
    assert events[1]["source_kind"] is None


def _make_table_proxy(rows: list[dict[str, object]]) -> pa.Table:
    """Helper: tabla Arrow canónica a partir de filas (igual a test_r2_reproducibility)."""
    return pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)


# ---------------------------------------------------------------------------
# 7. Lectura pura vía parse_provenance_migrated (reads / export)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_parse_provenance_migrated_aplicala_migracion() -> None:
    """parse_provenance_migrated (API pública de lectura) aplica la migración.

    Cualquier callsite externo que quiera consumir provenance con la
    migración on-read aplicada usa esta función. La migración vive en un
    solo lugar funcional (ver ``backends/_provenance_compat.py``).
    """
    raw = json.dumps(
        [
            {
                "action": "fetched",
                "equation_id": "chaining:forward:W12345",
                "chaining_hop": 1,
                "source": "chaining:forward",
                "fetched_at": "2026-01-01T00:00:00+00:00",
                "decided_by": None,
                "decided_at": None,
            }
        ]
    )

    from bib2graph.schemas import parse_provenance_migrated

    events = parse_provenance_migrated(raw)
    assert len(events) == 1
    assert events[0]["source_kind"] == "chaining_forward"
    assert events[0]["equation_id"] is None


@pytest.mark.unit
def test_parse_provenance_migrated_none_devuelve_lista_vacia() -> None:
    """``None`` como entrada → lista vacía (coherente con read de corpus sin events)."""
    from bib2graph.schemas import parse_provenance_migrated

    assert parse_provenance_migrated(None) == []


@pytest.mark.unit
def test_parse_provenance_migrated_corpus_vacio_devuelve_lista_vacia() -> None:
    """``[]`` como entrada → lista vacía."""
    from bib2graph.schemas import parse_provenance_migrated

    assert parse_provenance_migrated("[]") == []
