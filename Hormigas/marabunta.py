import math
import random
import numpy as np
import config

from .ant import Ant
from Automata.objects import NONE
from Automata.terrain import DIRT, NEST


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
        """nest_pos: el nido de la colonia que atacan (solo lo usa el modo 'smell'). agents: lista compartida."""
        super().__init__(y, x, nest_pos, agents)
        self.state = STATE_RAID
        self.carried_resource = NONE
        self.health = config.MARA_HEALTH
        self.prey = None
        self.raid_ticks = 0
        self.kills = 0
        self.advance = (0, 0)       # dirección de avance en modo contacto (la fija Simulation al crearla)
        self.loot_food = {}         # botín: {tipo: cantidad}
        self.loot_brood = []        # botín: crías robadas con su tiempo restante
        self.escaped = False
        # Memoria espacial corta (son ciegas): última posición donde tocaron un enemigo o el nido
        self.mem_pos = None
        self.mem_ttl = 0
        self.mem_kind = None        # "prey" | "nest"

    def loot_count(self):
        return sum(self.loot_food.values()) + len(self.loot_brood)

    # ------------------------------------------------------------ aparición
    @staticmethod
    def _edge_lines(automaton):
        """Las 4 orillas como listas de celdas ordenadas (celda, dirección de avance hacia adentro, dirección de relleno)."""
        h, w = automaton.terrain.matrix.shape
        return (
            ([(0, x) for x in range(w)], (1, 0)),
            ([(h - 1, x) for x in range(w)], (-1, 0)),
            ([(y, 0) for y in range(h)], (0, 1)),
            ([(y, w - 1) for y in range(h)], (0, -1)),
        )

    @staticmethod
    def swarm_plan(automaton, n):
        """Despliegue en FILA: n marabuntas contiguas sobre UNA sola orilla, mirando todas hacia adentro.
        Entre las ventanas de n celdas transitables y consecutivas elige (al azar entre las SWARM_POOL más cercanas
        al nido por camino) una que quede a SWARM_MIN_DIST o más. Si la orilla no da para n, completa con una
        segunda fila detrás (hacia adentro). Devuelve (celdas, avance)."""
        a = automaton
        dist = a.home_dist
        walk = (a.terrain.matrix == DIRT) & np.isfinite(dist)
        windows = []                                      # (distancia media, celdas, avance)
        best_short = None                                 # plan B: la tira más larga si ninguna alcanza n
        for line, adv in Marabunta._edge_lines(a):
            run = []
            for c in line + [None]:
                if c is not None and walk[c] and dist[c] >= config.SWARM_MIN_DIST:
                    run.append(c)
                    continue
                if len(run) >= n:
                    for i in range(len(run) - n + 1):
                        cells = run[i:i + n]
                        windows.append((float(np.mean([dist[q] for q in cells])), cells, adv))
                if run and (best_short is None or len(run) > len(best_short[1])):
                    best_short = (float(np.mean([dist[q] for q in run])), run, adv)
                run = []
        if windows:
            windows.sort(key=lambda t: t[0])
            _, cells, adv = random.choice(windows[:max(1, config.SWARM_POOL)])
            return list(cells), adv
        if best_short is not None:
            _, base, adv = best_short
            cells, k = list(base), 1
            while len(cells) < n and k < max(a.height, a.width):      # filas de refuerzo detrás de la primera
                for (y, x) in base:
                    q = (y + adv[0] * k, x + adv[1] * k)
                    if len(cells) < n and 0 <= q[0] < a.height and 0 <= q[1] < a.width and walk[q]:
                        cells.append(q)
                k += 1
            return cells[:n], adv
        # mapa chico o sin orillas válidas: la celda alcanzable más lejana
        ys, xs = np.nonzero(walk)
        if len(ys):
            i = int(np.argmax(dist[ys, xs]))
            c = (int(ys[i]), int(xs[i]))
            return [c], Marabunta.advance_for(a, *c)
        return [tuple(int(v) for v in a.terrain.nest_pos)], (0, 0)

    @staticmethod
    def spawn_cells(automaton, n):
        return Marabunta.swarm_plan(automaton, n)[0]

    @staticmethod
    def spawn_position(automaton):
        return random.choice(Marabunta.spawn_cells(automaton, 1))

    @staticmethod
    def advance_for(automaton, y, x):
        """Dirección de avance (modo contacto): hacia el interior del mapa desde el borde por el que entra.
        Si no nació en el borde, hacia el centro del mapa. No usa la posición del nido."""
        h, w = automaton.terrain.matrix.shape
        dy = 1 if y == 0 else (-1 if y == h - 1 else 0)
        dx = 1 if x == 0 else (-1 if x == w - 1 else 0)
        if dy == 0 and dx == 0:
            dy, dx = (h // 2 > y) - (h // 2 < y), (w // 2 > x) - (w // 2 < x)
        return dy, dx

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
        if automaton.terrain.matrix[self.y, self.x] == NEST and self.state != STATE_RETREAT:
            self._raid_nest(automaton)
        self._try_escape(automaton)

    def _evaluate_state(self, automaton):
        """Prioridad: huir del fuego > retirarse (herida, inventario lleno o tiempo) > atacar > avanzar."""
        if self._fire_near(automaton, self.y, self.x) > 0:
            self.state = config.STATE_FLEE
            self.prey = None
            return
        if self.state == STATE_RETREAT:
            return
        if (self.health < config.MARA_RETREAT_HEALTH or self.raid_ticks > config.MARA_MAX_RAID_TICKS
                or self.loot_count() >= config.MARA_CARRY_CAPACITY):
            self.state = STATE_RETREAT
            self.prey = None
            return
        self.prey = self._find_prey()
        self._update_memory(automaton)
        self.state = STATE_ATTACK if self.prey is not None else STATE_RAID

    # ------------------------------------------------------------ memoria espacial corta
    def _update_memory(self, automaton):
        """Recuerda dónde tocó un enemigo o el nido. Sin contacto, la memoria las guía un rato y se olvida al llegar."""
        if self.prey is not None:
            self.mem_pos, self.mem_ttl, self.mem_kind = (self.prey.y, self.prey.x), config.MARA_MEMORY_TICKS, "prey"
            return
        t = automaton.terrain.matrix
        R = config.MARA_CONTACT_RADIUS
        h, w = t.shape
        win = t[max(0, self.y - R):min(h, self.y + R + 1), max(0, self.x - R):min(w, self.x + R + 1)]
        if (win == NEST).any():                      # tocó el nido: lo recuerda más tiempo
            self.mem_pos = (int(automaton.terrain.nest_pos[0]), int(automaton.terrain.nest_pos[1]))
            self.mem_ttl, self.mem_kind = config.MARA_NEST_MEMORY_TICKS, "nest"
            return
        if self.mem_pos is not None:
            self.mem_ttl -= 1
            if self.mem_ttl <= 0 or max(abs(self.mem_pos[0] - self.y), abs(self.mem_pos[1] - self.x)) == 0:
                self.mem_pos, self.mem_kind = None, None

    def _find_prey(self):
        """Hormiga viva de la colonia más cercana dentro del radio de percepción, o None.
        'contact': solo ven lo que tocan. 'smell': sienten a MARA_SENSE_RADIUS."""
        radius = config.MARA_SENSE_RADIUS if config.MARA_SENSE == "smell" else config.MARA_CONTACT_RADIUS
        best, best_d = None, radius + 1
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

    @staticmethod
    def _d_exit(automaton, y, x):
        d = automaton.exit_dist[y, x]
        return float(d) if math.isfinite(d) else 1e6

    def _move(self, automaton, occupied_mask):
        if self.state == STATE_ATTACK and self.prey is not None and self.manhattan(self.prey) <= 1:
            return

        all_neighbors = self.get_valid_neighbors(automaton.terrain.matrix, automaton.fire.matrix, occupied_mask)
        if not all_neighbors:
            return
        neighbors = self.allowed_neighbors(all_neighbors)    # ciegas: el tabú siempre aplica

        heading = (self.y - self.last_y, self.x - self.last_x)
        d_cur = self.dist_home(automaton, self.y, self.x)
        e_cur = self._d_exit(automaton, self.y, self.x)
        ay, ax = self.advance
        a_norm = math.hypot(ay, ax)
        smell = config.MARA_SENSE == "smell"
        swarm = config.MARA_RAID_MODE == "swarm"

        moves, scores = [], []
        for ny, nx, dy, dx in neighbors:
            inertia = self._inertia(dy, dx, heading)

            if self.state == STATE_ATTACK and self.prey is not None:
                dist = abs(ny - self.prey.y) + abs(nx - self.prey.x)
                score = config.MARA_W_PREY / (1.0 + dist)
            elif self.state == config.STATE_FLEE:
                heat = self._fire_near(automaton, ny, nx) / float((2 * config.FIRE_ALERT_RADIUS + 1) ** 2)
                score = config.WEIGHT_FLEE * (1.0 - heat) + 0.5 * inertia
            elif self.state == STATE_RETREAT:        # a la salida más cercana del mapa
                e_new = self._d_exit(automaton, ny, nx)
                toward_exit = 1.0 if e_new < e_cur else (0.0 if e_new > e_cur else 0.5)
                score = 2.0 * config.MARA_W_TARGET * toward_exit + inertia
            else:  # RAID
                t_hunt = self._smell_hunt(automaton, ny, nx)
                trail = t_hunt / (t_hunt + config.MARA_HUNT_K)
                if smell:                            # huelen el nido: columna hacia él
                    d_new = self.dist_home(automaton, ny, nx)
                    toward = 1.0 if d_new < d_cur else (0.0 if d_new > d_cur else 0.5)
                    score = config.MARA_W_TARGET * toward + config.MARA_W_HUNT * trail + inertia
                    score += self._memory_pull(ny, nx)
                else:                                # ciegas: avanzan hacia adentro y se guían por su propio rastro
                    adv = ((dy * ay + dx * ax) / a_norm) if a_norm else 0.0
                    adv_term = config.MARA_W_ADVANCE * (adv + 1.0) / 2.0
                    if swarm:                        # abanico: se esparcen, huyendo del rastro propio
                        score = adv_term - config.MARA_W_SPREAD * trail + 0.5 * inertia + self.noise()
                    else:                            # columna: frente estrecho que sigue el rastro
                        score = adv_term + config.MARA_W_HUNT * trail + inertia
                    score += self._memory_pull(ny, nx)

            score += self.noise()
            moves.append((ny, nx))
            scores.append(score)

        self.commit_move(*self.pick_move(moves, scores))

    def _memory_pull(self, ny, nx):
        """Empuje hacia la última posición recordada (0 si no hay memoria)."""
        if self.mem_pos is None:
            return 0.0
        my, mx = self.mem_pos
        d_now = abs(self.y - my) + abs(self.x - mx)
        d_new = abs(ny - my) + abs(nx - mx)
        return config.MARA_W_MEMORY * (d_now - d_new + 1.0) / 2.0

    @staticmethod
    def _inertia(dy, dx, heading):
        hy, hx = heading
        if not (hy or hx):
            return 0.0
        return config.MARA_W_INERTIA * (dy * hy + dx * hx) / (math.hypot(dy, dx) * math.hypot(hy, hx))

    # ------------------------------------------------------------ saqueo (Fase 4)
    def _raid_nest(self, automaton):
        """En el nido: roba crías primero y luego comida, hasta MARA_CARRY_CAPACITY. Lleno o sin nada que robar: se va."""
        room = config.MARA_CARRY_CAPACITY - self.loot_count()
        if room <= 0:
            self.state = STATE_RETREAT
            return
        n = min(room, config.MARA_STEAL_PER_TICK)
        colony = automaton.colony
        brood = colony.steal_brood(n)
        self.loot_brood.extend(brood)
        food = colony.steal_food(n - len(brood)) if n - len(brood) > 0 else {}
        for k, q in food.items():
            self.loot_food[k] = self.loot_food.get(k, 0) + q
        if not brood and not food:               # no queda nada que robar
            self.state = STATE_RETREAT
        elif self.loot_count() >= config.MARA_CARRY_CAPACITY:
            self.state = STATE_RETREAT

    def _try_escape(self, automaton):
        """Si llega al borde retirándose, sale del mapa. El botín que lleva se pierde para siempre."""
        if self.state != STATE_RETREAT:
            return
        h, w = automaton.terrain.matrix.shape
        if self.y in (0, h - 1) or self.x in (0, w - 1):
            automaton.colony.lost_units += automaton.colony.loot_units(self.loot_food, self.loot_brood)
            self.loot_food, self.loot_brood = {}, []
            self.escaped = True
            self.die("ESCAPE")