"""Global configuration parameters and constants for the simulation."""

# GRUPO 4: Integración
COLLISION_MODE = "allies_pass"   # o "block"
INITIAL_WORKERS = 20
INITIAL_SOLDIERS = 3
BIRTH_INTERVAL = 3               # cada cuántos ticks se intenta iniciar una cría
BIRTH_SOLDIER_RATIO = 0.15
MAX_POPULATION = 100             # cuenta vivas + cola de salida + crías en desarrollo
STARVATION_INTERVAL = 10         # con el hongo sin comida, muere una hormiga cada tantos ticks

# Rendimiento
USE_SCIPY_CONVOLUTION = True     # usa scipy.ndimage.convolve si está instalado

# World Settings
SEED = 1
WIDTH = 110
HEIGHT = 20
NEST = None  # If None, the procedural generator will pick a random valid spot

# Global Wind
WIND_X = 0.0
WIND_Y = 0.0
WIND_STEP = 1.0

# Pheromone Parameters: (evaporation_rate, diffusion_rate)
# Evaporación 0.03 => el rastro se multiplica por 0.97 cada tick. Difusión baja (~0.03).
PHEROMONE_VEGETAL = (0.03, 0.08)
PHEROMONE_SUGAR = (0.02, 0.03)
PHEROMONE_ALARM = (0.35, 0.05)
PHEROMONE_HUNT = (0.30, 0.05)
# "max": el depósito toma el máximo (autopistas limpias). "sum": suma (satura). Para el sandbox.
PHEROMONE_MODE = {"vegetal": "max", "azucar": "max", "alarma": "sum", "caza": "sum"}

# Rastro con dirección: la obrera sale del recurso con fuerza 1.0 y la multiplica por
# TRAIL_DECAY en cada paso, así la feromona forma una pendiente que sube hacia el recurso.
TRAIL_DECAY = 0.97

# Fire Parameters
FIRE_BASE_PROB = 0.25
FIRE_WIND_C = 0.5
ASH_TICKS = 20
FIRE_ALERT_RADIUS = 2        # a esta distancia (Chebyshev) del fuego las hormigas huyen

# Terrain Densities
ROCK_DENSITY = 0.40
WATER_DENSITY = 0.38

# Resource Densities
GRASS_DENSITY = 0.5
MANGO_DENSITY = 0.015

# Mordidas totales de los objetos 2x2 (cada mordida = lo que carga una obrera)
MANGO_BITES = 8
BOCADILLO_BITES = 8

# Threshold for the sugar (reserva de bocadillo por encima de la cual el hongo se estresa)
T_SUGAR = 10

# Regeneración lenta
GRASS_MAX = None
MANGO_MAX = None
GRASS_SPROUT_INTERVAL = 20
GRASS_SPROUT_COUNT = 3
GRASS_MATURE_PROB = 1 / 60
MANGO_SPROUT_INTERVAL = 60

MOISTURE_THRESHOLD = 0.40    # compatibilidad

# ------------------------------------------------------------ Economía del nido (Fase 3)
# Unidades: 1 unidad = lo que carga una obrera en un viaje (una mordida).
START_STOCK = {"GRASS": 30, "MANGO": 10, "BOCADILLO": 0}
FUNGUS_INTERVAL = 5          # cada cuántos ticks come el hongo
FUNGUS_COST = 1              # unidades de pasto/mango que come el hongo por consumo
RESERVE_CYCLES = 3           # ciclos de hongo que deben quedar cubiertos antes de gastar en crías
CASTE_COST = {               # costo de crear una hormiga
    "WORKER": {"GRASS": 6, "MANGO": 2},
    "SOLDIER": {"GRASS": 8, "MANGO": 3},
}
DEV_TICKS = {"WORKER": 20, "SOLDIER": 35}   # ticks de desarrollo de la cría

