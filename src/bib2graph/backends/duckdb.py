"""backends.duckdb — ``DuckDBBackend``: biblioteca viva persistida en DuckDB.

Implementa el Protocol ``TabularBackend`` mediante SQL ``INSERT … ON CONFLICT
DO UPDATE`` (upsert por ``id``), cumpliendo las reglas D1/D2/D3 del ADR 0013
en SQL + UDFs Python registradas en la conexión DuckDB.

Detalles de diseño (ADR 0015):
- Mutación por SQL puro (no read-all → rebuild).
- Columnas ``list(string)`` nativas DuckDB ↔ ``pa.list_(pa.string())``.
- UDFs Python para ``provenance`` (append-only) y ``curation_status``
  (decisión humana más reciente), reusando helpers de ``backends.memory``
  para garantizar equivalencia byte a byte con ``InMemoryBackend``.
- ``corpus_hash`` se computa siempre sobre ``to_arrow()`` con la misma
  función que ``InMemoryBackend`` (D2).
- ``CycleState`` (ADR 0016 enmendado R3): importado de ``cycle.py`` (dominio
  puro); el backend solo persiste el ciclo en ``loop_state_log`` (estado + ronda).
  La columna ``round`` registra el número de ronda; ``reseed`` incrementa la ronda.
- Single-writer (ADR 0019): archivo bloqueado → ``StoreLockedError``.
- ``:memory:`` cuando no se pasa ``path``.
- ADR 0024: orden D3 garantizado por columna interna ``_seq BIGINT``
  (primera aparición = menor ``_seq``); ``to_arrow()`` excluye ``_seq`` y
  ordena por él. Elimina el DELETE+reinserción de ``merge``.

Este módulo importa ``duckdb`` a nivel de módulo (es correcto aquí; el
núcleo nunca importa este módulo directamente).
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Literal

import duckdb
import pyarrow as pa
from duckdb.func import FunctionNullHandling

from bib2graph.backends.memory import (
    _apply_curation_to_rows,
    _merge_curation_status,
    _merge_provenance,
    compute_corpus_hash,
)
from bib2graph.constants import LIST_COLUMNS, CurationStatus
from bib2graph.cycle import CycleState
from bib2graph.schemas import CORPUS_SCHEMA, validate_table

# ---------------------------------------------------------------------------
# Error de bloqueo de archivo (ADR 0019)
# ---------------------------------------------------------------------------


class StoreLockedError(OSError):
    """El archivo ``.duckdb`` está bloqueado por otro escritor (ADR 0019).

    El CLI (Hito 6) mapea esta excepción al exit code ``5``.
    """


# ---------------------------------------------------------------------------
# SQL DDL
# ---------------------------------------------------------------------------

# ADR 0024: ``_seq BIGINT`` es una columna interna (no parte de CORPUS_SCHEMA)
# que fija el orden de primera aparición para garantizar D3 sin DELETE+reinsert.
# La columna es nullable (sin DEFAULT) para que el UPSERT la controle
# explícitamente; filas existentes conservan su ``_seq`` original.
_DDL_CORPUS = """
CREATE TABLE IF NOT EXISTS corpus (
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
"""

_DDL_LOOP_STATE = """
CREATE TABLE IF NOT EXISTS loop_state_log (
    state       VARCHAR NOT NULL,
    round       INTEGER DEFAULT 0,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""

# R3: si la tabla ya existía sin la columna ``round`` (bases creadas antes de R3),
# agregamos la columna en modo migración liviana (pre-1.0, sin datos reales en uso).
# DuckDB no soporta ADD COLUMN con NOT NULL constraint; se agrega como nullable
# con default 0 y se trata como entero en loop_round().
_DDL_LOOP_STATE_MIGRATE = """
ALTER TABLE loop_state_log ADD COLUMN round INTEGER DEFAULT 0
"""

# #54 (opción B): tabla hermana de loop_state_log — acumula IDs observados en
# backward chaining pero no materializados en el corpus.  Append-only, sin
# constraint UNIQUE: la idempotencia de escritura la garantiza el comando chain
# (que solo escribe los IDs nuevos del lote en curso, no re-escribe anteriores).
# ``observed_at`` usa ``now()`` de DuckDB (mismo patrón que ``recorded_at`` en
# loop_state_log: reloj en la frontera del backend, no inyectado desde el núcleo).
_DDL_REFERENCED_BUT_NOT_FETCHED = """
CREATE TABLE IF NOT EXISTS referenced_but_not_fetched (
    ref_id      VARCHAR NOT NULL,
    cycle_round INTEGER NOT NULL DEFAULT 0,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""

# ADR 0036 (opción C): tabla lateral de IDs externos por motor (openalex, doi, etc.)
# PK lógica (paper_id, engine): un id por motor por paper.  Escritura idempotente
# vía INSERT OR REPLACE (upsert) — re-escribir el mismo (paper_id, engine) reemplaza
# el valor anterior sin duplicar.  Lateral al corpus: NO entra en CORPUS_SCHEMA
# ni en corpus_hash.
_DDL_EXTERNAL_IDS = """
CREATE TABLE IF NOT EXISTS external_ids (
    paper_id VARCHAR NOT NULL,
    engine   VARCHAR NOT NULL,
    id       VARCHAR NOT NULL,
    PRIMARY KEY (paper_id, engine)
)
"""

# #126 — tabla de pasos de filtro PRISMA para trazabilidad del manifest.
# Cada ejecución de ``b2g filter`` appendea una fila por criterio aplicado.
# ``name``/``criteria``/``count_before``/``count_after`` replican ``FilterStep``.
# ``recorded_at`` usa ``now()`` de DuckDB (patrón loop_state_log).
# No tiene PK UNIQUE: la idempotencia la maneja la capa de servicio que
# decide si re-registrar o actualizar (ver ``persist_filter_steps``).
_DDL_FILTER_LOG = """
CREATE TABLE IF NOT EXISTS filter_log (
    name         VARCHAR NOT NULL,
    criteria     VARCHAR NOT NULL,
    count_before INTEGER NOT NULL,
    count_after  INTEGER NOT NULL,
    recorded_at  TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""

# ADR 0024: migración liviana para bases pre-existentes sin columna ``_seq``.
# Se suprime el error si la columna ya existe (CatalogException o BinderException).
# El backfill usa ``rowid`` como proxy de orden de inserción original; es inocuo
# cuando no hay NULLs (UPDATE … WHERE _seq IS NULL no toca nada).
_DDL_CORPUS_MIGRATE_SEQ = """
ALTER TABLE corpus ADD COLUMN _seq BIGINT
"""

_DDL_CORPUS_BACKFILL_SEQ = """
UPDATE corpus SET _seq = rowid WHERE _seq IS NULL
"""

# ---------------------------------------------------------------------------
# SQL de UPSERT
# El merge campo a campo (D3) se expresa en SQL:
#   - Escalares: COALESCE(excluded.col, corpus.col)
#   - Listas: CASE WHEN … list_sort(list_distinct(list_concat(…))) END
#   - provenance / curation_status: delegados a UDFs Python
# ADR 0024: ``_seq`` se incluye en el INSERT pero NO en el DO UPDATE SET,
# de modo que filas existentes conservan su ``_seq`` original (primera aparición).
# ---------------------------------------------------------------------------


def _build_upsert_sql() -> str:
    """Construye el SQL de UPSERT con merge D3 para todos los campos.

    ADR 0024: incluye ``_seq`` como última columna del INSERT (placeholder extra)
    pero la excluye del ``ON CONFLICT DO UPDATE SET`` para preservar el orden
    de primera aparición de filas ya existentes.
    """
    scalar_cols = [
        "source_id",
        "doi",
        "title",
        "year",
        "abstract",
        "source",
        "language",
        "publisher",
        "is_seed",
    ]
    list_cols = list(LIST_COLUMNS)

    scalar_updates = [
        f"    {c} = COALESCE(excluded.{c}, corpus.{c})" for c in scalar_cols
    ]

    # D3 para listas: unión ordenada deduplicada; NULL si ambos son NULL
    list_updates = [
        f"    {c} = CASE\n"
        f"        WHEN corpus.{c} IS NULL AND excluded.{c} IS NULL THEN NULL\n"
        f"        ELSE list_sort(list_distinct(list_concat(\n"
        f"            COALESCE(corpus.{c}, []),\n"
        f"            COALESCE(excluded.{c}, [])\n"
        f"        )))\n"
        f"    END"
        for c in list_cols
    ]

    # UDFs para los campos especiales
    special_updates = [
        "    curation_status = _merge_curation_status_udf(\n"
        "        corpus.curation_status, corpus.provenance,\n"
        "        excluded.curation_status, excluded.provenance\n"
        "    )",
        "    provenance = _merge_provenance_udf(corpus.provenance, excluded.provenance)",
    ]

    all_updates = scalar_updates + list_updates + special_updates
    updates_sql = ",\n".join(all_updates)

    # ADR 0024: columnas del INSERT = CORPUS_SCHEMA + _seq (columna interna de orden)
    schema_cols = ", ".join(f.name for f in CORPUS_SCHEMA)
    insert_cols = f"{schema_cols}, _seq"
    # Un placeholder extra para _seq al final
    placeholders = ", ".join(f"${i + 1}" for i in range(len(CORPUS_SCHEMA) + 1))

    return (
        f"INSERT INTO corpus ({insert_cols})\n"
        f"VALUES ({placeholders})\n"
        f"ON CONFLICT (id) DO UPDATE SET\n"
        f"{updates_sql}"
    )


_UPSERT_SQL = _build_upsert_sql()

# ---------------------------------------------------------------------------
# Helpers de conversión Python ↔ DuckDB
# ---------------------------------------------------------------------------


def _row_to_params(row: dict[str, object]) -> list[object]:
    """Convierte un dict de fila a lista de parámetros posicionales para DuckDB.

    Respeta el orden de columnas de ``CORPUS_SCHEMA``.
    Solo incluye las columnas del schema canónico (no ``_seq``); el llamador
    es responsable de agregar el valor de ``_seq`` al final de la lista.
    """
    return [row.get(f.name) for f in CORPUS_SCHEMA]


def _arrow_table_from_con(con: duckdb.DuckDBPyConnection) -> pa.Table:
    """Lee la tabla ``corpus``, excluye ``_seq`` y ordena por él.

    ADR 0024: ``SELECT * EXCLUDE (_seq) … ORDER BY _seq`` garantiza que
    ``to_arrow()`` devuelva exactamente ``CORPUS_SCHEMA`` en orden de primera
    aparición (D3), sin necesidad de DELETE+reinsert.
    """
    result: pa.Table = con.execute(
        "SELECT * EXCLUDE (_seq) FROM corpus ORDER BY _seq"
    ).to_arrow_table()
    if len(result) == 0:
        return pa.table(
            {f.name: pa.array([], type=f.type) for f in CORPUS_SCHEMA},
            schema=CORPUS_SCHEMA,
        )
    return result.cast(CORPUS_SCHEMA)


# ---------------------------------------------------------------------------
# DuckDBBackend
# ---------------------------------------------------------------------------


class DuckDBBackend:
    """Backend de biblioteca viva persistida en DuckDB (ADR 0009, 0015).

    Implementa el Protocol ``TabularBackend`` con mutaciones por SQL puro
    (``INSERT … ON CONFLICT DO UPDATE`` por ``id``), cumpliendo D1/D2/D3
    (ADR 0013).

    Semántica de valor: todas las operaciones mutantes (``add_paper``,
    ``merge``, ``apply_curation``) devuelven una nueva instancia que
    comparte la misma ruta de archivo pero refleja el estado actualizado.
    Internamente cada instancia tiene su propia conexión; la semántica de
    valor se mantiene porque cada operación crea una nueva instancia.

    ``CycleState`` (ADR 0016): extensión propia con ``loop_state()`` y
    ``set_loop_state()``.

    ADR 0024: el orden D3 se garantiza mediante la columna interna ``_seq``
    (número de secuencia de primera aparición). ``to_arrow()`` devuelve
    exactamente ``CORPUS_SCHEMA`` (sin ``_seq``) ordenado por ``_seq``.

    Args:
        table: Tabla Arrow inicial.  Si se pasa, se hace upsert de sus filas
            en la base de datos.  Permite inicializar desde ``pa.Table``
            (patrón que usa la suite de contrato).
        path: Ruta al archivo ``.duckdb``.  Si es ``None`` (default), se usa
            ``:memory:``.
    """

    def __init__(
        self,
        table: pa.Table | None = None,
        *,
        path: str | Path | None = None,
    ) -> None:
        self._path: str = ":memory:" if path is None else str(path)
        try:
            self._con: duckdb.DuckDBPyConnection = duckdb.connect(self._path)
        except duckdb.IOException as exc:
            raise StoreLockedError(
                f"No se puede abrir '{self._path}': {exc}. "
                "El archivo puede estar bloqueado por otro escritor (ADR 0019). "
                "Cerrá el otro proceso y reintentá."
            ) from exc
        self._setup()
        if table is not None:
            self._upsert_table(table)

    # ------------------------------------------------------------------
    # Inicialización interna
    # ------------------------------------------------------------------

    def _setup(self) -> None:
        """Crea las tablas DDL, aplica migraciones y registra las UDFs Python."""
        self._con.execute(_DDL_CORPUS)
        self._con.execute(_DDL_LOOP_STATE)
        # R3: migración liviana — agrega columna round si falta (bases pre-R3).
        with contextlib.suppress(duckdb.CatalogException):
            self._con.execute(_DDL_LOOP_STATE_MIGRATE)
        # ADR 0024: migración liviana — agrega columna _seq si falta (bases pre-ADR 0024).
        # CatalogException: columna ya existe. BinderException: variante alternativa DuckDB.
        with contextlib.suppress(duckdb.CatalogException, duckdb.BinderException):
            self._con.execute(_DDL_CORPUS_MIGRATE_SEQ)
        # Backfill: asigna _seq = rowid a filas legacy sin _seq asignado.
        # Es inocuo cuando no hay NULLs (WHERE _seq IS NULL no toca nada).
        self._con.execute(_DDL_CORPUS_BACKFILL_SEQ)
        # ADR 0036: migración liviana — renombra openalex_id → source_id si falta.
        # Bases pre-ADR 0036 tienen la columna como openalex_id; se renombra.
        with contextlib.suppress(duckdb.CatalogException, duckdb.BinderException):
            self._con.execute(
                "ALTER TABLE corpus RENAME COLUMN openalex_id TO source_id"
            )
        # #54: tabla auxiliar para IDs backward observados pero no materializados.
        self._con.execute(_DDL_REFERENCED_BUT_NOT_FETCHED)
        # ADR 0036 (opción C): tabla lateral de IDs externos por motor.
        self._con.execute(_DDL_EXTERNAL_IDS)
        # #126: tabla de pasos de filtro PRISMA para trazabilidad del manifest.
        self._con.execute(_DDL_FILTER_LOG)
        self._register_udfs()

    def _register_udfs(self) -> None:
        """Registra UDFs Python en la conexión DuckDB (D3 para provenance/curation)."""

        def merge_curation_udf(
            status_a: str | None,
            prov_a: str | None,
            status_b: str | None,
            prov_b: str | None,
        ) -> str:
            return _merge_curation_status(
                str(status_a or CurationStatus.CANDIDATE),
                prov_a,
                str(status_b or CurationStatus.CANDIDATE),
                prov_b,
            )

        def merge_provenance_udf(
            prov_a: str | None,
            prov_b: str | None,
        ) -> str | None:
            return _merge_provenance(prov_a, prov_b)

        varchar = duckdb.type("VARCHAR")
        # Cuando dos conexiones comparten el mismo archivo DuckDB (con1 todavía
        # abierta, se abre con2), el catálogo de UDFs es compartido y el intento
        # de re-registrar falla con CatalogException.  Como la función ya está
        # registrada con la misma lógica, simplemente la omitimos.
        with contextlib.suppress(duckdb.CatalogException):
            self._con.create_function(
                "_merge_curation_status_udf",
                merge_curation_udf,
                [varchar, varchar, varchar, varchar],
                varchar,
                null_handling=FunctionNullHandling.SPECIAL,
            )

        with contextlib.suppress(duckdb.CatalogException):
            self._con.create_function(
                "_merge_provenance_udf",
                merge_provenance_udf,
                [varchar, varchar],
                varchar,
                null_handling=FunctionNullHandling.SPECIAL,
            )

    def _upsert_table(self, table: pa.Table) -> None:
        """Hace upsert de todas las filas de ``table`` en la base de datos.

        ADR 0024: calcula ``start = COALESCE(MAX(_seq), 0)`` una sola vez y
        asigna ``_seq = start + 1 + i`` (0-based) a cada fila. Filas ya
        existentes (ON CONFLICT) ignoran el ``_seq`` provisto porque el
        DO UPDATE no lo actualiza, preservando así el orden de primera
        aparición (D3).
        """
        rows = table.to_pylist()
        if not rows:
            return
        # ADR 0024: base para el _seq monótono de esta inserción por lote
        result = self._con.execute(
            "SELECT COALESCE(MAX(_seq), 0) FROM corpus"
        ).fetchone()
        start: int = int(result[0]) if result else 0
        for i, row in enumerate(rows):
            # _seq = start + 1 + i garantiza valores únicos y crecientes en este lote
            params = [*_row_to_params(row), start + 1 + i]
            self._con.execute(_UPSERT_SQL, params)

    def _clone(self) -> DuckDBBackend:
        """Crea una nueva instancia apuntando al mismo archivo (path compartido).

        Para ``:memory:`` exporta el estado actual y lo carga en una nueva
        conexión in-memory (no se puede compartir una conexión :memory:).

        ADR 0024: ``_arrow_table_from_con`` ya lee ordenado por ``_seq``;
        al hacer ``_upsert_table`` en la nueva instancia se reasigna ``_seq``
        fresco en ese mismo orden, preservando el orden D3.
        """
        if self._path == ":memory:":
            current_table = _arrow_table_from_con(self._con)
            new_backend = DuckDBBackend.__new__(DuckDBBackend)
            new_backend._path = ":memory:"
            new_backend._con = duckdb.connect(":memory:")
            new_backend._setup()
            if len(current_table) > 0:
                new_backend._upsert_table(current_table)
            # Copiar el loop_state_log (incluyendo round — R3)
            log_rows = self._con.execute(
                "SELECT state, round, recorded_at FROM loop_state_log ORDER BY recorded_at"
            ).fetchall()
            for state_val, round_val, at_val in log_rows:
                new_backend._con.execute(
                    "INSERT INTO loop_state_log (state, round, recorded_at) VALUES (?, ?, ?)",
                    [state_val, round_val, at_val],
                )
            # #54: copiar la tabla referenced_but_not_fetched (hermana de loop_state_log)
            ref_rows = self._con.execute(
                "SELECT ref_id, cycle_round, observed_at "
                "FROM referenced_but_not_fetched ORDER BY observed_at"
            ).fetchall()
            for ref_id_val, cycle_round_val, observed_at_val in ref_rows:
                new_backend._con.execute(
                    "INSERT INTO referenced_but_not_fetched "
                    "(ref_id, cycle_round, observed_at) VALUES (?, ?, ?)",
                    [ref_id_val, cycle_round_val, observed_at_val],
                )
            # ADR 0036: copiar la tabla lateral external_ids
            ext_rows = self._con.execute(
                "SELECT paper_id, engine, id FROM external_ids"
            ).fetchall()
            for paper_id_val, engine_val, id_val in ext_rows:
                new_backend._con.execute(
                    "INSERT OR REPLACE INTO external_ids (paper_id, engine, id) "
                    "VALUES (?, ?, ?)",
                    [paper_id_val, engine_val, id_val],
                )
            # #126: copiar la tabla de pasos de filtro PRISMA
            filter_rows = self._con.execute(
                "SELECT name, criteria, count_before, count_after, recorded_at "
                "FROM filter_log ORDER BY recorded_at"
            ).fetchall()
            for name_val, criteria_val, cb_val, ca_val, at_val in filter_rows:
                new_backend._con.execute(
                    "INSERT INTO filter_log "
                    "(name, criteria, count_before, count_after, recorded_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    [name_val, criteria_val, cb_val, ca_val, at_val],
                )
            return new_backend
        else:
            # Para archivo en disco: compartimos la ruta; nueva instancia abre nueva conexión
            new_backend = DuckDBBackend.__new__(DuckDBBackend)
            new_backend._path = self._path
            new_backend._con = duckdb.connect(self._path)
            new_backend._setup()
            return new_backend

    # ------------------------------------------------------------------
    # TabularBackend protocol
    # ------------------------------------------------------------------

    def to_arrow(self) -> pa.Table:
        """Exporta el contenido completo como tabla Arrow canónica.

        Impone el schema exacto de ``CORPUS_SCHEMA`` (orden y tipos).
        Valida con ``validate_table`` antes de devolver.

        Returns:
            Tabla Arrow con el schema canónico del Corpus (sin ``_seq``).
        """
        table = _arrow_table_from_con(self._con)
        validate_table(table)
        return table

    def add_paper(self, row: dict[str, object]) -> DuckDBBackend:
        """Agrega (upsert) una fila al backend y devuelve una nueva instancia.

        ADR 0024: asigna ``_seq = COALESCE(MAX(_seq), 0) + 1`` para que la
        fila nueva quede al final del orden de primera aparición (D3).

        Args:
            row: Fila ya validada con todos los campos del schema.

        Returns:
            Nueva instancia con el paper agregado.
        """
        new_backend = self._clone()
        # ADR 0024: _seq para la fila nueva = MAX actual + 1
        result = new_backend._con.execute(
            "SELECT COALESCE(MAX(_seq), 0) FROM corpus"
        ).fetchone()
        seq: int = int(result[0]) + 1 if result else 1
        params = [*_row_to_params(row), seq]
        new_backend._con.execute(_UPSERT_SQL, params)
        return new_backend

    def merge(self, other_table: pa.Table) -> DuckDBBackend:
        """Fusiona ``other_table`` respetando D3 y devuelve una nueva instancia.

        ADR 0024: el orden D3 (filas de ``self`` primero en su orden original,
        luego las nuevas filas de ``other_table`` en su orden de aparición) se
        garantiza por la columna interna ``_seq``:
        - Filas de ``self`` ya tienen ``_seq`` asignado (se preservan en el
          ON CONFLICT DO UPDATE, que no actualiza ``_seq``).
        - Filas nuevas de ``other_table`` reciben ``_seq`` mayor (calculado
          como ``MAX(_seq) + 1 + i`` en ``_upsert_table``).
        - ``_arrow_table_from_con`` lee con ``ORDER BY _seq``.
        No se requiere DELETE+reinsert.

        Args:
            other_table: Tabla Arrow a fusionar.

        Returns:
            Nueva instancia con las filas fusionadas, en orden D3.
        """
        new_backend = self._clone()
        new_backend._upsert_table(other_table)
        return new_backend

    def apply_curation(
        self,
        ids: list[str],
        *,
        action: str,
        by: str,
        decided_at: str | None = None,
        source: str | None = None,
    ) -> DuckDBBackend:
        """Aplica accept/reject a los papers indicados y devuelve backend nuevo.

        Reutiliza ``_apply_curation_to_rows`` de ``backends.memory`` para
        garantizar equivalencia exacta con ``InMemoryBackend``.

        R2: ``decided_at`` se inyecta desde la frontera (CLI).  Si es ``None``,
        ``_apply_curation_to_rows`` usa ``datetime.now(UTC)`` como fallback.

        Args:
            ids: Lista de ``id`` a actualizar.
            action: ``'accepted'`` o ``'rejected'``.
            by: Identificador de quien decide.
            decided_at: Timestamp ISO8601 UTC de la decisión (inyectado desde
                la frontera CLI; ``None`` = fallback a ``datetime.now(UTC)``).
            source: Origen del evento (p. ej. criterio de filtro PRISMA).
                Si es ``None``, el campo ``source`` del evento queda vacío.

        Returns:
            Nueva instancia con la curación aplicada.
        """
        # Leer solo las filas afectadas, aplicar la lógica Python verificada,
        # y hacer upsert de vuelta
        current_table = _arrow_table_from_con(self._con)
        current_rows = current_table.to_pylist()
        updated_rows = _apply_curation_to_rows(
            current_rows, ids, action, by, decided_at, source
        )

        new_backend = self._clone()
        # Sólo actualizar las filas que cambiaron
        id_set = set(ids)
        for row in updated_rows:
            if str(row.get("id")) in id_set:
                # ADR 0024: las filas actualizadas ya existen → ON CONFLICT preserva _seq.
                # Se pasa _seq=0 como placeholder; el DO UPDATE no lo sobrescribe.
                params = [*_row_to_params(row), 0]
                new_backend._con.execute(_UPSERT_SQL, params)
        return new_backend

    def filter_view(self, view: Literal["seeds", "candidates", "accepted"]) -> pa.Table:
        """Devuelve la tabla filtrada según la vista pedida.

        ADR 0024: usa ``SELECT * EXCLUDE (_seq) … ORDER BY _seq`` para
        mantener el orden D3 y excluir la columna interna del resultado.

        Args:
            view: ``'seeds'``, ``'candidates'`` o ``'accepted'``.

        Returns:
            Tabla Arrow filtrada.

        Raises:
            ValueError: Si la vista no es reconocida.
        """
        if view == "seeds":
            result = self._con.execute(
                "SELECT * EXCLUDE (_seq) FROM corpus WHERE is_seed = TRUE ORDER BY _seq"
            ).to_arrow_table()
        elif view == "candidates":
            result = self._con.execute(
                "SELECT * EXCLUDE (_seq) FROM corpus WHERE curation_status = "
                f"'{CurationStatus.CANDIDATE.value}' ORDER BY _seq"
            ).to_arrow_table()
        elif view == "accepted":
            result = self._con.execute(
                "SELECT * EXCLUDE (_seq) FROM corpus WHERE curation_status = "
                f"'{CurationStatus.ACCEPTED.value}' ORDER BY _seq"
            ).to_arrow_table()
        else:
            raise ValueError(
                f"Vista '{view}' no reconocida. Use: seeds, candidates, accepted."
            )
        if len(result) == 0:
            return pa.table(
                {f.name: pa.array([], type=f.type) for f in CORPUS_SCHEMA},
                schema=CORPUS_SCHEMA,
            )
        return result.cast(CORPUS_SCHEMA)

    def corpus_hash(self) -> str:
        """Computa el hash order-independent del contenido (D2).

        Se computa siempre sobre ``to_arrow()`` usando la misma función
        que ``InMemoryBackend`` (ADR 0015, ADR 0013 D2).

        Returns:
            Hexdigest SHA-256 del contenido de la tabla.
        """
        return compute_corpus_hash(self.to_arrow())

    def __len__(self) -> int:
        """Número de papers en el backend."""
        result = self._con.execute("SELECT COUNT(*) FROM corpus").fetchone()
        return int(result[0]) if result else 0

    def __eq__(self, other: object) -> bool:
        """Igualdad canónica: mismo hash de contenido (D2)."""
        if not isinstance(other, DuckDBBackend):
            return False
        return self.corpus_hash() == other.corpus_hash()

    # ------------------------------------------------------------------
    # Extensiones propias: CycleState (ADR 0016, R3)
    # ------------------------------------------------------------------

    def loop_state(self) -> CycleState | None:
        """Estado actual del lazo de investigación.

        Lee la última fila de ``loop_state_log`` (log append-only).

        Returns:
            El ``CycleState`` actual, o ``None`` si no hay transiciones aún.
        """
        row = self._con.execute(
            "SELECT state FROM loop_state_log ORDER BY recorded_at DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return CycleState(row[0])

    def loop_round(self) -> int:
        """Número de ronda actual del lazo.

        Lee la columna ``round`` de la última fila de ``loop_state_log``.
        Devuelve ``0`` cuando no hay transiciones (sin estado previo) o cuando
        la columna es NULL (bases migradas desde antes de R3).

        Returns:
            Entero >= 0.  0 = sin estado; 1 = primera ronda; 2+ = re-sembrados.
        """
        row = self._con.execute(
            "SELECT round FROM loop_state_log ORDER BY recorded_at DESC LIMIT 1"
        ).fetchone()
        if row is None or row[0] is None:
            return 0
        return int(row[0])

    def set_loop_state(
        self, state: CycleState, *, cycle_round: int | None = None
    ) -> None:
        """Registra una transición de ``CycleState`` (transición permisiva).

        Agrega una fila al log append-only ``loop_state_log``.  No bloquea
        ningún salto (ADR 0016: transiciones permisivas).

        R3: persiste también el número de ronda.  Si ``cycle_round`` es ``None``,
        conserva la ronda actual (útil para transiciones dentro de la misma
        ronda, p. ej. ``chain``/``filter``/``build``).

        La curación (``accept``/``reject``) es TRANSVERSAL y NO llama
        ``set_loop_state``: no transiciona el lazo.

        Args:
            state: El nuevo estado del lazo.
            cycle_round: Número de ronda a persistir.  Si es ``None``, usa la
                ronda actual del log.
        """
        current_round = self.loop_round() if cycle_round is None else cycle_round
        self._con.execute(
            "INSERT INTO loop_state_log (state, round) VALUES (?, ?)",
            [state.value, current_round],
        )

    # ------------------------------------------------------------------
    # Extensiones propias: referenced_but_not_fetched (#54)
    # ------------------------------------------------------------------

    def add_referenced_refs(self, ref_ids: list[str], *, cycle_round: int) -> int:
        """Appendea IDs backward observados a ``referenced_but_not_fetched``.

        No duplica IDs ya presentes (idempotencia basada en existencia): solo
        inserta los que aún no están en la tabla, independientemente del
        ``cycle_round``.  El ``observed_at`` lo provee ``now()`` de DuckDB.

        Args:
            ref_ids: IDs de OpenAlex observados en backward chaining.
            cycle_round: Número de ronda del ciclo en curso.

        Returns:
            Número de IDs nuevos insertados (0 si todos ya existían).
        """
        if not ref_ids:
            return 0
        # IDs ya presentes (cualquier ronda — el contrato es append sin duplicar).
        existing_rows = self._con.execute(
            "SELECT ref_id FROM referenced_but_not_fetched"
        ).fetchall()
        existing: set[str] = {r[0] for r in existing_rows}
        new_ids = [rid for rid in ref_ids if rid not in existing]
        for rid in new_ids:
            self._con.execute(
                "INSERT INTO referenced_but_not_fetched (ref_id, cycle_round) "
                "VALUES (?, ?)",
                [rid, cycle_round],
            )
        return len(new_ids)

    def referenced_refs_count(self) -> int:
        """Número de IDs en ``referenced_but_not_fetched``.

        Returns:
            Conteo total de filas en la tabla auxiliar.
        """
        row = self._con.execute(
            "SELECT COUNT(*) FROM referenced_but_not_fetched"
        ).fetchone()
        return int(row[0]) if row else 0

    def referenced_refs(self) -> list[str]:
        """Lista de IDs en ``referenced_but_not_fetched``, ordenados por ``observed_at``.

        Returns:
            Lista de ``ref_id`` en orden de inserción.
        """
        rows = self._con.execute(
            "SELECT ref_id FROM referenced_but_not_fetched ORDER BY observed_at"
        ).fetchall()
        return [r[0] for r in rows]

    # ------------------------------------------------------------------
    # Extensiones propias: external_ids (ADR 0036 opción C)
    # ------------------------------------------------------------------

    def add_external_id(self, paper_id: str, engine: str, id: str) -> None:
        """Registra un ID externo para un paper dado un motor.

        Idempotente: si ya existe una entrada ``(paper_id, engine)``, el valor
        se reemplaza (un ID por motor por paper).  La PK lógica
        ``(paper_id, engine)`` garantiza que no haya duplicados.

        Args:
            paper_id: ID interno del paper en el corpus.
            engine: Nombre del motor / fuente del ID (p. ej. ``'openalex'``,
                ``'semanticscholar'``, ``'doi'``).
            id: El ID externo correspondiente a ese motor.
        """
        self._con.execute(
            "INSERT OR REPLACE INTO external_ids (paper_id, engine, id) "
            "VALUES (?, ?, ?)",
            [paper_id, engine, id],
        )

    def external_ids_for(self, paper_id: str) -> dict[str, str]:
        """Devuelve todos los IDs externos registrados para un paper.

        Args:
            paper_id: ID interno del paper en el corpus.

        Returns:
            Diccionario ``{engine: id}`` con todos los IDs registrados para
            ese paper.  Vacío si el paper no tiene IDs externos registrados.
        """
        rows = self._con.execute(
            "SELECT engine, id FROM external_ids WHERE paper_id = ?",
            [paper_id],
        ).fetchall()
        return {r[0]: r[1] for r in rows}

    def all_external_ids(self) -> list[tuple[str, str, str]]:
        """Devuelve todas las entradas de la tabla ``external_ids``.

        Usado internamente para ``_clone()`` y tests de paridad.

        Returns:
            Lista de tuplas ``(paper_id, engine, id)`` en orden no definido.
        """
        rows = self._con.execute(
            "SELECT paper_id, engine, id FROM external_ids"
        ).fetchall()
        return [(r[0], r[1], r[2]) for r in rows]

    # ------------------------------------------------------------------
    # Extensiones propias: filter_log (#126)
    # ------------------------------------------------------------------

    def persist_filter_steps(
        self,
        steps: list[object],
        *,
        replace: bool = True,
    ) -> None:
        """Persiste los pasos de filtro PRISMA en ``filter_log``.

        #126 — trazabilidad PRISMA: los pasos aplicados en ``b2g filter``
        se guardan para que ``manifest.filters`` sobreviva entre cargas del
        store.

        Por defecto (``replace=True``) limpia los pasos anteriores antes de
        insertar los nuevos: cada invocación de ``b2g filter`` reemplaza el
        registro previo completo (idempotencia de ``run_filter``).

        Args:
            steps: Lista de ``FilterStep`` (se accede a sus atributos
                ``name``, ``criteria``, ``count_before``, ``count_after``).
            replace: Si es ``True`` (default), trunca ``filter_log`` antes
                de insertar.  Si es ``False``, appendea (útil para tests
                que verifican acumulación).
        """
        if replace:
            self._con.execute("DELETE FROM filter_log")
        for step in steps:
            self._con.execute(
                "INSERT INTO filter_log (name, criteria, count_before, count_after) "
                "VALUES (?, ?, ?, ?)",
                [
                    getattr(step, "name", None),
                    getattr(step, "criteria", None),
                    getattr(step, "count_before", None),
                    getattr(step, "count_after", None),
                ],
            )

    def load_filter_steps(self) -> list[dict[str, object]]:
        """Carga los pasos de filtro PRISMA desde ``filter_log``.

        #126 — trazabilidad PRISMA: permite que ``DuckDBStore.load()``
        reconstruya ``manifest.filters`` con los pasos persistidos.

        Returns:
            Lista de dicts con las claves ``name``, ``criteria``,
            ``count_before`` y ``count_after`` en el orden de inserción.
        """
        rows = self._con.execute(
            "SELECT name, criteria, count_before, count_after "
            "FROM filter_log ORDER BY recorded_at"
        ).fetchall()
        return [
            {
                "name": r[0],
                "criteria": r[1],
                "count_before": r[2],
                "count_after": r[3],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Extensión: query SQL libre
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Cierra la conexión DuckDB subyacente y libera el lock de archivo.

        Idempotente: llamarlo varias veces o sobre una conexión ya cerrada
        no lanza error.  Necesario en contextos donde se abren múltiples
        instancias sobre el mismo archivo en el mismo proceso (p. ej. dos
        llamadas consecutivas a ``run_seed_from_bib`` sobre el mismo path):
        Linux/DuckDB mantiene el lock de archivo hasta que la conexión se
        cierra explícitamente; depender del GC causa segfault.
        """
        with contextlib.suppress(Exception):
            self._con.close()

    def overwrite_corpus(self, table: pa.Table) -> None:
        """Reemplaza TODA la tabla ``corpus`` con el contenido de ``table``.

        Hace TRUNCATE + INSERT (no upsert) para que el estado en disco sea
        exactamente ``table``, sin residuos de filas previas.  Preserva las
        tablas hermanas (``loop_state_log``, ``referenced_but_not_fetched``).

        Úsalo solo en la ruta de ingesta (``seed``, ``restore``, ``chain``,
        ``thesaurus``) donde ya tenés el corpus completo y correcto en
        memoria.  El upsert normal (``_upsert_table``) sigue siendo correcto
        para el caso «mismo paper desde dos fuentes» (D3); este método NO lo
        reemplaza en ese contexto.

        ADR 0024: reasigna ``_seq`` desde 0 sobre la tabla limpia, manteniendo
        el orden de filas que viene en ``table`` (que ya salió de
        ``to_arrow()`` con ``ORDER BY _seq`` original).

        Args:
            table: Tabla Arrow con exactamente el contenido final a persistir.
                Debe cumplir ``CORPUS_SCHEMA``.
        """
        self._con.execute("DELETE FROM corpus")
        rows = table.to_pylist()
        for i, row in enumerate(rows):
            params = [*_row_to_params(row), i + 1]
            self._con.execute(_UPSERT_SQL, params)

    def query(self, sql: str) -> pa.Table:
        """Ejecuta una consulta SQL sobre el backend y devuelve tabla Arrow.

        Solo para lectura (no muta el estado).

        Args:
            sql: Sentencia SQL SELECT a ejecutar.

        Returns:
            Resultado como tabla Arrow.
        """
        return self._con.execute(sql).to_arrow_table()
