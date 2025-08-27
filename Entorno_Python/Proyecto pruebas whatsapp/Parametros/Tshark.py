# pcap_server_to_tshark.py
# PC escucha por TCP, recibe PCAP desde el teléfono (PCAPdroid en modo "exporter cliente"),
# lo alimenta a TShark por stdin y calcula jitter/loss por flujo RTP en tiempo casi real.
# Incluye filtro "sólo WhatsApp" en el RESUMEN final (y opcional en realtime).

import os, shutil, socket, subprocess, threading, time
from collections import defaultdict, namedtuple

HOST = "127.0.0.1"
PORT = 11111
PRINT_EVERY_S = 1.0

# Reloj por payload type (Opus ~ 48000 Hz)
CLOCK_BY_PT = {0:8000, 8:8000, 9:8000, 18:8000, 96:48000, 111:48000, 120:48000}
StreamKey = namedtuple("StreamKey", "src dst sport dport ssrc pt")

# -------- Config de filtrado WhatsApp --------
# Sólo aplicar filtro en RESUMEN final (por defecto ON)
FILTER_SUMMARY_ONLY = os.getenv("WA_SUMMARY_ONLY", "1") == "1"
# Aplicar filtro también en tiempo real (por defecto OFF)
FILTER_REALTIME = os.getenv("WA_REALTIME_ONLY", "0") == "1"
# No mostrar flujos muy cortos en el resumen (para evitar "probes")
MIN_PKTS_SHOW = int(os.getenv("MIN_PKTS_SHOW", "20"))

# Rangos IPv4 asociados a Meta/WhatsApp (AS32934)
WHATSAPP_NETS = [
    "157.240.0.0/16",
    "31.13.64.0/18",
    "31.13.24.0/21",
    "185.60.216.0/22",
    "66.220.144.0/20",
    "69.171.224.0/19",
    "69.63.176.0/20",
    "173.252.64.0/18",
    "204.15.20.0/22",
]

def _ip2int(ip):
    try:
        a,b,c,d = (int(x) for x in ip.split("."))
        return (a<<24)|(b<<16)|(c<<8)|d
    except Exception:
        return None

def _parse_cidr(cidr):
    base, bits = cidr.split("/")
    bits = int(bits)
    base_i = _ip2int(base)
    mask = (0xFFFFFFFF << (32 - bits)) & 0xFFFFFFFF
    return base_i, mask

NETS_META = [_parse_cidr(c) for c in WHATSAPP_NETS]

def _in_meta_nets(ip):
    ip_i = _ip2int(ip)
    if ip_i is None:
        return False
    for base, mask in NETS_META:
        if base is not None and (ip_i & mask) == (base & mask):
            return True
    return False

# -------- TShark detection --------
TSHARK_EXE = (
    os.environ.get("TSHARK_PATH")
    or shutil.which("tshark")
    or r"C:\Program Files\Wireshark\tshark.exe"
)

def start_tshark():
    if not (TSHARK_EXE and os.path.exists(TSHARK_EXE)):
        raise RuntimeError("No encuentro tshark. Define TSHARK_PATH o instala Wireshark/TShark.")
    print("[i] decode-as RTP en puertos: 3478,3479,5349")
    return subprocess.Popen(
        [
            TSHARK_EXE, "-r", "-",
            "-o","rtp.heuristic_rtp:TRUE",
            # Fuerza decodificar RTP en puertos típicos de STUN/TURN usados por WhatsApp
            "-d","udp.port==3478,rtp", "-d","udp.port==3479,rtp", "-d","udp.port==5349,rtp",
            "-Y","rtp","-T","fields",
            "-e","frame.time_epoch","-e","ip.src","-e","ip.dst",
            "-e","udp.srcport","-e","udp.dstport","-e","rtp.ssrc",
            "-e","rtp.seq","-e","rtp.timestamp","-e","rtp.p_type",
            "-E","separator=,","-E","occurrence=f"
        ],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1
    )

def feeder_socket_to_tshark(conn, tshark_proc):
    try:
        conn.settimeout(10)
        while True:
            chunk = conn.recv(16384)
            if not chunk:
                break
            tshark_proc.stdin.buffer.write(chunk)
            tshark_proc.stdin.flush()
    except Exception as e:
        print("[feeder] error:", e)
    finally:
        try: tshark_proc.stdin.close()
        except Exception: pass
        try: conn.close()
        except Exception: pass

