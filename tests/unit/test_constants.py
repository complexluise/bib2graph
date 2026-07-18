"""Tests de bib2graph.constants — derivación de URL canónica (#203).

Verifica:
- ``doi_to_url``: caso base ya cubierto en otros tests (test_service_reads.py,
  test_decorate.py); acá solo se agregan casos límite (None, string vacío).
- ``openalex_id_to_url``: derivación análoga desde ``source_id`` (OpenAlex).
- ``resolve_paper_url``: DOI-first, fallback a OpenAlex, None si no hay nada.

Marcador: ``unit`` (función pura, sin I/O).
"""

from __future__ import annotations

import pytest

from bib2graph.constants import doi_to_url, openalex_id_to_url, resolve_paper_url


@pytest.mark.unit
def test_doi_to_url_none_y_vacio() -> None:
    """doi_to_url devuelve None para None y para string vacío."""
    assert doi_to_url(None) is None
    assert doi_to_url("") is None


@pytest.mark.unit
def test_openalex_id_to_url_deriva_correctamente() -> None:
    """openalex_id_to_url deriva https://openalex.org/<id> desde un id corto."""
    assert openalex_id_to_url("W12345") == "https://openalex.org/W12345"


@pytest.mark.unit
def test_openalex_id_to_url_none_y_vacio() -> None:
    """openalex_id_to_url devuelve None para None y para string vacío."""
    assert openalex_id_to_url(None) is None
    assert openalex_id_to_url("") is None


@pytest.mark.unit
def test_resolve_paper_url_doi_first() -> None:
    """Con DOI y source_id presentes, resolve_paper_url prefiere el DOI (#203)."""
    url = resolve_paper_url("10.1234/ejemplo", "W12345")
    assert url == "https://doi.org/10.1234/ejemplo"


@pytest.mark.unit
def test_resolve_paper_url_fallback_openalex_sin_doi() -> None:
    """Sin DOI, resolve_paper_url cae a la URL de OpenAlex vía source_id (#203)."""
    url = resolve_paper_url(None, "W12345")
    assert url == "https://openalex.org/W12345"


@pytest.mark.unit
def test_resolve_paper_url_none_sin_doi_ni_source_id() -> None:
    """Sin DOI ni source_id, resolve_paper_url no inventa una URL."""
    assert resolve_paper_url(None, None) is None
    assert resolve_paper_url("", "") is None
