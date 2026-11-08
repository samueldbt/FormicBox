"""Game over: tiempo sobrevivido, recursos entregados y bajas por casta."""
import pygame
from . import ui

CASTE_NAMES = (("WORKER", "Obreras"), ("SOLDIER", "Soldadas"), ("MARABUNTA", "Marabuntas"))
RESOURCE_NAMES = (("grass", "Pasto"), ("mango", "Mango"), ("bocadillo", "Bocadillo"))


def format_time(seconds):
    seconds = int(seconds)
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


class GameOverScene(ui.MenuScene):
    title = "Fin de la colonia"
    top = 0.74
    spacing = 42

    def __init__(self, summary, on_restart):
        """summary: dict de Simulation.summary(). on_restart: función que reinicia la simulación."""
        super().__init__()
        self.summary = summary or {}
        self.on_restart = on_restart
        self.items = [("Reiniciar", self.restart), ("Volver al menú", self.back)]

    def restart(self):
        self.on_restart()
        self.manager.pop()                       # vuelve al Modo Dios ya reiniciado

    def back(self):
        from .menu import MainMenuScene
        if not self.manager.pop_to(MainMenuScene):
            self.manager.to_title()

    def draw(self, surface):
        W, H = surface.get_size()
        below = self.manager.stack[-2] if len(self.manager.stack) > 1 else None
        if below is not None:                    # el mapa congelado de fondo, oscurecido
            below.draw(surface)
            shade = pygame.Surface((W, H), pygame.SRCALPHA)
            shade.fill((0, 0, 0, 200))
            surface.blit(shade, (0, 0))
        else:
            surface.fill(ui.BG)

        self.draw_header(surface)
        s = self.summary
        cx = W // 2
        y = int(H * 0.29)
        ui.text(surface, f"Tiempo sobrevivido: {format_time(s.get('seconds', 0))}  ({s.get('ticks', 0)} ticks)",
                26, ui.FG, center=(cx, y))

        col_l, col_r = cx - 220, cx + 60
        y += 50
        ui.text(surface, "Recursos entregados", 22, ui.ACCENT, topleft=(col_l, y), bold=True)
        ui.text(surface, "Bajas por casta", 22, ui.ACCENT, topleft=(col_r, y), bold=True)
        delivered = s.get("delivered", {})
        deaths = s.get("deaths", {})
        for i in range(3):
            yy = y + 36 + i * 30
            key, name = RESOURCE_NAMES[i]
            ui.text(surface, f"{name:<10}{delivered.get(key, 0):>6}", 22, ui.FG, topleft=(col_l, yy))
            key, name = CASTE_NAMES[i]
            ui.text(surface, f"{name:<11}{deaths.get(key, 0):>6}", 22, ui.FG, topleft=(col_r, yy))

        cy = int(H * self.top)
        for i in range(len(self.items)):
            self.draw_item(surface, i, (cx, cy + i * self.spacing), i == self.index)
        ui.text(surface, "Flechas: mover   Enter: elegir   Esc: volver al menú", 16, ui.DIM, center=(cx, H - 24))
