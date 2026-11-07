"""Dueña del mundo: autómata + agentes. No sabe que existe la interfaz."""
import random
from collections import deque
import numpy as np
import config
from Automata.automaton import CellularAutomaton
from Automata.terrain import DIRT, ROCK, WATER
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
        self.terrain_version = 0                  # sube al poner/borrar roca o agua
        self.last_error = ""                      # mensaje para la interfaz
        self.game_over = False
        self.events = []                          # eventos de sonido (tarea opcional)
        self.deaths = {"WORKER": 0, "SOLDIER": 0, "MARABUNTA": 0}
        self._starve_timer = 0
        self.traffic = np.zeros((self.automaton.height, self.automaton.width), dtype=np.float32)
        castes = ["WORKER"] * config.INITIAL_WORKERS + ["SOLDIER"] * config.INITIAL_SOLDIERS
        random.shuffle(castes)
        self.queue = deque(castes)                # población inicial: sale del nido de a poco, sin costo

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

        # 3. Salida escalonada del nido (población inicial)
        for _ in range(config.SPAWN_PER_TICK):
            if self.queue:
                self.agents.append(self._make(self.queue.popleft(), *nest))

        # 3b. Nacimientos desde reservas y hambre
        self._births()
        self._hunger()

        # 4. Agentes, en orden aleatorio, actualizando la ocupación tras cada movimiento
        pass_mode = config.COLLISION_MODE == "allies_pass"
        if pass_mode:
            cnt, masks = self._group_masks()
        else:
            occupied = self._occupied_mask()
        order = [ag for ag in self.agents if ag.alive]
        random.shuffle(order)
        for ag in order:
            if not ag.alive:                      # la mató otra hormiga durante este tick
                continue
            old = (ag.y, ag.x)
            group = "MARA" if ag.CASTE == "MARABUNTA" else "ALLY"
            ag.update_logic(a, masks[group] if pass_mode else occupied)
            new = (ag.y, ag.x)
            if new != old:
                if pass_mode:
                    # esta hormiga es vista como ocupada por el grupo contrario
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
                ag.facing = (new[0] - old[0], new[1] - old[1])

        # 5. Las que murieron dejan alarma (una sola vez) y se cuentan las bajas
        for ag in self.agents:
            if not ag.alive and not ag.death_handled:
                ag.death_handled = True
                self.deaths[ag.CASTE] += 1
                if ag.CASTE != "MARABUNTA":
                    a.deposit_pheromone("alarma", ag.y, ag.x, config.DEPOSIT_AMOUNT_DEATH_ALARM)

        # 6. Mapa de tráfico (por dónde pasan las obreras)
        self.traffic *= config.TRAFFIC_DECAY
        for ag in self.agents:
            if ag.alive and ag.CASTE == "WORKER" and (ag.y, ag.x) != nest:
                self.traffic[ag.y, ag.x] += 1.0

        # 7. Game over: ninguna obrera viva (ni en cola) y sin reservas para una nueva
        workers_alive = any(ag.alive and ag.CASTE == "WORKER" for ag in self.agents)
        workers_queued = "WORKER" in self.queue
        if not workers_alive and not workers_queued and not a.colony.can_afford("WORKER"):
            self.game_over = True

    # ------------------------------------------------------------ nacimientos y hambre
    def _population(self):
        n = sum(1 for ag in self.agents if ag.alive and ag.CASTE != "MARABUNTA")
        return n + len(self.queue)

    def _births(self):
        if self.queue or self.tick % config.BIRTH_INTERVAL != 0:
            return
        if self._population() >= config.MAX_POPULATION:
            return
        colony = self.automaton.colony
        caste = "SOLDIER" if random.random() < config.BIRTH_SOLDIER_RATIO else "WORKER"
        if caste == "SOLDIER" and not colony.can_afford("SOLDIER"):
            caste = "WORKER"
        if colony.pay(caste):
            self.agents.append(self._make(caste, *self.nest))

    def _hunger(self):
        if self.automaton.colony.upkeep():
            self._starve_timer = 0
            return
        self._starve_timer += 1
        if self._starve_timer >= config.STARVATION_INTERVAL:
            self._starve_timer = 0
            victims = [ag for ag in self.agents if ag.alive and ag.CASTE != "MARABUNTA"]
            if victims:
                random.choice(victims).die("STARVE")

    # ------------------------------------------------------------ máscaras de ocupación
    def _occupied_mask(self):
        """Modo 'block': celdas ocupadas (vivas y cadáveres). El nido está exento."""
        m = np.zeros((self.automaton.height, self.automaton.width), dtype=bool)
        for ag in self.agents:
            m[ag.y, ag.x] = True
        m[self.nest] = False
        return m

    def _group_masks(self):
        """Modo 'allies_pass': conteos por celda y una máscara por grupo.
        ALLY (obreras+soldadas) ve marabuntas vivas y cadáveres.
        MARA (marabuntas) ve obreras/soldadas vivas y cadáveres."""
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
        if caste in ("WORKER", "SOLDIER") and not a.colony.pay(caste):
            self.last_error = "Reservas insuficientes"
            return False
        self.agents.append(self._make(caste, y, x))
        self.version += 1
        return True

    def spawn_swarm(self, n):
        """n marabuntas entrando por el borde más lejano al nido (gratis)."""
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
        a.terrain.matrix[y, x] = kind
        mask = np.zeros((a.height, a.width), dtype=bool)
        mask[y, x] = True
        a.objects.clear_mask(mask)                # borra pasto o el mango/bocadillo completo
        a.fire.matrix[y, x] = 0
        a.terrain.moisture[:] = 0                 # reinicia para que el agua borrada deje de mojar
        a.terrain._calculate_static_moisture()
        a.recompute_fields()
        self.version += 1
        self.terrain_version += 1
        return True

    def erase_terrain(self, y, x):
        return self.place_terrain(DIRT, y, x)

    # ------------------------------------------------------------ game over y estadísticas
    def summary(self):
        spt = config.TICK_SECONDS
        d = self.automaton.colony.delivered
        return {
            "ticks": self.tick,
            "seconds": self.tick * spt,
            "delivered": {"grass": d[GRASS], "mango": d[MANGO], "bocadillo": d[BOCADILLO]},
            "deaths": dict(self.deaths),
        }

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
            "mango": a.objects.count(MANGO),      # objetos 2x2, no celdas
            "bocadillos": len(a.objects.bocadillo_bites),
            "delivered": (d[GRASS], d[MANGO], d[BOCADILLO]),
            "stock": dict(a.colony.stock),
            "burning": int((a.fire.matrix == BURNING).sum()),
            "ash": int((a.fire.matrix == ASH).sum()),
        }
