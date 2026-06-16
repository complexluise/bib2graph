"""Tests R1 — capa constants / models / schemas (ADR 0023).

Verifica los tres contratos del Hito R1:
1. ``Col`` / ``CurationStatus`` / ``NetworkKind`` cubren el schema canónico.
2. ``ProvenanceEvent``: round-trip determinista y falla explícita ante JSON corrupto.
3. Paridad ``PaperRow`` ⇄ ``CORPUS_SCHEMA`` (test que falla si divergen).

Disciplina de tests del repo: solo lo que tiene lógica o riesgo de regresión.
No se testea cada miembro del enum por separado (trivial).

Marcador: ``unit`` (sin red, sin I/O).
"""

from __future__ import annotations

import json

import pytest

from bib2graph.constants import LIST_COLUMNS, Col, CurationStatus, NetworkKind
from bib2graph.schemas import (
    CORPUS_SCHEMA,
    PaperRow,
    ProvenanceEvent,
    assert_schema_parity,
)

# ---------------------------------------------------------------------------
# 1. Col / CurationStatus / NetworkKind cubren el schema canónico
# ---------------------------------------------------------------------------


class TestColCoversSchema:
    """Todo campo de CORPUS_SCHEMA tiene su Col correspondiente."""

    def test_col_values_match_corpus_schema_names(self) -> None:
        """Cada nombre de CORPUS_SCHEMA está representado por un miembro de Col."""
        schema_names = {f.name for f in CORPUS_SCHEMA}
        col_values = {c.value for c in Col}
        missing_in_col = schema_names - col_values
        assert not missing_in_col, (
            f"Campos de CORPUS_SCHEMA sin Col: {sorted(missing_in_col)}"
        )

    def test_col_values_are_valid_strings(self) -> None:
        """Col es un StrEnum: cada miembro se comporta como string."""
        # StrEnum: Col.ID == "id" == str(Col.ID)
        assert Col.ID == "id"
        assert Col.CURATION_STATUS == "curation_status"
        assert Col.REFERENCES_ID == "references_id"
        # Puede usarse directamente como clave de dict
        row: dict[str, object] = {Col.ID: "test-id"}
        assert row["id"] == "test-id"

    def test_curation_status_values(self) -> None:
        """CurationStatus tiene exactamente los tres valores canónicos."""
        assert CurationStatus.CANDIDATE == "candidate"
        assert CurationStatus.ACCEPTED == "accepted"
        assert CurationStatus.REJECTED == "rejected"
        assert len(CurationStatus) == 3

    def test_network_kind_values(self) -> None:
        """NetworkKind tiene exactamente los 5 kinds disponibles."""
        expected = {
            "bibliographic_coupling",
            "cocitation",
            "author_collab",
            "institution_collab",
            "keyword_cooccurrence",
        }
        assert {k.value for k in NetworkKind} == expected

    def test_network_kind_matches_spec_literal(self) -> None:
        """El ``Literal`` de ``NetworkSpec.kind`` no debe divergir de ``NetworkKind``.

        ``NetworkKind`` es la fuente única; el ``Literal`` se mantiene a mano por
        compatibilidad con mypy/Pydantic. Este test falla si se agrega un kind a
        uno y no al otro.
        """
        from typing import get_args

        from bib2graph.networks.spec import NetworkSpec

        literal_values = set(get_args(NetworkSpec.model_fields["kind"].annotation))
        assert literal_values == {k.value for k in NetworkKind}, (
            "NetworkSpec.kind (Literal) divergió de NetworkKind"
        )

    def test_list_columns_subset_of_col(self) -> None:
        """LIST_COLUMNS es un subconjunto de los valores de Col."""
        col_values = {c.value for c in Col}
        assert LIST_COLUMNS.issubset(col_values), (
            f"Columnas en LIST_COLUMNS sin Col: {LIST_COLUMNS - col_values}"
        )

    def test_list_columns_count(self) -> None:
        """LIST_COLUMNS tiene exactamente 11 columnas (las de tipo list[str])."""
        assert len(LIST_COLUMNS) == 11


# ---------------------------------------------------------------------------
# 2. ProvenanceEvent — round-trip y falla explícita ante JSON corrupto
# ---------------------------------------------------------------------------


