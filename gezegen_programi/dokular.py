"""Gerçekçi gezegen yüzeyleri (yalnızca Pillow): renk dokusu, kabartma (normal) haritası,
okyanus parlaklığı + şehir ışıkları haritası, bulut katmanı ve Samanyolu arka planı."""
import math
import random
from types import SimpleNamespace

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

W, H = 1536, 768
BIL = Image.Resampling.BICUBIC


def boyut(w):
    global W, H
    W, H = w, w // 2


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def ton(rgb, k):
    return tuple(max(0, min(255, int(c * k))) for c in rgb)


def gurultu(R, oktav=6, p=0.55, en=1.0, boy=1.0):
    """Yatayda dikişsiz fraktal gürültü (gri, 0-255)."""
    F = W // 8
    acc, toplam, ag = None, 0.0, 1.0
    for o in range(oktav):
        gw, gh = max(2, int(4 * 2 ** o * en)), max(2, int(2 * 2 ** o * boy))
        gw, gh = min(gw, W), min(gh, H)
        k = Image.new("L", (gw, gh))
        k.putdata([R.randrange(256) for _ in range(gw * gh)])
        b = k.resize((W + F, H), BIL)
        toplam += ag
        acc = b if acc is None else Image.blend(acc, b, ag / toplam)
        ag *= p
    out = acc.crop((0, 0, W, H))
    maske = Image.linear_gradient("L").rotate(90).resize((F, H))
    out.paste(Image.composite(acc.crop((0, 0, F, H)), acc.crop((W, 0, W + F, H)), maske), (0, 0))
    return ImageOps.autocontrast(out, cutoff=1)


def normal_harita(h, guc=2.0):
    """Yükseklik haritasından (gri) normal haritası üretir (Sobel)."""
    kx = ImageFilter.Kernel((3, 3), (-1, 0, 1, -2, 0, 2, -1, 0, 1), scale=guc, offset=128)
    ky = ImageFilter.Kernel((3, 3), (-1, -2, -1, 0, 0, 0, 1, 2, 1), scale=guc, offset=128)
    return Image.merge("RGB", (h.filter(kx), h.filter(ky), Image.new("L", h.size, 255)))


# ---------------- kayalık gezegenler ----------------
def kaya(R, pal, krater=90, kutup=False):
    koyu, orta, acik = pal
    arazi = gurultu(R, 6, .5)
    renk = ImageOps.colorize(Image.blend(Image.new("L", (W, H), 128), arazi, .6), koyu, acik, mid=orta)
    yuk = Image.blend(Image.new("L", (W, H), 128), gurultu(R, 7, .58), .55)

    kat = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dk = ImageDraw.Draw(kat)
    kh = Image.new("L", (W, H), 128)
    dh = ImageDraw.Draw(kh)
    for _ in range(krater):
        x, y = R.random() * W, 24 + R.random() * (H - 48)
        r = (2 + R.random() ** 3 * 30) * W / 512
        for dx in (-W, 0, W):                                     # dikiş yerinde taşan kraterler
            cx = x + dx
            dk.ellipse((cx - r, y - r, cx + r, y + r), fill=(*koyu, 24))
            dk.arc((cx - r, y - r, cx + r, y + r), 200, 340, fill=(*acik, 110), width=max(1, int(r / 8)))
            dh.ellipse((cx - r, y - r, cx + r, y + r), fill=96)                       # çukur
            dh.ellipse((cx - r, y - r, cx + r, y + r), outline=176, width=max(2, int(r / 5)))  # yükselmiş kenar
    kat = kat.filter(ImageFilter.GaussianBlur(1.1))
    renk = Image.alpha_composite(renk.convert("RGBA"), kat).convert("RGB")
    yuk = ImageChops.add(yuk, kh.filter(ImageFilter.GaussianBlur(1.6)), scale=1, offset=-128)
    if kutup:
        d2 = ImageDraw.Draw(renk, "RGBA")
        for y0, y1 in ((-H * .1, H * .045), (H * .955, H * 1.1)):
            d2.ellipse((-W * .1, y0, W * 1.1, y1), fill=(245, 247, 252, 225))
    return renk.filter(ImageFilter.GaussianBlur(.7)), normal_harita(yuk.filter(ImageFilter.GaussianBlur(.8)), 2.2)


