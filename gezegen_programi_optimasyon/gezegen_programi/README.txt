SAMANYOLU 3B GEZEGEN LABORATUVARI

Baslatma: calistir.bat
Ana giris: main.py

Klasorler:
  core/         Simulasyon, sahne, arayuz, doku, ses ve yapay zeka modulleri
  assets/       Logo ve ses dosyalari
  data/         Ozel gezegen verileri (JSON)
  docs/         Tanitim ve proje belgeleri
  gezegenler/   Hazir gezegen tanimlari

Performans: deterministik gezegen dokulari ayni parametrelerle tekrar
uretilmez; oturum ici onbellekten kullanilir. Mevcut ozellikler ve ana
calistirma giris noktasi (main.py) korunmustur.


YILDIZ SISTEMI SECIMI
Acilis animasyonundan sonra sistem secim menusu acilir:
  - Gunes Sistemi
  - Alpha Centauri (Proxima Centauri b ve d)
  - TRAPPIST-1 (7 gezegen)
  - Kepler-90 (8 gezegen)

Simulasyonun ust cubugundaki "Sistem Secimi" dugmesiyle bu menu
yeniden acilabilir. Otegezegenlerin olcekleri 3B goruntuleme icin
uyarlanmistir; yildizlar arasi ve gezegenler arasi uzakliklar gercek
uzay olceginde temsil edilmez.


ARKA PLAN MUZIGI (SUNO)
1. Suno'dan indirdiginiz muzik dosyasini assets klasorune kopyalayin.
2. Dosya adini uzay_muzigi.mp3 yapin (OGG/WAV da desteklenir).
3. Program acildiginda muzik otomatik calar ve donguye girer.
4. Ayarlar menusunden muzigi kapatabilir ve ses seviyesini degistirebilirsiniz.
5. Muzik dosyasi yoksa program normal sekilde calismaya devam eder.

Muzik yonetimi core/muzik.py dosyasindadir.
