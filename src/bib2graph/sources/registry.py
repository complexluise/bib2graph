"""sources.registry — Registro declarativo de proveedores (ADR 0053 D1.4).

El proveedor es un **dato**, no un ``if`` (precedente ADR 0046): cada
``Provider`` mapea a su fábrica y a las **capacidades** que declara.  Pedir una
capacidad que el proveedor no tiene falla **antes de tocar la red**, con un
``DependencyError`` (exit 3) que nombra el proveedor y la capacidad.

Sin efectos de import: las ``Source`` concretas (y ``httpx``) se importan
perezosamente dentro de cada fábrica.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from bib2graph.constants import Provider
from bib2graph.service.errors import DependencyError


class Capability(StrEnum):
    """Capacidades que un proveedor puede (o no) declarar."""

    SEED = "seed"
    SEED_FILTERS = "seed_filters"  # --native/--exclude/--min-year/--max-year
    BACKWARD = "backward"
    FORWARD = "forward"
    ENRICH_CITED_BY = "enrich_cited_by"
    ENRICH_REFS_DOI = "enrich_refs_doi"
    RESOLVE_DOI = "resolve_doi"


@dataclass(frozen=True)
class ProviderSpec:
    """Fábrica + capacidades declaradas de un proveedor.

    ``factory`` recibe ``email``, ``api_key``, ``transport`` y ``max_results``
    (este último ``None`` = default del source) y devuelve la ``Source``.
    """

    factory: Callable[..., Any]
    capabilities: frozenset[Capability]


def _openalex_factory(
    *,
    email: str | None,
    api_key: str | None,
    transport: Any,
    max_results: int | None,
) -> Any:
    from bib2graph.sources.openalex import OpenAlexSource

    kwargs: dict[str, Any] = {
        "email": email,
        "api_key": api_key,
        "transport": transport,
    }
    if max_results is not None:
        kwargs["max_results"] = max_results
    return OpenAlexSource(**kwargs)


def _s2_factory(
    *,
    email: str | None,
    api_key: str | None,
    transport: Any,
    max_results: int | None,
) -> Any:
    from bib2graph.sources.semanticscholar import SemanticScholarSource

    # S2 no tiene polite pool: ``email`` no aplica (el CLI lo rechaza antes).
    del email
    kwargs: dict[str, Any] = {"api_key": api_key, "transport": transport}
    if max_results is not None:
        kwargs["max_results"] = max_results
    return SemanticScholarSource(**kwargs)


def _doaj_factory(
    *,
    email: str | None,
    api_key: str | None,
    transport: Any,
    max_results: int | None,
) -> Any:
    from bib2graph.sources.doaj import DoajSource

    # DOAJ: search sin credenciales y sin polite pool; ``email``/``api_key`` no
    # aplican (el CLI rechaza ``--email`` antes).
    del email, api_key
    kwargs: dict[str, Any] = {"transport": transport}
    if max_results is not None:
        kwargs["max_results"] = max_results
    return DoajSource(**kwargs)


PROVIDERS: dict[Provider, ProviderSpec] = {
    Provider.OPENALEX: ProviderSpec(
        factory=_openalex_factory,
        capabilities=frozenset(Capability),
    ),
    # S2 (ADR 0042): sin filtros de ecuación (query nativa tal cual), sin
    # resolución refs→DOI ni DOI→id (el ``fetch_works_by_ids`` acepta ``DOI:``
    # pero no hay un método de resolución en lote análogo).
    Provider.S2: ProviderSpec(
        factory=_s2_factory,
        capabilities=frozenset(
            {
                Capability.SEED,
                Capability.BACKWARD,
                Capability.FORWARD,
                Capability.ENRICH_CITED_BY,
            }
        ),
    ),
    # DOAJ (ADR 0053 Corte 5, #252): solo siembra por query nativa
    # (Elasticsearch/Lucene, sin traducción). Sin grafo de citas: ni
    # backward/forward ni enriquecimientos, y sin ``seed_filters``.
    Provider.DOAJ: ProviderSpec(
        factory=_doaj_factory,
        capabilities=frozenset({Capability.SEED}),
    ),
}


def make_source(
    provider: Provider,
    *,
    email: str | None = None,
    api_key: str | None = None,
    transport: Any = None,
    max_results: int | None = None,
) -> Any:
    """Instancia la ``Source`` del proveedor vía el registro.

    Args:
        provider: Proveedor elegido.
        email: Email del polite pool (solo OpenAlex).
        api_key: API key (OpenAlex opcional; S2 recomendada para ``seed``).
        transport: Transport httpx inyectable (tests).
        max_results: Tope de resultados de ``seed``; ``None`` = default del source.

    Returns:
        La ``Source`` configurada.
    """
    return PROVIDERS[provider].factory(
        email=email, api_key=api_key, transport=transport, max_results=max_results
    )


def has(provider: Provider, capability: Capability) -> bool:
    """``True`` si el proveedor declara la capacidad."""
    return capability in PROVIDERS[provider].capabilities


def require(provider: Provider, capability: Capability) -> None:
    """Falla (``DependencyError``, exit 3) si el proveedor no declara la capacidad.

    Pensado para llamarse ANTES de abrir el store o tocar la red.
    """
    if has(provider, capability):
        return
    declared = ", ".join(sorted(c.value for c in PROVIDERS[provider].capabilities))
    raise DependencyError(
        f"El proveedor '{provider.value}' no soporta la capacidad "
        f"'{capability.value}' (declara: {declared}). "
        "Usá otro proveedor con --source o quitá el flag que la requiere."
    )
