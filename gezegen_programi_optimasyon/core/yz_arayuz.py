"""Yapay zekâ paneli (Ursina): Asistan, Oluşturucu, Analiz, Görevler, Senaryo sekmeleri.
Hesaplar yapay_zeka.py içindedir; burası yalnızca arayüz ve görsel olay animasyonlarıdır.

Yazılar taşıyorsa SATIR_GENISLIK'i düşürün, çok küçükse artırın.
"""
import math
import queue
import random
import textwrap
import time

from ursina import Entity, Mesh, Vec3, camera, destroy, invoke, mouse, window
from ursina.color import Color
from ursina.prefabs.input_field import InputField

import dokular
import yapay_zeka as yz
from arayuz import Dugme, Yazi

SATIR_GENISLIK = 62      # bir satıra sığan karakter sayısı
SATIR_SAYISI = 17        # panelde aynı anda görünen satır sayısı

PANEL = Color(.06, .07, .18, .94)
YAZI = Color(.93, .92, 1, 1)
SOLUK = Color(.68, .67, .82, 1)
CAMGOBEGI = Color(.4, .85, 1, 1)
SEKME_PASIF = Color(.22, .24, .48, 1)
SEKME_AKTIF = Color(.2, .6, .85, 1)
BUTON = Color(.25, .27, .5, 1)

SEKMELER = ["Asistan", "Oluşturucu", "Analiz", "Görevler", "Senaryo"]
ORNEK_GEZEGENLER = [
    "Bana okyanuslarla kaplı, iki uydusu bulunan ve atmosferi metan ağırlıklı bir gezegen oluştur.",
    "Adı Kızıl-9 olan, çok sıcak, volkanik, lavlarla kaplı küçük bir gezegen yap.",
    "Halkalı, soğuk, mavi bir gaz devi oluştur, dört uydusu olsun.",
]


# Ursina'nın varsayılan yazı tipinde bulunmayabilecek simgeler düz karşılıklarıyla değiştirilir.
GUVENLI = {"→": "->", "≈": "~", "₂": "2", "…": "...", "⊕": "E", "≥": ">=", "−": "-", "–": "-", "—": "-", "“": '"', "”": '"'}


def guvenli(metin):
    for k, v in GUVENLI.items():
        metin = metin.replace(k, v)
    return metin


def sar(metin):
    """Metni panel genişliğine göre satırlara böler."""
    metin = guvenli(metin)
    cikti = []
    for p in metin.split("\n"):
        cikti.extend(textwrap.wrap(p, SATIR_GENISLIK) or [""])
    return cikti


def sinirla(x, a, b):
    return max(a, min(b, x))


def renk_hex(h, a=1.0):
    r, g, b = dokular.hex_rgb(h)
    return Color(r / 255, g / 255, b / 255, a)


