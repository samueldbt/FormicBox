"""Kit de interfaz: paneles translúcidos con esquinas redondeadas, iconos pixel art (propios o placeholder),
botones, barras, notificaciones y ventanas modales. Colores, opacidad y tamaños salen de config.py (UI_*)."""
import pygame
import config
from . import manifest

_PANELS, _ICONS = {}, {}


# ------------------------------------------------------------ dibujo básico
def draw_panel(surf, rect, color=None, alpha=None, radius=None, border=True):
    rect = pygame.Rect(rect)
    color = color or config.UI_PANEL_COLOR
    alpha = config.UI_PANEL_ALPHA if alpha is None else alpha
    r = config.UI_RADIUS if radius is None else radius
    key = (rect.w, rect.h, tuple(color), alpha, r, border)
    img = _PANELS.get(key)
    if img is None:
        if len(_PANELS) > 80:
            _PANELS.clear()
        img = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(img, (*color, alpha), img.get_rect(), border_radius=r)
        if border:
            pygame.draw.rect(img, (*config.UI_BORDER_COLOR, min(255, alpha + 60)), img.get_rect(), 2, border_radius=r)
        _PANELS[key] = img
    surf.blit(img, rect.topleft)


def draw_text(surf, font, text, pos, color=None, anchor="topleft"):
    img = font.render(str(text), True, color or config.UI_TEXT_COLOR)
    r = img.get_rect(**{anchor: pos})
    surf.blit(img, r)
    return r


def draw_bar(surf, rect, frac, color, back=(40, 42, 52)):
    rect = pygame.Rect(rect)
    pygame.draw.rect(surf, back, rect, border_radius=3)
    w = int(rect.w * max(0.0, min(1.0, frac)))
    if w > 0:
        pygame.draw.rect(surf, color, (rect.x, rect.y, w, rect.h), border_radius=3)


def draw_lines(surf, font, topleft, width, lines, alpha=None):
    """Panel con líneas de inspector (ver inspector.py). Devuelve su Rect."""
    pad, h = 10, 8
    for ln in lines:
        h += {"title": 24, "gap": 8}.get(ln[0], 18)
    rect = pygame.Rect(topleft[0], topleft[1], width, h + pad)
    draw_panel(surf, rect, alpha=alpha)
    y = rect.y + 8
    for ln in lines:
        kind = ln[0]
        if kind == "title":
            draw_text(surf, font, ln[1], (rect.x + pad, y), ln[2])
            y += 24
        elif kind == "text":
            draw_text(surf, font, ln[1], (rect.x + pad, y), ln[2])
            y += 18
        elif kind == "kv":
            draw_text(surf, font, ln[1], (rect.x + pad, y), config.UI_DIM_COLOR)
            draw_text(surf, font, ln[2], (rect.right - pad, y), ln[3], "topright")
            y += 18
        elif kind == "bar":
            draw_text(surf, font, ln[1], (rect.x + pad, y), config.UI_DIM_COLOR)
            draw_bar(surf, (rect.x + pad + 72, y + 4, width - 2 * pad - 72 - 64, 9), ln[2], ln[3])
            draw_text(surf, font, ln[4], (rect.right - pad, y), config.UI_TEXT_COLOR, "topright")
            y += 18
        else:
            y += 8
    return rect


# ------------------------------------------------------------ iconos (16x16 pixel art, escalados sin suavizar)
def _R(s, c, x, y, w, h):
    pygame.draw.rect(s, c, (x, y, w, h))


def _ant(s, c, big=False):
    for cx, cy, r in ((8, 3, 2), (8, 7, 2), (8, 12, 3)):
        pygame.draw.circle(s, c, (cx, cy), r)
    for y0, y1 in ((6, 3), (8, 8), (10, 13)):
        pygame.draw.line(s, c, (8, y0 + 1), (2, y1), 1)
        pygame.draw.line(s, c, (8, y0 + 1), (14, y1), 1)
    if big:
        pygame.draw.line(s, c, (6, 2), (4, 0), 1)
        pygame.draw.line(s, c, (10, 2), (12, 0), 1)


def _gear(s, c):
    pygame.draw.circle(s, c, (8, 8), 6)
    pygame.draw.circle(s, (0, 0, 0, 0), (8, 8), 3)
    for r in ((7, 0, 2, 3), (7, 13, 2, 3), (0, 7, 3, 2), (13, 7, 3, 2)):
        _R(s, c, *r)


