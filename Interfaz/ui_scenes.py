"""Título, menú, ajustes y pantallas pendientes. Todo se maneja con flechas y Enter."""
import pygame
import config
from .scenes import Scene
from .game import GodScene
from .sandbox import SandboxScene
from Simulación.simulation import Simulation

ENTER = (pygame.K_RETURN, pygame.K_KP_ENTER)


def _overlay(size, alpha):
    s = pygame.Surface(size, pygame.SRCALPHA)
    s.fill((0, 0, 0, alpha))
    return s


class TitleScene(Scene):
    def __init__(self, app):
        self.app = app
        self.t = 0.0

    def update(self, dt):
        self.t += dt

    def handle_event(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key in ENTER:
                self.app.audio.play("menu")
                self.app.scenes.replace(MenuScene(self.app))
            elif e.key == pygame.K_ESCAPE:
                self.app.quit()

    def draw(self, screen):
        W, H = screen.get_size()
        screen.blit(self.app.background((W, H)), (0, 0))
        title = self.app.font(72).render("FormicBox", True, (240, 230, 200))
        screen.blit(title, title.get_rect(center=(W // 2, H // 2 - 20)))
        if int(self.t * 2) % 2 == 0:
            small = self.app.font(18).render("Presiona ENTER", True, (220, 220, 220))
            screen.blit(small, small.get_rect(center=(W // 2, H // 2 + 50)))


class MenuScene(Scene):
    OPTIONS = (("Modo Dios", "god"), ("Testeo", "test"), ("Competitivo", "comp"),
               ("Lucha", "fight"), ("Ajustes", "settings"), ("Salir", "quit"))

    def __init__(self, app):
        self.app = app
        self.i = 0

    def handle_event(self, e):
        if e.type != pygame.KEYDOWN:
            return
        if e.key == pygame.K_UP:
            self.i = (self.i - 1) % len(self.OPTIONS)
            self.app.audio.play("menu")
        elif e.key == pygame.K_DOWN:
            self.i = (self.i + 1) % len(self.OPTIONS)
            self.app.audio.play("menu")
        elif e.key in ENTER:
            self._activate(self.OPTIONS[self.i][1])
        elif e.key == pygame.K_ESCAPE:
            self.app.scenes.replace(TitleScene(self.app))

    def _activate(self, key):
        app = self.app
        app.audio.play("menu")
        if key == "god":
            app.scenes.push(GodScene(app, Simulation()))
        elif key == "fight":
            app.scenes.push(GodScene(app, Simulation(scenario="open_field"), waves=True))
        elif key == "settings":
            app.scenes.push(SettingsScene(app))
        elif key == "test":
            app.scenes.push(SandboxScene(app))
        elif key == "comp":
            app.scenes.push(PlaceholderScene(app, "Competitivo", "Se implementa al final"))
        elif key == "quit":
            app.quit()

    def draw(self, screen):
        W, H = screen.get_size()
        screen.blit(self.app.background((W, H)), (0, 0))
        screen.blit(_overlay((W, H), 150), (0, 0))
        f, fb = self.app.font(28), self.app.font(48)
        t = fb.render("FormicBox", True, (240, 230, 200))
        screen.blit(t, t.get_rect(center=(W // 2, 90)))
        y = 190
        for k, (label, _) in enumerate(self.OPTIONS):
            sel = k == self.i
            img = f.render(("> " if sel else "  ") + label, True, (255, 220, 120) if sel else (210, 210, 210))
            screen.blit(img, img.get_rect(center=(W // 2, y)))
            y += 46


class SettingsScene(Scene):
    ITEMS = (("Volumen general", "VOL_MASTER"), ("Musica", "VOL_MUSIC"), ("Efectos", "VOL_SFX"))
    SQUARES = 10

    def __init__(self, app):
        self.app = app
        self.i = 0

    def handle_event(self, e):
        if e.type != pygame.KEYDOWN:
            return
        key = self.ITEMS[self.i][1]
        if e.key == pygame.K_UP:
            self.i = (self.i - 1) % len(self.ITEMS)
        elif e.key == pygame.K_DOWN:
            self.i = (self.i + 1) % len(self.ITEMS)
        elif e.key in (pygame.K_LEFT, pygame.K_RIGHT):
            d = 1.0 / self.SQUARES * (1 if e.key == pygame.K_RIGHT else -1)
            setattr(config, key, round(min(1.0, max(0.0, getattr(config, key) + d)), 2))
            self.app.audio.play("menu")
        elif e.key in ENTER or e.key == pygame.K_ESCAPE:
            self.app.scenes.pop()

    def draw(self, screen):
        W, H = screen.get_size()
        screen.blit(self.app.background((W, H)), (0, 0))
        screen.blit(_overlay((W, H), 170), (0, 0))
        f = self.app.font(26)
        t = self.app.font(40).render("Ajustes", True, (240, 230, 200))
        screen.blit(t, t.get_rect(center=(W // 2, 90)))
        y = 190
        for k, (label, key) in enumerate(self.ITEMS):
            sel = k == self.i
            screen.blit(f.render(label, True, (255, 220, 120) if sel else (210, 210, 210)), (W // 2 - 280, y))
            filled = round(getattr(config, key) * self.SQUARES)
            for q in range(self.SQUARES):
                r = pygame.Rect(W // 2 + 20 + q * 26, y + 2, 20, 24)
                pygame.draw.rect(screen, (120, 200, 120) if q < filled else (70, 70, 80), r)
                pygame.draw.rect(screen, (230, 230, 230) if sel else (120, 120, 130), r, 1)
            y += 60
        hint = self.app.font(16).render("Flechas: elegir y ajustar   Enter / Esc: volver", True, (170, 170, 170))
        screen.blit(hint, hint.get_rect(center=(W // 2, H - 50)))


class PlaceholderScene(Scene):
    def __init__(self, app, title, subtitle):
        self.app, self.title, self.subtitle = app, title, subtitle

    def handle_event(self, e):
        if e.type == pygame.KEYDOWN and (e.key in ENTER or e.key == pygame.K_ESCAPE):
            self.app.scenes.pop()

    def draw(self, screen):
        W, H = screen.get_size()
        screen.blit(self.app.background((W, H)), (0, 0))
        screen.blit(_overlay((W, H), 170), (0, 0))
        t = self.app.font(40).render(self.title, True, (240, 230, 200))
        s = self.app.font(20).render(self.subtitle, True, (200, 200, 200))
        screen.blit(t, t.get_rect(center=(W // 2, H // 2 - 20)))
        screen.blit(s, s.get_rect(center=(W // 2, H // 2 + 30)))