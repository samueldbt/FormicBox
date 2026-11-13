import config
from enum import Enum
from .objects import GRASS, MANGO, BOCADILLO

KINDS = {"GRASS": GRASS, "MANGO": MANGO, "BOCADILLO": BOCADILLO}


class FungusState(Enum):
    NORMAL = "NORMAL"
    ESTRESADO = "ESTRESADO"


class Colony:
    """Reservas del nido, jardín fúngico, crías en desarrollo y hambre.

    Uso desde fuera:
      colony.is_stressed()          -> True / False
      colony.has_food() / eat()     -> comida para las hormigas (devuelve energía ganada)
      colony.can_afford(c) / pay(c) -> costo de una casta ("WORKER" / "SOLDIER")
      colony.start_brood(c)         -> paga y deja la cría en desarrollo
      colony.tick_brood()           -> avanza el desarrollo; devuelve las castas que maduraron
      colony.upkeep()               -> el hongo come; False si el nido está en hambruna
    """

    def __init__(self):
        self.delivered = {GRASS: 0, MANGO: 0, BOCADILLO: 0}     # acumulado histórico
        self.stock = {k: int(config.START_STOCK[n]) for n, k in KINDS.items()}   # reserva actual
        self.brood = []                                          # [{"caste", "ticks_left"}]
        self.starving = False
        self._tick = 0
        self.estado_hongo = FungusState.NORMAL
        self.update_fungus_state()

    # ------------------------------------------------------------ reservas
    def deliver(self, kind, quantity=1):
        kind = int(kind)
        if kind in self.stock:
            self.stock[kind] += quantity
            self.delivered[kind] += quantity
            self.update_fungus_state()

    def consume(self, kind, quantity=1):
        """Resta de la reserva (nunca baja de 0)."""
        kind = int(kind)
        if kind in self.stock:
            self.stock[kind] = max(0, self.stock[kind] - quantity)
            self.update_fungus_state()

    def vegetal(self):
        return self.stock[GRASS] + self.stock[MANGO]

    def has_food(self):
        return any(q > 0 for q in self.stock.values())

    def eat(self):
        """Una hormiga come una unidad de la reserva. Devuelve la energía ganada (0 si no hay)."""
        for name in config.EAT_ORDER:
            k = KINDS[name]
            if self.stock[k] > 0:
                self.consume(k)
                return float(config.ENERGY_PER_FOOD[name])
        return 0.0

    # ------------------------------------------------------------ hongo
    def update_fungus_state(self):
        """ESTRESADO si la reserva de bocadillo supera T_SUGAR; si no, NORMAL."""
        if self.stock[BOCADILLO] > config.T_SUGAR:
            self.estado_hongo = FungusState.ESTRESADO
        else:
            self.estado_hongo = FungusState.NORMAL

    def is_stressed(self):
        return self.estado_hongo == FungusState.ESTRESADO

    def upkeep(self):
        """El hongo come cada FUNGUS_INTERVAL ticks. Devuelve False mientras no haya con qué alimentarlo."""
        self._tick += 1
        if self._tick % config.FUNGUS_INTERVAL == 0:
            need = config.FUNGUS_COST
            have = self.vegetal()
            take = min(need, have)
            for k in (GRASS, MANGO):
                q = min(take, self.stock[k])
                self.consume(k, q)
                take -= q
            self.starving = have < need
        return not self.starving

    # ------------------------------------------------------------ crías
    def _cost(self, caste):
        return {KINDS[n]: q for n, q in config.CASTE_COST[caste].items()}

    def reserve_needed(self):
        """Pasto/mango que debe quedar para mantener el hongo RESERVE_CYCLES ciclos más."""
        return config.FUNGUS_COST * config.RESERVE_CYCLES

    def can_afford(self, caste, keep_reserve=False):
        cost = self._cost(caste)
        if any(self.stock[k] < q for k, q in cost.items()):
            return False
        if keep_reserve:
            left = self.vegetal() - sum(q for k, q in cost.items() if k in (GRASS, MANGO))
            if left < self.reserve_needed():
                return False
        return True

    def pay(self, caste, keep_reserve=False):
        if not self.can_afford(caste, keep_reserve):
            return False
        for k, q in self._cost(caste).items():
            self.consume(k, q)
        return True

    def start_brood(self, caste, keep_reserve=True):
        """Paga y deja la cría en desarrollo (el excedente sobre la reserva de 3 ciclos)."""
        if not self.pay(caste, keep_reserve):
            return False
        self.brood.append({"caste": caste, "ticks_left": int(config.DEV_TICKS[caste])})
        return True

    def tick_brood(self):
        """Avanza un tick el desarrollo. Devuelve la lista de castas que maduraron."""
        matured, rest = [], []
        for b in self.brood:
            b["ticks_left"] -= 1
            (matured if b["ticks_left"] <= 0 else rest).append(b)
        self.brood = rest
        return [b["caste"] for b in matured]

    def brood_count(self, caste=None):
        return sum(1 for b in self.brood if caste is None or b["caste"] == caste)