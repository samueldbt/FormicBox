"""Global configuration parameters and constants for the simulation.

Lo marcado (derivado) se recalcula en recompute_derived(), al final del archivo.
Si cambias una constante en caliente (como hace barrido.py), llama config.recompute_derived().
"""

# ------------------------------------------------------------ Integración
COLLISION_MODE = "allies_pass"   # o "block"
INITIAL_WORKERS = 20
INITIAL_SOLDIERS = 3
BIRTH_INTERVAL = 3               # cada cuántos ticks se intenta iniciar una cría
BIRTH_SOLDIER_RATIO = 0.15
MAX_POPULATION = 100             # vivas + cola de salida + crías en desarrollo
STARVATION_INTERVAL = 10         # con la bolsa vacía, muere una hormiga cada tantos ticks

USE_SCIPY_CONVOLUTION = True

# World Settings
SEED = 1
WIDTH = 110
HEIGHT = 20
NEST = None

# Global Wind
WIND_X = 0.0
WIND_Y = 0.0
WIND_STEP = 1.0

# ------------------------------------------------------------ Feromonas
# (evaporación, difusión)
PHEROMONE_VEGETAL = (0.015, 0.03)
PHEROMONE_SUGAR = (0.015, 0.03)
TRAIL_DECAY = 0.97       # pendiente NETA por celda (el decaimiento por paso ya compensa la evaporación)
TRAIL_CLIMB = 6.0
TRAFFIC_HIGHWAY = 30.0   # con 5 contaba casi todo el mapa como autopista (259 celdas en tu informe)
PHEROMONE_ALARM = (0.15, 0.25)
PHEROMONE_HUNT = (0.30, 0.05)
PHEROMONE_MODE = {"vegetal": "max", "azucar": "max", "alarma": "sum", "caza": "sum"}

# ------------------------------------------------------------ Fuego
FIRE_BASE_PROB = 0.30
FIRE_WIND_C = 1.2        # factor exp(C * alineación con el viento): a favor ~x3.3, en contra ~x0.3
FIRE_JUMP_PROB = 0.15    # prob. de que el fuego salte 2 celdas a favor del viento (si hay viento)
FIRE_MOISTURE_C = 3.0    # factor exp(-C * humedad): 0 -> x1, 0.5 -> x0.22, 1.0 -> x0.05
FIRE_BURNOUT_BASE = 0.30         # prob. por tick de apagarse (pasados 5 ticks)
FIRE_BURNOUT_MOISTURE = 0.50     # + esto * humedad (la humedad apaga más rápido)
ASH_TICKS = 20
FIRE_ALERT_RADIUS = 2

# Terrain Densities
ROCK_DENSITY = 0.40
WATER_DENSITY = 0.38

# ------------------------------------------------------------ Recursos del mapa
GRASS_DENSITY = 0.5
MANGO_DENSITY = 0.015
RESOURCE_MIN_DIST = 15       # los recursos nacen/brotan a esta distancia (por camino) del nido o más
RESOURCE_MAX_DIST = None     # None = sin tope

# Mordidas (cada mordida = lo que carga una obrera en un viaje)
GRASS_BITES = 4              # PAR: más de la mitad = pasto tupido, la mitad o menos = ralo
MANGO_BITES = 120
BOCADILLO_BITES = 160

T_SUGAR = 10                 # items de bocadillo en reserva a partir de los cuales el hongo se estresa

GRASS_MAX = None
MANGO_MAX = None
GRASS_SPROUT_INTERVAL = 20
GRASS_SPROUT_COUNT = 3
GRASS_MATURE_PROB = 1 / 60
MANGO_SPROUT_INTERVAL = 60
MOISTURE_THRESHOLD = 0.40    # compatibilidad

# ------------------------------------------------------------ Alimento y economía del nido
# 1 unidad de bolsa = 1 bocadillo = 2 mango = 3 pasto
FOOD_VALUE = {"BOCADILLO": 1.0, "MANGO": 1 / 2, "GRASS": 1 / 3}
ENERGY_PER_UNIT = 100.0      # energía que da 1 unidad de bolsa
PAY_ORDER = ("GRASS", "MANGO", "BOCADILLO")   # de qué se paga el hongo y las crías (lo barato primero)
EAT_ORDER = ("BOCADILLO", "MANGO", "GRASS")   # qué come primero una hormiga en el nido

RESERVE_CYCLES = 3           # ciclos de alimento que deben quedar cubiertos antes de gastar en crías
FUNGUS_COST = 1.0            # unidades de bolsa por consumo del hongo
FUNGUS_INTERVAL = None       # None -> un consumo por ciclo (CYCLE_TICKS)
CASTE_COST = {"WORKER": 3.0, "SOLDIER": 4.5}  # unidades de bolsa
DEV_TICKS = {"WORKER": 20, "SOLDIER": 35}
INITIAL_BROOD_ANTS = 10      # crías que el stock inicial debe poder financiar (con su reserva)
START_FOOD_SPLIT = {"GRASS": 0.7, "MANGO": 0.3, "BOCADILLO": 0.0}   # reparto del stock inicial (en unidades)
START_STOCK_OVERRIDE = None  # p. ej. {"GRASS": 300, "MANGO": 80, "BOCADILLO": 0}; None = calculado

