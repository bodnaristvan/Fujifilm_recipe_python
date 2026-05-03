"""Console USB diagnostics for FujiRecipe packaged builds."""

from __future__ import annotations

import sys
from pathlib import Path

import usb.core
import usb.util

from ptp.constants import FUJI_PRODUCT_IDS, FUJI_VENDOR_ID
from ptp.session import FujiCamera
from ptp.transport import PTPTransport


def main() -> int:
    print("FujiRecipe USB diagnostics")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Frozen: {bool(getattr(sys, 'frozen', False))}")
    print(f"Executable: {sys.executable}")
    print(f"_MEIPASS: {getattr(sys, '_MEIPASS', '')}")

    backend = PTPTransport._get_backend()
    print(f"libusb backend: {'OK' if backend is not None else 'NOT FOUND'}")
    if backend is None:
        return 2

    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        dlls = list(Path(frozen_root).rglob("libusb-1.0.dll"))
        print("Packaged libusb DLLs:")
        for dll in dlls:
            print(f"  {dll}")

    print("Known Fujifilm cameras:")
    found_any = False
    for product_id, model in FUJI_PRODUCT_IDS.items():
        try:
            dev = usb.core.find(
                idVendor=FUJI_VENDOR_ID,
                idProduct=product_id,
                backend=backend,
            )
        except Exception as exc:
            print(f"  {model} ({product_id:04X}): error: {type(exc).__name__}: {exc}")
            continue

        if dev is None:
            print(f"  {model} ({product_id:04X}): not visible")
            continue

        found_any = True
        print(f"  {model} ({product_id:04X}): visible")
        try:
            cfg = dev.get_active_configuration()
            print(f"    active configuration: {cfg.bConfigurationValue}")
        except Exception as exc:
            print(f"    configuration error: {type(exc).__name__}: {exc}")
        finally:
            try:
                usb.util.dispose_resources(dev)
            except Exception:
                pass

    if not found_any:
        print(
            "No supported Fujifilm camera is visible through libusb. On Windows, "
            "connect the camera, set the camera USB mode to a PTP/PC mode, and "
            "use Zadig to bind WinUSB to the camera interface."
        )
        return 1

    print("Opening FujiRecipe PTP session:")
    camera = FujiCamera()
    try:
        camera.connect()
        print(f"  connected: {camera.transport.model}")
        slot = camera.read_preset_slot(1)
        print(f"  slot 1 read: {slot.get('name', '')!r}, {len(slot.get('props', []))} props")
    except Exception as exc:
        print(f"  error: {type(exc).__name__}: {exc}")
        return 3
    finally:
        try:
            camera.disconnect()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
