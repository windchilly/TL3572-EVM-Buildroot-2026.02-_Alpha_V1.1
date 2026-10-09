#!/usr/bin/env python3
"""Read-only UART1/2 RS485 resource snapshot; no FIFO/GPIO accesses."""
import json
import mmap
import os
from pathlib import Path
import struct

from can_resource_preflight import GICD, gic_addresses
from run_can_direct_pair import command, micad_state

CRU = 0x26090000
PMU = 0x260B0000
RESOURCES = {
    "up-a": dict(device="26500000.serial", tty="ttyS1", physical="manual board UART2/A2/B2",
                 uart=1, cpu=4, spi=125, direction_pin=27,
                 p_gate=PMU + 0x814, p_reset=PMU + 0xA14, p_mask=0x80,
                 s_gate=PMU + 0x814, s_reset=PMU + 0xA14, s_mask=0x40,
                 select=PMU + 0x320, select_mask=3, select_value=1, disabled_select=2,
                 muxes=((0x26074010, 0xF, 9), (0x2607400C, 0xF000, 0x9000),
                        (0x26074018, 0xF000, 0x9000))),
    "up-b": dict(device="2c140000.serial", tty="ttyS2", physical="manual board UART1/A1/B1",
                 uart=2, cpu=5, spi=126, direction_pin=78,
                 p_gate=CRU + 0x838, p_reset=CRU + 0xA38, p_mask=0x20,
                 s_gate=CRU + 0x83C, s_reset=CRU + 0xA3C, s_mask=1,
                 select=CRU + 0x420, select_mask=0x7FF, select_value=0x300, disabled_select=0x30F,
                 muxes=((0x2608404C, 0xFFF, 0xC99),)),
}


def owned_masks():
    masks = {}
    for p in RESOURCES.values():
        for address, mask in ((p["select"], p["select_mask"]),
                              (p["p_reset"], p["p_mask"]), (p["s_reset"], p["s_mask"]),
                              (p["p_gate"], p["p_mask"]), (p["s_gate"], p["s_mask"]),
                              *((a, m) for a, m, _ in p["muxes"])):
            masks[address] = masks.get(address, 0) | mask
    return masks


def read_registers():
    addresses = set(owned_masks())
    # Guard neighbouring UARTs and UART1's unused main-domain parent.
    addresses.update(CRU + 0x300 + n * 4 for n in range(66, 79))
    addresses.update(CRU + 0x800 + n * 4 for n in range(14, 17))
    addresses.update(CRU + 0xA00 + n * 4 for n in range(14, 17))
    addresses.update((CRU + 0x374, CRU + 0x808))
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
    bit, shift = 1 << (intid % 32), (intid % 4) * 8
    selector = values[p["select"]] & p["select_mask"]
    return dict(uart=p["uart"], cpu=p["cpu"], physical=p["physical"], intid=intid,
                p_gated=bool(values[p["p_gate"]] & p["p_mask"]),
                s_gated=bool(values[p["s_gate"]] & p["s_mask"]),
                p_reset=bool(values[p["p_reset"]] & p["p_mask"]),
                s_reset=bool(values[p["s_reset"]] & p["s_mask"]), selector=selector,
                mux_ok=all(values[a] & m == v for a, m, v in p["muxes"]),
                enabled=bool(values[g["enabled"]] & bit), pending=bool(values[g["pending"]] & bit),
                active=bool(values[g["active"]] & bit),
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
    return dict(mode="read-only; no UART FIFO/GPIO reads, traffic or hardware writes",
                boot_id=Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
                kernel=command("uname", "-r").strip(), micad=micad_state(),
                mcs_status=command("mcsctl", "status"), controllers=controllers,
                clocks=[line.strip() for line in clocks.splitlines() if line.split() and
                        line.split()[0] in {"sclk_uart1", "pclk_uart1", "sclk_uart2", "pclk_uart2", "xin24m"}],
                registers={f"0x{a:08x}": f"0x{v:08x}" for a, v in sorted(values.items())})


if __name__ == "__main__":
    print(json.dumps(snapshot(), indent=2))
