"""Samanyolu'ndaki bilinen ötegezegen sistemleri için görselleştirme verileri.

Yörünge ve yarıçap değerleri bilimsel kataloglardan alınan yaklaşık değerlerdir.
Simülasyonun okunabilirliği için tüm sistemlerde görsel ölçekleme uygulanır.
"""
from copy import deepcopy
from gezegenler.dunya import GEZEGEN as SABLON

SISTEMLER = {
    "Alpha Centauri": {
        "aciklama": (
            "Alpha Centauri, Güneş'e en yakın yıldız sistemidir. Bu görünümde "
            "Proxima Centauri çevresindeki doğrulanmış Proxima b ve Proxima d "
            "gezegenleri gösterilir. Boyutlar ve yörüngeler görsel ölçeklidir."
        ),
        "gezegenler": [
            ("Proxima b", 1.07, 0.0485, 11.186, "#65a7d9", 0.0, 234, "Kayalık ötegezegen; yıldızının yaşanabilir bölgesinde bulunur."),
            ("Proxima d", 0.26, 0.0289, 5.122, "#b9a6dc", 0.0, 120, "Çok düşük kütleli, kısa yörüngeli doğrulanmış ötegezegen."),
        ],
    },
    "TRAPPIST-1": {
        "aciklama": (
            "TRAPPIST-1, yaklaşık 40 ışık yılı uzakta bulunan soğuk bir kırmızı "
            "cüce yıldızdır. Sistemde b, c, d, e, f, g ve h olarak adlandırılan "
            "yedi Dünya boyutlarında gezegen bulunur."
        ),
        "gezegenler": [
            ("TRAPPIST-1 b", 1.12, .0111, 1.5109, "#d58b69", 0.0, 400, "Sistemin yıldızına en yakın gezegeni."),
            ("TRAPPIST-1 c", 1.10, .0152, 2.4218, "#b8a0a0", 0.0, 342, "Kayalık yapıda olduğu düşünülen sıcak gezegen."),
            ("TRAPPIST-1 d", .78, .0214, 4.0496, "#6f9fbd", 0.0, 288, "Sistemin küçük gezegenlerinden biri."),
            ("TRAPPIST-1 e", .92, .0282, 6.0996, "#5c9c88", 0.0, 251, "Yaşanabilir bölge içinde yer alan Dünya boyutlarında gezegen."),
            ("TRAPPIST-1 f", 1.05, .0371, 9.2067, "#83a9c9", 0.0, 219, "Yaşanabilir bölge içinde yer alan gezegen."),
            ("TRAPPIST-1 g", 1.15, .0451, 12.3529, "#b4a17c", 0.0, 195, "Sistemin dış kesimindeki büyük gezegenlerden biri."),
            ("TRAPPIST-1 h", .76, .0596, 18.7729, "#9b8bbd", 0.0, 170, "Sistemin bilinen en dış gezegeni."),
        ],
    },
    "Kepler-90": {
        "aciklama": (
            "Kepler-90, yaklaşık 2.500 ışık yılı uzakta bulunan ve sekiz gezegeni "
            "bilinen bir yıldız sistemidir. Gezegenleri Kepler-90 b'den i'ye "
            "kadar adlandırılır. Yörüngeler görsel amaçla ölçeklenmiştir."
        ),
        "gezegenler": [
            ("Kepler-90 b", 1.32, .074, 7.008, "#d7a16d", 0.0, 500, "Yıldıza yakın, kısa yörüngeli gezegen."),
            ("Kepler-90 c", 1.19, .089, 8.719, "#a6b4c9", 0.0, 430, "İç sistemdeki ikinci gezegen."),
            ("Kepler-90 i", 1.32, .123, 14.449, "#83a8c9", 0.0, 350, "Dünya boyutlarına yakın gezegen."),
            ("Kepler-90 d", 2.9, .32, 59.736, "#c79c74", 0.0, 290, "Daha büyük, sıcak gezegen."),
            ("Kepler-90 e", 2.6, .42, 91.939, "#d6b27c", 0.0, 250, "Orta yörüngede bulunan gezegen."),
            ("Kepler-90 f", 2.9, .48, 124.914, "#8d9dbd", 0.0, 220, "Orta yörüngedeki büyük gezegen."),
            ("Kepler-90 g", 8.1, .71, 210.606, "#c98e69", 0.0, 190, "Gaz devi sınıfındaki dış gezegen."),
            ("Kepler-90 h", 11.3, 1.01, 331.600, "#b69b80", 0.0, 160, "Sistemin bilinen en dış gezegeni."),
        ],
    },
}


def sistem_verisi(ad):
    """İstenen sistemin gezegen sözlüklerini ve açıklamasını döndürür."""
    sistem = SISTEMLER[ad]
    liste = []
    for ad_, yaricap, au, periyot, renk, _halka, sicaklik, bilgi in sistem["gezegenler"]:
        v = deepcopy(SABLON)
        v.update({
            "ad": ad_,
            "renk": renk,
            "yaricap_km": int(6371 * yaricap),
            "au": au,
            "periyot": periyot,
            "uydu": 0,
            "sicak": sicaklik,
            "atm_renk": renk,
            "atm_k": .12,
            "gazlar": [("Hidrojen", 1.0)],
            "halka": None,
            "doku": "kaya",
            "bilgi": bilgi,
        })
        v["donme"] = 23.0  # Güneş Sistemi dışındaki sistemlerde dönüş periyodu 1 birim azaltıldı.
        v["egim"] = 0.0
        liste.append(v)
    liste.sort(key=lambda gezegen: gezegen["au"])
    return liste, sistem["aciklama"]
