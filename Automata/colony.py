import math
import config
from enum import Enum
from .objects import GRASS, MANGO, BOCADILLO

KINDS = {"GRASS": GRASS, "MANGO": MANGO, "BOCADILLO": BOCADILLO}
NAMES = {v: k for k, v in KINDS.items()}


class FungusState(Enum):
    NORMAL = "NORMAL"
    ESTRESADO = "ESTRESADO"


class Colony:
    """Bolsa de alimento del nido, jardín fúngico, crías en desarrollo y hambre.

    La bolsa se mide en UNIDADES: 1 bocadillo = 2 mango = 3 pasto (config.FOOD_VALUE).
    Crías, hongo y comida de las hormigas se pagan en unidades, no en cantidades exactas de cada recurso.

      colony.food_units() / has_food()   -> alimento total
      colony.feed(need)                  -> una hormiga come; devuelve la energía ganada
      colony.can_afford(c, keep_reserve, pop) / pay(...) / start_brood(c, pop)
      colony.tick_brood()                -> castas que maduraron
      colony.upkeep()                    -> el hongo come; False si la bolsa está vacía
      colony.is_stressed()               -> True si hay demasiado bocadillo en reserva
    """

    def __init__(self):
        self.delivered = {GRASS: 0, MANGO: 0, BOCADILLO: 0}                       # acumulado histórico (items)
        self.stock = {k: int(config.START_STOCK.get(n, 0)) for n, k in KINDS.items()}   # reserva actual (items)
        self.credit = 0.0         # "cambio": sobrante cuando un pago se pasa de la cuenta
        self.stolen_units = 0.0     # robado por marabuntas (acumulado)
        self.lost_units = 0.0       # salió del mapa con una marabunta (perdido para siempre)
        self.recovered_units = 0.0  # rescatado por obreras y soldadas
        self.brood = []           # [{"caste", "ticks_left"}]
        self.starving = False
        self._tick = 0
        self.estado_hongo = FungusState.NORMAL
        self.update_fungus_state()
        self.update_starving()

    # ------------------------------------------------------------ bolsa
    @staticmethod
    def value(kind):
        return config.FOOD_VALUE[NAMES[int(kind)]]

    def food_units(self):
        return sum(q * self.value(k) for k, q in self.stock.items()) + self.credit

    def has_food(self):
        return self.food_units() >= 0.2

    def deliver(self, kind, quantity=1):
        kind = int(kind)
        if kind in self.stock:
            self.stock[kind] += quantity
            self.delivered[kind] += quantity
            self.update_fungus_state()
            self.update_starving()

    def delivered_units(self):
        return sum(q * self.value(k) for k, q in self.delivered.items())

    def consume(self, kind, quantity=1):
        kind = int(kind)
        if kind in self.stock:
            self.stock[kind] = max(0, self.stock[kind] - quantity)
            self.update_fungus_state()

    def _take_units(self, units, order):
        """Saca `units` unidades de la bolsa en el orden dado. Devuelve lo que NO pudo pagar."""
        left = float(units)
        if self.credit > 0:
            use = min(self.credit, left)
            self.credit -= use
            left -= use
        for name in order:
            if left <= 1e-9:
                break
            k, v = KINDS[name], config.FOOD_VALUE[name]
            if self.stock[k] <= 0 or v <= 0:
                continue
            n = min(self.stock[k], math.ceil(left / v - 1e-9))
            self.stock[k] -= n
            left -= n * v
        if left < -1e-9:
            self.credit += -left       # se pasó de la cuenta: guarda el cambio
            left = 0.0
        self.update_fungus_state()
        return max(0.0, left)

    def feed(self, need):
        """Una hormiga come para recuperar hasta `need` de energía. Devuelve la energía ganada.
        No gasta un item entero si solo necesita menos de la mitad de lo que da."""
        gained = 0.0
        for name in config.EAT_ORDER:
            k = KINDS[name]
            e_item = config.ENERGY_PER_UNIT * config.FOOD_VALUE[name]
            while self.stock[k] > 0 and need - gained >= 0.5 * e_item:
                self.stock[k] -= 1
                gained += e_item
        self.update_fungus_state()
        self.update_starving()
        return gained

    # ------------------------------------------------------------ hongo
    def update_fungus_state(self):
        """ESTRESADO si la reserva de bocadillo supera T_SUGAR; si no, NORMAL."""
        if self.stock[BOCADILLO] > config.T_SUGAR:
            self.estado_hongo = FungusState.ESTRESADO
        else:
            self.estado_hongo = FungusState.NORMAL

    def is_stressed(self):
        return self.estado_hongo == FungusState.ESTRESADO

    def update_starving(self):
        self.starving = self.food_units() < config.FUNGUS_COST

    def upkeep(self):
        """El hongo come FUNGUS_COST unidades cada FUNGUS_EVERY ticks. False mientras la bolsa esté vacía."""
        self._tick += 1
        if self._tick % config.FUNGUS_EVERY == 0:
            self._take_units(config.FUNGUS_COST, config.PAY_ORDER)
        self.update_starving()
        return not self.starving

    # ------------------------------------------------------------ crías
    @staticmethod
    def demand_cycle(workers, soldiers):
        d = config.DEMAND_CYCLE
        return workers * d["WORKER"] + soldiers * d["SOLDIER"]

    def reserve_needed(self, workers, soldiers):
        """Unidades que deben quedar para alimentar a esa población (y al hongo) RESERVE_CYCLES ciclos."""
        fungus = config.FUNGUS_COST * config.CYCLE_TICKS / config.FUNGUS_EVERY
        return config.RESERVE_CYCLES * (self.demand_cycle(workers, soldiers) + fungus)

    def can_afford(self, caste, keep_reserve=False, pop=(0, 0)):
        """pop = (obreras, soldadas) contando vivas, en cola y en desarrollo."""
        cost = config.CASTE_COST[caste]
        units = self.food_units()
        if units < cost:
            return False
        if keep_reserve:
            w, s = pop
            w += caste == "WORKER"
            s += caste == "SOLDIER"
            if units - cost < self.reserve_needed(w, s):
                return False
        return True

    def pay(self, caste, keep_reserve=False, pop=(0, 0)):
        if not self.can_afford(caste, keep_reserve, pop):
            return False
        self._take_units(config.CASTE_COST[caste], config.PAY_ORDER)
        self.update_starving()
        return True

    def start_brood(self, caste, pop=(0, 0)):
        """Paga y deja la cría en desarrollo, solo con el excedente sobre la reserva de 3 ciclos."""
        if not self.pay(caste, True, pop):
            return False
        self.brood.append({"caste": caste, "ticks_left": int(config.DEV_TICKS[caste])})
        return True

    def tick_brood(self):
        matured, rest = [], []
        for b in self.brood:
            b["ticks_left"] -= 1
            (matured if b["ticks_left"] <= 0 else rest).append(b)
        self.brood = rest
        return [b["caste"] for b in matured]

    def brood_count(self, caste=None):
        return sum(1 for b in self.brood if caste is None or b["caste"] == caste)

    # ------------------------------------------------------------ saqueo y botín (Fase 4)
    @staticmethod
    def loot_units(food, brood):
        """Valor en unidades de bolsa de un botín: comida + lo que costó cada cría."""
        u = sum(q * config.FOOD_VALUE[NAMES[int(k)]] for k, q in food.items())
        return u + sum(config.CASTE_COST[b["caste"]] for b in brood)

    def steal_brood(self, n):
        """Quita hasta n crías en desarrollo (conservan su tiempo restante). Devuelve la lista."""
        taken, self.brood = self.brood[:n], self.brood[n:]
        self.stolen_units += self.loot_units({}, taken)
        return taken

    def steal_food(self, n):
        """Quita hasta n items de la bolsa (lo más valioso primero). Devuelve {tipo: cantidad}."""
        out = {}
        for name in config.EAT_ORDER:
            if n <= 0:
                break
            k = KINDS[name]
            take = min(self.stock[k], n)
            if take > 0:
                self.stock[k] -= take
                out[k] = out.get(k, 0) + take
                n -= take
        self.stolen_units += self.loot_units(out, [])
        self.update_fungus_state()
        self.update_starving()
        return out

    def return_loot(self, loot):
        """Un botín rescatado vuelve al nido: la comida a la bolsa y las crías a desarrollo."""
        for k, q in loot.food.items():
            self.stock[k] += q
        self.brood.extend(loot.brood)
        self.recovered_units += self.loot_units(loot.food, loot.brood)
        self.update_fungus_state()
        self.update_starving()