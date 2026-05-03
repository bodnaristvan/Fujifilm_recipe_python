"""Build a portable Windows executable distribution for FujiRecipe.

The app is a PyQt6 desktop program with bundled recipe JSON/JPG data and USB
access through pyusb.  This script builds a PyInstaller ``onedir`` package by
default because the app writes user-created recipes under ``recipes/user``;
that data would be temporary and lost after exit in a normal one-file build.

Usage:
    python build_exe.py
    python build_exe.py --clean
    python build_exe.py --onefile
    python build_exe.py --installer
    python build_exe.py --diagnostics

Outputs:
    dist/FujiRecipe/FujiRecipe.exe          portable folder build
    dist/FujiRecipeUSBCheck/FujiRecipeUSBCheck.exe
    installer/FujiRecipeSetup.exe          optional Inno Setup installer
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path


APP_NAME = "FujiRecipe"
ROOT = Path(__file__).resolve().parent
DEFAULT_ICON_SVG = ROOT / "assets" / "app_icon.svg"
DEFAULT_ICON_ICO = ROOT / "assets" / "app_icon.ico"
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
SPEC_DIR = ROOT / "build_spec"
INSTALLER_DIR = ROOT / "installer"


def run(cmd: list[str], *, cwd: Path = ROOT) -> None:
    print("+ " + " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True)


def ensure_pyinstaller(skip_install: bool) -> None:
    if importlib.util.find_spec("PyInstaller") is not None:
        return

    if skip_install:
        raise SystemExit(
            "PyInstaller is not installed. Install it with:\n"
            "  python -m pip install pyinstaller"
        )

    run([sys.executable, "-m", "pip", "install", "pyinstaller>=6.0"])


def data_arg(source: Path, target: str) -> str:
    # PyInstaller uses ';' on Windows and ':' on POSIX for --add-data.
    separator = ";" if os.name == "nt" else ":"
    return f"{source}{separator}{target}"


def add_existing_data(args: list[str]) -> None:
    recipes_builtin = ROOT / "recipes" / "builtin"
    if recipes_builtin.exists():
        args += ["--add-data", data_arg(recipes_builtin, "recipes/builtin")]

    assets = ROOT / "assets"
    if assets.exists():
        args += ["--add-data", data_arg(assets, "assets")]


def add_libusb_support(args: list[str]) -> None:
    """Ask PyInstaller to collect libusb-package when it is installed.

    pyusb still needs a backend DLL at runtime.  The app can use the PyPI
    ``libusb`` package if available; otherwise users must install a Windows USB
    driver/backend separately, as described in the README.
    """
    if importlib.util.find_spec("libusb") is None:
        print(
            "Note: Python package 'libusb' was not found. The EXE can still be "
            "built, but camera USB access will require a libusb backend/driver "
            "on the target machine.",
            flush=True,
        )
        return

    args += [
        "--hidden-import",
        "libusb",
        "--collect-binaries",
        "libusb",
    ]


def ensure_default_icon() -> Path | None:
    if DEFAULT_ICON_ICO.exists():
        return DEFAULT_ICON_ICO
    if not DEFAULT_ICON_SVG.exists():
        return None

    try:
        from PyQt6.QtCore import QSize, Qt
        from PyQt6.QtGui import QGuiApplication, QIcon, QImage, QPainter, QPixmap
        from PyQt6.QtSvg import QSvgRenderer
    except Exception as exc:
        print(f"Warning: could not import Qt SVG tools to create app icon: {exc}", flush=True)
        return None

    app = QGuiApplication.instance() or QGuiApplication([])
    renderer = QSvgRenderer(str(DEFAULT_ICON_SVG))
    if not renderer.isValid():
        print(f"Warning: SVG icon is not valid: {DEFAULT_ICON_SVG}", flush=True)
        return None

    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        image = QImage(size, size, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        icon.addPixmap(QPixmap.fromImage(image))

    DEFAULT_ICON_ICO.parent.mkdir(parents=True, exist_ok=True)
    if not icon.pixmap(QSize(256, 256)).save(str(DEFAULT_ICON_ICO), "ICO"):
        print(f"Warning: could not write icon file: {DEFAULT_ICON_ICO}", flush=True)
        return None
    return DEFAULT_ICON_ICO


def build_exe(args: argparse.Namespace) -> Path:
    ensure_pyinstaller(args.skip_dep_install)

    if args.clean:
        for path in (BUILD_DIR, SPEC_DIR, DIST_DIR / APP_NAME):
            if path.exists():
                shutil.rmtree(path)

    pyinstaller_args = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(ROOT / "main.py"),
        "--name",
        APP_NAME,
        "--noconfirm",
        "--windowed",
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(BUILD_DIR),
        "--specpath",
        str(SPEC_DIR),
        "--paths",
        str(ROOT),
        "--hidden-import",
        "usb.backend.libusb1",
    ]

    pyinstaller_args.append("--onefile" if args.onefile else "--onedir")
    add_existing_data(pyinstaller_args)
    add_libusb_support(pyinstaller_args)

    icon = Path(args.icon).resolve() if args.icon else ensure_default_icon()
    if icon:
        if not icon.exists():
            raise SystemExit(f"Icon file does not exist: {icon}")
        pyinstaller_args += ["--icon", str(icon)]

    run(pyinstaller_args)

    output = (
        DIST_DIR / f"{APP_NAME}.exe"
        if args.onefile
        else DIST_DIR / APP_NAME / f"{APP_NAME}.exe"
    )
    if not output.exists():
        raise SystemExit(f"Build finished, but expected EXE was not found: {output}")

    if args.onefile:
        print(
            "Warning: --onefile builds are convenient, but this app stores "
            "user recipes under its bundled recipes/user path. Prefer the "
            "default portable folder build if user-created recipes must persist.",
            flush=True,
        )

    return output


def build_usb_diagnostics(args: argparse.Namespace) -> Path:
    ensure_pyinstaller(args.skip_dep_install)

    if args.clean:
        for path in (BUILD_DIR / "FujiRecipeUSBCheck", DIST_DIR / "FujiRecipeUSBCheck"):
            if path.exists():
                shutil.rmtree(path)

    pyinstaller_args = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(ROOT / "diagnose_usb.py"),
        "--name",
        "FujiRecipeUSBCheck",
        "--noconfirm",
        "--console",
        "--onedir",
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(BUILD_DIR),
        "--specpath",
        str(SPEC_DIR),
        "--paths",
        str(ROOT),
        "--hidden-import",
        "usb.backend.libusb1",
    ]
    add_libusb_support(pyinstaller_args)
    run(pyinstaller_args)

    output = DIST_DIR / "FujiRecipeUSBCheck" / "FujiRecipeUSBCheck.exe"
    if not output.exists():
        raise SystemExit(f"Build finished, but expected diagnostic EXE was not found: {output}")
    return output


def find_iscc() -> Path | None:
    candidates = [
        shutil.which("iscc"),
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return Path(candidate)
    return None


def write_inno_script(portable_dir: Path) -> Path:
    INSTALLER_DIR.mkdir(exist_ok=True)
    iss_path = INSTALLER_DIR / f"{APP_NAME}.iss"
    app_version = os.environ.get("FUJIRECIPE_VERSION", "0.1.0")
    source = str(portable_dir / "*")
    output_dir = str(INSTALLER_DIR)

    iss_path.write_text(
        f"""#define MyAppName "{APP_NAME}"
