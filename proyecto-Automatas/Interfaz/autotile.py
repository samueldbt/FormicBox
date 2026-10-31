"""Bordes por vecindad (la regla S(t+1)=F(S,N,P) aplicada a la capa visual).

Máscara de 4 bits: N=1, E=2, S=4, O=8. Cada bit vale 1 si ese vecino ORTOGONAL es de
otra clase. Fuera del mapa cuenta como igual (no hay orillas falsas en el borde)."""
import numpy as np

N, E, S, W = 1, 2, 4, 8

# Forma base (con el borde hacia el norte) -> su máscara
BASE_MASKS = {
    "interior": 0,
    "edge": N,
    "corridor": N | S,
    "corner": N | E,
    "peninsula": N | E | S,
    "island": N | E | S | W,
}


def rotl4(mask, r):
    """Gira la máscara r pasos de 90° en sentido horario (N->E->S->O->N)."""
    return ((mask << r) | (mask >> (4 - r))) & 15


def masks(same):
    """same: matriz bool, True donde la celda es de la clase. Devuelve la máscara (uint8) de cada celda."""
    p = np.pad(same, 1, mode="constant", constant_values=True)
    m = (~p[:-2, 1:-1]).astype(np.uint8) * N
    m += (~p[1:-1, 2:]).astype(np.uint8) * E
    m += (~p[2:, 1:-1]).astype(np.uint8) * S
    m += (~p[1:-1, :-2]).astype(np.uint8) * W
    return m