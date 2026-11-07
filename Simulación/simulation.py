"""Dueña del mundo: autómata + agentes. No sabe que existe la interfaz."""
import random
from collections import deque
import numpy as np
import config
from Automata.automaton import CellularAutomaton
from Automata.terrain import DIRT
from Automata.objects import GRASS, MANGO, BOCADILLO
from Automata.fire import BURNING, ASH
from Hormigas.worker import Worker
from Hormigas.soldier import Soldier
from Hormigas.marabunta import Marabunta

CASTES = {"WORKER": Worker, "SOLDIER": Soldier, "MARABUNTA": Marabunta}


class Simulation:
    def __init__(self, seed=None):
        self.seed = config.SEED if seed is None else seed
        self.reset()

    def reset(self, seed=None):
        if seed is not None:
            self.seed = seed
        random.seed(self.seed)                    # los agentes usan el módulo random
        self.automaton = CellularAutomaton(config.WIDTH, config.HEIGHT, self.seed)
        self.agents = []                          # lista COMPARTIDA con soldadas/marabuntas: solo se muta en sitio
        self.tick = 0
        self.version = 0                          # sube con cada cambio del mundo (cachés del render)
        self.traffic = np.zeros((self.automaton.height, self.automaton.width), dtype=np.float32)
        castes = ["WORKER"] * config.NUM_WORKERS + ["SOLDIER"] * config.NUM_SOLDIERS
        random.shuffle(castes)
        self.queue = deque(castes)                # salen del nido de a poco

    @property
    def nest(self):
        y, x = self.automaton.terrain.nest_pos
        return int(y), int(x)

    # ------------------------------------------------------------ un tick
    def step(self):
        self.tick += 1
        self.version += 1
        a = self.automaton
        nest = self.nest

        # 0. Guardar posición previa (para interpolar) y retirar cadáveres vencidos
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

        # 3. Salida escalonada del nido
        for _ in range(config.SPAWN_PER_TICK):
            if self.queue:
                self.agents.append(self._make(self.queue.popleft(), *nest))

        # 4. Agentes, en orden aleatorio, actualizando la ocupación tras cada movimiento
        occupied = self._occupied_mask()
        order = [ag for ag in self.agents if ag.alive]
        random.shuffle(order)
        for ag in order:
            if not ag.alive:                      # la mató otra hormiga durante este tick
                continue
            old = (ag.y, ag.x)
            ag.update_logic(a, occupied)
            new = (ag.y, ag.x)
            if new != old:
                occupied[old] = False
                occupied[new] = new != nest
                ag.facing = (new[0] - old[0], new[1] - old[1])

        # 5. Las que murieron dejan alarma (una sola vez)
        for ag in self.agents:
            if not ag.alive and not ag.death_handled:
                ag.death_handled = True
                if ag.CASTE != "MARABUNTA":
                    a.deposit_pheromone("alarma", ag.y, ag.x, config.DEPOSIT_AMOUNT_DEATH_ALARM)

        # 6. Mapa de tráfico (por dónde pasan las obreras)
        self.traffic *= config.TRAFFIC_DECAY
        for ag in self.agents:
            if ag.alive and ag.CASTE == "WORKER" and (ag.y, ag.x) != nest:
                self.traffic[ag.y, ag.x] += 1.0

    def _occupied_mask(self):
        """Celdas ocupadas (vivas y cadáveres). El nido está exento: ahí abajo caben todas."""
        m = np.zeros((self.automaton.height, self.automaton.width), dtype=bool)
        for ag in self.agents:
            m[ag.y, ag.x] = True
        m[self.nest] = False
        return m

    def _make(self, caste, y, x):
        nest = self.nest
        cls = CASTES[caste]
        return cls(y, x, nest) if caste == "WORKER" else cls(y, x, nest, self.agents)

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
        self.agents.append(self._make(caste, y, x))
        self.version += 1
        return True

    def spawn_swarm(self, n):
        """n marabuntas entrando por el borde más lejano al nido."""
        occ = self._occupied_mask()
        made = 0
        for _ in range(n):
            for _try in range(30):
                y, x = Marabunta.spawn_position(self.automaton)
                if not occ[y, x]:
                    self.agents.append(self._make("MARABUNTA", y, x))
                    occ[y, x] = True
                    made += 1
                    break
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

    def stats(self):
        a = self.automaton
        c = {"WORKER": 0, "SOLDIER": 0, "MARABUNTA": 0}
        for ag in self.agents:
            if ag.alive:
                c[ag.CASTE] += 1
        d = a.colony.delivered
        return {
            **c,
            "tick": self.tick,
            "queued": len(self.queue),
            "grass": int((a.objects.matrix == GRASS).sum()),
            "mango": int((a.objects.matrix == MANGO).sum()),
            "bocadillos": len(a.objects.bocadillo_bites),
            "delivered": (d[GRASS], d[MANGO], d[BOCADILLO]),
            "burning": int((a.fire.matrix == BURNING).sum()),
            "ash": int((a.fire.matrix == ASH).sum()),
        }