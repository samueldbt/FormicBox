"""Dibuja las capas del mundo (solo los tiles visibles): terreno -> feromonas/overlays -> objetos -> fuego."""
import numpy as np
import pygame
import config
from Automata.terrain import ROCK, WATER, NEST
from Automata.objects import NONE, GRASS, BLOCK_KINDS, total_bites
from Automata.fire import BURNING, ASH
from Automata.autotile import masks

LAYER_NAMES = ("vegetal", "azucar", "alarma", "caza")


class ViewState:
    """Qué capas se muestran (las cambian teclas y botones)."""

    def __init__(self):
        self.pheromones = True
        self.layers = {n: True for n in LAYER_NAMES}
        self.gradient = False
        self.traffic = False
        self.moisture = False      # tecla H: película azul (húmedo) / amarillenta (seco)
        self.weather = True        # lluvia y rayos animados


class MapRenderer:
    def __init__(self, assets, sim, view):
        self.A = assets
        self.sim = sim
        self.view = view
        self._dense_cache = (-1, None)
        self._vrng = np.random.default_rng(7)   # solo para el dibujo de la lluvia
        self.rebuild()

    def rebuild(self):
        """Recalcula lo estático (terreno). Llamar tras reiniciar la simulación o cambiar terreno."""
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

        # 2. Feromonas y overlays
        self._draw_overlays(surf, cam, sl, x0, y0)

        # 3. Pasto (celdas sueltas)
        o = a.objects
        kind, lvl = o.matrix[sl].tolist(), o.level[sl].tolist()
        dense = self._dense_ids()[sl].tolist()
        blits = []
        for j in range(rows):
            py = (y0 + j) * T + oy
            for i in range(cols):
                if kind[j][i] != GRASS:
                    continue
                spr = dense[j][i] if lvl[j][i] >= 2 else self.A.grass1
                blits.append((sp[spr], ((x0 + i) * T + ox, py)))
        surf.blits(blits)

        # 3b. Mango y bocadillo: UNA imagen de 2x2 tiles por objeto, que cambia con las mordidas
        by0, bx0 = max(0, y0 - 1), max(0, x0 - 1)
        blits = []
        for j, i in np.argwhere(o.object_piece[by0:y1, bx0:x1] == 1).tolist():
            y, x = by0 + j, bx0 + i
            oid = int(o.object_id[y, x])
            k = o.object_kind.get(oid)
            if k is None:
                continue
            spr = self.A.block_surface(k, o.object_bites.get(oid, 1), total_bites(k))
            blits.append((spr, (x * T + ox, y * T + oy)))
        surf.blits(blits)
        
        # 3c. Botín de marabuntas caídas (placeholder 16x16 si falta el arte)
        if a.loot.items:
            blits = []
            for (ly, lx), lt in a.loot.items.items():
                if x0 <= lx < x1 and y0 <= ly < y1:
                    blits.append((self.A.loot_surface(bool(lt.brood)), (lx * T + ox, ly * T + oy)))
            surf.blits(blits)
            
        # 4. Fuego y ceniza
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

        # 5. Humedad (H), lluvia y rayos (encima de todo el mapa, debajo de las hormigas)
        self._draw_moisture(surf, cam, sl, x0, y0)
        if self.view.weather:
            self._draw_rain(surf, cam, x0, y0, x1, y1)
            self._draw_bolts(surf, cam, s)

    # ------------------------------------------------------------ clima
    def _draw_moisture(self, surf, cam, sl, x0, y0):
        """Película translúcida: azul donde hay humedad, amarillenta donde está seco. No tapa el mapa."""
        if not self.view.moisture:
            return
        m = self.sim.automaton.terrain.moisture[sl]
        self._overlay(surf, cam, 150.0 * np.power(m, 1.5), config.MOISTURE_VIEW_BLUE, x0, y0)
        dry = np.clip((config.MOISTURE_DRY_BELOW - m) / max(1e-6, config.MOISTURE_DRY_BELOW), 0.0, 1.0)
        self._overlay(surf, cam, 110.0 * dry, config.MOISTURE_VIEW_DRY, x0, y0)

    def _draw_rain(self, surf, cam, x0, y0, x1, y1):
        """Rayitas azules dentro de cada zona de lluvia (cantidad según su intensidad)."""
        T = config.TILE
        for z in self.sim.automaton.weather.zones_of("rain"):
            n = int(40 * z.intensity())
            if n <= 0:
                continue
            ang = self._vrng.uniform(0, 6.2832, n)
            rad = np.sqrt(self._vrng.uniform(0, 1, n)) * z.r
            cy = (z.y + 0.5 + rad * np.sin(ang)) * T - cam.y
            cx = (z.x + 0.5 + rad * np.cos(ang)) * T - cam.x
            for yy, xx in zip(cy.tolist(), cx.tolist()):
                pygame.draw.line(surf, (170, 205, 255), (xx, yy), (xx - 3, yy + 9), 1)

    def _draw_bolts(self, surf, cam, s):
        """Rayo: píxeles blancos revelados de arriba hacia abajo (orden de caída) que se apagan con la edad."""
        T, P = config.TILE, max(1, int(config.LIGHTNING_PIXEL))
        vw, vh = surf.get_size()
        for b in self.sim.automaton.weather.bolts:
            t = b.age + s
            reveal = min(1.0, t / 0.5)                         # cae en medio tick
            fade = 1.0 - max(0.0, t - 0.5) / max(0.25, b.life - 0.5)
            if fade <= 0:
                continue
            pts = b.pix[b.order <= reveal]
            col = (255, 255, 255) if fade > 0.4 else (190, 210, 255)
            for py, px in pts.tolist():
                sx, sy = px - cam.x, py - cam.y
                if 0 <= sx < vw and 0 <= sy < vh:
                    surf.fill(col, (sx, sy, P, P))
            if reveal >= 1.0:                                  # destello en el impacto
                glow = pygame.Surface((2 * T, 2 * T), pygame.SRCALPHA)
                pygame.draw.circle(glow, (255, 255, 255, int(150 * fade)), (T, T), T)
                surf.blit(glow, (b.x * T + T // 2 - T - cam.x, b.y * T + T // 2 - T - cam.y))

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