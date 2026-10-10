#!/usr/bin/env python3
"""Separate P1 dependency boundary; preserves the P0 audit and evidence unchanged."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
from audit_powerlink_core import HAL, LIBC, forbidden_instructions

EDRV = {name for name in HAL if name.startswith("edrv_")}
BSP = {"m7_eth2_hw_acquire", "m7_eth2_hw_start", "m7_eth2_hw_stop",
       "m7_eth2_hw_read", "m7_eth2_hw_write"}
REMAINING = (HAL - EDRV) | BSP


def check_boundary(undefined, defined):
    if undefined - REMAINING - LIBC or REMAINING - undefined:
        raise ValueError(f"Unexpected dependency boundary: {sorted(undefined)}")
    if EDRV - defined:
        raise ValueError(f"EDRV implementations missing: {sorted(EDRV - defined)}")


def audit(output, toolchain):
    prefix = str(toolchain / "bin/aarch64-none-elf-")
    merged = output / "mn-core-edrv.o"
    header = merged.read_bytes()[:64]
    if header[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<HH", header, 16) != (1, 183):
        raise ValueError("Expected little-endian AArch64 relocatable")
    symbols = subprocess.check_output([prefix + "nm", str(merged)], text=True).splitlines()
    undefined = {line.split()[-1] for line in symbols if len(line.split()) == 2 and line.split()[0] == "U"}
    defined = {line.split()[-1] for line in symbols if len(line.split()) == 3 and line.split()[1] in {"T", "D", "B", "R"}}
    check_boundary(undefined, defined)
    disassembly = subprocess.check_output([prefix + "objdump", "-d", str(merged)], text=True)
    if forbidden_instructions(disassembly):
        raise ValueError("FP/SIMD instructions present")
    commands = json.loads((output / "edrv-aarch64/compile_commands.json").read_text())
    if len(commands) != 1 or Path(commands[0]["file"]).name != "edrv-rk3572.c":
        raise ValueError("Unexpected EDRV sources")
    for flag in ("-Werror", "-mgeneral-regs-only", "-mno-outline-atomics", "-mstrict-align", "-DOPLK_TARGET_UNIPROTON"):
        if flag not in commands[0]["command"]:
            raise ValueError(f"Missing flag: {flag}")
    library = output / "edrv-aarch64/libm7_powerlink_eth2_edrv.a"
    report = {
        "phase": "P1 software baseline, BSP still unresolved here; no board test; NOT runnable MN",
        "edrv_defined": sorted(EDRV), "unresolved_hal": sorted(REMAINING),
        "unresolved_libc": sorted(undefined & LIBC),
        "dma_bytes": 61696, "tx_buffers": 32, "tx_ring": 8, "rx_ring": 8,
        "no_fp_simd_or_posix_dependencies": True,
        "library_bytes": library.stat().st_size,
        "library_sha256": hashlib.sha256(library.read_bytes()).hexdigest(),
        "merged_sha256": hashlib.sha256(merged.read_bytes()).hexdigest(),
        "edrv_source_sha256": hashlib.sha256(Path(commands[0]["file"]).read_bytes()).hexdigest(),
    }
    (output / "edrv-audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"P1 AUDIT PASS: {len(EDRV)} EDRV defined, {len(REMAINING)} real unresolved HAL, no FP/SIMD/POSIX; {report['library_sha256']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("toolchain", type=Path)
    args = parser.parse_args()
    audit(args.output, args.toolchain)