def _restart(s, c):
    pygame.draw.circle(s, c, (8, 9), 6, 2)
    _R(s, (0, 0, 0, 0), 8, 0, 8, 7)
    pygame.draw.polygon(s, c, [(7, 0), (7, 7), (13, 3)])


def _seed(s, c):
    pygame.draw.ellipse(s, c, (4, 7, 8, 9))
    _R(s, c, 7, 2, 2, 5)
    pygame.draw.polygon(s, c, [(9, 3), (14, 1), (11, 6)])


def _water(s, c):
    col = (90, 160, 255)
    for y in (4, 8, 12):
        pygame.draw.lines(s, col, False, [(1, y), (4, y - 2), (8, y), (12, y - 2), (15, y)], 2)


def _rain(s, c):
    for cx, cy, r in ((5, 6, 3), (9, 5, 4), (12, 7, 3)):
        pygame.draw.circle(s, (190, 200, 215), (cx, cy), r)
    for x in (4, 8, 12):
        pygame.draw.line(s, (90, 160, 255), (x, 11), (x - 1, 15), 1)


def _sun(s, c):
    pygame.draw.circle(s, (255, 205, 60), (8, 8), 4)
    for a, b in (((8, 0), (8, 2)), ((8, 14), (8, 16)), ((0, 8), (2, 8)), ((14, 8), (16, 8)),
                 ((2, 2), (4, 4)), ((12, 12), (14, 14)), ((12, 4), (14, 2)), ((2, 14), (4, 12))):
        pygame.draw.line(s, (255, 205, 60), a, b, 1)


def _fire(s, c):
    pygame.draw.polygon(s, (240, 90, 20), [(8, 0), (13, 7), (12, 14), (8, 16), (4, 14), (3, 8), (6, 6)])
    pygame.draw.polygon(s, (255, 210, 60), [(8, 7), (11, 11), (10, 15), (6, 15), (5, 11)])


def _swarm(s, c):
    for x, y in ((3, 3), (8, 2), (12, 4), (5, 8), (10, 9), (3, 13), (8, 13), (13, 13)):
        _R(s, (170, 100, 235), x, y, 2, 2)


_DRAW = {
    "gear": _gear,
    "play": lambda s, c: pygame.draw.polygon(s, c, [(4, 2), (4, 14), (14, 8)]),
    "pause": lambda s, c: (_R(s, c, 4, 3, 3, 10), _R(s, c, 10, 3, 3, 10)),
    "step": lambda s, c: (pygame.draw.polygon(s, c, [(2, 3), (2, 13), (10, 8)]), _R(s, c, 11, 3, 3, 10)),
    "restart": _restart,
    "seed": _seed,
    "edit": lambda s, c: (pygame.draw.line(s, c, (3, 13), (12, 4), 3), pygame.draw.polygon(s, c, [(2, 14), (3, 10), (6, 13)])),
    "entities": lambda s, c: _ant(s, c),
    "events": lambda s, c: pygame.draw.polygon(s, c, [(9, 0), (3, 9), (7, 9), (5, 16), (13, 6), (9, 6)]),
    "stats": lambda s, c: (_R(s, c, 2, 9, 3, 5), _R(s, c, 6, 5, 3, 9), _R(s, c, 10, 2, 3, 12)),
    "ok": lambda s, c: pygame.draw.lines(s, c, False, [(3, 8), (6, 12), (13, 3)], 3),
    "close": lambda s, c: (pygame.draw.line(s, c, (3, 3), (13, 13), 3), pygame.draw.line(s, c, (13, 3), (3, 13), 3)),
    "back": lambda s, c: pygame.draw.polygon(s, c, [(1, 8), (8, 2), (8, 6), (15, 6), (15, 10), (8, 10), (8, 14)]),
    "grass": lambda s, c: [pygame.draw.line(s, (60, 200, 60), a, b, 2) for a, b in (((4, 15), (3, 6)), ((8, 15), (8, 2)), ((12, 15), (13, 6)))],
    "water": _water,
    "rock": lambda s, c: pygame.draw.polygon(s, (150, 150, 155), [(1, 14), (3, 6), (8, 2), (13, 5), (15, 14)]),
    "erase": lambda s, c: (pygame.draw.polygon(s, (230, 200, 170), [(1, 9), (8, 2), (15, 8), (8, 15)]), pygame.draw.line(s, (120, 90, 70), (4, 12), (12, 5), 1)),
    "bocadillo": lambda s, c: (_R(s, (170, 25, 55), 2, 2, 12, 12), _R(s, (230, 90, 110), 4, 4, 4, 2)),
    "mango": lambda s, c: (pygame.draw.ellipse(s, (255, 190, 20), (2, 4, 12, 11)), pygame.draw.polygon(s, (60, 180, 60), [(8, 4), (13, 1), (11, 5)])),
    "worker": lambda s, c: _ant(s, (215, 130, 70)),
    "soldier": lambda s, c: _ant(s, (235, 80, 80), True),
    "marabunta": lambda s, c: _ant(s, (170, 110, 235), True),
    "fire": _fire, "rain": _rain, "drought": _sun, "swarm": _swarm,
    "lightning": lambda s, c: pygame.draw.polygon(s, (255, 240, 120), [(9, 0), (3, 9), (7, 9), (5, 16), (13, 6), (9, 6)]),
    "eye": lambda s, c: (pygame.draw.ellipse(s, c, (1, 4, 14, 8), 2), pygame.draw.circle(s, c, (8, 8), 2)),
}


