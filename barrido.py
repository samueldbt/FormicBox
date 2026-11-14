"""Barrido de parámetros: corre la simulación SIN interfaz con muchas combinaciones de constantes
y escribe un informe (CSV + Markdown) en reportes/ para elegir los mejores valores.

Uso:
    python barrido.py                                   # muestreo aleatorio de ESPACIO
    python barrido.py --ticks 1500 --semillas 3 --max 40 --procesos 4
    python barrido.py --escenario corridor
    python barrido.py --ataque 600                      # lanza un enjambre en el tick 600
Edita ESPACIO para elegir qué constantes variar y con qué valores.
"""
import argparse
import copy
import csv
import itertools
import os
import random
import statistics
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import config

# Constantes a variar: nombre en config -> valores a probar.
# Especiales: PHEROMONE_MODE_FOOD ("max"/"sum" para vegetal y azúcar) y TABU_WORKER ("off"/"explore"/"always").
ESPACIO = {
    "PHEROMONE_MODE_FOOD": ["max", "sum"],
    "EVAP_FOOD": [0.005, 0.015, 0.03],
    "TRAIL_DECAY": [0.95, 0.97, 0.985],
    "TRAIL_CLIMB": [3.0, 6.0, 10.0],
    "ROUTE_MEMORY": [True, False],
    "CLEAN_DEAD_TRAILS": [True, False],
    "TABU_WORKER": ["explore", "always"],
    "TABU_SIZE": [6, 12],
    "VISION_RADIUS": [3, 4],
    "RESOURCE_MIN_DIST": [8, 15, 25],
    "SPAWN_INTERVAL": [8, 12],
    "MANGO_BITES": [60, 120, 200],
    "SEARCH_DEPLETED": [True, False],
    "SEARCH_TICKS": [8, 14, 24],
    "MARA_SENSE": ["contact", "smell"],
    "MARA_RAID_MODE": ["column", "swarm"],
}
ESPECIALES = {"PHEROMONE_MODE_FOOD", "TABU_WORKER", "EVAP_FOOD"}

META_AUTOPISTA = 15          # celdas con tráfico >= config.TRAFFIC_HIGHWAY
META_RASTRO = 40             # celdas con feromona visible (>= 0.5) que cuentan como "caminos visibles"
META_CRECIMIENTO = 3.0


BASE = {k: copy.deepcopy(getattr(config, k)) for k in ESPACIO if k not in ESPECIALES}
BASE["PHEROMONE_MODE"] = copy.deepcopy(config.PHEROMONE_MODE)
BASE["TABU_MODE"] = copy.deepcopy(config.TABU_MODE)
BASE["PHEROMONE_VEGETAL"] = config.PHEROMONE_VEGETAL
BASE["PHEROMONE_SUGAR"] = config.PHEROMONE_SUGAR

def aplicar(params):
    """Restaura los valores base y aplica los de esta combinación."""
    for k, v in BASE.items():
        setattr(config, k, copy.deepcopy(v))
    for k, v in params.items():
        if k == "PHEROMONE_MODE_FOOD":
            config.PHEROMONE_MODE = {**config.PHEROMONE_MODE, "vegetal": v, "azucar": v}
        elif k == "TABU_WORKER":
            config.TABU_MODE = {**config.TABU_MODE, "WORKER": v}
        elif k == "EVAP_FOOD":
            config.PHEROMONE_VEGETAL = (v, BASE["PHEROMONE_VEGETAL"][1])
            config.PHEROMONE_SUGAR = (v, BASE["PHEROMONE_SUGAR"][1])
        else:
            setattr(config, k, v)
    config.recompute_derived()


