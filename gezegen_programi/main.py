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
import random

from ursina import (Button, Entity, Mesh, Text, Ursina, Vec3, application, camera, destroy,
                    held_keys, mouse, window, scene)
from ursina.color import Color
from ursina.prefabs.input_field import InputField

import bilgiler
import gezegenler
import ses
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
        self.surukle, self.bas = False, None
        self.olusum_aktif = False
        self.kamera_hassasiyet = 1.0
        
        # --- TEHDİT VE SAVUNMA SİSTEMİ DEĞİŞKENLERİ ---
        self.dunya_ref = next((g for g in self.gezegenler if g.v["ad"] == "Dünya"), None)
        self.tehditler = []
        self.fuzeler = []
        self.patlamalar = []
        
        # Alarm Yazısı
        self.alarm_yazi = Yazi(parent=camera.ui, text="!! TEHLİKE: DÜNYA'YA CİSİM YAKLAŞIYOR !!",
                               position=(0, .40), scale=1.5, color=Color(1, 0, 0, 1), origin=(0, 0))
        self.alarm_yazi.enabled = False

        # --- SİREN SESİ YÜKLEME ---
        try:
            from panda3d.core import Filename
            siren_mp3_yol = os.path.join(os.path.dirname(os.path.abspath(__file__)), "siren.mp3")
            siren_wav_yol = os.path.join(os.path.dirname(os.path.abspath(__file__)), "siren.wav")
            
            if os.path.exists(siren_mp3_yol):
                self.siren_sesi = application.base.loader.loadSfx(Filename.fromOsSpecific(siren_mp3_yol))
                self.siren_sesi.setPlayRate(1.0)
            elif os.path.exists(siren_wav_yol):
                self.siren_sesi = application.base.loader.loadSfx(Filename.fromOsSpecific(siren_wav_yol))
                self.siren_sesi.setPlayRate(1.0)
            else:
                self.siren_sesi = application.base.loader.loadSfx(Filename.fromOsSpecific(ses.patlama_yolu()))
                self.siren_sesi.setPlayRate(4.0) # Dosya yoksa geçici yüksek tizli alarm efekti

            self.siren_sesi.setLoop(True) # Sesi döngüye al (sürekli çalsın)
            self.siren_sesi.setVolume(0.5)
        except Exception:
            self.siren_sesi = None
            
        self.siren_caliyor = False

        # ---------- ARAYÜZ ----------
        self.panel_kur()
        self.ayarlar_kur()
        self.form_kur()
        self.hakkinda_kur()
        self.alt_cubuk_kur()

        self.sec(None)

    def patlama_sesi_cal(self):
        try:
            from panda3d.core import Filename
            yol = ses.patlama_yolu()
            patlama = application.base.loader.loadSfx(Filename.fromOsSpecific(yol))
            patlama.setVolume(0.8)
            patlama.play()
        except Exception:
            pass

    def fuze_sesi_cal(self):
        try:
            from panda3d.core import Filename
            yol = ses.patlama_yolu()
            fuze = application.base.loader.loadSfx(Filename.fromOsSpecific(yol))
            fuze.setPlayRate(2.8)
            fuze.setVolume(0.4)
            fuze.play()
        except Exception:
            pass

    # ================= model işlemleri =================
    def ekle(self, v, ozel=False):
        g = Gezegen3B(v, ozel, len(self.gezegenler))
        self.gezegenler.append(g)
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
        
        sag_x = window.aspect_ratio / 2
        panel_w = 0.55  
        panel_merkez_x = sag_x - (panel_w / 2)
        self.PX = sag_x - panel_w + 0.03  

        Entity(parent=ui, model="quad", color=PANEL, scale=(panel_w, 1.2), position=(panel_merkez_x, 0, 1))
        self.p_serit = Entity(parent=ui, model="quad", color=Color(1, .8, .4, 1), scale=(panel_w, .008),
                              position=(panel_merkez_x, .46, .5))
        
        self.p_ad = Yazi(parent=ui, text=" ", position=(self.PX, .425), scale=1.9)
        self.p_bilgi = Yazi(parent=ui, text=" ", position=(self.PX, .35), scale=0.85, color=SOLUK)
        self.p_bilgi.wordwrap = 45 
        
        self.p_stat = Yazi(parent=ui, text=" ", position=(self.PX, .15), scale=0.85, color=YAZI)
        self.p_stat.wordwrap = 45
        
        self.p_atm = Yazi(parent=ui, text="ATMOSFER BİLEŞİMİ", position=(self.PX, .02), scale=.8)
        
        self.canli_grup = Entity(parent=ui)
        self.p_canli_baslik = Yazi(parent=self.canli_grup, text="CANLI ATMOSFER VERİSİ (simüle)",
                                   position=(self.PX, -.04), scale=.8)
        self.satirlar = []
        for i, (ad, _, birim, _, renk) in enumerate(CANLI):
            y = -.09 - i * .10
            t = Yazi(parent=self.canli_grup, text=" ", position=(self.PX, y), scale=.85, color=hx(renk, 1, 1.2))
            e = Entity(parent=self.canli_grup, color=hx(renk))
            self.satirlar.append((t, e, y))

    def alt_cubuk_kur(self):
        ui = camera.ui
        sol_x = -window.aspect_ratio / 2 + 0.05 
        
        self.btn_oynat = Dugme(parent=ui, text="Duraklat", position=(sol_x + .05, -.465), scale=(.13, .04),
                                color=Color(1, .55, .25, 1), on_click=self.oynat_durdur)
        Dugme(parent=ui, text="-", position=(sol_x + .16, -.465), scale=(.04, .04), color=Color(.25, .27, .5, 1),
               on_click=lambda: self.hiz_degis(-1))
        self.hiz_yazi = Yazi(parent=ui, text="1x", position=(sol_x + .20, -.452), scale=.9)
        Dugme(parent=ui, text="+", position=(sol_x + .26, -.465), scale=(.04, .04), color=Color(.25, .27, .5, 1),
               on_click=lambda: self.hiz_degis(1))
               
        Dugme(parent=ui, text="+ Yeni Gezegen", position=(sol_x + .40, -.465), scale=(.18, .04),
               color=Color(1, .37, .63, 1), on_click=self.form_ac)
               
        Yazi(parent=ui, text="Sürükle: döndür   Tekerlek: yakınlaştır   Gezegene tıkla: seç", position=(sol_x + .53, -.452), scale=1.1, color=SOLUK)

        sag_x = window.aspect_ratio / 2
        Dugme(parent=ui, text="Ayarlar", position=(sag_x - 0.34, .465), scale=(.12, .04),
               color=Color(.2, .5, .7, 1), on_click=self.ayarlar_ac)
        Dugme(parent=ui, text="Hakkında", position=(sag_x - 0.21, .465), scale=(.12, .04),
              color=Color(1, .37, .63, 1), on_click=self.hakkinda_ac)
        Dugme(parent=ui, text="Çıkış", position=(sag_x - 0.08, .465), scale=(.12, .04),
              color=Color(.8, .2, .25, 1), on_click=application.quit)

    def ayarlar_kur(self):
        self.ust_menu_yazi_olcegi = 1.0  

        f = self.ayar_menu = Entity(parent=camera.ui, enabled=False, z=-2)
        
        Entity(parent=f, model="quad", color=PANEL, scale=(.46, .55), position=(0, 0, 1))
        Entity(parent=f, model="quad", color=Color(.4, .8, 1, 1), scale=(.46, .008), position=(0, .271, .5))
        
        Yazi(parent=f, text="AYARLAR", position=(-.21, .23), scale=1.2, color=Color(.4, .8, 1, 1))
        
        self.sl_menu_yazi = Kaydirici(f, -.21, .13, .42, 0.4, 2.5, self.ust_menu_yazi_olcegi, 0.1, "Üst Menü Yazı Boyutu", "x", 1)
        self.sl_kamera = Kaydirici(f, -.21, .05, .42, 0.1, 5.0, self.kamera_hassasiyet, 0.1, "Kamera Hassasiyeti", "x", 1)
        
        Yazi(parent=f, text="SİMÜLASYON OLAYLARI", position=(-.21, -.06), scale=0.9, color=Color(1, .5, .2, 1))
        Dugme(parent=f, text="Göktaşı Yolla", position=(-.12, -.12), scale=(.18, .04),
               color=Color(.6, .3, .2, 1), on_click=self.goktasi_gonder)
        Dugme(parent=f, text="Kuyruklu Yıldız", position=(.12, -.12), scale=(.18, .04),
               color=Color(.2, .6, .8, 1), on_click=self.kuyruklu_yildiz_gonder)
        
        Dugme(parent=f, text="Uygula", position=(-.12, -.22), scale=(.18, .04),
               color=Color(.3, .6, .8, 1), on_click=self.ayarlar_uygula)
        Dugme(parent=f, text="İptal", position=(.12, -.22), scale=(.18, .04),
               color=Color(.5, .2, .25, 1), on_click=self.ayarlar_kapat)

    def goktasi_gonder(self):
        if not self.dunya_ref: return
        baslangic = self.dunya_ref.govde.world_position + Vec3(random.uniform(-1,1), random.uniform(-1,1), random.uniform(-1,1)).normalized() * 150
        e = Entity(model='sphere', color=Color(.4, .3, .3, 1), scale=1.5, position=baslangic)
        self.tehditler.append({'ent': e, 'hedef': self.dunya_ref, 'hiz': 20, 'fuze_kalkti': False, 'tip': 'Göktaşı'})
        self.ayarlar_kapat()

    def kuyruklu_yildiz_gonder(self):
        if not self.dunya_ref: return
        baslangic = self.dunya_ref.govde.world_position + Vec3(random.uniform(-1,1), random.uniform(-1,1), random.uniform(-1,1)).normalized() * 250
        e = Entity(model='sphere', color=Color(.7, .9, 1, 1), scale=(1.5, 1.5, 4), position=baslangic)
        self.tehditler.append({'ent': e, 'hedef': self.dunya_ref, 'hiz': 35, 'fuze_kalkti': False, 'tip': 'Kuyruklu Yıldız'})
        self.ayarlar_kapat()

    def form_kur(self):
        f = self.form = Entity(parent=camera.ui, enabled=False, z=-2)
        Entity(parent=f, model="quad", color=PANEL, scale=(.8, .86), position=(0, 0, 1))
        Entity(parent=f, model="quad", color=Color(1, .37, .63, 1), scale=(.8, .008), position=(0, .426, .5))
        
        Yazi(parent=f, text="GELİŞMİŞ GEZEGEN OLUŞTURUCU", position=(-.35, .40), scale=1.2, color=Color(1, .37, .63, 1))
        Yazi(parent=f, text="--- YENİ GEZEGEN BİLGİLERİ ---", position=(-.35, .32), scale=1.0, color=Color(1, .6, .8, 1))
        
        self.ad_giris = InputField(parent=f, default_value="Aether-7", position=(-.20, .245), scale=(.20, .036), character_limit=18)
        self.tur = dongu_dugme(f, "Tür: ", ["Kayalık", "Gaz devi", "Buz", "Lav"], -.25, .19, .20)
        self.renk = dongu_dugme(f, "Renk: ", list(RENKLER), -.25, .14, .20)
        self.halka = dongu_dugme(f, "Halka: ", ["Yok", "Var"], -.25, .09, .20)
        
        self.cap = Kaydirici(f, -.35, .02, .25, 1000, 150000, 12000, 100, "Çap", "km", 0)
        self.kutle = Kaydirici(f, -.35, -.05, .25, 0.1, 10.0, 1.2, 0.1, "Kütle (Dünya)", "x", 1)
        self.cekimi = Kaydirici(f, -.35, -.12, .25, 1, 30, 11, 1, "Yerçekimi", "m/s²", 0)

        self.yas = Kaydirici(f, .1, .24, .25, 0.1, 13.0, 4.5, 0.1, "Yaş", "Mlyr", 1)
        self.atm_var = dongu_dugme(f, "Atmosfer: ", ["Var", "Yok"], .225, .17, .20)
        self.sicak = Kaydirici(f, .1, .10, .25, -200, 500, 15, 1, "Ort. Sıcaklık", "°C", 0)
        self.ruzgar = Kaydirici(f, .1, .03, .25, 0, 500, 40, 1, "Rüzgar Hızı", "km/h", 0)
        self.yogunluk = Kaydirici(f, .1, -.04, .25, 0.5, 15.0, 5.5, 0.1, "Yoğunluk", "g/cm³", 1)
        
        Dugme(parent=f, text="Göktaşı Çarpışmasıyla Oluştur!", position=(-.15, -.25), scale=(.25, .05),
               color=Color(1, .5, .2, 1), on_click=self.olustur)
               
        Dugme(parent=f, text="Seçiliyi Sil", position=(.1, -.25), scale=(.12, .04),
               color=Color(.6, .2, .25, 1), on_click=self.sil)
               
        Dugme(parent=f, text="Kapat", position=(.25, -.25), scale=(.12, .04),
               color=Color(.2, .4, .6, 1), on_click=self.form_kapat)

    def hakkinda_kur(self):
        import hakkinda
        h = self.hak = Entity(parent=camera.ui, enabled=False)
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

    def form_ac(self):
        self.ayarlar_kapat()
        self.hakkinda_kapat()
        self.form.enabled = True
        Kaydirici.gorunur = True

    def form_kapat(self):
        self.form.enabled = False
        Kaydirici.gorunur = False
        Kaydirici.aktif = None

    def ayarlar_ac(self):
        self.form_kapat()
        self.hakkinda_kapat()
        self.ayar_menu.enabled = True
        Kaydirici.gorunur = True
        self.sl_menu_yazi.ata(self.ust_menu_yazi_olcegi)
        self.sl_kamera.ata(self.kamera_hassasiyet)

    def ayarlar_kapat(self):
        self.ayar_menu.enabled = False
        Kaydirici.gorunur = False
        Kaydirici.aktif = None
        
    def ayarlar_uygula(self):
        self.ust_menu_yazi_olcegi = self.sl_menu_yazi.deger
        self.kamera_hassasiyet = self.sl_kamera.deger
        self.butonlari_yenile()
        
        self.ayar_menu.enabled = False
        Kaydirici.gorunur = False
        Kaydirici.aktif = None
        
    def hakkinda_ac(self):
        self.form_kapat()
        self.ayarlar_kapat()
        self.kay_t = 0.0
        self.hak.enabled = True

    def hakkinda_kapat(self):
        self.hak.enabled = False

    def kayan_yazi(self, dt):
        self.kay_t += dt * .55
        toplam = len(self.kayan) + 3
        U, a = 7.0, 2.6
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
            s = 1 / (1 + a * u / U)
            t.position = (0, y_alt + (y_ust - y_alt) * (1 - s) / norm, -1.1)
            t.scale = olcek * s * YAZI_OLCEK
            alfa = min(1, u / .7) * min(1, (U - u) / 2.5)
            t.color = Color(rgb[0], rgb[1], rgb[2], max(0, alfa))

    def butonlari_yenile(self):
        for b in self.btn:
            destroy(b)
        self.btn = []

        def fare_durumu(buton, uzerinde_mi):
            try:
                if uzerinde_mi:
                    buton.color = buton.highlight_color
                else:
                    buton.color = buton.orijinal_renk
            except Exception:
                pass

        ad = [("Güneş Sistemi", None, "#ffd36b")] + [(g.v["ad"], g, g.v["renk"]) for g in self.gezegenler]
        n = len(ad) - 1
        bas_w, bosluk = .15, .008
        
        sol_x = -window.aspect_ratio / 2 + 0.02
        sag_x = window.aspect_ratio / 2
        kullanilabilir_genislik = (sag_x - 0.45) - sol_x 
        
        w = min(.12, (kullanilabilir_genislik - bas_w - bosluk * (n + 1)) / max(1, n))
        x = sol_x

        for i, (t, g, renk) in enumerate(ad):
            gw = bas_w if i == 0 else w
            secili = g is self.secili

            b = Dugme(parent=camera.ui, text=t, position=(x + gw / 2, .465), scale=(gw, .06),
                      color=hx(renk, 1, 1 if secili else .38), on_click=lambda g=g: self.sec(g))
            b.text_color = Color(.05, .05, .12, 1) if secili else YAZI
            
            b.text_entity.scale *= self.ust_menu_yazi_olcegi
            
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

    def sec(self, g):
        self.secili = g
        self.dist_h = self.dmax * 1.7 if g is None else max(g.r * 5, 2.5)
        self.butonlari_yenile()
        self.panel_yenile()
        if g is not None:
            self.canli()

    def olustur(self):
        ad = (self.ad_giris.text or "Aether-7").strip()[:18]
        tur = self.tur.secenekler[self.tur.sec]
        renk = RENKLER[list(RENKLER)[self.renk.sec]]
        halka = renk if self.halka.sec == 1 else None
        
        cap = float(self.cap.deger)
        kutle = float(self.kutle.deger)
        cekimi = float(self.cekimi.deger)
        yas = float(self.yas.deger)
        yogunluk = float(self.yogunluk.deger)
        
        atm_var = self.atm_var.secenekler[self.atm_var.sec] == "Var"
        sicak = float(self.sicak.deger)
        ruzgar = float(self.ruzgar.deger)

        bilgi_metni = (f"{ad}, oluşumundan bu yana {yas} milyar yıl geçmiş bir {tur.lower()}dir.\n"
                       f"Gezegenin toplam çapı {cap:,.0f} km olup, {yogunluk} g/cm³ yoğunluğa sahiptir. "
                       f"Kütlesi Dünya'nın tam {kutle} katı büyüklüğündedir ve yüzeyindeki çekim kuvveti {cekimi} m/s² olarak ölçülmüştür.\n")
        
        if atm_var:
            bilgi_metni += (f"Gezegeni saran güçlü bir atmosfer tabakası mevcuttur. Ortalama yüzey sıcaklığı {sicak}°C'dir. "
                            f"Gökyüzünde sürekli esen ve hızı {ruzgar} km/saati bulan şiddetli fırtınalar gözlemlenmektedir.")
        else:
            bilgi_metni += f"Gezegende herhangi bir atmosfer tabakası veya hava akımı (rüzgar) bulunmamaktadır. Yüzey sıcaklığı {sicak}°C'dir."
            
        v = dict(
            ad=ad, 
            renk=renk,
            yaricap_km=cap / 2, 
            au=self.dmax + 2.5, 
            periyot=(self.dmax + 2.5) * 200, 
            uydu=0, 
            sicak=sicak,
            basinc=1.0 if atm_var else 0.0, 
            ruzgar=ruzgar if atm_var else 0,
            atm_renk=renk, 
            atm_k=0.6 if atm_var else 0.0,
            gazlar=[("Oksijen", 21), ("Azot", 78), ("Diğer", 1)] if atm_var else [("Diğer", 100)], 
            halka=halka,
            doku="kaya" if tur in ["Kayalık", "Lav"] else "gaz", 
            bilgi=bilgi_metni
        )
        
        g = self.ekle(v, True)
        g.govde.scale = 0.0001
        
        self.sec(g)
        self.form_kapat()
        
        self.goktaslari = []
        for _ in range(45): 
            rastgele_konum = g.govde.world_position + Vec3(random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(-1, 1)).normalized() * random.uniform(8, 20)
            boyut = random.uniform(0.1, 0.4)
            meteor = Entity(model='sphere', color=Color(.4, .3, .3, 1), scale=boyut, position=rastgele_konum)
            self.goktaslari.append(meteor)
            
        self.olusum_hedef = g
        self.hedef_final_scale = g.r * 2 
        self.olusum_aktif = True

    def sil(self):
        g = self.secili
        if g is None or not g.ozel:
            return
            
        if g == self.dunya_ref:
            self.dunya_ref = None
            
        self.sec(None)
        destroy(self.etiketler.pop(g))
        g.sil()
        self.gezegenler.remove(g)
        self.kaydet()
        self.form_kapat()

    def ui_ustunde(self):
        he = mouse.hovered_entity
        return he is not None and he.has_ancestor(camera.ui)

    def input(self, key):
        if key == "scroll up":
            self.dist_h = max(2, self.dist_h * .88)
        elif key == "scroll down":
            self.dist_h = min(400, self.dist_h * 1.14)
        elif key in ("left mouse down", "right mouse down"):
            self.surukle = not self.ui_ustunde()
            self.bas = (mouse.x, mouse.y)
        elif key in ("left mouse up", "right mouse up"):
            self.surukle = False
            if key == "left mouse up" and self.bas and abs(mouse.x - self.bas[0]) + abs(mouse.y - self.bas[1]) < .012:
                for g in self.gezegenler:
                    if mouse.hovered_entity is g.govde:
                        self.sec(g)
                        break
        elif key == "escape":
            if self.hak.enabled:
                self.hakkinda_kapat()
            elif self.ayar_menu.enabled:
                self.ayarlar_kapat()
            elif self.form.enabled:
                self.form_kapat()
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
            
            satir = sum(max(1, math.ceil(len(p) / 45)) for p in aciklama.split("\n"))
            self.p_stat.position = (self.PX, max(-.35, .35 - satir * .035 - .02)) 
            self.p_stat.text = "\n".join(f"{b}: {d}" for b, d in maddeler) or " "
            self.p_atm.enabled = False
            self.canli_grup.enabled = False
            return
            
        v = g.v
        self.p_serit.color = hx(v["renk"])
        self.p_ad.text, self.p_ad.color = v["ad"], hx(v["renk"], 1, 1.15)
        self.p_bilgi.text = v["bilgi"]
        
        satir = sum(max(1, math.ceil(len(p) / 45)) for p in v["bilgi"].split("\n"))
        self.p_stat.position = (self.PX, max(-.15, .35 - satir * .035 - .02))
        
        km = f"{v['yaricap_km']:,.0f}".replace(",", " ")
        self.p_stat.text = (f"Yarıçap: {km} km\nGüneş’e uzaklık: {v['au']} AU\n"
                            f"Yörünge periyodu: {v['periyot']} gün\nBilinen uydu: {v['uydu']}")
                            
        self.p_atm.enabled = True
        self.p_atm.color = hx(v["renk"], 1, 1.15)
        self.canli_grup.enabled = True
        
        top = sum(y for _, y in v["gazlar"])
        x = self.PX
        for i, (a, y) in enumerate(v["gazlar"]):
            c = hx(GAZ_RENK.get(a, PALET[i % len(PALET)]))
            w = y / top * .44
            self.dyn.append(Entity(parent=camera.ui, model="quad", color=c, scale=(w, .018),
                                   origin=(-.5, 0), position=(x, -.01, -.01)))
            x += w
            lx, ly = self.PX + (i % 2) * .22, -.04 - (i // 2) * .035
            self.dyn.append(Entity(parent=camera.ui, model="quad", color=c, scale=(.012, .012),
                                   position=(lx + .006, ly - .011, -.01)))
            self.dyn.append(Yazi(parent=camera.ui, text=f"{a} %{y / top * 100:.1f}",
                                 position=(lx + .02, ly), scale=.8, color=YAZI))

    def canli(self):
        g = self.secili
        g.canli_guncelle()
        for L, (t, e, y), (ad, _, birim, _, renk) in zip(g.canli, self.satirlar, CANLI):
            t.text = f"{ad}: {bicim(L['v'])} {birim}"
            h = L["h"]
            lo, hi = min(h), max(h)
            r = (hi - lo) or 1
            e.model = Mesh(vertices=[Vec3(self.PX + i / 39 * .44, y - .11 + (v - lo) / r * .05, -.02)
                                     for i, v in enumerate(h)], mode="line", thickness=2)

    # ================= her kare =================
    def kamera(self, dt):
        if self.surukle and Kaydirici.aktif is None and (held_keys["left mouse"] or held_keys["right mouse"]):
            self.yaw += mouse.velocity[0] * 120 * self.kamera_hassasiyet
            self.pitch = max(-85, min(85, self.pitch - mouse.velocity[1] * 100 * self.kamera_hassasiyet))
        hedef = Vec3(*self.secili.govde.position) if self.secili else Vec3(0, 0, 0)
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
        
        if self.olusum_aktif:
            merkez_hedef = self.olusum_hedef.govde.world_position
            animasyon_bitti = True
            
            for m in self.goktaslari:
                if m.enabled:
                    animasyon_bitti = False
                    yon = merkez_hedef - m.world_position
                    mesafe = yon.length()
                    
                    if mesafe < 0.6:  
                        m.enabled = False
                        artis = self.hedef_final_scale / len(self.goktaslari)
                        self.olusum_hedef.govde.scale += Vec3(artis, artis, artis)
                    else:
                        m.world_position += yon.normalized() * mesafe * dt * 10 
            
            if animasyon_bitti:
                self.olusum_aktif = False
                self.olusum_hedef.govde.scale = Vec3(self.hedef_final_scale, self.hedef_final_scale, self.hedef_final_scale)
                self.kaydet()
                self.butonlari_yenile()

        alarm_durumu = False
        
        for t in self.tehditler[:]:
            t_ent = t['ent']
            hedef_pos = t['hedef'].govde.world_position
            yon = (hedef_pos - t_ent.world_position)
            mesafe = yon.length()

            if t['tip'] == 'Kuyruklu Yıldız':
                t_ent.look_at(t['hedef'].govde)

            if mesafe > 0:
                t_ent.world_position += yon.normalized() * t['hiz'] * dt

            if mesafe < 80:
                alarm_durumu = True
                if not t['fuze_kalkti']:
                    t['fuze_kalkti'] = True
                    f_ent = Entity(model='cube', color=Color(1, .2, .1, 1), scale=(0.3, 0.3, 1.5), position=hedef_pos)
                    self.fuzeler.append({'ent': f_ent, 'hedef_tehdit': t, 'hiz': 55})
                    self.fuze_sesi_cal()

            if mesafe < t['hedef'].r + 0.5:
                destroy(t_ent)
                self.tehditler.remove(t)

        for f in self.fuzeler[:]:
            f_ent = f['ent']
            t = f['hedef_tehdit']
            t_ent = t['ent']

            if t not in self.tehditler:
                destroy(f_ent)
                self.fuzeler.remove(f)
                continue

            yon = (t_ent.world_position - f_ent.world_position)
            f_ent.look_at(t_ent)
            mesafe = yon.length()

            if mesafe > 0:
                f_ent.world_position += yon.normalized() * f['hiz'] * dt

            if mesafe < 2.0:
                self.patlama_sesi_cal()
                p_ent = Entity(model='sphere', color=Color(1, .6, .1, 0.8), scale=1, position=t_ent.world_position)
                self.patlamalar.append({'ent': p_ent, 'omur': 1.0, 'maks_omur': 1.0})
                
                destroy(t_ent)
                destroy(f_ent)
                if t in self.tehditler: self.tehditler.remove(t)
                if f in self.fuzeler: self.fuzeler.remove(f)

        for p in self.patlamalar[:]:
            p['omur'] -= dt
            if p['omur'] <= 0:
                destroy(p['ent'])
                self.patlamalar.remove(p)
            else:
                p['ent'].scale += Vec3(dt*20, dt*20, dt*20)
                p['ent'].color = Color(1, 0.6, 0.1, p['omur']/p['maks_omur'])

        if alarm_durumu:
            self.alarm_yazi.enabled = True
            self.alarm_yazi.color = Color(1, 0, 0, 1 if (int(time.time() * 6) % 2 == 0) else 0)
            if self.siren_sesi and not self.siren_caliyor:
                self.siren_sesi.play()
                self.siren_caliyor = True
        else:
            self.alarm_yazi.enabled = False
            if self.siren_sesi and self.siren_caliyor:
                self.siren_sesi.stop()
                self.siren_caliyor = False
        
        for g, t in self.etiketler.items():
            p = g.govde.position
            if (Vec3(*p) - camera.world_position).dot(camera.forward) > 0:
                sp = g.govde.screen_position
                y_offset = 0.05 + (g.r * 0.015)
                t.position = (sp[0], sp[1] + y_offset)
                t.enabled = True
            else:
                t.enabled = False

        if self.hak.enabled:
            self.kayan_yazi(dt)
        self.canli_t += dt
        if self.canli_t > .5 and self.secili is not None:
            self.canli_t = 0
            self.canli()


if __name__ == "__main__":
    from panda3d.core import loadPrcFileData
    loadPrcFileData("", "framebuffer-multisample 1\nmultisamples 4")
    
    app = Ursina(title="Samanyolu 3B Gezegen Laboratuvarı", borderless=False, fullscreen=True)
    
    try:
        from panda3d.core import AntialiasAttrib
        application.base.render.setAntialias(AntialiasAttrib.MAuto)
    except Exception:
        pass
    print("Gezegenler hazırlanıyor, birkaç saniye sürebilir...")
    uygulama = Uygulama()
    Acilis(uygulama)          
    app.run()