# -*- coding: utf-8 -*-
# B.py — Dispositivo B: contestar SOLO subiendo el botón (swipe/drag largo)

import re, time, signal
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.actions.pointer_input import PointerInput
from selenium.webdriver.common.actions.action_builder import ActionBuilder

# ================== CONFIG ==================
UDID_B = "YLEDU17215000182"                 # <-- serial B
APPIUM_URL_B = "http://127.0.0.1:4726"      # Appium B
SYSTEM_PORT_B = 8211

APP_PKG = "com.whatsapp"
APP_ACT = "com.whatsapp.HomeActivity"

ID_ACCEPT = "com.whatsapp:id/accept_incoming_call_view"      # handler real (ImageView no-clickable)
ID_HINT   = "com.whatsapp:id/accept_call_swipe_up_hint_view" # contenedor/hint
ID_CARD   = "com.whatsapp:id/call_controls_card"
ID_SUB    = "com.whatsapp:id/subtitle"
CONNECTED_RE = re.compile(r"^\d{1,2}:\d{2}$")  # 0:00, 12:34

# ================== SEÑALES ==================
detener = False
def manejar_senal(sig, frame):
    global detener
    print("\n[B] Señal recibida, saliendo...")
    detener = True
signal.signal(signal.SIGINT, manejar_senal)
signal.signal(signal.SIGTERM, manejar_senal)

# ================== DRIVER ==================
def setup_driver_b():
    caps = {
        "platformName": "Android",
        "automationName": "UiAutomator2",
        "udid": UDID_B,
        "deviceName": UDID_B,
        "noReset": True,
        "forceAppLaunch": False,          # importante en receptor
        "systemPort": SYSTEM_PORT_B,
        "ignoreHiddenApiPolicyError": True,
        "disableWindowAnimation": True,
    }
    return webdriver.Remote(APPIUM_URL_B, options=UiAutomator2Options().load_capabilities(caps))

# ================== HELPERS ==================
def device_wake(driver):
    try:
        driver.execute_script("mobile: shell", {"command":"input","args":["keyevent","224"]})  # WAKEUP
    except: pass

def screen_size(driver):
    sz = driver.get_window_size()
    return int(sz["width"]), int(sz["height"])

def top_target_y(driver, frac=0.12):
    """Y destino alto; por defecto 12% de pantalla. Baja el porcentaje si aún no engancha."""
    _, h = screen_size(driver)
    return max(60, int(h * frac))

def _get_bounds_center(el):
    """Centro y bounds desde atributo 'bounds'; fallback a rect si no está."""
    try:
        b = el.get_attribute("bounds")  # ej: [456,1463][624,1631]
        if b and b.startswith('['):
            import re as _re
            m = _re.findall(r'\[(\d+),(\d+)\]', b)
            if len(m) == 2:
                x1, y1 = map(int, m[0]); x2, y2 = map(int, m[1])
                cx, cy = (x1 + x2)//2, (y1 + y2)//2
                return (cx, cy), (x1, y1, x2, y2)
    except: pass
    r = el.rect
    x1, y1 = r["x"], r["y"]; x2, y2 = x1 + r["width"], y1 + r["height"]
    cx, cy = x1 + r["width"]//2, y1 + r["height"]//2
    return (cx, cy), (x1, y1, x2, y2)

def is_answered(driver) -> bool:
    """¿La llamada ya quedó conectada en B? (UI de controles o timer mm:ss)."""
    try:
        if driver.find_elements(AppiumBy.ID, ID_CARD):
            return True
    except: pass
    try:
        subs = driver.find_elements(AppiumBy.ID, ID_SUB)
        if subs:
            txt = (subs[0].text or "").strip()
            if CONNECTED_RE.match(txt):
                return True
    except: pass
    return False

# ======== GESTOS (3 vías) ========
def try_swipeGesture(driver, el, percent=0.98) -> bool:
    try:
        driver.execute_script("mobile: swipeGesture", {
            "elementId": el.id,
            "direction": "up",
            "percent": float(percent)
        })
        return True
    except: return False

def try_dragGesture(driver, el, end_x, end_y, speed=1400) -> bool:
    try:
        driver.execute_script("mobile: dragGesture", {
            "elementId": el.id,
            "endX": int(end_x), "endY": int(end_y),
            "speed": int(speed)
        })
        return True
    except: return False

def try_w3c_drag_steps(driver, start_x, start_y, end_x, end_y, steps=14, hold_ms=260) -> bool:
    try:
        actions = ActionChains(driver)
        finger = PointerInput(PointerInput.TOUCH, "finger")
        actions.w3c_actions = ActionBuilder(driver, mouse=finger)

        actions.w3c_actions.pointer_action.move_to_location(int(start_x), int(start_y))
        actions.w3c_actions.pointer_action.pointer_down()
        actions.w3c_actions.pointer_action.pause(hold_ms/1000.0)

        dx = (end_x - start_x) / float(steps)
        dy = (end_y - start_y) / float(steps)
        for i in range(1, steps+1):
            actions.w3c_actions.pointer_action.move_to_location(
                int(start_x + dx*i), int(start_y + dy*i)
            )
            actions.w3c_actions.pointer_action.pause(0.035)

        actions.w3c_actions.pointer_action.release()
        actions.perform()
        return True
    except: return False

