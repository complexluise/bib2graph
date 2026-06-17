"""backends.memory — ``InMemoryBackend``: implementación pura en Python.

Mueve la lógica de mutación que vivía en ``corpus.py`` (Hito 1) a este
módulo.  Sin I/O, sin dependencias externas al núcleo.  Es el backend
por defecto del ``Corpus`` y el que usan los tests del núcleo (sin DuckDB).

Las reglas D1/D2/D3 del ADR 0013 se cumplen aquí en Python puro;
``DuckDBBackend`` (Hito 3) las expresará en SQL.

R1 (ADR 0023):
- ``_LIST_COLS`` → ``LIST_COLUMNS`` de ``constants.py`` (fuente única).
- ``_parse_provenance``: falla ruidoso ante JSON corrupto (usa
  ``ProvenanceEvent.parse_list``); ya no traga silencioso.
- Construcción del evento de curación usa ``ProvenanceEvent``.

R2 (ADR 0017 enmendado):
- ``compute_corpus_hash``: excluye ``provenance`` del hash; la identidad
  es del *qué* (contenido bibliográfico), no del *cuándo* (auditoría).
- ``_apply_curation_to_rows``: acepta ``decided_at: str | None``; el
  núcleo **no** llama ``datetime.now()``. El timestamp se inyecta desde
  la frontera (CLI) o se omite pasando ``None`` (lo que activa el
  fallback ``datetime.now(UTC)`` como conveniencia para uso como librería).
  Mecanismo elegido: parámetro opcional ``decided_at`` en lugar de un
  ``clock: Callable`` porque (a) simplifica la firma, (b) los tests
  inyectan el timestamp exacto sin construir closures, y (c) mantiene
  ergonomía para uso como librería (sin argumento → fallback razonable).
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Literal

import pyarrow as pa
import pyarrow.compute as pc

from bib2graph.constants import LIST_COLUMNS, Col, CurationStatus
from bib2graph.schemas import CORPUS_SCHEMA, ProvenanceEvent

# ---------------------------------------------------------------------------
# Re-exportar LIST_COLUMNS con el alias histórico (_LIST_COLS) para que
# backends/duckdb.py y cualquier otro importador de la constante antigua
# no rompa en la transición (se puede retirar en R2).
# ---------------------------------------------------------------------------

_LIST_COLS: frozenset[str] = LIST_COLUMNS

# ---------------------------------------------------------------------------
# Constantes internas (D3)
# ---------------------------------------------------------------------------

_CURATION_PRIORITY: dict[str, int] = {
    CurationStatus.ACCEPTED: 2,
    CurationStatus.REJECTED: 1,
    CurationStatus.CANDIDATE: 0,
}

# ---------------------------------------------------------------------------
# Helpers internos — lógica pura movida desde corpus.py
# ---------------------------------------------------------------------------


def compute_corpus_hash(table: pa.Table) -> str:
    """Computa el hash order-independent del **contenido bibliográfico** (D2, R2).

    R2 (ADR 0017 enmendado): la columna ``provenance`` (log de auditoría con
    timestamps de curación) se **excluye** del hash.  Dos corridas que aceptan
    los mismos ids en instantes distintos producen el **mismo** hash porque el
    hash es del *qué* (contenido), no del *cuándo* (procedencia).  La
    procedencia sigue persistiendo como log append-only fuera de la identidad.

    Algoritmo: convertir a lista de dicts **sin** la columna ``provenance``,
    ordenar por ``id``, dentro de cada fila ordenar las listas de strings,
    serializar con JSON determinista y aplicar SHA-256.

    Args:
        table: Tabla Arrow del Corpus.

    Returns:
        Hexdigest SHA-256 del contenido bibliográfico (sin provenance).
    """
    rows = table.to_pylist()
    rows.sort(key=lambda r: r.get("id") or "")
    normalized: list[dict[str, object]] = []
    for row in rows:
        norm_row: dict[str, object] = {}
        for k, v in row.items():
            if k == Col.PROVENANCE:
                # R2: excluir provenance del hash (es auditoría, no identidad)
                continue
            if isinstance(v, list):
                norm_row[k] = sorted(str(x) for x in v if x is not None)
            else:
                norm_row[k] = v
        normalized.append(norm_row)
    serialized = json.dumps(normalized, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


def _parse_provenance(provenance_json: str | None) -> list[dict[str, object]]:
    """Parsea el JSON de provenance como lista de eventos (dicts).

    Delega a ``ProvenanceEvent.parse_list`` que falla ruidoso ante JSON
    corrupto.  Devuelve dicts (no modelos) para mantener compatibilidad con
    el resto de la lógica interna que los manipula como dicts.

    Args:
        provenance_json: String JSON o None.

    Returns:
        Lista de dicts de eventos (puede ser vacía si JSON es None o ``[]``).

    Raises:
        ValueError: Si el JSON es corrupto o no es una lista de objetos válidos.
    """
    events = ProvenanceEvent.parse_list(provenance_json)
    return [e.to_dict() for e in events]


def _latest_human_decided_at(events: list[dict[str, object]]) -> str | None:
    """Devuelve el ``decided_at`` más reciente entre eventos con decisión humana.

    Args:
        events: Lista de eventos de provenance.

    Returns:
        ISO8601 string o None si no hay decisiones humanas.
    """
    human_actions = {CurationStatus.ACCEPTED, CurationStatus.REJECTED}
    timestamps = [
        str(e["decided_at"])
        for e in events
        if e.get("action") in human_actions and e.get("decided_at")
    ]
    return max(timestamps) if timestamps else None


def _merge_curation_status(
    status_a: str,
    provenance_a: str | None,
    status_b: str,
    provenance_b: str | None,
) -> str:
    """Resuelve el ``curation_status`` al fusionar dos filas con el mismo id (D3).

    Gana la decisión humana más reciente mirando ``decided_at`` en provenance.
    Si empatan o no hay decisión humana, gana por prioridad: accepted > rejected
    > candidate.

    Args:
        status_a: Estado de la fila original.
        provenance_a: Provenance JSON de la fila original.
        status_b: Estado de la fila entrante.
        provenance_b: Provenance JSON de la fila entrante.

    Returns:
        El ``curation_status`` ganador.
    """
    ts_a = _latest_human_decided_at(_parse_provenance(provenance_a))
    ts_b = _latest_human_decided_at(_parse_provenance(provenance_b))

    if ts_a and ts_b:
        if ts_b > ts_a:
            return status_b
        if ts_a > ts_b:
            return status_a
    elif ts_b and not ts_a:
        return status_b
    elif ts_a and not ts_b:
        return status_a

    return max(status_a, status_b, key=lambda s: _CURATION_PRIORITY.get(s, 0))


def _merge_list_field(a: object, b: object) -> list[str] | None:
    """Unión de sets ordenada y estable para columnas list[string] (D3).

    Si ambos valores son None (no-lista), devuelve None para preservar la
    ausencia de dato (idempotencia: c.merge(c) == c).

    Args:
        a: Lista o None de la fila original.
        b: Lista o None de la fila entrante.

    Returns:
        Lista unión ordenada y deduplicada, o None si ambos son None.
    """
    if not isinstance(a, list) and not isinstance(b, list):
        return None
    set_a: set[str] = set(a) if isinstance(a, list) else set()
    set_b: set[str] = set(b) if isinstance(b, list) else set()
    return sorted(set_a | set_b)


def _merge_scalar(a: object, b: object) -> object:
    """Para escalares: el no-nulo gana; si ambos no-nulos, gana ``b`` (D3).

    Args:
        a: Valor de la fila original.
        b: Valor de la fila entrante (``other``).

    Returns:
        El valor resultante.
    """
    if b is not None:
        return b
    return a


def _merge_rows(
    row_a: dict[str, object], row_b: dict[str, object]
) -> dict[str, object]:
    """Fusiona dos filas con el mismo ``id`` según las reglas de D3.

    Args:
        row_a: Fila del Corpus original.
        row_b: Fila del Corpus entrante (``other``).

    Returns:
        Fila fusionada.
    """
    result: dict[str, object] = {}
    all_keys = set(row_a) | set(row_b)
    for key in all_keys:
        val_a = row_a.get(key)
        val_b = row_b.get(key)
        if key == Col.CURATION_STATUS:
            result[key] = _merge_curation_status(
                str(val_a or CurationStatus.CANDIDATE),
                str(row_a.get(Col.PROVENANCE)) if row_a.get(Col.PROVENANCE) else None,
                str(val_b or CurationStatus.CANDIDATE),
                str(row_b.get(Col.PROVENANCE)) if row_b.get(Col.PROVENANCE) else None,
            )
        elif key == Col.PROVENANCE:
            result[key] = _merge_provenance(
                str(val_a) if val_a else None,
                str(val_b) if val_b else None,
            )
        elif key in LIST_COLUMNS:
            result[key] = _merge_list_field(val_a, val_b)
        else:
            result[key] = _merge_scalar(val_a, val_b)
    return result


def _merge_provenance(
    provenance_a: str | None,
    provenance_b: str | None,
) -> str | None:
    """Fusiona dos strings de provenance JSON (D4 — log append-only).

    Une los eventos únicos de ambas listas de eventos.  Si ambos son
    ``None`` devuelve ``None`` (preserva la ausencia de dato).

    Exportada para que ``DuckDBBackend`` la registre como UDF Python,
    garantizando equivalencia byte a byte con ``InMemoryBackend``.

    Args:
        provenance_a: JSON de provenance de la fila original (o ``None``).
        provenance_b: JSON de provenance de la fila entrante (o ``None``).

    Returns:
        JSON fusionado como string, o ``None`` si ambos eran ``None``.
    """
    events_a = _parse_provenance(provenance_a)
    events_b = _parse_provenance(provenance_b)
    merged_events = events_a + [e for e in events_b if e not in events_a]
    if not merged_events and not provenance_a and not provenance_b:
        return None
    return json.dumps(merged_events, ensure_ascii=False)


def _rows_to_table(rows: list[dict[str, object]]) -> pa.Table:
    """Construye una tabla Arrow desde una lista de dicts con el schema canónico.

    Args:
        rows: Lista de dicts con los datos de cada fila.

    Returns:
        Tabla Arrow con el schema canónico.
    """
    return pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)


def _apply_curation_to_rows(
    rows: list[dict[str, object]],
    ids: list[str],
    action: str,
    by: str,
    decided_at: str | None = None,
) -> list[dict[str, object]]:
    """Aplica la acción de curación en la lista de filas y devuelve la nueva lista.

    R2 (ADR 0017 enmendado): el timestamp ``decided_at`` se recibe como
    parámetro inyectado desde la frontera (CLI).  Si es ``None``, se genera
    ``datetime.now(UTC)`` como conveniencia para uso como librería.  El núcleo
    **no** llama al reloj salvo como fallback cuando el caller no lo provee.

    Args:
        rows: Filas actuales del corpus.
        ids: Ids a actualizar.
        action: ``'accepted'`` o ``'rejected'``.
        by: Identificador de quien decide.
        decided_at: Timestamp ISO8601 UTC de la decisión.  Si es ``None``,
            se usa ``datetime.now(UTC).isoformat()`` como conveniencia
            (uso como librería sin frontera CLI).

    Returns:
        Nueva lista de filas con la curación aplicada.
    """
    id_set = set(ids)
    resolved_at: str = (
        decided_at if decided_at is not None else datetime.now(UTC).isoformat()
    )
    evento = ProvenanceEvent(
        action=action,
        equation_id=None,
        chaining_hop=None,
        source=None,
        fetched_at=None,
        decided_by=by,
        decided_at=resolved_at,
    )
    updated: list[dict[str, object]] = []
    for row in rows:
        if row.get(Col.ID) in id_set:
            new_row = dict(row)
            new_row[Col.CURATION_STATUS] = action
            events = _parse_provenance(
                str(row.get(Col.PROVENANCE)) if row.get(Col.PROVENANCE) else None
            )
            events.append(evento.to_dict())
            new_row[Col.PROVENANCE] = json.dumps(events, ensure_ascii=False)
            updated.append(new_row)
        else:
            updated.append(row)
    return updated


# ---------------------------------------------------------------------------
# InMemoryBackend
# ---------------------------------------------------------------------------


class InMemoryBackend:
    """Backend puro en Python: almacena el corpus como ``pa.Table`` en memoria.

    Preserva la lógica de mutación del Corpus del Hito 1 (``to_pylist()`` →
    mutar en Python → reconstruir la tabla Arrow).  No tiene I/O ni
    dependencias externas; es el backend de referencia para los tests.

    Semántica de valor: todas las operaciones mutantes devuelven una nueva
    instancia; la original no cambia nunca.

    #54: almacena también los IDs backward observados en ``_referenced_refs``
    (lista en memoria, equivalente a la tabla ``referenced_but_not_fetched``
    de ``DuckDBBackend``).
    """

    def __init__(
        self,
        table: pa.Table,
        *,
        referenced_refs: list[str] | None = None,
    ) -> None:
        """Constructor interno.

        Args:
            table: Tabla Arrow con el schema canónico (debe estar validada
                antes de construir el backend).
            referenced_refs: Lista de IDs ya registrados en la tabla auxiliar
                ``referenced_but_not_fetched`` (para clonar el estado en
                operaciones que devuelven una nueva instancia).
        """
        self._table = table
        # #54: IDs backward observados, en orden de inserción, sin duplicados.
        self._referenced_refs: list[str] = list(referenced_refs or [])

    # ------------------------------------------------------------------
    # TabularBackend protocol
    # ------------------------------------------------------------------

    def to_arrow(self) -> pa.Table:
        """Devuelve la tabla Arrow interna.

        Returns:
            Tabla Arrow con el schema canónico.
        """
        return self._table

    def add_paper(self, row: dict[str, object]) -> InMemoryBackend:
        """Agrega una fila al backend y devuelve una nueva instancia.

        Args:
            row: Fila ya validada con todos los campos del schema.

        Returns:
            Nueva instancia con el paper agregado.
        """
        existing = self._table.to_pylist()
        existing.append(row)
        return InMemoryBackend(
            _rows_to_table(existing), referenced_refs=self._referenced_refs
        )

    def merge(self, other_table: pa.Table) -> InMemoryBackend:
        """Fusiona ``other_table`` respetando D3 y devuelve una nueva instancia.

        Orden: filas de ``self`` primero, luego filas nuevas de ``other_table``.

        Args:
            other_table: Tabla Arrow a fusionar.

        Returns:
            Nueva instancia con las filas fusionadas.
        """
        rows_self_list = self._table.to_pylist()
        rows_other_list = other_table.to_pylist()

        rows_self: dict[str, dict[str, object]] = {
            str(r["id"]): r for r in rows_self_list
        }
        rows_other: dict[str, dict[str, object]] = {
            str(r["id"]): r for r in rows_other_list
        }

        result_rows: list[dict[str, object]] = []
        for row in rows_self_list:
            id_ = str(row["id"])
            if id_ in rows_other:
                result_rows.append(_merge_rows(row, rows_other[id_]))
            else:
                result_rows.append(row)
        for row in rows_other_list:
            id_ = str(row["id"])
            if id_ not in rows_self:
                result_rows.append(row)

        return InMemoryBackend(
            _rows_to_table(result_rows), referenced_refs=self._referenced_refs
        )

    def apply_curation(
        self,
        ids: list[str],
        *,
        action: str,
        by: str,
        decided_at: str | None = None,
    ) -> InMemoryBackend:
        """Aplica accept/reject a los ids indicados y devuelve una nueva instancia.

        R2: ``decided_at`` se inyecta desde la frontera (CLI).  Si es ``None``,
        ``_apply_curation_to_rows`` usa ``datetime.now(UTC)`` como fallback.

        Args:
            ids: Lista de ``id`` a actualizar.
            action: ``'accepted'`` o ``'rejected'``.
            by: Identificador de quien decide.
            decided_at: Timestamp ISO8601 UTC de la decisión (inyectado desde
                la frontera CLI; ``None`` = fallback a ``datetime.now(UTC)``).

        Returns:
            Nueva instancia con la curación aplicada.
        """
        updated = _apply_curation_to_rows(
            self._table.to_pylist(), ids, action, by, decided_at
        )
        return InMemoryBackend(
            _rows_to_table(updated), referenced_refs=self._referenced_refs
        )

    def filter_view(self, view: Literal["seeds", "candidates", "accepted"]) -> pa.Table:
        """Devuelve la tabla filtrada según la vista pedida.

        Args:
            view: ``'seeds'``, ``'candidates'`` o ``'accepted'``.

        Returns:
            Tabla Arrow filtrada.

        Raises:
            ValueError: Si el nombre de vista no es reconocido.
        """
        if view == "seeds":
            mask = self._table.column(Col.IS_SEED)
            return self._table.filter(mask)
        elif view == "candidates":
            col = self._table.column(Col.CURATION_STATUS)
            mask = pc.equal(col, CurationStatus.CANDIDATE)  # type: ignore[attr-defined]
            return self._table.filter(mask)
        elif view == "accepted":
            col = self._table.column(Col.CURATION_STATUS)
            mask = pc.equal(col, CurationStatus.ACCEPTED)  # type: ignore[attr-defined]
            return self._table.filter(mask)
        else:
            raise ValueError(
                f"Vista '{view}' no reconocida. Use: seeds, candidates, accepted."
            )

    def corpus_hash(self) -> str:
        """Computa el hash order-independent del contenido (D2).

        Returns:
            Hexdigest SHA-256 del contenido de la tabla.
        """
        return compute_corpus_hash(self._table)

    def __len__(self) -> int:
        """Número de papers en el backend."""
        return len(self._table)

    def __eq__(self, other: object) -> bool:
        """Igualdad canónica: mismo hash de contenido (D2)."""
        if not isinstance(other, InMemoryBackend):
            return False
        return self.corpus_hash() == other.corpus_hash()

    # ------------------------------------------------------------------
    # Extensiones: referenced_but_not_fetched (#54)
    # ------------------------------------------------------------------

    def add_referenced_refs(self, ref_ids: list[str], *, cycle_round: int) -> int:
        """Appendea IDs backward observados a la tabla auxiliar en memoria.

        Solo inserta los que aún no están (idempotente).  ``cycle_round`` se
        acepta por compatibilidad con el protocolo pero no se persiste en
        memoria (el backend en memoria no necesita auditoría de ronda).

        Args:
            ref_ids: IDs de OpenAlex observados en backward chaining.
            cycle_round: Número de ronda del ciclo en curso (ignorado en memoria).

        Returns:
            Número de IDs nuevos insertados.
        """
        existing = set(self._referenced_refs)
        new_ids = [rid for rid in ref_ids if rid not in existing]
        self._referenced_refs.extend(new_ids)
        return len(new_ids)

    def referenced_refs_count(self) -> int:
        """Número de IDs en la tabla auxiliar.

        Returns:
            Conteo total.
        """
        return len(self._referenced_refs)

    def referenced_refs(self) -> list[str]:
        """Lista de IDs en la tabla auxiliar, en orden de inserción.

        Returns:
            Lista de ``ref_id``.
        """
        return list(self._referenced_refs)
