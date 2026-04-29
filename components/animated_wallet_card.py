from kivy.uix.floatlayout import FloatLayout
from kivy.graphics import Color, RoundedRectangle
from kivy.animation import Animation


class AnimatedWalletCard(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        with self.canvas:
            Color(0.0, 0.78, 0.33, 1)  # Emerald Green
            self.rect = RoundedRectangle(radius=[20], size=self.size, pos=self.pos)

        self.bind(pos=self.update_rect, size=self.update_rect)
        self.start_animation()

    def update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size

    def start_animation(self):
        anim = Animation(opacity=0.8, duration=1) + Animation(opacity=1, duration=1)
        anim.repeat = True
        anim.start(self)
