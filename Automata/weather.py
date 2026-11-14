"""Clima (Fase 6): lluvia, sequía y rayos.

- Lluvia / sequía: ZONAS temporales con borde suave que suben/bajan la humedad poco a poco.
  La humedad vuelve sola a su valor base (MOISTURE_RECOVERY), así que el efecto se desvanece.
- Rayo: un autómata celular temporal a escala de píxel. Un tronco cae por la cuadrícula hasta la celda
  objetivo y se bifurca proceduralmente; cada píxel guarda su "orden" de caída para que el dibujo lo revele
  de arriba hacia abajo. El impacto (ignición / muerte) ocurre en el tick en que cae.
"""
import math
import random
import numpy as np
import config
from .terrain import DIRT, NEST, WATER
from .objects import GRASS, MANGO
from .fire import NO_FIRE, BURNING


class Zone:
    """Zona de lluvia o sequía: centro, radio, duración y pesos por celda (1 al centro, 0 al borde)."""
    __slots__ = ("kind", "y", "x", "r", "ticks", "age", "weight")

    def __init__(self, kind, y, x, r, ticks, shape):
        self.kind, self.y, self.x, self.r = kind, y, x, r
        self.ticks, self.age = ticks, 0
        yy, xx = np.ogrid[:shape[0], :shape[1]]
        d2 = ((yy - y) ** 2 + (xx - x) ** 2) / float(max(1, r * r))
        self.weight = np.clip(1.0 - d2, 0.0, 1.0).astype(np.float32)

    def intensity(self):
        """Sube al principio, baja al final (0..1)."""
        ramp = max(1, config.WEATHER_RAMP_TICKS)
        return float(max(0.0, min(1.0, (self.age + 1) / ramp, (self.ticks - self.age) / ramp)))


class Bolt:
    """Un rayo ya generado. pix: (N, 2) int32 con (py, px) de MUNDO en píxeles; order: (N,) 0 = arriba, 1 = impacto."""

    def __init__(self, y, x, pix, order, life):
        self.y, self.x = y, x
        self.pix, self.order = pix, order
        self.life = life
        self.age = 0


def make_bolt(y, x, rng):
    """Genera el rayo que cae sobre la celda (y, x). `rng` = random.Random (no toca el azar de las hormigas)."""
    T = config.TILE
    ty, tx = y * T + T // 2, x * T + T // 2
    H = max(T, int(config.LIGHTNING_HEIGHT_CELLS * T))
    top = ty - H
    pix = {(ty, tx)}

    # Tronco: de abajo (impacto) hacia arriba, con desvío lateral acotado
    px, trunk = tx, [(ty, tx)]
    for i in range(1, H + 1):
        py = ty - i
        r = rng.random()
        if r < config.LIGHTNING_WANDER:
            step = -1 if rng.random() < 0.5 else 1
            if abs(px + step - tx) <= config.LIGHTNING_MAX_DRIFT:
                px += step
        pix.add((py, px))
        trunk.append((py, px))

    # Ramas: salen del tronco hacia los lados y hacia abajo (sub-ramas con menos probabilidad)
    def branch(py, px, depth):
        d = -1 if rng.random() < 0.5 else 1
        length = rng.randint(8, 40 if depth == 0 else 18)
        for _ in range(length):
            if rng.random() < 0.65:
                px += d
            if rng.random() < 0.75:
                py += 1
            if py >= ty:
                break
            pix.add((py, px))
            if depth == 0 and rng.random() < config.LIGHTNING_BRANCH_PROB * 0.6:
                branch(py, px, 1)

    for (py, px_) in trunk[8:-4]:
        if rng.random() < config.LIGHTNING_BRANCH_PROB:
            branch(py, px_, 0)

    arr = np.array(sorted(pix), dtype=np.int32)
    order = ((arr[:, 0] - top) / float(max(1, ty - top))).clip(0.0, 1.0).astype(np.float32)
    return Bolt(y, x, arr, order, int(config.LIGHTNING_FLASH_TICKS))


