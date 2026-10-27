@echo off
REM Build the Windows app folder. Run from the repo root in an activated venv:
REM   .venv\Scripts\activate
REM   packaging\build_exe.bat
python -m pip install pyinstaller
python -m PyInstaller packaging\shearwall.spec --noconfirm --distpath dist --workpath build
echo.
echo Done. Run dist\ShearWallStack\ShearWallStack.exe  (keep the whole folder together)
