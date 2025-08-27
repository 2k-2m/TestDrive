# pcap_server_to_tshark.py
# PC escucha por TCP, recibe PCAP desde el teléfono (PCAPdroid en modo "TCP exporter - pcap-over-ip"),
# lo alimenta a TShark por stdin y calcula jitter/pérdidas por flujo RTP en tiempo casi real.
# Funciona en Windows. Incluye hints en vivo y "decode-as" para puertos típicos de WhatsApp.

import os, shutil, socket, subprocess, threading, time
from collections import defaultdict, namedtuple

HOST = "127.0.0.1"         # PC escucha local
PORT = 11111               # <-- mismo puerto en PCAPdroid y en 'adb reverse'
PRINT_EVERY_S = 1.0

# Reloj por payload type (Opus suele 48000 Hz; WhatsApp usa dinámicos como 120)
CLOCK_BY_PT = {0:8000, 8:8000, 9:8000, 18:8000, 96:48000, 111:48000, 120:48000}
StreamKey = namedtuple("StreamKey", "src dst sport dport ssrc pt")

# Umbrales suaves para ver resultados rápido
MIN_PKTS_SHOW = 5          # no mostrar flujos con menos de N paquetes
WARMUP_PKTS  = 6           # no contar jitter/loss en los 1ros N paquetes
MAX_SEQ_GAP_FOR_LOSS = 1000
MAX_ABS_D_MULT = 8         # clamp: descarta outliers |D| > 8*clock (en "ticks" de códec)

# Detectar TShark
TSHARK_EXE = (
    os.environ.get("TSHARK_PATH")
    or shutil.which("tshark")
    or r"C:\Program Files\Wireshark\tshark.exe"
)

# Puertos a forzar como RTP (decode-as), útil para 3478/3479/5349
DEFAULT_FORCE_PORTS = [3478, 3479, 5349]
ENV_FORCE = os.environ.get("FORCE_RTP_PORTS")  # ej: "3478,3479"
if ENV_FORCE:
    try:
        FORCE_PORTS = [int(p.strip()) for p in ENV_FORCE.split(",") if p.strip()]
    except Exception:
        FORCE_PORTS = DEFAULT_FORCE_PORTS[:]
else:
    FORCE_PORTS = DEFAULT_FORCE_PORTS[:]

def start_tshark():
    if not (TSHARK_EXE and os.path.exists(TSHARK_EXE)):
        raise RuntimeError("No encuentro tshark. Define TSHARK_PATH o instala Wireshark/TShark.")

    # Construir args con decode-as en puertos típicos
    args = [TSHARK_EXE, "-r", "-",
            "-o", "rtp.heuristic_rtp:TRUE",
            "-Y", "rtp",
            "-T", "fields",
            "-e", "frame.time_epoch", "-e", "ip.src", "-e", "ip.dst",
            "-e", "udp.srcport", "-e", "udp.dstport", "-e", "rtp.ssrc",
            "-e", "rtp.seq", "-e", "rtp.timestamp", "-e", "rtp.p_type",
            "-E", "separator=,", "-E", "occurrence=f"]

    # Forzar decode-as RTP para puertos conocidos
    for p in FORCE_PORTS:
        args.extend(["-d", f"udp.port=={p},rtp"])

    return subprocess.Popen(
        args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        bufsize=1
    )

def feeder_socket_to_tshark(conn, tshark_proc, mon):
    """Recibe bytes del teléfono y los vuelca a tshark.stdin (binario)."""
    try:
        conn.settimeout(3)
        while True:
            try:
                chunk = conn.recv(16384)
            except socket.timeout:
                # No llegan bytes aún
                mon.report_no_bytes()
                continue
            if not chunk:
                break
            # Marcar que sí llegan bytes
            mon.report_bytes(len(chunk))
            tshark_proc.stdin.buffer.write(chunk)
            tshark_proc.stdin.flush()
    except Exception as e:
        print("[feeder] error:", e)
    finally:
        try: tshark_proc.stdin.close()
        except Exception: pass
        try: conn.close()
        except Exception: pass
        print("[feeder] conexión cerrada por el teléfono")

def parser_tshark_stdout(tshark_proc, stats, prev_pkt, lock, stop_evt, mon):
    """Lee líneas de tshark.stdout (bloqueante) y actualiza métricas."""
    while not stop_evt.is_set():
        line = tshark_proc.stdout.readline()
        if not line:
            break
        parts = line.strip().split(",")
        if len(parts) != 9 or "" in parts:
            continue

        # Marcar que vemos RTP
        mon.report_rtp_line()

        t = float(parts[0]); src=parts[1]; dst=parts[2]
        sport=int(parts[3]); dport=int(parts[4]); ssrc=parts[5]
        seq=int(parts[6]); ts=int(parts[7]); pt=int(parts[8])

        key = StreamKey(src,dst,sport,dport,ssrc,pt)

        with lock:
            st = stats[key]
            st["pt"] = pt
            st["recv"] += 1
            st["n"]    += 1

            prev = prev_pkt.get(key)
            if prev:
                # Warm-up: no calcular métricas en los primeros paquetes
                if st["n"] <= WARMUP_PKTS:
                    prev_pkt[key] = {"t": t, "seq": seq, "ts": ts}
                    continue

                # Pérdidas (con resync si el gap es enorme)
                delta_seq = (seq - prev["seq"]) & 0xFFFF
                if 1 < delta_seq <= MAX_SEQ_GAP_FOR_LOSS:
                    st["lost"] += (delta_seq - 1)

                # Jitter RFC3550 con clamp de outliers
                clock = CLOCK_BY_PT.get(pt, 48000)
                arrival_delta = (t - prev["t"]) * clock
                ts_delta = (ts - prev["ts"]) & 0xFFFFFFFF
                D = arrival_delta - ts_delta
                if abs(D) <= MAX_ABS_D_MULT * clock:
                    st["J"] += (abs(D) - st["J"]) / 16.0
                    if st["J"] > st["Jmax"]:
                        st["Jmax"] = st["J"]
            prev_pkt[key] = {"t": t, "seq": seq, "ts": ts}

