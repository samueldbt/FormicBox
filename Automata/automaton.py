import numpy as np
import config
from .grid import Grid
from .scenario import get_scenario
from .terrain import Terrain, DIRT, ROCK, WATER, NEST
from .objects import EnvironmentObjects, NONE, GRASS, MANGO, BOCADILLO
from .pheromone import PheromoneLayer
from .fire import FireLayer, NO_FIRE, BURNING, ASH
from .colony import Colony
from collections import deque
from .loot import LootLayer
from .weather import Weather


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
        self.objects.set_zone(self.home_dist)
        if self.scenario is None:
            self.objects.spawn_resources(self.terrain.matrix)
        else:
            self.objects.matrix = o.astype(self.objects.matrix.dtype)
            self.objects.level[self.objects.matrix == GRASS] = 2
            self.objects.bites[self.objects.matrix == GRASS] = config.GRASS_BITES
            for kind, y, x in blocks:
                self.objects._put_block(kind, y, x)        # mango/bocadillo 2x2 completos
            self.objects.grass_max = config.GRASS_MAX or int((self.objects.matrix == GRASS).sum())
            self.objects.mango_max = config.MANGO_MAX or self.objects.count(MANGO)

        self.fire = FireLayer(width, height, seed)
        self.colony = Colony()
        self.loot = LootLayer()
        self.events = []              # eventos para el audio: (tipo, y, x)

        self.pheromones = {
            name: PheromoneLayer(width, height, *params, mode=config.PHEROMONE_MODE[name])
            for name, params in (("vegetal", config.PHEROMONE_VEGETAL),
                                 ("azucar", config.PHEROMONE_SUGAR),
                                 ("alarma", config.PHEROMONE_ALARM),
                                 ("caza", config.PHEROMONE_HUNT))
        }

        self.tick_counter = 0
        self.base_moisture = self.terrain.moisture.copy()   # humedad "de equilibrio": la lluvia y la sequía la desvían
        self.weather = Weather(self, seed)

    # ------------------------------------------------------------ utilidades
    def _disk(self, y, x, radius):
        yy, xx = np.ogrid[:self.height, :self.width]
        return (yy - y) ** 2 + (xx - x) ** 2 <= radius ** 2

    def rain(self, y, x, radius=None, ticks=None):
        """Zona de lluvia: sube la humedad poco a poco y apaga el fuego (ver weather.py)."""
        return self.weather.rain(y, x, radius, ticks)

    def drought(self, y, x, radius=None, ticks=None):
        """Zona de sequía: evapora la humedad progresivamente."""
        return self.weather.drought(y, x, radius, ticks)

    def lightning(self, y, x, sure=True):
        """Rayo en (y, x). Devuelve True si prendió fuego (pasto/mango sin fuego)."""
        return self.weather.strike(y, x, sure)

    def recompute_fields(self):
        """Rehace home_dist, home_field y outbound_field a partir de terrain.matrix actual.
        Llamarlo tras cambiar roca o agua (place_terrain ya lo hace)."""
        self.home_field, self.home_dist = Terrain.nest_gradient_field(
            self.terrain.matrix, NEST, (DIRT,)
        )
        self.outbound_field = np.where(
            np.isfinite(self.home_dist), 1.0 - self.home_field, 0.0
        ).astype(np.float32)
        self.exit_dist = self._exit_field()
        if hasattr(self, "objects"):
            self.objects.set_zone(self.home_dist)

    def emit(self, kind, y, x):
        self.events.append((kind, int(y), int(x)))

    def _exit_field(self):
        """Distancia por camino a la celda transitable más cercana del borde del mapa (retirada de las marabuntas)."""
        h, w = self.height, self.width
        walk = (self.terrain.matrix == DIRT) | (self.terrain.matrix == NEST)
        dist = np.full((h, w), np.inf)
        q = deque()
        for y in range(h):
            for x in range(w):
                if walk[y, x] and (y in (0, h - 1) or x in (0, w - 1)):
                    dist[y, x] = 0
                    q.append((y, x))
        while q:
            y, x = q.popleft()
            for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and walk[ny, nx] and dist[ny, nx] == np.inf:
                    dist[ny, nx] = dist[y, x] + 1
                    q.append((ny, nx))
        return dist

    rebuilt_gradient = recompute_fields   # nombre antiguo, por compatibilidad

    def _clear_cells(self, mask):
        """Borra objetos, fuego y feromona bajo la máscara."""
        self.objects.clear_mask(mask)
        self.loot.clear_where(mask)
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

        # La humedad base depende del agua: se recalcula, conservando lo que lluvia/sequía hayan desviado
        delta = self.terrain.moisture - self.base_moisture
        self.terrain.moisture.fill(0.0)
        self.terrain._calculate_static_moisture()
        if self.scenario is not None:
            self.terrain.moisture = np.maximum(self.terrain.moisture, self._scenario_moisture)
        self.base_moisture = self.terrain.moisture.copy()
        self.terrain.moisture = np.clip(self.base_moisture + delta, 0.0, 1.0).astype(np.float32)
        self.terrain.moisture[self.terrain.matrix == WATER] = 1.0
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

        # 1b. Clima: lluvia, sequía y rayos (cambian la humedad que lee el fuego)
        self.weather.update()

        # 2. Propagación del fuego (la ceniza expira dentro de FireLayer)
        self.fire.update_fire(self.terrain.matrix, self.objects.matrix, self.terrain.moisture)

        # 3. El fuego (y la ceniza) destruyen los objetos de su celda
        self.objects.clear_mask(self.fire.matrix != NO_FIRE)
        self.loot.clear_where(self.fire.matrix != NO_FIRE)

        # 4. Brotes y maduración lenta
        self.objects.update(self.terrain.matrix, self.terrain.moisture,
                            self.fire.matrix, self.tick_counter)