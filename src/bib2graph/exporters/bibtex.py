"""bibtex — exportador del corpus a un archivo ``.bib`` (BibTeX).

Implementa ``BibtexExporter`` según ADR 0050 D4 (defaults congelados por el
PO, resolución 2026-07-25, punto 6):

- **entry-type inferido**, con ``@article`` como default cuando no hay señal
  para inferir otro tipo (heurística mínima: si hay ``booktitle``/no hay
  ``journal`` → ``@inproceedings``, si no → ``@article``).
- **citekey = el ``id`` interno del paper** (``doi:…``/``src:…``/``tt:…``,
  D1 de ADR 0013): estable y sin colisiones. El DOI va como campo, no como
  citekey.
- **campos mínimos universales:** ``title``, ``author``, ``year``, ``doi``,
  ``journal`` (venue), ``url``. ``keywords``/``abstract`` quedan fuera del
  MVP.
- **scope = el corpus tal como llega** (ya scopeado por el caller vía
  ``Corpus.scoped``): las entradas con metadata incompleta se emiten con los
  campos que haya, sin filtrar.

Import de ``bibtexparser`` PEREZOSO (mismo patrón que ``sources/bibtex.py``):
se hace dentro de ``export()`` para no acoplar el núcleo al extra
``[bibtex]``; error claro si falta.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyarrow as pa

from bib2graph.constants import Col


def _infer_entry_type(row: dict[str, Any]) -> str:
    """Infiere el ``ENTRYTYPE`` BibTeX de una fila del corpus.

    Default congelado (ADR 0050 D4): ``article`` cuando no hay señal para
    inferir otro tipo. Única señal disponible en el MVP: si el venue vino
    de un ``booktitle`` (proceedings) en vez de ``journal`` no se puede
    distinguir en el schema canónico (ambos colapsan a ``source``), así que
    se usa siempre ``article`` — el schema no trae hoy un campo que permita
    diferenciar de forma confiable.

    Args:
        row: Fila del corpus (dict, una entrada de ``table.to_pylist()``).

    Returns:
        ``"article"`` (default del MVP; ver ADR 0050 D4 punto 6a).
    """
    return "article"


def _row_to_entry(row: dict[str, Any]) -> dict[str, str]:
    """Mapea una fila del corpus canónico a una entrada bibtexparser.

    Campos mínimos universales (ADR 0050 D4 punto 6c): ``title``, ``author``,
    ``year``, ``doi``, ``journal`` (venue = ``source``), ``url`` (derivado
    del DOI si está presente). Entradas con metadata incompleta emiten solo
    los campos presentes (no se rellenan placeholders).

    Args:
        row: Fila del corpus (dict de ``table.to_pylist()``).

    Returns:
        Dict de campos bibtexparser (incluye ``ENTRYTYPE``/``ID``).
    """
    entry: dict[str, str] = {
        "ENTRYTYPE": _infer_entry_type(row),
        "ID": str(row[Col.ID]),
    }

    title = row.get(Col.TITLE)
    if title:
        entry["title"] = str(title)

    authors_raw = row.get(Col.AUTHORS_RAW)
    if authors_raw:
        entry["author"] = " and ".join(str(a) for a in authors_raw)

    year = row.get(Col.YEAR)
    if year is not None:
        entry["year"] = str(year)

    doi = row.get(Col.DOI)
    if doi:
        entry["doi"] = str(doi)
        entry["url"] = f"https://doi.org/{doi}"

    venue = row.get(Col.SOURCE)
    if venue:
        entry["journal"] = str(venue)

    return entry


class BibtexExporter:
    """Exporta la tabla Arrow de un corpus (scopeado) a un archivo ``.bib``."""

    def export(self, table: pa.Table, out_path: str | Path) -> Path:
        """Escribe ``table`` a ``out_path`` como ``.bib`` parseable.

        Args:
            table: Tabla Arrow del corpus (típicamente
                ``corpus.scoped(scope).to_arrow()``).
            out_path: Ruta del archivo de salida (p. ej.
                ``<exports_dir>/corpus.bib``). El directorio padre se crea
                si no existe.

        Returns:
            La ``Path`` del archivo escrito.

        Raises:
            ImportError: Si ``bibtexparser`` no está instalado (extra
                ``[bibtex]``).
        """
        try:
            import bibtexparser
            from bibtexparser.bwriter import BibTexWriter
        except ImportError as exc:
            raise ImportError(
                "bibtexparser no está instalado. "
                'Instalá el extra: pip install "bib2graph[bibtex]" '
                "o uv sync --extra bibtex"
            ) from exc

        rows = table.to_pylist()
        db = bibtexparser.bibdatabase.BibDatabase()
        db.entries = [_row_to_entry(row) for row in rows]

        writer = BibTexWriter()
        writer.order_entries_by = None  # preservar el orden del corpus

        resolved = Path(out_path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(writer.write(db), encoding="utf-8")
        return resolved