def print_snapshot(stats, lock):
    out = []
    with lock:
        for k, s in list(stats.items()):
            if s["recv"] < MIN_PKTS_SHOW:
                continue
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

def print_summary(stats, lock):
    print("\n===== RESUMEN POR FLUJO RTP =====")
    printed = 0
    with lock:
        for k, s in stats.items():
            if s["recv"] < MIN_PKTS_SHOW:
                continue
            clock = CLOCK_BY_PT.get(s["pt"] or 96, 48000)
            exp = s["recv"] + s["lost"]
            loss_pct = (s["lost"]/exp*100.0) if exp else 0.0
            print(f"{k.src}:{k.sport}->{k.dst}:{k.dport} ssrc={k.ssrc} pt={s['pt']}")
            print(f"  pkts={s['recv']} lost%={loss_pct:.3f}  "
                  f"jitter_mean_ms={(s['J']/clock)*1000.0:.3f}  jitter_max_ms={(s['Jmax']/clock)*1000.0:.3f}")
            printed += 1
    if printed == 0:
        print("(sin flujos RTP válidos)")

class Monitor:
    """Imprime hints según estado: sin bytes / sin RTP / ok."""
    def __init__(self):
        self.bytes_total = 0
        self.rtp_lines   = 0
        self.last_bytes_ts = None
        self.last_rtp_ts   = None
        self.last_hint_ts  = 0

    def report_no_bytes(self):
        # solo marca tiempo; el timeout en feeder llama esto
        now = time.time()
        if self.last_bytes_ts is None:
            self.last_bytes_ts = 0  # "nunca"
        # hints los maneja el loop principal (según timestamps)

    def report_bytes(self, n):
        self.bytes_total += n
        self.last_bytes_ts = time.time()

    def report_rtp_line(self):
        self.rtp_lines += 1
        self.last_rtp_ts = time.time()

    def maybe_hint(self):
        now = time.time()
        if now - self.last_hint_ts < 2.5:
            return  # no spamear hints

        # Sin bytes aún
        if self.bytes_total == 0:
            print("[hint] Aún no recibo bytes del teléfono. ¿PCAPdroid en Start con VPN (llave) encendida?")
            self.last_hint_ts = now
            return

        # Con bytes pero sin RTP
        if self.bytes_total > 0 and self.rtp_lines == 0:
            print("[hint] Recibo bytes pero no veo RTP. Verifica:\n"
                  "       - PCAPdroid: Dump mode = 'TCP exporter (pcap-over-ip)' (no 'TCP/UDP exporter')\n"
                  "       - App filter = WhatsApp\n"
                  "       - Llamada de VOZ en curso (no solo señalización)")
            self.last_hint_ts = now

def main():
    print("[i] TShark:", TSHARK_EXE)
    if FORCE_PORTS:
        print("[i] decode-as RTP en puertos:", ",".join(str(p) for p in FORCE_PORTS))

    # Servidor TCP
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(1)
    print(f"[PC] Esperando conexión en {HOST}:{PORT} … (Start en PCAPdroid)")

    conn, addr = srv.accept()
    print(f"[PC] Cliente conectado desde {addr}")

    tshark = start_tshark()

    # Estado compartido
    stats = defaultdict(lambda: {"recv":0,"lost":0,"J":0.0,"Jmax":0.0,"pt":None,"n":0})
    prev_pkt = {}
    lock = threading.Lock()
    stop_evt = threading.Event()
    mon = Monitor()

    # Hilos
    t_feeder = threading.Thread(target=feeder_socket_to_tshark, args=(conn, tshark, mon), daemon=True)
    t_parser = threading.Thread(target=parser_tshark_stdout, args=(tshark, stats, prev_pkt, lock, stop_evt, mon), daemon=True)
    t_feeder.start()
    t_parser.start()

    # Impresión periódica
    try:
        last = time.time()
        while t_feeder.is_alive() or t_parser.is_alive():
            time.sleep(0.2)
            mon.maybe_hint()
            now = time.time()
            if now - last >= PRINT_EVERY_S:
                print_snapshot(stats, lock)
                last = now
    except KeyboardInterrupt:
        pass
    finally:
        stop_evt.set()
        try: tshark.terminate()
        except Exception: pass
        print_summary(stats, lock)

if __name__ == "__main__":
    main()
