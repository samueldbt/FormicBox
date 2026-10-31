"""Bucle principal pygame: paso fijo con acumulador, eventos, panel y dibujo."""
import pygame
import config
from .assets import AssetManager
from .camera import Camera
from .map_renderer import MapRenderer, ViewState, LAYER_NAMES
from .entity_renderer import EntityRenderer
from .widgets import Button
from .debug_tools import DebugTools, TOOLS


class Game:
    def __init__(self, sim):
        pygame.init()
        pygame.display.set_caption("FormicBox")
        self.screen = pygame.display.set_mode((config.SCREEN_W, config.SCREEN_H), pygame.RESIZABLE)
        self.sim = sim
        self.assets = AssetManager()          # requiere la ventana ya creada (convert_alpha)
        self.view = ViewState()
        self.map_renderer = MapRenderer(self.assets, sim, self.view)
        self.entities = EntityRenderer(self.assets)
        self.tools = DebugTools(sim)
        self.camera = Camera(sim.automaton.width, sim.automaton.height)
        self.font = pygame.font.SysFont("consolas,dejavusansmono,couriernew,monospace", 14)

        self.paused = False
        self.speeds = (1, 2, 4)
        self.speed_i = 0
        self.acc = 0.0
        self.step_request = False
        self.running = True
        self._layout()
        self.camera.center_on(*sim.nest)

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
        for i in range(0, len(TOOLS), 3):
            row([(label, lambda t=tid: self.tools.select(t), lambda t=tid: self.tools.tool == t)
                 for tid, label in TOOLS[i:i + 3]])

        title("Acciones")
        row([("Enjambre", self.tools.swarm, None), ("Fuego al azar", self.tools.random_fire, None)])

        title("Viento")
        row([("<", lambda: self.tools.wind(-1, 0), None), ("^", lambda: self.tools.wind(0, -1), None),
             ("v", lambda: self.tools.wind(0, 1), None), (">", lambda: self.tools.wind(1, 0), None),
             ("0", lambda: self.tools.wind(0, 0), None)])

        title("Capas (M, G, T, 1-4)")
        row([("Feromonas", lambda: setattr(self.view, "pheromones", not self.view.pheromones), lambda: self.view.pheromones),
             ("Gradiente", lambda: setattr(self.view, "gradient", not self.view.gradient), lambda: self.view.gradient),
             ("Trafico", lambda: setattr(self.view, "traffic", not self.view.traffic), lambda: self.view.traffic)])
        row([(lab, lambda n=n: self._toggle_layer(n), lambda n=n: self.view.layers[n])
             for n, lab in zip(LAYER_NAMES, ("veg", "azu", "ala", "caz"))])
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

    # ------------------------------------------------------------ eventos
    def _events(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.running = False
            elif e.type == pygame.VIDEORESIZE:
                self.screen = pygame.display.get_surface()
                self._layout()
            elif e.type == pygame.KEYDOWN:
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

    def _key(self, k):
        if k == pygame.K_ESCAPE:
            self.running = False
        elif k == pygame.K_SPACE:
            self.toggle_pause()
        elif k == pygame.K_n:
            self.request_step()
        elif k == pygame.K_m:
            self.view.pheromones = not self.view.pheromones
        elif k == pygame.K_g:
            self.view.gradient = not self.view.gradient
        elif k == pygame.K_t:
            self.view.traffic = not self.view.traffic
        elif k == pygame.K_r:
            self.restart(False)
        elif pygame.K_1 <= k <= pygame.K_4:
            self._toggle_layer(LAYER_NAMES[k - pygame.K_1])

    # ------------------------------------------------------------ bucle
    def run(self):
        clock = pygame.time.Clock()
        T = config.TICK_SECONDS
        while self.running:
            dt = clock.tick(config.FPS) / 1000.0
            self._events()
            self.camera.update(pygame.key.get_pressed(), dt)

            if not self.paused:
                self.acc += dt * self.speeds[self.speed_i]
                n = 0
                while self.acc >= T and n < config.MAX_STEPS_PER_FRAME:
                    self.acc -= T
                    self.sim.step()
                    n += 1
                if self.acc >= T:          # el PC no da abasto: se descarta el atraso
                    self.acc = 0.0
            elif self.step_request:
                self.sim.step()
                self.acc = T * 0.999       # en pausa se ve el estado final del tick
            self.step_request = False

            self._draw(min(1.0, self.acc / T))
        pygame.quit()

    # ------------------------------------------------------------ dibujo
    def _draw(self, s):
        self.screen.fill((24, 24, 28))
        view = self.screen.subsurface(self.map_rect)
        view.fill((12, 12, 14))
        self.map_renderer.draw(view, self.camera, s)
        self.entities.draw(view, self.camera, self.sim, s)
        self._draw_panel()
        pygame.display.flip()

    def _text(self, lines, x, y, color=(220, 220, 220)):
        for line in lines:
            self.screen.blit(self.font.render(line, True, color), (x, y))
            y += 16
        return y

    def _draw_panel(self):
        pygame.draw.rect(self.screen, (32, 32, 38), self.panel_rect)
        for text, pos in self.labels:
            self.screen.blit(self.font.render(text, True, (150, 190, 255)), pos)
        for b in self.buttons:
            b.draw(self.screen, self.font)

        st = self.sim.stats()
        x, y = self.panel_rect.x + 8, self._info_y
        y = self._text([
            f"Tick {st['tick']}  {'[PAUSA]' if self.paused else ''}  seed {self.sim.seed}",
            f"Obreras {st['WORKER']}  Soldadas {st['SOLDIER']}  Marab. {st['MARABUNTA']}",
            f"En cola de salida: {st['queued']}",
            f"Pasto {st['grass']}  Mango {st['mango']}  Bocad. {st['bocadillos']}",
            f"Entregado P/M/B: {st['delivered'][0]}/{st['delivered'][1]}/{st['delivered'][2]}",
            f"Fuego {st['burning']}  Ceniza {st['ash']}",
            f"Viento ({config.WIND_X:.1f}, {config.WIND_Y:.1f})",
        ], x, y)
        y = self._text([self.tools.message], x, y + 4, (255, 220, 140))

        mx, my = pygame.mouse.get_pos()
        if self.map_rect.collidepoint(mx, my):
            cell = self.camera.screen_to_cell(mx - self.map_rect.x, my - self.map_rect.y)
            if cell:
                self._text(self.tools.inspect_lines(*cell), x, y + 8, (170, 255, 170))