"""Tests TDD del Hito 5 — Preprocessor (normalize + thesaurus).

Tests prescriptos:
- Thesaurus idempotente (aplicar 2x == 1x).
- Colapso multilingüe: aliases en/es/pt del mismo concepto → mismo canónico.
- normalize: canonicaliza authors_id con variantes (acentos, case).
- Preprocessor.normalize registra PreprocRef en el Manifest.
- Preprocessor.apply_thesaurus registra PreprocRef en el Manifest.

Marcador: ``unit`` (sin red, sin I/O).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest

from bib2graph.corpus import Corpus
from bib2graph.preprocessors.normalize import normalize_authors_id, normalize_language
from bib2graph.preprocessors.preprocessor import Preprocessor
from bib2graph.preprocessors.thesaurus import (
    apply_thesaurus_to_rows,
    load_thesaurus,
)
from bib2graph.schemas import CORPUS_SCHEMA

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Thesaurus de prueba (en memoria, sin archivo)
# ---------------------------------------------------------------------------

_THESAURUS_DICT = {
    "concepts": {
        "unequal_exchange": {
            "aliases_en": [
                "unequal exchange",
                "ecological unequal exchange",
                "unequal ecological exchange",
            ],
            "aliases_es": [
                "intercambio desigual",
                "intercambio ecológicamente desigual",
                "intercambio ecologico desigual",
            ],
            "aliases_pt": [
                "troca desigual",
                "troca ecológica desigual",
                "troca ecologica desigual",
            ],
        },
        "ecological_debt": {
            "aliases_en": ["ecological debt", "ecological deficit"],
            "aliases_es": ["deuda ecológica", "deuda ecologica"],
            "aliases_pt": ["dívida ecológica", "divida ecologica"],
        },
    }
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_corpus(*rows: dict[str, Any]) -> Corpus:
    table = pa.Table.from_pylist(list(rows), schema=CORPUS_SCHEMA)
    return Corpus.from_arrow(table)


def _base_row(
    id: str,
    *,
    keywords_raw: list[str] | None = None,
    keywords_id: list[str] | None = None,
    authors_id: list[str] | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    return {
        "id": id,
        "openalex_id": None,
        "doi": None,
        "title": f"Paper {id}",
        "year": 2020,
        "abstract": None,
        "source": None,
        "language": language,
        "publisher": None,
        "research_areas": None,
        "is_seed": True,
        "curation_status": "candidate",
        "provenance": None,
        "authors_raw": None,
        "authors_id": authors_id,
        "authors_affiliations": None,
        "keywords_raw": keywords_raw,
        "keywords_id": keywords_id,
        "institutions_raw": None,
        "institutions_id": None,
        "references_id": None,
        "references_doi": None,
        "cited_by_id": None,
    }


# ---------------------------------------------------------------------------
# Tests de thesaurus puro
# ---------------------------------------------------------------------------


class TestLoadThesaurus:
    def test_load_desde_dict(self) -> None:
        lookup = load_thesaurus(_THESAURUS_DICT)
        assert isinstance(lookup, dict)
        assert len(lookup) > 0

    def test_load_desde_path(self, tmp_path: Path) -> None:
        import json

        thesaurus_path = tmp_path / "thesaurus.json"
        thesaurus_path.write_text(json.dumps(_THESAURUS_DICT), encoding="utf-8")
        lookup = load_thesaurus(thesaurus_path)
        assert isinstance(lookup, dict)

    def test_canonical_es_alias_de_si_mismo(self) -> None:
        """El propio canónico debe mapearse a sí mismo (idempotencia)."""
        lookup = load_thesaurus(_THESAURUS_DICT)
        # 'unequal_exchange' normalizado debe mapear a 'unequal_exchange'
        from bib2graph.preprocessors.thesaurus import _norm

        assert lookup.get(_norm("unequal_exchange")) == "unequal_exchange"


class TestApplyThesaurus:
    def test_colapso_multilingue(self) -> None:
        """Alias en inglés, español y portugués del mismo concepto → mismo canónico."""
        lookup = load_thesaurus(_THESAURUS_DICT)

        rows_en = [_base_row("P1", keywords_raw=["unequal exchange"])]
        rows_es = [_base_row("P2", keywords_raw=["intercambio ecologico desigual"])]
        rows_pt = [_base_row("P3", keywords_raw=["troca desigual"])]

        result_en = apply_thesaurus_to_rows(rows_en, lookup)
        result_es = apply_thesaurus_to_rows(rows_es, lookup)
        result_pt = apply_thesaurus_to_rows(rows_pt, lookup)

        canonical_en = result_en[0]["keywords_id"]
        canonical_es = result_es[0]["keywords_id"]
        canonical_pt = result_pt[0]["keywords_id"]

        # Los tres deben dar el mismo canónico
        assert canonical_en == canonical_es == canonical_pt
        assert canonical_en == ["unequal_exchange"]

    def test_idempotente(self) -> None:
        """Aplicar el thesaurus dos veces produce el mismo resultado que una."""
        lookup = load_thesaurus(_THESAURUS_DICT)
        rows = [_base_row("P1", keywords_raw=["ecological debt", "unequal exchange"])]

        once = apply_thesaurus_to_rows(rows, lookup)
        # Simular segunda aplicación (keywords_raw no cambia, keywords_id cambia)
        # La segunda pasada lee keywords_raw nuevamente (idempotente por diseño)
        twice = apply_thesaurus_to_rows(once, lookup)

        assert once[0]["keywords_id"] == twice[0]["keywords_id"]

    def test_keywords_no_matcheadas_se_dejan(self) -> None:
        """Keyword que no matchea ningún alias permanece como normalización mínima."""
        lookup = load_thesaurus(_THESAURUS_DICT)
        rows = [_base_row("P1", keywords_raw=["alguna keyword rara"])]
        result = apply_thesaurus_to_rows(rows, lookup)
        kw_ids = result[0]["keywords_id"]
        assert isinstance(kw_ids, list)
        assert len(kw_ids) == 1
        # Debe ser la versión normalizada (minúsculas, sin acentos)
        assert kw_ids[0] == "alguna keyword rara"

    def test_sin_keywords_raw_no_toca_keywords_id(self) -> None:
        """Sin keywords_raw, keywords_id no debe modificarse."""
        lookup = load_thesaurus(_THESAURUS_DICT)
        rows = [_base_row("P1", keywords_raw=None, keywords_id=["algo"])]
        result = apply_thesaurus_to_rows(rows, lookup)
        # keywords_id debe permanecer intacto
        assert result[0]["keywords_id"] == ["algo"]

    def test_deduplicacion_cuando_dos_aliases_mapean_al_mismo_canonico(self) -> None:
        """Dos aliases del mismo concepto en keywords_raw dan un solo canónico."""
        lookup = load_thesaurus(_THESAURUS_DICT)
        # 'unequal exchange' y 'ecological unequal exchange' → mismo canónico
        rows = [
            _base_row(
                "P1",
                keywords_raw=["unequal exchange", "ecological unequal exchange"],
            )
        ]
        result = apply_thesaurus_to_rows(rows, lookup)
        kw_ids = result[0]["keywords_id"]
        assert isinstance(kw_ids, list)
        assert kw_ids.count("unequal_exchange") == 1  # solo una vez


# ---------------------------------------------------------------------------
# Tests de normalize puro
# ---------------------------------------------------------------------------


class TestNormalizeAuthorsId:
    def test_lowercase_y_sin_acentos(self) -> None:
        result = normalize_authors_id(["García, Luis", "MÜLLER, Hans"])
        assert result is not None
        # Minúsculas y sin diacríticos
        assert result[0] == "garcia, luis"
        assert result[1] == "muller, hans"

    def test_colapso_espacios(self) -> None:
        result = normalize_authors_id(["  Smith,   John  "])
        assert result == ["smith, john"]

    def test_none_devuelve_none(self) -> None:
        assert normalize_authors_id(None) is None

    def test_lista_vacia_devuelve_none(self) -> None:
        assert normalize_authors_id([]) is None

    def test_idempotente(self) -> None:
        original = ["García, Luis"]
        once = normalize_authors_id(original)
        assert once is not None
        twice = normalize_authors_id(once)
        assert once == twice


class TestNormalizeLanguage:
    def test_subtag_primario(self) -> None:
        assert normalize_language("en-US") == "en"
        assert normalize_language("es_419") == "es"
        assert normalize_language("pt-BR") == "pt"

    def test_ya_iso_639_1(self) -> None:
        assert normalize_language("en") == "en"
        assert normalize_language("ES") == "es"

    def test_none_devuelve_none(self) -> None:
        assert normalize_language(None) is None

    def test_cadena_vacia_devuelve_none(self) -> None:
        assert normalize_language("") is None


# ---------------------------------------------------------------------------
# Tests del Preprocessor (orquestador)
# ---------------------------------------------------------------------------


class TestPreprocessorNormalize:
    def test_normalize_canonicaliza_authors_id(self) -> None:
        corpus = _make_corpus(
            _base_row("P1", authors_id=["García, Luis", "SMITH, John"])
        )
        preprocessor = Preprocessor()
        result = preprocessor.normalize(corpus)

        rows = result.to_arrow().to_pylist()
        assert rows[0]["authors_id"] == ["garcia, luis", "smith, john"]

    def test_normalize_canonicaliza_language(self) -> None:
        corpus = _make_corpus(_base_row("P1", language="en-US"))
        preprocessor = Preprocessor()
        result = preprocessor.normalize(corpus)

        rows = result.to_arrow().to_pylist()
        assert rows[0]["language"] == "en"

    def test_normalize_registra_preproc_ref(self) -> None:
        corpus = _make_corpus(_base_row("P1"))
        preprocessor = Preprocessor()
        result = preprocessor.normalize(corpus)

        assert len(result.manifest.preprocessors) == 1
        assert result.manifest.preprocessors[0].name == "normalize"

    def test_normalize_no_muta_corpus_entrada(self) -> None:
        corpus = _make_corpus(_base_row("P1", authors_id=["García"]))
        preprocessor = Preprocessor()
        preprocessor.normalize(corpus)

        rows = corpus.to_arrow().to_pylist()
        assert rows[0]["authors_id"] == ["García"]


class TestPreprocessorThesaurus:
    def test_apply_thesaurus_sobrescribe_keywords_id(self) -> None:
        corpus = _make_corpus(_base_row("P1", keywords_raw=["unequal exchange"]))
        preprocessor = Preprocessor()
        result = preprocessor.apply_thesaurus(corpus, _THESAURUS_DICT)

        rows = result.to_arrow().to_pylist()
        assert rows[0]["keywords_id"] == ["unequal_exchange"]

    def test_apply_thesaurus_registra_preproc_ref(self) -> None:
        corpus = _make_corpus(_base_row("P1", keywords_raw=["ecological debt"]))
        preprocessor = Preprocessor()
        result = preprocessor.apply_thesaurus(corpus, _THESAURUS_DICT)

        assert len(result.manifest.preprocessors) == 1
        assert result.manifest.preprocessors[0].name == "apply_thesaurus"

    def test_apply_thesaurus_idempotente(self) -> None:
        """Aplicar el thesaurus dos veces == una vez."""
        corpus = _make_corpus(
            _base_row("P1", keywords_raw=["ecological debt", "unequal exchange"])
        )
        preprocessor = Preprocessor()
        once = preprocessor.apply_thesaurus(corpus, _THESAURUS_DICT)
        twice = preprocessor.apply_thesaurus(once, _THESAURUS_DICT)

        rows_once = once.to_arrow().to_pylist()
        rows_twice = twice.to_arrow().to_pylist()
        assert rows_once[0]["keywords_id"] == rows_twice[0]["keywords_id"]

    def test_apply_thesaurus_acepta_path(self, tmp_path: Path) -> None:
        import json

        thesaurus_path = tmp_path / "thesaurus.json"
        thesaurus_path.write_text(json.dumps(_THESAURUS_DICT), encoding="utf-8")
        corpus = _make_corpus(_base_row("P1", keywords_raw=["unequal exchange"]))
        preprocessor = Preprocessor()
        result = preprocessor.apply_thesaurus(corpus, thesaurus_path)

        rows = result.to_arrow().to_pylist()
        assert rows[0]["keywords_id"] == ["unequal_exchange"]
        # El manifest debe registrar el source del path
        assert "source" in result.manifest.preprocessors[0].params
