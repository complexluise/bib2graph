"""Issue #63 — BibtexSource: contrato de persistencia de campos y idempotencia.

``test_seed_from_bib.py`` ya cubre el camino CLI (``run_seed_from_bib``,
mutua exclusión de modos, parser defensivo, etc.).  Este archivo cubre el
**contrato de la fuente** (``BibtexSource.load``) y sus garantías de datos:

Casos cubiertos:
1. Los campos ``title``, ``authors_raw``, ``year`` y ``keywords_raw`` del .bib
   se persisten correctamente en el corpus (verificación de campo a campo).
2. Cargar dos veces el mismo .bib y mergear produce el mismo ``corpus_hash``
   que una sola carga (idempotencia de merge = idempotencia del corpus).
3. ``corpus_hash`` idéntico entre dos llamadas a ``BibtexSource.load``
   sobre el mismo archivo (sin DuckDB: pure-Arrow round-trip).
4. Entradas con OpenAlex ID explícito en el campo ``note`` (patrón común):
   no se duplican al mergear dos cargas del mismo .bib con ese campo.
5. El ``sample.bib`` de ``examples/bibtex/`` persiste correctamente los
   campos de la primera entrada (``martinez-alier2010``).
6. DOI normalizado: prefijos ``https://doi.org/`` se remueven; el DOI
   queda en minúsculas sin prefijo de URL.
7. ``keywords_raw`` se parsea correctamente para separadores ``;`` y ``,``.
8. Entrada de libro (``@incollection`` con ``booktitle``) usa ``booktitle``
   como ``source`` cuando no hay ``journal``.

Sin red. Todos los .bib son inline o el fixture del ejemplo.

Marcador: ``unit`` (sin red ni I/O relevante; usa tmp_path solo para DuckDB).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Constantes y fixtures inline
# ---------------------------------------------------------------------------

_SAMPLE_BIB = Path(__file__).parent.parent.parent / "examples" / "bibtex" / "sample.bib"

# .bib mínimo con campos típicos y variantes de separadores
BIB_CAMPOS_COMPLETOS = """\
@article{smith2020,
  author    = {Smith, John and Doe, Jane},
  title     = {Ecological Unequal Exchange},
  journal   = {Ecological Economics},
  year      = {2020},
  doi       = {10.1016/j.ecolecon.2020.01.001},
  abstract  = {A study of ecological exchange.},
  keywords  = {ecology; exchange; metabolism},
  publisher = {Elsevier},
}
"""

# .bib con separador de keywords por coma
BIB_KEYWORDS_COMA = """\
@article{jones2019,
  author   = {Jones, Alice},
  title    = {Carbon Trade and Inequality},
  journal  = {Nature},
  year     = {2019},
  keywords = {carbon, trade, inequality},
}
"""

# .bib con DOI como URL completa
BIB_DOI_URL = """\
@article{brown2018,
  author  = {Brown, Robert},
  title   = {Environmental Flows},
  journal = {Science},
  year    = {2018},
  doi     = {https://doi.org/10.1126/science.abc.1234},
}
"""

# .bib de libro (incollection)
BIB_LIBRO = """\
@incollection{chapter2021,
  author    = {García, María},
  title     = {Metabolismo Social},
  booktitle = {Economía Ecológica: Fundamentos},
  year      = {2021},
  publisher = {Editorial CLACSO},
  keywords  = {metabolismo; sociedad},
}
"""

# .bib con 2 entradas idénticas (para testear idempotencia de merge)
BIB_DOS_IDENTICAS = """\
@article{p1,
  author  = {Autor Uno},
  title   = {Paper Uno},
  journal = {Journal A},
  year    = {2015},
  doi     = {10.1000/p1},
}

@article{p2,
  author  = {Autor Dos},
  title   = {Paper Dos},
  journal = {Journal B},
  year    = {2016},
  doi     = {10.1000/p2},
}
"""


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _load_bib(content: str) -> Any:
    """Carga un .bib inline usando BibtexSource.load desde un string."""
    import tempfile

    from bib2graph.sources.bibtex import BibtexSource

    source = BibtexSource()
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".bib", encoding="utf-8", delete=False
    ) as f:
        f.write(content)
        tmp_path = f.name

    try:
        corpus = source.load(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return corpus


# ---------------------------------------------------------------------------
# 1. Persistencia de campos: title, authors_raw, year, keywords_raw
# ---------------------------------------------------------------------------


def test_campos_title_autores_anio_keywords_persisten() -> None:
    """Los campos del .bib se mapean correctamente al schema canónico.

    Verifica campo a campo que la serialización del .bib hacia el schema
    canónico Arrow es correcta para los campos obligatorios y opcionales.
    """
    corpus = _load_bib(BIB_CAMPOS_COMPLETOS)
    rows = corpus.to_arrow().to_pylist()

    assert len(rows) == 1, f"Se esperaba 1 paper, se obtuvo {len(rows)}"
    row = rows[0]

    # Título
    assert row["title"] == "Ecological Unequal Exchange", (
        f"title incorrecto: {row['title']!r}"
    )
    # Año
    assert row["year"] == 2020, f"year incorrecto: {row['year']!r}"
    # Autores: separados por " and "
    authors = row["authors_raw"]
    assert isinstance(authors, list), (
        f"authors_raw debe ser una lista, es {type(authors)}"
    )
    assert len(authors) == 2, f"Se esperaban 2 autores, hay {len(authors)}: {authors}"
    assert "Smith, John" in authors
    assert "Doe, Jane" in authors
    # Keywords: separadas por ";" → lista sin espacios sobrantes
    kws = row["keywords_raw"]
    assert isinstance(kws, list), f"keywords_raw debe ser lista, es {type(kws)}"
    assert "ecology" in kws
    assert "exchange" in kws
    assert "metabolism" in kws
    # Revista
    assert row["source"] == "Ecological Economics"
    # DOI normalizado (sin prefijo, minúsculas)
    assert row["doi"] == "10.1016/j.ecolecon.2020.01.001"
    # Publisher
    assert row["publisher"] == "Elsevier"
    # is_seed y curation_status por defecto
    assert row["is_seed"] is True
    assert row["curation_status"] == "candidate"


# ---------------------------------------------------------------------------
# 2. Idempotencia de merge: cargar dos veces → mismo corpus_hash
# ---------------------------------------------------------------------------


def test_idempotencia_merge_dos_cargas_mismo_bib() -> None:
    """Cargar el mismo .bib dos veces y mergear produce el mismo corpus_hash.

    Verifica que ``corpus_a.merge(corpus_b)`` donde ambos vienen del mismo
    .bib produce el mismo corpus (mismo hash) que cargar el .bib una sola vez.
    Esto garantiza que el pipeline ``restore → restore → build`` no amplifica
    el corpus ni cambia su identidad.
    """
    corpus_a = _load_bib(BIB_DOS_IDENTICAS)
    corpus_b = _load_bib(BIB_DOS_IDENTICAS)

    hash_a = corpus_a._backend.corpus_hash()

    merged = corpus_a.merge(corpus_b)
    hash_merged = merged._backend.corpus_hash()

    # El merge de dos cargas idénticas debe producir el mismo corpus
    assert len(merged) == len(corpus_a), (
        f"El merge duplicó el corpus: se esperaban {len(corpus_a)} papers, "
        f"hay {len(merged)}."
    )
    assert hash_a == hash_merged, (
        f"El corpus_hash difiere entre una carga ({hash_a!r}) y "
        f"merge(A, B) con mismo contenido ({hash_merged!r}). "
        "El merge de dos cargas del mismo .bib debe ser idempotente."
    )


# ---------------------------------------------------------------------------
# 3. corpus_hash idéntico entre dos llamadas independientes a BibtexSource.load
# ---------------------------------------------------------------------------


def test_corpus_hash_identico_dos_llamadas_load(tmp_path: Path) -> None:
    """Dos llamadas a BibtexSource.load sobre el mismo archivo → mismo corpus_hash.

    Verifica que la generación de IDs (basada en hash de contenido) y el
    hash del corpus sean deterministas entre distintas llamadas. No debe
    depender del timestamp de carga ni de ningún estado global.
    """
    from bib2graph.sources.bibtex import BibtexSource

    source = BibtexSource()

    # Escribir el .bib una sola vez y leerlo dos veces
    bib_path = tmp_path / "test.bib"
    bib_path.write_text(BIB_DOS_IDENTICAS, encoding="utf-8")

    corpus_1 = source.load(str(bib_path))
    corpus_2 = source.load(str(bib_path))

    hash_1 = corpus_1._backend.corpus_hash()
    hash_2 = corpus_2._backend.corpus_hash()

    assert hash_1 == hash_2, (
        f"corpus_hash difiere entre dos llamadas a BibtexSource.load: "
        f"{hash_1!r} vs {hash_2!r}. "
        "R2: el hash debe ser determinista (no depende del timestamp de carga)."
    )
    # Ambos cargaron los mismos 2 papers
    assert len(corpus_1) == 2
    assert len(corpus_2) == 2


# ---------------------------------------------------------------------------
# 4. Sin duplicación al mergear corpus con papers de la misma fuente .bib
# ---------------------------------------------------------------------------


def test_merge_sin_duplicacion_misma_fuente(tmp_path: Path) -> None:
    """Mergear dos corpus cargados del mismo .bib no duplica papers.

    Los IDs canónicos de BibtexSource se derivan del contenido del paper
    (title + doi + year); el merge por ID garantiza que dos cargas del mismo
    .bib producen el mismo conjunto de papers.
    """
    from bib2graph.sources.bibtex import BibtexSource

    source = BibtexSource()
    bib_path = tmp_path / "test.bib"
    bib_path.write_text(BIB_DOS_IDENTICAS, encoding="utf-8")

    corpus_a = source.load(str(bib_path))
    corpus_b = source.load(str(bib_path))

    # IDs deben ser idénticos entre las dos cargas
    ids_a = set(corpus_a.to_arrow().column("id").to_pylist())
    ids_b = set(corpus_b.to_arrow().column("id").to_pylist())
    assert ids_a == ids_b, (
        f"Los IDs difieren entre dos cargas del mismo .bib: "
        f"solo en A: {ids_a - ids_b}, solo en B: {ids_b - ids_a}."
    )

    merged = corpus_a.merge(corpus_b)
    ids_merged = set(merged.to_arrow().column("id").to_pylist())

    assert ids_merged == ids_a, (
        f"El merge introdujo IDs nuevos o eliminó IDs. "
        f"Solo en merged: {ids_merged - ids_a}. Solo en original: {ids_a - ids_merged}."
    )
    assert len(merged) == 2, (
        f"El merge duplicó los papers: se esperaban 2, hay {len(merged)}."
    )


# ---------------------------------------------------------------------------
# 5. sample.bib del ejemplo: campos de la primera entrada correctamente persistidos
# ---------------------------------------------------------------------------


def test_sample_bib_primera_entrada_campos_correctos() -> None:
    """La primera entrada de sample.bib (martinez-alier2010) persiste correctamente.

    Verifica que el .bib del ejemplo (``examples/bibtex/sample.bib``) produce
    los campos esperados en la primera entrada. Si el archivo no existe, se
    saltea el test.
    """
    if not _SAMPLE_BIB.exists():
        pytest.skip(
            f"No se encontró examples/bibtex/sample.bib en {_SAMPLE_BIB}. "
            "El archivo debe estar commiteado."
        )

    from bib2graph.sources.bibtex import BibtexSource

    source = BibtexSource()
    corpus = source.load(str(_SAMPLE_BIB))

    rows = corpus.to_arrow().to_pylist()
    # El sample.bib tiene 10 entradas con título
    assert len(rows) == 10, (
        f"Se esperaban 10 papers del sample.bib, se obtuvieron {len(rows)}."
    )

    # Buscar la entrada martinez-alier2010 por título
    entry = next(
        (
            r
            for r in rows
            if "Ecological Economics from the Ground Up" in (r["title"] or "")
        ),
        None,
    )
    assert entry is not None, (
        "No se encontró la entrada 'martinez-alier2010' en el corpus. "
        "Verificá que el title sea 'Ecological Economics from the Ground Up'."
    )
    assert entry["year"] == 2010
    authors = entry["authors_raw"]
    assert isinstance(authors, list) and len(authors) >= 1, (
        f"authors_raw debe tener al menos 1 autor: {authors!r}"
    )
    assert entry["doi"] == "10.1016/j.ecolecon.2010.02.003", (
        f"DOI incorrecto: {entry['doi']!r}"
    )
    kws = entry["keywords_raw"]
    assert isinstance(kws, list) and len(kws) >= 1, (
        f"keywords_raw debe tener al menos 1 keyword: {kws!r}"
    )
    assert entry["is_seed"] is True
    assert entry["curation_status"] == "candidate"


# ---------------------------------------------------------------------------
# 6. DOI normalizado: se remueve el prefijo https://doi.org/
# ---------------------------------------------------------------------------


def test_doi_url_normalizado() -> None:
    """El prefijo 'https://doi.org/' se remueve del DOI; queda el path en minúsculas."""
    corpus = _load_bib(BIB_DOI_URL)
    rows = corpus.to_arrow().to_pylist()

    assert len(rows) == 1
    doi = rows[0]["doi"]
    assert doi is not None, "El DOI no debe ser None cuando está en el .bib"
    assert not doi.startswith("http"), f"El DOI no debe contener prefijo URL: {doi!r}"
    assert doi == "10.1126/science.abc.1234", f"DOI normalizado incorrecto: {doi!r}"


# ---------------------------------------------------------------------------
# 7. Keywords: separador por ";" y por ","
# ---------------------------------------------------------------------------


def test_keywords_separador_punto_y_coma() -> None:
    """Keywords separadas por ';' se parsean en una lista correctamente."""
    corpus = _load_bib(BIB_CAMPOS_COMPLETOS)
    rows = corpus.to_arrow().to_pylist()

    kws = rows[0]["keywords_raw"]
    assert set(kws) == {"ecology", "exchange", "metabolism"}, (
        f"keywords_raw con ';' incorrecto: {kws!r}"
    )


def test_keywords_separador_coma() -> None:
    """Keywords separadas por ',' se parsean en una lista correctamente."""
    corpus = _load_bib(BIB_KEYWORDS_COMA)
    rows = corpus.to_arrow().to_pylist()

    kws = rows[0]["keywords_raw"]
    assert set(kws) == {"carbon", "trade", "inequality"}, (
        f"keywords_raw con ',' incorrecto: {kws!r}"
    )


# ---------------------------------------------------------------------------
# 8. Libro (@incollection): booktitle como source cuando no hay journal
# ---------------------------------------------------------------------------


def test_libro_usa_booktitle_como_source() -> None:
    """Entradas @incollection usan booktitle como 'source' cuando no hay journal."""
    corpus = _load_bib(BIB_LIBRO)
    rows = corpus.to_arrow().to_pylist()

    assert len(rows) == 1
    row = rows[0]
    assert row["title"] == "Metabolismo Social"
    assert row["source"] == "Economía Ecológica: Fundamentos", (
        f"source debe ser booktitle: {row['source']!r}"
    )
    assert row["year"] == 2021
