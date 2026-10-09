#!/usr/bin/env python3
"""Temporary IRQ test with disabled clocks/asserted resets before UP startup."""
import mmap
import argparse
import os
from pathlib import Path
import re
import struct

import can_resource_preflight as resources
import run_can_direct_pair as pair


SAVED = None
CRU_MASK = 0x6600
ORIGINAL_UNBIND = pair.unbind_controllers
ORIGINAL_RESTORE = pair.restore_controllers


def write_register(address, value, byte=False):
    page = address & ~(mmap.PAGESIZE - 1)
    descriptor = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
    try:
        with mmap.mmap(descriptor, mmap.PAGESIZE, flags=mmap.MAP_SHARED,
                       prot=mmap.PROT_READ | mmap.PROT_WRITE, offset=page) as region:
            struct.pack_into("<B" if byte else "<I", region, address - page, value)
            # Force a readback before the next MMIO operation.
            struct.unpack_from("<B" if byte else "<I", region, address - page)
    finally:
        os.close(descriptor)


def hiword(address, mask, value):
    write_register(address, (mask << 16) | (value & mask))


def prepare_without_linux_start():
    clocks = Path("/sys/kernel/debug/clk/clk_summary").read_text()
    if not re.search(r"^\s*gpll\s+\d+\s+\d+\s+\d+\s+1188000000\s", clocks, re.M):
        raise RuntimeError("test bit timing requires the unchanged GPLL at 1188 MHz")
    for interface, profile in resources.RESOURCES.items():
        device = Path(f"/sys/class/net/{interface}/device").resolve().name
        if device != profile["device"]:
            raise RuntimeError(f"{interface}: wrong controller {device}")
        pair.command("ip", "link", "set", interface, "down")
    print("NO Linux CAN up or bitrate preparation", flush=True)


def unbind_and_disable_resources():
    global SAVED
    ORIGINAL_UNBIND()
    SAVED = resources.read_registers()
    for profile in resources.RESOURCES.values():
        decoded = resources.decode_resource(profile, SAVED)
        if decoded["gic_active"] or decoded["gic_pending"] or decoded["gic_edge_triggered"]:
            raise RuntimeError(f"SPI not quiescent/level-triggered: {decoded}")
    # Only the two temporary owners' bits are modified; other channels/roots stay unchanged.
    hiword(resources.CRU + 0xA2C, CRU_MASK, CRU_MASK)
    hiword(resources.CRU + 0x82C, CRU_MASK, CRU_MASK)
    for profile in resources.RESOURCES.values():
        hiword(profile["clksel"], 0x3F80, 15 << 7)
    current = resources.read_registers()
    if (current[resources.CRU + 0x82C] & CRU_MASK != CRU_MASK or
            current[resources.CRU + 0xA2C] & CRU_MASK != CRU_MASK):
        raise RuntimeError("could not establish disabled clocks/asserted resets")
    print("OWNED resources disabled: gates/resets=0x6600; baud dividers=/16", flush=True)


