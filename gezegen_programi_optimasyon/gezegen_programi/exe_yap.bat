@echo off
python -m pip install pyinstaller ursina
set EKLE=
if exist bozok_logo.png set EKLE=--add-data "bozok_logo.png;."
pyinstaller --noconfirm --onedir --windowed --name GezegenLab --collect-all ursina --collect-all panda3d --collect-submodules gezegenler %EKLE% main.py
if exist version.txt copy /Y version.txt dist\GezegenLab\version.txt
echo Program: dist\GezegenLab\GezegenLab.exe
pause
