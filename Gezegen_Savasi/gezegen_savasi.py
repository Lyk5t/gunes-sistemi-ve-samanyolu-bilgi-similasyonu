
from panda3d.core import loadPrcFileData

# Grafik ayarlari Ursina yuklenmeden once uygulanir.
loadPrcFileData("", "background-color 0.01 0.02 0.06 1")
loadPrcFileData("", "framebuffer-srgb false")
loadPrcFileData("", "sync-video false")

from ursina import *
import random

app = Ursina()

window.title = "Samanyolu 3B - Gezegen Savasi"
window.color = color.rgb(5, 8, 22)
window.fps_counter.enabled = True

# ==========================================================
# DURUM VE RENKLER
# ==========================================================

CYAN = color.rgb(0, 220, 255)
BLUE = color.rgb(30, 125, 255)
RED = color.rgb(255, 55, 75)
GOLD = color.rgb(255, 190, 45)
WHITE = color.rgb(235, 242, 255)
DARK = color.rgb(10, 15, 35)
GRAY = color.rgb(130, 150, 180)

planets = []
fleets = []
selected_planet = None
game_over = False
enemy_timer = 0.0

# ==========================================================
# KAMERA
# Testte calisan basit kamera yaklasimi korunuyor.
# ==========================================================

camera.position = (0, 0, -24)
camera.rotation = (0, 0, 0)
camera.fov = 70

# ==========================================================
# ARKA PLAN YILDIZLARI
# Kamera onunde degil, sahnenin icinde.
# ==========================================================

random.seed(12)

for _ in range(180):
    star = Entity(
        model="sphere",
        position=(
            random.uniform(-23, 23),
            random.uniform(-13, 13),
            random.uniform(8, 35)
        ),
        scale=random.uniform(0.025, 0.07),
        color=random.choice([CYAN, WHITE, BLUE]),
        unlit=True
    )

# ==========================================================
# ARAYUZ
# ==========================================================

Text(
    parent=camera.ui,
    text="SAMANYOLU 3B",
    position=(-0.86, 0.44),
    scale=1.5,
    color=CYAN
)

Text(
    parent=camera.ui,
    text="GEZEGEN SAVASI",
    position=(-0.86, 0.39),
    scale=0.8,
    color=WHITE
)

status_text = Text(
    parent=camera.ui,
    text="Mavi gezegenini sec, sonra hedefe tikla.",
    position=(-0.86, -0.45),
    scale=0.8,
    color=WHITE
)

Entity(
    parent=camera.ui,
    model="quad",
    position=(0.73, 0.05),
    scale=(0.48, 0.80),
    color=DARK,
    z=1
)

Text(
    parent=camera.ui,
    text="KOMUTA MERKEZI",
    position=(0.53, 0.40),
    scale=0.9,
    color=CYAN
)

Text(
    parent=camera.ui,
    text="Gonderilecek filo yuzdesi",
    position=(0.53, 0.31),
    scale=0.65,
    color=WHITE
)

fleet_slider = Slider(
    parent=camera.ui,
    min=10,
    max=90,
    default=50,
    step=10,
    position=(0.72, 0.24),
    scale=0.34
)

fleet_text = Text(
    parent=camera.ui,
    text="Filo: %50",
    position=(0.53, 0.18),
    scale=0.8,
    color=GOLD
)

Text(
    parent=camera.ui,
    text="NASIL OYNANIR?",
    position=(0.53, 0.08),
    scale=0.8,
    color=CYAN
)

Text(
    parent=camera.ui,
    text=(
        "1. Mavi gezegene tikla.\n"
        "2. Hedef gezegene tikla.\n"
        "3. Filo otomatik yola cikar.\n\n"
        "Mavi: Senin\n"
        "Kirmizi: Dusman\n"
        "Altin: Tarafsiz\n\n"
        "Fare tekerlegi: Zoom\n"
        "ESC: Cikis"
    ),
    position=(0.53, 0.02),
    scale=0.65,
    color=WHITE,
    line_height=1.4
)

# ==========================================================
# YARDIMCI FONKSIYONLAR
# ==========================================================

def set_status(message, tint=WHITE):
    status_text.text = message
    status_text.color = tint


def get_planet_color(owner, strength):
    factor = max(0.22, min(1.0, strength / 100))

    if owner == "player":
        base = (25, 155, 255)
    elif owner == "enemy":
        base = (255, 45, 75)
    else:
        base = (255, 180, 35)

    return color.rgb(
        int(base[0] * factor),
        int(base[1] * factor),
        int(base[2] * factor)
    )


def distance_between(a, b):
    return (a.position - b.position).length()


# ==========================================================
# GEZEGEN
# ==========================================================

class Planet(Entity):
    def __init__(self, name, pos, owner, strength, radius):
        super().__init__(
            model="sphere",
            position=pos,
            scale=radius,
            color=get_planet_color(owner, strength),
            collider="sphere",
            unlit=True
        )

        self.planet_name = name
        self.owner = owner
        self.strength = strength
        self.radius = radius

        self.label = Text(
            parent=self,
            text="",
            position=(0, 1.5, 0),
            origin=(0, 0),
            scale=3,
            billboard=True,
            color=WHITE
        )

        # Basit, parlak secim halkasi yerine ikinci bir kure
        self.marker = Entity(
            parent=self,
            model="sphere",
            scale=1.18,
            color=color.rgba(0, 220, 255, 80),
            unlit=True,
            enabled=False
        )

        # Marker gezegenin arkasinda durur.
        self.marker.z = 0.08

        self.refresh()

    def refresh(self):
        self.strength = max(0, min(100, self.strength))
        self.color = get_planet_color(self.owner, self.strength)

        self.label.text = (
            self.planet_name + "\nGuc: " + str(int(self.strength))
        )

        if self.owner == "player":
            self.label.color = CYAN
        elif self.owner == "enemy":
            self.label.color = RED
        else:
            self.label.color = GOLD

    def on_click(self):
        global selected_planet

        if game_over:
            return

        if self.owner == "player":
            if selected_planet is not None:
                selected_planet.marker.enabled = False

            selected_planet = self
            self.marker.enabled = True
            set_status(
                self.planet_name + " secildi. Simdi hedefi sec.",
                CYAN
            )
            return

        if selected_planet is not None:
            launch_fleet(selected_planet, self)


