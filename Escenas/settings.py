"""Ajustes del jugador guardados en settings.json (carpeta del proyecto).

No usa pygame. Si el archivo no existe, está dañado o trae valores raros, se
usan los valores por defecto (campo por campo) sin lanzar excepciones.
"""
import json
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "settings.json"

VOLUME_STEP = 5
DEFAULTS = {
    "music_volume": 70,     # 0..100, de 5 en 5 (todavía no hay sonido: solo se guarda)
    "sfx_volume": 70,
    "fullscreen": False,
}


def _clean_volume(value, default):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    value = int(round(value / VOLUME_STEP) * VOLUME_STEP)
    return max(0, min(100, value))


def _clean(data):
    out = dict(DEFAULTS)
    if not isinstance(data, dict):
        return out
    for key in ("music_volume", "sfx_volume"):
        out[key] = _clean_volume(data.get(key), DEFAULTS[key])
    if isinstance(data.get("fullscreen"), bool):
        out["fullscreen"] = data["fullscreen"]
    return out


def load(path=PATH):
    """Devuelve un dict completo y válido. Nunca falla."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return dict(DEFAULTS)
    except (OSError, ValueError) as e:      # ValueError incluye JSON mal formado y UnicodeDecodeError
        print(f"[ajustes] {Path(path).name} ilegible ({e.__class__.__name__}); uso valores por defecto")
        return dict(DEFAULTS)
    return _clean(data)


def save(settings, path=PATH):
    """Guarda los ajustes. Devuelve True si pudo escribir el archivo."""
    try:
        tmp = Path(path).with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_clean(settings), f, indent=2)
        tmp.replace(path)                   # escritura atómica: no deja un JSON a medias
        return True
    except OSError as e:
        print(f"[ajustes] no se pudo guardar {Path(path).name}: {e}")
        return False
