"""service.resolve — Resolución DOI→source_id para papers sin motor (ADR 0035).

Operación de servicio compartida: toma el corpus del workspace, filtra papers
con ``doi`` no nulo y ``source_id`` nulo, llama a
``OpenAlexSource.fetch_dois_to_openalex_ids``, puebla ``source_id`` en esas
filas y persiste con ``persist_replace``.

Capa neutral (ADR 0028/0032): sin ``print``, ``sys.exit``, Click ni FastAPI.
El I/O vive en el Source; este servicio orquesta.

Flujo:
  1. Abrir store → cargar corpus.
  2. Filtrar papers con doi != NULL AND source_id IS NULL.
  3. Llamar a ``fetch_dois_to_openalex_ids(dois)`` (batcheado en el Source).
  4. Para cada match doi→source_id, actualizar la fila en la tabla Arrow.
  5. ``persist_replace`` con el corpus actualizado.

Idempotente: re-ejecutar sobre el mismo corpus produce el mismo resultado
(los papers que ya tienen source_id no se tocan).

Puebla ``source_id`` y, tras persistir, registra ``external_ids`` con
``engine='openalex'`` (la resolución DOI→id solo existe en OpenAlex; ADR 0053
Corte 2, cierra #120).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bib2graph.constants import DEFAULT_PROVIDER, Col, Provider
from bib2graph.service.errors import NetworkError, StoreError

# Helper de normalización DOI (espeja el de openalex.py, función pura)


def _normalize_doi(raw: str | None) -> str | None:
    """Quita el prefijo URL del DOI y lo devuelve en minúsculas."""
    if not raw:
        return None
    doi = raw
    for prefix in ("https://doi.org/", "http://doi.org/"):
        if doi.startswith(prefix):
            doi = doi[len(prefix) :]
            break
    return doi.lower() or None


def _open_writable(path: Path, provider: Provider | str = DEFAULT_PROVIDER) -> Any:
    """Abre el store para escritura; falla accionable si está bloqueado.

    Args:
        path: Ruta al archivo ``.duckdb``.

    Returns:
        ``DuckDBStore`` abierto y listo para leer/escribir.

    Raises:
        StoreError: Si el store está bloqueado o no se puede abrir.
    """
    from bib2graph.backends.duckdb import StoreLockedError
    from bib2graph.stores.duckdb import DuckDBStore

    try:
        return DuckDBStore(path, provider, provider)
    except StoreLockedError as exc:
        raise StoreError(str(exc)) from exc
    except OSError as exc:
        raise StoreError(
            f"No se puede abrir el store '{path}': {exc}. "
            "Verificá que el archivo no esté bloqueado por otro proceso."
        ) from exc


def _resolve_dois_on_store(
    store: Any,
    *,
    email: str | None = None,
    transport: Any = None,
) -> dict[str, Any]:
    """Resuelve DOIs pendientes sobre un store YA ABIERTO y persiste.

    Núcleo de la operación de resolución DOI→source_id.  Opera sobre el
    ``DuckDBStore`` recibido SIN abrirlo ni cerrarlo: es responsabilidad
    del llamador el ciclo de vida del store.

    Separado de ``resolve_dois`` para permitir que el camino encadenado
    ``seed --from-bib --resolve`` reutilice el store abierto por seed,
    evitando el reopen que causaba el segfault (exit 139) por corrupción
    de UDF/closure en DuckDB (#110, #93).

    Args:
        store: ``DuckDBStore`` ya abierto y listo para leer/escribir.
        email: Email para el polite pool de OpenAlex (recomendado).
        transport: Transport inyectable para tests (``httpx.MockTransport``).

    Returns:
        Dict con:
          - ``resolved``: cantidad de papers a los que se les pobló source_id.
          - ``total_with_doi``: cantidad de papers con doi en el corpus.
          - ``already_resolved``: papers con doi que ya tenían source_id.
          - ``total_papers``: total de papers en el corpus.

    Raises:
        NetworkError: Si falla la conexión a OpenAlex.
    """
    import httpx
    import pyarrow as pa
    import pyarrow.compute as pc

    from bib2graph.corpus import Corpus
    from bib2graph.schemas import CORPUS_SCHEMA
    from bib2graph.sources.openalex import OpenAlexSource

    corpus = store.load()
    rows = corpus.to_arrow().to_pylist()
    total_papers = len(rows)

    total_with_doi = sum(1 for r in rows if r.get(Col.DOI))
    needs_resolve = [r for r in rows if r.get(Col.DOI) and r.get(Col.SOURCE_ID) is None]
    already_resolved = total_with_doi - len(needs_resolve)

    if not needs_resolve:
        return {
            "resolved": 0,
            "total_with_doi": total_with_doi,
            "already_resolved": already_resolved,
            "total_papers": total_papers,
        }

    dois_to_resolve: list[str] = []
    for row in needs_resolve:
        doi_norm = _normalize_doi(row.get(Col.DOI))
        if doi_norm:
            dois_to_resolve.append(doi_norm)

    if not dois_to_resolve:
        return {
            "resolved": 0,
            "total_with_doi": total_with_doi,
            "already_resolved": already_resolved,
            "total_papers": total_papers,
        }

    source = OpenAlexSource(email=email, transport=transport)
    try:
        doi_to_source_id = source.fetch_dois_to_openalex_ids(dois_to_resolve)
    except httpx.HTTPError as exc:
        raise NetworkError(
            f"Error de red al resolver DOIs contra OpenAlex: {exc}. "
            "Verificá la conexión o reintentá más tarde."
        ) from exc

    if not doi_to_source_id:
        return {
            "resolved": 0,
            "total_with_doi": total_with_doi,
            "already_resolved": already_resolved,
            "total_papers": total_papers,
        }

    resolved_count = 0
    resolved_ids: list[str] = []
    for row in rows:
        if row.get(Col.SOURCE_ID) is not None:
            continue  # ya tiene source_id; no tocar
        doi = row.get(Col.DOI)
        if not doi:
            continue
        doi_norm = _normalize_doi(doi)
        if doi_norm and doi_norm in doi_to_source_id:
            row[Col.SOURCE_ID] = doi_to_source_id[doi_norm]
            resolved_ids.append(row[Col.ID])
            resolved_count += 1

    updated_table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    updated_corpus = Corpus.from_arrow(updated_table)
    backend_close = getattr(updated_corpus._backend, "close", None)
    try:
        store.persist_replace(updated_corpus)
        # Solo las filas recién resueltas (resolve_dois es API pública y no pasa
        # por el guard de proveedor): el resto no se asume de OpenAlex.
        if resolved_ids:
            store.register_external_ids(
                Corpus.from_arrow(
                    updated_table.filter(
                        pc.is_in(  # type: ignore[attr-defined]
                            updated_table[Col.ID],
                            value_set=pa.array(resolved_ids, type=pa.string()),
                        )
                    )
                ),
                Provider.OPENALEX,
            )
    finally:
        # Cerrar el backend en memoria del corpus actualizado (InMemoryBackend
        # no tiene close(), DuckDBBackend sí; este backend es distinto del
        # backend del store — es el InMemoryBackend de Corpus.from_arrow).
        if backend_close is not None:
            backend_close()

    return {
        "resolved": resolved_count,
        "total_with_doi": total_with_doi,
        "already_resolved": already_resolved,
        "total_papers": total_papers,
    }


def resolve_dois(
    store_path: str | Path,
    *,
    email: str | None = None,
    transport: Any = None,
    provider: Provider | str = DEFAULT_PROVIDER,
) -> dict[str, Any]:
    """Resuelve DOIs pendientes a source_id de OpenAlex y persiste.

    Filtra los papers del corpus que tienen ``doi`` no nulo y ``source_id``
    nulo, consulta OpenAlex para resolver DOI→source_id (batcheado), y
    actualiza las filas correspondientes.  Persiste con ``persist_replace``.

    Idempotente: papers que ya tienen ``source_id`` no se tocan; volver a
    correr produce el mismo resultado.

    Usa filtrado Python puro (no ``pyarrow.compute``) para evitar las
    dependencias de stubs que mypy no puede resolver.

    Esta función abre y cierra su propio store.  Para el camino encadenado
    ``seed --from-bib --resolve`` (mismo proceso), usá ``_resolve_dois_on_store``
    directamente pasando el store ya abierto, evitando el reopen que causaba
    segfault (#110, #93).

    Args:
        store_path: Ruta al archivo ``.duckdb``.
        email: Email para el polite pool de OpenAlex (recomendado).
        transport: Transport inyectable para tests (``httpx.MockTransport``).

    Returns:
        Dict con:
          - ``resolved``: cantidad de papers a los que se les pobló source_id.
          - ``total_with_doi``: cantidad de papers con doi en el corpus.
          - ``already_resolved``: papers con doi que ya tenían source_id.
          - ``total_papers``: total de papers en el corpus.

    Raises:
        NetworkError: Si falla la conexión a OpenAlex.
        StoreError: Si el store está bloqueado.
    """
    path = Path(store_path)
    store = _open_writable(path, provider)
    try:
        return _resolve_dois_on_store(store, email=email, transport=transport)
    finally:
        store.close()
