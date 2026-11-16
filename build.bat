@echo off
rem Compila TOMATE77K en tu PC con Nuitka (opcional: el robot de GitHub ya lo hace solo).
rem Queda en dist\launcher.dist\TOMATE77K.exe (hay que mantener la carpeta completa).
rem La primera vez Nuitka puede pedir descargar un compilador de C: acepta (yes).
setlocal
cd /d "%~dp0"

python -m pip install -r requirements.txt nuitka ordered-set zstandard || goto :error
python -m nuitka --standalone --assume-yes-for-downloads --windows-console-mode=disable --enable-plugin=pyside6 --include-qt-plugins=platforms,styles,imageformats --windows-icon-from-ico=icon.ico --include-data-files=icon.ico=icon.ico --include-data-dir=fonts=fonts --include-package=minecraft_launcher_lib --include-package-data=certifi --include-package-data=minecraft_launcher_lib --company-name=Tomate77K --product-name=TOMATE77K --file-description=TOMATE77K --output-filename=TOMATE77K.exe --output-dir=dist launcher.py || goto :error

echo.
echo Listo. Tu app esta en: dist\launcher.dist\TOMATE77K.exe
pause
exit /b 0

:error
echo.
echo Algo fallo. Copia el mensaje de arriba y pasamelo.
pause
exit /b 1