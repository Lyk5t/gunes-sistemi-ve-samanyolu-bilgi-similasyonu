"""Yüzey keşfi: gezegene sağ tıklayıp “Gör” deyince gezegenin yüzeyinde bir insanla dolaşılır.

Gezegenin özellikleri deneyimi belirler:
  - yerçekimi        : zıplama yüksekliği ve düşüş hızı (Mars’ta uçar gibi, Jüpiter’de ağır)
  - atmosfer rengi   : gökyüzü, ufuk sisi ve havadaki toz parçacıkları
  - Güneş’e uzaklık  : Güneş’in gökteki büyüklüğü ve ışığın şiddeti
  - sıcaklık/basınç  : insan uzay giysisi giyer mi, zemine buz/sıcaklık tonu
  - rüzgâr           : havada uçuşan parçacıkların hızı
  - tür              : kayalıkta kraterler ve tepeler, Dünya’da su ve kıtalar,
                       gaz devlerinde katı yüzey yok (bulutların üstünde süzülen platform)
Gezegen yüzeyi açılışta kısa bir süre “biçimlenir”: ilk anda parlak ve düzdür, sonra yükselip soğur.
"""
import math
import random
import time

from ursina import Entity, Mesh, Shader, Sky, Texture, Vec3, application, camera, destroy, held_keys, mouse, scene, window
from ursina.color import Color

import dokular
from arayuz import Dugme, Yazi
from dokular import PALET, hex_rgb, ton

OFS = Vec3(30000, 0, 0)     # yüzey dünyası Güneş Sisteminden çok uzakta kurulur, birbirini görmezler
BOYUT, N = 240, 97          # arazi: 240 m x 240 m, 97 x 97 köşe
BICIMLENME_SURESI = 9.0     # gezegenin biçimlenme süresi (saniye)
SISLI_GOLGELEME = True      # ufuk sisi için özel gölgelendirici; sorun çıkarırsa False yapın
GUNES_YONU = (0.45, 0.78, 0.42)

YERCEKIMI = {"Merkür": 3.70, "Venüs": 8.87, "Dünya": 9.81, "Mars": 3.71,
             "Jüpiter": 24.79, "Satürn": 10.44, "Uranüs": 8.69, "Neptün": 11.15}
KAYALIK = {"Merkür", "Venüs", "Dünya", "Mars"}
GAZ_DEVLERI = {"Jüpiter", "Satürn", "Uranüs", "Neptün"}
PROFIL = {   # gen: yükseklik genliği (m), olcek: tepe genişliği (m), krater: krater sayısı
    "Merkür": dict(gen=9, olcek=55, krater=14),
    "Venüs": dict(gen=24, olcek=75, krater=1),
    "Dünya": dict(gen=15, olcek=60, krater=0),
    "Mars": dict(gen=18, olcek=70, krater=8),
}


def gaz_mi(v):
    if v["ad"] in KAYALIK:
        return False
    if v["ad"] in GAZ_DEVLERI:
        return True
    return v.get("doku") == "gaz"


def yercekimi(v):
    if v["ad"] in YERCEKIMI:
        return YERCEKIMI[v["ad"]]
    yogunluk = 1.3 if gaz_mi(v) else 5.5          # g ~ yoğunluk x yarıçap
    return max(1.0, min(60.0, 9.81 * (v["yaricap_km"] / 6371) * yogunluk / 5.51))


def uzay_giysisi_gerekli(v):
    if gaz_mi(v):
        return True, "gaz devinde nefes alınamaz"
    if v["sicak"] > 45:
        return True, "çok sıcak"
    if v["sicak"] < -25:
        return True, "çok soğuk"
    if v["basinc"] < 0.3:
        return True, "basınç çok düşük"
    if v["basinc"] > 5:
        return True, "basınç çok yüksek"
    return False, "gerekmiyor"


# =====================================================================
#  ARAZİ (saf Python: Ursina gerektirmez, ayrı test edilebilir)
# =====================================================================
class Gurultu:
    """Düzgün değer gürültüsü (0-1), her yönde tekrarlanır."""

    def __init__(self, R, n=64):
        self.n = n
        self.t = [[R.random() for _ in range(n)] for _ in range(n)]

    def deger(self, x, y):
        n, t = self.n, self.t
        xi, yi = math.floor(x), math.floor(y)
        fx, fy = x - xi, y - yi
        fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
        a, b = t[xi % n][yi % n], t[(xi + 1) % n][yi % n]
        c, d = t[xi % n][(yi + 1) % n], t[(xi + 1) % n][(yi + 1) % n]
        return a + (b - a) * fx + (c - a) * fy + (a - b - c + d) * fx * fy


