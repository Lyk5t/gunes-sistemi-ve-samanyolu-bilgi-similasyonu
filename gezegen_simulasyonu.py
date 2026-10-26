"""
Samanyolu Gezegenleri Simülasyonu (Python / Tkinter)
Mimari: Model - View - Controller, katmanlar EventBus ile haberleşir.
Çalıştırma:  python gezegen_simulasyonu.py   (ek kütüphane gerekmez)
"""
import math
import random
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk

BG, PANEL, INK, MUTE, SUN, ACC = "#0a0e1f", "#121832", "#e8e4d6", "#9aa0bd", "#f2b84b", "#5fb3b3"


# ======================= MODEL =======================
@dataclass(frozen=True)
class Planet:
    ad: str
    renk: str
    yaricap: float   # km
    au: float        # Güneş'e uzaklık
    yil: float       # yörünge periyodu (gün)
    sicak: float     # ortalama sıcaklık (°C)
    uydu: int
    atm: str
    bilgi: str


class PlanetModel:
    PLANETS = [
        Planet("Merkür", "#a8a39a", 2440, 0.387, 88, 167, 0, "Neredeyse yok",
               "Güneş'e en yakın ve en küçük gezegen. Gündüz-gece sıcaklık farkı çok büyüktür."),
        Planet("Venüs", "#e0b878", 6052, 0.723, 225, 464, 0, "Yoğun karbondioksit",
               "Sera etkisiyle en sıcak gezegen. Diğer gezegenlerin çoğunun tersine döner."),
        Planet("Dünya", "#4f8fd6", 6371, 1.0, 365.25, 15, 1, "Azot ve oksijen",
               "Yaşamın bilinen tek yuvası. Yüzeyinin yaklaşık %71'i sularla kaplıdır."),
        Planet("Mars", "#c8573a", 3390, 1.524, 687, -65, 2, "İnce karbondioksit",
               "Kızıl gezegen. Güneş Sistemi'nin en yüksek yanardağı Olympus Mons burada bulunur."),
        Planet("Jüpiter", "#d9a679", 69911, 5.203, 4333, -110, 95, "Hidrojen ve helyum",
               "En büyük gezegen. Büyük Kırmızı Leke yüzyıllardır süren dev bir fırtınadır. "
               "Galile uyduları: Io, Europa, Ganymede, Callisto."),
        Planet("Satürn", "#e3cf92", 58232, 9.537, 10759, -140, 146, "Hidrojen ve helyum",
               "Buz ve kaya parçalarından oluşan halkalarıyla tanınır. En büyük uydusu Titan'dır."),
        Planet("Uranüs", "#7fd0d6", 25362, 19.19, 30687, -195, 28, "Hidrojen, helyum, metan",
               "Ekseni yaklaşık 98 derece yatık buz devi. Metan mavi-yeşil rengini verir."),
        Planet("Neptün", "#4a6fe0", 24622, 30.07, 60190, -200, 16, "Hidrojen, helyum, metan",
               "Güneş'e en uzak gezegen. Güneş Sistemi'nin en şiddetli rüzgârları burada eser."),
    ]
    METRICS = {
        "yaricap": ("Yarıçap", "km"),
        "au": ("Güneş'e uzaklık", "AU"),
        "yil": ("Yörünge periyodu", "gün"),
        "sicak": ("Ort. sıcaklık", "°C"),
        "uydu": ("Uydu sayısı", ""),
    }

    @classmethod
    def all(cls):
        return cls.PLANETS


class EventBus:
    def __init__(self):
        self._h = {}

    def on(self, olay, fn):
        self._h.setdefault(olay, []).append(fn)

    def emit(self, olay, veri=None):
        for fn in self._h.get(olay, []):
            fn(veri)


class SimulationEngine:
    """Zaman ve gezegen açılarını yönetir. Ekranı bilmez."""
    HIZLAR = [0.25, 0.5, 1, 2, 4, 8]
    GUN_PER_SN = 30  # 1 gerçek saniye = 30 gün (hız 1×)

    def __init__(self, bus):
        self.bus = bus
        self.t = 0.0
        self.running = False
        self.hiz_i = 2
        self.secili = 2  # Dünya

    @property
    def hiz(self):
        return self.HIZLAR[self.hiz_i]

    def aci(self, p):
        return (self.t / p.yil) * 2 * math.pi

    def step(self, dt):
        if self.running:
            self.t += dt * self.GUN_PER_SN * self.hiz
            self.bus.emit("tick")

    def toggle(self):
        self.running = not self.running
        self.bus.emit("state")

    def reset(self):
        self.t = 0.0
        self.bus.emit("tick")

    def hiz_degistir(self, d):
        self.hiz_i = max(0, min(len(self.HIZLAR) - 1, self.hiz_i + d))
        self.bus.emit("state")

    def sec(self, i):
        self.secili = i
        self.bus.emit("select", i)


