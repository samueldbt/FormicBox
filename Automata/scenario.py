from dataclasses import dataclass
from typing import Callable, Optional, Tuple

import numpy as np

from .terrain import DIRT, ROCK, WATER, NEST
from .objects import NONE, GRASS, MANGO, BOCADILLO

MIN_W, MIN_H = 24, 14


@dataclass(frozen=True)
class Scenario:
    id: str
    name: str
    tip: str
    seed: int
    build: Callable  # (width, height) -> (terrain, objects, moisture, blocks)
    # blocks = [(kind, y, x)] de objetos 2x2 (MANGO/BOCADILLO); (y, x) = esquina superior izquierda
    colony: bool = True                       # False = sin hormigas (pruebas de fuego/clima)
    wind: Tuple[float, float] = (0.0, 0.0)    # viento propio del escenario (x, y)
    auto_weather: bool = False                # lluvia, sequía y rayos solos
    ignite: Optional[Tuple[float, float]] = None   # (fracción y, fracción x) del mapa donde arde desde el tick 0


def _blank(w, h, terrain_fill):
    if w < MIN_W or h < MIN_H:
        raise ValueError(f"Los escenarios necesitan al menos {MIN_W}x{MIN_H}, recibí {w}x{h}")
    t = np.full((h, w), terrain_fill, dtype=np.int16)
    o = np.full((h, w), NONE, dtype=np.int16)      # solo pasto en celdas sueltas
    m = np.full((h, w), 0.5, dtype=np.float32)
    return t, o, m


def _corridor(w, h):
    t, o, m = _blank(w, h, ROCK)
    mid = h // 2
    t[mid - 1:mid + 2, 1:w - 1] = DIRT
    t[mid - 1:mid + 2, 1:4] = NEST
    o[mid - 1, w - 3] = GRASS
    o[mid + 1, w - 5] = GRASS
    blocks = [(MANGO, mid - 1, w - 5), (BOCADILLO, mid, w - 3)]
    m[:] = 0.6
    return t, o, m, blocks


def _u_obstacle(w, h):
    t, o, m = _blank(w, h, DIRT)
    mid = h // 2
    t[mid - 1:mid + 2, 2:5] = NEST
    L = max(3, h // 4)
    xa, xb = w // 2 - 3, w // 2 + 3
    t[mid - L:mid + L + 1, xb] = ROCK
    t[mid - L, xa:xb + 1] = ROCK
    t[mid + L, xa:xb + 1] = ROCK
    o[mid - 1, w - 4] = GRASS
    blocks = [(MANGO, mid - 1, w - 8), (BOCADILLO, mid + 1, w - 6)]
    m[:] = 0.5
    return t, o, m, blocks


def _grass_field(w, h):
    t, o, m = _blank(w, h, DIRT)
    mid = h // 2
    t[mid - 1:mid + 2, 1:4] = NEST
    px = 2 * w // 3
    t[h // 4:h // 4 + 3, px:px + 4] = WATER
    o[t == DIRT] = GRASS
    o[:, :5] = NONE
    m[:] = 0.15
    return t, o, m, []


def _fire_field(w, h):
    """Pasto parejo sin obstáculos: para ver cómo se propaga el fuego (con y sin viento)."""
    t, o, m = _blank(w, h, DIRT)
    t[h // 2 - 1:h // 2 + 2, 1:4] = NEST
    o[t == DIRT] = GRASS
    o[:, :5] = NONE
    m[:] = 0.1
    return t, o, m, []


def _jam(w, h):
    """Pasillo de 1 celda con una sala de comida al fondo: sirve para ver atascos y colisiones."""
    t, o, m = _blank(w, h, ROCK)
    mid = h // 2
    t[mid, 1:w - 1] = DIRT
    t[mid, 1:4] = NEST
    t[mid - 2:mid + 3, w - 12:w - 2] = DIRT
    o[mid - 2, w - 10] = GRASS
    blocks = [(MANGO, mid - 1, w - 8), (BOCADILLO, mid, w - 5)]
    m[:] = 0.5
    return t, o, m, blocks


def _open_field(w, h):
    """Campo despejado (modo Lucha): sin rocas ni agua, con pasto y algo de fruta lejos del nido."""
    t, o, m = _blank(w, h, DIRT)
    mid = h // 2
    t[mid - 1:mid + 2, 1:4] = NEST
    o[1:h - 1:3, 14:w - 1:4] = GRASS
    blocks = [(MANGO, 3, w // 3), (MANGO, h - 5, w // 2), (BOCADILLO, mid, 3 * w // 4), (MANGO, mid - 3, w - 12)]
    m[:] = 0.3
    return t, o, m, blocks


def _weather_lab(w, h):
    """Pasto, una laguna y nada más: sin hormigas, con clima automático (mira la humedad con H)."""
    t, o, m = _blank(w, h, DIRT)
    t[h // 2 - 1:h // 2 + 2, 1:4] = NEST
    t[h // 4:h // 4 + 3, w // 2:w // 2 + 5] = WATER
    o[t == DIRT] = GRASS
    o[:, :5] = NONE
    m[:] = 0.2
    return t, o, m, []


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
    Scenario("fire_field", "Fuego: propagación",
             "Sin hormigas. Un incendio arde desde el centro-izquierda; compara sin viento y con viento (comparación Viento).",
             104, _fire_field, colony=False, ignite=(0.5, 0.35)),
    Scenario("jam", "Atascos",
             "Pasillo de 1 celda: compara Atravesarse / Intercambio / Bloqueo y mira dónde se forman los atascos.",
             105, _jam),
    Scenario("weather_lab", "Laboratorio de clima",
             "Sin hormigas. Lluvia, sequía y rayos automáticos: mira la humedad (H) y cómo cambia el fuego.",
             106, _weather_lab, colony=False, auto_weather=True),
    Scenario("open_field", "Campo abierto (Lucha)",
             "Campo despejado para las oleadas de marabuntas: mira cuánto aguanta el nido.",
             107, _open_field),
)}


def list_scenarios():
    return list(SCENARIOS.values())


def get_scenario(ref):
    """Acepta un id (str) o un objeto Scenario."""
    if isinstance(ref, Scenario):
        return ref
    try:
        return SCENARIOS[ref]
    except KeyError:
        raise ValueError(f"Escenario desconocido: {ref!r}. Disponibles: {list(SCENARIOS)}")