def karistir(a, b, k):
    return tuple(a[i] + (b[i] - a[i]) * k for i in range(3))


def duraklar(d, u):
    """d: [(konum, (r,g,b)), ...] sıralı duraklar; u: 0-1."""
    u = max(0.0, min(1.0, u))
    for (u0, c0), (u1, c1) in zip(d, d[1:]):
        if u <= u1:
            return karistir(c0, c1, (u - u0) / ((u1 - u0) or 1))
    return d[-1][1]


class Arazi:
    def __init__(self, v):
        self.v, ad = v, v["ad"]
        self.gaz = gaz_mi(v)
        self.tur = "dunya" if ad == "Dünya" else ("gaz" if self.gaz else "kaya")
        self.p = PROFIL.get(ad) or (dict(gen=3.5, olcek=45, krater=0) if self.gaz else dict(gen=12, olcek=55, krater=4))
        R = random.Random(sum(map(ord, ad)) * 131)
        self.gur = Gurultu(R)
        self.rnd = R
        self.kraterler = [(R.uniform(-95, 95), R.uniform(-95, 95), R.uniform(8, 26)) for _ in range(self.p["krater"])]
        ana = hex_rgb(v["renk"])
        self.pal = tuple(hex_rgb(c) for c in PALET[ad]) if ad in PALET else (ton(ana, .55), ana, ton(ana, 1.35))
        self.su = -1.8 if self.tur == "dunya" else None      # su yüzeyinin yüksekliği

    def yukseklik(self, x, z):
        p, s, a, f, t = self.p, 0.0, 1.0, 1.0 / self.p["olcek"], 0.0
        for _ in range(4):
            s += a * self.gur.deger(x * f + 40, z * f + 40)
            t += a
            a *= .5
            f *= 2.07
        h = (s / t - .5) * 2 * p["gen"]
        for cx, cz, r in self.kraterler:
            d = math.hypot(x - cx, z - cz)
            if d < r * 1.35:
                q = d / r
                h += -(1 - q * q) * r * .28 if q < 1 else r * .07 * (1 - (q - 1) / .35)
        return h

    def zemin_rengi(self, h, u, egim, x, z):
        koyu, orta, acik = self.pal
        if self.tur == "dunya":
            c = duraklar([(0, (70, 112, 56)), (.5, (96, 134, 66)), (.8, (120, 110, 96)), (1, (240, 243, 248))], u)
            if h < self.su + .9:
                c = karistir(c, (194, 178, 128), max(0.0, min(1.0, 1 - (h - self.su) / .9)))
        elif self.tur == "gaz":
            t = .5 + .5 * math.sin(z * .06 + 2 * self.gur.deger(x * .02, z * .02))
            c = duraklar([(0, koyu), (.5, orta), (1, acik)], t)
        else:
            c = duraklar([(0, koyu), (.5, orta), (1, acik)], u)
            c = tuple(v_ * (1 - min(.45, egim * 1.3)) for v_ in c)
        sicak = self.v["sicak"]
        if sicak < -100:
            c = karistir(c, (220, 235, 255), .22)       # buzlu ton
        elif sicak > 300:
            c = karistir(c, (255, 130, 50), .20)        # kızgın ton
        k = 1 + (self.rnd.random() - .5) * .10          # ince dokulu taneler
        return tuple(max(0, min(255, v_ * k)) for v_ in c)

    def mesh_verisi(self):
        """(köşeler, renkler, üçgenler): Ursina’ya verilecek ham veri."""
        yarim, adim = BOYUT / 2, BOYUT / (N - 1)
        yuk = [[self.yukseklik(-yarim + i * adim, -yarim + j * adim) for j in range(N)] for i in range(N)]
        lo, hi = min(map(min, yuk)), max(map(max, yuk))
        L = GUNES_YONU
        ln = math.sqrt(sum(c * c for c in L))
        L = tuple(c / ln for c in L)
        au = self.v["au"]
        parlak = max(.5, min(1.15, 1.15 / au ** .35))          # uzak gezegende ışık azalır
        verts, cols, tris = [], [], []
        for i in range(N):
            for j in range(N):
                x, z, h = -yarim + i * adim, -yarim + j * adim, yuk[i][j]
                hx_ = yuk[min(i + 1, N - 1)][j] - yuk[max(i - 1, 0)][j]
                hz_ = yuk[i][min(j + 1, N - 1)] - yuk[i][max(j - 1, 0)]
                nx, ny, nz = -hx_ / (2 * adim), 1.0, -hz_ / (2 * adim)
                nn = math.sqrt(nx * nx + ny * ny + nz * nz)
                nx, ny, nz = nx / nn, ny / nn, nz / nn
                isik = .28 + .72 * max(0.0, nx * L[0] + ny * L[1] + nz * L[2])
                c = self.zemin_rengi(h, (h - lo) / ((hi - lo) or 1), 1 - ny, x, z)
                verts.append((x, h, z))
                cols.append(tuple(min(1.0, c[k] / 255 * isik * parlak) for k in range(3)))
        for i in range(N - 1):
            for j in range(N - 1):
                a = i * N + j
                tris += [(a, a + 1, a + N), (a + 1, a + N + 1, a + N)]
        return verts, cols, tris


