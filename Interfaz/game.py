"""Modo Dios (y Lucha): mapa a pantalla completa con HUD flotante translúcido.
Barra superior (ajustes, play, paso, reiniciar, semilla, velocidad), barra izquierda de menús (Edición, Entidades,
Eventos, Estadísticas), inspección por hover, fijar entes con clic, notificaciones y barra de ayuda inferior."""
import time
import pygame
import config
from .scenes import Scene
from .camera import Camera
from .map_renderer import MapRenderer, ViewState, LAYER_NAMES
from .entity_renderer import EntityRenderer
from .debug_tools import DebugTools
from . import ui, inspector
from Automata.objects import GRASS, MANGO, BOCADILLO
from Automata.terrain import ROCK, WATER, DIRT

# id -> (etiqueta, icono, ayuda)
TOOLS = {
    "GRASS": ("Pasto", "grass", "Pincel de pasto: clic o arrastra sobre tierra libre. Rueda: tamano. Clic derecho: soltar."),
    "WATER": ("Agua", "water", "Pincel de agua: clic o arrastra. La tierra que quede aislada del nido se vuelve roca."),
    "ROCK": ("Piedra", "rock", "Pincel de piedra: clic o arrastra. No se puede sobre el nido ni bajo una hormiga."),
    "DIRT": ("Borrar", "erase", "Borrador: devuelve tierra y quita pasto, frutas, fuego y feromona de las celdas."),
    "BOCADILLO": ("Bocadillo", "bocadillo", "Clic: coloca un bocadillo (2x2, esquina superior izquierda en la celda)."),
    "MANGO": ("Mango", "mango", "Clic: coloca un mango (2x2, esquina superior izquierda en la celda)."),
    "WORKER": ("Obrera", "worker", "Clic en tierra libre: crea una obrera (se paga con la bolsa de comida)."),
    "SOLDIER": ("Soldada", "soldier", "Clic en tierra libre: crea una soldada (se paga con la bolsa de comida)."),
    "MARABUNTA": ("Marabunta", "marabunta", "Clic en tierra libre: crea una marabunta suelta (gratis)."),
    "FIRE": ("Fuego", "fire", "Clic en una celda exacta con pasto o mango: empieza un incendio."),
    "LIGHTNING": ("Rayo", "lightning", "Clic en una celda exacta: prende pasto/mango o mata al ente vivo que este ahi."),
}
BRUSH_TOOLS = ("GRASS", "WATER", "ROCK", "DIRT")
BLOCK_TOOLS = ("BOCADILLO", "MANGO")
SIDEBAR = (("edit", "edit", "Edicion: pinta terreno y coloca frutas (pausa el juego)"),
           ("entities", "entities", "Entidades: crea hormigas y marabuntas (pausa el juego)"),
           ("events", "events", "Eventos naturales: fuego, rayo, lluvia, sequia, enjambre"),
           ("stats", "stats", "Estadisticas detalladas"))
BRUSH_COLORS = {"GRASS": (50, 200, 60), "WATER": (70, 130, 220), "ROCK": (140, 140, 140), "DIRT": (230, 200, 160),
                "BOCADILLO": (200, 40, 70), "MANGO": (255, 200, 30)}
IDLE_HELP = "Clic en un ente: fijar | WASD: viento | V B N M: capas | Z: todas | G: gradiente | H: humedad | Esc: ajustes"


