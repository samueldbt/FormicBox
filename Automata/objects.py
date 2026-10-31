import numpy as np
import config as config
from .grid import Grid
from .terrain import DIRT

# Object Constants
NONE, GRASS, MANGO, BOCADILLO = 0, 1, 2, 3

class EnvironmentObjects(Grid):
    def __init__(self, width, height, seed=None):
        """Initializes a single matrix for all interactive resources."""
        super().__init__(width, height, seed)
        self.matrix = np.full((height, width), NONE, dtype=np.uint8)

    def spawn_resources(self, terrain_matrix):
        """Generates initial grass and mango safely on valid DIRT cells."""
        valid_dirt = (terrain_matrix == DIRT)
        
        # Ensure spots return proper boolean masks
        grass_spots = self.generate_spots(config.GRASS_DENSITY) > 0.5
        mango_spots = self.generate_spots(config.MANGO_DENSITY, iterations=2) > 0.5
        
        # If mango mask is entirely empty due to low density/seed, force at least one spot
        if not np.any(mango_spots & valid_dirt):
            # Fallback: force manual placement of a few mango spots if random generation misses
            y_indices = self.rng.integers(5, self.height - 5, size=3)
            x_indices = self.rng.integers(5, self.width - 5, size=3)
            for y, x in zip(y_indices, x_indices):
                if valid_dirt[y, x]:
                    mango_spots[y, x] = True

        # Populate matrix: Grass first, Mango overwrites Grass if overlapping
        self.matrix[valid_dirt & grass_spots] = GRASS
        self.matrix[valid_dirt & mango_spots] = MANGO

    def check_and_regenerate(self, terrain_matrix, fire_matrix):
        """Regenerates resources if global density falls below config thresholds."""
        total_cells = self.width * self.height
        valid_mask = (terrain_matrix == DIRT) & (fire_matrix == 0) & (self.matrix == NONE)

        current_grass = np.sum(self.matrix == GRASS) / total_cells
        if current_grass < config.MIN_GRASS_THRESHOLD:
            new_grass = self.generate_spots(config.GRASS_DENSITY) > 0.5
            self.matrix[valid_mask & new_grass] = GRASS
            
        current_mango = np.sum(self.matrix == MANGO) / total_cells
        if current_mango < config.MIN_MANGO_THRESHOLD:
            new_mango = self.generate_spots(config.MANGO_DENSITY, iterations=2) > 0.5
            self.matrix[valid_mask & new_mango] = MANGO