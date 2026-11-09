"""Yapay zekâ çekirdeği (Ursina'dan bağımsız, tek başına test edilebilir).

Beş özellik:
  1) cevapla()        Uzay asistanı: soruyu simülasyondaki gezegenin verileriyle yanıtlar
  2) gezegen_uret()   Doğal dil açıklamasından gezegen özellikleri üretir
  3) analiz_raporu()  Kütle, yoğunluk, yerçekimi, atmosfer, sıcaklık, yaşanabilirlik analizi
  4) gorevler()       Gezegenin özelliklerine göre değişen keşif görevleri
  5) senaryo_coz()    "Mars'a asteroit çarp", "güneş patlaması" gibi komutları çözer;
                      carpma_hesapla() ve gunes_raporu() fiziksel sonuçları hesaplar

Çalışma biçimi: Her şey ÇEVRİMDIŞI çalışır (fizik formülleri + kural tabanlı Türkçe anlama).
İsteğe bağlı olarak asistan, Claude API'ye bağlanabilir: ANTHROPIC_API_KEY ortam değişkenini
ayarlayın ya da anahtarı program klasöründeki anthropic_anahtar.txt dosyasına yazın.
"""
import json
import math
import os
import random
import re
import threading
import urllib.request

G = 6.674e-11
M_DUNYA = 5.972e24
MEGATON = 4.184e15            # 1 megaton TNT (joule)
G_DUNYA = 9.81
DEVLER = ("Jüpiter", "Satürn", "Uranüs", "Neptün")

# (kütle [Dünya=1], yoğunluk g/cm³) - gerçek gezegenler için
GERCEK = {
    "Merkür": (0.0553, 5.43), "Venüs": (0.815, 5.24), "Dünya": (1.0, 5.51), "Mars": (0.107, 3.93),
    "Jüpiter": (317.8, 1.33), "Satürn": (95.16, 0.687), "Uranüs": (14.54, 1.27), "Neptün": (17.15, 1.64),
    "Ay": (0.0123, 3.34),
}


# ---------------------------------------------------------------- yardımcılar
def sade(s):
    """Küçük harf, aksansız, noktalamasız metin (anahtar kelime eşleştirme için)."""
    s = s.replace("İ", "i").replace("I", "ı").lower()
    s = s.translate(str.maketrans("ıöüçşğâîû", "ioucsgaiu"))
    s = s.replace("'", " ").replace("’", " ").replace("‘", " ")
    s = re.sub(r"[?!;:()\"]", " ", s)
    return re.sub(r"(?<!\d)[.,]|[.,](?!\d)", " ", s)      # ondalık noktası (1.6) korunur


def tr(x, nd=1):
    """Türkçe sayı biçimi: 1.234,5"""
    s = f"{x:,.{nd}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def bilimsel(x):
    if x == 0:
        return "0"
    e = int(math.floor(math.log10(abs(x))))
    if -2 <= e <= 0:
        return tr(x, 2)
    if 1 <= e <= 4:
        return tr(x, 0)
    return f"{tr(x / 10 ** e, 1)}×10^{e}"


def bar(p):
    return tr(p, 3 if p < 0.1 else 2)


def uzunluk(km):
    return f"{tr(km * 1000, 0)} m" if km < 1 else f"{tr(km, 1)} km"


def trapez(x, a, b, c, d):
    """a'da 0, b-c arasında 1, d'de 0 olan yamuk üyelik fonksiyonu."""
    if x <= a or x >= d:
        return 0.0
    if x < b:
        return (x - a) / (b - a)
    if x <= c:
        return 1.0
    return (d - x) / (d - c)


def gaz_devi_mi(v):
    return v["ad"] in DEVLER or (v.get("doku") == "gaz" and v["yaricap_km"] >= 15000)


# ---------------------------------------------------------------- fizik / analiz
def fiziksel(v):
    """(kütle kg, yüzey çekimi m/s², yoğunluk g/cm³, kaçış hızı km/s)"""
    r = v["yaricap_km"] * 1000.0
    ad = v["ad"]
    if v.get("kutle"):
        M = float(v["kutle"]) * M_DUNYA
    elif ad in GERCEK:
        M = GERCEK[ad][0] * M_DUNYA
    else:
        M = float(v.get("cekimi") or G_DUNYA) * r * r / G
    g = G * M / r ** 2
    rho = M / (4 / 3 * math.pi * r ** 3) / 1000.0
    vk = math.sqrt(2 * G * M / r) / 1000.0
    return M, g, rho, vk


def kaynama(p_bar):
    """Suyun kaynama noktası (°C), Antoine denklemi. Üçlü nokta altında None."""
    if p_bar < 0.0061:
        return None
    mm = p_bar * 750.06
    payda = 8.07131 - math.log10(mm)
    if payda <= 0.05:
        return 374.0
    return min(374.0, 1730.63 / payda - 233.426)


def su_durumu(t, p):
    """(kod, açıklama): kod = yok | buz | sivi | buhar"""
    if p < 0.0061:
        if t <= 0:
            return "buz", "Basınç suyun sıvı kalabileceği alt sınırın (≈0,006 bar) altında: su yalnızca buz olabilir, sıvı su kararsızdır."
        return "yok", "Basınç çok düşük: su sıvı olarak kalamaz, doğrudan buharlaşır."
    b = kaynama(p)
    if t <= 0:
        return "buz", f"Sıcaklık donma noktasının altında: su buz halinde. (Bu basınçta kaynama noktası ≈ {tr(b, 0)} °C)"
    if t < b:
        return "sivi", f"Bu basınçta suyun kaynama noktası ≈ {tr(b, 0)} °C; ortalama sıcaklıkla sıvı su mümkündür."
    return "buhar", f"Sıcaklık, bu basınçtaki kaynama noktasının (≈ {tr(b, 0)} °C) üzerinde: su buhar halinde."


def bilesim(rho, devmi):
    if devmi:
        return "hidrojen-helyum (ve buz) ağırlıklı dev gezegen"
    if rho >= 5.0:
        return "büyük demir-nikel çekirdekli kayalık gezegen"
    if rho >= 3.5:
        return "silikat kayalarından oluşan kayalık gövde"
    if rho >= 2.0:
        return "kaya ile önemli oranda su buzu karışımı"
    if rho >= 1.0:
        return "buz ağırlıklı gövde (su, amonyak, metan buzları)"
    return "çok düşük yoğunluk: gaz ağırlıklı yapı"


def atm_tutma(vk):
    if vk >= 15:
        return "hidrojen ve helyum dahil neredeyse tüm gazları tutabilir"
    if vk >= 8:
        return "azot, oksijen, CO₂ gibi gazları uzun süre tutar (hafif hidrojen kaçar)"
    if vk >= 4:
        return "atmosferi orta düzeyde tutar; zamanla kaybedebilir (Mars gibi)"
    if vk >= 2:
        return "çekimi zayıf: atmosfer hızla kaçar"
    return "pratikte atmosfer tutamaz"


def sinif(s):
    if s >= 80:
        return "Çok uygun"
    if s >= 55:
        return "Uygun"
    if s >= 30:
        return "Zorlu"
    if s >= 10:
        return "Çok zorlu"
    return "Uygun değil"


