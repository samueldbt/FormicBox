import numpy as np

class PheromoneLayer:
    def __init__(self, width, height, evap_rate, diff_rate, mode="sum"):
        """Initializes a single chemical field with specific evaporation and diffusion."""
        if mode not in ('sum','max'):
            raise ValueError(f"mode must be 'sum' or 'max', got {mode!r}")
        self.mode = mode
        self.matrix = np.zeros((height, width), dtype=np.float32)
        self.added = np.zeros((height, width), dtype=np.float32)
        self.evap_rate = evap_rate
        self.diff_rate = diff_rate

    def deposit(self, y, x, amount):
        """Adds pheromone amount to the deposition buffer for the current tick."""
        if self.mode == 'max':
            if amount > self.added[y,x]:
                self.added[y, x] += amount
        else:
            self.added[y,x] += amount
        

    def update(self, moore_avg, wind_shifted):
        """Applies exact diffusion, evaporation, wind, and active deposition equations."""
        new_tau = (1.0 - self.evap_rate) * self.matrix
        new_tau += self.diff_rate * (moore_avg - self.matrix)
        new_tau += wind_shifted 
        
        if self.mode == "max":
            new_tau = np.maximum(new_tau, self.added)
        else:
            new_tau += self.added
        
        self.matrix = np.clip(new_tau, 0.0, None)
        self.added.fill(0.0)