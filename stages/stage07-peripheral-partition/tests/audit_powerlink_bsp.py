#!/usr/bin/env python3
"""Force-link audit of real UniProton EDRV+BSP objects, not discarded ELF sections."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from audit_powerlink_core import forbidden_instructions
from audit_powerlink_edrv import BSP, EDRV


def audit(object_file, toolchain):
    prefix = str(toolchain / "bin/aarch64-none-elf-")
    symbols = subprocess.check_output([prefix + "nm", str(object_file)], text=True).splitlines()
    undefined = {line.split()[-1] for line in symbols if len(line.split()) == 2 and line.split()[0] == "U"}
    defined = {line.split()[-1] for line in symbols if len(line.split()) == 3 and line.split()[1] == "T"}
    expected = {"PRT_Printf", "PRT_TaskDelay", "memcmp", "memcpy", "memset"}
    if undefined != expected or (BSP | EDRV) - defined:
        raise ValueError(f"BSP dependencies/implementations changed: undefined={sorted(undefined)}")
    disassembly = subprocess.check_output([prefix + "objdump", "-d", str(object_file)], text=True)
    if forbidden_instructions(disassembly):
        raise ValueError("FP/SIMD found in cumulative BSP/EDRV")
    report = {
        "phase": "P1 dormant cumulative candidate; compiled real BSP, no PHY/MMIO execution",
        "backend_defined": sorted(BSP), "edrv_defined": sorted(EDRV),
        "unresolved": sorted(undefined), "no_fp_simd_linux_or_atomic_runtime": True,
        "object_sha256": hashlib.sha256(object_file.read_bytes()).hexdigest(),
        "half_duplex_hardware_verified": False,
        "mn_runtime_integrated": False,
    }
    object_file.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("REAL BSP/EDRV AUDIT PASS: 14 implementations, only RTOS+libc unresolved; NOT hardware acceptance")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("object_file", type=Path)
    parser.add_argument("toolchain", type=Path)
    args = parser.parse_args()
    audit(args.object_file, args.toolchain)