class Weather:
    def __init__(self, automaton, seed=None):
        self.a = automaton
        self.rng = random.Random(seed)             # forma de los rayos y clima automático (reproducible)
        self.zones = []
        self.bolts = []
        self.strikes = []                          # impactos del tick (y, x): Simulation los consume para matar entes

    # ------------------------------------------------------------ consultas
    def zones_of(self, kind):
        return [z for z in self.zones if z.kind == kind]

    def rain_intensity(self):
        """Mapa (h, w) 0..1 de lluvia actual (para dibujo y para dirigir los rayos)."""
        a = self.a
        out = np.zeros((a.height, a.width), dtype=np.float32)
        for z in self.zones_of("rain"):
            out = np.maximum(out, z.weight * z.intensity())
        return out

    def is_raining(self):
        return any(z.kind == "rain" for z in self.zones)

    # ------------------------------------------------------------ poderes
    def _zone(self, kind, y, x, radius, ticks):
        a = self.a
        y = int(np.clip(y, 0, a.height - 1))
        x = int(np.clip(x, 0, a.width - 1))
        z = Zone(kind, y, x, int(radius), int(ticks), (a.height, a.width))
        self.zones.append(z)
        return z

    def rain(self, y, x, radius=None, ticks=None):
        return self._zone("rain", y, x, radius or config.RAIN_RADIUS, ticks or config.RAIN_TICKS)

    def drought(self, y, x, radius=None, ticks=None):
        return self._zone("drought", y, x, radius or config.DROUGHT_RADIUS, ticks or config.DROUGHT_TICKS)

    def strike(self, y, x, sure=True):
        """Cae un rayo en (y, x). Prende si hay pasto o mango; con sure=False la humedad lo puede impedir.
        Devuelve True si prendió fuego. Registra el impacto para que Simulation mate a quien esté ahí."""
        a = self.a
        if not (0 <= y < a.height and 0 <= x < a.width):
            return False
        self.bolts.append(make_bolt(y, x, self.rng))
        self.strikes.append((y, x))
        a.emit("thunder", y, x)
        combustible = a.objects.matrix[y, x] in (GRASS, MANGO)
        if not (a.terrain.matrix[y, x] == DIRT and combustible and a.fire.matrix[y, x] == NO_FIRE):
            return False
        if not sure and config.LIGHTNING_IGNITE_MOISTURE_C > 0:
            if self.rng.random() > math.exp(-config.LIGHTNING_IGNITE_MOISTURE_C * float(a.terrain.moisture[y, x])):
                return False
        a.fire.matrix[y, x] = BURNING
        a.fire.age[y, x] = 0
        return True

    # ------------------------------------------------------------ un tick
    def update(self):
        a = self.a
        m = a.terrain.moisture

        # La humedad regresa lentamente a su valor base
        m += config.MOISTURE_RECOVERY * (a.base_moisture - m)

        for z in self.zones:
            i = z.intensity()
            if z.kind == "rain":
                m += config.RAIN_RATE * i * z.weight
                burning = a.fire.matrix == BURNING
                if burning.any():
                    p = config.RAIN_EXTINGUISH_PROB * i * z.weight
                    out = burning & (a.fire.rng.random(m.shape) < p)
                    a.fire.matrix[out] = NO_FIRE
                    a.fire.age[out] = 0
            else:
                m -= config.DROUGHT_RATE * i * z.weight
            z.age += 1
        self.zones = [z for z in self.zones if z.age < z.ticks]
        np.clip(m, 0.0, 1.0, out=m)
        m[a.terrain.matrix == WATER] = 1.0

        for b in self.bolts:
            b.age += 1
        self.bolts = [b for b in self.bolts if b.age < b.life]

        if config.WEATHER_AUTO:
            self._auto()

    def _random_dirt(self):
        ys, xs = np.nonzero(self.a.terrain.matrix == DIRT)
        if len(ys) == 0:
            return None
        i = self.rng.randrange(len(ys))
        return int(ys[i]), int(xs[i])

    def _auto(self):
        """Clima espontáneo (solo con WEATHER_AUTO): lluvia, sequía y rayos; la lluvia atrae y multiplica los rayos."""
        r = self.rng.random
        if r() < config.RAIN_AUTO_PROB:
            c = self._random_dirt()
            if c:
                self.rain(*c)
        if r() < config.DROUGHT_AUTO_PROB:
            c = self._random_dirt()
            if c:
                self.drought(*c)
        raining = self.is_raining()
        p = config.LIGHTNING_BASE_PROB * (config.LIGHTNING_RAIN_MULT if raining else 1.0)
        if r() < p:
            if raining:
                z = self.rng.choice(self.zones_of("rain"))
                dy = int(round(self.rng.uniform(-z.r, z.r) * 0.7))
                dx = int(round(self.rng.uniform(-z.r, z.r) * 0.7))
                c = (z.y + dy, z.x + dx)
            else:
                c = self._random_dirt()
            if c:
                self.strike(c[0], c[1], sure=False)