#define MyAppVersion "{app_version}"

[Setup]
AppId={{{{20F8CC88-894C-4E82-A499-BC1515081E46}}}}
AppName={{#MyAppName}}
AppVersion={{#MyAppVersion}}
DefaultDirName={{autopf}}\\{{#MyAppName}}
DefaultGroupName={{#MyAppName}}
DisableProgramGroupPage=yes
OutputDir={output_dir}
OutputBaseFilename={APP_NAME}Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "{source}"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{{group}}\\{{#MyAppName}}"; Filename: "{{app}}\\{APP_NAME}.exe"
Name: "{{autodesktop}}\\{{#MyAppName}}"; Filename: "{{app}}\\{APP_NAME}.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{{app}}\\{APP_NAME}.exe"; Description: "Launch {{#MyAppName}}"; Flags: nowait postinstall skipifsilent
""",
        encoding="utf-8",
    )
    return iss_path


def build_installer(portable_exe: Path) -> None:
    portable_dir = portable_exe.parent
    if portable_dir == DIST_DIR:
        raise SystemExit("Installer generation requires the default --onedir build.")

    iscc = find_iscc()
    if iscc is None:
        raise SystemExit(
            "Inno Setup compiler was not found. Install Inno Setup 6, then rerun:\n"
            "  python build_exe.py --installer"
        )

    iss_path = write_inno_script(portable_dir)
    run([str(iscc), str(iss_path)])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build FujiRecipe for Windows.")
    parser.add_argument("--clean", action="store_true", help="Remove previous build output first.")
    parser.add_argument("--onefile", action="store_true", help="Build a single EXE instead of a portable folder.")
    parser.add_argument("--installer", action="store_true", help="Also build an Inno Setup installer.")
    parser.add_argument("--diagnostics", action="store_true", help="Also build a console USB diagnostic EXE.")
    parser.add_argument("--icon", help="Optional .ico file to use for the EXE.")
    parser.add_argument(
        "--skip-dep-install",
        action="store_true",
        help="Fail instead of installing PyInstaller when it is missing.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.installer and args.onefile:
        raise SystemExit("--installer is intended for the default portable folder build, not --onefile.")

    exe = build_exe(args)
    print(f"Built: {exe}", flush=True)

    if args.diagnostics:
        diag_exe = build_usb_diagnostics(args)
        print(f"USB diagnostics: {diag_exe}", flush=True)

    if args.installer:
        build_installer(exe)
        print(f"Installer: {INSTALLER_DIR / (APP_NAME + 'Setup.exe')}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
