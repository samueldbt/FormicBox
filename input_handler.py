"""Modo Dios: traduce clics del mouse a coordenadas (X, Y) de la matriz.

La función `screen_to_cell` es pura (no depende de pygame), así se puede probar
fácil y el Grupo 1 solo tiene que conectar `on_cell_click` a su matriz.
"""
from typing import Callable, Optional, Tuple

from . import config

Cell = Tuple[int, int]


def screen_to_cell(px: int, py: int) -> Optional[Cell]:
    """Convierte píxeles de pantalla a (x, y) de celda.

    Devuelve None si el clic cae fuera del mapa (por ejemplo, sobre el HUD).
    """
    if px < 0 or py < 0 or px >= config.MAP_PX_W or py >= config.MAP_PX_H:
        return None
    return px // config.CELL_SIZE, py // config.CELL_SIZE


def default_click_callback(x: int, y: int, button: int) -> None:
    """Callback por defecto del entregable 3: imprimir coordenadas."""
    nombre = {1: "izquierdo", 2: "central", 3: "derecho"}.get(button, str(button))
    print(f"Clic {nombre} en celda (X={x}, Y={y})")


class GodMode:
    """Detecta clics y los reenvía a un callback `(x, y, button)`.

    Más adelante: colocar pasto/bocadillo, iniciar fuego, herramienta kill.
    """

    def __init__(self, on_cell_click: Callable[[int, int, int], None] = default_click_callback):
        self.on_cell_click = on_cell_click
        self.hover: Optional[Cell] = None

    def handle_mouse_motion(self, px: int, py: int) -> None:
        self.hover = screen_to_cell(px, py)

    def handle_mouse_button(self, px: int, py: int, button: int) -> Optional[Cell]:
        cell = screen_to_cell(px, py)
        if cell is not None:
            self.on_cell_click(cell[0], cell[1], button)
        return cell