# ======================= VIEW =======================
def fmt(n):
    return f"{n:,.2f}".rstrip("0").rstrip(".").replace(",", " ") if isinstance(n, float) else f"{n:,}".replace(",", " ")


class GalaxyView(ttk.Frame):
    W, H = 520, 400

    def __init__(self, master):
        super().__init__(master)
        c = tk.Canvas(self, width=self.W, height=self.H, bg="#060916", highlightthickness=0)
        c.pack(side="left", padx=10, pady=10)
        self._ciz(c)
        txt = ("Samanyolu, yaklaşık 100 000 ışık yılı çapında bir çubuklu sarmal galaksidir ve "
               "yüz milyarlarca yıldız içerir.\n\n"
               "Güneş Sistemi, galaksi merkezinden yaklaşık 26 000 ışık yılı uzakta, Orion Kolu "
               "üzerinde yer alır.\n\n"
               "Güneş, galaksi merkezi etrafında yaklaşık 225–250 milyon yılda bir tur atar.")
        tk.Label(self, text=txt, wraplength=300, justify="left", bg=BG, fg=INK,
                 font=("Segoe UI", 11)).pack(side="left", anchor="n", padx=10, pady=14)

    def _ciz(self, c):
        cx, cy, R = self.W / 2, self.H / 2, self.H * 0.46
        random.seed(7)
        for _ in range(2600):
            kol = random.randrange(4)
            r = (random.random() ** 0.7) * R
            a = kol * math.pi / 2 + r / R * 4.2 + (random.random() - 0.5) * (0.5 + (1 - r / R) * 0.2)
            x, y = cx + math.cos(a) * r * 1.15, cy + math.sin(a) * r * 0.85
            k = random.randint(120, 255)
            c.create_rectangle(x, y, x + 1.4, y + 1.4, fill=f"#{k:02x}{k:02x}ff", outline="")
        c.create_oval(cx - 18, cy - 18, cx + 18, cy + 18, fill="#f5d99a", outline="")
        sx, sy = cx + R * 0.6, cy + R * 0.1
        c.create_oval(sx - 8, sy - 8, sx + 8, sy + 8, outline=SUN, width=2)
        c.create_text(sx - 6, sy - 20, text="Güneş Sistemi", fill=SUN, font=("Segoe UI", 11, "bold"))
        c.create_text(cx, cy + 34, text="Galaksi merkezi", fill=MUTE, font=("Segoe UI", 10))


class OrbitView(tk.Canvas):
    S = 640

    def __init__(self, master, engine, bus):
        super().__init__(master, width=self.S, height=self.S, bg="#060916", highlightthickness=0)
        self.engine = engine
        self.konum = []
        random.seed(3)
        self.yildiz = [(random.randrange(self.S), random.randrange(self.S), random.choice((1, 1, 2)))
                       for _ in range(110)]
        bus.on("tick", lambda _: self.ciz())
        bus.on("select", lambda _: self.ciz())
        self.ciz()

    @staticmethod
    def yaricap_ciz(au):
        return 30 + math.sqrt(au) * 46

    @staticmethod
    def boyut(p):
        return 3 + p.yaricap ** 0.33 * 0.34

    def ciz(self):
        self.delete("all")
        cx = cy = self.S / 2
        for x, y, s in self.yildiz:
            self.create_rectangle(x, y, x + s, y + s, fill="#8a90b0", outline="")
        self.create_oval(cx - 22, cy - 22, cx + 22, cy + 22, fill=SUN, outline="#fff4c8", width=3)
        self.konum = []
        for i, p in enumerate(PlanetModel.all()):
            r = self.yaricap_ciz(p.au)
            sec = i == self.engine.secili
            self.create_oval(cx - r, cy - r, cx + r, cy + r, outline=SUN if sec else "#2a3158",
                             width=2 if sec else 1)
            a = self.engine.aci(p)
            x, y, s = cx + math.cos(a) * r, cy + math.sin(a) * r, self.boyut(p)
            if p.ad == "Satürn":
                self.create_oval(x - s * 1.9, y - s * 0.6, x + s * 1.9, y + s * 0.6, outline=p.renk, width=2)
            self.create_oval(x - s, y - s, x + s, y + s, fill=p.renk, outline="")
            if sec:
                self.create_oval(x - s - 5, y - s - 5, x + s + 5, y + s + 5, outline=SUN, width=2)
                self.create_text(x + s + 10, y, text=p.ad, anchor="w", fill=INK, font=("Segoe UI", 12, "bold"))
            self.konum.append((i, x, y, max(s + 8, 16)))

    def sec_noktasi(self, x, y):
        for i, px, py, r in self.konum:
            if math.hypot(px - x, py - y) <= r:
                return i
        return None


