#!/usr/bin/env python3
"""Read-only CAN1/CAN3 resource snapshot before UP clock/IRQ bring-up.

Offsets come from the archived RK3572 kernel, not RK3576 CRU/IOC tables.
This script never reads the destructive CAN RX FIFO or writes MMIO/sysfs.
GIC banked registers are deliberately omitted: Linux cannot identify the
offline UP CPU target masks by reading its own banked ITARGETSR registers.
"""

import json
import mmap
import os
from pathlib import Path
import struct
import subprocess
from datetime import datetime, timezone


CRU = 0x26090000
IOC = 0x26072000
GICD = 0x2A601000
RESOURCES = {
    "can1": {
        "device": "2ab10000.can", "owner": "UP1/CPU4", "spi": 153,
        "gate_bits": (9, 10), "clksel": CRU + 0x404,
        "iomux": IOC + 0x1408C, "iomux_mask": 0xFF00, "iomux_value": 0xDD00,
    },
    "can3": {
        "device": "2ab30000.can", "owner": "UP2/CPU5", "spi": 155,
        "gate_bits": (13, 14), "clksel": CRU + 0x408,
        "iomux": IOC + 0x1003C, "iomux_mask": 0x0FF0, "iomux_value": 0x0DD0,
    },
}


def gic_addresses(intid):
    if not 32 <= intid < 384:
        raise ValueError("expected an RK3572 SPI INTID")
    word = (intid // 32) * 4
    byte = intid & ~3
    return {
        "group": GICD + 0x80 + word,
        "enabled": GICD + 0x100 + word,
        "pending": GICD + 0x200 + word,
        "active": GICD + 0x300 + word,
        "priority": GICD + 0x400 + byte,
        "target": GICD + 0x800 + byte,
        "config": GICD + 0xC00 + (intid // 16) * 4,
    }


def decode_resource(profile, values):
    intid = profile["spi"] + 32
    gic = gic_addresses(intid)
    bit = 1 << (intid % 32)
    byte_shift = (intid % 4) * 8
    gate = values[CRU + 0x82C]
    reset = values[CRU + 0xA2C]
    select = values[profile["clksel"]]
    mux = values[profile["iomux"]]
    bus_bit, can_bit = profile["gate_bits"]
    return {
        "owner": profile["owner"], "spi": profile["spi"], "intid": intid,
        "hclk_gated": bool(gate & (1 << bus_bit)),
        "baudclk_gated": bool(gate & (1 << can_bit)),
        "hclk_reset_asserted": bool(reset & (1 << bus_bit)),
        "can_reset_asserted": bool(reset & (1 << can_bit)),
        "clock_parent_selector": (select >> 12) & 3,
        "clock_divider": ((select >> 7) & 31) + 1,
        "pinmux_matches_live_dt": (mux & profile["iomux_mask"]) == profile["iomux_value"],
        "gic_igroupr_bit_observed": bool(values[gic["group"]] & bit),
        "gic_enabled": bool(values[gic["enabled"]] & bit),
        "gic_pending": bool(values[gic["pending"]] & bit),
        "gic_active": bool(values[gic["active"]] & bit),
        "gic_priority": (values[gic["priority"]] >> byte_shift) & 0xFF,
        "gic_target_mask": (values[gic["target"]] >> byte_shift) & 0xFF,
        "gic_edge_triggered": bool(values[gic["config"]] & (2 << ((intid % 16) * 2))),
    }


def read_registers():
    addresses = {CRU + 0x82C, CRU + 0xA2C}
    for profile in RESOURCES.values():
        addresses.update((profile["clksel"], profile["iomux"]))
        addresses.update(gic_addresses(profile["spi"] + 32).values())
    values = {}
    descriptor = os.open("/dev/mem", os.O_RDONLY | os.O_SYNC)
    try:
        for page in sorted({address & ~(mmap.PAGESIZE - 1) for address in addresses}):
            with mmap.mmap(descriptor, mmap.PAGESIZE, flags=mmap.MAP_SHARED,
                           prot=mmap.PROT_READ, offset=page) as region:
                for address in sorted(addresses):
                    if address & ~(mmap.PAGESIZE - 1) == page:
                        values[address] = struct.unpack_from("<I", region, address - page)[0]
    finally:
        os.close(descriptor)
    return values


def command(*args):
    result = subprocess.run(args, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=10, check=False)
    if result.returncode:
        raise RuntimeError(f"{args}: {result.stdout.strip()}")
    return result.stdout.strip()


def main():
    if os.geteuid() != 0:
        raise SystemExit("run as root")
    if mmap.PAGESIZE != 4096:
        raise SystemExit("this snapshot script expects the baseline 4 KiB pages")
    values = read_registers()
    controllers = {}
    for interface, profile in RESOURCES.items():
        device = Path("/sys/bus/platform/devices") / profile["device"]
        controllers[interface] = decode_resource(profile, values)
        controllers[interface]["linux_driver"] = (
            (device / "driver").resolve().name if (device / "driver").exists() else None)
        controllers[interface]["net_interfaces"] = (
            sorted(path.name for path in (device / "net").iterdir())
            if (device / "net").exists() else [])
    clocks = Path("/sys/kernel/debug/clk/clk_summary").read_text()
    snapshot = {
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "read-only; no CAN traffic, unbind, clock/reset or GIC writes",
        "kernel": command("uname", "-r"),
        "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        "cpu_online": Path("/sys/devices/system/cpu/online").read_text().strip(),
        "cpu_offline": Path("/sys/devices/system/cpu/offline").read_text().strip(),
        "mcs_status": command("mcsctl", "status"),
        "micad": command("systemctl", "show", "micad", "-p", "MainPID",
                         "-p", "ActiveState", "-p", "NRestarts"),
        "links": command("ip", "-brief", "link"),
        "clocks": [line.strip() for line in clocks.splitlines()
                   if line.split() and line.split()[0] in
                   {"clk_can1", "hclk_can1", "clk_can3", "hclk_can3", "gpll", "cpll"}],
        "registers": {f"0x{address:08x}": f"0x{value:08x}"
                      for address, value in sorted(values.items())},
        "controllers": controllers,
        "not_verified": ["UP CPU GIC target masks", "GIC security-group visibility",
                         "UP autonomous initialization",
                         "UP CAN interrupt delivery", "persistent DT handoff"],
    }
    print(json.dumps(snapshot, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