def parser_tshark_stdout(tshark_proc, stats, prev_pkt, lock, stop_evt, wa_ssrcs):
    last_any = time.time()
    while not stop_evt.is_set():
        line = tshark_proc.stdout.readline()
        if not line:
            # si no hay líneas, imprime hints cada 3 s mientras llegan bytes por feeder
            if time.time() - last_any > 3.0:
                print("[hint] Recibo bytes pero no veo RTP. Verifica:")
                print("       - PCAPdroid: Dump mode = 'TCP exporter (pcap-over-ip)' (no 'TCP/UDP exporter')")
                print("       - App filter = WhatsApp")
                print("       - Llamada de VOZ en curso (no solo señalización)")
                last_any = time.time()
            time.sleep(0.05)
            continue

        parts = line.strip().split(",")
        if len(parts) != 9 or "" in parts:
            continue

        t = float(parts[0]); src=parts[1]; dst=parts[2]
        sport=int(parts[3]); dport=int(parts[4]); ssrc=parts[5]
        seq=int(parts[6]); ts=int(parts[7]); pt=int(parts[8])

        # Si uno de los extremos es Meta, marca el SSRC como "de WhatsApp"
        if _in_meta_nets(src) or _in_meta_nets(dst):
            wa_ssrcs.add(ssrc)

        key = StreamKey(src,dst,sport,dport,ssrc,pt)
        with lock:
            st = stats[key]
            st.setdefault("pt", pt)
            st.setdefault("recv", 0)
            st.setdefault("lost", 0)
            st.setdefault("J", 0.0)
            st.setdefault("Jmax", 0.0)
            st["recv"] += 1

            prev = prev_pkt.get(key)
            if prev:
                # Pérdidas por salto de secuencia (wrap 16 bits)
                delta_seq = (seq - prev["seq"]) & 0xFFFF
                if delta_seq > 1:
                    st["lost"] += (delta_seq - 1)

                # Jitter RFC3550
                clock = CLOCK_BY_PT.get(pt, 48000)
                arrival_delta = (t - prev["t"]) * clock
                ts_delta = (ts - prev["ts"]) & 0xFFFFFFFF
                D = arrival_delta - ts_delta
                st["J"] += (abs(D) - st["J"]) / 16.0
                if st["J"] > st["Jmax"]:
                    st["Jmax"] = st["J"]

            prev_pkt[key] = {"t": t, "seq": seq, "ts": ts}
            last_any = time.time()

def _should_show_whatsapp(k, s, wa_ssrcs):
    """Regla de inclusión 'WhatsApp': IP Meta o SSRC observado con IP Meta."""
    return (_in_meta_nets(k.src) or _in_meta_nets(k.dst) or (k.ssrc in wa_ssrcs))

def print_snapshot(stats, lock, wa_ssrcs):
    with lock:
        out = []
        for k, s in list(stats.items()):
            if FILTER_REALTIME and not _should_show_whatsapp(k, s, wa_ssrcs):
                continue
            clock = CLOCK_BY_PT.get(s.get("pt") or 96, 48000)
            exp = s.get("recv",0) + s.get("lost",0)
            loss_pct = (s.get("lost",0)/exp*100.0) if exp else 0.0
            out.append({
                "flow": f"{k.src}:{k.sport}->{k.dst}:{k.dport} ssrc={k.ssrc} pt={s.get('pt')}",
                "pkts": s.get("recv",0),
                "loss_pct": round(loss_pct,3),
                "jitter_mean_ms": round((s.get("J",0.0)/clock)*1000.0,3),
                "jitter_max_ms":  round((s.get("Jmax",0.0)/clock)*1000.0,3),
            })
    if out:
        print("[REALTIME]", out)

def print_summary(stats, lock, wa_ssrcs):
    print("\n===== RESUMEN POR FLUJO RTP =====")
    printed = 0
    with lock:
        for k, s in stats.items():
            if FILTER_SUMMARY_ONLY and not _should_show_whatsapp(k, s, wa_ssrcs):
                continue
            if s.get("recv",0) < MIN_PKTS_SHOW:
                continue
            clock = CLOCK_BY_PT.get(s.get("pt") or 96, 48000)
            exp = s.get("recv",0) + s.get("lost",0)
            loss_pct = (s.get("lost",0)/exp*100.0) if exp else 0.0
            print(f"{k.src}:{k.sport}->{k.dst}:{k.dport} ssrc={k.ssrc} pt={s.get('pt')}")
            print(f"  pkts={s.get('recv',0)} lost%={loss_pct:.3f}  "
                  f"jitter_mean_ms={(s.get('J',0.0)/clock)*1000.0:.3f}  "
                  f"jitter_max_ms={(s.get('Jmax',0.0)/clock)*1000.0:.3f}")
            printed += 1
    if printed == 0:
        if FILTER_SUMMARY_ONLY:
            print("(sin flujos RTP válidos / WhatsApp)")
        else:
            print("(sin flujos RTP válidos)")

def main():
    print("[i] TShark:", TSHARK_EXE)
    if FILTER_SUMMARY_ONLY:
        print("[i] Resumen filtrado a WhatsApp (WA_SUMMARY_ONLY=1).")
    if FILTER_REALTIME:
        print("[i] Realtime filtrado a WhatsApp (WA_REALTIME_ONLY=1).")

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
    stats = defaultdict(dict)
    prev_pkt = {}
    lock = threading.Lock()
    stop_evt = threading.Event()
    wa_ssrcs = set()   # SSRCs "marcados" como WhatsApp

    # Hilos
    t_feeder = threading.Thread(target=feeder_socket_to_tshark, args=(conn, tshark), daemon=True)
    t_parser = threading.Thread(target=parser_tshark_stdout, args=(tshark, stats, prev_pkt, lock, stop_evt, wa_ssrcs), daemon=True)
    t_feeder.start()
    t_parser.start()

    # Impresión periódica
    try:
        last = time.time()
        while t_feeder.is_alive() or t_parser.is_alive():
            time.sleep(0.1)
            now = time.time()
            if now - last >= PRINT_EVERY_S:
                print_snapshot(stats, lock, wa_ssrcs)
                last = now
    except KeyboardInterrupt:
        pass
    finally:
        stop_evt.set()
        try: tshark.terminate()
        except Exception: pass
        print_summary(stats, lock, wa_ssrcs)

if __name__ == "__main__":
    main()
