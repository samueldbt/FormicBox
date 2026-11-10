from dataclasses import dataclass
from typing import Callable

import numpy as np

from .terrain import DIRT, ROCK, WATER, NEST
from .objects import NONE, GRASS, MANGO, BOCADILLO

MIN_W, MIN_H = 24, 14


@dataclass(frozen=True)
class Scenario:
    id: str        # clave estable para el menú: "corridor", "u_obstacle", "grass_field"
    name: str      # nombre para mostrar
    tip: str       # "qué mirar"
    seed: int      # semilla fija
    build: Callable  # (width, height) -> (terrain, objects, moisture)


def _blank(w, h, terrain_fill):
    if w < MIN_W or h < MIN_H:
        raise ValueError(f"Los escenarios necesitan al menos {MIN_W}x{MIN_H}, recibí {w}x{h}")
    t = np.full((h, w), terrain_fill, dtype=np.int16)
    o = np.full((h, w), NONE, dtype=np.int16)
    m = np.full((h, w), 0.5, dtype=np.float32)
    return t, o, m


def _corridor(w, h):
    t, o, m = _blank(w, h, ROCK)
    mid = h // 2
    t[mid - 1:mid + 2, 1:w - 1] = DIRT       # pasillo de 3 celdas de alto
    t[mid - 1:mid + 2, 1:4] = NEST           # nido en el extremo izquierdo
    o[mid - 1, w - 3] = GRASS                # comida en el extremo derecho
    o[mid, w - 3] = MANGO
    o[mid + 1, w - 3] = BOCADILLO
    m[:] = 0.6
    return t, o, m


def _u_obstacle(w, h):
    t, o, m = _blank(w, h, DIRT)
    mid = h // 2
    t[mid - 1:mid + 2, 2:5] = NEST
    L = max(3, h // 4)
    xa, xb = w // 2 - 3, w // 2 + 3
    t[mid - L:mid + L + 1, xb] = ROCK        # base de la U (lado opuesto al nido)
    t[mid - L, xa:xb + 1] = ROCK             # brazo superior
    t[mid + L, xa:xb + 1] = ROCK             # brazo inferior (la U abre hacia el nido)
    o[mid - 1, w - 4] = GRASS                # comida detrás de la U
    o[mid, w - 4] = MANGO
    o[mid + 1, w - 4] = BOCADILLO
    m[:] = 0.5
    return t, o, m


def _grass_field(w, h):
    t, o, m = _blank(w, h, DIRT)
    mid = h // 2
    t[mid - 1:mid + 2, 1:4] = NEST
    px = 2 * w // 3
    t[h // 4:h // 4 + 3, px:px + 4] = WATER  # laguna: cortafuego natural
    o[t == DIRT] = GRASS
    o[:, :5] = NONE                          # sin pasto pegado al nido
    m[:] = 0.15                              # seco: el fuego se propaga fácil
    return t, o, m


SCENARIOS = {s.id: s for s in (
    Scenario("corridor", "Corredor",
             "Mira cómo se forma un rastro delgado de feromona entre el nido y la comida (tecla M, capa 1).",
             101, _corridor),
    Scenario("u_obstacle", "Obstáculo en U",
             "Mira si las hormigas se quedan atrapadas en la U o logran rodearla para llegar a la comida.",
             102, _u_obstacle),
    Scenario("grass_field", "Campo de pasto",
             "Lanza un rayo y mira cómo se propaga el fuego; fíjate en si la laguna lo detiene.",
             103, _grass_field),
)}


def list_scenarios():
    """Lista ordenada de Scenario, para que el menú la recorra (id, name, tip)."""
    return list(SCENARIOS.values())


def get_scenario(ref):
    """Acepta un id (str) o un objeto Scenario."""
    if isinstance(ref, Scenario):
        return ref
    try:
        return SCENARIOS[ref]
    except KeyError:
        raise ValueError(f"Escenario desconocido: {ref!r}. Disponibles: {list(SCENARIOS)}")