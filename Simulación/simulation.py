"""Dueña del mundo: autómata + agentes. No sabe que existe la interfaz."""
import random
from collections import deque
import numpy as np
import config
from Automata.automaton import CellularAutomaton
from Automata.scenario import get_scenario
from Automata.terrain import DIRT, ROCK, WATER, NEST
from Automata.objects import GRASS, MANGO, BOCADILLO
from Automata.fire import BURNING, ASH
from Hormigas.worker import Worker
from Hormigas.soldier import Soldier
from Hormigas.marabunta import Marabunta

CASTES = {"WORKER": Worker, "SOLDIER": Soldier, "MARABUNTA": Marabunta}
_KEEP = object()


class Simulation:
    def __init__(self, seed=None, scenario=None):
        self.seed = config.SEED if seed is None else seed
        self.scenario = scenario
        self.reset()

    def reset(self, seed=None, scenario=_KEEP):
        """scenario: None = mapa aleatorio, id o Scenario = prefijado, sin pasarlo = conserva el actual."""
        if scenario is not _KEEP:
            self.scenario = scenario
        if seed is not None:
            self.seed = seed
        if self.scenario is not None:
            self.seed = get_scenario(self.scenario).seed
        random.seed(self.seed)
        self.automaton = CellularAutomaton(config.WIDTH, config.HEIGHT, self.seed, scenario=self.scenario)
        self.agents = []                          # lista COMPARTIDA: solo se muta en sitio
        self.tick = 0
        self.version = 0
        self.terrain_version = 0
        self.last_error = ""
        self.game_over = False
        self.events = []
        self.deaths = {"WORKER": 0, "SOLDIER": 0, "MARABUNTA": 0}
        self.death_causes = {}                    # causa -> cantidad (obreras y soldadas)
        self.lost_with_food = 0                   # murieron sin energía habiendo comida en el nido
        self.births = 0
        self._starve_timer = 0
        self.traffic = np.zeros((self.automaton.height, self.automaton.width), dtype=np.float32)
        castes = ["WORKER"] * config.INITIAL_WORKERS + ["SOLDIER"] * config.INITIAL_SOLDIERS
        random.shuffle(castes)
        self.queue = deque(castes)
        # Salida escalonada: la primera sale sola y las demás esperan a que entregue comida
        self.scout = None
        self.scout_tick = 0
        self.last_exit = -10 ** 9
        self.gate_open = False
        self.waiting_scout = False

    @property
    def nest(self):
        y, x = self.automaton.terrain.nest_pos
        return int(y), int(x)

    # ------------------------------------------------------------ un tick
    def step(self):
        if self.game_over:
            return
        self.tick += 1
        self.version += 1
        a = self.automaton
        nest = self.nest

        # 0. Posición previa (para interpolar) y retirada de cadáveres vencidos
        for ag in self.agents:
            ag.prev_y, ag.prev_x = ag.y, ag.x
            if not ag.alive:
                ag.dead_ticks += 1
        self.agents[:] = [ag for ag in self.agents if ag.alive or ag.dead_ticks < config.CORPSE_TICKS]

        # 1. Ambiente (feromonas, fuego, ceniza, recursos)
        a.update_step()

        # 2. Muerte por fuego
        fire = a.fire.matrix
        for ag in self.agents:
            if ag.alive and fire[ag.y, ag.x] > 0:
                ag.die("FIRE")

        # 3. Salida del nido, crías que maduran, nuevas crías y hambre del hongo
        self._release_queue(nest)
        self._mature_brood()
        self._births()
        self._hunger()

        # 4. Agentes en orden ALEATORIO cada tick (sin sesgo de movimiento)
        pass_mode = config.COLLISION_MODE == "allies_pass"
        if pass_mode:
            cnt, masks = self._group_masks()
        else:
            occupied = self._occupied_mask()
        order = [ag for ag in self.agents if ag.alive]
        random.shuffle(order)
        for ag in order:
            if not ag.alive:
                continue
            old = (ag.y, ag.x)
            group = "MARA" if ag.CASTE == "MARABUNTA" else "ALLY"
            ag.update_logic(a, masks[group] if pass_mode else occupied)
            new = (ag.y, ag.x)
            if new != old:
                if pass_mode:
                    other = "ALLY" if group == "MARA" else "MARA"
                    if old != nest:
                        cnt[other][old] -= 1
                        masks[other][old] = cnt[other][old] > 0
                    if new != nest:
                        cnt[other][new] += 1
                        masks[other][new] = True
                else:
                    occupied[old] = False
                    occupied[new] = new != nest
                if not ag.attacking:
                    ag.facing = (new[0] - old[0], new[1] - old[1])

        # 5. Bajas: se cuentan por causa; en combate o fuego dejan alarma (una vez)
        for ag in self.agents:
            if not ag.alive and not ag.death_handled:
                ag.death_handled = True
                self.deaths[ag.CASTE] += 1
                cause = ag.death_cause or "?"
                if ag.CASTE != "MARABUNTA":
                    self.death_causes[cause] = self.death_causes.get(cause, 0) + 1
                    if cause == "STARVE" and a.colony.has_food():
                        self.lost_with_food += 1
                    if cause in ("FIGHT", "FIRE"):
                        a.deposit_pheromone("alarma", ag.y, ag.x, config.DEPOSIT_AMOUNT_DEATH_ALARM)

        # 6. Mapa de tráfico
        self.traffic *= config.TRAFFIC_DECAY
        for ag in self.agents:
            if ag.alive and ag.CASTE == "WORKER" and (ag.y, ag.x) != nest:
                self.traffic[ag.y, ag.x] += 1.0

        # 7. Game over: ninguna obrera viva, en cola ni en desarrollo, y sin bolsa para una nueva
        c = a.colony
        workers_alive = any(ag.alive and ag.CASTE == "WORKER" for ag in self.agents)
        if (not workers_alive and "WORKER" not in self.queue
                and c.brood_count("WORKER") == 0 and not c.can_afford("WORKER")):
            self.game_over = True

    # ------------------------------------------------------------ salida, crías y hambre
    def _release_queue(self, nest):
        """Sale 1 hormiga cada SPAWN_INTERVAL ticks. La primera (una obrera) sale sola; las demás
        esperan a que entregue comida al nido (o a que pasen SCOUT_TIMEOUT ticks)."""
        self.waiting_scout = False
        if not self.queue:
            return
        if not self.gate_open:
            delivered = sum(self.automaton.colony.delivered.values()) > 0
            timed_out = self.scout is not None and self.tick - self.scout_tick > config.SCOUT_TIMEOUT
            if delivered or timed_out:
                self.gate_open = True
            elif self.scout is not None and self.scout.alive:
                self.waiting_scout = True
                return
        if self.tick - self.last_exit < config.SPAWN_INTERVAL:
            return
        caste = "WORKER" if "WORKER" in self.queue else self.queue[0]
        self.queue.remove(caste)
        ag = self._make(caste, *nest)
        self.agents.append(ag)
        self.last_exit = self.tick
        if not self.gate_open:
            self.scout, self.scout_tick = ag, self.tick

    def _pop_counts(self):
        """(obreras, soldadas) contando vivas, en cola de salida y en desarrollo."""
        w = sum(1 for ag in self.agents if ag.alive and ag.CASTE == "WORKER")
        s = sum(1 for ag in self.agents if ag.alive and ag.CASTE == "SOLDIER")
        w += sum(1 for c in self.queue if c == "WORKER") + self.automaton.colony.brood_count("WORKER")
        s += sum(1 for c in self.queue if c == "SOLDIER") + self.automaton.colony.brood_count("SOLDIER")
        return w, s

    def _population(self):
        w, s = self._pop_counts()
        return w + s

    def _mature_brood(self):
        for caste in self.automaton.colony.tick_brood():
            self.agents.append(self._make(caste, *self.nest))
            self.births += 1

    def _births(self):
        """El excedente (sobre 3 ciclos de alimento para toda la población y el hongo) se vuelve crías."""
        colony = self.automaton.colony
        if self.queue or self.tick % config.BIRTH_INTERVAL != 0 or colony.starving:
            return
        pop = self._pop_counts()
        if sum(pop) >= config.MAX_POPULATION:
            return
        caste = "SOLDIER" if random.random() < config.BIRTH_SOLDIER_RATIO else "WORKER"
        if caste == "SOLDIER" and not colony.can_afford("SOLDIER", True, pop):
            caste = "WORKER"
        colony.start_brood(caste, pop)

    def _hunger(self):
        """Con la bolsa vacía, una hormiga muere (HUNGER) cada STARVATION_INTERVAL ticks."""
        if self.automaton.colony.upkeep():
            self._starve_timer = 0
            return
        self._starve_timer += 1
        if self._starve_timer >= config.STARVATION_INTERVAL:
            self._starve_timer = 0
            victims = [ag for ag in self.agents if ag.alive and ag.CASTE != "MARABUNTA"]
            if victims:
                random.choice(victims).die("HUNGER")

    # ------------------------------------------------------------ máscaras de ocupación
    def _occupied_mask(self):
        m = np.zeros((self.automaton.height, self.automaton.width), dtype=bool)
        for ag in self.agents:
            m[ag.y, ag.x] = True
        m[self.nest] = False
        return m

    def _group_masks(self):
        shape = (self.automaton.height, self.automaton.width)
        cnt = {"ALLY": np.zeros(shape, dtype=np.int16), "MARA": np.zeros(shape, dtype=np.int16)}
        for ag in self.agents:
            if not ag.alive:
                cnt["ALLY"][ag.y, ag.x] += 1
                cnt["MARA"][ag.y, ag.x] += 1
            elif ag.CASTE == "MARABUNTA":
                cnt["ALLY"][ag.y, ag.x] += 1
            else:
                cnt["MARA"][ag.y, ag.x] += 1
        for k in cnt:
            cnt[k][self.nest] = 0
        masks = {k: v > 0 for k, v in cnt.items()}
        return cnt, masks

    def _make(self, caste, y, x):
        return CASTES[caste](y, x, self.nest, self.agents)

    # ------------------------------------------------------------ API de depuración / Modo Dios
    def agent_at(self, y, x):
        found = None
        for ag in self.agents:
            if ag.y == y and ag.x == x:
                if ag.alive:
                    return ag
                found = ag
        return found

    def spawn_at(self, caste, y, x):
        a = self.automaton
        if a.terrain.matrix[y, x] != DIRT or a.fire.matrix[y, x] > 0 or self.agent_at(y, x):
            return False
        if caste in ("WORKER", "SOLDIER"):
            if a.colony.starving:
                self.last_error = "Hongo sin comida: spawn bloqueado"
                return False
            if not a.colony.pay(caste):
                self.last_error = "Reservas insuficientes"
                return False
        self.agents.append(self._make(caste, y, x))
        self.version += 1
        return True

    def spawn_swarm(self, n):
        """n marabuntas en el borde más cercano al nido, a SWARM_MIN_DIST o más de camino (gratis)."""
        occ = self._occupied_mask()
        cells = Marabunta.spawn_cells(self.automaton, n)
        random.shuffle(cells)
        made = 0
        for y, x in cells:
            if made >= n:
                break
            if occ[y, x]:
                continue
            self.agents.append(self._make("MARABUNTA", y, x))
            occ[y, x] = True
            made += 1
        self.version += 1
        return made

    def place_resource(self, kind, y, x):
        a = self.automaton
        ok = a.objects.place_resource(kind, y, x, a.terrain.matrix, a.fire.matrix)
        self.version += 1
        return ok

    def place_bocadillo(self, y, x):
        a = self.automaton
        ok = a.objects.place_bocadillo(y, x, a.terrain.matrix, a.fire.matrix)
        self.version += 1
        return ok

    def ignite(self, y, x):
        a = self.automaton
        ok = a.fire.ignite(y, x, a.terrain.matrix, a.objects.matrix)
        self.version += 1
        return ok

    def random_fire(self):
        a = self.automaton
        pos = a.fire.ignite_random(a.terrain.matrix, a.objects.matrix)
        self.version += 1
        return pos

    def kill_at(self, y, x, cause):
        ag = self.agent_at(y, x)
        if ag and ag.alive:
            ag.die(cause)
            return True
        return False

    def set_wind(self, wx, wy):
        config.WIND_X, config.WIND_Y = wx, wy

    # ------------------------------------------------------------ piedra y agua
    def place_terrain(self, kind, y, x):
        """kind = ROCK, WATER o DIRT. No sobre el nido ni sobre una hormiga."""
        a = self.automaton
        if kind not in (DIRT, ROCK, WATER):
            return False
        if not (0 <= y < a.height and 0 <= x < a.width):
            return False
        if (y, x) == self.nest or self.agent_at(y, x):
            self.last_error = "No se puede poner terreno ahí"
            return False
        if not a.place_terrain(y, x, kind):
            return False
        for ag in self.agents:
            if ag.alive and a.terrain.matrix[ag.y, ag.x] not in (DIRT, NEST):
                ag.die("FIGHT")
        self.version += 1
        self.terrain_version += 1
        return True

    def erase_terrain(self, y, x):
        return self.place_terrain(DIRT, y, x)

    # ------------------------------------------------------------ game over y estadísticas
    def summary(self):
        d = self.automaton.colony.delivered
        return {
            "ticks": self.tick,
            "seconds": self.tick * config.TICK_SECONDS,
            "delivered": {"grass": d[GRASS], "mango": d[MANGO], "bocadillo": d[BOCADILLO]},
            "deaths": dict(self.deaths),
            "death_causes": dict(self.death_causes),
        }

    def stats(self):
        a = self.automaton
        c = {"WORKER": 0, "SOLDIER": 0, "MARABUNTA": 0}
        for ag in self.agents:
            if ag.alive:
                c[ag.CASTE] += 1
        d, s = a.colony.delivered, a.colony.stock
        return {
            **c,
            "tick": self.tick,
            "queued": len(self.queue),
            "grass": int((a.objects.matrix == GRASS).sum()),
            "mango": a.objects.count(MANGO),
            "bocadillos": len(a.objects.bocadillo_bites),
            "delivered": (d[GRASS], d[MANGO], d[BOCADILLO]),
            "stock": (s[GRASS], s[MANGO], s[BOCADILLO]),
            "units": a.colony.food_units(),
            "brood": a.colony.brood_count(),
            "births": self.births,
            "starving": a.colony.starving,
            "stressed": a.colony.is_stressed(),
            "burning": int((a.fire.matrix == BURNING).sum()),
            "ash": int((a.fire.matrix == ASH).sum()),
        }