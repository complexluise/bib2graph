"""bibtex — ``BibtexSource``: siembra un ``Corpus`` desde un archivo .bib.

Import de ``bibtexparser`` es PEREZOSO: se hace dentro de ``load()`` para no
acoplar el núcleo al extra ``[bibtex]``.  Si el extra falta, el error es claro
y apunta al comando de instalación.

Pre-procesador defensivo (bugfix T1 del sandbox): accede a todos los campos
con ``.get()`` y nunca falla por campo ausente.

BibTeX no soporta siembra por ecuación: ``seed()`` lanza ``NotImplementedError``
con un mensaje claro.

Mapeo de campos:
- ``author`` → ``authors_raw`` (``"Apellido, Nombre and …"`` → lista)
- ``title``, ``year``, ``journal``/``booktitle`` → ``title``, ``year``, ``source``
- ``doi`` → ``doi``
- ``keywords`` → ``keywords_raw``
- ``abstract`` → ``abstract``
- ``affiliation`` (campo no estándar) → ``authors_affiliations``
- ``publisher`` → ``publisher``

Ver ``docs/API.md`` §2, ADR 0018.
"""

from __future__ import annotations

import logging
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bib2graph.constants import Col, CurationStatus
from bib2graph.corpus import Corpus, _rows_with_ids
from bib2graph.schemas import CORPUS_SCHEMA, ProvenanceEvent

from .base import SeedResult

logger = logging.getLogger(__name__)


def _parse_authors(raw: str) -> list[str]:
    """Separa la cadena de autores BibTeX en una lista.

    BibTeX usa ``"Apellido, Nombre and Apellido2, Nombre2"`` o
    ``"Nombre Apellido and …"``.  Separa por `` and `` (case-insensitive),
    quita espacios sobrantes y filtra vacíos.

    Args:
        raw: Cadena de autores del campo BibTeX.

    Returns:
        Lista de autores como strings.
    """
    if not raw:
        return []
    parts = [p.strip() for p in raw.split(" and ")]
    return [p for p in parts if p]


def _entry_to_row(
    entry: dict[str, Any],
    *,
    fetched_at: str,
) -> dict[str, Any]:
    """Mapea una entrada bibtexparser al schema canónico.

    Acceso defensivo con ``.get()`` en todos los campos (bugfix T1: nunca
    ``entry["author"]`` → ``KeyError``).  Los campos opcionales ausentes
    quedan en ``None`` o ``[]``.

    Args:
        entry: Entrada de bibtexparser (dict de campos + metadatos).
        fetched_at: Timestamp ISO de la carga.

    Returns:
        Dict con todas las columnas del schema canónico (sin ``id``, que
        calcula ``Corpus.add_paper``).
    """
    raw_authors = str(entry.get("author") or "")
    authors_raw = _parse_authors(raw_authors) or None

    # Afiliación: campo no estándar del .bib → authors_affiliations
    affiliation = str(entry.get("affiliation") or "")
    authors_affiliations: list[str] | None = [affiliation] if affiliation else None

    # Keywords: separadas por comas o punto y coma
    raw_kw = str(entry.get("keywords") or "")
    if raw_kw:
        kw_list = [k.strip() for k in raw_kw.replace(";", ",").split(",") if k.strip()]
        keywords_raw: list[str] | None = kw_list or None
    else:
        keywords_raw = None

    # Venue: preferir journal, luego booktitle
    _venue_raw = entry.get("journal") or entry.get("booktitle")
    venue = str(_venue_raw) if _venue_raw else None

    # Año: convertir a int si es posible
    raw_year = entry.get("year")
    year: int | None = None
    if raw_year:
        try:
            year = int(str(raw_year).strip())
        except ValueError:
            year = None

    # DOI: normalizar quitando prefijo URL
    raw_doi = str(entry.get("doi") or "")
    doi: str | None = None
    if raw_doi:
        d = raw_doi.strip()
        for prefix in ("https://doi.org/", "http://doi.org/"):
            if d.startswith(prefix):
                d = d[len(prefix) :]
                break
        doi = d.lower() or None

    # Provenance
    provenance_event = ProvenanceEvent(
        action="seeded",
        equation_id=None,
        chaining_hop=None,
        source="bibtex",
        fetched_at=fetched_at,
        decided_by=None,
        decided_at=None,
    )

    return {
        Col.SOURCE_ID: None,
        Col.DOI: doi,
        Col.TITLE: str(entry.get("title") or "").strip() or "",
        Col.YEAR: year,
        Col.ABSTRACT: str(entry["abstract"]) if entry.get("abstract") else None,
        Col.SOURCE: venue,
        Col.LANGUAGE: None,
        Col.PUBLISHER: str(entry["publisher"]) if entry.get("publisher") else None,
        Col.RESEARCH_AREAS: None,
        Col.IS_SEED: True,
        Col.CURATION_STATUS: CurationStatus.CANDIDATE,
        Col.PROVENANCE: ProvenanceEvent.dump_list([provenance_event]),
        Col.AUTHORS_RAW: authors_raw,
        Col.AUTHORS_ID: None,
        Col.AUTHORS_AFFILIATIONS: authors_affiliations,
        Col.KEYWORDS_RAW: keywords_raw,
        Col.KEYWORDS_ID: None,
        Col.INSTITUTIONS_RAW: None,
        Col.INSTITUTIONS_ID: None,
        Col.REFERENCES_ID: None,
        Col.REFERENCES_DOI: None,
        Col.CITED_BY_ID: None,
    }


