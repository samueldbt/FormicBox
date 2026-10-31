import math
import config as config
from Automata.terrain import DIRT, NEST


class Ant:
    CASTE = "ANT"
    DEFAULT_HEALTH = 3.0

    def __init__(self, y, x, nest_pos):
        """Initializes base attributes like position, energy, and the nest reference."""
        self.y = y
        self.x = x
        self.nest_y, self.nest_x = nest_pos
        self.energy = config.MAX_ENERGY
        self.state = config.STATE_EXPLORE

        # --- Datos para la interfaz (la lógica no depende de ellos) ---
        self.prev_y = y            # celda al inicio del tick (para interpolar el dibujo)
        self.prev_x = x
        self.facing = (-1, 0)      # (dy, dx) unitario: hacia dónde mira
        self.attacking = False

        # --- Vida y muerte ---
        self.health = self.DEFAULT_HEALTH
        self.alive = True
        self.death_cause = None    # "FIGHT" o "FIRE"
        self.dead_ticks = 0
        self.death_handled = False

    def die(self, cause):
        """Marca la hormiga como muerta. Simulation decide cuándo retirar el cadáver."""
        if self.alive:
            self.alive = False
            self.death_cause = cause
            self.attacking = False
            self.dead_ticks = 0

    def manhattan(self, other):
        return abs(other.y - self.y) + abs(other.x - self.x)

    def face_towards(self, other):
        """Gira hacia otra hormiga (solo 4 direcciones)."""
        dy, dx = other.y - self.y, other.x - self.x
        if dy == 0 and dx == 0:
            return
        if abs(dy) >= abs(dx):
            self.facing = (1 if dy > 0 else -1, 0)
        else:
            self.facing = (0, 1 if dx > 0 else -1)

    def get_home_angle(self):
        """Calculates the angle towards the nest using arctangent for path integration."""
        dy = self.nest_y - self.y
        dx = self.nest_x - self.x
        return math.atan2(dy, dx)

    def get_valid_neighbors(self, terrain_matrix, fire_matrix, occupied_mask):
        """Returns adjacent cells (4 direcciones) that are walkable, safe and unoccupied."""
        neighbors = []
        shifts = [(-1, 0), (0, -1), (0, 1), (1, 0)]

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