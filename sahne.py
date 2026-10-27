"""Sahne katmanı: gezegenlerin 3B nesnelerini kurar ve hareket ettirir.
Yüzey dokuları dokular.py içinde üretilir."""
import math
import random

from ursina import Entity, Mesh, Shader, Texture, Vec3, destroy
from ursina.color import Color

import dokular
from dokular import hex_rgb, ton

try:   # eksen eğikliği için (panda3d, ursina ile birlikte gelir)
    from panda3d.core import Quat
    from panda3d.core import Vec3 as PVec3
except ImportError:
    Quat = None

# Gölgelendirme (gündüz/gece, atmosfer kenar parıltısı) sorun çıkarırsa False yapın.
GOLGELEME = True

# Canlı veri satırları: (başlık, sözlük anahtarı, birim, en küçük sapma, grafik rengi)
CANLI = [
    ("Sıcaklık", "sicak", "°C", 0.8, "#ff9a4d"),
    ("Basınç", "basinc", "bar", 0.0, "#4de1d2"),
    ("Rüzgâr hızı", "ruzgar", "m/s", 0.5, "#b79bff"),
]

# Gerçek gökbilim verileri (gezegen modüllerinde yoksa buradan okunur).
#   egim: dönme ekseni eğikliği (derece), donme: kendi etrafında dönme süresi (saat)
#   aylar: (ad, yarıçap km, uzaklık [gezegen yarıçapı], periyot gün, renk)
EK = {
    "Merkür": dict(egim=0.03, donme=1407.6),
    "Venüs": dict(egim=177.4, donme=5832.5),
    "Dünya": dict(egim=23.4, donme=23.9, aylar=[("Ay", 1737, 4.0, 27.3, "#b8b5ae")]),
    "Mars": dict(egim=25.2, donme=24.6),
    "Jüpiter": dict(egim=3.1, donme=9.9, aylar=[
        ("Io", 1822, 2.6, 1.77, "#e8d27a"), ("Europa", 1561, 3.2, 3.55, "#d8cfc0"),
        ("Ganymede", 2634, 4.0, 7.15, "#9b8f80"), ("Callisto", 2410, 4.9, 16.7, "#6e6459")]),
    "Satürn": dict(egim=26.7, donme=10.7, aylar=[("Titan", 2575, 4.2, 15.9, "#d9a64f")]),
    "Uranüs": dict(egim=97.8, donme=17.2),
    "Neptün": dict(egim=28.3, donme=16.1),
}


def ozellik(v, anahtar, varsayilan):
    if anahtar in v:
        return v[anahtar]
    return EK.get(v["ad"], {}).get(anahtar, varsayilan)


# ---------------- gölgelendirici ----------------
VS = """#version 140
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelViewMatrix;
uniform mat4 p3d_ModelMatrix;
in vec4 p3d_Vertex;
in vec2 p3d_MultiTexCoord0;
out vec2 uv;
out vec3 wn;
out vec3 wp;
out vec3 vn;
out vec3 vv;
void main() {
    vec3 n = normalize(p3d_Vertex.xyz);
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    uv = p3d_MultiTexCoord0;
    wp = (p3d_ModelMatrix * p3d_Vertex).xyz;
    wn = mat3(p3d_ModelMatrix) * n;
    vn = mat3(p3d_ModelViewMatrix) * n;
    vv = (p3d_ModelViewMatrix * p3d_Vertex).xyz;
}"""
FS = """#version 140
uniform sampler2D p3d_Texture0;
uniform vec3 atm_renk;
uniform float atm_k;
in vec2 uv;
in vec3 wn;
in vec3 wp;
in vec3 vn;
in vec3 vv;
out vec4 fragColor;
void main() {
    float ndl = dot(normalize(wn), normalize(-wp));            // Güneş (merkez) yönü
    float gun = smoothstep(-0.10, 0.40, ndl);                    // yumuşak gündüz/gece geçişi
    vec3 c = texture(p3d_Texture0, uv).rgb;
    vec3 renk = c * (0.03 + 1.08 * gun);
    float kenar = pow(1.0 - max(dot(normalize(vn), normalize(-vv)), 0.0), 3.0);
    renk += atm_renk * kenar * atm_k * smoothstep(-0.30, 0.50, ndl) * 1.5;   // atmosfer kenar parıltısı
    fragColor = vec4(renk, 1.0);
}"""
_golge = None


