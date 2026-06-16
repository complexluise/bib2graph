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
# Re-export CycleState bajo el alias LoopState para compatibilidad
# con código que ya importa LoopState desde este módulo.
# R3: el dominio vive en cycle.py; backends.duckdb solo persiste.
# ---------------------------------------------------------------------------

LoopState = CycleState  # alias de compatibilidad (R3)

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

_DDL_CORPUS = """
CREATE TABLE IF NOT EXISTS corpus (
    id                   VARCHAR NOT NULL PRIMARY KEY,
    openalex_id          VARCHAR,
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
    cited_by_id          VARCHAR[]
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

# ---------------------------------------------------------------------------
# SQL de UPSERT
# El merge campo a campo (D3) se expresa en SQL:
#   - Escalares: COALESCE(excluded.col, corpus.col)
#   - Listas: CASE WHEN … list_sort(list_distinct(list_concat(…))) END
#   - provenance / curation_status: delegados a UDFs Python
# ---------------------------------------------------------------------------


def _build_upsert_sql() -> str:
    """Construye el SQL de UPSERT con merge D3 para todos los campos."""
    scalar_cols = [
        "openalex_id",
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

    # Columnas en el INSERT (orden del schema canónico)
    insert_cols = ", ".join(f.name for f in CORPUS_SCHEMA)
    placeholders = ", ".join(f"${i + 1}" for i in range(len(CORPUS_SCHEMA)))

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
    """
    return [row.get(f.name) for f in CORPUS_SCHEMA]


def _arrow_table_from_con(con: duckdb.DuckDBPyConnection) -> pa.Table:
    """Lee la tabla ``corpus`` y la convierte al schema Arrow canónico."""
    result: pa.Table = con.execute("SELECT * FROM corpus").to_arrow_table()
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

    ``LoopState`` (ADR 0016): extensión propia con ``loop_state()`` y
    ``set_loop_state()``.

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
        """Crea las tablas DDL y registra las UDFs Python."""
        self._con.execute(_DDL_CORPUS)
        self._con.execute(_DDL_LOOP_STATE)
        # R3: migración liviana — agrega columna round si falta (bases pre-R3).
        with contextlib.suppress(duckdb.CatalogException):
            self._con.execute(_DDL_LOOP_STATE_MIGRATE)
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
        """Hace upsert de todas las filas de ``table`` en la base de datos."""
        rows = table.to_pylist()
        for row in rows:
            params = _row_to_params(row)
            self._con.execute(_UPSERT_SQL, params)

    def _clone(self) -> DuckDBBackend:
        """Crea una nueva instancia apuntando al mismo archivo (path compartido).

        Para ``:memory:`` exporta el estado actual y lo carga en una nueva
        conexión in-memory (no se puede compartir una conexión :memory:).
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
            Tabla Arrow con el schema canónico del Corpus.
        """
        table = _arrow_table_from_con(self._con)
        validate_table(table)
        return table

    def add_paper(self, row: dict[str, object]) -> DuckDBBackend:
        """Agrega (upsert) una fila al backend y devuelve una nueva instancia.

        Args:
            row: Fila ya validada con todos los campos del schema.

        Returns:
            Nueva instancia con el paper agregado.
        """
        new_backend = self._clone()
        params = _row_to_params(row)
        new_backend._con.execute(_UPSERT_SQL, params)
        return new_backend

    def merge(self, other_table: pa.Table) -> DuckDBBackend:
        """Fusiona ``other_table`` respetando D3 y devuelve una nueva instancia.

        El orden de filas resultante respeta la primera aparición (D3):
        filas de ``self`` primero (en su orden original), luego las filas
        nuevas de ``other_table``.  Se logra capturando los ids existentes
        antes del upsert y reconstruyendo el orden después.

        Args:
            other_table: Tabla Arrow a fusionar.

        Returns:
            Nueva instancia con las filas fusionadas.
        """
        # Capturar ids de self (en orden)
        existing_ids: list[str] = [
            str(r)
            for r in self._con.execute(
                "SELECT id FROM corpus ORDER BY rowid"
            ).fetchnumpy()["id"]
        ]
        existing_id_set = set(existing_ids)

        new_backend = self._clone()
        new_backend._upsert_table(other_table)

        # Reordenar: filas de self primero (en su orden original),
        # luego las filas nuevas de other_table en el orden en que aparecen
        other_rows = other_table.to_pylist()
        new_ids_in_order = [
            str(r["id"]) for r in other_rows if str(r["id"]) not in existing_id_set
        ]
        ordered_ids = existing_ids + new_ids_in_order

        if ordered_ids:
            placeholders = ", ".join(f"'{i}'" for i in ordered_ids)
            # Usamos un CASE WHEN para forzar el orden
            order_sql = (
                f"SELECT * FROM corpus WHERE id IN ({placeholders}) "
                f"ORDER BY CASE id "
                + " ".join(
                    f"WHEN '{id_}' THEN {pos}" for pos, id_ in enumerate(ordered_ids)
                )
                + " END"
            )
            ordered_table: pa.Table = (
                new_backend._con.execute(order_sql).to_arrow_table().cast(CORPUS_SCHEMA)
            )
            # Re-insertar en el orden correcto: limpiar y reinsertar
            new_backend._con.execute("DELETE FROM corpus")
            rows_ordered = ordered_table.to_pylist()
            for row in rows_ordered:
                params = _row_to_params(row)
                new_backend._con.execute(_UPSERT_SQL, params)

        return new_backend

    def apply_curation(
        self,
        ids: list[str],
        *,
        action: str,
        by: str,
        decided_at: str | None = None,
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

        Returns:
            Nueva instancia con la curación aplicada.
        """
        # Leer solo las filas afectadas, aplicar la lógica Python verificada,
        # y hacer upsert de vuelta
        current_table = _arrow_table_from_con(self._con)
        current_rows = current_table.to_pylist()
        updated_rows = _apply_curation_to_rows(
            current_rows, ids, action, by, decided_at
        )

        new_backend = self._clone()
        # Sólo actualizar las filas que cambiaron
        id_set = set(ids)
        for row in updated_rows:
            if str(row.get("id")) in id_set:
                params = _row_to_params(row)
                new_backend._con.execute(_UPSERT_SQL, params)
        return new_backend

    def filter_view(self, view: Literal["seeds", "candidates", "accepted"]) -> pa.Table:
        """Devuelve la tabla filtrada según la vista pedida.

        Args:
            view: ``'seeds'``, ``'candidates'`` o ``'accepted'``.

        Returns:
            Tabla Arrow filtrada.

        Raises:
            ValueError: Si la vista no es reconocida.
        """
        if view == "seeds":
            result = self._con.execute(
                "SELECT * FROM corpus WHERE is_seed = TRUE"
            ).to_arrow_table()
        elif view == "candidates":
            result = self._con.execute(
                "SELECT * FROM corpus WHERE curation_status = 'candidate'"
            ).to_arrow_table()
        elif view == "accepted":
            result = self._con.execute(
                "SELECT * FROM corpus WHERE curation_status = 'accepted'"
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
    # Extensiones propias: CycleState / LoopState (ADR 0016, R3)
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
    # Extensión: query SQL libre
    # ------------------------------------------------------------------

    def query(self, sql: str) -> pa.Table:
        """Ejecuta una consulta SQL sobre el backend y devuelve tabla Arrow.

        Solo para lectura (no muta el estado).

        Args:
            sql: Sentencia SQL SELECT a ejecutar.

        Returns:
            Resultado como tabla Arrow.
        """
        return self._con.execute(sql).to_arrow_table()
