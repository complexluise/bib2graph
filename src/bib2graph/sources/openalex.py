"""openalex — ``OpenAlexSource``: siembra desde la API de OpenAlex.

Implementa el backbone de datos de la V1 (ADR 0007).  No depende de
``pyalex`` (registro-ia 0.1); toda la I/O usa ``httpx`` (núcleo).

Decisiones de implementación:
- Traducción PASSTHROUGH: envuelve la ecuación en
  ``title_and_abstract.search:(...)``.  Detecta y reporta límites (NEAR,
  comodines, tags WoS) sin abortar.
- Paginación por cursor (``per_page=100``) con tope ``max_results``.
- ``cited_by_id`` queda ``[]`` en seed (no viene inline; lo puebla el
  Enricher en Hito 8).  ``references_id`` SÍ se trae (``referenced_works``).
- ``openalex_version`` del ``Manifest`` = fecha ISO del snapshot de OpenAlex
  en la respuesta (cabecera ``x-openalex-api-version``), o fecha de fetch
  como ancla mínima (ADR 0017).
- Credenciales inyectadas: ``email`` (pool cortés) + ``api_key`` opcional.
  Resolución: arg > entorno ``OPENALEX_API_KEY`` > ausencia → polite pool
  (ADR 0012).

Ver ``docs/API.md`` §2, ADR 0007/0012/0017/0018.
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import UTC, datetime
from typing import Any

import httpx
import pyarrow as pa

from bib2graph.constants import Col, CurationStatus
from bib2graph.corpus import Corpus, EquationRef, _rows_with_ids
from bib2graph.schemas import CORPUS_SCHEMA, ProvenanceEvent

from .base import SeedResult

# ---------------------------------------------------------------------------
# Constantes internas
# ---------------------------------------------------------------------------

_BASE_URL = "https://api.openalex.org"
_FIELDS = ",".join(
    [
        "id",
        "doi",
        "title",
        "display_name",
        "publication_year",
        "language",
        "abstract_inverted_index",
        "authorships",
        "keywords",
        "referenced_works",
        "primary_location",
        "type",
    ]
)

# Patrones que disparan límites documentados (ADR 0007)
_RE_NEAR = re.compile(r"\bNEAR/\d+\b", re.IGNORECASE)
_RE_WILDCARD = re.compile(r"\*")
_RE_WOS_TAG = re.compile(r"\b(TS|AB|TI|AU|SO|LA|DT|WC|SU)=", re.IGNORECASE)

# R5 — retry/backoff: parámetros para reintentos ante 429/5xx en fetch_citing.
# El seed/load no usa retry (son llamadas únicas al usuario, con cursor paging;
# si fallan el usuario puede reintentar el comando completo).
_RETRY_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})
_RETRY_MAX_ATTEMPTS: int = 3
_RETRY_BACKOFF_BASE: float = 1.0  # segundos; duplica por cada intento


# ---------------------------------------------------------------------------
# Traducción de ecuación (función pura, sin I/O)
# ---------------------------------------------------------------------------


def _translate(
    query: str,
    *,
    native: bool = False,
    exclude: list[str] | None = None,
) -> tuple[str, list[str]]:
    """Traduce una ecuación WoS-style a una query OpenAlex ejecutable.

    Si ``native=True`` pasa la query cruda sin ningún procesamiento (las
    exclusiones se ignoran en modo nativo).

    Detecta y reporta límites de OpenAlex (ADR 0007) sin abortar:
    - ``NEAR/n``: proximidad no soportada.
    - Comodín ``*``: comportamiento distinto al de WoS.
    - Tags de campo WoS (``TS=``, ``AB=``, ``AU=``…): no mapean 1:1.

    Las exclusiones (``exclude``) añaden cláusulas
    ``AND NOT title_and_abstract.search:"<término>"`` al final del filtro y
    se reportan en el translation_report para transparencia (PRD §4).

    Args:
        query: Ecuación de búsqueda.
        native: Si es ``True``, no traducir; usar query cruda.
        exclude: Lista de términos a excluir de título/abstract.  Cada uno
            genera una cláusula ``AND NOT title_and_abstract.search:"…"``.
            ``None`` o lista vacía = sin exclusiones.

    Returns:
        Tupla ``(executed_query, translation_report)``.
    """
    report: list[str] = []

    if native:
        return query, ["query nativa OpenAlex, sin traducción"]

    # Detectar límites y acumular reporte
    if _RE_NEAR.search(query):
        report.append(
            "Límite ADR-0007: NEAR/n no soportado en OpenAlex; "
            "se aproxima con AND (puede aumentar el recall)."
        )
    if _RE_WILDCARD.search(query):
        report.append(
            "Límite ADR-0007: comodín '*' tiene comportamiento distinto "
            "en OpenAlex que en WoS (revisa el reporte de resultados)."
        )
    if _RE_WOS_TAG.search(query):
        report.append(
            "Límite ADR-0007: tags de campo WoS (TS=, AB=, AU=…) no "
            "mapean 1:1 en OpenAlex; se descartaron del filtro de campo."
        )

    # Envolver en el filtro de OpenAlex (PASSTHROUGH)
    executed = f"title_and_abstract.search:({query})"

    # Negaciones: cada término excluido agrega una cláusula AND NOT (#30).
    # Las comillas internas se eliminan para no romper la frase entrecomillada
    # en el filtro de OpenAlex (un `"` embebido cierra la frase antes de tiempo).
    terms = [t.strip().replace('"', "") for t in (exclude or []) if t and t.strip()]
    if terms:
        not_clauses = " ".join(
            f'AND NOT title_and_abstract.search:"{t}"' for t in terms
        )
        executed = f"{executed} {not_clauses}"
        report.append(
            f"Exclusiones aplicadas ({len(terms)}): "
            + ", ".join(f'"{t}"' for t in terms)
            + ". Cláusulas AND NOT añadidas al filtro de OpenAlex."
        )

    return executed, report


# ---------------------------------------------------------------------------
# Helpers de mapeo JSON → fila del Corpus
# ---------------------------------------------------------------------------


def _reconstruct_abstract(inv_index: dict[str, list[int]] | None) -> str | None:
    """Reconstruye el abstract desde el índice invertido de OpenAlex.

    Args:
        inv_index: Diccionario ``{palabra: [posiciones]}``, o ``None``.

    Returns:
        Texto del abstract, o ``None`` si no hay índice.
    """
    if not inv_index:
        return None
    max_pos = max((p for ps in inv_index.values() for p in ps), default=-1)
    if max_pos < 0:
        return None
    out: list[str] = [""] * (max_pos + 1)
    for word, positions in inv_index.items():
        for p in positions:
            out[p] = word
    return " ".join(out).strip() or None


def _normalize_doi(raw: str | None) -> str | None:
    """Quita el prefijo URL del DOI y lo devuelve en minúsculas.

    Args:
        raw: DOI crudo (puede ser URL completa o None).

    Returns:
        DOI normalizado o ``None``.
    """
    if not raw:
        return None
    doi = raw
    for prefix in ("https://doi.org/", "http://doi.org/"):
        if doi.startswith(prefix):
            doi = doi[len(prefix) :]
            break
    return doi.lower() or None


def _oa_id_short(url: str | None) -> str | None:
    """Extrae el ID corto de OpenAlex de una URL (p. ej. ``W12345``).

    Args:
        url: URL completa de OpenAlex o ID corto directo.

    Returns:
        Segmento final de la URL, o ``None``.
    """
    if not url:
        return None
    return url.rsplit("/", 1)[-1] or None


def _work_to_row(
    work: dict[str, Any],
    *,
    equation_id: str,
    fetched_at: str,
) -> dict[str, Any]:
    """Mapea un objeto JSON de OpenAlex a la fila del schema canónico.

    Acceso defensivo con ``.get()`` en cadena (AGENTS.md).  Los campos de
    enriquecimiento (``authors_affiliations``, ``references_id``) se extraen
    con la misma estrategia; ``cited_by_id`` queda ``[]`` (no viene inline).

    Args:
        work: Objeto JSON de un Work de OpenAlex.
        equation_id: ID de la ecuación que originó la búsqueda (para provenance).
        fetched_at: Timestamp ISO de la consulta.

    Returns:
        Dict con todas las columnas del schema canónico.
    """
    # --- Identificadores ---
    openalex_id = _oa_id_short(work.get("id"))
    doi = _normalize_doi(work.get("doi"))

    # --- Autores y afiliaciones ---
    authorships: list[dict[str, Any]] = work.get("authorships") or []
    authors_raw: list[str] = []
    authors_id: list[str] = []
    authors_affiliations: list[str] = []

    for authorship in authorships:
        author: dict[str, Any] = authorship.get("author") or {}
        name = author.get("display_name") or ""
        if name:
            authors_raw.append(name)
        # ORCID o URL de OpenAlex → segmento final
        au_id = (
            _oa_id_short(author.get("orcid") or author.get("id")) or name or "unknown"
        )
        authors_id.append(au_id)
        # Afiliaciones per-autor
        for inst in authorship.get("institutions") or []:
            country = (inst.get("country_code") or "").upper() or "??"
            inst_name = inst.get("display_name") or "?"
            authors_affiliations.append(f"{inst_name} ({country})")

    # --- Instituciones únicas ---
    institutions_raw: list[str] = []
    institutions_id: list[str] = []
    seen_inst: set[str] = set()
    for authorship in authorships:
        for inst in authorship.get("institutions") or []:
            inst_name = inst.get("display_name") or ""
            inst_id = _oa_id_short(inst.get("id") or inst.get("ror")) or inst_name
            if inst_id and inst_id not in seen_inst:
                seen_inst.add(inst_id)
                if inst_name:
                    institutions_raw.append(inst_name)
                institutions_id.append(inst_id)

    # --- Keywords ---
    kws: list[dict[str, Any]] = work.get("keywords") or []
    keywords_raw = [k.get("display_name", "") for k in kws if k.get("display_name")]
    keywords_id = [
        _oa_id_short(k.get("id")) or k.get("display_name", "")
        for k in kws
        if k.get("id") or k.get("display_name")
    ]

    # --- Referencias (``referenced_works`` = URLs de OpenAlex) ---
    ref_urls: list[str] = work.get("referenced_works") or []
    references_id = [_oa_id_short(r) for r in ref_urls if r]
    # Filtra posibles None (aunque _oa_id_short solo devuelve None si la URL
    # es vacía, lo cual no ocurre en la lista anterior)
    references_id_clean: list[str] = [r for r in references_id if r]

    # --- Venue / source ---
    primary_loc: dict[str, Any] = work.get("primary_location") or {}
    loc_source: dict[str, Any] = primary_loc.get("source") or {}
    venue = loc_source.get("display_name")

    # --- Provenance (evento inicial) ---
    provenance_event = ProvenanceEvent(
        action="fetched",
        equation_id=equation_id,
        chaining_hop=None,
        source="openalex",
        fetched_at=fetched_at,
        decided_by=None,
        decided_at=None,
    )

    return {
        # id se calcula en Corpus.add_paper (D1)
        Col.OPENALEX_ID: openalex_id,
        Col.DOI: doi,
        Col.TITLE: work.get("title") or work.get("display_name") or "",
        Col.YEAR: work.get("publication_year"),
        Col.ABSTRACT: _reconstruct_abstract(work.get("abstract_inverted_index")),
        Col.SOURCE: venue,
        Col.LANGUAGE: work.get("language"),
        Col.PUBLISHER: None,
        Col.RESEARCH_AREAS: None,
        Col.IS_SEED: True,
        Col.CURATION_STATUS: CurationStatus.CANDIDATE,
        Col.PROVENANCE: ProvenanceEvent.dump_list([provenance_event]),
        Col.AUTHORS_RAW: authors_raw or None,
        Col.AUTHORS_ID: authors_id or None,
        Col.AUTHORS_AFFILIATIONS: authors_affiliations or None,
        Col.KEYWORDS_RAW: keywords_raw or None,
        Col.KEYWORDS_ID: keywords_id or None,
        Col.INSTITUTIONS_RAW: institutions_raw or None,
        Col.INSTITUTIONS_ID: institutions_id or None,
        Col.REFERENCES_ID: references_id_clean or None,
        Col.REFERENCES_DOI: None,
        Col.CITED_BY_ID: [],
    }


# ---------------------------------------------------------------------------
# OpenAlexSource
# ---------------------------------------------------------------------------


class OpenAlexSource:
    """Siembra un ``Corpus`` desde la API de OpenAlex.

    Ejemplo::

        source = OpenAlexSource(email="yo@example.com")
        result = source.seed('"unequal exchange" AND trade')
        print(result.executed_query)
        print(result.translation_report)

    Credenciales (ADR 0012): ``email`` y ``api_key`` se inyectan; nunca
    embebidos en el código. Resolución: argumento > ``OPENALEX_API_KEY`` >
    ausencia → polite pool.

    El ``transport`` permite pasar un ``httpx.MockTransport`` en tests (sin
    red en CI).
    """

    def __init__(
        self,
        *,
        email: str | None = None,
        api_key: str | None = None,
        transport: httpx.BaseTransport | None = None,
        base_url: str = _BASE_URL,
        max_results: int = 200,
    ) -> None:
        """Inicializa el source.

        Args:
            email: Email del pool cortés (recomendado; sin él → pool anónimo).
            api_key: API key opcional (mejora el rate limit; ADR 0012).
            transport: Transport de httpx (inyectar ``MockTransport`` en tests).
            base_url: URL base de la API (default producción).
            max_results: Tope de resultados por llamada a ``seed()``.
        """
        self._email = email
        # Resolución de api_key: argumento > entorno > ausencia
        self._api_key = api_key or os.environ.get("OPENALEX_API_KEY")
        self._base_url = base_url.rstrip("/")
        self._max_results = max_results
        self._transport = transport

    # ------------------------------------------------------------------
    # Construcción del cliente httpx
    # ------------------------------------------------------------------

    def _client(self) -> httpx.Client:
        """Construye el cliente httpx con las credenciales inyectadas.

        Returns:
            ``httpx.Client`` configurado.
        """
        headers: dict[str, str] = {}
        params: dict[str, str] = {}
        if self._email:
            params["mailto"] = self._email
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        if self._transport is not None:
            return httpx.Client(
                transport=self._transport,
                base_url=self._base_url,
                headers=headers,
                params=params,
            )
        return httpx.Client(
            base_url=self._base_url,
            headers=headers,
            params=params,
        )

    # ------------------------------------------------------------------
    # Paginación con cursor
    # ------------------------------------------------------------------

    def _fetch_all(self, filter_str: str) -> tuple[list[dict[str, Any]], str | None]:
        """Recupera works de OpenAlex paginando con cursor.

        ``cited_by_id`` no viene inline: se deja para el Enricher (Hito 8).
        ``references_id`` sí se trae vía ``referenced_works``.

        Args:
            filter_str: Valor del parámetro ``filter`` de la API.

        Returns:
            Tupla ``(works, openalex_version)`` donde ``openalex_version``
            es el valor de la cabecera ``x-openalex-api-version`` (o la
            fecha ISO de fetch si no viene).
        """
        works: list[dict[str, Any]] = []
        cursor = "*"
        openalex_version: str | None = None
        fetched_at = datetime.now(UTC).isoformat()

        with self._client() as client:
            while len(works) < self._max_results:
                remaining = self._max_results - len(works)
                per_page = min(100, remaining)
                resp = client.get(
                    "/works",
                    params={
                        "filter": filter_str,
                        "select": _FIELDS,
                        "per_page": per_page,
                        "cursor": cursor,
                    },
                )
                resp.raise_for_status()

                # Ancla de versión OpenAlex (ADR 0017)
                if openalex_version is None:
                    openalex_version = resp.headers.get(
                        "x-openalex-api-version", fetched_at
                    )

                data: dict[str, Any] = resp.json()
                page_works: list[dict[str, Any]] = data.get("results") or []
                works.extend(page_works)

                meta: dict[str, Any] = data.get("meta") or {}
                next_cursor: str | None = meta.get("next_cursor")
                if not next_cursor or not page_works:
                    break
                cursor = next_cursor

        return works[: self._max_results], openalex_version or fetched_at

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def seed(
        self,
        query: str,
        *,
        native: bool = False,
        exclude: list[str] | None = None,
    ) -> SeedResult:
        """Siembra un ``Corpus`` desde una ecuación de búsqueda.

        ``cited_by_id`` queda ``[]`` en el corpus sembrado: OpenAlex no lo
        entrega inline; lo pueblan el Forager/Enricher en Hito 5/8.
        ``references_id`` SÍ se trae inline (``referenced_works``).

        Args:
            query: Ecuación de búsqueda (WoS-style o nativa OpenAlex).
            native: Si es ``True``, pasa la query cruda sin traducción.
            exclude: Lista de términos a excluir de título/abstract (#30).
                Cada término genera ``AND NOT title_and_abstract.search:"…"``.

        Returns:
            ``SeedResult`` con el corpus, la query ejecutada y el reporte.
        """
        executed_query, translation_report = _translate(
            query, native=native, exclude=exclude
        )
        equation_id = f"eq-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}"
        fetched_at = datetime.now(UTC).isoformat()

        works, openalex_version = self._fetch_all(executed_query)

        # R5: bulk-load — construir tabla Arrow de una vez en vez de N add_paper/clone.
        rows = [
            _work_to_row(work, equation_id=equation_id, fetched_at=fetched_at)
            for work in works
        ]
        rows_with_ids = _rows_with_ids(rows)
        if rows_with_ids:
            table = pa.Table.from_pylist(rows_with_ids, schema=CORPUS_SCHEMA)
        else:
            table = pa.table(
                {col: [] for col in CORPUS_SCHEMA.names},
                schema=CORPUS_SCHEMA,
            )
        corpus = Corpus.from_arrow(table)

        # Actualizar Manifest con openalex_version y ecuación (ADR 0017)
        updated_manifest = corpus.manifest.model_copy(
            update={
                "openalex_version": openalex_version,
                "equations": [
                    EquationRef(
                        equation_id=equation_id,
                        query=executed_query,
                        translation_report=translation_report,
                    )
                ],
            }
        )
        # Sustituir el manifest en el corpus usando la API pública
        result_corpus = corpus.with_manifest(updated_manifest)

        return SeedResult(
            corpus=result_corpus,
            executed_query=executed_query,
            translation_report=translation_report,
        )

    def _fetch_all_with_retry(
        self, filter_str: str
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Como ``_fetch_all`` pero con retry/backoff ante 429/5xx.

        R5: el forward chaining hace N+1 requests (una por paper); sin retry
        ante rate-limit (429) o errores transitorios de servidor (5xx), un
        corpus mediano falla silenciosamente.  Este método implementa
        exponential backoff con ``_RETRY_MAX_ATTEMPTS`` intentos.

        No duerme en tests: el ``time.sleep`` está en el código de producción;
        los tests usan ``MockTransport`` que puede simular 429 → 200 sin delays
        reales (el test puede patchear ``time.sleep`` si necesita velocidad).

        Args:
            filter_str: Valor del parámetro ``filter`` de la API.

        Returns:
            Tupla ``(works, openalex_version)`` con retry/backoff.

        Raises:
            httpx.HTTPStatusError: Si se agotan los reintentos.
        """
        last_exc: Exception | None = None
        for attempt in range(_RETRY_MAX_ATTEMPTS):
            try:
                return self._fetch_all(filter_str)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in _RETRY_STATUS_CODES:
                    last_exc = exc
                    wait = _RETRY_BACKOFF_BASE * (2**attempt)
                    time.sleep(wait)
                else:
                    raise  # error no retryable: propagar inmediatamente
        # Se agotaron los reintentos
        assert last_exc is not None
        raise last_exc

    def fetch_citing(self, openalex_id: str) -> list[dict[str, Any]]:
        """Trae los works que citan al paper con ``openalex_id`` dado.

        Usa ``GET /works?filter=cites:{openalex_id}`` con paginación por
        cursor, reutilizando el cliente httpx y ``_work_to_row``.  Es el
        mecanismo del forward chaining (Hito 5, ADR 0008).

        R5: agrega retry/backoff ante 429/5xx (``_fetch_all_with_retry``).
        Sin esto, un corpus mediano falla en el forward chaining con un rate
        limit de OpenAlex (Nota 06, RAÍZ 3).

        Calcula el ``id`` canónico (D1) de cada citante antes de devolverlo,
        de modo que los consumidores de estas filas (``Forager``,
        ``compute_forward_scent``) pueden identificar los candidatos.

        Args:
            openalex_id: ID corto de OpenAlex (p. ej. ``W12345``).

        Returns:
            Lista de dicts con el schema canónico de filas del Corpus
            (misma estructura que produce ``_work_to_row`` + ``id`` calculado),
            con ``is_seed=False`` y provenance ``chaining_hop=1``.
        """
        from bib2graph.corpus import _compute_id

        filter_str = f"cites:{openalex_id}"
        fetched_at = datetime.now(UTC).isoformat()
        equation_id = f"chaining:forward:{openalex_id}"

        # R5: retry/backoff ante 429/5xx
        works, _ = self._fetch_all_with_retry(filter_str)
        rows: list[dict[str, Any]] = []
        for work in works:
            row = _work_to_row(work, equation_id=equation_id, fetched_at=fetched_at)
            # Sobrescribir is_seed y provenance para forward chaining
            row[Col.IS_SEED] = False
            provenance_event = ProvenanceEvent(
                action="fetched",
                equation_id=None,
                chaining_hop=1,
                source="openalex",
                fetched_at=fetched_at,
                decided_by=None,
                decided_at=None,
            )
            row[Col.PROVENANCE] = ProvenanceEvent.dump_list([provenance_event])
            # Calcular id canónico (D1) para que Forager y compute_forward_scent
            # puedan identificar el candidato
            row["id"] = _compute_id(
                openalex_id=row.get("openalex_id"),
                doi=row.get("doi"),
                title=str(row.get("title") or ""),
                year=row.get("year"),
            )
            rows.append(row)
        return rows

    def fetch_dois_for(self, ids: list[str]) -> dict[str, str]:
        """Resuelve una lista de IDs de OpenAlex a sus DOIs.

        Batchea la consulta en lotes de hasta 100 IDs por request, usando el
        filtro ``openalex_id:W1|W2|...`` con ``select=id,doi``.  Reutiliza el
        retry/backoff de ``_fetch_all_with_retry`` para resiliencia ante 429/5xx.

        Diseñado para el ``OpenAlexEnricher`` (Hito 8a): mantiene la frontera
        núcleo/costura — el Source hace la I/O; el Enricher orquesta.

        Hito 8b (futuro): el mismo patrón sirve para resolver
        ``cited_by_id``; el Enricher solo necesita un método distinto o un
        argumento adicional.

        Args:
            ids: Lista de IDs cortos de OpenAlex (p. ej. ``["W12345", "W67890"]``).
                Se acepta con o sin prefijo URL; se normalizan a ID corto.

        Returns:
            Dict ``{openalex_id: doi}`` con los DOIs encontrados.  Los IDs
            sin DOI en OpenAlex simplemente no aparecen en el resultado.
        """
        if not ids:
            return {}

        # Normalizar IDs a la forma corta (W...) por si vienen como URL
        normalized = [_oa_id_short(i) or i for i in ids]

        resultado: dict[str, str] = {}
        batch_size = 100

        for start in range(0, len(normalized), batch_size):
            lote = normalized[start : start + batch_size]
            # Filtro OR de OpenAlex: openalex_id:W1|W2|...
            filter_str = "openalex_id:" + "|".join(lote)

            # Usamos el cliente directamente con select acotado (id + doi)
            # en lugar de _fetch_all para no traer todos los campos.
            works = self._fetch_batch_select(filter_str, select="id,doi")

            for work in works:
                raw_id = work.get("id")
                raw_doi = work.get("doi")
                if raw_id and raw_doi:
                    short_id = _oa_id_short(raw_id)
                    doi = _normalize_doi(raw_doi)
                    if short_id and doi:
                        resultado[short_id] = doi

        return resultado

    def _fetch_batch_select(
        self, filter_str: str, *, select: str
    ) -> list[dict[str, Any]]:
        """Recupera works de OpenAlex con un ``select`` acotado y retry/backoff.

        A diferencia de ``_fetch_all``, no pagina por cursor: está pensado
        para lotes de IDs (≤100) donde la respuesta cabe en una sola página.
        Reutiliza el retry/backoff via la lógica interna de ``_fetch_all_with_retry``
        adaptada para el parámetro ``select`` personalizado.

        Args:
            filter_str: Valor del parámetro ``filter`` de la API.
            select: Campos a traer (p. ej. ``"id,doi"``).

        Returns:
            Lista de objetos JSON retornados por la API.

        Raises:
            httpx.HTTPStatusError: Si se agotan los reintentos.
        """
        last_exc: Exception | None = None
        for attempt in range(_RETRY_MAX_ATTEMPTS):
            try:
                with self._client() as client:
                    resp = client.get(
                        "/works",
                        params={
                            "filter": filter_str,
                            "select": select,
                            "per_page": 100,
                        },
                    )
                    resp.raise_for_status()
                    data: dict[str, Any] = resp.json()
                    return data.get("results") or []
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in _RETRY_STATUS_CODES:
                    last_exc = exc
                    wait = _RETRY_BACKOFF_BASE * (2**attempt)
                    time.sleep(wait)
                else:
                    raise
        assert last_exc is not None
        raise last_exc

    def fetch_citing_batch(
        self, ids: list[str], *, max_per_paper: int | None = None
    ) -> dict[str, list[str]]:
        """Trae en lote los citantes de varios papers usando ``cites:W1|W2|...``.

        Reemplaza N llamadas individuales a ``fetch_citing`` (patrón N+1) por una
        sola request por lote (≤50 IDs, límite empírico de OpenAlex para OR en
        ``cites:``).  Preserva el retry/backoff de ``_fetch_all_with_retry``.

        **Presupuesto por semilla (anti-starvation):** pagina con cursor sobre el
        filtro OR del lote y, página a página, atribuye cada citante a las semillas
        objetivo cruzando ``references_id`` del citante con el set de IDs.  Lleva
        un contador por semilla y deja de paginar cuando TODAS las semillas del
        lote alcanzaron ``max_per_paper`` citantes (o se agota la paginación).
        Así la semilla más citada no consume el presupuesto de las demás.

        El filtro ``cites:W1|W2`` es un OR válido en la API de OpenAlex: devuelve
        todos los works que citan al menos uno de los IDs listados.

        Args:
            ids: Lista de IDs cortos de OpenAlex (p. ej. ``["W111", "W222"]``).
                Se normalizan a ID corto internamente.
            max_per_paper: Presupuesto máximo de citantes a recolectar por semilla.
                ``None`` = sin tope (pagina todo).  Acota el fetch: cuando todas
                las semillas del lote alcanzan el tope, se detiene la paginación.

        Returns:
            Dict ``{seed_id: [citer_id, ...]}``.  Los citantes de cada semilla
            ya están atribuidos (cruzando ``references_id`` del citante) y
            acotados a ``max_per_paper``.  Los IDs de citantes son los IDs cortos
            de OpenAlex.  Orden determinista (alfabético).
        """
        if not ids:
            return {}

        normalized = [_oa_id_short(i) or i for i in ids]
        batch_size = 50  # límite empírico de OpenAlex para OR en cites:

        result: dict[str, list[str]] = {}

        for start in range(0, len(normalized), batch_size):
            lote = normalized[start : start + batch_size]
            lote_set = set(lote)
            # Acumulador de sets para idempotencia interna (elimina dupes entre páginas)
            batch_acc: dict[str, set[str]] = {tid: set() for tid in lote}

            # Filtro OR: cites:W1|W2 es un OR válido en OpenAlex (devuelve works que
            # citan al menos uno de los IDs; no requiere repetir el predicado por ID).
            filter_str = "cites:" + "|".join(lote)

            # Paginar con cursor, atribuyendo página a página con presupuesto por semilla
            cursor: str = "*"
            with self._client() as client:
                while True:
                    # Verificar si todas las semillas del lote ya están satisfechas
                    if max_per_paper is not None and all(
                        len(batch_acc[tid]) >= max_per_paper for tid in lote
                    ):
                        break

                    # Fetch con retry/backoff
                    page_works = self._fetch_page_with_retry(
                        client, filter_str, cursor=cursor
                    )
                    if page_works is None:
                        # Error irrecuperable tras reintentos (ya propagado)
                        break  # pragma: no cover

                    works_list, next_cursor = page_works

                    # Atribuir cada citante de la página a los seeds que realmente cita
                    for work in works_list:
                        citer_oa_id = _oa_id_short(work.get("id"))
                        if not citer_oa_id:
                            continue
                        ref_urls: list[str] = work.get("referenced_works") or []
                        citer_refs: set[str] = {
                            short
                            for r in ref_urls
                            if r and (short := _oa_id_short(r)) is not None
                        }
                        # Intersección: seeds que este citante realmente cita
                        for tid in lote_set & citer_refs:
                            if (
                                max_per_paper is None
                                or len(batch_acc[tid]) < max_per_paper
                            ):
                                batch_acc[tid].add(citer_oa_id)

                    if not next_cursor or not works_list:
                        break
                    cursor = next_cursor

            # Consolidar en el resultado global (orden determinista: alfabético)
            for tid in lote:
                existing = set(result.get(tid) or [])
                merged = existing | batch_acc[tid]
                if max_per_paper is not None:
                    result[tid] = sorted(merged)[:max_per_paper]
                else:
                    result[tid] = sorted(merged)

        return result

    def _fetch_page_with_retry(
        self,
        client: httpx.Client,
        filter_str: str,
        *,
        cursor: str,
        per_page: int = 100,
    ) -> tuple[list[dict[str, Any]], str | None] | None:
        """Recupera una página de works con retry/backoff ante 429/5xx.

        Comparte la lógica de retry de ``_RETRY_MAX_ATTEMPTS`` y
        ``_RETRY_BACKOFF_BASE`` sin reimplementar el bucle de backoff.

        Args:
            client: Cliente httpx ya abierto (reutilizado para conexión persistente).
            filter_str: Valor del parámetro ``filter`` de la API.
            cursor: Cursor de paginación (``"*"`` para la primera página).
            per_page: Tamaño de página (máx. 100 en OpenAlex).

        Returns:
            Tupla ``(works, next_cursor)`` si la página se obtuvo correctamente,
            o ``None`` si se agotaron los reintentos (este caso no debería ocurrir
            porque re-raise al agotar reintentos).

        Raises:
            httpx.HTTPStatusError: Si se agotan los reintentos.
        """
        last_exc: Exception | None = None
        for attempt in range(_RETRY_MAX_ATTEMPTS):
            try:
                resp = client.get(
                    "/works",
                    params={
                        "filter": filter_str,
                        "select": _FIELDS,
                        "per_page": per_page,
                        "cursor": cursor,
                    },
                )
                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
                works: list[dict[str, Any]] = data.get("results") or []
                meta: dict[str, Any] = data.get("meta") or {}
                next_cursor: str | None = meta.get("next_cursor")
                return works, next_cursor
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in _RETRY_STATUS_CODES:
                    last_exc = exc
                    wait = _RETRY_BACKOFF_BASE * (2**attempt)
                    time.sleep(wait)
                else:
                    raise
        assert last_exc is not None
        raise last_exc

    def load(self, path: str) -> Corpus:
        """Carga un export JSON de OpenAlex como ``Corpus``.

        Cada objeto del array JSON se trata como un Work de OpenAlex y se
        mapea al schema canónico con ``is_seed=True``.

        Args:
            path: Ruta al archivo JSON (array de Works).

        Returns:
            ``Corpus`` con los papers cargados.
        """
        from pathlib import Path

        data: list[dict[str, Any]] = json.loads(Path(path).read_text(encoding="utf-8"))
        fetched_at = datetime.now(UTC).isoformat()
        equation_id = "load"

        # R5: bulk-load — construir tabla Arrow de una vez en vez de N add_paper/clone.
        rows = [
            _work_to_row(work, equation_id=equation_id, fetched_at=fetched_at)
            for work in data
        ]
        rows_with_ids = _rows_with_ids(rows)
        if rows_with_ids:
            table = pa.Table.from_pylist(rows_with_ids, schema=CORPUS_SCHEMA)
        else:
            table = pa.table(
                {col: [] for col in CORPUS_SCHEMA.names},
                schema=CORPUS_SCHEMA,
            )
        return Corpus.from_arrow(table)
