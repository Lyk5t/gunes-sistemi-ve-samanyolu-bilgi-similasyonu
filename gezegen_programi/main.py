"""
Samanyolu 3B Gezegen Laboratuvarı (masaüstü programı, Python + Ursina)

Kurulum:    pip install ursina        (Windows'ta calistir.bat bunu kendisi yapar)
Çalıştırma: python main.py

Fare: basılı tutup sürükle = döndür, tekerlek = yakınlaştır, gezegene tıkla = seç.
"""
import json
import math
import os
import time

from ursina import (Button, Entity, Mesh, Text, Ursina, Vec3, application, camera, destroy,
                    held_keys, mouse, window)
from ursina.color import Color
from ursina.prefabs.input_field import InputField

import bilgiler
import gezegenler
from acilis import Acilis
from arayuz import YAZI_OLCEK, Dugme, Kaydirici, Yazi, dongu_dugme
from sahne import CANLI, Gezegen3B, hx, sahne_kur

DOSYA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ozel_gezegenler.json")
HIZLAR = [0.25, 1, 4, 16, 64]          # 1 gerçek saniye = 30 gün x hız
RENKLER = {"Pembe": "#ff7ac8", "Mavi": "#4f9bff", "Turkuaz": "#4de1d2", "Yeşil": "#5fd07a",
           "Sarı": "#ffd36b", "Turuncu": "#ff9a4d", "Kırmızı": "#e0453a", "Mor": "#a77bff",
           "Beyaz": "#f2f2f2", "Gri": "#9a9aa8"}
GAZ_RENK = {"Azot": "#6fa8ff", "Oksijen": "#ff6b7a", "Argon": "#c0a3ff", "Hidrojen": "#7ff0ff",
            "Helyum": "#ffe27a", "Metan": "#5af0a0", "Karbondioksit": "#ff9d5c",
            "Sodyum": "#ffc04d", "Neon": "#ff8ad8", "Su buharı": "#9fd8ff", "Diğer": "#8d8bb0"}
PALET = ["#ff7ac8", "#7ad8ff", "#ffd36b", "#8cf29b", "#b79bff", "#ff9a6b"]
PANEL = Color(.06, .07, .18, .88)
YAZI = Color(.93, .92, 1, 1)
SOLUK = Color(.68, .67, .82, 1)
PX = .435   # sağ panel sol kenarı


def bicim(v):
    if v == 0:
        return "0"
    if abs(v) < 0.01:
        return f"{v:.1e}"
    return f"{v:.2f}" if abs(v) < 10 else f"{v:.1f}"


