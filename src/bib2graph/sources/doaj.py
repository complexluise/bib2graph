"""doaj — ``DoajSource``: siembra desde la API de búsqueda de DOAJ.

1ª fuente Sur-global (ADR 0053 Corte 5, #252): cobertura OA hispana/lusófona
(ES/PT) que OpenAlex cubre mal.  Es **solo sembradora**: DOAJ no expone grafo de
citas, así que ``PROVIDERS`` declara únicamente la capacidad ``seed``.  Toda la
I/O usa ``httpx`` (núcleo); sin SDK.

Contrato de la API (verificado contra respuestas reales, v4; ver
``tests/fixtures/doaj/``): ``GET /api/v4/search/articles/{query}?page=&pageSize=``
devuelve ``{"total", "page", "pageSize", "results": [{"id", "bibjson": {...}}]}``.
``pageSize`` admite hasta 100.  Search **sin key** (la key es de editores).

Decisiones (ADR 0053):
- **Identidad (R3)**: ``source_id`` = id de artículo DOAJ.  Un artículo **con**
  DOI ancla al mismo ``id`` canónico que en OpenAlex (``doi:``); uno **sin**
  DOI (~2/3 en las muestras) queda como ``src:`` estable dentro de su carril.
  El ``identifier`` de ``bibjson`` mezcla el DOI con los ISSN de la revista
  (``pissn``/``eissn``): solo ``type == "doi"`` es el DOI del artículo.
- **Sin traducción (como S2, ADR 0042 D3)**: DOAJ usa sintaxis
  Elasticsearch/Lucene (``bibjson.title:"x" AND ...``), no WoS; la query se pasa
  nativa y ``translation_report`` lo declara.  Sin ``seed_filters``.
- **Sin citas**: ``references_id``/``references_doi`` quedan ``None`` y
  ``cited_by_id`` vacío.
- ``language`` queda ``None``: ``bibjson.journal.language`` es el idioma de la
  **revista** (lista), no del artículo; asignarlo sería inventar el dato.

``seed`` reintenta con backoff ante 429/5xx y, agotados los reintentos, mapea a
``NetworkError`` con subcode ``RATE_LIMITED``/``UPSTREAM_TIMEOUT`` (ADR 0045).
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx
import pyarrow as pa

from bib2graph.constants import Col, CurationStatus, Provider
from bib2graph.corpus import Corpus, EquationRef, _rows_with_ids
from bib2graph.schemas import CORPUS_SCHEMA, ProvenanceEvent, SourceKind
from bib2graph.service.errors import DataError, NetworkError
from bib2graph.sources.base import SeedResult
from bib2graph.sources.openalex import _normalize_doi

_BASE_URL = "https://doaj.org/api/v4"

# Retry/backoff: mismos parámetros que OpenAlex/S2 (ADR 0045).
_RETRY_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})
_RETRY_MAX_ATTEMPTS: int = 3
_RETRY_BACKOFF_BASE: float = 1.0  # segundos; duplica por cada intento

# pageSize máximo de la API v4; tope de max_results (paginación profunda de
# Elasticsearch: no se promete más de lo razonable para una siembra).
_PAGE_SIZE = 100
_MAX_SEARCH_RESULTS = 1000

# Reporte de traducción honesto (como S2, ADR 0042 D3): no hay capa WoS→DOAJ.
TRANSLATION_REPORT_LINE = (
    "DOAJ: query interpretada con sintaxis nativa de DOAJ "
    "(Elasticsearch/Lucene); sin traducción WoS"
)


def _doi_of(bibjson: dict[str, Any]) -> str | None:
    """DOI del artículo: ``identifier`` con ``type == "doi"`` (no los ISSN)."""
    for ident in bibjson.get("identifier") or []:
        if str(ident.get("type") or "").lower() == "doi":
            return _normalize_doi(ident.get("id"))
    return None


def _year_of(bibjson: dict[str, Any]) -> int | None:
    """``year`` de DOAJ viene como string (``"2012"``); ``None`` si no parsea."""
    raw = bibjson.get("year")
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _article_to_row(
    article: dict[str, Any],
    *,
    equation_id: str | None,
    fetched_at: str,
    is_seed: bool = True,
    action: str = "fetched",
    source_tag: str = Provider.DOAJ.value,
    source_kind: SourceKind | None = None,
) -> dict[str, Any]:
    """Mapea un resultado de ``/search/articles`` a la fila del schema canónico.

    Acceso defensivo con ``.get()`` (AGENTS.md).  El ``id`` canónico lo calcula
    ``_rows_with_ids`` (DOI-first, ADR 0036): con DOI coincide con el de
    OpenAlex; sin DOI usa ``src:`` sobre ``source_id`` (R3).

    Args:
        article: Objeto JSON de un artículo DOAJ (``{"id", "bibjson"}``).
        equation_id: Ecuación que originó la búsqueda (provenance).
        fetched_at: Timestamp ISO de la consulta.
        is_seed: Si el paper es semilla.
        action: Tipo de evento de provenance.
        source_tag: Etiqueta de fuente del evento (token ``Provider.DOAJ``).
        source_kind: Origen semántico del evento (ADR 0050 D2).

    Returns:
        Dict con todas las columnas del schema canónico.
    """
    bib: dict[str, Any] = article.get("bibjson") or {}
    journal: dict[str, Any] = bib.get("journal") or {}

    authors_raw: list[str] = []
    authors_id: list[str] = []
    affiliations: list[str] = []
    for author in bib.get("author") or []:
        name = author.get("name") or ""
        if name:
            authors_raw.append(name)
        # ORCID en forma corta (``0000-…``), como ``_oa_id_short`` en OpenAlex.
        orcid = str(author.get("orcid_id") or "").strip().rsplit("/", 1)[-1]
        authors_id.append(orcid or name or "unknown")
        if author.get("affiliation"):
            affiliations.append(str(author["affiliation"]))

    keywords = [str(k).strip() for k in (bib.get("keywords") or []) if k]
    keywords = [k for k in keywords if k]
    # keywords_id: DOAJ no da ids de concepto (a diferencia de OpenAlex): se usa
    # la forma normalizada (casefold, sin punto/coma final) para que la red de
    # co-ocurrencia una variantes triviales; keywords_raw conserva el original.
    keywords_id: list[str] = []
    for k in keywords:
        norm = k.casefold().strip(" .;,")
        if norm and norm not in keywords_id:
            keywords_id.append(norm)
    areas = [str(s["term"]) for s in (bib.get("subject") or []) if s.get("term")]

    provenance_event = ProvenanceEvent(
        action=action,
        equation_id=equation_id,
        chaining_hop=None,
        source=source_tag,
        fetched_at=fetched_at,
        decided_by=None,
        decided_at=None,
        source_kind=source_kind,
    )

    return {
        # id se calcula en _rows_with_ids (DOI-first; sin DOI → src:, R3)
        Col.PROVIDER: Provider.DOAJ.value,
        Col.SOURCE_ID: article.get("id"),
        Col.DOI: _doi_of(bib),
        Col.TITLE: bib.get("title") or "",
        Col.YEAR: _year_of(bib),
        Col.ABSTRACT: bib.get("abstract"),
        Col.SOURCE: journal.get("title"),
        Col.LANGUAGE: None,
        Col.PUBLISHER: journal.get("publisher"),
        Col.RESEARCH_AREAS: areas or None,
        Col.IS_SEED: is_seed,
        Col.CURATION_STATUS: CurationStatus.CANDIDATE,
        Col.PROVENANCE: ProvenanceEvent.dump_list([provenance_event]),
        Col.AUTHORS_RAW: authors_raw or None,
        Col.AUTHORS_ID: authors_id or None,
        Col.AUTHORS_AFFILIATIONS: affiliations or None,
        Col.KEYWORDS_RAW: keywords or None,
        Col.KEYWORDS_ID: keywords_id or None,
        Col.INSTITUTIONS_RAW: None,
        Col.INSTITUTIONS_ID: None,
        Col.REFERENCES_ID: None,
        Col.REFERENCES_DOI: None,
        Col.CITED_BY_ID: [],
    }


class DoajSource:
    """Siembra un ``Corpus`` desde la API de búsqueda de DOAJ.

    Ejemplo::

        source = DoajSource()
        result = source.seed('bibjson.title:"pensamiento complejo"')

    Sin credenciales (el search de DOAJ es público).  El ``transport`` permite
    inyectar un ``httpx.MockTransport`` en tests (sin red en CI).
    """

    def __init__(
        self,
        *,
        transport: httpx.BaseTransport | None = None,
        base_url: str = _BASE_URL,
        max_results: int = 200,
    ) -> None:
        """Inicializa el source.

        Args:
            transport: Transport de httpx (inyectar ``MockTransport`` en tests).
            base_url: URL base de la API (default producción, v4).
            max_results: Tope de resultados de ``seed()``, en ``1..1000``.

        Raises:
            ValueError: Si ``max_results`` está fuera de ``1..1000``.
        """
        if not 1 <= max_results <= _MAX_SEARCH_RESULTS:
            raise ValueError(
                f"max_results={max_results} fuera de rango: DOAJ admite entre 1 "
                f"y {_MAX_SEARCH_RESULTS} resultados por siembra."
            )
        self._base_url = base_url.rstrip("/")
        self._max_results = max_results
        self._transport = transport

    def _client(self) -> httpx.Client:
        if self._transport is not None:
            return httpx.Client(transport=self._transport, base_url=self._base_url)
        return httpx.Client(base_url=self._base_url)

    def _get_with_retry(
        self, client: httpx.Client, path: str, params: dict[str, Any]
    ) -> httpx.Response:
        """GET con retry/backoff ante 429/5xx (ADR 0045).

        Raises:
            NetworkError: 429 agotado (``RATE_LIMITED``) o 504 agotado
                (``UPSTREAM_TIMEOUT``).
            DataError: 400 (query Lucene inválida; no es un fallo de red).
            httpx.HTTPStatusError: otro código no retryable, o 5xx ≠ 504 agotado.
        """
        last_exc: httpx.HTTPStatusError | None = None
        for attempt in range(_RETRY_MAX_ATTEMPTS):
            try:
                resp = client.get(path, params=params)
                resp.raise_for_status()
                return resp
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status == 400:
                    raise DataError(_bad_query_message(exc.response)) from exc
                if status not in _RETRY_STATUS_CODES:
                    raise
                last_exc = exc
                if attempt < _RETRY_MAX_ATTEMPTS - 1:
                    time.sleep(_RETRY_BACKOFF_BASE * (2**attempt))
        assert last_exc is not None
        status = last_exc.response.status_code
        if status == 429:
            retry_after = last_exc.response.headers.get("Retry-After")
            msg = (
                "DOAJ respondió 429 (Too Many Requests) tras agotar los "
                "reintentos. El search es público y sin key: esperá antes de "
                "reintentar o reducí el volumen (--max-results)."
            )
            if retry_after:
                msg += f" DOAJ indicó Retry-After: {retry_after}."
            raise NetworkError(msg, subcode="RATE_LIMITED") from last_exc
        if status == 504:
            raise NetworkError(
                "DOAJ respondió 504 (Gateway Timeout) tras agotar los "
                "reintentos: la petición tardó demasiado upstream. Simplificá "
                "la query (menos términos, max_results más chico) y reintentá.",
                subcode="UPSTREAM_TIMEOUT",
            ) from last_exc
        raise last_exc

    def _fetch_search(self, query: str) -> list[dict[str, Any]]:
        """Pagina ``/search/articles/{query}`` hasta ``max_results``."""
        articles: list[dict[str, Any]] = []
        page = 1
        # La query viaja en el path: se percent-encodea todo (incluida "/").
        path = f"/search/articles/{quote(query, safe='')}"
        with self._client() as client:
            while len(articles) < self._max_results:
                # pageSize FIJO: DOAJ calcula el offset como (page-1)*pageSize;
                # variarlo en la última página saltaría/duplicaría resultados.
                size = min(_PAGE_SIZE, self._max_results)
                resp = self._get_with_retry(
                    client, path, {"page": page, "pageSize": size}
                )
                data: dict[str, Any] = resp.json()
                results: list[dict[str, Any]] = data.get("results") or []
                articles.extend(results)
                total = data.get("total")
                if not results or (total is not None and len(articles) >= total):
                    break
                page += 1
        return articles[: self._max_results]

    def seed(self, query: str) -> SeedResult:
        """Siembra un ``Corpus`` desde una query nativa de DOAJ.

        Sin traducción WoS→DOAJ: la query se pasa tal cual (sintaxis
        Elasticsearch/Lucene) y ``translation_report`` lo declara.

        Args:
            query: Query nativa de DOAJ.

        Returns:
            ``SeedResult`` con el corpus (filas ``provider="doaj"``), la query
            ejecutada y el reporte de traducción.

        Raises:
            NetworkError: 429/504 agotados (``RATE_LIMITED``/``UPSTREAM_TIMEOUT``).
            DataError: DOAJ rechazó la query (400).
        """
        equation_id = f"eq-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}"
        created_at = datetime.now(UTC).isoformat()

        articles = self._fetch_search(query)
        translation_report = [TRANSLATION_REPORT_LINE]

        rows = [
            _article_to_row(
                article,
                equation_id=equation_id,
                fetched_at=created_at,
                source_kind="seed_equation",  # ADR 0050 D2
            )
            for article in articles
        ]
        rows_with_ids = _rows_with_ids(rows)
        if rows_with_ids:
            table = pa.Table.from_pylist(rows_with_ids, schema=CORPUS_SCHEMA)
        else:
            table = pa.table(
                {col: [] for col in CORPUS_SCHEMA.names}, schema=CORPUS_SCHEMA
            )
        corpus = Corpus.from_arrow(table)

        # ADR 0050 D1: ``raw_query`` = ecuación cruda (== ``executed_query``).
        params: dict[str, object] = {
            "raw_query": query,
            "max_results": self._max_results,
            "executed_query": query,
            "translation_report": translation_report,
        }
        manifest = corpus.manifest.model_copy(
            update={
                "equations": [
                    EquationRef(
                        equation_id=equation_id,
                        query=query,
                        translation_report=translation_report,
                        engine=Provider.DOAJ.value,
                        params=params,
                        created_at=created_at,
                    )
                ],
            }
        )
        return SeedResult(
            corpus=corpus.with_manifest(manifest),
            executed_query=query,
            translation_report=translation_report,
        )

    def load(self, path: str) -> Corpus:
        """No soportado: DOAJ solo siembra por query.

        Raises:
            NotImplementedError: Siempre (fallar fuerte, como ``BibtexSource.seed``).
        """
        raise NotImplementedError(
            "DoajSource: carga desde archivo no soportada; usá seed() con una "
            "query nativa de DOAJ (b2g seed --equation ... --source doaj). "
            "Para un .bib usá b2g seed --from-bib."
        )


def _bad_query_message(response: httpx.Response) -> str:
    """Mensaje accionable para un 400 de DOAJ (query Lucene inválida)."""
    detail = ""
    try:
        body = response.json()
        detail = str(body.get("error") or "") if isinstance(body, dict) else ""
    except ValueError:
        detail = ""
    msg = (
        "DOAJ rechazó la query (400): la sintaxis es Elasticsearch/Lucene, no "
        'WoS (p. ej. bibjson.title:"pensamiento complejo" AND educación).'
    )
    return f"{msg} Detalle: {detail}" if detail else msg
