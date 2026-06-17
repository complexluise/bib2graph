"""sources.equation — ``EquationSpec`` y ``load_equation_spec``.

Define la capa declarativa de la ecuación de búsqueda (ADR 0030):
  - ``EquationSpec``: modelo Pydantic que empaqueta los parámetros de
    ``b2g seed`` en un YAML versionable (el artefacto "qué se busca").
  - ``load_equation_spec(path)``: carga y valida el YAML con la misma
    filosofía de errores accionables que ``load_specs`` en ``networks/spec.py``:
    YAML malformado → ``ValueError``; clave raíz ausente → ``ValueError``;
    campo desconocido / tipo incorrecto → ``ValueError`` citando archivo + campo.

Schema YAML (clave raíz ``equation:``, objeto — no lista):

    equation:
      query: '"unequal ecological exchange" OR "ecologically unequal exchange"'
      exclude:
        - "stock exchange"
      max_results: 150
      native: false
      min_year: 1990
      max_year: 2024

Los campos mapean 1:1 a los argumentos de ``run_seed`` / ``OpenAlexSource.seed``.

Ver ADR 0030 §Decisión (Schema de ``equation.yaml``) y ``networks/spec.py``
(precedente directo del patrón de loader).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError


class EquationSpec(BaseModel):
    """Configuración declarativa de una ecuación de búsqueda bibliográfica.

    ADR 0030: soporta carga desde YAML vía ``load_equation_spec``.

    ``extra="forbid"``: campos desconocidos en el YAML producen un error
    accionable en ``load_equation_spec`` (citando el campo problemático),
    en vez de ignorarse silenciosamente.

    Los campos mapean 1:1 a los argumentos de ``run_seed``
    (``equation`` → ``query``, ``exclude``, ``max_results``, ``native``,
    ``min_year``, ``max_year``).

    Args:
        query: Ecuación de búsqueda (WoS-style o nativa si ``native=True``).
            Campo requerido; no puede estar vacío.
        exclude: Términos a excluir del título/abstract (#30). Cada uno genera
            ``AND NOT title_and_abstract.search:"…"`` al filtro.
        max_results: Tope de resultados a traer de OpenAlex (#14). ``None``
            usa el default del source (200).
        native: Si es ``True``, pasa la ecuación cruda a OpenAlex sin traducción.
        min_year: Filtro de año mínimo (opcional).
        max_year: Filtro de año máximo (opcional).
    """

    model_config = ConfigDict(extra="forbid")

    query: str
    exclude: list[str] = []
    max_results: int | None = None
    native: bool = False
    min_year: int | None = None
    max_year: int | None = None


def load_equation_spec(path: str | Path) -> EquationSpec:
    """Carga y valida una ``EquationSpec`` desde un archivo YAML.

    El documento YAML debe tener la clave raíz ``equation:`` con un objeto
    de campos (no una lista); la entrada se valida construyendo
    ``EquationSpec(**data["equation"])`` para reusar la validación Pydantic.

    Errores accionables (mismo patrón que ``load_specs`` en ``networks/spec.py``):
    - YAML malformado (sintaxis) → ``ValueError`` con el detalle del
      ``yaml.YAMLError``.
    - Clave raíz ``equation:`` ausente → ``ValueError`` accionable.
    - Campo desconocido / tipo incorrecto → ``ValueError`` citando el archivo
      y el campo problemático extraído del ``ValidationError`` de Pydantic.

    Args:
        path: Ruta al archivo YAML con la definición de la ecuación.

    Returns:
        ``EquationSpec`` validada con los parámetros de siembra.

    Raises:
        ValueError: Si el YAML está malformado, falta la clave ``equation:``,
            o la entrada no cumple el schema de ``EquationSpec``.
        FileNotFoundError: Si el archivo no existe.

    Ejemplo de YAML válido::

        equation:
          query: '"unequal exchange" OR "ecological debt"'
          exclude:
            - "stock exchange"
          max_results: 150
          native: false
    """
    import yaml  # importación perezosa — PyYAML es dependencia declarada del proyecto

    resolved = Path(path)

    try:
        raw = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"YAML malformado en '{resolved}': {exc}") from exc

    if not isinstance(raw, dict) or "equation" not in raw:
        raise ValueError(
            f"El archivo '{resolved}' debe tener una clave raíz 'equation:' "
            "con los parámetros de la ecuación de búsqueda."
        )

    entry = raw["equation"]
    if not isinstance(entry, dict):
        raise ValueError(
            f"La clave 'equation:' en '{resolved}' debe ser un objeto de campos, "
            f"pero se encontró: {type(entry).__name__}."
        )

    try:
        return EquationSpec(**entry)
    except ValidationError as exc:
        first_error = exc.errors()[0]
        field = ".".join(str(loc) for loc in first_error["loc"]) or "<root>"
        msg = first_error["msg"]
        raise ValueError(
            f"'{resolved}' — equation: campo '{field}': {msg}. "
            f"({len(exc.errors())} error(es) de validación en total)"
        ) from exc
