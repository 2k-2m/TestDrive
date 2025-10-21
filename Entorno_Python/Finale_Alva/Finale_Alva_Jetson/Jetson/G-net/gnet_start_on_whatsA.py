from __future__ import annotations
import sys, time
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# === DISPOSITIVO WHATS A ===
UDID        = "6NUDU18529000033"   # <- Whats A
PKG         = "com.gyokovsolutions.gnettrackproplus"
ACT         = "com.gyokovsolutions.gnettrackproplus.MainActivity"

# Appium temporal (libre; no choca con 4723/4730/4786)
APPIUM_URL  = "http://127.0.0.1:4790"
SYSTEM_PORT = 8248                 # systemPort único (no 8208/8216)

def esperar(drv, cond, t=10):
    return WebDriverWait(drv, t).until(cond)

def abrir_menu(drv) -> bool:
    # 1) "Más opciones" (tres puntos)
    try:
        el = WebDriverWait(drv, 5).until(
            EC.element_to_be_clickable((AppiumBy.ACCESSIBILITY_ID, "Más opciones"))
        )
        el.click()
        time.sleep(0.3)
        return True
    except:
        pass
    # 2) Fallback id: menu2
    try:
        el = WebDriverWait(drv, 5).until(EC.element_to_be_clickable(
            (AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().resourceId("{PKG}:id/menu2").enabled(true)')
        ))
        el.click()
        time.sleep(0.3)
        return True
    except:
        return False

def clic_texto(drv, text, rid_filter=None, timeout=8) -> bool:
    try:
        if rid_filter:
            loc=(AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().resourceId("{rid_filter}").text("{text}")')
        else:
            loc=(AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().text("{text}")')
        esperar(drv, EC.element_to_be_clickable(loc), timeout).click()
        time.sleep(0.3)
        return True
    except:
        return False

def run():
    caps = {
        "platformName":"Android",
        "automationName":"UiAutomator2",
        "deviceName":UDID,
        "udid":UDID,
        "appPackage":PKG,
        "appActivity":ACT,
        "appWaitActivity":"*",
        "noReset":True,
        "forceAppLaunch":True,
        "systemPort":SYSTEM_PORT,
        "newCommandTimeout":180
    }
    drv = webdriver.Remote(APPIUM_URL, options=UiAutomator2Options().load_capabilities(caps))
    try:
        # Espera básica a que esté el paquete visible
        try:
            esperar(drv, EC.presence_of_element_located(
                (AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().packageName("{PKG}")')), 10)
        except:
            pass

        if not abrir_menu(drv):
            raise RuntimeError("No se pudo abrir el menú de G-Net")

        # SOLO Start Log
        if not clic_texto(drv, "Start Log", rid_filter=f"{PKG}:id/title", timeout=10):
            # último intento sin rid_filter
            if not clic_texto(drv, "Start Log", timeout=6):
                raise RuntimeError("No se encontró 'Start Log'")

        # Si aparece confirmación, aceptar (no siempre aparece)
        try:
            WebDriverWait(drv, 4).until(
                EC.element_to_be_clickable((AppiumBy.ID, "android:id/button1"))
            ).click()
            time.sleep(0.3)
        except:
            pass

        print("[OK] G-NetTrack (Whats A): 'Start Log' lanzado. Cerrando driver…")
        return 0
    except Exception as e:
        print(f"[ERR] {e}")
        return 1
    finally:
        try: drv.quit()
        except: pass

if __name__ == "__main__":
    sys.exit(run())
