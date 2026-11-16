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
        sc = get_scenario(self.scenario) if self.scenario is not None else None
        self.no_ants = sc is not None and not sc.colony      # escenarios de fuego/clima: sin hormigas ni hambre
        self.automaton = CellularAutomaton(config.WIDTH, config.HEIGHT, self.seed, scenario=self.scenario)
        if sc is not None and sc.ignite is not None:
            iy, ix = int(sc.ignite[0] * config.HEIGHT), int(sc.ignite[1] * config.WIDTH)
            self.automaton.fire.matrix[iy, ix] = BURNING
        self.agents = []                          # lista COMPARTIDA: solo se muta en sitio
        self.tick = 0
        self.version = 0
        self.terrain_version = 0
        self.last_error = ""
        self.game_over = False
        self.game_over_reason = ""
        self._doom = 0                            # ticks seguidos en estado irrecuperable
        self.events = []
        self.deaths = {"WORKER": 0, "SOLDIER": 0, "MARABUNTA": 0}
        self.death_causes = {}                    # causa -> cantidad (obreras y soldadas)
        self.lost_with_food = 0                   # murieron sin energía habiendo comida en el nido
        self.births = 0
        self.escaped = 0                          # marabuntas que salieron del mapa
        self._starve_timer = 0
        self.traffic = np.zeros((self.automaton.height, self.automaton.width), dtype=np.float32)
        castes = ["WORKER"] * config.INITIAL_WORKERS + ["SOLDIER"] * config.INITIAL_SOLDIERS
        random.shuffle(castes)
        self.queue = deque() if self.no_ants else deque(castes)
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
        self.agents[:] = [ag for ag in self.agents
                          if (ag.alive or ag.dead_ticks < config.CORPSE_TICKS) and not getattr(ag, "escaped", False)]
       
        # 1. Ambiente (feromonas, fuego, ceniza, recursos)
        a.update_step()
        self._apply_strikes()                     # los rayos del clima matan a quien estuviera en la celda

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
        pass_mode = config.COLLISION_MODE in ("allies_pass", "swap")
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
        if config.COLLISION_MODE == "swap":
            self._resolve_swaps(nest)

        # 5. Bajas: se cuentan por causa; en combate o fuego dejan alarma (una vez). Quien muere con botín lo suelta.
        for ag in self.agents:
            if not ag.alive and not ag.death_handled:
                ag.death_handled = True
                cause = ag.death_cause or "?"
                if cause == "ESCAPE":
                    self.escaped += 1
                    continue
                self.deaths[ag.CASTE] += 1
                self._release_loot(ag)
                self.events.append(("death", ag.y, ag.x))
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

        # 7. Game over (con periodo de gracia: solo si el estado irrecuperable se mantiene)
        self._check_game_over()

        # 8. Eventos para el audio (sin dependencias de la interfaz)
        bites = 0
        for ag in self.agents:
            if ag.alive and ag.attacking and bites < 3:
                self.events.append(("bite", ag.y, ag.x))
                bites += 1
        if self.tick % 8 == 0 and (a.fire.matrix > 0).any():
            ys, xs = np.nonzero(a.fire.matrix > 0)
            self.events.append(("fire", int(ys[len(ys) // 2]), int(xs[len(xs) // 2])))
        self.events.extend(a.events)
        a.events.clear()
        if len(self.events) > 300:
            del self.events[:-300]
    # ------------------------------------------------------------ fin de juego
    def _check_game_over(self):
        """La colonia está perdida si no queda ninguna obrera (viva, en cola o en desarrollo) y tampoco puede
        iniciar una cría de obrera DE VERDAD (con la reserva de ciclos y sin hongo famélico). Antes se comparaba
        sin la reserva: la colonia quedaba "viva" pero sin poder nacer nada y el juego se congelaba sin terminar.
        Debe mantenerse GAME_OVER_GRACE ticks seguidos para no disparar por un bache momentáneo."""
        if self.no_ants:
            return
        c = self.automaton.colony
        workers = sum(1 for ag in self.agents if ag.alive and ag.CASTE == "WORKER")
        pending = c.brood_count("WORKER") + sum(1 for q in self.queue if q == "WORKER")
        if workers or pending:
            self._doom = 0
            return
        rebuild = (not c.starving) and c.can_afford("WORKER", True, self._pop_counts())
        if rebuild:
            self._doom = 0
            return
        self._doom += 1
        if self._doom >= config.GAME_OVER_GRACE:
            self.game_over = True
            soldiers = sum(1 for ag in self.agents if ag.alive and ag.CASTE == "SOLDIER")
            self.game_over_reason = ("Sin obreras y sin reservas para criar otra"
                                     if c.starving or not rebuild else "Sin obreras")
            if soldiers == 0:
                self.game_over_reason = "La colonia desapareció"

    # ------------------------------------------------------------ clima y rayos
    def _apply_strikes(self):
        w = self.automaton.weather
        nest = self.nest
        for (y, x) in w.strikes:
            if (y, x) == nest:
                continue                          # bajo tierra
            for ag in self.agents:
                if ag.alive and ag.y == y and ag.x == x:
                    ag.die("LIGHTNING")
        w.strikes.clear()

    def _pick_cell(self, y, x):
        """Si no se da celda, elige una de tierra al azar (botones sin clic: Lluvia, Sequía)."""
        if y is not None and x is not None:
            return int(y), int(x)
        ys, xs = np.nonzero(self.automaton.terrain.matrix == DIRT)
        if len(ys) == 0:
            return self.nest
        i = random.randrange(len(ys))
        return int(ys[i]), int(xs[i])

    def rain(self, y=None, x=None, radius=None):
        self.automaton.rain(*self._pick_cell(y, x), radius)
        self.version += 1
        return True

    def drought(self, y=None, x=None, radius=None):
        self.automaton.drought(*self._pick_cell(y, x), radius)
        self.version += 1
        return True

    def lightning(self, y, x):
        """Rayo en una celda exacta: prende pasto/mango y mata al ente vivo que esté ahí."""
        a = self.automaton
        if not (0 <= y < a.height and 0 <= x < a.width):
            return False
        a.lightning(y, x, sure=True)
        self._apply_strikes()
        self.events.extend(a.events)
        a.events.clear()
        self.version += 1
        return True

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
        if self.no_ants or self.queue or self.tick % config.BIRTH_INTERVAL != 0 or colony.starving:
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
        if self.no_ants:
            return
        if self.automaton.colony.upkeep():
            self._starve_timer = 0
            return
        self._starve_timer += 1
        if self._starve_timer >= config.STARVATION_INTERVAL:
            self._starve_timer = 0
            victims = [ag for ag in self.agents if ag.alive and ag.CASTE != "MARABUNTA"]
            if victims:
                random.choice(victims).die("HUNGER")

    def _resolve_swaps(self, nest):
        """Modo "swap": si una aliada llegó a una celda donde otra se quedó, intercambian lugares (la que estaba
        pasa a la celda de la que llegó, si ahí no hay otra). Dos llegadas sin nadie que se quede siguen solapadas."""
        occ = {}
        for ag in self.agents:
            if ag.alive:
                occ.setdefault((ag.CASTE == "MARABUNTA", (ag.y, ag.x)), []).append(ag)
        for (mara, cell), group in list(occ.items()):
            if len(group) < 2 or cell == nest:
                continue
            arrivals = [g for g in group if (g.prev_y, g.prev_x) != cell]
            stayers = [g for g in group if (g.prev_y, g.prev_x) == cell]
            for arr in arrivals:
                if not stayers:
                    break
                dest = (arr.prev_y, arr.prev_x)
                if dest != nest and occ.get((mara, dest)):
                    continue
                other = stayers.pop()
                other.facing = (dest[0] - cell[0], dest[1] - cell[1])
                other.y, other.x = dest
                occ[(mara, cell)].remove(other)
                occ.setdefault((mara, dest), []).append(other)

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

    def _release_loot(self, ag):
        """Quien muere cargando botín lo deja en esa celda exacta, con la misma identidad."""
        a = self.automaton
        food, brood = {}, []
        if ag.CASTE == "MARABUNTA":
            food, brood = ag.loot_food, ag.loot_brood
            ag.loot_food, ag.loot_brood = {}, []
        elif getattr(ag, "carried_loot", None) is not None:
            food, brood = ag.carried_loot.food, ag.carried_loot.brood
            ag.carried_loot = None
        if food or brood:
            a.loot.drop(ag.y, ag.x, food, brood)

    def _make(self, caste, y, x):
        ag = CASTES[caste](y, x, self.nest, self.agents)
        if caste == "MARABUNTA":
            ag.advance = Marabunta.advance_for(self.automaton, y, x)
        return ag

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
        """n marabuntas en FILA contigua sobre una sola orilla (la más cercana al nido que cumpla SWARM_MIN_DIST),
        todas con el mismo avance hacia adentro. Gratis."""
        occ = self._occupied_mask()
        cells, adv = Marabunta.swarm_plan(self.automaton, n)
        made = 0
        for y, x in cells:
            if made >= n:
                break
            if occ[y, x]:
                continue
            ag = self._make("MARABUNTA", y, x)
            ag.advance = adv
            ag.facing = adv if adv != (0, 0) else ag.facing
            self.agents.append(ag)
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

    def paint_terrain(self, kind, cells, erase=False):
        """Pincel: pone ROCK/WATER/DIRT en varias celdas (no el nido ni bajo una hormiga). erase=True con DIRT también
        borra objetos y fuego. Devuelve cuántas celdas pintó."""
        a = self.automaton
        busy = {(ag.y, ag.x) for ag in self.agents}
        ok = [(y, x) for y, x in cells if (y, x) not in busy and (y, x) != self.nest]
        n = a.place_terrain_cells(ok, kind, clear=True if erase else None)
        if n:
            for ag in self.agents:
                if ag.alive and a.terrain.matrix[ag.y, ag.x] not in (DIRT, NEST):
                    ag.die("FIGHT")
            self.version += 1
            self.terrain_version += 1
        return n

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
            "loot": len(a.loot.items),
            "stolen": a.colony.stolen_units,
            "recovered": a.colony.recovered_units,
            "lost": a.colony.lost_units,
            "rain_zones": len(a.weather.zones_of("rain")),
            "drought_zones": len(a.weather.zones_of("drought")),
            "game_over": self.game_over,
            "game_over_reason": self.game_over_reason,
        }