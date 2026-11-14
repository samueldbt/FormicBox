"""Percepción de la máquina de Mealy de las hormigas.

Mealy = (Q, Σ, Λ, δ, λ):
  Q  estados: EXPLORE, RETURN, FEED, FLEE (y PATROL/ATTACK en soldadas)
  Σ  alfabeto de entrada: el `Percept` que construye perceive() cada tick
  δ  transición: la tabla de reglas (reglas.py) elige el siguiente estado a partir de (estado, Percept)
  λ  salida: depende de (estado, Percept): mover, depositar feromona, entregar, comer, morder
"""
from dataclasses import dataclass
import numpy as np
import config


@dataclass
class Percept:
    at_nest: bool = False
    resource_here: int = 0       # tipo de objeto en la celda propia (0 = nada)
    resource: tuple = None       # (y, x, tipo, distancia_manhattan) del recurso visible más cercano
    fire_dist: int = None        # distancia (Chebyshev) al fuego visible más cercano
    alarm_here: float = 0.0
    trail_here: float = 0.0
    enemy: object = None         # enemigo vivo más cercano a la vista
    allies: int = 0
    loot: tuple = None           # (y, x, distancia_manhattan) del botín visible más cercano
    loot_here: bool = False


def perceive(ant, automaton, ignore=()):
    """Mira el cuadrado de radio VISION_RADIUS alrededor de la hormiga.
    `ignore`: tipos de objeto que no cuentan como recurso (p. ej. bocadillo con el hongo estresado)."""
    R = config.VISION_RADIUS
    h, w = automaton.terrain.matrix.shape
    y0, y1 = max(0, ant.y - R), min(h, ant.y + R + 1)
    x0, x1 = max(0, ant.x - R), min(w, ant.x + R + 1)
    objs = automaton.objects.matrix
    fire = automaton.fire.matrix
    ph = automaton.pheromones

    p = Percept()
    p.at_nest = (ant.y, ant.x) == (ant.nest_y, ant.nest_x)
    p.resource_here = int(objs[ant.y, ant.x])
    p.alarm_here = float(ph["alarma"].matrix[ant.y, ant.x])
    p.trail_here = float(ph["vegetal"].matrix[ant.y, ant.x] + ph["azucar"].matrix[ant.y, ant.x])

    # Recursos visibles (sin contar la celda propia): el de mayor valor/(1+distancia)
    best, best_score = None, -1.0
    ys, xs = np.nonzero(objs[y0:y1, x0:x1])
    for j, i in zip(ys.tolist(), xs.tolist()):
        y, x = y0 + j, x0 + i
        d = abs(y - ant.y) + abs(x - ant.x)
        if d == 0:
            continue
        kind = int(objs[y, x])
        if kind in ignore or fire[y, x] != 0:
            continue
        score = config.food_value(kind) / (1.0 + d)
        if score > best_score:
            best, best_score = (y, x, kind, d), score
    p.resource = best

    # Botín visible (marabuntas caídas con carga)
    lt = automaton.loot
    p.loot_here = lt.at(ant.y, ant.x) is not None
    best_l = None
    for (ly, lx) in lt.items:
        if (ly, lx) != (ant.y, ant.x) and y0 <= ly < y1 and x0 <= lx < x1:
            d = abs(ly - ant.y) + abs(lx - ant.x)
            if best_l is None or d < best_l[2]:
                best_l = (ly, lx, d)
    p.loot = best_l
    
    # Fuego visible
    fy, fx = np.nonzero(fire[y0:y1, x0:x1] > 0)
    if len(fy):
        d = np.maximum(np.abs(fy + y0 - ant.y), np.abs(fx + x0 - ant.x))
        p.fire_dist = int(d.min())

    # Otras hormigas: enemigas (bando contrario) y aliadas
    best_d = R + 1
    for ag in ant.agents:
        if ag is ant or not ag.alive:
            continue
        d = max(abs(ag.y - ant.y), abs(ag.x - ant.x))
        if d > R:
            continue
        if (ag.CASTE == "MARABUNTA") != (ant.CASTE == "MARABUNTA"):
            if d < best_d:
                p.enemy, best_d = ag, d
        else:
            p.allies += 1
    return p