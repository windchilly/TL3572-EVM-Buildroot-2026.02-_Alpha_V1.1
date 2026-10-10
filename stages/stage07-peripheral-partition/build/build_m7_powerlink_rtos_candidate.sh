#!/usr/bin/env bash
# P2 builds upon P1 in a fresh UniProton tree. Formal firmware/ is not modified.
set -euo pipefail
readonly stage_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
readonly uni=${UNIPROTON_ROOT:?Set a NEW candidate UNIPROTON_ROOT}
readonly output=${POWERLINK_BUILD_ROOT:?Set the verified P2 software build root}
readonly toolchain=${TOOLCHAIN_PATH:-/home/openeuler/build/tl3572-2oo3/toolchain-14.3}
export OPLK_SOURCE="$output/p1/core/source/openPOWERLINK_V2-2.7.2"
bash "$stage_root/build/build_m7_powerlink_candidate.sh"
readonly demo="$uni/demos/rk3572_mica"
readonly app="$demo/apps/openamp"
install -m 0644 "$stage_root/source/overlay/uniproton/demos/rk3572_mica/apps/openamp/rk3572_powerlink_rtos.c" "$app/rk3572_powerlink_rtos.c"
for source in target-uniproton.c hrestimer-rk3572.c m7_plk_platform.h m7_plk_rtos.h m7_plk_cache.h m7_plk_gic.h; do
    install -m 0644 "$stage_root/source/powerlink/port/$source" "$app/powerlink-port/$source"
done
git -C "$uni" apply --check "$stage_root/source/patches/uniproton/0012-rk3572-powerlink-rtos-dormant.patch"
git -C "$uni" apply "$stage_root/source/patches/uniproton/0012-rk3572-powerlink-rtos-dormant.patch"
python3 "$stage_root/tests/audit_powerlink_rtos_abi.py" "$uni" "$toolchain" "$demo/build/rtos-abi.json"
for name in up-a up-b; do
    if [[ "$name" == up-a ]]; then cpu=4; sgi=8; image=0x7b200000; mmu=0x7ba00000
    else cpu=5; sgi=9; image=0x7c200000; mmu=0x7ca00000; fi
    build="$demo/build/m7-powerlink-p2-$name"
    cmake -S "$demo" -B "$build" -DAPP:STRING=rk3572_mica -DTOOLCHAIN_PATH:STRING="$toolchain" \
        -DMCS_CLIENT_CPU_ID:STRING="$cpu" -DMCS_NOTIFY_SGI_ID:STRING="$sgi" \
        -DMCS_IMAGE_ADDR:STRING="$image" -DMCS_MMU_ADDR:STRING="$mmu" \
        -DM7_CAN_DIRECT_TEST:BOOL=OFF -DM7_CAN_IRQ_TEST:BOOL=OFF \
        -DM7_INTEGRATED_FIRMWARE:BOOL=ON -DM7_POWERLINK_EDRV:BOOL=ON -DM7_POWERLINK_RTOS:BOOL=ON
    cmake --build "$build" --target rk3572_mica --parallel
    cp "$build/rk3572_mica" "$demo/build/tl3572-m7-integrated-$name.elf"
    "$toolchain/bin/aarch64-none-elf-objcopy" -O binary "$build/rk3572_mica" "$demo/build/$name.runtime.bin"
    sha256sum "$demo/build/tl3572-m7-integrated-$name.elf" "$demo/build/$name.runtime.bin"
done
python3 "$stage_root/tests/audit_integrated_mmu.py" --firmware-dir "$demo/build"
python3 "$stage_root/tests/verify_integrated_elf.py" --firmware-dir "$demo/build"
readonly objects="$demo/build/m7-powerlink-p2-up-b/apps/openamp/CMakeFiles/rpmsg.dir"
"$toolchain/bin/aarch64-none-elf-ld" -r "$output/mn-core-edrv-rtos.o" \
    "$objects/rk3572_eth_test.c.o" "$objects/rk3572_powerlink_rtos.c.o" \
    -o "$demo/build/mn-with-real-bsp.o"
python3 "$stage_root/tests/audit_powerlink_rtos.py" "$demo/build/mn-with-real-bsp.o" "$toolchain" --real-bsp
"$toolchain/bin/aarch64-none-elf-objcopy" --strip-debug "$demo/build/mn-with-real-bsp.o" "$demo/build/mn-with-real-bsp.stripped.o"
echo 'P2 REAL PLATFORM COMPILE PASS; no MN command / no hardware execution / no formal ELF replacement'
