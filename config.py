"""Global configuration parameters and constants for the simulation."""

# GRUPO 4: Integración 
COLLISION_MODE = "allies_pass"   # o "block"
INITIAL_WORKERS = 20
INITIAL_SOLDIERS = 3
BIRTH_INTERVAL = 3
BIRTH_SOLDIER_RATIO = 0.15
MAX_POPULATION = 100             # ajusta viendo la simulación
STARVATION_INTERVAL = 10         # ajusta viendo la simulación

# World Settings
SEED = 1
WIDTH = 110
HEIGHT = 20
NEST = None  # If None, the procedural generator will pick a random valid spot

# Global Wind
WIND_X = 0.0
WIND_Y = 0.0
WIND_STEP = 1.0   # intensidad que aplican los botones de viento

# Pheromone Parameters: (evaporation_rate, diffusion_rate)
PHEROMONE_VEGETAL = (0.01, 0.15)
PHEROMONE_SUGAR = (0.02, 0.10)
PHEROMONE_ALARM = (0.15, 0.25)
PHEROMONE_HUNT = (0.30, 0.05)

# Fire Parameters
FIRE_BASE_PROB = 0.25
FIRE_WIND_C = 0.5
ASH_TICKS = 20               # ticks que dura la ceniza antes de volver a tierra desnuda

# Terrain Densities (generación inicial del mapa)
ROCK_DENSITY = 0.40
WATER_DENSITY = 0.38

# Resource Densities (generación inicial)
GRASS_DENSITY = 0.5
MANGO_DENSITY = 0.015        # fracción de la tierra cubierta por mango (cada mango ocupa 2x2 = 4 celdas)

# Mordidas totales de los objetos de 2x2 (cada mordida = lo que carga una obrera)
MANGO_BITES = 4
BOCADILLO_BITES = 4

# Threshold for the sugar
T_SUGAR = 10

# Regeneración lenta. None = el máximo es lo que haya al generar el mapa
GRASS_MAX = None             # máximo de celdas con pasto
MANGO_MAX = None             # máximo de OBJETOS mango (bloques 2x2), no de celdas
GRASS_SPROUT_INTERVAL = 20   # cada cuántos ticks puede brotar pasto (solo si está bajo el máximo)
GRASS_SPROUT_COUNT = 3       # brotes máximos por intervalo
GRASS_MATURE_PROB = 1 / 60   # prob. por tick de que un brote (nivel 1) se vuelva tupido (nivel 2)
MANGO_SPROUT_INTERVAL = 60

# Ya no se usa para la ceniza (ahora es ASH_TICKS); se deja por compatibilidad
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
DEPOSIT_AMOUNT_DEATH_ALARM = 40.0   # alarma que deja una hormiga (no marabunta) al morir

# Población y tiempo
#NUM_WORKERS = 40
#NUM_SOLDIERS = 6
SPAWN_PER_TICK = 2           # hormigas que salen del nido por tick
SWARM_SIZE = 10              # tamaño del enjambre del botón de depuración
CORPSE_TICKS = 1             # ticks que un cadáver estorba
TRAFFIC_DECAY = 0.995        # el mapa de tráfico olvida lentamente

TICK_SECONDS = 1.0           # 1 tick lógico = 1 s a velocidad x1
ANIM_FRAMES = 6              # frames de animación por tick
FPS = 60
MAX_STEPS_PER_FRAME = 4      # evita la "espiral" si el PC se atrasa

# Display
TILE = 32
SCREEN_W = 1280
SCREEN_H = 720
PANEL_W = 290
CAMERA_SPEED = 700           # px/s

# Feromonas: nombre -> (color RGB, escala de intensidad, K de saturación t/(t+K))
PHEROMONE_VIEW_INTENSITY = 1.0   # global: 0 = invisible, 1 = normal, >1 más fuerte
PHEROMONE_SMOOTH = True          # True = se ve como nube; False = cuadrículas nítidas
PHEROMONE_VIEW = {
    "vegetal": ((60, 220, 60), 1.0, 10.0),
    "azucar": ((255, 90, 200), 1.0, 5.0),
    "alarma": ((255, 40, 40), 1.0, 5.0),
    "caza": ((170, 70, 255), 1.0, 10.0),
}
GRADIENT_COLOR = (0, 200, 255)
TRAFFIC_COLOR = (255, 230, 0)

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

# Ant Colors (solo para los placeholders cuando falta el arte)
COLOR_ANT_EMPTY = (0, 0, 0)
COLOR_ANT_LOADED = (255, 255, 255)
COLORS_CASTE = {
    "WORKER": (120, 60, 20),
    "SOLDIER": (170, 30, 30),
    "MARABUNTA": (70, 30, 110),
}
