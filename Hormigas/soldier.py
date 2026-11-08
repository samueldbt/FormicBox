import math
import random
import config

from .ant import Ant
from Automata.objects import NONE
from .marabunta import damage


STATE_PATROL = "PATROL"
STATE_ATTACK = "ATTACK"

# Parámetros. Pasarlos a config
PATROL_RADIUS = 12            # distancia máxima al nido al patrullar (celdas)
ATTACK_ENTER_ALARM = 0.5      # alarma en su celda a partir de la cual pasa a ATTACK
ATTACK_EXIT_ALARM = 0.1       # alarma por debajo de la cual deja de atacar
ALARM_TRAIL_K = 2.0           # saturación del rastro de alarma: t / (t + K)
FIRE_ALERT_RADIUS = 2         # radio (celdas) en el que el fuego la hace huir
DEPOSIT_AMOUNT_ALARM = 40.0   # alarma que deja al detectar una amenaza
WEIGHT_ALARM_ATTRACT = 8.0    # atracción hacia la alarma (en ATTACK)
WEIGHT_PATROL_HOME = 3.0      # fuerza que la devuelve al nido al pasarse del radio
WEIGHT_INERTIA = 1.5          # preferencia por seguir el rumbo
WEIGHT_FLEE = 10.0            # fuerza de la huida del fuego
SOLDIER_HEALTH = 10.0         # vida de la soldada (las marabuntas la muerden)
SOLDIER_BITE = 2.0            # daño por mordida de la soldada
THREAT_SENSE_RADIUS = 4       # a cuántas celdas ve una marabunta
WEIGHT_ENEMY = 8.0            # atracción hacia la marabunta vista


