#!/usr/bin/env python3
"""Enable only TL3572 ETH3's active-low U21/P02 power switch; no USB/PHY reset."""
import argparse
import json
from pathlib import Path
import time


DEVICE = "/sys/devices/platform/soc/2c030000.i2c/i2c-1/1-0020"
GPIO_ROOT = Path("/sys/class/gpio")


def discover_gpio(root=GPIO_ROOT, expected_device=DEVICE):
    matches = []
    for chip in root.glob("gpiochip*"):
        if (chip / "label").read_text().strip() != "1-0020":
            continue
        if str((chip / "device").resolve()) != str(Path(expected_device).resolve()):
            raise RuntimeError("U21 is not on the reviewed RK3572 I2C1 controller")
        if int((chip / "ngpio").read_text()) != 16:
            raise RuntimeError("U21 must expose exactly 16 GPIOs")
        matches.append(int((chip / "base").read_text()) + 2)
    if len(matches) != 1:
        raise RuntimeError("expected exactly one U21/1-0020 GPIO controller")
    return matches[0]


def enable_gpio(number, root=GPIO_ROOT):
    line = root / f"gpio{number}"
    exported = False
    if not line.exists():
        # A claimed kernel GPIO cannot be exported: fail, never bypass gpiolib via I2C.
        (root / "export").write_text(str(number))
        exported = True
        deadline = time.monotonic() + 2
        while not line.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
    if not line.exists():
        raise RuntimeError("GPIO export did not create the reviewed line")
    if (line / "active_low").read_text().strip() != "0":
        raise RuntimeError("unexpected active_low; refusing to reinterpret an existing GPIO")
    # 'low' sets output direction and initial physical level atomically, avoiding a glitch.
    # An already enabled line is left entirely alone, including its direction/value files.
    if ((line / "direction").read_text().strip(), (line / "value").read_text().strip()) != ("out", "0"):
        (line / "direction").write_text("low")
    if ((line / "direction").read_text().strip(), (line / "value").read_text().strip()) != ("out", "0"):
        raise RuntimeError("ETH3 power GPIO failed physical-low readback")
    return exported


def eth3_interfaces(net_root=Path("/sys/class/net")):
    return [net.name for net in net_root.iterdir()
            if (net / "device/driver").exists() and (net / "device/driver").resolve().name == "sr9900"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enable", action="store_true", help="explicitly power ETH3; default read-only")
    args = parser.parse_args()
    deadline = time.monotonic() + (15 if args.enable else 0)
    while True:
        try:
            number = discover_gpio()
            break
        except RuntimeError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.2)
    result = dict(mode="enable" if args.enable else "read-only", controller="U21/1-0020",
                  offset=2, global_gpio=number, physical_on=0, usb_or_phy_reset=False)
    if args.enable:
        result["new_export"] = enable_gpio(number)
        deadline = time.monotonic() + 15
        while not eth3_interfaces() and time.monotonic() < deadline:
            time.sleep(0.2)
        result["interfaces"] = eth3_interfaces()
        print(json.dumps(result, sort_keys=True), flush=True)
        if len(result["interfaces"]) != 1:
            raise RuntimeError("power enabled, but exactly one SR9900 interface did not enumerate; no power cycling")
    else:
        result["interfaces"] = eth3_interfaces()
        print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
