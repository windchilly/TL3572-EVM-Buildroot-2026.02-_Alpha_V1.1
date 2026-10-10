#!/usr/bin/env python3
"""P3a all-core + OD + app force-link audit. No hardware/runtime acceptance."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from audit_powerlink_core import HAL, LIBC, forbidden_instructions
from audit_powerlink_edrv import BSP
from audit_powerlink_rtos import PLATFORM


def audit(output, toolchain):
    obj = output / "mn-passive-full.o"
    prefix = str(toolchain / "bin/aarch64-none-elf-")
    lines = subprocess.check_output([prefix + "nm", str(obj)], text=True).splitlines()
    undefined = {line.split()[-1] for line in lines if len(line.split()) == 2 and line.split()[0] == "U"}
    defined = {line.split()[-1] for line in lines if len(line.split()) == 3 and line.split()[1] == "T"}
    required = HAL | {"oplk_create", "oplk_process", "oplk_destroy", "obdcreate_initObd",
                      "m7_mn_initialize", "m7_mn_prepare", "m7_mn_process", "m7_mn_stop", "m7_mn_exit"}
    if undefined != LIBC | BSP | PLATFORM or required - defined:
        raise ValueError(f"P3a dependency boundary: undefined={sorted(undefined)} missing={sorted(required-defined)}")
    asm = subprocess.check_output([prefix + "objdump", "-d", str(obj)], text=True)
    if forbidden_instructions(asm):
        raise ValueError("FP/SIMD in full core/OD/app")
    commands = json.loads((output / "aarch64/compile_commands.json").read_text())
    if len(commands) != 77:
        raise ValueError(f"Expected 72 core + 4 port + 1 OD C files, got {len(commands)}")
    for entry in commands:
        for flag in ("-mgeneral-regs-only", "-mstrict-align", "-mno-outline-atomics"):
            if flag not in entry["command"]:
                raise ValueError(f"ABI flag absent: {flag}: {entry['file']}")
        source = Path(entry["file"])
        if source.is_relative_to(output / "source"):
            if "Redistribution and use in source and binary forms" not in source.read_text():
                raise ValueError(f"Compiled upstream source lacks BSD header: {source}")
    report = {
        "phase": "P3a passive full-stack SOFTWARE ONLY", "source_files": len(commands),
        "all_hal_defined": sorted(HAL), "unresolved": sorted(undefined),
        "object_bytes": obj.stat().st_size, "object_sha256": hashlib.sha256(obj.read_bytes()).hexdigest(),
        "no_fp_simd_posix_atomic_runtime": True,
        "rtos_owner_task_added": False, "hardware_tested": False,
        "partial_init_policy": "terminal FAULT; retain allocations/leases until reboot; no automatic retry/cleanup",
        "stop_policy": "prove EDRV and highres timer stopped before freeing user/kernel resources",
    }
    (output / "passive-mn-audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"P3a FULL STACK AUDIT PASS: {len(commands)} C sources; all HAL/OD/app present, exact {len(undefined)} unresolved BSP/libc")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("toolchain", type=Path)
    args = parser.parse_args()
    audit(args.output, args.toolchain)
