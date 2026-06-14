"""
webserver.py - HTTP Web Server + UDP Echo Server
Dengan root direktori ke folder test/ (agar struktur folder sesuai)
"""

import socket
import threading
import os
import sys
import datetime
import mimetypes

TCP_HOST = "0.0.0.0"
TCP_PORT = 8000
UDP_HOST = "0.0.0.0"
UDP_PORT = 9000
BUFFER_SIZE = 4096

# ==================== MODIFIKASI: Root folder ke ../test ====================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = os.path.join(SCRIPT_DIR, "..", "test")   # karena webserver.py di code/, test/ di parent
if not os.path.isdir(DEFAULT_ROOT):
    DEFAULT_ROOT = SCRIPT_DIR  # fallback ke direktori sendiri

request_count = 0
request_lock = threading.Lock()

def log(tag, message):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{ts}] [{tag}] {message}")

def get_content_type(filepath):
    mime, _ = mimetypes.guess_type(filepath)
    return mime or "application/octet-stream"

def build_response(status_code, status_text, body_bytes, content_type="text/html; charset=utf-8"):
    headers = (
        f"HTTP/1.1 {status_code} {status_text}\r\n"
        f"Content-Type: {content_type}\r\n"
        f"Content-Length: {len(body_bytes)}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    )
    return headers.encode("utf-8") + body_bytes

def load_error_page(code, root_dir):
    error_file = os.path.join(root_dir, "status", f"{code}.html")
    if os.path.isfile(error_file):
        with open(error_file, "rb") as f:
            return f.read()
    fallback = {
        403: b"<h1>403 Forbidden</h1>",
        404: b"<h1>404 Not Found</h1>",
        500: b"<h1>500 Internal Server Error</h1>",
    }
    return fallback.get(code, f"<h1>{code} Error</h1>".encode())

def handle_client(conn, addr, root_dir):
    global request_count
    with request_lock:
        request_count += 1
        req_no = request_count

    try:
        raw = b""
        conn.settimeout(5)
        while b"\r\n\r\n" not in raw:
            chunk = conn.recv(BUFFER_SIZE)
            if not chunk:
                break
            raw += chunk
        if not raw:
            conn.close()
            return

        request_line = raw.decode("utf-8", errors="replace").split("\r\n")[0]
        parts = request_line.split()
        if len(parts) < 2:
            conn.close()
            return
        method = parts[0]
        path = parts[1]
        log("HTTP", f"[REQ #{req_no}] {method} {path} dari {addr[0]}")

        if method != "GET":
            conn.sendall(build_response(405, "Method Not Allowed", b""))
            conn.close()
            return

        if path in ("/", ""):
            path = "/index.html"
        if "?" in path:
            path = path.split("?")[0]

        # Security: cegah path traversal
        filepath = os.path.normpath(os.path.join(root_dir, path.lstrip("/")))
        if not filepath.startswith(os.path.abspath(root_dir)):
            conn.sendall(build_response(403, "Forbidden", load_error_page(403, root_dir)))
            conn.close()
            return

        if os.path.isfile(filepath):
            with open(filepath, "rb") as f:
                body = f.read()
            ct = get_content_type(filepath)
            conn.sendall(build_response(200, "OK", body, ct))
            log("HTTP", f"[REQ #{req_no}] 200 OK {path} ({len(body)}B)")
        else:
            conn.sendall(build_response(404, "Not Found", load_error_page(404, root_dir)))
            log("HTTP", f"[REQ #{req_no}] 404 NOT FOUND {path}")
    except Exception as e:
        log("HTTP", f"[REQ #{req_no}] ERROR: {e}")
        try:
            conn.sendall(build_response(500, "Internal Error", load_error_page(500, root_dir)))
        except:
            pass
    finally:
        conn.close()

def start_tcp_server(root_dir):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((TCP_HOST, TCP_PORT))
    server.listen(100)
    log("TCP", f"HTTP Server di {TCP_HOST}:{TCP_PORT}, root = {root_dir}")
    while True:
        try:
            conn, addr = server.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr, root_dir), daemon=True)
            t.start()
        except KeyboardInterrupt:
            server.close()
            break

def start_udp_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_HOST, UDP_PORT))
    log("UDP", f"Echo Server di {UDP_HOST}:{UDP_PORT}")
    while True:
        try:
            data, addr = sock.recvfrom(BUFFER_SIZE)
            sock.sendto(data, addr)
            log("UDP", f"Echo {len(data)}B ke {addr[0]}:{addr[1]}")
        except KeyboardInterrupt:
            sock.close()
            break

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=DEFAULT_ROOT, help="Root direktori web server (default: ../test)")
    args = parser.parse_args()

    root_dir = os.path.abspath(args.root)
    if not os.path.isdir(root_dir):
        print(f"ERROR: Root directory {root_dir} tidak ditemukan. Gunakan --root", file=sys.stderr)
        sys.exit(1)

    log("MAIN", "=" * 60)
    log("MAIN", f"Web Server - Root: {root_dir}")
    log("MAIN", f"TCP HTTP port {TCP_PORT} | UDP echo port {UDP_PORT}")
    log("MAIN", "=" * 60)

    udp_thread = threading.Thread(target=start_udp_server, daemon=True)
    udp_thread.start()

    try:
        start_tcp_server(root_dir)
    except KeyboardInterrupt:
        log("MAIN", "Server dimatikan.")
        sys.exit(0)