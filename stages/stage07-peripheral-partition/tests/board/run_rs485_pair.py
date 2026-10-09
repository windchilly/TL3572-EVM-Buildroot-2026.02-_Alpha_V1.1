#!/usr/bin/env python3
"""Temporary UP1/UART1 <-> UP2/UART2 half-duplex IRQ RS485 test; no Linux serial traffic."""
import argparse
import mmap
import os
from pathlib import Path
import re
import struct
import subprocess
import time

import rs485_resources as resources
import run_can_direct_pair as common

DRIVER = Path("/sys/bus/platform/drivers/dw-apb-uart")
TEST_ROOT = Path("/root/m7-rs485-20261009")


def write_register(address, value, byte=False):
    page = address & ~(mmap.PAGESIZE - 1)
    descriptor = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
    try:
        with mmap.mmap(descriptor, mmap.PAGESIZE, flags=mmap.MAP_SHARED,
                       prot=mmap.PROT_READ | mmap.PROT_WRITE, offset=page) as region:
            struct.pack_into("<B" if byte else "<I", region, address - page, value)
            struct.unpack_from("<B" if byte else "<I", region, address - page)
    finally:
        os.close(descriptor)


def hiword(address, mask, value):
    write_register(address, (mask << 16) | (value & mask))


def validate_result(text_a, text_b, baud):
    targets = []
    divisor = {115200: 13, 38400: 39, 9600: 156}[baud]
    for up, text, name in ((1, text_a, "up-a"), (2, text_b, "up-b")):
        p = resources.RESOURCES[name]
        before = re.search(rf"\[rs485\] UP{up} before pgate=0x([0-9a-f]+) sgate=0x([0-9a-f]+) "
                           r"preset=0x([0-9a-f]+) sreset=0x([0-9a-f]+) select=0x([0-9a-f]+)", text)
        if not before:
            raise RuntimeError(f"UP{up}: missing disabled-resource evidence")
        values = [int(v, 16) for v in before.groups()]
        if any(values[i] & mask != mask for i, mask in enumerate(
                (p["p_mask"], p["s_mask"], p["p_mask"], p["s_mask"]))):
            raise RuntimeError(f"UP{up}: gates/resets were not disabled/asserted")
        if values[4] & p["select_mask"] != p["disabled_select"]:
            raise RuntimeError(f"UP{up}: deliberate wrong clock selector/divider not evidenced")
        ready = re.search(rf"\[rs485\] UP{up} ready uart={p['uart']} mpidr=0x{0x100 + up - 1:x} "
                          rf"intid={p['spi'] + 32} target=0x([0-9a-f]+) baud={baud} "
                          rf"clock=24000000 divisor={divisor} lcr=0x3", text)
        counts = re.search(rf"\[rs485\] UP{up} counts irq=(\d+) txirq=(\d+) rxirq=(\d+) "
                           r"txbytes=(\d+) rxbytes=(\d+) err=0x([0-9a-f]+) overflow=(\d+) "
                           r"wrongcpu=(\d+) busy=(\d+) storm=(\d+) target=0x([0-9a-f]+)", text)
        if not ready or not counts:
            raise RuntimeError(f"UP{up}: missing/incorrect initialization or IRQ counters")
        numbers = [int(v, 16 if i in (5, 10) else 10) for i, v in enumerate(counts.groups())]
        irq, tx, rx, txbytes, rxbytes = numbers[:5]
        target = numbers[10]
        if (irq == 0 or tx < 32000 or rx == 0 or txbytes != 32000 or rxbytes != 32000 or
                any(numbers[5:10]) or not target or target & (target - 1) or
                target != int(ready.group(1), 16)):
            raise RuntimeError(f"UP{up}: invalid UART IRQ counters: {counts.group(0)}")
        if f"[rs485] UP{up} direct PASS baud={baud} tx=1000 rx=1000 bytes=32 rc=0" not in text:
            raise RuntimeError(f"UP{up}: missing exact sequence/CRC-tested PASS")
        direction = f"[rs485] UP{up} direction tx=1000 rx=1002 err=0 mcr=0x2 guardticks=4"
        if direction not in text:
            raise RuntimeError(f"UP{up}: missing exact half-duplex direction validation")
        targets.append(target)
    if targets[0] == targets[1]:
        raise RuntimeError("both UP instances routed serial IRQ to the same CPU target")
    print(f"UART IRQ VALIDATION PASS targets={targets}; 1000 frames/32000 bytes each direction", flush=True)


