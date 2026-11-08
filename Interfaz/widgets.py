import pygame


class Button:
    def __init__(self, rect, label, on_click, is_on=None):
        """label: str o función que devuelve str. is_on: función que devuelve bool (resalta el botón)."""
        self.rect = pygame.Rect(rect)
        self.label = label
        self.on_click = on_click
        self.is_on = is_on

    def draw(self, surf, font):
        on = self.is_on() if self.is_on else False
        pygame.draw.rect(surf, (50, 115, 60) if on else (55, 55, 62), self.rect, border_radius=4)
        pygame.draw.rect(surf, (110, 110, 120), self.rect, 1, border_radius=4)
        text = self.label() if callable(self.label) else self.label
        img = font.render(text, True, (235, 235, 235))
        surf.blit(img, img.get_rect(center=self.rect.center))

    def click(self, pos):
        if self.rect.collidepoint(pos):
            self.on_click()
            return True
        return False