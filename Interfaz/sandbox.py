"""Testeo: sandbox de comparación. Dos simulaciones A y B sobre la MISMA semilla y el mismo escenario, cada una con
sus propias constantes (feromonas, colisiones, capas, viento, clima...). Una sola cámara las mueve a la vez, y las
herramientas (fuego, rayo, lluvia...) caen en la misma celda en las dos."""
import time
import pygame
import config
from .scenes import Scene
from .camera import Camera
from .map_renderer import MapRenderer, ViewState, LAYER_NAMES
from .entity_renderer import EntityRenderer
from . import ui, inspector
from Automata.scenario import list_scenarios, get_scenario
from Automata.objects import MANGO
from Simulación.comparacion import COMPARISONS, Side, metrics

TOOLS = (("INSPECT", "Ver", "eye", "Pasa el cursor: muestra la celda o el ente (en el lado donde estes)."),
         ("FIRE", "Fuego", "fire", "Clic: enciende fuego en la MISMA celda de A y B."),
         ("LIGHTNING", "Rayo", "lightning", "Clic: cae un rayo en la misma celda de A y B."),
         ("RAIN", "Lluvia", "rain", "Clic: lluvia centrada en la celda, en A y B."),
         ("DROUGHT", "Sequia", "drought", "Clic: sequia centrada en la celda, en A y B."),
         ("MANGO", "Mango", "mango", "Clic: pone un mango en A y B."))

ROWS = (("Tick", "tick", "{:.0f}"), ("Obreras", "workers", "{:.0f}"), ("Soldadas", "soldiers", "{:.0f}"),
        ("Marabuntas", "mara", "{:.0f}"), ("Entregado (u)", "delivered", "{:.0f}"), ("Bolsa (u)", "units", "{:.0f}"),
        ("Nacimientos", "births", "{:.0f}"), ("Bajas", "deaths", "{:.0f}"), ("Autopistas", "highway", "{:.0f}"),
        ("Rastro (celdas)", "trail", "{:.0f}"), ("Fuego / Ceniza", None, ""), ("Humedad media", "moist", "{:.2f}"),
        ("Robado/Recup./Perdido", None, ""))