class BibtexSource:
    """Siembra un ``Corpus`` desde un archivo BibTeX.

    BibTeX es ``Source`` secundaria (ADR 0007): entrega el mínimo universal
    (título, año, autores, keywords) pero típicamente no referencias ni
    citantes.

    El import de ``bibtexparser`` es perezoso: se instala con el extra
    ``[bibtex]`` (``pip install "bib2graph[bibtex]"``).

    Example::

        source = BibtexSource()
        corpus = source.load("semillas.bib")
    """

    def seed(self, query: str) -> SeedResult:
        """No implementado: BibTeX no siembra por ecuación.

        Raises:
            NotImplementedError: Siempre. Usa ``load()`` en su lugar.
        """
        raise NotImplementedError(
            "BibtexSource no soporta siembra por ecuación. "
            "Usa load(path) para sembrar desde un archivo .bib. "
            "Para siembra por ecuación usa OpenAlexSource."
        )

    def load(self, path: str) -> Corpus:
        """Carga un archivo .bib como ``Corpus``.

        Todos los papers se marcan con ``is_seed=True`` y
        ``curation_status='candidate'``.  Campos faltantes quedan en ``None``
        (sin ``KeyError``, bugfix T1).

        Args:
            path: Ruta al archivo ``.bib``.

        Returns:
            ``Corpus`` con los papers del archivo.

        Raises:
            ImportError: Si ``bibtexparser`` no está instalado.
        """
        try:
            import bibtexparser
            from bibtexparser.bparser import BibTexParser
            from bibtexparser.customization import convert_to_unicode
        except ImportError as exc:
            raise ImportError(
                "bibtexparser no está instalado. "
                'Instalá el extra: pip install "bib2graph[bibtex]" '
                "o uv sync --extra bibtex"
            ) from exc

        bib_text = Path(path).read_text(encoding="utf-8")

        parser = BibTexParser(common_strings=True)
        parser.customization = convert_to_unicode
        try:
            bib_db = bibtexparser.loads(bib_text, parser=parser)
        except Exception as exc:
            # R5: archivo .bib con error de parseo → warning accionable (no no-op silencioso).
            # bibtexparser puede emitir advertencias internas pero raramente lanza excepciones;
            # este try/except captura errores graves del parser (p.ej. encoding inesperado).
            raise ValueError(
                f"Error al parsear el archivo BibTeX '{path}': {exc}. "
                "Verificá que el archivo esté bien formado (codificación UTF-8, llaves balanceadas)."
            ) from exc

        # R5: detectar si el parser encontró errores/warnings internos y avisar.
        # bibtexparser no lanza excepciones en entradas mal formadas; las ignora silenciosamente.
        # Verificamos si hay entradas nulas o completamente vacías como proxy de parsing roto.
        if not bib_db.entries:
            warnings.warn(
                f"El archivo BibTeX '{path}' no contiene entradas válidas o está vacío. "
                "Si el archivo tiene entradas, puede estar mal formado.",
                UserWarning,
                stacklevel=2,
            )

        fetched_at = datetime.now(UTC).isoformat()

        import pyarrow as pa

        rows: list[dict[str, Any]] = []
        skipped_no_title = 0
        for entry in bib_db.entries:
            row = _entry_to_row(entry, fetched_at=fetched_at)
            # Saltar entradas sin título (no pueden cumplir el schema)
            if not row.get("title"):
                skipped_no_title += 1
                continue
            rows.append(row)

        if skipped_no_title > 0:
            warnings.warn(
                f"{skipped_no_title} entrada(s) del archivo BibTeX '{path}' se omitieron "
                "por no tener título (campo 'title' ausente o vacío).",
                UserWarning,
                stacklevel=2,
            )

        # R5: bulk load — construir la tabla Arrow de una vez y usar from_arrow
        # en vez del loop add_paper/clone que era O(n²).
        # Pre-computar ids (D1) antes de armar la tabla.
        rows_complete = _rows_with_ids(rows) if rows else []
        if rows_complete:
            table = pa.Table.from_pylist(rows_complete, schema=CORPUS_SCHEMA)
            corpus = Corpus.from_arrow(table)
        else:
            corpus = Corpus.from_arrow(
                pa.table(
                    {col: [] for col in CORPUS_SCHEMA.names},
                    schema=CORPUS_SCHEMA,
                )
            )

        return corpus
