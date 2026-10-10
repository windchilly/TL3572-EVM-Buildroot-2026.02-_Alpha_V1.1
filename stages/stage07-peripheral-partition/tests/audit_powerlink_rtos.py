#!/usr/bin/env python3
"""P2 force-link dependency audit; hardware permissions/timing NOT established."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from audit_powerlink_core import LIBC, HAL, forbidden_instructions
from audit_powerlink_edrv import BSP

PLATFORM = {
    "m7_plk_task_id", "m7_plk_in_interrupt", "m7_plk_irq_enabled", "m7_plk_irq_save", "m7_plk_irq_restore",
    "m7_plk_milliseconds", "m7_plk_sleep", "m7_plk_sem_create", "m7_plk_sem_take",
    "m7_plk_sem_give", "m7_plk_sem_delete", "m7_plk_cache", "m7_plk_timer_acquire",
    "m7_plk_timer_release", "m7_plk_timer_now", "m7_plk_timer_arm", "m7_plk_timer_mask",
}
RTOS = {
    "PRT_Printf", "PRT_TaskDelay", "PRT_TaskSelf", "PRT_TickGetCount", "PRT_HwiLock",
    "PRT_HwiRestore", "PRT_HwiSetAttr", "PRT_HwiCreate", "PRT_SemCreate",
    "PRT_SemPend", "PRT_SemPost", "PRT_SemDelete", "g_uniFlag",
}


def audit(object_file, toolchain, real_bsp):
    prefix = str(toolchain / "bin/aarch64-none-elf-")
    lines = subprocess.check_output([prefix + "nm", str(object_file)], text=True).splitlines()
    undefined = {line.split()[-1] for line in lines if len(line.split()) == 2 and line.split()[0] == "U"}
    defined = {line.split()[-1] for line in lines if len(line.split()) == 3 and line.split()[1] == "T"}
    expected = LIBC | (RTOS if real_bsp else PLATFORM | BSP)
    required = HAL | (PLATFORM | BSP if real_bsp else set())
    if undefined != expected or required - defined:
        raise ValueError(f"P2 boundary changed: undefined={sorted(undefined)}, missing={sorted(required-defined)}")
    assembly = subprocess.check_output([prefix + "objdump", "-d", str(object_file)], text=True)
    if forbidden_instructions(assembly):
        raise ValueError("FP/SIMD instructions found")
    if real_bsp:
        for instruction in ("cntp_ctl_el0", "cntp_cval_el0", "cntpct_el0", "cvac", "civac"):
            if instruction not in assembly.lower():
                raise ValueError(f"Real platform instruction absent: {instruction}")
    result = {
        "phase": "P2 software only; dormant cumulative candidate" if real_bsp else "P2 portable target/timer",
        "core_hal_defined": sorted(HAL), "platform_defined": sorted(PLATFORM) if real_bsp else [],
        "unresolved": sorted(undefined), "no_fp_simd_posix_atomic_runtime": True,
        "object_bytes": object_file.stat().st_size,
        "object_sha256": hashlib.sha256(object_file.read_bytes()).hexdigest(),
        "timer": "UP2 CNTP/PPI30; CNTV/PPI27 untouched; handler reserved until reboot",
        "hardware_permissions_verified": False, "hardware_latency_verified": False,
        "mn_runtime_integrated": False,
    }
    object_file.with_suffix(".json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"P2 AUDIT PASS: {len(HAL)} HAL implemented; {len(undefined)} exact dependencies; real_bsp={real_bsp}; NOT hardware acceptance")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("toolchain", type=Path)
    parser.add_argument("--real-bsp", action="store_true")
    args = parser.parse_args()
    audit(args.output if args.real_bsp else args.output / "mn-core-edrv-rtos.o", args.toolchain, args.real_bsp)
