set -eu
task_project=/home/openeuler/build/tl3572-2oo3
task_bin="$task_project/toolchain-14.3/bin/aarch64-none-elf"
task_source="$task_project/src/UniProton-m7-integrated-final-v2-20261009"
task_original="$task_source/demos/rk3572_mica/build/tl3572-m7-integrated-up-a.elf"
task_diag="$task_project/src/UniProton-m7-integrated-passive-diag-20261009/demos/rk3572_mica/build/tl3572-m7-integrated-up-a.elf"
sha256sum "$task_original" "$task_diag"
"$task_bin-nm" -n -S "$task_original" | grep -E 'g_excInfoInternal|shm_device|g_mmu_ctrl|g_mmu_page_(begin|end)'
"$task_bin-nm" -n -S "$task_diag" | grep -E 'g_excInfoInternal|shm_device|g_mmu_ctrl|g_mmu_page_(begin|end)'
"$task_bin-objdump" -d --disassemble=metal_io_init "$task_original"
"$task_bin-objdump" -d --disassemble=Start "$task_original"
sed -n '35,85p' "$task_source/demos/rk3572_mica/component/libmetal/lib/io.c"
grep -R -n '__bss_start__\|__bss_end__' "$task_source/src/arch/cpu/armv8" "$task_source/demos/rk3572_mica/bsp"
