#!/usr/bin/env bash
set -euo pipefail
task_project=/home/openeuler/build/tl3572-2oo3
task_bin="$task_project/toolchain-14.3/bin/aarch64-none-elf"
task_root="$task_project/src/UniProton-m7-integrated-mmu-fix-v2-20261009"
for task_up in up-a up-b; do
    task_image="$task_root/demos/rk3572_mica/build/tl3572-m7-integrated-$task_up.elf"
    sha256sum "$task_image"
    "$task_bin-nm" -n -S "$task_image" | grep -E 'Start$|MmuBoot|UpLogMmu|g_mmu_(page|boot)'
    "$task_bin-objdump" -d --disassemble=Start "$task_image"
    "$task_bin-objdump" -d --disassemble=MmuBootFatal "$task_image"
done
"$task_bin-objdump" -d --disassemble=UpLogMmuFailure "$task_root/demos/rk3572_mica/build/tl3572-m7-integrated-up-a.elf"
cat "$task_root/demos/rk3572_mica/build/m7-integrated-up-a/bsp/CMakeFiles/bsp.dir/flags.make"
sha256sum "$task_project/src/UniProton/demos/rk3572_mica/libs/"*
sha256sum "$task_root/demos/rk3572_mica/libs/"*