# ---------------- Dünya ----------------
def dunya(R, ayri_bulut=True):
    yuk = gurultu(R, 7, .64)
    deniz = ImageOps.colorize(gurultu(R, 4, .5), (6, 24, 80), (38, 110, 190), mid=(14, 62, 140))
    kara = ImageOps.colorize(gurultu(R, 6, .6), (36, 86, 38), (196, 176, 118), mid=(86, 128, 58))
    dag = gurultu(R, 5, .6).point(lambda v: max(0, v - 150) * 2)
    kara = ImageChops.screen(kara, Image.merge("RGB", (dag, dag, dag)).point(lambda v: v // 3))
    maske = yuk.point(lambda v: 255 if v > 140 else 0).filter(ImageFilter.GaussianBlur(1.5))
    sig = yuk.point(lambda v: 255 if 128 < v <= 140 else 0).filter(ImageFilter.GaussianBlur(4)).point(lambda v: v // 2)
    deniz = Image.composite(Image.new("RGB", (W, H), (60, 170, 190)), deniz, sig)
    img = Image.composite(kara, deniz, maske)
    grad = Image.linear_gradient("L").resize((W, H))
    enlem = ImageChops.difference(grad, Image.new("L", (W, H), 128)).point(lambda v: min(255, v * 2))
    s = ImageChops.add(enlem, gurultu(R, 5, .6).point(lambda v: v // 5))
    kap = s.point(lambda v: 255 if v > 246 else (int((v - 226) * 12) if v > 226 else 0)).filter(ImageFilter.GaussianBlur(1.2))
    img = Image.composite(Image.new("RGB", (W, H), (243, 248, 255)), img, kap)
    bulut = gurultu(R, 7, .6, boy=1.4).point(lambda v: int(max(0, min(255, (v - 135) * 3.4)) * .85))

    bulut = ImageChops.multiply(bulut, enlem.point(lambda v: 255 - int(v * .78)))
    # kabartma: yalnızca karada
    ykl = maske.point(lambda v: v).filter(ImageFilter.GaussianBlur(1))
    kabar = ImageChops.multiply(yuk.point(lambda v: max(0, v - 120) * 2), ykl.point(lambda v: v))
    normal = normal_harita(kabar.filter(ImageFilter.GaussianBlur(1.0)), 1.0)
    # parlaklık (okyanus) + şehir ışıkları
    okyanus = ImageChops.multiply(ImageOps.invert(maske), ImageOps.invert(kap))
    kume = gurultu(R, 4, .55).point(lambda v: 255 if v > 95 else 0).filter(ImageFilter.GaussianBlur(6))
    sehir = Image.new("L", (W, H), 0)
    ds = ImageDraw.Draw(sehir)
    kara_px, kume_px, kap_px = maske.load(), kume.load(), kap.load()
    for _ in range(int(W * H / 260)):
        x, y = R.randrange(W), R.randrange(H)
        if kara_px[x, y] > 200 and kume_px[x, y] > 150 and kap_px[x, y] < 40:
            r = R.choice((.8, .8, 1.2, 1.8)) * W / 1536
            ds.ellipse((x - r, y - r, x + r, y + r), fill=R.randint(150, 255))
    sehir = sehir.filter(ImageFilter.GaussianBlur(.9)).point(lambda v: min(255, v * 2))
    ozel = Image.merge("RGB", (okyanus, sehir, Image.new("L", (W, H), 0)))
    if ayri_bulut:
        beyaz = Image.new("L", (W, H), 255)
        bulut_rgba = Image.merge("RGBA", (beyaz, beyaz, beyaz, bulut))
        return img.filter(ImageFilter.GaussianBlur(.6)), normal, ozel, bulut_rgba
    img = Image.composite(Image.new("RGB", (W, H), (255, 255, 255)), img, bulut)
    return img.filter(ImageFilter.GaussianBlur(.6)), normal, ozel, None


# ---------------- gaz devleri ----------------
def gaz(R, pal, bant=.55, leke=None, firtina=26):
    koyu, orta, acik = pal
    ph = R.random() * 6
    vals = []
    for y in range(H):
        t = y / H * math.pi
        v = .5 + .26 * math.sin(t * 10 + ph) + .15 * math.sin(t * 19 + ph * 2) + .09 * math.sin(t * 37 + ph * 3)
        vals.append(int(255 * max(0, min(1, v))))
    prof = Image.new("L", (1, H))
    prof.putdata(vals)
    bantlar = prof.resize((W, H), Image.Resampling.BILINEAR)
    mix = Image.blend(gurultu(R, 6, .6, en=.3, boy=2.0), bantlar, bant)
    # jet akımları: her satırı farklı miktarda kaydırarak bulutları gerçekçi biçimde uzat
    kay = Image.new("L", (W, H))
    for y in range(H):
        s = int(W * .02 * math.sin(y * .045 + ph) + W * .012 * math.sin(y * .11 + ph * 2))
        kay.paste(ImageChops.offset(mix.crop((0, y, W, y + 1)), s, 0), (0, y))
    img = ImageOps.colorize(ImageOps.autocontrast(kay, cutoff=1), koyu, acik, mid=orta)
    d = ImageDraw.Draw(img, "RGBA")
    for _ in range(firtina):
        x, y = R.random() * W, 40 * H / 256 + R.random() * (H - 80 * H / 256)
        rx, ry = (14 + R.random() * 50) * W / 512, (2 + R.random() * 6) * W / 512
        d.ellipse((x - rx, y - ry, x + rx, y + ry),
                  fill=(255, 255, 255, 38) if R.random() < .5 else (*ton(koyu, .7), 48))
    if leke:
        fx, fy, frx, fry, dolgu, kenar = leke
        cx, cy, rx, ry = fx * W, fy * H, frx * W, fry * H
        for k, a in ((1.7, 45), (1.35, 90), (1.1, 150), (.8, 200)):
            d.ellipse((cx - rx * k, cy - ry * k, cx + rx * k, cy + ry * k), fill=(*(kenar if k > 1 else dolgu), a))
    img = img.filter(ImageFilter.GaussianBlur(1.3 * W / 512))
    g = Image.linear_gradient("L").resize((W, H))
    kutup = ImageChops.difference(g, Image.new("L", (W, H), 128)).point(lambda v: max(0, v - 78) * 3)
    return Image.composite(Image.new("RGB", (W, H), ton(koyu, .55)), img, kutup.point(lambda v: min(150, v)))


def gunes(R):
    boyut(1024)
    img = ImageOps.colorize(gurultu(R, 7, .62), (176, 56, 0), (255, 240, 170), mid=(255, 160, 30))
    return img.filter(ImageFilter.GaussianBlur(.8))


# ---------------- halka ve parıltı ----------------
def halka_seridi(hexrenk):
    """Satürn tipi halka: radyal bantlar ve boşluklar (genişlik = yarıçap yönü)."""
    ana, N, R = hex_rgb(hexrenk), 1024, random.Random(5)
    img = Image.new("RGBA", (N, 4))
    d = ImageDraw.Draw(img)
    for x in range(N):
        r = x / (N - 1)
        if r < .16:
            a = .0
        elif r < .27:
            a = .16
        elif r < .56:
            a = .82 + .12 * math.sin(r * 95)
        elif r < .62:
            a = .05
        elif r < .93:
            a = .55 + .18 * math.sin(r * 150)
            if .84 < r < .855:
                a = .08
        else:
            a = .0
        k = .78 + .28 * math.sin(r * 55) + .12 * R.random() + .06 * math.sin(r * 420)
        d.line((x, 0, x, 3), fill=(*ton(ana, k), int(255 * max(0, min(1, a)))))
    return img


def parilti(rgb, boyut_=256):
    img = Image.new("RGBA", (boyut_, boyut_), (*rgb, 0))
    d = ImageDraw.Draw(img)
    m = boyut_ // 2
    for r in range(m, 0, -1):
        d.ellipse((m - r, m - r, m + r, m + r), fill=(*rgb, int(((1 - r / m) ** 2.2) * 255)))
    return img


# ---------------- uzay arka planı (Samanyolu) ----------------
def uzay(R):
    boyut(2048)
    # Samanyolu bandı: yatay eğri boyunca gauss profili
    prof = Image.new("L", (1, H))
    prof.putdata([int(255 * math.exp(-((y - H / 2) / (H * .085)) ** 2)) for y in range(H)])
    sut = prof.resize((W, H))
    bant = Image.new("L", (W, H))
    for x in range(0, W, 2):
        kay = int(H * .16 * math.sin(x / W * 2 * math.pi + .8))
        bant.paste(sut.crop((x, 0, x + 2, H)), (x, kay))
    bant = bant.filter(ImageFilter.GaussianBlur(6))
    toz = gurultu(R, 7, .62)
    bant = ImageChops.multiply(bant, toz.point(lambda v: int(70 + v * .75)))          # toz bulutları
    yarik = gurultu(R, 5, .55, en=1.5, boy=3).point(lambda v: 255 if v > 150 else 110)  # karanlık yarıklar
    bant = ImageChops.multiply(bant, yarik.filter(ImageFilter.GaussianBlur(3))).point(lambda v: min(255, int(v * 1.5)))
    img = ImageOps.colorize(bant, (3, 4, 11), (255, 226, 200), mid=(70, 74, 140))
    # renkli bulutsular
    kat = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(kat)
    for rgb in ((150, 60, 255), (255, 70, 150), (50, 200, 200), (255, 130, 50), (90, 120, 255)):
        for _ in range(3):
            x, y, r = R.random() * W, H * (.25 + R.random() * .5), W * (.04 + R.random() * .08)
            d.ellipse((x - r, y - r * .6, x + r, y + r * .6), fill=(*rgb, 34))
    kat = kat.filter(ImageFilter.GaussianBlur(W * .02))
    img = Image.alpha_composite(img.convert("RGBA"), kat).convert("RGB")
    # yıldızlar (banda doğru yoğunlaşır)
    d = ImageDraw.Draw(img, "RGBA")
    for _ in range(14000):
        x, y = R.randrange(W), R.randrange(H)
        if R.random() > .25 + .75 * bant.getpixel((x, y)) / 255:
            continue
        p = R.random() ** 7
        a = int(60 + 195 * p)
        h = R.choice([(255, 255, 255), (255, 220, 180), (170, 205, 255), (255, 180, 220)])
        if p > .55:
            d.ellipse((x - 1.5, y - 1.5, x + 1.5, y + 1.5), fill=(*h, a))
        else:
            d.point((x, y), fill=(*h, a))
    for _ in range(70):                                                                # parlak yıldızlar
        x, y = R.randrange(W), R.randrange(H)
        h = R.choice([(255, 255, 255), (255, 230, 200), (190, 215, 255)])
        for r, a in ((6, 25), (3.5, 60), (1.8, 200)):
            d.ellipse((x - r, y - r, x + r, y + r), fill=(*h, a))
    return img.filter(ImageFilter.GaussianBlur(.5))


# ---------------- gezegene özel renk paletleri (koyu, orta, açık) ----------------
PALET = {
    "Merkür": ("#38352f", "#8a847a", "#d2ccc0"),
    "Venüs": ("#b8873f", "#e2c386", "#f6e8c6"),
    "Mars": ("#4d2113", "#b4532f", "#e5a070"),
    "Jüpiter": ("#6e442b", "#c99a6a", "#f4e7d0"),
    "Satürn": ("#a08653", "#d8c48c", "#f5ebcb"),
    "Uranüs": ("#74c4ca", "#a0e2e6", "#cdf4f5"),
    "Neptün": ("#1b3aa8", "#3b62e0", "#86a6ff"),
    "Ay": ("#4a4844", "#8f8c86", "#d0cdc6"),
}
GAZ_AYAR = {   # bant ağırlığı, leke (x, y, yatay, dikey: görüntü oranı; dolgu, kenar), fırtına sayısı
    "Venüs": dict(bant=.18, firtina=10),
    "Jüpiter": dict(bant=.62, firtina=34, leke=(.68, .64, .055, .06, (176, 84, 52), (226, 178, 140))),
    "Satürn": dict(bant=.4, firtina=14),
    "Uranüs": dict(bant=.14, firtina=6),
    "Neptün": dict(bant=.3, firtina=16, leke=(.3, .45, .045, .045, (16, 30, 100), (150, 180, 255))),
}
BOYUT = {"Dünya": 2048, "Jüpiter": 2048, "Satürn": 1536}


def doku_uret(v, ayri_bulut=True):
    """Bir gezegen için tüm haritaları üretir: renk, normal, ozel (okyanus/şehir), bulut, bump."""
    ad, tip = v["ad"], (v.get("doku") or "gaz")
    boyut(v.get("boyut", BOYUT.get(ad, 1536)))
    R = random.Random(sum(map(ord, ad)) * 7919)
    ana = hex_rgb(v["renk"])
    pal = tuple(hex_rgb(c) for c in PALET[ad]) if ad in PALET else (ton(ana, .55), ana, ton(ana, 1.35))
    s = SimpleNamespace(renk=None, normal=None, ozel=None, bulut=None, bump=0.0)
    if tip == "dunya":
        s.renk, s.normal, s.ozel, s.bulut = dunya(R, ayri_bulut)
        s.bump = 0.8
    elif tip == "kaya":
        s.renk, s.normal = kaya(R, pal, krater=60 if ad == "Mars" else 110, kutup=(ad == "Mars"))
        s.bump = 1.0
    else:
        s.renk = gaz(R, pal, **GAZ_AYAR.get(ad, dict(bant=.5)))
    return s
