```python
import pygame
import random
import math

pygame.init()

# Ekran ayarları
GENISLIK = 1000
YUKSEKLIK = 700

ekran = pygame.display.set_mode((GENISLIK, YUKSEKLIK))
pygame.display.set_caption("Samanyolu Gezegenleri Simülasyonu")

saat = pygame.time.Clock()

# Renkler
SIYAH = (0, 0, 10)
BEYAZ = (255, 255, 255)
MAVI = (80, 180, 255)
ALTIN = (255, 205, 90)

# Proje bilgileri
PROJE_ADI = "Samanyolu Gezegenleri Simülasyonu"
OKUL = "Bozok Üniversitesi"
BIRIM = "Boğazlıyan Meslek Yüksek Okulu"
BOLUM = "Bilgisayar Programcılığı"
PROJE_LIDERI = "Hüseyin Solak"

EKIP = [
    "Elif Özen",
    "Burçin Karakuş",
    "Hüseyin Solak",
    "Sıla Nur Çetinol",
    "Oğuzhan Öcal",
]

# Yazı tipleri
baslik_font = pygame.font.SysFont("arial", 36, bold=True)
bilgi_font = pygame.font.SysFont("arial", 21)
isim_font = pygame.font.SysFont("arial", 30, bold=True)
alt_font = pygame.font.SysFont("arial", 18)

# Yıldızları oluştur
yildizlar = []

for _ in range(180):
    yildizlar.append({
        "x": random.randint(0, GENISLIK),
        "y": random.randint(0, YUKSEKLIK),
        "hiz": random.uniform(0.7, 3.5),
        "boyut": random.choice([1, 1, 2, 2, 3])
    })

# Ekip isimlerinin animasyon konumu
isim_y = float(YUKSEKLIK + 50)
isim_araligi = 75
toplam_yukseklik = len(EKIP) * isim_araligi

calisiyor = True

while calisiyor:
    dt = min(saat.tick(60) / 16.67, 2.0)

    for olay in pygame.event.get():
        if olay.type == pygame.QUIT:
            calisiyor = False

        if olay.type == pygame.KEYDOWN:
            if olay.key == pygame.K_ESCAPE:
                calisiyor = False

    # Arka plan
    ekran.fill(SIYAH)

    # Yıldız hareketleri
    for yildiz in yildizlar:
        yildiz["y"] -= yildiz["hiz"] * dt

        if yildiz["y"] < 0:
            yildiz["y"] = YUKSEKLIK
            yildiz["x"] = random.randint(0, GENISLIK)

        pygame.draw.circle(
            ekran,
            BEYAZ,
            (int(yildiz["x"]), int(yildiz["y"])),
            yildiz["boyut"]
        )

    # Proje başlığı
    baslik = baslik_font.render(PROJE_ADI, True, ALTIN)
    ekran.blit(
        baslik,
        baslik.get_rect(center=(GENISLIK // 2, 55))
    )

    # Üniversite bilgileri
    okul_yazi = bilgi_font.render(OKUL, True, BEYAZ)
    birim_yazi = bilgi_font.render(BIRIM, True, BEYAZ)

    ekran.blit(
        okul_yazi,
        okul_yazi.get_rect(center=(GENISLIK // 2, 100))
    )

    ekran.blit(
        birim_yazi,
        birim_yazi.get_rect(center=(GENISLIK // 2, 130))
    )

    if BOLUM:
        bolum_yazi = bilgi_font.render(BOLUM, True, MAVI)
        ekran.blit(
            bolum_yazi,
            bolum_yazi.get_rect(center=(GENISLIK // 2, 160))
        )

    # Uzayda ilerleyen ekip isimleri
    for i, isim in enumerate(EKIP):
        y = isim_y + i * isim_araligi

        if -50 < y < YUKSEKLIK + 50:
            # Ekranın ortasına yaklaşırken büyüyen yazı efekti
            merkez_mesafesi = abs(y - YUKSEKLIK * 0.55)
            olcek = max(0.65, 1.0 - merkez_mesafesi / 1000)

            font_boyutu = max(16, int(30 * olcek))
            animasyon_font = pygame.font.SysFont(
                "arial",
                font_boyutu,
                bold=True
            )

            # Kenarlarda solan görünüm
            alfa = max(
                0,
                min(255, int(255 * (1 - merkez_mesafesi / 450)))
            )

            metin = animasyon_font.render(isim, True, MAVI)
            metin.set_alpha(alfa)

            metin_rect = metin.get_rect(
                center=(GENISLIK // 2, int(y))
            )

            ekran.blit(metin, metin_rect)

    # Animasyonun yukarı doğru ilerlemesi
    isim_y -= 1.2 * dt

    # Ekip listesinin tamamı geçince animasyonu baştan başlat
    if isim_y + toplam_yukseklik < -50:
        isim_y = float(YUKSEKLIK + 50)

    # Proje lideri
    lider = alt_font.render(
        "Proje Lideri: " + PROJE_LIDERI,
        True,
        ALTIN
    )

    ekran.blit(
        lider,
        lider.get_rect(center=(GENISLIK // 2, YUKSEKLIK - 35))
    )

    pygame.display.flip()

pygame.quit()
```