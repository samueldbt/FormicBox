"""Pantalla de título: logo y "Pulsa Enter"."""
import math
import pygame
from . import ui
from .base import Scene


class TitleScene(Scene):
    def __init__(self):
        super().__init__()
        self.logo = None
        self.t = 0.0

    def on_enter(self):
        self.logo = ui.load_logo()

    def handle_event(self, e):
        if e.type != pygame.KEYDOWN:
            return
        if ui.is_enter(e):
            from .menu import MainMenuScene
            self.manager.push(MainMenuScene())
        elif e.key == pygame.K_ESCAPE:
            self.app.quit()

    def update(self, dt):
        self.t += dt

    def draw(self, surface):
        surface.fill(ui.BG)
        W, H = surface.get_size()
        ui.draw_logo(surface, self.logo, (W // 2, int(H * 0.40)), W * 0.8, H * 0.5)
        ui.text(surface, "Colonia de hormigas: autómata celular + agentes", 18, ui.DIM, center=(W // 2, int(H * 0.62)))
        blink = 0.5 + 0.5 * math.sin(self.t * 4)
        c = tuple(int(a + (b - a) * blink) for a, b in zip(ui.DIM, ui.ACCENT))
        ui.text(surface, "Pulsa Enter", 28, c, center=(W // 2, int(H * 0.78)), bold=True)
        ui.text(surface, "Esc: salir", 16, ui.DIM, center=(W // 2, H - 24))
