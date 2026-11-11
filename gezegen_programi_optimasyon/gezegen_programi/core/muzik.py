"""Program genelinde dongulu arka plan muzigi yonetimi (Panda3D/Ursina).

Suno cikti dosyanizi assets klasorune kopyalayin. Tercih edilen adlar:
  uzay_muzigi.mp3, uzay_muzigi.ogg veya uzay_muzigi.wav
"""
import os


class ArkaPlanMuzigi:
    DOSYA_ADLARI = (
        "uzay_muzigi.ogg", "uzay_muzigi.mp3", "uzay_muzigi.wav",
        "muzik.ogg", "muzik.mp3", "muzik.wav",
    )

    def __init__(self, assets_klasoru, ses_seviyesi=0.35):
        self.assets_klasoru = assets_klasoru
        self.ses_seviyesi = max(0.0, min(1.0, float(ses_seviyesi)))
        self.ses = None
        self.acik = True
        self.yuklendi = False
        self.yol = self._dosya_bul()

    def _dosya_bul(self):
        for ad in self.DOSYA_ADLARI:
            yol = os.path.join(self.assets_klasoru, ad)
            if os.path.isfile(yol):
                return yol
        return None

    def baslat(self):
        """Dosya varsa tek sefer yukler ve dongulu olarak calistirir."""
        if self.yuklendi:
            if self.acik and self.ses and not self.ses.status():
                self.ses.play()
            return bool(self.ses)
        self.yuklendi = True
        if not self.yol:
            print("[MUZIK] Dosya bulunamadi. assets/uzay_muzigi.mp3 ekleyin.")
            return False
        try:
            from panda3d.core import Filename
            from ursina import application
            self.ses = application.base.loader.loadMusic(
                Filename.fromOsSpecific(os.path.abspath(self.yol))
            )
            if self.ses is None:
                raise RuntimeError("Ses dosyasi yuklenemedi")
            self.ses.setLoop(True)
            self.ses.setVolume(self.ses_seviyesi)
            if self.acik and self.ses_seviyesi > 0:
                self.ses.play()
            print("[MUZIK] Arka plan muzigi hazir:", os.path.basename(self.yol))
            return True
        except Exception as hata:
            self.ses = None
            print("[MUZIK] Muzik baslatilamadi:", hata)
            return False

    def ses_ayarla(self, seviye):
        self.ses_seviyesi = max(0.0, min(1.0, float(seviye)))
        if self.ses:
            self.ses.setVolume(self.ses_seviyesi)
            if self.acik and self.ses_seviyesi > 0 and not self.ses.status():
                self.ses.play()
            elif self.ses_seviyesi <= 0:
                self.ses.stop()

    def degistir(self):
        self.acik = not self.acik
        if self.ses:
            if self.acik and self.ses_seviyesi > 0:
                self.ses.play()
            else:
                self.ses.stop()
        elif self.acik:
            self.baslat()
        return self.acik

    def durdur(self):
        if self.ses:
            self.ses.stop()
