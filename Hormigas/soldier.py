import math
import random
import config

from .ant import Ant
from Automata.objects import NONE
from .marabunta import damage


STATE_PATROL = "PATROL"
STATE_ATTACK = "ATTACK"

# Parámetros. Pasarlos a config
PATROL_RADIUS = 12
ATTACK_ENTER_ALARM = 0.5
ATTACK_EXIT_ALARM = 0.1
ALARM_TRAIL_K = 2.0
DEPOSIT_AMOUNT_ALARM = 40.0
WEIGHT_ALARM_ATTRACT = 8.0
WEIGHT_PATROL_HOME = 3.0
WEIGHT_INERTIA = 1.5
SOLDIER_HEALTH = 10.0
SOLDIER_BITE = 2.0
WEIGHT_ENEMY = 8.0


class Soldier(Ant):
    CASTE = "SOLDIER"

    def __init__(self, y, x, nest_pos, agents=None):
        super().__init__(y, x, nest_pos, agents)
        self.health = SOLDIER_HEALTH
        self.enemy = None                 # marabunta más cercana a la vista (radio VISION_RADIUS)
        self.state = STATE_PATROL
        self.carried_resource = NONE

    def update_logic(self, automaton, occupied_mask):
        if not self.alive:
            return
        self.attacking = False
        self.consume_energy()
        if not self.alive:
            return
        p = self.percept = self.perceive(automaton)
        self.enemy = p.enemy
        self._evaluate_state(automaton, p)
        self._move(automaton, occupied_mask)

        if self.enemy is not None:                       # ve una amenaza: deja alarma para reclutar
            automaton.deposit_pheromone("alarma", self.y, self.x, DEPOSIT_AMOUNT_ALARM)
        if self.state == STATE_ATTACK:
            self._attack()

    def _evaluate_state(self, automaton, p):
        """Prioridad: huir del fuego > comer en el nido > atacar > energía baja > patrullar."""
        if p.fire_dist is not None and p.fire_dist <= config.FIRE_ALERT_RADIUS:
            self.state = config.STATE_FLEE
            return
        if self.state == config.STATE_FLEE:
            self.state = STATE_PATROL

        if p.at_nest:
            self.refuel_at_nest(automaton, config.REFUEL_BELOW)
            if self.state == config.STATE_FEED:
                self.state = STATE_PATROL

        alarm = p.alarm_here
        if self.enemy is not None:
            self.state = STATE_ATTACK
        elif self.state == STATE_ATTACK:
            if alarm < ATTACK_EXIT_ALARM:
                self.state = STATE_PATROL
        elif alarm > ATTACK_ENTER_ALARM:
            self.state = STATE_ATTACK

        has_food = automaton.colony.has_food()
        if self.state == config.STATE_FEED and not has_food:
            self.state = STATE_PATROL
        if self.state == STATE_PATROL and self.energy < config.LOW_ENERGY_THRESHOLD and has_food:
            self.state = config.STATE_FEED

    def _move(self, automaton, occupied_mask):
        # Ya pegada (ortogonalmente) a una marabunta: se queda peleando
        if self.state == STATE_ATTACK and self.enemy is not None and self.manhattan(self.enemy) <= 1:
            return

        all_neighbors = self.get_valid_neighbors(automaton.terrain.matrix, automaton.fire.matrix, occupied_mask)
        if not all_neighbors:
            return
        neighbors = self.allowed_neighbors(all_neighbors)

        home_angle = self.get_home_angle()
        heading = (self.y - self.last_y, self.x - self.last_x)
        d_nest = max(abs(self.y - self.nest_y), abs(self.x - self.nest_x))

        moves, weights = [], []
        for ny, nx, dy, dx in neighbors:
            home_alignment = math.cos(home_angle - math.atan2(dy, dx))
            inertia = self._inertia(dy, dx, heading)
            alarm = automaton.pheromones["alarma"].matrix[ny, nx]

            if self.state == STATE_ATTACK and self.enemy is not None:
                dist = abs(ny - self.enemy.y) + abs(nx - self.enemy.x)
                score = WEIGHT_ENEMY / (1.0 + dist)
            elif self.state == STATE_ATTACK:
                trail = alarm / (alarm + ALARM_TRAIL_K)
                score = WEIGHT_ALARM_ATTRACT * trail + 0.5 * inertia
            elif self.state == config.STATE_FLEE:
                heat = self.fire_heat(automaton, ny, nx)
                score = config.WEIGHT_FLEE * (1.0 - heat) + 0.5 * inertia
            elif self.state == config.STATE_FEED:
                score = config.WEIGHT_HOME * home_alignment
            else:  # PATROL
                over = max(0.0, d_nest / PATROL_RADIUS - 1.0)
                score = WEIGHT_PATROL_HOME * over * home_alignment + inertia

            score += config.WEIGHT_RANDOM * random.random()
            moves.append((ny, nx))
            weights.append(max(0.001, score) ** 3)

        self.commit_move(*random.choices(moves, weights=weights, k=1)[0])

    @staticmethod
    def _inertia(dy, dx, heading):
        hy, hx = heading
        if not (hy or hx):
            return 0.0
        return WEIGHT_INERTIA * (dy * hy + dx * hx) / (math.hypot(dy, dx) * math.hypot(hy, hx))

    def _attack(self):
        """Muerde a la marabunta si está en una celda ortogonalmente vecina."""
        e = self.enemy
        if e is not None and self.manhattan(e) <= 1:
            self.face_towards(e)
            self.attacking = True
            damage(e, SOLDIER_BITE)
            if not e.alive:
                self.enemy = None