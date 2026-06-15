"""corpus - wrapper de semántica de valor sobre ``TabularBackend``.

Implementa ``Corpus``, ``Manifest``, ``CorpusSnapshot`` y los submodelos del
Manifest (``EquationRef``, ``ChainingParams``, ``PreprocRef``, ``FilterStep``,
``EnricherRef``) según API.md §1.2-1.3 y las decisiones D1-D6 (ADR 0013).

A partir del Hito 1.5 el ``Corpus`` delega todas las operaciones sobre datos
en un ``TabularBackend`` (ADR 0015).  Por defecto usa ``InMemoryBackend``;
en el Hito 3 se podrá pasar un ``DuckDBBackend``.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import BaseModel, Field

from bib2graph.backends import InMemoryBackend, TabularBackend
from bib2graph.backends.memory import compute_corpus_hash
from bib2graph.schemas import (
    CORPUS_SCHEMA,
    SCHEMA_VERSION,
    PaperRow,
    SchemaError,
    validate_table,
)

# ---------------------------------------------------------------------------
# Re-exporta compute_corpus_hash con el nombre histórico que usan los tests
# del Hito 1 (``from bib2graph.corpus import _compute_corpus_hash``).
# ---------------------------------------------------------------------------

_compute_corpus_hash = compute_corpus_hash


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
# Identidad canónica de un paper (D1) — accesible al backend y a Corpus
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
# Corpus (API.md §1.2)
# ---------------------------------------------------------------------------


class Corpus:
    """Wrapper de semántica de valor sobre un ``TabularBackend`` + un Manifest.

    Lo que circula por el pipeline: Source lo siembra, el Forager lo expande,
    el humano lo cura, el Preprocessor lo normaliza, el Store lo persiste
    (biblioteca viva), los Projectors lo consumen. NO envuelve una base de
    datos directamente; delega en el ``TabularBackend`` inyectado.

    Todos los métodos que modifican el contenido devuelven un ``Corpus``
    nuevo; la instancia original no muta nunca (semántica de valor).
    """

    def __init__(self, backend: TabularBackend, manifest: Manifest) -> None:
        """Constructor interno.

        Prefer ``Corpus.from_arrow`` para construir desde datos externos;
        este constructor asume que la tabla ya fue validada.

        Args:
            backend: Backend de almacenamiento ya inicializado con datos válidos.
            manifest: Metadatos del Corpus.
        """
        self._backend = backend
        self._manifest = manifest

    # ------------------------------------------------------------------
    # Propiedades de acceso
    # ------------------------------------------------------------------

    @property
    def table(self) -> pa.Table:
        """Tabla Arrow del contenido actual (delegada al backend)."""
        return self._backend.to_arrow()

    @property
    def manifest(self) -> Manifest:
        """Metadatos del Corpus (solo lectura)."""
        return self._manifest

    # ------------------------------------------------------------------
    # Constructor canónico
    # ------------------------------------------------------------------

    @classmethod
    def from_arrow(
        cls,
        table: pa.Table,
        *,
        backend: TabularBackend | None = None,
    ) -> Corpus:
        """Valida la tabla con el schema canónico y construye el Corpus.

        Falla ruidoso con ``SchemaError`` si el schema no coincide (columna
        faltante, tipo incorrecto o nulo en columna no-nullable).

        Args:
            table: Tabla Arrow a envolver.
            backend: Backend a usar.  Si es ``None`` (default), usa
                ``InMemoryBackend``.  El Hito 3 pasará un ``DuckDBBackend``.

        Returns:
            Instancia de ``Corpus`` validada.

        Raises:
            SchemaError: Si la tabla no cumple el schema canónico.
        """
        validate_table(table)
        resolved_backend: TabularBackend = (
            backend if backend is not None else InMemoryBackend(table)
        )
        manifest = Manifest(
            schema_version=SCHEMA_VERSION,
            corpus_hash="",  # se calcula al sellar (snapshot)
            lib_version=_lib_version(),
            created_at=datetime.now(UTC),
        )
        return cls(resolved_backend, manifest)

    # ------------------------------------------------------------------
    # Exportación
    # ------------------------------------------------------------------

    def to_arrow(self) -> pa.Table:
        """Devuelve la tabla Arrow del contenido actual.

        Returns:
            Tabla Arrow con el schema canónico.
        """
        return self._backend.to_arrow()

    # ------------------------------------------------------------------
    # Vistas filtradas (delegadas al backend)
    # ------------------------------------------------------------------

    def seeds(self) -> pa.Table:
        """Vista de los papers semilla (``is_seed == True``).

        Returns:
            Tabla Arrow filtrada.
        """
        return self._backend.filter_view("seeds")

    def candidates(self) -> pa.Table:
        """Vista de los candidatos (``curation_status == 'candidate'``).

        Returns:
            Tabla Arrow filtrada.
        """
        return self._backend.filter_view("candidates")

    def accepted(self) -> pa.Table:
        """Vista de los papers aceptados (``curation_status == 'accepted'``).

        Returns:
            Tabla Arrow filtrada.
        """
        return self._backend.filter_view("accepted")

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
        new_backend = self._backend.add_paper(new_row)
        return Corpus(new_backend, self._manifest)

    def with_manifest(self, manifest: Manifest) -> Corpus:
        """Devuelve un ``Corpus`` nuevo con el mismo contenido y un Manifest distinto.

        Semántica de valor: la instancia original no muta nunca.  El
        ``corpus_hash`` del resultado es idéntico al del original porque el
        hash es sobre el contenido (tabla), no sobre el manifest.

        Uso típico: actualizar ``openalex_version``, ``equations``,
        ``chaining``, ``filters`` o ``enrichers`` en el manifest sin tocar
        los datos del backend.

        Args:
            manifest: Nuevo Manifest a asociar al corpus.

        Returns:
            Nuevo ``Corpus`` con el mismo backend y el manifest dado.
        """
        return Corpus(self._backend, manifest)

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
        new_backend = self._backend.merge(other._backend.to_arrow())
        return Corpus(new_backend, self._manifest)

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
        new_backend = self._backend.apply_curation(ids, action="accepted", by=by)
        return Corpus(new_backend, self._manifest)

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
        new_backend = self._backend.apply_curation(ids, action="rejected", by=by)
        return Corpus(new_backend, self._manifest)

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
        rows = self._backend.to_arrow().to_pylist()
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

        table = self._backend.to_arrow()
        corpus_hash = self._backend.corpus_hash()
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

        pq.write_table(table, path / "corpus.parquet")  # type: ignore[no-untyped-call]
        (path / "manifest.json").write_text(
            manifest.model_dump_json(indent=2), encoding="utf-8"
        )
        return CorpusSnapshot(path=path, manifest=manifest)

    def __len__(self) -> int:
        """Número de papers en el Corpus."""
        return len(self._backend)

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
        return self._backend.corpus_hash() == other._backend.corpus_hash()


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
        backend: TabularBackend = InMemoryBackend(table)
        return Corpus(backend, manifest)

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