class GodScene(Scene):
    def __init__(self, app, sim, waves=False):
        self.app, self.sim, self.waves = app, sim, waves          # waves = Lucha: oleadas cada LUCHA_SWARM_EVERY ticks
        self._last_wave = 0
        self.view = ViewState()
        self.map_renderer = MapRenderer(app.assets, sim, self.view)
        self.entities = EntityRenderer(app.assets)
        self.tools = DebugTools(sim)
        self.camera = Camera(sim.automaton.width, sim.automaton.height)
        self.font, self.font_b = app.font(14), app.font(16)

        self.paused, self.speeds, self.speed_i, self.acc = False, (1, 2, 4), 0, 0.0
        self.step_request = False
        self.menu, self.tool, self.modal = None, None, None
        self.brush_i = config.BRUSH_DEFAULT
        self.pinned = None
        self.hover = None                       # celda bajo el mouse (fuera del HUD)
        self.painting, self._last_paint = False, None
        self._menu_prev_pause = self._modal_prev_pause = None
        self.toasts = ui.Toasts()
        self._tv = sim.terrain_version
        self._tps, self._tps_n, self._tps_t = 0.0, 0, time.perf_counter()
        self._seen = {}
        self._dyn = []                          # rects de paneles dinámicos (para no inspeccionar debajo)
        self._build_keys()
        self._layout()
        self.camera.center_on(*sim.nest)

    @property
    def screen(self):
        return self.app.screen

    def on_resize(self):
        self._layout()

    def on_exit(self):
        self.app.audio.set_fight(False)

    def notify(self, text, color=None):
        self.toasts.push(text, color=color)

    # ------------------------------------------------------------ teclas y layout
    def _build_keys(self):
        self.keymap = {}
        for action, name in config.KEYS.items():
            code = getattr(pygame, "K_" + name, None)
            if code is not None:
                self.keymap[code] = action

    def _layout(self):
        W, H = self.screen.get_size()
        self.camera.set_view(W, H)
        self._rebuild()

    def _rebuild(self):
        """Reconstruye botones y paneles según el menú abierto."""
        B, G = config.UI_BUTTON, config.UI_GAP
        self.widgets, self.panels, self.labels = [], [], []
        add, B_ = self.widgets.append, ui.Button

        # --- barra superior
        self.panels.append(pygame.Rect(8, 8, B + 12, B + 12))
        add(B_((14, 14, B, B), self.open_settings, "gear", tip="Ajustes: volumen, atajos, volver al titulo"))
        x0 = 8 + B + 20
        self.panels.append(pygame.Rect(x0, 8, 8 + 4 * (B + G) + 56 + G + 210, B + 12))
        x = x0 + 8
        add(B_((x, 14, B, B), self.toggle_pause, lambda: "play" if self.paused else "pause",
               tip="Play / Pausa (Espacio)"))
        add(B_((x + (B + G), 14, B, B), self.request_step, "step", tip="Paso a paso (solo en pausa)",
               enabled=lambda: self.paused))
        add(B_((x + 2 * (B + G), 14, B, B), lambda: self.restart(), "restart", tip="Reiniciar el escenario (R)"))
        add(B_((x + 3 * (B + G), 14, B, B), self.open_seed, "seed", tip="Cambiar la semilla del mapa"))
        add(B_((x + 4 * (B + G), 14, 56, B), self.cycle_speed, label=lambda: f"x{self.speeds[self.speed_i]}",
               tip="Velocidad de simulacion"))
        self._status_pos = (x + 4 * (B + G) + 56 + 14, 8 + (B + 12) // 2)

        # --- barra izquierda (se oculta al editar) y su submenú
        y1 = 8 + B + 12 + 8
        if self.menu != "edit":
            self.panels.append(pygame.Rect(8, y1, B + 12, len(SIDEBAR) * (B + G) + G + 6))
            for i, (key, ic, tip) in enumerate(SIDEBAR):
                add(B_((14, y1 + 6 + i * (B + G), B, B), lambda k=key: self.set_menu(k), ic, tip=tip,
                       active=lambda k=key: self.menu == k))
        mx = 8 + B + 12 + 8
        if self.menu == "entities":
            self._menu_panel(mx, y1, 210, [("Entidades", None), ("WORKER",), ("SOLDIER",), ("MARABUNTA",)])
        elif self.menu == "events":
            self._menu_panel(mx, y1, 210, [("Eventos naturales", None), ("FIRE",), ("LIGHTNING",),
                                           ("act", "Lluvia", "rain", self.do_rain, "Lluvia en el centro de la vista"),
                                           ("act", "Sequia", "drought", self.do_drought, "Sequia en el centro de la vista"),
                                           ("act", "Enjambre", "swarm", self.do_swarm, "Enjambre de marabuntas en una orilla")])
        elif self.menu == "edit":
            self._menu_panel(8, y1, 220, [("Terreno", None), ("GRASS",), ("WATER",), ("ROCK",), ("DIRT",),
                                          ("Elementos", None), ("BOCADILLO",), ("MANGO",), ("Pincel", None),
                                          ("sizes",), ("ok",)])

    def _menu_panel(self, x, y, w, rows):
        """rows: (titulo, None) | (id_herramienta,) | ("act", etiqueta, icono, callback, ayuda) | ("sizes",) | ("ok",)."""
        def height(r):
            if len(r) == 2 and r[1] is None:
                return 22
            return 34 if r[0] == "sizes" else 40

        self.panels.append(pygame.Rect(x, y, w, 16 + sum(height(r) for r in rows)))
        cy = y + 8
        for r in rows:
            if len(r) == 2 and r[1] is None:
                self.labels.append((r[0], (x + 12, cy + 2)))
            elif r[0] == "sizes":
                n = len(config.BRUSH_SIZES)
                bw = (w - 20 - (n - 1) * 4) // n
                for i, sz in enumerate(config.BRUSH_SIZES):
                    self.widgets.append(ui.Button((x + 10 + i * (bw + 4), cy, bw, 30), lambda i=i: self._set_brush(i),
                                                  label=f"{sz}x{sz}", tip="Tamano del pincel (tambien con la rueda)",
                                                  active=lambda i=i: self.brush_i == i))
            elif r[0] == "ok":
                self.widgets.append(ui.Button((x + 10, cy + 4, w - 20, 36), lambda: self.set_menu(None), "ok", "OK",
                                              tip="Guardar la edicion, mostrar la barra y reanudar", accent=config.UI_OK_COLOR))
            elif r[0] == "act":
                self.widgets.append(ui.Button((x + 10, cy, w - 20, 36), r[3], r[2], r[1], tip=r[4]))
            else:
                lab, ic, tip = TOOLS[r[0]]
                self.widgets.append(ui.Button((x + 10, cy, w - 20, 36), lambda t=r[0]: self.select_tool(t), ic, lab,
                                              tip=tip, active=lambda t=r[0]: self.tool == t))
            cy += height(r)

    # ------------------------------------------------------------ control
    def toggle_pause(self):
        self.paused = not self.paused

    def request_step(self):
        if self.paused:
            self.step_request = True

    def cycle_speed(self):
        self.speed_i = (self.speed_i + 1) % len(self.speeds)

    def set_menu(self, m):
        prev = self.menu
        if m == prev:
            m = None
        self.menu, self.tool = m, None
        pausing = ("edit", "entities")
        if m in pausing and prev not in pausing:
            self._menu_prev_pause, self.paused = self.paused, True
        elif prev in pausing and m not in pausing and self._menu_prev_pause is not None:
            self.paused, self._menu_prev_pause = self._menu_prev_pause, None
            if prev == "edit":
                self.notify("Edicion guardada")
        self._rebuild()

    def select_tool(self, t):
        self.tool = None if self.tool == t else t

    def _set_brush(self, i):
        self.brush_i = max(0, min(len(config.BRUSH_SIZES) - 1, i))

    def restart(self, seed=None):
        self.sim.reset(self.sim.seed if seed is None else seed)
        self.map_renderer.rebuild()
        self._tv = self.sim.terrain_version
        self.camera.center_on(*self.sim.nest)
        self.acc, self._last_wave, self.pinned, self._seen = 0.0, 0, None, {}
        self.notify(f"Reiniciado (semilla {self.sim.seed})")

    def open_settings(self):
        self._open_modal(ui.SettingsModal(self.app, self._close_modal, self._to_title))

    def open_seed(self):
        if self.sim.scenario is not None:
            self.notify("Este escenario tiene semilla fija")
            return
        self._open_modal(ui.NumberModal(self.app, "Semilla del mapa", self.sim.seed,
                                        lambda v: (self._close_modal(), self.restart(v)), self._close_modal))

    def _open_modal(self, m):
        self._modal_prev_pause, self.paused, self.modal = self.paused, True, m

    def _close_modal(self):
        self.modal = None
        if self._modal_prev_pause is not None:
            self.paused, self._modal_prev_pause = self._modal_prev_pause, None

    def _to_title(self):
        from .ui_scenes import TitleScene
        scenes = self.app.scenes
        while scenes.top is not None:
            scenes.pop()
        scenes.push(TitleScene(self.app))

    # ------------------------------------------------------------ acciones de eventos
    def do_rain(self):
        self.sim.rain(*self.camera.center_cell())
        self.notify("Lluvia en el centro de la vista")

    def do_drought(self):
        self.sim.drought(*self.camera.center_cell())
        self.notify("Sequia en el centro de la vista")

    def do_swarm(self):
        n = self.sim.spawn_swarm(config.SWARM_SIZE)
        self.notify(f"Enjambre: {n} marabuntas en una orilla", (255, 150, 150))

    # ------------------------------------------------------------ eventos de entrada
    def handle_event(self, e):
        if self.modal:
            self.modal.handle_event(e)
            if self.modal is not None and self.modal.closed:
                self._close_modal()
            return
        if e.type == pygame.KEYDOWN:
            self._key(e.key)
        elif e.type == pygame.MOUSEBUTTONDOWN:
            if e.button == 1:
                self._click(e.pos)
            elif e.button == 3:
                self._release()
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            self.painting = False
        elif e.type == pygame.MOUSEWHEEL and self.tool in BRUSH_TOOLS:
            self._set_brush(self.brush_i + (1 if e.y > 0 else -1))

    def _release(self):
        if self.tool:
            self.tool = None
        elif self.pinned is not None:
            self.pinned = None

    def _key(self, k):
        if k == pygame.K_ESCAPE:
            if self.tool or self.pinned is not None:
                self._release()
            elif self.menu:
                self.set_menu(None)
            else:
                self.open_settings()
            return
        act = self.keymap.get(k)
        wind = {"wind_up": (0, -1), "wind_down": (0, 1), "wind_left": (-1, 0), "wind_right": (1, 0)}
        if act == "pause":
            self.toggle_pause()
        elif act == "step":
            self.request_step()
        elif act == "restart":
            self.restart()
        elif act in wind:
            self.tools.wind_add(*wind[act])
        elif act == "wind_zero":
            self.tools.wind(0, 0)
        elif act and act.startswith("layer_"):
            self.view.layers[act[6:]] = not self.view.layers[act[6:]]
            self.view.pheromones = True
        elif act == "layers_all":
            on = not any(self.view.layers.values())
            for n in LAYER_NAMES:
                self.view.layers[n] = on
            self.view.pheromones = True
        elif act == "gradient":
            self.view.gradient = not self.view.gradient
        elif act == "traffic":
            self.view.traffic = not self.view.traffic
        elif act == "moisture":
            self.view.moisture = not self.view.moisture

    def over_hud(self, pos):
        return any(r.collidepoint(pos) for r in self.panels + self._dyn)

    def _click(self, pos):
        for w in self.widgets:
            if w.click(pos):
                return
        if self.over_hud(pos) or pos[1] >= self.screen.get_height() - config.HELP_BAR_H:
            return
        cell = self.camera.screen_to_cell(*pos)
        if cell is None:
            return
        if self.tool:
            self._apply(cell, first=True)
            if self.tool in BRUSH_TOOLS:
                self.painting, self._last_paint = True, cell
        else:
            ag = self.sim.agent_at(*cell)
            self.pinned = None if (ag is None or ag is self.pinned) else ag      # otra vez sobre el mismo: suelta

    # ------------------------------------------------------------ herramientas
    def _brush_cells(self, y, x):
        n = config.BRUSH_SIZES[self.brush_i]
        o = (n - 1) // 2
        a = self.sim.automaton
        return [(y - o + j, x - o + i) for j in range(n) for i in range(n)
                if 0 <= y - o + j < a.height and 0 <= x - o + i < a.width]

    def _apply(self, cell, first):
        y, x = cell
        s, t = self.sim, self.tool
        ok = True
        if t in BRUSH_TOOLS:
            cells = self._brush_cells(y, x)
            if t == "GRASS":
                ok = sum(1 for cy, cx in cells if s.place_resource(GRASS, cy, cx)) > 0
            else:
                kind = {"WATER": WATER, "ROCK": ROCK, "DIRT": DIRT}[t]
                ok = s.paint_terrain(kind, cells, erase=(t == "DIRT")) > 0
        elif not first:
            return
        elif t == "MANGO":
            ok = s.place_resource(MANGO, y, x)
        elif t == "BOCADILLO":
            ok = s.place_bocadillo(y, x)
        elif t in ("WORKER", "SOLDIER", "MARABUNTA"):
            ok = s.spawn_at(t, y, x)
            if not ok and s.last_error:
                self.notify(s.last_error, (255, 150, 150))
                s.last_error = ""
                return
        elif t == "FIRE":
            ok = s.ignite(y, x)
        elif t == "LIGHTNING":
            ok = s.lightning(y, x)
        if not ok and first:
            self.notify("No se pudo ahi (celda ocupada o invalida)", (255, 150, 150))

    # ------------------------------------------------------------ actualización
    def update(self, dt):
        T = config.TICK_SECONDS
        self.camera.update(pygame.key.get_pressed(), dt)
        self.toasts.update(dt)
        self._update_hover()
        if self.modal is None and self.painting and self.hover and pygame.mouse.get_pressed()[0] \
                and self.tool in BRUSH_TOOLS and self.hover != self._last_paint:
            self._last_paint = self.hover
            self._apply(self.hover, first=False)

        if not self.paused:
            self.acc += dt * self.speeds[self.speed_i]
            n = 0
            while self.acc >= T and n < config.MAX_STEPS_PER_FRAME:
                self.acc -= T
                self._step()
                n += 1
            if self.acc >= T:
                self.acc = 0.0
        elif self.step_request:
            self._step()
            self.acc = T * 0.999
        self.step_request = False

        if self.sim.terrain_version != self._tv:
            self._tv = self.sim.terrain_version
            self.map_renderer.rebuild()
        if self.pinned is not None and self.pinned not in self.sim.agents:
            self.pinned = None
            self.notify("El ente fijado ya no esta en el mapa")

        audio = self.app.audio
        for ev in self.sim.events:
            audio.play_event(ev, self.camera)
        self.sim.events.clear()
        audio.set_fight(any(ag.alive and ag.CASTE == "MARABUNTA" for ag in self.sim.agents))

    def _update_hover(self):
        pos = pygame.mouse.get_pos()
        self.hover = None
        if self.modal is None and not self.over_hud(pos) and pos[1] < self.screen.get_height() - config.HELP_BAR_H:
            self.hover = self.camera.screen_to_cell(*pos)

    def _step(self):
        if self.waves and self.sim.tick - self._last_wave >= config.LUCHA_SWARM_EVERY:
            self._last_wave = self.sim.tick
            n = self.sim.spawn_swarm(config.SWARM_SIZE)
            self.notify(f"Oleada: {n} marabuntas", (255, 150, 150))
        self.sim.step()
        self._tps_n += 1
        now = time.perf_counter()
        if now - self._tps_t >= 1.0:
            self._tps, self._tps_n, self._tps_t = self._tps_n / (now - self._tps_t), 0, now
        self._watch()

    def _watch(self):
        """Avisos de borde (una vez por cambio): hambre, hongo, marabuntas, saqueo, incendio, clima, fin."""
        st, seen, now = self.sim.stats(), self._seen, self.sim.tick

        def edge(key, value, text, color=None, cooldown=0):
            if value and not seen.get(key) and now - seen.get(key + "_t", -10 ** 9) >= cooldown:
                self.notify(text, color)
                seen[key + "_t"] = now
            seen[key] = value

        edge("starving", st["starving"], "El hongo se quedo sin comida", (255, 150, 150))
        edge("stressed", st["stressed"], "Hongo estresado: demasiado bocadillo en reserva", cooldown=200)
        edge("mara", st["MARABUNTA"] > 0, "Marabuntas en el mapa", (255, 150, 150))
        edge("fire", st["burning"] > 0, "Incendio en el mapa", (255, 170, 90), cooldown=100)
        edge("rain", st["rain_zones"] > 0, "Esta lloviendo", cooldown=100)
        edge("drought", st["drought_zones"] > 0, "Sequia", cooldown=100)
        if st["stolen"] > seen.get("stolen_v", 0) + 0.5:
            if now - seen.get("stolen_t", -10 ** 9) >= 60:
                self.notify("Marabuntas saquean el nido", (255, 150, 150))
                seen["stolen_t"] = now
            seen["stolen_v"] = st["stolen"]
        edge("over", st["game_over"], "Fin de la colonia: " + st["game_over_reason"], (255, 150, 150))

    # ------------------------------------------------------------ dibujo
    def draw(self, screen):
        s = min(1.0, self.acc / config.TICK_SECONDS)
        screen.fill((12, 12, 14))
        self.map_renderer.draw(screen, self.camera, s)
        self.entities.draw(screen, self.camera, self.sim, s, highlight=self.pinned)
        self._draw_preview(screen)
        self._draw_wind(screen)
        self._dyn = []
        self._draw_hud(screen)
        self._draw_info(screen)
        H = screen.get_height()
        self.toasts.draw(screen, self.font_b, H - config.HELP_BAR_H - 6)
        ui.draw_help(screen, self.font, self._help_text())
        if self.sim.game_over:
            self.paused = True
            self._draw_game_over(screen)
        if self.modal:
            self.modal.draw(screen)

    def _help_text(self):
        mouse = pygame.mouse.get_pos()
        for w in self.widgets:
            if w.rect.collidepoint(mouse) and w.tip:
                return w.tip
        if self.tool:
            lab, _, tip = TOOLS[self.tool]
            return f"Herramienta: {lab}. {tip}"
        if self.menu == "stats":
            return "Estadisticas detalladas de la colonia, el saqueo, el mapa y el clima."
        return IDLE_HELP

    def _draw_preview(self, screen):
        """Vista previa semitransparente de lo que hará el clic."""
        if not (self.tool and self.hover and self.modal is None):
            return
        T, (y, x) = config.TILE, self.hover
        if self.tool in BRUSH_TOOLS:
            cells = self._brush_cells(y, x)
        elif self.tool in BLOCK_TOOLS:
            cells = [(y + dy, x + dx) for dy in (0, 1) for dx in (0, 1)]
        elif self.tool in ("WORKER", "SOLDIER", "MARABUNTA", "FIRE", "LIGHTNING"):
            cells = [(y, x)]
        else:
            return
        col = BRUSH_COLORS.get(self.tool, (255, 230, 120))
        tile = pygame.Surface((T, T), pygame.SRCALPHA)
        tile.fill((*col, 110))
        pygame.draw.rect(tile, (*col, 230), tile.get_rect(), 2)
        screen.blits([(tile, (cx * T - self.camera.x, cy * T - self.camera.y)) for cy, cx in cells])

    def _draw_wind(self, screen):
        wx, wy = config.WIND_X, config.WIND_Y
        cx, cy = screen.get_width() // 2, 24
        ui.draw_panel(screen, (cx - 20, cy - 20, 40, 40), radius=20)
        if wx == 0 and wy == 0:
            pygame.draw.circle(screen, (140, 140, 150), (cx, cy), 3)
            return
        n = max(1e-6, (wx * wx + wy * wy) ** 0.5)
        ux, uy = wx / n, wy / n
        tip, tail = (cx + ux * 13, cy + uy * 13), (cx - ux * 11, cy - uy * 11)
        pygame.draw.line(screen, (235, 235, 235), tail, tip, 2)
        for sg in (-1, 1):
            pygame.draw.line(screen, (235, 235, 235), tip, (tip[0] - ux * 6 - sg * uy * 4, tip[1] - uy * 6 + sg * ux * 4), 2)

    def _draw_hud(self, screen):
        mouse = pygame.mouse.get_pos()
        for r in self.panels:
            ui.draw_panel(screen, r)
        for text, pos in self.labels:
            ui.draw_text(screen, self.font_b, text, pos, config.UI_ACCENT)
        for w in self.widgets:
            w.draw(screen, self.font_b, mouse)
        st = f"Tick {self.sim.tick}" + ("  PAUSA" if self.paused else f"  {self._tps:.0f} t/s")
        ui.draw_text(screen, self.font, st, self._status_pos, config.UI_TEXT_COLOR, "midleft")
        if self.menu == "stats":
            self._draw_stats(screen)

    def _draw_stats(self, screen):
        sim, a = self.sim, self.sim.automaton
        st, c = sim.stats(), a.colony
        hw = int((sim.traffic >= config.TRAFFIC_HIGHWAY).sum())
        causes = ", ".join(f"{k} {v}" for k, v in sorted(sim.death_causes.items())) or "-"
        K, W_, A = "kv", inspector.WHITE, config.UI_ACCENT
        L = [("title", "Poblacion", A),
             (K, "Obreras / Soldadas", f"{st['WORKER']} / {st['SOLDIER']}", W_),
             (K, "Marabuntas", str(st["MARABUNTA"]), W_),
             (K, "En cola / Crias", f"{st['queued']} / {st['brood']}", W_),
             (K, "Nacimientos", str(st["births"]), W_),
             (K, "Bajas O/S/M", f"{sim.deaths['WORKER']} / {sim.deaths['SOLDIER']} / {sim.deaths['MARABUNTA']}", W_),
             (K, "Causas", causes, inspector.DIM),
             ("title", "Alimento", A),
             (K, "Bolsa (unidades)", f"{st['units']:.0f}", inspector.BAD if st["starving"] else W_),
             (K, "Pasto / Mango / Bocad.", f"{st['stock'][0]} / {st['stock'][1]} / {st['stock'][2]}", W_),
             (K, "Entregado (u)", f"{c.delivered_units():.0f}", W_),
             (K, "Hongo", "ESTRESADO" if st["stressed"] else ("HAMBRE" if st["starving"] else "normal"), W_),
             ("title", "Saqueo", A),
             (K, "Robado / Recup. / Perdido", f"{st['stolen']:.0f} / {st['recovered']:.0f} / {st['lost']:.0f}", W_),
             (K, "Botines en el mapa", str(st["loot"]), W_),
             ("title", "Mapa y clima", A),
             (K, "Pasto / Mango / Bocad.", f"{st['grass']} / {st['mango']} / {st['bocadillos']}", W_),
             (K, "Fuego / Ceniza", f"{st['burning']} / {st['ash']}", W_),
             (K, "Humedad media", f"{a.terrain.moisture.mean():.2f}", W_),
             (K, "Lluvias / Sequias", f"{st['rain_zones']} / {st['drought_zones']}", W_),
             (K, "Viento", f"({config.WIND_X:.1f}, {config.WIND_Y:.1f})", W_),
             ("title", "Simulacion", A),
             (K, "Autopistas (celdas)", str(hw), W_),
             (K, "Velocidad", f"{self._tps:.0f} ticks/s", W_),
             (K, "Semilla", str(sim.seed), W_)]
        B = config.UI_BUTTON
        self._dyn.append(ui.draw_lines(screen, self.font, (8 + B + 20, 8 + B + 20), 330, L))

    def _draw_info(self, screen):
        """Inspección: el ente fijado (siempre) y lo que hay bajo el cursor (ente, o suelo con feromonas)."""
        W = screen.get_width()
        y = 8
        if self.pinned is not None:
            r = ui.draw_lines(screen, self.font, (W - 268, y), 260,
                              [("text", "[FIJADO] clic para soltar", inspector.GOOD)] + inspector.agent_lines(self.pinned))
            self._dyn.append(r)
            y = r.bottom + 6
        if self.hover:
            ag = self.sim.agent_at(*self.hover)
            if ag is None:
                lines = inspector.ground_lines(self.sim, *self.hover)
            elif ag is not self.pinned:
                lines = inspector.agent_lines(ag)
            else:
                return
            self._dyn.append(ui.draw_lines(screen, self.font, (W - 268, y), 260, lines))

    def _draw_game_over(self, screen):
        W, H = screen.get_size()
        ui._dim(screen, 120)
        box = pygame.Rect((W - 460) // 2, H // 2 - 110, 460, 220)
        ui.draw_panel(screen, box, alpha=235)
        st = self.sim.summary()
        ui.draw_text(screen, self.app.font(34), "FIN DE LA COLONIA", (box.centerx, box.y + 40), (255, 200, 120), "center")
        ui.draw_text(screen, self.font_b, self.sim.game_over_reason, (box.centerx, box.y + 82), anchor="center")
        ui.draw_text(screen, self.font, f"Ticks {st['ticks']}   Nacimientos {self.sim.births}   "
                     f"Bajas obreras {st['deaths']['WORKER']}", (box.centerx, box.y + 116), config.UI_DIM_COLOR, "center")
        ui.draw_text(screen, self.font, "R: reiniciar    Esc: ajustes / volver al titulo", (box.centerx, box.y + 160),
                     inspector.GOOD, "center")