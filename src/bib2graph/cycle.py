"""cycle — FSM cíclico del lazo de investigación (ADR 0016 enmendado 2026-06-15).

Concepto de DOMINIO puro: el modelo de estados, las reglas de transición y el
contador de ronda viven aquí.  El backend (DuckDB) solo persiste el resultado;
no define el dominio.

Diagrama del ciclo (Nota 05 §3):

    SEEDED ─(chain)→ FORAGED ─(filter)→ FILTERED ─(build)→ BUILT ─(monitor)→ MONITORED
       ▲                                                                           │
       └──────────────────────── reseed = "la idea muta" ◄──────────────────────────┘

Reglas:
- Las transiciones de la cadena principal (``chain``, ``filter``, ``build``,
  ``monitor``) llevan a los estados en secuencia.
- Las transiciones permisivas (saltos) están permitidas: no se bloquea ningún
  destino en la cadena principal.
- ``reseed`` es una transición de PRIMERA CLASE: loop-back a ``SEEDED`` desde
  cualquier estado, **incrementa** el contador de ronda y conserva lo curado.
- La curación (``accept``/``reject``) es TRANSVERSAL: está disponible en
  cualquier estado y NO transiciona el lazo.  ``status`` la expone siempre
  como acción siempre-disponible separada de ``transitions_available``.

Uso:

    >>> state = CycleState.SEEDED
    >>> round_ = 1
    >>> state, round_ = apply_transition(state, "chain", round_)
    >>> state
    <CycleState.FORAGED: 'FORAGED'>
    >>> round_
    1
    >>> state, round_ = apply_transition(state, "reseed", round_)
    >>> state
    <CycleState.SEEDED: 'SEEDED'>
    >>> round_
    2
"""

from __future__ import annotations

from enum import StrEnum

# ---------------------------------------------------------------------------
# CycleState
# ---------------------------------------------------------------------------


class CycleState(StrEnum):
    """Estados del lazo de investigación (ADR 0016 enmendado).

    Los estados reflejan el ciclo real de la Nota 05 §3:
    ``SEEDED`` → ``FORAGED`` → ``FILTERED`` → ``BUILT`` → ``MONITORED``
    con loop-back ``reseed`` a ``SEEDED`` (primera clase).

    ``MONITORED`` modela el paso 8 del ciclo.  El comando que lo dispara
    puede no existir aún (futuro); el estado y la regla de transición sí
    existen en el modelo de dominio.
    """

    SEEDED = "SEEDED"
    FORAGED = "FORAGED"
    FILTERED = "FILTERED"
    BUILT = "BUILT"
    MONITORED = "MONITORED"


# ---------------------------------------------------------------------------
# Tabla de transiciones de la cadena principal
# ---------------------------------------------------------------------------

# Acción → estado destino en la cadena principal (permisiva: no bloquea saltos,
# pero la acción nombrada lleva al estado que le corresponde en el ciclo).
_CHAIN_TRANSITIONS: dict[str, CycleState] = {
    "chain": CycleState.FORAGED,
    "filter": CycleState.FILTERED,
    "build": CycleState.BUILT,
    "monitor": CycleState.MONITORED,
    # "seed" en una primera siembra también lleva a SEEDED
    "seed": CycleState.SEEDED,
}

# ---------------------------------------------------------------------------
# Función de transición pura
# ---------------------------------------------------------------------------


