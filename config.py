"""Global configuration parameters and constants for the simulation."""

# World Settings
SEED = 1
WIDTH = 110
HEIGHT = 20
NEST = None  # If None, the procedural generator will pick a random valid spot

# Global Wind
WIND_X = 0.0
WIND_Y = 0.0

# Pheromone Parameters: (evaporation_rate, diffusion_rate)
PHEROMONE_VEGETAL = (0.01, 0.15)
PHEROMONE_SUGAR = (0.02, 0.10)
PHEROMONE_ALARM = (0.15, 0.25)
PHEROMONE_HUNT = (0.30, 0.05) 

# Fire Parameters
FIRE_BASE_PROB = 0.25
FIRE_WIND_C = 0.5

# Resource Densities
GRASS_DENSITY = 0.5
MANGO_DENSITY = 0.15
MIN_GRASS_THRESHOLD = 0.10
MIN_MANGO_THRESHOLD = 0.01

# Terrain & Recovery
MOISTURE_THRESHOLD = 0.40

# Ant Agents Configuration

# Ant States
STATE_EXPLORE = "EXPLORE"
STATE_RETURN = "RETURN"
STATE_FEED = "FEED"
STATE_FLEE = "FLEE"

# Energy Parameters
MAX_ENERGY = 100.0
LOW_ENERGY_THRESHOLD = 30.0
ENERGY_COST_PER_TICK = 1.0

# Foraging and Movement Weights (Section 5.3)
WEIGHT_VEGETAL = 2.0
WEIGHT_SUGAR = 3.0
WEIGHT_HOME = 5.0
WEIGHT_ALARM = 10.0
WEIGHT_FIRE = 15.0
WEIGHT_RANDOM = 1.0

# Pheromone Deposition
DEPOSIT_AMOUNT_GRASS = 30.0
DEPOSIT_AMOUNT_MANGO = 80.0  # Segregación superior para priorizar el mango
DEPOSIT_AMOUNT_BOCADILLO = 5.0

# Display & Simulation Settings (temporal)

CELL_SIZE = 12
FPS = 60
NUM_WORKERS = 100

# Colors (R, G, B)
COLOR_DIRT = (220, 200, 170)
COLOR_ROCK = (100, 100, 100)
COLOR_WATER = (70, 130, 180)
COLOR_NEST = (139, 69, 19)
COLOR_FIRE = (200, 40, 0)
COLOR_ASH = (50, 50, 50)

COLOR_GRASS = (34, 139, 34)
COLOR_MANGO = (255, 165, 0)
COLOR_BOCADILLO = (220, 20, 60)

# Ant Colors
COLOR_ANT_EMPTY = (0, 0, 0)
COLOR_ANT_LOADED = (255, 255, 255)