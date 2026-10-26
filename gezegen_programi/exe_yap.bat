@echo off
python -m pip install pyinstaller ursina
pyinstaller --noconfirm --onedir --windowed --name GezegenLab --collect-all ursina --collect-all panda3d --collect-submodules gezegenler main.py
echo Program: dist\GezegenLab\GezegenLab.exe
pause
