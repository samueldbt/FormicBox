"""Colores, fuentes y una escena de menú genérica (solo teclado)."""
import pygame
from pathlib import Path
from .base import Scene

BG = (18, 16, 14)
FG = (230, 225, 215)
DIM = (140, 135, 125)
ACCENT = (240, 180, 60)
TITLE = (150, 190, 255)
BAR_BG = (60, 56, 50)

LOGO_PATH = Path(__file__).resolve().parent.parent / "Assets" / "ui" / "logo.png"
_FONT_NAMES = "consolas,dejavusansmono,couriernew,monospace"
_fonts = {}


def font(size, bold=False):
    key = (size, bold)
    if key not in _fonts:
        _fonts[key] = pygame.font.SysFont(_FONT_NAMES, size, bold=bold)
    return _fonts[key]


def text(surface, msg, size, color, center=None, topleft=None, bold=False):
    img = font(size, bold).render(msg, True, color)
    rect = img.get_rect(center=center) if center else img.get_rect(topleft=topleft or (0, 0))
    surface.blit(img, rect)
    return rect


def load_logo():
    """Logo desde Assets/ui/logo.png; si no existe, None (las escenas dibujan el nombre)."""
    try:
        if LOGO_PATH.is_file():
            return pygame.image.load(str(LOGO_PATH)).convert_alpha()
    except pygame.error as e:
        print(f"[escenas] no se pudo cargar el logo: {e}")
    return None


def draw_logo(surface, logo, center, max_w, max_h):
    if logo is None:
        text(surface, "FormicBox", 72, ACCENT, center=center, bold=True)
        return
    w, h = logo.get_size()
    k = min(max_w / w, max_h / h, 1.0) if w and h else 1.0
    img = logo if k == 1.0 else pygame.transform.smoothscale(logo, (int(w * k), int(h * k)))
    surface.blit(img, img.get_rect(center=center))


def is_up(e):
    return e.key in (pygame.K_UP, pygame.K_w)


def is_down(e):
    return e.key in (pygame.K_DOWN, pygame.K_s)


def is_enter(e):
    return e.key in (pygame.K_RETURN, pygame.K_KP_ENTER)


class MenuScene(Scene):
    """Lista vertical: flechas arriba/abajo para moverse, Enter para elegir, Esc para volver.

    items: lista de (texto o función que devuelve texto, acción sin argumentos).
    """
    title = ""
    top = 0.45          # dónde empieza la lista (fracción de la altura)
    spacing = 46

    def __init__(self):
        super().__init__()
        self.items = []
        self.index = 0

    def label(self, i):
        lab = self.items[i][0]
        return lab() if callable(lab) else lab

    def back(self):
        self.manager.pop()

    def handle_event(self, e):
        if e.type != pygame.KEYDOWN or not self.items:
            return
        if is_up(e):
            self.index = (self.index - 1) % len(self.items)
        elif is_down(e):
            self.index = (self.index + 1) % len(self.items)
        elif is_enter(e):
            self.items[self.index][1]()
        elif e.key == pygame.K_ESCAPE:
            self.back()
        else:
            self.on_key(e)

    def on_key(self, e):
        """Teclas extra (izquierda/derecha en ajustes, etc.)."""

    def draw_header(self, surface):
        if self.title:
            text(surface, self.title, 44, TITLE, center=(surface.get_width() // 2, int(surface.get_height() * 0.18)), bold=True)

    def draw_item(self, surface, i, center, selected):
        color = ACCENT if selected else FG
        msg = self.label(i)
        text(surface, f"> {msg} <" if selected else msg, 30, color, center=center, bold=selected)

    def draw_footer(self, surface):
        text(surface, "Flechas: mover   Enter: elegir   Esc: volver", 16, DIM,
             center=(surface.get_width() // 2, surface.get_height() - 24))

    def draw(self, surface):
        surface.fill(BG)
        self.draw_header(surface)
        cx = surface.get_width() // 2
        y0 = int(surface.get_height() * self.top)
        for i in range(len(self.items)):
            self.draw_item(surface, i, (cx, y0 + i * self.spacing), i == self.index)
        self.draw_footer(surface)
