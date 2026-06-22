"""spec — NetworkSpec (modelo declarativo) y NetworkArtifact.

Contiene los tipos de datos centrales del módulo de redes:
  - ``NetworkSpec``: configuración declarativa de una red (Hito 9).
  - ``NetworkArtifact``: resultado de proyectar + analizar un corpus.
  - ``load_specs``: carga y valida una lista de ``NetworkSpec`` desde YAML.

R5: ``NetworkSpec.kind`` usa ``NetworkKind`` como tipo (fuente única, ADR 0023).
El ``Literal[...]`` duplicado fue eliminado; mypy sigue validando porque
``NetworkKind`` es un ``StrEnum`` con los mismos valores.

Ver API.md §10.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import networkx as nx
from pydantic import BaseModel, ConfigDict, ValidationError

from bib2graph.constants import NetworkKind

if TYPE_CHECKING:
    # nx.Graph es genérico solo en los stubs de types-networkx, no en runtime.
    _Graph = nx.Graph[Any, Any, Any]
else:
    _Graph = nx.Graph


class NetworkSpec(BaseModel):
    """Configuración declarativa de una red bibliométrica.

    Hito 9: soporta carga desde YAML vía ``load_specs``.

    R5: ``kind`` es de tipo ``NetworkKind`` (fuente única, ADR 0023).  Ya no
    hay un ``Literal[...]`` duplicado en ``spec.py`` y ``facade.py``.

    ``extra="forbid"``: campos desconocidos en el YAML producen un error
    accionable en ``load_specs`` (citando el campo y el índice de la red),
    en vez de ignorarse silenciosamente.

    Args:
        kind: Tipo de red a proyectar (``NetworkKind`` enum).
        min_weight: Peso mínimo de arista (D1). Default 1 = sin filtro.
        min_year: Filtro de año mínimo (futuro).
        max_year: Filtro de año máximo (futuro).
        scope: Alcance de la proyección.
        clustering: Método de detección de comunidades.
        resolution: Resolución para Louvain (python-louvain ``best_partition``).
            Default 1.0 reproduce el comportamiento anterior. Ignorado para
            ``label_prop`` y ``greedy_modularity`` (sin error).
        assortativity_attribute: Atributo categórico para asortatividad.
        layout: Algoritmo de layout para visualización (futuro).
        keyword_filter: Lista de términos temáticos. Si se provee (lista no
            vacía), solo entran al build los papers cuyo ``keywords_raw``
            contenga al menos un término que matchee (ANY) por substring
            case-insensitive. Ej: ``["complex", "ecolog"]`` incluye papers con
            keywords "Complexity" o "Ecological economics". ``None`` o lista
            vacía = sin filtro (comportamiento por defecto).
    """

    model_config = ConfigDict(extra="forbid")

    kind: NetworkKind
    min_weight: int = 1
    min_year: int | None = None
    max_year: int | None = None
    scope: Literal["full", "seeds_only"] = "full"
    clustering: Literal["louvain", "label_prop", "greedy_modularity"] | None = "louvain"
    resolution: float = 1.0
    assortativity_attribute: str | None = None
    layout: Literal["spring", "kamada_kawai", "circular"] | None = None
    keyword_filter: list[str] | None = None


def load_specs(path: str | Path) -> list[NetworkSpec]:
    """Carga y valida una lista de ``NetworkSpec`` desde un archivo YAML.

    El documento YAML debe tener la clave raíz ``networks:`` con una lista de
    entradas; cada entrada se valida construyendo ``NetworkSpec(**entry)`` para
    reusar la validación Pydantic (no se redefine el schema).

    Errores accionables:
    - YAML malformado (sintaxis) → ``ValueError`` con el detalle del
      ``yaml.YAMLError``.
    - Spec inválida (``kind`` desconocido, campo extra, tipo incorrecto) →
      ``ValueError`` citando el archivo, el índice de la red (0-based) y el
      campo problemático extraído del ``ValidationError`` de Pydantic.

    Args:
        path: Ruta al archivo YAML con la definición de redes.

    Returns:
        Lista de ``NetworkSpec`` validadas, en el orden del archivo.

    Raises:
        ValueError: Si el YAML está malformado, falta la clave ``networks:``,
            o alguna entrada no cumple el schema de ``NetworkSpec``.
        FileNotFoundError: Si el archivo no existe.

    Ejemplo de YAML válido::

        networks:
          - kind: bibliographic_coupling
            min_weight: 2
            resolution: 1.5
          - kind: author_collab
            clustering: label_prop
    """
    import yaml  # importación perezosa — PyYAML es dependencia declarada del proyecto

    resolved = Path(path)

    try:
        raw = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"YAML malformado en '{resolved}': {exc}") from exc

    if not isinstance(raw, dict) or "networks" not in raw:
        raise ValueError(
            f"El archivo '{resolved}' debe tener una clave raíz 'networks:' "
            "con una lista de definiciones de red."
        )

    entries = raw["networks"]
    if not isinstance(entries, list):
        raise ValueError(
            f"La clave 'networks:' en '{resolved}' debe ser una lista, "
            f"pero se encontró: {type(entries).__name__}."
        )

    specs: list[NetworkSpec] = []
    for idx, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(
                f"'{resolved}' — red #{idx}: se esperaba un objeto de campos, "
                f"pero se encontró: {type(entry).__name__}."
            )
        try:
            specs.append(NetworkSpec(**entry))
        except ValidationError as exc:
            # Extraer el primer error para dar un mensaje accionable
            first_error = exc.errors()[0]
            field = ".".join(str(loc) for loc in first_error["loc"]) or "<root>"
            msg = first_error["msg"]
            raise ValueError(
                f"'{resolved}' — red #{idx}: campo '{field}': {msg}. "
                f"({len(exc.errors())} error(es) de validación en total)"
            ) from exc

    return specs


@dataclass
class NetworkArtifact:
    """Resultado de proyectar y analizar un corpus con una ``NetworkSpec``.

    Agrupa el grafo, las métricas, las comunidades, la asortatividad, el layout
    y la especificación que lo originó.

    Attributes:
        graph: Grafo NetworkX proyectado.
        metrics: Salida de ``network_metrics`` (densidad, componentes, clustering).
        communities: Salida de ``detect_communities`` o None si no se calculó.
        assortativity: Salida de ``assortativity`` o None si no se calculó.
        layout: Dict nodo→coordenadas o None si no se calculó.
        spec: Especificación que generó este artefacto.
    """

    graph: _Graph
    metrics: dict[str, object]
    communities: dict[Any, int] | None
    assortativity: dict[str, object] | None
    layout: dict[Any, Any] | None
    spec: NetworkSpec