def correr(job):
    params, semilla, ticks, escenario, ataque = job
    aplicar(params)
    from Simulación.simulation import Simulation
    sim = Simulation(seed=semilla, scenario=escenario)
    c = sim.automaton.colony
    pop0 = config.INITIAL_WORKERS + config.INITIAL_SOLDIERS
    pop_peak, first, hw = pop0, None, []
    t_start = time.perf_counter()
    for t in range(ticks):
        if ataque is not None and sim.tick == ataque:
            sim.spawn_swarm(config.SWARM_SIZE)
        sim.step()
        if first is None and sum(c.delivered.values()) > 0:
            first = sim.tick
        if t % 10 == 0:
            pop_peak = max(pop_peak, sim._population())
        if t % 25 == 0:
            hw.append(int((sim.traffic >= config.TRAFFIC_HIGHWAY).sum()))
        if sim.game_over:
            break
    elapsed = max(1e-9, time.perf_counter() - t_start)
    tr = np.sort(sim.traffic.ravel())[::-1]
    tot = float(tr.sum())
    k = max(1, int(0.05 * tr.size))
    pop_end = sim._population()
    causas = sim.death_causes
    ph = sim.automaton.pheromones
    trail_cells = int(((ph["vegetal"].matrix + ph["azucar"].matrix) >= 0.5).sum())
    return {
        "stolen": round(c.stolen_units, 1), "recovered": round(c.recovered_units, 1),
        "lost_loot": round(c.lost_units, 1), "escaped": sim.escaped,
        "params": params, "semilla": semilla,
        "pop0": pop0, "pop_end": pop_end, "pop_peak": pop_peak, "births": sim.births,
        "units_end": round(c.food_units(), 1), "delivered_units": round(c.delivered_units(), 1),
        "first_delivery": first if first is not None else ticks,
        "deaths_energy": causas.get("STARVE", 0), "lost_with_food": sim.lost_with_food,
        "deaths_hunger": causas.get("HUNGER", 0), "deaths_fire": causas.get("FIRE", 0),
        "deaths_fight": causas.get("FIGHT", 0),
        "highway": statistics.mean(hw[len(hw) // 2:]) if hw else 0.0,
        "traffic_peak": round(float(tr[0]), 1) if tot > 0 else 0.0,
        "traffic_conc": round(float(tr[:k].sum() / tot), 3) if tot > 0 else 0.0,
        "extinct": int(sim.game_over or pop_end == 0),
        "ticks_run": sim.tick,
        "trail_cells": trail_cells,
        "ticks_per_sec": round(sim.tick / elapsed, 1),
        "ms_per_tick": round(1000.0 * elapsed / max(1, sim.tick), 3),
        "deaths_lightning": causas.get("LIGHTNING", 0),
    }


def puntaje(m):
    crec = min(m["pop_end"] / m["pop0"], META_CRECIMIENTO) / META_CRECIMIENTO
    trafico = min(m["highway"] / META_AUTOPISTA, 1.0)
    rastro = min(m["trail_cells"] / META_RASTRO, 1.0)
    perdidas = min(1.0, m["lost_with_food"] / m["pop0"])
    s = 40 * crec + 20 * trafico + 10 * rastro + 30 * (1.0 - perdidas)
    return s - (50 if m["extinct"] else 0)


def combinaciones(maximo, seed=0):
    claves = list(ESPACIO)
    todas = list(itertools.product(*(ESPACIO[k] for k in claves)))
    if len(todas) > maximo:
        todas = random.Random(seed).sample(todas, maximo)
    combos = [dict(zip(claves, vals)) for vals in todas]
    return [{}] + combos                      # la primera es la base (valores actuales de config.py)


def agrupar(filas):
    grupos = {}
    for f in filas:
        grupos.setdefault(tuple(sorted(f["params"].items())), []).append(f)
    out = []
    for clave, fs in grupos.items():
        row = {"params": dict(clave), "n": len(fs)}
        for k in fs[0]:
            if k in ("params", "semilla") or not isinstance(fs[0][k], (int, float)):
                continue
            row[k] = statistics.mean(f[k] for f in fs)
        row["puntaje"] = statistics.mean(puntaje(f) for f in fs)
        out.append(row)
    return sorted(out, key=lambda r: -r["puntaje"])


def escribir_informe(filas, filas_csv, args, seg):
    os.makedirs("reportes", exist_ok=True)
    sello = time.strftime("%Y%m%d_%H%M%S")
    ruta_csv, ruta_md = f"reportes/barrido_{sello}.csv", f"reportes/barrido_{sello}.md"
    cols = ["puntaje", "pop0", "pop_end", "pop_peak", "births", "highway", "traffic_peak", "traffic_conc",
            "delivered_units", "first_delivery", "deaths_energy", "lost_with_food", "deaths_hunger",
            "deaths_fire", "deaths_fight", "deaths_lightning", "extinct", "units_end", "trail_cells", "stolen", "recovered", "lost_loot", "escaped",
            "ticks_per_sec", "ms_per_tick"]
    with open(ruta_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["params"] + cols)
        for r in filas_csv:
            w.writerow([str(r["params"])] + [round(r[c], 2) for c in cols])

    L = [f"# Informe de barrido ({sello})", "",
         f"- Combinaciones: {len(filas)} | semillas por combinación: {args.semillas} | ticks: {args.ticks}"
         f" | escenario: {args.escenario or 'aleatorio'} | ataque en tick: {args.ataque}",
         f"- Tiempo: {seg:.0f} s. Puntaje 0-100 = 40 crecimiento + 20 tráfico + 10 rastros visibles + 30 no perderse sin llegar”",
         "- `highway` = celdas con tráfico ≥ TRAFFIC_HIGHWAY (promedio de la 2.ª mitad). "
         "`lost_with_food` = murieron sin energía habiendo comida en el nido.", "", "## Base (valores actuales de config.py)", ""]
    base = next(r for r in filas if not r["params"])
    L += [f"puntaje {base['puntaje']:.1f} | pop {base['pop0']:.0f}→{base['pop_end']:.0f} (pico {base['pop_peak']:.0f}) | "
          f"highway {base['highway']:.0f} | perdidas {base['lost_with_food']:.1f} | extinta {base['extinct']:.2f}", ""]

    def tabla(rs):
        out = ["| # | puntaje | pop fin | highway | perdidas | hambre | extinta | parámetros |", "|---|---|---|---|---|---|---|---|"]
        for i, r in enumerate(rs, 1):
            out.append(f"| {i} | {r['puntaje']:.1f} | {r['pop_end']:.0f} | {r['highway']:.0f} | {r['lost_with_food']:.1f} | "
                       f"{r['deaths_hunger']:.1f} | {r['extinct']:.2f} | {r['params']} |")
        return out
    L += ["## Rendimiento y botín (media de todas las combinaciones)", ""]
    prom = lambda k: statistics.mean(r[k] for r in filas)
    L += [f"- Velocidad: **{prom('ticks_per_sec'):.0f} ticks/s** ({prom('ms_per_tick'):.2f} ms/tick); "
          f"la más lenta: {min(r['ticks_per_sec'] for r in filas):.0f} ticks/s",
          f"- Botín: robado {prom('stolen'):.1f} u | recuperado {prom('recovered'):.1f} u | perdido al salir del mapa {prom('lost_loot'):.1f} u",
          f"- Bajas: combate {prom('deaths_fight'):.1f} | fuego {prom('deaths_fire'):.1f} | rayo {prom('deaths_lightning'):.1f} | "
          f"hambre {prom('deaths_hunger'):.1f}", "",
          "## Comandos sugeridos", "",
          "```",
          "python barrido.py --ticks 1500 --semillas 3 --max 40            # barrido general",
          "python barrido.py --ataque 600 --ticks 2000 --max 20            # ¿sobrevive a un enjambre en el tick 600?",
          "python barrido.py --clima --ticks 3000 --semillas 5 --max 20    # con lluvia, sequía y rayos",
          "python barrido.py --escenario corridor --ticks 800 --procesos 1 # un escenario, sin paralelismo (mide ticks/s limpio)",
          "python analisis.py                                              # equilibrio analítico (no simula)",
          "```", ""]
    L += ["## Mejores 10", ""] + tabla(filas[:10]) + ["", "## Peores 3", ""] + tabla(filas[-3:]) + ["",
          "## Efecto de cada parámetro (puntaje medio por valor)", ""]
    for k in ESPACIO:
        por = {}
        for r in filas:
            if k in r["params"]:
                por.setdefault(r["params"][k], []).append(r["puntaje"])
        if por:
            L.append(f"- **{k}**: " + " | ".join(f"{v} → {statistics.mean(p):.1f}" for v, p in por.items()))
    with open(ruta_md, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    return ruta_csv, ruta_md


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticks", type=int, default=1500)
    ap.add_argument("--semillas", type=int, default=3)
    ap.add_argument("--max", type=int, default=40, help="máximo de combinaciones (muestreo aleatorio)")
    ap.add_argument("--procesos", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--escenario", default=None)
    ap.add_argument("--ataque", type=int, default=None)
    ap.add_argument("--clima", action="store_true", help="activa lluvia, sequía y rayos automáticos (WEATHER_AUTO)")
    args = ap.parse_args()

    config.WEATHER_AUTO = args.clima
    BASE["WEATHER_AUTO"] = args.clima
    combos = combinaciones(args.max)
    jobs = [(p, s, args.ticks, args.escenario, args.ataque) for p in combos for s in range(1, args.semillas + 1)]
    print(f"{len(combos)} combinaciones x {args.semillas} semillas = {len(jobs)} corridas de {args.ticks} ticks")
    t0 = time.time()
    if args.procesos > 1:
        with ProcessPoolExecutor(max_workers=args.procesos) as ex:
            res = list(ex.map(correr, jobs, chunksize=1))
    else:
        res = [correr(j) for j in jobs]
    filas = agrupar(res)
    filas_csv = filas
    csv_path, md_path = escribir_informe(filas, filas_csv, args, time.time() - t0)
    print(f"Listo: {md_path}\n       {csv_path}\nPásame el .md.")


if __name__ == "__main__":
    main()