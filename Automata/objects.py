import numpy as np
import config
from .grid import Grid
from .terrain import DIRT

# Object Constants
NONE, GRASS, MANGO, BOCADILLO = 0, 1, 2, 3
BOCADILLO_BITES = 4   # mordidas totales de un bocadillo (2x2)

# bocadillo_piece: 1 = sup-izq, 2 = sup-der, 3 = inf-izq, 4 = inf-der


class EnvironmentObjects(Grid):
    def __init__(self, width, height, seed=None):
        """matrix guarda el tipo; level el estado (pasto 1 ralo / 2 tupido); el resto es del bocadillo."""
        super().__init__(width, height, seed)
        shape = (height, width)
        self.matrix = np.full(shape, NONE, dtype=np.uint8)
        self.level = np.zeros(shape, dtype=np.uint8)
        self.bocadillo_piece = np.zeros(shape, dtype=np.uint8)
        self.bocadillo_id = np.zeros(shape, dtype=np.int32)
        self.bocadillo_bites = {}   # id -> mordidas restantes
        self._next_id = 1
        self.grass_max = 0
        self.mango_max = 0

    # ------------------------------------------------------------ generación
    def spawn_resources(self, terrain_matrix):
        """Generates initial grass and mango safely on valid DIRT cells."""
        valid_dirt = (terrain_matrix == DIRT)

        grass_spots = self.generate_spots(config.GRASS_DENSITY) > 0.5
        mango_spots = self.generate_spots(config.MANGO_DENSITY, iterations=2) > 0.5

        # Si la máscara de mango queda vacía, se fuerzan algunos puntos
        if not np.any(mango_spots & valid_dirt):
            y_indices = self.rng.integers(5, self.height - 5, size=3)
            x_indices = self.rng.integers(5, self.width - 5, size=3)
            for y, x in zip(y_indices, x_indices):
                if valid_dirt[y, x]:
                    mango_spots[y, x] = True

        self.matrix[valid_dirt & grass_spots] = GRASS
        self.matrix[valid_dirt & mango_spots] = MANGO   # el mango pisa al pasto
        self.level[self.matrix == GRASS] = 2
        self.level[self.matrix == MANGO] = 1

        self.grass_max = config.GRASS_MAX or int((self.matrix == GRASS).sum())
        self.mango_max = config.MANGO_MAX or max(1, int((self.matrix == MANGO).sum()))

    # ------------------------------------------------------------ consumo
    def consume(self, y, x):
        """Lo único que las hormigas llaman al tomar o comer algo. Devuelve el tipo consumido.
        Pasto: 2 -> 1 -> vacío. Mango: vacío. Bocadillo: 4 mordidas y se borran las 4 celdas."""
        kind = int(self.matrix[y, x])
        if kind == NONE:
            return NONE
        if kind == GRASS and self.level[y, x] > 1:
            self.level[y, x] -= 1
        elif kind == BOCADILLO:
            bid = int(self.bocadillo_id[y, x])
            left = self.bocadillo_bites.get(bid, 1) - 1
            if left <= 0:
                self._remove_bocadillo(bid)
            else:
                self.bocadillo_bites[bid] = left
        else:
            self._wipe((slice(y, y + 1), slice(x, x + 1)))
        return kind

    def clear_mask(self, mask):
        """Borra todo objeto bajo la máscara (lo usa el fuego). Un bocadillo se borra completo."""
        hit = mask & (self.matrix != NONE)
        if not hit.any():
            return
        for bid in np.unique(self.bocadillo_id[hit & (self.matrix == BOCADILLO)]):
            self._remove_bocadillo(int(bid))
        self._wipe(mask)

    def _wipe(self, idx):
        self.matrix[idx] = NONE
        self.level[idx] = 0
        self.bocadillo_piece[idx] = 0
        self.bocadillo_id[idx] = 0

    def _remove_bocadillo(self, bid):
        if bid == 0:
            return
        self._wipe(self.bocadillo_id == bid)
        self.bocadillo_bites.pop(bid, None)

    # ------------------------------------------------------------ colocación manual
    def _free(self, y, x, terrain_matrix, fire_matrix):
        return (0 <= y < self.height and 0 <= x < self.width
                and terrain_matrix[y, x] == DIRT and self.matrix[y, x] == NONE and fire_matrix[y, x] == 0)

    def place_resource(self, kind, y, x, terrain_matrix, fire_matrix):
        """Pone pasto (tupido) o mango en una celda de tierra libre."""
        if not self._free(y, x, terrain_matrix, fire_matrix):
            return False
        self.matrix[y, x] = kind
        self.level[y, x] = 2 if kind == GRASS else 1
        return True

    def place_bocadillo(self, y, x, terrain_matrix, fire_matrix):
        """(y, x) = esquina superior izquierda. Exige 4 celdas de tierra libres."""
        cells = [(y, x, 1), (y, x + 1, 2), (y + 1, x, 3), (y + 1, x + 1, 4)]
        if not all(self._free(cy, cx, terrain_matrix, fire_matrix) for cy, cx, _ in cells):
            return False
        bid = self._next_id
        self._next_id += 1
        for cy, cx, piece in cells:
            self.matrix[cy, cx] = BOCADILLO
            self.bocadillo_piece[cy, cx] = piece
            self.bocadillo_id[cy, cx] = bid
        self.bocadillo_bites[bid] = BOCADILLO_BITES
        return True

    # ------------------------------------------------------------ regeneración lenta
    def update(self, terrain_matrix, moisture, fire_matrix, tick):
        """Los brotes maduran poco a poco; solo brotan nuevos si estamos bajo el máximo."""
        young = (self.matrix == GRASS) & (self.level == 1)
        if young.any():
            grow = young & (self.rng.random(self.matrix.shape) < config.GRASS_MATURE_PROB)
            self.level[grow] = 2

        if tick % config.GRASS_SPROUT_INTERVAL == 0 and int((self.matrix == GRASS).sum()) < self.grass_max:
            self._sprout(GRASS, config.GRASS_SPROUT_COUNT, terrain_matrix, moisture, fire_matrix)
        if tick % config.MANGO_SPROUT_INTERVAL == 0 and int((self.matrix == MANGO).sum()) < self.mango_max:
            self._sprout(MANGO, 1, terrain_matrix, moisture, fire_matrix)

    def _sprout(self, kind, max_n, terrain_matrix, moisture, fire_matrix):
        """Brota 1..max_n plantitas (nivel 1), prefiriendo celdas húmedas y cercanas a su especie."""
        free = (terrain_matrix == DIRT) & (fire_matrix == 0) & (self.matrix == NONE)
        near = self.get_moore_average((self.matrix == kind).astype(np.float32))
        w = np.where(free, 0.05 + moisture + near, 0.0).astype(np.float64).ravel()
        total = w.sum()
        if total <= 0:
            return
        n = min(int(self.rng.integers(1, max_n + 1)), int(np.count_nonzero(w)))
        idx = self.rng.choice(w.size, size=n, replace=False, p=w / total)
        ys, xs = np.unravel_index(idx, self.matrix.shape)
        self.matrix[ys, xs] = kind
        self.level[ys, xs] = 1