# ================== CORE ==================
def wait_accept_element(driver, timeout_s=25):
    """Espera handler aceptador; fallback al hint si no aparece."""
    end = time.monotonic() + timeout_s
    while time.monotonic() < end and not detener:
        try:
            els = driver.find_elements(AppiumBy.ID, ID_ACCEPT)
            if els:
                return els[0]
            hints = driver.find_elements(AppiumBy.ID, ID_HINT)
            if hints:
                return hints[0]
        except: pass
        time.sleep(0.12)
    return None

def answer_pull_up(driver) -> bool:
    """
    SOLO “subir el botón”: arrastre largo desde el handler real (sin notificaciones).
    Hace intentos escalonados y valida si la llamada quedó contestada.
    """
    el = wait_accept_element(driver, timeout_s=25)
    if not el:
        return False

    (cx, cy), (x1, y1, x2, y2) = _get_bounds_center(el)
    # punto de arranque: un poco debajo del centro del handler (agarre firme)
    start_x = cx
    start_y = cy + max(10, (y2 - y1)//5)

    attempts = [
        # método, destinos y parámetros (cada intento valida is_answered() tras ejecutar)
        ("swipeGesture", {"percent": 0.98}),                                     # 1
        ("dragGesture",  {"end_y_frac": 0.12, "speed": 1500}),                   # 2
        ("w3c",          {"end_y_frac": 0.10, "steps": 16, "hold_ms": 300}),     # 3
        ("dragGesture",  {"end_y_frac": 0.08, "speed": 1700}),                   # 4
        ("w3c",          {"end_y_frac": 0.06, "steps": 20, "hold_ms": 320}),     # 5
    ]

    w, h = screen_size(driver)
    for idx, (kind, params) in enumerate(attempts, 1):
        end_x = start_x
        end_y = top_target_y(driver, params.get("end_y_frac", 0.12))  # usa frac si está

        ok = False
        if kind == "swipeGesture":
            ok = try_swipeGesture(driver, el, percent=params["percent"])
        elif kind == "dragGesture":
            ok = try_dragGesture(driver, el, end_x, end_y, speed=params["speed"])
        elif kind == "w3c":
            ok = try_w3c_drag_steps(driver, start_x, start_y, end_x, end_y,
                                    steps=params["steps"], hold_ms=params["hold_ms"])

        # pausa breve y verificación
        time.sleep(0.15)
        if ok and is_answered(driver):
            print(f"[B] Contestó con {kind} (intento {idx})")
            return True

    print(f"[B] No logró arrastrar desde bounds=({x1},{y1},{x2},{y2}) "
          f"start=({start_x},{start_y}) -> end=(=same,{top_target_y(driver)})")
    return False

def hangup_if_visible(driver, wait_s=3) -> bool:
    """Cuelga con botón real (tap), sin gestos."""
    t_end = time.monotonic() + wait_s
    while time.monotonic() < t_end and not detener:
        try:
            cards = driver.find_elements(AppiumBy.ID, ID_CARD)
            if cards:
                try:
                    cards[0].find_element(AppiumBy.ID, "com.whatsapp:id/end_call_button").click()
                    print("[B] Colgó con end_call_button")
                    return True
                except: pass
        except: pass
        # Fallback accesible (depende de idioma/build)
        try:
            driver.find_element(AppiumBy.ACCESSIBILITY_ID, "Abandonar la llamada").click()
            print("[B] Colgó con accesibilidad")
            return True
        except: pass
        time.sleep(0.2)
    return False

def answer_call(driver, timeout_s=25) -> bool:
    device_wake(driver)
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline and not detener:
        if answer_pull_up(driver):
            return True
        time.sleep(0.12)
    return False

def wait_call_end(driver, idle_grace_s=2.0):
    """Espera a que la UI de llamada desaparezca."""
    missing_since = None
    while not detener:
        active = False
        try:
            if driver.find_elements(AppiumBy.ID, ID_CARD):
                active = True
        except: pass
        if not active:
            try:
                if driver.find_elements(AppiumBy.ID, ID_SUB):
                    active = True
            except: pass

        if active:
            missing_since = None
        else:
            if missing_since is None:
                missing_since = time.monotonic()
            if (time.monotonic() - missing_since) >= idle_grace_s:
                print("[B] Llamada finalizada.")
                return
        time.sleep(0.3)

# ================== MAIN ==================
def main():
    d = setup_driver_b()
    try:
        print("[B] Listo para contestar llamadas entrantes… (solo subir el botón)")
        while not detener:
            ok = answer_call(d, timeout_s=25)
            if ok:
                wait_call_end(d, idle_grace_s=2.0)
                print("[B] Fin de llamada, esperando próxima…")
                # Opcional: colgar automáticamente si quieres llamadas muy cortas
                # hangup_if_visible(d, wait_s=2)
            else:
                time.sleep(1.0)
    finally:
        try: d.quit()
        except: pass

if __name__ == "__main__":
    main()
