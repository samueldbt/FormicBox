"""Dibuja las hormigas: posición visual interpolada, independiente de la posición lógica."""
import pygame
import config
from .assets import DIR_INDEX

# Desplazamiento (px a TILE=32) de las aliadas que comparten celda: la 1.ª al centro, las demás alrededor
OFFSETS = ((0, 0), (9, -9), (-9, 9), (9, 9), (-9, -9), (0, 12), (12, 0), (0, -12), (-12, 0))


def carry_code(ag):
    """0 nada, 1-3 recurso (obrera), 4 botín (cualquier casta que lleve crías o comida robada)."""
    if ag.CASTE == "WORKER":
        return 4 if getattr(ag, "carried_loot", None) is not None else int(ag.carried_resource)
    if ag.CASTE == "SOLDIER":
        return 4 if getattr(ag, "carried_loot", None) is not None else 0
    return 4 if ag.loot_count() > 0 else 0


class EntityRenderer:
    def __init__(self, assets):
        self.A = assets

    def draw(self, surf, cam, sim, s, highlight=None):
        """s = progreso del tick actual (0..1). highlight = ente fijado (se le dibuja un marco)."""
        T = config.TILE
        sp = self.A.sprites
        frame = min(config.ANIM_FRAMES - 1, int(s * config.ANIM_FRAMES))
        nest = sim.nest
        vw, vh = surf.get_size()
        dead, alive = [], []
        slots = {}                                    # celda -> cuántas vivas ya dibujadas ahí (para el offset)
        k_off = T / 32.0
        mark = None

        for ag in sim.agents:
            if getattr(ag, "escaped", False):
                continue
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
                carry = carry_code(ag)
                k = frame if (moved or ag.attacking) else 0     # quieta = frame 0
                n = slots.get((ag.y, ag.x), 0)
                slots[(ag.y, ag.x)] = n + 1
                ox, oy = OFFSETS[n % len(OFFSETS)]
                px, py = px + int(ox * k_off), py + int(oy * k_off)
                alive.append((ag, action, carry, k, px, py))
            else:
                action = {"FIRE": "DEAD_FIRE", "LIGHTNING": "DEAD_FIRE", "STARVE": "DEAD_STARVE",
                          "HUNGER": "DEAD_STARVE"}.get(ag.death_cause, "DEAD_FIGHT")
                dead.append((ag, action, 0, 0, px, py))
            if ag is highlight:
                mark = (px, py)

        anim = self.A.anim
        for group in (dead, alive):                   # cadáveres debajo de las vivas
            blits = []
            for ag, act, carry, k, px, py in group:
                key = (ag.CASTE, act, carry, DIR_INDEX[ag.facing])
                if key not in anim:                   # sin arte para esa carga/acción: usa la sin carga
                    key = (ag.CASTE, act, 0, DIR_INDEX[ag.facing])
                blits.append((sp[anim[key][k]], (px, py)))
            surf.blits(blits)

        if mark is not None:
            pygame.draw.rect(surf, (255, 220, 90), (mark[0] - 2, mark[1] - 2, T + 4, T + 4), 2, border_radius=6)