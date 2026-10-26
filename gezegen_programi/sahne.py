"""Sahne katmanı: dokuları üretir, gezegenlerin 3B nesnelerini kurar ve hareket ettirir."""
import math
import random

from PIL import Image, ImageDraw, ImageFilter
from ursina import Entity, Mesh, Shader, Texture, Vec3
from ursina.color import Color

# Gölgelendirme (gündüz/gece aydınlatması) sorun çıkarırsa False yapın.
GOLGELEME = True

# Canlı veri satırları: (başlık, sözlük anahtarı, birim, en küçük sapma, grafik rengi)
CANLI = [
    ("Sıcaklık", "sicak", "°C", 0.8, "#ff9a4d"),
    ("Basınç", "basinc", "bar", 0.0, "#4de1d2"),
    ("Rüzgâr hızı", "ruzgar", "m/s", 0.5, "#b79bff"),
]

VS = """#version 140
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
in vec4 p3d_Vertex;
in vec2 p3d_MultiTexCoord0;
out vec2 uv;
out vec3 wn;
out vec3 wp;
void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    uv = p3d_MultiTexCoord0;
    wp = (p3d_ModelMatrix * p3d_Vertex).xyz;
    wn = mat3(p3d_ModelMatrix) * normalize(p3d_Vertex.xyz);
}"""
FS = """#version 140
uniform sampler2D p3d_Texture0;
in vec2 uv;
in vec3 wn;
in vec3 wp;
out vec4 fragColor;
void main() {
    float d = max(dot(normalize(wn), normalize(-wp)), 0.0);
    vec3 c = texture(p3d_Texture0, uv).rgb;
    fragColor = vec4(c * (0.10 + d), 1.0);
}"""
_golge = None


def golge():
    global _golge
    if _golge is None:
        _golge = Shader(language=Shader.GLSL, vertex=VS, fragment=FS)
    return _golge


# ---------------- renk yardımcıları ----------------
def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def hx(h, a=1.0, k=1.0):
    r, g, b = hex_rgb(h)
    return Color(min(1, r / 255 * k), min(1, g / 255 * k), min(1, b / 255 * k), a)


def ton(rgb, k):
    return tuple(max(0, min(255, int(c * k))) for c in rgb)


# ---------------- doku üreticiler ----------------
def doku_uret(v):
    W, H = 512, 256
    R = random.Random(sum(map(ord, v["ad"])))
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img, "RGBA")
    ana = hex_rgb(v["renk"])
    tip = v.get("doku") or "gaz"

    def blob(col, n, rmin, rmax, a):
        for _ in range(n):
            x, y, r = R.random() * W, R.random() * H, rmin + R.random() * (rmax - rmin)
            d.ellipse((x - r, y - r, x + r, y + r), fill=(*col, a))

    if tip == "dunya":
        d.rectangle((0, 0, W, H), fill=(27, 95, 176))
        blob((40, 130, 220), 120, 4, 18, 120)
        for _ in range(26):
            x, y = R.random() * W, 40 + R.random() * 176
            for _ in range(14):
                col = (63, 154, 74) if R.random() < 0.7 else (180, 154, 92)
                bx, by, r = x + (R.random() - .5) * 60, y + (R.random() - .5) * 34, 5 + R.random() * 14
                d.ellipse((bx - r, by - r, bx + r, by + r), fill=col)
        d.rectangle((0, 0, W, 12), fill=(244, 248, 255))
        d.rectangle((0, H - 12, W, H), fill=(244, 248, 255))
        blob((255, 255, 255), 90, 6, 22, 90)
    elif tip == "kaya":
        d.rectangle((0, 0, W, H), fill=ana)
        blob(ton(ana, .6), 260, 2, 16, 90)
        blob(ton(ana, 1.3), 200, 2, 12, 90)
        for _ in range(24):
            x, y, r = R.random() * W, R.random() * H, 3 + R.random() * 10
            d.ellipse((x - r, y - r, x + r, y + r), outline=ton(ana, .55), width=2)
    else:  # gaz devi: bantlı
        tonlar = [ton(ana, k) for k in (.72, .88, 1.0, 1.12, 1.28)]
        y = 0
        while y < H:
            h = 5 + R.random() * 24
            d.rectangle((0, y, W, y + h), fill=R.choice(tonlar))
            y += h
        for _ in range(70):
            x, y, rx, ry = R.random() * W, R.random() * H, 10 + R.random() * 40, 2 + R.random() * 4
            d.ellipse((x - rx, y - ry, x + rx, y + ry),
                      fill=(255, 255, 255, 25) if R.random() < .5 else (0, 0, 0, 25))
        if v.get("leke"):
            d.ellipse((330, 154, 390, 186), fill=(181, 72, 47), outline=(255, 220, 180), width=3)
        img = img.filter(ImageFilter.GaussianBlur(1.2))
    return Texture(img)