class Soldier(Ant):
    CASTE = "SOLDIER"

    def __init__(self, y, x, nest_pos, agents=None):
        """Inicializa una soldada. agents: lista compartida con todos los agentes (para ver marabuntas)."""
        super().__init__(y, x, nest_pos)
        self.health = SOLDIER_HEALTH
        self.agents = agents if agents is not None else []
        self.enemy = None                 # marabunta más cercana a la vista
        self.state = STATE_PATROL
        self.carried_resource = NONE      # la interfaz dibuja según este atributo

        self.last_y = y
        self.last_x = x

    def update_logic(self, automaton, occupied_mask):
        """Evalúa el estado, se mueve y, si detecta una amenaza, deja feromona de alarma."""
        if not self.alive:
            return
        self.attacking = False
        self.consume_energy()
        self.enemy = self._nearest_enemy()
        self._evaluate_state(automaton)
        self._move(automaton, occupied_mask)

        if self._detect_threat(automaton):
            automaton.deposit_pheromone("alarma", self.y, self.x, DEPOSIT_AMOUNT_ALARM)
        if self.state == STATE_ATTACK:
            self._attack(automaton)

    def _evaluate_state(self, automaton):
        """Prioridad: huir del fuego > atacar la alarma > recargar energía > patrullar."""
        # 1. Fuego cerca: huir
        if self._fire_near(automaton, self.y, self.x) > 0:
            self.state = config.STATE_FLEE
            return
        if self.state == config.STATE_FLEE:
            self.state = STATE_PATROL

        # 2. En el nido: recargar
        if (self.y, self.x) == (self.nest_y, self.nest_x):
            self.energy = config.MAX_ENERGY
            if self.state == config.STATE_FEED:
                self.state = STATE_PATROL

        alarm = automaton.pheromones["alarma"].matrix[self.y, self.x]
        if self.enemy is not None:
            self.state = STATE_ATTACK
        elif self.state == STATE_ATTACK:
            if alarm < ATTACK_EXIT_ALARM:
                self.state = STATE_PATROL
        elif alarm > ATTACK_ENTER_ALARM:
            self.state = STATE_ATTACK

        # 4. Energía baja: volver al nido
        if self.state == STATE_PATROL and self.energy < config.LOW_ENERGY_THRESHOLD:
            self.state = config.STATE_FEED

    @staticmethod
    def _fire_near(automaton, y, x, radius=FIRE_ALERT_RADIUS):
        """Cantidad de celdas en llamas dentro del cuadrado de lado 2*radius+1 centrado en (y, x)."""
        h, w = automaton.fire.matrix.shape
        y0, y1 = max(0, y - radius), min(h, y + radius + 1)
        x0, x1 = max(0, x - radius), min(w, x + radius + 1)
        return int((automaton.fire.matrix[y0:y1, x0:x1] > 0).sum())

    def _move(self, automaton, occupied_mask):
        """Elige la celda vecina con la misma ecuación P de Worker: puntaje, cubo y sorteo."""
        # Ya pegada (ortogonalmente) a una marabunta: se queda peleando
        if self.state == STATE_ATTACK and self.enemy is not None and self.manhattan(self.enemy) <= 1:
            return

        all_neighbors = self.get_valid_neighbors(automaton.terrain.matrix, automaton.fire.matrix, occupied_mask)
        if not all_neighbors:
            return

        neighbors = [(ny, nx, dy, dx) for ny, nx, dy, dx in all_neighbors
                     if (ny, nx) != (self.last_y, self.last_x) or len(all_neighbors) == 1]

        home_angle = self.get_home_angle()
        heading = (self.y - self.last_y, self.x - self.last_x)
        d_nest = max(abs(self.y - self.nest_y), abs(self.x - self.nest_x))

        valid_moves = []
        move_weights = []
        for ny, nx, dy, dx in neighbors:
            move_angle = math.atan2(dy, dx)
            home_alignment = math.cos(home_angle - move_angle)
            inertia = self._inertia(dy, dx, heading)
            alarm = automaton.pheromones["alarma"].matrix[ny, nx]

            if self.state == STATE_ATTACK and self.enemy is not None:
                dist = abs(ny - self.enemy.y) + abs(nx - self.enemy.x)
                score = WEIGHT_ENEMY / (1.0 + dist)
            elif self.state == STATE_ATTACK:
                trail = alarm / (alarm + ALARM_TRAIL_K)
                score = WEIGHT_ALARM_ATTRACT * trail + 0.5 * inertia
            elif self.state == config.STATE_FLEE:
                # Prefiere las celdas con menos fuego alrededor
                heat = self._fire_near(automaton, ny, nx) / float((2 * FIRE_ALERT_RADIUS + 1) ** 2)
                score = WEIGHT_FLEE * (1.0 - heat) + 0.5 * inertia
            elif self.state == config.STATE_FEED:
                score = config.WEIGHT_HOME * home_alignment
            else:  # PATROL: paseo con inercia que no se aleja demasiado del nido
                over = max(0.0, d_nest / PATROL_RADIUS - 1.0)
                score = WEIGHT_PATROL_HOME * over * home_alignment + inertia

            score += config.WEIGHT_RANDOM * random.random()
            valid_moves.append((ny, nx))
            move_weights.append(max(0.001, score) ** 3)

        self.last_y, self.last_x = self.y, self.x
        self.y, self.x = random.choices(valid_moves, weights=move_weights, k=1)[0]

    @staticmethod
    def _inertia(dy, dx, heading):
        hy, hx = heading
        if not (hy or hx):
            return 0.0
        return WEIGHT_INERTIA * (dy * hy + dx * hx) / (math.hypot(dy, dx) * math.hypot(hy, hx))

    def _nearest_enemy(self):
        """Marabunta viva más cercana dentro de THREAT_SENSE_RADIUS, o None."""
        best, best_d = None, THREAT_SENSE_RADIUS + 1
        for ag in self.agents:
            if getattr(ag, "CASTE", None) != "MARABUNTA" or not getattr(ag, "alive", True):
                continue
            d = max(abs(ag.y - self.y), abs(ag.x - self.x))
            if d < best_d:
                best, best_d = ag, d
        return best

    def _detect_threat(self, automaton):
        """True si ve una marabunta (entonces deja alarma para reclutar)."""
        return self.enemy is not None

    def _attack(self, automaton):
        """Muerde a la marabunta si está en una celda ortogonalmente vecina."""
        e = self.enemy
        if e is not None and self.manhattan(e) <= 1:
            self.face_towards(e)
            self.attacking = True
            damage(e, SOLDIER_BITE)
            if not e.alive:
                self.enemy = None