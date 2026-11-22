"""semanticscholar — ``SemanticScholarSource``: siembra desde la Academic
Graph API de Semantic Scholar (S2).

2º backbone real (ADR 0042), válida empíricamente la tesis de intercambiabilidad
de motores de ADR 0036/0018: el núcleo no se toca, S2 es "una ``Source`` nueva".
Toda la I/O usa ``httpx`` (núcleo); no depende de un SDK de S2.

Divergencias S2↔OpenAlex (ADR 0042, no copiar a ciegas de ``openalex.py``):
- **Auth**: header ``x-api-key`` (no ``Authorization: Bearer``), sin email/mailto.
- **Asimetría de credenciales por rol (D2)**: ``seed()`` (``/paper/search``)
  prácticamente exige ``api_key`` (429 sostenido sin ella); el forrajeo/
  materialización (``/paper/batch``, ``/paper/{id}/citations``) funciona sin key
  a bajo volumen. Esto dobla —no rompe— el principio de ADR 0012.
- **Sin traducción WoS→S2 (D3)**: ``seed(query)`` pasa la query nativa tal cual;
  ``translation_report`` lo declara honesto (sin capa ``_translate`` análoga a
  OpenAlex).
- **Citantes directos**: ``GET /paper/{id}/citations`` devuelve los papers
  citantes ya resueltos (campo ``citingPaper``); no hace falta el truco de
  OpenAlex de cruzar ``cites:W1|W2`` con ``references_id``. No hay OR-batch en
  S2: se itera por ID, acotando con ``max_per_paper`` (presupuesto trivial: cada
  ID ya tiene su propio tope, sin competencia entre semillas).
- **IDs**: ``paperId`` es un hash propio de S2 (no una URL); se consulta por DOI
  con el prefijo ``DOI:10.…`` (``/paper/batch`` acepta IDs heterogéneos sin
  normalización adicional).
- **Límites por endpoint**: ``/paper/batch`` ≤500 IDs por lote (no las
  constantes ≤50/≤100 de OpenAlex).
- **``keywords_raw``**: S2 no expone keywords ricas en estos endpoints; queda
  ``None`` con el grado de degradación documentado en ADR 0018-B (el scent de
  co-word se enrarece, no rompe). ``research_areas`` sí se puebla desde
  ``fieldsOfStudy``/``s2FieldsOfStudy``.

Fuera de este módulo (ADR 0042, D4/D5, explícitamente diferido):
- **Escritura de ``external_ids``**: el ``paperId`` vive en ``source_id``
  (cruza con OpenAlex vía DOI → mismo ``id`` canónico, dedup cross-motor
  gratis); la tabla lateral ``external_ids(engine="s2")`` (D4) la puebla
  ``DuckDBStore.register_external_ids`` tras cada persistencia (ADR 0053
  Corte 2, #255), no este módulo (la fuente es pura).
- **Selector CLI ``--source``**: lo cablea ``cli/_options.py`` + el registro
  ``sources/registry.py`` (ADR 0053 D1, #251).
- ``Forager`` (ADR 0053 D1.5): ``work_to_row`` expone el mapeo de un
  ``citingPaper`` (shape de ``_paper_to_row``) para que el ``Forager`` no
  dependa del mapeador de OpenAlex.

Ver ``docs/decisiones/0042-semantic-scholar-segundo-motor.md``.
"""

from __future__ import annotations

import os
import time
from datetime import UTC, date, datetime
from typing import Any

import httpx
import pyarrow as pa

from bib2graph.constants import Col, CurationStatus, Provider
from bib2graph.corpus import Corpus, EquationRef, _rows_with_ids
from bib2graph.schemas import CORPUS_SCHEMA, ProvenanceEvent, SourceKind
from bib2graph.service.errors import NetworkError
from bib2graph.sources.openalex import _normalize_doi

from .base import SeedResult

# Constantes internas

_BASE_URL = "https://api.semanticscholar.org/graph/v1"

