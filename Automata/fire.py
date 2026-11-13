import math
import numpy as np
import config
from .grid import Grid
from .terrain import DIRT, ROCK, WATER, NEST
from .objects import GRASS, MANGO, BOCADILLO

# Fire States
NO_FIRE, BURNING, ASH = 0, 1, -1


class FireLayer(Grid):
    def __init__(self, width, height, seed=None):
        super().__init__(width, height, seed)
        self.matrix = np.zeros((height, width), dtype=np.int8)
        self.age = np.zeros((height, width), dtype=np.int16)

    def ignite(self, y, x, terrain_matrix, objects_matrix):
        """Start a fire in (y, x) if there is something combustible."""
        combustible = objects_matrix[y, x] in (GRASS, MANGO)
        if terrain_matrix[y, x] == DIRT and combustible and self.matrix[y, x] == NO_FIRE:
            self.matrix[y, x] = BURNING
            self.age[y, x] = 0
            return True
        return False

    def ignite_random(self, terrain_matrix, objects_matrix):
        """Ignites a random combustible DIRT cell. Returns (y, x), or None if there is none."""
        valid = ((terrain_matrix == DIRT) & ((objects_matrix == GRASS) | (objects_matrix == MANGO))
                 & (self.matrix == NO_FIRE))
        ys, xs = np.nonzero(valid)
        if len(ys) == 0:
            return None
        i = int(self.rng.integers(len(ys)))
        y, x = int(ys[i]), int(xs[i])
        self.ignite(y, x, terrain_matrix, objects_matrix)
        return y, x

    def update_fire(self, terrain_matrix, objects_matrix, moisture=None):
        """Propagación probabilística (vecindad de Moore).

        - Viento: la probabilidad de cada dirección se multiplica por exp(FIRE_WIND_C * alineación con el viento);
          además, con viento el fuego puede saltar 2 celdas a favor (FIRE_JUMP_PROB).
        - Humedad: la probabilidad de que prenda una celda se multiplica por exp(-FIRE_MOISTURE_C * humedad),
          y el fuego se apaga más rápido donde hay más humedad.
        La ceniza dura ASH_TICKS y luego la celda vuelve a tierra desnuda."""
        directions = [(-1, -1), (-1, 0), (-1, 1), (0, -1),
                      (0, 1), (1, -1), (1, 0), (1, 1)]
        wx, wy = config.WIND_X, config.WIND_Y
        burning = self.matrix > 0

        not_ignited = np.ones((self.height, self.width), dtype=np.float32)
        for dy, dx in directions:
            wind_align = (wx * dx + wy * dy) / math.hypot(dy, dx)
            p_ign = min(1.0, config.FIRE_BASE_PROB * math.exp(config.FIRE_WIND_C * wind_align))
            not_ignited *= 1.0 - p_ign * self.shift_array(burning, dy, dx)

        mag = min(1.0, math.hypot(wx, wy))
        if mag > 0 and config.FIRE_JUMP_PROB > 0:
            sy = (wy > 0) - (wy < 0)
            sx = (wx > 0) - (wx < 0)
            not_ignited *= 1.0 - config.FIRE_JUMP_PROB * mag * self.shift_array(burning, 2 * sy, 2 * sx)

        p_cell = 1.0 - not_ignited
        if moisture is not None:
            p_cell = p_cell * np.exp(-config.FIRE_MOISTURE_C * moisture)

        combustible = (objects_matrix == GRASS) | (objects_matrix == MANGO)
        flammable = (terrain_matrix == DIRT) & combustible & (self.matrix == NO_FIRE)
        new_ignitions = flammable & (self.rng.random((self.height, self.width)) < p_cell)

        # Ceniza: envejece y desaparece
        ash = self.matrix == ASH
        self.age[ash] += 1
        expired = ash & (self.age > config.ASH_TICKS)
        self.matrix[expired] = NO_FIRE
        self.age[expired] = 0

        # Fuego: envejece y se apaga (antes si hay humedad)
        self.age[self.matrix > 0] += 1
        if moisture is not None:
            burn_p = np.clip(config.FIRE_BURNOUT_BASE + config.FIRE_BURNOUT_MOISTURE * moisture, 0.0, 1.0)
        else:
            burn_p = config.FIRE_BURNOUT_BASE
        burn_out = (self.matrix > 0) & (self.age > 5) & (self.rng.random((self.height, self.width)) < burn_p)

        self.matrix[new_ignitions] = BURNING
        self.age[new_ignitions] = 0
        self.matrix[burn_out] = ASH
        self.age[burn_out] = 0

    def render_fire(self, terrain_matrix, objects_matrix):
        """Console view: ^ burning, : ash, " grass, * mango, . empty dirt, # rock, ~ water, N nest."""
        terrain_symbols = {ROCK: "#", WATER: "~", NEST: "N"}
        rows = []
        for y in range(self.height):
            row = ""
            for x in range(self.width):
                if terrain_matrix[y, x] != DIRT:
                    row += terrain_symbols[terrain_matrix[y, x]]
                elif self.matrix[y, x] == BURNING:
                    row += "^"
                elif self.matrix[y, x] == ASH:
                    row += ":"
                else:
                    row += {GRASS: '"', MANGO: "*"}.get(objects_matrix[y, x], ".")
            rows.append(row)
        return "\n".join(rows)