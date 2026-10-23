#!/usr/bin/env bash
# P3h SOFTWARE ONLY: full OD preserved, UP2-only explicit 1MiB FSC option.
set -euo pipefail
readonly stage=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
readonly uni=${UNIPROTON_ROOT:?Set a NEW candidate root}
readonly output=${POWERLINK_BUILD_ROOT:?Set fresh rebuilt P3h full software root}
readonly toolchain=${TOOLCHAIN_PATH:-/home/openeuler/build/tl3572-2oo3/toolchain-14.3}
bash "$stage/build/build_m7_powerlink_nmt_probe_candidate.sh"
# Full context also accounts for the preceding integrated task-count patch.
git -C "$uni" apply --check "$stage/source/patches/uniproton/0020-rk3572-powerlink-nmt-heap.patch"
git -C "$uni" apply "$stage/source/patches/uniproton/0020-rk3572-powerlink-nmt-heap.patch"
readonly demo="$uni/demos/rk3572_mica"
readonly build="$demo/build/m7-powerlink-p3h-up-b"
cmake -S "$demo" -B "$build" -DAPP:STRING=rk3572_mica -DTOOLCHAIN_PATH:STRING="$toolchain" \
    -DCMAKE_EXPORT_COMPILE_COMMANDS:BOOL=ON \
    -DMCS_CLIENT_CPU_ID:STRING=5 -DMCS_NOTIFY_SGI_ID:STRING=9 \
    -DMCS_IMAGE_ADDR:STRING=0x7c200000 -DMCS_MMU_ADDR:STRING=0x7ca00000 \
    -DM7_CAN_DIRECT_TEST:BOOL=OFF -DM7_CAN_IRQ_TEST:BOOL=OFF -DM7_INTEGRATED_FIRMWARE:BOOL=ON \
    -DM7_POWERLINK_EDRV:BOOL=ON -DM7_POWERLINK_RTOS:BOOL=ON -DM7_POWERLINK_MN:BOOL=ON \
    -DM7_POWERLINK_OBJECT:FILEPATH="$output/mn-passive-full.o" \
    -DM7_POWERLINK_TIMER_PROBE:BOOL=ON -DM7_POWERLINK_TIMER_OBJECT:FILEPATH="$demo/build/timer-probe.o" \
    -DM7_POWERLINK_ETH_PROBE:BOOL=ON -DM7_POWERLINK_ETH_OBJECT:FILEPATH="$demo/build/eth-probe.o" \
    -DM7_POWERLINK_EDRV_PROBE:BOOL=ON -DM7_POWERLINK_EDRV_OBJECT:FILEPATH="$demo/build/edrv-probe.o" \
    -DM7_POWERLINK_MN_PROBE:BOOL=ON -DM7_POWERLINK_MN_PROBE_OBJECT:FILEPATH="$demo/build/mn-probe.o" \
    -DM7_POWERLINK_NMT_PROBE:BOOL=ON -DM7_POWERLINK_NMT_OBJECT:FILEPATH="$demo/build/nmt-probe.o" \
    -DM7_POWERLINK_NMT_HEAP:BOOL=ON
cmake --build "$build" --target rk3572_mica --parallel
cp "$build/rk3572_mica" "$demo/build/tl3572-m7-integrated-up-b.elf"
"$toolchain/bin/aarch64-none-elf-objcopy" -O binary "$build/rk3572_mica" "$demo/build/up-b.runtime.bin"
python3 "$stage/tests/audit_powerlink_nmt_heap.py" "$demo/build" "$output/mn-passive-full.o" "$toolchain" \
    "$stage/firmware/tl3572-m7-integrated-up-b.elf"
echo 'P3h full OD/1MiB UP2 heap/first error SOFTWARE ONLY; no board deployment or NMT authority'
