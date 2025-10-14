# -*- coding: utf-8 -*-
from kivy.config import Config
Config.set('graphics', 'fullscreen', '1')
Config.set('graphics', 'borderless', '1')
Config.set('graphics', 'width', '720')
Config.set('graphics', 'height', '480')

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.behaviors import ButtonBehavior
from kivy.graphics import Rectangle, Color
try:
    from kivy.graphics import RoundedRectangle
    HAS_ROUNDED = True
except Exception:
    HAS_ROUNDED = False

from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
import os
import subprocess

# ========= CONFIG =========
ICON_DIR    = "/home/pi/Desktop/In"
BG_PATH     = os.path.join(ICON_DIR, "Fondo.png")

ICON_START  = os.path.join(ICON_DIR, "PL.png")   # play
ICON_STOP   = os.path.join(ICON_DIR, "P.png")    # stop
ICON_RESET  = os.path.join(ICON_DIR, "R.png")    # reset

STATUS_WHITE = os.path.join(ICON_DIR, "status_white.png")
STATUS_GREEN = os.path.join(ICON_DIR, "status_green.png")
STATUS_RED   = os.path.join(ICON_DIR, "status_red.png")

# ===================== WIDGETS =====================
class IconButton(ButtonBehavior, Image):
    pass

class TitleBadge(FloatLayout):
    """Etiqueta tipo 'chip' con fondo y esquinas (opcional)."""
    def __init__(self, text, bg_rgba=(0.12, 0.35, 0.85, 1), fg_rgba=(1,1,1,1),
                 padding=(14, 8), radius=14, font_size=18, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self._pad_x, self._pad_y = padding

        self.label = Label(
            text=f"[b]{text}[/b]",
            markup=True,
            color=fg_rgba,           # << texto negro/lo que pases
            size_hint=(None, None),
            font_size=font_size
        )
        self.add_widget(self.label)

        with self.canvas.before:
            self._c = Color(*bg_rgba)
            self._bg = RoundedRectangle(radius=[(radius, radius)]*4, pos=self.pos, size=self.size) if HAS_ROUNDED \
                       else Rectangle(pos=self.pos, size=self.size)

        # Ajustar tamaño al texto y mantener centrado dentro del chip
        self.label.bind(texture_size=self._sync_size)
        self.bind(pos=self._sync_bg, size=self._sync_bg)

        # Primer cálculo
        self.label.texture_update()
        self._sync_size()

    def _sync_size(self, *args):
        w, h = self.label.texture_size
        self.size = (w + 2*self._pad_x, h + 2*self._pad_y)
        self.label.pos = (self.x + self._pad_x, self.y + self._pad_y)

    def _sync_bg(self, *args):
        self._bg.pos = self.pos
        self._bg.size = self.size
        self.label.pos = (self.x + self._pad_x, self.y + self._pad_y)

# ============================================ HOME =================================
class PrinterPanel(FloatLayout):
    """Pantalla Home: dos botones centrados (un poco más arriba) y botones de sistema."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Fondo
        if os.path.exists(BG_PATH):
            with self.canvas.before:
                self.bg = Rectangle(source=BG_PATH, pos=self.pos, size=self.size)
            self.bind(pos=self._update_bg, size=self._update_bg)
        else:
            print(f"[WARN] Fondo no encontrado: {BG_PATH}")

        # Botonera (subida un poco)
        self.botones = BoxLayout(
            orientation='vertical',
            spacing=16,
            size_hint=(None, None),
            width=360,
            height=2 * 60 + 16,
            pos_hint={"center_x": 0.5, "center_y": 0.58}
        )

        self.btn_P1 = Button(
            text="Modo: User Experience",
            font_size=18,
            size_hint=(None, None), size=(360, 60),
            background_normal='',
            background_color=(0.12, 0.35, 0.85, 1),
            color=(1, 1, 1, 1)
        )
        self.btn_P2 = Button(
            text="Modo: Benchmark",
            font_size=18,
            size_hint=(None, None), size=(360, 60),
            background_normal='',
            background_color=(0.20, 0.70, 0.45, 1),
            color=(1, 1, 1, 1)
        )

        self.botones.add_widget(self.btn_P1)
        self.botones.add_widget(self.btn_P2)
        self.add_widget(self.botones)

        # Botones de sistema (esquina inf. derecha)
        sys_box = BoxLayout(
            orientation='horizontal',
            spacing=10,
            size_hint=(None, None),
            size=(220, 44),
            pos_hint={"right": 0.98, "y": 0.02}
        )
        self.btn_shutdown = Button(
            text="Apagar",
            font_size=16, size_hint=(None, None), size=(100, 44),
            background_normal='', background_color=(0.85, 0.20, 0.20, 1),
            color=(1, 1, 1, 1)
        )
        self.btn_reboot = Button(
            text="Reiniciar",
            font_size=16, size_hint=(None, None), size=(110, 44),
            background_normal='', background_color=(0.95, 0.80, 0.20, 1),
            color=(0.15, 0.15, 0.15, 1)
        )
        self.btn_shutdown.bind(on_press=self._on_shutdown)
        self.btn_reboot.bind(on_press=self._on_reboot)
        sys_box.add_widget(self.btn_shutdown)
        sys_box.add_widget(self.btn_reboot)
        self.add_widget(sys_box)

    def _update_bg(self, *args):
        if hasattr(self, 'bg'):
            self.bg.pos = self.pos
            self.bg.size = self.size

    def _on_shutdown(self, *_):
        try:
            subprocess.Popen(["/bin/bash", "-lc", "sudo shutdown -h now"])
        except Exception as e:
            print("[WARN] No se pudo apagar:", e)

    def _on_reboot(self, *_):
        try:
            subprocess.Popen(["/bin/bash", "-lc", "sudo reboot"])
        except Exception as e:
            print("[WARN] No se pudo reiniciar:", e)

# ========= BASE PANEL (3 indicadores + timer, sin overlays) =========
class BaseWorkPanel(FloatLayout):
    def __init__(self, status_pos=("center_x", 0.5, "top", 0.90), **kwargs):
        super().__init__(**kwargs)

        # Fondo
        if os.path.exists(BG_PATH):
            with self.canvas.before:
                self.bg = Rectangle(source=BG_PATH, pos=self.pos, size=self.size)
            self.bind(pos=self._sync_bg, size=self._sync_bg)
        else:
            print(f"[WARN] Fondo no encontrado: {BG_PATH}")

        # 3 indicadores alineados (centrados arriba)
        STATUS_SIZE = (46, 46)
        pos_hint = {status_pos[0]: status_pos[1], status_pos[2]: status_pos[3]}
        indicators_box = BoxLayout(orientation="horizontal", spacing=10,
                                   size_hint=(None, None), size=(STATUS_SIZE[0]*3 + 20, STATUS_SIZE[1]),
                                   pos_hint=pos_hint)
        self.status_imgs = []
        for _ in range(3):
            img = Image(source=STATUS_WHITE if os.path.exists(STATUS_WHITE) else "",
                        size_hint=(None, None), size=STATUS_SIZE)
            self.status_imgs.append(img)
            indicators_box.add_widget(img)
        self.add_widget(indicators_box)

        # Timer (negro y bold)
        self.seconds = 0
        self.timer_event = None
        self.timer_label = Label(
            text="[b]Tiempo: 00:00:00[/b]",
            markup=True,
            font_size=16,
            size_hint=(None, None), size=(240, 34),
            pos_hint={"center_x": 0.5, "y": 0.09},
            color=(0, 0, 0, 1)
        )
        self.add_widget(self.timer_label)

    def _sync_bg(self, *args):
        if hasattr(self, 'bg'):
            self.bg.pos = self.pos
            self.bg.size = self.size

    # timer
    def _start_timer(self):
        if not self.timer_event:
            self.timer_event = Clock.schedule_interval(self._tick, 1)

    def _stop_timer(self):
        if self.timer_event:
            self.timer_event.cancel()
            self.timer_event = None

    def _reset_timer(self):
        self.seconds = 0
        self.timer_label.text = "[b]Tiempo: 00:00:00[/b]"

    def _tick(self, dt):
        self.seconds += 1
        hrs = self.seconds // 3600
        mins = (self.seconds % 3600) // 60
        secs = self.seconds % 60
        self.timer_label.text = f"[b]Tiempo: {hrs:02}:{mins:02}:{secs:02}[/b]"

    # indicadores (los 3 cambian a la vez)
    def _set_status(self, which: str):
        mapping = {"white": STATUS_WHITE, "green": STATUS_GREEN, "red": STATUS_RED}
        path = mapping.get(which, STATUS_WHITE)
        if os.path.exists(path):
            for img in self.status_imgs:
                img.source = path
                img.reload()

    # callbacks
    def on_start(self, *_):
        self._start_timer()
        self._set_status("green")

    def on_stop(self, *_):
        self._stop_timer()
        self._set_status("red")

    def on_reset(self, *_):
        self._reset_timer()
        self._set_status("white")

# ======================================= SCREEN 2 (USER) =======================================
class Panel_Interfaz(BaseWorkPanel):
    def __init__(self, **kwargs):
        super().__init__(status_pos=("center_x", 0.5, "top", 0.90), **kwargs)

        # Título (azul) en esquina superior derecha
        title = TitleBadge(
            text="User Experience",
            bg_rgba=(0.12, 0.35, 0.85, 1),   # azul (igual que antes)
            fg_rgba=(0, 0, 0, 1),            # <-- TEXTO NEGRO
            pos_hint={"right": 0.98, "top": 0.98}
        )
        self.add_widget(title)

        # Botones principales
        BUTTONS_Y = 0.35
        botones = BoxLayout(orientation='horizontal', spacing=12,
                            size_hint=(None, None), size=(360, 110),
                            pos_hint={"center_x": 0.5, "y": BUTTONS_Y})

        btn_stop  = IconButton(source=ICON_STOP  if os.path.exists(ICON_STOP)  else "",
                               size_hint=(None, None), size=(110, 110))
        btn_start = IconButton(source=ICON_START if os.path.exists(ICON_START) else "",
                               size_hint=(None, None), size=(110, 110))
        btn_reset = IconButton(source=ICON_RESET if os.path.exists(ICON_RESET) else "",
                               size_hint=(None, None), size=(110, 110))

        btn_stop.bind(on_press=self.on_stop)
        btn_start.bind(on_press=self.on_start)
        btn_reset.bind(on_press=self.on_reset)

        botones.add_widget(btn_stop)
        botones.add_widget(btn_start)
        botones.add_widget(btn_reset)
        self.add_widget(botones)

# ===================================== SCREEN 3 (BENCHMARK) ====================================
class Panel_Whats_Bench(BaseWorkPanel):
    def __init__(self, **kwargs):
        super().__init__(status_pos=("center_x", 0.5, "top", 0.90), **kwargs)

        # Título (rojo) en esquina superior derecha
        title = TitleBadge(
            text="Benchmark",
            bg_rgba=(0.20, 0.70, 0.45, 1),   # <-- VERDE (igual al botón de Home que va a esta pantalla)
            fg_rgba=(0, 0, 0, 1),            # <-- TEXTO NEGRO
            pos_hint={"right": 0.98, "top": 0.98}
        )
        self.add_widget(title)

        # Botones principales
        BUTTONS_Y = 0.35
        botones = BoxLayout(orientation='horizontal', spacing=12,
                            size_hint=(None, None), size=(360, 110),
                            pos_hint={"center_x": 0.5, "y": BUTTONS_Y})

        btn_stop  = IconButton(source=ICON_STOP  if os.path.exists(ICON_STOP)  else "",
                               size_hint=(None, None), size=(110, 110))
        btn_start = IconButton(source=ICON_START if os.path.exists(ICON_START) else "",
                               size_hint=(None, None), size=(110, 110))
        btn_reset = IconButton(source=ICON_RESET if os.path.exists(ICON_RESET) else "",
                               size_hint=(None, None), size=(110, 110))

        btn_stop.bind(on_press=self.on_stop)
        btn_start.bind(on_press=self.on_start)
        btn_reset.bind(on_press=self.on_reset)

        botones.add_widget(btn_stop)
        botones.add_widget(btn_start)
        botones.add_widget(btn_reset)
        self.add_widget(botones)

# ---------------- PANTALLAS ----------------
class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = PrinterPanel()
        self.add_widget(root)
        root.btn_P1.bind(on_press=lambda *_: self._go_to("second"))
        root.btn_P2.bind(on_press=lambda *_: self._go_to("terd"))

    def _go_to(self, name):
        if self.manager:
            self.manager.current = name

class SecondScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = Panel_Interfaz()
        self.add_widget(layout)
        # Home arriba izquierda
        back_btn = Button(
            text="Home",
            size_hint=(None, None), size=(90, 42),
            pos_hint={"x": 0.02, "top": 0.98},
            background_normal='',
            background_color=(0.85, 0.20, 0.20, 1),  # << ROJO
            color=(1, 1, 1, 1)                       # texto blanco
        )
        back_btn.bind(on_press=lambda *_: self._go_to("home"))
        layout.add_widget(back_btn)

    def _go_to(self, name):
        if self.manager:
            self.manager.current = name

class TerdScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = Panel_Whats_Bench()
        self.add_widget(layout)
        # Home arriba izquierda
        back_btn = Button(
            text="Home",
            size_hint=(None, None), size=(90, 42),
            pos_hint={"x": 0.02, "top": 0.98},
            background_normal='',
            background_color=(0.85, 0.20, 0.20, 1),  # << ROJO
            color=(1, 1, 1, 1)                       # texto blanco
        )
        back_btn.bind(on_press=lambda *_: self._go_to("home"))
        layout.add_widget(back_btn)

    def _go_to(self, name):
        if self.manager:
            self.manager.current = name

# ---------------- APP ----------------
class PrinterApp(App):
    def build(self):
        sm = ScreenManager(transition=FadeTransition(duration=0.25))
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(SecondScreen(name="second"))
        sm.add_widget(TerdScreen(name="terd"))
        sm.current = "home"
        return sm

if __name__ == '__main__':
    PrinterApp().run()