def golge():
    global _golge
    if _golge is None:
        _golge = Shader(language=Shader.GLSL, vertex=VS, fragment=FS)
    return _golge


def hx(h, a=1.0, k=1.0):
    r, g, b = hex_rgb(h)
    return Color(min(1, r / 255 * k), min(1, g / 255 * k), min(1, b / 255 * k), a)


def doku(v):
    return Texture(dokular.doku_uret(v))


def kure(v, yaricap, atm_renk="#000000", atm_k=0.0):
    """Gölgelendirilmiş küre (gezegen veya uydu)."""
    ek = {}
    if GOLGELEME:
        ek["shader"] = golge()
    e = Entity(model="sphere", texture=doku(v), scale=yaricap * 2, **ek)
    if GOLGELEME:
        r, g, b = hex_rgb(atm_renk)
        e.set_shader_input("atm_renk", Vec3(r / 255, g / 255, b / 255))
        e.set_shader_input("atm_k", float(atm_k))
    return e


def halka_mesh(ic, dis, n=120):
    v, t, uv = [], [], []
    for i in range(n):
        a = 2 * math.pi * i / n
        v += [Vec3(math.cos(a) * ic, 0, math.sin(a) * ic), Vec3(math.cos(a) * dis, 0, math.sin(a) * dis)]
        uv += [(0, .5), (1, .5)]
    for i in range(n):
        a, b = i * 2, (i * 2 + 2) % (2 * n)
        t += [(a, a + 1, b + 1), (a, b + 1, b)]
    return Mesh(vertices=v, triangles=t, uvs=uv)


# ---------------- sahne: Güneş, yıldızlar, bulutsular ----------------
def sahne_kur():
    R = random.Random(11)
    Entity(model="sphere", texture=Texture(dokular.gunes(R)), scale=7)
    for olcek, a in ((16, .85), (34, .32)):
        Entity(model="quad", texture=Texture(dokular.parilti((255, 190, 90))), scale=olcek,
               billboard=True, color=Color(1, 1, 1, a))
    v, c = [], []
    for _ in range(1200):
        a, b, r = R.uniform(0, 6.283), R.uniform(0, 3.1416), R.uniform(500, 650)
        v.append(Vec3(r * math.sin(b) * math.cos(a), r * math.cos(b), r * math.sin(b) * math.sin(a)))
        h = R.choice([(255, 255, 255), (255, 214, 170), (170, 205, 255), (255, 170, 225)])
        k = R.uniform(.45, 1)
        c.append(Color(h[0] / 255 * k, h[1] / 255 * k, h[2] / 255 * k, 1))
    Entity(model=Mesh(vertices=v, colors=c, mode="point", thickness=3))
    for rgb, pos in (((120, 80, 255), (-700, 150, -600)), ((255, 70, 160), (650, -100, -700)),
                     ((60, 220, 210), (-250, -300, 750)), ((255, 140, 60), (600, 280, 640))):
        Entity(model="quad", texture=Texture(dokular.parilti(rgb)), scale=1000, position=Vec3(*pos),
               billboard=True, color=Color(1, 1, 1, .30))


