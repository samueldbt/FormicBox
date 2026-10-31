
import config
from .grid import Grid
from .terrain import Terrain, DIRT, ROCK, WATER, NEST
from .objects import EnvironmentObjects, NONE, GRASS, MANGO, BOCADILLO
from .pheromone import PheromoneLayer
from .fire import FireLayer, NO_FIRE, ASH

class CellularAutomaton:
    def __init__(self, width=200, height=60, seed=1):
        """Coordinates and instantiates Terrain, Objects, Pheromones, and Fire."""
        self.width = width
        self.height = height
        self.grid = Grid(width, height)
        
        self.terrain = Terrain(width, height, seed)
        self.terrain.generate()
        
        self.objects = EnvironmentObjects(width, height, seed)
        self.objects.spawn_resources(self.terrain.matrix)
        
        self.fire = FireLayer(width, height, seed)
        
        self.pheromones = {
            "vegetal": PheromoneLayer(width, height, *config.PHEROMONE_VEGETAL),
            "azucar": PheromoneLayer(width, height, *config.PHEROMONE_SUGAR),
            "alarma": PheromoneLayer(width, height, *config.PHEROMONE_ALARM),
            "caza": PheromoneLayer(width, height, *config.PHEROMONE_HUNT)
        }
        
        self.tick_counter = 0

    def deposit_pheromone(self, phero_name, y, x, amount):
        """Suma el depósito del agente (A) al campo químico especificado."""
        if phero_name in self.pheromones:
            self.pheromones[phero_name].matrix[y, x] += amount
            
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
            
        # 2. Evaluate Fire Propagation
        self.fire.update_fire(self.terrain.matrix, self.objects.matrix)
        
        # 3. Update Resources and Terrain 
        recovery_mask = (self.fire.matrix == ASH) & (self.terrain.moisture >= config.MOISTURE_THRESHOLD)
        self.fire.matrix[recovery_mask] = NO_FIRE
        
        # Fire destroys objects
        destroyed = self.fire.matrix != NO_FIRE
        self.objects.matrix[destroyed] = NONE
        
        if self.tick_counter % 100 == 0:
            self.objects.check_and_regenerate(self.terrain.matrix, self.fire.matrix)


