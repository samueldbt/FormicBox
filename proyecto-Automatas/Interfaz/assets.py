"""AssetManager: carga todo UNA vez en una lista `sprites` y reparte IDs enteros.
Los nombres/archivos solo se usan aquí y en manifest.py."""
import numpy as np
import pygame
import config
from . import manifest
from .autotile import BASE_MASKS, rotl4

# facing (dy, dx) -> índice de dirección. El arte mira arriba; las demás son rotaciones horarias.
DIR_INDEX = {(-1, 0): 0, (0, 1): 1, (1, 0): 2, (0, -1): 3}

FAMILY_COLORS = {   # (relleno, borde) de los placeholders
    "water": (config.COLOR_WATER, (170, 215, 240)),
    "rock": (config.COLOR_ROCK, (55, 55, 55)),
    "grass2": ((20, 110, 20), config.COLOR_DIRT),
}
CARRY_COLORS = {1: config.COLOR_GRASS, 2: config.COLOR_MANGO, 3: config.COLOR_BOCADILLO}


def fit_to_tile(img, size=None):
    """Escala cualquier imagen al tamaño de tile SIN suavizar (conserva el pixel art)."""
    size = size or config.TILE
    if img.get_size() != (size, size):
        img = pygame.transform.scale(img, (size, size))
    return img


