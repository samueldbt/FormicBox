"""Clase base de las escenas y gestor de la pila de escenas."""


class Scene:
    """Una pantalla del juego. El gestor llama, en cada frame y SOLO a la de arriba:
    handle_event(e) por cada evento, update(dt) y draw(surface)."""

    def __init__(self):
        self.manager = None     # lo asigna SceneManager al apilarla

    @property
    def app(self):
        return self.manager.app

    def on_enter(self):
        """Al apilarse por primera vez."""

    def on_resume(self):
        """Al volver a quedar arriba porque se quitó la escena que la tapaba."""

    def on_exit(self):
        """Al salir de la pila."""

    def handle_event(self, event):
        pass

    def update(self, dt):
        pass

    def draw(self, surface):
        pass


class SceneManager:
    """Pila de escenas. La de abajo del todo es el título."""

    def __init__(self, app=None):
        self.app = app
        self.stack = []

    @property
    def current(self):
        return self.stack[-1] if self.stack else None

    @property
    def empty(self):
        return not self.stack

    def push(self, scene):
        scene.manager = self
        self.stack.append(scene)
        scene.on_enter()

    def pop(self):
        """Vuelve a la escena anterior. Si se quita la última, la pila queda vacía (el juego termina)."""
        if not self.stack:
            return None
        scene = self.stack.pop()
        scene.on_exit()
        if self.stack:
            self.stack[-1].on_resume()
        return scene

    def replace(self, scene):
        """Cambia la escena de arriba por otra."""
        if self.stack:
            self.stack.pop().on_exit()
        self.push(scene)

    def pop_to(self, scene_type):
        """Quita escenas hasta que la de arriba sea de `scene_type`. Si no hay ninguna, no hace nada."""
        if not any(isinstance(s, scene_type) for s in self.stack):
            return False
        while not isinstance(self.stack[-1], scene_type):
            self.stack.pop().on_exit()
        self.stack[-1].on_resume()
        return True

    def to_title(self):
        """Vuelve a la primera escena (el título)."""
        while len(self.stack) > 1:
            self.stack.pop().on_exit()
        if self.stack:
            self.stack[-1].on_resume()

    def clear(self):
        while self.stack:
            self.stack.pop().on_exit()

    # --- reenvío a la escena de arriba ---
    def handle_event(self, event):
        if self.current:
            self.current.handle_event(event)

    def update(self, dt):
        if self.current:
            self.current.update(dt)

    def draw(self, surface):
        if self.current:
            self.current.draw(surface)
