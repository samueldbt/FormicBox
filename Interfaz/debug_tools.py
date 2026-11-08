"""Herramientas temporales de depuración. Cada una llama a un método de Simulation,
así que el compañero del mouse puede reutilizarlas luego para el Modo Dios."""
import config
from Automata.objects import GRASS, MANGO

# (id, etiqueta del botón)
TOOLS = [
    ("INSPECT", "Ver"), ("WORKER", "Obrera"), ("SOLDIER", "Soldada"),
    ("MARABUNTA", "Marabunta"), ("GRASS", "Pasto"), ("MANGO", "Mango"),
    ("BOCADILLO", "Bocad."), ("FIRE", "Fuego"), ("KILL", "Matar"),
    ("KILL_FIRE", "Quemar"),
]

TERRAIN_NAMES = ["Tierra", "Roca", "Agua", "Nido"]
OBJECT_NAMES = ["-", "Pasto", "Mango", "Bocadillo"]


class DebugTools:
    def __init__(self, sim):
        self.sim = sim
        self.tool = "INSPECT"
        self.message = ""

    def select(self, tool):
        self.tool = tool
        self.message = f"Herramienta: {tool}"

    def apply(self, y, x):
        """Aplica la herramienta activa en la celda (y, x)."""
        s, t = self.sim, self.tool
        if t == "INSPECT":
            return
        if t in ("WORKER", "SOLDIER", "MARABUNTA"):
            ok = s.spawn_at(t, y, x)
        elif t == "GRASS":
            ok = s.place_resource(GRASS, y, x)
        elif t == "MANGO":
            ok = s.place_resource(MANGO, y, x)
        elif t == "BOCADILLO":
            ok = s.place_bocadillo(y, x)          # (y, x) = esquina superior izquierda
        elif t == "FIRE":
            ok = s.ignite(y, x)
        elif t == "KILL":
            ok = s.kill_at(y, x, "FIGHT")
        else:
            ok = s.kill_at(y, x, "FIRE")
        self.message = f"{t}: {'ok' if ok else 'no se pudo (celda inválida u ocupada)'}"

    def swarm(self):
        n = self.sim.spawn_swarm(config.SWARM_SIZE)
        self.message = f"Enjambre: {n} marabuntas"

    def random_fire(self):
        pos = self.sim.random_fire()
        self.message = f"Fuego en {pos}" if pos else "No hay nada combustible"

    def wind(self, dx, dy):
        self.sim.set_wind(dx * config.WIND_STEP, dy * config.WIND_STEP)
        self.message = f"Viento: ({config.WIND_X:.1f}, {config.WIND_Y:.1f})"

    def inspect_lines(self, y, x):
        a = self.sim.automaton
        k = int(a.objects.matrix[y, x])
        obj = OBJECT_NAMES[k] + (f" nivel {int(a.objects.level[y, x])}" if k == GRASS else "")
        fire = {0: "-", 1: "ARDIENDO", -1: "ceniza"}[int(a.fire.matrix[y, x])]
        ph = "/".join(f"{a.pheromones[n].matrix[y, x]:.1f}" for n in ("vegetal", "azucar", "alarma", "caza"))
        lines = [f"Celda ({y},{x})  {TERRAIN_NAMES[int(a.terrain.matrix[y, x])]}  hum {a.terrain.moisture[y, x]:.2f}",
                 f"Objeto: {obj}   Fuego: {fire}",
                 f"Feromonas V/A/AL/C: {ph}"]
        ag = self.sim.agent_at(y, x)
        if ag:
            lines.append(f"{ag.CASTE} {'viva' if ag.alive else 'muerta'}  estado {ag.state}")
            lines.append(f"energía {ag.energy:.0f}  vida {ag.health:.0f}")
        return lines