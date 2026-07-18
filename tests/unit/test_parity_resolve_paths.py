"""Paridad DOI->source_id entre camino separado y camino encadenado (guardia #165).

Verifica que el mismo .bib procesado por dos rutas distintas produce
exactamente los mismos ``source_id`` resueltos en el corpus:

  Camino A (separado):
    run_seed_from_bib(store_a, bib)                    # sin resolve
    resolve_dois(store_a, transport=mock)               # resolve explicito post-seed

  Camino B (encadenado, ruta canonica ``seed --resolve``):
    run_seed_from_bib(store_b, bib, resolve=True, transport=mock)

Ambos caminos delegan en ``service.resolve`` (ADR 0035, fuente unica): la
diferencia es cuando se abre/cierra el store.  Si la fuente unica es
verdaderamente compartida, los resultados deben ser identicos.

Nota (#207, ADR 0038 P1): el verbo suelto ``b2g resolve`` (y su función
núcleo ``cli.commands.resolve.run_resolve``) fue retirado en 0.12.0. El
Camino A usa ahora ``service.resolve.resolve_dois`` directamente — la misma
fuente que ``run_resolve`` delegaba, y la que ``seed --resolve`` invoca vía
``_resolve_dois_on_store``. Esta sigue siendo la red de seguridad original:
un fallo aquí indica que los dos caminos divergieron y hay duplicación real
de lógica sin reconciliar.

Marcador: ``unit`` (DuckDB real en tmp_path, sin red real; MockTransport para OA).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest

from bib2graph.constants import Col

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# BibTeX de prueba: 2 papers con DOI, 1 sin DOI
# ---------------------------------------------------------------------------

BIB_PARITY = """\
@article{paper_a,
  author  = {Autor, Uno},
  title   = {Paper A con DOI},
  journal = {Test Journal},
  year    = {2020},
  doi     = {10.1234/paper-a},
}

@article{paper_b,
  author  = {Autor, Dos},
  title   = {Paper B con DOI},
  journal = {Test Journal},
  year    = {2021},
  doi     = {10.5678/paper-b},
}

@article{paper_c,
  author  = {Autor, Tres},
  title   = {Paper C sin DOI},
  journal = {Test Journal},
  year    = {2022},
}
"""

# Mock works: OpenAlex resuelve los 2 DOIs del .bib a source_ids conocidos
_WORKS_MOCK: list[dict[str, Any]] = [
    {"id": "https://openalex.org/WP001", "doi": "https://doi.org/10.1234/paper-a"},
    {"id": "https://openalex.org/WP002", "doi": "https://doi.org/10.5678/paper-b"},
]


def _make_mock_transport(works: list[dict[str, Any]]) -> httpx.MockTransport:
    """MockTransport estatico: responde siempre con la lista completa de works.

    No simula paginacion (next_cursor=None), lo que es correcto para lotes
    de <=100 DOIs sin cursor.  El handler es idempotente: devuelve los mismos
    works en cualquier request, permitiendo que el test use una instancia
    por camino.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        body = {
            "results": works,
            "meta": {"count": len(works), "next_cursor": None},
        }
        return httpx.Response(
            200,
            json=body,
            headers={"x-openalex-api-version": "2026-05-01"},
        )

    return httpx.MockTransport(handler)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_doi_to_source_id(store_path: Path) -> dict[str | None, str | None]:
    """Abre el store, extrae el mapa doi->source_id y cierra."""
    from bib2graph.stores.duckdb import DuckDBStore

    store = DuckDBStore(store_path)
    rows = store.load().to_arrow().to_pylist()
    store.close()
    return {r[Col.DOI]: r[Col.SOURCE_ID] for r in rows}


# ---------------------------------------------------------------------------
# Test de paridad
# ---------------------------------------------------------------------------


def test_parity_seed_resolve_separado_vs_encadenado(tmp_path: Path) -> None:
    """Paridad: seed+resolve separados == seed --resolve encadenado.

    Camino A: run_seed_from_bib(store_a, bib) luego resolve_dois(store_a, mock)
    Camino B: run_seed_from_bib(store_b, bib, resolve=True, transport=mock)

    El assert principal es que el mapa doi->source_id es identico en ambos
    stores.  Los asserts secundarios verifican valores concretos para que el
    test falle con mensaje claro si cambia la logica de resolucion.
    """
    from bib2graph.cli.commands.seed import run_seed_from_bib
    from bib2graph.service.resolve import resolve_dois

    bib_path = tmp_path / "parity.bib"
    bib_path.write_text(BIB_PARITY, encoding="utf-8")

    store_path_a = tmp_path / "store_a.duckdb"
    store_path_b = tmp_path / "store_b.duckdb"

    # -- Camino A: dos operaciones secuenciales (store abre y cierra dos veces) --
    run_seed_from_bib(store_path_a, bib_path)
    resolve_dois(store_path_a, transport=_make_mock_transport(_WORKS_MOCK))

    # -- Camino B: operacion encadenada (store abre y cierra una sola vez) ----
    run_seed_from_bib(
        store_path_b,
        bib_path,
        resolve=True,
        transport=_make_mock_transport(_WORKS_MOCK),
    )

    # -- Comparar resultados ---------------------------------------------------
    map_a = _load_doi_to_source_id(store_path_a)
    map_b = _load_doi_to_source_id(store_path_b)

    assert map_a == map_b, (
        "Los dos caminos producen source_id distintos -- "
        "_resolve_dois_on_store ya no es la fuente unica compartida.\n"
        f"  Camino A (separado):   {map_a}\n"
        f"  Camino B (encadenado): {map_b}"
    )

    # Asserts concretos: los DOIs conocidos deben resolverse al source_id correcto
    assert map_a["10.1234/paper-a"] == "WP001", (
        f"DOI 10.1234/paper-a esperaba WP001, obtuvo {map_a['10.1234/paper-a']!r}"
    )
    assert map_a["10.5678/paper-b"] == "WP002", (
        f"DOI 10.5678/paper-b esperaba WP002, obtuvo {map_a['10.5678/paper-b']!r}"
    )
    # Paper sin DOI no debe tener source_id (None key en el mapa)
    assert map_a[None] is None, (
        f"Paper sin DOI no deberia tener source_id, obtuvo {map_a[None]!r}"
    )
