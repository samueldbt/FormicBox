import numpy as np
import config
from .grid import Grid
from .terrain import DIRT

# Object Constants
NONE, GRASS, MANGO, BOCADILLO = 0, 1, 2, 3
BOCADILLO_BITES = getattr(config, "BOCADILLO_BITES", 4)   # alias antiguo; el valor real se lee de config en cada uso

# Mango y bocadillo son objetos de 2x2 celdas: comparten id, pieza y mordidas.
BLOCK_KINDS = (MANGO, BOCADILLO)

# object_piece: 1 = sup-izq, 2 = sup-der, 3 = inf-izq, 4 = inf-der
BLOCK_CELLS = ((0, 0, 1), (0, 1, 2), (1, 0, 3), (1, 1, 4))   # (dy, dx, pieza)


def total_bites(kind):
    """Mordidas totales de un objeto 2x2 (se leen de config para poder editarlas)."""
    if kind == MANGO:
        return getattr(config, "MANGO_BITES", 4)
    return getattr(config, "BOCADILLO_BITES", 4)


def _quad_mean(arr):
    """Promedio de las 4 celdas de cada bloque 2x2 (resultado de tamaño (h-1, w-1))."""
    return (arr[:-1, :-1] + arr[:-1, 1:] + arr[1:, :-1] + arr[1:, 1:]) / 4.0


