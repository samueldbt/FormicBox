"""Pila de escenas: la de arriba recibe eventos, se actualiza y se dibuja."""


class Scene:
    def on_enter(self): pass
    def on_exit(self): pass
    def on_resize(self): pass
    def handle_event(self, e): pass
    def update(self, dt): pass
    def draw(self, screen): pass


class SceneStack:
    def __init__(self):
        self.stack = []

    @property
    def top(self):
        return self.stack[-1] if self.stack else None

    def push(self, scene):
        self.stack.append(scene)
        scene.on_enter()

    def pop(self):
        if self.stack:
            self.stack.pop().on_exit()

    def replace(self, scene):
        self.pop()
        self.push(scene)