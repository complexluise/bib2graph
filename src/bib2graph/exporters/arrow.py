"""arrow — exportador del corpus a un archivo Arrow IPC (Feather).

Implementa ``ArrowExporter`` según ADR 0050 D4. Serializa la tabla que
``Corpus.to_arrow()`` produce (schema + metadata ya poblados por la
proyección) a un único archivo ``.arrow`` (Arrow IPC / Feather),
autoverificable para consumidores externos (Atalaya).

Es un artefacto DISTINTO de ``snapshot create`` (parquet + manifest.json,
reproducibilidad interna, ADR 0017/0030): este exportador NO toca el
schema ni agrega/computa metadata — solo serializa la tabla tal como
``to_arrow()`` la entrega. ``pyarrow.feather.write_feather`` preserva la
metadata del schema (incluido cualquier ``equation_hash``/objeto ecuación
que la otra pieza del contrato, #291/#292, haya poblado) sin intervención
de este módulo.
"""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa


class ArrowExporter:
    """Exporta una tabla Arrow del corpus a un archivo Feather (Arrow IPC).

    No modifica el schema ni la tabla: solo la serializa. La metadata del
    schema (si la tabla la trae) viaja intacta dentro del archivo.
    """

    def export(self, table: pa.Table, out_path: str | Path) -> Path:
        """Escribe ``table`` a ``out_path`` en formato Feather (Arrow IPC).

        Args:
            table: Tabla Arrow a serializar (típicamente
                ``corpus.scoped(scope).to_arrow()``).
            out_path: Ruta del archivo de salida (p. ej.
                ``<exports_dir>/corpus.arrow``). El directorio padre se
                crea si no existe.

        Returns:
            La ``Path`` del archivo escrito.
        """
        from pyarrow import feather

        resolved = Path(out_path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        feather.write_feather(table, str(resolved))  # type: ignore[no-untyped-call]
        return resolved
