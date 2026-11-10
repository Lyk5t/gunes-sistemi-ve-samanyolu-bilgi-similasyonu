"""Açılış sahnesi: iki gezegen (gerçekçi dokulu) ekranın ortasında çarpışır; çarpışma noktasında
Yozgat Bozok Üniversitesi amblemi belirir ve "Samanyolu ve Güneş Sistemi Simülasyonu" başlığı yazılır.
Ardından kamera uzaktan yaklaşarak ana ekran açılır. Herhangi bir tuşla atlanabilir.

Amblem: program klasörüne bozok_logo.png (şeffaf arka planlı PNG önerilir) koyun. Dosya yoksa
geçici bir yer tutucu amblem çizilir.
"""
import math
import os
import random
import time

from PIL import Image, ImageDraw, ImageFont
from ursina import Entity, Mesh, Texture, Vec3, application, camera, destroy
from ursina.color import Color

import dokular
import hakkinda
import ses
from arayuz import YAZI_OLCEK, Yazi

KLASOR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO_ADLARI = ("bozok_logo.png", "bozok_logo.jpg", "bozok_logo.jpeg", "amblem.png", "logo.png")
BASLIK = "SAMANYOLU VE GÜNEŞ SİSTEMİ SİMÜLASYONU"
ALT_YAZI = "Yozgat Bozok Üniversitesi"

TC = 2.5                  # iki gezegenin çarpıştığı an (sn)
LOGO_T = 0.6              # çarpışmadan kaç sn sonra amblem belirmeye başlar
SOLMA = TC + 4.0          # ekranın solmaya başladığı an
SOLMA_SURE = 1.4          # solma süresi
DOKU_BOYUT = 768          # gezegen dokusu çözünürlüğü (büyüdükçe açılış gecikir)

LOGO_BOYUT = .46          # amblemin ekran yüksekliğine oranı
DUNYA_CAP, MARS_CAP = .36, .24          # ekrandaki çapları (ekran yüksekliği = 1)


