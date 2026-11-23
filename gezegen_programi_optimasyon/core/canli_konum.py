"""Gezegenlerin GERÇEK güncel konumları.

1) NASA JPL Horizons API'sinden (internet gerekir, ek kurulum yok: yalnızca standart kütüphane)
   her gezegenin Güneş merkezli ekliptik boylamı alınır.
2) İnternet yoksa ya da istek başarısız olursa, JPL'nin yayımladığı yaklaşık yörünge
   elemanlarından (Keplerian elements, 1800-2050) aynı boylam yerelde hesaplanır.

Ağ istekleri ayrı bir iş parçacığında yapılır; program donmaz.
"""
import json
import math
import threading
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
HORIZONS_ID = {"Merkür": "199", "Venüs": "299", "Dünya": "399", "Mars": "499",
               "Jüpiter": "599", "Satürn": "699", "Uranüs": "799", "Neptün": "899"}

# a [AU], e, I [°], L [°], boylam_günberi [°], çıkış_düğümü [°]  ve yüzyıllık değişimleri
ELEMAN = {
    "Merkür": ((0.38709927, 0.00000037), (0.20563593, 0.00001906), (7.00497902, -0.00594749),
               (252.25032350, 149472.67411175), (77.45779628, 0.16047689), (48.33076593, -0.12534081)),
    "Venüs": ((0.72333566, 0.00000390), (0.00677672, -0.00004107), (3.39467605, -0.00078890),
              (181.97909950, 58517.81538729), (131.60246718, 0.00268329), (76.67984255, -0.27769418)),
    "Dünya": ((1.00000261, 0.00000562), (0.01671123, -0.00004392), (-0.00001531, -0.01294668),
              (100.46457166, 35999.37244981), (102.93768193, 0.32327364), (0.0, 0.0)),
    "Mars": ((1.52371034, 0.00001847), (0.09339410, 0.00007882), (1.84969142, -0.00813131),
             (-4.55343205, 19140.30268499), (-23.94362959, 0.44441088), (49.55953891, -0.29257343)),
    "Jüpiter": ((5.20288700, -0.00011607), (0.04838624, -0.00013253), (1.30439695, -0.00183714),
                (34.39644051, 3034.74612775), (14.72847983, 0.21252668), (100.47390909, 0.20469106)),
    "Satürn": ((9.53667594, -0.00125060), (0.05386179, -0.00050991), (2.48599187, 0.00193609),
               (49.95424423, 1222.49362201), (92.59887831, -0.41897216), (113.66242448, -0.28867794)),
    "Uranüs": ((19.18916464, -0.00196176), (0.04725744, -0.00004397), (0.77263783, -0.00242939),
               (313.23810451, 428.48202785), (170.95427630, 0.40805281), (74.01692503, 0.04240589)),
    "Neptün": ((30.06992276, 0.00026291), (0.00859048, 0.00005105), (1.77004347, 0.00035372),
               (-55.12002969, 218.45945325), (44.96476227, -0.32241464), (131.78422574, -0.00508664)),
}


def _jd(an):
    return an.timestamp() / 86400.0 + 2440587.5


def yaklasik_boylam(ad, an):
    """Güneş merkezli ekliptik boylam (derece), internetsiz hesap."""
    T = (_jd(an) - 2451545.0) / 36525.0
    a, e, I, L, vp, Om = [x0 + x1 * T for x0, x1 in ELEMAN[ad]]
    M = math.radians((L - vp + 180.0) % 360.0 - 180.0)
    E = M
    for _ in range(12):
        E -= (E - e * math.sin(E) - M) / (1.0 - e * math.cos(E))
    xp, yp = a * (math.cos(E) - e), a * math.sqrt(1.0 - e * e) * math.sin(E)
    w, Om_r, I_r = math.radians(vp - Om), math.radians(Om), math.radians(I)
    cw, sw, co, so, ci = math.cos(w), math.sin(w), math.cos(Om_r), math.sin(Om_r), math.cos(I_r)
    x = (cw * co - sw * so * ci) * xp + (-sw * co - cw * so * ci) * yp
    y = (cw * so + sw * co * ci) * xp + (-sw * so + cw * co * ci) * yp
    return math.degrees(math.atan2(y, x)) % 360.0


def horizons_boylam(ad, an, zaman_asimi=8):
    """NASA JPL Horizons'tan Güneş merkezli ekliptik boylam (derece)."""
    bas = an.strftime("%Y-%m-%d %H:%M")
    bit = (an + timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
    q = {"format": "json", "COMMAND": f"'{HORIZONS_ID[ad]}'", "OBJ_DATA": "'NO'", "MAKE_EPHEM": "'YES'",
         "EPHEM_TYPE": "'VECTORS'", "CENTER": "'500@10'", "START_TIME": f"'{bas}'", "STOP_TIME": f"'{bit}'",
         "STEP_SIZE": "'1 d'", "VEC_TABLE": "'1'", "REF_PLANE": "'ECLIPTIC'", "OUT_UNITS": "'AU-D'",
         "CSV_FORMAT": "'YES'"}
    istek = urllib.request.Request(URL + "?" + urllib.parse.urlencode(q), headers={"User-Agent": "GezegenLab/1.0"})
    with urllib.request.urlopen(istek, timeout=zaman_asimi) as r:
        metin = json.loads(r.read().decode("utf-8", "replace"))["result"]
    satir = metin.split("$$SOE")[1].split("$$EOE")[0].strip().splitlines()[0]
    p = [s.strip() for s in satir.split(",")]
    return math.degrees(math.atan2(float(p[3]), float(p[2]))) % 360.0


class Sonuc:
    def __init__(self):
        self.bitti = False
        self.boylam = {}        # ad -> derece
        self.kaynak = {}        # ad -> "NASA JPL" | "yerel hesap"
        self.an = None          # sorgulanan UTC zamanı


def baslat():
    """Arka planda tüm gezegenlerin konumunu alır; dönen nesnenin .bitti alanı True olunca hazırdır."""
    s = Sonuc()
    s.an = datetime.now(timezone.utc)

    def is_():
        ag_yok = False
        for ad in HORIZONS_ID:
            deger, kaynak = None, "yerel hesap"
            if not ag_yok:
                try:
                    deger, kaynak = horizons_boylam(ad, s.an), "NASA JPL"
                except Exception:
                    ag_yok = True           # bir kez başarısızsa kalan gezegenler için bekletme
            if deger is None:
                deger = yaklasik_boylam(ad, s.an)
            s.boylam[ad], s.kaynak[ad] = deger, kaynak
        s.bitti = True

    threading.Thread(target=is_, daemon=True).start()
    return s
