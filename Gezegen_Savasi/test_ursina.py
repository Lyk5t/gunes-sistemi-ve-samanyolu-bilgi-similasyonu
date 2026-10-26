
from panda3d.core import loadPrcFileData

loadPrcFileData("", "background-color 0.01 0.02 0.06 1")
loadPrcFileData("", "framebuffer-srgb false")
loadPrcFileData("", "sync-video false")
loadPrcFileData("", "show-frame-rate-meter true")

from ursina import *

app = Ursina()

window.title = "Panda3D Grafik Kontrolu"
window.color = color.rgb(5, 8, 22)

camera.position = (0, 0, -12)
camera.rotation = (0, 0, 0)

Entity(
    model="sphere",
    position=(-3, 0, 0),
    scale=2,
    color=color.red,
    unlit=True
)

Entity(
    model="sphere",
    position=(0, 0, 0),
    scale=2,
    color=color.azure,
    unlit=True
)

Entity(
    model="sphere",
    position=(3, 0, 0),
    scale=2,
    color=color.lime,
    unlit=True
)

Text(
    text="GRAFIK TESTI",
    position=(-0.25, 0.4),
    scale=1.5,
    color=color.white
)

app.run()
