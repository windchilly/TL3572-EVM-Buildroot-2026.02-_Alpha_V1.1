#!/bin/bash
# Stage4 v4 recon: CMDLINE_PARTITION semantics + where v3 FIT was assembled
K=/home/openeuler/build/tl3572-2oo3/build-kernel

echo ====KCONFIG_DEF
grep -rn --include="Kconfig*" -B2 -A12 "config CMDLINE_PARTITION" "$K/arch/arm64/" "$K/init/" 2>/dev/null | head -40

echo ====CODE_REFS
grep -rn "CMDLINE_PARTITION\|cmdline_partition" "$K/init/main.c" "$K/arch/arm64/kernel/setup.c" "$K/drivers/of/fdt.c" 2>/dev/null | head -10

echo ====ARM64_KCONFIG_CHOICE
grep -n -A6 "prompt \"Kernel command line type\"" "$K/arch/arm64/Kconfig" 2>/dev/null | head -20

echo ====V3_ASSEMBLY_DIRS
find /home/openeuler -maxdepth 4 -type d -newermt "2026-09-16 15:20" 2>/dev/null | grep -v "/tl3572-2oo3/src/" | head -20

echo ====V3_FILES
find /home/openeuler -maxdepth 5 -type f -size -600k -newermt "2026-09-16 15:30" 2>/dev/null | grep -vE "/src/|/build-kernel/|\.git/" | head -40
