"""05 — Métricas de redes + informe narrado del caso IED.

Para cada red calcula:
- Top-N nodos por **centralidad de grado** (degree centrality) y por
  **centralidad de intermediación** (betweenness centrality). La segunda
  es cara O(V*E) — se aplica sólo si la red tiene < 500 nodos.
- Distribución de componentes conexas (cuántos nodos están en el componente
  gigante).
- **Asimetrías geográficas** del corpus: a partir de ``authors_affiliations``
  (que sí están pobladas cuando la fuente es OpenAlex, no cuando es .bib),
  cuenta papers con al menos un autor en cada macro-región (Global North vs
  Global South). Si el corpus no tiene afiliaciones, se reporta como
  "no medible con este corpus" en vez de inventar.

Salida:
- ``informe_ied.md`` con secciones por red, más una sección de "tensiones
  detectadas" con la plantilla del README (``Decisión / Por qué / Implicación
  para el diseño / Pendiente``).

Las comunidades (louvain) se calculan si el paquete está instalado
(``python-louvain``), siguiendo la regla de ``lecciones-v0.md``: fallar fuerte
sólo cuando se pide; nunca en silencio.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx

DATA_DIR = Path(__file__).resolve().parent.parent / "datos"
REDES_DIR = DATA_DIR / "redes"
INFORME = DATA_DIR.parent / "informe_ied.md"

NORTH = {"US", "USA", "UNITED STATES", "GB", "UK", "UNITED KINGDOM", "DE", "GERMANY",
         "FR", "FRANCE", "NL", "NETHERLANDS", "SE", "SWEDEN", "FI", "FINLAND",
         "NO", "NORWAY", "DK", "DENMARK", "CA", "CANADA", "AU", "AUSTRALIA",
         "JP", "JAPAN", "AT", "AUSTRIA", "CH", "SWITZERLAND", "IT", "ITALY",
         "ES", "SPAIN", "BE", "BELGIUM"}
SOUTH = {"AR", "ARGENTINA", "BR", "BRAZIL", "BO", "BOLIVIA", "CL", "CHILE",
         "CO", "COLOMBIA", "EC", "ECUADOR", "PE", "PERU", "MX", "MEXICO",
         "VE", "VENEZUELA", "UY", "URUGUAY", "PY", "PARAGUAY", "IN", "INDIA",
         "ZA", "SOUTH AFRICA", "CN", "CHINA", "ID", "INDONESIA", "NG", "NIGERIA",
         "KE", "KENYA", "EG", "EGYPT"}


def extract_country(affil: str) -> str:
    """Extrae código de país de un string de afiliación.

    Soporta dos formatos:
    - OpenAlex-style: ``"University of X (US)"`` -> ``"US"``
    - Sandbox-style: ``"Paper affiliation: AR"`` -> ``"AR"``
    """
    s = affil.strip()
    m = re.search(r"\(([A-Z]{2,})\)\s*$", s)
    if m:
        return m.group(1).upper()
    if ":" in s:
        tail = s.rsplit(":", 1)[1].strip()
        if re.match(r"^[A-Z]{2,}$", tail):
            return tail
    return ""


def paper_geography(paper: dict[str, object]) -> set[str]:
    """Devuelve {'NORTH', 'SOUTH', 'MIXED', 'UNKNOWN'}."""
    affils = paper.get("authors_affiliations") or []
    if not affils:
        return {"UNKNOWN"}
    has_n = has_s = False
    for a in affils:
        c = extract_country(str(a))
        if c in NORTH:
            has_n = True
        elif c in SOUTH:
            has_s = True
    if has_n and has_s:
        return {"MIXED"}
    if has_n:
        return {"NORTH"}
    if has_s:
        return {"SOUTH"}
    return {"UNKNOWN"}


def top_by_centrality(g: nx.Graph, kind: str, n: int = 10) -> list[tuple[str, float]]:
    if g.number_of_nodes() == 0:
        return []
    if kind == "degree":
        scores = nx.degree_centrality(g)
    elif kind == "betweenness":
        if g.number_of_nodes() > 500:
            return []
        scores = nx.betweenness_centrality(g, weight="weight")
    else:
        raise ValueError(kind)
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:n]


def components_summary(g: nx.Graph) -> tuple[int, int, float]:
    if g.number_of_nodes() == 0:
        return 0, 0, 0.0
    comps = list(nx.connected_components(g))
    n_comps = len(comps)
    gcc = max(comps, key=len)
    gcc_frac = len(gcc) / g.number_of_nodes()
    return n_comps, len(gcc), gcc_frac


def try_louvain(g: nx.Graph) -> dict[str, int] | None:
    try:
        import community as community_louvain
    except ImportError:
        return None
    if g.number_of_nodes() == 0:
        return {}
    partition = community_louvain.best_partition(g, weight="weight", random_state=42)
    return partition


def load_graph(path: Path) -> nx.Graph | None:
    if not path.exists():
        return None
    return nx.read_graphml(path)


def load_coupling_graph(out_dir: Path) -> nx.Graph | None:
    """Carga el grafo de coupling: prefiere la versión 'full' (con citadores)
    si existe, si no la 'seeds'. El script 04 puede generar las dos
    según ``--coupling-scope``; acá tomamos la más completa disponible."""
    for name in ("coupling_full.graphml", "coupling_seeds.graphml", "coupling.graphml"):
        g = load_graph(out_dir / name)
        if g is not None:
            return g
    return None


def report_network(g: nx.Graph, kind: str, papers: list[dict[str, object]] | None = None) -> str:
    lines = [f"### Red: `{kind}`", ""]
    if g is None or g.number_of_nodes() == 0:
        lines += ["**Vacía** — sin estructura. Posibles causas reportadas en "
                  "la sección de tensiones.", ""]
        return "\n".join(lines)
    n_n, n_e = g.number_of_nodes(), g.number_of_edges()
    density = nx.density(g)
    n_comps, gcc_size, gcc_frac = components_summary(g)

    geo_attr: dict[str, str] = {}
    if papers and kind == "co_autoria":
        for p in papers:
            countries = [extract_country(str(aff))
                         for aff in (p.get("authors_affiliations") or [])]
            countries = [c for c in countries if c]
            if not countries:
                continue
            region = "NORTH" if countries[0] in NORTH else (
                "SOUTH" if countries[0] in SOUTH else "UNKNOWN")
            for a in (p.get("authors_id") or []):
                if a:
                    geo_attr[a] = region
        for n in g.nodes:
            if n in geo_attr:
                g.nodes[n]["geo"] = geo_attr[n]

    lines += [
        f"- Nodos: **{n_n}** | Aristas: **{n_e}** | Densidad: **{density:.4f}**",
        f"- Componentes conexas: **{n_comps}** | GCC: **{gcc_size}** nodos "
        f"(**{gcc_frac:.0%}** del total)",
        "",
    ]

    if geo_attr and kind == "co_autoria":
        nodes_with_geo = [n for n in g.nodes if n in geo_attr]
        n_geo = len(nodes_with_geo)
        n_no_geo = g.number_of_nodes() - n_geo
        if n_geo > 0:
            try:
                ass = nx.attribute_assortativity_coefficient(g, "geo")
            except Exception:
                ass = None
            try:
                deg_ass = nx.degree_assortativity_coefficient(g, weight="weight")
            except Exception:
                deg_ass = None
            lines.append(f"**Asortatividad (autoría con geografía):**")
            lines.append(f"  - Nodos con geografía asignada: **{n_geo}/{g.number_of_nodes()}** "
                         f"({n_geo / g.number_of_nodes():.0%}) — {n_no_geo} sin asignar "
                         f"(autores OpenAlex sin afiliación poblada).")
            if ass is not None and not (isinstance(ass, float) and ass != ass):
                lines.append(f"  - Por región (NORTH/SOUTH/UNKNOWN): "
                             f"**{ass:+.3f}**  "
                             f"({'positivo = homofilia (Norte con Norte)' if ass > 0 else 'negativo = heterofilia (Norte con Sur)'})")
            else:
                lines.append("  - Por región: _(no calculable — distribución degenerada)_")
            if deg_ass is not None and not (isinstance(deg_ass, float) and deg_ass != deg_ass):
                lines.append(f"  - Por grado (degree assortativity, ponderada): "
                             f"**{deg_ass:+.3f}**  "
                             f"({'autores prolíficos co-firman con prolíficos' if deg_ass > 0 else 'autores prolíficos co-firman con periferia'})")
            lines.append("")

    lines.append("**Top 10 por centralidad de grado:**\n")
    for node, score in top_by_centrality(g, "degree", 10):
        label = g.nodes[node].get("label", node)
        suffix = f" [{geo_attr.get(node, '')}]" if geo_attr and node in geo_attr else ""
        lines.append(f"  - `{label}`{suffix} — {score:.3f}")
    lines.append("")
    lines.append("**Top 10 por centralidad de intermediación** (betweenness):\n")
    bt = top_by_centrality(g, "betweenness", 10)
    if not bt:
        lines.append("  - _(red > 500 nodos: salteado por costo)_")
    else:
        for node, score in bt:
            label = g.nodes[node].get("label", node)
            suffix = f" [{geo_attr.get(node, '')}]" if geo_attr and node in geo_attr else ""
            lines.append(f"  - `{label}`{suffix} — {score:.4f}")
    lines.append("")

    partition = try_louvain(g)
    if partition is not None and partition:
        sizes = Counter(partition.values())
        n_comms = len(sizes)
        lines.append(f"**Comunidades (louvain):** {n_comms}\n")
        for cid, size in sorted(sizes.items(), key=lambda kv: -kv[1])[:5]:
            members = [n for n, c in partition.items() if c == cid]
            sample = ", ".join(f"`{g.nodes[m].get('label', m)}`" for m in members[:3])
            if geo_attr:
                geo_counts = Counter(geo_attr.get(m, "?") for m in members)
                geo_str = ", ".join(f"{k}:{v}" for k, v in sorted(geo_counts.items()))
                lines.append(f"  - Comunidad {cid} ({size} nodos): {sample}… — geo: {geo_str}")
            else:
                lines.append(f"  - Comunidad {cid} ({size} nodos): {sample}…")
    elif partition is None:
        lines.append("**Comunidades:** _(python-louvain no instalado; `pip install python-louvain`)_")
    lines.append("")
    return "\n".join(lines)


def report_geography(papers: list[dict[str, object]]) -> str:
    counts: Counter[str] = Counter()
    for p in papers:
        for g_name in paper_geography(p):
            counts[g_name] += 1
    n = len(papers)
    if n == 0:
        return "### Geografía\n\n_Sin papers._\n"
    lines = ["### Geografía del corpus", ""]
    if all(c == "UNKNOWN" for c in counts) or not counts:
        lines += [
            f"- {n} papers en el corpus, **sin afiliaciones pobladas**.",
            "- Imposible medir asimetrías Norte-Sur **con este corpus**.",
            "- El .bib sintético no tiene afiliaciones (campo raro en BibTeX).",
            "- En datos reales de OpenAlex (script 01) este análisis sí es viable.",
            "",
        ]
        return "\n".join(lines)
    lines.append(f"- {n} papers totales.\n")
    for region in ("NORTH", "SOUTH", "MIXED", "UNKNOWN"):
        c = counts.get(region, 0)
        if c:
            lines.append(f"  - **{region}**: {c} ({c / n:.0%})")
    lines.append("")
    n_s = counts.get("SOUTH", 0)
    n_n = counts.get("NORTH", 0)
    n_m = counts.get("MIXED", 0)
    if n_s + n_n > 0 and n_s > 0:
        ratio = (n_s + n_m) / (n_s + n_n + n_m) if (n_s + n_n + n_m) else 0
        lines.append(
            f"- **Asimetría:** {ratio:.0%} de los papers tiene al menos un autor "
            f"del Global South (incluyendo co-autorías mixtas). Útil para IED: "
            f"indica penetración del Sur en el campo, no solo hegemonía del Norte."
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DATA_DIR / "corpus_ied.parquet")
    parser.add_argument("--out", type=Path, default=INFORME)
    parser.add_argument("--kinds", nargs="+",
                        default=["co_citacion", "co_autoria", "co_word", "coupling"])
    args = parser.parse_args()

    if not args.corpus.exists():
        print(f"[05] ERROR: no existe {args.corpus}.", file=sys.stderr)
        return 2

    import pyarrow.parquet as pq
    papers = pq.read_table(args.corpus).to_pylist()

    sections: list[str] = ["# Informe IED — sandbox `exploracion/`", "",
                            f"_Generado por `05_metrics_report.py` sobre "
                            f"`{args.corpus.name}` ({len(papers)} papers)._", ""]
    sections += ["## Composición del corpus", "",
                  f"- {len(papers)} papers totales.",
                  f"- {sum(1 for p in papers if p.get('is_seed'))} semillas."]

    geo = defaultdict(int)
    for p in papers:
        for k in paper_geography(p):
            geo[k] += 1
    if geo and not (len(geo) == 1 and "UNKNOWN" in geo):
        sections += [f"- Distribución geográfica: "
                     + ", ".join(f"{k}={v}" for k, v in sorted(geo.items()))]
    sections.append("")

    sections += ["## Redes", ""]
    for kind in args.kinds:
        if kind == "coupling":
            g = load_coupling_graph(REDES_DIR)
        else:
            g = load_graph(REDES_DIR / f"{kind}.graphml")
        sections.append(report_network(g, kind, papers=papers))

    sections.append(report_geography(papers))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(sections), encoding="utf-8")
    print(f"[05] Informe -> {args.out}", file=sys.stderr)
    candidates = sorted(args.out.parent.glob("informe_ied_lectura_*.md"),
                        key=lambda p: p.stat().st_mtime, reverse=True)
    candidates = [c for c in candidates if "auto" not in c.name]
    if candidates:
        print(f"[05] Lectura sustantiva (a mano, más reciente): {candidates[0]}", file=sys.stderr)
    else:
        print(f"[05] AVISO: no hay informe_ied_lectura_*.md — escribila a mano "
              f"con tensiones y hallazgos cualitativos.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
