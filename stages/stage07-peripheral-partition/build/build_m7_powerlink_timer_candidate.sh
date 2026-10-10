#!/usr/bin/env bash
# Fresh M6/cumulative/P3b -> explicit P3c diagnostic; never install on board.
set -euo pipefail
readonly stage=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
readonly uni=${UNIPROTON_ROOT:?Set a NEW candidate root}
readonly output=${POWERLINK_BUILD_ROOT:?Set verified P3a software root}
readonly toolchain=${TOOLCHAIN_PATH:-/home/openeuler/build/tl3572-2oo3/toolchain-14.3}
bash "$stage/build/build_m7_powerlink_owner_candidate.sh"
readonly demo="$uni/demos/rk3572_mica"
readonly app="$demo/apps/openamp"
install -m 0644 "$stage/source/powerlink/port/m7_timer_probe.h" "$app/powerlink-port/m7_timer_probe.h"
"$toolchain/bin/aarch64-none-elf-gcc" -std=c11 -O2 -g -Wall -Wextra -Werror \
    -mcpu=cortex-a53 -mgeneral-regs-only -mstrict-align -mno-outline-atomics \
    -DOPLK_TARGET_UNIPROTON -DCONFIG_MN -include common/oplkinc.h \
    -I "$stage/source/powerlink/port" -I "$output/source/openPOWERLINK_V2-2.7.2/stack/include" \
    -I "$output/source/openPOWERLINK_V2-2.7.2/contrib" \
    -c "$stage/source/powerlink/port/m7_timer_probe.c" -o "$demo/build/timer-probe.o"
git -C "$uni" apply --check "$stage/source/patches/uniproton/0014-rk3572-powerlink-timer-probe.patch"
git -C "$uni" apply "$stage/source/patches/uniproton/0014-rk3572-powerlink-timer-probe.patch"
readonly build="$demo/build/m7-powerlink-p3c-up-b"
cmake -S "$demo" -B "$build" -DAPP:STRING=rk3572_mica -DTOOLCHAIN_PATH:STRING="$toolchain" \
    -DMCS_CLIENT_CPU_ID:STRING=5 -DMCS_NOTIFY_SGI_ID:STRING=9 \
    -DMCS_IMAGE_ADDR:STRING=0x7c200000 -DMCS_MMU_ADDR:STRING=0x7ca00000 \
    -DM7_CAN_DIRECT_TEST:BOOL=OFF -DM7_CAN_IRQ_TEST:BOOL=OFF \
    -DM7_INTEGRATED_FIRMWARE:BOOL=ON -DM7_POWERLINK_EDRV:BOOL=ON -DM7_POWERLINK_RTOS:BOOL=ON \
    -DM7_POWERLINK_MN:BOOL=ON -DM7_POWERLINK_OBJECT:FILEPATH="$output/mn-passive-full.o" \
    -DM7_POWERLINK_TIMER_PROBE:BOOL=ON -DM7_POWERLINK_TIMER_OBJECT:FILEPATH="$demo/build/timer-probe.o"
cmake --build "$build" --target rk3572_mica --parallel
cp "$build/rk3572_mica" "$demo/build/tl3572-m7-integrated-up-b.elf"
"$toolchain/bin/aarch64-none-elf-objcopy" -O binary "$build/rk3572_mica" "$demo/build/up-b.runtime.bin"
python3 "$stage/tests/audit_powerlink_timer.py" "$demo/build" "$output/mn-passive-full.o" "$toolchain" \
    "$stage/firmware/tl3572-m7-integrated-up-b.elf"
echo 'P3c TIMER CANDIDATE SOFTWARE PASS; hardware acceptance requires explicit board test'
