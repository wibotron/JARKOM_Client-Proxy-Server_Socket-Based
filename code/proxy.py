"""
proxy.py - Proxy Server dengan Caching, Multithreading, Error Handling, dan QoS UDP
Tugas Besar Jaringan Komputer - Client-Proxy-Server
"""

import socket
import threading
import datetime
import os
import sys
import time

# ─── KONFIGURASI DEFAULT ─────────────────────────────────────────────────────────
PROXY_HOST  = "0.0.0.0"
PROXY_PORT  = 8080          # TCP untuk HTTP
PROXY_UDP_PORT = 9090       # UDP untuk QoS (sesuai spesifikasi)

SERVER_HOST = "127.0.0.1"   # IP Web Server (HTTP)
SERVER_PORT = 8000
SERVER_UDP_PORT = 9000      # UDP echo server di webserver

BUFFER_SIZE    = 4096
SERVER_TIMEOUT = 5          # detik timeout untuk HTTP ke web server
UDP_TIMEOUT    = 2          # timeout untuk forward UDP ke webserver

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "proxy_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

cache_lock    = threading.Lock()
stats_lock    = threading.Lock()

# ─── STATISTIK GLOBAL ────────────────────────────────────────────────────────────
stats = {
    "total_req"  : 0,
    "cache_hit"  : 0,
    "cache_miss" : 0,
    "err_502"    : 0,
    "err_504"    : 0,
    "forwarded"  : 0,
    "udp_packets": 0,       # tambahan untuk UDP QoS
}

# ─── UTILITAS ───────────────────────────────────────────────────────────────────
def log(tag, message):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    thread = threading.current_thread().name
    print(f"[{ts}] [{tag}] [{thread}] {message}", flush=True)

def print_stats():
    log("STATS", "─" * 50)
    log("STATS", f"  Total Request  : {stats['total_req']}")
    log("STATS", f"  Cache HIT      : {stats['cache_hit']}")
    log("STATS", f"  Cache MISS     : {stats['cache_miss']}")
    log("STATS", f"  Forwarded OK   : {stats['forwarded']}")
    log("STATS", f"  Error 502      : {stats['err_502']}")
    log("STATS", f"  Error 504      : {stats['err_504']}")
    log("STATS", f"  UDP Packets    : {stats['udp_packets']}")
    log("STATS", "─" * 50)

# ─── CACHE HELPERS ───────────────────────────────────────────────────────────────
def url_to_cache_path(url_path):
    safe = url_path.lstrip("/").replace("/", "_").replace("?", "_").replace("&", "_")
    if not safe:
        safe = "index.html"
    return os.path.join(CACHE_DIR, safe)

def cache_exists(url_path):
    return os.path.isfile(url_to_cache_path(url_path))

def read_cache(url_path):
    with open(url_to_cache_path(url_path), "rb") as f:
        return f.read()

def write_cache(url_path, data):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(url_to_cache_path(url_path), "wb") as f:
        f.write(data)

# ─── ERROR PAGE ──────────────────────────────────────────────────────────────────
def load_error_page(code):
    path = os.path.join(BASE_DIR, "status", f"{code}.html")
    if os.path.isfile(path):
        with open(path, "rb") as f:
            return f.read()
    fallback = {
        400: b"<h1>400 Bad Request</h1>",
        502: b"<h1>502 Bad Gateway</h1><p>Web server tidak merespons dengan benar.</p>",
        504: b"<h1>504 Gateway Timeout</h1><p>Web server tidak merespons dalam batas waktu.</p>",
    }
    return fallback.get(code, f"<h1>{code} Error</h1>".encode())

