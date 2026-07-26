"""Tests — ``cli._scope.map_scope`` (helper compartido, DRY entre build/export).

Antes de esta extracción, ``build.py`` y ``export.py`` tenían cada uno una
copia literal idéntica de este mapeo (hallazgo de revisión arquitectónica
0.14.0). Este test cubre el helper único; ``build.py``/``export.py`` lo
importan con el alias histórico ``_map_scope`` (ver
``test_build_absorber_networks.py::test_map_scope_seeds_a_seeds_only`` para
el contrato re-exportado desde ``build``).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestMapScope:
    def test_seeds_mapea_a_seeds_only(self) -> None:
        from bib2graph.cli._scope import map_scope

        assert map_scope("seeds") == "seeds_only"

    def test_all_y_accepted_pasan_sin_cambio(self) -> None:
        from bib2graph.cli._scope import map_scope

        assert map_scope("all") == "all"
        assert map_scope("accepted") == "accepted"

    def test_build_y_export_reexportan_el_mismo_helper(self) -> None:
        """build._map_scope y export._map_scope son el mismo objeto (no copias)."""
        from bib2graph.cli._scope import map_scope
        from bib2graph.cli.commands.build import _map_scope as build_map_scope
        from bib2graph.cli.commands.export import _map_scope as export_map_scope

        assert build_map_scope is map_scope
        assert export_map_scope is map_scope
