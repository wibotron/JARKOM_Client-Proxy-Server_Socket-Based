"""
client.py - HTTP Client (TCP ke proxy) + UDP QoS Tester (ke proxy)
Tugas Besar Jaringan Komputer
"""

import socket
import time
import datetime
import argparse
import sys
import statistics
import csv
import os

# ─── KONFIGURASI DEFAULT ─────────────────────────────────────────────────────────
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 8080          # TCP proxy HTTP

PROXY_UDP_HOST = "127.0.0.1"
PROXY_UDP_PORT = 9090      # UDP proxy untuk QoS (sesuai spesifikasi)

BUFFER_SIZE = 4096
UDP_TIMEOUT = 1.0
UDP_COUNT = 10
UDP_INTERVAL = 0.5
UDP_PAYLOAD_SIZE = 64      # bytes, bisa diatur

CSV_FILENAME = "qos_results.csv"

def log(tag, message):
    ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{ts}] [{tag}] {message}")

def separator(char="─", width=60):
    print(char * width)

# ─── MODE TCP: HTTP CLIENT KE PROXY ─────────────────────────────────────────────
def http_get(proxy_host, proxy_port, url_path="/index.html"):
    separator()
    log("TCP", f"HTTP GET {url_path} → Proxy {proxy_host}:{proxy_port}")

    request = (
        f"GET {url_path} HTTP/1.1\r\n"
        f"Host: {proxy_host}:{proxy_port}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    ).encode("utf-8")

    t_send = time.time()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(10)
        s.connect((proxy_host, proxy_port))
        s.sendall(request)

        response = b""
        while True:
            chunk = s.recv(BUFFER_SIZE)
            if not chunk:
                break
            response += chunk
        s.close()
        t_recv = time.time()
        rtt = (t_recv - t_send) * 1000

        if b"\r\n\r\n" in response:
            header_part, body_part = response.split(b"\r\n\r\n", 1)
            status_line = header_part.decode("utf-8", errors="replace").split("\r\n")[0]
        else:
            body_part = response
            status_line = "Unknown"

        log("TCP", f"Status   : {status_line}")
        log("TCP", f"RTT      : {rtt:.2f} ms")
        log("TCP", f"Ukuran   : {len(response)} bytes")
        print(body_part.decode("utf-8", errors="replace")[:500])
        return True
    except Exception as e:
        log("TCP", f"ERROR: {e}")
        return False

# ─── MODE UDP: QoS TESTER KE PROXY ─────────────────────────────────────────────
def udp_qos_test(proxy_udp_host, proxy_udp_port, count=10, interval=0.5, payload_size=64):
    """
    Kirim paket UDP ke proxy, proxy akan forward ke webserver echo dan balik.
    Hitung RTT, loss, jitter, throughput.
    Simpan hasil ke CSV.
    """
    separator()
    log("UDP-QOS", f"Memulai UDP QoS Test ke Proxy {proxy_udp_host}:{proxy_udp_port}")
    log("UDP-QOS", f"Jumlah: {count} | Interval: {interval}s | Payload: {payload_size}B | Timeout: {UDP_TIMEOUT}s")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(UDP_TIMEOUT)

    rtt_list = []
    sent = 0
    received = 0
    total_bytes = 0
    test_start = time.time()
    results = []  # untuk CSV

    for seq in range(1, count + 1):
        t_send = time.time()
        payload = f"SEQ{seq} TS{t_send}".ljust(payload_size, 'X')[:payload_size].encode()
        try:
            sock.sendto(payload, (proxy_udp_host, proxy_udp_port))
            sent += 1

            data, _ = sock.recvfrom(BUFFER_SIZE)
            t_recv = time.time()
            rtt = (t_recv - t_send) * 1000
            rtt_list.append(rtt)
            received += 1
            total_bytes += len(data)
            log("UDP-QOS", f"Paket {seq:3d}: RTT = {rtt:.2f} ms | {len(data)}B")
            results.append((seq, rtt, len(data)))
        except socket.timeout:
            log("UDP-QOS", f"Paket {seq:3d}: TIMEOUT (packet loss)")
            results.append((seq, -1, 0))
        if seq < count:
            time.sleep(interval)

    test_duration = time.time() - test_start
    sock.close()

    # Statistik
    packet_loss = ((sent - received) / sent * 100) if sent > 0 else 100.0
    if rtt_list:
        rtt_min = min(rtt_list)
        rtt_avg = statistics.mean(rtt_list)
        rtt_max = max(rtt_list)
        if len(rtt_list) >= 2:
            diffs = [abs(rtt_list[i] - rtt_list[i-1]) for i in range(1, len(rtt_list))]
            jitter = statistics.stdev(diffs) if len(diffs) > 1 else diffs[0]
        else:
            jitter = 0.0
        throughput_kbps = (total_bytes * 8 / 1000) / test_duration if test_duration > 0 else 0
    else:
        rtt_min = rtt_avg = rtt_max = jitter = throughput_kbps = 0

    # Tampilkan di terminal
    separator("─")
    log("UDP-QOS", "── STATISTIK QoS ────────────────────────────────────")
    print(f"  Paket Dikirim   : {sent}")
    print(f"  Paket Diterima  : {received}")
    print(f"  Packet Loss     : {packet_loss:.1f}%")
    print(f"  RTT Min         : {rtt_min:.2f} ms")
    print(f"  RTT Avg         : {rtt_avg:.2f} ms")
    print(f"  RTT Max         : {rtt_max:.2f} ms")
    print(f"  Jitter          : {jitter:.2f} ms")
    print(f"  Throughput      : {throughput_kbps:.2f} kbps")
    print(f"  Durasi Tes      : {test_duration:.2f} s")
    separator()

    # ── SIMPAN KE CSV ──────────────────────────────────────────────────
    csv_exists = os.path.isfile(CSV_FILENAME)
    with open(CSV_FILENAME, mode='a', newline='') as csvfile:
        writer = csv.writer(csvfile)
        if not csv_exists:
            writer.writerow(["timestamp", "target", "count", "interval_s", "payload_size_B",
                             "sent", "received", "loss_percent", "rtt_min_ms", "rtt_avg_ms",
                             "rtt_max_ms", "jitter_ms", "throughput_kbps"])
        writer.writerow([
            datetime.datetime.now().isoformat(),
            f"{proxy_udp_host}:{proxy_udp_port}",
            count, interval, payload_size,
            sent, received, round(packet_loss, 2),
            round(rtt_min, 2), round(rtt_avg, 2), round(rtt_max, 2),
            round(jitter, 2), round(throughput_kbps, 2)
        ])
    log("UDP-QOS", f"Hasil QoS disimpan ke {CSV_FILENAME}")

    return rtt_list, packet_loss

# ─── MULTI-CLIENT CONCURRENT (untuk uji beban) ─────────────────────────────────
def multi_request(proxy_host, proxy_port, urls, concurrent=False):
    import threading
    if concurrent:
        log("TCP", f"MULTI-CLIENT: {len(urls)} request concurrent")
        threads = []
        results = [None] * len(urls)
        def worker(idx, url):
            results[idx] = http_get(proxy_host, proxy_port, url)
        for i, url in enumerate(urls):
            t = threading.Thread(target=worker, args=(i, url))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        log("TCP", f"Selesai: {sum(1 for r in results if r)}/{len(urls)} berhasil")
    else:
        for url in urls:
            http_get(proxy_host, proxy_port, url)

# ─── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Client TCP+UDP untuk Proxy")
    parser.add_argument("-mode", choices=["tcp", "udp", "both"], default="tcp")
    parser.add_argument("-url", default="/index.html")
    parser.add_argument("-proxy-host", default=PROXY_HOST)
    parser.add_argument("-proxy-port", type=int, default=PROXY_PORT, help="TCP port proxy")
    parser.add_argument("-proxy-udp-host", default=PROXY_UDP_HOST, help="UDP proxy host untuk QoS")
    parser.add_argument("-proxy-udp-port", type=int, default=PROXY_UDP_PORT, help="UDP proxy port untuk QoS")
    parser.add_argument("-count", type=int, default=UDP_COUNT, help="Jumlah paket UDP")
    parser.add_argument("-interval", type=float, default=UDP_INTERVAL, help="Interval antar paket (detik)")
    parser.add_argument("-size", type=int, default=UDP_PAYLOAD_SIZE, help="Ukuran payload UDP (bytes)")
    parser.add_argument("-multi", action="store_true", help="Multi-client concurrent (TCP)")

    args = parser.parse_args()

    print("\n" + "═" * 60)
    print(f"  CLIENT - Mode: {args.mode.upper()}")
    print("═" * 60 + "\n")

    if args.mode in ("tcp", "both"):
        if args.multi:
            # Simulasi 5 client
            urls = ["/index.html"] * 5
            multi_request(args.proxy_host, args.proxy_port, urls, concurrent=True)
        else:
            http_get(args.proxy_host, args.proxy_port, args.url)

    if args.mode in ("udp", "both"):
        udp_qos_test(args.proxy_udp_host, args.proxy_udp_port,
                     args.count, args.interval, args.size)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[CLIENT] Dihentikan.")
        sys.exit(0)