def analiz(v):
    M, g, rho, vk = fiziksel(v)
    devmi = gaz_devi_mi(v)
    p = float(v.get("basinc") or 0)
    t = float(v.get("sicak") or 0)
    gz = v.get("gazlar") or []
    top = sum(y for _, y in gz) or 1
    oran = {a: y / top * 100 for a, y in gz}
    kod, su_ac = su_durumu(t, p)

    # --- genel (mikrobiyal) yaşam
    Ts = trapez(t, -20, 5, 30, 60)
    Ps = trapez(p, 0.0061, 0.3, 3, 50)
    Ws = {"sivi": 1.0, "buz": 0.3, "buhar": 0.0, "yok": 0.0}[kod]
    Ko = min(1.0, max(0.0, (vk - 2) / 3))
    genel = 100 * (0.35 * Ts + 0.15 * Ps + 0.35 * Ws + 0.15 * Ko)
    if devmi:
        genel = min(genel, 3.0)

    # --- insan
    g_oran = g / G_DUNYA
    Th = trapez(t, -10, 10, 28, 45)
    Ph = trapez(p, 0.5, 0.8, 1.3, 2.0)
    pO2 = p * oran.get("Oksijen", 0) / 100
    Oh = trapez(pO2, 0.10, 0.16, 0.35, 0.5)
    Gh = trapez(g_oran, 0.3, 0.6, 1.5, 2.5)
    zehir = (oran.get("Karbondioksit", 0) * p / 100 > 0.01) or (oran.get("Metan", 0) * p / 100 > 0.05)
    insan = 100 * (Th * Ph * Oh * Gh) ** 0.25 * (0.2 if zehir else 1.0)
    if devmi:
        insan = 0.0

    sinirlar = []
    if Th < .6:
        sinirlar.append((Th, f"Sıcaklık ({tr(t, 0)} °C) insan için {'çok düşük' if t < 10 else 'çok yüksek'}."))
    if Ph < .6:
        sinirlar.append((Ph, f"Basınç ({bar(p)} bar) {'çok düşük: korumasız insan yaşayamaz' if p < 0.8 else 'çok yüksek'}."))
    if Oh < .6:
        sinirlar.append((Oh, f"Oksijen kısmi basıncı ({bar(pO2)} bar) solunum için yetersiz/uygunsuz (ideal ≈ 0,16-0,35 bar)."))
    if Gh < .6:
        sinirlar.append((Gh, f"Yerçekimi ({tr(g_oran, 2)} g) {'çok zayıf (kas/kemik kaybı)' if g_oran < 1 else 'çok güçlü'}."))
    if zehir:
        sinirlar.append((0.0, "Atmosferdeki CO₂/metan miktarı insan için zehirli ya da patlayıcı düzeyde."))
    sinirlar.sort()

    uyari = []
    if v.get("kutle") and v.get("cekimi"):
        gc = float(v["cekimi"])
        if abs(gc - g) / g > 0.35:
            uyari.append(f"Girilen kütle ve çapa göre yerçekimi ≈ {tr(g, 1)} m/s² olmalı; ancak {tr(gc, 1)} m/s² girilmiş. "
                         f"Değerler fiziksel olarak tutarsız (analizde kütle ve çap esas alındı).")
    return dict(ad=v["ad"], devmi=devmi, r_km=v["yaricap_km"], kutle=M / M_DUNYA, kutle_kg=M, g=g, g_oran=g_oran,
                rho=rho, vk=vk, p=p, t=t, oran=oran, su=(kod, su_ac), genel=genel, insan=insan,
                sinirlar=sinirlar, uyari=uyari, bilesim=bilesim(rho, devmi), tutma=atm_tutma(vk))


def analiz_raporu(v):
    a = analiz(v)
    L = [f"BİLİMSEL DEĞERLENDİRME: {a['ad']}", ""]
    tip = "gaz/buz devi (katı yüzey yok)" if a["devmi"] else "kayalık / katı yüzeyli gezegen"
    L.append(f"Tür: {tip}   Çap: {tr(2 * a['r_km'], 0)} km")
    nd = 4 if a["kutle"] < 0.1 else (3 if a["kutle"] < 1 else 2)
    L.append(f"Kütle: {tr(a['kutle'], nd)} Dünya kütlesi ({bilimsel(a['kutle_kg'])} kg)")
    L.append(f"Yoğunluk: {tr(a['rho'], 2)} g/cm³ → {a['bilesim']}.")
    L.append(f"Yüzey çekimi: {tr(a['g'], 2)} m/s² ({tr(a['g_oran'], 2)} g). 70 kg'lık biri burada ≈ {tr(70 * a['g_oran'], 0)} kg gibi hisseder.")
    L.append(f"Kaçış hızı: {tr(a['vk'], 1)} km/s → {a['tutma']}.")
    if a["p"] < 0.001:
        L.append("Atmosfer: yok ya da ihmal edilebilir düzeyde.")
    else:
        ilk = sorted(a["oran"].items(), key=lambda kv: -kv[1])[:3]
        L.append(f"Atmosfer: {bar(a['p'])} bar; " + ", ".join(f"%{tr(y, 0)} {ad}" for ad, y in ilk) + ".")
    L.append(f"Ortalama sıcaklık: {tr(a['t'], 0)} °C" + (" (bulut tepesi/üst atmosfer değeri)" if a["devmi"] else "") + ".")
    L.append(f"Su: {a['su'][1]}")
    L.append("")
    L.append("YAŞANABİLİRLİK (Dünya'daki yaşam koşullarına göre)")
    L.append(f"Genel yaşam (mikrobiyal): %{tr(a['genel'], 0)} → {sinif(a['genel'])}")
    L.append(f"İnsan yaşamı: %{tr(a['insan'], 0)} → {sinif(a['insan'])}")
    if a["sinirlar"]:
        L.append("İnsan için sınırlayıcı etkenler:")
        for _, m in a["sinirlar"][:4]:
            L.append(" - " + m)
    for u in a["uyari"]:
        L.append("UYARI: " + u)
    L.append("")
    L.append("Not: Basit fiziksel modele dayalı bir tahmindir; manyetik alan, radyasyon ve sera etkisi hesaba katılmamıştır.")
    return "\n".join(L)