# Energía de cada hormiga
MAX_ENERGY = 100.0
LOW_ENERGY_THRESHOLD = 30.0
ENERGY_COST_PER_TICK = 0.5
ENERGY_PER_FOOD = {"BOCADILLO": 120.0, "MANGO": 60.0, "GRASS": 20.0}   # energía por unidad comida
EAT_ORDER = ("BOCADILLO", "MANGO", "GRASS")   # qué come primero del nido
REFUEL_BELOW = 70.0          # en el nido come si tiene menos energía que esto
EAT_MAP_BELOW = 60.0         # come un bocadillo del mapa si tiene menos que esto

# ------------------------------------------------------------ Ant Agents
STATE_EXPLORE = "EXPLORE"
STATE_RETURN = "RETURN"
STATE_FEED = "FEED"
STATE_FLEE = "FLEE"

# Máquina de Mealy: visión y memoria (Fase 2)
VISION_RADIUS = 3            # celdas (cuadrado) para objetos, fuego, feromonas y hormigas
TABU_SIZE = 5                # últimas celdas pisadas que evita
MEMORY_TICKS = 30            # cuánto recuerda la posición del último recurso visto

# Valor de cada recurso al elegir objetivo: valor / (1 + distancia). Claves: 1 pasto, 2 mango, 3 bocadillo
RESOURCE_VALUE = {1: 1.0, 2: 3.0, 3: 2.0}

# Foraging and Movement Weights
WEIGHT_VEGETAL = 4.0
WEIGHT_SUGAR = 5.0
WEIGHT_HOME = 5.0
WEIGHT_ALARM = 10.0
WEIGHT_FIRE = 15.0
WEIGHT_FLEE = 10.0
WEIGHT_RANDOM = 1.0
WEIGHT_RESOURCE = 5.0        # atracción hacia el recurso visto o recordado
TRAIL_CLIMB = 3.0            # premio por subir la pendiente de feromona

# Exploración
EXPLORE_TRAIL_K = 1.0        # saturación t/(t+K); las feromonas ahora valen 0..1
EXPLORE_INERTIA = 1.0
EXPLORE_DOOR_PUSH = 2.0
EXPLORE_DOOR_RADIUS = 6

# Pheromone Deposition (fuerza inicial, se multiplica por TRAIL_DECAY en cada paso)
DEPOSIT_AMOUNT_GRASS = 3.0
DEPOSIT_AMOUNT_MANGO = 6.0
DEPOSIT_AMOUNT_BOCADILLO = 12.0
EXPLORE_TRAIL_K = 2.0
DEPOSIT_AMOUNT_DEATH_ALARM = 40.0

# Población y tiempo
SPAWN_INTERVAL = 8           # ticks entre una salida y la siguiente
SCOUT_TIMEOUT = 300          # si la exploradora no entrega nada en este tiempo, se abre la salida igual
SWARM_SIZE = 10
CORPSE_TICKS = 1
TRAFFIC_DECAY = 0.995

TICK_SECONDS = 1.0
ANIM_FRAMES = 6
FPS = 60
MAX_STEPS_PER_FRAME = 4

# Display
TILE = 32
SCREEN_W = 1280
SCREEN_H = 720
PANEL_W = 290
CAMERA_SPEED = 700

# Feromonas: nombre -> (color RGB, escala de intensidad, K de saturación t/(t+K))
PHEROMONE_VIEW_INTENSITY = 1.0
PHEROMONE_SMOOTH = True
PHEROMONE_VIEW = {
    "vegetal": ((0, 140, 30), 1.0, 1.0),
    "azucar": ((230, 0, 140), 1.0, 1.0),
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

# Placeholders 2x2 (cuando falta el arte): se oscurecen y encogen con las mordidas
COLOR_MANGO_BLOCK = (255, 220, 0)       # amarillo
COLOR_BOCADILLO_BLOCK = (140, 15, 35)   # rojo oscuro

# Ant Colors (solo para los placeholders cuando falta el arte)
COLOR_ANT_EMPTY = (0, 0, 0)
COLOR_ANT_LOADED = (255, 255, 255)
COLORS_CASTE = {
    "WORKER": (120, 60, 20),
    "SOLDIER": (170, 30, 30),
    "MARABUNTA": (70, 30, 110),
}