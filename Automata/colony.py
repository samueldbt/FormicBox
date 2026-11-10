import config
from enum import Enum
from .objects import GRASS, MANGO, BOCADILLO


class FungusState(Enum):
    NORMAL = "NORMAL"
    ESTRESADO = "ESTRESADO"


class Colony:
    """Reservas entregadas al nido y estado del jardín fúngico.

    Uso desde fuera: automaton.colony.is_stressed() -> True / False.
    """

    def __init__(self):
        self.delivered = {GRASS: 0, MANGO: 0, BOCADILLO: 0}
        self.estado_hongo = FungusState.NORMAL

    def deliver(self, kind, quantity=1):
        """Suma lo entregado al nido y actualiza el estado del hongo."""
        kind = int(kind)
        if kind in self.delivered:
            self.delivered[kind] += quantity
            self.update_fungus_state()

    def consume(self, kind, quantity=1):
        """Resta de la reserva (nunca baja de 0) y actualiza el estado del hongo."""
        kind = int(kind)
        if kind in self.delivered:
            self.delivered[kind] = max(0, self.delivered[kind] - quantity)
            self.update_fungus_state()

    def update_fungus_state(self):
        """ESTRESADO si la reserva de bocadillo supera T_SUGAR; si no, NORMAL."""
        if self.delivered[BOCADILLO] > config.T_SUGAR:
            self.estado_hongo = FungusState.ESTRESADO
        else:
            self.estado_hongo = FungusState.NORMAL

    def is_stressed(self):
        return self.estado_hongo == FungusState.ESTRESADO