class EnvironmentObjects(Grid):
    def __init__(self, width, height, seed=None):
        """matrix guarda el tipo; level el estado (pasto 1 ralo / 2 tupido); el resto es de los objetos 2x2."""
        super().__init__(width, height, seed)
        shape = (height, width)
        self.matrix = np.full(shape, NONE, dtype=np.uint8)
        self.level = np.zeros(shape, dtype=np.uint8)

        # Objetos 2x2 (mango y bocadillo)
        self.object_piece = np.zeros(shape, dtype=np.uint8)
        self.object_id = np.zeros(shape, dtype=np.int32)
        self.object_bites = {}   # id -> mordidas restantes
        self.object_kind = {}    # id -> MANGO o BOCADILLO

        # Nombres antiguos (los usa la interfaz): apuntan a las mismas matrices
        self.bocadillo_piece = self.object_piece
        self.bocadillo_id = self.object_id

        self._next_id = 1
        self.grass_max = 0
        self.mango_max = 0   # cuenta OBJETOS (bloques 2x2), no celdas

    @property
    def bocadillo_bites(self):
        """Nombre antiguo: mordidas restantes de cada bocadillo (id -> mordidas)."""
        return {i: b for i, b in self.object_bites.items() if self.object_kind.get(i) == BOCADILLO}

    def count(self, kind):
        """Cantidad de objetos de un tipo: celdas para el pasto, bloques 2x2 para mango y bocadillo."""
        if kind in BLOCK_KINDS:
            return sum(1 for k in self.object_kind.values() if k == kind)
        return int((self.matrix == kind).sum())

    # ------------------------------------------------------------ generación
    def spawn_resources(self, terrain_matrix):
        """Generates initial grass and mango (2x2 blocks) safely on valid DIRT cells."""
        valid_dirt = (terrain_matrix == DIRT)

        grass_spots = self.generate_spots(config.GRASS_DENSITY) > 0.5
        self.matrix[valid_dirt & grass_spots] = GRASS
        self.level[self.matrix == GRASS] = 2

        self._spawn_mangos(valid_dirt)   # el mango pisa al pasto

        self.grass_max = config.GRASS_MAX or int((self.matrix == GRASS).sum())
        self.mango_max = config.MANGO_MAX or max(1, self.count(MANGO))

    def _spawn_mangos(self, valid_dirt):
        """Reparte mangos de 2x2 sobre bloques de 4 celdas de tierra.
        MANGO_DENSITY = fracción de la tierra que cubre el mango (cada mango ocupa 4 celdas)."""
        anchors = (valid_dirt[:-1, :-1] & valid_dirt[:-1, 1:]
                   & valid_dirt[1:, :-1] & valid_dirt[1:, 1:])
        ys, xs = np.nonzero(anchors)
        if len(ys) == 0:
            return
        want = max(1, int(round(config.MANGO_DENSITY * int(valid_dirt.sum()) / 4.0)))
        for i in self.rng.permutation(len(ys)):
            if want <= 0:
                break
            y, x = int(ys[i]), int(xs[i])
            if (self.matrix[y:y + 2, x:x + 2] == MANGO).any():   # no se encima con otro mango
                continue
            self._put_block(MANGO, y, x)
            want -= 1

    # ------------------------------------------------------------ consumo
    def consume(self, y, x):
        """Lo único que las hormigas llaman al tomar o comer algo. Devuelve el tipo consumido.
        Pasto: 2 -> 1 -> vacío. Mango y bocadillo: una mordida por llamada; al llegar a 0 se borran las 4 celdas."""
        kind = int(self.matrix[y, x])
        if kind == NONE:
            return NONE
        if kind == GRASS and self.level[y, x] > 1:
            self.level[y, x] -= 1
        elif kind in BLOCK_KINDS and int(self.object_id[y, x]) in self.object_bites:
            self._bite(int(self.object_id[y, x]))
        else:
            self._wipe((slice(y, y + 1), slice(x, x + 1)))
        return kind

    def _bite(self, oid):
        left = self.object_bites.get(oid, 1) - 1
        if left <= 0:
            self._remove_object(oid)
        else:
            self.object_bites[oid] = left

    def clear_mask(self, mask):
        """Borra todo objeto bajo la máscara (lo usa el fuego). Un mango o bocadillo se borra completo."""
        hit = mask & (self.matrix != NONE)
        if not hit.any():
            return
        for oid in np.unique(self.object_id[hit]):
            self._remove_object(int(oid))
        self._wipe(mask)

    def _wipe(self, idx):
        self.matrix[idx] = NONE
        self.level[idx] = 0
        self.object_piece[idx] = 0
        self.object_id[idx] = 0

    def _remove_object(self, oid):
        if oid == 0:
            return
        self._wipe(self.object_id == oid)
        self.object_bites.pop(oid, None)
        self.object_kind.pop(oid, None)

    def _remove_bocadillo(self, bid):
        """Nombre antiguo de _remove_object."""
        self._remove_object(bid)

    # ------------------------------------------------------------ colocación manual
    def _free(self, y, x, terrain_matrix, fire_matrix):
        return (0 <= y < self.height and 0 <= x < self.width
                and terrain_matrix[y, x] == DIRT and self.matrix[y, x] == NONE and fire_matrix[y, x] == 0)

    def _put_block(self, kind, y, x):
        """Escribe un objeto 2x2 con (y, x) como esquina superior izquierda (sin validar)."""
        oid = self._next_id
        self._next_id += 1
        for dy, dx, piece in BLOCK_CELLS:
            self.matrix[y + dy, x + dx] = kind
            self.level[y + dy, x + dx] = 1 if kind == MANGO else 0
            self.object_piece[y + dy, x + dx] = piece
            self.object_id[y + dy, x + dx] = oid
        self.object_bites[oid] = total_bites(kind)
        self.object_kind[oid] = kind
        return oid

    def _place_block(self, kind, y, x, terrain_matrix, fire_matrix):
        """(y, x) = esquina superior izquierda. Exige 4 celdas de tierra libres."""
        if not all(self._free(y + dy, x + dx, terrain_matrix, fire_matrix) for dy, dx, _ in BLOCK_CELLS):
            return False
        self._put_block(kind, y, x)
        return True

    def place_resource(self, kind, y, x, terrain_matrix, fire_matrix):
        """Pone pasto (tupido) en una celda libre, o un mango de 2x2 con (y, x) como esquina superior izquierda."""
        if kind in BLOCK_KINDS:
            return self._place_block(kind, y, x, terrain_matrix, fire_matrix)
        if not self._free(y, x, terrain_matrix, fire_matrix):
            return False
        self.matrix[y, x] = kind
        self.level[y, x] = 2 if kind == GRASS else 1
        return True

    def place_bocadillo(self, y, x, terrain_matrix, fire_matrix):
        """(y, x) = esquina superior izquierda. Exige 4 celdas de tierra libres."""
        return self._place_block(BOCADILLO, y, x, terrain_matrix, fire_matrix)

    # ------------------------------------------------------------ regeneración lenta
    def update(self, terrain_matrix, moisture, fire_matrix, tick):
        """Los brotes maduran poco a poco; solo brotan nuevos si estamos bajo el máximo."""
        young = (self.matrix == GRASS) & (self.level == 1)
        if young.any():
            grow = young & (self.rng.random(self.matrix.shape) < config.GRASS_MATURE_PROB)
            self.level[grow] = 2

        if tick % config.GRASS_SPROUT_INTERVAL == 0 and int((self.matrix == GRASS).sum()) < self.grass_max:
            self._sprout(GRASS, config.GRASS_SPROUT_COUNT, terrain_matrix, moisture, fire_matrix)
        if tick % config.MANGO_SPROUT_INTERVAL == 0 and self.count(MANGO) < self.mango_max:
            self._sprout(MANGO, 1, terrain_matrix, moisture, fire_matrix)

    def _sprout(self, kind, max_n, terrain_matrix, moisture, fire_matrix):
        """Brota 1..max_n plantitas (nivel 1), prefiriendo celdas húmedas y cercanas a su especie.
        El mango brota como un bloque completo de 2x2."""
        if kind in BLOCK_KINDS:
            self._sprout_block(kind, max_n, terrain_matrix, moisture, fire_matrix)
            return
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

    def _sprout_block(self, kind, max_n, terrain_matrix, moisture, fire_matrix):
        """Brota 1..max_n objetos 2x2 en bloques de 4 celdas libres, prefiriendo humedad y cercanía."""
        for _ in range(int(self.rng.integers(1, max_n + 1))):
            free = (terrain_matrix == DIRT) & (fire_matrix == 0) & (self.matrix == NONE)
            ok = free[:-1, :-1] & free[:-1, 1:] & free[1:, :-1] & free[1:, 1:]
            if not ok.any():
                return
            near = self.get_moore_average((self.matrix == kind).astype(np.float32))
            score = 0.05 + _quad_mean(moisture) + _quad_mean(near)
            w = np.where(ok, score, 0.0).astype(np.float64).ravel()
            idx = self.rng.choice(w.size, p=w / w.sum())
            y, x = np.unravel_index(idx, ok.shape)
            self._put_block(kind, int(y), int(x))
