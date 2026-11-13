import math
from collections import deque
import config as config
from Automata.terrain import DIRT, NEST
from .mealy import perceive


class Ant:
    CASTE = "ANT"
    DEFAULT_HEALTH = 3.0

    def __init__(self, y, x, nest_pos, agents=None):
        """Posición, energía, nido, memoria tabú y lista compartida de agentes (para ver a las demás)."""
        self.y = y
        self.x = x
        self.nest_y, self.nest_x = nest_pos
        self.energy = config.MAX_ENERGY
        self.state = config.STATE_EXPLORE
        self.agents = agents if agents is not None else []

        # Memoria
        self.last_y = y
        self.last_x = x
        self.tabu = deque(maxlen=config.TABU_SIZE)   # últimas celdas pisadas
        self.mem_target = None                       # (y, x) del último recurso visto
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
        self.death_cause = None    # "FIGHT", "FIRE" o "STARVE"
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
        """Gira hacia otra hormiga (solo 4 direcciones)."""
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
        """Celdas adyacentes (4 direcciones) transitables, sin fuego y libres."""
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
        """Pierde energía cada tick; con 0 muere de hambre."""
        self.energy = max(0.0, self.energy - config.ENERGY_COST_PER_TICK)
        if self.energy <= 0.0:
            self.die("STARVE")

    def refuel_at_nest(self, automaton, below):
        """En el nido: si tiene menos de `below` de energía, come una unidad de la reserva."""
        if self.energy >= below:
            return False
        gained = automaton.colony.eat()
        if gained <= 0.0:
            return False
        self.energy = min(config.MAX_ENERGY, self.energy + gained)
        return True

    # ------------------------------------------------------------ percepción y movimiento
    def perceive(self, automaton, ignore=()):
        return perceive(self, automaton, ignore)

    @staticmethod
    def fire_heat(automaton, y, x, radius=None):
        """Fracción de celdas en llamas en el cuadrado de radio `radius` centrado en (y, x)."""
        radius = config.FIRE_ALERT_RADIUS if radius is None else radius
        m = automaton.fire.matrix
        h, w = m.shape
        win = m[max(0, y - radius):min(h, y + radius + 1), max(0, x - radius):min(w, x + radius + 1)]
        return float((win > 0).sum()) / float((2 * radius + 1) ** 2)

    def allowed_neighbors(self, neighbors):
        """Quita las celdas de la memoria tabú; si no queda ninguna (acorralada) devuelve todas."""
        fresh = [n for n in neighbors if (n[0], n[1]) not in self.tabu]
        return fresh if fresh else neighbors

    def commit_move(self, ny, nx):
        """Se mueve a (ny, nx) recordando la celda que deja."""
        self.tabu.append((self.y, self.x))
        self.last_y, self.last_x = self.y, self.x
        self.y, self.x = ny, nx