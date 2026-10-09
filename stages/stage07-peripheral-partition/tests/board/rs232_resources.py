#!/usr/bin/env python3
"""RK3572 UART4/8 resource snapshot; never read serial FIFO or write hardware."""
import json
import mmap
import os
from pathlib import Path
import struct

from can_resource_preflight import GICD, gic_addresses
from run_can_direct_pair import command, micad_state

CRU = 0x26090000
RESOURCES = {
    "up-a": dict(device="2c160000.serial", tty="ttyS4", physical="UART4/T4/R4",
                 uart=4, cpu=4, spi=128, p_mask=0x80, s_mask=0x40,
                 s_gate=CRU + 0x83C, s_reset=CRU + 0xA3C, select=CRU + 0x428,
                 mux=0x2607400C, mux_mask=0xFF, mux_value=0x99),
    "up-b": dict(device="2c1a0000.serial", tty="ttyS8", physical="UART3/T3/R3",
                 uart=8, cpu=5, spi=132, p_mask=0x800, s_mask=4,
                 s_gate=CRU + 0x840, s_reset=CRU + 0xA40, select=CRU + 0x438,
                 mux=0x26074010, mux_mask=0xFF0, mux_value=0x990),
}


def owned_masks():
    masks = {CRU + 0x838: 0x880, CRU + 0xA38: 0x880}
    for p in RESOURCES.values():
        masks[p["s_gate"]] = p["s_mask"]
        masks[p["s_reset"]] = p["s_mask"]
        masks[p["select"]] = 0x7FF
        masks[p["mux"]] = p["mux_mask"]
    return masks


def read_registers():
    # Include all UART sources/gates/resets for neighbour-field guards, and shared frac sources.
    addresses = set(owned_masks())
    addresses.update(CRU + 0x300 + n * 4 for n in range(70, 79))
    addresses.update(CRU + 0x800 + n * 4 for n in range(14, 17))
    addresses.update(CRU + 0xA00 + n * 4 for n in range(14, 17))
    addresses.update(CRU + 0x300 + n * 4 for n in range(66, 70))
    for p in RESOURCES.values():
        addresses.update(gic_addresses(p["spi"] + 32).values())
    values = {}
    descriptor = os.open("/dev/mem", os.O_RDONLY | os.O_SYNC)
    try:
        for page in sorted({address & ~(mmap.PAGESIZE - 1) for address in addresses}):
            with mmap.mmap(descriptor, mmap.PAGESIZE, flags=mmap.MAP_SHARED,
                           prot=mmap.PROT_READ, offset=page) as region:
                for address in addresses:
                    if address & ~(mmap.PAGESIZE - 1) == page:
                        values[address] = struct.unpack_from("<I", region, address - page)[0]
    finally:
        os.close(descriptor)
    return values


def decode(p, values):
    intid = p["spi"] + 32
    g = gic_addresses(intid)
    bit = 1 << (intid % 32)
    shift = (intid % 4) * 8
    return dict(uart=p["uart"], cpu=p["cpu"], physical=p["physical"], intid=intid,
                p_gated=bool(values[CRU + 0x838] & p["p_mask"]),
                s_gated=bool(values[p["s_gate"]] & p["s_mask"]),
                p_reset=bool(values[CRU + 0xA38] & p["p_mask"]),
                s_reset=bool(values[p["s_reset"]] & p["s_mask"]),
                source=(values[p["select"]] >> 8) & 7,
                divider=(values[p["select"]] & 255) + 1,
                mux_ok=(values[p["mux"]] & p["mux_mask"]) == p["mux_value"],
                enabled=bool(values[g["enabled"]] & bit),
                pending=bool(values[g["pending"]] & bit), active=bool(values[g["active"]] & bit),
                edge=bool(values[g["config"]] & (2 << (intid % 16 * 2))),
                target=(values[g["target"]] >> shift) & 255,
                priority=(values[g["priority"]] >> shift) & 255)


def snapshot():
    values = read_registers()
    controllers = {}
    for name, p in RESOURCES.items():
        device = Path("/sys/bus/platform/devices") / p["device"]
        controllers[name] = decode(p, values)
        controllers[name]["linux_driver"] = (device / "driver").resolve().name if (device / "driver").exists() else None
    clocks = Path("/sys/kernel/debug/clk/clk_summary").read_text()
    return dict(mode="read-only; no serial FIFO reads, traffic or hardware writes",
                boot_id=Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
                kernel=command("uname", "-r").strip(), micad=micad_state(),
                mcs_status=command("mcsctl", "status"), controllers=controllers,
                clocks=[line.strip() for line in clocks.splitlines() if line.split() and
                        line.split()[0] in {"sclk_uart4", "pclk_uart4", "sclk_uart8", "pclk_uart8", "xin24m"}],
                registers={f"0x{a:08x}": f"0x{v:08x}" for a, v in sorted(values.items())})


if __name__ == "__main__":
    print(json.dumps(snapshot(), indent=2))