class SandboxScene(Scene):
    def __init__(self, app, scenario_i=1, comp_i=0):
        self.app = app
        self.font, self.font_b = app.font(14), app.font(16)
        self.scen_ids = [None] + [s.id for s in list_scenarios()]       # None = mapa aleatorio
        self.scen_i, self.comp_i = scenario_i % len(self.scen_ids), comp_i
        self.seed = config.SEED
        self.view = ViewState()
        self.camera = Camera(config.WIDTH, config.HEIGHT)
        self.paused, self.speeds, self.speed_i, self.acc = False, (1, 2, 4), 0, 0.0
        self.step_request, self.tool, self.modal = False, "INSPECT", None
        self.hover = None
        self._prev_pause = None
        self._tps, self._tps_n, self._tps_t = 0.0, 0, time.perf_counter()
        self.toasts = ui.Toasts()
        self._panels = []
        self._build()

    @property
    def screen(self):
        return self.app.screen

    def on_resize(self):
        self._layout()

    # ------------------------------------------------------------ construcción
    def _build(self):
        sid, comp = self.scen_ids[self.scen_i], COMPARISONS[self.comp_i]
        scn = get_scenario(sid) if sid else None
        base = {"WIND_X": scn.wind[0] if scn else config.WIND_X, "WIND_Y": scn.wind[1] if scn else config.WIND_Y,
                "WEATHER_AUTO": scn.auto_weather if scn else False}
        self.sides = [Side(sid, self.seed, {**base, **comp["a"]}, comp["la"])]
        if comp["b"] is not None:
            self.sides.append(Side(sid, self.seed, {**base, **comp["b"]}, comp["lb"]))
        self.rend = [(MapRenderer(self.app.assets, sd.sim, self.view), EntityRenderer(self.app.assets)) for sd in self.sides]
        self._tv = [sd.sim.terrain_version for sd in self.sides]
        self.camera = Camera(self.sides[0].sim.automaton.width, self.sides[0].sim.automaton.height)
        self.acc = 0.0
        self.view.moisture = self.sides[0].sim.no_ants          # escenarios sin hormigas: se mira la humedad
        self.tip = scn.tip if scn else "Mapa aleatorio: la semilla se cambia con el boton de semilla."
        self._layout()
        self.camera.center_on(*self.sides[0].sim.nest)

    def _layout(self):
        W, H = self.screen.get_size()
        n = len(self.sides)
        self.halves = [pygame.Rect(i * (W // n), 0, W // n if i < n - 1 else W - i * (W // n), H) for i in range(n)]
        self.camera.set_view(self.halves[0].w, H)
        B, G = config.UI_BUTTON, config.UI_GAP
        add, B_ = [], ui.Button
        self.widgets = add
        x, y = 14, 14
        add.append(B_((x, y, B, B), lambda: self.app.scenes.pop(), "back", tip="Volver al menu (Esc)"))
        add.append(B_((x + (B + G), y, B, B), self._toggle_pause, lambda: "play" if self.paused else "pause", tip="Play / Pausa"))
        add.append(B_((x + 2 * (B + G), y, B, B), self._request_step, "step", tip="Paso a paso (solo en pausa)", enabled=lambda: self.paused))
        add.append(B_((x + 3 * (B + G), y, B, B), self._build, "restart", tip="Reiniciar con las mismas condiciones iniciales (R)"))
        add.append(B_((x + 4 * (B + G), y, B, B), self._open_seed, "seed", tip="Semilla (solo en el mapa aleatorio)"))
        add.append(B_((x + 5 * (B + G), y, 56, B), lambda: setattr(self, "speed_i", (self.speed_i + 1) % 3),
                      label=lambda: f"x{self.speeds[self.speed_i]}", tip="Velocidad"))
        x2 = x + 5 * (B + G) + 56 + G
        add.append(B_((x2, y, 270, B), self._next_scenario, label=lambda: "Escenario: " + self._scen_name(),
                      tip="Siguiente escenario (E). Todos usan semilla fija para repetirse igual."))
        add.append(B_((x2 + 276, y, 400, B), self._next_comp, label=lambda: "Comparar: " + COMPARISONS[self.comp_i]["name"],
                      tip="Siguiente comparacion (Tab)"))
        total = x2 + 276 + 400 + 8
        for i, (tid, lab, ic, tip) in enumerate(TOOLS):
            add.append(B_((x + i * 112, y + B + G, 106, 34), lambda t=tid: setattr(self, "tool", t), ic, lab, tip=tip,
                          active=lambda t=tid: self.tool == t))
        add.append(B_((x + len(TOOLS) * 112, y + B + G, 130, 34), self._swarm, "swarm", "Enjambre",
                      tip="Enjambre de marabuntas en A y B"))
        self._bar = pygame.Rect(8, 8, min(W - 16, total - 8), 2 * B + 3 * G + 20)

    def _scen_name(self):
        sid = self.scen_ids[self.scen_i]
        return get_scenario(sid).name if sid else "Aleatorio"

    def _next_scenario(self):
        self.scen_i = (self.scen_i + 1) % len(self.scen_ids)
        self._build()

    def _next_comp(self):
        self.comp_i = (self.comp_i + 1) % len(COMPARISONS)
        self._build()

    def _toggle_pause(self):
        self.paused = not self.paused

    def _request_step(self):
        if self.paused:
            self.step_request = True

    def _swarm(self):
        for sd in self.sides:
            sd.run(lambda s: s.spawn_swarm(config.SWARM_SIZE))
        self.toasts.push("Enjambre en A y B")

    def _open_seed(self):
        if self.scen_ids[self.scen_i] is not None:
            self.toasts.push("Este escenario tiene semilla fija")
            return
        self._prev_pause, self.paused = self.paused, True
        self.modal = ui.NumberModal(self.app, "Semilla del mapa", self.seed, self._seed_ok, self._close_modal)

    def _seed_ok(self, v):
        self.seed = v
        self._close_modal()
        self._build()

    def _close_modal(self):
        self.modal = None
        if self._prev_pause is not None:
            self.paused, self._prev_pause = self._prev_pause, None

    # ------------------------------------------------------------ entrada
    def handle_event(self, e):
        if self.modal:
            self.modal.handle_event(e)
            if self.modal is not None and self.modal.closed:
                self._close_modal()
            return
        if e.type == pygame.KEYDOWN:
            self._key(e.key)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for w in self.widgets:
                if w.click(e.pos):
                    return
            if not self._bar.collidepoint(e.pos) and not any(r.collidepoint(e.pos) for r in self._panels):
                self._apply(e.pos)

    def _key(self, k):
        km = {getattr(pygame, "K_" + n, None): a for a, n in config.KEYS.items()}
        act = km.get(k)
        if k == pygame.K_ESCAPE:
            self.app.scenes.pop()
        elif k == pygame.K_TAB:
            self._next_comp()
        elif k == pygame.K_e:
            self._next_scenario()
        elif act == "pause":
            self._toggle_pause()
        elif act == "step":
            self._request_step()
        elif act == "restart":
            self._build()
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

    def _cell_at(self, pos):
        """(índice del lado, celda) bajo el mouse, o None."""
        for i, r in enumerate(self.halves):
            if r.collidepoint(pos):
                cell = self.camera.screen_to_cell(pos[0] - r.x, pos[1] - r.y)
                return (i, cell) if cell else None
        return None

    def _apply(self, pos):
        hit = self._cell_at(pos)
        if not hit or self.tool == "INSPECT":
            return
        y, x = hit[1]
        acts = {"FIRE": lambda s: s.ignite(y, x), "LIGHTNING": lambda s: s.lightning(y, x),
                "RAIN": lambda s: s.rain(y, x), "DROUGHT": lambda s: s.drought(y, x),
                "MANGO": lambda s: s.place_resource(MANGO, y, x)}
        res = [sd.run(acts[self.tool]) for sd in self.sides]
        if not any(res):
            self.toasts.push("No se pudo ahi (celda invalida u ocupada)")

    # ------------------------------------------------------------ actualización
    def update(self, dt):
        T = config.TICK_SECONDS
        self.camera.update(pygame.key.get_pressed(), dt)
        self.toasts.update(dt)
        pos = pygame.mouse.get_pos()
        hit = self._cell_at(pos) if (self.modal is None and not self._bar.collidepoint(pos)) else None
        self.hover = hit
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
        for i, sd in enumerate(self.sides):
            if sd.sim.terrain_version != self._tv[i]:
                self._tv[i] = sd.sim.terrain_version
                self.rend[i][0].rebuild()
            sd.sim.events.clear()

    def _step(self):
        for sd in self.sides:
            sd.step()
        self._tps_n += 1
        now = time.perf_counter()
        if now - self._tps_t >= 1.0:
            self._tps, self._tps_n, self._tps_t = self._tps_n / (now - self._tps_t), 0, now

    # ------------------------------------------------------------ dibujo
    def draw(self, screen):
        s = min(1.0, self.acc / config.TICK_SECONDS)
        screen.fill((12, 12, 14))
        for sd, r, (mr, er) in zip(self.sides, self.halves, self.rend):
            view = screen.subsurface(r)
            mr.draw(view, self.camera, s)
            er.draw(view, self.camera, sd.sim, s)
        if len(self.sides) == 2:
            pygame.draw.line(screen, (200, 200, 210), (self.halves[1].x, 0), (self.halves[1].x, screen.get_height()), 2)
        self._panels = []
        mouse = pygame.mouse.get_pos()
        ui.draw_panel(screen, self._bar)
        for w in self.widgets:
            w.draw(screen, self.font_b, mouse)
        self._draw_labels(screen)
        self._draw_metrics(screen)
        self._draw_hover(screen)
        self.toasts.draw(screen, self.font_b, screen.get_height() - config.HELP_BAR_H - 6)
        tip = next((w.tip for w in self.widgets if w.rect.collidepoint(mouse) and w.tip), self.tip)
        ui.draw_help(screen, self.font, tip)
        if self.modal:
            self.modal.draw(screen)

    def _draw_labels(self, screen):
        y = self._bar.bottom + 8
        for i, (sd, r) in enumerate(zip(self.sides, self.halves)):
            name = ("A" if len(self.sides) == 2 and i == 0 else "B" if i == 1 else "") 
            text = f"{name}: {sd.label}" if name else sd.label
            w = self.font_b.size(text)[0] + 24
            box = pygame.Rect(r.x + 10, y, w, 30)
            ui.draw_panel(screen, box)
            ui.draw_text(screen, self.font_b, text, box.center, config.UI_ACCENT, "center")
            self._panels.append(box)

    def _draw_metrics(self, screen):
        ms = [metrics(sd.sim) for sd in self.sides]
        W, H = screen.get_size()
        n = len(ms)
        w = 250 + 130 * n
        box = pygame.Rect((W - w) // 2, H - config.HELP_BAR_H - 12 - (len(ROWS) + 1) * 17 - 14, w, (len(ROWS) + 1) * 17 + 14)
        ui.draw_panel(screen, box)
        self._panels.append(box)
        y = box.y + 8
        ui.draw_text(screen, self.font, f"{self._tps:.0f} ticks/s", (box.x + 12, y), config.UI_DIM_COLOR)
        for i, sd in enumerate(self.sides):
            ui.draw_text(screen, self.font, f"{sd.label}  {sd.ms:.2f}ms", (box.x + 250 + 130 * i, y), config.UI_ACCENT)
        y += 17
        for label, key, fmt in ROWS:
            ui.draw_text(screen, self.font, label, (box.x + 12, y), config.UI_DIM_COLOR)
            vals = []
            for m in ms:
                if key:
                    vals.append(fmt.format(m[key]))
                elif label.startswith("Fuego"):
                    vals.append(f"{m['burning']} / {m['ash']}")
                else:
                    vals.append(f"{m['stolen']:.0f}/{m['recovered']:.0f}/{m['lost']:.0f}")
            diff = n == 2 and vals[0] != vals[1]
            for i, v in enumerate(vals):
                ui.draw_text(screen, self.font, v, (box.x + 250 + 130 * i, y), inspector.WARN if diff else config.UI_TEXT_COLOR)
            y += 17

    def _draw_hover(self, screen):
        if not self.hover:
            return
        i, cell = self.hover
        sim = self.sides[i].sim
        ag = sim.agent_at(*cell)
        lines = inspector.agent_lines(ag) if ag else inspector.ground_lines(sim, *cell)
        W = screen.get_width()
        self._panels.append(ui.draw_lines(screen, self.font, (W - 268, self._bar.bottom + 8), 260, lines))