#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ====== MUY IMPORTANTE: antes de importar Kivy ======
import os
os.environ["KIVY_NO_FILELOG"] = "1"

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
import subprocess
import threading

# ========= CONFIG =========
ICON_DIR     = "/home/pi/Desktop/In"
BG_PATH      = f"{ICON_DIR}/Fondo.png"

ICON_START   = f"{ICON_DIR}/PL.png"   # play
ICON_STOP    = f"{ICON_DIR}/P.png"    # stop
ICON_RESET   = f"{ICON_DIR}/R.png"    # reset

STATUS_WHITE = f"{ICON_DIR}/status_white.png"
STATUS_GREEN = f"{ICON_DIR}/status_green.png"
STATUS_RED   = f"{ICON_DIR}/status_red.png"

LAUNCHER_PATH = "/home/pi/Desktop/Finale_Alva/launcher.sh"

JETSON_LAMP_SIZE = (18, 18)
JETSON_LAMP_POS  = {"center_x": 0.5, "top": 0.97}
LAMP_REFRESH_SEC = 3.0

SERVICE_NAME = "finale.service"

# ========= helpers =========
def _popen(cmdline: str):
    # CLAVE: Aísla a la GUI del launcher creando NUEVA SESIÓN/PGID
    return subprocess.Popen(
        ["/bin/bash", "-lc", cmdline],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

def run_launcher(cmd: str):
    try:
        if cmd == "start":
            _popen("/usr/local/bin/finale-start")
            _popen(f'"{LAUNCHER_PATH}" start')

        elif cmd == "stop":
            _popen(f'"{LAUNCHER_PATH}" stop')
            _popen("/usr/local/bin/finale-stop")

        elif cmd == "reset":
            _popen(
                '/usr/local/bin/finale-stop || true; '
                'sleep 1; '
                f'"{LAUNCHER_PATH}" reset; '
                'sleep 1; '
                '/usr/local/bin/finale-start'
            )
        else:
            _popen(f'"{LAUNCHER_PATH}" {cmd}')
        print(f"[INFO] Lanzado: {cmd}")
    except Exception as e:
        print(f"[ERROR] No se pudo ejecutar acción ({cmd}): {e}")

def _jetson_connected() -> bool:
    try:
        r = subprocess.run(
            ["/bin/bash", "-lc", "timeout 3s /usr/local/bin/run_jetson 'echo ok'"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True
        )
        return r.returncode == 0
    except Exception:
        return False

def _service_running() -> bool:
    try:
        r = subprocess.run(
            ["/bin/bash", "-lc", f"timeout 3s /usr/local/bin/run_jetson 'sudo -n systemctl is-active --quiet {SERVICE_NAME}'"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True
        )
        return r.returncode == 0
    except Exception:
        return False

# ===================== WIDGETS =====================
class IconButton(ButtonBehavior, Image):
    pass

class TitleBadge(FloatLayout):
    def __init__(self, text, bg_rgba=(0.12, 0.35, 0.85, 1), fg_rgba=(1,1,1,1),
                 padding=(14, 8), radius=14, font_size=18, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self._pad_x, self._pad_y = padding

        self.label = Label(
            text=f"[b]{text}[/b]",
            markup=True,
            color=fg_rgba,
            size_hint=(None, None),
            font_size=font_size
        )
        self.add_widget(self.label)

        with self.canvas.before:
            self._c = Color(*bg_rgba)
            self._bg = RoundedRectangle(radius=[(radius, radius)]*4, pos=self.pos, size=self.size) if HAS_ROUNDED \
                       else Rectangle(pos=self.pos, size=self.size)

        self.label.bind(texture_size=self._sync_size)
        self.bind(pos=self._sync_bg, size=self._sync_bg)

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

# ========= BASE PANEL =========
class BaseWorkPanel(FloatLayout):
    def __init__(self, status_pos=("center_x", 0.5, "top", 0.90), **kwargs):
        super().__init__(**kwargs)

        try:
            with self.canvas.before:
                self.bg = Rectangle(source=BG_PATH, pos=self.pos, size=self.size)
            self.bind(pos=self._sync_bg, size=self._sync_bg)
        except Exception:
            print(f"[WARN] Fondo no encontrado: {BG_PATH}")

        STATUS_SIZE = (46, 46)
        pos_hint = {status_pos[0]: status_pos[1], status_pos[2]: status_pos[3]}
        indicators_box = BoxLayout(orientation="horizontal", spacing=10,
                                   size_hint=(None, None), size=(STATUS_SIZE[0]*3 + 20, STATUS_SIZE[1]),
                                   pos_hint=pos_hint)
        self.status_imgs = []
        for _ in range(3):
            img = Image(source=STATUS_WHITE, size_hint=(None, None), size=STATUS_SIZE)
            self.status_imgs.append(img)
            indicators_box.add_widget(img)
        self.add_widget(indicators_box)

        self.jetson_lamp = Image(source=STATUS_WHITE,
                                 size_hint=(None, None), size=JETSON_LAMP_SIZE,
                                 pos_hint=JETSON_LAMP_POS)
        self.add_widget(self.jetson_lamp)

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

        self._status_check_inflight = False
        Clock.schedule_interval(self._schedule_status_check, LAMP_REFRESH_SEC)
        Clock.schedule_once(lambda dt: self._schedule_status_check(dt), 0.5)

    def _sync_bg(self, *args):
        if hasattr(self, 'bg'):
            self.bg.pos = self.pos
            self.bg.size = self.size

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

    def _set_status(self, which: str):
        mapping = {"white": STATUS_WHITE, "green": STATUS_GREEN, "red": STATUS_RED}
        path = mapping.get(which, STATUS_WHITE)
        for img in self.status_imgs:
            img.source = path
            img.reload()

    def _schedule_status_check(self, *_):
        if self._status_check_inflight:
            return
        self._status_check_inflight = True

        def worker():
            try:
                if not _jetson_connected():
                    state = "red"
                else:
                    state = "green" if _service_running() else "white"
            except Exception:
                state = "red"
            finally:
                def apply(_dt):
                    src = STATUS_RED if state == "red" else (STATUS_GREEN if state == "green" else STATUS_WHITE)
                    self.jetson_lamp.source = src
                    self.jetson_lamp.reload()
                    self._status_check_inflight = False
                Clock.schedule_once(apply, 0)

        threading.Thread(target=worker, daemon=True).start()

    def on_start(self, *_):
        self._start_timer()
        self._set_status("green")
        self._schedule_status_check()

    def on_stop(self, *_):
        self._stop_timer()
        self._set_status("red")
        self._schedule_status_check()

    def on_reset(self, *_):
        self._reset_timer()
        self._set_status("white")
        self._schedule_status_check()

# ======================================= SCREEN 2 (USER) =======================================
class Panel_Interfaz(BaseWorkPanel):
    def __init__(self, **kwargs):
        super().__init__(status_pos=("center_x", 0.5, "top", 0.90), **kwargs)

        title = TitleBadge(
            text="User Experience",
            bg_rgba=(0.12, 0.35, 0.85, 1),
            fg_rgba=(1, 1, 1, 1),
            pos_hint={"right": 0.98, "top": 0.98}
        )
        self.add_widget(title)

        BUTTONS_Y = 0.35
        botones = BoxLayout(orientation='horizontal', spacing=12,
                            size_hint=(None, None), size=(360, 110),
                            pos_hint={"center_x": 0.5, "y": BUTTONS_Y})

        btn_stop  = IconButton(source=ICON_STOP,  size_hint=(None, None), size=(110, 110))
        btn_start = IconButton(source=ICON_START, size_hint=(None, None), size=(110, 110))
        btn_reset = IconButton(source=ICON_RESET, size_hint=(None, None), size=(110, 110))

        btn_stop.bind(on_press=self._stop_all)
        btn_start.bind(on_press=self._start_all)
        btn_reset.bind(on_press=self._reset_all)

        botones.add_widget(btn_stop)
        botones.add_widget(btn_start)
        botones.add_widget(btn_reset)
        self.add_widget(botones)

    def _start_all(self, *_):
        super().on_start(*_)
        run_launcher("start")
        Clock.schedule_once(lambda dt: self._schedule_status_check(), 0.5)

    def _stop_all(self, *_):
        super().on_stop(*_)
        run_launcher("stop")
        Clock.schedule_once(lambda dt: self._schedule_status_check(), 0.5)

    def _reset_all(self, *_):
        super().on_reset(*_)
        run_launcher("reset")
        Clock.schedule_once(lambda dt: self._schedule_status_check(), 1.0)

# ===================================== SCREEN 3 (BENCHMARK) ====================================
class Panel_Whats_Bench(BaseWorkPanel):
    def __init__(self, **kwargs):
        super().__init__(status_pos=("center_x", 0.5, "top", 0.90), **kwargs)

        title = TitleBadge(
            text="Benchmark",
            bg_rgba=(0.20, 0.70, 0.45, 1),
            fg_rgba=(1, 1, 1, 1),
            pos_hint={"right": 0.98, "top": 0.98}
        )
        self.add_widget(title)

        BUTTONS_Y = 0.35
        botones = BoxLayout(orientation='horizontal', spacing=12,
                            size_hint=(None, None), size=(360, 110),
                            pos_hint={"center_x": 0.5, "y": BUTTONS_Y})

        btn_stop  = IconButton(source=ICON_STOP,  size_hint=(None, None), size=(110, 110))
        btn_start = IconButton(source=ICON_START, size_hint=(None, None), size=(110, 110))
        btn_reset = IconButton(source=ICON_RESET, size_hint=(None, None), size=(110, 110))

        btn_stop.bind(on_press=self._stop_all)
        btn_start.bind(on_press=self._start_all)
        btn_reset.bind(on_press=self._reset_all)

        botones.add_widget(btn_stop)
        botones.add_widget(btn_start)
        botones.add_widget(btn_reset)
        self.add_widget(botones)

    def _start_all(self, *_):
        super().on_start(*_)
        run_launcher("start")
        Clock.schedule_once(lambda dt: self._schedule_status_check(), 0.5)

    def _stop_all(self, *_):
        super().on_stop(*_)
        run_launcher("stop")
        Clock.schedule_once(lambda dt: self._schedule_status_check(), 0.5)

    def _reset_all(self, *_):
        super().on_reset(*_)
        run_launcher("reset")
        Clock.schedule_once(lambda dt: self._schedule_status_check(), 1.0)

# ---------------- PANTALLAS ----------------
class PrinterPanel(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        try:
            with self.canvas.before:
                self.bg = Rectangle(source=BG_PATH, pos=self.pos, size=self.size)
            self.bind(pos=self._update_bg, size=self._update_bg)
        except Exception:
            print(f"[WARN] Fondo no encontrado: {BG_PATH}")

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
            _popen(f'"{LAUNCHER_PATH}" stop; timeout 3s /usr/local/bin/finale-stop || true')
        except Exception as e:
            print("[WARN] No se pudo detener ordenadamente:", e)

        try:
            _popen("timeout 3s /usr/local/bin/jetson-poweroff || true")
        except Exception as e:
            print("[WARN] No se pudo enviar poweroff a Jetson:", e)

        try:
            _popen("sleep 1; sudo systemctl poweroff || sudo shutdown -h now")
        except Exception as e:
            print("[WARN] No se pudo apagar la Pi:", e)

    def _on_reboot(self, *_):
        try:
            _popen(f'"{LAUNCHER_PATH}" stop; timeout 3s /usr/local/bin/finale-stop || true')
        except Exception as e:
            print("[WARN] No se pudo detener ordenadamente:", e)

        try:
            _popen("timeout 3s /usr/local/bin/jetson-reboot || true")
        except Exception as e:
            print("[WARN] No se pudo enviar reboot a Jetson:", e)

        try:
            _popen("sleep 1; sudo systemctl reboot || sudo reboot")
        except Exception as e:
            print("[WARN] No se pudo reiniciar la Pi:", e)

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
        back_btn = Button(
            text="Home",
            size_hint=(None, None), size=(90, 42),
            pos_hint={"x": 0.02, "top": 0.98},
            background_normal='',
            background_color=(0.85, 0.20, 0.20, 1),
            color=(1, 1, 1, 1)
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
        back_btn = Button(
            text="Home",
            size_hint=(None, None), size=(90, 42),
            pos_hint={"x": 0.02, "top": 0.98},
            background_normal='',
            background_color=(0.85, 0.20, 0.20, 1),
            color=(1, 1, 1, 1)
        )
        back_btn.bind(on_press=lambda *_: self._go_to("home"))
        layout.add_widget(back_btn)

    def _go_to(self, name):
        if self.manager:
            self.manager.current = name

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
