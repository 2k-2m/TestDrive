# -*- coding: utf-8 -*-
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import WebDriverException

from urllib.parse import urlparse
from pathlib import Path
from datetime import datetime
import time, csv, random, os, base64, subprocess, re
import signal
import socket
import json




# =============================
# === CONFIGURACIÓN MEJORADA ===
# =============================
BROWSER_PACKAGE = "com.android.chrome"
UDID = "R92Y515NJEP"
ALWAYS_DUMP = os.getenv("ALWAYS_DUMP", "0") == "1"
SEND_TIMEOUT = float(os.getenv("SEND_TIMEOUT", "7.0"))
ENABLE_SCREENSHOTS = False 


caps = {
    "platformName": "Android",
    "appium:automationName": "UiAutomator2",
    "appium:deviceName": "Android",
    "appium:udid": UDID,
    "appium:appPackage": "com.android.chrome",
    "appium:appActivity": "com.google.android.apps.chrome.Main",
    "appium:noReset": True,
    "appium:newCommandTimeout": 360,
    "appium:autoGrantPermissions": True,
    "appium:autoAcceptAlerts": True,
    "appium:ensureWebviewsHavePages": True,


    "goog:chromeOptions": {
        "androidPackage": "com.android.chrome",
        "androidActivity": "com.google.android.apps.chrome.Main",
        "androidDeviceSerial": UDID,
        #"w3c": False,
        "args": [
            "--disable-fre",
            "--no-first-run",
            "--disable-web-security",
            "--allow-running-insecure-content",
            "--disable-popup-blocking",
            "--disable-translate",
            "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding",
            "--disable-backgrounding-occluded-windows"
        ]
    },
}
#extra
caps.update({
    "appium:chromedriverAutodownload": True
})



# =============================
# === RUTAS / ARCHIVOS     ===
# =============================
FILE_TS = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
#BASE_DIR = str(Path.home() / "Finale_Alva" / "Chrome"
BASE_DIR = f"/home/jetson/Desktop/Finale_Alva/Chrome"
IG_CSV_PATH = os.path.join(BASE_DIR, f"Instagram_Data_{FILE_TS}.csv")
FB_CSV_PATH = os.path.join(BASE_DIR, f"Facebook_Data_{FILE_TS}.csv")

# =============================
# === CSV ===
# =============================
encabezados = [
    "App", "Red", "Type of test", "Latitude", "Longitude",
    "Initial Time", "Final Time", "State", "Cause of failure", "Content Size (MB)"
]
archivo_csv = None

def escribir_fila(app, red, tipo, latitud, longitud, inicio_dt, fin_dt, resultado, falla, tamanio):
    assert isinstance(inicio_dt, datetime) and isinstance(fin_dt, datetime), "inicio/fin deben ser datetime"
    fila = [
        app, red, tipo, latitud, longitud,
        inicio_dt.strftime("%Y-%m-%d %H:%M:%S"),
        fin_dt.strftime("%Y-%m-%d %H:%M:%S"),
        resultado, falla, tamanio
    ]
    os.makedirs(os.path.dirname(archivo_csv), exist_ok=True)
    with open(archivo_csv, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=',')
        if f.tell() == 0:
            writer.writerow(encabezados)
        writer.writerow(fila)

# =============================
# === CONSTANTES Y MÉTRICAS ===
# =============================
detener = False
def manejar_senal(sig, frame):
    global detener
    print("[INFO] Señal de terminación recibida.")
    detener = True
signal.signal(signal.SIGTERM, manejar_senal)
signal.signal(signal.SIGINT, manejar_senal)

METRICAS = {
    "FEED":   "Feed loading",
    "REELS":  "Reels page load",
    "RVIDEO": "Short video playback",
    "DM":     "Direct Message"
}

DEFAULT_TIMEOUT = 10
REELS_VIDEO_TIMEOUT = 10    

# =============================
# === UTILIDADES GENERALES  ===
# =============================
def obtener_conectividad(driver=None, udid=None):
    """
    Devuelve: 'WiFi' | 'Mobile' | 'Disconnected'
    Usa únicamente Appium mobile:shell (sin helper _adb).
    """
    def _sh(cmd, args):
        # devuelve stdout o "" si falla
        if driver is None:
            return ""
        try:
            res = driver.execute_script("mobile: shell", {
                "command": cmd, "args": args,
                "includeStderr": True, "timeout": 8000
            })
            return (res or {}).get("stdout", "") or ""
        except Exception:
            return ""

    # 1) cmd connectivity diagnostics
    out = _sh("cmd", ["connectivity", "diagnostics"])
    if out:
        if re.search(r'\b(Default|Active default)\s+network\s+(is:|:)\s*(WIFI|WLAN)\b', out, re.I):
            return "WiFi"
        if re.search(r'\b(Default|Active default)\s+network\s+(is:|:)\s*(CELLULAR|MOBILE)\b', out, re.I):
            return "Mobile"

    # 2) dumpsys connectivity
    out = _sh("dumpsys", ["connectivity"])
    if out:
        if re.search(r'NetworkAgentInfo.*?\bWIFI\b.*?\bCONNECTED\b.*?\bVALIDATED\b', out, re.I|re.S):
            return "WiFi"
        if re.search(r'NetworkAgentInfo.*?\b(MOBILE|CELLULAR)\b.*?\bCONNECTED\b.*?\bVALIDATED\b', out, re.I|re.S):
            return "Mobile"
        if re.search(r'default network is.*\b(WIFI|WLAN)\b', out, re.I):
            return "WiFi"
        if re.search(r'default network is.*\b(MOBILE|CELLULAR)\b', out, re.I):
            return "Mobile"

    # 3) ip route get 8.8.8.8
    route = _sh("ip", ["route", "get", "8.8.8.8"])
    if route:
        if re.search(r'\bwlan\d*\b', route):
            return "WiFi"
        if re.search(r'\b(rmnet(_data)?\d*|ccmni\d*|wwan\d*|rmnet|rmnet_ipa)\b', route):
            return "Mobile"

    # 4) dumpsys wifi como indicio final
    w = _sh("dumpsys", ["wifi"])
    if w and re.search(r'\bconnected\b', w, re.I):
        return "WiFi"

    return "Disconnected"