class YapayZekaPaneli(Entity):
    def __init__(self, uygulama):
        super().__init__()
        self.u = uygulama
        self.sekme = 0
        self.satirlar, self.ofset = [], 0
        self.sohbet = []                      # (kim, metin)
        self.gecmis = []                      # Claude için (rol, metin)
        self.kuyruk = queue.Queue()
        self.bekliyor = False
        self.gorev_durum = {}                 # gezegen adı -> tamamlanan görev sayısı
        self.orijinal = {}                    # yörünge değişiminden önceki değerler
        self.olaylar, self.efektler = [], []
        self.log = []
        self.son_secili = object()
        self.son_gezegen_metni = ""
        self.hizli = []
        self.sonuc_metni = ""

        ar = window.aspect_ratio
        # ---- üst çubuktaki açma düğmesi
        self.ac_btn = Dugme(parent=camera.ui, text="Yapay Zekâ", position=(ar / 2 - .47, .465), scale=(.13, .04),
                            color=Color(.15, .62, .55, 1), on_click=self.degistir)

        # ---- panel
        p = self.panel = Entity(parent=camera.ui, enabled=False, position=(-.12, 0, -2))
        Entity(parent=p, model="quad", color=PANEL, scale=(.80, .86), position=(0, 0, 1), collider="box")
        Entity(parent=p, model="quad", color=CAMGOBEGI, scale=(.80, .008), position=(0, .43, .5))
        Yazi(parent=p, text="YAPAY ZEKÂ UZAY ASİSTANI", position=(-.37, .415), scale=1.1, color=CAMGOBEGI)
        self.anahtar_modu = False             # True: bir sonraki Gönder, API anahtarını kaydeder
        self.online_btn = Dugme(parent=p, text="Online AI: KAPALI", position=(.16, .398), scale=(.24, .032),
                                color=Color(.35, .35, .45, 1), on_click=self.online_degistir)
        Dugme(parent=p, text="X", position=(.37, .398), scale=(.04, .032), color=Color(.7, .2, .25, 1),
              on_click=self.kapat)

        self.sekme_btn = []
        for i, ad in enumerate(SEKMELER):
            b = Dugme(parent=p, text=ad, position=(-.32 + .16 * i, .345), scale=(.15, .034), color=SEKME_PASIF,
                      on_click=lambda i=i: self.sekme_sec(i))
            self.sekme_btn.append(b)
        self.baglam = Yazi(parent=p, text=" ", position=(-.37, .31), scale=.8, color=SOLUK)
        self.cikti = Yazi(parent=p, text=" ", position=(-.37, .27), scale=.8, color=YAZI)

        self.btn_yukari = Dugme(parent=p, text="Yukarı", position=(.345, .24), scale=(.09, .03), color=BUTON,
                                on_click=lambda: self.kaydir(-1))
        self.btn_asagi = Dugme(parent=p, text="Aşağı", position=(.345, -.20), scale=(.09, .03), color=BUTON,
                               on_click=lambda: self.kaydir(1))
        self.sayfa = Yazi(parent=p, text=" ", position=(.30, -.235), scale=.7, color=SOLUK)

        self.ipucu = Yazi(parent=p, text=" ", position=(-.37, -.285), scale=.75, color=Color(1, .85, .45, 1))
        self.giris = InputField(parent=p, default_value="", position=(-.13, -.335), scale=(.52, .04),
                                character_limit=100)
        self.gonder_btn = Dugme(parent=p, text="Gönder", position=(.27, -.335), scale=(.2, .04),
                                color=Color(.15, .62, .55, 1), on_click=self.gonder)
        self.hizli_grup = Entity(parent=p)

        self.sekme_sec(0)
        self.mod_guncelle()

    # ------------------------------------------------------------- açma / kapama
    def acik(self):
        return bool(self.panel.enabled)

    def ac(self):
        self.panel.enabled = True
        self.u.sag_tik_menu.enabled = False
        self.u.form_kapat()
        self.u.ayarlar_kapat()
        self.u.hakkinda_kapat()
        self.sekme_sec(self.sekme)

    def kapat(self):
        self.panel.enabled = False

    def degistir(self):
        self.kapat() if self.acik() else self.ac()

    def fare_ustunde(self):
        he = mouse.hovered_entity
        return bool(self.panel.enabled and he is not None and he.has_ancestor(self.panel))

    def mod_guncelle(self):
        acik = yz.cevrimici_acik()
        self.online_btn.text = "Online AI: AÇIK" if acik else "Online AI: KAPALI"
        self.online_btn.color = Color(.15, .62, .55, 1) if acik else Color(.35, .35, .45, 1)

    def sistem_mesaji(self, metin):
        self.sohbet.append(("SİSTEM", metin))
        self.sohbet = self.sohbet[-12:]
        if self.sekme == 0:
            self.goster(self.sohbet_metni(), alta=True)

    def online_degistir(self):
        """Online (Claude) modunu açar/kapatır. Anahtar yoksa önce anahtar ister."""
        if yz.cevrimici_acik():
            yz.cevrimici_ayarla(False)
            self.sistem_mesaji("Online mod KAPALI. Yanıtlar çevrimdışı (fizik + kural tabanlı) üretilecek.")
        elif yz.claude_hazir():
            yz.cevrimici_ayarla(True)
            self.anahtar_modu = False
            self.sistem_mesaji("Online mod AÇIK. Asistan ve gezegen oluşturucu Claude ile çalışacak; "
                               "internet yoksa ya da hata olursa çevrimdışı moda döner.")
        else:
            self.anahtar_modu = True
            self.sistem_mesaji("Online mod için Claude API anahtarı gerekli. Anahtarı (sk-ant-... ile başlar) alttaki "
                               "kutuya yapıştırıp Gönder'e bas. Anahtar yalnızca bu bilgisayarda, program klasöründeki "
                               "anthropic_anahtar.txt dosyasında saklanır.")
        self.mod_guncelle()
        self.sekme_sec(0)

    def anahtar_al(self, metin):
        k = metin.strip()
        if not (k.startswith("sk-") and len(k) > 20):
            self.sistem_mesaji("Bu bir API anahtarına benzemiyor (sk- ile başlamalı). Tekrar dene ya da başka bir yere "
                               "tıklayıp Online AI düğmesine basarak vazgeç.")
            return
        yz.anahtar_kaydet(k)
        yz.cevrimici_ayarla(True)
        self.anahtar_modu = False
        self.mod_guncelle()
        self.sistem_mesaji("Anahtar kaydedildi, online mod AÇIK.")
        self.sekme_sec(0)

    def anahtar_sil(self):
        yz.anahtar_sil()
        self.anahtar_modu = False
        self.mod_guncelle()
        self.sistem_mesaji("Kayıtlı API anahtarı silindi, online mod KAPALI.")

    # ------------------------------------------------------------- metin alanı
    def goster(self, metin, alta=False):
        self.satirlar = sar(metin)
        self.ofset = max(0, len(self.satirlar) - SATIR_SAYISI) if alta else 0
        self.ciz()

    def ciz(self):
        n = len(self.satirlar)
        self.ofset = int(sinirla(self.ofset, 0, max(0, n - SATIR_SAYISI)))
        parca = self.satirlar[self.ofset:self.ofset + SATIR_SAYISI]
        self.cikti.text = "\n".join(parca) if parca else " "
        sayfa_sayisi = max(1, math.ceil(n / SATIR_SAYISI))
        self.sayfa.text = f"{self.ofset // SATIR_SAYISI + 1}/{sayfa_sayisi}" if n > SATIR_SAYISI else " "
        self.btn_yukari.enabled = self.btn_asagi.enabled = n > SATIR_SAYISI

    def kaydir(self, yon):
        self.ofset += yon * 4
        self.ciz()

    def giris_ata(self, t):
        try:
            self.giris.text = t
        except Exception:
            try:
                self.giris.text_field.text = t
            except Exception:
                pass

    def secili_v(self):
        g = self.u.secili
        return g.v if g else None

    def tumu(self):
        return [g.v for g in self.u.gezegenler]

    def g_bul(self, ad):
        for g in self.u.gezegenler:
            if g.v["ad"] == ad:
                return g
        return None

    # ------------------------------------------------------------- sekmeler
    def sekme_sec(self, i):
        self.sekme = i
        for k, b in enumerate(self.sekme_btn):
            b.color = SEKME_AKTIF if k == i else SEKME_PASIF
        for e in self.hizli:
            destroy(e)
        self.hizli = []
        self.giris.enabled = self.gonder_btn.enabled = i in (0, 1, 4)
        self.ipucu.text = {
            0: "Bir soru yaz: Mars'ta yaşam mümkün mü? (Enter ile gönder)",
            1: "Gezegeni tarif et: okyanuslu, iki uydulu, metan atmosferli...",
            2: " ", 3: " ",
            4: "Komut yaz: Mars'a 10 km çapında asteroit çarp / güneş patlaması X10",
        }[i]
        if i == 0 and self.anahtar_modu:
            self.ipucu.text = "API anahtarını yapıştır (sk-ant-...) ve Gönder'e bas"
        if i == 0:
            butonlar = [("Yaşam?", lambda: self.hizli_sor("Burada yaşam mümkün mü?")),
                        ("İnsan?", lambda: self.hizli_sor("Bu gezegende insan yaşayabilir mi?")),
                        ("Halkalar?", lambda: self.hizli_sor("Satürn'ün halkaları neden var?")),
                        ("Temizle", self.sohbet_temizle),
                        ("Anahtarı Sil", self.anahtar_sil)]
        elif i == 1:
            butonlar = [("Örnek 1", lambda: self.giris_ata(ORNEK_GEZEGENLER[0])),
                        ("Örnek 2", lambda: self.giris_ata(ORNEK_GEZEGENLER[1])),
                        ("Örnek 3", lambda: self.giris_ata(ORNEK_GEZEGENLER[2])),
                        ("Seçiliyi Sil", self.sil_secili)]
        elif i in (2, 3):
            butonlar = [("Yenile", self.yenile)]
            if i == 3:
                butonlar = [("Görevi İlerlet", self.gorev_ilerlet), ("Görevleri Sıfırla", self.gorev_sifirla),
                            ("Yenile", self.yenile)]
        else:
            butonlar = [("Asteroit", lambda: self.hizli_olay("asteroit")),
                        ("Gezegen Çarp.", lambda: self.hizli_olay("carpisma")),
                        ("Güneş Patl.", lambda: self.hizli_olay("gunes")),
                        ("Yörünge", lambda: self.hizli_olay("yorunge")),
                        ("Sıfırla", self.yorunge_sifirla)]
        n = len(butonlar)
        w = min(.19, .76 / n - .01)
        adim = w + .012
        x0 = -adim * (n - 1) / 2
        for k, (ad, fn) in enumerate(butonlar):
            self.hizli.append(Dugme(parent=self.hizli_grup, text=ad, position=(x0 + k * adim, -.39),
                                    scale=(w, .034), color=BUTON, on_click=fn))
        self.yenile()

    def yenile(self):
        self.son_secili = self.u.secili
        g = self.u.secili
        self.baglam.text = f"Seçili gezegen: {g.v['ad']}" if g else "Seçili gezegen yok (Güneş Sistemi görünümü)"
        if self.sekme == 0:
            self.goster(self.sohbet_metni() or yz.yardim_metni(), alta=True)
        elif self.sekme == 1:
            self.goster(self.son_gezegen_metni or
                        "Yapay zekâ gezegen oluşturucu\n\nİstediğin gezegeni Türkçe olarak anlat; tür, boyut, atmosfer, "
                        "sıcaklık, uydu sayısı, halka, renk ve ad gibi özellikleri çıkarırım, eksik kalanları "
                        "bilimsel olarak tutarlı şekilde tamamlar ve simülasyona eklerim.\n\nÖrnekler için alttaki "
                        "'Örnek' düğmelerine bas, sonra Gönder'e tıkla.\n\nNot: Dokunun üretimi birkaç saniye sürebilir.")
        elif self.sekme == 2:
            self.goster(yz.analiz_raporu(g.v) if g else "Analiz için üst menüden bir gezegen seç.")
        elif self.sekme == 3:
            self.goster(self.gorev_metni(g) if g else "Görevler için üst menüden bir gezegen seç.")
        else:
            self.goster(self.senaryo_metni() or
                        "Akıllı evren simülasyonu\n\nKomut örnekleri:\n - Dünya'ya 10 km çapında asteroit çarp\n"
                        " - Mars ile Dünya çarpışsın\n - Güneş patlaması X10 olsun\n - Jüpiter'in yörüngesini 2 kat büyüt\n"
                        " - Mars yörüngesi Güneş'e yaklaşsın\n\nAlttaki düğmeler seçili gezegen için hızlı senaryo başlatır; "
                        "'Sıfırla' değiştirilen yörüngeleri eski haline getirir.")

    # ------------------------------------------------------------- gönder
    def gonder(self):
        metin = (self.giris.text or "").strip()
        if not metin or self.sekme not in (0, 1, 4):
            return
        self.giris_ata("")
        if self.sekme == 0 and self.anahtar_modu:
            self.anahtar_al(metin)                 # anahtar sohbete yazılmaz
            return
        if self.sekme == 0:
            self.soru_sor(metin)
        elif self.sekme == 1:
            self.gezegen_olustur(metin)
        else:
            self.senaryo_baslat(metin)

    def input(self, key):
        if key == "enter" and self.panel.enabled and (self.giris.text or "").strip():
            self.gonder()

    # ------------------------------------------------------------- 1) asistan
    def sohbet_metni(self):
        return "\n\n".join(f"{k}: {m}" for k, m in self.sohbet)

    def sohbet_temizle(self):
        self.sohbet, self.gecmis = [], []
        self.yenile()

    def hizli_sor(self, soru):
        self.soru_sor(soru)

    def soru_sor(self, soru):
        v = self.secili_v()
        self.sohbet.append(("SEN", soru))
        if yz.cevrimici_acik():
            self.sohbet.append(("ASİSTAN [online]", "düşünüyor…"))
            self.bekliyor = True
            yz.claude_sor_baslat(self.kuyruk, soru, v, list(self.gecmis))
            self.gecmis.append(("user", soru))
            self._bekleyen_soru = (soru, v)
        else:
            c = yz.cevapla(soru, v, self.tumu())
            self.sohbet.append(("ASİSTAN", c))
            self.gecmis += [("user", soru), ("assistant", c)]
        self.sohbet = self.sohbet[-12:]
        if self.sekme == 0:
            self.goster(self.sohbet_metni(), alta=True)

    def kuyruk_isle(self):
        while not self.kuyruk.empty():
            etiket, durum, metin = self.kuyruk.get()
            if etiket == "uret":
                ai = yz.ai_json_coz(metin) if durum == "ok" else None
                if ai:
                    not_ = ""
                elif durum == "ok":
                    not_ = "Claude'un yanıtı anlaşılamadı; kural tabanlı üretim kullanıldı.\n\n"
                else:
                    not_ = f"Claude'a ulaşılamadı ({metin[:80]}); kural tabanlı üretim kullanıldı.\n\n"
                self.uret_son(getattr(self, "_uret_metin", ""), ai, not_)
                continue
            self.bekliyor = False
            if durum == "ok" and metin:
                kim, cevap = "ASİSTAN [online]", metin
            else:
                soru, v = getattr(self, "_bekleyen_soru", ("", None))
                kim = "ASİSTAN [çevrimdışı]"
                cevap = (yz.cevapla(soru, v, self.tumu())
                         + f"\n(Claude'a ulaşılamadı: {metin[:80]}. Çevrimdışı yanıt verildi.)")
            if self.sohbet and self.sohbet[-1][1] == "düşünüyor…":
                self.sohbet[-1] = (kim, cevap)
            else:
                self.sohbet.append((kim, cevap))
            self.gecmis.append(("assistant", cevap))
            if self.sekme == 0:
                self.goster(self.sohbet_metni(), alta=True)

    # ------------------------------------------------------------- 2) gezegen oluşturucu
    def gezegen_olustur(self, metin):
        if yz.cevrimici_acik():
            self._uret_metin = metin
            self.goster("Claude'a soruluyor… (online mod)")
            yz.claude_uret_baslat(self.kuyruk, metin)
        else:
            self.uret_son(metin, None, "")

    def uret_son(self, metin, ai, not_):
        adlar = [g.v["ad"] for g in self.u.gezegenler]
        v, rapor = yz.gezegen_uret(metin, adlar, self.u.dmax + 2.5, ai=ai)
        rapor = not_ + rapor
        self.son_gezegen_metni = rapor
        self.goster("Gezegen oluşturuluyor… (doku üretimi birkaç saniye sürebilir)\n\n" + rapor)
        invoke(self._gezegen_ekle, v, rapor, delay=.2)

    def _gezegen_ekle(self, v, rapor):
        try:
            g = self.u.ekle(v, True)
            self.u.sec(g, True)
            self.u.kaydet()
            sonuc = rapor + "\n\nGezegen simülasyona eklendi ve seçildi. Güneş Sistemi görünümünde en dış yörüngede."
        except Exception as hata:
            sonuc = rapor + f"\n\nGezegen eklenemedi: {hata}"
        self.son_gezegen_metni = sonuc
        if self.sekme == 1:
            self.goster(sonuc)

    def sil_secili(self):
        g = self.u.secili
        if g is not None and g.ozel:
            self.u.sil()
            self.son_gezegen_metni = "Seçili gezegen silindi."
        else:
            self.son_gezegen_metni = "Yalnızca yapay zekâyla/formla oluşturulan gezegenler silinebilir; önce birini seç."
        self.yenile()

    # ------------------------------------------------------------- 4) görevler
    def gorev_metni(self, g):
        L = yz.gorevler(g.v)
        yapilan = self.gorev_durum.get(g.v["ad"], 0)
        s = [f"KEŞİF GÖREVLERİ: {g.v['ad']}  ({yapilan}/{len(L)} tamamlandı)", ""]
        for i, m in enumerate(L):
            isaret = "[x]" if i < yapilan else ("[>]" if i == yapilan else "[ ]")
            s.append(f"{isaret} {i + 1}. {m['ad']}  (risk: {m['risk']}, ≈{m['sure']} gün)")
            s.append("      " + m["aciklama"])
            if i < yapilan:
                s.append("      BULGU: " + m["sonuc"])
            s.append("")
        if yapilan >= len(L):
            s.append("Tüm görevler tamamlandı.")
        return "\n".join(s)

    def gorev_ilerlet(self):
        g = self.u.secili
        if g is None:
            return
        n = len(yz.gorevler(g.v))
        ad = g.v["ad"]
        self.gorev_durum[ad] = min(n, self.gorev_durum.get(ad, 0) + 1)
        self.yenile()

    def gorev_sifirla(self):
        g = self.u.secili
        if g is not None:
            self.gorev_durum[g.v["ad"]] = 0
        self.yenile()

    # ------------------------------------------------------------- 5) senaryo
    def senaryo_metni(self):
        return "\n\n".join(self.log)

    def log_ekle(self, metin):
        self.log.append(metin)
        self.log = self.log[-6:]
        if self.sekme == 4:
            self.goster(self.senaryo_metni(), alta=True)

    def hizli_olay(self, tip):
        g = self.u.secili
        ad = g.v["ad"] if g else ("Dünya" if self.g_bul("Dünya") else self.u.gezegenler[0].v["ad"])
        diger = [x.v["ad"] for x in self.u.gezegenler if x.v["ad"] != ad and x.v["ad"] != "Ay"]
        komut = {"asteroit": f"{ad}'a 10 km çapında asteroit çarp",
                 "carpisma": f"{diger[0] if diger else 'Mars'} ile {ad} çarpışsın",
                 "gunes": "Güneş patlaması X10 olsun",
                 "yorunge": f"{ad} yörüngesini 1.6 kat büyüt"}[tip]
        self.senaryo_baslat(komut)

    def senaryo_baslat(self, metin):
        adlar = [g.v["ad"] for g in self.u.gezegenler]
        sec = self.u.secili.v["ad"] if self.u.secili else None
        plan = yz.senaryo_coz(metin, adlar, sec)
        tip = plan["tip"]
        if tip == "bilinmiyor" or (tip != "gunes" and plan["hedef"] is None):
            self.log_ekle("Komutu anlayamadım. Örnek: \"Mars'a 10 km çapında asteroit çarp\", "
                          "\"güneş patlaması X10\", \"Jüpiter'in yörüngesini 2 kat büyüt\".")
            return
        if tip == "asteroit":
            self.olay_asteroit(plan)
        elif tip == "carpisma":
            self.olay_carpisma(plan)
        elif tip == "gunes":
            self.olay_gunes(plan)
        else:
            self.olay_yorunge(plan)

    # ---- yardımcı: görsel efektler
    def patlama_efekti(self, poz, g, h):
        frac = sinirla((math.log10(max(h["Emt"], 1e-6)) + 6) / 15, 0, 1)
        maks = g.r * (0.35 + 3.0 * frac)
        e = Entity(model="sphere", color=Color(1, .6, .1, .9), position=poz, scale=.05, unlit=True)
        self.efektler.append(dict(tip="patlama", ent=e, omur=2.2, maks_omur=2.2, boyut=maks))
        yon0 = (poz - Vec3(*g.govde.world_position))
        yon0 = yon0.normalized() if yon0.length() > 1e-6 else Vec3(0, 1, 0)
        for _ in range(int(10 + 35 * frac)):
            d = Entity(model="sphere", color=random.choice([Color(.5, .45, .4, 1), Color(1, .55, .15, 1)]),
                       position=poz, scale=g.r * random.uniform(.03, .09), unlit=True)
            hiz = (yon0 + Vec3(random.uniform(-.8, .8), random.uniform(-.8, .8), random.uniform(-.8, .8))) \
                * random.uniform(.6, 3.0) * (1 + 2 * frac)
            self.efektler.append(dict(tip="parca", ent=d, omur=3.0, maks_omur=3.0, hiz=hiz))
        try:
            self.u.patlama_sesi_cal()
        except Exception:
            pass

    def halka_efekti(self, poz, renk, boyut):
        e = Entity(model="sphere", color=renk, position=poz, scale=.05, unlit=True)
        self.efektler.append(dict(tip="halka", ent=e, omur=1.6, maks_omur=1.6, boyut=boyut, renk=renk))

    # ---- asteroit
    def olay_asteroit(self, plan):
        g = self.g_bul(plan["hedef"])
        cap = plan["cap_km"] or 10.0
        hiz = plan["hiz"] or 20.0
        h = yz.carpma_hesapla(g.v, cap, hiz)
        self.baslat_ucus(g, cap, hiz, h, None, Color(.45, .35, .3, 1), sinirla(.25 + .35 * math.log10(cap * 1000 + 10), .25, 2.0))
        self.u.sec(g, True)
        self.u.dist_h = max(g.r * 14, 12)
        self.log_ekle(f"Asteroit {g.v['ad']} gezegenine doğru yola çıktı…\n" + yz.carpma_metni(g.v, h, cap, hiz))

    def olay_carpisma(self, plan):
        g = self.g_bul(plan["hedef"])
        k = self.g_bul(plan["kaynak"]) if plan["kaynak"] else None
        if k is not None and k is not g:
            M_k, _, _, vk_k = yz.fiziksel(k.v)
            _, _, _, vk_h = yz.fiziksel(g.v)
            rk, rk_km, renk, kad = k.r, k.v["yaricap_km"], renk_hex(k.v["renk"]), k.v["ad"]
        else:                                        # varsayılan: Theia benzeri protogezegen
            M_k, vk_k = 0.107 * yz.M_DUNYA, 5.0
            _, _, _, vk_h = yz.fiziksel(g.v)
            rk_km, rk = 3400.0, 0.5 * math.sqrt(3400 / 6371)
            renk, kad = Color(.75, .5, .35, 1), "Protogezegen"
        hiz = plan["hiz"] or math.sqrt(vk_h ** 2 + vk_k ** 2)          # serbest düşüşteki en düşük çarpma hızı
        h = yz.carpma_hesapla(g.v, 2 * rk_km, hiz, kutle_kg=M_k)
        self.baslat_ucus(g, 2 * rk_km, hiz, h, kad, renk, max(.3, 2 * rk))
        self.u.sec(g, True)
        self.u.dist_h = max(g.r * 14, 12)
        not_ = "\nNot: Çarpışma görsel olarak gösterilir; kaynak gezegen yörüngesinde kalmaya devam eder." if k else ""
        self.log_ekle(f"{kad} → {g.v['ad']} çarpışması başlıyor…\n" + yz.carpma_metni(g.v, h, 2 * rk_km, hiz, kad) + not_)

    def baslat_ucus(self, g, cap, hiz, h, kaynak_ad, renk, boyut):
        yon = Vec3(random.uniform(-1, 1), random.uniform(-.4, .4), random.uniform(-1, 1))
        yon = yon.normalized()
        d0 = max(g.r * 12, 10)
        e = Entity(model="sphere", color=renk, scale=boyut, position=Vec3(*g.govde.world_position) + yon * d0, unlit=True)
        self.olaylar.append(dict(tip="ucus", ent=e, g=g, h=h, hiz=d0 / 5.0, boyut=boyut, kaynak=kaynak_ad,
                                 cap=cap, v=hiz))

    # ---- güneş patlaması
    def olay_gunes(self, plan):
        sn = plan["sinif"]
        baslik, sonuc = yz.gunes_raporu(sn, self.tumu())
        self.u.sec(None)
        e = Entity(model="sphere", color=Color(1, .75, .25, .5), position=(0, 0, 0), scale=1, unlit=True,
                   double_sided=True)
        maks = max(g.d for g in self.u.gezegenler) * 1.1
        self.olaylar.append(dict(tip="gunes", ent=e, r=0.0, maks=maks, hiz=maks / 6.0,
                                 gez=[[g, False] for g in self.u.gezegenler], sonuc=sonuc))
        self.log_ekle(baslik + "\nPatlama dalgası yayılıyor (animasyon zamanı gerçek zamandan çok daha hızlıdır)…")

    # ---- yörünge
    def olay_yorunge(self, plan):
        g = self.g_bul(plan["hedef"])
        if g.v["ad"] not in self.orijinal:
            self.orijinal[g.v["ad"]] = dict(au=g.v["au"], periyot=g.v["periyot"], sicak=g.v["sicak"], d=g.d)
        h = yz.yorunge_hesapla(g.v, faktor=plan["faktor"], au_hedef=plan["au"])
        o = self.orijinal[g.v["ad"]]
        yeni_d = 10 + math.sqrt(h["au"]) * 9
        self.olaylar.append(dict(tip="yorunge", g=g, t=0.0, sure=4.0, d0=g.d, d1=yeni_d, au0=g.v["au"], au1=h["au"],
                                 per0=g.v["periyot"], per1=h["periyot"], s0=g.v["sicak"], s1=h["sicak"], o=o))
        self.u.sec(g, True)
        self.log_ekle(h["metin"] + "\n\n'Sıfırla' düğmesi yörüngeleri eski haline getirir.")

    def yorunge_mesh(self, g):
        pts = [Vec3(math.cos(i / 128 * 6.2832) * g.d, 0, math.sin(i / 128 * 6.2832) * g.d) for i in range(129)]
        g.yorunge.model = Mesh(vertices=pts, mode="line", thickness=1.5)

    def yorunge_uygula(self, g, d, au, per, sicak):
        """Gezegenin faz açısını koruyarak yörünge değerlerini değiştirir (ışınlanma olmaz)."""
        T = self.u.T
        a = T / g.v["periyot"] * 2 * math.pi + g.faz
        g.d, g.v["au"], g.v["periyot"], g.v["sicak"] = d, au, per, sicak
        g.faz = a - T / per * 2 * math.pi
        self.yorunge_mesh(g)

    def yorunge_sifirla(self):
        if not self.orijinal:
            self.log_ekle("Değiştirilmiş yörünge yok.")
            return
        for ad, o in list(self.orijinal.items()):
            g = self.g_bul(ad)
            if g is not None:
                self.yorunge_uygula(g, o["d"], o["au"], o["periyot"], o["sicak"])
        self.orijinal = {}
        self.olaylar = [e for e in self.olaylar if e["tip"] != "yorunge"]
        self.log_ekle("Tüm yörüngeler eski haline getirildi.")
        self.u.canli() if self.u.secili else None

    # ------------------------------------------------------------- her kare
    def update(self):
        dt = min(time.dt, 0.05)
        self.kuyruk_isle()

        # yüzey modunda düğme ve panel gizlenir
        gizle = bool(self.u.yuzey_modu or self.u.gecis_aktif)
        self.ac_btn.enabled = not gizle
        if gizle and self.panel.enabled:
            self.kapat()

        # seçim değişince Analiz/Görevler otomatik yenilenir
        if self.panel.enabled and self.sekme in (2, 3) and self.u.secili is not self.son_secili:
            self.yenile()
        elif self.panel.enabled and self.u.secili is not self.son_secili:
            self.son_secili = self.u.secili
            self.baglam.text = (f"Seçili gezegen: {self.u.secili.v['ad']}" if self.u.secili
                                else "Seçili gezegen yok (Güneş Sistemi görünümü)")

        for o in self.olaylar[:]:
            if o["tip"] == "ucus":
                self.ucus_guncelle(o, dt)
            elif o["tip"] == "gunes":
                self.gunes_guncelle(o, dt)
            elif o["tip"] == "yorunge":
                self.yorunge_guncelle(o, dt)

        for e in self.efektler[:]:
            e["omur"] -= dt
            if e["omur"] <= 0:
                destroy(e["ent"])
                self.efektler.remove(e)
                continue
            k = 1 - e["omur"] / e["maks_omur"]
            if e["tip"] == "patlama":
                s = e["boyut"] * (1 - (1 - k) ** 3)
                e["ent"].scale = max(.05, s)
                e["ent"].color = Color(1, .6 - .3 * k, .1, (1 - k) * .9)
            elif e["tip"] == "halka":
                e["ent"].scale = max(.05, e["boyut"] * (1 - (1 - k) ** 2))
                r = e["renk"]
                e["ent"].color = Color(r.r, r.g, r.b, (1 - k) * .6)
            else:
                e["ent"].position += e["hiz"] * dt
                e["ent"].color = Color(e["ent"].color.r, e["ent"].color.g, e["ent"].color.b, 1 - k)

    def ucus_guncelle(self, o, dt):
        g, e = o["g"], o["ent"]
        hedef = Vec3(*g.govde.world_position)
        yon = hedef - e.world_position
        mesafe = yon.length()
        if mesafe <= g.r + o["boyut"] * .4:
            yon0 = (e.world_position - hedef)
            yon0 = yon0.normalized() if yon0.length() > 1e-6 else Vec3(0, 1, 0)
            poz = hedef + yon0 * g.r
            destroy(e)
            self.olaylar.remove(o)
            self.patlama_efekti(poz, g, o["h"])
            self.log_ekle("ETKİ: çarpma gerçekleşti.\n" + yz.carpma_metni(g.v, o["h"], o["cap"], o["v"], o["kaynak"]))
            return
        e.world_position += yon.normalized() * min(o["hiz"] * dt, mesafe)

    def gunes_guncelle(self, o, dt):
        o["r"] += o["hiz"] * dt
        r = o["r"]
        o["ent"].scale = max(.1, r * 2)
        o["ent"].color = Color(1, .75, .25, max(0.0, .45 * (1 - r / o["maks"])))
        for par in o["gez"]:
            g, tetik = par
            if tetik:
                continue
            if r >= Vec3(*g.govde.world_position).length():
                par[1] = True
                self.halka_efekti(Vec3(*g.govde.world_position), Color(1, .7, .2, 1), max(g.r * 6, 1.2))
                m = o["sonuc"].get(g.v["ad"])
                if m:
                    self.log_ekle("DALGA ULAŞTI: " + m)
        if r >= o["maks"]:
            destroy(o["ent"])
            self.olaylar.remove(o)
            self.log_ekle("Güneş patlamasının dalgası tüm gezegenleri geçti.")

    def yorunge_guncelle(self, o, dt):
        o["t"] += dt
        p = sinirla(o["t"] / o["sure"], 0, 1)
        k = p * p * (3 - 2 * p)
        g = o["g"]
        d = o["d0"] + (o["d1"] - o["d0"]) * k
        au = o["au0"] + (o["au1"] - o["au0"]) * k
        per = o["per0"] * (au / o["au0"]) ** 1.5
        sicak = o["s0"] + (o["s1"] - o["s0"]) * k
        self.yorunge_uygula(g, d, au, per, sicak)
        if p >= 1:
            self.olaylar.remove(o)
            self.yorunge_uygula(g, o["d1"], o["au1"], o["per1"], o["s1"])
            if self.u.secili is g:
                self.u.canli()
                self.u.panel_yenile()
