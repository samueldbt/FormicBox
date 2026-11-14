"""Modo Dios (y Lucha): escena con paso fijo y acumulador, panel de herramientas y dibujo. El bucle lo maneja App."""
import pygame
import config
from .scenes import Scene
from .camera import Camera
from .map_renderer import MapRenderer, ViewState, LAYER_NAMES
from .entity_renderer import EntityRenderer
from .widgets import Button
from .debug_tools import DebugTools, TOOLS


class GodScene(Scene):
    def __init__(self, app, sim, waves=False):
        self.app = app
        self.sim = sim
        self.waves = waves                    # Lucha: una oleada de marabuntas cada LUCHA_SWARM_EVERY ticks
        self._last_wave = 0
        self.view = ViewState()
        self.map_renderer = MapRenderer(app.assets, sim, self.view)
        self.entities = EntityRenderer(app.assets)
        self.tools = DebugTools(sim)
        self.camera = Camera(sim.automaton.width, sim.automaton.height)
        self.font = app.font(14)

        self.paused = False
        self.speeds = (1, 2, 4)
        self.speed_i = 0
        self.acc = 0.0
        self.step_request = False
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

    def _build_keys(self):
        """config.KEYS (nombres de pygame sin K_) -> {código: acción}."""
        self.keymap = {}
        for action, name in config.KEYS.items():
            code = getattr(pygame, "K_" + name, None)
            if code is not None:
                self.keymap[code] = action

    # ------------------------------------------------------------ layout y panel
    def _layout(self):
        W, H = self.screen.get_size()
        self.map_rect = pygame.Rect(0, 0, max(100, W - config.PANEL_W), H)
        self.panel_rect = pygame.Rect(self.map_rect.right, 0, config.PANEL_W, H)
        self.camera.set_view(self.map_rect.w, self.map_rect.h)
        self._build_panel()

    def _build_panel(self):
        p = self.panel_rect
        x0, w = p.x + 8, p.w - 16
        self.buttons, self.labels = [], []
        self._y = 8

        def title(text):
            self.labels.append((text, (x0, self._y)))
            self._y += 18

        def row(items):
            n = len(items)
            bw = (w - (n - 1) * 4) // n
            for i, (label, cb, on) in enumerate(items):
                self.buttons.append(Button((x0 + i * (bw + 4), self._y, bw, 24), label, cb, on))
            self._y += 28

        title("Simulacion")
        row([(lambda: "Play" if self.paused else "Pausa", self.toggle_pause, None),
             ("Paso (N)", self.request_step, None),
             (lambda: f"x{self.speeds[self.speed_i]}", self.cycle_speed, None)])
        row([("Reiniciar (R)", lambda: self.restart(False), None),
             ("Semilla+1", lambda: self.restart(True), None)])

        title("Herramienta (clic en el mapa)")
        for i in range(0, len(TOOLS), 4):
            row([(label, lambda t=tid: self.tools.select(t), lambda t=tid: self.tools.tool == t)
                 for tid, label in TOOLS[i:i + 4]])

        title("Acciones")
        row([("Enjambre", self.tools.swarm, None), ("Fuego azar", self.tools.random_fire, None)])
        row([("Lluvia azar", self.tools.rain_random, None), ("Sequia azar", self.tools.drought_random, None),
             ("Clima auto", self.tools.toggle_weather_auto, lambda: config.WEATHER_AUTO)])

        title("Viento (WASD, X = calma)")
        row([("<", lambda: self.tools.wind(-1, 0), None), ("^", lambda: self.tools.wind(0, -1), None),
             ("v", lambda: self.tools.wind(0, 1), None), (">", lambda: self.tools.wind(1, 0), None),
             ("0", lambda: self.tools.wind(0, 0), None)])

        title("Capas (V B N M, Z, G, T, H)")
        row([("Feromonas", lambda: setattr(self.view, "pheromones", not self.view.pheromones), lambda: self.view.pheromones),
             ("Gradiente", lambda: setattr(self.view, "gradient", not self.view.gradient), lambda: self.view.gradient),
             ("Trafico", lambda: setattr(self.view, "traffic", not self.view.traffic), lambda: self.view.traffic)])
        row([(lab, lambda n=n: self._toggle_layer(n), lambda n=n: self.view.layers[n])
             for n, lab in zip(LAYER_NAMES, ("veg", "azu", "ala", "caz"))]
            + [("Humedad", lambda: setattr(self.view, "moisture", not self.view.moisture), lambda: self.view.moisture)])
        self._info_y = self._y + 6

    def _toggle_layer(self, name):
        self.view.layers[name] = not self.view.layers[name]

    # ------------------------------------------------------------ control
    def toggle_pause(self):
        self.paused = not self.paused

    def request_step(self):
        self.paused = True
        self.step_request = True

    def cycle_speed(self):
        self.speed_i = (self.speed_i + 1) % len(self.speeds)

    def restart(self, new_seed):
        self.sim.reset(self.sim.seed + 1 if new_seed else self.sim.seed)
        self.map_renderer.rebuild()
        self.camera.center_on(*self.sim.nest)
        self.acc = 0.0
        self._last_wave = 0

    # ------------------------------------------------------------ eventos
    def handle_event(self, e):
        if e.type == pygame.KEYDOWN:
            self._key(e.key)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.map_rect.collidepoint(e.pos):
                cell = self.camera.screen_to_cell(e.pos[0] - self.map_rect.x, e.pos[1] - self.map_rect.y)
                if cell:
                    self.tools.apply(*cell)
            else:
                for b in self.buttons:
                    if b.click(e.pos):
                        break

    def _toggle_all_layers(self):
        on = not any(self.view.layers.values())
        for n in LAYER_NAMES:
            self.view.layers[n] = on
        self.view.pheromones = True

    def _key(self, k):
        if k == pygame.K_ESCAPE:
            self.app.scenes.pop()
            return
        act = self.keymap.get(k)
        if act is None:
            return
        wind = {"wind_up": (0, -1), "wind_down": (0, 1), "wind_left": (-1, 0), "wind_right": (1, 0)}
        if act == "pause":
            self.toggle_pause()
        elif act == "step":
            self.request_step()
        elif act == "restart":
            self.restart(False)
        elif act in wind:
            self.tools.wind_add(*wind[act])
        elif act == "wind_zero":
            self.tools.wind(0, 0)
        elif act.startswith("layer_"):
            self._toggle_layer(act[6:])                       # layer_vegetal -> "vegetal"
        elif act == "layers_all":
            self._toggle_all_layers()
        elif act == "gradient":
            self.view.gradient = not self.view.gradient
        elif act == "traffic":
            self.view.traffic = not self.view.traffic
        elif act == "moisture":
            self.view.moisture = not self.view.moisture

    # ------------------------------------------------------------ actualización
    def update(self, dt):
        T = config.TICK_SECONDS
        self.camera.update(pygame.key.get_pressed(), dt)

        if not self.paused:
            self.acc += dt * self.speeds[self.speed_i]
            n = 0
            while self.acc >= T and n < config.MAX_STEPS_PER_FRAME:
                self.acc -= T
                self._step()
                n += 1
            if self.acc >= T:          # el PC no da abasto: se descarta el atraso
                self.acc = 0.0
        elif self.step_request:
            self._step()
            self.acc = T * 0.999       # en pausa se ve el estado final del tick
        self.step_request = False

        # Audio: eventos de la simulación con volumen por distancia y pista de lucha si hay marabuntas
        audio = self.app.audio
        for ev in self.sim.events:
            audio.play_event(ev, self.camera)
        self.sim.events.clear()
        audio.set_fight(any(ag.alive and ag.CASTE == "MARABUNTA" for ag in self.sim.agents))

    def _step(self):
        if self.waves and self.sim.tick - self._last_wave >= config.LUCHA_SWARM_EVERY:
            self._last_wave = self.sim.tick
            self.sim.spawn_swarm(config.SWARM_SIZE)
        self.sim.step()

    # ------------------------------------------------------------ dibujo
    def draw(self, screen):
        s = min(1.0, self.acc / config.TICK_SECONDS)
        screen.fill((24, 24, 28))
        view = screen.subsurface(self.map_rect)
        view.fill((12, 12, 14))
        self.map_renderer.draw(view, self.camera, s)
        self.entities.draw(view, self.camera, self.sim, s)
        self._draw_wind(view)
        if self.sim.game_over:
            self.paused = True
            self._draw_game_over(view)
        self._draw_panel(screen)

    def _draw_wind(self, view):
        """Indicador del viento en el borde superior del mapa: flecha hacia donde SOPLA (W = hacia arriba)."""
        wx, wy = config.WIND_X, config.WIND_Y
        cx, cy = view.get_width() // 2, 22
        pygame.draw.circle(view, (20, 20, 26), (cx, cy), 16)
        pygame.draw.circle(view, (140, 140, 150), (cx, cy), 16, 1)
        if wx == 0 and wy == 0:
            pygame.draw.circle(view, (140, 140, 150), (cx, cy), 3)
            return
        n = max(1e-6, (wx * wx + wy * wy) ** 0.5)
        ux, uy = wx / n, wy / n
        tip = (cx + ux * 12, cy + uy * 12)
        tail = (cx - ux * 10, cy - uy * 10)
        pygame.draw.line(view, (235, 235, 235), tail, tip, 2)
        for sgn in (-1, 1):
            hx = tip[0] - ux * 6 - sgn * uy * 4
            hy = tip[1] - uy * 6 + sgn * ux * 4
            pygame.draw.line(view, (235, 235, 235), tip, (hx, hy), 2)

    def _draw_game_over(self, view):
        w, h = view.get_size()
        shade = pygame.Surface((w, h), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 150))
        view.blit(shade, (0, 0))
        st = self.sim.summary()
        lines = [("FIN DE LA COLONIA", 40, (255, 200, 120)), (self.sim.game_over_reason, 20, (230, 230, 230)),
                 (f"Ticks {st['ticks']}   Nacimientos {self.sim.births}   Bajas obreras {st['deaths']['WORKER']}", 16, (200, 200, 200)),
                 ("R: reiniciar    Esc: volver al menu", 16, (170, 220, 170))]
        y = h // 2 - 60
        for text, size, col in lines:
            img = self.app.font(size).render(text, True, col)
            view.blit(img, img.get_rect(center=(w // 2, y)))
            y += size + 18

    def _text(self, screen, lines, x, y, color=(220, 220, 220)):
        for line in lines:
            screen.blit(self.font.render(line, True, color), (x, y))
            y += 16
        return y

    def _draw_panel(self, screen):
        pygame.draw.rect(screen, (32, 32, 38), self.panel_rect)
        for text, pos in self.labels:
            screen.blit(self.font.render(text, True, (150, 190, 255)), pos)
        for b in self.buttons:
            b.draw(screen, self.font)

        st = self.sim.stats()
        x, y = self.panel_rect.x + 8, self._info_y
        ph = self.sim.automaton.pheromones["vegetal"]
        y = self._text(screen, [
            f"Tick {st['tick']}  {'[PAUSA]' if self.paused else ''}  seed {self.sim.seed}"
            f"{'  LUCHA' if self.waves else ''}",
            f"Obreras {st['WORKER']}  Soldadas {st['SOLDIER']}  Marab. {st['MARABUNTA']}",
            f"En cola de salida: {st['queued']}",
            f"Salida: {'esperando a la exploradora' if self.sim.waiting_scout else 'libre'}",
            f"Pasto {st['grass']}  Mango {st['mango']}  Bocad. {st['bocadillos']}",
            f"Bolsa {st['units']:.0f} u (P/M/B {st['stock'][0]}/{st['stock'][1]}/{st['stock'][2]})",
            f"Crias {st['brood']}",
            f"Hongo: {'ESTRESADO' if st['stressed'] else 'normal'} {'| HAMBRE' if st['starving'] else ''}",
            f"Botin {st['loot']}  robado {st['stolen']:.0f}u  recup. {st['recovered']:.0f}u ",
            f"perd. {st['lost']:.0f}u",
            f"Fuego {st['burning']}  Ceniza {st['ash']}",
            f"Humedad {self.sim.automaton.terrain.moisture.mean():.2f}  lluvia {st['rain_zones']}  sequia {st['drought_zones']}"
            f"{'  AUTO' if config.WEATHER_AUTO else ''}",
            f"Viento ({config.WIND_X:.1f}, {config.WIND_Y:.1f})",
            f"Feromona veg: {ph.mode}  evap {ph.evap_rate}",
            f"Marab.: {config.MARA_SENSE} / {config.MARA_RAID_MODE}",
        ], x, y)
        y = self._text(screen, [self.tools.message], x, y + 4, (255, 220, 140))

        mx, my = pygame.mouse.get_pos()
        if self.map_rect.collidepoint(mx, my):
            cell = self.camera.screen_to_cell(mx - self.map_rect.x, my - self.map_rect.y)
            if cell:
                self._text(screen, self.tools.inspect_lines(*cell), x, y + 8, (170, 255, 170))