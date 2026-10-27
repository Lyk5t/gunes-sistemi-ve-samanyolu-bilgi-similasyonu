"""Ses üretimi: patlama sesini matematikle sentezler, dışarıdan ses dosyası gerekmez."""
import math
import os
import random
import struct
import wave


def patlama_uret(yol, sure=5.0, sr=22050):
    """Alçak frekanslı gümbürtü + çatlama + sönen gürültüden oluşan patlama sesi (WAV)."""
    R = random.Random(3)
    n = int(sure * sr)
    ornek, faz, lp, lp2 = [], 0.0, 0.0, 0.0
    for i in range(n):
        t = i / sr
        f = 26 + 74 * math.exp(-t * 3.0)                 # frekans hızla düşer: "büüm"
        faz += 2 * math.pi * f / sr
        gumbur = math.sin(faz) * math.exp(-t * 0.9)
        g = R.uniform(-1, 1)
        k = 0.015 + 0.55 * math.exp(-t * 4.5)            # başta parlak, sonra boğuk gürültü
        lp += k * (g - lp)
        lp2 += k * (lp - lp2)
        gurultu = lp2 * math.exp(-t * 1.3) * 7.0
        catlama = g * math.exp(-t * 35) * 0.9            # ilk çatlama
        v = 0.95 * gumbur + gurultu + catlama
        if t > sure - 0.6:                                # sonda yumuşak kapanış
            v *= max(0.0, (sure - t) / 0.6)
        ornek.append(math.tanh(v * 1.5))
    tepe = max(abs(x) for x in ornek) or 1.0
    with wave.open(yol, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"".join(struct.pack("<h", int(x / tepe * 0.85 * 32767)) for x in ornek))
    return yol


def patlama_yolu():
    klasor = os.path.dirname(os.path.abspath(__file__))
    yol = os.path.join(klasor, "patlama.wav")
    if not os.path.exists(yol):
        try:
            patlama_uret(yol)
        except OSError:
            import tempfile
            yol = patlama_uret(os.path.join(tempfile.gettempdir(), "gezegenlab_patlama.wav"))
    return yol
