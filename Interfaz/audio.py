"""Audio: 8 canales de pygame.mixer (0-1 música con crossfade, 2-7 efectos). Volumen de efectos por distancia
a la cámara. Si falta un archivo o no hay dispositivo de audio, avisa por consola y sigue en silencio."""
import math
import pygame
import config
from . import manifest

SFX = {
    "fire": "audio/sfx/fire.ogg", "thunder": "audio/sfx/thunder.ogg", "bite": "audio/sfx/bite.ogg",
    "deliver": "audio/sfx/deliver.ogg", "death": "audio/sfx/death.ogg", "menu": "audio/sfx/menu.ogg",
}
MUSIC = {"calm": "audio/music/calm.ogg", "fight": "audio/music/fight.ogg"}
EVENT_SFX = {"fire": "fire", "thunder": "thunder", "bite": "bite", "deliver": "deliver", "death": "death"}


class AudioManager:
    def __init__(self):
        self.ok = False
        self.sfx, self.music, self.ch = {}, {}, {}
        self._warned = set()
        self.fight = 0.0            # 0 = pista calma, 1 = pista de lucha
        self.want_fight = False
        try:
            pygame.mixer.init()
            pygame.mixer.set_num_channels(8)
            self.ok = True
        except pygame.error as e:
            print(f"[audio] sin mixer, sigo en silencio: {e}")
            return
        for k, rel in SFX.items():
            self.sfx[k] = self._load(rel)
        for i, (k, rel) in enumerate(MUSIC.items()):
            self.music[k] = self._load(rel)
            self.ch[k] = pygame.mixer.Channel(i)
            if self.music[k] is not None:
                self.ch[k].play(self.music[k], loops=-1)
        self._apply_music()

    def _load(self, rel):
        path = manifest.ROOT / rel
        if not path.is_file():
            if rel not in self._warned:
                self._warned.add(rel)
                print(f"[audio] falta {rel}: silencio")
            return None
        try:
            return pygame.mixer.Sound(str(path))
        except pygame.error as e:
            print(f"[audio] no pude cargar {rel}: {e}")
            return None

    def _apply_music(self):
        v = config.VOL_MASTER * config.VOL_MUSIC
        self.ch["calm"].set_volume(v * (1.0 - self.fight))
        self.ch["fight"].set_volume(v * self.fight)

    def set_fight(self, on):
        self.want_fight = on

    def update(self, dt):
        """Crossfade entre la pista calma y la de lucha."""
        if not self.ok:
            return
        step = dt / max(0.01, config.AUDIO_FADE_SECONDS)
        target = 1.0 if self.want_fight else 0.0
        self.fight = min(target, self.fight + step) if self.fight < target else max(target, self.fight - step)
        self._apply_music()

    def play(self, name, y=None, x=None, cam=None):
        """Efecto de sonido. Con (y, x) y cámara, el volumen baja con la distancia al centro de la vista."""
        if not self.ok:
            return
        snd = self.sfx.get(name)
        if snd is None:
            return
        vol = config.VOL_MASTER * config.VOL_SFX
        if cam is not None and y is not None:
            T = config.TILE
            cy, cx = (cam.y + cam.view_h / 2) / T, (cam.x + cam.view_w / 2) / T
            vol *= max(0.0, 1.0 - math.hypot(y - cy, x - cx) / config.AUDIO_MAX_DIST)
        if vol <= 0.01:
            return
        ch = pygame.mixer.find_channel()
        if ch is not None:
            ch.set_volume(vol)
            ch.play(snd)

    def play_event(self, ev, cam):
        kind, y, x = ev
        name = EVENT_SFX.get(kind)
        if name:
            self.play(name, y, x, cam)