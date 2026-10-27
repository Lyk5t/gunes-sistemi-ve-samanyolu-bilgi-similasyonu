"""Büyük Patlama açılışı: tek bir noktadan patlama, parçacıklar, şok dalgası ve ses.
Ardından kamera uzaktan yaklaşarak ana ekran açılır. Herhangi bir tuşla atlanabilir."""
import math
import random
import time

from ursina import Entity, Mesh, Texture, Vec3, application, camera, destroy
from ursina.color import Color

import dokular
import ses
from arayuz import Yazi

T0 = 1.8          # patlamadan önceki bekleyiş (sn)
SOLMA = 3.4       # patlamadan sonra solmanın başladığı an
SOLMA_SURE = 1.8  # solma süresi


def sinirla(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def yavasla(x):
    return 1 - (1 - sinirla(x)) ** 3


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

        # tüm ekranı örten siyah perde (tıklamaları da yutar)
        self.kara = ekle(model="quad", color=Color(0, 0, 0, 1), scale=(4, 2), z=-1, collider="box")
        self.parilti = ekle(model="quad", texture=Texture(dokular.parilti((255, 170, 80))),
                            scale=.01, z=-1.05, color=Color(1, 1, 1, 0))
        self.nokta = ekle(model="quad", texture=Texture(dokular.parilti((255, 240, 200))),
                          scale=.03, z=-1.5, color=Color(1, 1, 1, 1))

        # parçacık bulutları: (mesh, en büyük ölçek, hız katsayısı)
        self.bulutlar = []
        for adet, renkler, kalin, maks, hiz in (
                (1400, [(1, 1, 1), (1, .95, .7)], 3, 2.4, 3.0),
                (1400, [(1, .55, .15), (1, .25, .55), (.35, .55, 1), (.7, .35, 1)], 4, 1.7, 1.7),
                (900, [(.8, .85, 1)], 2, 3.0, 1.1)):
            v, c = [], []
            for _ in range(adet):
                a, d = R.uniform(0, 6.2832), R.random() ** .5
                v.append(Vec3(math.cos(a) * d, math.sin(a) * d, 0))
                r, g, b = R.choice(renkler)
                k = R.uniform(.5, 1)
                c.append(Color(r * k, g * k, b * k, 1))
            e = ekle(model=Mesh(vertices=v, colors=c, mode="point", thickness=kalin), z=-1.2, scale=.001)
            self.bulutlar.append((e, maks, hiz))

        # şok dalgası halkaları
        cember = [Vec3(math.cos(i / 128 * 6.2832), math.sin(i / 128 * 6.2832), 0) for i in range(129)]
        self.halkalar = []
        for gecikme, kalin, maks in ((0.0, 5, 2.6), (.35, 3, 2.2)):
            e = ekle(model=Mesh(vertices=cember, mode="line", thickness=kalin), z=-1.3,
                     scale=.001, color=Color(1, .9, .7, 0))
            self.halkalar.append((e, gecikme, maks))

        self.flas = ekle(model="quad", color=Color(1, 1, 1, 0), scale=(4, 2), z=-2)

        def yazi(metin, olcek, y, renk):
            t = Yazi(parent=ui, text=metin, origin=(0, 0), position=(0, y, -3), scale=olcek, color=renk)
            self.parcalar.append(t)
            return t
        self.giris = yazi("Başlangıçta her şey tek bir noktaydı…", 1.5, -.12, Color(.85, .85, 1, 0))
        self.baslik = yazi("SAMANYOLU 3B GEZEGEN LABORATUVARI", 3.0, .06, Color(1, .95, .85, 0))
        self.alt = yazi("Büyük Patlama’dan Güneş Sistemi’ne", 1.5, -.04, Color(1, .8, .5, 0))
        self.ipucu = yazi("Geçmek için herhangi bir tuşa basın", .9, -.46, Color(.7, .7, .85, .8))

    # ---------------- ses ----------------
    def ses_cal(self):
        try:
            from panda3d.core import Filename
            yol = ses.patlama_yolu()
            self.ses = application.base.loader.loadSfx(Filename.fromOsSpecific(yol))
            self.ses.setVolume(1.0)
            self.ses.play()
        except Exception as hata:              # ses çalmazsa görüntü yine de devam eder
            print("Patlama sesi çalınamadı:", hata)

    # ---------------- olaylar ----------------
    def input(self, key):
        if self.t < T0 + SOLMA:                # herhangi bir tuşla animasyonu atla
            self.atlandi = True
            self.t = T0 + SOLMA

    def bitir(self):
        for e in self.parcalar:
            destroy(e)
        destroy(self)

    # ---------------- her kare ----------------
    def update(self):
        self.t += min(1 / 20, time.dt)
        t = self.t
        if t < T0:                                          # 1) bekleyiş: parlayan nokta
            x = t / T0
            self.nokta.scale = .02 + .012 * math.sin(t * 11) + .05 * x ** 2
            self.giris.color = Color(.85, .85, 1, sinirla(t / .6) * sinirla((T0 - .2 - t) / .4))
            return
        tb = t - T0
        if not self.patladi:                                # 2) patlama anı
            self.patladi = True
            self.nokta.enabled = False
            self.giris.enabled = False
            if not self.atlandi:
                self.ses_cal()
        solma = sinirla((tb - SOLMA) / SOLMA_SURE)
        gorunur = 1 - solma

        self.flas.color = Color(1, 1, 1, (sinirla(1 - tb / 1.0)) ** 1.6 * (0 if self.atlandi else 1))
        self.parilti.scale = .05 + 3.8 * yavasla(tb / 1.6)
        self.parilti.color = Color(1, 1, 1, sinirla(1 - tb / 3.4) * gorunur)
        for e, maks, hiz in self.bulutlar:
            e.scale = max(.001, maks * (1 - math.exp(-tb * hiz)))
            e.color = Color(1, 1, 1, gorunur)
        for e, gecikme, maks in self.halkalar:
            s = sinirla((tb - gecikme) / 2.4)
            e.scale = max(.001, maks * yavasla(s))
            e.color = Color(1, .9, .7, (1 - s) * .9 * (1 if tb > gecikme else 0))

        self.baslik.color = Color(1, .95, .85, sinirla((tb - .9) / .9) * gorunur)
        self.alt.color = Color(1, .8, .5, sinirla((tb - 1.5) / .9) * gorunur)
        self.ipucu.color = Color(.7, .7, .85, .8 * gorunur)
        self.kara.color = Color(0, 0, 0, 1 - solma)

        if solma > 0 and not self.baslatildi:               # 3) ana ekran uzaktan yaklaşarak gelir
            self.baslatildi = True
            self.u.dist = 420
            self.u.enabled = True
            self.kara.collider = None
        if solma >= 1:
            self.bitir()
