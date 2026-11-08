"""Corre la simulación SIN pygame y saca números para comparar antes/después.

Uso (desde la carpeta del proyecto):
    python pruebas/headless.py --seed 1 --ticks 2000
    python pruebas/headless.py --seed 1 --ticks 2000 --json   # una línea JSON

Mide:
  - hormigas vivas por casta y bajas por casta
  - recursos entregados (pasto, mango, bocadillo)
  - hormigas vivas que NO se han movido en los últimos --quieto ticks (50 por defecto)
  - fracción del tráfico total que concentra el --top % de celdas más
    transitadas (5 % por defecto). Si las obreras se reparten al azar, esa
    fracción ronda el propio 5 %; cuanto más alta, más "autopistas" hay.

El tráfico se cuenta aquí SIN olvido (cada tick, +1 en la celda de cada obrera
viva fuera del nido), así que cubre toda la corrida y no depende de
TRAFFIC_DECAY. El porcentaje se toma sobre las celdas caminables (tierra) del
mapa al final, sin contar el nido.
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import config  # noqa: E402
from Simulación.compat import ensure_colony_api  # noqa: E402
from Simulación.simulation import Simulation  # noqa: E402
from Automata.terrain import DIRT  # noqa: E402

CASTES = ("WORKER", "SOLDIER", "MARABUNTA")
NOMBRES = {"WORKER": "Obreras", "SOLDIER": "Soldadas", "MARABUNTA": "Marabuntas"}


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="FormicBox sin interfaz: N ticks con semilla fija.")
    p.add_argument("--seed", type=int, default=config.SEED, help=f"semilla (por defecto {config.SEED})")
    p.add_argument("--ticks", type=int, default=1000, help="ticks a correr (por defecto 1000)")
    p.add_argument("--quieto", type=int, default=50,
                   help="ventana para contar hormigas quietas (por defecto 50 ticks)")
    p.add_argument("--top", type=float, default=5.0,
                   help="porcentaje de celdas más transitadas (por defecto 5)")
    p.add_argument("--json", action="store_true", help="imprime el resultado como una línea JSON")
    return p.parse_args(argv)


def top_share(traffic, walkable, top_pct):
    """Fracción del tráfico total que cae en el top_pct % de celdas caminables más transitadas."""
    values = traffic[walkable]
    total = float(values.sum())
    if total <= 0 or values.size == 0:
        return 0.0, 0
    k = max(1, int(round(values.size * top_pct / 100.0)))
    top = np.partition(values, values.size - k)[-k:]
    return float(top.sum()) / total, k


def run(seed, ticks, quieto=50, top_pct=5.0):
    ensure_colony_api(verbose=False)
    sim = Simulation(seed)
    a = sim.automaton
    nest = sim.nest
    traffic = np.zeros((a.height, a.width), dtype=np.float64)
    last_move = {}            # id(hormiga) -> último tick en que cambió de celda
    born = {}                 # id(hormiga) -> tick en que apareció

    t0 = time.perf_counter()
    for _ in range(ticks):
        if sim.game_over:
            break
        sim.step()
        t = sim.tick
        for ag in sim.agents:
            if not ag.alive:
                continue
            key = id(ag)
            if key not in born:
                born[key] = t
                last_move[key] = t
            elif (ag.y, ag.x) != (ag.prev_y, ag.prev_x):
                last_move[key] = t
            if ag.CASTE == "WORKER" and (ag.y, ag.x) != nest:
                traffic[ag.y, ag.x] += 1.0
        # ids de hormigas que ya no están: se olvidan (id() se puede reutilizar)
        if t % 100 == 0:
            vivos = {id(ag) for ag in sim.agents}
            for d in (born, last_move):
                for key in list(d):
                    if key not in vivos:
                        del d[key]
    elapsed = time.perf_counter() - t0

    alive = {c: 0 for c in CASTES}
    stuck = {c: 0 for c in CASTES}
    stuck_in_nest = 0
    elegibles = 0             # hormigas que llevan al menos `quieto` ticks en el mapa
    for ag in sim.agents:
        if not ag.alive:
            continue
        alive[ag.CASTE] += 1
        key = id(ag)
        if sim.tick - born.get(key, sim.tick) < quieto:
            continue
        elegibles += 1
        if sim.tick - last_move.get(key, sim.tick) >= quieto:
            stuck[ag.CASTE] += 1
            if (ag.y, ag.x) == nest:
                stuck_in_nest += 1

    walkable = a.terrain.matrix == DIRT
    walkable[nest] = False
    share, k = top_share(traffic, walkable, top_pct)
    summary = sim.summary()

    return {
        "seed": seed,
        "ticks_pedidos": ticks,
        "ticks_corridos": sim.tick,
        "game_over": bool(sim.game_over),
        "segundos_cpu": round(elapsed, 3),
        "vivas": alive,
        "bajas": summary["deaths"],
        "en_cola": len(sim.queue),
        "entregado": summary["delivered"],
        "quietas": {
            "ventana": quieto,
            "total": sum(stuck.values()),
            "por_casta": stuck,
            "en_el_nido": stuck_in_nest,
            "elegibles": elegibles,
        },
        "trafico": {
            "top_pct": top_pct,
            "celdas_top": k,
            "celdas_caminables": int(walkable.sum()),
            "celdas_con_trafico": int((traffic[walkable] > 0).sum()),
            "total": int(traffic.sum()),
            "fraccion_top": round(share, 4),
        },
    }


def print_report(r):
    q, tr = r["quietas"], r["trafico"]
    fin = " (GAME OVER)" if r["game_over"] else ""
    print(f"FormicBox headless  seed={r['seed']}  ticks={r['ticks_corridos']}/{r['ticks_pedidos']}{fin}"
          f"  [{r['segundos_cpu']} s]")
    print("Vivas:    " + "  ".join(f"{NOMBRES[c]} {r['vivas'][c]}" for c in CASTES)
          + f"  (en cola {r['en_cola']})")
    print("Bajas:    " + "  ".join(f"{NOMBRES[c]} {r['bajas'].get(c, 0)}" for c in CASTES))
    e = r["entregado"]
    print(f"Entregado: pasto {e['grass']}  mango {e['mango']}  bocadillo {e['bocadillo']}")
    print(f"Quietas (sin moverse en {q['ventana']} ticks): {q['total']} de {q['elegibles']} elegibles  "
          + "  ".join(f"{NOMBRES[c]} {q['por_casta'][c]}" for c in CASTES)
          + f"  | de ellas en el nido: {q['en_el_nido']}")
    print(f"Tráfico: el {tr['top_pct']:g} % de celdas más transitadas ({tr['celdas_top']} de "
          f"{tr['celdas_caminables']} caminables) concentra el {tr['fraccion_top'] * 100:.1f} % "
          f"del tráfico total ({tr['total']} pasos; {tr['celdas_con_trafico']} celdas pisadas)")


def main(argv=None):
    args = parse_args(argv)
    if args.ticks < 0 or args.quieto < 1 or not (0 < args.top <= 100):
        sys.exit("argumentos fuera de rango: --ticks >= 0, --quieto >= 1, 0 < --top <= 100")
    r = run(args.seed, args.ticks, args.quieto, args.top)
    assert "pygame" not in sys.modules, "la simulación no debería importar pygame"
    if args.json:
        print(json.dumps(r, ensure_ascii=False))
    else:
        print_report(r)


if __name__ == "__main__":
    main()
