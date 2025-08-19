from kivy.config import Config
Config.set('graphics', 'fullscreen', '1')
Config.set('graphics', 'borderless', '1')
Config.set('graphics', 'width', '720')
Config.set('graphics', 'height', '480')

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.graphics import Rectangle, Color, Ellipse
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.image import Image
import subprocess
import os
import signal

class ImageButton(ButtonBehavior, Image):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

class StatusIndicator(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas:
            self.color_instruction = Color(1, 1, 1, 1)
            self.circle = Ellipse(pos=self.pos, size=self.size)
        self.bind(pos=self.update_shape, size=self.update_shape)

    def update_shape(self, *args):
        self.circle.pos = self.pos
        self.circle.size = self.size

    def set_color(self, rgba):
        self.color_instruction.rgba = rgba

class PrinterPanel(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.process = None
        self.apps = [
            {"name": "WhatsApp", "icon": "/home/pi/Desktop/In/icon_whatsapp.png"},
            {"name": "Facebook", "icon": "/home/pi/Desktop/In/icon_facebook.png"},
            {"name": "Instagram", "icon": "/home/pi/Desktop/In/icon_instagram.png"}
        ]

        with self.canvas.before:
            self.bg = Rectangle(source="/home/pi/Desktop/In/Fondo.png", pos=self.pos, size=self.size)
        self.bind(pos=self.update_bg, size=self.update_bg)

        self.cell_app_indices = [0, 1, 2]
        self.cell_buttons = []
        self.labels = []
        self.indicators = []

        positions = [{"x": 0.05}, {"center_x": 0.5}, {"right": 0.95}]
        for i in range(3):
            container = BoxLayout(orientation='vertical', size_hint=(0.28, 0.45), pos_hint={**positions[i], "top": 0.95}, spacing=5)
            app = self.apps[self.cell_app_indices[i]]
            btn = ImageButton(source=app["icon"], size_hint=(1, 0.75), on_press=self.make_switch_callback(i))
            label = Label(text=app["name"], font_size=16, size_hint=(1, 0.1), color=(0, 0, 0, 1))
            indicator = StatusIndicator(size_hint=(None, None), size=(20, 20))
            indicator.pos_hint = {"center_x": 0.5}
            self.cell_buttons.append(btn)
            self.labels.append(label)
            self.indicators.append(indicator)
            container.add_widget(btn)
            container.add_widget(label)
            container.add_widget(indicator)
            self.add_widget(container)

        self.timer_label = Label(
            text="Tiempo: 00:00:00",
            font_size=16,
            size_hint=(None, None),
            size=(200, 30),
            pos_hint={"center_x": 0.5, "y": 0.09},
            color=(0, 0, 0, 1)
        )
        self.add_widget(self.timer_label)
        self.seconds = 0
        self.timer_event = None

        botones_layout = BoxLayout(
            orientation='horizontal',
            spacing=10,
            size_hint=(None, None),
            size=(300, 90),
            pos_hint={"center_x": 0.5, "y": 0.18}
        )

        btn_pausar = ImageButton(source="/home/pi/Desktop/In/P.png", size_hint=(None, None), size=(90, 90), on_press=self.pausar)
        btn_iniciar = ImageButton(source="/home/pi/Desktop/In/PL.png", size_hint=(None, None), size=(90, 90), on_press=self.iniciar)
        btn_reiniciar = ImageButton(source="/home/pi/Desktop/In/R.png", size_hint=(None, None), size=(90, 90), on_press=self.reiniciar)

        botones_layout.add_widget(btn_pausar)
        botones_layout.add_widget(btn_iniciar)
        botones_layout.add_widget(btn_reiniciar)
        self.add_widget(botones_layout)

        self.add_widget(Button(
            text="Salir",
            font_size=14,
            size=(80, 40),
            size_hint=(None, None),
            pos_hint={"right": 0.98, "y": 0.02},
            on_press=self.salir,
            background_color=(1, 0, 0, 1)
        ))

    def update_bg(self, *args):
        self.bg.pos = self.pos
        self.bg.size = self.size

    def make_switch_callback(self, idx):
        def callback(instance):
            self.cell_app_indices[idx] = (self.cell_app_indices[idx] + 1) % len(self.apps)
            app = self.apps[self.cell_app_indices[idx]]
            self.cell_buttons[idx].source = app["icon"]
            self.labels[idx].text = app["name"]
            print(f"Celular {idx+1} -> App: {app['name']}")
        return callback

    def iniciar(self, instance):
        for ind in self.indicators:
            ind.set_color((0, 1, 0, 1))  # Verde

        if not self.timer_event:
            self.timer_event = Clock.schedule_interval(self.update_timer, 1)

        pid_file = "/home/pi/union.pid"
        log_path = os.path.expanduser("~/Desktop/drivetest.log")

        if not os.path.exists(pid_file):
            print("[INFO] Primera ejecución: start_test.sh")
            with open(log_path, "w") as log_file:
                self.process = subprocess.Popen(
                    ["bash", "/home/pi/Desktop/Finale/start_test.sh"],
                    stdout=log_file,
                    stderr=subprocess.STDOUT
                )
        else:
            with open(pid_file, "r") as f:
                pid = f.read().strip()
            if not pid.isdigit() or not os.path.exists(f"/proc/{pid}"):
                print("[INFO] Reanudando: solo Union_prueba1.py")
                subprocess.Popen(["bash", "/home/pi/Desktop/Finale/run_union.sh"])
            else:
                print("[INFO] Union_prueba1.py ya está corriendo.")

    def pausar(self, instance):
        for ind in self.indicators:
            ind.set_color((1, 0, 0, 1))  # Rojo

        pid_file = "/home/pi/union_children.pid"
        if os.path.exists(pid_file):
            with open(pid_file, "r") as f:
                for line in f:
                    pid = line.strip()
                    if pid.isdigit() and os.path.exists(f"/proc/{pid}"):
                        os.kill(int(pid), signal.SIGTERM)
                        print(f"[INFO] Proceso hijo detenido (PID {pid}).")

        if self.timer_event:
            self.timer_event.cancel()
            self.timer_event = None

    def reiniciar(self, instance):
        for ind in self.indicators:
            ind.set_color((1, 1, 1, 1))  # Blanco

        if self.timer_event:
            self.timer_event.cancel()
            self.timer_event = None

        self.seconds = 0
        self.timer_label.text = "Tiempo: 00:00:00"

        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.process.wait()

        log_path = os.path.expanduser("~/Desktop/drivetest.log")
        with open(log_path, "w") as log_file:
            self.process = subprocess.Popen(
                ["bash", "/home/pi/Desktop/Finale/start_test.sh"],
                stdout=log_file,
                stderr=subprocess.STDOUT
            )

    def update_timer(self, dt):
        self.seconds += 1
        hrs = self.seconds // 3600
        mins = (self.seconds % 3600) // 60
        secs = self.seconds % 60
        self.timer_label.text = f"Tiempo: {hrs:02}:{mins:02}:{secs:02}"

    def salir(self, instance):
        if self.process and self.process.poll() is None:
            self.process.terminate()
        App.get_running_app().stop()

class PrinterApp(App):
    def build(self):
        return PrinterPanel()

if __name__ == '__main__':
    PrinterApp().run()