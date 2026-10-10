#!/usr/bin/env python3
"""Check the pinned non-SMP RTOS archive supplies real P2 APIs and allocators."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from audit_powerlink_rtos import RTOS
from audit_powerlink_core import LIBC


def audit(uni, toolchain):
    demo = uni / "demos/rk3572_mica"
    archive = demo / "libs/libRK3572.a"
    flags = (uni / "src/arch/include/prt_asm_cpu_external.h").read_text()
    for name, value in (("HWI", "0x0001"), ("TICK", "0x0008"), ("SYS", "0x0010"), ("EXC", "0x0020")):
        if f"#define OS_FLG_{name}_ACTIVE {value}" not in flags:
            raise ValueError("Private context flag ABI changed; review BSP before build/deploy")
    lines = subprocess.check_output([str(toolchain / "bin/aarch64-none-elf-nm"), "--defined-only", str(archive)], text=True)
    defined = {line.split()[-1] for line in lines.splitlines() if len(line.split()) == 3}
    required = (RTOS - {"PRT_Printf"}) | LIBC | {"PRT_MemAlloc", "PRT_MemFree"}
    missing = required - defined
    if missing:
        raise ValueError(f"Pinned RTOS library missing implementations: {sorted(missing)}")
    return {"phase": "P2 static RTOS ABI only, not an executed allocation/IRQ test",
            "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            "required_symbols_defined": sorted(required), "context_flags_verified": True,
            "allocator": "pinned libc malloc -> PRT_MemAlloc default FSC; existing UP2 image heap",
            "ppis": "do not use generic GICR disable/delete; banked GICv2 PPI30 only"}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("uni", type=Path); p.add_argument("toolchain", type=Path); p.add_argument("report", type=Path)
    a = p.parse_args()
    a.report.write_text(json.dumps(audit(a.uni, a.toolchain), indent=2) + "\n", encoding="utf-8")
    print("P2 RTOS ABI PASS: private flags and real kernel/libc symbols present; NOT hardware acceptance")
