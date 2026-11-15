# CCTV Monitoring Perhatian Siswa

## Instalasi
    python -m venv venv && venv\Scripts\activate     (Windows)
    pip install -r requirements.txt
## Menjalankan
1. Untuk menggunakan webcam laptop, biarkan `config.json` pada `source.type = "webcam"` dan `source.value = "0"` (kamera utama). Untuk kamera lain, coba indeks `1`.
2. Pastikan aplikasi lain seperti Zoom/Meet/Camera tidak sedang memakai webcam.
3. Jalankan `python run.py`
3. Laptop: http://localhost:8000  | Admin: http://localhost:8000/admin
4. HP (Wi-Fi sama): http://<IP-laptop>:8000  (cek `ipconfig`; izinkan port 8000 di Windows Firewall)
5. Login admin awal: `admin` / `admin123` (ubah di config.json SEBELUM run pertama), lalu klik "Mulai".
## Memilih sumber video
- Webcam laptop: Admin > Sumber > Webcam Laptop, isi `0`, klik `Set sumber`, lalu klik `Mulai`.
- Jika kamera utama tidak terbuka, coba indeks `1`.
- Video: pilih MP4 dan isi `videos/classroom.mp4`.
- CCTV IP: pilih RTSP dan isi URL stream, misalnya `rtsp://user:pass@192.168.1.x:554/stream1`.
- Di Windows, izinkan akses kamera untuk aplikasi desktop di Settings > Privacy & security > Camera.
- Jika webcam tetap gagal, tutup aplikasi lain yang memakai kamera dan periksa izin kamera Windows.
## Model
Pertama kali berjalan, `yolov8n-pose.pt` diunduh Ultralytics (butuh internet sekali; atau taruh di `models/`).
Orientasi saat ini = ATURAN heuristik atas keypoint pose (`backend/cv/orientation.py`), BUKAN model terlatih,
akurasi belum diuji. Untuk akurasi nyata: kumpulkan crop siswa dari kamera belakang berlabel 6 kelas, latih classifier,
ganti `classify()`.


## Statistik C300
Dashboard Admin dan Guest menampilkan rata-rata jumlah siswa yang terdeteksi menghadap papan tulis per menit. Nilai dihitung dari jumlah siswa menghadap depan pada setiap sampel pemrosesan dalam menit berjalan; riwayat admin menyimpan rata-rata tersebut per menit. Persentase kategori tetap tersedia di riwayat admin sebagai informasi tambahan.
