import config


class Camera:
    """Desplazamiento de la vista sobre el mapa. (A futuro: aquí va el zoom.)"""

    def __init__(self, map_w, map_h):
        self.map_w, self.map_h = map_w, map_h     # en celdas
        self.view_w = self.view_h = 0             # en píxeles
        self._x = self._y = 0.0

    @property
    def x(self):
        return int(self._x)

    @property
    def y(self):
        return int(self._y)

    def set_view(self, w, h):
        self.view_w, self.view_h = w, h
        self._clamp()

    def center_on(self, cy, cx):
        T = config.TILE
        self._x = cx * T + T / 2 - self.view_w / 2
        self._y = cy * T + T / 2 - self.view_h / 2
        self._clamp()

    def update(self, keys, dt):
        import pygame
        dx = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
        dy = (keys[pygame.K_DOWN] or keys[pygame.K_s]) - (keys[pygame.K_UP] or keys[pygame.K_w])
        self._x += dx * config.CAMERA_SPEED * dt
        self._y += dy * config.CAMERA_SPEED * dt
        self._clamp()

    def _clamp(self):
        T = config.TILE
        mw, mh = self.map_w * T, self.map_h * T
        if mw <= self.view_w:
            self._x = (mw - self.view_w) / 2          # mapa más chico que la vista: centrado
        else:
            self._x = min(max(self._x, 0), mw - self.view_w)
        if mh <= self.view_h:
            self._y = (mh - self.view_h) / 2
        else:
            self._y = min(max(self._y, 0), mh - self.view_h)

    def visible_cells(self):
        """(x0, y0, x1, y1) con x1, y1 exclusivos."""
        T = config.TILE
        x0, y0 = max(0, self.x // T), max(0, self.y // T)
        x1 = min(self.map_w, (self.x + self.view_w) // T + 1)
        y1 = min(self.map_h, (self.y + self.view_h) // T + 1)
        return x0, y0, x1, y1

    def screen_to_cell(self, sx, sy):
        """Píxel de la vista -> (fila, columna), o None si cae fuera del mapa."""
        T = config.TILE
        cx, cy = (sx + self.x) // T, (sy + self.y) // T
        if 0 <= cx < self.map_w and 0 <= cy < self.map_h:
            return int(cy), int(cx)
        return None