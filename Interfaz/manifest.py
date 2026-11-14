"""Nombre lógico -> archivo. Todo el arte se dibuja MIRANDO HACIA ARRIBA; el cargador rota.
Si un archivo no existe se genera un placeholder, así que se puede probar sin arte."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "Assets"

# Los patrones con {i} cargan walk_1.png, walk_2.png... hasta que falte uno.
# Con 3 frames se repiten x2 para llegar a 6; con 6 se usan tal cual.
FRAME_START = 1

TILES = {
    "dirt": "terrain/dirt.png",
    "nest": "terrain/nest.png",
    "ash": "fire/ash.png",             # opcional: hoy hay ceniza provisional por código
    "grass1": "objects/grass_1.png",   # pasto ralo (nivel 1), con fondo transparente
    "mango": "objects/mango.png",
}
BOCADILLO = "objects/bocadillo.png"    # una sola imagen (cualquier tamaño cuadrado): se parte en 4
LOOT = "objects/botin.png"             # botín de marabunta (cualquier tamaño cuadrado); si falta, 16x16 provisional
FIRE = "fire/fire_{i}.png"             # 1 o 6 frames

# Familias con bordes: se dibujan 6 formas con el borde hacia el NORTE.
AUTOTILE = {
    "water": "terrain/water_{shape}.png",
    "rock": "terrain/rock_{shape}.png",
    "grass2": "objects/grass2_{shape}.png",   # pasto tupido (nivel 2)
}
# Formas: interior, edge, corridor, corner, peninsula, island
# Para sobreescribir una máscara concreta (0-15) con un PNG propio:
# AUTOTILE_OVERRIDES = {("water", 5): "terrain/water_corridor_especial.png"}
AUTOTILE_OVERRIDES = {}

# (acción, carga) -> patrón. Carga: 0 nada, 1 pasto, 2 mango, 3 bocadillo, 4 botín (crías/comida robada).
# Si falta el arte de una carga se usa un placeholder (hormiga con punto dorado); si falta una acción cargada, se usa la sin carga.
ANTS = {
    "WORKER": {
        ("WALK", 0): "worker/walk_empty_{i}.png",
        ("WALK", 1): "worker/walk_grass_{i}.png",
        ("WALK", 2): "worker/walk_mango_{i}.png",
        ("WALK", 3): "worker/walk_bocadillo_{i}.png",
        ("WALK", 4): "worker/walk_loot_{i}.png",
        ("DEAD_FIGHT", 0): "worker/dead_fight.png",
        ("DEAD_FIRE", 0): "worker/dead_fire.png",
        ("DEAD_STARVE", 0): "worker/dead_starve.png",      
    },
    "SOLDIER": {
        ("WALK", 0): "soldier/walk_{i}.png",
        ("WALK", 4): "soldier/walk_loot_{i}.png",
        ("ATTACK", 0): "soldier/attack_{i}.png",
        ("DEAD_FIGHT", 0): "soldier/dead_fight.png",
        ("DEAD_FIRE", 0): "soldier/dead_fire.png",
        ("DEAD_STARVE", 0): "soldier/dead_starve.png",     
    },
    "MARABUNTA": {
        ("WALK", 0): "marabunta/walk_{i}.png",
        ("WALK", 4): "marabunta/walk_loot_{i}.png",
        ("ATTACK", 0): "marabunta/attack_{i}.png",
        ("DEAD_FIGHT", 0): "marabunta/dead_fight.png",
        ("DEAD_FIRE", 0): "marabunta/dead_fire.png",
    },
}