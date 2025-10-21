from __future__ import annotations
import sys, time, subprocess, os
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

UDID = "6NUDU18529000033"  # Whats A
PKG  = "com.gyokovsolutions.gnettrackproplus"
ACT  = "com.gyokovsolutions.gnettrackproplus.MainActivity"

APPIUM_URL  = "http://127.0.0.1:4790"
SYSTEM_PORT = 8248

OUT_DIR = os.path.dirname(__file__)
SHOT = os.path.join(OUT_DIR, "stop_endlog_last.png")
SRC  = os.path.join(OUT_DIR, "stop_endlog_last.xml")

def esperar(drv, cond, t=10):
    return WebDriverWait(drv, t).until(cond)

def abrir_menu(drv) -> bool:
    for acc in ("Más opciones", "More options"):
        try:
            WebDriverWait(drv, 6).until(
                EC.element_to_be_clickable((AppiumBy.ACCESSIBILITY_ID, acc))
            ).click()
            time.sleep(0.3)
            return True
        except:
            pass
    try:
        WebDriverWait(drv, 5).until(EC.element_to_be_clickable(
            (AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().resourceId("{PKG}:id/menu2").enabled(true)')
        )).click()
        time.sleep(0.3); return True
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

def click_yes_if_visible(drv, t=4):
    try:
        WebDriverWait(drv, t).until(
            EC.element_to_be_clickable((AppiumBy.ID, "android:id/button1"))
        ).click()
        time.sleep(0.2)
        return True
    except:
        return False

def cerrar_app_asegurado(drv):
    try:
        drv.terminate_app(PKG); time.sleep(0.3)
    except: pass
    try:
        subprocess.run(["adb", "-s", UDID, "shell", "am", "force-stop", PKG], check=False)
    except: pass

def run():
    # Sesión sin appPackage/appActivity → Appium NO usa -S
    caps = {
        "platformName":"Android",
        "automationName":"UiAutomator2",
        "deviceName":UDID,
        "udid":UDID,
        "noReset":True,
        "systemPort":SYSTEM_PORT,
        "newCommandTimeout":180
    }
    drv = webdriver.Remote(APPIUM_URL, options=UiAutomator2Options().load_capabilities(caps))
    try:
        # Traer G-Net al frente SIN -S (adb normal)
        subprocess.run(["adb", "-s", UDID, "shell", "am", "start", "-n", f"{PKG}/{ACT}"], check=False)
        time.sleep(0.7)

        # Esperar a que G-Net esté visible
        try:
            esperar(drv, EC.presence_of_element_located(
                (AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().packageName("{PKG}")')), 8)
        except: pass

        # Abrir menú → 'End Log'
        if not abrir_menu(drv):
            try:
                drv.save_screenshot(SHOT)
                with open(SRC, "w", encoding="utf-8") as f: f.write(drv.page_source)
            except: pass
            raise RuntimeError("No se pudo abrir el menú de G-Net")

        if not clic_texto(drv, "End Log", rid_filter=f"{PKG}:id/title", timeout=8):
            if not clic_texto(drv, "End Log", timeout=5):
                print("[WARN] No se encontró 'End Log' (posible que no estuviera logueando).")

        click_yes_if_visible(drv, t=4)

        # Cerrar app
        cerrar_app_asegurado(drv)
        print("[OK] End Log + cierre G-Net (Whats A) completados.")
        return 0

    except Exception as e:
        print(f"[ERR] {e}")
        try:
            drv.save_screenshot(SHOT)
            with open(SRC, "w", encoding="utf-8") as f: f.write(drv.page_source)
        except: pass
        try: cerrar_app_asegurado(drv)
        except: pass
        return 1
    finally:
        try: drv.quit()
        except: pass

if __name__ == "__main__":
    sys.exit(run())