def restore_after_cpu_off():
    # pair.main only calls this after querying both CPUs as PSCI OFF.
    if SAVED is not None:
        before_restore = resources.read_registers()
        quiesce_errors = []
        for profile in resources.RESOURCES.values():
            decoded = resources.decode_resource(profile, before_restore)
            saved = resources.decode_resource(profile, SAVED)
            print(f"UP IRQ QUIESCE intid={decoded['intid']} enabled={decoded['gic_enabled']} "
                  f"pending={decoded['gic_pending']} active={decoded['gic_active']} "
                  f"target={decoded['gic_target_mask']}", flush=True)
            if (decoded["gic_enabled"] or decoded["gic_pending"] or decoded["gic_active"] or
                    decoded["gic_target_mask"] != saved["gic_target_mask"] or
                    decoded["gic_priority"] != saved["gic_priority"]):
                quiesce_errors.append(f"INTID {decoded['intid']}: UP did not quiesce/restore IRQ")
        for profile in resources.RESOURCES.values():
            intid = profile["spi"] + 32
            bit = 1 << (intid % 32)
            word = (intid // 32) * 4
            gic = resources.gic_addresses(intid)
            write_register(resources.GICD + 0x180 + word, bit)
            write_register(resources.GICD + 0x280 + word, bit)
            write_register(resources.GICD + 0x380 + word, bit)
            for field in ("target", "priority"):
                value = (SAVED[gic[field]] >> ((intid % 4) * 8)) & 255
                write_register(gic[field] + (intid % 4), value, byte=True)
            if SAVED[gic["enabled"]] & bit:
                write_register(resources.GICD + 0x100 + word, bit)
            hiword(profile["clksel"], 0x3F80, SAVED[profile["clksel"]])
            hiword(profile["iomux"], profile["iomux_mask"], SAVED[profile["iomux"]])
        hiword(resources.CRU + 0xA2C, CRU_MASK, SAVED[resources.CRU + 0xA2C])
        hiword(resources.CRU + 0x82C, CRU_MASK, SAVED[resources.CRU + 0x82C])
        current = resources.read_registers()
        unowned_fields = [(resources.CRU + 0x82C, 0xFFFF & ~CRU_MASK),
                          (resources.CRU + 0xA2C, 0xFFFF & ~CRU_MASK)]
        for profile in resources.RESOURCES.values():
            unowned_fields.extend(((profile["clksel"], 0xFFFF & ~0x3F80),
                                   (profile["iomux"], 0xFFFF & ~profile["iomux_mask"])))
        for address, mask in unowned_fields:
            if (current[address] & mask) != (SAVED[address] & mask):
                quiesce_errors.append(f"unowned resource bits changed at 0x{address:x}")
        for profile in resources.RESOURCES.values():
            decoded = resources.decode_resource(profile, current)
            if decoded["gic_pending"] or decoded["gic_active"]:
                quiesce_errors.append(f"CAN SPI not quiescent after cleanup: {decoded}")
        print("RESOURCE RESTORE PASS; other CAN gate/reset bits unchanged", flush=True)
    ORIGINAL_RESTORE()
    if SAVED is not None and quiesce_errors:
        raise RuntimeError("; ".join(quiesce_errors))


def validate_irq_result(text_a, text_b):
    targets = []
    for up, text, mask in ((1, text_a, 0x0600), (2, text_b, 0x6000)):
        before = re.search(rf"\[can-irq\] UP{up} before gate=0x([0-9a-f]+) "
                           r"reset=0x([0-9a-f]+) select=0x([0-9a-f]+)", text)
        if not before or any(int(before.group(i), 16) & mask != mask for i in (1, 2)):
            raise RuntimeError(f"UP{up}: disabled clocks/asserted resets not evidenced")
        if int(before.group(3), 16) & 0x3F80 != 15 << 7:
            raise RuntimeError(f"UP{up}: test divider state not evidenced")
        report = re.search(rf"\[can-irq\] UP{up} counts irq=(\d+) txirq=(\d+) rxirq=(\d+) "
                           r"err=0x([0-9a-f]+) overflow=(\d+) wrongcpu=(\d+) target=0x([0-9a-f]+)", text)
        if report is None:
            raise RuntimeError(f"UP{up}: missing IRQ counters")
        irq, tx, rx, error, overflow, wrong, target = [int(value, 16 if index in (3, 6) else 10)
                                                     for index, value in enumerate(report.groups())]
        if tx != 10000 or rx != 10000 or irq < 10000 or error or overflow or wrong:
            raise RuntimeError(f"UP{up}: invalid IRQ counters {report.group(0)}")
        if target == 0 or target & (target - 1):
            raise RuntimeError(f"UP{up}: invalid GIC target mask")
        if f"[can] UP{up} direct PASS tx=10000 rx=10000 txerr=0 rxerr=0" not in text:
            raise RuntimeError(f"UP{up}: CAN error counters not zero")
        targets.append(target)
    if targets[0] == targets[1]:
        raise RuntimeError("two UP instances used the same GIC target bit")
    print(f"IRQ VALIDATION PASS target masks={targets}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stop-a-first", action="store_true")
    args = parser.parse_args()
    pair.TEST_ROOT = Path("/root/m7-can-irq-20261009")
    pair.CLIENTS = ("up-b-m7-can-irq", "up-a-m7-can-irq")
    pair.CONFIGS = {name: pair.TEST_ROOT / f"{name}.conf" for name in pair.CLIENTS}
    pair.EXPECTED_FRAMES = 10000
    pair.STOP_CLIENTS = tuple(reversed(pair.CLIENTS)) if args.stop_a_first else pair.CLIENTS
    print(f"STOP ORDER {pair.STOP_CLIENTS}", flush=True)
    pair.TEST_DEADLINE = 75.0
    pair.prepare_linux_controllers = prepare_without_linux_start
    pair.unbind_controllers = unbind_and_disable_resources
    pair.restore_controllers = restore_after_cpu_off
    pair.validate_result = validate_irq_result
    pair.main()


if __name__ == "__main__":
    main()
