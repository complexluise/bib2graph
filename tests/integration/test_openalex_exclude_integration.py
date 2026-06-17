"""Tests de integración para el filtro --exclude de OpenAlexSource.

Estos tests tocan la API real de OpenAlex (sin MockTransport) y verifican
que la forma del filtro producida por _translate genera resultados reales.

La clase de bug que cubren (campo repetido fuera del paréntesis) da 0
resultados contra la API real pero no es detectable por mocks, ya que el
mock no valida la semántica del filtro de OpenAlex.

Marcados como ``network`` → excluidos del gate/CI por defecto
(``addopts = ["-m", "not network"]``), porque requieren red real a OpenAlex.
Los tests ``integration`` que NO tocan red (p.ej. duckdb/store) siguen
corriendo en el gate.  Para correr estos con red real:
    uv run pytest -m network
"""

from __future__ import annotations

import pytest

from bib2graph.sources.openalex import OpenAlexSource


@pytest.mark.network
def test_exclude_filter_retorna_resultados_no_cero() -> None:
    """La query con --exclude devuelve count > 0 contra OpenAlex real.

    Si el filtro tuviera la forma buggeada (campo repetido fuera del
    paréntesis), OpenAlex devuelve 0 resultados.  Con la forma correcta
    (NOT dentro del paréntesis) devuelve results > 0.

    Query elegida: "complexity" (amplia) con exclude=["machine learning",
    "deep learning"] — confirmada 3958 resultados en la sesión de QA del bug.
    """
    source = OpenAlexSource(email="trama.complejidad@gmail.com", max_results=10)
    result = source.seed(
        "complexity",
        exclude=["machine learning", "deep learning"],
        max_year=2023,
    )

    count = len(result.corpus)
    assert count > 0, (
        f"Se esperaban resultados > 0 pero se obtuvieron {count}. "
        "Posible regresión a la forma buggeada del filtro --exclude "
        "(campo repetido fuera del paréntesis → 0 resultados en OpenAlex)."
    )


@pytest.mark.network
def test_exclude_filter_campo_no_repetido_en_query_ejecutada() -> None:
    """La query ejecutada contra OpenAlex real contiene exactamente un campo de búsqueda.

    Verifica que ``_translate`` no repite ``title_and_abstract.search:``
    y que la forma enviada a la API es la correcta.
    """
    source = OpenAlexSource(email="trama.complejidad@gmail.com", max_results=5)
    result = source.seed(
        "systems thinking",
        exclude=["artificial intelligence"],
    )

    assert result.executed_query.count("title_and_abstract.search:") == 1, (
        f"Se repite el campo en la query ejecutada: {result.executed_query!r}"
    )
    assert "AND NOT title_and_abstract.search:" not in result.executed_query
    assert 'AND NOT "artificial intelligence"' in result.executed_query