# ------------------------------------------------------------ Energía
ENERGY_COST_PER_TICK = 0.5
WORKER_RANGE = 110           # celdas que una obrera debe poder recorrer ida y vuelta con el tanque lleno
ENERGY_SAFETY = 1.25         # margen sobre ese recorrido
SOLDIER_PATROL_TICKS = 250   # ticks de patrullaje con el tanque lleno (soldadas)
RETURN_MARGIN = 1.25         # vuelve al nido cuando la energía <= distancia_al_nido * costo * margen + reserva
ENERGY_RESERVE_FRAC = 0.10   # reserva (fracción del tanque) que siempre deja para el regreso
REFUEL_FRACTION = 0.95       # en el nido come hasta llenarse si está por debajo de esta fracción
EAT_MAP_FRACTION = 0.60      # come un bocadillo del mapa si tiene menos de esta fracción

# ------------------------------------------------------------ Estados
STATE_EXPLORE = "EXPLORE"
STATE_RETURN = "RETURN"
STATE_FEED = "FEED"
STATE_FLEE = "FLEE"
STATE_CLEAN = "CLEAN"

# ------------------------------------------------------------ Máquina de Mealy: visión, memoria y rastro
VISION_RADIUS = 3
MEMORY_TICKS = 30
TABU_SIZE = 6
# "off" = sin tabú; "explore" = solo en los estados de TABU_STATES (no bloquea el camino de regreso);
# "always" = siempre. Las marabuntas son ciegas, por eso "always".
TABU_MODE = {"WORKER": "explore", "SOLDIER": "explore", "MARABUNTA": "always"}
TABU_STATES = ("EXPLORE", "PATROL", "RAID")
RETURN_USE_FIELD = True      # el regreso usa la distancia real por camino al nido (BFS). False = ángulo recto
DETERMINISTIC_MOVES = False  # True = siempre la mejor celda, sin sorteo (y sin ruido)
MOVE_EXPONENT = 3            # nitidez del sorteo: puntaje ** esto

# Limpieza de rastros muertos (callejones sin comida)
CLEAN_DEAD_TRAILS = True
CLEAN_MIN_TRAIL = 0.3        # rastro mínimo en la punta para considerarla un callejón
CLEAN_STOP_TRAIL = 0.05      # deja de limpiar cuando el rastro baja de esto
CLEAN_TIP_MARGIN = 1.01      # la punta debe superar a sus 8 vecinos por este factor

# Memoria de ruta: tras entregar, repite al revés el camino del regreso hasta la fuente
ROUTE_MEMORY = True
ROUTE_BONUS = 20.0           # empuje hacia la siguiente celda de la ruta
ROUTE_MAX_LEN = 400
ROUTE_LOST_TICKS = 4         # ticks fuera de la ruta antes de soltarla
ROUTE_LOOKAHEAD = 3          # puede saltar hasta N celdas adelante si la siguiente está bloqueada

PREFER_BETTER_DIST = 5       # no toma un recurso si hay uno de más valor a esta distancia o menos

# Pesos de movimiento
WEIGHT_VEGETAL = 4.0
WEIGHT_SUGAR = 5.0
WEIGHT_HOME = 5.0
WEIGHT_ALARM = 10.0
WEIGHT_FIRE = 15.0
WEIGHT_FLEE = 10.0
WEIGHT_RANDOM = 1.0
WEIGHT_RESOURCE = 5.0

EXPLORE_TRAIL_K = 2.0
EXPLORE_INERTIA = 1.0
EXPLORE_DOOR_PUSH = 2.0
EXPLORE_DOOR_RADIUS = 6

# Depósito de feromona (fuerza inicial; se multiplica por TRAIL_DECAY en cada paso)
DEPOSIT_AMOUNT_GRASS = 3.0
DEPOSIT_AMOUNT_MANGO = 6.0
DEPOSIT_AMOUNT_BOCADILLO = 8.0
DEPOSIT_AMOUNT_DEATH_ALARM = 40.0

# ------------------------------------------------------------ Soldadas
SOLDIER_PATROL_RADIUS = 12   # distancia máxima al nido al patrullar (celdas)
SOLDIER_HEALTH = 10.0
SOLDIER_BITE = 2.0

