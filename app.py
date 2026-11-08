"""App: crea la ventana UNA sola vez y corre el bucle con la pila de escenas."""
import pygame
import config
from Escenas import settings as settings_io
from Escenas.base import SceneManager
from Escenas.title import TitleScene


class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("FormicBox")
        self.settings = settings_io.load()
        self.screen = None
        self._apply_display_mode()
        pygame.key.set_repeat(300, 60)       # mantener una flecha pulsada repite (menús y volumen)
        self.manager = SceneManager(self)
        self.clock = pygame.time.Clock()
        self.running = True

    # ------------------------------------------------------------ ventana
    def _apply_display_mode(self):
        if self.settings["fullscreen"]:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode((config.SCREEN_W, config.SCREEN_H), pygame.RESIZABLE)

    def set_fullscreen(self, on):
        self.settings["fullscreen"] = bool(on)
        try:
            self._apply_display_mode()
        except pygame.error as e:            # p. ej. sin soporte de pantalla completa
            print(f"[app] no se pudo cambiar el modo de pantalla: {e}")
            self.settings["fullscreen"] = False
            self._apply_display_mode()
        self.save_settings()

    def save_settings(self):
        settings_io.save(self.settings)

    def quit(self):
        self.running = False

    # ------------------------------------------------------------ bucle
    def run(self, first_scene=None):
        self.manager.push(first_scene or TitleScene())
        while self.running and not self.manager.empty:
            dt = min(self.clock.tick(config.FPS) / 1000.0, 0.25)   # tras una pausa larga no "salta"
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.quit()
                elif e.type == pygame.VIDEORESIZE:
                    self.screen = pygame.display.get_surface()
                self.manager.handle_event(e)
                if not self.running or self.manager.empty:
                    break
            if not self.running or self.manager.empty:
                break
            self.manager.update(dt)
            self.manager.draw(self.screen)
            pygame.display.flip()
        self.manager.clear()
        pygame.quit()
