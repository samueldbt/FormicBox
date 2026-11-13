import math
import random
from collections import deque
import config as config
from Automata.terrain import DIRT, NEST
from .mealy import perceive


class Ant:
    CASTE = "ANT"
    DEFAULT_HEALTH = 3.0

    def __init__(self, y, x, nest_pos, agents=None):
        self.y = y
        self.x = x
        self.nest_y, self.nest_x = nest_pos
        self.max_energy = config.MAX_ENERGY_BY_CASTE.get(self.CASTE, config.MAX_ENERGY)
        self.energy = self.max_energy
        self.state = config.STATE_EXPLORE
        self.agents = agents if agents is not None else []

        # Memoria
        self.last_y = y
        self.last_x = x
        self.tabu = deque(maxlen=config.TABU_SIZE)
        self.mem_target = None
        self.mem_ttl = 0
        self.percept = None

        # Datos para la interfaz
        self.prev_y = y
        self.prev_x = x
        self.facing = (-1, 0)
        self.attacking = False

        # Vida y muerte
        self.health = self.DEFAULT_HEALTH
        self.alive = True
        self.death_cause = None    # "FIGHT", "FIRE", "STARVE" (sin energía) o "HUNGER" (bolsa vacía)
        self.dead_ticks = 0
        self.death_handled = False

    def die(self, cause):
        if self.alive:
            self.alive = False
            self.death_cause = cause
            self.attacking = False
            self.dead_ticks = 0

    def manhattan(self, other):
        return abs(other.y - self.y) + abs(other.x - self.x)

    def face_towards(self, other):
        dy, dx = other.y - self.y, other.x - self.x
        if dy == 0 and dx == 0:
            return
        if abs(dy) >= abs(dx):
            self.facing = (1 if dy > 0 else -1, 0)
        else:
            self.facing = (0, 1 if dx > 0 else -1)

    def get_home_angle(self):
        return math.atan2(self.nest_y - self.y, self.nest_x - self.x)

    def get_valid_neighbors(self, terrain_matrix, fire_matrix, occupied_mask):
        neighbors = []
        h, w = terrain_matrix.shape
        for dy, dx in ((-1, 0), (0, -1), (0, 1), (1, 0)):
            ny, nx = self.y + dy, self.x + dx
            if 0 <= ny < h and 0 <= nx < w:
                if (terrain_matrix[ny, nx] in (DIRT, NEST)
                        and fire_matrix[ny, nx] <= 0 and not occupied_mask[ny, nx]):
                    neighbors.append((ny, nx, dy, dx))
        return neighbors

    # ------------------------------------------------------------ energía
    def consume_energy(self):
        """Pierde energía cada tick; con 0 muere (STARVE)."""
        self.energy = max(0.0, self.energy - config.ENERGY_COST_PER_TICK)
        if self.energy <= 0.0:
            self.die("STARVE")

    def refuel_at_nest(self, automaton):
        """En el nido: si está por debajo de REFUEL_FRACTION del tanque, come de la bolsa hasta llenarse."""
        if self.energy >= config.REFUEL_FRACTION * self.max_energy:
            return False
        gained = automaton.colony.feed(self.max_energy - self.energy)
        if gained <= 0.0:
            return False
        self.energy = min(self.max_energy, self.energy + gained)
        return True

    @staticmethod
    def dist_home(automaton, y, x):
        """Distancia real por camino al nido (BFS)."""
        d = automaton.home_dist[y, x]
        return float(d) if math.isfinite(d) else 1e6

    def low_energy(self, automaton):
        """True si la energía ya no sobra para volver al nido desde donde está (más una reserva)."""
        d = self.dist_home(automaton, self.y, self.x)
        if d >= 1e6:
            d = 0.0
        need = d * config.ENERGY_COST_PER_TICK * config.RETURN_MARGIN + config.ENERGY_RESERVE_FRAC * self.max_energy
        return self.energy <= min(need, 0.95 * self.max_energy)

    # ------------------------------------------------------------ percepción y movimiento
    def perceive(self, automaton, ignore=()):
        return perceive(self, automaton, ignore)

    @staticmethod
    def fire_heat(automaton, y, x, radius=None):
        radius = config.FIRE_ALERT_RADIUS if radius is None else radius
        m = automaton.fire.matrix
        h, w = m.shape
        win = m[max(0, y - radius):min(h, y + radius + 1), max(0, x - radius):min(w, x + radius + 1)]
        return float((win > 0).sum()) / float((2 * radius + 1) ** 2)

    def home_align(self, automaton, ny, nx, dy, dx, d_cur, home_angle):
        """-1..1: +1 si el paso acerca al nido. Con RETURN_USE_FIELD usa la distancia real por camino."""
        if config.RETURN_USE_FIELD:
            d_new = self.dist_home(automaton, ny, nx)
            return 1.0 if d_new < d_cur else (-1.0 if d_new > d_cur else 0.0)
        return math.cos(home_angle - math.atan2(dy, dx))

    def tabu_active(self):
        mode = config.TABU_MODE.get(self.CASTE, "always")
        if mode == "off":
            return False
        if mode == "always":
            return True
        return self.state in config.TABU_STATES    # "explore": no bloquea el camino de regreso

    def allowed_neighbors(self, neighbors):
        """Quita las celdas de la memoria tabú (si aplica); si no queda ninguna, devuelve todas."""
        if not self.tabu_active():
            return neighbors
        fresh = [n for n in neighbors if (n[0], n[1]) not in self.tabu]
        return fresh if fresh else neighbors

    def noise(self):
        return 0.0 if config.DETERMINISTIC_MOVES else config.WEIGHT_RANDOM * random.random()

    @staticmethod
    def pick_move(moves, scores):
        """Sorteo ponderado por puntaje**MOVE_EXPONENT; con DETERMINISTIC_MOVES elige la mejor celda."""
        if config.DETERMINISTIC_MOVES:
            best = max(scores)
            return next(m for m, s in zip(moves, scores) if s >= best - 1e-9)
        weights = [max(0.001, s) ** config.MOVE_EXPONENT for s in scores]
        return random.choices(moves, weights=weights, k=1)[0]

    def commit_move(self, ny, nx):
        self.tabu.append((self.y, self.x))
        self.last_y, self.last_x = self.y, self.x
        self.y, self.x = ny, nx