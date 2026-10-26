
from ursina import *

app = Ursina()

window.title = "Gezegen Savasi - Goruntu Testi"
window.color = color.black

camera.position = (0, 0, -20)
camera.rotation = (0, 0, 0)
camera.fov = 60

Entity(
    model="sphere",
    position=(-4, 0, 0),
    scale=2,
    color=color.red,
    unlit=True
)

Entity(
    model="sphere",
    position=(0, 0, 0),
    scale=2,
    color=color.green,
    unlit=True
)

Entity(
    model="sphere",
    position=(4, 0, 0),
    scale=2,
    color=color.azure,
    unlit=True
)

Text(
    text="GORUNTU TESTI",
    position=(-0.15, 0.4),
    scale=2,
    color=color.white
)

app.run()
