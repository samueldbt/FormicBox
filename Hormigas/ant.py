import math
import config as config
from Automata.terrain import DIRT, NEST

class Ant:
    def __init__(self, y, x, nest_pos):
        """Initializes base attributes like position, energy, and the nest reference."""
        self.y = y
        self.x = x
        self.nest_y, self.nest_x = nest_pos
        self.energy = config.MAX_ENERGY
        self.state = config.STATE_EXPLORE

    def get_home_angle(self):
        """Calculates the angle towards the nest using arctangent for path integration."""
        dy = self.nest_y - self.y
        dx = self.nest_x - self.x
        return math.atan2(dy, dx)

    def get_valid_neighbors(self, terrain_matrix, fire_matrix, occupied_mask):
        """Returns adjacent cells (Moore) that are walkable and unoccupied."""
        neighbors = []
        shifts = [(-1, -1), (-1, 0), (-1, 1), (0, -1), 
                  (0, 1), (1, -1), (1, 0), (1, 1)]
        
        h, w = terrain_matrix.shape
        for dy, dx in shifts:
            ny, nx = self.y + dy, self.x + dx
            if 0 <= ny < h and 0 <= nx < w:
                is_walkable = terrain_matrix[ny, nx] in (DIRT, NEST)
                is_safe = fire_matrix[ny, nx] <= 0
                is_free = not occupied_mask[ny, nx]
                
                if is_walkable and is_safe and is_free:
                    neighbors.append((ny, nx, dy, dx))
                    
        return neighbors

    def consume_energy(self):
        """Reduces energy per tick. Prevents energy from dropping below zero."""
        self.energy = max(0.0, self.energy - config.ENERGY_COST_PER_TICK)