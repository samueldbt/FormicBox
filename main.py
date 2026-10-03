"""FormicBox - bucle principal (Grupo 4).

Ejecutar desde la raíz del repo:  python -m src.main
"""
import os
import sys

if os.environ.get("SDL_VIDEODRIVER") is None:
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from src import config
    from src.input_handler import GodMode
else:
    from . import config
    from .input_handler import GodMode


def draw_grid(screen: pygame.Surface) -> None:
    screen.fill(config.COLOR_BG, pygame.Rect(0, 0, config.MAP_PX_W, config.MAP_PX_H))
    for x in range(0, config.MAP_PX_W + 1, config.CELL_SIZE):
        pygame.draw.line(screen, config.COLOR_GRID, (x, 0), (x, config.MAP_PX_H))
    for y in range(0, config.MAP_PX_H + 1, config.CELL_SIZE):
        pygame.draw.line(screen, config.COLOR_GRID, (0, y), (config.MAP_PX_W, y))


def draw_hover(screen: pygame.Surface, hover) -> None:
    if hover is not None:
        rect = pygame.Rect(hover[0] * config.CELL_SIZE, hover[1] * config.CELL_SIZE,
                           config.CELL_SIZE, config.CELL_SIZE)
        pygame.draw.rect(screen, config.COLOR_HIGHLIGHT, rect, 2)


def draw_hud_placeholder(screen: pygame.Surface, font: pygame.font.Font, hover) -> None:
    pygame.draw.rect(screen, config.COLOR_HUD,
                     pygame.Rect(config.MAP_PX_W, 0, config.HUD_WIDTH, config.WINDOW_H))
    texto = "Celda: -" if hover is None else f"Celda: ({hover[0]}, {hover[1]})"
    screen.blit(font.render("FormicBox", True, (230, 230, 230)), (config.MAP_PX_W + 12, 12))
    screen.blit(font.render(texto, True, (200, 200, 200)), (config.MAP_PX_W + 12, 44))


def run(max_frames: int = 0) -> None:
    """Bucle principal. `max_frames` > 0 limita la ejecución (útil para pruebas)."""
    pygame.init()
    screen = pygame.display.set_mode((config.WINDOW_W, config.WINDOW_H))
    pygame.display.set_caption("FormicBox")
    font = pygame.font.SysFont(None, 24)
    clock = pygame.time.Clock()
    god = GodMode()

    running, frames = True, 0
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            elif event.type == pygame.MOUSEMOTION:
                god.handle_mouse_motion(*event.pos)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                god.handle_mouse_button(event.pos[0], event.pos[1], event.button)

        # TODO(G1): world.update()   TODO(G2): agents.update()
        draw_grid(screen)
        # TODO(G3): render de mapa y sprites
        draw_hover(screen, god.hover)
        draw_hud_placeholder(screen, font, god.hover)
        pygame.display.flip()
        clock.tick(config.FPS)

        frames += 1
        if max_frames and frames >= max_frames:
            running = False
    pygame.quit()


if __name__ == "__main__":
    run()