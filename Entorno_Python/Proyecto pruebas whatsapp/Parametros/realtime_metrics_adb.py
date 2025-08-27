# realtime_metrics_adb.py (versión corregida, una sola start_tshark)
# Lee el stream PCAP de PCAPdroid vía ADB (127.0.0.1:8080),
# alimenta a tshark por stdin y calcula jitter/pérdida por flujo RTP en (casi) tiempo real.

import os, shutil, requests, subprocess, threading, time, sys, signal
from collections import defaultdict, namedtuple
import socket

TCP_HOST = "127.0.0.1"   # por ADB forward
TCP_PORT = 11111         # el que pusiste en PCAPdroid

def stream_to_tshark(_unused_url, tshark_proc):
    # Lee el PCAP “crudo” del TCP exporter y lo pasa a tshark stdin
    while True:
        try:
            with socket.create_connection((TCP_HOST, TCP_PORT), timeout=5) as s:
                s.settimeout(15)  # lectura
                while True:
                    data = s.recv(16384)
                    if not data:
                        return
                    tshark_proc.stdin.buffer.write(data)
                    tshark_proc.stdin.flush()
        except (socket.timeout, ConnectionRefusedError, OSError):
            time.sleep(1)
            continue

# --- Config ---
PHONE_URL = "http://127.0.0.1:8080"   # ADB forward: adb forward tcp:8080 tcp:8080
PRINT_EVERY_S = 1.0
CLOCK_BY_PT = {0:8000, 8:8000, 9:8000, 18:8000, 96:48000, 111:48000}  # ajusta si conoces el códec
StreamKey = namedtuple("StreamKey", "src dst sport dport ssrc pt")

# Detectar ruta de tshark (PATH, variable, o ruta fija)
TSHARK_EXE = (
    os.environ.get("TSHARK_PATH") or
    shutil.which("tshark") or
    r"C:\Program Files\Wireshark\tshark.exe"
)

def assert_tshark():
    if not (TSHARK_EXE and os.path.exists(TSHARK_EXE)):
        raise RuntimeError(
            "No encuentro 'tshark'. Define TSHARK_PATH o instala Wireshark/TShark.\n"
            r"Ejemplo PowerShell: $env:TSHARK_PATH='C:\Program Files\Wireshark\tshark.exe'"
        )

def start_tshark():
    assert_tshark()
    return subprocess.Popen(
        [TSHARK_EXE, "-r", "-",
         "-o", "rtp.heuristic_rtp:TRUE", "-Y", "rtp", "-T", "fields",
         "-e", "frame.time_epoch", "-e", "ip.src", "-e", "ip.dst",
         "-e", "udp.srcport", "-e", "udp.dstport", "-e", "rtp.ssrc",
         "-e", "rtp.seq", "-e", "rtp.timestamp", "-e", "rtp.p_type",
         "-E", "separator=,", "-E", "occurrence=f"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1
    )

def stream_to_tshark(phone_url, tshark_proc):
    with requests.get(phone_url, stream=True, timeout=10) as r:
        for chunk in r.iter_content(16384):
            if not chunk: break
            tshark_proc.stdin.buffer.write(chunk)
            tshark_proc.stdin.flush()
    try: tshark_proc.stdin.close()
    except Exception: pass

def print_snapshot(stats):
    out = []
    for k, s in list(stats.items()):
        clock = CLOCK_BY_PT.get(s["pt"] or 96, 48000)
        exp = s["recv"] + s["lost"]
        loss_pct = (s["lost"]/exp*100.0) if exp else 0.0
        out.append({
            "flow": f"{k.src}:{k.sport}->{k.dst}:{k.dport} ssrc={k.ssrc} pt={s['pt']}",
            "pkts": s["recv"],
            "loss_pct": round(loss_pct,3),
            "jitter_mean_ms": round((s["J"]/clock)*1000.0,3),
            "jitter_max_ms":  round((s["Jmax"]/clock)*1000.0,3),
        })
    if out:
        print("[REALTIME]", out)

def print_summary(stats):
    print("\n===== RESUMEN POR FLUJO RTP =====")
    for k, s in stats.items():
        clock = CLOCK_BY_PT.get(s["pt"] or 96, 48000)
        exp = s["recv"] + s["lost"]
        loss_pct = (s["lost"]/exp*100.0) if exp else 0.0
        print(f"{k.src}:{k.sport}->{k.dst}:{k.dport} ssrc={k.ssrc} pt={s['pt']}")
        print(f"  pkts={s['recv']} lost={s['lost']} loss%={loss_pct:.3f}  "
              f"jitter_mean_ms={(s['J']/clock)*1000.0:.3f}  jitter_max_ms={(s['Jmax']/clock)*1000.0:.3f}")

def stream_tcp_exporter(host, port, tshark_proc):
    while True:
        try:
            with socket.create_connection((host, port), timeout=10) as s:
                s.settimeout(10)
                while True:
                    try:
                        chunk = s.recv(16384)
                        if not chunk:
                            break
                        tshark_proc.stdin.buffer.write(chunk)
                        tshark_proc.stdin.flush()
                    except socket.timeout:
                        # Sin bytes por unos segundos: seguimos esperando
                        continue
        except Exception as e:
            print("[TCP feeder] reconectando:", e)
            time.sleep(1)
            continue


def run():
    print(f"[i] Conectando a {PHONE_URL} (inicia la captura en PCAPdroid y haz la llamada)…")
    tshark = start_tshark()

    feeder = threading.Thread(
        target=stream_tcp_exporter,
        args=("127.0.0.1", 11111, tshark),
        daemon=True
    )
    feeder.start()
    
    prev_pkt = {}
    stats = defaultdict(lambda: {"recv":0,"lost":0,"J":0.0,"Jmax":0.0,"pt":None})
    last_print = time.time()

    def graceful_exit(*_):
        print("\n[i] Finalizando…")
        print_summary(stats)
        try: tshark.terminate()
        except Exception: pass
        sys.exit(0)

    signal.signal(signal.SIGINT, graceful_exit)
    signal.signal(signal.SIGTERM, graceful_exit)

    for line in tshark.stdout:
        parts = line.strip().split(",")
        if len(parts) != 9 or "" in parts:
            continue
        t = float(parts[0]); src=parts[1]; dst=parts[2]
        sport=int(parts[3]); dport=int(parts[4]); ssrc=parts[5]
        seq=int(parts[6]); ts=int(parts[7]); pt=int(parts[8])

        key = StreamKey(src,dst,sport,dport,ssrc,pt)
        st = stats[key]; st["pt"] = pt; st["recv"] += 1

        prev = prev_pkt.get(key)
        if prev:
            delta_seq = (seq - prev["seq"]) & 0xFFFF
            if delta_seq > 1: st["lost"] += (delta_seq - 1)
            clock = CLOCK_BY_PT.get(pt, 48000)
            arrival_delta = (t - prev["t"]) * clock
            ts_delta = (ts - prev["ts"]) & 0xFFFFFFFF
            D = arrival_delta - ts_delta
            st["J"] += (abs(D) - st["J"]) / 16.0
            if st["J"] > st["Jmax"]: st["Jmax"] = st["J"]
        prev_pkt[key] = {"t": t, "seq": seq, "ts": ts}

        now = time.time()
        if now - last_print >= PRINT_EVERY_S:
            print_snapshot(stats)
            last_print = now

if __name__ == "__main__":
    run()