def sinirla(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def yavasla(x):
    return 1 - (1 - sinirla(x)) ** 3


def kure_gorseli(doku, boyut=256, isik=(-.55, .45, .70), donus=0.0, atm=(120, 170, 255), atm_guc=.55):
    """Düzlemsel (enlem-boylam) dokuyu ışıklandırılmış, kenarı atmosfer parıltılı bir küre diskine çevirir."""
    W, H = doku.size
    px = doku.convert("RGB").load()
    lx, ly, lz = isik
    ln = math.sqrt(lx * lx + ly * ly + lz * lz)
    lx, ly, lz = lx / ln, ly / ln, lz / ln
    img = Image.new("RGBA", (boyut, boyut), (0, 0, 0, 0))
    out = img.load()
    c = (boyut - 1) / 2
    R = boyut / 2 - 2
    for j in range(boyut):
        ny = (c - j) / R
        for i in range(boyut):
            nx = (i - c) / R
            d = nx * nx + ny * ny
            if d > 1.0:
                continue
            nz = math.sqrt(1 - d)
            lon = math.atan2(nx, nz) + donus
            lat = math.asin(ny)
            u = (lon / (2 * math.pi) + .5) % 1.0
            v = .5 - lat / math.pi
            r, g, b = px[int(u * (W - 1)), int(sinirla(v) * (H - 1))]
            lam = max(0.0, nx * lx + ny * ly + nz * lz)
            k = .10 + 1.05 * lam ** .9
            rim = (1 - nz) ** 3 * atm_guc * (.35 + .65 * lam)
            r = min(255, int(r * k + atm[0] * rim))
            g = min(255, int(g * k + atm[1] * rim))
            b = min(255, int(b * k + atm[2] * rim))
            a = 255 if d < .96 else int(sinirla((1 - d) / .04) * 255)
            out[i, j] = (r, g, b, a)
    return img


def yer_tutucu_logo(n=512):
    """bozok_logo.png yoksa kullanılan geçici amblem."""
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((4, 4, n - 4, n - 4), fill=(14, 40, 92, 255), outline=(255, 205, 90, 255), width=10)
    d.ellipse((58, 58, n - 58, n - 58), outline=(255, 255, 255, 255), width=4)
    try:
        f1, f2 = ImageFont.load_default(size=70), ImageFont.load_default(size=40)
    except TypeError:
        f1 = f2 = ImageFont.load_default()
    for metin, y, f in (("YOZGAT", 165, f2), ("BOZOK", 225, f1), ("UNIVERSITESI", 320, f2)):
        w = d.textlength(metin, font=f)
        d.text(((n - w) / 2, y), metin, fill=(255, 255, 255, 255), font=f)
    return img


def logo_yukle(n=512):
    """Amblemi kare, şeffaf bir tuvale oranını bozmadan yerleştirir."""
    for ad in LOGO_ADLARI:
        yol = os.path.join(KLASOR, "assets", ad)
        if not os.path.exists(yol):
            yol = os.path.join(KLASOR, ad)
        if os.path.exists(yol):
            try:
                im = Image.open(yol).convert("RGBA")
                im.thumbnail((n, n), Image.Resampling.LANCZOS)
                tuval = Image.new("RGBA", (n, n), (0, 0, 0, 0))
                tuval.paste(im, ((n - im.width) // 2, (n - im.height) // 2), im)
                return tuval
            except Exception as hata:
                print("Amblem okunamadı:", ad, hata)
    print("bozok_logo.png bulunamadı; geçici amblem kullanılıyor.")
    return yer_tutucu_logo(n)


class Acilis(Entity):
    def __init__(self, uygulama):
        super().__init__()
        self.u = uygulama
        self.u.enabled = False                 # ana program, animasyon bitene dek bekler
        self.t = 0.0
        self.patladi = self.atlandi = self.baslatildi = False
        self.ses = None
        R = random.Random(21)
        ui = camera.ui
        self.parcalar = []

        def ekle(**kw):
            e = Entity(parent=ui, **kw)
            self.parcalar.append(e)
            return e
        self.ekle = ekle

        # ---- gezegen görselleri (gerçekçi dokulardan)
        print("Açılış gezegenleri hazırlanıyor...")
        d_img = dokular.doku_uret(dict(ad="Dünya", renk="#4f9bff", doku="dunya", boyut=DOKU_BOYUT),
                                  ayri_bulut=False).renk
        m_img = dokular.doku_uret(dict(ad="Mars", renk="#b4532f", doku="kaya", boyut=DOKU_BOYUT)).renk
        self.dunya_tex = Texture(kure_gorseli(d_img, 256, donus=2.2))
        self.mars_tex = Texture(kure_gorseli(m_img, 256, donus=.6, atm=(255, 170, 120), atm_guc=.25))
        self.logo_tex = Texture(logo_yukle())

        # ---- arka plan
        self.kara = ekle(model="quad", color=Color(0, 0, 0, 1), scale=(4, 2), z=-1, collider="box")
        self.parilti = ekle(model="quad", texture=Texture(dokular.parilti((255, 170, 80))),
                            scale=.01, z=-1.15, color=Color(1, 1, 1, 0))

        # ---- gezegenler: çarpışma noktası ekranın tam ortası (0, 0)
        self.d_bas, self.m_bas = (-1.15, .17), (1.15, -.13)
        self.d_son, self.m_son = (-DUNYA_CAP / 2, 0.0), (MARS_CAP / 2, 0.0)
        self.dunya = ekle(model="quad", texture=self.dunya_tex, scale=DUNYA_CAP, position=(*self.d_bas, -1.3),
                          color=Color(1, 1, 1, 1))
        self.mars = ekle(model="quad", texture=self.mars_tex, scale=MARS_CAP, position=(*self.m_bas, -1.3),
                         color=Color(1, 1, 1, 1))

        # ---- çarpışma: yalnızca şok halkaları (kıvılcım/ışıltı yok)
        cember = [Vec3(math.cos(i / 128 * 6.2832), math.sin(i / 128 * 6.2832), 0) for i in range(129)]
        self.halkalar = []
        for gecikme, kalin, maks in ((0.0, 5, 2.4), (.3, 3, 2.0)):
            e = ekle(model=Mesh(vertices=cember, mode="line", thickness=kalin), z=-1.35,
                     scale=.001, color=Color(1, .9, .7, 0))
            self.halkalar.append((e, gecikme, maks))

        # ---- amblem (tam ortada) ve parıltısı
        self.logo = ekle(model="quad", texture=self.logo_tex, scale=.01, position=(0, 0, -1.6),
                         color=Color(1, 1, 1, 0))
        self.flas = ekle(model="quad", color=Color(1, 1, 1, 0), scale=(4, 2), z=-2)

        # ---- hakkındaki isimler: çarpışmadan sonra ekrana gelişi güzel dağılır
        adlar = list(dict.fromkeys(getattr(hakkinda, "EKIP", [])))
        R2 = random.Random(5)
        renkler = [(1, .95, .85), (1, .82, .45), (.65, .85, 1), (1, .7, .85), (.7, 1, .8)]
        yerler = []
        self.isimler = []
        for ad in adlar:
            olcek = R2.uniform(1.6, 2.1)
            yari = len(ad) * .0183 * olcek * YAZI_OLCEK / 2          # yazının yaklaşık yarı genişliği
            xs = .86 - yari - .04
            for _ in range(800):
                fx, fy = R2.uniform(-xs, xs), R2.uniform(-.44, .44)
                if abs(fy) < .31 and abs(fx) < yari + .30:           # amblem bölgesi
                    continue
                if -.47 < fy < -.27:                                 # başlık ve alt yazı bölgesi
                    continue
                if any(abs(fx - a_) < yari + h_ + .07 and abs(fy - b_) < .09 for a_, b_, h_ in yerler):
                    continue
                break
            yerler.append((fx, fy, yari))
            t = Yazi(parent=ui, text=ad, origin=(0, 0), position=(0, 0, -1.4), scale=.01,
                     color=Color(1, 1, 1, 0))
            self.parcalar.append(t)
            self.isimler.append((t, fx, fy, R2.uniform(-18, 18), olcek, R2.uniform(0, 6.28), R2.choice(renkler),
                                 R2.uniform(.015, .03), R2.uniform(.012, .025), R2.uniform(.7, 1.5), R2.uniform(.6, 1.3)))

        def yazi(metin, olcek, y, renk):
            t = Yazi(parent=ui, text=metin, origin=(0, 0), position=(0, y, -3), scale=olcek, color=renk)
            self.parcalar.append(t)
            return t
        self.baslik = yazi(BASLIK, 2.3, -.33, Color(1, .95, .85, 0))
        self.alt = yazi(ALT_YAZI, 1.5, -.405, Color(1, .8, .5, 0))
        self.ipucu = yazi("Geçmek için herhangi bir tuşa basın", .9, -.475, Color(.7, .7, .85, .8))

    # ---------------- ses ----------------
    def ses_cal(self):
        try:
            from panda3d.core import Filename
            yol = ses.patlama_yolu()
            self.ses = application.base.loader.loadSfx(Filename.fromOsSpecific(yol))
            self.ses.setVolume(1.0)
            self.ses.play()
        except Exception as hata:              # ses çalmazsa görüntü yine de devam eder
            print("Çarpışma sesi çalınamadı:", hata)

    # ---------------- olaylar ----------------
    def input(self, key):
        if self.t < SOLMA:                     # herhangi bir tuşla animasyonu atla
            self.atlandi = True
            self.t = SOLMA

    def bitir(self):
        for e in self.parcalar:
            destroy(e)
        destroy(self)

    def carpisma_baslat(self):
        self.patladi = True
        self.dunya.enabled = False
        self.mars.enabled = False
        if not self.atlandi:
            self.ses_cal()

    # ---------------- her kare ----------------
    def update(self):
        self.t += min(1 / 20, time.dt)
        t = self.t
        solma = sinirla((t - SOLMA) / SOLMA_SURE)
        gorunur = 1 - solma

        # 1) yaklaşma: gezegenler hızlanarak ekranın ortasına gelir
        if t < TC:
            p = sinirla((t - .2) / (TC - .2))
            e = p ** 2.2
            self.dunya.position = (self.d_bas[0] + (self.d_son[0] - self.d_bas[0]) * e,
                                   self.d_bas[1] + (self.d_son[1] - self.d_bas[1]) * e, -1.3)
            self.mars.position = (self.m_bas[0] + (self.m_son[0] - self.m_bas[0]) * e,
                                  self.m_bas[1] + (self.m_son[1] - self.m_bas[1]) * e, -1.3)
            self.dunya.rotation_z = t * 14
            self.mars.rotation_z = -t * 24
            self.dunya.color = self.mars.color = Color(1, 1, 1, sinirla(t / .3))
            if p > .88:                          # çarpışmaya yakın hafif parıltı
                self.parilti.scale = .03 + .5 * ((p - .88) / .12) ** 2
                self.parilti.color = Color(1, 1, 1, .8 * ((p - .88) / .12))
            return

        tb = t - TC
        if not self.patladi:
            self.carpisma_baslat()

        # 2) çarpışma
        self.flas.color = Color(1, 1, 1, (sinirla(1 - tb / .8)) ** 1.6 * (0 if self.atlandi else 1))
        self.parilti.scale = .08 + 1.2 * yavasla(tb / .5)
        self.parilti.color = Color(1, 1, 1, sinirla(1 - tb / .35) * gorunur)
        for e, gecikme, maks in self.halkalar:
            s = sinirla((tb - gecikme) / 2.3)
            e.scale = max(.001, maks * yavasla(s))
            e.color = Color(1, .9, .7, (1 - s) * .9 * (1 if tb > gecikme else 0))
        for yz_, fx, fy, rot, olcek, faz, rgb, ax, ay, f1, f2 in self.isimler:   # çarpışma noktasından saçılır, süzülür
            k = yavasla((tb - .15) / 1.3)
            yz_.position = (fx * k + ax * math.sin(t * f1 + faz), fy * k + ay * math.cos(t * f2 + faz), -1.4)
            yz_.scale = olcek * (.3 + .7 * k) * (1 + .03 * math.sin(t * 1.6 + faz)) * YAZI_OLCEK
            yz_.rotation_z = rot * k + 4 * math.sin(t * f1 * .8 + faz)
            yz_.color = Color(rgb[0], rgb[1], rgb[2], sinirla((tb - .2) / .5) * gorunur)

        # 3) amblem çarpışma noktasında (tam ortada) doğar, başlık yazılır
        la = yavasla((tb - LOGO_T) / 1.0)
        nabiz = 1 + .025 * math.sin(t * 2.2)
        self.logo.scale = max(.01, LOGO_BOYUT * la * nabiz)
        self.logo.position = (.012 * math.sin(t * 1.1), .014 * math.sin(t * 1.7), -1.6)
        self.logo.rotation_z = 4 * math.sin(t * 1.3) * la
        self.logo.color = Color(1, 1, 1, la * gorunur)
        self.baslik.color = Color(1, .95, .85, sinirla((tb - 1.2) / .7) * gorunur)
        self.alt.color = Color(1, .8, .5, sinirla((tb - 1.7) / .7) * gorunur)
        self.ipucu.color = Color(.7, .7, .85, .8 * gorunur)
        self.kara.color = Color(0, 0, 0, 1 - solma)

        if solma > 0 and not self.baslatildi:               # 4) ana ekran uzaktan yaklaşarak gelir
            self.baslatildi = True
            self.u.dist = 420
            self.u.enabled = True
            self.kara.collider = None
        if solma >= 1:
            self.bitir()
