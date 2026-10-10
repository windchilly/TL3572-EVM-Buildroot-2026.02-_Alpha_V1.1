#!/usr/bin/env python3
"""P3b final ELF presence/dependency/memory audit, not a hardware test."""
import argparse
import hashlib
import json
import re
import struct
from pathlib import Path
import subprocess
from audit_powerlink_core import HAL, forbidden_instructions
from audit_powerlink_edrv import BSP
from audit_powerlink_rtos import PLATFORM
from verify_integrated_elf import symbols_and_data
from audit_integrated_mmu import audit as mmu_audit


def text_symbols(prefix, path):
    lines = subprocess.check_output([prefix + "nm", "-g", "--defined-only", str(path)], text=True).splitlines()
    return {x.split()[-1] for x in lines if len(x.split()) == 3 and x.split()[1] == "T"}


def simd_sites(assembly):
    sites = {}
    function, start = "", 0
    for line in assembly.splitlines():
        header = re.match(r"^([0-9a-f]+) <(.+)>:$", line)
        if header:
            start, function = int(header[1], 16), header[2]
        elif forbidden_instructions(line):
            opcode = re.match(r"\s*([0-9a-f]+):\s+([0-9a-f]{8})", line)
            if not function or not opcode:
                raise ValueError("Unattributed FP/SIMD instruction")
            sites[(function, int(opcode[1], 16) - start)] = opcode[2]
    return sites


def check_simd(candidate, baseline, relocated=None):
    sites, old = simd_sites(candidate), simd_sites(baseline)
    changed = [key for key, opcode in sites.items() if old.get(key) != opcode]
    if relocated:
        changed = [key for key in changed if key not in relocated or
                   relocated[key][0] != relocated[key][1]]
    if changed:
        raise ValueError(f"NEW/changed FP/SIMD in UP2: {changed[:8]}")
    return sites


def read_address(path, address, length):
    data = path.read_bytes()
    offset = struct.unpack_from("<Q", data, 32)[0]
    stride, count = struct.unpack_from("<HH", data, 54)
    for i in range(count):
        kind, flags, start, va, pa, size, memory, align = struct.unpack_from("<II6Q", data, offset + i * stride)
        if kind == 1 and va <= address and address + length <= va + size:
            return data[start + address - va:start + address - va + length]
    raise ValueError("FP literal address outside file-backed PT_LOAD")


def inherited_literal(path, load_offset, adrp_offset):
    # Exactly two relocation-bearing loads in pinned M6 PRT_cvt. Verify opcode
    # registers AND target literal bytes, not merely strip every LDR immediate.
    start, size, code = symbols_and_data(path)["PRT_cvt"]
    load = struct.unpack_from("<I", code, load_offset)[0]
    adrp = struct.unpack_from("<I", code, adrp_offset)[0]
    if load & 0xffc003e0 != 0xfd400000 or adrp & 0x9f00001f != 0x90000000:
        raise ValueError("Pinned PRT_cvt literal load/base changed")
    immediate = ((adrp >> 5) & 0x7ffff) << 2 | ((adrp >> 29) & 3)
    if immediate & (1 << 20): immediate -= 1 << 21
    address = ((start + adrp_offset) & ~4095) + immediate * 4096 + ((load >> 10) & 4095) * 8
    return load & 0xffc003ff, read_address(path, address, 8)


def audit(build, full, toolchain, baseline):
    prefix = str(toolchain / "bin/aarch64-none-elf-")
    required = text_symbols(prefix, full) | HAL | BSP | PLATFORM | {
        "Rk3572PowerlinkInit", "Rk3572PowerlinkInput", "Rk3572PowerlinkSnapshot"}
    images = []
    if hashlib.sha256(baseline.read_bytes()).hexdigest() != "627545f53ffba3d876973371042c70174c254734f433f01afc1b47578057e660":
        raise ValueError("Use the pinned unchanged formal UP2 ELF as SIMD baseline")
    old_asm = subprocess.check_output([prefix + "objdump", "-d", str(baseline)], text=True)
    old_simd = {}
    for role, image in (("a", 0x7b200000), ("b", 0x7c200000)):
        path = build / f"tl3572-m7-integrated-up-{role}.elf"
        symbols = symbols_and_data(path)
        undefined = subprocess.check_output([prefix + "nm", "-u", str(path)], text=True).strip()
        if undefined:
            raise ValueError(f"Final ELF unresolved: {undefined}")
        if role == "b":
            missing = required - text_symbols(prefix, path)
            if missing:
                raise ValueError(f"Final ELF dropped complete MN/OD/port/BSP functions: {sorted(missing)}")
            if symbols["ownerStack"][1] != 0x8000 or symbols["ownerStack"][0] % 16:
                raise ValueError("Owner stack layout changed")
            asm = subprocess.check_output([prefix + "objdump", "-d", str(path)], text=True)
            relocated = {("PRT_cvt", offset): (inherited_literal(path, offset, base),
                         inherited_literal(baseline, offset, base)) for offset, base in ((240,224), (396,392))}
            old_simd = check_simd(asm, old_asm, relocated)
        elif any(x in symbols for x in ("m7_mn_initialize", "Rk3572PowerlinkInit", "ownerStack")):
            raise ValueError("UP1 unexpectedly contains MN owner/stack")
        end = symbols["__os_section_end"][0]
        if not image < end <= image + 0x800000:
            raise ValueError(f"Image/BSS exceeds private reservation: {hex(end)}")
        if symbols["g_memRegion00"][1] != 0x80000:
            raise ValueError("Pinned 512KiB FSC allocator pool changed")
        runtime = build / f"up-{role}.runtime.bin"
        images.append({"role": role, "elf_bytes": path.stat().st_size,
            "elf_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "runtime_bytes": runtime.stat().st_size,
            "runtime_sha256": hashlib.sha256(runtime.read_bytes()).hexdigest(),
            "image_used_including_noload_bytes": end - image,
            "image_remaining_bytes": image + 0x800000 - end,
            "fsc_pool_bytes": 0x80000, "page_tables": mmu_audit(path)})
    report = {"phase": "P3b final cumulative SOFTWARE ONLY", "images": images,
        "complete_global_functions_retained_in_UP2": len(required),
        "all_hal_bsp_resolved": True, "final_undefined_symbols": [],
        "no_NEW_fp_simd_in_final_UP2": True, "hardware_tested": False,
        "inherited_simd_instruction_count": len(old_simd),
        "inherited_simd_functions": sorted({x[0] for x in old_simd}),
        "simd_limit": "Pinned M6/libmetal instructions remain; site/opcode matches formal UP2 except exactly two PRT_cvt literal-load relocations checked by registers+literal bytes. NOT an all-ELF no-FPU claim.",
        "default": "dormant; no stack environment init/prepare/PHY/CNTP/NMT/TX",
        "commands": ["PLK status", "PLK env-init", "PLK env-exit"],
        "limits": "single non-SMP owner; one pending OR running; 32KiB static stack; 2 tick idle polling, NOT cyclic timing"}
    (build / "owner-audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"P3b FINAL ELF AUDIT PASS: {len(required)} complete global functions, zero unresolved, private memory fits; {len(old_simd)} inherited SIMD instructions, zero NEW")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("build", type=Path); p.add_argument("full", type=Path); p.add_argument("toolchain", type=Path)
    p.add_argument("baseline", type=Path)
    a = p.parse_args(); audit(a.build, a.full, a.toolchain, a.baseline)