def ozel_yukle():
    try:
        with open(DOSYA, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


class Uygulama(Entity):
    def __init__(self):
        super().__init__()
        camera.clip_plane_far = 4000
        camera.fov = 60
        window.color = Color(.02, .03, .08, 1)
        window.exit_button.visible = False
        window.fps_counter.enabled = False
        sahne_kur()

        # ---------- MODEL ----------
        self.gezegenler, self.etiketler = [], {}
        for v in gezegenler.yukle():
            self.ekle(v)
        for v in ozel_yukle():
            self.ekle(v, True)
        self.secili = None
        self.T = 0.0
        self.calisiyor = True
        self.hiz = 1
        self.canli_t = 0.0
        self.dyn, self.btn = [], []
        # kamera durumu
        self.yaw, self.pitch, self.dist = 25, 35, 100
        self.dist_h = self.dist
        self.hedef = Vec3(0, 0, 0)
        self.serbest_merkez = Vec3(0, 0, 0)
        self.surukle_sol = False
        self.surukle_sag = False
        self.bas = None

        # ---------- ARAYÜZ ----------
        self.panel_kur()
        self.form_kur()
        self.hakkinda_kur()
        self.alt_cubuk_kur()
        self.sec(None)

    # ================= model işlemleri =================
    def ekle(self, v, ozel=False):
        g = Gezegen3B(v, ozel, len(self.gezegenler))
        self.gezegenler.append(g)
        # scale=.85 olan değeri scale=1.6 olarak değiştirdik
        # scale=.85 olan değeri scale=1.6 olarak değiştirdik
        self.etiketler[g] = Yazi(parent=camera.ui, text=v["ad"], origin=(0, 0), scale=2.0,
                                 color=hx(v["renk"], 1, 1.15))
        return g

    def kaydet(self):
        try:
            with open(DOSYA, "w", encoding="utf-8") as f:
                json.dump([g.v for g in self.gezegenler if g.ozel], f, ensure_ascii=False)
        except OSError:
            pass

    @property
    def dmax(self):
        return max(g.d for g in self.gezegenler)

    # ================= arayüz kurulumu =================
    def panel_kur(self):
        ui = camera.ui
        Entity(parent=ui, model="quad", color=PANEL, scale=(.47, .86), position=(.655, -.02, 1))
        self.p_serit = Entity(parent=ui, model="quad", color=Color(1, .8, .4, 1), scale=(.47, .008),
                              position=(.655, .41, .5))
        self.p_ad = Yazi(parent=ui, text=" ", position=(PX, .395), scale=1.9)
        self.p_bilgi = Yazi(parent=ui, text=" ", position=(PX, .33), scale=.8, color=SOLUK)
        self.p_bilgi.wordwrap = int(24 / YAZI_OLCEK)
        self.p_stat = Yazi(parent=ui, text=" ", position=(PX, .205), scale=.8, color=YAZI)
        self.p_stat.wordwrap = int(24 / YAZI_OLCEK)
        self.p_atm = Yazi(parent=ui, text="ATMOSFER BİLEŞİMİ", position=(PX, .105), scale=.75)
        self.canli_grup = Entity(parent=ui)
        self.p_canli_baslik = Yazi(parent=self.canli_grup, text="CANLI ATMOSFER VERİSİ (simüle)",
                                   position=(PX, -.055), scale=.75)
        self.satirlar = []
        for i, (ad, _, birim, _, renk) in enumerate(CANLI):
            y = -.09 - i * .115
            t = Yazi(parent=self.canli_grup, text=" ", position=(PX, y), scale=.85, color=hx(renk, 1, 1.2))
            e = Entity(parent=self.canli_grup, color=hx(renk))
            self.satirlar.append((t, e, y))

    def alt_cubuk_kur(self):
        ui = camera.ui
        self.btn_oynat = Dugme(parent=ui, text="Duraklat", position=(-.80, -.465), scale=(.13, .04),
                                color=Color(1, .55, .25, 1), on_click=self.oynat_durdur)
        Dugme(parent=ui, text="-", position=(-.715, -.465), scale=(.04, .04), color=Color(.25, .27, .5, 1),
               on_click=lambda: self.hiz_degis(-1))
        self.hiz_yazi = Yazi(parent=ui, text="1x", position=(-.690, -.452), scale=.9)
        Dugme(parent=ui, text="+", position=(-.625, -.465), scale=(.04, .04), color=Color(.25, .27, .5, 1),
               on_click=lambda: self.hiz_degis(1))
        Dugme(parent=ui, text="+ Yeni gezegen", position=(-.51, -.465), scale=(.16, .04),
               color=Color(1, .37, .63, 1), on_click=self.form_ac)
        Yazi(parent=ui, text="Sol Tık Sürükle: Döndür  |  Sağ Tık Sürükle: Kaydır  |  Tekerlek: Yakınlaştır", position=(-.40, -.452), scale=1.4, color=SOLUK)

    def form_kur(self):
        f = self.form = Entity(parent=camera.ui, enabled=False)
        Entity(parent=f, model="quad", color=PANEL, scale=(.40, .86), position=(-.69, 0, 1))
        Entity(parent=f, model="quad", color=Color(1, .37, .63, 1), scale=(.40, .008), position=(-.69, .43, .5))
        Yazi(parent=f, text="KENDİ GEZEGENİNİ OLUŞTUR", position=(-.88, .418), scale=1.0, color=Color(1, .6, .8, 1))
        Yazi(parent=f, text="Ad:", position=(-.88, .378), scale=.85)
        self.ad_giris = InputField(parent=f, default_value="Nova", position=(-.68, .36), scale=(.30, .036),
                                   character_limit=18)
        self.tur = dongu_dugme(f, "Tür: ", ["Kayalık", "Gaz devi"], -.79, .31, .17)
        self.renk = dongu_dugme(f, "Renk: ", list(RENKLER), -.605, .31, .17)
        self.atm_renk = dongu_dugme(f, "Atm.: ", list(RENKLER), -.79, .27, .17, 2)
        self.halka = dongu_dugme(f, "Halka: ", ["Yok", "Var"], -.605, .27, .17)
        sl = [("yaricap", "Yarıçap (Dünya=1)", .1, 12, 1.5, .1, "", 1),
              ("au", "Güneş’e uzaklık", .3, 40, 2.5, .1, "AU", 1),
              ("periyot", "Yörünge periyodu", 10, 70000, 500, 10, "gün", 0),
              ("sicak", "Sıcaklık", -250, 500, 20, 1, "°C", 0),
              ("basinc", "Basınç", 0, 100, 1.2, .1, "bar", 1),
              ("ruzgar", "Rüzgâr hızı", 0, 600, 12, 1, "m/s", 0),
              ("atm_k", "Atmosfer kalınlığı", 0, 1, .6, .05, "", 2)]
        self.sl = {}
        for i, (k, et, mn, mx, de, ad, bi, nd) in enumerate(sl):
            self.sl[k] = Kaydirici(f, -.88, .205 - i * .05, .36, mn, mx, de, ad, et, bi, nd)
        Yazi(parent=f, text="Atmosfer gazları (yüzde)", position=(-.88, -.1), scale=.8, color=SOLUK)
        secenek = ["—"] + list(GAZ_RENK)
        self.gaz_satir = []
        for i, (gaz, y) in enumerate((("Azot", 70), ("Oksijen", 20), ("Argon", 10))):
            yy = -.16 - i * .05
            b = dongu_dugme(f, "", secenek, -.805, yy - .006, .15, secenek.index(gaz))
            k = Kaydirici(f, -.72, yy, .20, 0, 100, y, 1, "Pay", "%", 0)
            self.gaz_satir.append((b, k))
        Dugme(parent=f, text="Gezegeni oluştur", position=(-.79, -.315), scale=(.17, .036),
               color=Color(1, .37, .63, 1), on_click=self.olustur)
        Dugme(parent=f, text="Seçiliden kopyala", position=(-.605, -.315), scale=(.17, .036),
               color=Color(.25, .27, .5, 1), on_click=self.kopyala)
        Dugme(parent=f, text="Seçiliyi sil", position=(-.79, -.36), scale=(.17, .036),
               color=Color(.5, .2, .25, 1), on_click=self.sil)
        Dugme(parent=f, text="Kapat", position=(-.605, -.36), scale=(.17, .036),
               color=Color(.25, .27, .5, 1), on_click=self.form_kapat)

    def hakkinda_kur(self):
        import hakkinda
        ui = camera.ui
        Dugme(parent=ui, text="Hakkında", position=(.80, .465), scale=(.14, .04),
              color=Color(1, .37, .63, 1), on_click=self.hakkinda_ac)
        h = self.hak = Entity(parent=ui, enabled=False)
        Entity(parent=h, model="quad", color=Color(.05, .06, .16, .97), scale=(.62, .76), position=(0, 0, -1))
        Entity(parent=h, model="quad", color=Color(1, .37, .63, 1), scale=(.62, .008), position=(0, .378, -1.05))
        y = .345

        def satir(t, olcek=1.0, renk=YAZI, bosluk=.04):
            nonlocal y
            Yazi(parent=h, text=t, position=(-.28, y, -1.1), scale=olcek, color=renk)
            y -= bosluk
        ALTIN = Color(1, .83, .42, 1)
        satir("HAKKINDA", 1.8, Color(1, .6, .8, 1), .075)
        satir(hakkinda.PROJE_ADI, 1.1, YAZI, .06)
        satir(hakkinda.OKUL, 1.0, YAZI, .038)
        satir(hakkinda.BIRIM, 1.0, SOLUK, .038)
        if getattr(hakkinda, "BOLUM", ""):
            satir(hakkinda.BOLUM, 1.0, SOLUK, .06)
        else:
            y -= .02
        # --- Star Wars tarzı kayan yazı: lider ve ekip isimleri perspektifle yukarı süzülür ---
        Entity(parent=h, model="quad", color=Color(1, .83, .42, .45), scale=(.5, .002), position=(0, .05, -1.06))
        ALTIN_RGB, SARI_RGB, BEYAZ_RGB = (1, .83, .42), (1, .95, .6), (.93, .92, 1)
        satirlar = ([("PROJE LİDERİ", 1.0, ALTIN_RGB), (hakkinda.PROJE_LIDERI, 1.7, SARI_RGB),
                     (None, 0, None), ("EKİP", 1.0, ALTIN_RGB)]
                    + [(ad, 1.5, BEYAZ_RGB) for ad in hakkinda.EKIP])
        self.kayan = []
        for metin, olcek, rgb in satirlar:
            t = None if metin is None else Yazi(parent=h, text=metin, origin=(0, 0), position=(0, 0, -1.1),
                                                scale=olcek, color=Color(*rgb, 0))
            self.kayan.append((t, olcek, rgb))
        self.kay_t = 0.0
        Dugme(parent=h, text="Kapat", position=(0, -.335, -1.1), scale=(.14, .04),
              color=Color(.25, .27, .5, 1), on_click=self.hakkinda_kapat)

    def hakkinda_ac(self):
        self.kay_t = 0.0
        self.hak.enabled = True

    def hakkinda_kapat(self):
        self.hak.enabled = False

    def kayan_yazi(self, dt):
        """Satırlar aşağıdan (büyük, yakın) yukarıya (küçük, uzak) süzülür ve solar."""
        self.kay_t += dt * .55                     # kayma hızı (satır/sn); büyütürseniz hızlanır
        toplam = len(self.kayan) + 3               # döngüde yeni tur öncesi boşluk
        U, a = 7.0, 2.6                            # görünür derinlik ve perspektif şiddeti
        y_ust, y_alt = .04, -.29
        norm = 1 - 1 / (1 + a)
        for i, (t, olcek, rgb) in enumerate(self.kayan):
            if t is None:
                continue
            u = (self.kay_t - i) % toplam
            if u > U:
                t.enabled = False
                continue
            t.enabled = True
            s = 1 / (1 + a * u / U)                # uzaklaştıkça küçülür
            t.position = (0, y_alt + (y_ust - y_alt) * (1 - s) / norm, -1.1)
            t.scale = olcek * s * YAZI_OLCEK
            alfa = min(1, u / .7) * min(1, (U - u) / 2.5)
            t.color = Color(rgb[0], rgb[1], rgb[2], max(0, alfa))

    def butonlari_yenile(self):
        for b in self.btn:
            destroy(b)
        self.btn = []

        # --- YENİ KORUMA KALKANI VE HOVER (PARLAMA) EFEKTİ ---
        def fare_durumu(buton, uzerinde_mi):
            try:
                if uzerinde_mi:
                    buton.color = buton.highlight_color # Fare gelince parlat
                else:
                    buton.color = buton.orijinal_renk   # Fare gidince eski renge dön
            except Exception:
                pass # Buton silinmişse programı çökertme
        # -----------------------------------------------------

        ad = [("Güneş Sistemi", None, "#ffd36b")] + [(g.v["ad"], g, g.v["renk"]) for g in self.gezegenler]
        n = len(ad) - 1
        bas_w, bosluk = .15, .008
        w = min(.092, (1.6 - bas_w - bosluk * (n + 1)) / max(1, n))
        x = -.86

        for i, (t, g, renk) in enumerate(ad):
            gw = bas_w if i == 0 else w
            secili = g is self.secili

            # Yüksekliği .04'ten .06'ya çıkardık
            b = Dugme(parent=camera.ui, text=t, position=(x + gw / 2, .465), scale=(gw, .06),
                      color=hx(renk, 1, 1 if secili else .38), on_click=lambda g=g: self.sec(g))
            b.text_color = Color(.05, .05, .12, 1) if secili else YAZI

            # Yazıyı bozmadan uygun boyuta (0.8) ayarlayan kod
            b.text_entity.scale *= 1.6

            # Parlatma (Hover) komutu
            b.orijinal_renk = b.color
            b.on_mouse_enter = lambda b=b: fare_durumu(b, True)
            b.on_mouse_exit = lambda b=b: fare_durumu(b, False)

            self.btn.append(b)
            x += gw + bosluk

    def oynat_durdur(self):
        self.calisiyor = not self.calisiyor
        self.btn_oynat.text = "Duraklat" if self.calisiyor else "Başlat"

    def hiz_degis(self, d):
        self.hiz = max(0, min(len(HIZLAR) - 1, self.hiz + d))
        self.hiz_yazi.text = f"{HIZLAR[self.hiz]}x"

    def form_ac(self):
        self.form.enabled = True
        Kaydirici.gorunur = True

    def form_kapat(self):
        self.form.enabled = False
        Kaydirici.gorunur = False
        Kaydirici.aktif = None

    def sec(self, g):
        self.secili = g
        self.dist_h = self.dmax * 1.7 if g is None else max(g.r * 5, 2.5)
        self.butonlari_yenile()
        self.panel_yenile()
        if g is not None:
            self.canli()

    def olustur(self):
        gazlar = [(b.secenekler[b.sec], float(k.deger)) for b, k in self.gaz_satir
                  if b.secenekler[b.sec] != "—" and k.deger > 0] or [("Diğer", 100.0)]
        renk = RENKLER[list(RENKLER)[self.renk.sec]]
        v = dict(ad=(self.ad_giris.text or "Nova").strip()[:18] or "Nova", renk=renk,
                 yaricap_km=float(self.sl["yaricap"].deger) * 6371, au=float(self.sl["au"].deger),
                 periyot=float(self.sl["periyot"].deger), uydu=0, sicak=float(self.sl["sicak"].deger),
                 basinc=float(self.sl["basinc"].deger), ruzgar=float(self.sl["ruzgar"].deger),
                 atm_renk=RENKLER[list(RENKLER)[self.atm_renk.sec]], atm_k=float(self.sl["atm_k"].deger),
                 gazlar=gazlar, halka=renk if self.halka.sec == 1 else None,
                 doku="kaya" if self.tur.sec == 0 else "gaz", bilgi="Sizin oluşturduğunuz gezegen.")
        g = self.ekle(v, True)
        self.kaydet()
        self.form_kapat()
        self.sec(g)

    def kopyala(self):
        g = self.secili
        if g is None:
            return
        v = g.v
        for k, x in {"yaricap": v["yaricap_km"] / 6371, "au": v["au"], "periyot": v["periyot"],
                     "sicak": v["sicak"], "basinc": v["basinc"], "ruzgar": v["ruzgar"],
                     "atm_k": v["atm_k"]}.items():
            self.sl[k].ata(x)
        self.ad_giris.text = v["ad"][:15] + " 2"
        self.tur.ata(1 if v.get("doku") == "gaz" else 0)
        self.halka.ata(1 if v.get("halka") else 0)
        secenek = ["—"] + list(GAZ_RENK)
        for (b, k), (gaz, y) in zip(self.gaz_satir, list(v["gazlar"]) + [("—", 0)] * 3):
            b.ata(secenek.index(gaz) if gaz in secenek else 0)
            k.ata(y)

    def sil(self):
        g = self.secili
        if g is None or not g.ozel:
            return
        self.sec(None)
        destroy(self.etiketler.pop(g))
        g.sil()
        self.gezegenler.remove(g)
        self.kaydet()
        self.butonlari_yenile()

    def ui_ustunde(self):
        he = mouse.hovered_entity
        return he is not None and he.has_ancestor(camera.ui)

    def input(self, key):
        if key == "scroll up":
            self.dist_h = max(2, self.dist_h * .88)
        elif key == "scroll down":
            self.dist_h = min(400, self.dist_h * 1.14)
        elif key == "right mouse down":
            self.surukle_sag = not self.ui_ustunde()
            self.bas = (mouse.x, mouse.y)
        elif key == "left mouse down":
            self.surukle_sol = not self.ui_ustunde()
            self.bas = (mouse.x, mouse.y)
        elif key in ("right mouse up", "left mouse up"):
            if key == "right mouse up":
                self.surukle_sag = False
            if key == "left mouse up":
                self.surukle_sol = False
                if self.bas and abs(mouse.x - self.bas[0]) + abs(mouse.y - self.bas[1]) < .012:
                    for g in self.gezegenler:
                        if mouse.hovered_entity is g.govde:
                            self.sec(g)
                            break
        elif key == "escape":
            if self.hak.enabled:
                self.hakkinda_kapat()
            else:
                application.quit()

    # ================= bilgi paneli =================
    def panel_yenile(self):
        for e in self.dyn:
            destroy(e)
        self.dyn = []
        g = self.secili
        if g is None:
            self.p_serit.color = Color(1, .8, .4, 1)
            self.p_ad.text, self.p_ad.color = getattr(bilgiler, "BASLIK", "Güneş Sistemi"), Color(1, .83, .42, 1)
            aciklama = getattr(bilgiler, "ACIKLAMA", "") or " "
            maddeler = getattr(bilgiler, "MADDELER", [])
            self.p_bilgi.text = aciklama
            # açıklama uzunsa maddeleri aşağı kaydır (satır sayısı yaklaşık hesaplanır)
            satir = sum(max(1, math.ceil(len(p) / 38)) for p in aciklama.split("\n"))
            self.p_stat.position = (PX, max(-.3, .33 - satir * .021 - .035))
            self.p_stat.text = "\n".join(f"{b}: {d}" for b, d in maddeler) or " "
            self.p_atm.enabled = False
            self.canli_grup.enabled = False
            return
        v = g.v
        self.p_serit.color = hx(v["renk"])
        self.p_ad.text, self.p_ad.color = v["ad"], hx(v["renk"], 1, 1.15)
        self.p_bilgi.text = v["bilgi"]
        self.p_stat.position = (PX, .205)
        km = f"{v['yaricap_km']:,.0f}".replace(",", " ")
        self.p_stat.text = (f"Yarıçap: {km} km\nGüneş’e uzaklık: {v['au']} AU\n"
                            f"Yörünge periyodu: {v['periyot']} gün\nBilinen uydu: {v['uydu']}")
        self.p_atm.enabled = True
        self.p_atm.color = hx(v["renk"], 1, 1.15)
        self.canli_grup.enabled = True
        top = sum(y for _, y in v["gazlar"])
        x = PX
        for i, (a, y) in enumerate(v["gazlar"]):
            c = hx(GAZ_RENK.get(a, PALET[i % len(PALET)]))
            w = y / top * .44
            self.dyn.append(Entity(parent=camera.ui, model="quad", color=c, scale=(w, .018),
                                   origin=(-.5, 0), position=(x, .078, -.01)))
            x += w
            lx, ly = PX + (i % 2) * .22, .05 - (i // 2) * .028
            self.dyn.append(Entity(parent=camera.ui, model="quad", color=c, scale=(.012, .012),
                                   position=(lx + .006, ly - .011, -.01)))
            self.dyn.append(Yazi(parent=camera.ui, text=f"{a} %{y / top * 100:.1f}",
                                 position=(lx + .02, ly), scale=.75, color=YAZI))

    def canli(self):
        g = self.secili
        g.canli_guncelle()
        for L, (t, e, y), (ad, _, birim, _, renk) in zip(g.canli, self.satirlar, CANLI):
            t.text = f"{ad}: {bicim(L['v'])} {birim}"
            h = L["h"]
            lo, hi = min(h), max(h)
            r = (hi - lo) or 1
            e.model = Mesh(vertices=[Vec3(PX + i / 39 * .44, y - .095 + (v - lo) / r * .05, -.02)
                                     for i, v in enumerate(h)], mode="line", thickness=2)

    # ================= her kare =================
    def kamera(self, dt):
        # SOL TIK: Yörünge etrafında döndürme (Orbit)
        if getattr(self, "surukle_sol", False) and Kaydirici.aktif is None and held_keys["left mouse"]:
            self.yaw -= mouse.velocity[0] * 120
            self.pitch = max(-85, min(85, self.pitch - mouse.velocity[1] * 100))
            
        # SAĞ TIK: Serbest sahne kaydırma (Pan)
        if getattr(self, "surukle_sag", False) and Kaydirici.aktif is None and held_keys["right mouse"]:
            if self.secili is not None:
                self.sec(None)
            
            pan_hizi = self.dist * 0.04
            
            # serbest_merkez değişkeni henüz tanımlanmadıysa hatayı önlemek için:
            if not hasattr(self, "serbest_merkez"):
                self.serbest_merkez = Vec3(0, 0, 0)
                
            self.serbest_merkez -= camera.right * mouse.velocity[0] * pan_hizi * 50
            self.serbest_merkez -= camera.up * mouse.velocity[1] * pan_hizi * 50

        # Eğer bir gezegen seçiliyse hedefini o yap, değilse kendi serbest merkezimiz
        if not hasattr(self, "serbest_merkez"):
            self.serbest_merkez = Vec3(0, 0, 0)
            
        hedef = Vec3(*self.secili.govde.position) if self.secili else self.serbest_merkez
        
        if self.secili:
            self.serbest_merkez = Vec3(hedef.x, hedef.y, hedef.z)

        self.hedef += (hedef - self.hedef) * min(1, dt * 8)
        self.dist += (self.dist_h - self.dist) * min(1, dt * 5)
        
        y, p = math.radians(self.yaw), math.radians(self.pitch)
        camera.position = self.hedef + Vec3(math.sin(y) * math.cos(p), math.sin(p),
                                            -math.cos(y) * math.cos(p)) * self.dist
        camera.look_at(self.hedef)
    def update(self):
        dt = time.dt
        if self.calisiyor:
            self.T += dt * 30 * HIZLAR[self.hiz]
        for g in self.gezegenler:
            g.guncelle(self.T, dt, self.calisiyor)
        self.kamera(dt)
        # --- GEZEGEN İSİMLERİNİN DİNAMİK YÜKSEKLİK AYARI ---
        for g, t in self.etiketler.items():
            p = g.govde.position
            if (Vec3(*p) - camera.world_position).dot(camera.forward) > 0:
                sp = g.govde.screen_position
                # y_offset ile yazıyı gezegenin üstüne tam oturtuyoruz
                y_offset = 0.05 + (g.r * 0.015)
                t.position = (sp[0], sp[1] + y_offset)
                t.enabled = True
            else:
                t.enabled = False
        # ---------------------------------------------------

        if self.hak.enabled:
            self.kayan_yazi(dt)
        self.canli_t += dt
        if self.canli_t > .5 and self.secili is not None:
            self.canli_t = 0
            self.canli()


if __name__ == "__main__":
    # Kenar yumuşatma (MSAA): gezegen kenarları ve halkalar pürüzsüz görünür.
    # Ekran kartınız desteklemezse bu iki satırı silin.
    from panda3d.core import loadPrcFileData
    loadPrcFileData("", "framebuffer-multisample 1\nmultisamples 4")
    app = Ursina(title="Samanyolu 3B Gezegen Laboratuvarı", borderless=False)
    try:
        from panda3d.core import AntialiasAttrib
        application.base.render.setAntialias(AntialiasAttrib.MAuto)
    except Exception:
        pass
    print("Gezegenler hazırlanıyor, birkaç saniye sürebilir...")
    uygulama = Uygulama()
    Acilis(uygulama)          # Büyük Patlama açılışı; bitince ana ekran gelir
    app.run()