# ---------------------------------------------------------------- bilgi tabanı
OZEL_YASAM = {
    "Merkür": "Gündüz yaklaşık 430 °C, gece yaklaşık -180 °C; atmosferi neredeyse yok. Kutuplardaki kalıcı gölgeli kraterlerde su buzu bulunduğu düşünülüyor, ancak yaşam beklenmez.",
    "Venüs": "Yüzeyi yaklaşık 465 °C ve 90 barın üzerinde basınçta. Buna karşın yaklaşık 50-60 km yükseklikte sıcaklık ve basınç Dünya'ya benzer; bulut katmanında yaşam olup olmadığı tartışılır, kanıt yoktur.",
    "Mars": "Geçmişte akarsular ve göller vardı; mikrobiyal yaşam o dönemde mümkün olmuş olabilir. Bugün atmosfer çok ince, ortalama sıcaklık ≈ -60 °C ve radyasyon yüksek; yüzeyde sıvı su kararsız. Yaşam kanıtı henüz yok; yer altı ve eski göl tortulları araştırılıyor.",
    "Jüpiter": "Katı yüzey yok; yaşam beklenmez. Asıl ilgi çeken yer, buz kabuğunun altında okyanus bulunduğu düşünülen uydusu Europa.",
    "Satürn": "Katı yüzey yok; gezegende yaşam beklenmez. Uydusu Enceladus'ta (su püskürtmeleri) ve Titan'da (sıvı metan gölleri, yer altı okyanusu olasılığı) yaşam araştırılıyor.",
    "Uranüs": "Buz devi; katı yüzey ve yaşam beklenmez.",
    "Neptün": "Buz devi; katı yüzey ve yaşam beklenmez.",
    "Ay": "Atmosfer ve sıvı su yok; yaşam yok. Kutuplardaki gölgeli kraterlerde su buzu var.",
    "Dünya": "Bildiğimiz tek yaşam taşıyan gezegen: sıvı su, kalın ve dengeli atmosfer, manyetik alan.",
}
RENK_NEDENI = {
    "Mars": "yüzeyindeki toz ve kayaların demir oksit (pas) içermesi nedeniyle kırmızımsı görünür.",
    "Venüs": "kükürt dioksit ve sülfürik asit bulutlarından oluşan kalın, sarımsı bir bulut örtüsü nedeniyle sarımsı-beyaz görünür.",
    "Dünya": "okyanuslar ve atmosferin mavi ışığı saçması nedeniyle mavi görünür.",
    "Jüpiter": "amonyak ve diğer bileşiklerden oluşan, farklı hızlarda akan bulut bantları nedeniyle şeritli görünür.",
    "Satürn": "üst atmosferdeki sis ve amonyak bulutları nedeniyle soluk altın renkte görünür.",
    "Uranüs": "atmosferdeki metanın kırmızı ışığı soğurması nedeniyle açık mavi-yeşil görünür.",
    "Neptün": "metanın kırmızı ışığı soğurması ve üst atmosferdeki farklı bulut/sis katmanları nedeniyle koyu mavi görünür.",
    "Merkür": "kraterli, koyu gri bazalt yüzeyi nedeniyle gri görünür.",
    "Ay": "gri bazalt ve anortozit kayalarıyla kaplı yüzeyi nedeniyle gri görünür.",
}
HALKA_GENEL = (
    "Satürn'ün halkaları büyük oranda su buzu parçacıklarından oluşur; parçacık boyutları santimetreden birkaç metreye kadar değişir. "
    "Kökenleri tartışmalıdır: gezegene fazla yaklaşan bir uydunun ya da kuyruklu yıldızın, gelgit kuvvetleri nedeniyle (Roche sınırı içinde) "
    "parçalanması veya bir uydunun hiç oluşamamış artık malzemesi olabilir. Roche sınırı içinde gelgit kuvveti, parçacıkların "
    "birleşip uydu oluşturmasını engellediği için malzeme halka halinde kalır. Halkaların yaşı da tartışmalıdır "
    "(yüz milyon yıldan birkaç milyar yıla kadar tahminler var). Jüpiter, Uranüs ve Neptün'ün de ince, sönük halkaları vardır."
)


def bul_gezegen(f, tumu):
    tok = f.split()
    for w in tumu:
        n = sade(w["ad"])
        if (len(n) >= 3 and n in f) or n in tok:
            return w
    return None


def _ozet_atm(a):
    if a["p"] < 0.001:
        return "belirgin bir atmosferi yok"
    ilk = sorted(a["oran"].items(), key=lambda kv: -kv[1])[:3]
    return f"{bar(a['p'])} bar basınçlı bir atmosferi var (" + ", ".join(f"%{tr(y, 0)} {ad}" for ad, y in ilk) + ")"


def yardim_metni():
    return ("Merhaba! Seçili gezegenin verilerine göre soruları yanıtlarım. Örnekler:\n"
            " - Mars'ta yaşam mümkün mü?\n"
            " - Satürn'ün halkaları neden var?\n"
            " - Bu gezegende insan yaşayabilir mi?\n"
            " - Yerçekimi ne kadar? / Sıcaklık kaç derece?\n"
            " - Atmosferi neyden oluşuyor? / Su var mı?\n"
            " - Neden kırmızı görünüyor?\n"
            "Soruda gezegen adı geçerse o gezegeni, geçmezse seçili gezegeni kullanırım.")


def cevapla(soru, v, tumu=()):
    """Çevrimdışı uzay asistanı. v: seçili gezegen sözlüğü (None olabilir)."""
    f = sade(soru)
    w = bul_gezegen(f, tumu) or v
    if any(k in f for k in ("merhaba", "selam", "yardim", "ne yapabilirsin", "neler sorabilirim")):
        return yardim_metni()
    if w is None:
        return "Hangi gezegeni soruyorsun? Üst menüden bir gezegen seç ya da sorunda gezegenin adını yaz."
    a = analiz(w)
    ad = w["ad"]

    if any(k in f for k in ("halka",)):
        if w.get("halka") or ad == "Satürn":
            return f"{ad} için: " + HALKA_GENEL
        return f"{ad} gezegeninin simülasyonda halkası yok. Genel bilgi: " + HALKA_GENEL

    if "insan" in f and any(k in f for k in ("yasa", "yerles", "gidebil", "yasam")):
        s = a["insan"]
        if s >= 75:
            bas = f"Evet, {ad} insan yaşamı için büyük oranda uygun görünüyor (%{tr(s, 0)})."
        elif s >= 30:
            bas = f"{ad} insan için kısmen uygun (%{tr(s, 0)}); bazı koşullar teknolojiyle telafi edilmeli."
        else:
            bas = f"Hayır, korumasız bir insan {ad} üzerinde yaşayamaz (uygunluk %{tr(s, 0)})."
        sn = " ".join(m for _, m in a["sinirlar"][:3])
        ek = ""
        if a["devmi"]:
            ek = " Katı bir yüzeyi olmadığı için ancak atmosferde süzülen bir istasyon düşünülebilir."
        elif s < 75:
            ek = " Yerleşim için basınçlı kubbe/yaşam destek sistemi ve radyasyon korunması gerekir."
        return f"{bas} {sn}{ek}".strip()

    if any(k in f for k in ("yasam", "canli", "mikrop", "hayat", "yasanabilir", "yasayabilir")):
        s = a["genel"]
        bas = f"{ad} için genel (mikrobiyal) yaşam uygunluğu %{tr(s, 0)} ({sinif(s).lower()}). Sıcaklık {tr(a['t'], 0)} °C; {_ozet_atm(a)}. {a['su'][1]}"
        ek = OZEL_YASAM.get(ad, "")
        return (bas + ("\n" + ek if ek else "")).strip()

    if any(k in f for k in ("neden", "niye", "niçin", "nicin")) and any(k in f for k in ("renk", "kirmizi", "mavi", "sari", "gri", "gorun")):
        if ad in RENK_NEDENI:
            return f"{ad}, {RENK_NEDENI[ad]}"
        return f"{ad}, simülasyonda {w['renk']} tonlarında gösteriliyor; gerçek renk yüzey/atmosfer bileşimine bağlıdır."

    if any(k in f for k in ("yercekim", "agirlik", "cekim", "ziplar", "kilo")):
        return (f"{ad} yüzeyinde yerçekimi ≈ {tr(a['g'], 2)} m/s² (Dünya'nın %{tr(a['g_oran'] * 100, 0)}'i). "
                f"70 kg'lık biri burada ≈ {tr(70 * a['g_oran'], 0)} kg gibi hisseder; Dünya'da 50 cm zıplayan biri ≈ {tr(50 / a['g_oran'], 0)} cm zıplar. "
                f"Kaçış hızı {tr(a['vk'], 1)} km/s.")

    if any(k in f for k in ("sicak", "isi", "soguk", "derece")):
        return f"{ad} üzerinde ortalama sıcaklık ≈ {tr(a['t'], 0)} °C. {a['su'][1]}"

    if any(k in f for k in ("atmosfer", "hava", "gaz", "basinc", "oksijen", "metan", "solun")):
        return f"{ad}: {_ozet_atm(a)}. Kaçış hızı {tr(a['vk'], 1)} km/s olduğundan {a['tutma']}."

    if any(k in f for k in ("su ", "suyu", "okyanus", "deniz", "buz")) or f.strip().endswith(" su"):
        return f"{ad} için su durumu: {a['su'][1]}"

    if any(k in f for k in ("uydu", "ay sayisi")):
        n = w.get("uydu", 0)
        return f"{ad} gezegeninin bilinen uydu sayısı: {n}."

    if any(k in f for k in ("kutle", "yogun", "cap", "yaricap", "boyut", "buyuk")):
        return (f"{ad}: çap ≈ {tr(2 * a['r_km'], 0)} km, kütle ≈ {tr(a['kutle'], 3 if a['kutle'] < 1 else 2)} Dünya kütlesi, "
                f"yoğunluk ≈ {tr(a['rho'], 2)} g/cm³ → {a['bilesim']}.")

    if any(k in f for k in ("gorev", "kesif", "ne yapmaliyiz", "ne yapalim")):
        g = gorevler(w)[:3]
        return f"{ad} için önerilen ilk görevler: " + "; ".join(x["ad"] for x in g) + ". Ayrıntı için 'Görevler' sekmesine bak."

    if any(k in f for k in ("asteroit", "gokta", "carp", "patlama", "yorunge")):
        return "Bu tür olayları 'Senaryo' sekmesinde çalıştırabilirsin; örneğin: \"Mars'a 10 km çapında asteroit çarp\"."

    return (f"{ad}: {tr(2 * a['r_km'], 0)} km çaplı, {tr(a['t'], 0)} °C ortalama sıcaklıkta, {tr(a['g'], 2)} m/s² çekimli bir gezegen; "
            f"{_ozet_atm(a)}. Yaşanabilirlik: genel %{tr(a['genel'], 0)}, insan %{tr(a['insan'], 0)}.\n"
            "Daha ayrıntılı sormak için 'yardım' yaz.")