# Fields exigidos por el contrato de seed() (D1, ADR 0042): mínimo universal +
# enriquecimiento barato. NO incluye "references" (decisión de costo + límite no
# verificado): no hay evidencia offline (tests/fixtures/ADR 0042) de que
# /paper/search acepte ese field, y traerlas en cada resultado de búsqueda no se
# justifica en la siembra. Se traen en fetch_works_by_ids / fetch_citing_*, donde
# el universo de papers ya está acotado. Las semillas quedan con
# references_id/references_doi en None hasta materializarlas por ID.
_SEARCH_FIELDS = ",".join(
    [
        "title",
        "year",
        "authors",
        "abstract",
        "externalIds",
        "fieldsOfStudy",
        "s2FieldsOfStudy",
        "referenceCount",
        "citationCount",
    ]
)

# Fields para fetch_works_by_ids / fetch_citing_*: agrega referencias (con DOI)
# para poblar references_id/references_doi en el mapeo completo.
_FULL_FIELDS = _SEARCH_FIELDS + ",references,references.externalIds"

# Retry/backoff: mismos parámetros que OpenAlexSource (ADR 0042 no decide
# valores distintos). Aplica a seed() (#287, espejo de OpenAlex) y al forrajeo.
# Si el 429/504 persiste tras agotar los reintentos, aflora NetworkError tipado.
_RETRY_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})
_RETRY_MAX_ATTEMPTS: int = 3
_RETRY_BACKOFF_BASE: float = 1.0  # segundos; duplica por cada intento

# Tope de /paper/search: offset + limit <= 1000 (límite de la API de S2).
_MAX_SEARCH_RESULTS = 1000


def _build_rate_limit_message(
    *, has_key: bool, retry_after: str | None, endpoint: str
) -> str:
    """Mensaje accionable para 429 agotado (D2, ADR 0042).

    Distingue si ya hay API key: a quien ya la pasó no se le pide una (el
    remedio es esperar/bajar el volumen); a quien no, se le nombra la key
    gratuita de S2 (no el "polite pool" de OpenAlex, ADR 0012).
    """
    msg = (
        f"Semantic Scholar respondió 429 (Too Many Requests) en {endpoint} "
        "tras agotar los reintentos. "
    )
    if has_key:
        msg += (
            "La API key ya está configurada: el límite de tasa aplica igualmente. "
            "Esperá antes de reintentar o reducí el volumen (ADR 0042). "
        )
    else:
        msg += (
            "El rol sembrador de S2 prácticamente exige una API key (ADR 0042, "
            "D2). Remedio: obtené una API key gratuita de Semantic Scholar "
            "(https://www.semanticscholar.org/product/api#api-key) y pasala via "
            "SemanticScholarSource(api_key='tu-key') o la variable de entorno "
            "S2_API_KEY. El forrajeo (fetch_works_by_ids/fetch_citing_batch) sí "
            "funciona sin key a bajo volumen. Ver ADR 0042. "
        )
    if retry_after:
        msg += f"S2 indicó Retry-After: {retry_after} (esperá ese tiempo)."
    return msg.rstrip()


def _msg_upstream_timeout_504(endpoint: str) -> str:
    """Mensaje accionable para 504 agotado (ADR 0045)."""
    return (
        f"Semantic Scholar respondió 504 (Gateway Timeout) en {endpoint} tras "
        "agotar los reintentos: la petición tardó demasiado upstream. "
        "Simplificá la query (menos términos, max_results más chico) y reintentá."
    )


# Reporte de traducción honesto (D3, ADR 0042): no hay capa WoS→S2; la query
# se ejecuta nativa.
TRANSLATION_REPORT_LINE = (
    "S2: query interpretada con sintaxis nativa de Semantic Scholar; sin traducción WoS"
)


# Helpers de mapeo JSON → fila del Corpus