# ==========================================================
# FILO
# ==========================================================

class Fleet(Entity):
    def __init__(self, source, target, owner, amount):
        super().__init__(
            model="sphere",
            position=source.position + Vec3(0, 0.35, 0),
            scale=0.22,
            color=CYAN if owner == "player" else RED,
            unlit=True
        )

        self.source = source
        self.target = target
        self.owner = owner
        self.amount = amount
        self.speed = 5 if owner == "player" else 3.5

    def update(self):
        if game_over:
            return

        if not self.target or not self.target.enabled:
            destroy(self)
            return

        direction = self.target.position - self.position
        distance = direction.length()

        if distance <= self.target.radius + 0.25:
            self.arrive()
            return

        if distance > 0:
            self.position += direction.normalized() * self.speed * time.dt

    def arrive(self):
        target = self.target

        if target.owner == self.owner:
            target.strength = min(100, target.strength + self.amount)
        else:
            target.strength -= self.amount

            if target.strength <= 0:
                target.owner = self.owner
                target.strength = max(10, abs(target.strength))

                if self.owner == "player":
                    set_status(
                        target.planet_name + " ele gecirildi!",
                        CYAN
                    )
                else:
                    set_status(
                        target.planet_name + " dusmana gecti!",
                        RED
                    )

        target.refresh()
        destroy(self)
        check_game_over()


# ==========================================================
# FILO GONDERME
# ==========================================================

def launch_fleet(source, target):
    global selected_planet

    if game_over or source is None or target is None:
        return

    if source == target:
        set_status("Ayni gezegene saldiri yapilamaz.", GOLD)
        return

    if source.owner != "player":
        set_status("Kendi gezegenini secmelisin.", RED)
        return

    amount = int(source.strength * int(fleet_slider.value) / 100)

    if amount < 1:
        set_status("Gonderilecek filo yetersiz.", GOLD)
        return

    source.strength -= amount
    source.refresh()

    fleets.append(Fleet(source, target, "player", amount))

    set_status(
        source.planet_name + " -> " + target.planet_name
        + " | Filo: " + str(amount),
        CYAN
    )

    if selected_planet is not None:
        selected_planet.marker.enabled = False

    selected_planet = None


# ==========================================================
# DUSMAN YAPAY ZEKASI
# ==========================================================

def enemy_turn():
    if game_over:
        return

    enemies = [p for p in planets if p.owner == "enemy"]

    for enemy in enemies:
        if enemy.strength < 25:
            continue

        targets = [
            p for p in planets
            if p.owner in ("player", "neutral")
        ]

        if not targets:
            return

        target = min(
            targets,
            key=lambda p: distance_between(enemy, p)
        )

        amount = max(1, int(enemy.strength * 0.25))
        enemy.strength -= amount
        enemy.refresh()

        fleets.append(Fleet(enemy, target, "enemy", amount))


# ==========================================================
# OYUN BITIS KONTROLU
# ==========================================================

def check_game_over():
    global game_over

    if game_over:
        return

    player_planets = [p for p in planets if p.owner == "player"]
    enemy_planets = [p for p in planets if p.owner == "enemy"]

    if not enemy_planets:
        game_over = True
        set_status("ZAFER! Galaksiyi ele gecirdin!", GOLD)

    elif not player_planets:
        game_over = True
        set_status("YENILGI! Butun gezegenlerini kaybettin.", RED)


# ==========================================================
# GEZEGENLERI OLUSTUR
# ==========================================================

planet_data = [
    ("DUNYA", (-8, 3, 0), "player", 100, 1.20),
    ("MARS", (-3, -2, 0), "neutral", 50, 0.85),
    ("VENUS", (2, 3, 0), "neutral", 40, 0.90),
    ("JUPITER", (7, -1, 0), "enemy", 100, 1.35),
    ("SATURN", (10, 4, 0), "enemy", 70, 1.00),
    ("NEPTUN", (-11, -3, 0), "neutral", 35, 0.80),
    ("KEPLER", (0, -5, 0), "neutral", 45, 0.95)
]

for name, pos, owner, strength, radius in planet_data:
    planets.append(Planet(name, pos, owner, strength, radius))


# ==========================================================
# OYUN DONGUSU
# ==========================================================

def update():
    global enemy_timer

    fleet_text.text = "Filo: %" + str(int(fleet_slider.value))

    if game_over:
        return

    enemy_timer += time.dt

    if enemy_timer >= 9:
        enemy_timer = 0
        enemy_turn()

    fleets[:] = [f for f in fleets if f and f.enabled]


# ==========================================================
# KONTROLLER
# ==========================================================

def input(key):
    if key == "scroll up":
        camera.position += camera.forward * 1.5

    elif key == "scroll down":
        camera.position -= camera.forward * 1.5

    elif key == "escape":
        application.quit()

# GECICI GORUNTU TESTI
debug_planet = Entity(
    model="sphere",
    position=(0, 0, 0),
    scale=3,
    color=color.red,
    unlit=True
)

debug_planet.name = "TEST_GEZEGENI"

app.run()
