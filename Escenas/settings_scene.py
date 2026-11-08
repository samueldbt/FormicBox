"""Ajustes: volúmenes (izquierda/derecha), pantalla completa (Enter) y lista de controles."""
import pygame
from . import ui
from .settings import VOLUME_STEP

CONTROLS = [
    ("Menús", [
        ("Flechas arriba/abajo", "moverse"),
        ("Enter", "elegir / activar"),
        ("Izquierda/derecha", "cambiar volumen"),
        ("Esc", "volver"),
    ]),
    ("Modo Dios", [
        ("Flechas o WASD", "mover la cámara"),
        ("Espacio", "pausa / seguir"),
        ("N", "avanzar un tick"),
        ("R", "reiniciar"),
        ("M / G / T", "feromonas / gradiente / tráfico"),
        ("1-4", "capas de feromona"),
        ("Clic (panel)", "herramientas"),
        ("F9", "forzar game over (prueba)"),
        ("Esc", "volver al menú"),
    ]),
]


class SettingsScene(ui.MenuScene):
    title = "Ajustes"
    top = 0.28
    spacing = 44

    def __init__(self):
        super().__init__()
        self.items = [
            ("Música", lambda: None),
            ("Efectos", lambda: None),
            (lambda: f"Pantalla completa: {'Sí' if self.app.settings['fullscreen'] else 'No'}",
             lambda: self.app.set_fullscreen(not self.app.settings["fullscreen"])),
            ("Volver", lambda: self.manager.pop()),
        ]
        self.volume_keys = {0: "music_volume", 1: "sfx_volume"}

    def on_key(self, e):
        key = self.volume_keys.get(self.index)
        if key is None:
            return
        if e.key in (pygame.K_LEFT, pygame.K_a):
            delta = -VOLUME_STEP
        elif e.key in (pygame.K_RIGHT, pygame.K_d):
            delta = VOLUME_STEP
        else:
            return
        s = self.app.settings
        new = max(0, min(100, s[key] + delta))
        if new != s[key]:
            s[key] = new
            self.app.save_settings()

    def draw_item(self, surface, i, center, selected):
        key = self.volume_keys.get(i)
        if key is None:
            return super().draw_item(surface, i, center, selected)
        color = ui.ACCENT if selected else ui.FG
        cx, cy = center
        bar_w, bar_h = 300, 18
        ui.text(surface, ("> " if selected else "  ") + self.label(i), 30, color,
                topleft=(cx - bar_w // 2 - 230, cy - 17), bold=selected)
        rect = pygame.Rect(cx - bar_w // 2, cy - bar_h // 2, bar_w, bar_h)
        value = self.app.settings[key]
        pygame.draw.rect(surface, ui.BAR_BG, rect, border_radius=4)
        fill = rect.copy()
        fill.w = int(bar_w * value / 100)
        if fill.w:
            pygame.draw.rect(surface, color, fill, border_radius=4)
        pygame.draw.rect(surface, ui.DIM, rect, 1, border_radius=4)
        arrows = "<  >" if selected else ""
        ui.text(surface, f"{value:3d}  {arrows}", 24, color, topleft=(rect.right + 16, cy - 13))

    def draw_footer(self, surface):
        W, H = surface.get_size()
        y0 = int(H * self.top) + len(self.items) * self.spacing + 10
        ui.text(surface, "Controles", 24, ui.TITLE, center=(W // 2, y0), bold=True)
        col_w = min(560, W // 2 - 20)
        for c, (group, rows) in enumerate(CONTROLS):
            x = W // 2 - col_w - 10 + c * (col_w + 20)
            y = y0 + 24
            ui.text(surface, group, 18, ui.ACCENT, topleft=(x, y), bold=True)
            y += 24
            for key, what in rows:
                ui.text(surface, key, 16, ui.FG, topleft=(x, y))
                ui.text(surface, what, 16, ui.DIM, topleft=(x + 230, y))
                y += 19
        ui.text(surface, "El sonido llega la semana que viene: por ahora los volúmenes solo se guardan.",
                14, ui.DIM, center=(W // 2, H - 22))
