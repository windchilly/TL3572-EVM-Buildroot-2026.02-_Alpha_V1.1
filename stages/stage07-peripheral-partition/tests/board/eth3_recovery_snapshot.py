#!/usr/bin/env python3
"""Read-only evidence for ETH3 power recovery and untouched management resources."""
import json
from pathlib import Path
import subprocess
import time


def command(*args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=10)
    return dict(argv=args, rc=result.returncode, stdout=result.stdout, stderr=result.stderr)


def snapshot():
    gpio = Path("/sys/class/gpio")
    chips = {}
    for chip in gpio.glob("gpiochip*"):
        if (chip / "label").read_text().strip() in ("1-0020", "1-0021"):
            chips[chip.name] = dict(label=(chip / "label").read_text().strip(),
                                   base=int((chip / "base").read_text()),
                                   device=str((chip / "device").resolve()))
    net = {}
    for port in Path("/sys/class/net").iterdir():
        if port.name.startswith("can") or port.name == "lo":
            continue
        net[port.name] = dict(device=str((port / "device").resolve()),
                             driver=(port / "device/driver").resolve().name)
        for name in ("address", "operstate", "carrier", "speed", "duplex"):
            try:
                net[port.name][name] = (port / name).read_text().strip()
            except OSError as error:
                net[port.name][name] = str(error)
        net[port.name]["statistics"] = {
            name: int((port / "statistics" / name).read_text())
            for name in ("rx_packets", "tx_packets", "rx_bytes", "tx_bytes", "rx_errors", "tx_errors", "rx_dropped", "tx_dropped")
        }
    return dict(utc_epoch=time.time(),
                boot_id=Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
                gpiochips=chips, gpio_debug=Path("/sys/kernel/debug/gpio").read_text(),
                networks=net,
                commands=[command(*args) for args in (
                    ("lsusb",), ("lsusb", "-t"), ("ip", "-br", "address"), ("ip", "route"),
                    ("systemctl", "show", "micad", "--property=MainPID,NRestarts,ActiveState"),
                    ("mcsctl", "status"), ("findmnt", "-rn", "-o", "SOURCE,TARGET,FSTYPE"),
                    ("ethtool", "eth1"),
                    ("ethtool", "eth2"),
                    ("ethtool", "-i", "eth2"),
                    ("systemctl", "show", "m7-eth3-power.service", "--property=LoadState,ActiveState,SubState,Result,ExecMainStatus"),
                    ("systemctl", "is-enabled", "m7-eth3-power.service"),
                )])


if __name__ == "__main__":
    print(json.dumps(snapshot(), indent=2))
