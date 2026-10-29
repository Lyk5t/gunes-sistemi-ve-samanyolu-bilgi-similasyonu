"""Arayüz bileşenleri (Ursina): kaydırıcı ve seçenek düğmesi."""
from ursina import Button, Entity, Text, held_keys, mouse
from ursina.color import Color

BEYAZ = Color(1, 1, 1, 1)

# Tüm yazıların boyut çarpanı. Yazılar hâlâ büyükse düşürün (0.5), küçükse artırın (0.8).
YAZI_OLCEK = 0.70


def Yazi(*args, **kw):
    """Ölçeklenmiş Text."""
    kw["scale"] = kw.get("scale", 1) * YAZI_OLCEK
    return Text(*args, **kw)


def Dugme(*args, **kw):
    """Düğme yazısı küçültülmüş Button."""
    b = Button(*args, **kw)
    try:
        b.text_entity.scale *= YAZI_OLCEK
    except AttributeError:
        pass
    return b


class Kaydirici(Entity):
    """Sürüklenebilir kaydırıcı. ax: sol kenarın ekran x konumu, w: genişlik."""
    aktif = None      # o anda sürüklenen kaydırıcı
    gorunur = False   # form açık mı

    def __init__(self, ebeveyn, ax, y, w, mn, mx, deger, adim, etiket, birim="", nd=1, renk=Color(1, .37, .63, 1)):
        super().__init__(parent=ebeveyn)
        self.ax, self.w, self.mn, self.mx, self.adim = ax, w, mn, mx, adim
        self.etiket, self.birim, self.nd = etiket, birim, nd
        self.yazi = Yazi(parent=ebeveyn, text=" ", position=(ax, y + .022), scale=.75, color=Color(.85, .85, .95, 1))
        self.vurus = Entity(parent=ebeveyn, model="quad", color=Color(0, 0, 0, 0), scale=(w, .03),
                            position=(ax + w / 2, y), collider="box")
        Entity(parent=ebeveyn, model="quad", color=Color(1, 1, 1, .18), scale=(w, .006), position=(ax + w / 2, y))
        self.dolu = Entity(parent=ebeveyn, model="quad", color=renk, scale=(.001, .006),
                           origin=(-.5, 0), position=(ax, y, -.01))
        self.tut = Entity(parent=ebeveyn, model="circle", color=BEYAZ, scale=.018, position=(ax, y, -.02))
        self.y = y
        self.ata(deger)

    def ata(self, v):
        v = max(self.mn, min(self.mx, v))
        self.deger = v
        t = (v - self.mn) / (self.mx - self.mn)
        self.tut.x = self.ax + t * self.w
        self.dolu.scale_x = max(.001, t * self.w)
        self.yazi.text = f"{self.etiket}: {v:.{self.nd}f} {self.birim}"

    def update(self):
        if not Kaydirici.gorunur:
            return
        if held_keys["left mouse"]:
            if Kaydirici.aktif is None and self.vurus.hovered:
                Kaydirici.aktif = self
            if Kaydirici.aktif is self:
                t = max(0, min(1, (mouse.x - self.ax) / self.w))
                v = self.mn + t * (self.mx - self.mn)
                self.ata(round(v / self.adim) * self.adim)
        elif Kaydirici.aktif is self:
            Kaydirici.aktif = None


def dongu_dugme(ebeveyn, onek, secenekler, x, y, w, idx=0):
    """Tıklandıkça seçenekler arasında dönen düğme."""
    b = Dugme(parent=ebeveyn, text=f"{onek}{secenekler[idx]}", position=(x, y), scale=(w, .034),
               color=Color(.25, .27, .5, 1))
    b.sec, b.secenekler, b.onek = idx, secenekler, onek

    def tikla():
        b.ata((b.sec + 1) % len(secenekler))
    b.ata = lambda i: (setattr(b, "sec", i), setattr(b, "text", f"{onek}{secenekler[i]}"))
    b.on_click = tikla
    return b
