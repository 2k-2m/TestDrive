# -*- coding: utf-8 -*-
import time
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ---------- Parámetros por defecto (puedes sobreescribir al llamar) ----------
DEFAULTS = {
    "udid": "RF8MB0G4KTJ",  # cambia por tu UDID si quieres
    "pkg":  "com.gyokovsolutions.gnettrackproplus",
    "act":  "com.gyokovsolutions.gnettrackproplus.MainActivity",
    "server_url": "http://127.0.0.1:4793",
    # Si está ya abierta no la forzamos a relanzar; tampoco reseteamos el estado:
    "caps": {
        "platformName": "Android",
        "automationName": "UiAutomator2",
        # Se colocan dinámicamente:
        "udid": None,
        "deviceName": None,
        "appPackage": None,
        "appActivity": None,
        # Mantener estado y no matar la app:
        "noReset": True,
        "dontStopAppOnReset": True,
        "forceAppLaunch": False,
        "newCommandTimeout": 180,
        # Puedes sobreescribir con caps_overrides:
        # "systemPort": 8240,
        # "mjpegServerPort": 7815,
        # "chromedriverPort": 9517,
    },
    # Tras la acción, mandar HOME para dejar la app en 2º plano:
    "background_after": True,
    # ¿Disparar también la Data Sequence al iniciar?
    "start_data_sequence": True,
    # ¿Intentar detener Data Sequence al cerrar?
    "stop_data_sequence": True,
}

# ------------------------- Helpers de UI reutilizables -------------------------
def _esperar(driver, cond, timeout=12):
    return WebDriverWait(driver, timeout).until(cond)

def _clic_texto(driver, text, rid_filter=None, timeout=10, mandatory=True):
    try:
        if rid_filter:
            locator = (AppiumBy.ANDROID_UIAUTOMATOR,
                       f'new UiSelector().resourceId("{rid_filter}").text("{text}")')
        else:
            locator = (AppiumBy.ANDROID_UIAUTOMATOR,
                       f'new UiSelector().text("{text}")')
        el = _esperar(driver, EC.element_to_be_clickable(locator), timeout)
        el.click(); time.sleep(0.3)
        return True
    except Exception:
        if mandatory:
            raise
        return False

def _clic_desc(driver, content_desc, timeout=8, mandatory=True):
    try:
        el = _esperar(driver, EC.element_to_be_clickable(
            (AppiumBy.ACCESSIBILITY_ID, content_desc)), timeout)
        el.click(); time.sleep(0.25)
        return True
    except Exception:
        if mandatory:
            raise
        return False

def _click_button_id(driver, rid, timeout=8, mandatory=True):
    try:
        el = _esperar(driver, EC.element_to_be_clickable((AppiumBy.ID, rid)), timeout)
        el.click(); time.sleep(0.25)
        return True
    except Exception:
        if mandatory:
            raise
        return False

def _abrir_menu(driver, pkg):
    """
    Intenta abrir el menú tipo 'tres puntos':
    1) Por accessibility id 'Más opciones'
    2) Fallback id: <pkg>:id/menu2
    """
    if _clic_desc(driver, "Más opciones", timeout=4, mandatory=False):
        return True
    if _click_si_clickable(driver, pkg, f"{pkg}:id/menu2", timeout=4):
        return True
    # Fallback extra por clase + desc contiene "opciones"
    try:
        el = _esperar(driver, EC.element_to_be_clickable(
            (AppiumBy.ANDROID_UIAUTOMATOR,
             'new UiSelector().className("android.widget.ImageView").descriptionContains("opciones")')), 3)
        el.click(); time.sleep(0.25)
        return True
    except Exception:
        pass
    raise RuntimeError("No se pudo abrir el menú (Más opciones / menu2).")

def _click_si_clickable(driver, pkg, rid, timeout=6):
    try:
        el = _esperar(driver, EC.element_to_be_clickable(
            (AppiumBy.ANDROID_UIAUTOMATOR,
             f'new UiSelector().resourceId("{rid}").enabled(true)')), timeout)
        el.click(); time.sleep(0.25)
        return True
    except Exception:
        return False

def _poner_en_segundo_plano(driver):
    """Manda HOME para que la app quede en background, sin cerrarla."""
    try:
        driver.press_keycode(3)  # KEYCODE_HOME
        time.sleep(0.3)
    except Exception:
        pass

# --------------------------- Sesión / Driver ---------------------------
def _crear_driver(udid, pkg, act, server_url, caps_overrides=None):
    """
    Crea el driver aplicando caps por defecto + overrides opcionales (systemPort, etc.).
    """
    caps = dict(DEFAULTS["caps"])
    caps["udid"] = udid
    caps["deviceName"] = udid
    caps["appPackage"] = pkg
    caps["appActivity"] = act

    # 👉 aplicar overrides si te pasan puertos u otros flags
    if caps_overrides:
        caps.update(caps_overrides)

    options = UiAutomator2Options().load_capabilities(caps)
    return webdriver.Remote(server_url, options=options)

