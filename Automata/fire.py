import numpy as np
import config
from .grid import Grid
from .terrain import DIRT, ROCK, WATER, NEST
from .objects import GRASS, MANGO, BOCADILLO

# Fire States
NO_FIRE, BURNING, ASH = 0, 1, -1

class FireLayer(Grid):
    def __init__(self, width, height, seed=None):
        """Initializes the fire state matrix and fire age tracker."""
        super().__init__(width, height, seed)
        self.matrix = np.zeros((height, width), dtype=np.int8)
        self.age = np.zeros((height, width), dtype=np.int16)   # edad del fuego o de la ceniza

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

    def update_fire(self, terrain_matrix, objects_matrix):
        """Propagates fire to DIRT cells with vegetal resources, considering wind vectors.
        La ceniza dura ASH_TICKS y luego la celda vuelve a tierra desnuda."""
        directions = [(-1, -1), (-1, 0), (-1, 1), (0, -1),
                      (0, 1), (1, -1), (1, 0), (1, 1)]

        not_ignited = np.ones((self.height, self.width), dtype=np.float32)

        for dy, dx in directions:
            norm = np.hypot(dy, dx)
            wind_align = (config.WIND_X * dx + config.WIND_Y * dy) / norm
            p_ign = config.FIRE_BASE_PROB * (1.0 + config.FIRE_WIND_C * wind_align)
            p_ign = np.clip(p_ign, 0.0, 1.0)

            source_fire = self.shift_array(self.matrix > 0, dy, dx)
            not_ignited *= 1.0 - (p_ign * source_fire)

        combustible = (objects_matrix == GRASS) | (objects_matrix == MANGO)
        flammable = (terrain_matrix == DIRT) & combustible & (self.matrix == NO_FIRE)

        new_ignitions = flammable & (self.rng.random((self.height, self.width)) < (1.0 - not_ignited))

        # Ceniza: envejece y desaparece
        ash = self.matrix == ASH
        self.age[ash] += 1
        expired = ash & (self.age > config.ASH_TICKS)
        self.matrix[expired] = NO_FIRE
        self.age[expired] = 0

        # Fuego: envejece y se apaga
        self.age[self.matrix > 0] += 1
        burn_out = (self.matrix > 0) & (self.age > 5) & (self.rng.random((self.height, self.width)) < 0.3)

        self.matrix[new_ignitions] = BURNING
        self.age[new_ignitions] = 0
        self.matrix[burn_out] = ASH
        self.age[burn_out] = 0

    def render_fire(self, terrain_matrix, objects_matrix):
        """Console view of the fire: ^ burning, : ash, " grass, * mango, . empty dirt, # rock, ~ water, N nest."""
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