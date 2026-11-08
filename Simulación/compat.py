"""Parche TEMPORAL mientras Colony no tenga la economía que usa Simulation.

simulation.py ya llama a colony.can_afford / pay / upkeep / stock y a
config.U_AZUCAR, pero Automata/colony.py todavía no los define. Para poder
probar el menú y el script sin pygame, este módulo rellena SOLO lo que falte
con un comportamiento neutro:

  - can_afford(casta) -> False   (no nacen hormigas nuevas)
  - pay(casta)        -> False
  - upkeep()          -> True    (nadie muere de hambre)
  - stock             -> {}
  - config.U_AZUCAR   -> config.T_SUGAR

Si Colony ya tiene un método, no se toca. Cuando la economía real exista,
este archivo deja de hacer nada y se puede borrar (y sus dos llamadas).
"""
import config
from Automata.colony import Colony

_NEUTRAL = {
    "can_afford": lambda self, caste: False,
    "pay": lambda self, caste: False,
    "upkeep": lambda self: True,
}


def ensure_colony_api(verbose=True):
    """Rellena lo que falte. Devuelve la lista de nombres parcheados."""
    patched = []
    if not hasattr(config, "U_AZUCAR"):
        config.U_AZUCAR = getattr(config, "T_SUGAR", 10)
        patched.append("config.U_AZUCAR")
    for name, fn in _NEUTRAL.items():
        if not hasattr(Colony, name):
            setattr(Colony, name, fn)
            patched.append(f"Colony.{name}")
    if not hasattr(Colony, "stock"):
        Colony.stock = property(lambda self: {})
        patched.append("Colony.stock")
    if patched and verbose:
        print("[compat] faltan en Colony/config, uso valores neutros:", ", ".join(patched))
    return patched
