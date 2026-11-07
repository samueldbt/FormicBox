import numpy as np

class Grid:
    def __init__(self, width, height, seed=None):
        """Initializes grid dimensions and random number generator."""
        self.width = width
        self.height = height
        self.rng = np.random.default_rng(seed)

    def shift_array(self, arr, dy, dx):
        """Shifts a 2D array by dy and dx. Out-of-bounds become zero."""
        out = np.zeros_like(arr)
        h, w = arr.shape
        ys, yd = slice(max(dy, 0), h + min(dy, 0)), slice(max(-dy, 0), h + min(-dy, 0))
        xs, xd = slice(max(dx, 0), w + min(dx, 0)), slice(max(-dx, 0), w + min(-dx, 0))
        out[ys, xs] = arr[yd, xd]
        return out

    def get_moore_average(self, arr):
        """Calculates the average of the 8 Moore neighborhood cells."""
        shifts = [(-1, -1), (-1, 0), (-1, 1), (0, -1), 
                  (0, 1), (1, -1), (1, 0), (1, 1)]
        total = sum(self.shift_array(arr, dy, dx) for dy, dx in shifts)
        return total / 8.0

    def generate_spots(self, density, iterations=4):
        """Generates organic patches using a cellular automata smoothing rule."""
        cells = self.rng.random((self.height, self.width)) < density
        for _ in range(iterations):
            neighbors = sum(self.shift_array(cells, dy, dx) for dy, dx in 
                            [(-1, -1), (-1, 0), (-1, 1), (0, -1), 
                             (0, 1), (1, -1), (1, 0), (1, 1)])
            cells = (neighbors >= 5) | ((neighbors == 4) & cells)
        return cells.astype(np.float32)

    def get_orthogonal_neighbors(self, y, x):
        """Returns valid 4-way orthogonal neighbors for a given cell."""
        deltas = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        return [(y + dy, x + dx) for dy, dx in deltas 
                if 0 <= y + dy < self.height and 0 <= x + dx < self.width]