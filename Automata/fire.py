import numpy as np
import config as config
from .grid import Grid
from .terrain import DIRT
from .objects import GRASS, MANGO, BOCADILLO

# Fire States
NO_FIRE, BURNING, ASH = 0, 1, -1

class FireLayer(Grid):
    def __init__(self, width, height, seed=None):
        """Initializes the fire state matrix and fire age tracker."""
        super().__init__(width, height, seed)
        self.matrix = np.zeros((height, width), dtype=np.int8)
        self.age = np.zeros((height, width), dtype=np.int16)

    def update_fire(self, terrain_matrix, objects_matrix):
        """Propagates fire to DIRT cells with vegetal resources, considering wind vectors."""
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

        # Fire burns over Grass and Mango[cite: 1]
        combustible = (objects_matrix == GRASS) | (objects_matrix == MANGO)
        flammable = (terrain_matrix == DIRT) & combustible & (self.matrix == NO_FIRE)
        
        new_ignitions = flammable & (self.rng.random((self.height, self.width)) < (1.0 - not_ignited))
        
        self.age[self.matrix > 0] += 1
        burn_out = (self.matrix > 0) & (self.age > 5) & (self.rng.random((self.height, self.width)) < 0.3)
        
        self.matrix[new_ignitions] = BURNING
        self.matrix[burn_out] = ASH
        self.age[burn_out] = 0