def parilti(rgb, boyut=256):
    img = Image.new("RGBA", (boyut, boyut), (*rgb, 0))
    d = ImageDraw.Draw(img)
    m = boyut // 2
    for r in range(m, 0, -1):
        a = int(((1 - r / m) ** 2.2) * 255)
        d.ellipse((m - r, m - r, m + r, m + r), fill=(*rgb, a))
    return Texture(img)


def halka_mesh(ic, dis, n=96):
    v, t = [], []
    for i in range(n):
        a = 2 * math.pi * i / n
        v += [Vec3(math.cos(a) * ic, 0, math.sin(a) * ic), Vec3(math.cos(a) * dis, 0, math.sin(a) * dis)]
    for i in range(n):
        a, b = i * 2, (i * 2 + 2) % (2 * n)
        t += [(a, a + 1, b + 1), (a, b + 1, b)]
    return Mesh(vertices=v, triangles=t)


# ---------------- sahne: Güneş, yıldızlar, bulutsular ----------------
def sahne_kur():
    R = random.Random(11)
    gun = Image.new("RGB", (512, 256), (255, 180, 58))
    d = ImageDraw.Draw(gun, "RGBA")
    for _ in range(350):
        x, y, r = R.random() * 512, R.random() * 256, 3 + R.random() * 16
        d.ellipse((x - r, y - r, x + r, y + r),
                  fill=(255, 110, 20, 70) if R.random() < .5 else (255, 235, 150, 80))
    Entity(model="sphere", texture=Texture(gun), scale=7)
    for olcek, a in ((17, .85), (34, .35)):
        Entity(model="quad", texture=parilti((255, 190, 90)), scale=olcek, billboard=True, color=Color(1, 1, 1, a))
    v, c = [], []
    for _ in range(900):
        a, b, r = R.uniform(0, 6.283), R.uniform(0, 3.1416), R.uniform(500, 650)
        v.append(Vec3(r * math.sin(b) * math.cos(a), r * math.cos(b), r * math.sin(b) * math.sin(a)))
        h = R.choice([(255, 255, 255), (255, 200, 150), (160, 200, 255), (255, 150, 220)])
        c.append(Color(h[0] / 255, h[1] / 255, h[2] / 255, 1))
    Entity(model=Mesh(vertices=v, colors=c, mode="point", thickness=3))
    for rgb, pos in (((120, 80, 255), (-700, 150, -600)), ((255, 70, 160), (650, -100, -700)),
                     ((60, 220, 210), (-250, -300, 750)), ((255, 140, 60), (600, 280, 640))):
        Entity(model="quad", texture=parilti(rgb), scale=1000, position=Vec3(*pos),
               billboard=True, color=Color(1, 1, 1, .35))


# ---------------- tek gezegen ----------------
class Gezegen3B:
    def __init__(self, v, ozel=False, sira=0):
        self.v, self.ozel = v, ozel
        self.r = 0.5 * math.sqrt(v["yaricap_km"] / 6371)   # ekrana sığması için ölçekli
        self.d = 10 + math.sqrt(v["au"]) * 9                # yörünge yarıçapı (ölçekli)
        self.faz = sira * 1.15 + random.random()
        ek = {"shader": golge()} if GOLGELEME else {}
        self.govde = Entity(model="sphere", texture=doku_uret(v), scale=self.r * 2,
                            collider="sphere", **ek)
        self.parcalar = [self.govde]
        k = v["atm_k"]
        self.atm = None
        if k > 0.02:   # atmosfer parıltısı
            self.atm = Entity(model="sphere", scale=self.r * 2 * (1.05 + k * 0.12),
                              color=hx(v["atm_renk"], 0.10 + k * 0.25))
            self.parcalar.append(self.atm)
        self.halka = None
        if v.get("halka"):
            self.halka = Entity(model=halka_mesh(self.r * 1.5, self.r * 2.5), color=hx(v["halka"], .75),
                                double_sided=True, rotation_x=25)
            self.parcalar.append(self.halka)
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
        if donsun:
            self.govde.rotation_y += 25 * dt

    def canli_guncelle(self):
        """Simüle canlı veri: gezegenin ortalama değeri etrafında dalgalanır."""
        for L, (_, k, _, mn, _) in zip(self.canli, CANLI):
            taban = self.v[k]
            sapma = max(abs(taban) * 0.04, mn)
            L["v"] += (taban + random.uniform(-1, 1) * sapma - L["v"]) * 0.4
            L["h"].append(L["v"])
            L["h"].pop(0)

    def sil(self):
        from ursina import destroy
        for o in self.parcalar + [self.yorunge]:
            destroy(o)
