"""Gezegen modülleri paketi.
Bu klasöre yeni bir .py dosyası ekleyip içine GEZEGEN sözlüğü yazarsanız
gezegen otomatik olarak simülasyona eklenir."""
import importlib
import pkgutil


def yukle():
    liste = []
    for m in pkgutil.iter_modules(__path__):
        modul = importlib.import_module(f"{__name__}.{m.name}")
        if hasattr(modul, "GEZEGEN"):
            liste.append(modul.GEZEGEN)
    return sorted(liste, key=lambda g: g["au"])