def check_uart_free():
    clocks = Path("/sys/kernel/debug/clk/clk_summary").read_text()
    if not re.search(r"^\s*xin24m\s+\d+\s+\d+\s+\d+\s+24000000\s", clocks, re.M):
        raise RuntimeError("xin24m must be 24 MHz")
    cmdline = Path("/proc/cmdline").read_text()
    for p in resources.RESOURCES.values():
        dev = Path("/sys/bus/platform/devices") / p["device"]
        if not (dev / "driver").exists() or (dev / "driver").resolve().name != DRIVER.name:
            raise RuntimeError(f"{p['device']}: original Linux UART driver not bound")
        tty = Path("/sys/class/tty") / p["tty"] / "device"
        # Kernel 6.12 serial core inserts serial-controller/serial-port children.
        if dev.resolve() not in tty.resolve().parents:
            raise RuntimeError(f"{p['tty']}: wrong controller mapping {tty.resolve()}")
        if re.search(rf"console={p['tty']}\b", cmdline):
            raise RuntimeError(f"{p['tty']} is a system console")
        result = subprocess.run(["fuser", "-v", f"/dev/{p['tty']}"], text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=10)
        if result.returncode != 1 or result.stdout.strip():
            raise RuntimeError(f"{p['tty']}: occupied or fuser failed: {result.stdout}")
    pinmux = Path("/sys/kernel/debug/pinctrl/pinctrl-rockchip-pinctrl/pinmux-pins").read_text()
    for p in resources.RESOURCES.values():
        line = next((line for line in pinmux.splitlines()
                     if re.match(rf"pin {p['direction_pin']} ", line)), "")
        if "MUX UNCLAIMED" not in line or "GPIO UNCLAIMED" not in line:
            raise RuntimeError(f"RS485 direction pin already owned: {line}")
    print("NO Linux GPIO direction writes; RTSN exclusively controlled by UP MCR", flush=True)
    print("NO Linux serial open/stty/TX/RX preparation; UART0 untouched", flush=True)


def disable_owned(saved):
    for p in resources.RESOURCES.values():
        state = resources.decode(p, saved)
        if state["active"] or state["pending"] or state["edge"] or state["enabled"]:
            raise RuntimeError(f"UART SPI not released/quiescent/level: {state}")
    for p in resources.RESOURCES.values():
        hiword(p["p_reset"], p["p_mask"], p["p_mask"])
        hiword(p["p_gate"], p["p_mask"], p["p_mask"])
        hiword(p["s_reset"], p["s_mask"], p["s_mask"])
        hiword(p["s_gate"], p["s_mask"], p["s_mask"])
        hiword(p["select"], p["select_mask"], p["disabled_select"])
    for p in resources.RESOURCES.values():
        state = resources.decode(p, resources.read_registers())
        if not all(state[k] for k in ("p_gated", "s_gated", "p_reset", "s_reset")) or state["selector"] != p["disabled_select"]:
            raise RuntimeError(f"could not establish deliberate disabled UART state: {state}")
    print("OWNED UART clocks disabled, resets asserted, UART1=RC oscillator, UART2=xin24m /16", flush=True)


