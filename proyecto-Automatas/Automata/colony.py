from .objects import GRASS, MANGO, BOCADILLO


class Colony:
    """Contadores de lo entregado al nido (base para las estadísticas)."""

    def __init__(self):
        self.delivered = {GRASS: 0, MANGO: 0, BOCADILLO: 0}

    def deliver(self, kind):
        kind = int(kind)
        if kind in self.delivered:
            self.delivered[kind] += 1