def _paper_to_row(
    paper: dict[str, Any],
    *,
    equation_id: str | None,
    fetched_at: str,
    is_seed: bool = True,
    action: str = "fetched",
    chaining_hop: int | None = None,
    source_tag: str = "s2",
    source_kind: SourceKind | None = None,
) -> dict[str, Any]:
    """Mapea un objeto JSON de Semantic Scholar a la fila del schema canónico.

    Acceso defensivo con ``.get()`` en cadena (AGENTS.md), espejo funcional de
    ``openalex._work_to_row``.  El ``id`` canónico se calcula aparte (D1',
    ADR 0036) por ``_rows_with_ids``/``Corpus.add_paper``: si el paper trae
    DOI, ancla al mismo ``id`` que un paper de OpenAlex con el mismo DOI
    (dedup cross-motor gratis, ADR 0042).

    Args:
        paper: Objeto JSON de un paper de Semantic Scholar (``/paper/search``,
            ``/paper/batch`` o el ``citingPaper`` de ``/paper/{id}/citations``).
        equation_id: ID de la ecuación que originó la búsqueda (para provenance),
            o ``None`` si no aplica (forward chaining, ADR 0050 D2).
        fetched_at: Timestamp ISO de la consulta.
        is_seed: Si el paper es semilla (``True``) o candidato (``False``).
        action: Tipo de evento de provenance (``'fetched'``, ``'fetched_by_id'``).
        chaining_hop: Profundidad del chaining (1 = primera expansión), o
            ``None`` si no aplica (seed/fetch_works_by_ids).
        source_tag: Etiqueta de fuente para el evento de provenance.
            Default ``'s2'`` (token ``Provider.S2``, ADR 0053 D1.6).
        source_kind: Origen semántico del evento (ADR 0050 D2). ``seed()``
            pasa ``"seed_equation"``; ``None`` para el resto.

    Returns:
        Dict con todas las columnas del schema canónico.
    """
    external_ids: dict[str, Any] = paper.get("externalIds") or {}
    doi = _normalize_doi(external_ids.get("DOI"))
    source_id = paper.get("paperId")

    authors_list: list[dict[str, Any]] = paper.get("authors") or []
    authors_raw: list[str] = []
    authors_id: list[str] = []
    for author in authors_list:
        name = author.get("name") or ""
        if name:
            authors_raw.append(name)
        author_id = author.get("authorId")
        authors_id.append(str(author_id) if author_id else (name or "unknown"))

    # research_areas: fieldsOfStudy (lista de strings) o, si está ausente,
    # s2FieldsOfStudy[].category (más granular, puede repetir categorías).
    fields_of_study: list[str] | None = paper.get("fieldsOfStudy")
    research_areas: list[str] | None
    if fields_of_study:
        research_areas = [f for f in fields_of_study if f]
    else:
        s2_fields: list[dict[str, Any]] = paper.get("s2FieldsOfStudy") or []
        research_areas = [
            str(category) for f in s2_fields if (category := f.get("category"))
        ]
    research_areas = research_areas or None

    # keywords_raw: S2 no expone keywords ricas en estos endpoints (a diferencia
    # de OpenAlex.keywords). Se deja vacío; el scent de co-word degrada en
    # corpus mixtos OpenAlex+S2, no rompe (ADR 0018-B).
    keywords_raw = None

    references_list: list[dict[str, Any]] = paper.get("references") or []
    references_id: list[str] = []
    references_doi: list[str] = []
    for ref in references_list:
        ref_id = ref.get("paperId")
        if ref_id:
            references_id.append(ref_id)
        ref_doi = _normalize_doi((ref.get("externalIds") or {}).get("DOI"))
        if ref_doi:
            references_doi.append(ref_doi)

    provenance_event = ProvenanceEvent(
        action=action,
        equation_id=equation_id,
        chaining_hop=chaining_hop,
        source=source_tag,
        fetched_at=fetched_at,
        decided_by=None,
        decided_at=None,
        source_kind=source_kind,
    )

    return {
        # id se calcula en Corpus.add_paper / _rows_with_ids (D1', ADR 0036)
        Col.SOURCE_ID: source_id,
        Col.DOI: doi,
        Col.TITLE: paper.get("title") or "",
        Col.YEAR: paper.get("year"),
        Col.ABSTRACT: paper.get("abstract"),
        Col.SOURCE: None,
        Col.LANGUAGE: None,
        Col.PUBLISHER: None,
        Col.RESEARCH_AREAS: research_areas,
        Col.IS_SEED: is_seed,
        Col.CURATION_STATUS: CurationStatus.CANDIDATE,
        Col.PROVENANCE: ProvenanceEvent.dump_list([provenance_event]),
        Col.AUTHORS_RAW: authors_raw or None,
        Col.AUTHORS_ID: authors_id or None,
        Col.AUTHORS_AFFILIATIONS: None,
        Col.KEYWORDS_RAW: keywords_raw,
        Col.KEYWORDS_ID: None,
        Col.INSTITUTIONS_RAW: None,
        Col.INSTITUTIONS_ID: None,
        Col.REFERENCES_ID: references_id or None,
        Col.REFERENCES_DOI: references_doi or None,
        Col.CITED_BY_ID: [],
    }


