"""Tests directos de ``_compute_id`` — invariante central del ADR 0036.

Protege la precedencia de identidad ``doi > source_id > título+año`` como
**aserción**, no solo como dato (el corpus de ejemplo migrado). Si alguien
invirtiera la precedencia en un refactor futuro, estos tests lo detectan
(antes el gate quedaba verde porque nada llamaba a ``_compute_id`` directo).
"""

from __future__ import annotations

from typing import ClassVar

import pytest

from bib2graph.corpus import _compute_id, _title_key


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


# ---------------------------------------------------------------------------
# ADR 0053 D3 (#254): clave tt normalizada fuerte
# ---------------------------------------------------------------------------


def _tt(title: str, year: int | None = 2020) -> str:
    return _compute_id(None, None, title, year)


@pytest.mark.unit
class TestTitleKeyFalsosSplits:
    """Variantes del MISMO título deben dar la MISMA clave."""

    @pytest.mark.parametrize(
        ("a", "b"),
        [
            ("Café y Complejidad", "Cafe y complejidad"),
            ("Self-Organization", "Self organization"),
            ("  Título   con  espacios ", "Título con espacios"),
            ("Straße", "STRASSE"),  # casefold: ß -> ss
            ("İstanbul", "istanbul"),  # casefold -> NFKD -> sin marcas (U+0307)
            ("ＡＢＣ", "ABC"),  # noqa: RUF001 (ancho completo, NFKD)
            ("Title.", "Title"),
            ("“Quoted” it’s", '"Quoted" it\'s'),  # noqa: RUF001 (tipográficas)
        ],
    )
    def test_misma_clave(self, a: str, b: str) -> None:
        assert _title_key(a) == _title_key(b)
        assert _tt(a) == _tt(b)


@pytest.mark.unit
class TestTitleKeyFalsosMerges:
    """Títulos o años distintos deben seguir separados."""

    def test_mismo_titulo_distinto_anio(self) -> None:
        assert _tt("Café", 2019) != _tt("Café", 2020)

    def test_year_none_distinto_de_2020(self) -> None:
        assert _tt("Café", None) != _tt("Café", 2020)

    def test_cpp_no_se_funde_con_c(self) -> None:
        # Los símbolos (S*) se conservan; solo la puntuación (P*) se descarta.
        assert _title_key("C++ programming") != _title_key("C programming")
        assert _tt("C++ programming") != _tt("C programming")

    def test_numeracion_romana(self) -> None:
        assert _tt("Parte I") != _tt("Parte II")

    def test_orden_de_palabras(self) -> None:
        assert _tt("redes sociales") != _tt("sociales redes")


@pytest.mark.unit
class TestTtPurezaYNoRegresion:
    def test_misma_entrada_mismo_id(self) -> None:
        assert _tt("Café y Complejidad") == _tt("Café y Complejidad")

    def test_regla_exacta(self) -> None:
        import hashlib

        digest = hashlib.sha256(b"cafe y complejidad|2020").hexdigest()[:16]
        assert _tt("Café y Complejidad") == f"tt:{digest}"

    def test_digests_doi_y_src_valores_dorados(self) -> None:
        # Calculados con la implementación previa a D3: no deben cambiar.
        assert _compute_id("10.1/x", None, "T", 2020) == "doi:4d718a0a89634e64"
        assert (
            _compute_id("https://doi.org/10.1000/ABC", "W1", "T", 1)
            == "doi:a8d873c73f28e9fc"
        )
        assert _compute_id(None, "W123", "T", 2020) == "src:b9932de3e4b0566b"
        assert _compute_id(None, "S999", "otro", None) == "src:68906fb6f169feae"


@pytest.mark.unit
class TestTitleKeyRobustez:
    """Idempotencia, caracteres de formato y títulos solo de puntuación."""

    _DOD: ClassVar[list[str]] = [
        "Café y Complejidad",
        "Self-Organization",
        "  Título   con  espacios ",
        "Straße",
        "İstanbul",
        "ＡＢＣ",  # noqa: RUF001
        "Title.",
        "“Quoted” it’s",  # noqa: RUF001
        "C++ programming",
        "Parte II",
    ]

    @pytest.mark.parametrize("x", [*_DOD, "tm™", "tmTM", "℃", "№ 5", "..."])
    def test_idempotente(self, x: str) -> None:
        assert _title_key(_title_key(x)) == _title_key(x)

    def test_tm_y_symbol_coinciden(self) -> None:
        assert _title_key("tm™") == _title_key("tmTM") == "tmtm"

    def test_cf_se_descarta_sin_dejar_espacio(self) -> None:
        # guion blando, ZWSP y BOM se eliminan (no se vuelven espacio).
        assert _title_key("Self\u00adorganization") == _title_key("Selforganization")
        assert _title_key("a\u200bb") == "ab"
        assert _title_key("\ufeffTitle") == "title"

    @pytest.mark.parametrize("title", ["...", "???", "---", "—", ""])
    def test_titulo_solo_puntuacion_usa_clave_previa(self, title: str) -> None:
        import hashlib

        old = hashlib.sha256(f"{title.lower().strip()}|2020".encode()).hexdigest()
        assert _tt(title) == f"tt:{old[:16]}"

    def test_puntuacion_distinta_no_se_funde(self) -> None:
        assert _tt("...") != _tt("???")
        assert _tt("---") != _tt("—")