def apply_transition(
    current_state: CycleState | None,
    action: str,
    current_round: int,
) -> tuple[CycleState, int]:
    """Aplica una acción sobre el estado actual y devuelve (nuevo_estado, nueva_ronda).

    Modelo de dominio puro: dado (estado_actual, ronda, acción) → (estado_nuevo,
    ronda_nueva).  Sin tocar DuckDB.

    Reglas:
    - ``reseed``: loop-back a ``SEEDED``, ronda + 1.  Es la única acción que
      incrementa la ronda.  Está disponible desde cualquier estado.
    - Acciones de cadena (``seed``, ``chain``, ``filter``, ``build``,
      ``monitor``): transicionan al estado correspondiente, ronda sin cambio.
    - Acción desconocida: se lanza ``ValueError``.
    - La curación (``accept``/``reject``) NO es una transición: no se maneja
      aquí.  ``status`` la expone como acción siempre-disponible separada.

    Args:
        current_state: Estado actual del lazo (``None`` = sin estado previo).
        action: Nombre de la acción a aplicar.
        current_round: Número de ronda actual (empieza en 1 con la primera
            siembra).

    Returns:
        Tupla ``(nuevo_estado, nueva_ronda)``.

    Raises:
        ValueError: Si la acción no es reconocida.

    Examples:
        >>> apply_transition(None, "seed", 0)
        (<CycleState.SEEDED: 'SEEDED'>, 1)
        >>> apply_transition(CycleState.BUILT, "reseed", 1)
        (<CycleState.SEEDED: 'SEEDED'>, 2)
    """
    if action == "reseed":
        return CycleState.SEEDED, current_round + 1

    if action == "seed":
        # Primera siembra: ronda pasa a 1 si era 0
        new_round = max(current_round, 1)
        return CycleState.SEEDED, new_round

    if action in _CHAIN_TRANSITIONS:
        return _CHAIN_TRANSITIONS[action], current_round

    raise ValueError(
        f"Acción '{action}' no reconocida. "
        f"Acciones válidas: {[*sorted(_CHAIN_TRANSITIONS.keys()), 'reseed']}."
    )


# ---------------------------------------------------------------------------
# Helper: transiciones disponibles desde un estado dado
# ---------------------------------------------------------------------------

# Curación transversal: siempre disponible, nunca transiciona el lazo.
# Se documenta aquí como constante de dominio y se expone en ``status``.
CURATION_ACTIONS: list[str] = ["accept", "reject"]

# Transiciones de la cadena (permisivas: se muestran desde el estado más lógico
# pero no se bloquean desde otros).  El mapa refleja el ciclo real de la Nota 05.
_AVAILABLE_TRANSITIONS: dict[str | None, list[str]] = {
    None: ["seed"],
    CycleState.SEEDED: [
        "chain",
        "filter",
        "build",
        "snapshot",
        "inspect",
        "validate",
        "reseed",
    ],
    CycleState.FORAGED: [
        "filter",
        "build",
        "chain",
        "snapshot",
        "inspect",
        "validate",
        "reseed",
    ],
    CycleState.FILTERED: [
        "build",
        "filter",
        "chain",
        "snapshot",
        "inspect",
        "validate",
        "reseed",
    ],
    CycleState.BUILT: [
        "monitor",
        "export",
        "build",
        "filter",
        "chain",
        "snapshot",
        "inspect",
        "validate",
        "reseed",
    ],
    CycleState.MONITORED: [
        "monitor",
        "reseed",
        "build",
        "filter",
        "chain",
        "export",
        "snapshot",
        "inspect",
        "validate",
    ],
}


def available_transitions(state: CycleState | None) -> list[str]:
    """Devuelve la lista de transiciones disponibles desde el estado dado.

    Las transiciones son permisivas (no se bloquean saltos), pero la lista
    refleja el ciclo lógico de la Nota 05.  ``reseed`` siempre está incluido
    cuando hay un estado previo (no en ``None``).

    La curación (``accept``/``reject``) es TRANSVERSAL: no aparece aquí sino
    en ``CURATION_ACTIONS``.  ``status`` los muestra por separado como
    ``curation_available``.

    Args:
        state: Estado actual del lazo (``None`` = sin estado previo).

    Returns:
        Lista de nombres de acciones disponibles desde el estado dado.
    """
    return list(_AVAILABLE_TRANSITIONS.get(state, ["seed"]))
