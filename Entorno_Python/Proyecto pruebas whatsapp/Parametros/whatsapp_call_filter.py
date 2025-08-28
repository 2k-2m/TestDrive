#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
whatsapp_call_filter.py
Lee PCAP en vivo desde PCAPdroid (HTTP exporter) vía ADB (USB) y muestra SOLO RTP (voz WhatsApp).
No guarda PCAP: lo que imprime es lo que se guarda con --out.
Resumen por flujo: pérdida, jitter medio/máx, duración y pps.

Uso típico (PowerShell, Windows):
  $env:TSHARK_PATH="C:\Program Files\Wireshark\tshark.exe"
  adb -s 6NUDU18529000033 forward tcp:8080 tcp:8080
  python whatsapp_call_filter.py --serial 6NUDU18529000033 --port 8080 --out whatsapp_llamada.log --strict-wa
"""

import os, sys, time, argparse, shutil, subprocess, platform
from collections import defaultdict, namedtuple
from threading import Event

try:
    import requests
except ImportError:
    requests = None

StreamKey = namedtuple("StreamKey", "src dst sport dport ssrc pt")
CLOCK_BY_PT = {0:8000, 8:8000, 9:8000, 18:8000, 96:48000, 111:48000, 120:48000}
DEFAULT_FORCE_PORTS = [3478, 3479, 5349]

def which_tshark():
    cand = os.environ.get("TSHARK_PATH")
    if cand and os.path.isfile(cand):
        return cand
    if platform.system().lower().startswith("win"):
        exe = shutil.which("tshark.exe")
        if exe: return exe
        default = r"C:\Program Files\Wireshark\tshark.exe"
        if os.path.exists(default): return default
        raise RuntimeError("No encuentro 'tshark.exe'. Instala Wireshark o define TSHARK_PATH.")
    exe = shutil.which("tshark")
    if exe: return exe
    raise RuntimeError("No encuentro 'tshark'. Instálalo o define TSHARK_PATH.")

def adb_forward(port: int, serial: str | None):
    adb = shutil.which("adb") or "adb"
    cmd = [adb]
    if serial:
        cmd += ["-s", serial]
    cmd += ["forward", f"tcp:{port}", f"tcp:{port}"]
    subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

def start_tshark(tshark_path: str, strict_wa: bool):
    args = [
        tshark_path, "-r", "-",
        "-o", "rtp.heuristic_rtp:TRUE",
        "-Y", "rtp",
        "-T", "fields",
        "-e", "frame.time_epoch",
        "-e", "ip.src", "-e", "ip.dst",
        "-e", "udp.srcport", "-e", "udp.dstport",
        "-e", "rtp.ssrc", "-e", "rtp.seq", "-e", "rtp.timestamp",
        "-e", "rtp.p_type",
        "-E", "separator=,", "-E", "occurrence=f",
        "-l"
    ]
    if strict_wa:
        for p in DEFAULT_FORCE_PORTS:
            args.extend(["-d", f"udp.port=={p},rtp"])
    return subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)

def stream_http_to_tshark(url: str, tshark_proc, stop_evt: Event):
    if requests is None:
        raise RuntimeError("Falta 'requests'. Instálalo: pip install requests")
    with requests.get(url, stream=True, timeout=5) as r:
        r.raise_for_status()
        for chunk in r.iter_content(16384):
            if stop_evt.is_set():
                break
            if not chunk:
                continue
            try:
                tshark_proc.stdin.buffer.write(chunk)
                tshark_proc.stdin.flush()
            except BrokenPipeError:
                break
    try:
        tshark_proc.stdin.close()
    except Exception:
        pass

def tee_print(s: str, fh):
    print(s)
    if fh:
        fh.write(s + ("\n" if not s.endswith("\n") else ""))
        fh.flush()

def main():
    ap = argparse.ArgumentParser(description="Analizador de llamadas WhatsApp (RTP) por ADB; guarda LOG de consola, no PCAP.")
    ap.add_argument("--serial", default=os.environ.get("ANDROID_SERIAL", ""), help="Serial ADB del teléfono (ej. 6NUDU18529000033)")
    ap.add_argument("--port", type=int, default=8080, help="Puerto HTTP exporter (teléfono). Default: 8080")
    ap.add_argument("--host", default="127.0.0.1", help="Host local (no cambiar). Default: 127.0.0.1")
    ap.add_argument("--out", default="", help="Archivo para guardar EXACTAMENTE lo que se imprime (opcional)")
    ap.add_argument("--min-pkts", type=int, default=8, help="Mínimo de paquetes RTP para el resumen")
    ap.add_argument("--strict-wa", action="store_true", help="Fuerza decode-as RTP en 3478/3479/5349")
    args = ap.parse_args()

    serial = args.serial if args.serial else None
    url = f"http://{args.host}:{args.port}"

    # ADB forward al dispositivo correcto
    try:
        adb_forward(args.port, serial)
    except subprocess.CalledProcessError:
        print("[x] Error con 'adb forward'. ¿Dispositivo conectado/autorizado y serial correcto?")
        sys.exit(1)

    tshark_path = which_tshark()
    logfh = open(args.out, "w", encoding="utf-8") if args.out else None

    tee_print(f"[adb] forward ({'serial='+serial if serial else 'default'}) tcp:{args.port} -> tcp:{args.port} OK", logfh)
    tee_print(f"[i] TShark: {tshark_path}", logfh)
    tee_print(f"[i] Fuente: {url} (PCAPdroid → HTTP exporter → Start)", logfh)
    if args.strict_wa:
        tee_print("[i] Modo estricto activado (decode-as RTP en 3478/3479/5349).", logfh)

    stop_evt = Event()
    tshark = start_tshark(tshark_path, args.strict_wa)

    prev_pkt = {}
    stats = defaultdict(lambda: {"recv":0,"lost":0,"J":0.0,"Jmax":0.0,"pt":None, "first_t":None, "last_t":None})

    def handle_line(line: str):
        parts = line.strip().split(",")
        if len(parts) != 9 or "" in parts:
            return
        try:
            t = float(parts[0]); src=parts[1]; dst=parts[2]
            sport=int(parts[3]); dport=int(parts[4]); ssrc=parts[5]
            seq=int(parts[6]); ts=int(parts[7]); pt=int(parts[8])
        except Exception:
            return

        key = StreamKey(src,dst,sport,dport,ssrc,pt)
        st = stats[key]
        st["pt"] = pt
        st["recv"] += 1
        if st["first_t"] is None:
            st["first_t"] = t
        st["last_t"] = t

        prev = prev_pkt.get(key)
        if prev:
            delta_seq = (seq - prev["seq"]) & 0xFFFF
            if delta_seq > 1:
                st["lost"] += (delta_seq - 1)
            clock = CLOCK_BY_PT.get(pt, 48000)
            arrival_delta = (t - prev["t"]) * clock
            ts_delta = (ts - prev["ts"]) & 0xFFFFFFFF
            D = arrival_delta - ts_delta
            if abs(D) <= 8 * clock:
                st["J"] += (abs(D) - st["J"]) / 16.0
                if st["J"] > st["Jmax"]:
                    st["Jmax"] = st["J"]
        prev_pkt[key] = {"t": t, "seq": seq, "ts": ts}

        # Log por-paquete (lo que ves también se guarda con --out)
        tee_print(f"[RTP] {src}:{sport}->{dst}:{dport} ssrc={ssrc} pt={pt} seq={seq} ts={ts} t={t:.6f}", logfh)

    try:
        import threading
        feeder = threading.Thread(target=stream_http_to_tshark, args=(url, tshark, stop_evt), daemon=True)
        feeder.start()

        while True:
            line = tshark.stdout.readline()
            if not line:
                break
            handle_line(line)
    except KeyboardInterrupt:
        pass
    finally:
        stop_evt.set()
        try: tshark.terminate()
        except Exception: pass

        # Resumen
        tee_print("\n===== RESUMEN POR FLUJO RTP (WhatsApp) =====", logfh)
        printed = 0
        for k, s in stats.items():
            if s["recv"] < args.min_pkts:
                continue
            clock = CLOCK_BY_PT.get(s["pt"] or 96, 48000)
            exp = s["recv"] + s["lost"]
            loss_pct = (s["lost"]/exp*100.0) if exp else 0.0
            jitter_ms = (s["J"]/clock)*1000.0 if clock else 0.0
            jitter_max_ms = (s["Jmax"]/clock)*1000.0 if clock else 0.0
            dur_s = max(0.0, (s["last_t"] - s["first_t"])) if s["first_t"] is not None else 0.0
            pps = (s["recv"]/dur_s) if dur_s > 0 else 0.0

            tee_print(f"{k.src}:{k.sport} -> {k.dst}:{k.dport}  ssrc={k.ssrc}  pt={s['pt']}", logfh)
            tee_print(f"  pkts={s['recv']}  lost={s['lost']}  loss%={loss_pct:.3f}  "
                      f"jitter_mean_ms={jitter_ms:.3f}  jitter_max_ms={jitter_max_ms:.3f}  "
                      f"dur_s={dur_s:.2f}  pps={pps:.1f}", logfh)
            printed += 1

        if printed == 0:
            tee_print("(sin flujos RTP válidos; ¿PCAPdroid en Start y llamada en curso?)", logfh)

        if logfh: logfh.close()

if __name__ == "__main__":
    main()
