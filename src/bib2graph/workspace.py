"""workspace — Abstracción de «una investigación = una carpeta workspace».

Capa seam-level: maneja filesystem, paths y manifest.  El núcleo puro
(corpus, cycle, projectors, analyzer) **NO importa este módulo**.

Estructura canónica de un workspace:

    mi-investigacion/
    ├── workspace.json    # marcador + manifest mínimo
    ├── library.duckdb    # biblioteca viva
    ├── networks/         # cache de redes (build), regenerable
    ├── snapshots/        # snapshots sellados
    └── exports/          # exports regenerables

Resolución ambiente (patrón git/cargo), de mayor a menor precedencia:
  1. ``--workspace``/``--store`` explícito en la invocación CLI.
  2. Variable de entorno ``B2G_WORKSPACE``.
  3. Caminar hacia arriba desde cwd buscando ``workspace.json``.
  4. Sin ninguno → ``WorkspaceNotFoundError`` con sugerencia accionable.

El workspace «degenerado» (``--store archivo.duckdb`` suelto) mantiene
retrocompatibilidad: ``library_path`` apunta al archivo y los dirs caen
en su dir hermano, como antes de ADR 0029.

ADR 0029: https://github.com/complexluise/bib2graph/docs/decisiones/0029-workspace-por-investigacion.md
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Manifest mínimo (marcador del workspace)
# ---------------------------------------------------------------------------

WORKSPACE_MANIFEST_FILE = "workspace.json"
WORKSPACE_SCHEMA_VERSION = "1"
LIBRARY_FILENAME = "library.duckdb"


def _lib_version() -> str:
    """Devuelve la versión instalada de bib2graph (fallback 'unknown')."""
    try:
        import importlib.metadata as _meta

        return _meta.version("bib2graph")
    except Exception:
        return "unknown"


class WorkspaceManifest(BaseModel):
    """Manifest mínimo del workspace (marcador + metadatos de versión).

    Campos:
        name: Nombre legible de la investigación.
        created_at: Timestamp ISO-8601 UTC de creación (frontera, no entra a hashes).
        bib2graph_version: Versión del paquete al momento de la creación.
        schema_version: Versión del schema del manifest (``"1"`` por ahora).
    """

    name: str
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    bib2graph_version: str = Field(default_factory=_lib_version)
    schema_version: str = WORKSPACE_SCHEMA_VERSION


# ---------------------------------------------------------------------------
# Excepción propia del seam workspace
# ---------------------------------------------------------------------------


class WorkspaceNotFoundError(Exception):
    """No se pudo resolver ningún workspace desde el contexto actual.

    Incluye un mensaje accionable que sugiere ``b2g init .`` o ``--workspace``.
    """

    def __init__(self, message: str | None = None) -> None:
        if message is None:
            message = (
                "No se encontró un workspace activo.\n"
                "  • Creá uno con: b2g init <nombre> (o b2g init . para el directorio actual)\n"
                "  • O apuntá a uno con: --workspace <carpeta> o --store <archivo.duckdb>\n"
                "  • O exportá la variable: export B2G_WORKSPACE=<carpeta>"
            )
        super().__init__(message)


class WorkspaceExistsError(Exception):
    """Ya existe un workspace.json en el directorio destino."""


# ---------------------------------------------------------------------------
# Workspace
# ---------------------------------------------------------------------------

_DIRS = ("networks", "snapshots", "exports")


class Workspace:
    """Abstracción de «una investigación = una carpeta workspace».

    Maneja scaffolding, resolución ambiente y acceso a paths derivados.
    No importa duckdb ni ningún módulo del núcleo.

    Atributos principales:
        root: Carpeta raíz del workspace (o ``None`` para el modo degenerado).
        manifest: ``WorkspaceManifest`` leído/creado.
        library_path: Ruta al archivo ``library.duckdb``.
        networks_dir: Ruta al directorio ``networks/``.
        snapshots_dir: Ruta al directorio ``snapshots/``.
        exports_dir: Ruta al directorio ``exports/``.
        source: De dónde salió la resolución (``"flag"``, ``"env"``, ``"cwd"``, ``"degenerate"``).
    """

    def __init__(
        self,
        *,
        root: Path | None,
        library_path: Path,
        manifest: WorkspaceManifest | None,
        source: str,
    ) -> None:
        self._root = root
        self._library_path = library_path
        self._manifest = manifest
        self._source = source

    # ------------------------------------------------------------------
    # Propiedades públicas
    # ------------------------------------------------------------------

    @property
    def root(self) -> Path | None:
        """Carpeta raíz del workspace (``None`` en modo degenerado)."""
        return self._root

    @property
    def library_path(self) -> Path:
        """Ruta al archivo ``library.duckdb`` (o al ``.duckdb`` suelto en modo degenerado)."""
        return self._library_path

    @property
    def networks_dir(self) -> Path:
        """Directorio ``networks/`` del workspace."""
        if self._root is not None:
            return self._root / "networks"
        return self._library_path.parent / "networks"

    @property
    def snapshots_dir(self) -> Path:
        """Directorio ``snapshots/`` del workspace."""
        if self._root is not None:
            return self._root / "snapshots"
        return self._library_path.parent / "snapshots"

    @property
    def exports_dir(self) -> Path:
        """Directorio ``exports/`` del workspace."""
        if self._root is not None:
            return self._root / "exports"
        return self._library_path.parent / "exports"

    @property
    def manifest(self) -> WorkspaceManifest | None:
        """Manifest del workspace (``None`` en modo degenerado)."""
        return self._manifest

    @property
    def source(self) -> str:
        """De dónde salió la resolución del workspace.

        Valores posibles: ``"flag"``, ``"env"``, ``"cwd"``, ``"degenerate"``.
        """
        return self._source

    # ------------------------------------------------------------------
    # Factory: init (scaffolding)
    # ------------------------------------------------------------------

    @classmethod
    def init(cls, path: Path, name: str) -> Workspace:
        """Scaffolds una carpeta como workspace nuevo.

        Crea el directorio ``path`` (si no existe), escribe ``workspace.json``,
        crea los subdirectorios ``networks/``, ``snapshots/``, ``exports/`` y
        toca ``library.duckdb`` mediante el store existente para inicializarlo.

        Args:
            path: Ruta de la carpeta a inicializar como workspace.
            name: Nombre legible de la investigación.

        Returns:
            Workspace recién creado.

        Raises:
            WorkspaceExistsError: Si ya existe un ``workspace.json`` en ``path``.
        """
        root = path.resolve()
        manifest_path = root / WORKSPACE_MANIFEST_FILE

        if manifest_path.exists():
            raise WorkspaceExistsError(
                f"Ya existe un workspace en '{root}'. "
                "Si querés reiniciarlo, borrá workspace.json manualmente."
            )

        root.mkdir(parents=True, exist_ok=True)
        for d in _DIRS:
            (root / d).mkdir(exist_ok=True)

        manifest = WorkspaceManifest(name=name)
        manifest_path.write_text(
            json.dumps(manifest.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # Inicializar library.duckdb vía DuckDBStore (carga perezosa de duckdb)
        library_path = root / LIBRARY_FILENAME
        _init_library(library_path)

        return cls(
            root=root,
            library_path=library_path,
            manifest=manifest,
            source="init",
        )

    # ------------------------------------------------------------------
    # Factory: open (desde carpeta ya existente)
    # ------------------------------------------------------------------

    @classmethod
    def open(cls, path: Path, *, source: str = "flag") -> Workspace:
        """Abre un workspace existente desde su carpeta raíz.

        Args:
            path: Carpeta raíz del workspace (debe contener ``workspace.json``).
            source: Etiqueta de origen para diagnóstico.

        Returns:
            Workspace resuelto.

        Raises:
            WorkspaceNotFoundError: Si no existe ``workspace.json`` en ``path``.
        """
        root = path.resolve()
        manifest_path = root / WORKSPACE_MANIFEST_FILE
        if not manifest_path.exists():
            raise WorkspaceNotFoundError(
                f"No se encontró workspace.json en '{root}'. "
                "¿Es esta la carpeta correcta? Podés crear el workspace con "
                f"'b2g init {root.name}' o apuntar a otro con '--workspace <carpeta>'."
            )
        manifest = _read_manifest(manifest_path)
        library_path = root / LIBRARY_FILENAME
        return cls(
            root=root,
            library_path=library_path,
            manifest=manifest,
            source=source,
        )

    # ------------------------------------------------------------------
    # Factory: resolve (resolución ambiente completa)
    # ------------------------------------------------------------------

    @classmethod
    def resolve(
        cls,
        *,
        workspace: str | None = None,
        store: str | None = None,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> Workspace:
        """Resuelve el workspace activo aplicando la precedencia del ADR 0029.

        Precedencia (de mayor a menor):
          1. ``workspace`` (--workspace explícito) → ``Workspace.open()``.
          2. ``store`` (--store explícito, modo degenerado) → library_path = ese archivo.
          3. ``B2G_WORKSPACE`` en ``env`` → ``Workspace.open()``.
          4. Caminar hacia arriba desde ``cwd`` buscando ``workspace.json``.
          5. Ninguno → ``WorkspaceNotFoundError``.

        Args:
            workspace: Ruta a la carpeta del workspace (--workspace).
            store: Ruta a un archivo .duckdb suelto (--store, retrocompat).
            cwd: Directorio actual (default: ``Path.cwd()``).
            env: Variables de entorno (default: ``os.environ``).

        Returns:
            El ``Workspace`` resuelto.

        Raises:
            WorkspaceNotFoundError: Si no se puede resolver ningún workspace,
                o si se pasan ``--workspace`` y ``--store`` simultáneamente
                (son mutuamente excluyentes).
        """
        if env is None:
            env = dict(os.environ)
        if cwd is None:
            cwd = Path.cwd()

        # Colisión de flags: --workspace y --store son mutuamente excluyentes.
        # --workspace es la forma canónica; --store es el modo degenerado
        # de retrocompat. Pasar ambos es ambiguo y se rechaza explícitamente
        # (ADR 0029 §Sub-decisiones).
        if workspace is not None and store is not None:
            raise WorkspaceNotFoundError(
                "--workspace y --store son mutuamente excluyentes.\n"
                "  • Usá --workspace <carpeta> para un workspace completo.\n"
                "  • Usá --store <archivo.duckdb> solo para un .duckdb suelto (modo legado)."
            )

        # 1. --workspace explícito
        if workspace is not None:
            return cls.open(Path(workspace), source="flag")

        # 2. --store explícito (modo degenerado — retrocompatibilidad ADR 0029)
        if store is not None:
            library_path = Path(store).resolve()
            return cls(
                root=None,
                library_path=library_path,
                manifest=None,
                source="degenerate",
            )

        # 3. Variable de entorno B2G_WORKSPACE
        env_ws = env.get("B2G_WORKSPACE")
        if env_ws:
            return cls.open(Path(env_ws), source="env")

        # 4. Caminar hacia arriba desde cwd
        found = _walk_up(cwd)
        if found is not None:
            return cls.open(found, source="cwd")

        # 5. Sin workspace → error accionable
        raise WorkspaceNotFoundError()

    # ------------------------------------------------------------------
    # Representación
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"Workspace(root={self._root!r}, "
            f"library={self._library_path!r}, source={self._source!r})"
        )

    def read_networks_corpus_hash(self) -> str | None:
        """Lee el ``corpus_hash`` sellado en ``networks/.corpus_hash``.

        Devuelve ``None`` si el archivo no existe (cache no generada aún).

        Returns:
            El hash sellado como string, o ``None``.
        """
        hash_file = self.networks_dir / ".corpus_hash"
        if not hash_file.exists():
            return None
        return hash_file.read_text(encoding="utf-8").strip()

    def is_networks_cache_stale(self, live_corpus_hash: str) -> bool:
        """Verifica si la cache de redes está desactualizada respecto al corpus vivo.

        Compara el ``corpus_hash`` sellado en ``networks/.corpus_hash`` con el
        ``live_corpus_hash`` del corpus actual.  Devuelve ``True`` si la cache
        existe pero su hash no coincide (stale); ``False`` si coincide o si la
        cache todavía no existe (no hay cache que invalidar).

        Args:
            live_corpus_hash: Hash del corpus vivo (calculado con
                ``compute_corpus_hash``).

        Returns:
            ``True`` si la cache existe y su hash difiere del corpus vivo.
            ``False`` en cualquier otro caso.
        """
        sealed = self.read_networks_corpus_hash()
        if sealed is None:
            return False
        return sealed != live_corpus_hash

    def to_dict(self) -> dict[str, Any]:
        """Serializa el workspace a dict para el envelope JSON del CLI."""
        return {
            "root": str(self._root) if self._root is not None else None,
            "library_path": str(self._library_path),
            "networks_dir": str(self.networks_dir),
            "snapshots_dir": str(self.snapshots_dir),
            "exports_dir": str(self.exports_dir),
            "source": self._source,
            "manifest": self._manifest.model_dump() if self._manifest else None,
        }


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _walk_up(start: Path) -> Path | None:
    """Camina hacia arriba desde ``start`` buscando un directorio con workspace.json.

    Args:
        start: Directorio desde donde comenzar la búsqueda.

    Returns:
        El primer directorio que contiene ``workspace.json``, o ``None``.
    """
    current = start.resolve()
    while True:
        if (current / WORKSPACE_MANIFEST_FILE).exists():
            return current
        parent = current.parent
        if parent == current:
            # Llegamos a la raíz del filesystem sin encontrar nada
            return None
        current = parent


def _read_manifest(path: Path) -> WorkspaceManifest:
    """Lee y valida el manifest desde un archivo workspace.json.

    Args:
        path: Ruta al archivo ``workspace.json``.

    Returns:
        WorkspaceManifest validado con Pydantic.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    return WorkspaceManifest.model_validate(raw)


def _init_library(library_path: Path) -> None:
    """Inicializa la biblioteca viva en ``library_path`` vía DuckDBStore.

    Importación perezosa de duckdb: solo se importa cuando se llama esta función.
    El núcleo (workspace.py en sí) no importa duckdb al nivel de módulo.

    Args:
        library_path: Ruta donde crear el archivo ``library.duckdb``.
    """
    from bib2graph.stores.duckdb import DuckDBStore

    DuckDBStore(library_path)
