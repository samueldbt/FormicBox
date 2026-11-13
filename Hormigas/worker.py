import math
import config
import reglas

from .ant import Ant
from Automata.objects import NONE, GRASS, MANGO, BOCADILLO


class Worker(Ant):
    CASTE = "WORKER"

    def __init__(self, y, x, nest_pos, agents=None):
        super().__init__(y, x, nest_pos, agents)
        self.carried_resource = NONE
        self.trail = 0.0          # fuerza del rastro al volver (1.0 al tomar, decae por paso)
        self.clean_last = 0.0
        self._ignore = set()
        # Memoria de ruta
        self.route = []           # celdas del regreso (fuente -> nido), se llena al volver con carga
        self.route_out = []       # ruta de ida (nido -> fuente), para repetirla tras entregar
        self.route_idx = {}       # celda -> posición en route_out
        self.route_pos = 0
        self.route_lost = 0

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
        self._update_route_pos()
        self._evaluate_state(automaton, p)
        self._move(automaton, occupied_mask, p)

        if self.state == config.STATE_RETURN and self.carried_resource != NONE:
            self._record_route()
            self._deposit_pheromones(automaton)

    def _ignored_kinds(self, automaton):
        """Con el hongo estresado (demasiado azúcar) ignoran el bocadillo, salvo que tengan hambre."""
        if automaton.colony.is_stressed() and self.energy >= config.EAT_MAP_FRACTION * self.max_energy:
            return {BOCADILLO}
        return set()

    # ------------------------------------------------------------ memoria de recurso
    def _update_memory(self, automaton, p):
        if p.resource is not None:
            self.mem_target = (p.resource[0], p.resource[1])
            self.mem_ttl = config.MEMORY_TICKS
        elif p.resource_here != NONE and p.resource_here not in self._ignore:
            self.mem_target = (self.y, self.x)
            self.mem_ttl = config.MEMORY_TICKS
        elif self.mem_target is not None:
            self.mem_ttl -= 1
            ty, tx = self.mem_target
            visible = max(abs(ty - self.y), abs(tx - self.x)) <= config.VISION_RADIUS
            if self.mem_ttl <= 0 or (visible and automaton.objects.matrix[ty, tx] == NONE):
                self.mem_target = None

    # ------------------------------------------------------------ memoria de ruta
    def _record_route(self):
        """Anota el regreso. Si pisa una celda que ya estaba, borra el bucle."""
        if not config.ROUTE_MEMORY:
            return
        cell = (self.y, self.x)
        if cell in self.route:
            del self.route[self.route.index(cell) + 1:]
        elif len(self.route) < config.ROUTE_MAX_LEN:
            self.route.append(cell)

    def _store_route(self):
        """Al entregar: la ruta de ida es el regreso al revés (nido -> fuente)."""
        if config.ROUTE_MEMORY and len(self.route) >= 2:
            self.route_out = list(reversed(self.route))
            self.route_idx = {c: i for i, c in enumerate(self.route_out)}
            self.route_pos = 0
            self.route_lost = 0
        else:
            self._drop_route()
        self.route = []

    def _drop_route(self):
        self.route_out, self.route_idx = [], {}
        self.route_pos = self.route_lost = 0

    def _update_route_pos(self):
        if not self.route_out:
            return
        if self.state in (config.STATE_FEED, config.STATE_FLEE, config.STATE_RETURN, config.STATE_CLEAN):
            self._drop_route()
            return
        i = self.route_idx.get((self.y, self.x))
        if i is not None and i > self.route_pos:
            self.route_pos = i
        if self.route_pos >= len(self.route_out) - 1:       # llegó a la fuente
            self._drop_route()

    def _route_next(self, neighbors):
        """Vecino que sigue la ruta (hasta ROUTE_LOOKAHEAD celdas adelante), o None."""
        if not self.route_out:
            return None
        best, best_i = None, self.route_pos
        for ny, nx, dy, dx in neighbors:
            i = self.route_idx.get((ny, nx))
            if i is not None and best_i < i <= self.route_pos + config.ROUTE_LOOKAHEAD:
                best, best_i = (ny, nx), i
        if best is None:
            self.route_lost += 1
            if self.route_lost > config.ROUTE_LOST_TICKS:
                self._drop_route()
        else:
            self.route_lost = 0
        return best

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
            self._store_route()
        self.trail = 0.0
        self.refuel_at_nest(automaton)
        self.state = config.STATE_EXPLORE
        return True

    def _rule_eat_map(self, automaton, p):
        if (p.resource_here == BOCADILLO and self.carried_resource == NONE
                and self.energy < config.EAT_MAP_FRACTION * self.max_energy):
            automaton.objects.consume(self.y, self.x)        # una mordida
            self.energy = min(self.max_energy,
                              self.energy + config.ENERGY_PER_UNIT * config.FOOD_VALUE["BOCADILLO"])
            if self.state in (config.STATE_FEED, config.STATE_CLEAN):
                self.state = config.STATE_EXPLORE
            return True
        return False

    def _rule_pickup(self, automaton, p):
        kind = p.resource_here
        if (self.carried_resource == NONE and kind != NONE and kind not in self._ignore
                and self.state == config.STATE_EXPLORE):
            best = p.resource
            if (best is not None and best[3] <= config.PREFER_BETTER_DIST
                    and config.food_value(best[2]) > config.food_value(kind)):
                return False          # hay algo de más valor cerca: no se conforma con esto
            self.carried_resource = int(kind)
            self.trail = 1.0
            self._drop_route()
            self.route = [(self.y, self.x)]       # el regreso empieza en la fuente
            self.state = config.STATE_RETURN
            automaton.objects.consume(self.y, self.x)
            return True
        return False

    def _rule_go_feed(self, automaton, p):
        if self.carried_resource != NONE or self.state not in (
                config.STATE_EXPLORE, config.STATE_FEED, config.STATE_CLEAN):
            return False
        if self.low_energy(automaton) and automaton.colony.has_food():
            self.state = config.STATE_FEED
            return True
        if self.state == config.STATE_FEED:
            self.state = config.STATE_EXPLORE
        return False

    # ---- limpieza de callejones: retrocede borrando el rastro cuyo recurso ya se acabó
    def _trail_at(self, automaton, y, x):
        ph = automaton.pheromones
        v = float(ph["vegetal"].matrix[y, x])
        if BOCADILLO not in self._ignore:
            v += float(ph["azucar"].matrix[y, x])
        return v

    def _at_tip(self, automaton, here):
        """Punta real del rastro: supera a sus 8 vecinos por CLEAN_TIP_MARGIN.
        Un rastro plano, o uno que sigue hacia los lados o en diagonal, NO cuenta."""
        if here < config.CLEAN_MIN_TRAIL:
            return False
        h, w = automaton.terrain.matrix.shape
        top = 0.0
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                ny, nx = self.y + dy, self.x + dx
                if (dy or dx) and 0 <= ny < h and 0 <= nx < w:
                    top = max(top, self._trail_at(automaton, ny, nx))
        return here >= config.CLEAN_TIP_MARGIN * top

    def _rule_clean(self, automaton, p):
        if not config.CLEAN_DEAD_TRAILS:
            if self.state == config.STATE_CLEAN:
                self.state = config.STATE_EXPLORE
            return False
        if self.state == config.STATE_CLEAN:
            if p.resource is not None or p.resource_here != NONE:      # apareció comida: a recogerla
                self.state = config.STATE_EXPLORE
                return False
            return True                                                # el paso lo da _clean_step (en _move)
        if (self.state == config.STATE_EXPLORE and self.carried_resource == NONE
                and p.resource is None and p.resource_here == NONE
                and self.mem_target is None and not self.route_out):
            if self._at_tip(automaton, self._trail_at(automaton, self.y, self.x)):
                self.state = config.STATE_CLEAN
                self.clean_last = 0.0
                return True
        return False

    def _clean_step(self, automaton, neighbors):
        """Borra el rastro de esta celda y retrocede hacia el vecino con más rastro. False = termina."""
        here = self._trail_at(automaton, self.y, self.x)
        if self.clean_last > 0 and here > self.clean_last * 1.02:   # el rastro sube: es otro camino vivo
            self.state, self.clean_last = config.STATE_EXPLORE, 0.0
            return False
        for name in ("vegetal", "azucar"):
            automaton.pheromones[name].matrix[self.y, self.x] = 0.0
        best, best_v = None, config.CLEAN_STOP_TRAIL
        for ny, nx, dy, dx in neighbors:
            v = self._trail_at(automaton, ny, nx)
            if v > best_v:
                best, best_v = (ny, nx), v
        if best is None:
            self.state, self.clean_last = config.STATE_EXPLORE, 0.0
            return False
        self.clean_last = here
        self.commit_move(*best)
        return True

    def _rule_explore(self, automaton, p):
        if self.state not in (config.STATE_RETURN, config.STATE_FEED, config.STATE_FLEE, config.STATE_CLEAN):
            self.state = config.STATE_EXPLORE
        return True

    # ------------------------------------------------------------ salida λ: movimiento
    def _move(self, automaton, occupied_mask, p):
        all_neighbors = self.get_valid_neighbors(automaton.terrain.matrix, automaton.fire.matrix, occupied_mask)
        if not all_neighbors:
            return
        if self.state == config.STATE_CLEAN and self._clean_step(automaton, all_neighbors):
            return
        neighbors = self.allowed_neighbors(all_neighbors)

        home_angle = self.get_home_angle()
        d_cur = self.dist_home(automaton, self.y, self.x)
        heading = (self.y - self.last_y, self.x - self.last_x)
        ph = automaton.pheromones
        sugar_ok = BOCADILLO not in self._ignore
        has_food = automaton.colony.has_food()
        exploring = self.state == config.STATE_EXPLORE or (self.state == config.STATE_FEED and not has_food)
        t_here = float(ph["vegetal"].matrix[self.y, self.x]
                       + (ph["azucar"].matrix[self.y, self.x] if sugar_ok else 0.0))
        route_next = self._route_next(neighbors) if self.state == config.STATE_EXPLORE else None

        moves, scores = [], []
        for ny, nx, dy, dx in neighbors:
            align = self.home_align(automaton, ny, nx, dy, dx, d_cur, home_angle)
            t_veg = float(ph["vegetal"].matrix[ny, nx])
            t_sug = float(ph["azucar"].matrix[ny, nx])
            t_alarm = float(ph["alarma"].matrix[ny, nx])
            r_fire = 1.0 if automaton.fire.matrix[ny, nx] > 0 else 0.0

            if exploring:
                score = self._score_explore(ny, nx, dy, dx, t_veg, t_sug, t_here, align, heading, sugar_ok,
                                            (ny, nx) == route_next)
            elif self.state in (config.STATE_FEED, config.STATE_RETURN):
                score = config.WEIGHT_HOME * (align + 1.0) / 2.0
            else:  # FLEE: lejos del fuego y hacia el nido
                heat = self.fire_heat(automaton, ny, nx)
                score = config.WEIGHT_FLEE * (1.0 - heat) + 0.5 * config.WEIGHT_HOME * (align + 1.0) / 2.0

            score += -(config.WEIGHT_ALARM * t_alarm) - (config.WEIGHT_FIRE * r_fire) + self.noise()
            moves.append((ny, nx))
            scores.append(score)

        self.commit_move(*self.pick_move(moves, scores))

    def _score_explore(self, ny, nx, dy, dx, t_veg, t_sug, t_here, align, heading, sugar_ok, on_route):
        """Rastro saturado + subir la pendiente + inercia + empuje de salida + recurso + ruta recordada."""
        K = config.EXPLORE_TRAIL_K
        ws = config.WEIGHT_SUGAR if sugar_ok else 0.0
        t_sug = t_sug if sugar_ok else 0.0

        rastro = config.WEIGHT_VEGETAL * (t_veg / (t_veg + K)) + ws * (t_sug / (t_sug + K))

        # Pendiente normalizada: una subida de (1 - TRAIL_DECAY) por celda cuenta como +1, una bajada como -1
        t_new = t_veg + t_sug
        top = max(t_new, t_here, 0.02)
        climb = (t_new - t_here) / (top * (1.0 - config.TRAIL_DECAY) + 1e-6)
        rastro += config.TRAIL_CLIMB * max(-1.0, min(1.0, climb))
        rastro = max(0.0, rastro)

        hy, hx = heading
        if hy or hx:
            inercia = config.EXPLORE_INERTIA * (dy * hy + dx * hx) / (math.hypot(dy, dx) * math.hypot(hy, hx))
        else:
            inercia = 0.0

        afuera = -align
        d_nido = max(abs(ny - self.nest_y), abs(nx - self.nest_x))
        puerta = config.EXPLORE_DOOR_PUSH * max(0.0, 1.0 - d_nido / config.EXPLORE_DOOR_RADIUS) * afuera

        objetivo = 0.0
        if self.mem_target is not None:
            ty, tx = self.mem_target
            d_now = abs(self.y - ty) + abs(self.x - tx)
            d_new = abs(ny - ty) + abs(nx - tx)
            objetivo = config.WEIGHT_RESOURCE * (d_now - d_new + 1.0) / 2.0

        ruta = config.ROUTE_BONUS if on_route else 0.0
        return rastro + inercia + puerta + objetivo + ruta

    # ------------------------------------------------------------ salida λ: feromona
    def _deposit_pheromones(self, automaton):
        """Rastro con dirección. El decaimiento por paso es TRAIL_DECAY * (1 - evaporación del campo):
        así la pendiente NETA por celda es exactamente TRAIL_DECAY, sin que la evaporación la borre."""
        kind = self.carried_resource
        if kind == GRASS:
            name, amount = "vegetal", config.DEPOSIT_AMOUNT_GRASS
        elif kind == MANGO:
            name, amount = "vegetal", config.DEPOSIT_AMOUNT_MANGO
        elif kind == BOCADILLO:
            name, amount = "azucar", config.DEPOSIT_AMOUNT_BOCADILLO
        else:
            return
        automaton.deposit_pheromone(name, self.y, self.x, amount * self.trail)
        self.trail *= config.TRAIL_DECAY * (1.0 - automaton.pheromones[name].evap_rate)