class CardView(tk.Frame):
    def __init__(self, master, engine, bus):
        super().__init__(master, bg=PANEL, padx=14, pady=12)
        self.engine = engine
        self.baslik = tk.Label(self, bg=PANEL, fg=INK, font=("Georgia", 20, "bold"), anchor="w")
        self.aciklama = tk.Label(self, bg=PANEL, fg=INK, wraplength=300, justify="left",
                                 font=("Segoe UI", 10), anchor="w")
        self.baslik.pack(fill="x")
        self.aciklama.pack(fill="x", pady=(4, 10))
        self.satirlar = {}
        for k in ("Yarıçap", "Güneş'e uzaklık", "Yörünge periyodu", "Ort. sıcaklık", "Bilinen uydu", "Atmosfer"):
            f = tk.Frame(self, bg=PANEL)
            f.pack(fill="x", pady=1)
            tk.Label(f, text=k, bg=PANEL, fg=MUTE, font=("Segoe UI", 10)).pack(side="left")
            v = tk.Label(f, bg=PANEL, fg=INK, font=("Segoe UI", 10))
            v.pack(side="right")
            self.satirlar[k] = v
        bus.on("select", lambda _: self.guncelle())
        self.guncelle()

    def guncelle(self):
        p = PlanetModel.all()[self.engine.secili]
        self.baslik.config(text=p.ad, fg=p.renk)
        self.aciklama.config(text=p.bilgi)
        deger = {"Yarıçap": f"{fmt(p.yaricap)} km", "Güneş'e uzaklık": f"{fmt(p.au)} AU",
                 "Yörünge periyodu": f"{fmt(p.yil)} gün", "Ort. sıcaklık": f"{fmt(p.sicak)} °C",
                 "Bilinen uydu": fmt(p.uydu), "Atmosfer": p.atm}
        for k, v in deger.items():
            self.satirlar[k].config(text=v)