# ------------------------------------------------------------ Marabuntas
MARA_HEALTH = 6.0
MARA_BITE = 1.0
MARA_SENSE_RADIUS = 3        # ciegas, pero sienten a la presa de cerca
MARA_RETREAT_HEALTH = 2.0
MARA_MAX_RAID_TICKS = 800
MARA_HUNT_K = 5.0
MARA_HUNT_RADIUS = 3
MARA_DEPOSIT_HUNT = 10.0
MARA_W_TARGET = 3.0          # atracción al olor del nido
MARA_W_HUNT = 4.0            # atracción al rastro del enjambre
MARA_W_PREY = 8.0
MARA_W_INERTIA = 1.5
SWARM_SIZE = 10
SWARM_MIN_DIST = 20          # distancia mínima por camino al nido al aparecer (> radio de patrulla 12 + margen)
SWARM_POOL = 12              # elige al azar entre las N celdas de borde más cercanas que cumplan

# ------------------------------------------------------------ Población y tiempo
SPAWN_INTERVAL = 8           # ticks entre una salida del nido y la siguiente
SCOUT_TIMEOUT = 300          # si la primera no entrega nada en este tiempo, se abre la salida igual
CORPSE_TICKS = 1
TRAFFIC_DECAY = 0.995
TICK_SECONDS = 1.0
ANIM_FRAMES = 6
FPS = 60
MAX_STEPS_PER_FRAME = 4

# ------------------------------------------------------------ Display
TILE = 32
SCREEN_W = 1280
SCREEN_H = 720
PANEL_W = 290
CAMERA_SPEED = 700

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
COLOR_MANGO_BLOCK = (255, 220, 0)
COLOR_BOCADILLO_BLOCK = (140, 15, 35)

COLOR_ANT_EMPTY = (0, 0, 0)
COLOR_ANT_LOADED = (255, 255, 255)
COLORS_CASTE = {
    "WORKER": (120, 60, 20),
    "SOLDIER": (170, 30, 30),
    "MARABUNTA": (70, 30, 110),
}

# ------------------------------------------------------------ Utilidades y valores derivados
_KIND_NAME = {1: "GRASS", 2: "MANGO", 3: "BOCADILLO"}


def food_value(kind):
    """Valor en unidades de bolsa de un tipo de objeto (1 pasto, 2 mango, 3 bocadillo)."""
    return FOOD_VALUE.get(_KIND_NAME.get(int(kind)), 0.0)


def recompute_derived():
    """Recalcula lo que depende de otras constantes. Llámala tras cambiar alguna en caliente."""
    global MAX_ENERGY, SOLDIER_MAX_ENERGY, MAX_ENERGY_BY_CASTE, CYCLE_TICKS, FUNGUS_EVERY
    global DEMAND_CYCLE, START_FOOD_UNITS, START_STOCK

    # Tanque lleno: la obrera recorre WORKER_RANGE celdas de ida y WORKER_RANGE de vuelta (con margen)
    MAX_ENERGY = 2.0 * WORKER_RANGE * ENERGY_COST_PER_TICK * ENERGY_SAFETY
    SOLDIER_MAX_ENERGY = SOLDIER_PATROL_TICKS * ENERGY_COST_PER_TICK
    MAX_ENERGY_BY_CASTE = {"WORKER": MAX_ENERGY, "SOLDIER": SOLDIER_MAX_ENERGY, "MARABUNTA": MAX_ENERGY}

    # Un ciclo = lo que dura un tanque lleno (sale, se pone hambrienta y vuelve)
    CYCLE_TICKS = max(1, int(round(MAX_ENERGY / ENERGY_COST_PER_TICK)))
    FUNGUS_EVERY = int(FUNGUS_INTERVAL) if FUNGUS_INTERVAL else CYCLE_TICKS

    # Alimento (en unidades de bolsa) que gasta una hormiga por ciclo = rellenar el tanque
    DEMAND_CYCLE = {"WORKER": MAX_ENERGY / ENERGY_PER_UNIT, "SOLDIER": SOLDIER_MAX_ENERGY / ENERGY_PER_UNIT}

    # Stock inicial = 3 ciclos de alimento para la población inicial y el hongo
    #                 + un depósito para financiar INITIAL_BROOD_ANTS crías (su costo y su reserva de 3 ciclos)
    ants = INITIAL_WORKERS * DEMAND_CYCLE["WORKER"] + INITIAL_SOLDIERS * DEMAND_CYCLE["SOLDIER"]
    fungus = FUNGUS_COST * CYCLE_TICKS / FUNGUS_EVERY
    brood = INITIAL_BROOD_ANTS * (CASTE_COST["WORKER"] + RESERVE_CYCLES * DEMAND_CYCLE["WORKER"])
    START_FOOD_UNITS = RESERVE_CYCLES * (ants + fungus) + brood
    if START_STOCK_OVERRIDE:
        START_STOCK = dict(START_STOCK_OVERRIDE)
    else:
        START_STOCK = {k: int(round(START_FOOD_UNITS * frac / FOOD_VALUE[k]))
                       for k, frac in START_FOOD_SPLIT.items()}


recompute_derived()