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
- ketik disemua laptop "ipconfig" -> Buat ngecek IP address laptop
- bagian web server ketik "python webserver.py --root ../test" -> Nyalain web server
- python proxy.py --server-host [IP_WEBSERVER] -> Nyalain proxy server, diarahkan ke IP laptop webserver biar bisa forward request kesana
- python client.py -url /index.html -proxy-host [IP proxy] -proxy-udp-host [IP proxy]
- python client.py -mode udp -proxy-udp-host [IP_PROXY] -> Tes mode UDP, ngirim paket QoS ke proxy buat ukur RTT, packet loss, jitter, throughput
- python client.py -multi -proxy-host [IP_PROXY] -> Tes multi-client, simulasi 5 client ngirim request bersamaan
  Tes Error 502
- webserver putus hubungan dengan proxy
- python client.py -url /index.html -proxy-host [IP_PROXY] -proxy-udp-host [IP_PROXY] -> Jalanin request TCP
- python client.py -url /osi.html -proxy-host [IP_PROXY] -proxy-udp-host [IP_PROXY] -> kalo misal osi.html
> **Urutan penting:** Web Server → Proxy Server → Client

### 1. Menjalankan Web Server

Buka terminal di folder `code/`:

```bash
python webserver.py --root ../test
