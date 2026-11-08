"""Menú principal y la pantalla "Próximamente"."""
import pygame
from . import ui
from .base import Scene


class MainMenuScene(ui.MenuScene):
    title = "FormicBox"
    top = 0.36

    def __init__(self):
        super().__init__()
        self.items = [
            ("Modo Dios", self.god_mode),
            ("Testeo", lambda: self.manager.push(ComingSoonScene("Testeo"))),
            ("Lucha", lambda: self.manager.push(ComingSoonScene("Lucha"))),
            ("Ajustes", self.settings),
            ("Salir", lambda: self.app.quit()),
        ]

    def god_mode(self):
        from .god_mode import GodModeScene
        self.manager.push(GodModeScene())

    def settings(self):
        from .settings_scene import SettingsScene
        self.manager.push(SettingsScene())

    def back(self):
        self.manager.to_title()


class ComingSoonScene(Scene):
    """Testeo y Lucha: se llenan con los escenarios la semana que viene."""

    def __init__(self, name):
        super().__init__()
        self.name = name

    def handle_event(self, e):
        if e.type == pygame.KEYDOWN and (e.key == pygame.K_ESCAPE or ui.is_enter(e)):
            self.manager.pop()

    def draw(self, surface):
        surface.fill(ui.BG)
        W, H = surface.get_size()
        ui.text(surface, self.name, 44, ui.TITLE, center=(W // 2, int(H * 0.35)), bold=True)
        ui.text(surface, "Próximamente", 34, ui.ACCENT, center=(W // 2, int(H * 0.52)))
        ui.text(surface, "Enter o Esc: volver", 16, ui.DIM, center=(W // 2, H - 24))