# ---------------- tek gezegen ----------------
class Gezegen3B:
    def __init__(self, v, ozel=False, sira=0):
        self.v, self.ozel = v, ozel
        self.r = 0.5 * math.sqrt(v["yaricap_km"] / 6371)   # ekrana sığması için ölçekli
        self.d = 10 + math.sqrt(v["au"]) * 9                # yörünge yarıçapı (ölçekli)
        self.faz = sira * 1.15 + random.random()
        k = v["atm_k"]
        self.govde = kure(v, self.r, v["atm_renk"], k)
        self.govde.collider = "sphere"
        self.parcalar = [self.govde]

        # eksen eğikliği ve kendi etrafında dönme
        self.egim = float(ozellik(v, "egim", 0.0))
        self.donme_hizi = 25 * 24 / max(1.0, float(ozellik(v, "donme", 24.0)))
        self.aci = 0.0
        self.q_ok = Quat is not None
        if self.q_ok:
            self.egim_q = Quat()
            self.egim_q.setFromAxisAngle(self.egim, PVec3(0, 1, 0))

        # ince dış atmosfer parıltısı
        self.atm = None
        if k > 0.02:
            self.atm = Entity(model="sphere", scale=self.r * 2 * (1.04 + k * 0.07),
                              color=hx(v["atm_renk"], 0.03 + k * 0.09))
            self.parcalar.append(self.atm)

        # halka (dokulu, boşluklu)
        self.halka = None
        if v.get("halka"):
            self.halka = Entity(model=halka_mesh(self.r * 1.4, self.r * 2.5),
                                texture=Texture(dokular.halka_seridi(v["halka"])),
                                color=Color(1, 1, 1, .999), double_sided=True)
            if self.q_ok:
                self.halka.setQuat(self.egim_q)
            else:
                self.halka.rotation_x = self.egim
            self.parcalar.append(self.halka)

        # uydular
        self.aylar = []
        for ad, km, mesafe, per, renk in ozellik(v, "aylar", []):
            mr = max(.06, self.r * km / v["yaricap_km"])
            e = kure({"ad": ad, "renk": renk, "doku": "kaya"}, mr)
            self.aylar.append((e, mesafe * self.r + (self.r if self.halka else 0), per, random.random() * 6.28))

        pts = [Vec3(math.cos(i / 128 * 6.2832) * self.d, 0, math.sin(i / 128 * 6.2832) * self.d)
               for i in range(129)]
        self.yorunge = Entity(model=Mesh(vertices=pts, mode="line", thickness=1.5),
                              color=hx(v["renk"], .45))
        self.canli = [{"v": v[k_], "h": [v[k_]] * 40} for _, k_, _, _, _ in CANLI]

    def guncelle(self, T, dt, donsun=True):
        """T: geçen gün. Gezegeni yörüngesindeki yerine koyar."""
        a = T / self.v["periyot"] * 2 * math.pi + self.faz
        p = Vec3(math.cos(a) * self.d, 0, math.sin(a) * self.d)
        for o in self.parcalar:
            o.position = p
        for e, mesafe, per, faz in self.aylar:
            b = T / per * 2 * math.pi + faz
            e.position = p + Vec3(math.cos(b) * mesafe, 0, math.sin(b) * mesafe)
        if donsun:
            self.aci = (self.aci + dt * self.donme_hizi) % 360
        if self.q_ok:
            try:
                q = Quat()
                q.setFromAxisAngle(self.aci, PVec3(0, 0, 1))
                self.govde.setQuat(q * self.egim_q)
                return
            except Exception:
                self.q_ok = False
        self.govde.rotation_y = self.aci

    def canli_guncelle(self):
        """Simüle canlı veri: gezegenin ortalama değeri etrafında dalgalanır."""
        for L, (_, k, _, mn, _) in zip(self.canli, CANLI):
            taban = self.v[k]
            sapma = max(abs(taban) * 0.04, mn)
            L["v"] += (taban + random.uniform(-1, 1) * sapma - L["v"]) * 0.4
            L["h"].append(L["v"])
            L["h"].pop(0)

    def sil(self):
        for o in self.parcalar + [self.yorunge] + [e for e, *_ in self.aylar]:
            destroy(o)