def icon(name, size=None):
    """Icono escalado a `size` sin suavizar. Si existe Assets/ui/icons/<name>.png se usa ese (cualquier tamaño)."""
    size = size or config.UI_ICON_SIZE
    key = (name, size)
    s = _ICONS.get(key)
    if s is None:
        path = manifest.ROOT / "ui" / "icons" / f"{name}.png"
        if path.is_file():
            base = pygame.image.load(str(path)).convert_alpha()
        else:
            base = pygame.Surface((16, 16), pygame.SRCALPHA)
            _DRAW.get(name, lambda s_, c: _R(s_, c, 3, 3, 10, 10))(base, (240, 240, 245))
        s = _ICONS[key] = pygame.transform.scale(base, (size, size))
    return s


# ------------------------------------------------------------ widgets
class Button:
    """icon / label: texto o nombre de icono (pueden ser funciones). tip: ayuda en la barra inferior."""

    def __init__(self, rect, cb, icon=None, label=None, tip="", active=None, enabled=None, accent=None):
        self.rect = pygame.Rect(rect)
        self.cb, self.icon, self.label, self.tip = cb, icon, label, tip
        self.active, self.enabled, self.accent = active, enabled, accent

    def is_enabled(self):
        return self.enabled() if self.enabled else True

    def draw(self, surf, font, mouse):
        r = self.rect
        en, on = self.is_enabled(), bool(self.active and self.active())
        hover = en and r.collidepoint(mouse)
        if self.accent:
            bg, alpha = self.accent, 230 if hover else 190
        elif on:
            bg, alpha = (110, 88, 30), 220
        else:
            bg, alpha = (46, 52, 74), 170 if hover else 100
        draw_panel(surf, r, bg, alpha, radius=6, border=on or hover)
        name = self.icon() if callable(self.icon) else self.icon
        text = self.label() if callable(self.label) else self.label
        col = config.UI_ACCENT if on else (config.UI_TEXT_COLOR if en else (110, 110, 120))
        isz = min(config.UI_ICON_SIZE, r.h - 10)
        ic = icon(name, isz) if name else None
        if ic is not None and not en:
            ic = ic.copy()
            ic.set_alpha(90)
        if ic and text:
            surf.blit(ic, (r.x + 8, r.centery - isz // 2))
            draw_text(surf, font, text, (r.x + 16 + isz, r.centery), col, "midleft")
        elif ic:
            surf.blit(ic, ic.get_rect(center=r.center))
        elif text:
            draw_text(surf, font, text, r.center, col, "center")

    def click(self, pos):
        if self.rect.collidepoint(pos) and self.is_enabled():
            self.cb()
            return True
        return False


class Slider:
    def __init__(self, rect, get, set_):
        self.rect, self.get, self.set, self.drag = pygame.Rect(rect), get, set_, False

    def _val(self, x):
        self.set(round(max(0.0, min(1.0, (x - self.rect.x) / max(1, self.rect.w))), 2))

    def handle(self, e):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.rect.inflate(0, 16).collidepoint(e.pos):
            self.drag = True
            self._val(e.pos[0])
            return True
        if e.type == pygame.MOUSEMOTION and self.drag:
            self._val(e.pos[0])
            return True
        if e.type == pygame.MOUSEBUTTONUP and e.button == 1 and self.drag:
            self.drag = False
            return True
        return False

    def draw(self, surf):
        draw_bar(surf, self.rect, self.get(), config.UI_OK_COLOR)
        x = self.rect.x + int(self.rect.w * self.get())
        pygame.draw.rect(surf, (235, 235, 240), (x - 4, self.rect.y - 4, 8, self.rect.h + 8), border_radius=3)


# ------------------------------------------------------------ notificaciones y barra de ayuda
class Toasts:
    """Globos informativos temporales (NOTIFY_SECONDS) en la parte baja de la pantalla."""

    def __init__(self):
        self.items = []

    def push(self, text, seconds=None, color=None):
        if self.items and self.items[-1][0] == text:
            self.items[-1][1] = seconds or config.NOTIFY_SECONDS
            return
        self.items.append([text, seconds or config.NOTIFY_SECONDS, color or config.UI_TEXT_COLOR])
        del self.items[:-3]

    def update(self, dt):
        for it in self.items:
            it[1] -= dt
        self.items = [it for it in self.items if it[1] > 0]

    def draw(self, surf, font, bottom):
        W = surf.get_width()
        y = bottom
        for text, left, color in reversed(self.items):
            img = font.render(text, True, color)
            w, h = img.get_width() + 28, img.get_height() + 14
            box = pygame.Surface((w, h), pygame.SRCALPHA)
            draw_panel(box, (0, 0, w, h), alpha=210)
            box.blit(img, (14, 7))
            box.set_alpha(int(255 * min(1.0, left / 0.6)))
            y -= h + 6
            surf.blit(box, ((W - w) // 2, y))


def draw_help(surf, font, text):
    W, H = surf.get_size()
    r = pygame.Rect(0, H - config.HELP_BAR_H, W, config.HELP_BAR_H)
    draw_panel(surf, r, alpha=140, radius=0, border=False)
    draw_text(surf, font, text, (12, r.centery), config.UI_DIM_COLOR, "midleft")
    return r


# ------------------------------------------------------------ modales
class Modal:
    closed = False

    def handle_event(self, e):
        pass

    def draw(self, screen):
        pass


def _dim(screen, alpha=150):
    shade = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    shade.fill((0, 0, 0, alpha))
    screen.blit(shade, (0, 0))


KEY_LABELS = {"space": "ESPACIO", "period": "."}
SHORTCUTS = (("pause", "Play / Pausa"), ("step", "Paso a paso (en pausa)"), ("restart", "Reiniciar"),
             ("wind_up", "Viento arriba"), ("wind_down", "Viento abajo"), ("wind_left", "Viento izquierda"),
             ("wind_right", "Viento derecha"), ("wind_zero", "Viento en calma"),
             ("layer_vegetal", "Capa vegetal"), ("layer_azucar", "Capa azucar"), ("layer_alarma", "Capa alarma"),
             ("layer_caza", "Capa caza"), ("layers_all", "Todas las capas"), ("gradient", "Gradiente"),
             ("traffic", "Trafico"), ("moisture", "Humedad"))


class SettingsModal(Modal):
    """Volúmenes, atajos y volver al título."""

    def __init__(self, app, on_close, on_title):
        self.app, self.on_close, self.on_title = app, on_close, on_title
        self.view = "main"
        self.sliders, self.buttons = [], []
        self._layout()

    def close(self):
        self.closed = True
        self.on_close()

    def _set(self, key):
        return lambda v: setattr(config, key, v)

    def _layout(self):
        W, H = self.app.screen.get_size()
        pw, ph = 480, 360 if self.view == "main" else 470
        self.rect = pygame.Rect((W - pw) // 2, (H - ph) // 2, pw, ph)
        r, self.sliders, self.buttons = self.rect, [], []
        if self.view == "main":
            for i, (label, key) in enumerate((("Volumen general", "VOL_MASTER"), ("Musica", "VOL_MUSIC"), ("Efectos", "VOL_SFX"))):
                self.sliders.append((label, Slider((r.x + 200, r.y + 84 + i * 48, 240, 10),
                                                   lambda k=key: getattr(config, k), self._set(key))))
            bw = r.w - 60
            self.buttons = [Button((r.x + 30, r.y + 230, bw, 38), lambda: self._go("keys"), "eye", "Atajos de teclado"),
                            Button((r.x + 30, r.y + 276, bw, 38), self.on_title, "back", "Volver al titulo"),
                            Button((r.right - 50, r.y + 10, 36, 36), self.close, "close", tip="Cerrar")]
        else:
            self.buttons = [Button((r.x + 30, r.bottom - 54, r.w - 60, 38), lambda: self._go("main"), "back", "Atras")]

    def _go(self, view):
        self.view = view
        self._layout()

    def handle_event(self, e):
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            self.close() if self.view == "main" else self._go("main")
            return
        for _, s in self.sliders:
            if s.handle(e):
                return
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for b in self.buttons:
                if b.click(e.pos):
                    return

    def draw(self, screen):
        _dim(screen)
        f, fb = self.app.font(16), self.app.font(26)
        draw_panel(screen, self.rect, alpha=238)
        r = self.rect
        draw_text(screen, fb, "Ajustes" if self.view == "main" else "Atajos", (r.x + 30, r.y + 18), config.UI_ACCENT)
        mouse = pygame.mouse.get_pos()
        if self.view == "main":
            for label, s in self.sliders:
                draw_text(screen, f, label, (r.x + 30, s.rect.y - 4))
                s.draw(screen)
                draw_text(screen, f, f"{int(s.get() * 100)}%", (r.right - 30, s.rect.y - 4), anchor="topright")
        else:
            y = r.y + 64
            for i, (act, label) in enumerate(SHORTCUTS):
                x = r.x + 30 + (i % 2) * 220
                yy = y + (i // 2) * 22
                key = config.KEYS.get(act, "?")
                draw_text(screen, f, KEY_LABELS.get(key, key.upper()), (x, yy), config.UI_ACCENT)
                draw_text(screen, f, label, (x + 62, yy))
            extra = ("Flechas: mover camara", "Clic en un ente: fijarlo (otra vez: soltar)",
                     "Clic derecho o Esc: soltar herramienta", "Rueda: tamano del pincel")
            for i, t in enumerate(extra):
                draw_text(screen, f, t, (r.x + 30, y + 8 * 22 + 14 + i * 22), config.UI_DIM_COLOR)
        for b in self.buttons:
            b.draw(screen, f, mouse)


class NumberModal(Modal):
    """Entrada numérica (semilla) con Aceptar / Cancelar."""

    def __init__(self, app, title, value, on_ok, on_cancel):
        self.app, self.title, self.text = app, title, str(value)
        self.on_ok, self.on_cancel = on_ok, on_cancel
        W, H = app.screen.get_size()
        self.rect = pygame.Rect((W - 400) // 2, (H - 210) // 2, 400, 210)
        r = self.rect
        self.buttons = [Button((r.x + 30, r.bottom - 60, 160, 40), self.ok, "ok", "Aceptar", accent=config.UI_OK_COLOR),
                        Button((r.right - 190, r.bottom - 60, 160, 40), self.cancel, "close", "Cancelar")]

    def ok(self):
        self.closed = True
        self.on_ok(int(self.text) if self.text else 0)

    def cancel(self):
        self.closed = True
        self.on_cancel()

    def handle_event(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.ok()
            elif e.key == pygame.K_ESCAPE:
                self.cancel()
            elif e.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif e.unicode.isdigit() and len(self.text) < 9:
                self.text += e.unicode
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for b in self.buttons:
                if b.click(e.pos):
                    return

    def draw(self, screen):
        _dim(screen)
        f, fb = self.app.font(16), self.app.font(26)
        draw_panel(screen, self.rect, alpha=238)
        r = self.rect
        draw_text(screen, fb, self.title, (r.x + 30, r.y + 18), config.UI_ACCENT)
        box = pygame.Rect(r.x + 30, r.y + 70, r.w - 60, 44)
        draw_panel(screen, box, (8, 9, 14), 230, radius=6)
        cursor = "_" if int(pygame.time.get_ticks() / 400) % 2 == 0 else " "
        draw_text(screen, fb, self.text + cursor, (box.x + 12, box.centery), anchor="midleft")
        draw_text(screen, f, "Solo digitos. Enter = aceptar, Esc = cancelar", (r.x + 30, box.bottom + 8), config.UI_DIM_COLOR)
        mouse = pygame.mouse.get_pos()
        for b in self.buttons:
            b.draw(screen, f, mouse)