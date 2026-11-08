import math
import random
import config

from .ant import Ant
from Automata.objects import NONE
from Automata.terrain import DIRT


STATE_RAID = "RAID"
STATE_ATTACK = "ATTACK"
STATE_RETREAT = "RETREAT"

# Parámetros. Pasarlos a config
MARABUNTA_HEALTH = 6.0        # vida de cada marabunta
BITE_DAMAGE = 1.0             # daño por mordida (por tick, a una hormiga vecina)
PREY_SENSE_RADIUS = 3         # a cuántas celdas ve una presa
RETREAT_HEALTH = 2.0          # con menos vida que esto se retira
MAX_RAID_TICKS = 800          # duración de una incursión antes de retirarse
HUNT_TRAIL_K = 5.0            # saturación del rastro de caza: t / (t + K)
HUNT_SENSE_RADIUS = 3         # la "caza" se huele en un cuadrado de este radio
DEPOSIT_AMOUNT_HUNT = 10.0    # "caza" que deja cada marabunta por tick al avanzar
WEIGHT_TARGET = 3.0           # atracción hacia el nido de la colonia
WEIGHT_HUNT = 4.0             # atracción hacia el rastro del enjambre
WEIGHT_PREY = 8.0             # atracción hacia la presa en ATTACK
WEIGHT_INERTIA = 1.5          # preferencia por seguir el rumbo
FIRE_ALERT_RADIUS = 2         # radio (celdas) en el que el fuego la hace huir
WEIGHT_FLEE = 10.0            # fuerza de la huida del fuego


def damage(target, amount):
    """Quita vida a un agente. Al llegar a 0 muere por pelea (Ant.die);
    Simulation decide cuándo retira el cadáver."""
    target.health -= amount
    if target.health <= 0:
        target.die("FIGHT")


