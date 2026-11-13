import math
import random
import config
import reglas

from .ant import Ant
from Automata.objects import NONE, GRASS, MANGO, BOCADILLO


class Worker(Ant):
    CASTE = "WORKER"

    def __init__(self, y, x, nest_pos, agents=None):
        super().__init__(y, x, nest_pos, agents)
        self.carried_resource = NONE
        self.trail = 0.0          # fuerza del rastro que deja al volver (1.0 al tomar, x0.97 por paso)
        self._ignore = set()

    # ------------------------------------------------------------ tick
    def update_logic(self, automaton, occupied_mask):
        if not self.alive:
            return
        self.consume_energy()
        if not self.alive:
            return
        self._ignore = self._ignored_kinds(automaton)
        p = self.percept = self.perceive(automaton, self._ignore)
        self._update_memory(automaton, p)
        self._evaluate_state(automaton, p)
        self._move(automaton, occupied_mask, p)

        if self.state == config.STATE_RETURN and self.carried_resource != NONE:
            self._deposit_pheromones(automaton)

    def _ignored_kinds(self, automaton):
        """Con el hongo estresado (demasiado azúcar) ignoran el bocadillo, salvo que tengan hambre."""
        if automaton.colony.is_stressed() and self.energy >= config.LOW_ENERGY_THRESHOLD:
            return {BOCADILLO}
        return set()

    # ------------------------------------------------------------ memoria de recurso
    def _update_memory(self, automaton, p):
        if p.resource is not None:
            self.mem_target = (p.resource[0], p.resource[1])
            self.mem_ttl = config.MEMORY_TICKS
        elif self.mem_target is not None:
            self.mem_ttl -= 1
            ty, tx = self.mem_target
            visible = max(abs(ty - self.y), abs(tx - self.x)) <= config.VISION_RADIUS
            if self.mem_ttl <= 0 or (visible and automaton.objects.matrix[ty, tx] == NONE):
                self.mem_target = None

    # ------------------------------------------------------------ transición δ (tabla de reglas)
    def _evaluate_state(self, automaton, p):
        for name in reglas.WORKER_RULES:
            rule = getattr(self, "_rule_" + name.lower(), None)
            if rule is None:
                raise ValueError(f"reglas.py: regla desconocida {name!r}")
            if rule(automaton, p):
                return

    def _rule_flee(self, automaton, p):
        fire_close = p.fire_dist is not None and p.fire_dist <= config.FIRE_ALERT_RADIUS
        if p.alarm_here > 0.5 or fire_close:
            self.state = config.STATE_FLEE
            return True
        if self.state == config.STATE_FLEE:
            self.state = config.STATE_RETURN if self.carried_resource != NONE else config.STATE_EXPLORE
        return False

    def _rule_refuel_nest(self, automaton, p):
        if not p.at_nest:
            return False
        if self.carried_resource != NONE:
            automaton.colony.deliver(self.carried_resource)
            self.carried_resource = NONE
        self.trail = 0.0
        self.refuel_at_nest(automaton, config.REFUEL_BELOW)
        self.state = config.STATE_EXPLORE
        return True

    def _rule_eat_map(self, automaton, p):
        if (p.resource_here == BOCADILLO and self.carried_resource == NONE
                and self.energy < config.EAT_MAP_BELOW):
            automaton.objects.consume(self.y, self.x)        # una mordida
            self.energy = min(config.MAX_ENERGY, self.energy + config.ENERGY_PER_FOOD["BOCADILLO"])
            if self.state == config.STATE_FEED:
                self.state = config.STATE_EXPLORE
            return True
        return False

    def _rule_pickup(self, automaton, p):
        kind = p.resource_here
        if (self.carried_resource == NONE and kind != NONE and kind not in self._ignore
                and self.state == config.STATE_EXPLORE):
            if kind == GRASS and p.resource is not None and p.resource[2] == MANGO:
                return False          # hay un mango a la vista: no se conforma con el pasto
            self.carried_resource = int(kind)
            self.trail = 1.0
            self.state = config.STATE_RETURN
            automaton.objects.consume(self.y, self.x)        # pasto 2->1->vacío, mango/bocadillo -1 mordida
            return True
        return False

    def _rule_go_feed(self, automaton, p):
        if self.carried_resource != NONE or self.state not in (config.STATE_EXPLORE, config.STATE_FEED):
            return False
        if self.energy < config.LOW_ENERGY_THRESHOLD and automaton.colony.has_food():
            self.state = config.STATE_FEED
            return True
        if self.state == config.STATE_FEED:      # ya no hace falta (o no hay reservas): a buscar comida
            self.state = config.STATE_EXPLORE
        return False

    def _rule_explore(self, automaton, p):
        if self.state not in (config.STATE_RETURN, config.STATE_FEED, config.STATE_FLEE):
            self.state = config.STATE_EXPLORE
        return True

    # ------------------------------------------------------------ salida λ: movimiento
    def _move(self, automaton, occupied_mask, p):
        all_neighbors = self.get_valid_neighbors(automaton.terrain.matrix, automaton.fire.matrix, occupied_mask)
        if not all_neighbors:
            return
        neighbors = self.allowed_neighbors(all_neighbors)

        home_angle = self.get_home_angle()
        heading = (self.y - self.last_y, self.x - self.last_x)
        ph = automaton.pheromones
        sugar_ok = BOCADILLO not in self._ignore
        has_food = automaton.colony.has_food()
        exploring = self.state == config.STATE_EXPLORE or (self.state == config.STATE_FEED and not has_food)
        t_here = float(ph["vegetal"].matrix[self.y, self.x]
                       + (ph["azucar"].matrix[self.y, self.x] if sugar_ok else 0.0))

        moves, weights = [], []
        for ny, nx, dy, dx in neighbors:
            home_alignment = math.cos(home_angle - math.atan2(dy, dx))
            t_veg = float(ph["vegetal"].matrix[ny, nx])
            t_sug = float(ph["azucar"].matrix[ny, nx])
            t_alarm = float(ph["alarma"].matrix[ny, nx])
            r_fire = 1.0 if automaton.fire.matrix[ny, nx] > 0 else 0.0

            if exploring:
                score = self._score_explore(ny, nx, dy, dx, t_veg, t_sug, t_here, home_alignment, heading, sugar_ok)
            elif self.state == config.STATE_FEED:
                score = config.WEIGHT_HOME * home_alignment + (config.WEIGHT_SUGAR * 2.0 * t_sug if sugar_ok else 0.0)
            elif self.state == config.STATE_RETURN:
                score = config.WEIGHT_HOME * home_alignment
            else:  # FLEE: lejos del fuego y hacia el nido
                heat = self.fire_heat(automaton, ny, nx)
                score = config.WEIGHT_FLEE * (1.0 - heat) + 0.5 * config.WEIGHT_HOME * home_alignment

            score += -(config.WEIGHT_ALARM * t_alarm) - (config.WEIGHT_FIRE * r_fire) \
                     + config.WEIGHT_RANDOM * random.random()
            moves.append((ny, nx))
            weights.append(max(0.001, score) ** 3)

        self.commit_move(*random.choices(moves, weights=weights, k=1)[0])

    def _score_explore(self, ny, nx, dy, dx, t_veg, t_sug, t_here, home_alignment, heading, sugar_ok):
        """Puntaje de una celda vecina al explorar: rastro saturado + subir la pendiente
        + inercia + empuje de salida + atracción al recurso visto/recordado."""
        K = config.EXPLORE_TRAIL_K
        ws = config.WEIGHT_SUGAR if sugar_ok else 0.0
        t_sug = t_sug if sugar_ok else 0.0

        rastro = config.WEIGHT_VEGETAL * (t_veg / (t_veg + K)) + ws * (t_sug / (t_sug + K))
        t_new = t_veg + t_sug
        K = config.EXPLORE_TRAIL_K
        ws = config.WEIGHT_SUGAR if sugar_ok else 0.0
        t_sug = t_sug if sugar_ok else 0.0

        rastro = config.WEIGHT_VEGETAL * (t_veg / (t_veg + K)) + ws * (t_sug / (t_sug + K))
        t_new = t_veg + t_sug
        rastro += config.TRAIL_CLIMB * (t_new - t_here) / (t_new + t_here + 0.02)   # -1..1: sube o baja la pendient

        hy, hx = heading
        if hy or hx:
            inercia = config.EXPLORE_INERTIA * (dy * hy + dx * hx) / (math.hypot(dy, dx) * math.hypot(hy, hx))
        else:
            inercia = 0.0

        afuera = -home_alignment
        d_nido = max(abs(ny - self.nest_y), abs(nx - self.nest_x))
        puerta = config.EXPLORE_DOOR_PUSH * max(0.0, 1.0 - d_nido / config.EXPLORE_DOOR_RADIUS) * afuera

        objetivo = 0.0
        if self.mem_target is not None:
            ty, tx = self.mem_target
            d_now = abs(self.y - ty) + abs(self.x - tx)
            d_new = abs(ny - ty) + abs(nx - tx)
            objetivo = config.WEIGHT_RESOURCE * (d_now - d_new + 1.0) / 2.0   # 1 si se acerca, 0 si se aleja

        return rastro + inercia + puerta + objetivo

    # ------------------------------------------------------------ salida λ: feromona
    def _deposit_pheromones(self, automaton):
        """Rastro con dirección: deja `trail` (1.0 al salir del recurso) y lo multiplica por 0.97 en cada paso."""
        if self.carried_resource == GRASS:
            automaton.deposit_pheromone("vegetal", self.y, self.x, config.DEPOSIT_AMOUNT_GRASS * self.trail)
        elif self.carried_resource == MANGO:
            automaton.deposit_pheromone("vegetal", self.y, self.x, config.DEPOSIT_AMOUNT_MANGO * self.trail)
        elif self.carried_resource == BOCADILLO:
            automaton.deposit_pheromone("azucar", self.y, self.x, config.DEPOSIT_AMOUNT_BOCADILLO * self.trail)
        self.trail *= config.TRAIL_DECAY