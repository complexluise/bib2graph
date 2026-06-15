"""02 — Cargar un .bib semilla y volcarlo a CSV con el schema común.

Reglas de la sandbox:
- Acceso **defensivo** a campos (``entry.get('author', [])``, no
  ``entry['author']``). En BibTeX los campos opcionales faltan seguido.
- El ``author`` se guarda como lista separada por `` and `` en ``authors_raw``
  y se intenta parsear a ``"Apellido, Nombre"`` en ``authors_id`` (canonización
  muy liviana; lo serio queda para el ``Preprocessor`` del núcleo).
- Sin afiliaciones en BibTeX estándar: ``authors_affiliations`` queda vacío.
  El parser no inventa afiliaciones (lección 4 de v0 en ``lecciones-v0.md``).
- ``is_seed=True`` para todo lo que viene de .bib (el .bib es siempre semilla).
- Si la entrada no tiene DOI, se le asigna un id sintético ``bib:<entry_id>``
  para que sea dedupeable por el merge de ``03_merge_corpus.py``.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Any

from _schema import CORPUS_COLUMNS, new_row

OUT_CSV_DEFAULT = Path(__file__).resolve().parent.parent / "datos" / "semillas_ied.csv"


def parse_author(raw: str) -> tuple[str, str]:
    """Devuelve (display_name, canonical_id) muy liviano.

    Para "Apellido, Nombre" se conserva. Para "Nombre Apellido" se reordena.
    El id canónico es ``"apellido_nombre"`` lowercased y sin acentos; sirve
    para que la co-autoría matchee aunque la firma venga con/sin tilde.
    """
    raw = (raw or "").strip()
    if not raw:
        return "", ""
    if "," in raw:
        apellido, _, nombre = raw.partition(",")
    else:
        parts = raw.split()
        apellido = parts[-1] if parts else ""
        nombre = " ".join(parts[:-1])
    apellido = apellido.strip()
    nombre = nombre.strip()
    canon = re.sub(r"\s+", "_", f"{apellido}_{nombre}").lower()
    canon = re.sub(r"[^\w]", "", canon, flags=re.UNICODE)
    return f"{apellido}, {nombre}".strip(", "), canon


def _unescape_latex(value: str) -> str:
    """Desescapa secuencias LaTeX básicas que aparecen en .bib de revistas latam.

    No es un desescapador completo; sólo lo que la literatura de IED usa:
    acentos, eñes, comillas tipográficas. La normalización profunda (canonización
    de keywords, thesaurus) es trabajo del ``Preprocessor`` del núcleo.

    Soporta dos formas: ``\\'o`` simple y ``{\\'o}`` con llaves agrupadoras
    (típico de revistas latam que embeben comandos LaTeX en grupos).
    """
    import re
    char_map = {
        "a": "á", "e": "é", "i": "í", "o": "ó", "u": "ú",
        "A": "Á", "E": "É", "I": "Í", "O": "Ó", "U": "Ú",
        "n": "ñ", "N": "Ñ",
    }
    pattern = re.compile(r"\{\\['`\"\^~]([aeiounAEIOUN])\}|\\['`\"\^~]([aeiounAEIOUN])")
    def _replace(m: re.Match[str]) -> str:
        letter = m.group(1) or m.group(2)
        return char_map.get(letter, m.group(0))
    value = pattern.sub(_replace, value)

    replacements = {
        '\\"a': "ä", '\\"e': "ë", '\\"i': "ï", '\\"o': "ö", '\\"u': "ü",
        "\\`a": "à", "\\`e": "è", "\\`o": "ò",
        "``": "“", "''": "”", "`": "‘",
    }
    for k, v in replacements.items():
        value = value.replace(k, v)
    return value


def get_keywords(entry: dict[str, Any]) -> list[str]:
    raw = entry.get("keywords") or entry.get("keyword")
    if not raw:
        return []
    if isinstance(raw, list):
        return [_unescape_latex(str(k)).strip() for k in raw if str(k).strip()]
    return [_unescape_latex(k).strip() for k in str(raw).split(",") if k.strip()]


def entry_to_row(entry_dict: dict[str, Any], entry_id: str) -> dict[str, object]:
    row = new_row()
    row["id"] = entry_dict.get("doi") or f"bib:{entry_id}"
    row["doi"] = entry_dict.get("doi")
    row["title"] = _unescape_latex(entry_dict.get("title") or "")
    row["year"] = int(entry_dict["year"]) if entry_dict.get("year") else None
    row["abstract"] = _unescape_latex(entry_dict.get("abstract") or "")
    authors_raw = entry_dict.get("author") or entry_dict.get("authors") or []
    if isinstance(authors_raw, str):
        authors_raw = [_unescape_latex(a).strip() for a in re.split(r"\s+and\s+", authors_raw) if a.strip()]
    elif authors_raw:
        authors_raw = [_unescape_latex(str(a)).strip() for a in authors_raw if str(a).strip()]
    names, ids = zip(*[parse_author(a) for a in authors_raw]) if authors_raw else ([], [])
    row["authors_raw"] = list(names)
    row["authors_id"] = list(ids)
    aff = entry_dict.get("affiliation")
    if aff:
        affil_text = _unescape_latex(aff) if isinstance(aff, str) else str(aff)
        affil_text = affil_text.strip()
        if affil_text:
            row["authors_affiliations"] = [f"Paper affiliation: {affil_text}"]
        else:
            row["authors_affiliations"] = []
    else:
        row["authors_affiliations"] = []
    row["keywords_raw"] = get_keywords(entry_dict)
    row["keywords_id"] = [re.sub(r"\s+", "_", k.lower()) for k in row["keywords_raw"]]
    row["references_doi"] = []
    source = entry_dict.get("journal") or entry_dict.get("booktitle") or entry_dict.get("publisher")
    row["source"] = _unescape_latex(source) if source else None
    row["language"] = entry_dict.get("language")
    row["is_seed"] = True
    return row


def serialize_list(value: object) -> str:
    if isinstance(value, list):
        return "; ".join(str(x) for x in value)
    return "" if value is None else str(value)


def write_csv(rows: list[dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CORPUS_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({c: serialize_list(row.get(c)) for c in CORPUS_COLUMNS})


def _preprocess_bib(text: str) -> tuple[str, int]:
    """Limpia el .bib antes de pasárselo a ``bibtexparser``.

    Bug documentado de ``bibtexparser`` 1.4.x que esta función mitiga
    (ver ``informe_ied_lectura.md`` T1):

    **``keywords`` como último campo + comentario ``%`` antes del ``}``**:
    el parser **se come la entry entera**. Específicamente, si una entry
    termina con ``keywords = {...},`` y después viene una línea ``%``
    (incluso vacía, incluso ASCII puro) antes del ``}`` de cierre, el
    parser pierde la entry. Reproducible aislado. La fix es eliminar las
    líneas ``%`` que estén dentro de una entry, justo antes del ``}``
    de cierre. Los comentarios entre campos o entre entries no se tocan.

    Devuelve ``(texto_limpio, n_comentarios_eliminados)``.
    """
    n_fixed = 0
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    in_entry = False
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()
        if stripped.startswith("@"):
            in_entry = True
            out.append(line)
            i += 1
            continue
        if not in_entry:
            out.append(line)
            i += 1
            continue
        if stripped.startswith("}"):
            in_entry = False
            out.append(line)
            i += 1
            continue
        if stripped.startswith("%"):
            j = i
            while j < len(lines) and lines[j].lstrip().startswith("%"):
                j += 1
            if j < len(lines) and lines[j].lstrip().startswith("}"):
                n_fixed += j - i
                i = j
                continue
            out.extend(lines[i:j])
            i = j
            continue
        out.append(line)
        i += 1
    return "".join(out), n_fixed


def load_bibtex(path: Path) -> list[dict[str, Any]]:
    try:
        import bibtexparser
        from bibtexparser.bparser import BibTexParser
    except ImportError as exc:
        raise SystemExit(
            f"bibtexparser no instalado. Hacé `pip install bibtexparser`.\n{exc}"
        ) from exc

    raw = path.read_text(encoding="utf-8")
    cleaned, n_fixed = _preprocess_bib(raw)
    if n_fixed:
        print(f"[02] Pre-procesador: {n_fixed} comentarios ``%`` antes de "
              f"``}}`` eliminados (fix de bug bibtexparser T1).", file=sys.stderr)

    parser = BibTexParser(common_strings=True)
    parser.ignore_nonstandard_types = False
    db = bibtexparser.loads(cleaned, parser=parser)
    return [dict(e) for e in db.entries]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bib", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=OUT_CSV_DEFAULT)
    args = parser.parse_args()

    if not args.bib.exists():
        print(f"[02] ERROR: no existe {args.bib}", file=sys.stderr)
        return 2

    entries = load_bibtex(args.bib)
    print(f"[02] {len(entries)} entradas leídas de {args.bib}", file=sys.stderr)

    rows = [entry_to_row(e, e.get("ID", f"n{i}")) for i, e in enumerate(entries)]
    n_sin_doi = sum(1 for r in rows if not r.get("doi"))
    n_sin_kw = sum(1 for r in rows if not r["keywords_raw"])
    n_sin_abs = sum(1 for r in rows if not r.get("abstract"))
    print(f"[02] Defensivo: {n_sin_doi} sin DOI, {n_sin_kw} sin keywords, "
          f"{n_sin_abs} sin abstract", file=sys.stderr)

    write_csv(rows, args.out)
    print(f"[02] {len(rows)} filas -> {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
