"""
Samanyolu 3B Gezegen Laboratuvarı (masaüstü programı, Python + Ursina)

Kurulum:    pip install ursina        (Windows'ta calistir.bat bunu kendisi yapar)
Çalıştırma: python main.py

Fare: basılı tutup sürükle = döndür, tekerlek = yakınlaştır, gezegene tıkla = seç, sağ tık = menü.
"""
import json
import math
import os
import time
import random

from PIL import Image, ImageDraw
from ursina import (Button, Entity, Mesh, Texture, Text, Ursina, Vec3, application, camera, destroy,
                    held_keys, mouse, window, scene)
from ursina.color import Color
from ursina.prefabs.input_field import InputField

import bilgiler
import dokular
import gezegenler
import ses
from acilis import Acilis
from arayuz import YAZI_OLCEK, Dugme, Kaydirici, Yazi, dongu_dugme
from sahne import CANLI, Gezegen3B, hx, sahne_kur


def lerp(a, b, t):
    return a + (b - a) * t


def turk_bayragi_doku():
    """Стандартты пропорцияларда қызыл фонда ақ ай мен жұлдызы бар Түркия туының текстурасын жасаңыз. 
       Оғызхан ұстазым, егер басқа бір нәрсе керек болса, оны да қарастырамыз. Түркияға сәлем!"""
    W, H = 512, 340
    img = Image.new("RGBA", (W, H), (227, 10, 23, 255))
    d = ImageDraw.Draw(img)

    cx1, cy1, r1 = int(W * 0.36), int(H * 0.5), int(H * 0.25)
    d.ellipse((cx1 - r1, cy1 - r1, cx1 + r1, cy1 + r1), fill=(255, 255, 255, 255))

    cx2, cy2, r2 = int(W * 0.415), int(H * 0.5), int(H * 0.20)
    d.ellipse((cx2 - r2, cy2 - r2, cx2 + r2, cy2 + r2), fill=(227, 10, 23, 255))

    sx, sy = W * 0.585, H * 0.5
    sr_dis = H * 0.125
    sr_ic = sr_dis * 0.382
    noktalar = []
    baslangic_aci = math.radians(180)
    for i in range(10):
        aci = baslangic_aci + i * math.pi / 5.0
        r = sr_dis if i % 2 == 0 else sr_ic
        noktalar.append((sx + math.cos(aci) * r, sy + math.sin(aci) * r))
    d.polygon(noktalar, fill=(255, 255, 255, 255))
    return Texture(img)


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