def expand(frames, n):
    """Estira una lista de frames a n (3 -> [0,0,1,1,2,2])."""
    return [frames[min(len(frames) - 1, k * len(frames) // n)] for k in range(n)]


class AssetManager:
    def __init__(self):
        self.T = config.TILE
        self.sprites = []          # id -> Surface
        self._warned = set()
        self.autotiles = {}        # familia -> np.array de 16 ids, indexado por máscara
        self.anim = {}             # (casta, acción, carga, dirección) -> tupla de 6 ids
        self.bocadillo = [None] * 5   # 1..4
        self.fire = []

        self._load_tiles()
        self._load_autotiles()
        self._load_fire()
        self._load_ants()

    # ------------------------------------------------------------ utilidades
    def add(self, surf):
        self.sprites.append(surf)
        return len(self.sprites) - 1

    def _read(self, rel, warn=True):
        path = manifest.ROOT / rel
        if path.is_file():
            return pygame.image.load(str(path)).convert_alpha()
        if warn and rel not in self._warned:
            self._warned.add(rel)
            print(f"[assets] falta {rel}: uso placeholder")
        return None

    def _frames(self, pattern):
        """Lista de frames de un patrón (con o sin {i}). Vacía si no hay archivos."""
        if "{i}" not in pattern:
            img = self._read(pattern)
            return [fit_to_tile(img)] if img else []
        out, i = [], manifest.FRAME_START
        while True:
            img = self._read(pattern.format(i=i), warn=False)
            if img is None:
                break
            out.append(fit_to_tile(img))
            i += 1
        if not out and pattern not in self._warned:
            self._warned.add(pattern)
            print(f"[assets] faltan frames {pattern}: uso placeholder")
        return out

    def _surf(self, alpha=True):
        return pygame.Surface((self.T, self.T), pygame.SRCALPHA if alpha else 0)

    # ------------------------------------------------------------ carga
    def _tile(self, key, placeholder):
        img = self._read(manifest.TILES[key])
        return self.add(fit_to_tile(img) if img else placeholder())

    def _load_tiles(self):
        self.dirt = self._tile("dirt", lambda: self._solid(config.COLOR_DIRT))
        self.nest = self._tile("nest", self._ph_nest)
        self.ash = self._tile("ash", lambda: self._solid(config.COLOR_ASH, 170))
        self.grass1 = self._tile("grass1", self._ph_grass1)
        self.mango = self._tile("mango", self._ph_mango)

        # Bocadillo: una imagen -> 2T x 2T -> 4 trozos de T x T
        T = self.T
        img = self._read(manifest.BOCADILLO)
        big = pygame.transform.scale(img, (2 * T, 2 * T)) if img else self._ph_bocadillo()
        for i, (dy, dx) in enumerate(((0, 0), (0, 1), (1, 0), (1, 1)), start=1):
            self.bocadillo[i] = self.add(big.subsurface((dx * T, dy * T, T, T)).copy())

    def _load_autotiles(self):
        for fam, pattern in manifest.AUTOTILE.items():
            base, missing = {}, []
            for shape in BASE_MASKS:
                img = self._read(pattern.format(shape=shape), warn=False)
                if img is None:
                    missing.append(shape)
                    base[shape] = self._ph_autotile(fam, shape)
                else:
                    base[shape] = fit_to_tile(img)
            if missing:
                print(f"[assets] {fam}: faltan formas {missing}: uso placeholder")

            table = [None] * 16
            for shape, bmask in BASE_MASKS.items():
                for r in range(4):
                    m = rotl4(bmask, r)
                    if table[m] is None:
                        surf = base[shape] if r == 0 else pygame.transform.rotate(base[shape], -90 * r)
                        table[m] = self.add(surf)
            for (f, m), rel in manifest.AUTOTILE_OVERRIDES.items():
                img = self._read(rel) if f == fam else None
                if img:
                    table[m] = self.add(fit_to_tile(img))
            assert all(t is not None for t in table), f"autotile {fam}: máscaras sin llenar"
            self.autotiles[fam] = np.array(table, dtype=np.int32)

    def _load_fire(self):
        frames = self._frames(manifest.FIRE) or [self._ph_fire(k) for k in range(config.ANIM_FRAMES)]
        self.fire = [self.add(f) for f in expand(frames, config.ANIM_FRAMES)]

    def _load_ants(self):
        n = config.ANIM_FRAMES
        for caste, spec in manifest.ANTS.items():
            for (action, carry), pattern in spec.items():
                frames = self._frames(pattern)
                if not frames:
                    count = 1 if action.startswith("DEAD") else n
                    frames = [self._ph_ant(caste, action, carry, k) for k in range(count)]
                frames = expand(frames, n)
                for d in range(4):                       # 0 arriba, 1 derecha, 2 abajo, 3 izquierda
                    ids, seq = {}, []
                    for f in frames:
                        if id(f) not in ids:
                            ids[id(f)] = self.add(pygame.transform.rotate(f, -90 * d) if d else f)
                        seq.append(ids[id(f)])
                    self.anim[(caste, action, carry, d)] = tuple(seq)

    # ------------------------------------------------------------ placeholders
    def _solid(self, color, alpha=255):
        s = self._surf()
        s.fill((*color, alpha))
        return s

    def _ph_nest(self):
        s = self._solid(config.COLOR_DIRT)
        pygame.draw.circle(s, config.COLOR_NEST, (self.T // 2, self.T // 2), self.T // 2 - 2)
        pygame.draw.circle(s, (40, 20, 5), (self.T // 2, self.T // 2), self.T // 4)
        return s

    def _ph_grass1(self):
        s = self._surf()
        for x, y in ((6, 10), (14, 20), (22, 8), (10, 26), (26, 22), (18, 14)):
            pygame.draw.line(s, config.COLOR_GRASS, (x, y), (x - 2, y - 6), 2)
            pygame.draw.line(s, config.COLOR_GRASS, (x, y), (x + 2, y - 6), 2)
        return s

    def _ph_mango(self):
        s = self._surf()
        c = self.T // 2
        pygame.draw.circle(s, config.COLOR_MANGO, (c, c + 2), 9)
        pygame.draw.ellipse(s, config.COLOR_GRASS, (c, c - 12, 8, 5))
        return s

    def _ph_bocadillo(self):
        T = self.T
        s = pygame.Surface((2 * T, 2 * T), pygame.SRCALPHA)
        pygame.draw.rect(s, config.COLOR_BOCADILLO, (6, 6, 2 * T - 12, 2 * T - 12), border_radius=8)
        pygame.draw.rect(s, (255, 255, 255), (6, 6, 2 * T - 12, 2 * T - 12), 2, border_radius=8)
        return s

    def _ph_fire(self, k):
        T = self.T
        s = self._surf()
        for i in range(3):
            x = 8 + 8 * i
            h = 12 + ((k + 2 * i) % 3) * 5
            pygame.draw.polygon(s, config.COLOR_FIRE, [(x - 6, T - 2), (x, T - 2 - h), (x + 6, T - 2)])
            pygame.draw.polygon(s, (255, 200, 40), [(x - 3, T - 2), (x, T - 2 - h // 2), (x + 3, T - 2)])
        return s

    def _ph_autotile(self, fam, shape):
        fill, border = FAMILY_COLORS[fam]
        T, b = self.T, 5
        s = self._surf()
        s.fill((*fill, 255))
        sides = {"interior": "", "edge": "N", "corridor": "NS", "corner": "NE",
                 "peninsula": "NES", "island": "NESW"}[shape]
        rects = {"N": (0, 0, T, b), "E": (T - b, 0, b, T), "S": (0, T - b, T, b), "W": (0, 0, b, T)}
        for side in sides:
            pygame.draw.rect(s, border, rects[side])
        return s

    def _ph_ant(self, caste, action, carry, k):
        T = self.T
        c = T // 2
        s = self._surf()
        hw, hh = {"WORKER": (5, 8), "SOLDIER": (7, 10), "MARABUNTA": (5, 9)}[caste]
        col = config.COLORS_CASTE[caste]
        if action == "DEAD_FIGHT":
            col = (120, 120, 120)
        elif action == "DEAD_FIRE":
            col = (35, 35, 35)
        off = 2 if k % 2 == 0 else -2          # las patas alternan por frame
        for dy in (-5, 0, 5):
            pygame.draw.line(s, col, (c - hw, c + dy), (c - hw - 5, c + dy + off), 2)
            pygame.draw.line(s, col, (c + hw, c + dy), (c + hw + 5, c + dy - off), 2)
        pygame.draw.ellipse(s, col, (c - hw, c - hh + 3, 2 * hw, 2 * hh))
        pygame.draw.circle(s, col, (c, c - hh + 1), 4)             # cabeza = hacia dónde mira
        pygame.draw.circle(s, (255, 255, 255), (c, c - hh), 1)
        if action == "ATTACK":
            ln = 3 + (k % 2) * 3
            pygame.draw.line(s, (255, 240, 120), (c - 3, c - hh - 2), (c - 6, c - hh - 2 - ln), 2)
            pygame.draw.line(s, (255, 240, 120), (c + 3, c - hh - 2), (c + 6, c - hh - 2 - ln), 2)
        if action.startswith("DEAD"):
            pygame.draw.line(s, (255, 255, 255), (c - 5, c - 4), (c + 5, c + 8), 2)
            pygame.draw.line(s, (255, 255, 255), (c + 5, c - 4), (c - 5, c + 8), 2)
        if carry:
            pygame.draw.circle(s, CARRY_COLORS[carry], (c, c - hh - 4), 3)
        return s