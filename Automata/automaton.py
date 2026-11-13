import numpy as np
import config
from .grid import Grid
from .scenario import get_scenario
from .terrain import Terrain, DIRT, ROCK, WATER, NEST
from .objects import EnvironmentObjects, NONE, GRASS, MANGO, BOCADILLO
from .pheromone import PheromoneLayer
from .fire import FireLayer, NO_FIRE, BURNING, ASH
from .colony import Colony


class CellularAutomaton:
    def __init__(self, width=config.WIDTH, height=config.HEIGHT, seed=config.SEED, scenario=None):
        """Coordina Terrain, Objects, Pheromones, Fire y Colony.
        scenario=None -> generador aleatorio. scenario="corridor" (id) o un Scenario -> mapa prefijado."""
        self.width = width
        self.height = height
        self.grid = Grid(width, height)

        self.scenario = get_scenario(scenario) if scenario is not None else None
        blocks = []
        if self.scenario is not None:
            seed = self.scenario.seed
            t, o, m, blocks = self.scenario.build(width, height)
            self._scenario_moisture = m.copy()

        self.terrain = Terrain(width, height, seed)
        if self.scenario is None:
            self.terrain.generate()
        else:
            self.terrain.matrix = t.astype(self.terrain.matrix.dtype)
            self.terrain.moisture = m
            ys, xs = np.nonzero(t == NEST)
            self.terrain.nest_pos = (int(round(ys.mean())), int(round(xs.mean())))

        self.recompute_fields()

        self.objects = EnvironmentObjects(width, height, seed)
        if self.scenario is None:
            self.objects.spawn_resources(self.terrain.matrix)
        else:
            self.objects.matrix = o.astype(self.objects.matrix.dtype)
            self.objects.level[self.objects.matrix == GRASS] = 2
            for kind, y, x in blocks:
                self.objects._put_block(kind, y, x)        # mango/bocadillo 2x2 completos
            self.objects.grass_max = config.GRASS_MAX or int((self.objects.matrix == GRASS).sum())
            self.objects.mango_max = config.MANGO_MAX or self.objects.count(MANGO)

        self.fire = FireLayer(width, height, seed)
        self.colony = Colony()

        self.pheromones = {
            name: PheromoneLayer(width, height, *params, mode=config.PHEROMONE_MODE[name])
            for name, params in (("vegetal", config.PHEROMONE_VEGETAL),
                                 ("azucar", config.PHEROMONE_SUGAR),
                                 ("alarma", config.PHEROMONE_ALARM),
                                 ("caza", config.PHEROMONE_HUNT))
        }

        self.tick_counter = 0

    # ------------------------------------------------------------ utilidades
    def _disk(self, y, x, radius):
        yy, xx = np.ogrid[:self.height, :self.width]
        return (yy - y) ** 2 + (xx - x) ** 2 <= radius ** 2

    def rain(self, y, x, radius, amount=0.4):
        """Sube la humedad en la zona (tope 1.0) y apaga el fuego que esté ardiendo."""
        mask = self._disk(y, x, radius)
        self.terrain.moisture[mask] = np.clip(self.terrain.moisture[mask] + amount, 0.0, 1.0)
        self.fire.matrix[mask & (self.fire.matrix == BURNING)] = NO_FIRE

    def drought(self, y, x, radius, amount=0.4):
        mask = self._disk(y, x, radius)
        self.terrain.moisture[mask] = np.clip(self.terrain.moisture[mask] - amount, 0.0, 1.0)

    def lightning(self, y, x):
        """Ignición en una celda. Solo prende si es tierra y no está ya en llamas."""
        if not (0 <= y < self.height and 0 <= x < self.width):
            return False
        if self.terrain.matrix[y, x] != DIRT or self.fire.matrix[y, x] != NO_FIRE:
            return False
        self.fire.matrix[y, x] = BURNING
        return True

    def recompute_fields(self):
        """Rehace home_dist, home_field y outbound_field a partir de terrain.matrix actual.
        Llamarlo tras cambiar roca o agua (place_terrain ya lo hace)."""
        self.home_field, self.home_dist = Terrain.nest_gradient_field(
            self.terrain.matrix, NEST, (DIRT,)
        )
        self.outbound_field = np.where(
            np.isfinite(self.home_dist), 1.0 - self.home_field, 0.0
        ).astype(np.float32)

    rebuilt_gradient = recompute_fields   # nombre antiguo, por compatibilidad

    def _clear_cells(self, mask):
        """Borra objetos, fuego y feromona bajo la máscara."""
        self.objects.clear_mask(mask)
        self.fire.matrix[mask] = NO_FIRE
        self.fire.age[mask] = 0
        for layer in self.pheromones.values():
            layer.matrix[mask] = 0.0
            layer.added[mask] = 0.0

    def place_terrain(self, y, x, kind):
        """Pone DIRT, ROCK o WATER en (y, x) y deja todo coherente.
        La tierra que quede inalcanzable desde el nido se vuelve roca.
        Devuelve False si no se pudo: fuera del mapa, tipo inválido o la celda es el nido."""
        if kind not in (DIRT, ROCK, WATER):
            return False
        if not (0 <= y < self.height and 0 <= x < self.width):
            return False
        if self.terrain.matrix[y, x] == NEST:
            return False
        if self.terrain.matrix[y, x] == kind:
            return True
        self.terrain.matrix[y, x] = kind

        if kind != DIRT:
            cell = np.zeros((self.height, self.width), dtype=bool)
            cell[y, x] = True
            self._clear_cells(cell)

        # Conectividad: lo que quede aislado del nido pasa a roca
        was_rock = self.terrain.matrix == ROCK
        self.terrain._ensure_connectivity()
        sealed = (self.terrain.matrix == ROCK) & ~was_rock
        if sealed.any():
            self._clear_cells(sealed)

        # La humedad depende del agua: se recalcula desde cero
        self.terrain.moisture.fill(0.0)
        self.terrain._calculate_static_moisture()
        if self.scenario is not None:
            self.terrain.moisture = np.maximum(self.terrain.moisture, self._scenario_moisture)
        self.recompute_fields()
        return True

    def deposit_pheromone(self, name, y, x, amount):
        """API para los agentes: deja feromona en una celda (se aplica en el próximo update)."""
        self.pheromones[name].deposit(y, x, amount)

    def guidance_field(self, name, returning, weight=0.5):
        bias = self.home_field if returning else self.outbound_field
        return (1.0 - weight) * self.pheromones[name].matrix + weight * bias

    @staticmethod
    def loop_weight(revisits, base=0.2, step=0.1):
        return min(1.0, base + step * revisits)

    def update_step(self):
        """Un tick del ambiente: feromonas, fuego, objetos."""
        self.tick_counter += 1

        # 1. Feromonas (difusión por convolución, evaporación, viento, depósito)
        wx_shift = 1 if config.WIND_X > 0 else -1 if config.WIND_X < 0 else 0
        wy_shift = 1 if config.WIND_Y > 0 else -1 if config.WIND_Y < 0 else 0
        wind_strength = min(abs(config.WIND_X) + abs(config.WIND_Y), 0.2)
        is_dirt = (self.terrain.matrix == DIRT) | (self.terrain.matrix == NEST)

        for layer in self.pheromones.values():
            moore_avg = self.grid.get_moore_average(layer.matrix)
            shifted = self.grid.shift_array(layer.matrix, wy_shift, wx_shift)
            wind_effect = wind_strength * (shifted - layer.matrix)
            layer.update(moore_avg, wind_effect)
            layer.matrix *= is_dirt

        # 2. Propagación del fuego (la ceniza expira dentro de FireLayer)
        self.fire.update_fire(self.terrain.matrix, self.objects.matrix)

        # 3. El fuego (y la ceniza) destruyen los objetos de su celda
        self.objects.clear_mask(self.fire.matrix != NO_FIRE)

        # 4. Brotes y maduración lenta
        self.objects.update(self.terrain.matrix, self.terrain.moisture,
                            self.fire.matrix, self.tick_counter)