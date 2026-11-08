"""Dibuja las capas del mundo (solo los tiles visibles): terreno -> feromonas/overlays -> objetos -> fuego."""
import numpy as np
import pygame
import config
from Automata.terrain import ROCK, WATER, NEST
from Automata.objects import NONE, GRASS, MANGO
from Automata.fire import BURNING, ASH
from .autotile import masks

LAYER_NAMES = ("vegetal", "azucar", "alarma", "caza")


class ViewState:
    """Qué capas se muestran (las cambian teclas y botones)."""

    def __init__(self):
        self.pheromones = True
        self.layers = {n: True for n in LAYER_NAMES}
        self.gradient = False
        self.traffic = False


class MapRenderer:
    def __init__(self, assets, sim, view):
        self.A = assets
        self.sim = sim
        self.view = view
        self._dense_cache = (-1, None)
        self.rebuild()

    def rebuild(self):
        """Recalcula lo estático (terreno). Llamar tras reiniciar la simulación."""
        A = self.A
        t = self.sim.automaton.terrain.matrix
        self.base = np.full(t.shape, A.dirt, dtype=np.int32)
        self.base[t == NEST] = A.nest
        self.over = np.full(t.shape, -1, dtype=np.int32)
        for kind, fam in ((ROCK, "rock"), (WATER, "water")):
            sel = t == kind
            self.over[sel] = A.autotiles[fam][masks(sel)[sel]]
        self.phase = np.random.default_rng(0).integers(0, config.ANIM_FRAMES, size=t.shape)
        self._dense_cache = (-1, None)

    def _dense_ids(self):
        """IDs de autotile del pasto tupido, recalculados solo cuando cambia el mundo."""
        if self._dense_cache[0] != self.sim.version:
            o = self.sim.automaton.objects
            dense = (o.matrix == GRASS) & (o.level >= 2)
            self._dense_cache = (self.sim.version, self.A.autotiles["grass2"][masks(dense)])
        return self._dense_cache[1]

    def draw(self, surf, cam, s):
        T = config.TILE
        sp = self.A.sprites
        a = self.sim.automaton
        x0, y0, x1, y1 = cam.visible_cells()
        if x1 <= x0 or y1 <= y0:
            return
        ox, oy = -cam.x, -cam.y
        sl = (slice(y0, y1), slice(x0, x1))
        rows, cols = y1 - y0, x1 - x0

        # 1. Terreno
        base, over = self.base[sl].tolist(), self.over[sl].tolist()
        blits = []
        for j in range(rows):
            py = (y0 + j) * T + oy
            for i in range(cols):
                px = (x0 + i) * T + ox
                blits.append((sp[base[j][i]], (px, py)))
                if over[j][i] >= 0:
                    blits.append((sp[over[j][i]], (px, py)))
        surf.blits(blits)

        # 2. Feromonas y overlays (encima de la tierra, debajo de objetos y hormigas)
        self._draw_overlays(surf, cam, sl, x0, y0)

        # 3. Objetos
        o = a.objects
        kind, lvl = o.matrix[sl].tolist(), o.level[sl].tolist()
        piece, dense = o.bocadillo_piece[sl].tolist(), self._dense_ids()[sl].tolist()
        blits = []
        for j in range(rows):
            py = (y0 + j) * T + oy
            for i in range(cols):
                k = kind[j][i]
                if k == NONE:
                    continue
                if k == GRASS:
                    spr = dense[j][i] if lvl[j][i] >= 2 else self.A.grass1
                elif k == MANGO:
                    spr = self.A.mango
                else:
                    spr = self.A.bocadillo[piece[j][i]]
                blits.append((sp[spr], ((x0 + i) * T + ox, py)))
        surf.blits(blits)

        # 4. Fuego y ceniza (cada llama con su fase para que no latan todas a la vez)
        frame = min(config.ANIM_FRAMES - 1, int(s * config.ANIM_FRAMES))
        fire, phase = a.fire.matrix[sl].tolist(), self.phase[sl].tolist()
        blits = []
        for j in range(rows):
            py = (y0 + j) * T + oy
            for i in range(cols):
                f = fire[j][i]
                if f == 0:
                    continue
                spr = self.A.fire[(frame + phase[j][i]) % config.ANIM_FRAMES] if f == BURNING else self.A.ash
                blits.append((sp[spr], ((x0 + i) * T + ox, py)))
        surf.blits(blits)

    # ------------------------------------------------------------ overlays
    def _draw_overlays(self, surf, cam, sl, x0, y0):
        v, a = self.view, self.sim.automaton
        if v.pheromones:
            for name, (color, scale, k) in config.PHEROMONE_VIEW.items():
                if v.layers[name]:
                    t = a.pheromones[name].matrix[sl]
                    alpha = 255.0 * config.PHEROMONE_VIEW_INTENSITY * scale * t / (t + k)
                    self._overlay(surf, cam, alpha, color, x0, y0)
        if v.gradient:
            self._overlay(surf, cam, a.home_field[sl] * 140.0, config.GRADIENT_COLOR, x0, y0)
        if v.traffic:
            tr = self.sim.traffic
            self._overlay(surf, cam, tr[sl] / max(1.0, float(tr.max())) * 200.0, config.TRAFFIC_COLOR, x0, y0)

    def _overlay(self, surf, cam, alpha, color, x0, y0):
        """Pinta una matriz de alfa (0-255) con un color: 1 píxel por celda, escalado a TILE."""
        alpha = np.clip(alpha, 0, 255).astype(np.uint8)
        if not alpha.any():
            return
        h, w = alpha.shape
        small = pygame.Surface((w, h), pygame.SRCALPHA)
        small.fill((*color, 0))
        pa = pygame.surfarray.pixels_alpha(small)
        pa[:] = alpha.T
        del pa
        size = (w * config.TILE, h * config.TILE)
        big = pygame.transform.smoothscale(small, size) if config.PHEROMONE_SMOOTH else pygame.transform.scale(small, size)
        surf.blit(big, (x0 * config.TILE - cam.x, y0 * config.TILE - cam.y))