# =====================================================================
#  İNSAN
# =====================================================================
class Insan(Entity):
    def __init__(self, uzay):
        super().__init__()
        giysi = Color(.95, .95, .97, 1) if uzay else Color(.20, .45, .85, 1)
        pantolon = Color(.85, .85, .90, 1) if uzay else Color(.16, .18, .28, 1)
        ten = Color(.95, .75, .60, 1)
        self.faz = 0.0
        Entity(parent=self, model="cube", color=giysi, scale=(.55, .75, .30), y=1.2)
        Entity(parent=self, model="sphere", color=ten, scale=.34, y=1.78)
        if uzay:
            Entity(parent=self, model="sphere", color=Color(.75, .90, 1, .35), scale=.52, y=1.78)
            Entity(parent=self, model="cube", color=Color(.8, .8, .85, 1), scale=(.4, .55, .18), y=1.22, z=-.24)
            Entity(parent=self, model="cube", color=Color(1, .5, .1, 1), scale=(.57, .08, .32), y=1.0)
        else:
            Entity(parent=self, model="sphere", color=Color(.25, .15, .1, 1), scale=(.36, .22, .36), y=1.88)
        self.kollar, self.bacaklar = [], []
        for yon in (-1, 1):
            p = Entity(parent=self, y=1.5, x=.38 * yon)
            Entity(parent=p, model="cube", color=giysi, scale=(.16, .60, .16), y=-.30)
            self.kollar.append(p)
            q = Entity(parent=self, y=.85, x=.14 * yon)
            Entity(parent=q, model="cube", color=pantolon, scale=(.20, .85, .20), y=-.42)
            self.bacaklar.append(q)

    def yurut(self, hiz, dt, havada):
        if havada:
            self.faz += dt * 3
            salin = .25
        else:
            self.faz += dt * max(0.0, hiz) * 2.2
            salin = min(1.0, hiz / 4.0)
        s = math.sin(self.faz) * 38 * salin
        self.kollar[0].rotation_x, self.kollar[1].rotation_x = s, -s
        self.bacaklar[0].rotation_x, self.bacaklar[1].rotation_x = -s, s


# =====================================================================
#  SİS GÖLGELENDİRİCİSİ (ufuk gökyüzü rengine karışır)
# =====================================================================
VS_SIS = """#version 140
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelViewMatrix;
in vec4 p3d_Vertex;
in vec4 p3d_Color;
out vec4 renk;
out float uzak;
void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    renk = p3d_Color;
    uzak = length((p3d_ModelViewMatrix * p3d_Vertex).xyz);
}"""
FS_SIS = """#version 140
uniform vec4 p3d_ColorScale;
uniform vec3 sis_renk;
uniform float sis_yakin;
uniform float sis_uzak;
in vec4 renk;
in float uzak;
out vec4 fragColor;
void main() {
    float f = clamp((uzak - sis_yakin) / (sis_uzak - sis_yakin), 0.0, 1.0);
    vec4 c = renk * p3d_ColorScale;
    fragColor = vec4(mix(c.rgb, sis_renk, f), c.a);
}"""
_sis = None