# ---------------------------------------------------------------- Claude (isteğe bağlı)
MODEL = "claude-sonnet-5-5"          # model adını gerekirse değiştirin
API_URL = "https://api.anthropic.com/v1/messages"
SISTEM = ("Sen 'Samanyolu 3B Gezegen Laboratuvarı' simülasyonunun uzay asistanısın. Türkçe, kısa ve net yanıt ver "
          "(en fazla 120 kelime). Önce sana verilen gezegen verilerini kullan; veride olmayan bir şeyi bilimsel olarak "
          "doğrulanmış bilgiyle tamamla ve emin olmadığında bunu açıkça söyle. Bilgi uydurma.")


def anahtar():
    k = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if k:
        return k
    try:
        yol = os.path.join(os.path.dirname(os.path.abspath(__file__)), "anthropic_anahtar.txt")
        with open(yol, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def claude_hazir():
    return bool(anahtar())


def _claude_cagri(soru, v, gecmis):
    baglam = analiz_raporu(v) if v else "Seçili gezegen yok."
    msgs = []
    for rol, metin in gecmis[-6:]:
        if msgs and msgs[-1]["role"] == rol:
            continue
        msgs.append({"role": rol, "content": metin})
    while msgs and msgs[0]["role"] != "user":
        msgs.pop(0)
    if msgs and msgs[-1]["role"] == "user":
        msgs.pop()
    msgs.append({"role": "user", "content": f"[Simülasyon verileri]\n{baglam}\n\n[Soru]\n{soru}"})
    govde = json.dumps({"model": MODEL, "max_tokens": 600, "system": SISTEM, "messages": msgs}).encode("utf-8")
    istek = urllib.request.Request(API_URL, data=govde, method="POST", headers={
        "x-api-key": anahtar(), "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(istek, timeout=40) as r:
        d = json.loads(r.read().decode("utf-8"))
    return "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text").strip()


def claude_sor_baslat(kuyruk, soru, v, gecmis):
    """Arka plan iş parçacığında sorar; sonuç kuyruğa ('ok', metin) ya da ('hata', mesaj) olarak düşer."""
    def is_():
        try:
            kuyruk.put(("ok", _claude_cagri(soru, v, gecmis)))
        except Exception as hata:
            kuyruk.put(("hata", str(hata)))
    threading.Thread(target=is_, daemon=True).start()


# ---------------------------------------------------------------- gezegen oluşturucu
RENKLER = {"pembe": "#ff7ac8", "mavi": "#4f9bff", "turkuaz": "#4de1d2", "yesil": "#5fd07a", "sari": "#ffd36b",
           "turuncu": "#ff9a4d", "kirmizi": "#e0453a", "mor": "#a77bff", "beyaz": "#f2f2f2", "gri": "#9a9aa8"}
ATM_RENK = {"Azot": "#6fa8ff", "Oksijen": "#7fb8ff", "Argon": "#c0a3ff", "Hidrojen": "#9fe8ff", "Helyum": "#ffe27a",
            "Metan": "#6fe0c0", "Karbondioksit": "#ff9d5c", "Sodyum": "#ffc04d", "Neon": "#ff8ad8",
            "Su buharı": "#9fd8ff", "Diğer": "#8d8bb0"}
GAZ_ANAHTAR = [("metan", "Metan"), ("azot", "Azot"), ("oksijen", "Oksijen"), ("karbondioksit", "Karbondioksit"),
               ("karbon dioksit", "Karbondioksit"), ("co2", "Karbondioksit"), ("hidrojen", "Hidrojen"),
               ("helyum", "Helyum"), ("argon", "Argon"), ("su buhar", "Su buharı"), ("neon", "Neon"),
               ("sodyum", "Sodyum")]
SAYI_KELIME = {"bir": 1, "tek": 1, "iki": 2, "cift": 2, "uc": 3, "dort": 4, "bes": 5, "alti": 6, "yedi": 7, "sekiz": 8}
ROMEN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"]
ON_AD = ["Aether", "Nyx", "Kepler", "Titan", "Orion", "Lyra", "Vega", "Helios", "Zephyr"]


def _gaz_karisimi(f, devmi):
    """(gazlar listesi, belirtildi mi, baskın gaz)"""
    bulunan = []
    for anahtar_, ad in GAZ_ANAHTAR:
        i = f.find(anahtar_)
        if i >= 0 and ad not in [b[1] for b in bulunan]:
            bulunan.append((i, ad, anahtar_))
    bulunan.sort()
    if not bulunan:
        return None, False, None
    dom = bulunan[0][1]
    for i, ad, k in bulunan:
        if re.search(re.escape(k) + r"\s+(?:\w+\s+)?agirlik", f) or re.search(r"agirlikli\s+" + re.escape(k), f):
            dom = ad
            break
    digerleri = [ad for _, ad, _ in bulunan if ad != dom]
    sonuc = {dom: 70}
    for o in digerleri:
        sonuc[o] = 20 / len(digerleri)
    if devmi:
        for ad, y in (("Hidrojen", 25), ("Helyum", 10)):
            if ad not in sonuc:
                sonuc[ad] = y
    kalan = 100 - sum(sonuc.values())
    if kalan > 0:
        for ad in ("Azot", "Argon", "Diğer"):
            if ad not in sonuc:
                sonuc[ad] = kalan
                break
    ham = list(sonuc.items())
    top = sum(y for _, y in ham)
    liste = [(ad, max(1, round(y / top * 100))) for ad, y in ham]
    return liste, True, dom


def gezegen_uret(metin, mevcut_adlar=(), au=60.0):
    """Doğal dil açıklamasından gezegen sözlüğü ve bir rapor metni üretir."""
    f = sade(metin)
    varsayim = []

    # ---- ad
    ad = None
    m = re.search(r"(?:adi|ismi|adli|isimli)\s+([\w\-]+)", metin, flags=re.I | re.U)
    m2 = re.search(r"([\w\-]+)\s+(?:adli|isimli|adinda|isminde)", f)
    if m2 and m2.group(1) not in ("bir", "gezegen"):
        ad = m2.group(1)
    elif m and m.group(1).lower() not in ("olan", "bir"):
        ad = m.group(1)
    if ad:
        # özgün yazımı koru
        orj = re.search(re.escape(ad), metin, flags=re.I)
        ad = (orj.group(0) if orj else ad)[:18].capitalize() if ad.islower() else ad[:18]
    else:
        ad = f"{ON_AD[sum(map(ord, f)) % len(ON_AD)]}-{100 + sum(map(ord, f)) % 900}"
        varsayim.append(f"Ad belirtilmediği için '{ad}' adını verdim.")
    while ad in mevcut_adlar:
        ad += " II"
    ad = ad[:18]

    # ---- tür
    metan_okyanus = bool(re.search(r"sivi metan|metan (?:okyanus|deniz|gol)|titan", f))
    if "gaz dev" in f or "gazdev" in f or "buz dev" in f:
        tur = "gaz"
    elif re.search(r"lav|volkan|magma", f):
        tur = "lav"
    elif re.search(r"okyanus|deniz|su ile kapli|sularla kapli|sulu", f):
        tur = "okyanus"
    elif re.search(r"buz|buzul|donmus|karla kapli", f):
        tur = "buz"
    elif "col" in f.split():
        tur = "col"
    else:
        tur = "kaya"
        varsayim.append("Tür belirtilmediği için kayalık gezegen varsaydım.")
    devmi = tur == "gaz"

    # ---- çap
    cap = None
    mk = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:km|kilometre)", f)
    if mk:
        cap = float(mk.group(1).replace(",", "."))
    elif re.search(r"super dunya", f):
        cap = 18000
    elif re.search(r"dunya (?:boyut|buyukluk|capinda)", f):
        cap = 12742
    elif re.search(r"cuce|minik|kucuk", f):
        cap = 4800
    elif re.search(r"dev |buyuk|kocaman", f + " "):
        cap = 90000 if devmi else 24000
    if cap is None:
        cap = 90000 if devmi else (12000 if tur != "col" else 9000)
        varsayim.append(f"Boyut belirtilmediği için çapı {tr(cap, 0)} km aldım.")
    cap = max(1000, min(150000, cap))

    # ---- uydu sayısı
    uydu = None
    if "uydusuz" in f:
        uydu = 0
    else:
        mu = re.search(r"(\d+|bir|tek|iki|cift|uc|dort|bes|alti|yedi|sekiz)\s+(?:adet\s+)?uydu", f)
        if mu:
            uydu = int(mu.group(1)) if mu.group(1).isdigit() else SAYI_KELIME[mu.group(1)]
    uydu = 0 if uydu is None else min(uydu, 8)

    # ---- atmosfer
    atmsiz = bool(re.search(r"atmosfer(?:i|siz)?\s*(?:yok|olmayan)|atmosfersiz", f))
    gazlar, belirtildi, dom = _gaz_karisimi(f, devmi)
    if metan_okyanus:
        gazlar, dom, belirtildi = [("Azot", 95), ("Metan", 5)], "Azot", True
    if atmsiz:
        gazlar, basinc = [("Diğer", 100)], 0.0
    else:
        if gazlar is None:
            if devmi:
                gazlar = [("Hidrojen", 86), ("Helyum", 13), ("Metan", 1)]
            elif tur == "lav":
                gazlar = [("Karbondioksit", 90), ("Azot", 8), ("Diğer", 2)]
            elif "yasanabilir" in f or "dunya gibi" in f:
                gazlar = [("Azot", 78), ("Oksijen", 21), ("Diğer", 1)]
            else:
                gazlar = [("Azot", 80), ("Karbondioksit", 15), ("Argon", 5)]
            varsayim.append("Atmosfer bileşimi belirtilmediği için tür/koşullara uygun bir karışım seçtim.")
        if devmi:
            basinc = 100.0
        elif re.search(r"kalin atmosfer|yogun atmosfer", f):
            basinc = 20.0
        elif re.search(r"ince atmosfer", f):
            basinc = 0.1
        else:
            basinc = 1.2 if tur == "okyanus" else (60.0 if tur == "lav" else 1.0)
    atm_k = 0.0 if atmsiz else (0.35 if basinc < 0.3 else 0.55)

    # ---- sıcaklık
    if metan_okyanus:
        sicak = -179.0
    elif re.search(r"cehennem|kavurucu|cok sicak", f):
        sicak = 350.0
    elif re.search(r"dondurucu|cok soguk|buzul", f):
        sicak = -130.0
    elif re.search(r"\bsicak", f):
        sicak = 90.0
    elif re.search(r"iliman|ilik", f) or "yasanabilir" in f:
        sicak = 16.0
    elif re.search(r"soguk|donuk", f):
        sicak = -60.0
    else:
        sicak = {"gaz": -110.0, "lav": 420.0, "okyanus": 14.0, "buz": -90.0, "col": 55.0, "kaya": 5.0}[tur]
        varsayim.append(f"Sıcaklık belirtilmediği için {tr(sicak, 0)} °C aldım.")
    if "Metan" in dict(gazlar) and dom == "Metan" and tur == "okyanus" and not metan_okyanus and not atmsiz:
        if sicak < 20 and not re.search(r"sicak|soguk|iliman", f):
            sicak = 28.0
            varsayim[-1:] = [f"Metan güçlü bir sera gazı olduğundan sıcaklığı {tr(sicak, 0)} °C aldım."]

    # ---- yoğunluk, çekim
    rho = {"gaz": 1.3, "okyanus": 4.8, "buz": 2.6, "lav": 5.3, "col": 4.2, "kaya": 5.0}[tur]
    r_m = cap * 500.0
    M = rho * 1000 * 4 / 3 * math.pi * r_m ** 3
    cekim = G * M / r_m ** 2
    kutle = M / M_DUNYA

    # ---- renk, halka, rüzgâr
    renk = None
    for k, h in RENKLER.items():
        if re.search(r"\b" + k, f):
            renk = h
            break
    if renk is None:
        renk = {"gaz": "#ffd36b", "okyanus": "#4f9bff", "buz": "#cdf4f5", "lav": "#e0453a",
                "col": "#e0a060", "kaya": "#9a9aa8"}[tur]
    halka = renk if (re.search(r"halkali", f) and "halkasiz" not in f) else None
    if devmi:
        ruzgar = 300
    elif atmsiz:
        ruzgar = 0
    else:
        ruzgar = 40 if tur == "okyanus" else 60
    if re.search(r"firtina|ruzgarli", f):
        ruzgar += 120

    # ---- uydular
    rnd = random.Random(sum(map(ord, ad)))
    aylar = []
    for i in range(uydu):
        km = max(120, min(rnd.uniform(250, 1700), cap * 0.27))
        mesafe = 3.0 + 1.5 * i + rnd.random() * .4
        per = round(1.3 * mesafe ** 1.5, 2)
        g_ = rnd.randint(110, 190)
        aylar.append((f"{ad} {ROMEN[i]}", round(km), round(mesafe, 2), per, "#%02x%02x%02x" % (g_, g_ - 6, g_ - 14)))

    tur_ad = {"gaz": "gaz devi", "okyanus": "okyanus dünyası", "buz": "buz gezegeni", "lav": "lav gezegeni",
              "col": "çöl gezegeni", "kaya": "kayalık gezegen"}[tur]
    ozet = f"{ad}, {tr(cap, 0)} km çaplı bir {tur_ad}dir."
    if tur == "okyanus":
        ozet = f"{ad}, yüzeyini okyanusların kapladığı, {tr(cap, 0)} km çaplı bir dünyadır." if not metan_okyanus else \
            f"{ad}, yüzeyinde sıvı metan okyanusları bulunan, {tr(cap, 0)} km çaplı Titan benzeri bir dünyadır."
    bilgi = (f"{ozet} Ortalama sıcaklık {tr(sicak, 0)} °C, yerçekimi {tr(cekim, 1)} m/s², "
             f"atmosfer: " + ("yok" if atmsiz else ", ".join(f"%{y} {a}" for a, y in gazlar)) + f". Uydu sayısı: {uydu}.")

    doku = "gaz" if devmi else ("dunya" if (tur == "okyanus" and not metan_okyanus) else "kaya")
    v = dict(ad=ad, renk=renk, yaricap_km=cap / 2, au=au, periyot=au * 200, uydu=uydu, sicak=sicak,
             basinc=basinc, ruzgar=ruzgar, atm_renk=ATM_RENK.get(dom or gazlar[0][0], renk), atm_k=atm_k,
             gazlar=[(a, y) for a, y in gazlar], halka=halka, doku=doku, bilgi=bilgi, cekimi=round(cekim, 2),
             kutle=round(kutle, 3), yogunluk=rho, yas=4.5, boyut=1024)
    if aylar:
        v["aylar"] = aylar

    a = analiz(v)
    rapor = [f"YENİ GEZEGEN: {ad}", "", bilgi, "",
             f"Kütle ≈ {tr(kutle, 2 if kutle >= 1 else 3)} Dünya kütlesi, yoğunluk ≈ {tr(rho, 1)} g/cm³, kaçış hızı ≈ {tr(a['vk'], 1)} km/s.",
             f"Yaşanabilirlik: genel %{tr(a['genel'], 0)} ({sinif(a['genel'])}), insan %{tr(a['insan'], 0)} ({sinif(a['insan'])})."]
    if metan_okyanus:
        rapor.append("Not: Okyanuslar su değil, -180 °C civarında sıvı metan/etan.")
    if varsayim:
        rapor += ["", "Varsayımlarım:"] + [" - " + x for x in varsayim]
    return v, "\n".join(rapor)


# ---------------------------------------------------------------- uzay görevleri
def gorevler(v):
    a = analiz(v)
    ad = v["ad"]
    L = []

    def ekle(baslik, aciklama, risk, sure, sonuc):
        L.append(dict(ad=baslik, aciklama=aciklama, risk=risk, sure=sure, sonuc=sonuc))

    ilk_sonuc = (f"Çap {tr(2 * a['r_km'], 0)} km, kütle {tr(a['kutle'], 3 if a['kutle'] < 1 else 2)} Dünya kütlesi, yoğunluk {tr(a['rho'], 2)} g/cm³: "
                 f"{a['bilesim']}.")
    ekle("Bilinmeyen gezegeni araştır",
         f"{ad} yörüngesine sensörlü bir keşif aracı yerleştir; çekim alanı, yüzey/bulut haritası ve genel yapıyı belirle.",
         "Düşük", 40, ilk_sonuc)

    if a["p"] >= 0.001:
        ilk = sorted(a["oran"].items(), key=lambda kv: -kv[1])
        sonuc = f"Basınç {tr(a['p'], 2)} bar. Bileşim: " + ", ".join(f"%{tr(y, 0)} {g}" for g, y in ilk[:4]) + "."
        risk = "Yüksek" if (a["p"] > 20 or a["t"] > 250 or a["devmi"]) else ("Orta" if a["p"] > 3 or a["t"] > 80 else "Düşük")
        yontem = "Atmosfere sonda bırakıp bulut tepesinden numune al" if a["devmi"] else "Alçak yörüngeden atmosfer sondası gönder, inişte numune al"
        ekle("Atmosferden numune al", f"{yontem}; gaz oranlarını ve iz gazları analiz et.", risk, 25, sonuc)

    kod = a["su"][0]
    su_sonuc = {"sivi": "Sıvı su mümkün: yüzey ve yer altı sularını spektrometre ve radarla haritala.",
                "buz": "Su büyük olasılıkla buz halinde: kutup ve gölgeli bölgelerde buz yatakları ara.",
                "buhar": "Su yalnızca buhar halinde; yüzey suyu beklenmez, atmosferdeki su buharını ölç.",
                "yok": "Yüzeyde kalıcı su beklenmez; gölgeli kraterlerde buz olasılığını incele."}[kod]
    ekle("Su kaynaklarını tespit et", "Radar ve kızılötesi spektrometre ile su/buz taraması yap. " + su_sonuc,
         "Düşük" if kod in ("sivi", "buz") else "Orta", 30, a["su"][1])

    o2, ch4 = a["oran"].get("Oksijen", 0), a["oran"].get("Metan", 0)
    if o2 > 0.5 and ch4 > 0.05:
        ys = "Atmosferde oksijen ve metan birlikte var; Dünya'da bu birliktelik yaşamla ilişkilidir. Abiyotik kaynaklar elenmeli."
    elif a["genel"] >= 40:
        ys = "Koşullar mikrobiyal yaşama elverişli: sıvı su, uygun sıcaklık ve basınç. Yüzey/yer altı örnekleri alınmalı."
    elif a["devmi"]:
        ys = "Yüzey yok; yaşam ancak bulut katmanında aranabilir, olasılık düşük."
    else:
        ys = "Yüzeyde yaşam koşulları zorlu; yer altı ve kutup buzları yaşam izi (organik molekül) için taranmalı."
    ekle("Yabancı yaşam belirtilerini incele", "Organik molekül, metan/oksijen dengesizliği ve biyolojik izler için örnekleri analiz et.",
         "Orta", 60, ys)

    if v.get("uydu", 0) > 0 or v.get("aylar"):
        n = len(v["aylar"]) if v.get("aylar") else v.get("uydu")
        ekle("Uyduları keşfet", f"{ad} çevresindeki {n} uyduyu yakın geçişle görüntüle; buz kabuğu ve yer altı okyanusu ara.", "Orta", 35,
             "Uydu yüzeyleri kraterli; buz kabuğu altında sıvı olasılığı için radar geçişi önerilir.")
    if v.get("halka"):
        ekle("Halka parçacıklarından örnek al", "Halka düzlemine alçak geçiş yapıp buz/toz parçacıklarını topla.", "Yüksek", 20,
             "Parçacıklar büyük oranda su buzu; boyutları santimetre-metre ölçeğinde.")
    if not a["devmi"] and (a["p"] > 20 or a["t"] > 250):
        ekle("Aşırı sıcaklığa/basınca dayanıklı iniş aracı", f"{tr(a['t'], 0)} °C ve {tr(a['p'], 1)} bar için ısı kalkanlı iniş aracı tasarla.", "Yüksek", 90,
             "İniş aracı birkaç saat çalışabilir; süre ısı yüküyle sınırlı.")
    if a["t"] < -100 and not a["devmi"]:
        ekle("Kriyojenik buz karotu al", "Yüzeyden derin karot alıp donmuş uçucuları analiz et.", "Orta", 45,
             "Karot, donmuş uçucu (su/metan/azot) tabakalarını gösteriyor.")
    if float(v.get("ruzgar") or 0) > 150:
        ekle("Fırtına ve rüzgâr profilini ölç", f"Rüzgâr hızı {tr(float(v['ruzgar']), 0)} km/s düzeyinde; balon/sonda ile yükseklik profili çıkar.", "Yüksek", 30,
             "Rüzgâr yükseklikle belirgin şekilde değişiyor; jet akımları saptandı.")
    if a["insan"] >= 30:
        ekle("İnsanlı iniş fizibilitesi", "Yaşam destek, radyasyon ve iniş senaryolarını değerlendir.", "Orta", 120,
             f"İnsan uygunluğu %{tr(a['insan'], 0)}; kubbe/yaşam destek ile ilk üs mümkün.")
    else:
        ekle("Robotik üs kur", "İnsanlı görev yerine uzun süreli robotik gözlem istasyonu yerleştir.", "Orta", 75,
             "İstasyon hava durumu, sıcaklık ve radyasyon verisini sürekli gönderiyor.")
    return L


# ---------------------------------------------------------------- senaryolar
DAT = ("a", "e", "ya", "ye", "na", "ne")


def senaryo_coz(metin, adlar, secili=None):
    """Komut metnini çözer. Dönen sözlük: tip, hedef, kaynak, cap_km, hiz, sinif, faktor, au"""
    f = sade(metin)
    tok = f.split()
    bul = []
    for i, t in enumerate(tok):
        for ad in adlar:
            n = sade(ad)
            if t == n or (len(n) >= 3 and t.startswith(n) and len(t) - len(n) <= 5):
                ek = t[len(n):]
                if not ek and i + 1 < len(tok):
                    ek = tok[i + 1]
                bul.append((i, ad, ek in DAT))
                break
    hedef = kaynak = None
    dat = [b for b in bul if b[2]]
    if dat:
        hedef = dat[0][1]
        diger = [b[1] for b in bul if b[1] != hedef]
        kaynak = diger[0] if diger else None
    elif len(bul) >= 2:
        kaynak, hedef = bul[0][1], bul[-1][1]
    elif len(bul) == 1:
        hedef = bul[0][1]
    if hedef is None:
        hedef = secili if secili in adlar else ("Dünya" if "Dünya" in adlar else None)

    if "gunes" in f and any(k in f for k in ("patlama", "flare", "firtina", "parlama", "cme", "ejeksiyon", "kutle atimi")):
        tip = "gunes"
    elif "yorunge" in f or "uzaklas" in f or "yaklas" in f:
        tip = "yorunge"
    elif "carpis" in f or "protogezegen" in f or "theia" in f or (kaynak and "carp" in f) or re.search(r"gezegen\w*\s+carp", f):
        tip = "carpisma"
    elif any(k in f for k in ("asteroit", "gokta", "meteor", "kuyruklu", "comet", "carp")):
        tip = "asteroit"
    else:
        tip = "bilinmiyor"

    cap = None
    mk = re.search(r"(\d+(?:[.,]\d+)?)\s*(km|kilometre|metre|m)\b", f)
    if mk:
        cap = float(mk.group(1).replace(",", "."))
        if mk.group(2) in ("m", "metre"):
            cap /= 1000.0
    hiz = None
    mh = re.search(r"(\d+(?:[.,]\d+)?)\s*km\s*/\s*(?:s|sn|saniye)", f)
    if mh:
        hiz = float(mh.group(1).replace(",", "."))
    sn = "X5"
    ms = re.search(r"\b([cmx])\s?-?(\d+(?:[.,]\d+)?)\b", f)
    if ms:
        sn = ms.group(1).upper() + ms.group(2).replace(",", ".")
    elif "super" in f or "dev patlama" in f:
        sn = "X20"
    elif re.search(r"\bx\b", f):
        sn = "X5"
    faktor = au = None
    mkat = re.search(r"(\d+(?:[.,]\d+)?)\s*kat", f)
    maU = re.search(r"(\d+(?:[.,]\d+)?)\s*au\b", f)
    azalt = any(k in f for k in ("yaklas", "kucult", "azalt", "kisalt", "icine"))
    if maU:
        au = float(maU.group(1).replace(",", "."))
    elif mkat:
        x = float(mkat.group(1).replace(",", "."))
        faktor = 1 / x if (azalt and x != 0) else x
    else:
        faktor = 0.6 if azalt else 1.6
    if faktor is not None:
        faktor = max(0.25, min(4.0, faktor))
    return dict(tip=tip, hedef=hedef, kaynak=kaynak, cap_km=cap, hiz=hiz, sinif=sn, faktor=faktor, au=au)


def carpma_hesapla(hedef_v, cap_km, hiz_kms, rho_cisim=3000.0, kutle_kg=None, aci=45.0):
    """Çarpma enerjisi, krater boyutu ve etki sınıfı."""
    M_h, g, rho_h, vk = fiziksel(hedef_v)
    v = hiz_kms * 1000.0
    L = cap_km * 1000.0
    m = kutle_kg if kutle_kg else rho_cisim * 4 / 3 * math.pi * (L / 2) ** 3
    E = 0.5 * m * v * v
    Emt = E / MEGATON
    U = 3 * G * M_h ** 2 / (5 * hedef_v["yaricap_km"] * 1000.0)       # bağlanma enerjisi
    oran = E / U
    devmi = gaz_devi_mi(hedef_v)
    p = float(hedef_v.get("basinc") or 0)
    krater = None
    if not devmi and oran < 1e-4:
        rho_t = 900.0 if hedef_v.get("doku") == "gaz" and hedef_v["ad"] not in GERCEK else 2500.0
        d_tc = (1.161 * (rho_cisim / rho_t) ** (1 / 3) * L ** 0.78 * v ** 0.44 * g ** -0.22
                * math.sin(math.radians(aci)) ** (1 / 3))
        dc = 3200.0 * G_DUNYA / g
        d_f = 1.25 * d_tc if 1.25 * d_tc < dc else 1.17 * d_tc ** 1.13 / dc ** 0.13
        krater = d_f / 1000.0
    hava = (not devmi and kutle_kg is None and p >= 0.3 and L < 50.0)
    if oran >= 1.0:
        sn = "Gezegen parçalanır / küresel yeniden şekillenme"
    elif oran >= 1e-3:
        sn = "Dev çarpışma: kabuk ve manto erir, Ay benzeri uydu oluşturabilecek enkaz fırlar"
    elif Emt >= 1e8:
        sn = "Küresel kıyamet (Chicxulub düzeyi ve üstü): kitlesel yok oluş"
    elif Emt >= 1e5:
        sn = "Küresel iklim çöküşü; toz ve kül yıllarca güneşi kapatır"
    elif Emt >= 1e3:
        sn = "Kıtasal yıkım, bölgesel iklim etkisi"
    elif Emt >= 1.0:
        sn = "Bölgesel yıkım (şehir/ülke ölçeği)"
    else:
        sn = "Yerel etki"
    if hava:
        sn = "Atmosferde parçalanır (hava patlaması); yüzeyde krater oluşmayabilir"
    return dict(E=E, Emt=Emt, bag_orani=oran, krater_km=krater, sinif=sn, devmi=devmi, hava=hava, frac=oran)


def carpma_metni(hedef_v, h, cap_km, hiz, kaynak_ad=None):
    L = []
    kim = f"{kaynak_ad} " if kaynak_ad else ""
    L.append(f"ÇARPMA: {kim}→ {hedef_v['ad']} | cisim çapı {uzunluk(cap_km)}, hız {tr(hiz, 1)} km/s")
    L.append(f"Enerji ≈ {bilimsel(h['E'])} J ≈ {bilimsel(h['Emt'])} megaton TNT (Chicxulub çarpması ≈ 10^8 megaton).")
    L.append(f"Gezegenin bağlanma enerjisinin %{bilimsel(h['bag_orani'] * 100)}'i.")
    if h["krater_km"]:
        L.append(f"Tahmini krater çapı ≈ {tr(h['krater_km'], 1)} km.")
    elif h["devmi"]:
        L.append("Katı yüzey olmadığından krater oluşmaz; cisim bulutlara gömülüp atmosferde buharlaşır.")
    else:
        L.append("Krater formülü bu ölçekte geçerli değil; etki küresel yeniden şekillenmedir.")
    L.append("Sonuç: " + h["sinif"] + ".")
    return "\n".join(L)


def gunes_cme_hiz(sn):
    harf, sayi = sn[0], float(sn[1:] or 1)
    return {"C": 400.0, "M": 800.0}.get(harf, 2500.0 if sayi >= 10 else 1500.0)


def gunes_akisi(sn):
    harf, sayi = sn[0], float(sn[1:] or 1)
    return {"C": 1e-6, "M": 1e-5, "X": 1e-4}[harf] * sayi


def gunes_etki(v):
    ad = v["ad"]
    ozel = {
        "Dünya": "Manyetosfer korur; jeomanyetik fırtına, güçlü kutup ışıkları; uydu, GPS ve elektrik şebekesi risk altında.",
        "Mars": "Küresel manyetik alan yok: parçacık yağmuru yüzey radyasyonunu artırır, üst atmosferin kaybını hızlandırır.",
        "Venüs": "Kendi manyetik alanı yok; kalın atmosfer yüzeyi korur, üst atmosfer iyonlaşır ve kaybı artar.",
        "Merkür": "Zayıf manyetosfer yüzeye kadar sıkışır; yüzey doğrudan sert radyasyona maruz.",
        "Ay": "Atmosfer ve manyetosfer yok; yüzey doğrudan ışınlanır.",
        "Jüpiter": "Güçlü manyetosfer: kutup ışıkları parlaklaşır, radyasyon kuşakları şişer.",
        "Satürn": "Manyetosfer kutup ışıklarını parlatır; halkalar parçacıkla yüklenir.",
        "Uranüs": "Eğik manyetosfer: düzensiz kutup ışıkları.",
        "Neptün": "Eğik manyetosfer: düzensiz kutup ışıkları.",
    }
    if ad in ozel:
        return ozel[ad]
    if float(v.get("basinc") or 0) < 0.01:
        return "Atmosfer yok: yüzey doğrudan sert radyasyona maruz."
    return "Üst atmosfer iyonlaşır, kutup ışığı benzeri parlamalar olur; yüzey atmosfer tarafından kısmen korunur."


def gunes_raporu(sn, tumu):
    """(başlık metni, {gezegen adı: metin})"""
    akis = gunes_akisi(sn)
    cme = gunes_cme_hiz(sn)
    baslik = (f"GÜNEŞ PATLAMASI: {sn} sınıfı (1 AU'da X-ışını akısı ≈ {bilimsel(akis)} W/m²), "
              f"CME hızı ≈ {tr(cme, 0)} km/s. Akı mesafenin karesiyle azalır.")
    sonuc = {}
    for w in tumu:
        au = max(0.05, float(w.get("au", 1)))
        if au > 40:
            continue                              # kullanıcı gezegenlerinin AU değeri simülasyon ölçeğindedir
        saat = au * 1.496e8 / cme / 3600
        sonuc[w["ad"]] = (f"{w['ad']} ({tr(au, 2)} AU): akı ≈ {bilimsel(akis / au ** 2)} W/m², CME ≈ {tr(saat, 0)} saatte ulaşır. "
                          + gunes_etki(w))
    return baslik, sonuc


def yorunge_hesapla(v, faktor=None, au_hedef=None):
    """Yörünge uzaklığını değiştirince yeni AU, periyot, sıcaklık ve yaşanabilirlik."""
    au0 = float(v["au"])
    au1 = au_hedef if au_hedef else au0 * faktor
    au1 = max(0.1, au1)
    f = au1 / au0
    per1 = float(v["periyot"]) * f ** 1.5
    t1 = (float(v["sicak"]) + 273.15) * f ** -0.5 - 273.15
    yeni = dict(v, au=au1, periyot=per1, sicak=t1)
    a0, a1 = analiz(v), analiz(yeni)
    metin = (f"YÖRÜNGE DEĞİŞİMİ: {v['ad']} Güneş'ten {tr(au0, 2)} AU → {tr(au1, 2)} AU ({tr(f, 2)} kat).\n"
             f"Yıl uzunluğu (Kepler): {tr(float(v['periyot']), 0)} gün → {tr(per1, 0)} gün.\n"
             f"Denge sıcaklığı yaklaşık {tr(float(v['sicak']), 0)} °C → {tr(t1, 0)} °C (sera etkisi ve atmosfer değişimi hesaba katılmadı).\n"
             f"Genel yaşanabilirlik %{tr(a0['genel'], 0)} → %{tr(a1['genel'], 0)}, insan %{tr(a0['insan'], 0)} → %{tr(a1['insan'], 0)}.")
    return dict(au=au1, periyot=per1, sicak=t1, metin=metin, f=f)


if __name__ == "__main__":
    print(analiz_raporu(dict(ad="Mars", renk="#b4532f", yaricap_km=3390, au=1.52, periyot=687, uydu=2, sicak=-63,
                             basinc=0.006, ruzgar=20, atm_renk="#e5a070", atm_k=.2, doku="kaya",
                             gazlar=[("Karbondioksit", 95), ("Azot", 3), ("Argon", 2)])))
