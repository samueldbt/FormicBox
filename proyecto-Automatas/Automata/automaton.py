import numpy as np
import config
from .grid import Grid
from .terrain import Terrain, DIRT, ROCK, WATER, NEST
from .objects import EnvironmentObjects, NONE, GRASS, MANGO, BOCADILLO
from .pheromone import PheromoneLayer
from .fire import FireLayer, NO_FIRE, BURNING, ASH
from .colony import Colony


class CellularAutomaton:
    def __init__(self, width=config.WIDTH, height=config.HEIGHT, seed=config.SEED):
        """Coordinates and instantiates Terrain, Objects, Pheromones, Fire and Colony."""
        self.width = width
        self.height = height
        self.grid = Grid(width, height)

        self.terrain = Terrain(width, height, seed)
        self.terrain.generate()

        # Gradient field (distancia al nido)
        self.home_field, self.home_dist = Terrain.nest_gradient_field(self.terrain.matrix, NEST, (DIRT,))
        self.outbound_field = np.where(np.isfinite(self.home_dist), 1.0 - self.home_field, 0.0).astype(np.float32)

        self.objects = EnvironmentObjects(width, height, seed)
        self.objects.spawn_resources(self.terrain.matrix)

        self.fire = FireLayer(width, height, seed)
        self.colony = Colony()

        self.pheromones = {
            "vegetal": PheromoneLayer(width, height, *config.PHEROMONE_VEGETAL),
            "azucar": PheromoneLayer(width, height, *config.PHEROMONE_SUGAR),
            "alarma": PheromoneLayer(width, height, *config.PHEROMONE_ALARM),
            "caza": PheromoneLayer(width, height, *config.PHEROMONE_HUNT)
        }

        self.tick_counter = 0

    def deposit_pheromone(self, name, y, x, amount):
        """API para los agentes: deja feromona en una celda (se aplica en el próximo update)."""
        self.pheromones[name].deposit(y, x, amount)

    def guidance_field(self, name, returning, weight=0.5):
        """Pheromone layer blended with the nest gradient (API for the agents).
        returning=True  -> bias toward the nest. returning=False -> inverse gradient (away from it)."""
        bias = self.home_field if returning else self.outbound_field
        return (1.0 - weight) * self.pheromones[name].matrix + weight * bias

    @staticmethod
    def loop_weight(revisits, base=0.2, step=0.1):
        """Adaptive blend weight PER AGENT: grows with the agent's total revisited cells."""
        return min(1.0, base + step * revisits)

    def update_step(self):
        """Executes the simulation loop exactly as ordered in the technical document."""
        self.tick_counter += 1

        # 1. Update Pheromones
        for name, layer in self.pheromones.items():
            moore_avg = self.grid.get_moore_average(layer.matrix)

            wx_shift = 1 if config.WIND_X > 0 else -1 if config.WIND_X < 0 else 0
            wy_shift = 1 if config.WIND_Y > 0 else -1 if config.WIND_Y < 0 else 0
            wind_strength = min(abs(config.WIND_X) + abs(config.WIND_Y), 0.2)

            shifted = self.grid.shift_array(layer.matrix, wy_shift, wx_shift)
            wind_effect = wind_strength * (shifted - layer.matrix)

            layer.update(moore_avg, wind_effect)
            layer.matrix *= (self.terrain.matrix == DIRT)

        # 2. Fire propagation (la ceniza expira dentro de FireLayer)
        self.fire.update_fire(self.terrain.matrix, self.objects.matrix)

        # 3. El fuego (y la ceniza) destruyen los objetos de su celda
        self.objects.clear_mask(self.fire.matrix != NO_FIRE)

        # 4. Brotes y maduración lenta
        self.objects.update(self.terrain.matrix, self.terrain.moisture,
                            self.fire.matrix, self.tick_counter)