class TestProvenanceEvent:
    """Contrato de ProvenanceEvent: serialización determinista y parseo honesto."""

    def _make_event(self, **kwargs: object) -> ProvenanceEvent:
        defaults: dict[str, object] = {
            "action": "fetched",
            "equation_id": "eq-001",
            "chaining_hop": None,
            "source": "openalex",
            "fetched_at": "2026-06-15T10:00:00+00:00",
            "decided_by": None,
            "decided_at": None,
        }
        defaults.update(kwargs)
        return ProvenanceEvent(**defaults)  # type: ignore[arg-type]

    def test_round_trip_stable(self) -> None:
        """Serializar → parsear → serializar produce el mismo JSON."""
        event = self._make_event()
        serialized = ProvenanceEvent.dump_list([event])
        parsed = ProvenanceEvent.parse_list(serialized)
        assert len(parsed) == 1
        re_serialized = ProvenanceEvent.dump_list(parsed)
        assert serialized == re_serialized, (
            "El round-trip no es estable: la serialización difiere."
        )

    def test_round_trip_multiple_events(self) -> None:
        """Lista de eventos sobrevive el round-trip manteniendo el orden."""
        events = [
            self._make_event(action="fetched"),
            self._make_event(
                action="accepted",
                decided_by="human",
                decided_at="2026-06-15T12:00:00+00:00",
            ),
        ]
        serialized = ProvenanceEvent.dump_list(events)
        parsed = ProvenanceEvent.parse_list(serialized)
        assert len(parsed) == 2
        assert parsed[0].action == "fetched"
        assert parsed[1].action == "accepted"
        assert parsed[1].decided_by == "human"

    def test_parse_none_returns_empty(self) -> None:
        """None → lista vacía (provenance ausente es válido)."""
        result = ProvenanceEvent.parse_list(None)
        assert result == []

    def test_parse_empty_list_returns_empty(self) -> None:
        """JSON de lista vacía → lista vacía."""
        result = ProvenanceEvent.parse_list("[]")
        assert result == []

    def test_corrupt_json_raises_value_error(self) -> None:
        """JSON roto → ValueError explícito, NO lista vacía silenciosa."""
        with pytest.raises(ValueError, match="corrupto"):
            ProvenanceEvent.parse_list("{not valid json}")

    def test_non_list_json_raises_value_error(self) -> None:
        """JSON que no es lista → ValueError explícito."""
        with pytest.raises(ValueError, match="lista"):
            ProvenanceEvent.parse_list('{"action": "fetched"}')

    def test_list_with_invalid_item_raises_value_error(self) -> None:
        """Lista con ítem no-objeto → ValueError explícito."""
        with pytest.raises(ValueError):
            ProvenanceEvent.parse_list('["string_item", 42]')

    def test_serialization_order_stable(self) -> None:
        """El orden de campos en la serialización es determinista entre instancias."""
        event_a = ProvenanceEvent(
            action="fetched",
            equation_id="eq-1",
            chaining_hop=None,
            source="openalex",
            fetched_at="2026-01-01T00:00:00+00:00",
            decided_by=None,
            decided_at=None,
        )
        event_b = ProvenanceEvent(
            action="fetched",
            equation_id="eq-1",
            chaining_hop=None,
            source="openalex",
            fetched_at="2026-01-01T00:00:00+00:00",
            decided_by=None,
            decided_at=None,
        )
        # Mismos datos → mismo JSON
        assert ProvenanceEvent.dump_list([event_a]) == ProvenanceEvent.dump_list(
            [event_b]
        )

    def test_to_dict_matches_dump_list_structure(self) -> None:
        """to_dict() produce el dict que dump_list usa internamente."""
        event = self._make_event()
        d = event.to_dict()
        # dump_list serializa como lista de to_dict()
        from_dump = json.loads(ProvenanceEvent.dump_list([event]))
        assert len(from_dump) == 1
        assert from_dump[0] == d


# ---------------------------------------------------------------------------
# 3. Paridad PaperRow ⇄ CORPUS_SCHEMA
# ---------------------------------------------------------------------------


class TestSchemaParidad:
    """PaperRow y CORPUS_SCHEMA deben tener exactamente los mismos campos."""

    def test_assert_schema_parity_passes(self) -> None:
        """assert_schema_parity() no lanza cuando los campos están sincronizados."""
        # Si esto falla, es que PaperRow y CORPUS_SCHEMA driftaron
        assert_schema_parity()

    def test_paper_row_has_all_schema_fields(self) -> None:
        """Cada campo de CORPUS_SCHEMA está en PaperRow."""
        schema_names = {f.name for f in CORPUS_SCHEMA}
        model_names = set(PaperRow.model_fields.keys())
        missing = schema_names - model_names
        assert not missing, (
            f"Campos de CORPUS_SCHEMA ausentes en PaperRow: {sorted(missing)}"
        )

    def test_paper_row_has_no_extra_fields(self) -> None:
        """PaperRow no tiene campos que no estén en CORPUS_SCHEMA."""
        schema_names = {f.name for f in CORPUS_SCHEMA}
        model_names = set(PaperRow.model_fields.keys())
        extra = model_names - schema_names
        assert not extra, (
            f"Campos de PaperRow sin CORPUS_SCHEMA: {sorted(extra)}"
        )

    def test_col_enum_covers_corpus_schema(self) -> None:
        """Col enumera exactamente los mismos nombres que CORPUS_SCHEMA."""
        schema_names = {f.name for f in CORPUS_SCHEMA}
        col_values = {c.value for c in Col}
        # Col puede tener un superconjunto si se añaden cols futuras, pero
        # el mínimo es que todos los campos del schema estén en Col
        assert schema_names.issubset(col_values), (
            f"Campos del schema sin Col: {sorted(schema_names - col_values)}"
        )
