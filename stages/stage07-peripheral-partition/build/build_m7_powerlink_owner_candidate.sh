#!/usr/bin/env bash
# P3b final cumulative candidate link. No board connection/formal replacement.
set -euo pipefail
readonly stage_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
readonly uni=${UNIPROTON_ROOT:?Set a NEW candidate UNIPROTON_ROOT}
readonly output=${POWERLINK_BUILD_ROOT:?Set the verified P3a software build root}
readonly toolchain=${TOOLCHAIN_PATH:-/home/openeuler/build/tl3572-2oo3/toolchain-14.3}
test -f "$output/mn-passive-full.o"
python3 "$stage_root/tests/audit_powerlink_passive_mn.py" "$output" "$toolchain"
POWERLINK_BUILD_ROOT="$output/p2" bash "$stage_root/build/build_m7_powerlink_rtos_candidate.sh"
readonly demo="$uni/demos/rk3572_mica"
readonly app="$demo/apps/openamp"
for source in rk3572_powerlink_app.c rk3572_powerlink_app.h; do
    install -m 0644 "$stage_root/source/overlay/uniproton/demos/rk3572_mica/apps/openamp/$source" "$app/$source"
done
install -m 0644 "$stage_root/source/powerlink/port/m7_mn.h" "$app/powerlink-port/m7_mn.h"
git -C "$uni" apply --check "$stage_root/source/patches/uniproton/0013-rk3572-powerlink-owner-dormant.patch"
git -C "$uni" apply "$stage_root/source/patches/uniproton/0013-rk3572-powerlink-owner-dormant.patch"
for name in up-a up-b; do
    if [[ "$name" == up-a ]]; then cpu=4; sgi=8; image=0x7b200000; mmu=0x7ba00000
    else cpu=5; sgi=9; image=0x7c200000; mmu=0x7ca00000; fi
    build="$demo/build/m7-powerlink-p3b-$name"
    cmake -S "$demo" -B "$build" -DAPP:STRING=rk3572_mica -DTOOLCHAIN_PATH:STRING="$toolchain" \
        -DMCS_CLIENT_CPU_ID:STRING="$cpu" -DMCS_NOTIFY_SGI_ID:STRING="$sgi" \
        -DMCS_IMAGE_ADDR:STRING="$image" -DMCS_MMU_ADDR:STRING="$mmu" \
        -DM7_CAN_DIRECT_TEST:BOOL=OFF -DM7_CAN_IRQ_TEST:BOOL=OFF \
        -DM7_INTEGRATED_FIRMWARE:BOOL=ON -DM7_POWERLINK_EDRV:BOOL=ON -DM7_POWERLINK_RTOS:BOOL=ON \
        -DM7_POWERLINK_MN:BOOL=ON -DM7_POWERLINK_OBJECT:FILEPATH="$output/mn-passive-full.o"
    cmake --build "$build" --target rk3572_mica --parallel
    cp "$build/rk3572_mica" "$demo/build/tl3572-m7-integrated-$name.elf"
    "$toolchain/bin/aarch64-none-elf-objcopy" -O binary "$build/rk3572_mica" "$demo/build/$name.runtime.bin"
    sha256sum "$demo/build/tl3572-m7-integrated-$name.elf" "$demo/build/$name.runtime.bin"
done
python3 "$stage_root/tests/audit_integrated_mmu.py" --firmware-dir "$demo/build"
python3 "$stage_root/tests/verify_integrated_elf.py" --firmware-dir "$demo/build"
python3 "$stage_root/tests/audit_powerlink_owner.py" "$demo/build" "$output/mn-passive-full.o" "$toolchain" \
    "$stage_root/firmware/tl3572-m7-integrated-up-b.elf"
echo 'P3b FINAL CUMULATIVE LINK PASS; dormant owner/software mailbox only, no hardware acceptance/deployment'
