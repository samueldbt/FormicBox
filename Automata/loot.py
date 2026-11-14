"""Botín: lo que una marabunta robó y soltó al morir. Conserva la identidad exacta de lo robado."""


class Loot:
    """food: {tipo de objeto: cantidad}. brood: [{"caste", "ticks_left"}] (cada cría conserva su tiempo restante)."""

    def __init__(self, food=None, brood=None):
        self.food = {int(k): int(q) for k, q in (food or {}).items() if q > 0}
        self.brood = [dict(b) for b in (brood or [])]

    def merge(self, other):
        for k, q in other.food.items():
            self.food[k] = self.food.get(k, 0) + q
        self.brood.extend(other.brood)


class LootLayer:
    def __init__(self):
        self.items = {}          # (y, x) -> Loot

    def at(self, y, x):
        return self.items.get((y, x))

    def drop(self, y, x, food, brood):
        """Deja un botín en (y, x). Si ya había uno, se junta con él."""
        new = Loot(food, brood)
        if not new.food and not new.brood:
            return
        cur = self.items.get((y, x))
        if cur is None:
            self.items[(y, x)] = new
        else:
            cur.merge(new)

    def take(self, y, x):
        return self.items.pop((y, x), None)

    def clear_where(self, mask):
        """Borra el botín bajo la máscara (fuego, terreno nuevo)."""
        for (y, x) in list(self.items):
            if mask[y, x]:
                del self.items[(y, x)]