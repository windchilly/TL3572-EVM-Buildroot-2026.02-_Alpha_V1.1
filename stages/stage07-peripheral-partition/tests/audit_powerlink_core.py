#!/usr/bin/env python3
"""P0 ABI, dependency, license and no-FP audit; does not claim a runnable MN."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess

LIBC = {"calloc", "free", "malloc", "memcmp", "memcpy", "memset", "strlen", "strncpy"}
HAL = {
    "edrv_allocTxBuffer", "edrv_changeRxFilter", "edrv_clearRxMulticastMacAddr",
    "edrv_exit", "edrv_freeTxBuffer", "edrv_getMacAddr", "edrv_init",
    "edrv_sendTxBuffer", "edrv_setRxMulticastMacAddr",
    "hrestimer_controlExtSyncIrq", "hrestimer_deleteTimer", "hrestimer_exit",
    "hrestimer_init", "hrestimer_modifyTimer",
    "m7_powerlink_cache_flush", "m7_powerlink_cache_invalidate",
    "target_cleanup", "target_createMutex", "target_destroyMutex",
    "target_enableGlobalInterrupt", "target_getTickCount", "target_init",
    "target_lockMutex", "target_msleep", "target_unlockMutex",
}


def check_undefined(symbols):
    unexpected = symbols - LIBC - HAL
    missing = HAL - symbols
    if unexpected or missing:
        raise ValueError(f"Dependency boundary changed: unexpected={sorted(unexpected)}, missing={sorted(missing)}")


def forbidden_instructions(disassembly):
    bad = []
    for line in disassembly.splitlines():
        match = re.match(r"\s*[0-9a-f]+:\s+[0-9a-f]{8}\s+(\S+)\s*(.*)", line)
        if not match:
            continue
        mnemonic, operands = match.groups()
        if (mnemonic.startswith("f")
                or re.search(r"\bv\d+\.", operands)
                or (mnemonic.startswith(("ld", "st", "mov"))
                    and re.match(r"[vqsdbh]\d+\b", operands))):
            bad.append(line)
    return bad


def audit(output, toolchain):
    core = output / "aarch64/mn-core.o"
    library = output / "aarch64/libm7_powerlink_mn_core.a"
    header = core.read_bytes()[:64]
    if (header[:6] != b"\x7fELF\x02\x01"
            or struct.unpack_from("<HH", header, 16) != (1, 183)):
        raise ValueError("Core must be ELF64 little-endian AArch64 relocatable")
    prefix = str(toolchain / "bin/aarch64-none-elf-")
    undefined_text = subprocess.check_output([prefix + "nm", "-u", str(core)], text=True)
    undefined = {line.split()[-1] for line in undefined_text.splitlines() if line.strip()}
    check_undefined(undefined)
    disassembly = subprocess.check_output([prefix + "objdump", "-d", str(core)], text=True)
    bad = forbidden_instructions(disassembly)
    if bad:
        raise ValueError("FP/SIMD instructions violate cumulative firmware ABI: " + str(bad[:8]))
    commands = json.loads((output / "aarch64/compile_commands.json").read_text())
    source_root = (output / "source/openPOWERLINK_V2-2.7.2").resolve()
    source_list = []
    for command in commands:
        source = Path(command["file"]).resolve()
        relative = source.relative_to(source_root)
        text = source.read_text(encoding="utf-8")
        if "Redistribution and use in source and binary forms" not in text:
            raise ValueError(f"Review non-BSD source before use: {relative}")
        for flag in ("-mgeneral-regs-only", "-mno-outline-atomics", "-mstrict-align", "-DOPLK_TARGET_UNIPROTON"):
            if flag not in command["command"]:
                raise ValueError(f"Required ABI flag missing: {flag}")
        source_list.append({"path": relative.as_posix(), "sha256": hashlib.sha256(source.read_bytes()).hexdigest()})
    report = {
        "phase": "P0 only; NOT runnable firmware; NO board test",
        "architecture": "AArch64 ELF64 little-endian; general registers only",
        "source_files": len(source_list), "sources": sorted(source_list, key=lambda item: item["path"]),
        "compiled_sources_license": "BSD headers present; full archive includes other platform licenses",
        "library_bytes": library.stat().st_size,
        "library_sha256": hashlib.sha256(library.read_bytes()).hexdigest(),
        "unresolved_hal": sorted(HAL), "unresolved_libc": sorted(undefined & LIBC),
        "no_linux_socket_pcap_pthread_file_io_or_libatomic_dependency": True,
        "no_fp_simd_instructions": True,
    }
    (output / "core-audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"P0 AUDIT PASS: {len(source_list)} BSD-header sources; {len(HAL)} unresolved HAL + {len(undefined & LIBC)} libc; no FP/SIMD/POSIX; {report['library_sha256']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("toolchain", type=Path)
    args = parser.parse_args()
    audit(args.output, args.toolchain)
