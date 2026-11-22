"""Tests del Corte 5 (#252) del ADR 0053: ``DoajSource``, 1ª fuente Sur-global.

Sin red: ``httpx.MockTransport`` sobre respuestas reales de la API v4 de DOAJ
(``tests/fixtures/doaj/``, recortadas a 3-4 artículos; ES y PT).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pyarrow as pa
import pytest
from click.testing import CliRunner

from bib2graph.cli import b2g
from bib2graph.cli._errors import DependencyError
from bib2graph.constants import Col, CurationStatus, Provider
from bib2graph.corpus import Corpus, _compute_id, _rows_with_ids
from bib2graph.schemas import CORPUS_SCHEMA, ProvenanceEvent
from bib2graph.service.errors import DataError, NetworkError
from bib2graph.sources.base import Source
from bib2graph.sources.doaj import DoajSource, _article_to_row
from bib2graph.sources.openalex import _normalize_doi
from bib2graph.sources.registry import PROVIDERS, Capability, make_source
from bib2graph.workspace import Workspace

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "doaj"


def _fixture(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        (FIXTURES / f"search_{name}.json").read_text(encoding="utf-8")
    )
    return data


def _transport(*, seen: list[httpx.Request] | None = None) -> httpx.MockTransport:
    """Mock DOAJ: la query decide el fixture; solo la página 1 trae resultados."""

    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        assert "/search/articles/" in request.url.path
        if request.url.params.get("page") != "1":
            return httpx.Response(200, json={"total": 0, "results": []})
        fixture = "pt" if "complexidade" in request.url.path else "es"
        return httpx.Response(200, json=_fixture(fixture))

    return httpx.MockTransport(handler)


class _ExplodingTransport(httpx.BaseTransport):
    """Falla si se lo llama: prueba "falla antes de la red"."""

    def __init__(self) -> None:
        self.calls = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        raise AssertionError("se tocó la red")


@pytest.fixture
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    sleeps: list[float] = []
    monkeypatch.setattr("bib2graph.sources.doaj.time.sleep", sleeps.append)
    return sleeps


def _s2_like_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"total": 0, "data": []})

    return httpx.MockTransport(handler)


def _rows(corpus: Corpus) -> list[dict[str, Any]]:
    return corpus.to_arrow().to_pylist()


# Source: seed + mapeo


class TestDoajSeed:
    def test_doaj_seed_mock_es(self) -> None:
        seen: list[httpx.Request] = []
        source = DoajSource(transport=_transport(seen=seen))

        result = source.seed("educación pensamiento complejo")

        rows = _rows(result.corpus)
        assert len(rows) == 4
        assert {r[Col.PROVIDER] for r in rows} == {"doaj"}
        assert all(r[Col.IS_SEED] for r in rows)
        # Query nativa tal cual, percent-encodeada en el path (v4, sin key).
        assert result.executed_query == "educación pensamiento complejo"
        assert any("sin traducción" in line for line in result.translation_report)
        assert seen[0].url.path.startswith("/api/v4/search/articles/")
        assert "x-api-key" not in seen[0].headers
        assert "authorization" not in seen[0].headers
        # Mínimo universal + metadata de la revista.
        con_kw = next(r for r in rows if r[Col.KEYWORDS_RAW])
        assert con_kw[Col.TITLE]
        assert con_kw[Col.YEAR] is not None
        assert con_kw[Col.AUTHORS_RAW]
        assert con_kw[Col.SOURCE]
        # Sin citas: nada que proyectar a citación.
        assert all(not r[Col.REFERENCES_ID] for r in rows)
        assert all(not r[Col.CITED_BY_ID] for r in rows)

    def test_doaj_seed_mock_pt(self) -> None:
        source = DoajSource(transport=_transport())

        result = source.seed("ecologia complexidade")

        rows = _rows(result.corpus)
        assert len(rows) == 3
        assert {r[Col.PROVIDER] for r in rows} == {"doaj"}
        assert all(r[Col.DOI] for r in rows)  # el fixture PT trae DOI en los 3

    def test_doaj_seed_sella_provenance_y_ecuacion(self) -> None:
        result = DoajSource(transport=_transport()).seed("educación x")

        for row in _rows(result.corpus):
            event = ProvenanceEvent.parse_list(row[Col.PROVENANCE])[0]
            assert event.source == "doaj"
            assert event.source_kind == "seed_equation"
            assert event.equation_id == result.corpus.manifest.equations[0].equation_id
        eq = result.corpus.manifest.equations[0]
        assert eq.engine == "doaj"
        assert eq.params["raw_query"] == "educación x"
        assert eq.params["executed_query"] == "educación x"
        assert eq.created_at

    @pytest.mark.parametrize("max_results", [150, 250, 999])
    def test_doaj_pagina_sin_duplicados_ni_saltos(self, max_results: int) -> None:
        """El mock respeta ``page``/``pageSize`` como DOAJ: offset=(page-1)*pageSize.

        Con pageSize variable en la última página (bug previo) se duplicaban
        unos resultados y se perdían otros.
        """
        total = 1200
        universe = [
            {
                "id": f"art{i:05d}",
                "bibjson": {"title": f"Articulo sintetico {i}", "year": "2020"},
            }
            for i in range(total)
        ]
        requested: list[tuple[int, int]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            page = int(request.url.params["page"])
            size = int(request.url.params["pageSize"])
            requested.append((page, size))
            start = (page - 1) * size
            return httpx.Response(
                200, json={"total": total, "results": universe[start : start + size]}
            )

        source = DoajSource(
            transport=httpx.MockTransport(handler), max_results=max_results
        )
        result = source.seed("q")

        source_ids = [r[Col.SOURCE_ID] for r in _rows(result.corpus)]
        assert len(source_ids) == len(set(source_ids)) == max_results
        assert set(source_ids) == {a["id"] for a in universe[:max_results]}
        # pageSize constante en todas las páginas.
        assert len({size for _, size in requested}) == 1
        assert [p for p, _ in requested] == list(range(1, len(requested) + 1))

    def test_doaj_max_results_fuera_de_rango(self) -> None:
        with pytest.raises(ValueError, match="max_results"):
            DoajSource(max_results=0)
        with pytest.raises(ValueError, match="max_results"):
            DoajSource(max_results=1001)

    def test_doaj_cumple_source_y_load_es_error_accionable(self) -> None:
        source = DoajSource()
        assert isinstance(source, Source)
        with pytest.raises(NotImplementedError, match="seed"):
            source.load("x.bib")

    def test_doaj_400_es_dataerror_no_reintenta(self, _no_sleep: list[float]) -> None:
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            return httpx.Response(400, json={"status": "bad_request", "error": "boom"})

        with pytest.raises(DataError, match="Lucene"):
            DoajSource(transport=httpx.MockTransport(handler)).seed("a:(")
        assert len(calls) == 1
        assert _no_sleep == []


# Identidad (R3)


class TestDoajIdentidad:
    def _articles(self) -> list[dict[str, Any]]:
        return _fixture("es")["results"]

    def test_doaj_sin_doi_usa_src_no_tt(self) -> None:
        sin_doi = next(
            a
            for a in self._articles()
            if not any(i["type"] == "doi" for i in a["bibjson"]["identifier"])
        )
        row = _article_to_row(sin_doi, equation_id="eq", fetched_at="t")
        (with_id,) = _rows_with_ids([row])

        assert row[Col.DOI] is None
        assert row[Col.SOURCE_ID] == sin_doi["id"]
        assert str(with_id[Col.ID]).startswith("src:")
        assert not str(with_id[Col.ID]).startswith("tt:")

    def test_doaj_con_doi_mismo_id_que_openalex(self) -> None:
        con_doi = next(
            a
            for a in self._articles()
            if any(i["type"] == "doi" for i in a["bibjson"]["identifier"])
        )
        row = _article_to_row(con_doi, equation_id="eq", fetched_at="t")
        (with_id,) = _rows_with_ids([row])
        doi = row[Col.DOI]

        assert doi and doi == doi.lower() and not doi.startswith("http")
        # Mismo id que produce OpenAlex para ese DOI (con su W… como source_id).
        assert with_id[Col.ID] == _compute_id(doi, "W123456", "otro titulo", 1999)
        assert str(with_id[Col.ID]).startswith("doi:")

    @pytest.mark.parametrize(
        "raw",
        [
            "10.1000/Abc.1",
            " 10.1000/abc.1 ",
            "doi:10.1000/abc.1",
            "DOI:10.1000/abc.1 ",
            "https://doi.org/10.1000/ABC.1",
            "HTTP://DOI.ORG/10.1000/abc.1",
            "https://dx.doi.org/10.1000/abc.1",
            "http://dx.doi.org/10.1000/abc.1",
            "doi.org/10.1000/abc.1",
            "dx.doi.org/10.1000/abc.1",
        ],
    )
    def test_doi_variantes_normalizan_igual_y_dan_mismo_id_que_openalex(
        self, raw: str
    ) -> None:
        art = {
            "id": "xyz",
            "bibjson": {
                "title": "T",
                "year": "2020",
                "identifier": [{"id": raw, "type": "doi"}],
            },
        }
        row = _article_to_row(art, equation_id=None, fetched_at="t")
        (with_id,) = _rows_with_ids([row])

        assert row[Col.DOI] == "10.1000/abc.1"
        # OpenAlex entrega el DOI como URL https://doi.org/...
        oa_doi = _normalize_doi("https://doi.org/10.1000/abc.1")
        assert with_id[Col.ID] == _compute_id(oa_doi, "W1", "otro", 1999)

    def test_doi_vacio_o_solo_prefijo_es_none(self) -> None:
        assert _normalize_doi("  ") is None
        assert _normalize_doi("doi:") is None
        assert _normalize_doi(None) is None

    def test_orcid_en_forma_corta(self) -> None:
        art = {
            "id": "xyz",
            "bibjson": {
                "title": "T",
                "author": [
                    {
                        "name": "Ana",
                        "orcid_id": "https://orcid.org/0000-0002-1825-0097",
                    },
                    {"name": "Beto", "orcid_id": "0000-0001-0000-0001"},
                    {"name": "Cami"},
                ],
            },
        }
        row = _article_to_row(art, equation_id=None, fetched_at="t")
        assert row[Col.AUTHORS_ID] == [
            "0000-0002-1825-0097",
            "0000-0001-0000-0001",
            "Cami",
        ]

    def test_issn_no_se_confunde_con_doi(self) -> None:
        art = {
            "id": "abc",
            "bibjson": {
                "title": "T",
                "year": "2020",
                "identifier": [{"id": "1234-5678", "type": "eissn"}],
            },
        }
        row = _article_to_row(art, equation_id=None, fetched_at="t")
        assert row[Col.DOI] is None
        assert row[Col.YEAR] == 2020


# Reintentos / subcodes (ADR 0045)


class TestDoajRetry:
    def test_doaj_429_reintenta_y_mapea_subcode(self, _no_sleep: list[float]) -> None:
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            return httpx.Response(429, headers={"Retry-After": "7"})

        source = DoajSource(transport=httpx.MockTransport(handler))
        with pytest.raises(NetworkError) as exc_info:
            source.seed("q")

        assert exc_info.value.subcode == "RATE_LIMITED"
        assert exc_info.value.exit_code == 4
        assert "Retry-After: 7" in exc_info.value.message
        assert len(calls) == 3
        assert _no_sleep == [1.0, 2.0]

    def test_doaj_504_mapea_upstream_timeout(self, _no_sleep: list[float]) -> None:
        source = DoajSource(
            transport=httpx.MockTransport(lambda r: httpx.Response(504))
        )
        with pytest.raises(NetworkError) as exc_info:
            source.seed("q")
        assert exc_info.value.subcode == "UPSTREAM_TIMEOUT"

    def test_doaj_429_transitorio_se_recupera(self, _no_sleep: list[float]) -> None:
        state = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            state["n"] += 1
            if state["n"] <= 2:
                return httpx.Response(429)
            if request.url.params.get("page") != "1":
                return httpx.Response(200, json={"total": 0, "results": []})
            return httpx.Response(200, json=_fixture("pt"))

        result = DoajSource(transport=httpx.MockTransport(handler)).seed("q")
        assert len(result.corpus) == 3
        assert _no_sleep == [1.0, 2.0]


# Registro, capacidades y superficie CLI


class TestDoajRegistro:
    def test_doaj_declara_solo_seed(self) -> None:
        assert PROVIDERS[Provider.DOAJ].capabilities == frozenset({Capability.SEED})
        assert isinstance(make_source(Provider.DOAJ), DoajSource)

    def test_workspace_source_doaj_valido(self, tmp_path: Path) -> None:
        ws = Workspace.init(tmp_path / "w", "w", source=Provider.DOAJ)
        raw = json.loads((ws.root / "workspace.json").read_text(encoding="utf-8"))
        assert raw["source"] == "doaj"
        assert Workspace.open(ws.root).provider == Provider.DOAJ

    def test_init_cli_source_doaj(self, tmp_path: Path, monkeypatch: Any) -> None:
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(b2g, ["init", "inv", "--source", "doaj"])
        assert result.exit_code == 0, result.output
        raw = json.loads((tmp_path / "inv" / "workspace.json").read_text("utf-8"))
        assert raw["source"] == "doaj"

    def test_preview_doaj_query_nativa_sin_red(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(
            b2g,
            ["seed", "--equation", "a b", "--source", "doaj", "--preview", "--json"],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout.strip().splitlines()[-1])["data"]
        assert data["executed_query"] == "a b"
        assert any(
            "DOAJ" in w and "sin traducción" in w for w in data["translation_report"]
        )
        assert data["provider"] == {"name": "doaj", "origin": "flag"}

    @pytest.mark.parametrize(
        "kwargs",
        [{"exclude": ["y"]}, {"native": True}, {"min_year": 2000}, {"max_year": 2020}],
    )
    def test_seed_doaj_con_filtros_es_error_antes_de_red(
        self, tmp_path: Path, kwargs: dict[str, Any]
    ) -> None:
        from bib2graph.cli.commands.seed import run_seed

        transport = _ExplodingTransport()
        store_path = tmp_path / "lib.duckdb"
        with pytest.raises(DependencyError) as exc_info:
            run_seed(
                store_path, "x", provider=Provider.DOAJ, transport=transport, **kwargs
            )
        assert exc_info.value.exit_code == 3
        assert transport.calls == 0
        assert not store_path.exists()

    def test_email_con_doaj_no_se_ignora_en_silencio(self, tmp_path: Path) -> None:
        ws = Workspace.init(tmp_path / "w", "w")
        result = CliRunner().invoke(
            b2g,
            ["--workspace", str(ws.root), "seed", "--equation", "x",
             "--source", "doaj", "--email", "a@b.c", "--json"],
        )  # fmt: skip
        assert result.exit_code == 1, result.output
        assert "DOAJ" in result.output


class TestDoajCli:
    def test_seed_doaj_persiste_en_carril_doaj(self, tmp_path: Path) -> None:
        from bib2graph.cli.commands.seed import run_seed
        from bib2graph.stores.duckdb import DuckDBStore

        store_path = tmp_path / "lib.duckdb"
        data = run_seed(
            store_path,
            "educación pensamiento complejo",
            provider=Provider.DOAJ,
            transport=_transport(),
        )
        assert data["papers_added"] == 4

        store = DuckDBStore(store_path, provider=Provider.DOAJ)
        try:
            rows = store.load().to_arrow().to_pylist()
            con = store.backend._con  # type: ignore[attr-defined]
            engines = con.execute("SELECT engine FROM equations").fetchall()
            ext = con.execute("SELECT DISTINCT engine FROM external_ids").fetchall()
        finally:
            store.close()
        assert len(rows) == 4
        assert {r[Col.PROVIDER] for r in rows} == {"doaj"}
        assert engines == [("doaj",)]
        assert ext == [("doaj",)]  # source_id = id de artículo DOAJ

    def test_chain_doaj_falla_antes_de_red(self, tmp_path: Path) -> None:
        from bib2graph.cli.commands.chain import run_chain

        transport = _ExplodingTransport()
        store_path = tmp_path / "lib.duckdb"
        for direction in ("forward", "backward", "both"):
            with pytest.raises(DependencyError) as exc_info:
                run_chain(
                    store_path,
                    direction=direction,
                    provider=Provider.DOAJ,
                    transport=transport,
                )
            assert exc_info.value.exit_code == 3
            assert "doaj" in exc_info.value.message
        assert transport.calls == 0
        assert not store_path.exists()

    def test_chain_doaj_cli_exit_3(self, tmp_path: Path) -> None:
        ws = Workspace.init(tmp_path / "w", "w", source=Provider.DOAJ)
        result = CliRunner().invoke(
            b2g, ["--workspace", str(ws.root), "chain", "--json"]
        )
        assert result.exit_code == 3, result.output

    def test_build_doaj_redes_de_citas_vacias_con_warning(self, tmp_path: Path) -> None:
        from bib2graph.cli.commands.build import run_build
        from bib2graph.stores.duckdb import DuckDBStore

        # Corpus DOAJ con semillas ACEPTADAS (dispara la pasada cited_by, que
        # DOAJ no declara: se omite sin tocar la red).
        rows = []
        for art in _fixture("pt")["results"]:
            row = _article_to_row(art, equation_id="eq", fetched_at="t")
            row[Col.CURATION_STATUS] = CurationStatus.ACCEPTED
            rows.append(row)
        table = pa.Table.from_pylist(_rows_with_ids(rows), schema=CORPUS_SCHEMA)
        store_path = tmp_path / "lib.duckdb"
        store = DuckDBStore(store_path, provider=Provider.DOAJ)
        store.persist(Corpus.from_arrow(table))
        store.close()

        transport = _ExplodingTransport()
        data = run_build(
            store_path,
            out_dir=tmp_path / "nets",
            provider=Provider.DOAJ,
            transport=transport,
        )

        assert transport.calls == 0
        # UN solo warning por lo mismo (no además el de la pasada cited_by).
        assert len(data["warnings"]) == 1
        assert "no expone citas" in data["warnings"][0]
        nets = {n["kind"]: n for n in data["networks"]}
        empty = {e["kind"]: e for e in data["empty_networks"]}
        # Redes SIN citas: tienen datos reales (el fixture PT trae un paper con
        # 3 autores y varios con keywords) -> no vacías.
        for kind in ("author_collab", "keyword_cooccurrence"):
            assert kind in nets, kind
            assert nets[kind]["edges"] > 0, kind
            assert kind not in empty, kind
        # Redes de CITAS: vacías, y sin sugerir un comando que da exit 3.
        assert "bibliographic_coupling" in empty
        assert empty["bibliographic_coupling"]["fix_command"] is None
        # La co-citación ni se arma (Networks.quick la omite sin cited_by_id).
        assert "cocitation" not in nets
        assert (
            "institution_collab" not in nets or nets["institution_collab"]["edges"] == 0
        )
        # Sin sugerir `chain forward` (DOAJ no lo soporta).
        assert not any("chain forward" in w for w in data["warnings"])
        assert (tmp_path / "nets" / ".provider").read_text("utf-8") == "doaj"


class TestDoajCoexistencia:
    def test_seed_cli_source_doaj_en_investigacion_openalex(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sembrar en el carril doaj no toca el hash del carril openalex."""
        from bib2graph.backends.memory import compute_corpus_hash
        from bib2graph.sources.registry import ProviderSpec
        from bib2graph.stores.duckdb import DuckDBStore

        ws = Workspace.init(tmp_path / "w", "w")  # openalex

        oa_row: dict[str, Any] = {name: None for name in CORPUS_SCHEMA.names}
        oa_row.update(
            {
                "id": "P1",
                "title": "OA paper",
                "year": 2020,
                "provider": "openalex",
                "is_seed": True,
                "curation_status": "candidate",
                "cited_by_id": [],
            }
        )
        store = DuckDBStore(ws.library_path, provider="openalex")
        store.persist(
            Corpus.from_arrow(pa.Table.from_pylist([oa_row], schema=CORPUS_SCHEMA))
        )
        store.close()

        def lane_hash(provider: Provider) -> str:
            s = DuckDBStore(ws.library_path, provider=provider)
            try:
                return compute_corpus_hash(s.load().to_arrow())
            finally:
                s.close()

        before = lane_hash(Provider.OPENALEX)

        # La CLI no inyecta transport: se reemplaza la fábrica del registro.
        monkeypatch.setitem(
            PROVIDERS,
            Provider.DOAJ,
            ProviderSpec(
                factory=lambda **_: DoajSource(transport=_transport()),
                capabilities=PROVIDERS[Provider.DOAJ].capabilities,
            ),
        )
        result = CliRunner().invoke(
            b2g,
            [
                "--workspace", str(ws.root), "seed",
                "--equation", "educación pensamiento complejo",
                "--source", "doaj", "--json",
            ],
        )  # fmt: skip

        assert result.exit_code == 0, result.output
        assert lane_hash(Provider.OPENALEX) == before
        s = DuckDBStore(ws.library_path, provider=Provider.DOAJ)
        try:
            doaj_rows = s.load().to_arrow().to_pylist()
        finally:
            s.close()
        assert len(doaj_rows) == 4
        assert {r[Col.PROVIDER] for r in doaj_rows} == {"doaj"}