class CompareView(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.metrik = tk.StringVar(value="yaricap")
        self.asc = False
        ust = ttk.Frame(self)
        ust.pack(fill="x", padx=10, pady=8)
        ttk.Label(ust, text="Özellik:").pack(side="left")
        self.kutu = ttk.Combobox(ust, state="readonly", width=22,
                                 values=[v[0] for v in PlanetModel.METRICS.values()])
        self.kutu.current(0)
        self.kutu.pack(side="left", padx=8)
        self.kutu.bind("<<ComboboxSelected>>", lambda e: self.grafik())
        self.cv = tk.Canvas(self, height=250, bg=PANEL, highlightthickness=0)
        self.cv.pack(fill="x", padx=10)
        kolonlar = ["ad"] + list(PlanetModel.METRICS)
        self.tablo = ttk.Treeview(self, columns=kolonlar, show="headings", height=8)
        self.tablo.heading("ad", text="Gezegen", command=lambda: self.sirala("ad"))
        self.tablo.column("ad", width=100)
        for k, (ad, _) in PlanetModel.METRICS.items():
            self.tablo.heading(k, text=ad, command=lambda k=k: self.sirala(k))
            self.tablo.column(k, width=110, anchor="e")
        self.tablo.pack(fill="x", padx=10, pady=10)
        self.cv.bind("<Configure>", lambda e: self.grafik())
        self.tabloyu_doldur(list(PlanetModel.all()))

    def anahtar(self):
        return list(PlanetModel.METRICS)[self.kutu.current()]

    def grafik(self):
        m = self.anahtar()
        birim = PlanetModel.METRICS[m][1]
        self.cv.delete("all")
        W = max(self.cv.winfo_width(), 400)
        en = max(abs(getattr(p, m)) for p in PlanetModel.all())
        for i, p in enumerate(PlanetModel.all()):
            y = 12 + i * 29
            v = getattr(p, m)
            w = max(3, abs(v) / en * (W - 260))
            self.cv.create_text(10, y + 9, text=p.ad, anchor="w", fill=INK, font=("Segoe UI", 10))
            self.cv.create_rectangle(90, y, 90 + w, y + 18, fill=p.renk, outline="")
            self.cv.create_text(98 + w, y + 9, text=f"{fmt(v)} {birim}", anchor="w", fill=MUTE,
                                font=("Segoe UI", 10))

    def tabloyu_doldur(self, liste):
        self.tablo.delete(*self.tablo.get_children())
        for p in liste:
            self.tablo.insert("", "end", values=[p.ad] + [fmt(getattr(p, k)) for k in PlanetModel.METRICS])

    def sirala(self, anahtar):
        self.asc = not self.asc
        liste = sorted(PlanetModel.all(), key=lambda p: getattr(p, anahtar), reverse=not self.asc)
        self.tabloyu_doldur(liste)


# ======================= CONTROLLER =======================
class Controller:
    FPS_MS = 33

    def __init__(self, root):
        self.root = root
        self.bus = EventBus()
        self.engine = SimulationEngine(self.bus)

        stil = ttk.Style()
        stil.theme_use("clam")
        stil.configure("TFrame", background=BG)
        stil.configure("TLabel", background=BG, foreground=INK)
        stil.configure("TNotebook", background=BG)
        stil.configure("TNotebook.Tab", padding=(14, 6))

        tk.Label(root, text="Samanyolu Gezegenleri Simülasyonu", bg=BG, fg=INK,
                 font=("Georgia", 20, "bold")).pack(anchor="w", padx=14, pady=(10, 0))
        tk.Label(root, text="Gezegenleri tanıyın, karşılaştırın ve Güneş etrafındaki hareketlerini izleyin.",
                 bg=BG, fg=MUTE).pack(anchor="w", padx=14, pady=(0, 8))

        nb = ttk.Notebook(root)
        nb.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        nb.add(GalaxyView(nb), text="Samanyolu")

        sim = ttk.Frame(nb)
        nb.add(sim, text="Simülasyon")
        self.orbit = OrbitView(sim, self.engine, self.bus)
        self.orbit.grid(row=0, column=0, rowspan=2, padx=10, pady=10)
        self.orbit.bind("<Button-1>", self.tikla)
        CardView(sim, self.engine, self.bus).grid(row=0, column=1, sticky="new", padx=(0, 10), pady=10)

        panel = ttk.Frame(sim)
        panel.grid(row=1, column=1, sticky="new", padx=(0, 10))
        self.btn = ttk.Button(panel, text="Başlat", command=self.engine.toggle)
        self.btn.grid(row=0, column=0, padx=3, pady=3)
        ttk.Button(panel, text="Sıfırla", command=self.engine.reset).grid(row=0, column=1, padx=3)
        ttk.Button(panel, text="−", width=3, command=lambda: self.engine.hiz_degistir(-1)).grid(row=1, column=0, sticky="e")
        self.hiz_et = ttk.Label(panel, text="1×")
        self.hiz_et.grid(row=1, column=1)
        ttk.Button(panel, text="+", width=3, command=lambda: self.engine.hiz_degistir(1)).grid(row=1, column=2, sticky="w")
        self.secici = ttk.Combobox(panel, state="readonly", values=[p.ad for p in PlanetModel.all()])
        self.secici.current(self.engine.secili)
        self.secici.grid(row=2, column=0, columnspan=3, pady=8, sticky="we")
        self.secici.bind("<<ComboboxSelected>>", lambda e: self.engine.sec(self.secici.current()))

        nb.add(CompareView(nb), text="Karşılaştırma")

        self.bus.on("state", lambda _: self.durum_guncelle())
        self.bus.on("select", lambda i: self.secici.current(i))
        self.root.after(self.FPS_MS, self.dongu)

    def tikla(self, ev):
        i = self.orbit.sec_noktasi(ev.x, ev.y)
        if i is not None:
            self.engine.sec(i)

    def durum_guncelle(self):
        self.btn.config(text="Durdur" if self.engine.running else "Başlat")
        self.hiz_et.config(text=f"{self.engine.hiz}×")

    def dongu(self):
        self.engine.step(self.FPS_MS / 1000)
        self.root.after(self.FPS_MS, self.dongu)


if __name__ == "__main__":
    pencere = tk.Tk()
    pencere.title("Samanyolu Gezegenleri Simülasyonu")
    pencere.configure(bg=BG)
    Controller(pencere)
    pencere.mainloop()
