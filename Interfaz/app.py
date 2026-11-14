"""Ventana, pila de escenas y bucle principal."""
import pygame
import config
from . import manifest
from .assets import AssetManager
from .audio import AudioManager
from .scenes import SceneStack
from .ui_scenes import TitleScene


class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("FormicBox")
        self.screen = pygame.display.set_mode((config.SCREEN_W, config.SCREEN_H), pygame.RESIZABLE)
        self.assets = AssetManager()          # requiere la ventana ya creada (convert_alpha)
        self.audio = AudioManager()
        self.scenes = SceneStack()
        self.running = True
        self._fonts = {}
        self._bg = None
        self._bg_warned = False
        self.scenes.push(TitleScene(self))

    def font(self, size):
        f = self._fonts.get(size)
        if f is None:
            f = self._fonts[size] = pygame.font.SysFont("consolas,dejavusansmono,couriernew,monospace", size)
        return f

    def background(self, size):
        """Imagen del título cubriendo la ventana. Si falta Assets/ui/title.png usa un degradado provisional."""
        if self._bg is None or self._bg[0] != size:
            path = manifest.ROOT / "ui/title.png"
            surf = pygame.Surface(size)
            if path.is_file():
                img = pygame.image.load(str(path)).convert()
                iw, ih = img.get_size()
                k = max(size[0] / iw, size[1] / ih)
                img = pygame.transform.smoothscale(img, (int(iw * k) + 1, int(ih * k) + 1))
                surf.blit(img, ((size[0] - img.get_width()) // 2, (size[1] - img.get_height()) // 2))
            else:
                if not self._bg_warned:
                    self._bg_warned = True
                    print("[assets] falta ui/title.png: uso fondo provisional")
                for y in range(size[1]):
                    c = int(20 + 45 * y / max(1, size[1]))
                    pygame.draw.line(surf, (c, c // 2 + 10, c // 3), (0, y), (size[0], y))
            self._bg = (size, surf)
        return self._bg[1]

    def quit(self):
        self.running = False

    def run(self):
        clock = pygame.time.Clock()
        while self.running and self.scenes.top is not None:
            dt = clock.tick(config.FPS) / 1000.0
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.running = False
                elif e.type == pygame.VIDEORESIZE:
                    self.screen = pygame.display.get_surface()
                    for s in self.scenes.stack:
                        s.on_resize()
                else:
                    top = self.scenes.top
                    if top is not None:
                        top.handle_event(e)
            top = self.scenes.top
            if top is None:
                break
            top.update(dt)
            self.audio.update(dt)
            top = self.scenes.top
            if top is None:
                break
            self.screen.fill((12, 12, 14))
            top.draw(self.screen)
            pygame.display.flip()
        pygame.quit()