# =========================== FUNCIONES EXPORTABLES ===========================
def iniciar_logs(
    udid: str = DEFAULTS["udid"],
    pkg: str = DEFAULTS["pkg"],
    act: str = DEFAULTS["act"],
    server_url: str = DEFAULTS["server_url"],
    background_after: bool = DEFAULTS["background_after"],
    start_data_sequence: bool = DEFAULTS["start_data_sequence"],
    # 👇 nuevo: permite puertos únicos (systemPort/mjpegServerPort/etc.)
    caps_overrides: dict | None = None,
) -> bool:
    """
    Abre (sin resetear) G-NetTrack Pro+, abre el menú y toca:
    - 'Start Log'
    - opcional: 'Start Data Sequence' + confirma 'YES'

    Deja la app en 2º plano al terminar (no la cierra). Cierra sólo el driver.
    """
    driver = None
    try:
        driver = _crear_driver(udid, pkg, act, server_url, caps_overrides=caps_overrides)
        # Pequeña espera por si hay animaciones de arranque/foreground:
        try:
            _esperar(driver, EC.presence_of_element_located(
                (AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().packageName("{pkg}")')), 8)
        except Exception:
            pass

        _abrir_menu(driver, pkg)

        # 1) Start Log
        _clic_texto(driver, "Start Log", rid_filter=f"{pkg}:id/title", timeout=10, mandatory=True)

        # 2) (opcional) Start Data Sequence / Data Test (variantes)
        if start_data_sequence:
            variantes = ["Start Data Sequence", "Start Data Test", "Start DataSequence", "Start Data Seq"]
            tocado = False
            # El menú se podría cerrar; reabro por si acaso:
            try:
                _abrir_menu(driver, pkg)
            except Exception:
                pass
            for v in variantes:
                if _clic_texto(driver, v, rid_filter=f"{pkg}:id/title", timeout=6, mandatory=False):
                    tocado = True; break
            if not tocado:
                for v in variantes:
                    if _clic_texto(driver, v, rid_filter=None, timeout=4, mandatory=False):
                        tocado = True; break
            if tocado:
                # Confirmación YES si aparece
                _click_button_id(driver, "android:id/button1", timeout=6, mandatory=False)

        # Dejar app en background si se pide:
        if background_after:
            _poner_en_segundo_plano(driver)

        return True

    finally:
        try:
            if driver:
                driver.quit()
        except Exception:
            pass


def detener_logs(
    udid: str = DEFAULTS["udid"],
    pkg: str = DEFAULTS["pkg"],
    act: str = DEFAULTS["act"],
    server_url: str = DEFAULTS["server_url"],
    background_after: bool = DEFAULTS["background_after"],
    stop_data_sequence: bool = DEFAULTS["stop_data_sequence"],
    # 👇 nuevo: igual soporte de overrides
    caps_overrides: dict | None = None,
) -> bool:
    """
    Abre (sin resetear) G-NetTrack Pro+, abre el menú y toca:
    - 'End/Stop/Finish Log' (acepta variantes)
    - opcional: 'Stop Data Sequence' + confirma 'YES'

    Deja la app en 2º plano al terminar (no la cierra). Cierra sólo el driver.
    """
    driver = None
    try:
        driver = _crear_driver(udid, pkg, act, server_url, caps_overrides=caps_overrides)
        # Pequeña espera por si hay animaciones de arranque/foreground:
        try:
            _esperar(driver, EC.presence_of_element_located(
                (AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().packageName("{pkg}")')), 8)
        except Exception:
            pass

        _abrir_menu(driver, pkg)

        # 1) End/Stop/Finish Log (varias variantes)
        variantes_log = ["End Log", "Stop Log", "Finish Log", "Endlog", "END LOG"]
        tocado = False
        for v in variantes_log:
            if _clic_texto(driver, v, rid_filter=f"{pkg}:id/title", timeout=6, mandatory=False):
                tocado = True; break
        if not tocado:
            for v in variantes_log:
                if _clic_texto(driver, v, rid_filter=None, timeout=4, mandatory=False):
                    tocado = True; break

        # 2) (opcional) Stop Data Sequence
        if stop_data_sequence:
            try:
                _abrir_menu(driver, pkg)
            except Exception:
                pass
            if not _clic_texto(driver, "Stop Data Sequence", rid_filter=f"{pkg}:id/title",
                               timeout=5, mandatory=False):
                _clic_texto(driver, "Stop Data Sequence", rid_filter=None,
                            timeout=4, mandatory=False)
            # Confirmación YES si sale diálogo
            _click_button_id(driver, "android:id/button1", timeout=6, mandatory=False)

        if background_after:
            _poner_en_segundo_plano(driver)

        return True

    finally:
        try:
            if driver:
                driver.quit()
        except Exception:
            pass


# ------------------------------ Exportación ------------------------------
__all__ = [
    "iniciar_logs",
    "detener_logs",
]

