import math
import random
import numpy as np
import config

from .ant import Ant
from Automata.objects import NONE
from Automata.terrain import DIRT


STATE_RAID = "RAID"
STATE_ATTACK = "ATTACK"
STATE_RETREAT = "RETREAT"


def damage(target, amount):
    """Quita vida a un agente. Al llegar a 0 muere por pelea (Ant.die)."""
    target.health -= amount
    if target.health <= 0:
        target.die("FIGHT")


class Marabunta(Ant):
    CASTE = "MARABUNTA"

    def __init__(self, y, x, nest_pos, agents=None):
        """nest_pos: el nido de la colonia que atacan. agents: lista compartida (para ver presas)."""
        super().__init__(y, x, nest_pos, agents)
        self.state = STATE_RAID
        self.carried_resource = NONE
        self.health = config.MARA_HEALTH
        self.prey = None
        self.raid_ticks = 0
        self.kills = 0

    # ------------------------------------------------------------ aparición
    @staticmethod
    def spawn_cells(automaton, n):
        """Celdas de aparición: el borde del mapa MÁS CERCANO al nido (por camino) que quede a
        SWARM_MIN_DIST o más. Si el borde no alcanza para n, completa con las celdas interiores más cercanas."""
        a = automaton
        dist = a.home_dist
        walk = (a.terrain.matrix == DIRT) & np.isfinite(dist)
        edge = np.zeros(walk.shape, dtype=bool)
        edge[0, :] = edge[-1, :] = True
        edge[:, 0] = edge[:, -1] = True
        want = max(n, config.SWARM_POOL)

        pool = []
        for mask, limit in ((walk & edge, want), (walk, n)):
            if len(pool) >= limit:
                continue
            ys, xs = np.nonzero(mask & (dist >= config.SWARM_MIN_DIST))
            for i in np.argsort(dist[ys, xs], kind="stable").tolist():
                c = (int(ys[i]), int(xs[i]))
                if c not in pool:
                    pool.append(c)
                if len(pool) >= limit:
                    break
        if not pool:                           # mapa chico: la celda alcanzable más lejana
            ys, xs = np.nonzero(walk)
            if len(ys):
                i = int(np.argmax(dist[ys, xs]))
                pool = [(int(ys[i]), int(xs[i]))]
            else:
                pool = [tuple(int(v) for v in a.terrain.nest_pos)]
        return pool

    @staticmethod
    def spawn_position(automaton):
        return random.choice(Marabunta.spawn_cells(automaton, 1))

    # ------------------------------------------------------------ tick
    def update_logic(self, automaton, occupied_mask):
        if not self.alive:
            return
        self.attacking = False
        self.raid_ticks += 1
        self._evaluate_state(automaton)
        self._move(automaton, occupied_mask)

        if self.state in (STATE_RAID, STATE_ATTACK):
            automaton.deposit_pheromone("caza", self.y, self.x, config.MARA_DEPOSIT_HUNT)
        if self.state == STATE_ATTACK:
            self._bite()
        if (self.y, self.x) == (self.nest_y, self.nest_x):
            self._raid_nest(automaton)

    def _evaluate_state(self, automaton):
        """Prioridad: huir del fuego > retirarse > atacar presa cercana > avanzar."""
        if self._fire_near(automaton, self.y, self.x) > 0:
            self.state = config.STATE_FLEE
            self.prey = None
            return
        if self.state == STATE_RETREAT:
            return
        if self.health < config.MARA_RETREAT_HEALTH or self.raid_ticks > config.MARA_MAX_RAID_TICKS:
            self.state = STATE_RETREAT
            self.prey = None
            return
        self.prey = self._find_prey()
        self.state = STATE_ATTACK if self.prey is not None else STATE_RAID

    def _find_prey(self):
        """Hormiga viva de la colonia más cercana dentro de MARA_SENSE_RADIUS, o None."""
        best, best_d = None, config.MARA_SENSE_RADIUS + 1
        for ag in self.agents:
            if getattr(ag, "CASTE", None) == self.CASTE or not getattr(ag, "alive", True):
                continue
            d = max(abs(ag.y - self.y), abs(ag.x - self.x))
            if d < best_d:
                best, best_d = ag, d
        return best

    def _bite(self):
        p = self.prey
        if p is None or self.manhattan(p) > 1:
            return
        self.face_towards(p)
        self.attacking = True
        damage(p, config.MARA_BITE)
        if not getattr(p, "alive", True):
            self.kills += 1
            self.prey = None

    @staticmethod
    def _fire_near(automaton, y, x, radius=None):
        radius = config.FIRE_ALERT_RADIUS if radius is None else radius
        h, w = automaton.fire.matrix.shape
        y0, y1 = max(0, y - radius), min(h, y + radius + 1)
        x0, x1 = max(0, x - radius), min(w, x + radius + 1)
        return int((automaton.fire.matrix[y0:y1, x0:x1] > 0).sum())

    @staticmethod
    def _smell_hunt(automaton, y, x, radius=None):
        radius = config.MARA_HUNT_RADIUS if radius is None else radius
        m = automaton.pheromones["caza"].matrix
        h, w = m.shape
        return float(m[max(0, y - radius):min(h, y + radius + 1), max(0, x - radius):min(w, x + radius + 1)].sum())

    def _move(self, automaton, occupied_mask):
        """Ciegas, pero huelen el nido (distancia real por camino) y el rastro de su enjambre."""
        if self.state == STATE_ATTACK and self.prey is not None and self.manhattan(self.prey) <= 1:
            return

        all_neighbors = self.get_valid_neighbors(automaton.terrain.matrix, automaton.fire.matrix, occupied_mask)
        if not all_neighbors:
            return
        neighbors = self.allowed_neighbors(all_neighbors)    # ciegas: el tabú siempre aplica

        heading = (self.y - self.last_y, self.x - self.last_x)
        d_cur = self.dist_home(automaton, self.y, self.x)

        moves, scores = [], []
        for ny, nx, dy, dx in neighbors:
            d_new = self.dist_home(automaton, ny, nx)
            toward = 1.0 if d_new < d_cur else (0.0 if d_new > d_cur else 0.5)   # 1 = se acerca al nido
            inertia = self._inertia(dy, dx, heading)

            if self.state == STATE_ATTACK and self.prey is not None:
                dist = abs(ny - self.prey.y) + abs(nx - self.prey.x)
                score = config.MARA_W_PREY / (1.0 + dist)
            elif self.state == config.STATE_FLEE:
                heat = self._fire_near(automaton, ny, nx) / float((2 * config.FIRE_ALERT_RADIUS + 1) ** 2)
                score = config.WEIGHT_FLEE * (1.0 - heat) + 0.5 * inertia
            elif self.state == STATE_RETREAT:
                score = config.MARA_W_TARGET * (1.0 - toward) + inertia
            else:  # RAID: hacia el nido, en columna con el enjambre
                t_hunt = self._smell_hunt(automaton, ny, nx)
                score = (config.MARA_W_TARGET * toward
                         + config.MARA_W_HUNT * (t_hunt / (t_hunt + config.MARA_HUNT_K))
                         + inertia)

            score += self.noise()
            moves.append((ny, nx))
            scores.append(score)

        self.commit_move(*self.pick_move(moves, scores))

    @staticmethod
    def _inertia(dy, dx, heading):
        hy, hx = heading
        if not (hy or hx):
            return 0.0
        return config.MARA_W_INERTIA * (dy * hy + dx * hx) / (math.hypot(dy, dx) * math.hypot(hy, hx))

    def _raid_nest(self, automaton):
        """STUB (Fase 4): robar reservas y crías."""
        return None