def restore_owned(saved):
    before = resources.read_registers()
    errors = []
    for p in resources.RESOURCES.values():
        state = resources.decode(p, before)
        original = resources.decode(p, saved)
        print(f"UART QUIESCE {state}", flush=True)
        if state["enabled"] or state["pending"] or state["active"] or any(
                state[k] != original[k] for k in ("priority", "target")):
            errors.append(f"UART{p['uart']}: UP did not quiesce/restore IRQ")
        intid = p["spi"] + 32
        for offset in (0x180, 0x280, 0x380):
            write_register(resources.GICD + offset + intid // 32 * 4, 1 << (intid % 32))
        for field, offset in (("target", 0x800), ("priority", 0x400)):
            write_register(resources.GICD + offset + intid, original[field], byte=True)
    masks = resources.owned_masks()
    # Restore selectors/mux, resets, then gate state, always using hiword masks.
    for address, mask in masks.items():
        hiword(address, mask, saved[address])
    current = resources.read_registers()
    for address in saved:
        if address < resources.GICD or address >= resources.GICD + 0x1000:
            if current[address] != saved[address]:
                errors.append(f"CRU/IOC resource not restored or neighbour changed at 0x{address:x}")
    for p in resources.RESOURCES.values():
        original = resources.decode(p, saved)
        final = resources.decode(p, current)
        if final != original:
            errors.append(f"UART/GIC fields not restored: {original} -> {final}")
        g = resources.gic_addresses(p["spi"] + 32)
        for field in ("group", "config", "priority", "target"):
            if current[g[field]] != saved[g[field]]:
                errors.append(f"shared GIC {field} changed at 0x{g[field]:x}")
    if errors:
        raise RuntimeError("; ".join(errors))
    print("RESOURCE RESTORE PASS UART CRU/IOC and shared GIC fields unchanged", flush=True)


def rebind_devices(devices):
    errors = []
    for device in devices:
        try:
            (DRIVER / "bind").write_text(device)
            if not (Path("/sys/bus/platform/devices") / device / "driver").exists():
                raise RuntimeError("driver remains unbound")
            print(f"REBOUND {device}", flush=True)
        except Exception as error:
            errors.append(f"{device}: {error}")
    if errors:
        raise RuntimeError("; ".join(errors))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baud", type=int, choices=(9600, 38400, 115200), default=115200)
    parser.add_argument("--stop-a-first", action="store_true")
    args = parser.parse_args()
    if os.geteuid() != 0 or mmap.PAGESIZE != 4096:
        raise SystemExit("requires root and baseline 4 KiB pages")
    clients = tuple(f"{name}-m7-rs485-{args.baud}" for name in ("up-b", "up-a"))
    configs = {name: TEST_ROOT / f"{name}.conf" for name in clients}
    common.CLIENTS = clients
    common.STOP_CLIENTS = tuple(reversed(clients)) if args.stop_a_first else clients
    baseline = common.micad_state()
    status = common.command("mcsctl", "status")
    if baseline.get("ActiveState") != "active" or status.count("Offline") != 2 or "up-a" not in status or "up-b" not in status:
        raise RuntimeError(f"unexpected baseline: {baseline}\n{status}")
    for config in configs.values():
        lines = config.read_text().splitlines()
        if "AutoBoot=no" not in lines:
            raise RuntimeError("temporary configs must have AutoBoot=no")
        images = [Path(line.split("=", 1)[1]) for line in lines if line.startswith("ClientPath=")]
        if len(images) != 1 or not images[0].is_file():
            raise RuntimeError(f"firmware missing in {config}")
    reader = common.load_log_reader()
    seq = {name: common.log_header(reader, name)[1] for name in ("up-a", "up-b")}
    common.confirm_up_cpus_off()
    check_uart_free()
    print(f"BASELINE micad={baseline} seq={seq} baud={args.baud} stop={common.STOP_CLIENTS}", flush=True)
    unbound, saved, primary, logs = [], None, None, {}
    try:
        for p in resources.RESOURCES.values():
            (DRIVER / "unbind").write_text(p["device"])
            unbound.append(p["device"])
            if (Path("/sys/bus/platform/devices") / p["device"] / "driver").exists():
                raise RuntimeError(f"UART driver remains bound: {p['device']}")
            print(f"UNBOUND {p['device']}", flush=True)
        saved = resources.read_registers()
        disable_owned(saved)
        for client in clients:
            result = common.command("mcsctl", "create", str(configs[client]))
            if "success" not in result.lower():
                raise RuntimeError(f"create {client}: {result}")
        common.control("start", clients[0]); time.sleep(1)
        common.control("start", clients[1])
        deadline = time.monotonic() + 150
        while time.monotonic() < deadline:
            logs = {name: common.new_log_messages(reader, name, seq[name]) for name in seq}
            texts = {name: "".join(message for _, _, message in entries) for name, entries in logs.items()}
            if any("direct FAIL" in text for text in texts.values()):
                raise RuntimeError("UP RS485 firmware reports failure")
            if all(f"[rs485] UP{up} direct PASS" in texts[name] for up, name in ((1, "up-a"), (2, "up-b"))):
                validate_result(texts["up-a"], texts["up-b"], args.baud)
                print(f"OVERALL PASS RS485 baud={args.baud} requests=1000 responses=1000", flush=True)
                break
            time.sleep(0.2)
        else:
            raise RuntimeError("timeout waiting for two RS485 PASS reports")
    except Exception as error:
        primary = error
    finally:
        for name, entries in logs.items():
            for serial, boot, message in entries:
                print(f"[{name} boot={boot} seq={serial}] {message}", end="" if message.endswith("\n") else "\n", flush=True)
        cleanup_errors = []
        try:
            common.cleanup_clients()
        except Exception as error:
            cleanup_errors.append(f"clients: {error}")
        cpus_off = False
        try:
            common.confirm_up_cpus_off(); cpus_off = True
        except Exception as error:
            cleanup_errors.append(f"CPU OFF not confirmed; no resource restore/rebind: {error}")
        if cpus_off:
            if saved is not None:
                try:
                    restore_owned(saved)
                except Exception as error:
                    cleanup_errors.append(f"resources: {error}")
            try:
                rebind_devices(unbound)
            except Exception as error:
                cleanup_errors.append(f"Linux drivers: {error}")
        current = common.micad_state()
        if current != baseline:
            cleanup_errors.append(f"micad changed: {baseline} -> {current}")
        if cleanup_errors:
            primary = RuntimeError(f"{primary or 'data test passed'}; cleanup: {'; '.join(cleanup_errors)}")
    if primary:
        raise primary
    print("CLEANUP PASS temporary clients removed; UART1/2 rebound; micad unchanged", flush=True)


if __name__ == "__main__":
    main()
