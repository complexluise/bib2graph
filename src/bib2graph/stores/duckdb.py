"""stores.duckdb — ``DuckDBStore``: fachada de costura sobre ``DuckDBBackend``.

Implementa el Protocol ``Store`` (``persist``/``load``) delegando toda la
I/O en ``DuckDBBackend``.  Es la costura por defecto para la biblioteca
viva (ADR 0009, 0015).

El ``DuckDBStore`` es una fachada delgada:
- ``persist`` hace un ``merge`` del corpus entrante en el backend persistido.
- ``load`` devuelve un ``Corpus`` respaldado por el ``DuckDBBackend`` del
  archivo (la bibliotheca viva acumulada).

Single-writer (ADR 0019): si el archivo está bloqueado por otro proceso,
``StoreLockedError`` se propaga; el CLI (Hito 6) lo mapea al exit code 5.
"""

from __future__ import annotations

from pathlib import Path

from bib2graph.backends.duckdb import DuckDBBackend, StoreLockedError
from bib2graph.constants import Col, Provider
from bib2graph.corpus import Corpus
from bib2graph.cycle import CycleState
from bib2graph.schemas import CORPUS_SCHEMA

__all__ = ["CycleState", "DuckDBStore", "StoreLockedError"]


class DuckDBStore:
    """Fachada de persistencia sobre ``DuckDBBackend`` (ADR 0009, 0015).

    Implementa el Protocol ``Store``: ``persist`` / ``load``.

    Args:
        path: Ruta al archivo ``.duckdb`` de la biblioteca viva.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        # Abrir (o crear) el backend en disco; propaga StoreLockedError si bloqueado
        self._backend: DuckDBBackend = DuckDBBackend(path=self._path)

    def persist(self, corpus: Corpus) -> None:
        """Persiste el corpus en la biblioteca viva (idempotente).

        Hace un merge del corpus entrante en el backend persistido.
        Idempotente: persistir el mismo corpus dos veces no duplica filas
        (el upsert por ``id`` garantiza la idempotencia, D1/D3).

        Args:
            corpus: El ``Corpus`` a persistir.
        """
        self._backend._upsert_table(corpus.to_arrow())

    def persist_replace(self, corpus: Corpus) -> None:
        """Reemplaza toda la tabla ``corpus`` con el contenido de ``corpus``.

        Equivale a TRUNCATE + INSERT: el estado en disco queda siendo
        exactamente el corpus dado, sin residuos de variantes previas.
        Preserva las tablas hermanas (``loop_state_log``,
        ``referenced_but_not_fetched``).

        Úsalo en la ruta de ingesta (seed, restore, chain, thesaurus) donde
        ya tenés el corpus completo y deduplcado en memoria.  Para el caso
        «acumular papers de una nueva fuente sin dedup cross-biblioteca»,
        seguí usando ``persist`` (upsert-concat D3).

        Args:
            corpus: El ``Corpus`` completo y final a persistir.
        """
        self._backend.overwrite_corpus(corpus.to_arrow())

    def register_external_ids(self, corpus: Corpus, engine: Provider) -> int:
        """Registra en ``external_ids`` el ``source_id`` de cada fila (ADR 0053 Corte 2).

        Registra ``(id, engine, source_id)`` de cada fila con ``source_id`` no
        nulo vía ``backend.add_external_ids_bulk`` (``engine`` = token
        ``Provider``: ``openalex`` | ``s2``).  Las filas sin ``source_id`` (p. ej.
        ``seed --from-bib`` sin ``--resolve``) no se registran.

        Bulk (una sentencia) y deja la tabla sin huérfanos (``paper_id`` que ya
        no está en ``corpus``).  Idempotente por la PK ``(paper_id, engine)``.
        Llamarlo al FINAL de la ingesta: si falla antes, la próxima ingesta
        rellena (es idempotente).  ``external_ids`` es una
        tabla lateral: no entra en ``corpus_hash`` (D4 de ADR 0042).

        Args:
            corpus: Corpus YA persistido (obligatorio: la limpieza de huérfanos
                usa la tabla ``corpus``) del que leer ``id`` y ``source_id``.
            engine: Proveedor que resolvió esos ``source_id``.

        Returns:
            Cantidad de filas registradas.
        """
        import pyarrow as pa
        import pyarrow.compute as pc

        table = corpus.to_arrow()
        mask = pc.is_valid(table.column(Col.SOURCE_ID))  # type: ignore[attr-defined]
        valid = table.filter(mask)
        n = len(valid)
        ext = pa.table(
            {
                "paper_id": valid.column(Col.ID).cast(pa.string()),
                "engine": pa.array([engine.value] * n, type=pa.string()),
                "id": valid.column(Col.SOURCE_ID).cast(pa.string()),
            }
        )
        # Una sola sentencia + limpieza de huérfanos (ver add_external_ids_bulk).
        self._backend.add_external_ids_bulk(ext)
        return n

    def load(self) -> Corpus:
        """Carga el corpus acumulado desde la biblioteca viva.

        Devuelve un ``Corpus`` respaldado por el ``DuckDBBackend`` del
        archivo; las operaciones subsecuentes (``accept``, ``reject``,
        ``merge``) mutarán el archivo en disco.

        Ref #126: reconstruye ``manifest.filters`` desde ``filter_log`` para que
        los pasos PRISMA persistan entre sesiones.
        Ref #141: reconstruye ``manifest.enrichers`` desde ``enricher_log`` para
        que los ``EnricherRef`` persistan entre sesiones.
        QA 0.14.0 (hallazgo #1, ADR 0050 D1): reconstruye ``manifest.equations``
        desde la tabla lateral ``equations`` para que los ``EquationRef``
        persistan entre sesiones (antes se perdían: la tabla lateral se
        poblaba en ``seed``, pero ``load()`` nunca la leía de vuelta hacia el
        manifest, así que un ``snapshot create`` posterior sellaba
        ``equations: []`` pese a haber ecuaciones registradas).

        Returns:
            El ``Corpus`` acumulado en el store.
        """
        import json

        import pyarrow as pa

        from bib2graph.corpus import EnricherRef, EquationRef, FilterStep

        table = self._backend.to_arrow()
        if len(table) == 0:
            table = pa.table(
                {f.name: pa.array([], type=f.type) for f in CORPUS_SCHEMA},
                schema=CORPUS_SCHEMA,
            )
        corpus = Corpus.from_arrow(table, backend=self._backend)

        raw_steps = self._backend.load_filter_steps()
        if raw_steps:
            filter_steps = [
                FilterStep(
                    name=str(s["name"]),
                    criteria=str(s["criteria"]),
                    count_before=int(str(s["count_before"])),
                    count_after=int(str(s["count_after"])),
                )
                for s in raw_steps
            ]
            new_manifest = corpus.manifest.model_copy(update={"filters": filter_steps})
            corpus = corpus.with_manifest(new_manifest)

        raw_refs = self._backend.load_enricher_refs()
        if raw_refs:
            enricher_refs = [
                EnricherRef(
                    name=str(r["name"]),
                    params={str(k): str(v) for k, v in r["params"].items()},
                )
                for r in raw_refs
            ]
            new_manifest = corpus.manifest.model_copy(
                update={"enrichers": enricher_refs}
            )
            corpus = corpus.with_manifest(new_manifest)

        # QA 0.14.0 (hallazgo #1, ADR 0050 D1): reconstruye manifest.equations
        # desde la tabla lateral ``equations``. La tabla se crea con
        # ``CREATE TABLE IF NOT EXISTS`` en todo DuckDBBackend (incluidos
        # stores viejos pre-D1): ``load_equations()`` nunca lanza por tabla
        # ausente, simplemente devuelve ``[]`` cuando no hay ecuaciones
        # registradas — retrocompat sin excepciones.
        raw_equations = self._backend.load_equations()
        if raw_equations:
            equation_refs = []
            for eq in raw_equations:
                eq_params = dict(json.loads(str(eq["params_json"] or "{}")))
                # ``query`` es histórico: la query EJECUTADA (traducida), no la
                # cruda (ver docstring de EquationRef). ``params["executed_query"]``
                # la conserva; si falta (ecuación persistida sin ese campo), el
                # mejor fallback disponible es ``raw_query``.
                executed_query = eq_params.get("executed_query")
                translation_report = eq_params.get("translation_report") or []
                equation_refs.append(
                    EquationRef(
                        equation_id=str(eq["equation_id"]),
                        query=str(executed_query)
                        if executed_query is not None
                        else str(eq["raw_query"]),
                        translation_report=[str(x) for x in translation_report],
                        engine=str(eq["engine"])
                        if eq.get("engine") is not None
                        else None,
                        params=eq_params,
                        created_at=str(eq["created_at"])
                        if eq.get("created_at") is not None
                        else None,
                    )
                )
            new_manifest = corpus.manifest.model_copy(
                update={"equations": equation_refs}
            )
            corpus = corpus.with_manifest(new_manifest)

        return corpus

    def close(self) -> None:
        """Cierra la conexión DuckDB y libera el lock de archivo.

        Delega en ``DuckDBBackend.close()``.  Idempotente: llamarlo varias
        veces no lanza error.  Debe llamarse explícitamente en comandos que
        abren el store y terminan (``run_seed_from_bib``, ``run_seed``, etc.)
        para garantizar que el lock se libera antes de la siguiente apertura
        en el mismo proceso, especialmente en Linux donde DuckDB no libera
        el lock al hacer GC del objeto.
        """
        self._backend.close()

    @property
    def backend(self) -> DuckDBBackend:
        """Acceso directo al ``DuckDBBackend`` subyacente.

        Permite usar extensiones propias como ``loop_state()``,
        ``set_loop_state()`` y ``query(sql)``.

        Returns:
            El ``DuckDBBackend`` de esta biblioteca viva.
        """
        return self._backend
