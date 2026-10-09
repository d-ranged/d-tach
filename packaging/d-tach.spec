# PyInstaller spec for the packaged d-tach: a onedir build on Windows, a .app on macOS.
#
# Build from the repo root, in a venv with requirements.txt and
# packaging/requirements-build.txt installed:
#
#   pyinstaller packaging/d-tach.spec --noconfirm
#
# Output: dist/d-tach/ with d-tach.exe on Windows, dist/d-tach.app on macOS.
# Language models are not bundled; d-tach downloads them into the per-user folder.
# GitHub Actions runs the same command, see .github/workflows/build.yml.

import os
import re
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

REPO_ROOT = Path(SPECPATH).parent
PACKAGING_DIR = Path(SPECPATH)
APP_NAME = "d-tach"
BUNDLE_IDENTIFIER = "org.d-ranged.d-tach"

# Packages whose data files, binaries and lazily imported submodules PyInstaller
# does not find on its own (spaCy's registries, Presidio's recognizers, the
# phone number metadata, langdetect's profiles, tldextract's suffix list).
COLLECT_ALL = [
    "spacy",
    "thinc",
    "presidio_analyzer",
    "presidio_anonymizer",
    "langdetect",
    "tldextract",
    "phonenumbers",
]
# Test suites that collect_all drags in with the packages above. Not needed to run.
EXCLUDES = ["pytest", "_pytest", "spacy.tests", "thinc.tests"]
TRAY_BACKENDS = {"win32": "pystray._win32", "darwin": "pystray._darwin"}


def read_version() -> str:
    """Return __version__ from app/__init__.py without importing the app."""
    source = (REPO_ROOT / "app" / "__init__.py").read_text(encoding="utf-8")
    return re.search(r'^__version__ = "([^"]+)"', source, re.MULTILINE).group(1)


def point_tk_at_tcl() -> None:
    """Set TCL_LIBRARY and TK_LIBRARY when Python does not, so tkinter is bundled.

    pyenv-win ships Tcl under <base_prefix>/tcl without telling Tk, and
    PyInstaller then drops tkinter as broken. Same idea as app/tcl_support.py.
    """
    tcl_root = Path(sys.base_prefix) / "tcl"
    if sys.platform != "win32" or not tcl_root.is_dir():
        return
    for var, prefix in (("TCL_LIBRARY", "tcl"), ("TK_LIBRARY", "tk")):
        candidates = sorted(
            d for d in tcl_root.iterdir()
            if d.is_dir() and d.name.startswith(prefix) and d.name[len(prefix):len(prefix) + 1].isdigit()
        )
        if candidates and not os.environ.get(var):
            os.environ[var] = str(candidates[-1])


def check_images_are_real() -> None:
    """Stop the build if the PNGs are Git LFS pointer files, not images.

    A checkout without LFS still builds, but the tray icon then fails to load
    and d-tach crashes on start.
    """
    for image in (REPO_ROOT / "app" / "static").glob("*.png"):
        if not image.read_bytes().startswith(PNG_SIGNATURE):
            raise SystemExit(f"{image} is not a PNG, likely a Git LFS pointer. Run: git lfs pull")


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

point_tk_at_tcl()
check_images_are_real()
VERSION = read_version()

datas = [
    (str(REPO_ROOT / "app" / "templates"), "app/templates"),
    (str(REPO_ROOT / "app" / "static"), "app/static"),
    (str(REPO_ROOT / "app" / "data"), "app/data"),
]
binaries = []
hiddenimports = collect_submodules("app")
if sys.platform in TRAY_BACKENDS:
    hiddenimports.append(TRAY_BACKENDS[sys.platform])

for package in COLLECT_ALL:
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += [name for name in package_hiddenimports if not name.startswith(tuple(EXCLUDES))]

a = Analysis(
    [str(REPO_ROOT / "tray.py")],
    pathex=[str(REPO_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=EXCLUDES,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    console=False,
    icon=str(PACKAGING_DIR / ("d-tach.icns" if sys.platform == "darwin" else "d-tach.ico")),
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name=APP_NAME, upx=False)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=str(PACKAGING_DIR / "d-tach.icns"),
        bundle_identifier=BUNDLE_IDENTIFIER,
        version=VERSION,
        info_plist={
            "CFBundleDisplayName": APP_NAME,
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "12.0",
        },
    )
