# Tugas Besar Jaringan Komputer – Client-Proxy-Server Socket-Based

## Deskripsi Proyek

Proyek ini merupakan implementasi sistem komunikasi **Client-Proxy-Web Server** berbasis socket (TCP/UDP) dalam satu jaringan. Proxy server berfungsi sebagai perantara yang menangani:

- **HTTP request** dari client ke web server (TCP port 8080)
- **Caching** konten statis (HIT/MISS)
- **Error handling** 502 (Bad Gateway) dan 504 (Gateway Timeout)
- **Multithreading** untuk menangani banyak client bersamaan
- **Quality of Service (QoS)** melalui protokol UDP (port 9090) dengan parameter yang dapat diatur (jumlah paket, interval, ukuran payload)
- **Logging** aktivitas dan penyimpanan hasil QoS ke file CSV

Proyek ini memenuhi spesifikasi tugas besar mata kuliah Jaringan Komputer – IFLAB Universitas Telkom.

---

## Struktur Folder
```
JARKOM_Client-Proxy-Server_Socket-Based/
├── code/
│   ├── client.py               # Script client (Mendukung TCP/UDP & Multi-client)
│   ├── proxy.py                # Core proxy server dengan multithreading & caching
│   ├── webserver.py            # Backend HTTP web server statis
│   └── proxy_cache_8080/       # Direktori lokal penyimpanan cache proxy (auto-generated)
├── test/                       # Root directory asset web statis untuk diserver
│   ├── assets/                 # Gambar dan file media pendukung (ex: .png, .mp4)
│   ├── css/                    # File stylesheet (style.css)
│   ├── status/                 # Halaman error kustom (404, 500, 502, 504)
│   ├── index.html              # Landing page utama server
│   ├── implementation.html     # Dokumentasi implementasi sistem
│   ├── osi.html                # Materi pembelajaran OSI Layer
│   ├── qos.html                # Materi Quality of Service
│   └── tcpip.html              # Materi TCP/IP Protocol
├── .gitignore                  # Konfigurasi pengecualian pelacakan Git (ex: *.mp4)
└── README.md                   # Dokumentasi proyek
```


---

## Persyaratan Sistem

- **Python 3.7+** (tidak perlu library tambahan selain standar)
- Sistem operasi: Windows / Linux / macOS
- Semua perangkat (client, proxy, web server) terhubung ke **Wi-Fi yang sama** untuk pengujian multi-laptop

---

## Cara Menjalankan

> **Urutan penting:** Web Server → Proxy Server → Client

### 1. Menjalankan Web Server

Buka terminal di folder `code/`:

```bash
python webserver.py --root ../test