# Gezegen Savaşı — 3B uzay strateji oyunu

Bu oyun, mevcut **Samanyolu 3B Gezegen Laboratuvarı** projesindeki teknolojiyle uyumlu olacak şekilde **Python + Ursina Engine** kullanılarak hazırlanmıştır.

## Kurulum

1. Bilgisayarında Python 3.10 veya üzeri kurulu olsun.
2. Bu klasörü aç.
3. `kurulum.bat` dosyasına çift tıkla veya terminalde:
   ```bash
   python -m pip install -r requirements.txt
   ```
4. `oyunu_baslat.bat` dosyasına çift tıkla veya:
   ```bash
   python gezegen_savasi.py
   ```

## Oynanış

- **Mavi takım sensin**, kırmızı takım bilgisayar rakibidir.
- Önce mavi bir gezegene tıkla (filonun kalkış noktası).
- Sonra hedef gezegene tıkla.
- `FİLO GÖNDER` düğmesine veya klavyedeki **F** tuşuna bas.
- `+` ve `−` ile gönderilecek filo büyüklüğünü ayarla.
- Gezegenler zamanla güç üretir.
- Düşman gezegeninin gücü saldırıyla azaldıkça rengi koyulaşır. Gücü sıfırlanırsa gezegen ele geçirilir ve takım rengini alır.
- Bilgisayar rakibi yaklaşık her 8 saniyede bir saldırı yapar.
- Amaç kırmızı takımın bütün gezegenlerini ele geçirmek.

## Proje dosyaları

- `gezegen_savasi.py` — oyunun tamamı
- `requirements.txt` — gerekli Python paketi
- `oyunu_baslat.bat` — oyunu çalıştırır
- `kurulum.bat` — Ursina'yı kurar

## Not

Bu sürüm oynanabilir bir ilk prototiptir. Gezegen ve gemiler basit 3B modellerden oluşur; gerçek astronomik ölçek veya fizik simülasyonu hedeflenmez.
