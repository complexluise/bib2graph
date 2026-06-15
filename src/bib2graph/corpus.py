"""corpus - wrapper de semántica de valor sobre la tabla Arrow canónica.

Implementa ``Corpus``, ``Manifest``, ``CorpusSnapshot`` y los submodelos del
Manifest (``EquationRef``, ``ChainingParams``, ``PreprocRef``, ``FilterStep``,
``EnricherRef``) según API.md §1.2-1.3 y las decisiones D1-D6.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from pydantic import BaseModel, Field

from bib2graph.schemas import (
    CORPUS_SCHEMA,
    SCHEMA_VERSION,
    PaperRow,
    SchemaError,
    validate_table,
)

# ---------------------------------------------------------------------------
# Versión de la librería (D5)
# ---------------------------------------------------------------------------


def _lib_version() -> str:
    """Devuelve la versión instalada de bib2graph, con fallback a '0.0.0'."""
    try:
        from importlib.metadata import version

        return version("bib2graph")
    except Exception:
        return "0.0.0"


# ---------------------------------------------------------------------------
# Submodelos del Manifest (API.md §1.3)
# ---------------------------------------------------------------------------


class EquationRef(BaseModel):
    """Referencia a una ecuación de búsqueda ejecutada."""

    equation_id: str
    query: str
    translation_report: list[str] = Field(default_factory=list)


class ChainingParams(BaseModel):
    """Parámetros del forrajeo/chaining."""

    depth: int = 1
    max_candidates: int | None = None
    direction: Literal["backward", "forward", "both"] = "both"


class PreprocRef(BaseModel):
    """Referencia a un preprocesador aplicado."""

    name: str
    params: dict[str, str] = Field(default_factory=dict)


class FilterStep(BaseModel):
    """Paso de filtro PRISMA con conteos."""

    name: str
    criteria: str
    count_before: int
    count_after: int


class EnricherRef(BaseModel):
    """Referencia a un enricher aplicado."""

    name: str
    params: dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Manifest (API.md §1.3, D5)
# ---------------------------------------------------------------------------


class Manifest(BaseModel):
    """Metadatos sellados del Corpus.

    Se serializa a ``manifest.json`` junto al ``corpus.parquet`` del snapshot.
    Los campos obligatorios no tienen default; los opcionales sí (D5).
    """

    schema_version: str
    corpus_hash: str
    lib_version: str
    created_at: datetime

    # Opcionales con default (D5)
    openalex_version: str | None = None
    equations: list[EquationRef] = Field(default_factory=list)
    chaining: ChainingParams | None = None
    preprocessors: list[PreprocRef] = Field(default_factory=list)
    filters: list[FilterStep] = Field(default_factory=list)
    enrichers: list[EnricherRef] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _compute_id(
    openalex_id: str | None,
    doi: str | None,
    title: str,
    year: int | None,
) -> str:
    """Computa el ``id`` canónico de un paper (D1).

    Precedencia: openalex_id > doi > título+año.

    Args:
        openalex_id: ID de OpenAlex (``W...``).
        doi: DOI normalizado (sin prefijo URL).
        title: Título del paper.
        year: Año de publicación.

    Returns:
        ``id`` con prefijo ``oa:``, ``doi:`` o ``tt:``.
    """
    if openalex_id:
        valor = openalex_id
        prefix = "oa"
    elif doi:
        # Normalizar: minúsculas, sin prefijo URL
        valor = (
            doi.lower().removeprefix("https://doi.org/").removeprefix("http://doi.org/")
        )
        prefix = "doi"
    else:
        title_norm = title.lower().strip()
        valor = f"{title_norm}|{year}"
        prefix = "tt"
    digest = hashlib.sha256(valor.encode()).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _compute_corpus_hash(table: pa.Table) -> str:
    """Computa el hash order-independent del contenido de la tabla (D2).

    Algoritmo: convertir a lista de dicts, ordenar por ``id``, dentro de cada
    fila ordenar las listas de strings, serializar con JSON determinista y
    aplicar SHA-256.

    Args:
        table: Tabla Arrow del Corpus.

    Returns:
        Hexdigest SHA-256 del contenido.
    """
    rows = table.to_pylist()
    # Ordenar filas por id
    rows.sort(key=lambda r: r.get("id") or "")
    # Dentro de cada fila, ordenar listas
    normalized: list[dict[str, object]] = []
    for row in rows:
        norm_row: dict[str, object] = {}
        for k, v in row.items():
            if isinstance(v, list):
                norm_row[k] = sorted(str(x) for x in v if x is not None)
            else:
                norm_row[k] = v
        normalized.append(norm_row)
    serialized = json.dumps(normalized, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


def _parse_provenance(provenance_json: str | None) -> list[dict[str, object]]:
    """Parsea el JSON de provenance como lista de eventos.

    Args:
        provenance_json: String JSON o None.

    Returns:
        Lista de eventos (puede ser vacía).
    """
    if not provenance_json:
        return []
    try:
        result = json.loads(provenance_json)
        if isinstance(result, list):
            return [e for e in result if isinstance(e, dict)]
        return []
    except (json.JSONDecodeError, TypeError):
        return []


def _latest_human_decided_at(events: list[dict[str, object]]) -> str | None:
    """Devuelve el ``decided_at`` más reciente entre eventos con decisión humana.

    Args:
        events: Lista de eventos de provenance.

    Returns:
        ISO8601 string o None si no hay decisiones humanas.
    """
    human_actions = {"accepted", "rejected"}
    timestamps = [
        str(e["decided_at"])
        for e in events
        if e.get("action") in human_actions and e.get("decided_at")
    ]
    return max(timestamps) if timestamps else None


_CURATION_PRIORITY = {"accepted": 2, "rejected": 1, "candidate": 0}


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
        # Empate por timestamp → prioridad
    elif ts_b and not ts_a:
        return status_b
    elif ts_a and not ts_b:
        return status_a

    # Sin decisión humana → prioridad
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


# Columnas que son listas de strings
_LIST_COLS = {
    "research_areas",
    "authors_raw",
    "authors_id",
    "authors_affiliations",
    "keywords_raw",
    "keywords_id",
    "institutions_raw",
    "institutions_id",
    "references_id",
    "references_doi",
    "cited_by_id",
}


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
        if key == "curation_status":
            result[key] = _merge_curation_status(
                str(val_a or "candidate"),
                str(row_a.get("provenance")) if row_a.get("provenance") else None,
                str(val_b or "candidate"),
                str(row_b.get("provenance")) if row_b.get("provenance") else None,
            )
        elif key == "provenance":
            # Unir listas de eventos (append-only log).
            # Si ambos originales son falsy (None/""), preservar None para
            # mantener idempotencia: c.merge(c) == c.
            events_a = _parse_provenance(str(val_a) if val_a else None)
            events_b = _parse_provenance(str(val_b) if val_b else None)
            merged_events = events_a + [e for e in events_b if e not in events_a]
            if not merged_events and not val_a and not val_b:
                result[key] = None
            else:
                result[key] = json.dumps(merged_events, ensure_ascii=False)
        elif key in _LIST_COLS:
            result[key] = _merge_list_field(val_a, val_b)
        else:
            result[key] = _merge_scalar(val_a, val_b)
    return result


def _rows_to_table(rows: list[dict[str, object]]) -> pa.Table:
    """Construye una tabla Arrow desde una lista de dicts, aplicando el schema canónico.

    Args:
        rows: Lista de dicts con los datos de cada fila.

    Returns:
        Tabla Arrow con el schema canónico.
    """
    return pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)


# ---------------------------------------------------------------------------
# Corpus (API.md §1.2)
# ---------------------------------------------------------------------------


class Corpus:
    """Wrapper de semántica de valor sobre una tabla Arrow + un Manifest.

    Lo que circula por el pipeline: Source lo siembra, el Forager lo expande,
    el humano lo cura, el Preprocessor lo normaliza, el Store lo persiste
    (biblioteca viva), los Projectors lo consumen. NO envuelve una base de
    datos.

    Todos los métodos que modifican el contenido devuelven un ``Corpus``
    nuevo; la instancia original no muta nunca.
    """

    def __init__(self, table: pa.Table, manifest: Manifest) -> None:
        """Constructor interno.

        Prefer ``Corpus.from_arrow`` para construir desde datos externos;
        este constructor asume que la tabla ya fue validada.

        Args:
            table: Tabla Arrow validada con el schema canónico.
            manifest: Metadatos del Corpus.
        """
        self._table = table
        self._manifest = manifest

    # ------------------------------------------------------------------
    # Propiedades de acceso
    # ------------------------------------------------------------------

    @property
    def table(self) -> pa.Table:
        """Tabla Arrow interna (solo lectura)."""
        return self._table

    @property
    def manifest(self) -> Manifest:
        """Metadatos del Corpus (solo lectura)."""
        return self._manifest

    # ------------------------------------------------------------------
    # Constructor canónico
    # ------------------------------------------------------------------

    @classmethod
    def from_arrow(cls, table: pa.Table) -> Corpus:
        """Valida la tabla con el schema canónico y construye el Corpus.

        Falla ruidoso con ``SchemaError`` si el schema no coincide (columna
        faltante, tipo incorrecto o nulo en columna no-nullable).

        Args:
            table: Tabla Arrow a envolver.

        Returns:
            Instancia de ``Corpus`` validada.

        Raises:
            SchemaError: Si la tabla no cumple el schema canónico.
        """
        validate_table(table)
        manifest = Manifest(
            schema_version=SCHEMA_VERSION,
            corpus_hash="",  # se calcula al sellar (snapshot)
            lib_version=_lib_version(),
            created_at=datetime.now(UTC),
        )
        return cls(table, manifest)

    # ------------------------------------------------------------------
    # Exportación
    # ------------------------------------------------------------------

    def to_arrow(self) -> pa.Table:
        """Devuelve la tabla Arrow subyacente.

        Returns:
            Copia de la tabla Arrow interna.
        """
        return self._table

    # ------------------------------------------------------------------
    # Vistas filtradas
    # ------------------------------------------------------------------

    def seeds(self) -> pa.Table:
        """Vista de los papers semilla (``is_seed == True``).

        Returns:
            Tabla Arrow filtrada.
        """
        mask = self._table.column("is_seed")
        return self._table.filter(mask)

    def candidates(self) -> pa.Table:
        """Vista de los candidatos (``curation_status == 'candidate'``).

        Returns:
            Tabla Arrow filtrada.
        """
        col = self._table.column("curation_status")
        mask = pc.equal(col, "candidate")  # type: ignore[attr-defined]
        return self._table.filter(mask)

    def accepted(self) -> pa.Table:
        """Vista de los papers aceptados (``curation_status == 'accepted'``).

        Returns:
            Tabla Arrow filtrada.
        """
        col = self._table.column("curation_status")
        mask = pc.equal(col, "accepted")  # type: ignore[attr-defined]
        return self._table.filter(mask)

    # ------------------------------------------------------------------
    # Mutación (semántica de valor: devuelven Corpus nuevo)
    # ------------------------------------------------------------------

    def add_paper(self, row: dict[str, object]) -> Corpus:
        """Agrega un paper validando la fila con ``PaperRow``.

        Si el ``id`` no está presente en el dict, lo calcula automáticamente
        con la lógica de D1 (openalex_id > doi > título+año).

        Args:
            row: Diccionario con los datos del paper. Debe incluir al menos
                ``title``, ``is_seed`` y ``curation_status``.

        Returns:
            Nuevo ``Corpus`` con el paper agregado.

        Raises:
            SchemaError: Si los datos no pasan la validación de ``PaperRow``.
        """
        row_copy = dict(row)
        # Calcular id si no viene
        if not row_copy.get("id"):
            raw_year = row_copy.get("year")
            row_copy["id"] = _compute_id(
                openalex_id=str(row_copy["openalex_id"])
                if row_copy.get("openalex_id")
                else None,
                doi=str(row_copy["doi"]) if row_copy.get("doi") else None,
                title=str(row_copy.get("title", "")),
                year=int(str(raw_year)) if raw_year is not None else None,
            )
        try:
            validated = PaperRow(**row_copy)
        except Exception as exc:
            raise SchemaError(f"Fila inválida: {exc}") from exc

        new_row = validated.model_dump()
        existing_rows = self._table.to_pylist()
        existing_rows.append(new_row)
        new_table = _rows_to_table(existing_rows)
        return Corpus(new_table, self._manifest)

    def merge(self, other: Corpus) -> Corpus:
        """Combina dos Corpus deduplicando por ``id`` (idempotente).

        Cuando dos filas comparten ``id``, las fusiona campo a campo según D3:
        - Escalares: el no-nulo gana; si ambos no-nulos, gana ``other``.
        - Listas: unión de sets, ordenada y estable.
        - ``curation_status``: decisión humana más reciente (por ``decided_at``
          en provenance); si empatan → prioridad accepted > rejected > candidate.
        - ``provenance``: log append-only (unión de eventos únicos).

        ``merge`` es idempotente: ``c.merge(c)`` produce un Corpus equivalente.
        El orden de filas resultante es determinista: primero las filas de
        ``self`` en su orden original, luego las filas nuevas de ``other``
        (las que no estaban en ``self``) en el orden en que aparecen en ``other``.

        Args:
            other: Corpus a fusionar con este.

        Returns:
            Nuevo ``Corpus`` con las filas fusionadas.
        """
        rows_self_list = self._table.to_pylist()
        rows_other_list = other._table.to_pylist()

        rows_self: dict[str, dict[str, object]] = {
            str(r["id"]): r for r in rows_self_list
        }
        rows_other: dict[str, dict[str, object]] = {
            str(r["id"]): r for r in rows_other_list
        }

        # Orden determinista: filas de self primero, luego nuevas de other.
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

        new_table = _rows_to_table(result_rows)
        return Corpus(new_table, self._manifest)

    def accept(self, ids: list[str], *, by: str = "human") -> Corpus:
        """Marca los papers con los ids dados como 'accepted'.

        Agrega un evento al log de provenance con ``action='accepted'``,
        ``decided_by`` y ``decided_at`` (ISO8601 UTC). El Corpus original
        no muta (semántica de valor).

        Args:
            ids: Lista de ``id`` a aceptar.
            by: Identificador de quien toma la decisión (default ``'human'``).

        Returns:
            Nuevo ``Corpus`` con los papers aceptados.
        """
        return self._apply_curation(ids, action="accepted", by=by)

    def reject(self, ids: list[str], *, by: str = "human") -> Corpus:
        """Marca los papers con los ids dados como 'rejected'.

        Agrega un evento al log de provenance con ``action='rejected'``,
        ``decided_by`` y ``decided_at`` (ISO8601 UTC). El Corpus original
        no muta (semántica de valor).

        Args:
            ids: Lista de ``id`` a rechazar.
            by: Identificador de quien toma la decisión (default ``'human'``).

        Returns:
            Nuevo ``Corpus`` con los papers rechazados.
        """
        return self._apply_curation(ids, action="rejected", by=by)

    def _apply_curation(
        self,
        ids: list[str],
        action: str,
        by: str,
    ) -> Corpus:
        """Aplica una acción de curación (accept/reject) a los ids dados.

        Args:
            ids: Lista de ids a actualizar.
            action: Acción a registrar (``'accepted'`` o ``'rejected'``).
            by: Quien toma la decisión.

        Returns:
            Nuevo ``Corpus`` con la curación aplicada.
        """
        id_set = set(ids)
        decided_at = datetime.now(UTC).isoformat()
        evento: dict[str, object] = {
            "action": action,
            "equation_id": None,
            "chaining_hop": None,
            "source": None,
            "fetched_at": None,
            "decided_by": by,
            "decided_at": decided_at,
        }
        rows = self._table.to_pylist()
        updated: list[dict[str, object]] = []
        for row in rows:
            if row.get("id") in id_set:
                new_row = dict(row)
                new_row["curation_status"] = action
                events = _parse_provenance(
                    str(row.get("provenance")) if row.get("provenance") else None
                )
                events.append(evento)
                new_row["provenance"] = json.dumps(events, ensure_ascii=False)
                updated.append(new_row)
            else:
                updated.append(row)
        new_table = _rows_to_table(updated)
        return Corpus(new_table, self._manifest)

    def materialize(
        self, view: Literal["author", "keyword", "institution"]
    ) -> pa.Table:
        """Materializa una vista explodida por entidad (author/keyword/institution).

        Devuelve una tabla Arrow con una fila por (paper_id, entidad), útil
        para análisis de co-autoría o co-ocurrencia sin salir de Arrow.

        Args:
            view: Nombre de la vista a materializar.

        Returns:
            Tabla Arrow con columnas ``paper_id`` + la columna de la entidad.

        Raises:
            ValueError: Si el nombre de vista no es reconocido.
        """
        col_map = {
            "author": "authors_id",
            "keyword": "keywords_id",
            "institution": "institutions_id",
        }
        if view not in col_map:
            raise ValueError(f"Vista '{view}' no reconocida. Use: {list(col_map)}.")
        col = col_map[view]
        rows = self._table.to_pylist()
        result: list[dict[str, object]] = []
        for row in rows:
            items = row.get(col) or []
            for item in items:
                result.append({"paper_id": row["id"], view: item})
        return pa.table(
            {
                "paper_id": [r["paper_id"] for r in result],
                view: [r[view] for r in result],
            }
        )

    def snapshot(self, path: Path) -> CorpusSnapshot:
        """Exporta una foto sellada del estado actual (parquet + manifest.json).

        Crea la carpeta ``path`` si no existe, escribe ``corpus.parquet`` y
        ``manifest.json`` con el ``corpus_hash`` calculado (D2). NO es la
        persistencia (eso es el Store DuckDB); es un export derivable.

        Args:
            path: Directorio donde escribir el snapshot.

        Returns:
            ``CorpusSnapshot`` apuntando al directorio recién escrito.
        """
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        corpus_hash = _compute_corpus_hash(self._table)
        manifest = Manifest(
            schema_version=self._manifest.schema_version,
            corpus_hash=corpus_hash,
            lib_version=self._manifest.lib_version,
            openalex_version=self._manifest.openalex_version,
            equations=self._manifest.equations,
            chaining=self._manifest.chaining,
            preprocessors=self._manifest.preprocessors,
            filters=self._manifest.filters,
            enrichers=self._manifest.enrichers,
            created_at=datetime.now(UTC),
        )

        pq.write_table(self._table, path / "corpus.parquet")  # type: ignore[no-untyped-call]
        (path / "manifest.json").write_text(
            manifest.model_dump_json(indent=2), encoding="utf-8"
        )
        return CorpusSnapshot(path=path, manifest=manifest)

    def __len__(self) -> int:
        """Número de papers en el Corpus."""
        return len(self._table)

    def __eq__(self, other: object) -> bool:
        """Igualdad canónica: mismo contenido semántico (no manifest ni orden de filas).

        Dos Corpus son iguales sii tienen los mismos papers con los mismos
        valores en todas las columnas, independientemente del orden de filas y
        del orden interno de las columnas de lista. Usa la misma definición
        autoritativa que ``corpus_hash`` (D2), por lo que es consistente con el
        hash y robusta ante cualquier ``PYTHONHASHSEED``.
        """
        if not isinstance(other, Corpus):
            return False
        return _compute_corpus_hash(self._table) == _compute_corpus_hash(other._table)


# ---------------------------------------------------------------------------
# CorpusSnapshot (API.md §1.3)
# ---------------------------------------------------------------------------


class CorpusSnapshot:
    """Carpeta con corpus.parquet + manifest.json: export sellado.

    Reproducible y versionable. No es la biblioteca viva, es su foto.
    El ``corpus`` se reconstruye en cada acceso desde el parquet (property
    lazy).
    """

    def __init__(self, path: Path, manifest: Manifest) -> None:
        """Constructor interno.

        Args:
            path: Directorio del snapshot.
            manifest: Manifest del snapshot.
        """
        self._path = path
        self._manifest = manifest

    @property
    def path(self) -> Path:
        """Directorio del snapshot."""
        return self._path

    @property
    def manifest(self) -> Manifest:
        """Manifest del snapshot."""
        return self._manifest

    @property
    def corpus(self) -> Corpus:
        """Reconstruye el Corpus desde el parquet del snapshot.

        Returns:
            ``Corpus`` reconstruido desde ``corpus.parquet``.
        """
        table = pq.read_table(self._path / "corpus.parquet", schema=CORPUS_SCHEMA)  # type: ignore[no-untyped-call]
        manifest = self._manifest
        corpus = Corpus(table, manifest)
        return corpus

    @classmethod
    def load(cls, path: Path) -> CorpusSnapshot:
        """Carga un snapshot desde un directorio.

        Lee ``manifest.json`` y verifica que ``corpus.parquet`` exista.

        Args:
            path: Directorio del snapshot.

        Returns:
            ``CorpusSnapshot`` apuntando al directorio dado.

        Raises:
            FileNotFoundError: Si faltan archivos requeridos en el directorio.
            SchemaError: Si el manifest.json no es válido.
        """
        path = Path(path)
        manifest_path = path / "manifest.json"
        parquet_path = path / "corpus.parquet"
        if not manifest_path.exists():
            raise FileNotFoundError(f"manifest.json no encontrado en {path}")
        if not parquet_path.exists():
            raise FileNotFoundError(f"corpus.parquet no encontrado en {path}")
        manifest = Manifest.model_validate_json(
            manifest_path.read_text(encoding="utf-8")
        )
        return cls(path=path, manifest=manifest)