def sis_golge():
    global _sis
    if _sis is None:
        _sis = Shader(language=Shader.GLSL, vertex=VS_SIS, fragment=FS_SIS)
    return _sis


# =====================================================================
#  YÜZEY SAHNESİ
# =====================================================================
class Yuzey(Entity):
    def __init__(self, uygulama, gezegen):
        super().__init__()
        self.u, self.g = uygulama, gezegen
        v = self.v = gezegen.v
        self.t, self.cikis_t = 0.0, None
        self.parcalar, self.toz = [], []
        self.yg = yercekimi(v)
        self.uzay, self.uzay_neden = uzay_giysisi_gerekli(v)
        self.arazi_v = Arazi(v)

        # ana programı ve arayüzünü bekletir
        uygulama.enabled = False
        try:
            if getattr(uygulama, "siren_sesi", None):
                uygulama.siren_sesi.stop()
                uygulama.siren_caliyor = False
        except Exception:
            pass
        self.gizlenen = [e for e in camera.ui.children if e.enabled]
        for e in self.gizlenen:
            e.enabled = False
        self.eski_renk, self.eski_fov = window.color, camera.fov
        camera.fov = 70

        # gökyüzü ve sis
        k = v["atm_k"]
        atm = hex_rgb(v["atm_renk"])
        gok = tuple(c / 255 * min(1.0, k * 1.3) for c in atm)
        self.yildizli = k < .25
        window.color = Color(0, 0, 0, 1) if self.yildizli else Color(*gok, 1)
        self.sis_renk = (0, 0, 0) if self.yildizli else gok
        self.sis_uzak = min(115.0, 600 * (1 - k) + 60)
        self.sis_yakin = self.sis_uzak * .30 if not self.yildizli else self.sis_uzak * .45
        self.skyler = [e for e in scene.entities if isinstance(e, Sky)]
        self.sky_eski = [e.enabled for e in self.skyler]
        for e in self.skyler:
            e.enabled = self.yildizli

        # arazi
        verts, cols, tris = self.arazi_v.mesh_verisi()
        mesh = Mesh(vertices=[Vec3(*p) for p in verts], triangles=tris,
                    colors=[Color(*c, 1) for c in cols])
        self.arazi = self.ekle(Entity(model=mesh, position=OFS, double_sided=True, scale_y=.001))
        if self.arazi_v.su is not None:
            su = self.arazi_v.su
            yr = 500
            sm = Mesh(vertices=[Vec3(-yr, su, -yr), Vec3(-yr, su, yr), Vec3(yr, su, -yr), Vec3(yr, su, yr)],
                      triangles=[(0, 1, 2), (1, 3, 2)], colors=[Color(.10, .32, .62, 1)] * 4)
            self.su_e = self.ekle(Entity(model=sm, position=OFS, double_sided=True))
        else:
            self.su_e = None
        if SISLI_GOLGELEME:
            for e in (self.arazi, self.su_e):
                if e is not None:
                    e.shader = sis_golge()
                    e.setShaderInput("sis_renk", Vec3(*self.sis_renk))
                    e.setShaderInput("sis_yakin", float(self.sis_yakin))
                    e.setShaderInput("sis_uzak", float(self.sis_uzak))

        # Güneş (uzaklığa göre küçülür, kalın atmosferde silikleşir)
        L = Vec3(*GUNES_YONU).normalized()
        self.ekle(Entity(model="quad", texture=Texture(dokular.parilti((255, 235, 190))), billboard=True,
                         position=OFS + L * 260, scale=max(1.5, min(120.0, 45 / max(.3, v["au"]))),
                         color=Color(1, .97, .85, max(.15, 1 - .85 * k))))

        # insan
        self.insan = self.ekle(Insan(self.uzay))
        self.px = self.pz = 0.0
        self.py = self.zemin(0, 0)
        self.vy, self.yerde, self.suda = 0.0, True, False
        self.yaw, self.pitch, self.mesafe = 20.0, 22.0, 6.5

        # havadaki parçacıklar (rüzgâr)
        R = random.Random(5)
        sayi = int(30 + 90 * min(1.0, k * 2)) if k > .05 else 0
        self.ruzgar_hizi = min(150.0, v["ruzgar"]) / 8 + .3
        yon = math.radians(R.uniform(0, 360))
        self.ruzgar_yon = Vec3(math.cos(yon), 0, math.sin(yon))
        rgb = tuple(min(1, c / 255 * 1.2 + .2) for c in atm)
        for _ in range(sayi):
            e = self.ekle(Entity(model="quad", billboard=True, scale=R.uniform(.12, .4),
                                 color=Color(*rgb, .40)))
            e.rel = Vec3(R.uniform(-22, 22), R.uniform(.2, 9), R.uniform(-22, 22))
            self.toz.append(e)

        # arayüz
        self.arayuz_kur()
        self.perde = Entity(parent=camera.ui, model="quad", color=Color(0, 0, 0, 1), scale=(4, 2), z=-5)
        self.hud_ogeleri.append(self.perde)

    # ---------- yardımcılar ----------
    def ekle(self, e):
        self.parcalar.append(e)
        return e

    def zemin(self, x, z):
        """İnsanın ayağının bastığı yükseklik (arazi biçimlenirken birlikte yükselir)."""
        h = self.arazi_v.yukseklik(x, z) * self.bicim
        if self.arazi_v.su is not None and h < self.arazi_v.su:
            self.suda = True
            return self.arazi_v.su - .85
        self.suda = False
        return h

    @property
    def bicim(self):
        b = min(1.0, self.t / BICIMLENME_SURESI)
        return max(.001, b * b * (3 - 2 * b))

    # ---------- arayüz ----------
    def arayuz_kur(self):
        v, ui = self.v, camera.ui
        self.hud_ogeleri = []

        def y(metin, x, yy, olcek, renk):
            t = Yazi(parent=ui, text=metin, position=(x, yy), scale=olcek, color=renk)
            self.hud_ogeleri.append(t)
            return t
        sol = -window.aspect_ratio / 2 + .04
        y(v["ad"].upper(), sol, .46, 2.2, Color(1, .83, .42, 1))
        satirlar = [
            f"Yerçekimi: {self.yg:.2f} m/s²  ({self.yg / 9.81:.2f} g)",
            f"Sıcaklık: {v['sicak']:g} °C     Basınç: {v['basinc']:g} bar",
            f"Rüzgâr: {v['ruzgar']:g} m/s     Atmosfer: " + ("çok ince" if v["atm_k"] < .1 else f"%{int(v['atm_k'] * 100)} yoğunluk"),
            "Uzay giysisi: " + (f"VAR ({self.uzay_neden})" if self.uzay else "gerekmiyor"),
        ]
        for i, s in enumerate(satirlar):
            y(s, sol, .405 - i * .032, 1.0, Color(.93, .92, 1, 1) if i < 3 else Color(1, .7, .4, 1) if self.uzay else Color(.6, 1, .7, 1))
        if self.arazi_v.gaz:
            y("Katı yüzey yok: bulutların üzerinde süzülen bir platformdasınız.", sol, .275, .9, Color(.7, .85, 1, 1))
        self.durum = y(" ", -.28, .43, 1.6, Color(1, .6, .25, 1))
        y("W A S D: yürü   Shift: koş   Boşluk: zıpla   Sağ tuş + sürükle (ya da Q/E): etrafa bak   Tekerlek: yakınlaş   Esc: çık",
          -.55, -.475, .9, Color(.75, .75, .9, 1))
        d = Dugme(parent=ui, text="Çık", position=(window.aspect_ratio / 2 - .09, .46), scale=(.12, .045),
                  color=Color(1, .37, .63, 1), on_click=self.cik)
        self.hud_ogeleri.append(d)

    # ---------- olaylar ----------
    def input(self, key):
        if key == "scroll up":
            self.mesafe = max(2.5, self.mesafe * .9)
        elif key == "scroll down":
            self.mesafe = min(16.0, self.mesafe * 1.1)
        elif key == "escape":
            self.cik()

    def cik(self):
        if self.cikis_t is None:
            self.cikis_t = 0.0

    def geri_don(self):
        for e in self.parcalar + self.hud_ogeleri:
            destroy(e)
        for e, a in zip(self.skyler, self.sky_eski):
            e.enabled = a
        window.color, camera.fov = self.eski_renk, self.eski_fov
        for e in self.gizlenen:
            e.enabled = True
        self.u.enabled = True
        destroy(self)

    # ---------- her kare ----------
    def update(self):
        dt = min(time.dt, .05)
        self.t += dt
        if self.cikis_t is None:
            self.perde.color = Color(0, 0, 0, max(0.0, 1 - self.t / .9))
        else:
            self.cikis_t += dt
            self.perde.color = Color(0, 0, 0, min(1.0, self.cikis_t / .5))
            if self.cikis_t >= .55:
                self.geri_don()
                return

        # biçimlenme: yüzey yükselir, kızgın tondan doğal renge soğur
        e = self.bicim
        self.arazi.scale_y = e
        self.arazi.color = Color(1, .45 + .55 * e, .25 + .75 * e, 1)
        b = min(1.0, self.t / BICIMLENME_SURESI)
        if b < 1:
            self.durum.text = f"GEZEGEN BİÇİMLENİYOR…  %{int(b * 100)}"
        elif self.t < BICIMLENME_SURESI + 3:
            self.durum.text = "Yüzey hazır, keşfedin."
        else:
            self.durum.text = " "

        # kamera dönüşü
        if held_keys["right mouse"]:
            self.yaw += mouse.velocity[0] * 140
            self.pitch = max(-5.0, min(75.0, self.pitch - mouse.velocity[1] * 100))
        self.yaw += (held_keys["e"] - held_keys["q"]) * dt * 90

        # hareket (kameraya göre)
        yw = math.radians(self.yaw)
        ileri, sag = Vec3(math.sin(yw), 0, math.cos(yw)), Vec3(math.cos(yw), 0, -math.sin(yw))
        ix = held_keys["d"] - held_keys["a"] + held_keys["right arrow"] - held_keys["left arrow"]
        iz = held_keys["w"] - held_keys["s"] + held_keys["up arrow"] - held_keys["down arrow"]
        hareket = ileri * iz + sag * ix
        hiz = 0.0
        if hareket.length() > 0:
            hiz = 4.5 * (1.8 if held_keys["left shift"] else 1.0) * min(1.3, max(.6, (9.81 / self.yg) ** .2))
            if self.suda:
                hiz *= .55
            hareket = hareket.normalized()
            self.px = max(-105, min(105, self.px + hareket.x * hiz * dt))
            self.pz = max(-105, min(105, self.pz + hareket.z * hiz * dt))
            self.insan.rotation_y = math.degrees(math.atan2(hareket.x, hareket.z))

        # zıplama ve yerçekimi: aynı hızla zıplar, yerçekimine göre yükselir
        zemin = self.zemin(self.px, self.pz)
        if self.yerde and held_keys["space"]:
            self.vy, self.yerde = 4.4, False
        self.vy -= self.yg * dt
        self.py += self.vy * dt
        if self.py <= zemin:
            self.py, self.vy, self.yerde = zemin, 0.0, True
        elif self.yerde and self.py > zemin + .05:
            self.yerde = False
        self.insan.position = OFS + Vec3(self.px, self.py, self.pz)
        self.insan.yurut(hiz, dt, not self.yerde)

        # kamera (üçüncü şahıs)
        hedef = self.insan.position + Vec3(0, 1.6, 0)
        p = math.radians(self.pitch)
        kp = hedef + Vec3(math.sin(yw) * math.cos(p), math.sin(p), -math.cos(yw) * math.cos(p)) * (-self.mesafe)
        kp = Vec3(kp.x, max(kp.y, OFS.y + self.arazi_v.yukseklik(kp.x - OFS.x, kp.z - OFS.z) * e + .6), kp.z)
        camera.position = kp
        camera.look_at(hedef)

        # rüzgârla savrulan parçacıklar
        for z in self.toz:
            z.rel += self.ruzgar_yon * self.ruzgar_hizi * dt
            for ek in ("x", "z"):
                d = getattr(z.rel, ek)
                if abs(d) > 22:
                    setattr(z.rel, ek, d - math.copysign(44, d))
            z.position = self.insan.position + z.rel