def obtener_gps_real(udid, max_age_s = None, timeout =69):
    try:
        output = subprocess.check_output(
            ["adb", "-s", udid, "shell", "dumpsys", "location"],
            encoding="utf-8"
        )
        match = re.search(r'gps:\s+Location\[gps\s+([-\d\.]+),\s*([-\d\.]+)', output, re.I)
        if match:
            return str(match.group(1)), str(match.group(2))
    except Exception as e:
        print(f"Error obteniendo ubicación real: {e}")
    return "n/a", "n/a"

def cerrar_apps(paquetes, udid):
    for paquete in paquetes:
        try:
            subprocess.run(['adb', '-s', udid, 'shell', 'am', 'force-stop', paquete], check=False)
            print(f"App {paquete} cerrada en {udid}.")
        except Exception as e:
            print(f"[WARN] No se pudo cerrar {paquete}: {e}")

def save_debug(driver, tag):
    try:
        with open(f"page_source_{tag}.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print(f"[DEBUG] Page source guardado: page_source_{tag}.html")
    except Exception as e:
        print(f"[DEBUG] Error guardando source: {e}")
    if ENABLE_SCREENSHOTS:
        try:
            screenshot_path = f"screenshot_{tag}.png"
            driver.save_screenshot(screenshot_path)
            print(f"[DEBUG] Screenshot guardado: {screenshot_path}")
        except Exception as e:
            print(f"[DEBUG] Error guardando screenshot: {e}")
    try:
        current_url = driver.current_url
        print(f"[DEBUG] URL actual: {current_url}")
    except Exception:
        pass

# =============================
# === WEBVIEW / CONTEXTOS  ===
# =============================
def wait_for_chrome_ready(driver, timeout=30):
    print("[INFO] Esperando a que Chrome esté listo...")
    time.sleep(5)
    try:
        current_activity = driver.current_activity
        print(f"[DEBUG] Actividad actual: {current_activity}")
        if "chrome" not in current_activity.lower():
            print("[WARN] Chrome no está en primer plano, intentando activarlo...")
            driver.start_activity(BROWSER_PACKAGE, "com.google.android.apps.chrome.Main")
            time.sleep(3)
    except Exception as e:
        print(f"[DEBUG] Error verificando actividad: {e}")

def switch_to_webview(driver, timeout=30):
    t0 = time.time()
    wait_for_chrome_ready(driver)
    while time.time() - t0 < timeout:
        try:
            current_contexts = driver.contexts
            print(f"[DEBUG] Contexts disponibles: {current_contexts}")
            for context in current_contexts:
                if context.startswith("WEBVIEW"):
                    print(f"[INFO] Intentando cambiar a contexto: {context}")
                    try:
                        driver.switch_to.context(context)
                        current_context = driver.current_context
                        if current_context == context:
                            print(f"[OK] Contexto cambiado exitosamente a: {context}")
                            try:
                                WebDriverWait(driver, 10).until(
                                    lambda d: d.execute_script("return document.readyState") == "complete"
                                )
                                print("[OK] WebView listo y documento cargado")
                            except:
                                print("[WARN] WebView cargado pero documento no completamente listo")
                            return True
                    except Exception as e:
                        print(f"[WARN] Error cambiando a contexto {context}: {e}")
                        continue
        except Exception as e:
            print(f"[DEBUG] Error obteniendo contextos: {e}")
        print("[WAIT] Esperando contextos WebView...")
        time.sleep(2)
    print("[ERROR] No se pudo cambiar a WebView dentro del timeout")
    return False

def switch_to_native(driver):
    try:
        driver.switch_to.context('NATIVE_APP')
        print("[OK] Cambiado a contexto NATIVE_APP")
        return True
    except Exception as e:
        print(f"[ERROR] Error cambiando a contexto nativo: {e}")
        return False

# =============================
# === RED/DOM HELPERS ===
# =============================

def wait_network_idle(driver, steady_ms=800, poll_ms=200, timeout=5):
    t_end = time.time() + timeout
    last = -1
    estable_desde = None
    while time.time() < t_end:
        try:
            cnt = driver.execute_script(
                "return (performance.getEntriesByType && performance.getEntriesByType('resource').length) || 0;"
            )
        except Exception:
            return False
        if cnt == last:
            if estable_desde is None:
                estable_desde = time.time()
            if (time.time() - estable_desde) * 1000 >= steady_ms:
                return True
        else:
            last = cnt
            estable_desde = None
        time.sleep(poll_ms/1000.0)
    return False

def ensure_webview_stabilized(driver):
    """
    Estabiliza WebView/Chrome ANTES de medir: cambia a WEBVIEW y espera un DOM legible.
    """
    if not switch_to_webview(driver, 25):
        return False
    try:
        wait_network_idle(driver, steady_ms=600, timeout=2)
    except Exception:
        pass
    return True

# =============================
# === NAVEGACIÓN + MÉTRICAS ===
# =============================
def medir_carga_pagina(driver, url, timeout_sec=DEFAULT_TIMEOUT):
    """
    1) Espera que WebView/Chrome esté estabilizado.
    2) Navega a URL.
    3) Mide tiempo hasta readyState='complete' (+ breve idle).
       Si tarda > timeout_sec => Failed.
    """
    if not ensure_webview_stabilized(driver):
        return False, "WebView no disponible", (datetime.now(), datetime.now()), 0.0

    start_dt = datetime.now()
    t0 = time.perf_counter()

    try:
        driver.get(url)
    except Exception as e:
        end_dt = datetime.now()
        return False, f"Error navegando: {e}", (start_dt, end_dt), 0.0

    ok_dom = False
    while (time.perf_counter() - t0) <= timeout_sec:
        try:
            if driver.execute_script("return document.readyState") == "complete":
                ok_dom = True
                break
        except Exception:
            pass
        time.sleep(0.1)
    if ok_dom:
        remaining = max(0.0, timeout_sec - (time.perf_counter() - t0))
        if remaining > 0:
            try:
                wait_network_idle(driver, steady_ms=600, timeout=min(2, remaining))
            except Exception:
                pass

    end_dt = datetime.now()
    elapsed = time.perf_counter() - t0

    if (not ok_dom) or (elapsed > timeout_sec):
        return False, f"Timeout >{timeout_sec}s", (start_dt, end_dt), elapsed

    return True, "", (start_dt, end_dt), elapsed

# =============================
# === NAVEGACIÓN CLÁSICA   ===
# =============================
def navegar_y_verificar_pagina(driver, url, timeout=30):
    print(f"[NAV] Navegando a: {url}")
    try:
        if not driver.current_context.startswith("WEBVIEW"):
            if not switch_to_webview(driver, 15):
                print("[ERROR] No se pudo cambiar a WebView para navegar")
                return False, "No se pudo cambiar a WebView"
        if "reels" in url.lower():
            print("[INFO] Página de Reels detectada, usando estrategia especial...")
            driver.get(url)
            time.sleep(8)
            try:
                current_url = driver.current_url or ""
                if "instagram.com" in current_url or "facebook.com" in current_url:
                    print("[OK] Página de Reels cargada (verificación básica)")
                    #save_debug(driver, f"loaded_{urlparse(url).netloc}")
                    return True, ""
                else:
                    return False, "Redirección inesperada en Reels"
            except Exception as e:
                return False, f"Error verificando Reels: {str(e)}"
        else:
            driver.get(url)
            WebDriverWait(driver, timeout).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            time.sleep(3)
            current_url = driver.current_url or ""
            expected_domain = urlparse(url).netloc.lower()
            if expected_domain not in current_url.lower():
                print(f"[WARN] Posible redirección. Esperado: {expected_domain}, Actual: {current_url}")
            #save_debug(driver, f"loaded_{urlparse(url).netloc}")
            try:
                body_text = driver.execute_script("return document.body.innerText || ''")
                if len(body_text.strip()) < 10:
                    print("[WARN] Página con contenido mínimo")
            except Exception:
                pass
            print(f"[OK] Página cargada correctamente: {url}")
            return True, ""
    except TimeoutException:
        print(f"[ERROR] Timeout cargando la página: {url}")
        #save_debug(driver, f"timeout_{urlparse(url).netloc}")
        return False, "Timeout cargando la página"
    except Exception as e:
        print(f"[ERROR] Error navegando a {url}: {e}")
        #save_debug(driver, f"error_{urlparse(url).netloc}")
        return False, str(e)

# =============================
# === INSTAGRAM DIRECT     ===
# =============================
def ensure_direct_inbox(driver):
    print("[INFO] Navegando a Instagram Direct...")
    if not switch_to_webview(driver, 25):
        raise RuntimeError("No se pudo cambiar a WebView. Abre Chrome en el teléfono y reintenta.")
    driver.get("https://www.instagram.com/direct/inbox/")
    try:
        WebDriverWait(driver, 20).until(
            lambda d: "instagram.com/direct" in (d.current_url or "")
        )
    except TimeoutException:
        raise RuntimeError("Timeout esperando Instagram Direct")
    time.sleep(2.0)
    return True

def wait_thread_open(driver, timeout=15):
    t0 = time.time()
    while time.time() - t0 < timeout:
        current_url = driver.current_url or ""
        if "/direct/t/" in current_url.lower():
            return True
        time.sleep(0.5)
    return False

def open_first_thread(driver):
    js = r"""
      function visible(n){
        if(!n) return false;
        const s = getComputedStyle(n);
        return s && s.visibility!=='hidden' && s.display!=='none' && n.offsetParent!==null;
      }
      function baseTop(){
        const heads = Array.from(document.querySelectorAll('h1,h2,h3,[role="heading"]'));
        let y = 120;
        const h = heads.find(x => /mensajes|messages/i.test((x.textContent||'').trim()));
        if (h) y = Math.max(y, h.getBoundingClientRect().bottom);
        const srch = document.querySelector('input[placeholder*="Buscar"]') || document.querySelector('input[type="search"]');
        if (srch) y = Math.max(y, srch.getBoundingClientRect().bottom + 10);
        return y;
      }
      function isSolicitudes(el){
        const t = (el.innerText||"").toLowerCase();
        if (t.includes("solicitudes")||t.includes("requests")) return true;
        const a = el.closest('a');
        const href = a ? (a.getAttribute('href')||"") : (el.getAttribute && el.getAttribute('href'))||"";
        return /\/direct\/requests/i.test(href);
      }
      function fireClick(el){
        try{ el.scrollIntoView({block:'center'});}catch(e){}
        const evs = ['pointerdown','mousedown','mouseup','click'];
        for (const e of evs){
          try{ el.dispatchEvent(new MouseEvent(e,{bubbles:true,cancelable:true,view:window})); }catch(_){}
        }
      }
      const topLimit = baseTop();
      const candidates = Array.from(document.querySelectorAll(
        'a[href*="/direct/t/"], [role="listitem"], [role="row"], li, [role="button"]'
      ))
      .map(n => n.closest('a[href*="/direct/t/"], [role="listitem"], [role="row"], li, [role="button"]'))
      .filter(Boolean)
      .filter(n => visible(n) && n.getBoundingClientRect().top > topLimit)
      .filter(n => !isSolicitudes(n));
      if (!candidates.length) return false;
      const anchor = candidates.map(n => (n.tagName==='A'?n:n.querySelector('a[href*="/direct/t/"]'))).find(Boolean);
      const target = anchor || candidates[0];
      const href = (target.tagName==='A' ? target.getAttribute('href') : (target.querySelector('a[href*="/direct/t/"]')||{}).getAttribute?.('href')) || "";
      fireClick(target);
      setTimeout(() => {
        try{
          if (href && !/\/direct\/t\//i.test(location.pathname)) {
            location.href = href;
          }
        }catch(_){}
      }, 200);
      return true;
    """
    try:
        res = driver.execute_script(js)
        return bool(res)
    except Exception:
        return False

def wait_chat_ready(driver, timeout=20):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            ok = driver.execute_script(
                "return !!document.querySelector(\"div[contenteditable='true'][role='textbox']\");"
            )
            if ok:
                return True
        except Exception:
            pass
        time.sleep(0.3)
    return False

def type_message_js(driver, text):
    js = r"""
      const txt = arguments[0] || "";
      let box = document.querySelector("div[contenteditable='true'][role='textbox']");
      if (!box) return "no_box";
      box.focus();
      try{
        const sel = window.getSelection();
        const r = document.createRange();
        r.selectNodeContents(box);
        r.collapse(false);
        sel.removeAllRanges();
        sel.addRange(r);
      }catch(_){}
      try { box.dispatchEvent(new InputEvent('beforeinput', {inputType:'insertText', data:txt, bubbles:true, cancelable:true})); } catch(_){}
      try {
        if (document.execCommand) { document.execCommand('insertText', false, txt); }
        else { box.textContent = (box.textContent||"") + txt; }
      } catch(_){
        box.textContent = (box.textContent||"") + txt;
      }
      try { box.dispatchEvent(new Event('input', {bubbles:true})); } catch(_){}
      try { box.dispatchEvent(new KeyboardEvent('keyup', {key:' ', bubbles:true})); } catch(_){}
      return "typed";
    """
    return driver.execute_script(js, text) == "typed"

def click_send_button(driver):
    js = r"""
      function visible(n){
        if(!n) return false;
        const s = getComputedStyle(n);
        return s && s.visibility!=='hidden' && s.display!=='none' && n.offsetParent!==null;
      }
      let btn = Array.from(document.querySelectorAll('[role="button"],button'))
        .find(b => visible(b) && /^(send|enviar)$/i.test((b.innerText||'').trim()));
      if(!btn){
        btn = Array.from(document.querySelectorAll('[aria-label]'))
          .find(b => visible(b) && /(send|enviar)/i.test(b.getAttribute('aria-label')||''));
      }
      if(!btn){
        const box = document.querySelector("div[contenteditable='true'][role='textbox']");
        let root = box ? (box.closest('form') || box.parentElement) : null;
        if (root){
          const all = Array.from(root.querySelectorAll('[role="button"],button')).filter(visible);
          if (all.length) btn = all[all.length-1];
        }
      }
      if(!btn) return "no_btn";
      try { btn.scrollIntoView({block:'center'}); } catch(_){}
      try { btn.click(); } catch(_){}
      setTimeout(() => { try{ btn.click(); }catch(_){} }, 80);
      return "clicked";
    """
    return driver.execute_script(js) == "clicked"

def count_sending_icons(driver):
    try:
        return int(driver.execute_script(
            'return document.querySelectorAll(\'[aria-label="IGD message sending status icon"]\').length;'
        ) or 0)
    except Exception:
        return 0

def wait_sent_overall(driver, total_timeout=7.0, poll=0.2):
    """
    Espera el envío TOTAL desde el click:
      - detecta aparición del ícono de envío
      - espera a que desaparezca
      - todo dentro de total_timeout (segundos)
    """
    baseline = count_sending_icons(driver)
    t_end = time.time() + total_timeout
    appeared = False
    while time.time() < t_end:
        cnt = count_sending_icons(driver)
        if not appeared:
            if cnt > baseline:
                appeared = True
        else:
            if cnt <= baseline:
                return ("sent",)
        time.sleep(poll)
    return ("no_icon",) if not appeared else ("timeout",)

def bytes_to_mb_str(n_bytes):
    try:
        mb = n_bytes / (1024.0 * 1024.0)
        return f"{mb:.6f}"
    except Exception:
        return "0.0"

# =============================
# === VIDEO / REELS HELPERS ===
# =============================
def _safe_js_json(driver, body):
    wrapped = f"""
        try {{
            const __res = (function(){{ {body} }})();
            if (typeof __res === 'undefined') return JSON.stringify({{'__error__':'no-return'}});
            if (typeof __res === 'string') return __res;
            return JSON.stringify(__res ?? {{__note__:'null'}});
        }} catch(e) {{
            return JSON.stringify({{'__error__': String(e)}});
        }}
    """
    try:
        s = driver.execute_script(wrapped)
    except Exception as e:
        return {"__error__": f"execute_script failed: {e}"}
    if s is None:
        return {"__error__": "null result from execute_script"}
    try:
        return json.loads(s)
    except Exception as e:
        return {"__error__": f"json parse failed: {e}", "__raw__": s}

def _ensure_video_in_viewport(driver, timeout=4):
    js = r"""
    (function(){
      function collect(root, out){
        try { if (root.querySelectorAll) { out.push(...root.querySelectorAll('video')); } } catch(e){}
        let nodes = [];
        try { if (root.querySelectorAll) { nodes = root.querySelectorAll('*'); } } catch(e){}
        for (const el of nodes){
          if (el && el.shadowRoot){
            try { collect(el.shadowRoot, out); } catch(_){}
          }
          if (el && el.tagName === 'IFRAME'){
            try { if (el.contentDocument) collect(el.contentDocument, out); } catch(_){}
          }
        }
      }
      const vids = [];
      collect(document, vids);
      for (const v of vids){
        const r = v.getBoundingClientRect();
        if (r.width>1 && r.height>1 && r.top<innerHeight && r.bottom>0) return true
      }
      return false
    })()
    """
    end = time.time() + timeout
    while time.time() < end:
        try:
            if driver.execute_script("return !!(" + js + ");"):
                return True
        except Exception:
            pass
        time.sleep(0.25)
    return False

def _kickstart_all_videos(driver):
    js = r"""
      (function(){
        const vids = Array.from(document.querySelectorAll('video'));
        for (const v of vids){
          try {
            v.muted = true;
            const p = v.play();
            if (p && typeof p.then==='function') p.catch(()=>{});
          }catch(_){}
        }
        return true;
      })();
    """
    try:
        driver.execute_script(js)
    except Exception:
        pass

def _js_best_video_stats(driver):
    return _safe_js_json(driver, r"""
        function inViewport(el){
          const r = el.getBoundingClientRect();
          return r.width>0 && r.height>0 && r.bottom>0 && r.top<innerHeight && r.right>0 && r.left<innerWidth;
        }
        function collectFromRoot(root, out){
            let vids = [];
            try { vids = root.querySelectorAll ? root.querySelectorAll('video') : []; } catch(_){}
            vids.forEach(v => out.push(v));
            let nodes = [];
            try { nodes = root.querySelectorAll ? root.querySelectorAll('*') : []; } catch(_){}
            for (const el of nodes){
                if (el && el.shadowRoot){
                    try { collectFromRoot(el.shadowRoot, out); } catch(_){}
                }
                if (el && el.tagName === 'IFRAME'){
                    try { if (el.contentDocument) collectFromRoot(el.contentDocument, out); } catch(_){}
                }
            }
        }
        function metr(v){
          let cur=0,dur=null,be=0,ba=0,rs=0,paused=true;
          try{
            cur = v.currentTime || 0;
            rs = v.readyState|0;
            paused = !!v.paused;
            if (Number.isFinite(v.duration)) dur = v.duration;
            if (v.buffered && v.buffered.length){
              be = v.buffered.end(v.buffered.length-1);
              ba = Math.max(0, be - cur);
            }
          }catch(_){}
          const vis = inViewport(v);
          const cov = dur ? (be / Math.max(0.001,dur)) : null;
          const score = (rs>=3?200:0) + ba;
          return {vis,cur,dur,be,ba,rs,paused,score,cov};
        }
        const all = [];
        collectFromRoot(document, all);
        if (!all.length) return {found:false, videos:0, url: location.href};
        const ms = all.map(metr);
        let cand = ms.filter(m => m.vis);
        if (!cand.length) cand = ms;
        let idx = 0, best = cand[0].score;
        for (let i=1;i<cand.length;i++){ if (cand[i].score>best){ best=cand[i].score; idx=i; } }
        const m = cand[idx];
        return {found:true, videos:ms.length, best:m, url:location.href};
    """)

def wait_reel_fully_loaded(driver, timeout=REELS_VIDEO_TIMEOUT, coverage=0.95, min_ahead_s=3.0, poll=0.35):
    end = time.time() + timeout
    kicked = False
    while time.time() < end:
        stats = _js_best_video_stats(driver)
        if stats.get("__error__"):
            time.sleep(poll); continue
        if not stats.get("found"):
            if not kicked:
                _kickstart_all_videos(driver); kicked = True
            time.sleep(poll); continue
        b = stats.get("best") or {}
        dur = b.get("dur")
        be  = float(b.get("be") or 0.0)
        ba  = float(b.get("ba") or 0.0)
        rs  = int(b.get("rs") or 0)
        cur = float(b.get("cur") or 0.0)
        paused = bool(b.get("paused"))
        if paused and not kicked:
            _kickstart_all_videos(driver); kicked = True
        if dur and dur > 0:
            cov = be / max(0.001, dur)
            near_end = (dur - cur) <= 1.2 and be >= (dur - 0.1)
            enough_ahead = ba >= 3.0
            loaded = (rs >= 3) and (cov >= coverage or enough_ahead or near_end)
        else:
            loaded = (rs >= 3) and (ba >= min_ahead_s)
        if loaded:
            try: wait_network_idle(driver, steady_ms=600, timeout=2)
            except Exception: pass
            return True
        time.sleep(poll)
    return False

# =============================
# === PRUEBAS INSTAGRAM     ===
# =============================
def probar_feed_ig(driver, red):
    lat, lon = obtener_gps_real(UDID, None, None)
    print(f"[GPS] Instagram Feed -> lat={lat}, lon={lon}")
    print("[TEST] Probando Feed de Instagram (medición exacta 7s)...")
    ok, causa, (inicio_dt, fin_dt), elapsed = medir_carga_pagina(driver, "https://www.instagram.com/", DEFAULT_TIMEOUT)
    estado, falla = ("Successful", "") if ok else ("Failed", causa)
    print(f"[IG FEED] {estado} en {elapsed:.2f}s")
    escribir_fila("Instagram", red, METRICAS["FEED"], lat, lon, inicio_dt, fin_dt, estado, falla, "0.0")
    return ok

def probar_reel_ig(driver, red):
    lat, lon = obtener_gps_real(UDID, None, None)
    print(f"[GPS] Instagram Reels -> lat={lat}, lon={lon}")
    print("[TEST] Probando Reels de Instagram (page load 7s)...")
    ok_page, causa_page, (ini_reels, fin_reels), elapsed = medir_carga_pagina(driver, "https://www.instagram.com/reels/", DEFAULT_TIMEOUT)
    estado_page, falla_page = ("Successful", "") if ok_page else ("Failed", causa_page)
    print(f"[IG REELS PAGE] {estado_page} en {elapsed:.2f}s")
    escribir_fila("Instagram", red, METRICAS["REELS"], lat, lon, ini_reels, fin_reels, estado_page, falla_page, "0.0")

    ini_video = datetime.now()
    if ok_page:
        _kickstart_all_videos(driver)
        vis = _ensure_video_in_viewport(driver, timeout=2)
        if not vis:
            try:
                driver.execute_script(r"""
                  (function(){
                    const as = Array.from(document.querySelectorAll('a'));
                    for (const a of as){
                      const href = a.href || a.getAttribute('href') || '';
                      if (/\/reels?\/[^\/?#]+/.test(href) && !/\/reels?\/?$/.test(href)){
                        a.click(); return true;
                      }
                    }
                    return false;
                  })();
                """)
            except Exception:
                pass
            time.sleep(1.0)
            _kickstart_all_videos(driver)
            vis = _ensure_video_in_viewport(driver, timeout=2)

        if vis:
            loaded = wait_reel_fully_loaded(driver, timeout=REELS_VIDEO_TIMEOUT, coverage=0.95, min_ahead_s=3.0)
            estado_video, falla_video = ("Successful", "") if loaded else ("Failed", "Video no totalmente bufferizado")
        else:
            estado_video, falla_video = ("Failed", "No hay video visible en el viewport")
    else:
        estado_video, falla_video = ("Failed", "No se pudo cargar la página de Reels")
    fin_video = datetime.now()
    print(f"[IG REELS VIDEO] {estado_video}")
    escribir_fila("Instagram", red, METRICAS["RVIDEO"], lat, lon, ini_video, fin_video, estado_video, falla_video, "0.0")

    return ok_page

def probar_dm_ig(driver, red):
    lat, lon = obtener_gps_real(UDID, None, None)
    print(f"[GPS] Instagram DM -> lat={lat}, lon={lon}")
    try:
        print("[TEST] Probando Mensajes Directos de Instagram...")
        ensure_direct_inbox(driver)

        #if ALWAYS_DUMP:
            #save_debug(driver, "dm_start")

        print("[DEBUG] Intentando abrir el primer chat...")
        opened = open_first_thread(driver)
        if not opened:
            try:
                driver.execute_script("window.scrollBy(0, 300)")
                time.sleep(0.6)
            except Exception:
                pass
            opened = open_first_thread(driver)

        if not opened or not wait_thread_open(driver, 10):
            #save_debug(driver, "dm_open_fail")
            raise RuntimeError("No pude abrir el primer chat desde la bandeja.")

        print("[OK] Primer chat abierto.")
        print("[DEBUG] Esperando a que cargue el editor del chat...")
        if not wait_chat_ready(driver, 20):
            raise RuntimeError("El editor del chat no apareció.")

        msg = str(random.randint(10_000, 99_999_999))
        msg_bytes = len(msg.encode("utf-8"))
        msg_mb_str = bytes_to_mb_str(msg_bytes)

        print("[INFO] Escribiendo:", msg)
        time.sleep(0.5)
        if not type_message_js(driver, msg):
            raise RuntimeError("No pude escribir en el editor.")

        time.sleep(0.5)
        clicked = click_send_button(driver)
        if not clicked:
            try:
                driver.execute_script("""
                  let box = document.querySelector("div[contenteditable='true'][role='textbox']");
                  if (box){
                    box.focus();
                    box.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', code:'Enter', keyCode:13, which:13, bubbles:true}));
                    box.dispatchEvent(new KeyboardEvent('keyup',   {key:'Enter', code:'Enter', keyCode:13, which:13, bubbles:true}));
                  }
                """)
            except Exception:
                pass

        inicio_dt = datetime.now()
        status_tuple = wait_sent_overall(driver, total_timeout=SEND_TIMEOUT, poll=0.25)
        fin_dt = datetime.now()

        status = status_tuple[0] if status_tuple else "timeout"
        if status == "sent":
            print(f"[SUCCESS] Mensaje enviado en {(fin_dt - inicio_dt).total_seconds():.2f}s")
            estado, falla, content_size = "Successful", "", msg_mb_str
        elif status == "no_icon":
            print("[WARN] El icono de envío no apareció dentro del timeout total")
            estado, falla, content_size = "Failed", "Icono de envío no detectado", "0.0"
        else:
            print(f"[FAILED] Mensaje NO enviado (timeout total {SEND_TIMEOUT}s)")
            estado, falla, content_size = "Failed", f"Timeout de envío ({SEND_TIMEOUT}s)", "0.0"

        escribir_fila("Instagram", red, METRICAS["DM"], lat, lon, inicio_dt, fin_dt, estado, falla, content_size)
        return estado == "Successful"

    except Exception as e:
        fin_dt = datetime.now()
        print(f"[ERROR] {e}")

        escribir_fila("Instagram", red, METRICAS["DM"], lat, lon, fin_dt, fin_dt, "Failed", str(e), "0.0")
        return False

# =============================
# === PRUEBAS FACEBOOK      ===
# =============================
def probar_feed_fb(driver, red):
    lat, lon = obtener_gps_real(UDID, None, None)
    print(f"[GPS] Facebook Feed -> lat={lat}, lon={lon}")
    print("[TEST] Probando Feed de Facebook (medición exacta 7s)...")
    ok, causa, (inicio_dt, fin_dt), elapsed = medir_carga_pagina(driver, "https://m.facebook.com/", DEFAULT_TIMEOUT)
    estado, falla = ("Successful", "") if ok else ("Failed", causa)
    print(f"[FB FEED] {estado} en {elapsed:.2f}s")
    escribir_fila("Facebook", red, METRICAS["FEED"], lat, lon, inicio_dt, fin_dt, estado, falla, "0.0")
    return ok

def probar_reel_fb(driver, red):
    lat, lon = obtener_gps_real(UDID, None, None)
    print(f"[GPS] Facebook Reels -> lat={lat}, lon={lon}")
    print("[TEST] Probando Reels de Facebook (page load 7s)...")
    ok_page, causa_page, (ini_reels, fin_reels), elapsed = medir_carga_pagina(driver, "https://m.facebook.com/reel/?referral_source=unknown", DEFAULT_TIMEOUT)
    estado_page, falla_page = ("Successful", "") if ok_page else ("Failed", causa_page)
    print(f"[FB REELS PAGE] {estado_page} en {elapsed:.2f}s")
    escribir_fila("Facebook", red, METRICAS["REELS"], lat, lon, ini_reels, fin_reels, estado_page, falla_page, "0.0")

    ini_video = datetime.now()
    if ok_page:
        _kickstart_all_videos(driver)
        vis = _ensure_video_in_viewport(driver, timeout=2)
        if not vis:
            try:
                driver.execute_script(r"""
                  (function(){
                    const as = Array.from(document.querySelectorAll('a'));
                    for (const a of as){
                      const href = a.href || a.getAttribute('href') || '';
                      if (/\/reel\/[^\/?#]+/.test(href)){
                        a.click(); return true;
                      }
                    }
                    return false;
                  })();
                """)
            except Exception:
                pass
            time.sleep(1.0)
            _kickstart_all_videos(driver)
            vis = _ensure_video_in_viewport(driver, timeout=2)

        if vis:
            loaded = wait_reel_fully_loaded(driver, timeout=REELS_VIDEO_TIMEOUT, coverage=0.95, min_ahead_s=3.0)
            estado_video, falla_video = ("Successful", "") if loaded else ("Failed", "Video no totalmente bufferizado")
        else:
            estado_video, falla_video = ("Failed", "No hay video visible en el viewport")
    else:
        estado_video, falla_video = ("Failed", "No se pudo cargar la página de Reels")
    fin_video = datetime.now()
    print(f"[FB REELS VIDEO] {estado_video}")
    escribir_fila("Facebook", red, METRICAS["RVIDEO"], lat, lon, ini_video, fin_video, estado_video, falla_video, "0.0")

    return ok_page

# =============================
# === SUITES / DRIVER       ===
# =============================
def setup_driver():
    try:
        print("[INFO] Inicializando driver de Appium...")
        cerrar_apps([BROWSER_PACKAGE], UDID)
        time.sleep(3)
        opts = UiAutomator2Options().load_capabilities(caps)
        driver = webdriver.Remote("http://127.0.0.1:4730/wd/hub", options=opts)
        try:
            driver.implicitly_wait(2)
        except Exception:
            pass
        print("[INFO] Driver de Appium inicializado correctamente")
        print("[INFO] Esperando a que Chrome se estabilice...")
        time.sleep(8)
        return driver
    except Exception as e:
        print(f"[ERROR] No se pudo iniciar Appium: {e}")
        return None

def test_instagram_web():
    global archivo_csv
    archivo_csv = IG_CSV_PATH
    print(f"[CSV] Archivo activo IG: {archivo_csv}")

    print("INICIANDO PRUEBAS DE INSTAGRAM WEB...")
    driver = setup_driver()
    if not driver:
        return False
    time.sleep(2.0)
    try:
        red = obtener_conectividad(driver)
        if detener:
            print("[INFO] Proceso detenido por el usuario.")
            return False

        print("1. Probando Feed IG...")
        probar_feed_ig(driver, red)
        if detener:
            print("[INFO] Proceso detenido por el usuario.")
            return False

        print("2. Probando Reels IG...")
        try:
            probar_reel_ig(driver, red)
        except Exception as e:
            print(f"[ERROR CRÍTICO] Prueba de Reels falló: {e}")

        if detener:
            print("[INFO] Proceso detenido por el usuario.")
            return False

        print("3. Probando Mensajes Directos IG...")
        probar_dm_ig(driver, red)

        print("PRUEBAS DE INSTAGRAM COMPLETADAS")
        return True
    except Exception as e:
        print(f"ERROR en pruebas de Instagram: {e}")
        return False
    finally:
        try:
            switch_to_native(driver)
            cerrar_apps([BROWSER_PACKAGE], UDID)
        except Exception:
            pass
        try:
            driver.quit()
        except Exception:
            pass
        time.sleep(1)

def test_facebook_web():
    global archivo_csv
    archivo_csv = FB_CSV_PATH
    print(f"[CSV] Archivo activo FB: {archivo_csv}")

    print("INICIANDO PRUEBAS DE FACEBOOK WEB...")
    driver = setup_driver()
    if not driver:
        return False
    time.sleep(2.0)
    try:
        red = obtener_conectividad(driver)
        if detener:
            print("[INFO] Proceso detenido por el usuario.")
            return False

        print("1. Probando Feed FB...")
        probar_feed_fb(driver, red)
        if detener:
            print("[INFO] Proceso detenido por el usuario.")
            return False

        print("2. Probando Reels FB...")
        probar_reel_fb(driver, red)

        print("PRUEBAS DE FACEBOOK COMPLETADAS")
        return True
    except Exception as e:
        print(f"ERROR en pruebas de Facebook: {e}")
        return False
    finally:
        try:
            switch_to_native(driver)
            cerrar_apps([BROWSER_PACKAGE], UDID)
        except Exception:
            pass
        try:
            driver.quit()
        except Exception:
            pass
        time.sleep(1)

# =============================
# === MAIN / EJECUCIÓN     ===
# =============================
def ejecutar_pruebas():
    contador = 0
    while True:
        contador += 1
        if detener:
            print(f"Detenido externamente en la interacción {contador}")
            break
        print("\n" + "="*50)
        print(f"INTERACCIÓN {contador}")
        print("="*50)

        try:
            print("\nINICIANDO PRUEBAS DE INSTAGRAM")
            continuar = test_instagram_web()
            if not continuar:
                print("[INFO] Finalizando ejecución desde test_instagram_web")
                break

            print("\nINICIANDO PRUEBAS DE FACEBOOK")
            continuar_fb = test_facebook_web()
            if not continuar_fb:
                print("[INFO] Finalizando ejecución desde test_facebook_web")
                break

            print(f"\nIteración {contador} completada exitosamente")
        except Exception as e:
            print(f"ERROR en la insteracción {contador}: {e}")

if __name__ == "__main__":
    print("INICIANDO SISTEMA DE PRUEBAS AUTOMATIZADAS")
    print(f"CSV IG: {IG_CSV_PATH}")
    print(f"CSV FB: {FB_CSV_PATH}")
    detener = False
    
    try:
        ejecutar_pruebas()
    except KeyboardInterrupt:
        print("\n\nEjecución interrumpida por el usuario (Ctrl+C)")
        detener = True
    finally:
        print("\nEJECUCIÓN FINALIZADA")
