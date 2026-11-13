"""Estimación analítica de equilibrio con los valores de config.py (no simula)."""
import config


def main():
    config.recompute_derived()
    c = config.ENERGY_COST_PER_TICK / config.ENERGY_PER_UNIT      # unidades de bolsa que gasta una hormiga por tick
    f = config.FUNGUS_COST / config.FUNGUS_EVERY                  # unidades por tick que come el hongo
    h = 2.0                                                       # ticks de manipulación por viaje (recoger + entregar)

    print(f"Tanque obrera {config.MAX_ENERGY:.1f} | soldada {config.SOLDIER_MAX_ENERGY:.1f} | ciclo {config.CYCLE_TICKS} ticks")
    print(f"Demanda por ciclo: obrera {config.DEMAND_CYCLE['WORKER']:.3f} u | soldada {config.DEMAND_CYCLE['SOLDIER']:.3f} u")
    print(f"Stock inicial: {config.START_FOOD_UNITS:.1f} u -> {config.START_STOCK}")
    print(f"Consumo por hormiga: c = {c:.4f} u/tick | hongo: f = {f:.5f} u/tick\n")

    print("Una forrajera gana c*t del trayecto si v/(2d+h) > c  =>  d* = v/(2c) - h/2")
    for name, v in config.FOOD_VALUE.items():
        print(f"  {name:10s} v={v:.2f} u/viaje -> distancia de equilibrio d* = {v / (2 * c) - h / 2:.0f} celdas")

    g_grass = (1 + config.GRASS_SPROUT_COUNT) / 2 / config.GRASS_SPROUT_INTERVAL \
        * config.GRASS_BITES * config.FOOD_VALUE["GRASS"]
    g_mango = config.MANGO_BITES * config.FOOD_VALUE["MANGO"] / config.MANGO_SPROUT_INTERVAL
    g = g_grass + g_mango
    print(f"\nRegeneración máxima del mapa: pasto {g_grass:.3f} u/tick + mango {g_mango:.3f} u/tick = {g:.3f} u/tick")
    print(f"Población que sostiene esa regeneración: N* = (g - f)/c = {(g - f) / c:.0f} hormigas "
          f"(tope MAX_POPULATION = {config.MAX_POPULATION})")


if __name__ == "__main__":
    main()