def _empty_corpus_table() -> pa.Table:
    """Tabla Arrow vacía con el schema canónico (helper para corpus vacío)."""
    return pa.table(
        {col: [] for col in CORPUS_SCHEMA.names},
        schema=CORPUS_SCHEMA,
    )


class SemanticScholarSource:
    """Siembra/forrajea/materializa un ``Corpus`` desde Semantic Scholar (S2).

    Ejemplo::

        source = SemanticScholarSource(api_key="tu-key")
        result = source.seed("unequal exchange ecological debt")
        print(result.executed_query)       # query nativa, sin traducción
        print(result.translation_report)   # honestidad de D3, ADR 0042

    Credenciales (ADR 0042 D2): ``api_key`` se inyecta, nunca embebida.
    Resolución: argumento > entorno ``S2_API_KEY`` > ausencia. A diferencia de
    OpenAlex (ADR 0012, ambos roles sin key), en S2 el rol **sembrador**
    (``seed()``) prácticamente exige la key (429 sostenido sin ella); el
    forrajeo/materialización (``fetch_works_by_ids``/``fetch_citing_batch``)
    funciona sin key a bajo volumen.

    El ``transport`` permite pasar un ``httpx.MockTransport`` en tests (sin
    red en CI).
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        transport: httpx.BaseTransport | None = None,
        base_url: str = _BASE_URL,
        max_results: int = 200,
    ) -> None:
        """Inicializa el source.

        Args:
            api_key: API key de Semantic Scholar (recomendada para ``seed()``;
                opcional para forrajeo/materialización). Sin email/mailto: S2
                no tiene polite pool (a diferencia de OpenAlex, ADR 0012).
            transport: Transport de httpx (inyectar ``MockTransport`` en tests).
            base_url: URL base de la API (default producción).
            max_results: Tope de resultados por llamada a ``seed()``. Debe estar
                en ``1..1000`` (límite offset+limit de ``/paper/search``).

        Raises:
            ValueError: Si ``max_results`` está fuera de ``1..1000``.
        """
        if not 1 <= max_results <= _MAX_SEARCH_RESULTS:
            raise ValueError(
                f"max_results={max_results} fuera de rango: /paper/search de "
                f"Semantic Scholar admite offset+limit <= {_MAX_SEARCH_RESULTS}; "
                f"usá un valor entre 1 y {_MAX_SEARCH_RESULTS}."
            )
        # Resolución de api_key: argumento > entorno > ausencia (D2, ADR 0042)
        self._api_key = api_key or os.environ.get("S2_API_KEY")
        self._base_url = base_url.rstrip("/")
        self._max_results = max_results
        self._transport = transport

    # Construcción del cliente httpx

    def _client(self) -> httpx.Client:
        """Construye el cliente httpx con las credenciales inyectadas.

        Auth via header ``x-api-key`` (no ``Authorization: Bearer`` como
        OpenAlex). Sin parámetro de email/mailto: S2 no tiene polite pool.

        Returns:
            ``httpx.Client`` configurado.
        """
        headers: dict[str, str] = {}
        if self._api_key:
            headers["x-api-key"] = self._api_key
        if self._transport is not None:
            return httpx.Client(
                transport=self._transport,
                base_url=self._base_url,
                headers=headers,
            )
        return httpx.Client(base_url=self._base_url, headers=headers)

    # Request con retry/backoff (compartido por seed, batch y citations)

    def _request_with_retry(
        self,
        client: httpx.Client,
        method: str,
        path: str,
        *,
        params: dict[str, Any],
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Ejecuta un request con retry/backoff ante 429/5xx.

        Returns:
            La respuesta 2xx.

        Raises:
            NetworkError: Si se agotan los reintentos con 429 (subcode
                ``RATE_LIMITED``) o 504 (``UPSTREAM_TIMEOUT``), ADR 0045.
            httpx.HTTPStatusError: Código no retryable (propaga de inmediato) o
                retryable 5xx distinto de 504 agotado.
        """
        last_exc: httpx.HTTPStatusError | None = None
        for attempt in range(_RETRY_MAX_ATTEMPTS):
            try:
                resp = client.request(method, path, params=params, json=json)
                resp.raise_for_status()
                return resp
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code not in _RETRY_STATUS_CODES:
                    raise
                last_exc = exc
                if attempt < _RETRY_MAX_ATTEMPTS - 1:
                    time.sleep(_RETRY_BACKOFF_BASE * (2**attempt))
        assert last_exc is not None
        status = last_exc.response.status_code
        endpoint = "/paper/{id}/citations" if path.endswith("/citations") else path
        if status == 429:
            raise NetworkError(
                _build_rate_limit_message(
                    has_key=bool(self._api_key),
                    retry_after=last_exc.response.headers.get("Retry-After"),
                    endpoint=endpoint,
                ),
                subcode="RATE_LIMITED",
            ) from last_exc
        if status == 504:
            raise NetworkError(
                _msg_upstream_timeout_504(endpoint), subcode="UPSTREAM_TIMEOUT"
            ) from last_exc
        raise last_exc

    # Paginación de búsqueda

    def _fetch_search(self, query: str) -> list[dict[str, Any]]:
        """Recupera papers de ``/paper/search`` paginando con offset/limit.

        Cada página se pide con retry/backoff (#287, espejo de OpenAlex).

        Args:
            query: Query nativa de S2 (sin traducción, D3).

        Returns:
            Lista de objetos JSON de papers, acotada a ``self._max_results``.
        """
        papers: list[dict[str, Any]] = []
        offset = 0
        page_size = 100  # límite de página de /paper/search

        with self._client() as client:
            while len(papers) < self._max_results:
                remaining = self._max_results - len(papers)
                limit = min(page_size, remaining)
                resp = self._request_with_retry(
                    client,
                    "GET",
                    "/paper/search",
                    params={
                        "query": query,
                        "fields": _SEARCH_FIELDS,
                        "offset": offset,
                        "limit": limit,
                    },
                )
                data: dict[str, Any] = resp.json()
                page_papers: list[dict[str, Any]] = data.get("data") or []
                papers.extend(page_papers)

                if not page_papers:
                    break
                offset += len(page_papers)
                total = data.get("total")
                if total is not None and offset >= total:
                    break

        return papers[: self._max_results]

    # API pública

    def seed(self, query: str) -> SeedResult:
        """Siembra un ``Corpus`` desde una query nativa de Semantic Scholar.

        No hay traducción WoS→S2 (D3, ADR 0042): la query se pasa tal cual a
        ``/paper/search``; ``translation_report`` lo declara honesto.

        Args:
            query: Query nativa de S2 (sintaxis propia de relevance search).

        Returns:
            ``SeedResult`` con el corpus, la query ejecutada (idéntica a
            ``query``) y el reporte de traducción (honesto: sin traducción).

        Raises:
            NetworkError: Si tras reintentar S2 responde 429
                (``subcode="RATE_LIMITED"``) o 504 (``"UPSTREAM_TIMEOUT"``).
        """
        equation_id = f"eq-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}"
        created_at = datetime.now(UTC).isoformat()
        fetched_at = created_at

        papers = self._fetch_search(query)

        translation_report = [TRANSLATION_REPORT_LINE]

        rows = [
            _paper_to_row(
                paper,
                equation_id=equation_id,
                fetched_at=fetched_at,
                source_kind="seed_equation",  # ADR 0050 D2
            )
            for paper in papers
        ]
        rows_with_ids = _rows_with_ids(rows)
        if rows_with_ids:
            table = pa.Table.from_pylist(rows_with_ids, schema=CORPUS_SCHEMA)
        else:
            table = _empty_corpus_table()
        corpus = Corpus.from_arrow(table)

        # ADR 0050 D1: ``raw_query`` es la ecuación cruda (S2 no traduce, así
        # que coincide con ``executed_query``).
        equation_params: dict[str, object] = {
            "raw_query": query,
            "max_results": self._max_results,
            "executed_query": query,
            "translation_report": translation_report,
        }
        updated_manifest = corpus.manifest.model_copy(
            update={
                "equations": [
                    EquationRef(
                        equation_id=equation_id,
                        query=query,
                        translation_report=translation_report,
                        engine=Provider.S2.value,
                        params=equation_params,
                        created_at=created_at,
                    )
                ],
            }
        )
        result_corpus = corpus.with_manifest(updated_manifest)

        return SeedResult(
            corpus=result_corpus,
            executed_query=query,
            translation_report=translation_report,
        )

    def load(self, path: str) -> Corpus:
        """No implementado: carga desde archivo S2 no soportada todavía.

        Decisión del PO: declarado explícitamente (fallar fuerte, no cablear
        un stub silencioso), no diferido en silencio. Usá ``seed()`` para
        sembrar por query o ``fetch_works_by_ids()`` para materializar IDs
        conocidos.

        Args:
            path: Ruta al archivo (sin uso; siempre lanza).

        Raises:
            NotImplementedError: Siempre.
        """
        raise NotImplementedError(
            "SemanticScholarSource: carga desde archivo S2 no soportada "
            "todavía; usá seed() para sembrar por query o "
            "fetch_works_by_ids()/fetch_citing_batch() para materializar "
            "candidatos. Ver ADR 0042."
        )

    def _fetch_batch_with_retry(self, ids: list[str]) -> list[dict[str, Any] | None]:
        """Recupera un lote de papers de ``POST /paper/batch`` con retry/backoff.

        S2 devuelve un array alineado posicionalmente con ``ids``: ``None``
        en las posiciones de IDs no encontrados (en vez de simplemente
        omitirlos como hace OpenAlex con el filtro OR).

        Args:
            ids: Hasta 500 IDs de S2 (``paperId`` o ``DOI:10.…``, sin
                normalización: S2 acepta IDs heterogéneos directamente).

        Returns:
            Lista alineada con ``ids``: objeto JSON del paper o ``None``.

        Raises:
            NetworkError: Si se agotan los reintentos con 429/504 (con subcode).
            httpx.HTTPStatusError: Otro código no retryable.
        """
        with self._client() as client:
            resp = self._request_with_retry(
                client,
                "POST",
                "/paper/batch",
                params={"fields": _FULL_FIELDS},
                json={"ids": ids},
            )
            data: list[dict[str, Any] | None] = resp.json()
            return data

    def fetch_works_by_ids(self, ids: list[str]) -> Corpus:
        """Trae papers completos de S2 a partir de una lista de IDs.

        Batchea en lotes de hasta 500 IDs (``POST /paper/batch``, límite del
        endpoint — no las constantes ≤50/≤100 de OpenAlex). Acepta IDs de S2
        (``paperId``) o por DOI con prefijo ``DOI:10.…``: S2 los resuelve sin
        normalización adicional de nuestra parte.

        Espejo funcional de ``OpenAlexSource.fetch_works_by_ids``: filas con
        ``is_seed=False``, ``curation_status=CANDIDATE``,
        ``provenance[action="fetched_by_id"]``, ordenadas por ``id`` canónico
        (determinismo, ADR 0017).

        Args:
            ids: Lista de IDs de S2 (``paperId`` o ``DOI:10.…``).

        Returns:
            ``Corpus`` con los papers encontrados. IDs inexistentes (``None``
            en la respuesta posicional de S2) se omiten sin error.
        """
        if not ids:
            return Corpus.from_arrow(_empty_corpus_table())

        fetched_at = datetime.now(UTC).isoformat()
        all_rows: list[dict[str, Any]] = []
        batch_size = 500

        for start in range(0, len(ids), batch_size):
            lote = ids[start : start + batch_size]
            papers = self._fetch_batch_with_retry(lote)
            for paper in papers:
                if not paper:
                    continue  # ID no encontrado (S2 devuelve null posicional)
                row = _paper_to_row(
                    paper,
                    equation_id="fetched_by_id",
                    fetched_at=fetched_at,
                    is_seed=False,
                    action="fetched_by_id",
                )
                all_rows.append(row)

        rows_with_ids = _rows_with_ids(all_rows)
        rows_with_ids.sort(key=lambda r: str(r.get(Col.ID, "")))

        if rows_with_ids:
            table = pa.Table.from_pylist(rows_with_ids, schema=CORPUS_SCHEMA)
        else:
            table = _empty_corpus_table()
        return Corpus.from_arrow(table)

    def _fetch_citations_page_with_retry(
        self,
        client: httpx.Client,
        paper_id: str,
        *,
        offset: int,
        limit: int,
    ) -> dict[str, Any]:
        """Recupera una página de ``GET /paper/{id}/citations`` con retry/backoff.

        Args:
            client: Cliente httpx ya abierto.
            paper_id: ID de S2 (``paperId``) del paper semilla.
            offset: Offset de paginación.
            limit: Tamaño de página.

        Returns:
            Objeto JSON de la respuesta (``{"offset", "next", "data"}``).

        Raises:
            NetworkError: Si se agotan los reintentos con 429/504 (con subcode).
            httpx.HTTPStatusError: Otro código no retryable.
        """
        resp = self._request_with_retry(
            client,
            "GET",
            f"/paper/{paper_id}/citations",
            params={"fields": _FULL_FIELDS, "offset": offset, "limit": limit},
        )
        data: dict[str, Any] = resp.json()
        return data

    def _fetch_citing_one(
        self,
        paper_id: str,
        *,
        max_per_paper: int | None,
        since: date | None,
    ) -> tuple[list[str], dict[str, dict[str, Any]]]:
        """Trae los citantes directos de un paper vía ``/paper/{id}/citations``.

        DIVERGENCIA CLAVE (ADR 0042): S2 da los citantes ya resueltos
        (``citingPaper``); no hace falta el truco de OpenAlex de cruzar
        ``cites:W1|W2`` con ``references_id``. No hay OR-batch por varios IDs
        en S2: se pagina por ID individual; el presupuesto ``max_per_paper``
        es trivialmente anti-starvation porque cada ID ya tiene su propio tope
        (sin competencia entre semillas, a diferencia del batch OR de OpenAlex).

        ``since`` se aproxima por año (S2 no expone un filtro de fecha nativo
        en este endpoint, a diferencia de ``from_publication_date`` de
        OpenAlex): se descartan citantes con ``year < since.year``.

        Args:
            paper_id: ID de S2 (``paperId``) del paper semilla.
            max_per_paper: Tope de citantes a recolectar. ``None`` = sin tope.
            since: Filtra citantes con año de publicación >= ``since.year``.
                ``None`` = sin filtro.

        Returns:
            Tupla ``(citer_ids, works_map)``: ``citer_ids`` ordenados
            alfabéticamente y acotados a ``max_per_paper``; ``works_map`` es
            ``{citer_id: citingPaper_json}`` con el objeto JSON completo de
            cada citante (campos ``_FULL_FIELDS``).
        """
        seen: set[str] = set()
        works_map: dict[str, dict[str, Any]] = {}
        offset = 0
        page_size = 100

        if max_per_paper is not None and max_per_paper <= 0:
            return [], {}

        with self._client() as client:
            while max_per_paper is None or len(seen) < max_per_paper:
                limit = page_size
                if max_per_paper is not None:
                    limit = min(page_size, max_per_paper - len(seen))
                data = self._fetch_citations_page_with_retry(
                    client, paper_id, offset=offset, limit=limit
                )
                entries: list[dict[str, Any]] = data.get("data") or []
                if not entries:
                    break

                for entry in entries:
                    citing_paper: dict[str, Any] = entry.get("citingPaper") or {}
                    citer_id = citing_paper.get("paperId")
                    if not citer_id:
                        continue
                    if since is not None:
                        year = citing_paper.get("year")
                        if year is not None and year < since.year:
                            continue
                    seen.add(citer_id)
                    works_map[citer_id] = citing_paper
                    if max_per_paper is not None and len(seen) >= max_per_paper:
                        break

                offset += len(entries)
                if data.get("next") is None or len(entries) < limit:
                    break

        citer_ids = sorted(seen)
        if max_per_paper is not None:
            citer_ids = citer_ids[:max_per_paper]
        works_map = {cid: works_map[cid] for cid in citer_ids}
        return citer_ids, works_map

    def _fetch_citing_pages(
        self,
        ids: list[str],
        *,
        max_per_paper: int | None,
        since: date | None,
    ) -> tuple[dict[str, list[str]], dict[str, dict[str, Any]]]:
        """Núcleo compartido de ``fetch_citing_batch``/``_with_works``.

        Itera por ID (S2 no soporta OR-batch en ``/citations``), acumulando
        la atribución y el mapa de works JSON.

        Args:
            ids: IDs de S2 (``paperId``) de las semillas.
            max_per_paper: Tope de citantes por semilla. ``None`` = sin tope.
            since: Filtro de año mínimo (aproximación, ver ``_fetch_citing_one``).

        Returns:
            Tupla ``(attribution, works_map)``: ``attribution`` es
            ``{seed_id: [citer_id, ...]}`` con una entrada por cada ID de
            ``ids`` (incluso si la lista de citantes es vacía); ``works_map``
            es ``{citer_id: citingPaper_json}`` de todos los citantes únicos.
        """
        attribution: dict[str, list[str]] = {}
        works_map: dict[str, dict[str, Any]] = {}
        for paper_id in ids:
            citer_ids, paper_works = self._fetch_citing_one(
                paper_id, max_per_paper=max_per_paper, since=since
            )
            attribution[paper_id] = citer_ids
            works_map.update(paper_works)
        return attribution, works_map

    def work_to_row(
        self,
        work: dict[str, Any],
        *,
        equation_id: str | None,
        fetched_at: str,
        is_seed: bool = True,
        action: str = "fetched",
        chaining_hop: int | None = None,
        source_tag: str = "s2",
        source_kind: SourceKind | None = None,
    ) -> dict[str, Any]:
        """Mapea un ``citingPaper`` de S2 a la fila canónica (ADR 0053 D1.5).

        Contrato duck-typed que consume el ``Forager`` para materializar los
        candidatos forward con metadata real (el ``works_map`` de
        ``fetch_citing_batch_with_works`` trae JSON crudo de S2, no de
        OpenAlex).  Envuelve ``_paper_to_row``.
        """
        return _paper_to_row(
            work,
            equation_id=equation_id,
            fetched_at=fetched_at,
            is_seed=is_seed,
            action=action,
            chaining_hop=chaining_hop,
            source_tag=source_tag,
            source_kind=source_kind,
        )

    def fetch_citing_batch(
        self,
        ids: list[str],
        *,
        max_per_paper: int | None = None,
        since: date | None = None,
    ) -> dict[str, list[str]]:
        """Trae los citantes directos de varios papers (uno a uno, sin OR-batch).

        Consumido por el ``Forager`` vía ``hasattr`` (duck-typing, sin
        depender de un tipo común; ver ``foraging/forager.py``).

        Args:
            ids: Lista de IDs de S2 (``paperId``) de las semillas.
            max_per_paper: Tope de citantes a recolectar por semilla.
                ``None`` = sin tope.
            since: Filtra citantes con año de publicación >= ``since.year``.

        Returns:
            Dict ``{seed_id: [citer_id, ...]}``, orden alfabético determinista.
            ``{}`` si ``ids`` está vacío.
        """
        if not ids:
            return {}
        attribution, _ = self._fetch_citing_pages(
            ids, max_per_paper=max_per_paper, since=since
        )
        return attribution

    def fetch_citing_batch_with_works(
        self,
        ids: list[str],
        *,
        max_per_paper: int | None = None,
        since: date | None = None,
    ) -> tuple[dict[str, list[str]], dict[str, dict[str, Any]]]:
        """Como ``fetch_citing_batch`` pero conserva los objetos JSON completos.

        Sin red extra: los ``citingPaper`` ya vienen en las páginas de
        ``/paper/{id}/citations`` que se usan para la atribución.

        Args:
            ids: Lista de IDs de S2 (``paperId``) de las semillas.
            max_per_paper: Tope de citantes por semilla. ``None`` = sin tope.
            since: Filtra citantes con año de publicación >= ``since.year``.

        Returns:
            Tupla ``(attribution, works_map)``. ``works_map`` trae JSON crudo
            de S2 (shape de ``_paper_to_row``, NO de ``openalex._work_to_row``
            — ver nota de riesgo en el docstring del módulo). ``({}, {})`` si
            ``ids`` está vacío.
        """
        if not ids:
            return {}, {}
        return self._fetch_citing_pages(ids, max_per_paper=max_per_paper, since=since)
