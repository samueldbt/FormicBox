"""Dibuja las hormigas: posición visual interpolada, independiente de la posición lógica."""
import config
from .assets import DIR_INDEX


class EntityRenderer:
    def __init__(self, assets):
        self.A = assets

    def draw(self, surf, cam, sim, s):
        """s = progreso del tick actual (0..1)."""
        T = config.TILE
        sp = self.A.sprites
        frame = min(config.ANIM_FRAMES - 1, int(s * config.ANIM_FRAMES))
        nest = sim.nest
        vw, vh = surf.get_size()
        dead, alive = [], []

        for ag in sim.agents:
            moved = (ag.prev_y, ag.prev_x) != (ag.y, ag.x)
            # Quieta dentro del nido = bajo tierra, no se dibuja
            if ag.alive and not moved and (ag.y, ag.x) == nest:
                continue
            fy = ag.prev_y + (ag.y - ag.prev_y) * s
            fx = ag.prev_x + (ag.x - ag.prev_x) * s
            px, py = int(fx * T - cam.x), int(fy * T - cam.y)
            if px < -T or py < -T or px > vw or py > vh:
                continue

            if ag.alive:
                action = "ATTACK" if ag.attacking else "WALK"
                carry = int(ag.carried_resource) if ag.CASTE == "WORKER" else 0
                k = frame if (moved or ag.attacking) else 0     # quieta = frame 0
                alive.append((ag, action, carry, k, px, py))
            else:
                action = "DEAD_FIRE" if ag.death_cause == "FIRE" else "DEAD_FIGHT"
                dead.append((ag, action, 0, 0, px, py))

        # Cadáveres debajo de las vivas
        for group in (dead, alive):
            surf.blits([(sp[self.A.anim[(ag.CASTE, act, carry, DIR_INDEX[ag.facing])][k]], (px, py))
                        for ag, act, carry, k, px, py in group])