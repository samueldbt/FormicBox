import numpy as np
from collections import deque
from .grid import Grid
import config

# Terrain Constants
DIRT, ROCK, WATER, NEST = 0, 1, 2, 3

class Terrain(Grid):
    def __init__(self, width, height, seed):
        """Initializes the terrain matrix and static moisture map."""
        super().__init__(width, height, seed)
        self.matrix = np.full((height, width), DIRT, dtype=np.uint8)
        self.moisture = np.zeros((height, width), dtype=np.float32)
        self.nest_pos = config.NEST

    def generate(self, rock_density=None, water_density=None, nest_radius=3):
        """Generates procedural terrain ensuring connectivity and proper nest placement.

        If rock_density / water_density are None, config.ROCK_DENSITY and
        config.WATER_DENSITY are used.
        """
        if rock_density is None:
            rock_density = config.ROCK_DENSITY
        if water_density is None:
            water_density = config.WATER_DENSITY

        water_mask = self.generate_spots(water_density) > 0
        rock_mask = self.generate_spots(rock_density) > 0
        
        self.matrix[rock_mask] = ROCK
        self.matrix[water_mask] = WATER

        # 1. Pick nest location
        if self.nest_pos is None:
            self.nest_pos = self._choose_nest(nest_radius)

        # 2. Clear radius around nest
        ny, nx = self.nest_pos
        yy, xx = np.ogrid[:self.height, :self.width]
        zone = (yy - ny) ** 2 + (xx - nx) ** 2 <= (nest_radius + 2) ** 2
        self.matrix[zone] = DIRT
        self.matrix[ny, nx] = NEST

        # 3. Ensure connectivity (unreachable dirt becomes rock)
        self._ensure_connectivity()
        
        # 4. Precalculate moisture
        self._calculate_static_moisture()

    def _distance_to(self, mask):
        """Calculates distance from each cell to the closest cell in the mask."""
        dist = np.full((self.height, self.width), self.height + self.width, dtype=np.int32)
        line = deque()
        for y, x in zip(*np.nonzero(mask)):
            dist[y, x] = 0
            line.append((int(y), int(x)))
            
        while line:
            y, x = line.popleft()
            for vy, vx in self.get_orthogonal_neighbors(y, x):
                if dist[vy, vx] > dist[y, x] + 1:
                    dist[vy, vx] = dist[y, x] + 1
                    line.append((vy, vx))
        return dist

    def _largest_region(self, mask):
        """Finds and returns the largest connected region in a boolean mask."""
        seen = np.zeros_like(mask, dtype=bool)
        best = []
        for sy, sx in zip(*np.nonzero(mask)):
            if seen[sy, sx]: continue
            region = [(int(sy), int(sx))]
            seen[sy, sx] = True
            line = deque(region)
            while line:
                y, x = line.popleft()
                for vy, vx in self.get_orthogonal_neighbors(y, x):
                    if mask[vy, vx] and not seen[vy, vx]:
                        seen[vy, vx] = True
                        region.append((vy, vx))
                        line.append((vy, vx))
            if len(region) > len(best):
                best = region
                
        out = np.zeros_like(mask, dtype=bool)
        for y, x in best:
            out[y, x] = True
        return out

    def _choose_nest(self, nest_radius, min_water_dist=8, min_rock_dist=3):
        """Selects optimal nest location away from hazards and map edges."""
        margin = nest_radius + 2
        dirt_mask = self.matrix == DIRT
        region = self._largest_region(dirt_mask)
        
        if not region.any():
            return (self.height // 2, self.width // 2)

        dist_water = self._distance_to(self.matrix == WATER)
        dist_rock = self._distance_to(self.matrix == ROCK)
        yy, xx = np.mgrid[:self.height, :self.width]
        inside = ((yy >= margin) & (yy < self.height - margin) & 
                  (xx >= margin) & (xx < self.width - margin))

        dw, dr = min_water_dist, min_rock_dist
        while True:
            candidates = region & inside & (dist_water >= dw) & (dist_rock >= dr)
            if candidates.any(): break
            if dw <= 0 and dr <= 0: return (self.height // 2, self.width // 2)
            dw, dr = max(dw - 1, 0), max(dr - 1, 0)

        score = np.minimum(dist_water, 12) + 0.5 * np.minimum(dist_rock, 6)
        ys, xs = np.nonzero(candidates)
        values = score[ys, xs]
        keep = values >= np.quantile(values, 0.8)
        ys, xs = ys[keep], xs[keep]
        i = int(self.rng.integers(len(ys)))
        return (int(ys[i]), int(xs[i]))

    def _ensure_connectivity(self):
        """Converts dirt unreachable from the nest into rock."""
        visited = np.zeros_like(self.matrix, dtype=bool)
        line = deque([self.nest_pos])
        visited[self.nest_pos] = True
        
        while line:
            y, x = line.popleft()
            for vy, vx in self.get_orthogonal_neighbors(y, x):
                if not visited[vy, vx] and self.matrix[vy, vx] in (DIRT, NEST):
                    visited[vy, vx] = True
                    line.append((vy, vx))
                    
        alone = (self.matrix == DIRT) & ~visited
        self.matrix[alone] = ROCK

    # Indicate how far is each cell to the nest using a gradient field, giving the map, the number for the nest and the values of the cells the automata can walk 

    @staticmethod
    def nest_gradient_field (terrain, nest_value, walkable_values):
        h,w = terrain.shape

        # Minumun distance of each cell to the nest

        distance = np.full((h,w), np.inf)
        is_walkable = np.isin(terrain, list(walkable_values) + [nest_value])
        q = deque()

        # iterate through ordered pairs 

        for y, x in zip(*np.where(terrain == nest_value)):
            distance[y,x] = 0; q.append((int(y), int(x)))
        while q:
            y,x = q.popleft()
            for dy, dx in ((-1,0),(1,0),(0,-1),(0,1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and is_walkable[ny,nx] and distance[ny,nx] == np.inf:
                    distance[ny,nx] = distance[y,x] + 1; q.append((ny,nx))
        fin = np.isfinite(distance)
        dmax = max(distance[fin].max(), 1.0)

        # Give a float value between 0 and 1 to each cell reachable, when the cell is closer to the nest the value is higher

        home = np.where(fin, 1.0 - np.where(fin, distance, 0)/dmax, 0.0)
        return home.astype(np.float32), distance
        

    def _calculate_static_moisture(self, diffusion_steps=15):
        """Precalculates static moisture spreading outward from water cells."""
        self.moisture[self.matrix == WATER] = 1.0
        for _ in range(diffusion_steps):
            avg = self.get_moore_average(self.moisture)
            self.moisture = 0.7 * self.moisture + 0.3 * avg
            self.moisture[self.matrix == WATER] = 1.0