"""Texto de inspección (sin pygame). Cada línea es una tupla:
("title", texto, color) | ("text", texto, color) | ("kv", clave, valor, color) | ("bar", etiqueta, fracción, color, valor) | ("gap",)"""
import config
from Automata.terrain import NEST
from Automata.objects import GRASS, BLOCK_KINDS

WHITE, DIM, GOOD, WARN, BAD = (230, 230, 235), (150, 150, 165), (140, 220, 140), (255, 205, 90), (240, 100, 100)
CASTE_NAMES = {"WORKER": "Obrera", "SOLDIER": "Soldada", "MARABUNTA": "Marabunta"}
TERRAIN_NAMES = ["Tierra", "Roca", "Agua", "Nido"]
OBJECT_NAMES = {0: "-", 1: "Pasto", 2: "Mango", 3: "Bocadillo"}
CAUSES = {"FIGHT": "pelea", "FIRE": "fuego", "STARVE": "sin energia", "HUNGER": "hambre", "LIGHTNING": "rayo", "ESCAPE": "escapo"}


def max_health(ag):
    return {"SOLDIER": config.SOLDIER_HEALTH, "MARABUNTA": config.MARA_HEALTH}.get(ag.CASTE, ag.DEFAULT_HEALTH)


def _loot_text(food, brood):
    return f"comida {sum(food.values())}, crias {len(brood)}"


def agent_lines(ag):
    """Solo datos del ente: estado, salud, energía, carga de recurso / botín / crías."""
    dead = not ag.alive
    L = [("title", CASTE_NAMES.get(ag.CASTE, ag.CASTE) + (" (muerta)" if dead else ""), BAD if dead else WARN)]
    if dead:
        L.append(("kv", "Causa", CAUSES.get(ag.death_cause, ag.death_cause or "?"), BAD))
    L += [("kv", "Estado", ag.state, WHITE), ("kv", "Celda", f"({ag.y},{ag.x})", DIM),
          ("bar", "Vida", max(0.0, ag.health) / max_health(ag), BAD, f"{max(0, ag.health):.0f}/{max_health(ag):.0f}")]
    if ag.CASTE != "MARABUNTA":
        L.append(("bar", "Energia", ag.energy / ag.max_energy, GOOD, f"{ag.energy:.0f}/{ag.max_energy:.0f}"))
    carry = getattr(ag, "carried_resource", 0)
    loot = getattr(ag, "carried_loot", None)
    if ag.CASTE == "MARABUNTA":
        L.append(("kv", "Botin", _loot_text(ag.loot_food, ag.loot_brood) if ag.loot_count() else "-", WHITE))
        L.append(("kv", "Bajas", str(ag.kills), WHITE))
        if ag.mem_pos is not None:
            L.append(("kv", "Memoria", f"{ag.mem_kind} {ag.mem_pos} ({ag.mem_ttl})", DIM))
    else:
        L.append(("kv", "Carga", OBJECT_NAMES.get(int(carry), "-") if carry else "-", WHITE))
        if loot is not None:
            L.append(("kv", "Botin", _loot_text(loot.food, loot.brood), WARN))
        if ag.CASTE == "WORKER" and ag.route_out:
            L.append(("kv", "Ruta", f"{len(ag.route_out)} celdas", DIM))
    return L


def ground_lines(sim, y, x):
    """Celda vacía: terreno, objeto, fuego y concentración de cada feromona."""
    a = sim.automaton
    t = int(a.terrain.matrix[y, x])
    k = int(a.objects.matrix[y, x])
    obj = OBJECT_NAMES[k]
    if k == GRASS:
        obj += f" nivel {int(a.objects.level[y, x])}"
    elif k in BLOCK_KINDS:
        obj += f" ({a.objects.object_bites.get(int(a.objects.object_id[y, x]), 0)} mordidas)"
    fire = {0: "-", 1: "ARDIENDO", -1: "ceniza"}[int(a.fire.matrix[y, x])]
    L = [("title", f"Celda ({y},{x})", WARN), ("kv", "Terreno", TERRAIN_NAMES[t], WHITE),
         ("bar", "Humedad", float(a.terrain.moisture[y, x]), (90, 150, 255), f"{a.terrain.moisture[y, x]:.2f}"),
         ("kv", "Objeto", obj, WHITE), ("kv", "Fuego", fire, BAD if fire == "ARDIENDO" else WHITE)]
    lt = a.loot.at(y, x)
    if lt is not None:
        L.append(("kv", "Botin", _loot_text(lt.food, lt.brood), WARN))
    if t != 1 and t != 2:
        d = a.home_dist[y, x]
        L.append(("kv", "Dist. nido", f"{d:.0f}" if d == d and d != float("inf") else "-", DIM))
    L.append(("title", "Feromonas", WARN))
    for name, label in (("vegetal", "Vegetal"), ("azucar", "Azucar"), ("alarma", "Alarma"), ("caza", "Caza")):
        v = float(a.pheromones[name].matrix[y, x])
        color, _, kk = config.PHEROMONE_VIEW[name]
        L.append(("bar", label, v / (v + kk), color, f"{v:.2f}"))
    return L