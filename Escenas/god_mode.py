"""Modo Dios: la simulación de siempre, usando Game dentro de la pila de escenas."""
import pygame
from .base import Scene
from .game_over import GameOverScene

# Teclas que maneja la escena y NO llegan a Game.
KEY_BACK = pygame.K_ESCAPE
KEY_FORCE_GAME_OVER = pygame.K_F9      # para probar la pantalla de game over


class GodModeScene(Scene):
    def __init__(self, seed=None):
        super().__init__()
        self.seed = seed
        self.sim = None
        self.game = None
        self._game_over_shown = False

    def on_enter(self):
        from Simulación.compat import ensure_colony_api
        from Simulación.simulation import Simulation
        from Interfaz.game import Game
        ensure_colony_api()
        self.sim = Simulation(self.seed)
        self.game = Game(self.sim, screen=self.app.screen)
        self.game.running_standalone = False   # la App hace el flip de pantalla

    def on_resume(self):
        if not self.sim.game_over:             # se reinició desde la pantalla de game over
            self._game_over_shown = False

    def restart(self):
        self.game.restart(False)               # misma semilla; sim.reset() quita el game over
        self._game_over_shown = False

    def handle_event(self, e):
        if e.type in (pygame.QUIT, pygame.VIDEORESIZE):
            return                             # de eso se encarga la App
        if e.type == pygame.KEYDOWN:
            if e.key == KEY_BACK:
                self.manager.pop()
                return
            if e.key == KEY_FORCE_GAME_OVER:
                self.sim.game_over = True
                return
        self.game.handle_event(e)

    def update(self, dt):
        if self.sim.game_over:
            if not self._game_over_shown:
                self._game_over_shown = True
                self.manager.push(GameOverScene(self.sim.summary(), self.restart))
            return
        self.game.update(dt)

    def draw(self, surface):
        self.game.draw(surface)
