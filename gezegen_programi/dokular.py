"""Gerçekçi gezegen yüzeyleri: fraktal gürültü, kraterler, kıtalar, bulut bantları.
Yalnızca Pillow kullanır. Her fonksiyon bir PIL görüntüsü döndürür."""
import math
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

W, H = 1024, 512
BIL = Image.Resampling.BICUBIC


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def ton(rgb, k):
    return tuple(max(0, min(255, int(c * k))) for c in rgb)


def gurultu(R, oktav=6, p=0.55, en=1.0, boy=1.0):
    """Yatayda dikişsiz fraktal gürültü (gri, 0-255). en/boy < 1 ise ızgara seyrekleşir."""
    F = W // 8
    acc, toplam, ag = None, 0.0, 1.0
    for o in range(oktav):
        gw, gh = max(2, int(4 * 2 ** o * en)), max(2, int(2 * 2 ** o * boy))
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


def kaya(R, pal, krater=90, kutup=False):
    koyu, orta, acik = pal
    h = Image.blend(Image.new("L", (W, H), 128), gurultu(R, 6, .5), .6)       # düşük kontrastlı arazi
    img = ImageOps.colorize(h, koyu, acik, mid=orta)
    kat = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(kat)
    for _ in range(krater):
        x, y = R.random() * W, 24 + R.random() * (H - 48)
        r = (2 + R.random() ** 3 * 30) * W / 512
        for dx in (-W, 0, W):                                                    # dikiş yerinde taşan kraterler
            cx = x + dx
            d.ellipse((cx - r, y - r, cx + r, y + r), fill=(*koyu, 20))          # çukur
            d.ellipse((cx - r * .8 - r * .12, y - r * .8 - r * .12, cx + r * .8 - r * .12, y + r * .8 - r * .12),
                      fill=(*koyu, 18))
            d.arc((cx - r, y - r, cx + r, y + r), 200, 340, fill=(*acik, 120), width=max(1, int(r / 8)))  # aydınlık kenar
    kat = kat.filter(ImageFilter.GaussianBlur(1.1))
    img = Image.alpha_composite(img.convert("RGBA"), kat).convert("RGB")
    if kutup:
        d2 = ImageDraw.Draw(img, "RGBA")
        for y0, y1 in ((-H * .1, H * .045), (H * .955, H * 1.1)):
            d2.ellipse((-W * .1, y0, W * 1.1, y1), fill=(245, 247, 252, 225))
    return img.filter(ImageFilter.GaussianBlur(.7))


