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
from datetime import UTC, datetime
from typing import Any

import httpx
import pyarrow as pa

from bib2graph.corpus import Corpus, EquationRef, Manifest
from bib2graph.schemas import CORPUS_SCHEMA

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


# ---------------------------------------------------------------------------
# Traducción de ecuación (función pura, sin I/O)
# ---------------------------------------------------------------------------


def _translate(query: str, *, native: bool = False) -> tuple[str, list[str]]:
    """Traduce una ecuación WoS-style a una query OpenAlex ejecutable.

    Si ``native=True`` pasa la query cruda sin ningún procesamiento.

    Detecta y reporta límites de OpenAlex (ADR 0007) sin abortar:
    - ``NEAR/n``: proximidad no soportada.
    - Comodín ``*``: comportamiento distinto al de WoS.
    - Tags de campo WoS (``TS=``, ``AB=``, ``AU=``…): no mapean 1:1.

    Args:
        query: Ecuación de búsqueda.
        native: Si es ``True``, no traducir; usar query cruda.

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
    provenance_event = {
        "action": "fetched",
        "equation_id": equation_id,
        "chaining_hop": None,
        "source": "openalex",
        "fetched_at": fetched_at,
        "decided_by": None,
        "decided_at": None,
    }

    return {
        # id se calcula en Corpus.add_paper (D1)
        "openalex_id": openalex_id,
        "doi": doi,
        "title": work.get("title") or work.get("display_name") or "",
        "year": work.get("publication_year"),
        "abstract": _reconstruct_abstract(work.get("abstract_inverted_index")),
        "source": venue,
        "language": work.get("language"),
        "publisher": None,
        "research_areas": None,
        "is_seed": True,
        "curation_status": "candidate",
        "provenance": json.dumps([provenance_event]),
        "authors_raw": authors_raw or None,
        "authors_id": authors_id or None,
        "authors_affiliations": authors_affiliations or None,
        "keywords_raw": keywords_raw or None,
        "keywords_id": keywords_id or None,
        "institutions_raw": institutions_raw or None,
        "institutions_id": institutions_id or None,
        "references_id": references_id_clean or None,
        "references_doi": None,
        "cited_by_id": [],
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

    def seed(self, query: str, *, native: bool = False) -> SeedResult:
        """Siembra un ``Corpus`` desde una ecuación de búsqueda.

        ``cited_by_id`` queda ``[]`` en el corpus sembrado: OpenAlex no lo
        entrega inline; lo pueblan el Forager/Enricher en Hito 5/8.
        ``references_id`` SÍ se trae inline (``referenced_works``).

        Args:
            query: Ecuación de búsqueda (WoS-style o nativa OpenAlex).
            native: Si es ``True``, pasa la query cruda sin traducción.

        Returns:
            ``SeedResult`` con el corpus, la query ejecutada y el reporte.
        """
        executed_query, translation_report = _translate(query, native=native)
        equation_id = f"eq-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}"
        fetched_at = datetime.now(UTC).isoformat()

        works, openalex_version = self._fetch_all(executed_query)

        corpus = Corpus.from_arrow(
            pa.table(
                {col: [] for col in CORPUS_SCHEMA.names},
                schema=CORPUS_SCHEMA,
            )
        )
        for work in works:
            row = _work_to_row(work, equation_id=equation_id, fetched_at=fetched_at)
            corpus = corpus.add_paper(row)

        # Actualizar Manifest con openalex_version y ecuación (ADR 0017)
        updated_manifest = Manifest(
            schema_version=corpus.manifest.schema_version,
            corpus_hash=corpus.manifest.corpus_hash,
            lib_version=corpus.manifest.lib_version,
            created_at=corpus.manifest.created_at,
            openalex_version=openalex_version,
            equations=[
                EquationRef(
                    equation_id=equation_id,
                    query=executed_query,
                    translation_report=translation_report,
                )
            ],
        )
        # Sustituir el manifest en el corpus usando la API pública
        result_corpus = corpus.with_manifest(updated_manifest)

        return SeedResult(
            corpus=result_corpus,
            executed_query=executed_query,
            translation_report=translation_report,
        )

    def fetch_citing(self, openalex_id: str) -> list[dict[str, Any]]:
        """Trae los works que citan al paper con ``openalex_id`` dado.

        Usa ``GET /works?filter=cites:{openalex_id}`` con paginación por
        cursor, reutilizando el cliente httpx y ``_work_to_row``.  Es el
        mecanismo del forward chaining (Hito 5, ADR 0008).

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

        works, _ = self._fetch_all(filter_str)
        rows: list[dict[str, Any]] = []
        for work in works:
            row = _work_to_row(work, equation_id=equation_id, fetched_at=fetched_at)
            # Sobrescribir is_seed y provenance para forward chaining
            row["is_seed"] = False
            provenance_event = {
                "action": "fetched",
                "equation_id": None,
                "chaining_hop": 1,
                "source": "openalex",
                "fetched_at": fetched_at,
                "decided_by": None,
                "decided_at": None,
            }
            row["provenance"] = json.dumps([provenance_event])
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

        corpus = Corpus.from_arrow(
            pa.table(
                {col: [] for col in CORPUS_SCHEMA.names},
                schema=CORPUS_SCHEMA,
            )
        )
        for work in data:
            row = _work_to_row(work, equation_id=equation_id, fetched_at=fetched_at)
            corpus = corpus.add_paper(row)
        return corpus