def build_error_response(code, text):
    body = load_error_page(code)
    header = (
        f"HTTP/1.1 {code} {text}\r\n"
        f"Content-Type: text/html; charset=utf-8\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    ).encode("utf-8")
    return header + body

# ─── FORWARD KE WEB SERVER (HTTP) ───────────────────────────────────────────────
def forward_to_server(request_data, url_path, req_no):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(SERVER_TIMEOUT)
        s.connect((SERVER_HOST, SERVER_PORT))
        log("FORWARD", f"[REQ #{req_no}] Terhubung ke {SERVER_HOST}:{SERVER_PORT}")
        s.sendall(request_data)

        response = b""
        while True:
            chunk = s.recv(BUFFER_SIZE)
            if not chunk:
                break
            response += chunk
        s.close()

        if not response:
            return None, 502
        return response, None
    except socket.timeout:
        return None, 504
    except Exception:
        return None, 502

# ─── PARSE REQUEST ───────────────────────────────────────────────────────────────
def parse_request(raw):
    text = raw.decode("utf-8", errors="replace")
    first_line = text.split("\r\n")[0]
    parts = first_line.split()
    if len(parts) < 2:
        raise ValueError(f"Request line invalid: {first_line!r}")
    return parts[0], parts[1]

# ─── HANDLER PER CLIENT (TCP) ────────────────────────────────────────────────────
def handle_client(client_conn, client_addr):
    with stats_lock:
        stats["total_req"] += 1
        req_no = stats["total_req"]

    log("PROXY", f"[REQ #{req_no}] ▶ Koneksi TCP dari {client_addr[0]}:{client_addr[1]}")
    start_time = datetime.datetime.now()

    try:
        raw_request = b""
        client_conn.settimeout(5)
        while b"\r\n\r\n" not in raw_request:
            chunk = client_conn.recv(BUFFER_SIZE)
            if not chunk:
                break
            raw_request += chunk

        if not raw_request:
            client_conn.close()
            return

        method, url_path = parse_request(raw_request)
        log("PROXY", f"[REQ #{req_no}] {method} {url_path}")

        with cache_lock:
            hit = cache_exists(url_path)

        if hit:
            cached_response = read_cache(url_path)
            elapsed = (datetime.datetime.now() - start_time).total_seconds() * 1000
            with stats_lock:
                stats["cache_hit"] += 1
            log("CACHE", f"[REQ #{req_no}] ✔ HIT  {url_path} | {len(cached_response)}B | {elapsed:.1f}ms")
            client_conn.sendall(cached_response)
        else:
            with stats_lock:
                stats["cache_miss"] += 1
            log("CACHE", f"[REQ #{req_no}] ✘ MISS {url_path} → forward")

            response, err_code = forward_to_server(raw_request, url_path, req_no)

            if err_code == 504:
                with stats_lock:
                    stats["err_504"] += 1
                client_conn.sendall(build_error_response(504, "Gateway Timeout"))
                log("PROXY", f"[REQ #{req_no}] ⚠ 504 Gateway Timeout")
                print_stats()
                return
            if err_code == 502:
                with stats_lock:
                    stats["err_502"] += 1
                client_conn.sendall(build_error_response(502, "Bad Gateway"))
                log("PROXY", f"[REQ #{req_no}] ⚠ 502 Bad Gateway")
                print_stats()
                return

            first_line = response.split(b"\r\n")[0].decode("utf-8", errors="replace")
            if "200" in first_line:
                write_cache(url_path, response)
                log("CACHE", f"[REQ #{req_no}] ✔ STORED {url_path}")
            with stats_lock:
                stats["forwarded"] += 1

            elapsed = (datetime.datetime.now() - start_time).total_seconds() * 1000
            log("PROXY", f"[REQ #{req_no}] ✔ Selesai | {len(response)}B | {elapsed:.1f}ms")
            client_conn.sendall(response)

    except Exception as e:
        log("PROXY", f"[REQ #{req_no}] ERROR: {e}")
        try:
            client_conn.sendall(build_error_response(502, "Bad Gateway"))
        except:
            pass
    finally:
        client_conn.close()
        if stats["total_req"] % 5 == 0:
            print_stats()

# ==================== MODIFIKASI: UDP QoS SERVER ====================
def udp_qos_server(udp_port, server_udp_host, server_udp_port):
    """
    Menerima paket UDP dari client, meneruskan ke web server UDP echo,
    lalu mengembalikan balasan ke client.
    Alur: Client -> Proxy (UDP) -> Web Server (UDP) -> Proxy -> Client
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", udp_port))
    log("UDP-QOS", f"Listening UDP QoS on port {udp_port} (forward ke {server_udp_host}:{server_udp_port})")

    while True:
        try:
            data, client_addr = sock.recvfrom(BUFFER_SIZE)
            with stats_lock:
                stats["udp_packets"] += 1

            log("UDP-QOS", f"Terima {len(data)}B dari {client_addr[0]}:{client_addr[1]}")

            # Forward ke web server UDP
            try:
                forward_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                forward_sock.settimeout(UDP_TIMEOUT)
                forward_sock.sendto(data, (server_udp_host, server_udp_port))
                response, _ = forward_sock.recvfrom(BUFFER_SIZE)
                forward_sock.close()

                # Kirim balasan ke client
                sock.sendto(response, client_addr)
                log("UDP-QOS", f"Balas {len(response)}B ke {client_addr[0]}:{client_addr[1]} (via webserver echo)")
            except socket.timeout:
                log("UDP-QOS", f"Timeout forward ke webserver UDP, paket dari {client_addr} hilang")
                # Tidak mengirim balasan -> client akan anggap packet loss
            except Exception as e:
                log("UDP-QOS", f"Error forward UDP: {e}")
        except Exception as e:
            log("UDP-QOS", f"Loop error: {e}")

# ─── MAIN PROXY (TCP + UDP) ──────────────────────────────────────────────────────
def start_proxy(tcp_port, udp_port, server_host, server_port, server_udp_port):
    # Jalankan UDP QoS server di thread terpisah
    udp_thread = threading.Thread(
        target=udp_qos_server,
        args=(udp_port, server_host, server_udp_port),
        daemon=True,
        name="UDP-QoS-Thread"
    )
    udp_thread.start()

    # TCP Server untuk HTTP proxy
    tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcp_server.bind((PROXY_HOST, tcp_port))
    tcp_server.listen(100)

    log("PROXY", "=" * 60)
    log("PROXY", f"  Proxy Server - Dengan QoS UDP")
    log("PROXY", f"  TCP HTTP Proxy : {PROXY_HOST}:{tcp_port}")
    log("PROXY", f"  UDP QoS Proxy  : {PROXY_HOST}:{udp_port} (forward ke {server_host}:{server_udp_port})")
    log("PROXY", f"  Web Server HTTP: {server_host}:{server_port}")
    log("PROXY", "=" * 60)
    log("PROXY", "  Siap menerima koneksi...")

    while True:
        try:
            conn, addr = tcp_server.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()
        except KeyboardInterrupt:
            log("PROXY", "Menghentikan proxy...")
            print_stats()
            tcp_server.close()
            break
        except Exception as e:
            log("PROXY", f"ERROR accept: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Proxy Server - IFLAB")
    parser.add_argument("--port", type=int, default=PROXY_PORT, help=f"TCP port proxy (default: {PROXY_PORT})")
    parser.add_argument("--udp-port", type=int, default=PROXY_UDP_PORT, help=f"UDP port untuk QoS (default: {PROXY_UDP_PORT})")
    parser.add_argument("--server-host", default=SERVER_HOST, help=f"IP Web Server (default: {SERVER_HOST})")
    parser.add_argument("--server-port", type=int, default=SERVER_PORT, help=f"HTTP port Web Server (default: {SERVER_PORT})")
    parser.add_argument("--server-udp-port", type=int, default=SERVER_UDP_PORT, help=f"UDP port Web Server untuk echo (default: {SERVER_UDP_PORT})")
    args = parser.parse_args()

    CACHE_DIR = os.path.join(BASE_DIR, f"proxy_cache_{args.port}")
    os.makedirs(CACHE_DIR, exist_ok=True)

    try:
        start_proxy(args.port, args.udp_port, args.server_host, args.server_port, args.server_udp_port)
    except KeyboardInterrupt:
        sys.exit(0)