class Marabunta(Ant):
    CASTE = "MARABUNTA"

    def __init__(self, y, x, nest_pos, agents=None):
        """y, x: punto de entrada (un borde del mapa). nest_pos: el nido de la colonia que ataca.
        agents: lista compartida con todos los agentes (para ver presas)."""
        super().__init__(y, x, nest_pos)
        self.state = STATE_RAID
        self.carried_resource = NONE      # la interfaz dibuja según este atributo
        self.health = MARABUNTA_HEALTH
        self.agents = agents if agents is not None else []
        self.prey = None                  # agente que está atacando
        self.raid_ticks = 0
        self.kills = 0

        self.last_y = y
        self.last_x = x

    @staticmethod
    def spawn_position(automaton):
        """Celda de tierra al azar en el borde (izquierdo o derecho) más lejano del nido."""
        h, w = automaton.terrain.matrix.shape
        nest_x = automaton.terrain.nest_pos[1]
        step = 1 if nest_x > w // 2 else -1
        col = 0 if step == 1 else w - 1
        for i in range(w):
            c = col + step * i
            rows = [y for y in range(h) if automaton.terrain.matrix[y, c] == DIRT]
            if rows:
                return random.choice(rows), c
        return automaton.terrain.nest_pos

    def update_logic(self, automaton, occupied_mask):
        """Evalúa el estado, se mueve, marca el rastro del enjambre y muerde si tiene presa al lado."""
        if not self.alive:
            return
        self.attacking = False
        self.raid_ticks += 1
        self._evaluate_state(automaton)
        self._move(automaton, occupied_mask)

        if self.state in (STATE_RAID, STATE_ATTACK):
            automaton.deposit_pheromone("caza", self.y, self.x, DEPOSIT_AMOUNT_HUNT)
        if self.state == STATE_ATTACK:
            self._bite()
        if (self.y, self.x) == (self.nest_y, self.nest_x):
            self._raid_nest(automaton)

    def _evaluate_state(self, automaton):
        """Prioridad: huir del fuego > retirarse > atacar presa visible > avanzar."""
        if self._fire_near(automaton, self.y, self.x) > 0:
            self.state = config.STATE_FLEE
            self.prey = None
            return
        if self.state == STATE_RETREAT:
            return
        if self.health < RETREAT_HEALTH or self.raid_ticks > MAX_RAID_TICKS:
            self.state = STATE_RETREAT
            self.prey = None
            return

        self.prey = self._find_prey()
        self.state = STATE_ATTACK if self.prey is not None else STATE_RAID

    def _find_prey(self):
        """Hormiga viva de la colonia más cercana dentro de PREY_SENSE_RADIUS, o None."""
        best, best_d = None, PREY_SENSE_RADIUS + 1
        for ag in self.agents:
            if getattr(ag, "CASTE", None) == self.CASTE or not getattr(ag, "alive", True):
                continue
            d = max(abs(ag.y - self.y), abs(ag.x - self.x))
            if d < best_d:
                best, best_d = ag, d
        return best

    def _bite(self):
        """Muerde a la presa si está en una celda ortogonalmente vecina."""
        p = self.prey
        if p is None or self.manhattan(p) > 1:
            return
        self.face_towards(p)
        self.attacking = True
        damage(p, BITE_DAMAGE)
        if not getattr(p, "alive", True):
            self.kills += 1
            self.prey = None

    @staticmethod
    def _fire_near(automaton, y, x, radius=FIRE_ALERT_RADIUS):
        """Cantidad de celdas en llamas dentro del cuadrado de lado 2*radius+1 centrado en (y, x)."""
        h, w = automaton.fire.matrix.shape
        y0, y1 = max(0, y - radius), min(h, y + radius + 1)
        x0, x1 = max(0, x - radius), min(w, x + radius + 1)
        return int((automaton.fire.matrix[y0:y1, x0:x1] > 0).sum())

    @staticmethod
    def _smell_hunt(automaton, y, x, radius=HUNT_SENSE_RADIUS):
        """Suma de 'caza' en el cuadrado de radio `radius` (la difusión sola casi no llega lejos)."""
        m = automaton.pheromones["caza"].matrix
        h, w = m.shape
        return float(m[max(0, y - radius):min(h, y + radius + 1), max(0, x - radius):min(w, x + radius + 1)].sum())

    def _move(self, automaton, occupied_mask):
        """Elige la celda vecina con la misma ecuación P de Worker: puntaje, cubo y sorteo."""
        # Ya pegada (ortogonalmente) a la presa: se queda quieta mordiendo
        if self.state == STATE_ATTACK and self.prey is not None and self.manhattan(self.prey) <= 1:
            return

        all_neighbors = self.get_valid_neighbors(automaton.terrain.matrix, automaton.fire.matrix, occupied_mask)
        if not all_neighbors:
            return

        neighbors = [(ny, nx, dy, dx) for ny, nx, dy, dx in all_neighbors
                     if (ny, nx) != (self.last_y, self.last_x) or len(all_neighbors) == 1]

        nest_angle = self.get_home_angle()
        heading = (self.y - self.last_y, self.x - self.last_x)

        valid_moves = []
        move_weights = []
        for ny, nx, dy, dx in neighbors:
            move_angle = math.atan2(dy, dx)
            to_nest = math.cos(nest_angle - move_angle)
            inertia = self._inertia(dy, dx, heading)

            if self.state == STATE_ATTACK and self.prey is not None:
                dist = abs(ny - self.prey.y) + abs(nx - self.prey.x)
                score = WEIGHT_PREY / (1.0 + dist)
            elif self.state == config.STATE_FLEE:
                heat = self._fire_near(automaton, ny, nx) / float((2 * FIRE_ALERT_RADIUS + 1) ** 2)
                score = WEIGHT_FLEE * (1.0 - heat) + 0.5 * inertia
            elif self.state == STATE_RETREAT:
                score = WEIGHT_TARGET * (-to_nest) + inertia
            else:  # RAID: hacia el nido, en columna con el enjambre
                t_hunt = self._smell_hunt(automaton, ny, nx)
                score = (WEIGHT_TARGET * (to_nest + 1) / 2
                         + WEIGHT_HUNT * (t_hunt / (t_hunt + HUNT_TRAIL_K))
                         + inertia)

            score += config.WEIGHT_RANDOM * random.random()
            valid_moves.append((ny, nx))
            move_weights.append(max(0.001, score) ** 3)

        self.last_y, self.last_x = self.y, self.x
        self.y, self.x = random.choices(valid_moves, weights=move_weights, k=1)[0]

    @staticmethod
    def _inertia(dy, dx, heading):
        """Coseno entre el paso candidato y el rumbo anterior, por WEIGHT_INERTIA."""
        hy, hx = heading
        if not (hy or hx):
            return 0.0
        return WEIGHT_INERTIA * (dy * hy + dx * hx) / (math.hypot(dy, dx) * math.hypot(hy, hx))

    def _raid_nest(self, automaton):
        """STUB. Qué pasa cuando una marabunta llega al nido (robar crías, comida, etc.)."""
        return None