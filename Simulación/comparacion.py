"""Comparación A/B para el Testeo: dos simulaciones con la MISMA semilla y distintas constantes de config.
Cada lado guarda su propio estado del azar de `random`, así cada uno es reproducible e independiente."""
import contextlib
import random
import time
import config
from .simulation import Simulation

# a / b: constantes de config que cambian en cada lado (b = None -> una sola simulación).
# "PHEROMONE_MODE_FOOD" ("sum"/"max") se aplica directo a las capas vegetal y azúcar.
COMPARISONS = (
    dict(id="none", name="Sin comparacion", la="Normal", lb="", a={}, b=None),
    dict(id="pher", name="Feromonas: Suma vs Maximo", la="Suma", lb="Maximo",
         a={"PHEROMONE_MODE_FOOD": "sum"}, b={"PHEROMONE_MODE_FOOD": "max"}),
    dict(id="coll", name="Colisiones: Atravesarse vs Intercambio", la="Atravesarse", lb="Intercambio",
         a={"COLLISION_MODE": "allies_pass"}, b={"COLLISION_MODE": "swap"}),
    dict(id="block", name="Colisiones: Atravesarse vs Bloqueo", la="Atravesarse", lb="Bloqueo",
         a={"COLLISION_MODE": "allies_pass"}, b={"COLLISION_MODE": "block"}),
    dict(id="layers", name="Capas: 2 (hogar+comida) vs 1 (general)", la="2 capas", lb="1 capa",
         a={"FOOD_LAYERS": 2, "RETURN_USE_FIELD": True}, b={"FOOD_LAYERS": 1, "RETURN_USE_FIELD": False}),
    dict(id="wind", name="Fuego: sin viento vs con viento", la="Sin viento", lb="Viento >",
         a={"WIND_X": 0.0, "WIND_Y": 0.0}, b={"WIND_X": 1.0, "WIND_Y": 0.0}),
    dict(id="weather", name="Clima: apagado vs automatico", la="Sin clima", lb="Con clima",
         a={"WEATHER_AUTO": False}, b={"WEATHER_AUTO": True}),
    dict(id="route", name="Memoria de ruta: no vs si", la="Sin memoria", lb="Con memoria",
         a={"ROUTE_MEMORY": False}, b={"ROUTE_MEMORY": True}),
)


@contextlib.contextmanager
def with_config(overrides):
    """Aplica constantes de config solo durante el bloque."""
    keys = [k for k in overrides if hasattr(config, k)]
    saved = {k: getattr(config, k) for k in keys}
    for k in keys:
        setattr(config, k, overrides[k])
    try:
        yield
    finally:
        for k, v in saved.items():
            setattr(config, k, v)


class Side:
    def __init__(self, scenario, seed, overrides, label=""):
        self.overrides, self.label = dict(overrides), label
        self.ms = 0.0                                  # ms por tick (media móvil)
        with with_config(self.overrides):
            self.sim = Simulation(seed=seed, scenario=scenario)
        self._modes()
        self.rng_state = random.getstate()

    def _modes(self):
        m = self.overrides.get("PHEROMONE_MODE_FOOD")
        if m:
            for n in ("vegetal", "azucar"):
                self.sim.automaton.pheromones[n].mode = m

    def run(self, fn):
        """Ejecuta fn(sim) con las constantes y el azar de este lado."""
        outer = random.getstate()
        random.setstate(self.rng_state)
        try:
            with with_config(self.overrides):
                self._modes()
                return fn(self.sim)
        finally:
            self.rng_state = random.getstate()
            random.setstate(outer)

    def step(self):
        t = time.perf_counter()
        self.run(lambda s: s.step())
        self.ms = 0.95 * self.ms + 0.05 * (time.perf_counter() - t) * 1000.0


def metrics(sim):
    st, a = sim.stats(), sim.automaton
    ph = a.pheromones
    return {
        "tick": sim.tick, "workers": st["WORKER"], "soldiers": st["SOLDIER"], "mara": st["MARABUNTA"],
        "delivered": a.colony.delivered_units(), "units": st["units"], "births": sim.births,
        "deaths": sum(sim.deaths.values()),
        "highway": int((sim.traffic >= config.TRAFFIC_HIGHWAY).sum()),
        "trail": int(((ph["vegetal"].matrix + ph["azucar"].matrix) >= 0.5).sum()),
        "burning": st["burning"], "ash": st["ash"], "moist": float(a.terrain.moisture.mean()),
        "stolen": st["stolen"], "recovered": st["recovered"], "lost": st["lost"],
    }