YERCEKIMI_TABLOSU = {
    "Merkür": 3.7,
    "Venüs": 8.87,
    "Dünya": 9.81,
    "Mars": 3.71,
    "Jüpiter": 24.79,
    "Satürn": 10.44,
    "Uranüs": 8.69,
    "Neptün": 11.15,
    "Ay": 1.62
}


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
        camera.clip_plane_far = 5000
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
        self.goktaslari = []

        # kamera durumu
        self.yaw, self.pitch, self.dist = 25, 35, 100
        self.dist_h = self.dist
        self.hedef = Vec3(0, 0, 0)
        self.surukle, self.bas = False, None
        self.olusum_aktif = False
        self.kamera_hassasiyet = 1.0

        # --- YÜZEY, BAYRAK VE NUMUNE SİMÜLASYONU DEĞİŞKENLERİ ---
        self.yuzey_modu = False
        self.gecis_aktif = False
        self.gecis_t = 0.0
        self.hedef_yuzey_gezegen = None
        self.gecis_bas_pos = Vec3(0, 0, 0)

        self.yuzey_merkez = Vec3(0, -2000, 0)
        self.yuzey_kok = None
        self.astronot = None
        self.sol_kol = None
        self.sag_kol = None
        self.sol_bacak = None
        self.sag_bacak = None
        self.ates_listesi = []
        self.numune_nesneleri = []
        self.dikilen_bayraklar = []
        self.envanter = {"Kaya": 0, "Buz": 0, "Lav": 0}
        self.bayrak_sayisi = 0
        self.bayrak_dokusu = turk_bayragi_doku()

        self.astronot_vy = 0.0
        self.yerde_mi = True
        self.yurume_zamani = 0.0
        self.yuzey_yaw = 0.0
        self.yuzey_pitch = 20.0
        self.yuzey_dist = 8.0

        # Atmosfer geçiş perdesi
        self.gecis_perde = Entity(parent=camera.ui, model="quad", scale=(4, 2),
                                  color=Color(0, 0, 0, 0), z=-5, enabled=False)

        # Sağ Tık Menüsü
        self.sag_tik_gezegen = None
        self.sag_tik_menu = Entity(parent=camera.ui, enabled=False, z=-3)
        Entity(parent=self.sag_tik_menu, model="quad", color=PANEL, scale=(.24, .13), position=(0, 0, 1))
        Entity(parent=self.sag_tik_menu, model="quad", color=Color(1, .37, .63, 1), scale=(.24, .006), position=(0, .062, .5))
        self.st_baslik = Yazi(parent=self.sag_tik_menu, text="Gezegen", position=(-.10, .035), scale=0.95, color=Color(1, .83, .42, 1))
        Dugme(parent=self.sag_tik_menu, text="Gezegende Gez", position=(0, -.02), scale=(.20, .04),
              color=Color(1, .37, .63, 1), on_click=self.yuzey_modunu_baslat)

        # Dünya Uyarı Penceresi
        self.dunya_uyari = Entity(parent=camera.ui, enabled=False, z=-4)
        Entity(parent=self.dunya_uyari, model="quad", color=PANEL, scale=(.56, .26), position=(0, 0, 1))
        Entity(parent=self.dunya_uyari, model="quad", color=Color(1, .83, .42, 1), scale=(.56, .008), position=(0, .126, .5))
        Yazi(parent=self.dunya_uyari, text="SİMÜLASYON UYARISI", origin=(0, 0), position=(0, .08), scale=1.2, color=Color(1, .83, .42, 1))
        Yazi(parent=self.dunya_uyari, text="Zaten Dünya'dasın!\nGezinti yapmak istiyorsan evden çık gez :)",
             origin=(0, 0), position=(0, .01), scale=1.0, color=YAZI)
        Dugme(parent=self.dunya_uyari, text="Tamam, Haklısın", position=(0, -.08), scale=(.22, .045),
              color=Color(.25, .6, .4, 1), on_click=lambda: setattr(self.dunya_uyari, 'enabled', False))

        # Yüzey HUD Paneli (Sol üst köşe)
        sol_ust_x = -window.aspect_ratio / 2 + 0.24
        self.yuzey_hud = Entity(parent=camera.ui, enabled=False, z=-2)
        Entity(parent=self.yuzey_hud, model="quad", color=PANEL, scale=(.44, .48), position=(sol_ust_x, .21, 1))
        Entity(parent=self.yuzey_hud, model="quad", color=Color(1, .83, .42, 1), scale=(.44, .008), position=(sol_ust_x, .446, .5))
        self.yh_baslik = Yazi(parent=self.yuzey_hud, text="YÜZEY KEŞİF MODU", position=(sol_ust_x - .20, .42), scale=1.05, color=Color(1, .83, .42, 1))
        self.yh_bilgi = Yazi(parent=self.yuzey_hud, text=" ", position=(sol_ust_x - .20, .37), scale=0.78, color=YAZI)
        self.yh_bilgi.wordwrap = 42
        self.yh_envanter = Yazi(parent=self.yuzey_hud, text=" ", position=(sol_ust_x - .20, .17), scale=0.82, color=Color(.5, .95, .65, 1))
        self.yh_ipucu = Yazi(parent=self.yuzey_hud, text=" ", origin=(0, 0), position=(0, -.38), scale=1.15, color=Color(1, .9, .4, 1))

        # Yüzey Etkileşim Düğmeleri
        Dugme(parent=self.yuzey_hud, text="Türk Bayrağı Dik (F)", position=(sol_ust_x - .105, .055), scale=(.20, .038),
              color=Color(.85, .12, .18, 1), on_click=self.bayrak_dik)
        Dugme(parent=self.yuzey_hud, text="Numune Topla (E)", position=(sol_ust_x + .105, .055), scale=(.20, .038),
              color=Color(.2, .6, .45, 1), on_click=self.numune_topla)
        Dugme(parent=self.yuzey_hud, text="Yörüngeye Dön (ESC)", position=(sol_ust_x, .002), scale=(.41, .038),
              color=Color(.3, .35, .6, 1), on_click=self.yuzey_modundan_cik)

        # --- TEHDİT VE SAVUNMA SİSTEMİ ---
        self.dunya_ref = next((g for g in self.gezegenler if g.v["ad"] == "Dünya"), None)
        self.tehditler = []
        self.fuzeler = []
        self.patlamalar = []

        self.alarm_yazi = Yazi(parent=camera.ui, text="!! TEHLİKE: DÜNYA'YA CİSİM YAKLAŞIYOR !!",
                               position=(0, .40), scale=1.5, color=Color(1, 0, 0, 1), origin=(0, 0))
        self.alarm_yazi.enabled = False

        try:
            from panda3d.core import Filename
            siren_mp3_yol = os.path.join(os.path.dirname(os.path.abspath(__file__)), "siren.mp3")
            siren_wav_yol = os.path.join(os.path.dirname(os.path.abspath(__file__)), "siren.wav")
            if os.path.exists(siren_mp3_yol):
                self.siren_sesi = application.base.loader.loadSfx(Filename.fromOsSpecific(siren_mp3_yol))
            elif os.path.exists(siren_wav_yol):
                self.siren_sesi = application.base.loader.loadSfx(Filename.fromOsSpecific(siren_wav_yol))
            else:
                self.siren_sesi = application.base.loader.loadSfx(Filename.fromOsSpecific(ses.patlama_yolu()))
                self.siren_sesi.setPlayRate(4.0)
            self.siren_sesi.setLoop(True)
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

    def etkilesim_sesi_cal(self, hiz=2.2):
        try:
            from panda3d.core import Filename
            yol = ses.patlama_yolu()
            efekt = application.base.loader.loadSfx(Filename.fromOsSpecific(yol))
            efekt.setPlayRate(hiz)
            efekt.setVolume(0.35)
            efekt.play()
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
        self.sag_panel_grup = Entity(parent=camera.ui)
        ui = self.sag_panel_grup
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
        self.alt_cubuk_grup = Entity(parent=camera.ui)
        ui = self.alt_cubuk_grup
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

        Yazi(parent=ui, text="Sürükle: döndür | Sağ Tık: Gezegende Gez | Tekerlek: Yakınlaştır",
             position=(sol_x + .53, -.452), scale=1.0, color=SOLUK)

        sag_x = window.aspect_ratio / 2
        Dugme(parent=camera.ui, text="Ayarlar", position=(sag_x - 0.34, .465), scale=(.12, .04),
              color=Color(.2, .5, .7, 1), on_click=self.ayarlar_ac)
        Dugme(parent=camera.ui, text="Hakkında", position=(sag_x - 0.21, .465), scale=(.12, .04),
              color=Color(1, .37, .63, 1), on_click=self.hakkinda_ac)
        Dugme(parent=camera.ui, text="Çıkış", position=(sag_x - 0.08, .465), scale=(.12, .04),
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
        if not self.dunya_ref:
            return
        baslangic = self.dunya_ref.govde.world_position + Vec3(random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(-1, 1)).normalized() * 150
        e = Entity(model='sphere', color=Color(.4, .3, .3, 1), scale=1.5, position=baslangic)
        self.tehditler.append({'ent': e, 'hedef': self.dunya_ref, 'hiz': 20, 'fuze_kalkti': False, 'tip': 'Göktaşı'})
        self.ayarlar_kapat()

    def kuyruklu_yildiz_gonder(self):
        if not self.dunya_ref:
            return
        baslangic = self.dunya_ref.govde.world_position + Vec3(random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(-1, 1)).normalized() * 250
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
            b.enabled = not (self.yuzey_modu or self.gecis_aktif)
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

    # ================= YÜZEY, TÜRK BAYRAĞI DİKME VE NUMUNE TOPLAMA =================
    def yuzey_hud_guncelle(self):
        self.yh_envanter.text = (
            f"Dikilen Türk Bayrağı: {self.bayrak_sayisi}\n"
            f"Toplanan Numuneler: Kaya ({self.envanter['Kaya']}) | "
            f"Buz ({self.envanter['Buz']}) | Lav ({self.envanter['Lav']})"
        )

    def bayrak_dik(self):
        if not self.yuzey_modu or not self.astronot:
            return
        aci = math.radians(self.astronot.rotation_y)
        ileri = Vec3(math.sin(aci), 0, math.cos(aci))
        konum = self.astronot.position + ileri * 1.6
        konum.y = 0.0

        kok = Entity(parent=self.yuzey_kok, position=konum, rotation_y=self.astronot.rotation_y)
        Entity(parent=kok, model="sphere", color=Color(0.55, 0.58, 0.62, 1),
               scale=(0.55, 0.2, 0.55), position=(0, 0.08, 0), unlit=True)
        Entity(parent=kok, model="cube", color=Color(0.88, 0.9, 0.94, 1),
               scale=(0.07, 3.4, 0.07), position=(0, 1.7, 0), unlit=True)
        Entity(parent=kok, model="sphere", color=Color(1.0, 0.84, 0.2, 1),
               scale=(0.18, 0.18, 0.18), position=(0, 3.45, 0), unlit=True)
        kumas = Entity(
            parent=kok,
            model="quad",
            texture=self.bayrak_dokusu,
            scale=(1.65, 1.1),
            position=(0.85, 2.8, 0),
            double_sided=True,
            unlit=True
        )
        self.dikilen_bayraklar.append((kumas, random.uniform(0, 6.28)))
        self.bayrak_sayisi += 1
        self.etkilesim_sesi_cal(1.8)
        self.yuzey_hud_guncelle()
        self.yh_ipucu.text = "Türk Bayrağı yüzeye dikildi!"

    def en_yakin_numune(self):
        if not self.astronot:
            return None, 999.0
        en_yakin = None
        en_kisa = 999.0
        apos = self.astronot.position
        for item in self.numune_nesneleri:
            if item["toplanmis"]:
                continue
            d = (item["pos"] - apos).length()
            if d < en_kisa:
                en_kisa = d
                en_yakin = item
        return en_yakin, en_kisa

    def numune_topla(self):
        if not self.yuzey_modu or not self.astronot:
            return
        hedef, mesafe = self.en_yakin_numune()
        if hedef is not None and mesafe <= 5.0:
            hedef["toplanmis"] = True
            for e in hedef["parcalar"]:
                if e in self.ates_listesi:
                    self.ates_listesi.remove(e)
                destroy(e)
            tur = hedef["tur"]
            self.envanter[tur] = self.envanter.get(tur, 0) + 1
            self.etkilesim_sesi_cal(2.6)
            self.yuzey_hud_guncelle()
            self.yh_ipucu.text = f"+1 {tur} numunesi envantere eklendi!"
        else:
            self.yh_ipucu.text = "Yakında toplanabilir numune yok! Bir kaya, buz veya lava yaklaşın."

    def yuzey_modunu_baslat(self):
        self.sag_tik_menu.enabled = False
        g = self.sag_tik_gezegen
        if not g:
            return

        if g.v["ad"] == "Dünya":
            self.dunya_uyari.enabled = True
            return

        self.sec(g)
        self.hedef_yuzey_gezegen = g
        self.gecis_bas_pos = Vec3(camera.position)
        self.gecis_aktif = True
        self.gecis_t = 0.0
        self.gecis_perde.enabled = True
        self.gecis_perde.color = Color(0, 0, 0, 0)

        for b in self.btn:
            b.enabled = False
        self.sag_panel_grup.enabled = False
        self.alt_cubuk_grup.enabled = False
        for e in self.dyn:
            e.enabled = False

    def yuzey_modunu_aktiflestir(self):
        self.yuzey_modu = True
        g = self.hedef_yuzey_gezegen
        v = g.v

        if self.yuzey_kok:
            destroy(self.yuzey_kok)
        self.yuzey_kok = Entity(position=self.yuzey_merkez)
        self.ates_listesi = []
        self.numune_nesneleri = []
        self.dikilen_bayraklar = []
        self.envanter = {"Kaya": 0, "Buz": 0, "Lav": 0}
        self.bayrak_sayisi = 0

        R = random.Random(sum(map(ord, v["ad"])) * 997)
        ana_rgb = dokular.hex_rgb(v["renk"])
        pal = (dokular.ton(ana_rgb, 0.45), ana_rgb, dokular.ton(ana_rgb, 1.35))
        dokular.boyut(512)
        zemin_img, _ = dokular.kaya(R, pal, krater=45, kutup=False)
        zemin_tex = Texture(zemin_img)

        self.yuzey_zemin = Entity(
            parent=self.yuzey_kok,
            model="plane",
            scale=(300, 1, 300),
            texture=zemin_tex,
            texture_scale=(12, 12),
            unlit=True,
            position=(0, 0, 0)
        )

        atm_renk = hx(v.get("atm_renk", v["renk"]), 0.35, 0.5)
        Entity(
            parent=self.yuzey_kok,
            model="sphere",
            scale=(280, 140, 280),
            color=atm_renk,
            double_sided=True,
            unlit=True,
            position=(0, -10, 0)
        )

        sicaklik = v.get("sicak", 15)
        tur_bilgi = v.get("bilgi", "").lower()

        kaya_renk_1 = hx(v["renk"], 1.0, 0.55)
        kaya_renk_2 = hx(v["renk"], 1.0, 0.38)

        for _ in range(95):
            rx = R.uniform(-110, 110)
            rz = R.uniform(-110, 110)
            if abs(rx) < 6 and abs(rz) < 6:
                continue

            if sicaklik >= 60 or "lav" in tur_bilgi or v["ad"] in ("Merkür", "Venüs"):
                secim = R.choice(["kaya", "kaya", "ates", "lav"])
            elif sicaklik <= -20 or "buz" in tur_bilgi or v["ad"] in ("Mars", "Uranüs", "Neptün", "Satürn", "Jüpiter"):
                secim = R.choice(["kaya", "buz", "buz"])
            else:
                secim = R.choice(["kaya", "kaya", "buz" if sicaklik < 5 else "kaya"])

            if secim == "kaya":
                bx = R.uniform(1.2, 4.2)
                by = R.uniform(0.8, 2.8)
                bz = R.uniform(1.2, 4.2)
                ent = Entity(
                    parent=self.yuzey_kok,
                    model="sphere",
                    color=R.choice([kaya_renk_1, kaya_renk_2]),
                    scale=(bx, by, bz),
                    position=(rx, by * 0.35, rz),
                    rotation=(R.uniform(0, 25), R.uniform(0, 360), R.uniform(0, 25)),
                    unlit=True
                )
                self.numune_nesneleri.append({
                    "tur": "Kaya",
                    "pos": Vec3(rx, 0, rz),
                    "parcalar": [ent],
                    "toplanmis": False
                })
            elif secim in ("ates", "lav"):
                cap = R.uniform(1.5, 3.8)
                parcalar = []
                havuz = Entity(
                    parent=self.yuzey_kok,
                    model="sphere",
                    color=Color(1.0, 0.25, 0.0, 1),
                    scale=(cap, 0.25, cap),
                    position=(rx, 0.08, rz),
                    unlit=True
                )
                parcalar.append(havuz)
                for _ in range(3):
                    yuk = R.uniform(1.4, 3.2)
                    alev = Entity(
                        parent=self.yuzey_kok,
                        model="cube",
                        color=Color(1.0, R.uniform(0.45, 0.85), 0.05, 0.95),
                        scale=(cap * 0.28, yuk, cap * 0.28),
                        position=(rx + R.uniform(-0.3, 0.3), yuk * 0.5, rz + R.uniform(-0.3, 0.3)),
                        rotation=(0, R.uniform(0, 90), 0),
                        unlit=True
                    )
                    parcalar.append(alev)
                    self.ates_listesi.append((alev, yuk, R.uniform(0, 6.28)))
                self.numune_nesneleri.append({
                    "tur": "Lav",
                    "pos": Vec3(rx, 0, rz),
                    "parcalar": parcalar,
                    "toplanmis": False
                })
            elif secim == "buz":
                gen = R.uniform(0.8, 2.2)
                yuk = R.uniform(2.2, 6.0)
                ent = Entity(
                    parent=self.yuzey_kok,
                    model="cube",
                    color=Color(0.65, 0.92, 1.0, 0.92),
                    scale=(gen, yuk, gen),
                    position=(rx, yuk * 0.45, rz),
                    rotation=(R.uniform(-12, 12), R.uniform(0, 180), R.uniform(-12, 12)),
                    unlit=True
                )
                self.numune_nesneleri.append({
                    "tur": "Buz",
                    "pos": Vec3(rx, 0, rz),
                    "parcalar": [ent],
                    "toplanmis": False
                })

        # Eklemli Astronot Modeli ve Sırt Çantasında "BOĞAZLIYAN M.Y.O." Yazısı
        self.astronot = Entity(parent=self.yuzey_kok, position=(0, 0, 0))
        # Gövde
        Entity(parent=self.astronot, model="cube", color=Color(0.95, 0.95, 0.98, 1),
               scale=(0.75, 1.0, 0.45), position=(0, 1.25, 0), unlit=True)
        # Turuncu Göğüs Şeridi
        Entity(parent=self.astronot, model="cube", color=Color(1.0, 0.45, 0.1, 1),
               scale=(0.77, 0.25, 0.47), position=(0, 1.4, 0), unlit=True)
        # Sırt Çantası (Yaşam Destek Ünitesi)
        Entity(parent=self.astronot, model="cube", color=Color(0.75, 0.78, 0.82, 1),
               scale=(0.55, 0.75, 0.32), position=(0, 1.3, -0.32), unlit=True)
        # Sırttaki Çantanın Arkasına Okul Yazısı (Text bileşeni)
        Text(parent=self.astronot, text="BOĞAZLIYAN M.Y.O.", origin=(0, 0),
             position=(0, 1.38, -0.49), rotation=(0, 180, 0), scale=2.5, color=Color(1, 0.85, 0.2, 1))

        # Kask ve Altın/Mavi Vizör
        Entity(parent=self.astronot, model="sphere", color=Color(0.98, 0.98, 1.0, 1),
               scale=(0.68, 0.68, 0.68), position=(0, 2.05, 0), unlit=True)
        Entity(parent=self.astronot, model="sphere", color=Color(0.1, 0.75, 0.95, 1),
               scale=(0.52, 0.42, 0.45), position=(0, 2.05, 0.18), unlit=True)

        # Kollar ve Bacaklar
        self.sol_kol = Entity(parent=self.astronot, model="cube", color=Color(0.9, 0.9, 0.95, 1),
                              scale=(0.24, 0.8, 0.24), position=(-0.52, 1.2, 0), unlit=True)
        self.sag_kol = Entity(parent=self.astronot, model="cube", color=Color(0.9, 0.9, 0.95, 1),
                              scale=(0.24, 0.8, 0.24), position=(0.52, 1.2, 0), unlit=True)
        self.sol_bacak = Entity(parent=self.astronot, model="cube", color=Color(0.85, 0.85, 0.9, 1),
                                scale=(0.28, 0.75, 0.28), position=(-0.22, 0.38, 0), unlit=True)
        self.sag_bacak = Entity(parent=self.astronot, model="cube", color=Color(0.85, 0.85, 0.9, 1),
                                scale=(0.28, 0.75, 0.28), position=(0.22, 0.38, 0), unlit=True)

        self.astronot_vy = 0.0
        self.yerde_mi = True
        self.yuzey_yaw = 0.0
        self.yuzey_pitch = 20.0
        self.yuzey_dist = 8.0

        cekimi = v.get("cekimi", YERCEKIMI_TABLOSU.get(v["ad"], 9.81))
        ruzgar = v.get("ruzgar", 10)
        basinc = v.get("basinc", 1.0)
        self.yh_baslik.text = f"YÜZEY KEŞFİ: {v['ad'].upper()}"
        self.yh_bilgi.text = (
            f"Sıcaklık: {sicaklik} °C | Yerçekimi: {cekimi:.2f} m/s²\n"
            f"Rüzgar: {ruzgar} km/s | Basınç: {basinc} bar\n"
            f"Yürüme: WASD / Yön | Zıplama: Space\n"
            f"Türk Bayrağı Dik: F | Numune Topla: E"
        )
        self.yuzey_hud_guncelle()
        self.yh_ipucu.text = "Keşfe başlamak için yürüyün, F ile Türk Bayrağı dikin."
        self.yuzey_hud.enabled = True

    def yuzey_modundan_cik(self):
        self.yuzey_modu = False
        self.gecis_aktif = False
        self.gecis_perde.enabled = False
        self.yuzey_hud.enabled = False
        if self.yuzey_kok:
            destroy(self.yuzey_kok)
            self.yuzey_kok = None
        self.ates_listesi.clear()
        self.numune_nesneleri.clear()
        self.dikilen_bayraklar.clear()

        self.sag_panel_grup.enabled = True
        self.alt_cubuk_grup.enabled = True
        for b in self.btn:
            b.enabled = True
        self.sec(self.hedef_yuzey_gezegen)

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
                       f"Çapı {cap:,.0f} km, yoğunluğu {yogunluk} g/cm³ ve kütlesi Dünya'nın {kutle} katıdır. "
                       f"Yerçekimi kuvveti {cekimi} m/s²'dir.")

        v = dict(
            ad=ad, renk=renk, yaricap_km=cap / 2, au=self.dmax + 2.5,
            periyot=(self.dmax + 2.5) * 200, uydu=0, sicak=sicak,
            basinc=1.0 if atm_var else 0.0, ruzgar=ruzgar if atm_var else 0,
            atm_renk=renk, atm_k=0.6 if atm_var else 0.0,
            gazlar=[("Oksijen", 21), ("Azot", 78), ("Diğer", 1)] if atm_var else [("Diğer", 100)],
            halka=halka, doku="kaya" if tur in ["Kayalık", "Lav"] else "gaz",
            bilgi=bilgi_metni, cekimi=cekimi
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
        if self.yuzey_modu:
            if key == "escape":
                self.yuzey_modundan_cik()
            elif key == "f":
                self.bayrak_dik()
            elif key == "e":
                self.numune_topla()
            elif key == "scroll up":
                self.yuzey_dist = max(3.5, self.yuzey_dist * 0.9)
            elif key == "scroll down":
                self.yuzey_dist = min(22.0, self.yuzey_dist * 1.1)
            elif key == "space" and self.yerde_mi:
                v = self.hedef_yuzey_gezegen.v
                cekim = v.get("cekimi", YERCEKIMI_TABLOSU.get(v["ad"], 9.81))
                oran = max(0.25, cekim / 9.81)
                self.astronot_vy = 7.5 / math.sqrt(oran)
                self.yerde_mi = False
            return

        if key == "scroll up":
            self.dist_h = max(2, self.dist_h * .88)
        elif key == "scroll down":
            self.dist_h = min(400, self.dist_h * 1.14)
        elif key == "left mouse down":
            if not self.ui_ustunde():
                self.sag_tik_menu.enabled = False
                self.dunya_uyari.enabled = False
            self.surukle = not self.ui_ustunde()
            self.bas = (mouse.x, mouse.y)
        elif key == "right mouse down":
            self.surukle = not self.ui_ustunde()
            self.bas = (mouse.x, mouse.y)
            if not self.ui_ustunde():
                self.dunya_uyari.enabled = False
                hedef_g = None
                for g in self.gezegenler:
                    if mouse.hovered_entity in (g.govde, g.bulut, g.atm):
                        hedef_g = g
                        break
                if hedef_g is not None:
                    self.sag_tik_gezegen = hedef_g
                    self.st_baslik.text = hedef_g.v["ad"]
                    self.sag_tik_menu.position = (mouse.x, mouse.y)
                    self.sag_tik_menu.enabled = True
                else:
                    self.sag_tik_menu.enabled = False
        elif key in ("left mouse up", "right mouse up"):
            self.surukle = False
            if key == "left mouse up" and self.bas and abs(mouse.x - self.bas[0]) + abs(mouse.y - self.bas[1]) < .012:
                for g in self.gezegenler:
                    if mouse.hovered_entity in (g.govde, g.bulut, g.atm):
                        self.sec(g)
                        break
        elif key == "escape":
            if self.dunya_uyari.enabled:
                self.dunya_uyari.enabled = False
            elif self.sag_tik_menu.enabled:
                self.sag_tik_menu.enabled = False
            elif self.hak.enabled:
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

    # ================= hӘр шар =================
    def kamera(self, dt):
        if self.gecis_aktif:
            self.gecis_t += dt * 0.85
            p = min(1.0, self.gecis_t)
            ease = 1.0 - (1.0 - p) ** 3

            hedef_pos = self.hedef_yuzey_gezegen.govde.world_position
            yon = (self.gecis_bas_pos - hedef_pos)
            if yon.length() == 0:
                yon = Vec3(0, 1, -2)
            yon = yon.normalized()
            inis_noktasi = hedef_pos + yon * (self.hedef_yuzey_gezegen.r * 1.05)

            camera.position = lerp(self.gecis_bas_pos, inis_noktasi, ease)
            camera.look_at(hedef_pos)

            atm_c = hx(self.hedef_yuzey_gezegen.v["renk"], max(0.0, (p - 0.55) / 0.45), 0.7)
            self.gecis_perde.color = atm_c

            if p >= 1.0:
                self.gecis_aktif = False
                self.yuzey_modunu_aktiflestir()
            return

        if self.yuzey_modu:
            if self.gecis_perde.enabled:
                yeni_a = max(0.0, self.gecis_perde.color.a - dt * 1.8)
                self.gecis_perde.color = Color(self.gecis_perde.color.r, self.gecis_perde.color.g, self.gecis_perde.color.b, yeni_a)
                if yeni_a <= 0.01:
                    self.gecis_perde.enabled = False

            if not self.ui_ustunde() and (held_keys["left mouse"] or held_keys["right mouse"]):
                self.yuzey_yaw += mouse.velocity[0] * 120 * self.kamera_hassasiyet
                self.yuzey_pitch = max(8.0, min(75.0, self.yuzey_pitch - mouse.velocity[1] * 90 * self.kamera_hassasiyet))

            if self.astronot:
                ry = math.radians(self.yuzey_yaw)
                rp = math.radians(self.yuzey_pitch)
                ofset = Vec3(
                    math.sin(ry) * math.cos(rp),
                    math.sin(rp),
                    -math.cos(ry) * math.cos(rp)
                ) * self.yuzey_dist
                hedef_k = self.astronot.world_position + Vec3(0, 1.8, 0) + ofset
                camera.position = lerp(camera.position, hedef_k, min(1.0, dt * 10))
                camera.look_at(self.astronot.world_position + Vec3(0, 1.5, 0))
            return

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

        if self.yuzey_modu and self.astronot:
            v = self.hedef_yuzey_gezegen.v
            cekim = v.get("cekimi", YERCEKIMI_TABLOSU.get(v["ad"], 9.81))
            ruzgar = v.get("ruzgar", 10)

            ileri_x = -math.sin(math.radians(self.yuzey_yaw))
            ileri_z = math.cos(math.radians(self.yuzey_yaw))
            sag_x = math.cos(math.radians(self.yuzey_yaw))
            sag_z = math.sin(math.radians(self.yuzey_yaw))

            giris_z = (1 if (held_keys["w"] or held_keys["up arrow"]) else 0) - (1 if (held_keys["s"] or held_keys["down arrow"]) else 0)
            giris_x = (1 if (held_keys["d"] or held_keys["right arrow"]) else 0) - (1 if (held_keys["a"] or held_keys["left arrow"]) else 0)

            hareket = Vec3(ileri_x * giris_z + sag_x * giris_x, 0, ileri_z * giris_z + sag_z * giris_x)
            if hareket.length() > 0:
                hareket = hareket.normalized()
                hiz = 7.5 * dt
                self.astronot.position += hareket * hiz
                self.astronot.rotation_y = math.degrees(math.atan2(hareket.x, hareket.z))

                self.yurume_zamani += dt * 10.0
                aci = math.sin(self.yurume_zamani) * 35.0
                self.sol_bacak.rotation_x = aci
                self.sag_bacak.rotation_x = -aci
                self.sol_kol.rotation_x = -aci * 0.8
                self.sag_kol.rotation_x = aci * 0.8
            else:
                self.sol_bacak.rotation_x = lerp(self.sol_bacak.rotation_x, 0, dt * 10)
                self.sag_bacak.rotation_x = lerp(self.sag_bacak.rotation_x, 0, dt * 10)
                self.sol_kol.rotation_x = lerp(self.sol_kol.rotation_x, 0, dt * 10)
                self.sag_kol.rotation_x = lerp(self.sag_kol.rotation_x, 0, dt * 10)

            if ruzgar > 80:
                self.astronot.x += (ruzgar / 2000.0) * dt

            self.astronot.x = max(-120, min(120, self.astronot.x))
            self.astronot.z = max(-120, min(120, self.astronot.z))

            self.astronot_vy -= cekim * 1.6 * dt
            self.astronot.y += self.astronot_vy * dt
            if self.astronot.y <= 0.0:
                self.astronot.y = 0.0
                self.astronot_vy = 0.0
                self.yerde_mi = True

            yakin_numune, mesafe = self.en_yakin_numune()
            if yakin_numune is not None and mesafe <= 5.0:
                self.yh_ipucu.text = f"[E] tuşuna basarak {yakin_numune['tur']} numunesi topla ({mesafe:.1f}m)"

            t_simdi = time.time()
            for alev, baz_yuk, faz in self.ates_listesi:
                if alev and alev.enabled:
                    yeni_y = baz_yuk * (0.8 + 0.35 * math.sin(t_simdi * 7.0 + faz))
                    alev.scale_y = yeni_y
                    alev.y = yeni_y * 0.5

            ruzgar_hiz_katsayi = max(2.5, min(12.0, ruzgar * 0.08))
            for kumas, faz in self.dikilen_bayraklar:
                if kumas and kumas.enabled:
                    kumas.rotation_y = math.sin(t_simdi * ruzgar_hiz_katsayi + faz) * 8.0
                    kumas.rotation_z = math.cos(t_simdi * ruzgar_hiz_katsayi * 0.7 + faz) * 2.5

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
                if t in self.tehditler:
                    self.tehditler.remove(t)
                if f in self.fuzeler:
                    self.fuzeler.remove(f)

        for p in self.patlamalar[:]:
            p['omur'] -= dt
            if p['omur'] <= 0:
                destroy(p['ent'])
                self.patlamalar.remove(p)
            else:
                p['ent'].scale += Vec3(dt * 20, dt * 20, dt * 20)
                p['ent'].color = Color(1, 0.6, 0.1, p['omur'] / p['maks_omur'])

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
            if (Vec3(*p) - camera.world_position).dot(camera.forward) > 0 and not self.yuzey_modu and not self.gecis_aktif:
                sp = g.govde.screen_position
                y_offset = 0.05 + (g.r * 0.015)
                t.position = (sp[0], sp[1] + y_offset)
                t.enabled = True
            else:
                t.enabled = False

        if self.hak.enabled:
            self.kayan_yazi(dt)
        self.canli_t += dt
        if self.canli_t > .5 and self.secili is not None and not self.yuzey_modu and not self.gecis_aktif:
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