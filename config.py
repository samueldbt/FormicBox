"""Constantes globales de FormicBox. Los demás grupos pueden importar de aquí."""

GRID_W = 80          # columnas del mapa (celdas)
GRID_H = 60          # filas del mapa (celdas)
CELL_SIZE = 10       # tamaño de cada celda en píxeles
HUD_WIDTH = 220      # ancho del panel lateral (Grupo 3) en píxeles
FPS = 30

MAP_PX_W = GRID_W * CELL_SIZE
MAP_PX_H = GRID_H * CELL_SIZE
WINDOW_W = MAP_PX_W + HUD_WIDTH
WINDOW_H = MAP_PX_H

# Colores provisionales (el Grupo 3 los reemplazará por sprites)
COLOR_BG = (34, 40, 34)
COLOR_GRID = (50, 58, 50)
COLOR_HUD = (24, 24, 28)
COLOR_HIGHLIGHT = (240, 200, 60)
