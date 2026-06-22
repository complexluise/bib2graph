"""Tests directos de ``_compute_id`` — invariante central del ADR 0036.

Protege la precedencia de identidad ``doi > source_id > título+año`` como
**aserción**, no solo como dato (el corpus de ejemplo migrado). Si alguien
invirtiera la precedencia en un refactor futuro, estos tests lo detectan
(antes el gate quedaba verde porque nada llamaba a ``_compute_id`` directo).
"""

from __future__ import annotations

import pytest

from bib2graph.corpus import _compute_id


@pytest.mark.unit
class TestComputeIdPrecedencia:
    """Precedencia D1' del ADR 0036: doi > source_id > título+año."""

    def test_solo_doi_rinde_prefijo_doi(self) -> None:
        assert _compute_id("10.1/x", None, "Título", 2020).startswith("doi:")

    def test_doi_gana_sobre_source_id(self) -> None:
        """Un paper con DOI **y** source_id ancla en el DOI (afirmación central del ADR)."""
        assert _compute_id("10.1/x", "W123", "Título", 2020).startswith("doi:")

    def test_solo_source_id_rinde_prefijo_src(self) -> None:
        assert _compute_id(None, "W123", "Título", 2020).startswith("src:")

    def test_sin_doi_ni_source_id_rinde_prefijo_tt(self) -> None:
        assert _compute_id(None, None, "Título", 2020).startswith("tt:")

    def test_source_id_vacio_cae_a_tt(self) -> None:
        assert _compute_id(None, "", "Título", 2020).startswith("tt:")


@pytest.mark.unit
class TestComputeIdNormalizacionDoi:
    """El DOI se normaliza (prefijo URL + minúsculas) antes de hashear."""

    def test_url_https_igual_que_doi_pelado(self) -> None:
        assert _compute_id("https://doi.org/10.1/x", None, "T", 2020) == _compute_id(
            "10.1/x", None, "T", 2020
        )

    def test_url_http_igual_que_doi_pelado(self) -> None:
        assert _compute_id("http://doi.org/10.1/x", None, "T", 2020) == _compute_id(
            "10.1/x", None, "T", 2020
        )

    def test_case_insensitive(self) -> None:
        assert _compute_id("10.1/ABC", None, "T", 2020) == _compute_id(
            "10.1/abc", None, "T", 2020
        )


@pytest.mark.unit
class TestComputeIdInteroperabilidad:
    """El DOI es interoperable entre motores: mismo DOI → mismo id (clave del ADR 0036)."""

    def test_mismo_doi_distinto_source_id_mismo_id(self) -> None:
        """El mismo paper resuelto por OpenAlex (W...) y por Semantic Scholar (S...)
        rinde el MISMO id si comparte DOI — base del cruce/dedup cross-motor."""
        via_openalex = _compute_id("10.1/x", "W123", "T", 2020)
        via_semanticscholar = _compute_id("10.1/x", "S999", "T", 2020)
        assert via_openalex == via_semanticscholar

    def test_determinista(self) -> None:
        assert _compute_id("10.1/x", "W1", "T", 2020) == _compute_id(
            "10.1/x", "W1", "T", 2020
        )
