@echo off
REM Programın Adı: Samanyolu Gezegenleri Simülasyonu
REM Windows Batch File
REM Geliştirici: Oğuzhan Öcal
REM Tarih: 09.11.2026
REM Sürüm: 1.0
REM Açıklama: 3 boyutlu gezegen simülasyonu

chcp 65001 >nul
setlocal
title Samanyolu ve Gunes Sistemi Simulasyonu

echo.
echo ==========================================
echo   SAMANYOLU VE GUNES SISTEMI SIMULASYONU
echo ==========================================
echo.

REM Python kontrolu
python --version >nul 2>&1
if errorlevel 1 (
    echo HATA: Python bulunamadi veya PATH'e eklenmemis.
    echo Lutfen Python kurulumunu kontrol edin.
    pause
    exit /b 1
)

REM Ursina kurulu mu kontrol et
python -c "import ursina" >nul 2>&1
if errorlevel 1 (
    echo Ursina kurulu degil.
    echo Ursina yukleniyor, lutfen bekleyin...
    echo.

    REM requirements.txt varsa proje bagimliliklarini kur
    if exist "requirements.txt" (
        python -m pip install -r requirements.txt
    ) else (
        python -m pip install ursina
    )

    REM Kurulum basarili mi tekrar kontrol et
    python -c "import ursina" >nul 2>&1
    if errorlevel 1 (
        echo.
        echo HATA: Ursina yuklenemedi.
        echo Internet baglantinizi ve Python pip kurulumunu kontrol edin.
        pause
        exit /b 1
    )

    echo.
    echo Ursina basariyla yuklendi.
) else (
    echo Ursina zaten yuklu. Kurulum atlandi.
)

echo.
echo Simulasyon baslatiliyor...
echo.

if not exist "main.py" (
    echo HATA: main.py dosyasi bulunamadi.
    echo Bu BAT dosyasini proje ana klasorunde calistirin.
    pause
    exit /b 1
)

python main.py

if errorlevel 1 (
    echo.
    echo Program bir hata nedeniyle kapandi.
    pause
)

endlocal