class TestDoajConsejos:
    def test_doaj_mapea_keywords_raw_y_id(self) -> None:
        art = {
            "id": "k",
            "bibjson": {
                "title": "T",
                "keywords": [
                    "Pensamiento Complejo",
                    " pensamiento complejo.",
                    "Educación",
                ],
            },
        }
        row = _article_to_row(art, equation_id=None, fetched_at="t")
        assert row[Col.KEYWORDS_RAW] == [
            "Pensamiento Complejo",
            "pensamiento complejo.",
            "Educación",
        ]
        assert row[Col.KEYWORDS_ID] == ["pensamiento complejo", "educación"]

    def test_status_doaj_no_sugiere_comandos_con_exit_3(self, tmp_path: Path) -> None:
        from bib2graph.cli.commands.seed import run_seed
        from bib2graph.cli.commands.status import run_status

        store_path = tmp_path / "lib.duckdb"
        run_seed(
            store_path, "educación pensamiento complejo",
            provider=Provider.DOAJ, transport=_transport(),
        )  # fmt: skip
        data = run_status(store_path, Provider.DOAJ)

        assert data["next_best_action"] == "build"
        assert "chain" not in data["transitions_available"]
        fixes = {
            str(i["fix_command"]) for i in data["build_preview"] if i["fix_command"]
        }
        assert not any("--resolve" in f for f in fixes)
        coc = next(i for i in data["build_preview"] if i["kind"] == "cocitation")
        assert coc["fix_command"] is None

    def test_status_openalex_sigue_sugiriendo_chain(self, tmp_path: Path) -> None:
        from bib2graph.cli.commands.seed import run_seed
        from bib2graph.cli.commands.status import run_status

        store_path = tmp_path / "lib.duckdb"
        run_seed(
            store_path, "x", provider=Provider.S2, transport=_s2_like_transport(),
        )  # fmt: skip
        data = run_status(store_path, Provider.S2)
        assert data["next_best_action"] == "chain"
        assert "chain" in data["transitions_available"]

    def test_read_top_doaj_no_sugiere_build_para_cocitacion(
        self, tmp_path: Path
    ) -> None:
        from bib2graph.cli.commands.seed import run_seed
        from bib2graph.service.reads import get_top

        ws = Workspace.init(tmp_path / "w", "w", source=Provider.DOAJ)
        run_seed(
            ws.library_path, "educación pensamiento complejo",
            provider=Provider.DOAJ, transport=_transport(),
        )  # fmt: skip
        data = get_top(ws, kind="author_collab", provider=Provider.DOAJ)

        assert data["cocitation"] == []
        assert data.get("fix_command") is None
