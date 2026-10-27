# PyInstaller spec. Build from the repo root:  pyinstaller packaging/shearwall.spec --noconfirm
# Produces dist/ShearWallStack/ShearWallStack(.exe). Build on the OS you will run it on (Windows build on Windows).
import os
from PyInstaller.utils.hooks import collect_all, copy_metadata

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))   # repo root (SPECPATH = this file's folder)
R = lambda *p: os.path.join(ROOT, *p)

datas = [
    (R("src", "ui"), "src/ui"),
    (R("src", "design"), "src/design"),          # includes components/data/*.csv
    (R("src", "analysis"), "src/analysis"),
    (R("tests", "woodworks_example.py"), "tests"),
    (R("tests", "fixtures", "woodworks_components"), "tests/fixtures/woodworks_components"),
    (R("presets"), "presets"),
]
binaries, hiddenimports = [], []
for pkg in ("streamlit",):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h
datas += copy_metadata("streamlit") + copy_metadata("pandas") + copy_metadata("numpy")
hiddenimports += ["design", "analysis", "ui", "woodworks_example"]

a = Analysis(
    [R("packaging", "launcher.py")],
    pathex=[R("src"), R("tests")],
    datas=datas, binaries=binaries, hiddenimports=hiddenimports,
    excludes=["openseespy", "scipy", "matplotlib", "pytest", "tkinter"],  # not used by the app
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ShearWallStack", console=True)  # console shows the server log
coll = COLLECT(exe, a.binaries, a.datas, name="ShearWallStack")
