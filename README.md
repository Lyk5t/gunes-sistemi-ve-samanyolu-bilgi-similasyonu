Güneş Sistemi ve Samanyolu Bilgi Simülasyonu

Samanyolu Galaksisi’ndeki gezegenleri tanıtan, özelliklerini karşılaştırmanıza izin veren ve gezegenlerin Güneş etrafındaki hareketini 3B olarak gösteren bir masaüstü programıdır. Python ve Ursina ile yazılmıştır, tarayıcı gerektirmez.

Bozok Üniversitesi, Boğazlıyan Meslek Yüksek Okulu, Bilgisayar Programcılığı grup projesi.

Özellikler
Büyük Patlama açılışı: Program tek bir noktadan patlayan bir animasyon ve patlama sesiyle açılır. Herhangi bir tuşla atlanabilir.
3B Güneş Sistemi: Sekiz gezegen, Güneş, yörünge çizgileri, Samanyolu arka planı.
Gerçekçi gezegenler:
Her gezegenin yüzeyi program içinde üretilir (kıtalar, kraterler, bulut bantları, Büyük Kırmızı Leke).
Güneş’e dönük yarı aydınlık, öbür yarı karanlıktır.
Kabartma (kraterler ve dağlar), okyanus yansıması, Dünya’nın gece şehir ışıkları ve bulut katmanı vardır.
Atmosfer ışıması, Satürn’ün bantlı halkası ve halka üzerine düşen gezegen gölgesi vardır.
Gerçek eksen eğikliği ve dönme hızları kullanılır. Ay, Galile uyduları ve Titan gezegenlerinin etrafında döner.
Bilgi paneli: Seçilen gezegenin boyutu, uzaklığı, yörünge süresi, uydu sayısı ve renkli atmosfer bileşimi.
Canlı atmosfer verisi: Sıcaklık, basınç ve rüzgâr hızı için sürekli güncellenen grafikler (simülasyondur, aşağıya bakın).
Kendi gezegenini oluştur: Boyut, uzaklık, periyot, sıcaklık, basınç, rüzgâr, gazlar, renk ve halka seçerek yeni bir gezegen eklenir. Oluşturulan gezegenler kaydedilir.
Kontroller: Başlat/Duraklat, 0.25× – 64× hız ayarı, gezegen seçme düğmeleri.
Hakkında ekranı: Okul, proje lideri ve ekip bilgileri hakkinda.py dosyasından okunur.
Kurulum ve çalıştırma

Python 3.10 veya daha yeni bir sürüm gerekir.

bash
pip install -r requirements.txt
python main.py

Windows’ta calistir.bat dosyasına çift tıklamak da aynı işi yapar.

İlk açılışta yüzey dokuları üretildiği için program 8-10 saniye geç açılabilir.

Kontroller
İşlem	Nasıl
Döndürme	Fareyi basılı tutup sürükleyin
Yakınlaştırma	Fare tekerleği
Gezegen seçme	Gezegene tıklayın veya üstteki düğmeleri kullanın
Güneş Sistemi görünümü	Üstteki “Güneş Sistemi” düğmesi
Açılışı atlama	Herhangi bir tuş
Kapatma / pencereyi kapatma	Esc
Dosya yapısı
gezegen_programi/
├─ main.py            Ana program: arayüz, kontroller, animasyon döngüsü
├─ acilis.py          Büyük Patlama açılış animasyonu
├─ ses.py             Patlama sesini kodla üretir (ayrı ses dosyası gerekmez)
├─ sahne.py           3B sahne: gezegenler, ışık ve gölgelendiriciler, uydular, halka
├─ dokular.py         Yüzey dokuları, kabartma haritaları, Samanyolu arka planı (Pillow)
├─ arayuz.py          Kaydırıcı, düğme ve yazı bileşenleri
├─ hakkinda.py        “Hakkında” ekranındaki bilgiler
├─ gezegenler/        Her gezegen ayrı bir modül
│  ├─ merkur.py, venus.py, dunya.py, mars.py
│  └─ jupiter.py, saturn.py, uranus.py, neptun.py
├─ requirements.txt
├─ calistir.bat       Windows için kurulum ve çalıştırma
└─ exe_yap.bat        (Deneysel) .exe oluşturma

Program çalışırken iki dosya otomatik oluşur: patlama.wav (açılış sesi) ve ozel_gezegenler.json (sizin oluşturduğunuz gezegenler).

Özelleştirme

Hakkında bilgileri: hakkinda.py dosyasında okul, bölüm, proje lideri ve EKIP listesi bulunur. İsimleri değiştirip programı yeniden açın.

Gezegen verileri: Her gezegenin verisi kendi modülündedir (gezegenler/dunya.py gibi). Yarıçap, Güneş’e uzaklık, periyot, sıcaklık, basınç, rüzgâr ve atmosfer gazları orada düzenlenir. gezegenler/ klasörüne yeni bir .py dosyası ekleyip içine GEZEGEN sözlüğü yazarsanız gezegen programa otomatik eklenir.

Eksen eğikliği, dönme süresi ve uydular: sahne.py içindeki EK sözlüğündedir.

Grafik ayarları (sahne.py başı): Bir şey bozuk görünürse ilgili ayarı False yapın.

Ayar	Kapattığınızda
GOLGELEME	Güneş ışığı kapanır, düz renkli gezegenler görünür
GELISMIS	Kabartma, okyanus yansıması, şehir ışıkları, bulut katmanı ve halka gölgesi kapanır
ATMOSFER_PARLAMA	Gezegen kenarındaki dışa taşan ışıma kapanır
UZAY_ARKAPLANI	Samanyolu arka planı kapanır

Yazı boyutları arayuz.py içindeki YAZI_OLCEK değeriyle, açılış süreleri acilis.py içindeki T0 ve SOLMA değerleriyle ayarlanır. Ekran kartınız kenar yumuşatmayı desteklemiyorsa main.py sonundaki “Kenar yumuşatma” bloğunu silin.

Önemli notlar
Canlı veriler simülasyondur. Sıcaklık, basınç ve rüzgâr değerleri gerçek bir uzay verisi değildir. Her gezegenin yaklaşık ortalama değeri etrafında rastgele dalgalanır. Arayüzde de “simüle” olarak belirtilmiştir.
Boyutlar ve uzaklıklar ölçeklidir. Gezegenlerin boyutu ve Güneş’e uzaklığı ekrana sığması için küçültülmüştür, gerçek oranları yansıtmaz. Uydu mesafeleri de gezegene yaklaştırılmıştır.
Dokular gerçek fotoğraf değildir. Yüzey görüntüleri algoritmayla üretilir, NASA görüntüsü değildir.
Gezegen verileri (atmosfer oranları, sıcaklıklar vb.) yaklaşıktır. Ödev veya sunumda kullanmadan önce kendi kaynağınızla doğrulayın.
Ekip
Proje lideri: Hüseyin Solak
Ekip: Elif Özen, Burçin Karakuş, Sıla Nur Çetinol, Oğuzhan Öcal
Kullanılan teknolojiler
Python
Ursina Engine (Panda3D tabanlı 3B oyun motoru)
Pillow (yüzey dokularının üretimi)