def dunya(R):
    yuk = gurultu(R, 7, .55)
    deniz = ImageOps.colorize(gurultu(R, 4, .5), (6, 24, 80), (38, 110, 190), mid=(14, 62, 140))
    kara = ImageOps.colorize(gurultu(R, 6, .6), (36, 86, 38), (196, 176, 118), mid=(86, 128, 58))
    dag = gurultu(R, 5, .6).point(lambda v: max(0, v - 150) * 2)       # dağ/çöl açıklığı
    kara = ImageChops.screen(kara, Image.merge("RGB", (dag, dag, dag)).point(lambda v: v // 3))
    maske = yuk.point(lambda v: 255 if v > 146 else 0).filter(ImageFilter.GaussianBlur(1.5))
    # kıyıda sığ su
    sig = yuk.point(lambda v: 255 if 134 < v <= 146 else 0).filter(ImageFilter.GaussianBlur(4)).point(lambda v: v // 2)
    deniz = Image.composite(Image.new("RGB", (W, H), (60, 170, 190)), deniz, sig)
    img = Image.composite(kara, deniz, maske)
    # kutup buzulları
    grad = Image.linear_gradient("L").resize((W, H))
    enlem = ImageChops.difference(grad, Image.new("L", (W, H), 128)).point(lambda v: min(255, v * 2))
    s = ImageChops.add(enlem, gurultu(R, 5, .6).point(lambda v: v // 5))
    kap = s.point(lambda v: 255 if v > 246 else (int((v - 226) * 12) if v > 226 else 0)).filter(ImageFilter.GaussianBlur(1.2))
    img = Image.composite(Image.new("RGB", (W, H), (243, 248, 255)), img, kap)
    # bulutlar
    bulut = gurultu(R, 6, .58, en=1.0, boy=1.4).point(lambda v: int(max(0, min(255, (v - 118) * 3)) * .82))
    img = Image.composite(Image.new("RGB", (W, H), (255, 255, 255)), img, bulut)
    return img.filter(ImageFilter.GaussianBlur(.6))


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
    mix = ImageOps.autocontrast(Image.blend(gurultu(R, 6, .6, en=.3, boy=2.0), bantlar, bant), cutoff=1)
    img = ImageOps.colorize(mix, koyu, acik, mid=orta)
    d = ImageDraw.Draw(img, "RGBA")
    for _ in range(firtina):
        x, y = R.random() * W, 40 + R.random() * (H - 80)
        rx, ry = (14 + R.random() * 50) * W / 512, (2 + R.random() * 6) * W / 512
        d.ellipse((x - rx, y - ry, x + rx, y + ry),
                  fill=(255, 255, 255, 38) if R.random() < .5 else (*ton(koyu, .7), 48))
    if leke:
        cx, cy, rx, ry, dolgu, kenar = leke
        for k, a in ((1.7, 45), (1.35, 90), (1.1, 150), (.8, 200)):
            d.ellipse((cx - rx * k, cy - ry * k, cx + rx * k, cy + ry * k), fill=(*(kenar if k > 1 else dolgu), a))
    img = img.filter(ImageFilter.GaussianBlur(1.3 * W / 512))
    # kutuplarda doğal koyulaşma
    g = Image.linear_gradient("L").resize((W, H))
    kutup = ImageChops.difference(g, Image.new("L", (W, H), 128)).point(lambda v: max(0, v - 78) * 3)
    return Image.composite(Image.new("RGB", (W, H), ton(koyu, .55)), img, kutup.point(lambda v: min(150, v)))


def gunes(R):
    img = ImageOps.colorize(gurultu(R, 7, .62), (176, 56, 0), (255, 240, 170), mid=(255, 160, 30))
    return img.filter(ImageFilter.GaussianBlur(.8))


def halka_seridi(hexrenk):
    """Satürn tipi halka: radyal bantlar ve boşluklar (genişlik = yarıçap yönü)."""
    ana, N, R = hex_rgb(hexrenk), 512, random.Random(5)
    img = Image.new("RGBA", (N, 4))
    d = ImageDraw.Draw(img)
    for x in range(N):
        r = x / (N - 1)
        if r < .16:
            a = .0
        elif r < .27:
            a = .16                                          # C halkası: soluk
        elif r < .56:
            a = .82 + .12 * math.sin(r * 95)                 # B halkası: parlak
        elif r < .62:
            a = .05                                          # Cassini boşluğu
        elif r < .93:
            a = .55 + .18 * math.sin(r * 150)                # A halkası
            if .84 < r < .855:
                a = .08                                      # Encke boşluğu
        else:
            a = .0
        k = .78 + .28 * math.sin(r * 55) + .1 * R.random()
        d.line((x, 0, x, 3), fill=(*ton(ana, k), int(255 * max(0, min(1, a)))))
    return img


def parilti(rgb, boyut=256):
    img = Image.new("RGBA", (boyut, boyut), (*rgb, 0))
    d = ImageDraw.Draw(img)
    m = boyut // 2
    for r in range(m, 0, -1):
        d.ellipse((m - r, m - r, m + r, m + r), fill=(*rgb, int(((1 - r / m) ** 2.2) * 255)))
    return img


# ---------------- gezegenlere özel renk paletleri (koyu, orta, açık) ----------------
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
GAZ_AYAR = {   # bant ağırlığı, leke (x, y, yatay, dikey, dolgu rengi, kenar rengi), fırtına sayısı
    "Venüs": dict(bant=.18, firtina=10),
    "Jüpiter": dict(bant=.62, firtina=34,
                    leke=(int(W * .68), int(H * .64), W * .055, H * .06, (176, 84, 52), (226, 178, 140))),
    "Satürn": dict(bant=.4, firtina=14),
    "Uranüs": dict(bant=.14, firtina=6),
    "Neptün": dict(bant=.3, firtina=16,
                   leke=(int(W * .3), int(H * .45), W * .045, H * .045, (16, 30, 100), (150, 180, 255))),
}


def doku_uret(v):
    ad, tip = v["ad"], (v.get("doku") or "gaz")
    R = random.Random(sum(map(ord, ad)) * 7919)
    ana = hex_rgb(v["renk"])
    pal = tuple(hex_rgb(c) for c in PALET[ad]) if ad in PALET else (ton(ana, .55), ana, ton(ana, 1.35))
    if tip == "dunya":
        return dunya(R)
    if tip == "kaya":
        return kaya(R, pal, krater=60 if ad == "Mars" else 110, kutup=(ad == "Mars"))
    return gaz(R, pal, **GAZ_AYAR.get(ad, dict(bant=.5)))
